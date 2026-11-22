"""生成到 Sequencer / 烘焙动画序列。"""
import math
from pathlib import Path

import mineprep
import unreal
from mineprep import sequencer_tools
from mineprep.rig import Rig, describe_skeleton

from . import bbmodel, biped, curves, face_presets, java_clip, library, rig_rules, sampling, util


def _prepare_batches(rig, times, batches):
    prepared = {}
    for name, values in batches.items():
        name = rig._resolve_name(name)
        if len(values) != len(times):
            raise ValueError(name + ': sample count does not match times')
        if rig._type(name) != unreal.RigControlType.EULER_TRANSFORM:
            raise ValueError(name + ': numeric bone import requires EulerTransform control')
        if name in prepared:
            raise ValueError('Multiple source bones map to ' + name)
        prepared[name] = (times, values)
    return prepared


def _rig_control_aliases(rig) -> set[str] | None:
    if not hasattr(rig, 'names'):
        return None
    aliases: set[str] = set()
    for full in rig.names():
        text = str(full)
        short = text.rsplit('/', 1)[-1]
        aliases.add(text.casefold())
        aliases.add(short.casefold())
        if short.endswith('_CURVE_CONTROL'):
            aliases.add(short[:-len('_CURVE_CONTROL')].casefold())
        elif short.endswith('_CONTROL'):
            aliases.add(short[:-len('_CONTROL')].casefold())
    return aliases


def _prepare_curve_batches(rig, times, float_batches):
    prepared = {}
    for cname, values in (float_batches or {}).items():
        name = rig._resolve_name(cname)
        if len(values) != len(times):
            raise ValueError(name + ': sample count does not match times')
        if rig._type(name) not in (unreal.RigControlType.FLOAT, unreal.RigControlType.SCALE_FLOAT):
            raise ValueError(name + ': curve import requires Float control')
        if name in prepared:
            raise ValueError('Multiple source channels map to ' + name)
        prepared[name] = (times, [float(v) for v in values])
    return prepared


def _valid_time(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} 必须为有限整数帧或浮点秒')
    return value


def write_batches(rig, times, prepared, *, replace_span=True,
                  time_unit=sequencer_tools._TIME_UNIT, hold_ticks=()):
    """Replace only the prepared controls within the clip's half-open [start, end) span."""
    rig._key_batches(prepared, 'linear', replace_span=replace_span,
                     time_unit=time_unit, hold_ticks=hold_ticks)
    return sum(len(ts) for ts, _ in prepared.values())


def _matching_head_bones(head_target, reference):
    """Return child bone names shared between a split Head target and the main skeleton."""
    head = head_target if isinstance(head_target, dict) else describe_skeleton(head_target)
    if 'head' not in head or head['head']['parent'] is not None:
        raise ValueError('Head 网格需要以 head 为根骨骼')
    shared = set()
    for name, bone in head.items():
        if name == 'head':
            continue
        body = reference.get(name)
        if body is not None:
            if (body['parent'] != bone['parent']
                    or not body['local'].is_near_equal(bone['local'], 1e-4)):
                raise ValueError('头身子骨骼绑定姿势不匹配: ' + name)
            shared.add(name)
    return shared


def _head_batches(component, reference, batches):
    """Split meshes sync matching child bones; Head-exclusive bones stay untouched."""
    shared = _matching_head_bones(component, reference)
    return {name: batches[name] for name in shared if name in batches}


def _prepare_rig(rig, sequence, *, layered=False):
    """Validate or initialize one FK Control Rig track (`Replace`, `Layered`, or `'auto'`)."""
    if sequencer_tools.resolve_sequence() != sequence:
        raise RuntimeError('写键前活动关卡序列已改变，请重新调用')
    sections = rig.track.get_sections()
    if len(sections) != 1:
        raise ValueError('动画导入需要单 section 的 FK Control Rig 轨')
    lib = unreal.ControlRigSequencerLibrary
    is_layered = bool(lib.is_layered_control_rig(rig.target))
    apply_mode = lib.get_fk_control_rig_apply_mode(rig.target)
    has_keys = any(ch.get_num_keys() for ch in sections[0].get_all_channels())

    if layered == 'auto':
        # Reuse existing track mode when already keyed; prefer Layered on fresh empty tracks
        if has_keys or (is_layered and apply_mode == unreal.ControlRigFKRigExecuteMode.ADDITIVE):
            return
        want_layered = True
    else:
        want_layered = bool(layered)

    if want_layered:
        if not (is_layered and apply_mode == unreal.ControlRigFKRigExecuteMode.ADDITIVE):
            if has_keys:
                raise ValueError('已有动画的 FK Replace 轨无法直接转为分层，请取消勾选「分层绑定」或清空原轨道')
            if not lib.set_control_rig_layered_mode(rig.track, True):
                raise RuntimeError('无法切换到 Layered 分层绑定模式')
            yield
            if sequencer_tools.resolve_sequence() != sequence:
                raise RuntimeError('写键前活动关卡序列已改变，请重新调用')
            if not (lib.is_layered_control_rig(rig.target)
                    and lib.get_fk_control_rig_apply_mode(rig.target) == unreal.ControlRigFKRigExecuteMode.ADDITIVE):
                raise RuntimeError('无法切换到 Layered 分层绑定模式')
    else:
        if is_layered or apply_mode != unreal.ControlRigFKRigExecuteMode.REPLACE:
            if has_keys:
                raise ValueError('已有动画的 Layered Rig 请勾选「分层绑定」，或改用单 section 的 FK Replace 轨')
            if not lib.set_control_rig_layered_mode(rig.track, False):
                raise RuntimeError('无法切换到 FK Replace 模式')
            yield
            if sequencer_tools.resolve_sequence() != sequence:
                raise RuntimeError('写键前活动关卡序列已改变，请重新调用')
            if (lib.is_layered_control_rig(rig.target)
                    or lib.get_fk_control_rig_apply_mode(rig.target) != unreal.ControlRigFKRigExecuteMode.REPLACE):
                raise RuntimeError('无法切换到 FK Replace 模式')


def _try_sparse_curves(clip, data):
    """Return `(duration, {curve_name: (times_s, values)})` for pure-curve linear clips, else None."""
    if data.get('bones') or not data.get('curves'):
        return None
    for feature in ('animation_controllers', 'timeline', 'particle_effects', 'sound_effects'):
        if feature in data:
            return None
    raw_curves = data['curves']
    if not isinstance(raw_curves, dict) or not raw_curves:
        return None
    parsed = {}
    max_t = 0.0
    for cname, raw_val in raw_curves.items():
        keys = sampling.scalar_channel(raw_val, f'{clip}/curves/{cname}')
        for t, pre, post, mode in keys:
            if mode != 'linear' or pre != post:
                return None
        ts = [t for t, _, _, _ in keys]
        vs = [float(post[0]) for _, _, post, _ in keys]
        if ts:
            max_t = max(max_t, ts[-1])
        parsed[cname] = (ts, vs)
    anim_len = data.get('animation_length')
    duration = float(anim_len) if anim_len is not None else max_t
    if not math.isfinite(duration) or duration < 0.0:
        raise ValueError(f'{clip}: animation_length 须为非负有限数')
    return max(duration, max_t), parsed


