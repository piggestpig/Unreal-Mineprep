"""生成到 Sequencer / 烘焙动画序列。"""
import math
from pathlib import Path

import mineprep
import unreal
import mc_sequencer
from mc_rig import Rig, describe_skeleton

from . import bbmodel, biped, curves, java_clip, library, sampling, util


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


def _valid_time(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} 必须为有限整数帧或浮点秒')
    return value


def write_batches(rig, times, prepared, *, replace_span=True,
                  time_unit=mc_sequencer._TIME_UNIT, hold_ticks=()):
    """Replace only the prepared controls within the clip's half-open [start, end) span."""
    rig._key_batches(prepared, 'linear', replace_span=replace_span,
                     time_unit=time_unit, hold_ticks=hold_ticks)
    return len(times) * len(prepared)


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


def _prepare_rig(rig, sequence):
    """Validate or initialize one FK Replace track before any component writes keys."""
    if mc_sequencer.resolve_sequence() != sequence:
        raise RuntimeError('写键前活动关卡序列已改变，请重新调用')
    sections = rig.track.get_sections()
    if len(sections) != 1:
        raise ValueError('动画导入需要单 section 的 FK Replace 轨')
    lib = unreal.ControlRigSequencerLibrary
    if (lib.is_layered_control_rig(rig.target)
            or lib.get_fk_control_rig_apply_mode(rig.target) != unreal.ControlRigFKRigExecuteMode.REPLACE):
        if any(ch.get_num_keys() for ch in sections[0].get_all_channels()):
            raise ValueError('已有动画的 Layered Rig 请改用单 section 的 FK Replace 轨')
        if not lib.set_control_rig_layered_mode(rig.track, False):
            raise RuntimeError('无法切换到 FK Replace 模式')
        yield
        if mc_sequencer.resolve_sequence() != sequence:
            raise RuntimeError('写键前活动关卡序列已改变，请重新调用')
        if (lib.is_layered_control_rig(rig.target)
                or lib.get_fk_control_rig_apply_mode(rig.target) != unreal.ControlRigFKRigExecuteMode.REPLACE):
            raise RuntimeError('无法切换到 FK Replace 模式')


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
        seq = mc_sequencer.resolve_sequence()
        if not seq:
            mineprep.throw('未打开 Level Sequence，请先在 Sequencer 中打开或聚焦一个序列')
        t0 = mineprep.sequencer.frame() if props.StartAtPlayhead else 0
    return apply_animation(path, target, sequence=seq, clip=clip, time_scale=props.TimeScale,
                           start_time=t0, resize_playback=create_new, save=create_new)


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
        mc_sequencer.set_sequence_range(sequence, start_frame, end)
    elif resize:
        old_start = sequence.get_playback_start()
        old_end = sequence.get_playback_end()
        new_start = min(old_start, start_frame)
        new_end = max(old_end, end)
        if (new_start, new_end) != (old_start, old_end):
            mc_sequencer.set_sequence_range(sequence, new_start, new_end)


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


def _resolve_bone_mask(bones, reference):
    if bones is None:
        return None
    by_case, ambiguous = bbmodel.reference_case_map(reference)
    selected = set()
    for name in bones:
        if name in reference:
            selected.add(name)
            continue
        key = name.casefold()
        if key in ambiguous:
            raise ValueError(f'目标骨架存在大小写冲突骨骼: {name}')
        target = by_case.get(key)
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
                   *, bone_mask=None, skeleton_mode=None, ignore_missing_bones=False):
    if skeleton_mode is not None:
        raise ValueError('skeleton_mode 仅适用于 Bedrock 动画')
    if ignore_missing_bones:
        raise ValueError('.bbmodel 动画不支持 ignore_missing_bones；须完整匹配参考骨架')
    from mc_handle import _tick_resolution_sync

    weighted = _tick_resolution_sync() is not None
    fps = 60.0
    tick_rate = 24000.0
    if sequence is not None:
        disp = sequence.get_display_rate()
        fps = disp.numerator / disp.denominator
        res = sequence.get_tick_resolution()
        tick_rate = res.numerator / res.denominator
        start_frame = mc_sequencer._resolve_frame(start_time, sequence)
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
    body = Rig(components['body'], layered=False)
    rigs = {'body': body}
    if head_channels:
        rigs['head'] = Rig(components['head'], layered=False)
    yield
    for rig in rigs.values():
        yield from _prepare_rig(rig, sequence)

    actual_res = sequence.get_tick_resolution()
    actual_tick_rate = actual_res.numerator / actual_res.denominator
    start_frame = mc_sequencer._resolve_frame(start_time, sequence)
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
    with mc_sequencer._defer_refresh(), unreal.ScopedEditorTransaction('Import Blockbench animation'):
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


