"""Bedrock player reference redirection and generic local-offset compilation."""
import unreal

from . import bbmodel, retarget, rig_rules

_GENERIC_ALIASES = rig_rules.GENERIC_ALIASES
PARENTS = {k: ('none' if v is None else v) for k, v in rig_rules.BIPED_PARENTS.items()}
_SOURCE_POSITIONS = rig_rules.BIPED_SOURCE_POSITIONS
TARGET_BONES = rig_rules.BIPED_TARGET_BONES


def rotation_xyz(rotation):
    x, y, z = rotation
    # UE Rotator already uses -X/-Y and +Z in the ZYX rotation product,
    # matching the Bedrock -> Blockbench rotation codec.
    q = unreal.Rotator(roll=x, pitch=y, yaw=z).quaternion()
    # Change basis from Blockbench (X,Y,Z) to UE (-Z,X,Y). The quaternion
    # vector is axial, so the reflection contributes an additional minus sign.
    return unreal.Quat(x=q.z, y=-q.x, z=-q.y, w=q.w).rotator()


def control_samples(channels):
    return [unreal.Transform(
        location=unreal.Vector(*rig_rules.bedrock_pos_to_ue_cm(p)),
        rotation=rotation_xyz(r),
        scale=unreal.Vector(*rig_rules.bedrock_scale_to_ue(s)),
    ) for p, r, s in zip(channels['position'], channels['rotation'], channels['scale'])]


_biped_control_name = rig_rules.biped_control_name


def filter_source_samples(samples, *, reference=None):
    """Partition Bedrock samples into biped-supported channels and unknown/missing-target source bones."""
    matched = {}
    seen = {}
    skipped = []
    missing_targets = {'leftarm': 'left_arm', 'rightarm': 'right_arm'}
    for bone, channels in samples.items():
        control = _biped_control_name(bone)
        if control is None or (reference is not None and control in missing_targets and missing_targets[control] not in reference):
            skipped.append(bone)
            continue
        if control in seen:
            raise ValueError(f'多条源骨骼映射到同一控件: {control}')
        seen[control] = bone
        matched[bone] = channels
    return matched, skipped


def _source_controls(samples, count):
    batches = {}
    for bone, channels in samples.items():
        control = _biped_control_name(bone)
        if control is None:
            raise ValueError(f'Bedrock 玩家参考骨架没有骨骼: {bone}')
        if control in batches:
            raise ValueError(f'多条源骨骼映射到同一控件: {control}')
        batches[control] = control_samples(channels)
    neutral = unreal.Transform()
    for control in PARENTS:
        if control not in batches:
            batches[control] = [neutral] * count
    return batches


def _uniform(scale):
    return scale.x > 0 and abs(scale.x-scale.y) < 1e-6 and abs(scale.x-scale.z) < 1e-6


QUADRUPED_EDIT_BONES = rig_rules.QUADRUPED_EDIT_BONES
QUADRUPED_EDIT_OPTIONAL = rig_rules.QUADRUPED_EDIT_OPTIONAL
_QUADRUPED_EDIT_REPARENTED = rig_rules.QUADRUPED_EDIT_REPARENTED
_QUADRUPED_BODY_CHILDREN = rig_rules.QUADRUPED_BODY_CHILDREN
_QUADRUPED_REQUIRED = rig_rules.QUADRUPED_REQUIRED


def _validate_edit_target(reference, profile, required, optional=None):
    for name, parent in required.items():
        bone = reference.get(name)
        allowed = parent if isinstance(parent, (tuple, list, set, frozenset)) else (parent,)
        if not bone or bone['parent'] not in allowed or not _uniform(bone['local'].scale3d):
            raise ValueError(f'{profile} 骨骼参考姿势不匹配: {name}')
    for name, parents in (optional or {}).items():
        bone = reference.get(name)
        allowed = parents if isinstance(parents, (tuple, list, set, frozenset)) else (parents,)
        if bone and (bone['parent'] not in allowed or not _uniform(bone['local'].scale3d)):
            raise ValueError(f'{profile} 骨骼参考姿势不匹配: {name}')
    if not reference['body']['local'].is_near_equal(unreal.Transform()):
        raise ValueError(f'{profile} 要求 body 与 pelvis 共享髋部枢轴和参考轴')


def validate_target(reference):
    """Ensure the target skeleton matches the reparented Mineprep biped (open or folded arms)."""
    core = {
        name: parent for name, (parent, _) in TARGET_BONES.items()
        if name not in ('left_arm', 'right_arm')
    }
    if 'left_arm' in reference or 'right_arm' in reference:
        required = {**core, 'left_arm': 'body', 'right_arm': 'body'}
        optional = {'arms': ('body',)}
    else:
        required = {**core, 'arms': 'body'}
        optional = None
    _validate_edit_target(reference, 'biped', required, optional)