def _place_sampled_ticks(rig, sequence, start_frame, source_times, batches, time_scale, left_indices=()):
    rate = sequence.get_tick_resolution()
    ticks_per_second = rate.numerator / rate.denominator
    first = rig._key_tick(unreal.FrameNumber(start_frame))
    ticks = [first + round(t * time_scale * ticks_per_second) for t in source_times]
    events = {}
    step_ticks = set()
    for index in sorted(left_indices):
        post = ticks[index]
        if post - 1 < first or post - 1 in events or post in events:
            raise ValueError('Bedrock steps are too close for the sequence tick resolution')
        events[post - 1] = index
        events[post] = index + 1
        step_ticks.update((post - 1, post))
    hold_ticks = {ticks[index] - 1 for index in left_indices}
    for index, tick in enumerate(ticks):
        if tick not in step_ticks:
            events[tick] = index
    ordered = sorted(events)
    return ordered, {name: [values[events[tick]] for tick in ordered]
                     for name, values in batches.items()}, hold_ticks


def _sequence_end_frame(start_frame, duration, fps, time_scale, *, loop=False):
    frames = max(0, math.ceil(duration * fps * time_scale - 1e-5))
    return start_frame + (frames if loop and frames > 0 else frames + 1)


def _panel_advanced_options(mod):
    props = mod.props
    ignore_missing = bool(getattr(props, 'IgnoreMissingBones', False))
    raw_mode = str(getattr(mod, 'skeleton_mode', 'auto') or 'auto')
    skel_mode = None if raw_mode == 'auto' else raw_mode
    export_fps = int(getattr(props, 'ExportFps', 60) or 60)
    return ignore_missing, skel_mode, export_fps


def apply(mod):
    """从面板属性读取参数并启动动画转换任务。"""
    props = mod.props
    path, clip = mod.selected_clip()
    had_actor = isinstance(props.Actor, unreal.Actor)
    target = util.resolve_actor(props)
    if not had_actor:
        util.sync_asset_names(props, clip)
    create_new = bool(props.CreateNewSequence)
    if create_new:
        if not (props.LevelSequenceName or '').strip():
            util.sync_asset_names(props, clip)
        seq_name = util.ls_name(props.LevelSequenceName)
        if not seq_name:
            mineprep.throw('关卡序列名称为空')
        seq = seq_name
        t0 = 0
    else:
        seq = sequencer_tools.resolve_sequence()
        if not seq:
            mineprep.throw('未打开 Level Sequence，请先在 Sequencer 中打开或聚焦一个序列')
        t0 = mineprep.sequencer.frame() if props.StartAtPlayhead else 0
    ignore_missing, skel_mode, _ = _panel_advanced_options(mod)
    layered = bool(getattr(props, 'UseLayeredRig', False))
    return apply_animation(path, target, sequence=seq, clip=clip, time_scale=props.TimeScale,
                           start_time=t0, resize_playback=create_new, save=create_new,
                           ignore_missing_bones=ignore_missing, skeleton_mode=skel_mode,
                           layered=layered)


def export_direct(mod):
    """从面板直接编译并写出 AnimSequence 资产（无需经过 Sequencer 烘焙）。"""
    props = mod.props
    path, clip = mod.selected_clip()
    had_actor = isinstance(props.Actor, unreal.Actor)
    target = util.resolve_actor(props)
    if not had_actor:
        util.sync_asset_names(props, clip)
    if not (props.AnimSequenceName or '').strip():
        util.sync_asset_names(props, clip)
    anim_name = util.sanitize_asset(props.AnimSequenceName)
    if not anim_name:
        mineprep.throw('动画序列名称为空')
    ignore_missing, skel_mode, export_fps = _panel_advanced_options(mod)
    return export_anim_sequence(
        path, target, anim_name, clip=clip, fps=export_fps, time_scale=props.TimeScale,
        ignore_missing_bones=ignore_missing, skeleton_mode=skel_mode,
    )


def apply_face_preset(
    target,
    preset,
    *,
    sequence=None,
    start_time=None,
    strength=1.0,
    blend_in=0.0,
    hold=0.0,
    blend_out=0.0,
    reset_others=None,
    layered='auto',
    register_missing_curves=False,
    resize_playback=False,
    save=False,
):
    """Apply a cross-species facial preset (or curve dict) onto an Actor in a LevelSequence."""
    seq = sequence if sequence is not None else sequencer_tools.resolve_sequence()
    if seq is None:
        mineprep.throw('未打开 Level Sequence，请先在 Sequencer 中打开或聚焦一个序列')
    t0 = mineprep.sequencer.frame() if start_time is None else start_time
    clip_name, clip_dict = face_presets.build_pose_clip(
        preset,
        strength=strength,
        blend_in=blend_in,
        hold=hold,
        blend_out=blend_out,
        reset_others=reset_others,
    )
    return apply_animation(
        clip_dict, target, sequence=seq, clip=clip_name,
        start_time=t0, resize_playback=resize_playback, save=save,
        layered=layered, register_missing_curves=register_missing_curves,
    )


def apply_auto_blink(
    target,
    *,
    sequence=None,
    start_time=None,
    duration=None,
    min_interval=2.4,
    max_interval=4.4,
    blink_duration=0.21,
    hold_closed=0.08,
    double_blink_chance=0.15,
    phase_offset=0.0,
    seed=None,
    layered='auto',
    register_missing_curves=False,
    save=False,
):
    """Generate and apply sparse synchronized procedural blinks (`face_blink_l/r`) onto an Actor."""
    seq = sequence if sequence is not None else sequencer_tools.resolve_sequence()
    if seq is None:
        mineprep.throw('未打开 Level Sequence，请先在 Sequencer 中打开或聚焦一个序列')
    resolved_seq = sequencer_tools.resolve_sequence(seq) if isinstance(seq, unreal.LevelSequence) else None
    t0 = 0 if start_time is None else start_time
    dur = duration
    if dur is None or float(dur) <= 0.0:
        if resolved_seq is None:
            raise ValueError('新建序列路径下须显式提供正的 duration（秒）')
        rate = resolved_seq.get_display_rate()
        fps = rate.numerator / rate.denominator
        start_f = sequencer_tools._resolve_frame(t0, resolved_seq)
        end_f = int(resolved_seq.get_playback_end())
        span_frames = max(1, end_f - start_f)
        dur = span_frames / fps
    clip_name, clip_dict = face_presets.build_auto_blink_clip(
        duration=float(dur),
        min_interval=min_interval,
        max_interval=max_interval,
        blink_duration=blink_duration,
        hold_closed=hold_closed,
        double_blink_chance=double_blink_chance,
        phase_offset=phase_offset,
        seed=seed,
    )
    return apply_animation(
        clip_dict, target, sequence=seq, clip=clip_name,
        start_time=t0, resize_playback=False, save=save,
        layered=layered, register_missing_curves=register_missing_curves,
    )


def _open_sequence(sequence):
    if not isinstance(sequence, unreal.LevelSequence):
        raise ValueError('需要有效的 LevelSequence')
    if not unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence):
        raise RuntimeError('无法打开关卡序列: ' + sequence.get_path_name())


