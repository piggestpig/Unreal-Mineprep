"""Bedrock animation offsets for Mineprep's unified biped_v1 player."""
import unreal


PARENTS = {
    'root': 'none', 'waist': 'root', 'body': 'waist', 'head': 'body',
    'leftarm': 'body', 'rightarm': 'body', 'leftleg': 'root', 'rightleg': 'root',
}


def validate_mesh(component):
    mesh = component.get_skeletal_mesh_asset()
    if not mesh or not mesh.skeleton:
        raise ValueError('biped_v1 需要一体化玩家骨骼网格体')
    pose = mesh.skeleton.get_reference_pose()
    bones = {str(bone).casefold(): bone for bone in pose.get_bone_names()}
    for name, parent in PARENTS.items():
        bone = bones.get(name)
        if bone is None or str(component.get_parent_bone(bone)).casefold() != parent:
            raise ValueError(f'biped_v1 骨骼层级不匹配: {name}')
        rotation = pose.get_ref_bone_pose(bone).rotation
        if rotation.x**2 + rotation.y**2 + rotation.z**2 > 1e-8:
            raise ValueError(f'biped_v1 骨骼参考轴不匹配: {name}')


def rotation_xyz(rotation):
    x, y, z = rotation
    # UE Rotator already uses -X/-Y and +Z in the ZYX rotation product,
    # matching the Bedrock -> Blockbench rotation codec.
    q = unreal.Rotator(roll=x, pitch=y, yaw=z).quaternion()
    # Change basis from Blockbench (X,Y,Z) to UE (-Z,X,Y). The quaternion
    # vector is axial, so the reflection contributes an additional minus sign.
    return unreal.Quat(x=q.z, y=-q.x, z=-q.y, w=q.w).rotator()


def continuous_eulers(angles):
    """Choose the nearest equivalent Euler representation for each sample."""
    result = []
    for roll, pitch, yaw in angles:
        canonical = (roll, pitch, yaw)
        if not result:
            result.append(canonical)
            continue
        previous = result[-1]
        alternate = (roll + 180., 180. - pitch, yaw + 180.)
        candidates = [tuple(value + 360. * round((prior - value) / 360.)
                            for value, prior in zip(choice, previous))
                      for choice in (canonical, alternate)]
        result.append(min(candidates, key=lambda choice: sum(
            (value - prior)**2 for value, prior in zip(choice, previous))))
    return result


def control_samples(channels):
    rotations = [rotation_xyz(value) for value in channels['rotation']]
    angles = continuous_eulers((r.roll, r.pitch, r.yaw) for r in rotations)
    return [unreal.EulerTransform(
        location=unreal.Vector(-p[2], -p[0], p[1]) * 6.25,
        rotation=unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw),
        scale=unreal.Vector(s[2], s[0], s[1]),
    ) for p, (roll, pitch, yaw), s in zip(channels['position'], angles, channels['scale'])]


def compile_controls(samples, count):
    batches = {}
    for bone, channels in samples.items():
        name = bone.casefold()
        control = 'waist' if name == 'hip' else name
        if control not in PARENTS:
            raise ValueError(f'biped_v1 无对应骨骼: {bone}')
        if control in batches:
            raise ValueError(f'多条源骨骼映射到同一控件: {control}')
        batches[control] = control_samples(channels)
    neutral = unreal.EulerTransform(scale=unreal.Vector(1, 1, 1))
    for control in PARENTS:
        if control not in batches:
            batches[control] = [neutral] * count
    return batches
