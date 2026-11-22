"""Sample numeric Bedrock channels with linear / Catmull-Rom interpolation and pre/post limits."""
from bisect import bisect_right
import math


def _parse_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def channel(value, where):
    def xyz(v):
        if _parse_number(v) is not None or isinstance(v, (bool, str)):
            v = [v] * 3
        elif isinstance(v, (list, tuple)) and len(v) == 1:
            v = v * 3
        if not isinstance(v, (list, tuple)) or len(v) != 3:
            raise ValueError(where + ': expected numeric XYZ; Molang is unsupported')
        numbers = [_parse_number(x) for x in v]
        if any(x is None for x in numbers):
            raise ValueError(where + ': expected numeric XYZ; Molang is unsupported')
        if any(not math.isfinite(x) for x in numbers):
            raise ValueError(where + ': expected finite numeric XYZ')
        return tuple(numbers)
    if not isinstance(value, dict):
        point = xyz(value)
        return [(0.0, point, point, 'linear')]
    result = []
    for t, v in value.items():
        if isinstance(t, bool):
            raise ValueError(where + ': unsupported time/interpolation: ' + str(t))
        try:
            time = float(t)
        except (TypeError, ValueError) as exc:
            raise ValueError(where + ': unsupported time/interpolation: ' + str(t)) from exc
        if not math.isfinite(time) or time < 0:
            raise ValueError(where + ': time must be finite and nonnegative')
        if isinstance(v, dict):
            mode = v.get('lerp_mode', 'linear')
            if mode not in ('linear', 'catmullrom'):
                raise ValueError(where + ': unsupported lerp_mode: ' + str(mode))
            if 'pre' not in v and 'post' not in v:
                raise ValueError(where + ': key requires pre or post')
            pre = xyz(v.get('pre', v.get('post')))
            post = xyz(v.get('post', v.get('pre')))
        else:
            mode = 'linear'
            pre = post = xyz(v)
        result.append((time, pre, post, mode))
    result.sort(key=lambda key: key[0])
    if not result or any(a[0] == b[0] for a, b in zip(result, result[1:])):
        raise ValueError(where + ': empty channel or duplicate time')
    return result


def _catmullrom(u, p0, p1, p2, p3):
    if u <= 0.0:
        return p1
    if u >= 1.0:
        return p2
    u2 = u * u
    u3 = u2 * u
    return tuple(
        0.5 * (
            2.0 * b
            + (c - a) * u
            + (2.0 * a - 5.0 * b + 4.0 * c - d) * u2
            + (3.0 * b - a - 3.0 * c + d) * u3
        )
        for a, b, c, d in zip(p0, p1, p2, p3)
    )


def evaluate(keys, time, default, *, before=False):
    if not keys:
        return default
    i = bisect_right(keys, time, key=lambda key: key[0])
    if not i:
        return keys[0][1]
    if before and keys[i-1][0] == time:
        if i < 2 or keys[i-2][3] != 'catmullrom':
            return keys[i-1][1]
        return keys[i-1][2]
    if i == len(keys):
        return keys[-1][2]
    a, pre1, p1, mode = keys[i-1]
    b, p2, post2, _ = keys[i]
    u = (time-a)/(b-a)
    if mode == 'catmullrom':
        # Catmull-Rom always interpolates across the sequence of post values;
        # pre only serves an incoming linear segment or an explicit t > 0 initial jump.
        p0 = keys[i-2][2] if i >= 2 else p1
        p3 = keys[i+1][2] if i + 1 < len(keys) else post2
        return _catmullrom(u, p0, p1, post2, p3)
    return tuple(x + (y-x)*u for x, y in zip(p1, p2))


def regular_times(duration, fps):
    """Return uniform frame timestamps [0, ..., duration] for an effective output fps."""
    if not math.isfinite(duration) or duration < 0 or not math.isfinite(fps) or fps <= 0:
        raise ValueError('invalid duration or fps')
    return [min(i / fps, duration) for i in range(int(math.ceil(duration * fps - 1e-5)) + 1)]


