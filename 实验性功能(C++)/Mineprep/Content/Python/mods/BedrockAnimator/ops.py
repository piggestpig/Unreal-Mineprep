"""生成到 Sequencer / 烘焙动画序列。"""
import json
import os

import mineprep
import unreal
import mc_sequencer

from . import util


def apply(mod):
    props = mod.props
    bone_map = util.parse_bone_map(props.BoneMap)
    path = util.json_file(props)
    if not path or not os.path.isfile(path):
        mineprep.throw('找不到 JSON: ' + path)
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    anim_name, anim = util.first_anim(data)
    bones = anim.get('bones') or {}
    had_actor = isinstance(props.Actor, unreal.Actor)
    target = util.resolve_actor(props)
    if not had_actor:
        util.sync_asset_names(props)
    ah = mineprep.actor(target)
    if not ah.target:
        mineprep.throw('找不到角色')
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
    body = ah.rig()
    time_scale = float(props.TimeScale) if props.TimeScale else 1.0
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
                    body.key(ctrl, val, t0 + t * time_scale)
                    nkey += 1
            if create_new:
                util.set_playback_seconds(seq, duration)
    finally:
        mc_sequencer._refresh_sequencer = refresh
        refresh()
    if create_new:
        unreal.EditorAssetLibrary.save_loaded_asset(seq)
    msg = anim_name + ' keys=' + str(nkey)
    if skipped:
        msg += ' skip=' + ','.join(skipped)
    mineprep.prints(msg)
    print('OK APPLY', nkey, anim_name)
    return nkey


def bake(mod):
    props = mod.props
    had_actor = isinstance(props.Actor, unreal.Actor)
    target = util.resolve_actor(props)
    if not had_actor:
        util.sync_asset_names(props)
    skm = util.body_skm(target)
    mesh = skm.get_skeletal_mesh_asset() if skm else None
    skeleton = mesh.skeleton if mesh else None
    if not skeleton:
        mineprep.throw('角色没有骨骼网格体')
    if not (props.AnimSequenceName or '').strip():
        util.sync_asset_names(props)
    anim_name = util.sanitize_asset(props.AnimSequenceName)
    if not anim_name:
        mineprep.throw('动画序列名称为空')
    seq = _sequence_for_bake(props)
    binding = mc_sequencer._ensure_binding(seq, skm)
    anim = util.open_or_create_anim(anim_name, skeleton)
    ok = unreal.SequencerTools.export_anim_sequence(
        mineprep.world(), seq, anim, util.export_options(), binding, False,
    )
    if not ok:
        mineprep.throw('烘焙动画失败')
    unreal.EditorAssetLibrary.save_loaded_asset(anim)
    nkeys = int(unreal.AnimationLibrary.get_num_keys(anim) or 0)
    mineprep.prints(anim_name + ' keys=' + str(nkeys))
    print('OK BAKE', nkeys, anim_name)
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
