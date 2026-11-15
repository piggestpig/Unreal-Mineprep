"""Read Java model-part samples exported by the Mineprep prototype."""
import math

import unreal

from . import biped, retarget


def _transform(matrix):
    if len(matrix) != 16 or not all(math.isfinite(v) for v in matrix):
        raise ValueError('Java pose must contain 16 finite matrix values')
    x = unreal.Vector(matrix[10], matrix[8], matrix[9])
    y = unreal.Vector(matrix[2], matrix[0], matrix[1])
    z = unreal.Vector(matrix[6], matrix[4], matrix[5])
    scale = x.length()
    if scale <= 0 or max(abs(y.length()-scale), abs(z.length()-scale)) > 1e-5:
        raise ValueError('Java pose requires positive uniform scale')
    return unreal.Transform(
        location=unreal.Vector(-100*matrix[14], -100*matrix[12], 150-100*matrix[13]),
        rotation=unreal.MathLibrary.make_rot_from_xy(x, y),
        scale=unreal.Vector(scale, scale, scale),
    )


def _local_transform(pose, root):
    x, y, z, qx, qy, qz, qw, sx, sy, sz = pose
    # Java (X right-to-left, Y down, Z back) to UE (-Z, -X, -Y).
    # The reflected basis flips the quaternion vector's sign as well.
    return unreal.Transform(
        location=unreal.Vector(-z * 6.25, -x * 6.25, (24 * root - y) * 6.25),
        rotation=unreal.Quat(x=qz, y=qx, z=qy, w=qw).rotator(),
        scale=unreal.Vector(sz, sx, sy),
    )


def _resample(sampled, count, rate):
    for index in range(count):
        time = min(index * rate, len(sampled) - 1)
        a = int(time)
        poses = sampled[a]
        if time > a:
            poses = [unreal.MathLibrary.t_lerp(v, w, time - a)
                     for v, w in zip(poses, sampled[a + 1], strict=True)]
        yield poses


def compile_clip(data, reference, output_fps):
    bones = data['bones']
    names = [bone['name'] for bone in bones]
    if not names or len(names) != len(set(names)):
        raise ValueError('Java clip needs unique bone names')
    parents = {}
    for index, (name, bone) in enumerate(zip(names, bones)):
        parent = bone['parent']
        if type(parent) is not int or parent >= index or parent < -1:
            raise ValueError(f'Invalid Java parent for {name}')
        parents[name] = None if parent == -1 else names[parent]
    mapping = dict(zip(names, names))
    local = data.get('space') == 'local_trs'
    edit_target = biped.edit_target_parents(reference) if 'pelvis' not in parents else None
    if edit_target is not None:
        if local:
            raise ValueError('Local TRS clip needs the original bind hierarchy')
        profile, required_parents, optional_parents = edit_target
        for name, parent in required_parents.items():
            if name == 'root':
                expected_sources = (None,)
            elif parent == 'pelvis':
                expected_sources = ('root',)
            elif parent == 'body':
                expected_sources = ('root', 'body')
            else:
                expected_sources = (parent,)
            if name not in parents or parents[name] not in expected_sources:
                raise ValueError(f'{profile} Java source hierarchy does not match: {name}')
            parents[name] = parent
        for name, parent in optional_parents.items():
            if parents.get(name) == 'root' and reference.get(name, {}).get('parent') == parent:
                parents[name] = parent
        parents['pelvis'] = 'root'
        mapping['pelvis'] = None
    for name, parent in parents.items():
        if name not in reference or reference[name]['parent'] != parent:
            raise ValueError(f'Java clip hierarchy does not match: {name}')

    source_fps = float(data['fps'])
    frames = data['frames']
    if not math.isfinite(source_fps) or source_fps <= 0 or not frames:
        raise ValueError('Java clip requires frames and a positive sample rate')
    if len(data['bind']) != len(names) or any(len(frame) != len(names) for frame in frames):
        raise ValueError('Java clip sample count does not match its bones')
    count = math.ceil((len(frames)-1)*output_fps/source_fps-1e-8)+1
    rate = source_fps / output_fps

    if local:
        def decode(frame):
            return [_local_transform(pose, parents[name] is None)
                    for name, pose in zip(names, frame, strict=True)]

        binds = decode(data['bind'])
        for name, rest in zip(names, binds, strict=True):
            if not rest.is_near_equal(reference[name]['local'], 1e-4):
                raise ValueError(f'Local TRS clip needs the original bind pose: {name}')
        offsets = {name: [] for name in names}
        for poses in _resample([decode(frame) for frame in frames], count, rate):
            for name, pose, rest in zip(names, poses, binds, strict=True):
                offsets[name].append(pose.make_relative(rest))
        return {name: retarget.euler_batch(values) for name, values in offsets.items()}, count

    binds = dict(zip(names, map(_transform, data['bind']), strict=True))
    sampled = [[_transform(matrix) for matrix in frame] for frame in frames]
    source_frames = (dict(zip(names, poses, strict=True)) for poses in _resample(sampled, count, rate))
    return retarget.transfer(reference, binds, source_frames, mapping), count