def _resolve_clip_source(json_path, clip):
    if json_path is None:
        if clip is None:
            raise ValueError('需要动画 JSON 路径、完整片段键 clip 或动画字典')
        return library.find(clip), clip
    if isinstance(json_path, Path):
        return json_path, clip
    if not isinstance(json_path, str):
        raise ValueError('动画来源须为路径、完整片段键 clip 或动画字典')
    text = json_path
    if not text.strip():
        if clip is None:
            raise ValueError('需要动画 JSON 路径、完整片段键 clip 或动画字典')
        return library.find(clip), clip
    path = Path(text)
    if not path.is_file() and not text.lower().endswith(('.json', '.bbmodel')) and '/' not in text and '\\' not in text:
        if clip is not None and clip != text:
            raise ValueError(f'clip 与完整片段键不一致: {text!r} != {clip!r}')
        return library.find(text), text
    return path, clip


def _update_playback_range(sequence, start_frame, end, *, created, resize):
    if created:
        sequencer_tools.set_sequence_range(sequence, start_frame, end)
    elif resize:
        old_start = sequence.get_playback_start()
        old_end = sequence.get_playback_end()
        new_start = min(old_start, start_frame)
        new_end = max(old_end, end)
        if (new_start, new_end) != (old_start, old_end):
            sequencer_tools.set_sequence_range(sequence, new_start, new_end)


def _validate_bbmodel_targets(rigs, routed_channels):
    """Ensure every targeted .bbmodel bone maps to an EulerTransform scalar curve channel."""
    for rig_key, entries in routed_channels.items():
        rig = rigs[rig_key]
        checked_bones = set()
        for entry in entries:
            bone = entry['bone']
            if bone not in checked_bones:
                full = rig._resolve_name(bone)
                if rig._type(full) != unreal.RigControlType.EULER_TRANSFORM:
                    raise ValueError(full + ': .bbmodel 骨骼导入需要 EulerTransform 控件')
                checked_bones.add(bone)
            chosen = rig.channels(entry['selector'])
            if (len(chosen) != 1 or not isinstance(
                    chosen.target[0], (unreal.MovieSceneScriptingFloatChannel, unreal.MovieSceneScriptingDoubleChannel))):
                raise ValueError(entry['selector'] + ': 找不到目标 Float/Double 通道')


def _normalize_bones_arg(bones):
    if bones is None:
        return None
    if isinstance(bones, str):
        raw = [bones]
    elif isinstance(bones, (bytes, bytearray)):
        raise ValueError('bones 须为目标骨骼名字符串或字符串序列')
    else:
        try:
            raw = list(bones)
        except TypeError as exc:
            raise ValueError('bones 须为目标骨骼名字符串或字符串序列') from exc
    if not raw:
        raise ValueError('bones 不能为空；传 None 表示导入全部骨骼')
    result = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError('bones 中的骨骼名须为非空字符串')
        result.append(item.strip())
    return result


def _resolve_bone_mask(bones, reference, head_reference=None):
    if bones is None:
        return None
    merged = dict(reference)
    if head_reference:
        for k, v in head_reference.items():
            merged.setdefault(k, v)
    by_case, ambiguous = bbmodel.reference_case_map(merged)
    selected = set()
    for name in bones:
        if name in merged:
            selected.add(name)
            continue
        key = name.casefold()
        if key in ambiguous:
            raise ValueError(f'目标骨架存在大小写冲突骨骼: {name}')
        target = by_case.get(key)
        if target is None:
            mapped = rig_rules.GENERIC_ALIASES.get(key) or rig_rules.GENERIC_ALIASES.get(rig_rules.canonical_snake_name(name))
            if mapped is not None:
                target = by_case.get(mapped.casefold())
        if target is None:
            raise ValueError(f'目标骨架不存在骨骼: {name}')
        selected.add(target)
    return selected


def _resolve_bedrock_mode(skeleton_mode, index_entry):
    if skeleton_mode is not None:
        return skeleton_mode
    if index_entry is None:
        return 'biped'
    explicit = index_entry.get('skeleton_mode')
    if explicit is not None:
        if explicit not in ('biped', 'quadruped', 'local'):
            raise ValueError("动画索引中的 skeleton_mode 须为 'biped'、'quadruped' 或 'local'")
        return explicit
    skeleton = index_entry.get('skeleton')
    if skeleton is None or skeleton == 'bedrock_player':
        return 'biped'
    if skeleton == 'quadruped':
        return 'quadruped'
    return 'local'


def _filter_bbmodel_channels(channels, bone_mask):
    if bone_mask is None:
        return channels
    filtered = [entry for entry in channels if entry['bone'] in bone_mask]
    if not filtered:
        raise ValueError('所选 bones 与动画包含的骨骼通道无交集')
    return filtered


def _apply_bbmodel(data, actor, clip, components, reference, sequence, destination,
                   time_scale, start_time, resize_playback, save,
                   *, bone_mask=None, skeleton_mode=None, ignore_missing_bones=False, layered=False):
    if skeleton_mode is not None:
        raise ValueError('skeleton_mode 仅适用于 Bedrock 动画')
    if ignore_missing_bones:
        raise ValueError('.bbmodel 动画不支持 ignore_missing_bones；须完整匹配参考骨架')
    from mineprep.handles import _tick_resolution_sync

    weighted = _tick_resolution_sync() is not None
    fps = 60.0
    tick_rate = 24000.0
    if sequence is not None:
        disp = sequence.get_display_rate()
        fps = disp.numerator / disp.denominator
        res = sequence.get_tick_resolution()
        tick_rate = res.numerator / res.denominator
        start_frame = sequencer_tools._resolve_frame(start_time, sequence)
    elif start_time is None:
        start_frame = 0
    elif isinstance(start_time, int):
        start_frame = start_time
    else:
        start_frame = int(round(start_time * fps))
    start_sec = start_frame / fps

    compiled = bbmodel.compile_clip(
        data, reference, tick_rate, start_time=start_sec, time_scale=time_scale, weighted=weighted,
    )
    channels = _filter_bbmodel_channels(compiled['channels'], bone_mask)
    head_shared = _matching_head_bones(components['head'], reference) if 'head' in components else set()
    head_channels = [entry for entry in channels if entry['bone'] in head_shared]

    created_sequence = sequence is None and bool(destination)
    if created_sequence:
        sequence = util.create_sequence(destination, fps=60)
    _open_sequence(sequence)
    init_layered = (layered is True) or (layered == 'auto')
    body = Rig(components['body'], layered=init_layered)
    rigs = {'body': body}
    if head_channels:
        rigs['head'] = Rig(components['head'], layered=init_layered)
    yield
    for rig in rigs.values():
        yield from (_prepare_rig(rig, sequence, layered=layered) if layered else _prepare_rig(rig, sequence))

    actual_res = sequence.get_tick_resolution()
    actual_tick_rate = actual_res.numerator / actual_res.denominator
    start_frame = sequencer_tools._resolve_frame(start_time, sequence)
    start_tick = body._key_tick(unreal.FrameNumber(start_frame))
    actual_start_sec = start_tick / actual_tick_rate
    if abs(actual_tick_rate - tick_rate) > 1e-6 or abs(actual_start_sec - start_sec) > 1e-9:
        compiled = bbmodel.compile_clip(
            data, reference, actual_tick_rate,
            start_time=actual_start_sec, time_scale=time_scale, weighted=weighted,
        )
        channels = _filter_bbmodel_channels(compiled['channels'], bone_mask)
        head_channels = [entry for entry in channels if entry['bone'] in head_shared]

    routed = {'body': channels}
    if 'head' in rigs:
        routed['head'] = head_channels
    _validate_bbmodel_targets(rigs, routed)

    end = _sequence_end_frame(start_frame, compiled['duration'], fps, time_scale, loop=compiled['is_loop'])
    max_written_tick = max(
        (body._time_tick(float(t)) for entries in routed.values()
         for entry in entries for t in entry['prepared']['times']),
        default=start_tick,
    )
    span_end_tick = max(body._key_tick(unreal.FrameNumber(end)), max_written_tick + 1)

    reports = []
    with sequencer_tools._defer_refresh(), unreal.ScopedEditorTransaction('Import Blockbench animation'):
        sequence.modify()
        for rig_key, entries in routed.items():
            rig = rigs[rig_key]
            for entry in entries:
                reports.append(curves.write_prepared(
                    rig, entry['selector'], entry['prepared'],
                    replace_span=(start_tick, span_end_tick),
                ))
        _update_playback_range(sequence, start_frame, end, created=created_sequence, resize=resize_playback)

    nkey = sum(len(rep['keys']) for rep in reports)
    channel_keys = sum(
        ch.get_num_keys() for rig in rigs.values() for section in rig.track.get_sections()
        for ch in section.get_all_channels()
    )
    if save and not unreal.EditorAssetLibrary.save_loaded_asset(sequence):
        raise RuntimeError('保存关卡序列失败: ' + sequence.get_path_name())
    mineprep.prints(clip + ' keys=' + str(nkey))
    matched_bones = list(dict.fromkeys(entry['bone'] for entry in channels))
    return dict(
        sequence=sequence, actor=actor, clip=clip,
        start_frame=start_frame, end_frame=end,
        keys=nkey, channel_keys=channel_keys,
        weighted=any(rep['weighted'] for rep in reports),
        extra_keys=sum(rep['extra_keys'] for rep in reports),
        sampled_error=max((rep['sampled_error'] for rep in reports), default=0.0),
        matched_bones=matched_bones, skipped_bones=[],
    )


