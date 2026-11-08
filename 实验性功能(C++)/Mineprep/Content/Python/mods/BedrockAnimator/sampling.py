"""Finite, linear Bedrock channels. No engine or scene dependencies."""
from bisect import bisect_right
import math


def channel(value, where):
    def xyz(v):
        if isinstance(v, (int, float)):
            v = [v] * 3
        if not isinstance(v, (list, tuple)) or len(v) != 3:
            raise ValueError(where + ': expected numeric XYZ; Molang/pre/post are unsupported')
        if any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in v):
            raise ValueError(where + ': expected finite numeric XYZ')
        return tuple(float(x) for x in v)
    if not isinstance(value, dict):
        return [(0.0, xyz(value))]
    result = []
    for t, v in value.items():
        try:
            time = float(t)
        except ValueError as exc:
            raise ValueError(where + ': unsupported time/interpolation: ' + str(t)) from exc
        if not math.isfinite(time) or time < 0:
            raise ValueError(where + ': time must be finite and nonnegative')
        result.append((time, xyz(v)))
    result.sort()
    if not result or any(a[0] == b[0] for a, b in zip(result, result[1:])):
        raise ValueError(where + ': empty channel or duplicate time')
    return result


def evaluate(keys, time, default):
    if not keys:
        return default
    i = bisect_right([k[0] for k in keys], time)
    if not i:
        return keys[0][1]
    if i == len(keys):
        return keys[-1][1]
    (a, av), (b, bv) = keys[i-1:i+1]
    u = (time-a)/(b-a)
    return tuple(x + (y-x)*u for x, y in zip(av, bv))


def compile_animation(name, animation, fps):
    """Return duration, source sample seconds and per-bone P/R/S arrays."""
    for feature in ('animation_controllers', 'timeline', 'particle_effects', 'sound_effects'):
        if feature in animation:
            raise ValueError(name + ': unsupported ' + feature)
    parsed = {}
    duration = float(animation.get('animation_length', 0))
    for bone, channels in animation.get('bones', {}).items():
        parsed[bone] = {}
        for prop, default in (('position', (0.,)*3), ('rotation', (0.,)*3), ('scale', (1.,)*3)):
            keys = channel(channels[prop], f'{name}/{bone}/{prop}') if prop in channels else []
            parsed[bone][prop] = (keys, default)
            if keys:
                duration = max(duration, keys[-1][0])
    if not math.isfinite(duration) or duration < 0 or not math.isfinite(fps) or fps <= 0:
        raise ValueError(name + ': invalid duration or fps')
    times = [min(i/fps, duration) for i in range(int(math.ceil(duration*fps - 1e-5))+1)]
    samples = {bone: {prop: [evaluate(keys, t, default) for t in times]
                      for prop, (keys, default) in channels.items()}
               for bone, channels in parsed.items()}
    return duration, times, samples
