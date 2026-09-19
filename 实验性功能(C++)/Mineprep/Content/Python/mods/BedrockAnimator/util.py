"""共享常量与解析 / 资产 / 角色辅助。"""
import ast
import os
import re

import mineprep
import unreal

from .props import DEFAULT_BONE_MAP_TEXT

SEQ_DIR = '/Game/mc/anim'
PX = 100.0 / 16.0


def json_file(props):
    raw = props.JsonPath
    if isinstance(raw, str):
        path = raw
    else:
        path = getattr(raw, 'file_path', '') or ''
    s = (path or '').strip()
    for q in ('"', "'", '\u201c', '\u201d', '\u2018', '\u2019'):
        s = s.strip(q)
    return s.strip()


def json_stem(path):
    base = os.path.basename(path or '')
    lower = base.casefold()
    if lower.endswith('.animation.json'):
        return base[:-len('.animation.json')]
    if lower.endswith('.json'):
        return base[:-len('.json')]
    return os.path.splitext(base)[0]


def sanitize_asset(name):
    s = re.sub(r'[^\w]+', '_', str(name or ''), flags=re.UNICODE).strip('_')
    if not s:
        return ''
    if s[0].isdigit():
        s = 'S_' + s
    return s


def ls_name(base):
    name = sanitize_asset(base)
    if not name:
        return ''
    if name.casefold().startswith('ls_'):
        name = name[3:]
    return 'LS_' + name if name else 'LS_Anim'


def body_skm(actor):
    if not isinstance(actor, unreal.Actor):
        return None
    return actor.get_component_by_class(unreal.SkeletalMeshComponent)


def skm_asset_name(actor):
    skm = body_skm(actor)
    mesh = skm.get_skeletal_mesh_asset() if skm else None
    return mesh.get_name() if mesh else ''


def is_skm_actor(obj):
    return bool(body_skm(obj))


def resolve_actor(props):
    target = props.Actor
    if isinstance(target, unreal.Actor):
        if not is_skm_actor(target):
            mineprep.throw('角色没有骨骼网格体')
        return target
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    sel = list(sub.get_selected_level_actors()) if sub else []
    if not sel:
        mineprep.throw('请选择角色')
    first = sel[0]
    if not is_skm_actor(first):
        mineprep.throw('选中的不是骨骼网格体 Actor')
    props.Actor = first
    return first


def suggested_anim_name(props):
    actor = props.Actor if isinstance(props.Actor, unreal.Actor) else None
    skm = skm_asset_name(actor)
    js = json_stem(json_file(props))
    if skm and js:
        return sanitize_asset(skm + '_' + js)
    return sanitize_asset(skm or js)


def sync_asset_names(props):
    anim = suggested_anim_name(props)
    if not anim:
        return
    ls = ls_name(anim)
    if (props.AnimSequenceName or '') != anim:
        props.AnimSequenceName = anim
    if (props.LevelSequenceName or '') != ls:
        props.LevelSequenceName = ls


def ensure_seq_dir():
    if not unreal.EditorAssetLibrary.does_directory_exist(SEQ_DIR):
        unreal.EditorAssetLibrary.make_directory(SEQ_DIR)


def open_or_create_sequence(name):
    path = SEQ_DIR + '/' + name
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        seq = unreal.load_asset(path)
        if not isinstance(seq, unreal.LevelSequence):
            mineprep.throw('已存在但不是关卡序列: ' + path)
    else:
        ensure_seq_dir()
        seq = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, SEQ_DIR, unreal.LevelSequence, unreal.LevelSequenceFactoryNew(),
        )
        if not isinstance(seq, unreal.LevelSequence):
            mineprep.throw('无法创建关卡序列: ' + path)
    if not unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq):
        mineprep.throw('无法打开关卡序列: ' + path)
    return seq


def open_or_create_anim(name, skeleton):
    path = SEQ_DIR + '/' + name
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        anim = unreal.load_asset(path)
        if not isinstance(anim, unreal.AnimSequence):
            mineprep.throw('已存在但不是动画序列: ' + path)
        return anim
    ensure_seq_dir()
    factory = unreal.AnimSequenceFactory()
    factory.set_editor_property('target_skeleton', skeleton)
    anim = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, SEQ_DIR, unreal.AnimSequence, factory,
    )
    if not isinstance(anim, unreal.AnimSequence):
        mineprep.throw('无法创建动画序列: ' + path)
    return anim


def set_playback_seconds(seq, seconds):
    rate = seq.get_display_rate()
    fps = float(rate.numerator) / float(rate.denominator or 1)
    end = max(1, int(round(float(seconds) * fps)))
    unreal.MovieSceneSequenceExtensions.set_playback_start(seq, 0)
    unreal.MovieSceneSequenceExtensions.set_playback_end(seq, end)