def scalar_channel(value, where):
    """Parse a scalar float channel (constant or time -> number / {pre, post, lerp_mode})."""
    def num(v):
        parsed = _parse_number(v)
        if parsed is None or not math.isfinite(parsed):
            raise ValueError(where + ': expected finite numeric scalar')
        return (parsed,)

    if not isinstance(value, dict):
        pt = num(value)
        return [(0.0, pt, pt, 'linear')]
    result = []
    for t, v in value.items():
        if isinstance(t, bool):
            raise ValueError(where + ': unsupported time/interpolation: ' + str(t))
        try:
            time = float(t)
        except (TypeError, ValueError) as exc:
            raise ValueError(where + ': unsupported time/interpolation: ' + str(t)) from exc
        if not math.isfinite(time) or time < 0:
            raise ValueError(where + ': time must be finite and nonnegative')
        if isinstance(v, dict):
            mode = v.get('lerp_mode', 'linear')
            if mode not in ('linear', 'catmullrom'):
                raise ValueError(where + ': unsupported lerp_mode: ' + str(mode))
            if 'pre' not in v and 'post' not in v:
                raise ValueError(where + ': key requires pre or post')
            pre = num(v.get('pre', v.get('post')))
            post = num(v.get('post', v.get('pre')))
        else:
            mode = 'linear'
            pre = post = num(v)
        result.append((time, pre, post, mode))
    result.sort(key=lambda key: key[0])
    if not result or any(a[0] == b[0] for a, b in zip(result, result[1:])):
        raise ValueError(where + ': empty channel or duplicate time')
    return result


def compile_clip_channels(name, animation, fps):
    """Return (duration, times, bone_samples, curve_samples, left_indices)."""
    for feature in ('animation_controllers', 'timeline', 'particle_effects', 'sound_effects'):
        if feature in animation:
            raise ValueError(name + ': unsupported ' + feature)
    parsed = {}
    parsed_curves = {}
    jumps = set()
    duration = float(animation.get('animation_length', 0))
    for bone, channels in (animation.get('bones') or {}).items():
        parsed[bone] = {}
        for prop, default in (('position', (0.,)*3), ('rotation', (0.,)*3), ('scale', (1.,)*3)):
            keys = channel(channels[prop], f'{name}/{bone}/{prop}') if prop in channels else []
            parsed[bone][prop] = (keys, default)
            if keys:
                duration = max(duration, keys[-1][0])
                jumps.update(
                    t for idx, (t, pre, post, _) in enumerate(keys)
                    if t > 0 and pre != post and (idx == 0 or keys[idx-1][3] != 'catmullrom')
                )
    raw_curves = animation.get('curves') or {}
    if not isinstance(raw_curves, dict):
        raise ValueError(name + ': curves must be an object')
    for cname, spec in raw_curves.items():
        if not isinstance(cname, str) or not cname.strip():
            raise ValueError(name + ': curve name must be a non-empty string')
        keys = scalar_channel(spec, f'{name}/curves/{cname}')
        parsed_curves[cname.strip()] = keys
        if keys:
            duration = max(duration, keys[-1][0])
            jumps.update(
                t for idx, (t, pre, post, _) in enumerate(keys)
                if t > 0 and pre != post and (idx == 0 or keys[idx-1][3] != 'catmullrom')
            )
    if not math.isfinite(duration) or duration < 0 or not math.isfinite(fps) or fps <= 0:
        raise ValueError(name + ': invalid duration or fps')
    times = regular_times(duration, fps)
    timeline = sorted({(t, False) for t in times} | {(t, left) for t in jumps for left in (True, False)},
                      key=lambda sample: (sample[0], not sample[1]))
    samples = {bone: {prop: [evaluate(keys, t, default, before=left) for t, left in timeline]
                      for prop, (keys, default) in channels.items()}
               for bone, channels in parsed.items()}
    curve_samples = {cname: [evaluate(keys, t, (0.0,), before=left)[0] for t, left in timeline]
                     for cname, keys in parsed_curves.items()}
    return (
        duration,
        [t for t, _ in timeline],
        samples,
        curve_samples,
        {i for i, (_, left) in enumerate(timeline) if left},
    )


def compile_animation(name, animation, fps):
    """Return duration, sample seconds, per-bone P/R/S and pre-limit sample indices."""
    duration, times, samples, _curves, left_indices = compile_clip_channels(name, animation, fps)
    return duration, times, samples, left_indices