def _validate_time_scale(time_scale):
    if isinstance(time_scale, bool) or not isinstance(time_scale, (int, float)):
        raise ValueError('time_scale 必须为正有限数')
    time_scale = float(time_scale)
    if not math.isfinite(time_scale) or time_scale <= 0:
        raise ValueError('time_scale 必须为正有限数')
    return time_scale


def _load_clip_source(json_path, clip):
    if isinstance(json_path, dict):
        clips = library.resolve_clips(json_path, clip=clip)
        source_path = None
    else:
        source_path, clip = _resolve_clip_source(json_path, clip)
        clips = library.clips(source_path, clip=clip)
    if clip is None and len(clips) == 1:
        clip = next(iter(clips))
    if clip not in clips:
        raise ValueError('请选择完整的动画片段键: ' + ', '.join(clips))
    index_entry = None if isinstance(json_path, dict) else library.match_entry(source_path, clip)
    return clip, clips[clip], index_entry


def _compile_bedrock_batches(mode, reference, samples, count, *, ignore_missing_bones=False):
    if mode == 'biped':
        if ignore_missing_bones:
            biped.validate_target(reference)
            samples, skipped_bones = biped.filter_source_samples(samples, reference=reference)
            if not samples:
                raise ValueError('动画与目标骨架没有可匹配的共有骨骼')
        else:
            skipped_bones = []
        return biped.compile_controls(reference, samples, count), skipped_bones
    if mode == 'quadruped':
        return biped.compile_quadruped_controls(
            reference, samples, count, ignore_missing_bones=bool(ignore_missing_bones),
        )
    return biped.compile_generic_controls(
        reference, samples, count, ignore_missing_bones=bool(ignore_missing_bones),
    )


def _resolve_ref_bone(bone: str, reference: dict) -> str | None:
    by_case, ambiguous = bbmodel.reference_case_map(reference)
    return rig_rules.resolve_aliased_bone(
        bone, reference, lambda folded: None if folded in ambiguous else by_case.get(folded),
    )


def _compile_bedrock_with_head(mode, reference, samples, count, *, head_reference=None, ignore_missing_bones=False):
    if not samples:
        return {}, {}, []
    head_only_samples = {}
    body_samples = {}
    for bone, ch in samples.items():
        if mode == 'biped' and rig_rules.biped_control_name(bone) is not None:
            body_samples[bone] = ch
            continue
        if _resolve_ref_bone(bone, reference) is not None:
            body_samples[bone] = ch
            continue
        if head_reference is not None:
            hit = _resolve_ref_bone(bone, head_reference)
            if hit is not None and hit != 'head':
                head_only_samples[bone] = ch
                continue
        body_samples[bone] = ch

    batches, skipped_bones = {}, []
    if body_samples:
        if mode == 'biped':
            extra_local = {b: c for b, c in body_samples.items()
                           if rig_rules.biped_control_name(b) is None and _resolve_ref_bone(b, reference) is not None}
            core_biped = {b: c for b, c in body_samples.items() if b not in extra_local}
            if core_biped or not extra_local:
                batches, skipped_bones = _compile_bedrock_batches(
                    mode, reference, core_biped, count, ignore_missing_bones=ignore_missing_bones,
                )
            else:
                biped.validate_target(reference)
            if extra_local:
                local_batches, local_skipped = biped.compile_generic_controls(
                    reference, extra_local, count, ignore_missing_bones=ignore_missing_bones,
                )
                batches.update(local_batches)
                skipped_bones.extend(local_skipped)
        else:
            batches, skipped_bones = _compile_bedrock_batches(
                mode, reference, body_samples, count, ignore_missing_bones=ignore_missing_bones,
            )
    head_extra = {}
    if head_only_samples and head_reference is not None:
        head_extra, head_skipped = biped.compile_generic_controls(
            head_reference, head_only_samples, count, ignore_missing_bones=ignore_missing_bones,
        )
        skipped_bones.extend(head_skipped)
    return batches, head_extra, skipped_bones


def _filter_batches_by_mask(batches, bone_mask, *, allow_empty=False):
    if bone_mask is None:
        return batches
    filtered = {name: vals for name, vals in batches.items() if name in bone_mask}
    if not filtered and not allow_empty:
        raise ValueError('所选 bones 与动画包含的骨骼通道无交集')
    return filtered


def _regular_sample_indices(regular, timeline_times, left_indices):
    indices = []
    j = 0
    total = len(timeline_times)
    for t in regular:
        while j < total and (j in left_indices or timeline_times[j] < t - 1e-12):
            j += 1
        if j >= total or abs(timeline_times[j] - t) > 1e-9:
            raise RuntimeError(f'采样时间对齐失败: {t}')
        indices.append(j)
        j += 1
    return indices


