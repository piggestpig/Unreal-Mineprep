"""共享常量与解析 / 资产 / 角色辅助。"""
from collections.abc import Mapping
from fractions import Fraction
import math
import os
import re

import mineprep
import unreal

SEQ_DIR = '/Game/mc/anim'


def json_file(props):
    return props.JsonPath.file_path.strip().strip('"')


def json_stem(path):
    base = os.path.basename(path or '')
    lower = base.casefold()
    if lower.endswith('.animation.json'):
        return base[:-len('.animation.json')]
    if lower.endswith('.clip.json'):
        return base[:-len('.clip.json')]
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
    if isinstance(actor, unreal.SkeletalMeshActor):
        return actor.skeletal_mesh_component
    return actor.get_component_by_class(unreal.SkeletalMeshComponent)


def animation_components(actor):
    """主网格与 VanillaMobLoader 挂在 head 骨骼上的独立 Head 网格。"""
    body = body_skm(actor)
    if not body or not body.get_skeletal_mesh_asset():
        raise ValueError('角色没有骨骼网格体')
    result = {'body': body}
    for component in actor.get_components_by_class(unreal.SkeletalMeshComponent):
        if (component != body and component.get_name() == 'Head'
                and component.get_attach_parent() == body
                and str(component.get_attach_socket_name()) == 'head'
                and component.get_skeletal_mesh_asset()):
            result['head'] = component
            break
    return result


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


def suggested_anim_name(props, clip):
    actor = props.Actor if isinstance(props.Actor, unreal.Actor) else None
    skm = skm_asset_name(actor)
    js = clip or json_stem(json_file(props))
    if skm and js:
        return sanitize_asset(skm + '_' + js)
    return sanitize_asset(skm or js)


def sync_asset_names(props, clip=None):
    anim = suggested_anim_name(props, clip)
    if not anim:
        return
    ls = ls_name(anim)
    if (props.AnimSequenceName or '') != anim:
        props.AnimSequenceName = anim
    if (props.LevelSequenceName or '') != ls:
        props.LevelSequenceName = ls


def _asset_path(name):
    path = str(name or '').strip()
    path = path if path.startswith('/') else SEQ_DIR + '/' + path
    if not path.startswith('/Game/') or any(p in ('', '.', '..') for p in path[1:].split('/')):
        raise ValueError('需要 /Game/.../Name 资产路径')
    return path


def find_sequence(name):
    path = _asset_path(name)
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        seq = unreal.load_asset(path)
        if not isinstance(seq, unreal.LevelSequence):
            mineprep.throw('已存在但不是关卡序列: ' + path)
        return seq


def create_sequence(name, *, fps):
    path = _asset_path(name)
    directory, name = path.rsplit('/', 1)
    unreal.EditorAssetLibrary.make_directory(directory)
    seq = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, directory, unreal.LevelSequence, unreal.LevelSequenceFactoryNew(),
    )
    if not isinstance(seq, unreal.LevelSequence):
        mineprep.throw('无法创建关卡序列: ' + path)
    seq.set_display_rate(unreal.FrameRate(numerator=fps, denominator=1))
    return seq


def normalize_frame_rate(fps):
    """将数值帧率、(num, den) 或 unreal.FrameRate 规范化为正有理 FrameRate。"""
    if isinstance(fps, unreal.FrameRate):
        num, den = int(fps.numerator), int(fps.denominator)
    elif (isinstance(fps, tuple) and len(fps) == 2
          and all(isinstance(v, int) and not isinstance(v, bool) for v in fps)):
        num, den = int(fps[0]), int(fps[1])
    elif isinstance(fps, bool) or not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps <= 0:
        raise ValueError('fps 须为正有限数、(num, den) 或 unreal.FrameRate')
    elif isinstance(fps, int) or abs(fps - round(fps)) <= 1e-6:
        num, den = int(round(fps)), 1
    else:
        frac = Fraction(str(round(float(fps), 6))).limit_denominator(10000)
        num, den = frac.numerator, frac.denominator
    if num <= 0 or den <= 0:
        raise ValueError('fps 分子和分母必须为正整数')
    return unreal.FrameRate(numerator=num, denominator=den)


