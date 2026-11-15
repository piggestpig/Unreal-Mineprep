"""Scalar Bezier preparation for sparse import; no Blockbench parser or UI dependency.

Points are absolute (seconds, channel value), with positions already in cm and
rotations in degrees. Prepare every channel before committing an imported clip.
"""
import math

TOLERANCES = {'rotation': 0.01, 'position': 0.01, 'scale': 1e-4}


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _tick(seconds, tick_rate):
    return math.floor(seconds * tick_rate + 0.5)


def _point(points, u):
    v = 1-u
    return tuple(v**3*a + 3*v*v*u*b + 3*v*u*u*c + u**3*d
                 for a,b,c,d in zip(*points))


def _split_bezier(points):
    """Subdivide a 2D Bezier segment at u = 0.5 via de Casteljau."""
    p0, p1, p2, p3 = points
    m0 = ((p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5)
    m1 = ((p1[0] + p2[0]) * 0.5, (p1[1] + p2[1]) * 0.5)
    m2 = ((p2[0] + p3[0]) * 0.5, (p2[1] + p3[1]) * 0.5)
    l2 = ((m0[0] + m1[0]) * 0.5, (m0[1] + m1[1]) * 0.5)
    r1 = ((m1[0] + m2[0]) * 0.5, (m1[1] + m2[1]) * 0.5)
    mid = ((l2[0] + r1[0]) * 0.5, (l2[1] + r1[1]) * 0.5)
    return (p0, m0, l2, mid), (mid, r1, m2, p3)


def _sample(points, time):
    if time <= points[0][0]:
        u = 0.0
    elif time >= points[3][0]:
        u = 1.0
    else:
        lo, hi = 0.0, 1.0
        for _ in range(48):
            u = (lo+hi)/2
            if _point(points, u)[0] < time:
                lo = u
            else:
                hi = u
        u = (lo+hi)/2
    value = _point(points, u)[1]
    v = 1-u
    dx, dy = (3*v*v*(b-a)+6*v*u*(c-b)+3*u*u*(d-c)
              for a,b,c,d in zip(*points))
    # A coincident endpoint handle has the limiting direction of the next edge.
    if dx == 0 and dy == 0 and u in (0.0, 1.0):
        edges = zip(points, points[1:]) if u == 0 else zip(reversed(points[:-1]), reversed(points[1:]))
        for a,b in edges:
            dx, dy = b[0]-a[0], b[1]-a[1]
            if dx != 0 or dy != 0:
                break
    if dx <= 0 or not math.isfinite(dy/dx):
        raise ValueError('Bezier has a vertical tangent; cannot encode a finite Cubic slope')
    return value, dy/dx


def _hermite(t, a, b, ya, yb, ma, mb):
    u = (t-a)/(b-a)
    return ((2*u**3-3*u*u+1)*ya + (u**3-2*u*u+u)*(b-a)*ma
            + (-2*u**3+3*u*u)*yb + (u**3-u*u)*(b-a)*mb)


def _append_curve_part(merged, part, tick_rate):
    if merged is None:
        return {key: list(val) if isinstance(val, list) else val for key, val in part.items()}
    if (_tick(merged['times'][-1], tick_rate) != _tick(part['times'][0], tick_rate)
            or merged['values'][-1] != part['values'][0]):
        raise ValueError('Bezier segments must share their boundary time and value')
    merged['leave'][-1] = part['leave'][0]
    merged['leave_weight'][-1] = part['leave_weight'][0]
    merged['leave_weighted'][-1] = part['leave_weighted'][0]
    for field in ('times', 'values', 'arrive', 'leave',
                  'arrive_weight', 'leave_weight', 'arrive_weighted', 'leave_weighted'):
        merged[field].extend(part[field][1:])
    merged['weighted'] = merged['weighted'] or part['weighted']
    merged['sampled_error'] = max(merged['sampled_error'], part['sampled_error'])
    return merged


def _prepare_bezier(points, tick_rate, *, kind='rotation', tolerance=None, weighted=True, _depth=0):
    points = [tuple(p) for p in points]
    if len(points) != 4 or any(len(p) != 2 or any(not _is_number(v) for v in p) for p in points):
        raise ValueError('Bezier needs four finite (seconds, value) points')
    a, b = points[0][0], points[3][0]
    if b <= a or any(not a <= p[0] <= b for p in points[1:3]):
        raise ValueError('Bezier handle times must lie within a positive-duration segment')
    tolerance = TOLERANCES[kind] if tolerance is None else tolerance
    if not _is_number(tick_rate) or tick_rate <= 0 or not _is_number(tolerance) or tolerance <= 0:
        raise ValueError('tick_rate and tolerance must be positive and finite')
    first, last = _tick(a, tick_rate), _tick(b, tick_rate)
    if last <= first:
        raise ValueError('Bezier segment is shorter than the tick resolution')
    ma, mb = _sample(points, a)[1], _sample(points, b)[1]
    if weighted:
        # UE's GAvoidOverlappingWeightedTangents shrinks overlapping handles; split at u=0.5 first.
        if points[1][0] > points[2][0]:
            left_pts, right_pts = _split_bezier(points)
            _sample(left_pts, left_pts[3][0])
            mid_tick = _tick(left_pts[3][0], tick_rate)
            if mid_tick <= first or last <= mid_tick or _depth >= 4:
                if last - first >= 2:
                    return _prepare_bezier(points, tick_rate, kind=kind, tolerance=tolerance, weighted=False)
                raise ValueError('Bezier handles overlap on a segment shorter than two ticks')
            left_part = _prepare_bezier(left_pts, tick_rate, kind=kind, tolerance=tolerance,
                                        weighted=True, _depth=_depth + 1)
            right_part = _prepare_bezier(right_pts, tick_rate, kind=kind, tolerance=tolerance,
                                         weighted=True, _depth=_depth + 1)
            joined = _append_curve_part(_append_curve_part(None, left_part, tick_rate), right_part, tick_rate)
            joined['extra_keys'] = len(joined['times']) - 2
            return joined
        left = math.hypot(points[3][0] - points[2][0], points[3][1] - points[2][1])
        right = math.hypot(points[1][0] - points[0][0], points[1][1] - points[0][1])
        return dict(
            times=[a, b], values=[points[0][1], points[3][1]],
            arrive=[ma, mb], leave=[ma, mb],
            arrive_weight=[0.0, left], leave_weight=[right, 0.0],
            arrive_weighted=[False, True], leave_weighted=[True, False],
            weighted=True, extra_keys=0, sampled_error=0.0,
        )
    rows = []
    error = 0.0

    def split(ta, tb, depth):
        nonlocal error
        x, y = ta / tick_rate, tb / tick_rate
        ya, sa = _sample(points, x)
        yb, sb = _sample(points, y)
        samples = [x + (y - x) * i / 16 for i in range(1, 16)]
        deviation = max(abs(_sample(points, t)[0] - _hermite(t, x, y, ya, yb, sa, sb)) for t in samples)
        if deviation <= tolerance * 0.5:
            rows.append((x, ya, sa))
            error = max(error, deviation)
            if len(rows) >= 4096:
                raise ValueError('Bezier fitting exceeded 4096 keys')
            return
        mid = (ta + tb) // 2
        if depth >= 20 or mid <= ta or mid >= tb:
            raise ValueError('Bezier fitting cannot meet tolerance at this tick resolution')
        split(ta, mid, depth + 1)
        split(mid, tb, depth + 1)

    split(first, last, 0)
    y, slope = _sample(points, last / tick_rate)
    rows.append((last / tick_rate, y, slope))
    count = len(rows)
    return dict(
        times=[r[0] for r in rows], values=[r[1] for r in rows],
        arrive=[r[2] for r in rows], leave=[r[2] for r in rows],
        arrive_weight=[0.0] * count, leave_weight=[0.0] * count,
        arrive_weighted=[False] * count, leave_weighted=[False] * count,
        weighted=False, extra_keys=count - 2, sampled_error=error,
    )


def prepare_bezier(points, tick_rate, *, kind='rotation', tolerance=None, weighted=True):
    """Preflight one segment; return scalar keys and a precise/fitted report.

    Splits overlapping weighted handles at u = 0.5 to avoid UE handle clamping,
    falling back to Hermite fitting on tick-limit edge cases. Vertical tangents
    still fail explicitly. Fitted error checks 15 interior points per interval.
    """
    return _prepare_bezier(points, tick_rate, kind=kind, tolerance=tolerance, weighted=weighted)


def _upgrade_linear_into_cubic(times, values, arrive, leave, arrive_w, leave_w,
                               arrive_on, leave_on, interp_modes):
    """Turn linear segments entering cubic keys into unweighted cubic linear tangents."""
    for i in range(len(times) - 2, -1, -1):
        if interp_modes[i] == 'linear' and interp_modes[i + 1] == 'cubic':
            slope = (values[i + 1] - values[i]) / (times[i + 1] - times[i])
            interp_modes[i] = 'cubic'
            leave[i] = slope
            leave_w[i] = 0.0
            leave_on[i] = False
            arrive[i + 1] = slope
            arrive_w[i + 1] = 0.0
            arrive_on[i + 1] = False


def prepare_mixed_curve(segments, tick_rate, *, kind='rotation', tolerance=None,
                        weighted=True, initial=None, initial_pre=None,
                        end_mode=None, end_post=None):
    """Prepare a 1D curve with per-segment step/linear/bezier modes and jump splits."""
    tolerance = TOLERANCES[kind] if tolerance is None else tolerance
    if not _is_number(tick_rate) or tick_rate <= 0 or not _is_number(tolerance) or tolerance <= 0:
        raise ValueError('tick_rate and tolerance must be positive and finite')
    if end_mode is not None and end_mode not in ('constant', 'linear', 'cubic'):
        raise ValueError(f'Unsupported end_mode: {end_mode!r}')
    if initial_pre is not None and not _is_number(initial_pre):
        raise ValueError('initial_pre must be a finite number')
    if end_post is not None and not _is_number(end_post):
        raise ValueError('end_post must be a finite number')

    if not segments:
        if not initial or len(initial) not in (2, 3):
            raise ValueError('Single-key curve requires (time, value[, mode])')
        time, value = float(initial[0]), float(initial[1])
        mode = initial[2] if len(initial) == 3 else 'linear'
        if not _is_number(time) or not _is_number(value) or mode not in ('constant', 'linear', 'cubic'):
            raise ValueError('Single-key curve requires finite time, value and valid mode')
        if end_post is not None:
            value = float(end_post)
        final_mode = end_mode if end_mode is not None else mode
        if initial_pre is not None and float(initial_pre) != value:
            v_pre = float(initial_pre)
            tick0 = _tick(time, tick_rate)
            return dict(
                times=[tick0 / tick_rate, (tick0 + 1) / tick_rate],
                values=[v_pre, value],
                arrive=[0.0, 0.0], leave=[0.0, 0.0],
                arrive_weight=[0.0, 0.0], leave_weight=[0.0, 0.0],
                arrive_weighted=[False, False], leave_weighted=[False, False],
                interp_modes=['constant', final_mode],
                weighted=False, extra_keys=0, sampled_error=0.0,
            )
        return dict(
            times=[time], values=[value], arrive=[0.0], leave=[0.0],
            arrive_weight=[0.0], leave_weight=[0.0],
            arrive_weighted=[False], leave_weighted=[False],
            interp_modes=[final_mode], weighted=False, extra_keys=0, sampled_error=0.0,
        )

    times, values = [], []
    arrive, leave = [], []
    arrive_w, leave_w = [], []
    arrive_on, leave_on = [], []
    interp_modes = []
    any_weighted = False
    max_error = 0.0
    source_keys = 1 + len(segments)
    prev_tick = None
    prev_val = None

    if initial_pre is not None:
        v_pre = float(initial_pre)
        pts0 = segments[0]['points']
        t_first, v_first = float(pts0[0][0]), float(pts0[0][1])
        if not _is_number(t_first) or not _is_number(v_first):
            raise ValueError('Segment points must contain finite numbers')
        if v_pre != v_first:
            tick_first = _tick(t_first, tick_rate)
            times.append(tick_first / tick_rate)
            values.append(v_pre)
            arrive.append(0.0)
            leave.append(0.0)
            arrive_w.append(0.0)
            leave_w.append(0.0)
            arrive_on.append(False)
            leave_on.append(False)
            interp_modes.append('constant')
            prev_tick = tick_first
            prev_val = v_pre

    for seg_index, seg in enumerate(segments):
        mode = seg['mode']
        if mode not in ('constant', 'linear', 'bezier'):
            raise ValueError(f'Unsupported mixed curve segment mode: {mode!r}')
        pts = [(float(p[0]), float(p[1])) for p in seg['points']]
        if any(not _is_number(v) for p in pts for v in p):
            raise ValueError('Segment points must contain finite numbers')
        t0, v0 = pts[0]
        t1, v1 = pts[-1]
        tick0, tick1 = _tick(t0, tick_rate), _tick(t1, tick_rate)
        if t1 <= t0 or tick1 <= tick0:
            raise ValueError('Segment duration must exceed the tick resolution')

        has_prev = prev_tick is not None
        discontinuous = has_prev and (tick0 != prev_tick or v0 != prev_val)
        if has_prev and tick0 == prev_tick and v0 != prev_val:
            interp_modes[-1] = 'constant'
            t0 = (tick0 + 1) / tick_rate
            tick0 = tick0 + 1
            if tick1 <= tick0 or t1 <= t0:
                raise ValueError('Discontinuity keyframe interval is shorter than two ticks')
            if mode == 'bezier' and len(pts) == 4:
                pts = [
                    (t0, v0),
                    (min(max(pts[1][0], t0), t1), pts[1][1]),
                    (min(max(pts[2][0], t0), t1), pts[2][1]),
                    (t1, v1),
                ]
            else:
                pts = [(t0, v0), (t1, v1)]
            source_keys += 1
        elif has_prev and tick0 < prev_tick:
            raise ValueError('Mixed curve segments must have non-decreasing tick times')

        if mode == 'bezier':
            use_weight = bool(weighted and seg.get('allow_weighted', True))
            part = _prepare_bezier(pts, tick_rate, kind=kind, tolerance=tolerance, weighted=use_weight)
            p_times = part['times']
            p_values = part['values']
            p_arrive = part['arrive']
            p_leave = part['leave']
            p_aw = part['arrive_weight']
            p_lw = part['leave_weight']
            p_aon = part['arrive_weighted']
            p_lon = part['leave_weighted']
            p_modes = ['cubic'] * len(p_times)
            any_weighted = any_weighted or part['weighted']
            max_error = max(max_error, part['sampled_error'])
        else:
            p_times = [t0, t1]
            p_values = [v0, v1]
            p_arrive = [0.0, 0.0]
            p_leave = [0.0, 0.0]
            p_aw = [0.0, 0.0]
            p_lw = [0.0, 0.0]
            p_aon = [False, False]
            p_lon = [False, False]
            p_modes = [mode, mode]

        if not times or discontinuous:
            times.extend(p_times)
            values.extend(p_values)
            arrive.extend(p_arrive)
            leave.extend(p_leave)
            arrive_w.extend(p_aw)
            leave_w.extend(p_lw)
            arrive_on.extend(p_aon)
            leave_on.extend(p_lon)
            interp_modes.extend(p_modes)
        else:
            leave[-1] = p_leave[0]
            leave_w[-1] = p_lw[0]
            leave_on[-1] = p_lon[0]
            interp_modes[-1] = p_modes[0]
            times.extend(p_times[1:])
            values.extend(p_values[1:])
            arrive.extend(p_arrive[1:])
            leave.extend(p_leave[1:])
            arrive_w.extend(p_aw[1:])
            leave_w.extend(p_lw[1:])
            arrive_on.extend(p_aon[1:])
            leave_on.extend(p_lon[1:])
            interp_modes.extend(p_modes[1:])

        prev_tick = tick1
        prev_val = v1

    if end_post is not None:
        v_end_post = float(end_post)
        if v_end_post != values[-1]:
            interp_modes[-1] = 'constant'
            leave[-1] = 0.0
            leave_w[-1] = 0.0
            leave_on[-1] = False
            times.append((prev_tick + 1) / tick_rate)
            values.append(v_end_post)
            arrive.append(0.0)
            leave.append(0.0)
            arrive_w.append(0.0)
            leave_w.append(0.0)
            arrive_on.append(False)
            leave_on.append(False)
            interp_modes.append(end_mode if end_mode is not None else 'linear')
            source_keys += 1
        elif end_mode is not None:
            interp_modes[-1] = end_mode
    elif end_mode is not None:
        interp_modes[-1] = end_mode
    if len(times) > 4096:
        raise ValueError('Prepared mixed curve exceeded 4096 keys')
    _upgrade_linear_into_cubic(times, values, arrive, leave, arrive_w, leave_w,
                               arrive_on, leave_on, interp_modes)
    return dict(
        times=times, values=values, arrive=arrive, leave=leave,
        arrive_weight=arrive_w, leave_weight=leave_w,
        arrive_weighted=arrive_on, leave_weighted=leave_on,
        interp_modes=interp_modes, weighted=any_weighted,
        extra_keys=len(times) - source_keys, sampled_error=max_error,
    )


def fit_sampled_vector_curve(segments, sample_fn, error_fn, tick_rate, *,
                             tolerance=None, max_keys=4096,
                             initial_pre=None, end_post=None, end_mode=None):
    """Fit piecewise vector Hermite curves (e.g. coupled 3D rotation) within tolerance.

    Each segment in ``segments`` is ``(t_start, t_end, mode, jump_before)`` where
    ``mode`` is ``'constant'`` or ``'cubic'``. Returns a tuple of prepared scalar
    curve dicts ``(prepared_0, prepared_1, ...)``.
    """
    tolerance = TOLERANCES['rotation'] if tolerance is None else tolerance
    if not _is_number(tick_rate) or tick_rate <= 0 or not _is_number(tolerance) or tolerance <= 0:
        raise ValueError('tick_rate and tolerance must be positive and finite')
    if end_mode is not None and end_mode not in ('constant', 'linear', 'cubic'):
        raise ValueError(f'Unsupported end_mode: {end_mode!r}')
    if initial_pre is not None:
        init_pre_vals = tuple(float(v) for v in initial_pre)
        if not init_pre_vals or any(not _is_number(v) for v in init_pre_vals):
            raise ValueError('initial_pre must contain finite numbers')
    else:
        init_pre_vals = None
    if end_post is not None:
        end_post_vals = tuple(float(v) for v in end_post)
        if not end_post_vals or any(not _is_number(v) for v in end_post_vals):
            raise ValueError('end_post must contain finite numbers')
    else:
        end_post_vals = None
    if not segments:
        raise ValueError('Sampled vector curve needs at least one segment')

    channels = None
    max_error = 0.0
    prev_state = None
    prev_tick = None
    jump_count = 0

    def append_knot(ch_idx, t_sec, val, in_slope, out_slope, mode):
        ch = channels[ch_idx]
        ch['times'].append(float(t_sec))
        ch['values'].append(float(val))
        ch['arrive'].append(float(in_slope))
        ch['leave'].append(float(out_slope))
        ch['interp_modes'].append(mode)

    def subdivide(seg_index, ta, tb, va, ma, vb, mb, dim, depth):
        nonlocal max_error
        xa, xb = ta / tick_rate, tb / tick_rate
        worst = 0.0
        for step in range(1, 8):
            t = xa + (xb - xa) * step / 8
            herm = tuple(_hermite(t, xa, xb, va[i], vb[i], ma[i], mb[i]) for i in range(dim))
            ref_vals, _ = sample_fn(seg_index, t, va, None)
            comp_err = max(abs(herm[i] - ref_vals[i]) for i in range(dim))
            worst = max(worst, comp_err, error_fn(seg_index, t, herm))
        if worst <= tolerance * 0.5:
            max_error = max(max_error, worst)
            if len(channels[0]['times']) >= max_keys:
                raise ValueError(f'Sampled rotation fitting exceeded {max_keys} keys')
            for idx in range(dim):
                append_knot(idx, xb, vb[idx], mb[idx], mb[idx], 'cubic')
            return
        mid = (ta + tb) // 2
        if depth >= 20 or mid <= ta or mid >= tb:
            raise ValueError('Sampled rotation fitting cannot meet tolerance at this tick resolution')
        xm = mid / tick_rate
        vm, mm = sample_fn(seg_index, xm, va, None)
        subdivide(seg_index, ta, mid, va, ma, vm, mm, dim, depth + 1)
        subdivide(seg_index, mid, tb, vm, mm, vb, mb, dim, depth + 1)

    for seg_index, seg in enumerate(segments):
        t0, t1, mode, jump_before = float(seg[0]), float(seg[1]), seg[2], bool(seg[3])
        if mode not in ('constant', 'cubic'):
            raise ValueError(f'Unsupported sampled vector mode: {mode!r}')
        tick0, tick1 = _tick(t0, tick_rate), _tick(t1, tick_rate)
        if tick1 <= tick0:
            raise ValueError('Segment shorter than tick resolution')

        if seg_index > 0 and jump_before:
            for ch in channels:
                ch['interp_modes'][-1] = 'constant'
                ch['leave'][-1] = 0.0
            tick0 = tick0 + 1
            if tick1 <= tick0:
                raise ValueError('Discontinuity segment shorter than two ticks')
            t0 = tick0 / tick_rate
            prev_state = None
            jump_count += 1

        start_vals, start_out = sample_fn(seg_index, t0, prev_state, 'start')
        dim = len(start_vals)
        if channels is None:
            channels = [dict(times=[], values=[], arrive=[], leave=[], interp_modes=[])
                        for _ in range(dim)]
        if seg_index == 0 and init_pre_vals is not None:
            if len(init_pre_vals) != dim:
                raise ValueError('initial_pre dimension mismatch')
            if any(a != b for a, b in zip(init_pre_vals, start_vals)):
                for idx in range(dim):
                    append_knot(idx, tick0 / tick_rate, init_pre_vals[idx], 0.0, 0.0, 'constant')
                tick0 = tick0 + 1
                if tick1 <= tick0:
                    raise ValueError('Discontinuity segment shorter than two ticks')
                t0 = tick0 / tick_rate
                jump_count += 1
                jump_before = True
                start_vals, start_out = sample_fn(seg_index, t0, None, 'start')

        if mode == 'constant':
            end_vals, _ = sample_fn(seg_index, t1, start_vals, 'end')
            if seg_index == 0 or jump_before:
                for idx in range(dim):
                    append_knot(idx, t0, start_vals[idx], 0.0, 0.0, 'constant')
            else:
                for idx in range(dim):
                    channels[idx]['interp_modes'][-1] = 'constant'
                    channels[idx]['leave'][-1] = 0.0
            for idx in range(dim):
                append_knot(idx, t1, end_vals[idx], 0.0, 0.0, 'constant')
            prev_state = end_vals
            prev_tick = tick1
            continue

        end_vals, end_in = sample_fn(seg_index, t1, start_vals, 'end')
        if seg_index == 0 or jump_before:
            for idx in range(dim):
                append_knot(idx, t0, start_vals[idx], start_out[idx], start_out[idx], 'cubic')
        else:
            for idx in range(dim):
                channels[idx]['leave'][-1] = start_out[idx]
                channels[idx]['interp_modes'][-1] = 'cubic'

        subdivide(seg_index, tick0, tick1, start_vals, start_out, end_vals, end_in, dim, 0)
        prev_state = end_vals
        prev_tick = tick1

    if end_post_vals is not None:
        if len(end_post_vals) != len(channels):
            raise ValueError('end_post dimension mismatch')
        if any(a != b for a, b in zip(end_post_vals, (ch['values'][-1] for ch in channels))):
            post_t = (prev_tick + 1) / tick_rate
            final_mode = end_mode if end_mode is not None else 'linear'
            for idx, ch in enumerate(channels):
                ch['interp_modes'][-1] = 'constant'
                ch['leave'][-1] = 0.0
                append_knot(idx, post_t, end_post_vals[idx], 0.0, 0.0, final_mode)
            jump_count += 1
        elif end_mode is not None:
            for ch in channels:
                ch['interp_modes'][-1] = end_mode
    elif end_mode is not None:
        for ch in channels:
            ch['interp_modes'][-1] = end_mode

    result = []
    source_keys = 1 + len(segments) + jump_count
    for ch in channels:
        count = len(ch['times'])
        result.append(dict(
            times=ch['times'], values=ch['values'],
            arrive=ch['arrive'], leave=ch['leave'],
            arrive_weight=[0.0] * count, leave_weight=[0.0] * count,
            arrive_weighted=[False] * count, leave_weighted=[False] * count,
            interp_modes=ch['interp_modes'], weighted=False,
            extra_keys=max(0, count - source_keys),
            sampled_error=max_error,
        ))
    return tuple(result)


def prepare_curve(segments, tick_rate, *, kind='rotation', tolerance=None, weighted=True):
    """Prepare a contiguous scalar curve, keeping separate incoming/outgoing handles."""
    merged = None
    source_keys = 0
    for points in segments:
        part = _prepare_bezier(points, tick_rate, kind=kind, tolerance=tolerance, weighted=weighted)
        merged = _append_curve_part(merged, part, tick_rate)
        source_keys += 2 if source_keys == 0 else 1
    if merged is None:
        raise ValueError('Bezier curve needs at least one segment')
    merged['extra_keys'] = len(merged['times']) - source_keys
    if len(merged['times']) > 4096:
        raise ValueError('Bezier curve exceeded 4096 keys')
    return merged


def write_curve(rig, selector, segments, *, kind='rotation', tolerance=None):
    """Prepare the entire scalar curve before writing; auto-fit without the C++ binding."""
    from mc_handle import _tick_resolution_sync
    weighted = _tick_resolution_sync() is not None
    rate = rig.sequence.get_tick_resolution()
    prepared = prepare_curve(segments, rate.numerator / rate.denominator,
                             kind=kind, tolerance=tolerance, weighted=weighted)
    return write_prepared(rig, selector, prepared)


def _prepare_write_payload(prepared):
    times = [float(t) for t in prepared['times']]
    values = [float(v) for v in prepared['values']]
    arrive = [float(a) for a in prepared['arrive']]
    leave = [float(l) for l in prepared['leave']]
    count = len(times)
    if count < 1 or any(len(seq) != count for seq in (values, arrive, leave)):
        raise ValueError('Prepared curve needs matching arrays with at least one key')
    if any(not _is_number(v) for seq in (times, values, arrive, leave) for v in seq):
        raise ValueError('Prepared curve times, values and tangents must be finite numbers')
    interp_modes = list(prepared['interp_modes']) if 'interp_modes' in prepared else ['cubic'] * count
    if len(interp_modes) != count or any(mode not in ('constant', 'linear', 'cubic') for mode in interp_modes):
        raise ValueError('Prepared curve interp_modes must match keys and be constant, linear, or cubic')
    weighted = bool(prepared.get('weighted'))
    arrive_w = [float(w) for w in prepared['arrive_weight']] if weighted or 'arrive_weight' in prepared else [0.0] * count
    leave_w = [float(w) for w in prepared['leave_weight']] if weighted or 'leave_weight' in prepared else [0.0] * count
    arrive_on = (list(prepared['arrive_weighted']) if 'arrive_weighted' in prepared
                 else ([False] + [True] * (count - 1) if weighted else [False] * count))
    leave_on = (list(prepared['leave_weighted']) if 'leave_weighted' in prepared
                else ([True] * (count - 1) + [False] if weighted else [False] * count))
    if any(len(seq) != count for seq in (arrive_w, leave_w, arrive_on, leave_on)):
        raise ValueError('Prepared curve weight arrays must match key count')
    if any(not _is_number(w) or w < 0 for seq in (arrive_w, leave_w) for w in seq):
        raise ValueError('Prepared curve weights must be finite and non-negative')
    return (times, values, arrive, leave, arrive_w, leave_w,
            [bool(x) for x in arrive_on], [bool(x) for x in leave_on], interp_modes)


def write_prepared(rig, selector, prepared, *, replace_span=None):
    """Commit prepared scalar keys in one transaction.

    Existing boundary keys preserve their outer slope, weight, weight flag, and
    end interpolation mode; new boundary keys leave the outer side unweighted so
    adjacent curves are never zero-clamped or rebuilt retroactively.
    """
    import unreal
    import mc_sequencer as mcseq
    from mc_handle import _tick_resolution_sync
    from mc_rig import _key_tick_time

    (times, values, arrive, leave, arrive_w, leave_w,
     arrive_on, leave_on, interp_modes) = _prepare_write_payload(prepared)
    mcseq.require_focused_sequence(rig.sequence)
    ticks = [rig._time_tick(time) for time in times]
    if any(second <= first for first, second in zip(ticks, ticks[1:])):
        raise ValueError('Prepared curve keys must map to strictly increasing ticks')
    if replace_span is None:
        replace_slice = slice(ticks[0], ticks[-1] + 1)
    elif isinstance(replace_span, slice):
        if (replace_span.step not in (None, 1)
                or any(isinstance(t, bool) or not isinstance(t, int)
                       for t in (replace_span.start, replace_span.stop))
                or replace_span.stop <= replace_span.start
                or replace_span.start > ticks[0] or ticks[-1] >= replace_span.stop):
            raise ValueError('Prepared curve replace_span slice must cover written ticks')
        replace_slice = replace_span
    elif isinstance(replace_span, (tuple, list)) and len(replace_span) == 2:
        start_t, end_t = replace_span
        if (any(isinstance(t, bool) or not isinstance(t, int) for t in (start_t, end_t))
                or end_t <= start_t or start_t > ticks[0] or ticks[-1] >= end_t):
            raise ValueError('Prepared curve replace_span tuple must cover written ticks')
        replace_slice = slice(start_t, end_t)
    else:
        raise ValueError('Prepared curve replace_span must be None, tick slice, or (start_tick, end_tick)')

    if len(rig.track.get_sections()) != 1:
        raise ValueError('Rig 写键需要单个 section')
    chosen = rig.channels(selector)
    if (len(chosen) != 1 or not isinstance(
            chosen.target[0], (unreal.MovieSceneScriptingFloatChannel, unreal.MovieSceneScriptingDoubleChannel))):
        raise ValueError('写曲线需要单个 Float 或 Double 通道选择器')

    tick_unit = unreal.MovieSceneTimeUnit.TICK_RESOLUTION
    rate = rig.sequence.get_tick_resolution()
    tick_rate = rate.numerator / rate.denominator
    existing = {_key_tick_time(key, tick_unit): key for key in chosen.target[0].get_keys()}
    has_removed_before = any(replace_slice.start <= k < ticks[0] for k in existing)
    has_removed_after = any(ticks[-1] < k < replace_slice.stop for k in existing)
    old_start = None if has_removed_before else existing.get(ticks[0])
    old_end = None if has_removed_after else existing.get(ticks[-1])
    weight_enum = unreal.RichCurveTangentWeightMode
    if old_start is not None:
        arrive[0] = float(old_start.get_arrive_tangent()) * tick_rate
        arrive_w[0] = max(0.0, float(old_start.get_arrive_tangent_weight()))
        arrive_on[0] = old_start.get_tangent_weight_mode() in (
            weight_enum.RCTWM_WEIGHTED_ARRIVE, weight_enum.RCTWM_WEIGHTED_BOTH)
    end_interp = None
    if old_end is not None:
        leave[-1] = float(old_end.get_leave_tangent()) * tick_rate
        leave_w[-1] = max(0.0, float(old_end.get_leave_tangent_weight()))
        leave_on[-1] = old_end.get_tangent_weight_mode() in (
            weight_enum.RCTWM_WEIGHTED_LEAVE, weight_enum.RCTWM_WEIGHTED_BOTH)
        end_interp = old_end.get_interpolation_mode()
        if len(times) >= 2 and end_interp == unreal.RichCurveInterpMode.RCIM_CUBIC and interp_modes[-2] == 'linear':
            interp_modes[-1] = 'cubic'
            _upgrade_linear_into_cubic(times, values, arrive, leave, arrive_w, leave_w,
                                       arrive_on, leave_on, interp_modes)

    weight_modes = [('none', 'arrive', 'leave', 'both')[int(in_on) + 2 * int(out_on)]
                    for in_on, out_on in zip(arrive_on, leave_on)]
    has_weights = any(mode != 'none' for mode in weight_modes)
    if has_weights and _tick_resolution_sync() is None:
        raise RuntimeError('Exact weighted curve requires the compiled C++ synchronization binding')

    interp_enum = unreal.RichCurveInterpMode
    ue_modes = {
        'constant': interp_enum.RCIM_CONSTANT,
        'linear': interp_enum.RCIM_LINEAR,
        'cubic': interp_enum.RCIM_CUBIC,
    }
    needs_tangents = (
        any(mode == 'cubic' for mode in interp_modes)
        or has_weights
        or old_start is not None
        or old_end is not None
    )

    with mcseq._defer_refresh(), unreal.ScopedEditorTransaction('Write animation curve'):
        try:
            written = rig._key_batches(
                {selector: (ticks, values)}, 'linear',
                time_unit=tick_unit, replace_span=replace_slice,
            )
            if needs_tangents:
                kwargs = dict(arrive=arrive, leave=leave, weight_mode=weight_modes)
                if has_weights:
                    kwargs.update(arrive_weight=arrive_w, leave_weight=leave_w)
                written.tangents(**kwargs)
            for idx, (key, mode_name) in enumerate(zip(written.target, interp_modes)):
                target_mode = end_interp if (idx == len(written.target) - 1 and end_interp is not None) else ue_modes[mode_name]
                if key.get_interpolation_mode() != target_mode:
                    key.set_interpolation_mode(target_mode)
        finally:
            mcseq._refresh_sequencer()
    return dict(
        keys=written,
        weighted=bool(prepared.get('weighted')),
        extra_keys=prepared.get('extra_keys', len(times) - 2),
        sampled_error=prepared.get('sampled_error', 0.0),
    )