def _filter_or_register_curves(
    cap_target,
    skeleton,
    curve_names: tuple[str, ...],
    *,
    has_bones: bool,
    register_missing_curves: bool,
) -> tuple[set[str], list[str]]:
    """Filter curves by target capabilities, or register missing ones while preserving existing skeleton flags."""
    if not curve_names:
        return set(), []
    from mineprep.face import describe_actor_capabilities, setup_face_skeleton

    if register_missing_curves:
        setup_face_skeleton(skeleton, curve_names, preserve_existing=True)
        return set(curve_names), []

    caps = describe_actor_capabilities(cap_target)
    if caps['source'] in ('metadata', 'fallback'):
        supported_set = set(caps['curves'])
    elif skeleton is not None and hasattr(skeleton, 'get_curve_meta_data_names'):
        supported_set = {
            str(n) for n in (skeleton.get_curve_meta_data_names() or ())
            if not str(n).startswith('_mc_')
        }
    else:
        supported_set = set()

    unsupported = [c for c in curve_names if c not in supported_set]
    kept = {c for c in curve_names if c in supported_set}
    if unsupported and not has_bones and not kept:
        if supported_set:
            raise ValueError(
                f"目标角色不支持该表情所需的曲线（缺失: {', '.join(unsupported)}；"
                f"当前支持: {', '.join(sorted(supported_set))}）"
            )
        raise ValueError(
            f"目标角色不支持表情曲线（缺失: {', '.join(unsupported)}；"
            "请先为角色启用 2D/3D 表情，或传 register_missing_curves=True）"
        )
    return kept, unsupported


def _offsets_to_local_tracks(reference, batches, *, pad_single=False):
    tracks = {}
    for bone_name, offsets in batches.items():
        rest = reference[bone_name]['local']
        locals_list = [
            unreal.Transform(location=et.location, rotation=et.rotation, scale=et.scale).multiply(rest)
            for et in offsets
        ]
        if pad_single and len(locals_list) == 1:
            locals_list.append(locals_list[0])
        tracks[bone_name] = locals_list
    return tracks