def _anim_frame_rates(anim):
    dm = unreal.load_object(None, anim.get_editor_property('data_model_interface').get_path_name())
    dm_rate = dm.get_frame_rate()
    ptfr = anim.get_editor_property('platform_target_frame_rate').get_editor_property('default')
    return (int(dm_rate.numerator), int(dm_rate.denominator)), (int(ptfr.numerator), int(ptfr.denominator))


def _unwrap_target_obj(obj):
    if not isinstance(obj, (unreal.Object, str, Mapping, tuple, list)) and hasattr(obj, 'target'):
        return obj.target
    return obj


def _resolve_mesh_asset(slot, label='target'):
    slot = _unwrap_target_obj(slot)
    if isinstance(slot, str):
        path = slot.strip()
        if not path:
            raise ValueError(f'{label} 资产路径不能为空')
        loaded = unreal.load_asset(path)
        if loaded is None:
            raise ValueError(f'找不到 {label} 骨骼资产: {path}')
        slot = loaded
    if isinstance(slot, unreal.Actor):
        skm = body_skm(slot)
        if not skm:
            raise ValueError(f'{label} Actor 没有 SkeletalMeshComponent')
        slot = skm
    if isinstance(slot, unreal.SkeletalMeshComponent):
        mesh = slot.get_skeletal_mesh_asset()
        if not mesh:
            raise ValueError(f'{label} SkeletalMeshComponent 没有分配 SkeletalMesh')
        return mesh
    if isinstance(slot, unreal.SkeletalMesh):
        return slot
    if isinstance(slot, unreal.Skeleton):
        preview = slot.get_skeleton_preview_mesh()
        if preview is None:
            raise ValueError(f'{label} Skeleton 缺少 PreviewMesh，无法解析骨骼层级；请传 SkeletalMesh、路径或 Actor')
        return preview
    raise ValueError(f'{label} 须为 SkeletalMesh、SkeletalMeshComponent、Actor 或资产路径，当前: {type(slot).__name__}')


def resolve_skeleton_targets(target):
    """解析无 UI 直写目标，返回 {'body': USkeletalMesh, 可选 'head': USkeletalMesh}。"""
    target = _unwrap_target_obj(target)
    if isinstance(target, unreal.Actor):
        comps = animation_components(target)
        return {key: comp.get_skeletal_mesh_asset() for key, comp in comps.items()}
    if isinstance(target, Mapping):
        if 'body' not in target or target['body'] is None:
            raise ValueError("target 映射必须包含非空的 'body' 网格")
        result = {'body': _resolve_mesh_asset(target['body'], 'body')}
        if target.get('head') is not None:
            result['head'] = _resolve_mesh_asset(target['head'], 'head')
        return result
    if isinstance(target, (tuple, list)):
        if len(target) != 2 or target[0] is None:
            raise ValueError('target 元组/列表须为 (body, head)')
        result = {'body': _resolve_mesh_asset(target[0], 'body')}
        if target[1] is not None:
            result['head'] = _resolve_mesh_asset(target[1], 'head')
        return result
    return {'body': _resolve_mesh_asset(target, 'body')}