def export_options():
    opt = unreal.AnimSeqExportOption()
    opt.set_editor_property('export_transforms', True)
    opt.set_editor_property('export_morph_targets', False)
    opt.set_editor_property('export_attribute_curves', False)
    opt.set_editor_property('export_material_curves', False)
    opt.set_editor_property('record_in_world_space', False)
    opt.set_editor_property('evaluate_all_skeletal_mesh_components', False)
    opt.set_editor_property('use_custom_frame_rate', False)
    opt.set_editor_property('transact_recording', False)
    return opt


def as_xyz(val):
    if isinstance(val, dict):
        val = val.get('post', val.get('pre'))
    if isinstance(val, (int, float)):
        v = float(val)
        return (v, v, v)
    if isinstance(val, str):
        return None
    if isinstance(val, (list, tuple)):
        if any(isinstance(x, str) for x in val):
            return None
        if len(val) == 0:
            return (0.0, 0.0, 0.0)
        if len(val) == 1:
            v = float(val[0])
            return (v, v, v)
        if len(val) >= 3:
            return (float(val[0]), float(val[1]), float(val[2]))
    return None


def parse_channel(ch):
    if ch is None:
        return []
    if not isinstance(ch, dict):
        xyz = as_xyz(ch)
        return [(0.0, xyz)] if xyz else []
    out = []
    for t_s, val in ch.items():
        xyz = as_xyz(val)
        if xyz is None:
            continue
        out.append((float(t_s), xyz))
    out.sort(key=lambda kv: kv[0])
    return out


def idle(keys, rest=0.0):
    return all(abs(v - rest) < 1e-3 for _, trip in keys for v in trip)


def first_anim(data):
    anims = data.get('animations') or {}
    if not anims:
        mineprep.throw('JSON 里没有 animations')
    name = next(iter(anims))
    return name, anims[name]


def parse_axes(spec):
    raw = str(spec or 'xyz').strip().casefold().replace(' ', '')
    axes = []
    i = 0
    while i < len(raw):
        sign = 1.0
        if raw[i] == '+':
            i += 1
        elif raw[i] == '-':
            sign = -1.0
            i += 1
        if i >= len(raw) or raw[i] not in 'xyz':
            mineprep.throw('轴映射无效: ' + str(spec))
        axes.append((raw[i], sign))
        i += 1
    if len(axes) != 3:
        mineprep.throw('轴映射必须是三个轴: ' + str(spec))
    return axes


def remap(xyz, spec):
    src = {'x': float(xyz[0]), 'y': float(xyz[1]), 'z': float(xyz[2])}
    return tuple(src[ax] * sign for ax, sign in parse_axes(spec))


def parse_bone_map(text):
    try:
        data = ast.literal_eval((text or '').strip() or DEFAULT_BONE_MAP_TEXT)
    except (SyntaxError, ValueError) as exc:
        mineprep.throw('骨骼映射不是合法 Python 字典: ' + str(exc))
    if not isinstance(data, dict):
        mineprep.throw('骨骼映射必须是字典')
    out = {}
    for raw, spec in data.items():
        if not isinstance(spec, (tuple, list)) or len(spec) < 1:
            mineprep.throw('映射值应为 (ue_bone, pos, rot, scale): ' + str(raw))
        ue = str(spec[0]).strip()
        if not ue:
            continue
        pos = str(spec[1]) if len(spec) > 1 else 'xyz'
        rot = str(spec[2]) if len(spec) > 2 else 'xyz'
        scl = str(spec[3]) if len(spec) > 3 else 'xyz'
        parse_axes(pos)
        parse_axes(rot)
        parse_axes(scl)
        out[str(raw).casefold().replace(' ', '')] = (ue, pos, rot, scl)
    return out


def resolve_bone_spec(raw_bone, bone_map):
    """Dict hit → (ue_bone, pos, rot, scale). Missing key → same name, native xyz axes."""
    name = str(raw_bone)
    spec = bone_map.get(name.casefold().replace(' ', ''))
    if spec:
        return spec
    return (name, 'xyz', 'xyz', 'xyz')


def has_ctrl(rig, name):
    want = name.casefold()
    for n in rig.names():
        short = n.rsplit('/', 1)[-1].casefold()
        if short.endswith('_curve_control'):
            short = short[:-len('_curve_control')]
        elif short.endswith('_control'):
            short = short[:-len('_control')]
        if short == want or n.casefold() == want:
            return True
    return False


def anim_length(anim, bones):
    length = 0.0
    raw = anim.get('animation_length')
    try:
        length = float(raw)
    except (TypeError, ValueError):
        pass
    tmax = 0.0
    for chans in (bones or {}).values():
        if not isinstance(chans, dict):
            continue
        for key in ('rotation', 'position', 'scale'):
            for t, _ in parse_channel(chans.get(key)):
                if t > tmax:
                    tmax = t
    return max(length, tmax)


def clear_track(rig):
    if not rig or not getattr(rig, 'track', None):
        return
    for section in rig.track.get_sections():
        for ch in section.get_all_channels():
            for k in list(ch.get_keys()):
                ch.remove_key(k)