@mineprep.asynctask
def apply_animation(json_path, actor, *, sequence, clip=None, time_scale=1.0,
                    start_time=0, resize_playback=False, save=False,
                    bones=None, ignore_missing_bones=False, skeleton_mode=None,
                    layered=False, register_missing_curves=False):
    """Write a clip (by JSON/.bbmodel path, full library key, or parsed dict) to a LevelSequence."""
    time_scale = _validate_time_scale(time_scale)
    start_time = _valid_time(start_time, 'start_time')
    if skeleton_mode not in (None, 'biped', 'quadruped', 'local'):
        raise ValueError("skeleton_mode 须为 None、'biped'、'quadruped' 或 'local'")
    if layered not in (False, True, 'auto'):
        raise ValueError("layered 须为 False、True 或 'auto'")
    bone_names = _normalize_bones_arg(bones)
    components = util.animation_components(actor)
    reference = describe_skeleton(components['body'])
    head_ref = describe_skeleton(components['head']) if 'head' in components else None
    bone_mask = _resolve_bone_mask(bone_names, reference, head_ref)
    clip, data, index_entry = _load_clip_source(json_path, clip)
    destination = sequence if isinstance(sequence, str) else None
    if destination:
        sequence = util.find_sequence(destination)
    elif not isinstance(sequence, unreal.LevelSequence):
        raise ValueError('需要有效的 LevelSequence')
    if data.get('_format') == 'bbmodel':
        return (yield from _apply_bbmodel(
            data, actor, clip, components, reference, sequence, destination,
            time_scale, start_time, resize_playback, save,
            bone_mask=bone_mask, skeleton_mode=skeleton_mode,
            ignore_missing_bones=bool(ignore_missing_bones), layered=layered,
        ))
    fps = 60.0
    if sequence is not None:
        rate = sequence.get_display_rate()
        fps = rate.numerator / rate.denominator
    left_indices = set()
    skipped_bones = []
    head_extra_batches = {}
    curve_samples = {}
    sparse_curves = None
    batches = {}
    source_times = [0.0]
    if 'frames' in data:
        if skeleton_mode is not None:
            raise ValueError('skeleton_mode 仅适用于 Bedrock 动画')
        if ignore_missing_bones:
            raise ValueError('Java 动画不支持 ignore_missing_bones；须完整匹配参考骨架')
        batches, count = java_clip.compile_clip(data, reference, fps * time_scale)
        duration = (len(data['frames']) - 1) / float(data['fps'])
        source_times = [min(i / (fps * time_scale), duration) for i in range(count)]
        is_loop = (data['loop'] is True) if 'loop' in data else bool(index_entry and index_entry.get('loop'))
        batches = _filter_batches_by_mask(batches, bone_mask)
    else:
        sparse_result = _try_sparse_curves(clip, data)
        if sparse_result is not None:
            duration, sparse_curves = sparse_result
            is_loop = (data['loop'] is True) if 'loop' in data else bool(index_entry and index_entry.get('loop'))
        else:
            mode = _resolve_bedrock_mode(skeleton_mode, index_entry)
            duration, source_times, samples, curve_samples, left_indices = sampling.compile_clip_channels(
                clip, data, fps * time_scale,
            )
            count = len(source_times)
            is_loop = (data['loop'] is True) if 'loop' in data else bool(index_entry and index_entry.get('loop'))
            batches, head_extra_batches, skipped_bones = _compile_bedrock_with_head(
                mode, reference, samples, count,
                head_reference=head_ref, ignore_missing_bones=bool(ignore_missing_bones),
            )
            if not batches and not head_extra_batches and not curve_samples:
                raise ValueError('动画不包含可用的骨骼或表情曲线通道')
            if bone_mask is not None:
                batches = _filter_batches_by_mask(batches, bone_mask, allow_empty=True)
                head_extra_batches = _filter_batches_by_mask(head_extra_batches, bone_mask, allow_empty=True)
                if not batches and not head_extra_batches:
                    raise ValueError('所选 bones 与动画包含的骨骼通道无交集')

    head_shared = (_head_batches(head_ref, reference, batches) if head_ref is not None else {})
    head_bone_batches = {**{name: batches[name] for name in head_shared}, **head_extra_batches}
    curve_names = tuple(sparse_curves) if sparse_curves is not None else tuple(curve_samples)
    unsupported_curves: list[str] = []
    if curve_names:
        target_comp = components['head'] if 'head' in components else components['body']
        target_mesh = target_comp.get_skeletal_mesh_asset() if hasattr(target_comp, 'get_skeletal_mesh_asset') else None
        kept_set, unsupported_curves = _filter_or_register_curves(
            actor,
            getattr(target_mesh, 'skeleton', None),
            curve_names,
            has_bones=bool(batches or head_extra_batches),
            register_missing_curves=bool(register_missing_curves),
        )
        if unsupported_curves:
            if sparse_curves is not None:
                sparse_curves = {k: v for k, v in sparse_curves.items() if k in kept_set}
            else:
                curve_samples = {k: v for k, v in curve_samples.items() if k in kept_set}
            curve_names = tuple(sparse_curves) if sparse_curves is not None else tuple(curve_samples)

    body_has_curves = bool(curve_names) and ('head' not in components)
    head_has_curves = bool(curve_names) and ('head' in components)

    created_sequence = sequence is None and bool(destination)
    if created_sequence:
        sequence = util.create_sequence(destination, fps=60)
    _open_sequence(sequence)

    # If a pure canonical `face_*` sparse clip (e.g. `apply_face_preset` / `apply_auto_blink`) targets an
    # actor with `CR_MC_Face` already mounted, write ONLY the affected `CR_MC_Face` controls directly so
    # presets/blinks actually take effect above priority >= 1 without clobbering unrelated hand edits or
    # spawning an extra FKControlRig track.
    mounted_face_rig = None
    if sparse_curves is not None and sparse_curves:
        from mineprep.face import FACE_CURVES, find_mounted_face_rig
        if set(sparse_curves) <= set(FACE_CURVES):
            face_key = 'head' if 'head' in components else 'body'
            mounted_face_rig = find_mounted_face_rig(sequence, components[face_key])

    if mounted_face_rig is not None:
        from mineprep.face import (
            describe_actor_capabilities,
            read_mounted_face_look_x,
            sparse_curves_to_face_rig_batches,
        )
        from mineprep.face.face_rig import _set_channel_default

        face_key = 'head' if 'head' in components else 'body'
        yield
        start_frame = sequencer_tools._resolve_frame(start_time, sequence)
        end = _sequence_end_frame(start_frame, duration, fps, time_scale, loop=is_loop)
        start_tick = mounted_face_rig._key_tick(unreal.FrameNumber(start_frame))
        tick_rate = sequence.get_tick_resolution()
        ticks_per_second = tick_rate.numerator / tick_rate.denominator
        max_tick = start_tick
        sparse_placed = {}
        for cname, (ts, vs) in sparse_curves.items():
            dedup = {}
            for t_s, val in zip(ts, vs):
                tk = start_tick + round(t_s * time_scale * ticks_per_second)
                dedup[tk] = float(val)
            ordered_ticks = sorted(dedup)
            if ordered_ticks:
                max_tick = max(max_tick, ordered_ticks[-1])
            sparse_placed[cname] = (ordered_ticks, [dedup[tk] for tk in ordered_ticks])
        span_end_tick = max(mounted_face_rig._key_tick(unreal.FrameNumber(end)), max_tick + 1)

        try:
            pupil_mode = int(mounted_face_rig.get('face_panel_ctrl.Pupil_Rest_Mode', start_frame))
        except Exception:
            pupil_mode = int(describe_actor_capabilities(actor).get('pupil_rest_mode', -1))
        existing_look_x = None
        span_end_inclusive = max(start_tick, span_end_tick - 1)
        if ('face_look_x_l' in sparse_placed) ^ ('face_look_x_r' in sparse_placed):
            present_ticks = sparse_placed.get('face_look_x_l', sparse_placed.get('face_look_x_r', ([], [])))[0]
            existing_look_x = read_mounted_face_look_x(
                mounted_face_rig, present_ticks, start_tick, span_end_inclusive,
                pupil_rest_mode=pupil_mode,
            )
        face_batches, need_ov_x = sparse_curves_to_face_rig_batches(
            sparse_placed,
            pupil_rest_mode=pupil_mode,
            existing_look_x=existing_look_x,
            span_ticks=(start_tick, span_end_inclusive),
        )
        try:
            cur_ov_x = float(mounted_face_rig.get('gaze_ctrl.Eye_Overflow_X', start_frame))
        except Exception:
            cur_ov_x = 0.5
        if need_ov_x > cur_ov_x + 1e-4:
            _set_channel_default(mounted_face_rig, 'gaze_ctrl.Eye_Overflow_X', round(min(1.0, need_ov_x), 4))

        replace_slice = slice(start_tick, span_end_tick)
        options = dict(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION, hold_ticks=())
        with sequencer_tools._defer_refresh():
            nkey = write_batches(mounted_face_rig, [], face_batches, replace_span=replace_slice, **options)
            _update_playback_range(sequence, start_frame, end, created=created_sequence, resize=resize_playback)
        channel_keys = sum(
            ch.get_num_keys() for section in mounted_face_rig.track.get_sections()
            for ch in section.get_all_channels()
        )
        if save and not unreal.EditorAssetLibrary.save_loaded_asset(sequence):
            raise RuntimeError('保存关卡序列失败: ' + sequence.get_path_name())
        if unsupported_curves:
            mineprep.prints(f"{clip} skipped unsupported curves: {', '.join(unsupported_curves)}")
        mineprep.prints(clip + ' (CR_MC_Face) keys=' + str(nkey))
        written_curves = list(sparse_placed.keys())
        return dict(
            sequence=sequence, actor=actor, clip=clip,
            start_frame=start_frame, end_frame=end,
            keys=nkey, channel_keys=channel_keys,
            matched_bones=[],
            matched_curves=written_curves,
            written_curves=written_curves,
            unsupported_curves=list(unsupported_curves),
            skipped_bones=skipped_bones,
            target_components=[face_key],
            rig_modes={face_key: 'face_rig'},
            target_rig='CR_MC_Face',
            replace_tick_span=(start_tick, span_end_tick),
        )

    init_layered = (layered is True) or (layered == 'auto')
    rigs = {}
    if batches or body_has_curves or not ('head' in components and (head_bone_batches or head_has_curves)):
        rigs['body'] = Rig(components['body'], layered=init_layered)
    if 'head' in components and (head_bone_batches or head_has_curves):
        rigs['head'] = Rig(components['head'], layered=init_layered)
    primary_rig = rigs.get('body') or rigs['head']
    yield
    for rig in rigs.values():
        yield from (_prepare_rig(rig, sequence, layered=layered) if layered else _prepare_rig(rig, sequence))
    start_frame = sequencer_tools._resolve_frame(start_time, sequence)
    end = _sequence_end_frame(start_frame, duration, fps, time_scale, loop=is_loop)
    start_tick = primary_rig._key_tick(unreal.FrameNumber(start_frame))

    written_curves: list[str] = []
    if sparse_curves is not None:
        # Pure-curve linear clip: write ONLY exact sparse timestamps (no 60fps dense resampling!)
        tick_rate = sequence.get_tick_resolution()
        ticks_per_second = tick_rate.numerator / tick_rate.denominator
        max_tick = start_tick
        sparse_placed = {}
        for cname, (ts, vs) in sparse_curves.items():
            dedup = {}
            for t_s, val in zip(ts, vs):
                tk = start_tick + round(t_s * time_scale * ticks_per_second)
                dedup[tk] = float(val)
            ordered_ticks = sorted(dedup)
            if ordered_ticks:
                max_tick = max(max_tick, ordered_ticks[-1])
            sparse_placed[cname] = (ordered_ticks, [dedup[tk] for tk in ordered_ticks])
        span_end_tick = max(primary_rig._key_tick(unreal.FrameNumber(end)), max_tick + 1)
        options = dict(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION, hold_ticks=())
        target_key = 'head' if 'head' in components else 'body'
        prepared = {k: {} for k in rigs}
        target_rig = rigs[target_key]
        rig_ctrl_lower = _rig_control_aliases(target_rig)
        for cname, (cticks, cvals) in sparse_placed.items():
            if rig_ctrl_lower is not None and cname.casefold() not in rig_ctrl_lower and not register_missing_curves:
                unsupported_curves.append(cname)
                continue
            ctrl = target_rig._resolve_name(cname)
            if target_rig._type(ctrl) not in (unreal.RigControlType.FLOAT, unreal.RigControlType.SCALE_FLOAT):
                raise ValueError(ctrl + ': curve import requires Float control')
            prepared[target_key][ctrl] = (cticks, cvals)
            written_curves.append(cname)
        if not written_curves:
            raise ValueError(
                f"目标 Control Rig 未暴露可用表情曲线控件（缺失: {', '.join(unsupported_curves)}）"
            )
        times = []
    else:
        combined_all = {**batches, **{f'__head__{k}': v for k, v in head_bone_batches.items()},
                        **{f'__curve__{k}': v for k, v in curve_samples.items()}}
        times, placed_all, hold_ticks = _place_sampled_ticks(
            primary_rig, sequence, start_frame, source_times, combined_all, time_scale, left_indices,
        )
        placed_body = {k: placed_all[k] for k in batches}
        placed_head = {k: placed_all[f'__head__{k}'] for k in head_bone_batches}
        placed_curves = {k: placed_all[f'__curve__{k}'] for k in curve_samples}
        span_end_tick = max(primary_rig._key_tick(unreal.FrameNumber(end)), times[-1] + 1)
        options = dict(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION, hold_ticks=hold_ticks)
        routed_bones = {'body': placed_body, 'head': placed_head}
        routed_curves = {'body': placed_curves if 'head' not in components else {},
                         'head': placed_curves if 'head' in components else {}}
        prepared = {}
        for key, rig in rigs.items():
            entry = _prepare_batches(rig, times, routed_bones.get(key, {}))
            raw_curve_map = routed_curves.get(key) or {}
            if raw_curve_map:
                rig_ctrl_lower = _rig_control_aliases(rig)
                kept_curves = {}
                for cname, cvals in raw_curve_map.items():
                    if rig_ctrl_lower is not None and cname.casefold() not in rig_ctrl_lower and not register_missing_curves:
                        unsupported_curves.append(cname)
                        continue
                    kept_curves[cname] = cvals
                if kept_curves:
                    curves_entry = _prepare_curve_batches(rig, times, kept_curves)
                    overlap = set(entry) & set(curves_entry)
                    if overlap:
                        raise ValueError('Multiple source channels map to ' + ', '.join(sorted(overlap)))
                    entry = {**entry, **curves_entry}
                    written_curves.extend(kept_curves.keys())
            prepared[key] = entry
        if not any(prepared.values()):
            raise ValueError(
                f"目标 Control Rig 未暴露可用骨骼或表情曲线控件（缺失: {', '.join(unsupported_curves)}）"
            )
    replace_slice = slice(start_tick, span_end_tick)
    with sequencer_tools._defer_refresh():
        nkey = sum(write_batches(rig, times, prepared[key], replace_span=replace_slice, **options)
                   for key, rig in rigs.items() if prepared[key])
        _update_playback_range(sequence, start_frame, end, created=created_sequence, resize=resize_playback)
    channel_keys = sum(ch.get_num_keys() for rig in rigs.values() for section in rig.track.get_sections()
                       for ch in section.get_all_channels())
    if save and not unreal.EditorAssetLibrary.save_loaded_asset(sequence):
        raise RuntimeError('保存关卡序列失败: ' + sequence.get_path_name())
    if skipped_bones:
        mineprep.prints(f"{clip} skipped missing bones: {', '.join(skipped_bones)}")
    if unsupported_curves:
        mineprep.prints(f"{clip} skipped unsupported curves: {', '.join(unsupported_curves)}")
    mineprep.prints(clip + ' keys=' + str(nkey))
    cr_lib = getattr(unreal, 'ControlRigSequencerLibrary', None)
    rig_modes = {}
    for key, rig in rigs.items():
        if cr_lib is not None and hasattr(cr_lib, 'is_layered_control_rig'):
            try:
                rig_modes[key] = 'layered' if bool(cr_lib.is_layered_control_rig(rig.target)) else 'replace'
            except Exception:
                rig_modes[key] = 'unknown'
        else:
            rig_modes[key] = 'layered' if init_layered else 'replace'
    matched_list = list(dict.fromkeys([*batches, *head_extra_batches]))
    return dict(sequence=sequence, actor=actor, clip=clip,
                start_frame=start_frame, end_frame=end,
                keys=nkey, channel_keys=channel_keys,
                matched_bones=matched_list,
                matched_curves=list(written_curves),
                written_curves=list(written_curves),
                unsupported_curves=list(unsupported_curves),
                skipped_bones=skipped_bones,
                target_components=list(rigs.keys()),
                rig_modes=rig_modes,
                replace_tick_span=(start_tick, span_end_tick))


