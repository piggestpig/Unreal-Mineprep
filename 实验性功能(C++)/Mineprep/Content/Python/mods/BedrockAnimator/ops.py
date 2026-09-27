"""生成到 Sequencer / 烘焙动画序列。"""
import json
import math
import os

import mineprep
import unreal
import mc_sequencer

from . import util


def apply(mod):
    """面板适配；返回异步句柄，完成后的 result 包含实际写键信息。"""
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
                    start_time=0.0, resize_playback=False, save=False):
    """写入首个 Bedrock 动画。UE 主线程调用；时间为秒，返回 AsyncTaskRunner。"""
    time_scale, start_time = float(time_scale), float(start_time)
    if not math.isfinite(time_scale) or time_scale <= 0 or not math.isfinite(start_time):
        raise ValueError('time_scale 必须为正有限数，start_time 必须为有限数')
    if not util.body_skm(actor):
        raise ValueError('角色没有骨骼网格体')
    bone_map = util.parse_bone_map(bone_map)
    if not json_path or not os.path.isfile(json_path):
        raise FileNotFoundError('找不到 JSON: ' + str(json_path))
    with open(json_path, encoding='utf-8-sig') as f:
        anim_name, anim = util.first_anim(json.load(f))
    bones = anim.get('bones') or {}
    _open_sequence(sequence)
    body = mineprep.actor(actor).rig()
    # 新建 Control Rig 的绑定/通道要经过编辑器一帧才可可靠写键。
    yield
    if mc_sequencer.resolve_sequence() != sequence:
        raise RuntimeError('写键前活动关卡序列已改变，请重新调用')
    duration = util.anim_length(anim, bones) * time_scale
    nkey = 0
    skipped = []
    refresh = mc_sequencer._refresh_sequencer
    mc_sequencer._refresh_sequencer = lambda: None
    try:
        with unreal.ScopedEditorTransaction('Bedrock anim ' + anim_name):
            util.clear_track(body)
            for raw_bone, chans in bones.items():
                spec = util.resolve_bone_spec(raw_bone, bone_map)
                ctrl, pos_spec, rot_spec, scl_spec = spec
                if not util.has_ctrl(body, ctrl):
                    skipped.append(str(raw_bone) + '->' + ctrl)
                    continue
                rots = util.parse_channel(chans.get('rotation'))
                has_pos = 'position' in chans
                has_scl = 'scale' in chans
                poss = util.parse_channel(chans.get('position')) if has_pos else []
                scls = util.parse_channel(chans.get('scale')) if has_scl else []
                if util.idle(rots) and util.idle(poss) and util.idle(scls, 1.0):
                    continue
                times = sorted({t for t, _ in rots} | {t for t, _ in poss} | {t for t, _ in scls})
                ri = pi = si = 0
                last_r = (0.0, 0.0, 0.0)
                last_p = (0.0, 0.0, 0.0)
                last_s = (1.0, 1.0, 1.0)
                for t in times:
                    while ri < len(rots) and rots[ri][0] <= t:
                        last_r = rots[ri][1]
                        ri += 1
                    while pi < len(poss) and poss[pi][0] <= t:
                        last_p = poss[pi][1]
                        pi += 1
                    while si < len(scls) and scls[si][0] <= t:
                        last_s = scls[si][1]
                        si += 1
                    rx, ry, rz = util.remap(last_r, rot_spec)
                    rot = unreal.Rotator(pitch=ry, yaw=rz, roll=rx)
                    if has_pos or has_scl:
                        loc = unreal.Vector(*util.remap(last_p, pos_spec)) * util.PX if has_pos else unreal.Vector(0, 0, 0)
                        sx, sy, sz = util.remap(last_s, scl_spec) if has_scl else (1.0, 1.0, 1.0)
                        val = unreal.EulerTransform(
                            location=loc, rotation=rot, scale=unreal.Vector(sx, sy, sz),
                        )
                    else:
                        val = rot
                    body.key(ctrl, val, float(start_time + t * time_scale))
                    nkey += 1
            if resize_playback:
                util.set_playback_seconds(sequence, max(0.0, start_time) + duration)
    finally:
        mc_sequencer._refresh_sequencer = refresh
        refresh()
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
