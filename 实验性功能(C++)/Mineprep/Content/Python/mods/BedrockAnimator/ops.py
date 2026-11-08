"""生成到 Sequencer / 烘焙动画序列。"""
import json
import math
import os

import mineprep
import unreal
import mc_sequencer

from . import biped, sampling, util


def write_batches(rig, times, batches):
    """All values/names must be compiled before replacing the track."""
    prepared = [(rig._resolve_name(name), unreal.Array.cast(unreal.EulerTransform, values))
                for name, values in batches.items()]
    for name, values in prepared:
        if len(values) != len(times):
            raise ValueError(name + ': sample count does not match times')
        if rig._type(name) != unreal.RigControlType.EULER_TRANSFORM:
            raise ValueError(name + ': numeric bone import requires EulerTransform control')
    with unreal.ScopedEditorTransaction('Import numeric Bedrock animation'):
        rig.clear()
        for name, values in prepared:
            rig.keyframes(name, times, values)
        for section in rig.track.get_sections():
            for ch in section.get_all_channels():
                if isinstance(ch, (unreal.MovieSceneScriptingFloatChannel, unreal.MovieSceneScriptingDoubleChannel)):
                    for key in ch.get_keys():
                        key.set_interpolation_mode(unreal.RichCurveInterpMode.RCIM_LINEAR)
    mc_sequencer._refresh_sequencer()
    return len(times) * len(prepared)


def apply(mod):
    """从面板属性读取参数并启动动画转换任务。"""
    props = mod.props
    had_actor = isinstance(props.Actor, unreal.Actor)
    target = util.resolve_actor(props)
    if not had_actor:
        util.sync_asset_names(props)
    create_new = bool(props.CreateNewSequence)
    if create_new:
        if not (props.LevelSequenceName or '').strip():
            util.sync_asset_names(props)
        seq_name = util.ls_name(props.LevelSequenceName)
        if not seq_name:
            mineprep.throw('关卡序列名称为空')
        seq = util.open_or_create_sequence(seq_name)
        t0 = 0.0
    else:
        seq = mc_sequencer.resolve_sequence()
        if not seq:
            mineprep.throw('未打开 Level Sequence，请先在 Sequencer 中打开或聚焦一个序列')
        t0 = mineprep.sequencer.time() if props.StartAtPlayhead else 0.0
    return apply_animation(util.json_file(props), target, sequence=seq,
                           bone_map=props.BoneMap, time_scale=props.TimeScale or 1.0,
                           start_time=t0, resize_playback=create_new, save=create_new)


def _open_sequence(sequence):
    if not isinstance(sequence, unreal.LevelSequence):
        raise ValueError('需要有效的 LevelSequence')
    if not unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence):
        raise RuntimeError('无法打开关卡序列: ' + sequence.get_path_name())