def validate_quadruped_edit(reference):
    """Ensure the target skeleton matches the reparented Mineprep quadruped edit rig."""
    _validate_edit_target(reference, 'quadruped_edit', QUADRUPED_EDIT_BONES, QUADRUPED_EDIT_OPTIONAL)


def edit_target_parents(reference):
    """Return (profile, required_parents, optional_parents) when reference is a supported edit rig."""
    if 'pelvis' not in reference:
        return None
    if any(b in reference for b in ('left_arm', 'right_arm', 'arms', 'left_leg', 'right_leg')):
        validate_target(reference)
        required = {
            name: parent for name, (parent, _) in TARGET_BONES.items()
            if name != 'pelvis' and name in reference
        }
        if 'arms' in reference and 'left_arm' not in required:
            required['arms'] = 'body'
        return (
            'biped',
            required,
            {'arms': 'body'},
        )
    if any(b in reference for b in ('left_front_leg', 'right_front_leg', 'left_hind_leg', 'right_hind_leg')):
        validate_quadruped_edit(reference)
        optional = {
            name: reference[name]['parent'] if name in reference else allowed[0]
            for name, allowed in QUADRUPED_EDIT_OPTIONAL.items()
        }
        required = {
            name: (reference['head']['parent'] if name == 'head' else parent)
            for name, parent in QUADRUPED_EDIT_BONES.items()
            if name != 'pelvis'
        }
        return (
            'quadruped_edit',
            required,
            optional,
        )
    return None


def _biped_source_layout(reference):
    """Match Bedrock player sockets and translation scale to `reference` proportions."""
    def _vec(name):
        t = reference[name]['reference'].translation
        return (t.x, t.y, t.z)

    positions, scale = rig_rules.biped_source_layout(
        _vec('root'),
        _vec('pelvis'),
        _vec('head') if 'head' in reference else None,
        {name: _vec(name) for name in ('head', 'left_arm', 'right_arm', 'left_leg', 'right_leg') if name in reference},
    )
    return {name: unreal.Transform(location=unreal.Vector(*pos)) for name, pos in positions.items()}, scale


def compile_controls(reference, samples, count, *, ignore_missing_bones=False):
    """Retarget Bedrock player poses to the Mineprep biped."""
    validate_target(reference)
    if not samples:
        raise ValueError('Bedrock 片段没有骨骼通道')
    missing_targets = []
    for bone in samples:
        ctrl = _biped_control_name(bone)
        tgt = {'leftarm': 'left_arm', 'rightarm': 'right_arm'}.get(ctrl)
        if tgt and tgt not in reference and tgt not in missing_targets:
            missing_targets.append(tgt)
    if missing_targets and not ignore_missing_bones:
        raise ValueError(f"目标骨架缺少骨骼: {', '.join(missing_targets)}（跨骨架复用请传 ignore_missing_bones=True）")
    if ignore_missing_bones:
        samples, _ = filter_source_samples(samples, reference=reference)
        if not samples:
            raise ValueError('动画与目标骨架没有可匹配的共有骨骼')
    controls = _source_controls(samples, count)
    if any(not _uniform(value.scale3d) for values in controls.values() for value in values):
        raise ValueError('biped 仅支持正等比缩放')
    source_local, trans_scale = _biped_source_layout(reference)
    source_ref = {}
    for name, parent in PARENTS.items():
        local = source_local[name]
        source_ref[name] = local if parent == 'none' else local.multiply(source_ref[parent])
    def source_frames():
        scale_trans = abs(trans_scale - 1.0) > 1e-6
        for index in range(count):
            pose = {}
            for name, parent in PARENTS.items():
                ctrl = controls[name][index]
                if scale_trans:
                    ctrl = ctrl.copy()
                    ctrl.translation = ctrl.translation * trans_scale
                local = ctrl.multiply(source_local[name])
                pose[name] = local if parent == 'none' else local.multiply(pose[parent])
            yield pose

    mapping = {name: source for name, (_, source) in TARGET_BONES.items() if name in reference}
    return retarget.transfer(reference, source_ref, source_frames(), mapping)


def _lookup_case_safe(key, by_case, ambiguous):
    if key in ambiguous:
        raise ValueError(f'目标骨架存在大小写冲突骨骼: {key}')
    return by_case.get(key)


def _resolve_generic_bone(bone, exact, by_case, ambiguous):
    return rig_rules.resolve_aliased_bone(
        bone, exact, lambda key: _lookup_case_safe(key, by_case, ambiguous),
    )