def bake(mod):
    props = mod.props
    had_actor = isinstance(props.Actor, unreal.Actor)
    target = util.resolve_actor(props)
    if not had_actor:
        util.sync_asset_names(props)
    if not (props.AnimSequenceName or '').strip():
        util.sync_asset_names(props)
    anim_name = util.sanitize_asset(props.AnimSequenceName)
    if not anim_name:
        mineprep.throw('动画序列名称为空')
    seq = _sequence_for_bake(props)
    return bake_animation(target, seq, anim_name)


def export_anim_sequence(json_path, target, output_path, *, clip=None, fps=60,
                         time_scale=1.0, save=True, bones=None,
                         ignore_missing_bones=False, skeleton_mode=None,
                         register_missing_curves=False):
    """无 Sequencer UI / 关卡 Actor 依赖，直接将动画片段编译并写入 AnimSequence 资产。"""
    time_scale = _validate_time_scale(time_scale)
    if skeleton_mode not in (None, 'biped', 'quadruped', 'local'):
        raise ValueError("skeleton_mode 须为 None、'biped'、'quadruped' 或 'local'")
    rate = util.normalize_frame_rate(fps)
    out_fps = rate.numerator / rate.denominator
    dest_base = util._asset_path(str(output_path))
    dest_head = dest_base + '_Head'
    bone_names = _normalize_bones_arg(bones)

    targets = util.resolve_skeleton_targets(target)
    reference = util.describe_mesh_skeleton(targets['body'])
    head_ref = None
    head_shared = set()
    if 'head' in targets:
        head_ref = util.describe_mesh_skeleton(targets['head'])
        head_shared = _matching_head_bones(head_ref, reference)
    bone_mask = _resolve_bone_mask(bone_names, reference, head_ref)

    clip, data, index_entry = _load_clip_source(json_path, clip)
    skipped_bones = []
    head_extra_batches = {}
    curve_samples = {}
    if data.get('_format') == 'bbmodel':
        if skeleton_mode is not None:
            raise ValueError('skeleton_mode 仅适用于 Bedrock 动画')
        if ignore_missing_bones:
            raise ValueError('.bbmodel 动画不支持 ignore_missing_bones；须完整匹配参考骨架')
        sampled = bbmodel.sample_clip_offsets(data, reference, out_fps * time_scale, bone_mask=bone_mask)
        frame_count = max(1, len(sampled['times']) - 1)
        pad_single = len(sampled['times']) == 1
        batches = {
            bone_name: [
                unreal.EulerTransform(
                    location=unreal.Vector(*loc),
                    rotation=unreal.Rotator(roll=rot[0], pitch=rot[1], yaw=rot[2]),
                    scale=unreal.Vector(*scl),
                )
                for loc, rot, scl in entries
            ]
            for bone_name, entries in sampled['offsets'].items()
        }
    elif 'frames' in data:
        if skeleton_mode is not None:
            raise ValueError('skeleton_mode 仅适用于 Bedrock 动画')
        if ignore_missing_bones:
            raise ValueError('Java 动画不支持 ignore_missing_bones；须完整匹配参考骨架')
        batches, count = java_clip.compile_clip(data, reference, out_fps * time_scale)
        batches = _filter_batches_by_mask(batches, bone_mask)
        frame_count = max(1, count - 1)
        pad_single = count == 1
    else:
        mode = _resolve_bedrock_mode(skeleton_mode, index_entry)
        eff_fps = out_fps * time_scale
        duration, source_times, samples, curve_samples, left_indices = sampling.compile_clip_channels(
            clip, data, eff_fps,
        )
        batches, head_extra_batches, skipped_bones = _compile_bedrock_with_head(
            mode, reference, samples, len(source_times),
            head_reference=head_ref, ignore_missing_bones=bool(ignore_missing_bones),
        )
        if not batches and not head_extra_batches and not curve_samples:
            raise ValueError('动画不包含可用的骨骼或表情曲线通道')
        if bone_mask is not None:
            batches = _filter_batches_by_mask(batches, bone_mask, allow_empty=True)
            head_extra_batches = _filter_batches_by_mask(head_extra_batches, bone_mask, allow_empty=True)
            if not batches and not head_extra_batches:
                raise ValueError('所选 bones 与动画包含的骨骼通道无交集')
        regular = sampling.regular_times(duration, eff_fps)
        indices = _regular_sample_indices(regular, source_times, left_indices)
        batches = {name: [vals[i] for i in indices] for name, vals in batches.items()}
        head_extra_batches = {name: [vals[i] for i in indices] for name, vals in head_extra_batches.items()}
        curve_samples = {cname: [vals[i] for i in indices] for cname, vals in curve_samples.items()}
        frame_count = max(1, len(regular) - 1)
        pad_single = len(regular) == 1

    unsupported_curves: list[str] = []
    if curve_samples:
        curve_mesh = targets['head'] if 'head' in targets else targets['body']
        kept_set, unsupported_curves = _filter_or_register_curves(
            curve_mesh,
            getattr(curve_mesh, 'skeleton', None),
            tuple(curve_samples),
            has_bones=bool(batches or head_extra_batches),
            register_missing_curves=bool(register_missing_curves),
        )
        if unsupported_curves:
            curve_samples = {k: v for k, v in curve_samples.items() if k in kept_set}

    util.validate_existing_anim(dest_base, targets['body'].skeleton, fps=rate)
    if 'head' in targets:
        util.validate_existing_anim(dest_head, targets['head'].skeleton, fps=rate)

    body_curves = curve_samples if 'head' not in targets else None
    head_curves = curve_samples if 'head' in targets else None
    body_tracks = _offsets_to_local_tracks(reference, batches, pad_single=pad_single)
    body_anim = util.open_or_create_anim(
        dest_base, targets['body'].skeleton, fps=rate, preview_mesh=targets['body'],
    )
    util.write_anim_tracks(
        body_anim, reference, body_tracks, frame_count,
        float_curves=body_curves, save=bool(save),
    )

    head_anim = None
    if 'head' in targets:
        head_tracks = {
            **{name: body_tracks[name] for name in head_shared if name in body_tracks},
            **_offsets_to_local_tracks(head_ref, head_extra_batches, pad_single=pad_single),
        }
        head_anim = util.open_or_create_anim(
            dest_head, targets['head'].skeleton, fps=rate, preview_mesh=targets['head'],
        )
        util.write_anim_tracks(
            head_anim, head_ref, head_tracks, frame_count,
            float_curves=head_curves, save=bool(save),
        )

    if skipped_bones:
        mineprep.prints(f"{clip} skipped missing bones: {', '.join(skipped_bones)}")
    if unsupported_curves:
        mineprep.prints(f"{clip} skipped unsupported curves: {', '.join(unsupported_curves)}")
    mineprep.prints(f"{body_anim.get_name()} frames={frame_count} keys={frame_count + 1}")
    if head_anim is not None:
        mineprep.prints(f"{head_anim.get_name()} frames={frame_count} keys={frame_count + 1}")
    matched_list = list(dict.fromkeys([*batches, *head_extra_batches]))
    return dict(
        body=body_anim,
        head=head_anim,
        clip=clip,
        fps=out_fps,
        frames=frame_count,
        keys=frame_count + 1,
        duration=frame_count / out_fps,
        matched_bones=matched_list,
        matched_curves=list(curve_samples),
        skipped_bones=skipped_bones,
        unsupported_curves=unsupported_curves,
        saved=bool(save),
    )