@mineprep.asynctask
def apply_animation(json_path, actor, *, sequence, bone_map=None, time_scale=1.0,
                    start_time=0.0, resize_playback=False, save=False, profile=None):
    """读取 JSON 中的首个基岩版动画，并写入目标角色在关卡序列中的 Control Rig 轨道。"""
    time_scale, start_time = float(time_scale), float(start_time)
    if not math.isfinite(time_scale) or time_scale <= 0 or not math.isfinite(start_time):
        raise ValueError('time_scale 必须为正有限数，start_time 必须为有限数')
    component = util.body_skm(actor)
    if not component:
        raise ValueError('角色没有骨骼网格体')
    if profile not in (None, 'biped_v1'):
        raise ValueError(f'未知动画配置: {profile}')
    if profile == 'biped_v1':
        if bone_map is not None:
            raise ValueError('biped_v1 与 bone_map 不能同时指定')
        biped.validate_mesh(component)
    else:
        bone_map = util.parse_bone_map(bone_map)
    if not json_path or not os.path.isfile(json_path):
        raise FileNotFoundError('找不到 JSON: ' + str(json_path))
    with open(json_path, encoding='utf-8-sig') as f:
        data = json.load(f)
    if 'animation_controllers' in data:
        raise ValueError('animation_controllers are unsupported')
    anim_name, anim = util.first_anim(data)
    rate = sequence.get_display_rate()
    fps = rate.numerator / rate.denominator
    duration, source_times, samples = sampling.compile_animation(anim_name, anim, fps * time_scale)
    if profile == 'biped_v1':
        batches = biped.compile_controls(samples, len(source_times))
    _open_sequence(sequence)
    body = mineprep.actor(actor).rig()
    yield
    if mc_sequencer.resolve_sequence() != sequence:
        raise RuntimeError('写键前活动关卡序列已改变，请重新调用')
    skipped = []
    if profile == 'biped_v1':
        lib = unreal.ControlRigSequencerLibrary
        if lib.get_fk_control_rig_apply_mode(body.target) != unreal.ControlRigFKRigExecuteMode.REPLACE:
            if not lib.set_control_rig_layered_mode(body.track, False):
                raise RuntimeError('无法切换到 FK Replace 模式')
            yield
            if mc_sequencer.resolve_sequence() != sequence:
                raise RuntimeError('写键前活动关卡序列已改变，请重新调用')
        start_frame = mc_sequencer._resolve_frame(start_time, sequence)
        times = range(start_frame, start_frame + len(source_times))
        end_frame = times.stop
    else:
        times = [float(start_time + t * time_scale) for t in source_times]
        end_frame = int(round((start_time + duration*time_scale)*fps)) + 1
        batches, skipped = _mapped_controls(body, samples, bone_map)
    nkey = write_batches(body, times, batches)
    if resize_playback:
        sequence.set_playback_end(end_frame)
    channel_keys = sum(ch.get_num_keys() for section in body.track.get_sections()
                       for ch in section.get_all_channels())
    if nkey and not channel_keys:
        raise RuntimeError('Control Rig 未写入关键帧')
    if save and not unreal.EditorAssetLibrary.save_loaded_asset(sequence):
        raise RuntimeError('保存关卡序列失败: ' + sequence.get_path_name())
    msg = anim_name + ' keys=' + str(nkey)
    if skipped:
        msg += ' skip=' + ','.join(skipped)
    mineprep.prints(msg)
    print('OK APPLY', nkey, anim_name)
    return dict(sequence=sequence, actor=actor, keys=nkey,
                channel_keys=channel_keys, skipped=skipped)


def _mapped_controls(body, samples, bone_map):
    batches, skipped = {}, []
    for raw_bone, channels in samples.items():
        ctrl, pos_spec, rot_spec, scl_spec = util.resolve_bone_spec(raw_bone, bone_map)
        if not util.has_ctrl(body, ctrl):
            skipped.append(str(raw_bone) + '->' + ctrl)
            continue
        full = body._resolve_name(ctrl)
        if full in batches:
            raise ValueError('Multiple source bones map to ' + full)
        values = []
        for p, r, s in zip(channels['position'], channels['rotation'], channels['scale']):
            rx, ry, rz = util.remap(r, rot_spec)
            values.append(unreal.EulerTransform(
                location=unreal.Vector(*util.remap(p, pos_spec)) * util.PX,
                rotation=unreal.Rotator(roll=rx, pitch=ry, yaw=rz),
                scale=unreal.Vector(*util.remap(s, scl_spec))))
        batches[full] = values
    return batches, skipped


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


def bake_animation(actor, sequence, output_path):
    """烘焙为 AnimSequence 并保存；output_path 可为名称或 /Game/... 资产路径。"""
    skm = util.body_skm(actor)
    mesh = skm.get_skeletal_mesh_asset() if skm else None
    if not mesh or not mesh.skeleton:
        raise ValueError('角色没有骨骼网格体')
    _open_sequence(sequence)
    binding = mc_sequencer._ensure_binding(sequence, skm)
    anim = util.open_or_create_anim(output_path, mesh.skeleton)
    ok = unreal.SequencerTools.export_anim_sequence(
        mineprep.world(), sequence, anim, util.export_options(), binding, False,
    )
    if not ok:
        mineprep.throw('烘焙动画失败')
    if not unreal.EditorAssetLibrary.save_loaded_asset(anim):
        raise RuntimeError('保存动画失败: ' + anim.get_path_name())
    nkeys = int(unreal.AnimationLibrary.get_num_keys(anim) or 0)
    mineprep.prints(anim.get_name() + ' keys=' + str(nkeys))
    return anim


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