def _filter_batches_by_mask(batches, bone_mask):
    if bone_mask is None:
        return batches
    filtered = {name: vals for name, vals in batches.items() if name in bone_mask}
    if not filtered:
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
                    bones=None, ignore_missing_bones=False, skeleton_mode=None):
    """Write a clip (by JSON/.bbmodel path, full library key, or parsed dict) to a LevelSequence."""
    time_scale = _validate_time_scale(time_scale)
    start_time = _valid_time(start_time, 'start_time')
    if skeleton_mode not in (None, 'biped', 'quadruped', 'local'):
        raise ValueError("skeleton_mode 须为 None、'biped'、'quadruped' 或 'local'")
    bone_names = _normalize_bones_arg(bones)
    components = util.animation_components(actor)
    reference = describe_skeleton(components['body'])
    bone_mask = _resolve_bone_mask(bone_names, reference)
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
            ignore_missing_bones=bool(ignore_missing_bones),
        ))
    fps = 60.0
    if sequence is not None:
        rate = sequence.get_display_rate()
        fps = rate.numerator / rate.denominator
    left_indices = set()
    skipped_bones = []
    if 'frames' in data:
        if skeleton_mode is not None:
            raise ValueError('skeleton_mode 仅适用于 Bedrock 动画')
        if ignore_missing_bones:
            raise ValueError('Java 动画不支持 ignore_missing_bones；须完整匹配参考骨架')
        batches, count = java_clip.compile_clip(data, reference, fps * time_scale)
        duration = (len(data['frames']) - 1) / float(data['fps'])
        source_times = [min(i / (fps * time_scale), duration) for i in range(count)]
        is_loop = (data['loop'] is True) if 'loop' in data else bool(index_entry and index_entry.get('loop'))
    else:
        mode = _resolve_bedrock_mode(skeleton_mode, index_entry)
        duration, source_times, samples, left_indices = sampling.compile_animation(clip, data, fps * time_scale)
        count = len(source_times)
        is_loop = (data['loop'] is True) if 'loop' in data else bool(index_entry and index_entry.get('loop'))
        batches, skipped_bones = _compile_bedrock_batches(
            mode, reference, samples, count, ignore_missing_bones=bool(ignore_missing_bones),
        )
    batches = _filter_batches_by_mask(batches, bone_mask)
    head_names = (_head_batches(components['head'], reference, batches)
                  if 'head' in components else {})
    created_sequence = sequence is None and bool(destination)
    if created_sequence:
        sequence = util.create_sequence(destination, fps=60)
    _open_sequence(sequence)
    body = Rig(components['body'], layered=False)
    rigs = {'body': body}
    if head_names:
        rigs['head'] = Rig(components['head'], layered=False)
    yield
    for rig in rigs.values():
        yield from _prepare_rig(rig, sequence)
    start_frame = mc_sequencer._resolve_frame(start_time, sequence)
    end = _sequence_end_frame(start_frame, duration, fps, time_scale, loop=is_loop)
    start_tick = body._key_tick(unreal.FrameNumber(start_frame))
    times, batches, hold_ticks = _place_sampled_ticks(
        body, sequence, start_frame, source_times, batches, time_scale, left_indices,
    )
    span_end_tick = max(body._key_tick(unreal.FrameNumber(end)), times[-1] + 1)
    options = dict(time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION, hold_ticks=hold_ticks)
    routed = {'body': batches}
    if 'head' in rigs:
        routed['head'] = {name: batches[name] for name in head_names}
    prepared = {key: _prepare_batches(rig, times, routed[key]) for key, rig in rigs.items()}
    with mc_sequencer._defer_refresh():
        nkey = sum(write_batches(rig, times, prepared[key], replace_span=(start_tick, span_end_tick), **options)
                   for key, rig in rigs.items())
        _update_playback_range(sequence, start_frame, end, created=created_sequence, resize=resize_playback)
    channel_keys = sum(ch.get_num_keys() for rig in rigs.values() for section in rig.track.get_sections()
                       for ch in section.get_all_channels())
    if save and not unreal.EditorAssetLibrary.save_loaded_asset(sequence):
        raise RuntimeError('保存关卡序列失败: ' + sequence.get_path_name())
    if skipped_bones:
        mineprep.prints(f"{clip} skipped missing bones: {', '.join(skipped_bones)}")
    mineprep.prints(clip + ' keys=' + str(nkey))
    return dict(sequence=sequence, actor=actor, clip=clip,
                start_frame=start_frame, end_frame=end,
                keys=nkey, channel_keys=channel_keys,
                matched_bones=list(batches), skipped_bones=skipped_bones)


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
                         ignore_missing_bones=False, skeleton_mode=None):
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
    bone_mask = _resolve_bone_mask(bone_names, reference)
    head_ref = None
    head_shared = set()
    if 'head' in targets:
        head_ref = util.describe_mesh_skeleton(targets['head'])
        head_shared = _matching_head_bones(head_ref, reference)

    clip, data, index_entry = _load_clip_source(json_path, clip)
    skipped_bones = []
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
        duration, source_times, samples, left_indices = sampling.compile_animation(clip, data, eff_fps)
        batches, skipped_bones = _compile_bedrock_batches(
            mode, reference, samples, len(source_times), ignore_missing_bones=bool(ignore_missing_bones),
        )
        batches = _filter_batches_by_mask(batches, bone_mask)
        regular = sampling.regular_times(duration, eff_fps)
        indices = _regular_sample_indices(regular, source_times, left_indices)
        batches = {name: [vals[i] for i in indices] for name, vals in batches.items()}
        frame_count = max(1, len(regular) - 1)
        pad_single = len(regular) == 1

    util.validate_existing_anim(dest_base, targets['body'].skeleton)
    if 'head' in targets:
        util.validate_existing_anim(dest_head, targets['head'].skeleton)

    body_tracks = _offsets_to_local_tracks(reference, batches, pad_single=pad_single)
    body_anim = util.open_or_create_anim(
        dest_base, targets['body'].skeleton, fps=rate, preview_mesh=targets['body'],
    )
    util.write_anim_tracks(body_anim, reference, body_tracks, frame_count, save=bool(save))

    head_anim = None
    if 'head' in targets:
        head_tracks = {name: body_tracks[name] for name in head_shared if name in body_tracks}
        head_anim = util.open_or_create_anim(
            dest_head, targets['head'].skeleton, fps=rate, preview_mesh=targets['head'],
        )
        util.write_anim_tracks(head_anim, head_ref, head_tracks, frame_count, save=bool(save))

    if skipped_bones:
        mineprep.prints(f"{clip} skipped missing bones: {', '.join(skipped_bones)}")
    mineprep.prints(f"{body_anim.get_name()} frames={frame_count} keys={frame_count + 1}")
    if head_anim is not None:
        mineprep.prints(f"{head_anim.get_name()} frames={frame_count} keys={frame_count + 1}")
    return dict(
        body=body_anim,
        head=head_anim,
        clip=clip,
        fps=out_fps,
        frames=frame_count,
        keys=frame_count + 1,
        duration=frame_count / out_fps,
        matched_bones=list(batches),
        skipped_bones=skipped_bones,
        saved=bool(save),
    )