def _set_playback_bounds(sequence, first, last):
    if first >= sequence.get_playback_end():
        sequence.set_playback_end(last)
        sequence.set_playback_start(first)
    else:
        sequence.set_playback_start(first)
        sequence.set_playback_end(last)
    sequencer_tools._refresh_sequencer()


def bake_animation(actor, sequence, output_path, *, start=None, end=None):
    """返回 body/head 动画资产；[start, end) 为序列帧或秒，省略边界时沿用原播放范围。"""
    components = util.animation_components(actor)
    sequence = sequencer_tools.resolve_sequence(sequence)
    if not isinstance(sequence, unreal.LevelSequence):
        raise ValueError('需要有效的 LevelSequence')
    util._asset_path(str(output_path))
    orig_start = int(sequence.get_playback_start())
    orig_end = int(sequence.get_playback_end())
    first = orig_start if start is None else sequencer_tools._resolve_frame(_valid_time(start, 'start'), sequence)
    last = orig_end if end is None else sequencer_tools._resolve_frame(_valid_time(end, 'end'), sequence)
    if last <= first:
        raise ValueError('烘焙区间结束帧必须晚于起始帧')
    _open_sequence(sequence)
    changed = (first, last) != (orig_start, orig_end)
    if changed:
        _set_playback_bounds(sequence, first, last)
    result = {'body': None, 'head': None}
    try:
        for key, skm in components.items():
            binding = sequencer_tools._ensure_binding(sequence, skm)
            name = str(output_path) + ('_Head' if key == 'head' else '')
            anim = util.open_or_create_anim(name, skm.get_skeletal_mesh_asset().skeleton)
            ok = unreal.SequencerTools.export_anim_sequence(
                mineprep.world(), sequence, anim, util.export_options(), binding, False,
            )
            if not ok:
                mineprep.throw('烘焙动画失败: ' + key)
            if not unreal.EditorAssetLibrary.save_loaded_asset(anim):
                raise RuntimeError('保存动画失败: ' + anim.get_path_name())
            nkeys = int(unreal.AnimationLibrary.get_num_keys(anim) or 0)
            mineprep.prints(anim.get_name() + ' keys=' + str(nkeys))
            result[key] = anim
    finally:
        if changed:
            _set_playback_bounds(sequence, orig_start, orig_end)
        else:
            sequencer_tools._refresh_sequencer()
    return result


def _sequence_for_bake(props):
    if bool(props.CreateNewSequence):
        seq_name = util.ls_name(props.LevelSequenceName)
        if not seq_name:
            mineprep.throw('关卡序列名称为空')
        path = util.SEQ_DIR + '/' + seq_name
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            mineprep.throw('找不到关卡序列: ' + path)
        seq = unreal.load_asset(path)
        if not isinstance(seq, unreal.LevelSequence):
            mineprep.throw('不是关卡序列: ' + path)
        if not unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq):
            mineprep.throw('无法打开关卡序列: ' + path)
        return seq
    seq = sequencer_tools.resolve_sequence()
    if not seq:
        mineprep.throw('未打开 Level Sequence，请先在 Sequencer 中打开或聚焦一个序列')
    return seq