def _build_skeleton_reference(entries):
    axes = [unreal.Vector(x, y, z) for x, y, z in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    bones = {}
    for name, parent, local in entries:
        reference = local if parent is None else local.multiply(bones[parent]['reference'])
        bones[name] = dict(
            parent=parent,
            local=local,
            reference=reference,
            pivot=reference.translation,
            axes=dict(zip('xyz', (reference.rotation.rotate_vector(axis) for axis in axes))),
        )
    return bones


def describe_mesh_skeleton(target):
    """无需关卡 Actor，直接读取组件或 SkeletalMesh / Skeleton 的参考骨架信息。"""
    target = _unwrap_target_obj(target)
    if isinstance(target, unreal.SkeletalMeshComponent):
        from mineprep.rig import describe_skeleton
        return describe_skeleton(target)
    mesh = _resolve_mesh_asset(target, 'skeleton')
    get_bounds = getattr(getattr(unreal, 'mineprep', None), 'get_bone_local_bounds', None)
    if get_bounds is not None:
        bounds, err = get_bounds(mesh)
        if not err and bounds:
            entries = [
                (
                    str(entry.bone_name),
                    None if str(entry.parent_bone_name).casefold() == 'none' else str(entry.parent_bone_name),
                    entry.local_transform,
                )
                for entry in bounds
            ]
            return _build_skeleton_reference(entries)
    pose = unreal.AnimPoseExtensions.get_reference_pose(mesh.skeleton)
    entries = []
    for bone_name in unreal.AnimPoseExtensions.get_bone_names(pose):
        parent = str(mesh.get_bone_parent(bone_name))
        entries.append((
            str(bone_name),
            None if parent.casefold() == 'none' else parent,
            unreal.AnimPoseExtensions.get_bone_pose(pose, bone_name, space=unreal.AnimPoseSpaces.LOCAL),
        ))
    return _build_skeleton_reference(entries)


def validate_existing_anim(name, skeleton, *, fps=None):
    path = _asset_path(name)
    if not unreal.EditorAssetLibrary.does_asset_exist(path):
        return False
    rate = normalize_frame_rate(fps) if fps is not None else None
    target_tuple = (int(rate.numerator), int(rate.denominator)) if rate else None
    _check_existing_anim_rate(path, skeleton, target_tuple)
    return True


def _check_existing_anim_rate(path, skeleton, target_tuple):
    anim = unreal.load_asset(path)
    if not isinstance(anim, unreal.AnimSequence):
        mineprep.throw('已存在但不是动画序列: ' + path)
    if anim.get_editor_property('skeleton') != skeleton:
        raise ValueError('已有动画使用不同骨架: ' + path)
    if target_tuple is None:
        return anim
    dm_tuple, ptfr_tuple = _anim_frame_rates(anim)
    if dm_tuple != target_tuple or ptfr_tuple != target_tuple:
        raise ValueError(
            f'已有动画帧率不匹配: {path}，期望 {target_tuple}，'
            f'实际 data={dm_tuple} platform={ptfr_tuple}；请使用新的输出路径'
        )
    return anim


def open_or_create_anim(name, skeleton, *, fps=None, preview_mesh=None):
    path = _asset_path(name)
    directory, asset_name = path.rsplit('/', 1)
    target_rate = normalize_frame_rate(fps) if fps is not None else None
    target_tuple = (int(target_rate.numerator), int(target_rate.denominator)) if target_rate else None
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return _check_existing_anim_rate(path, skeleton, target_tuple)
    unreal.EditorAssetLibrary.make_directory(directory)
    factory = unreal.AnimSequenceFactory()
    factory.set_editor_property('target_skeleton', skeleton)
    if preview_mesh is not None:
        factory.set_editor_property('preview_skeletal_mesh', preview_mesh)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    if target_rate is not None:
        settings = unreal.get_default_object(unreal.AnimationSettings)
        orig_rate = settings.get_editor_property('default_frame_rate')
        settings.set_editor_property('default_frame_rate', target_rate)
        try:
            anim = asset_tools.create_asset(asset_name, directory, unreal.AnimSequence, factory)
        finally:
            settings.set_editor_property('default_frame_rate', orig_rate)
    else:
        anim = asset_tools.create_asset(asset_name, directory, unreal.AnimSequence, factory)
    if not isinstance(anim, unreal.AnimSequence):
        mineprep.throw('无法创建动画序列: ' + path)
    if target_tuple is not None:
        dm_tuple, ptfr_tuple = _anim_frame_rates(anim)
        if dm_tuple != target_tuple or ptfr_tuple != target_tuple:
            raise RuntimeError(f'创建动画帧率不一致: 期望 {target_tuple}，实际 data={dm_tuple} platform={ptfr_tuple}')
    return anim


def write_anim_tracks(anim, reference, animated_tracks, frame_count, *, float_curves=None, save=True):
    """向 AnimSequence 写入全骨骼局部轨道与可选浮点表情曲线；未动画骨骼保持绑定姿势。"""
    nframes = max(1, int(frame_count))
    nkeys = nframes + 1
    ctrl = anim.controller
    dm = unreal.load_object(None, anim.get_editor_property('data_model_interface').get_path_name())
    dm_rate = dm.get_frame_rate()
    fps_val = dm_rate.numerator / dm_rate.denominator
    ctrl.open_bracket('Export MCAnimConverter AnimSequence', should_transact=False)
    try:
        ctrl.remove_all_bone_tracks(should_transact=False)
        ctrl.remove_all_curves_of_type(unreal.RawCurveTrackTypes.RCT_FLOAT, should_transact=False)
        if int(dm.get_number_of_frames()) != nframes:
            ctrl.set_number_of_frames(unreal.FrameNumber(nframes), should_transact=False)
        for bone_name, ref_entry in reference.items():
            transforms = animated_tracks.get(bone_name)
            if transforms is None:
                transforms = [ref_entry['local']] * nkeys
            elif len(transforms) != nkeys:
                raise ValueError(f'{bone_name}: 采样键数 {len(transforms)} 与目标帧数 {nkeys} 不一致')
            pos_keys = []
            rot_keys = []
            scale_keys = []
            prev_q = None
            for tf in transforms:
                pos_keys.append(tf.translation)
                q = tf.rotation
                if prev_q is not None and (prev_q.x * q.x + prev_q.y * q.y + prev_q.z * q.z + prev_q.w * q.w) < 0.0:
                    q = unreal.Quat(-q.x, -q.y, -q.z, -q.w)
                rot_keys.append(q)
                scale_keys.append(tf.scale3d)
                prev_q = q
            bname = unreal.Name(bone_name)
            ctrl.add_bone_curve(bname, should_transact=False)
            ctrl.set_bone_track_keys(bname, pos_keys, rot_keys, scale_keys, should_transact=False)
        for curve_name, values in (float_curves or {}).items():
            vals = list(values)
            if len(vals) == 1 and nkeys == 2:
                vals = [vals[0], vals[0]]
            if len(vals) != nkeys:
                raise ValueError(f'{curve_name}: 曲线采样键数 {len(vals)} 与目标帧数 {nkeys} 不一致')
            cid = unreal.AnimationCurveIdentifierExtensions.set_curve_identifier(
                unreal.AnimationCurveIdentifier(),
                unreal.Name(curve_name),
                unreal.RawCurveTrackTypes.RCT_FLOAT,
            )
            ctrl.add_curve(cid, should_transact=False)
            rkeys = [unreal.RichCurveKey(time=i / fps_val, value=float(v)) for i, v in enumerate(vals)]
            ctrl.set_curve_keys(cid, rkeys, should_transact=False)
    finally:
        ctrl.close_bracket(should_transact=False)
    if save and not unreal.EditorAssetLibrary.save_loaded_asset(anim, only_if_is_dirty=False):
        raise RuntimeError('保存动画失败: ' + anim.get_path_name())
    return anim


def export_options():
    opt = unreal.AnimSeqExportOption()
    opt.set_editor_property('export_transforms', True)
    opt.set_editor_property('export_morph_targets', True)
    opt.set_editor_property('export_attribute_curves', True)
    opt.set_editor_property('export_material_curves', True)
    opt.set_editor_property('record_in_world_space', False)
    opt.set_editor_property('evaluate_all_skeletal_mesh_components', False)
    opt.set_editor_property('use_custom_frame_rate', False)
    opt.set_editor_property('transact_recording', False)
    return opt






