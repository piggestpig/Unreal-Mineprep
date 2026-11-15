"""Transfer component-space skin deltas, then solve target-local FK offsets."""
import unreal


def continuous_eulers(angles):
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


def transfer(reference, source_bind, source_frames, mapping):
    """Mapping is target -> source. A None source keeps the target's local bind."""
    names = [name for name in reference if name in mapping]
    binds = {name: reference[name]['reference'].multiply(source_bind[source].inverse())
             for name, source in mapping.items() if source is not None}
    offsets = {name: [] for name in names}
    for frame in source_frames:
        poses = {}
        for name in names:
            parent = reference[name]['parent']
            rest = reference[name]['local']
            source = mapping[name]
            if source is None:
                poses[name] = rest.multiply(poses[parent]) if parent else rest
                offsets[name].append(unreal.Transform())
                continue
            pose = binds[name].multiply(frame[source])
            poses[name] = pose
            local = pose.make_relative(poses[parent]) if parent else pose
            offsets[name].append(local.make_relative(rest))
    return {name: euler_batch(values) for name, values in offsets.items()}


def euler_batch(transforms):
    rotations = (t.rotation.rotator() for t in transforms)
    angles = continuous_eulers((r.roll, r.pitch, r.yaw) for r in rotations)
    return [unreal.EulerTransform(location=t.translation, scale=t.scale3d,
                                 rotation=unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw))
            for t, (roll, pitch, yaw) in zip(transforms, angles)]