def _map_source_bones(reference, samples, count, *, ignore_missing_bones=False):
    exact = set(reference)
    by_case, ambiguous = bbmodel.reference_case_map(reference)
    mapped_sources = {}
    matched = {}
    skipped = []
    for src_bone, channels in samples.items():
        target = _resolve_generic_bone(src_bone, exact, by_case, ambiguous)
        if target is None:
            if not ignore_missing_bones:
                raise ValueError(f'目标骨架缺少骨骼: {src_bone}')
            skipped.append(src_bone)
            continue
        if target in mapped_sources:
            raise ValueError(f'多条源骨骼映射到同一目标骨骼: {target} ({mapped_sources[target]}, {src_bone})')
        mapped_sources[target] = src_bone
        if any(min(scale) <= 0.0 for scale in channels['scale']):
            raise ValueError(f'Bedrock 仅支持正缩放: {src_bone}')
        transforms = control_samples(channels)
        if len(transforms) != count:
            raise ValueError(f'{src_bone}: sample count does not match timeline')
        matched[target] = transforms
    return matched, skipped


def compile_generic_controls(reference, samples, count, *, ignore_missing_bones=False):
    """Compile target-local Bedrock channels directly to matching zero-bind-rot controls."""
    if not samples:
        raise ValueError('Bedrock 片段没有骨骼通道')
    matched, skipped = _map_source_bones(
        reference, samples, count, ignore_missing_bones=ignore_missing_bones,
    )
    batches = {}
    for target, transforms in matched.items():
        _, ue_rot, ue_scale = bbmodel.extract_bind_trs(reference[target], target)
        if max(abs(a) for a in ue_rot) > bbmodel.BIND_ROT_TOL_DEG:
            raise ValueError(f'目标 UE 骨骼绑定旋转非零: {target} {ue_rot}')
        if max(abs(s - 1.0) for s in ue_scale) > bbmodel.BIND_SCALE_TOL:
            raise ValueError(f'目标 UE 骨骼绑定缩放非单位值: {target} {ue_scale}')
        batches[target] = retarget.euler_batch(transforms)
    if not batches:
        raise ValueError('动画与目标骨架没有可匹配的共有骨骼')
    return batches, skipped


def compile_quadruped_controls(reference, samples, count, *, ignore_missing_bones=False):
    """Retarget flat Bedrock quadruped animations onto raw or edit quadruped skeletons."""
    if not samples:
        raise ValueError('Bedrock 片段没有骨骼通道')
    for name in _QUADRUPED_REQUIRED:
        bone = reference.get(name)
        if not bone or not _uniform(bone['local'].scale3d):
            raise ValueError(f'quadruped 目标骨架不匹配: {name}')
    edit_rig = 'pelvis' in reference
    if edit_rig:
        validate_quadruped_edit(reference)

    controls, skipped = _map_source_bones(
        reference, samples, count, ignore_missing_bones=ignore_missing_bones,
    )
    if 'pelvis' in controls:
        raise ValueError("quadruped 重定向片段不能直接包含 pelvis；请改用 skeleton_mode='local'")
    for target, transforms in controls.items():
        if any(not _uniform(value.scale3d) for value in transforms):
            raise ValueError(f'quadruped 仅支持正等比缩放: {target}')
    if not controls:
        raise ValueError('动画与目标骨架没有可匹配的共有骨骼')

    src_parents = rig_rules.quadruped_source_parents(
        {name: reference[name]['parent'] for name in reference},
        controls,
        edit_rig=edit_rig,
    )
    active_bones = list(src_parents)
    head_follows_neck = edit_rig and src_parents.get('head') in ('head_parts', 'neck')
    source_ref = {
        name: unreal.Transform(location=reference[name]['reference'].translation)
        for name in active_bones
    }
    source_local = {
        name: (source_ref[name] if src_parents[name] is None
               else source_ref[name].multiply(source_ref[src_parents[name]].inverse()))
        for name in active_bones
    }

    def source_frames():
        for index in range(count):
            pose = {}

            def pose_of(name):
                if name not in pose:
                    ctrl = controls[name][index] if name in controls else unreal.Transform()
                    local = ctrl.multiply(source_local[name])
                    parent = src_parents[name]
                    pose[name] = local if parent is None else local.multiply(pose_of(parent))
                return pose[name]

            for name in active_bones:
                pose_of(name)
            yield pose

    mapping = {name: name for name in active_bones}
    if edit_rig:
        mapping['pelvis'] = None
    batches = retarget.transfer(reference, source_ref, source_frames(), mapping)
    keep = set(controls)
    if edit_rig and 'body' in controls:
        comp_children = _QUADRUPED_BODY_CHILDREN - ({'head'} if head_follows_neck else set())
        keep |= (comp_children & set(batches))
    batches = {name: vals for name, vals in batches.items() if name in keep}
    if not batches:
        raise ValueError('动画与目标骨架没有可匹配的共有骨骼')
    return batches, skipped