def _set_playback_bounds(sequence, first, last):
    if first >= sequence.get_playback_end():
        sequence.set_playback_end(last)
        sequence.set_playback_start(first)
    else:
        sequence.set_playback_start(first)
        sequence.set_playback_end(last)
    mc_sequencer._refresh_sequencer()


def bake_animation(actor, sequence, output_path, *, start=None, end=None):
    """返回 body/head 动画资产；[start, end) 为序列帧或秒，省略边界时沿用原播放范围。"""
    components = util.animation_components(actor)
    sequence = mc_sequencer.resolve_sequence(sequence)
    if not isinstance(sequence, unreal.LevelSequence):
        raise ValueError('需要有效的 LevelSequence')
    util._asset_path(str(output_path))
    orig_start = int(sequence.get_playback_start())
    orig_end = int(sequence.get_playback_end())
    first = orig_start if start is None else mc_sequencer._resolve_frame(_valid_time(start, 'start'), sequence)
    last = orig_end if end is None else mc_sequencer._resolve_frame(_valid_time(end, 'end'), sequence)
    if last <= first:
        raise ValueError('烘焙区间结束帧必须晚于起始帧')
    _open_sequence(sequence)
    changed = (first, last) != (orig_start, orig_end)
    if changed:
        _set_playback_bounds(sequence, first, last)
    result = {'body': None, 'head': None}
    try:
        for key, skm in components.items():
            binding = mc_sequencer._ensure_binding(sequence, skm)
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
    seq = mc_sequencer.resolve_sequence()
    if not seq:
        mineprep.throw('未打开 Level Sequence，请先在 Sequencer 中打开或聚焦一个序列')
    return seq
