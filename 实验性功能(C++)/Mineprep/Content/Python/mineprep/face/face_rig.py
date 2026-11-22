"""Builder and Sequencer attachment helper for the shared Mineprep facial Control Rig (`CR_MC_Face`)."""
from __future__ import annotations

try:
    import unreal
except ModuleNotFoundError:
    unreal = None

from .capabilities import describe_actor_capabilities
from .materials import _warn_face
from .protocol import (
    DEFAULT_EYE_BOUNDS,
    FACE_CURVES,
    FACE_RIG_CR_PATH,
    FACE_RIG_VERSION,
    FACE_RIG_VERSION_TAG,
)

_FACE_CURVE_SET = frozenset(FACE_CURVES)

_CURVE_CLAMP: dict[str, tuple[float, float]] = {
    'face_blink_l': (0.0, 1.0),
    'face_blink_r': (0.0, 1.0),
    'face_eye_wide': (-1.5, 1.5),
    'face_pupil_scale': (-1.5, 1.5),
    'face_look_x_l': (-2.0, 2.0),
    'face_look_x_r': (-2.0, 2.0),
    'face_look_y': (-2.0, 2.0),
    'face_brow_y_l': (-1.0, 1.0),
    'face_brow_y_r': (-1.0, 1.0),
    'face_brow_rot_l': (-1.0, 1.0),
    'face_brow_rot_r': (-1.0, 1.0),
    'face_mouth_open': (-1.0, 1.0),
    'face_mouth_wide': (-1.0, 1.0),
    'face_mouth_smile': (-1.0, 1.0),
    'face_mouth_x': (-1.0, 1.0),
}

# Static Imported anchor chain so UE's SetBoneInitialTransformsFromRefSkeleton & PoseAdapter
# automatically snap `face_panel_root` onto the bound mesh's live head across all MC skeletons:
# - split-head (`head`)
# - unified biped & standard quadrupeds (`root -> pelvis -> body -> head`)
# - horse / horse_baby (`root -> pelvis -> body -> head_parts -> head`)
# - wolf (`root -> pelvis -> body -> head -> real_head`)
# - bee / ghast (`root -> pelvis -> body`)
# - custom rigs with an optional `neck` bone (`... -> body -> neck -> ... -> head`)
# Any bone absent from a target mesh stays at Identity local transform, forwarding its parent's live pose.
_HEAD_ANCHOR_CHAIN = ('root', 'pelvis', 'body', 'neck', 'head_parts', 'head', 'real_head')
_DEFAULT_OVERFLOW_X = 0.5
_DEFAULT_OVERFLOW_Y = 1.0


def _clamp(val: float, lo: float, hi: float) -> float:
    return lo if val < lo else (hi if val > hi else val)


def _pupil_base_bounds(pupil_rest_mode: int) -> tuple[tuple[float, float], tuple[float, float]]:
    if pupil_rest_mode < 0:
        return (0.0, 1.0), (-1.0, 0.0)
    if pupil_rest_mode > 0:
        return (-1.0, 0.0), (0.0, 1.0)
    return (0.0, 0.0), (0.0, 0.0)


def _forward_clamp_look_x(
    gx: float,
    cx: float,
    pupil_rest_mode: int,
    ov_x: float,
    pupil_scale: float = 0.0,
    eye_bounds: dict[str, float] | None = None,
) -> tuple[float, float]:
    """Exact Python mirror of `CR_MC_Face` v5 two-step horizontal gaze clamping (socket+overflow, then head+scale)."""
    eb = eye_bounds or DEFAULT_EYE_BOUNDS
    ov = _clamp(float(ov_x), 0.0, 1.0)
    (base_lo_l, base_hi_l), (base_lo_r, base_hi_r) = _pupil_base_bounds(int(pupil_rest_mode))
    step1_l = _clamp(float(gx) + float(cx), base_lo_l - ov, base_hi_l + ov)
    step1_r = _clamp(float(gx) - float(cx), base_lo_r - ov, base_hi_r + ov)

    m_in = max(0.0, float(eb.get('margin_in', DEFAULT_EYE_BOUNDS['margin_in'])))
    m_out = max(0.0, float(eb.get('margin_out', DEFAULT_EYE_BOUNDS['margin_out'])))
    shift = max(0.0, float(eb.get('scale_shift', DEFAULT_EYE_BOUNDS['scale_shift'])))
    grow = max(0.0, float(pupil_scale)) * shift

    raw_lo_l = -m_in + grow
    raw_hi_l = m_out - grow
    mid_l = 0.5 * (raw_lo_l + raw_hi_l)
    safe_lo_l = min(raw_lo_l, mid_l)
    safe_hi_l = max(raw_hi_l, mid_l)

    raw_lo_r = -m_out + grow
    raw_hi_r = m_in - grow
    mid_r = -mid_l
    safe_lo_r = min(raw_lo_r, mid_r)
    safe_hi_r = max(raw_hi_r, mid_r)

    return (
        _clamp(_clamp(step1_l, safe_lo_l, safe_hi_l), -2.0, 2.0),
        _clamp(_clamp(step1_r, safe_lo_r, safe_hi_r), -2.0, 2.0),
    )


def _sample_recorded_float_curve(
    raw_times,
    raw_vals,
    target_times: list[float],
    dt: float,
) -> list[float]:
    """Sample an `AnimationRecorder`-exported float curve at `target_times` (seconds).

    `AnimationRecorder` only emits keys on frames where `bIsCurveValid` was true, saving each key's
    real timestamp. Target times outside `[raw_times[0], raw_times[-1]]` (beyond `0.5 * dt`) or inside
    unrecorded inactive gaps wider than `1.5 * dt` therefore evaluate to `0.0`.
    """
    n = min(len(raw_times), len(raw_vals))
    if n == 0:
        return [0.0] * len(target_times)
    pairs = sorted((float(raw_times[i]), float(raw_vals[i])) for i in range(n))
    ts = [p[0] for p in pairs]
    vs = [p[1] for p in pairs]
    snap_tol = max(1e-5, 0.5 * float(dt))
    gap_tol = max(2e-5, 1.5 * float(dt))

    out: list[float] = []
    for t in target_times:
        tf = float(t)
        if tf < ts[0] - snap_tol or tf > ts[-1] + snap_tol:
            out.append(0.0)
            continue
        if tf <= ts[0]:
            out.append(vs[0])
            continue
        if tf >= ts[-1]:
            out.append(vs[-1])
            continue
        lo, hi = 0, n - 1
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if ts[mid] <= tf:
                lo = mid
            else:
                hi = mid
        span = ts[hi] - ts[lo]
        if span > gap_tol:
            if abs(tf - ts[lo]) <= snap_tol:
                out.append(vs[lo])
            elif abs(tf - ts[hi]) <= snap_tol:
                out.append(vs[hi])
            else:
                out.append(0.0)
        elif span <= 1e-9:
            out.append(vs[lo])
        else:
            frac = (tf - ts[lo]) / span
            out.append(vs[lo] + (vs[hi] - vs[lo]) * frac)
    return out


def _needed_overflow_x(lx_l: float, lx_r: float, pupil_rest_mode: int) -> float:
    (lo_l, hi_l), (lo_r, hi_r) = _pupil_base_bounds(pupil_rest_mode)
    return max(0.0, lo_l - lx_l, lx_l - hi_l, lo_r - lx_r, lx_r - hi_r)


def _eval_piecewise_linear(ticks: list[int], vals: list[float], t: int) -> float:
    if not ticks:
        return 0.0
    if t <= ticks[0]:
        return float(vals[0])
    if t >= ticks[-1]:
        return float(vals[-1])
    lo, hi = 0, len(ticks) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if ticks[mid] <= t:
            lo = mid
        else:
            hi = mid
    if ticks[lo] == t:
        return float(vals[lo])
    if ticks[hi] == t:
        return float(vals[hi])
    frac = (t - ticks[lo]) / float(ticks[hi] - ticks[lo])
    return float(vals[lo]) + (float(vals[hi]) - float(vals[lo])) * frac


def curves_to_face_rig_controls(
    curve_samples: dict[str, list[float]],
    *,
    pupil_rest_mode: int = -1,
    supported_curves: set[str] | frozenset[str] | None = None,
) -> tuple[dict[str, list], float]:
    """Convert dense sampled canonical `face_*` curves into smooth `CR_MC_Face` control tracks.

    Returns `(control_values_by_name, required_overflow_x)`.
    Uses the continuous, branch-free inverse mapping (blinks -> `eye_l/r_ctrl`, wide/squint -> `eye_both_ctrl`)
    so there is never a jump across `face_eye_wide == 0`.
    """
    n = max((len(v) for v in curve_samples.values()), default=0)
    if n == 0:
        return {}, 0.0
    allow = set(FACE_CURVES) if supported_curves is None else set(supported_curves)

    def _series(cname: str) -> list[float]:
        vals = curve_samples.get(cname)
        return [float(x) for x in vals] if vals and len(vals) == n else [0.0] * n

    out: dict[str, list] = {}
    max_need_ov_x = 0.0

    if 'face_eye_wide' in allow:
        ew = _series('face_eye_wide')
        out['eye_both_ctrl'] = [
            (max(0.0, -_clamp(w, -1.5, 1.5)), max(0.0, _clamp(w, -1.5, 1.5)))
            for w in ew
        ]
    if 'face_blink_l' in allow:
        out['eye_l_ctrl'] = [-_clamp(v, 0.0, 1.0) for v in _series('face_blink_l')]
    if 'face_blink_r' in allow:
        out['eye_r_ctrl'] = [-_clamp(v, 0.0, 1.0) for v in _series('face_blink_r')]

    has_lx = ('face_look_x_l' in allow) or ('face_look_x_r' in allow)
    has_ly = 'face_look_y' in allow
    if has_lx or has_ly:
        lx_l = _series('face_look_x_l')
        lx_r = _series('face_look_x_r')
        ly = _series('face_look_y')
        gaze_vals = []
        cross_vals = []
        for a, b, yv in zip(lx_l, lx_r, ly):
            a_c = _clamp(a, -2.0, 2.0)
            b_c = _clamp(b, -2.0, 2.0)
            y_c = _clamp(yv, -1.0, 1.0)
            max_need_ov_x = max(max_need_ov_x, _needed_overflow_x(a_c, b_c, pupil_rest_mode))
            gaze_vals.append((_clamp(0.5 * (a_c + b_c), -1.0, 1.0), y_c))
            cross_vals.append(_clamp(0.5 * (a_c - b_c), -1.5, 1.5))
        out['gaze_ctrl'] = gaze_vals
        if has_lx:
            out['gaze_ctrl.Eye_Cross'] = cross_vals
    if 'face_pupil_scale' in allow:
        out['gaze_ctrl.Pupil_Scale'] = [_clamp(v, -1.5, 1.5) for v in _series('face_pupil_scale')]

    if ('face_brow_y_l' in allow) or ('face_brow_rot_l' in allow):
        by_l, br_l = _series('face_brow_y_l'), _series('face_brow_rot_l')
        out['brow_l_ctrl'] = [(_clamp(r, -1.0, 1.0), _clamp(y, -1.0, 1.0)) for r, y in zip(br_l, by_l)]
    if ('face_brow_y_r' in allow) or ('face_brow_rot_r' in allow):
        by_r, br_r = _series('face_brow_y_r'), _series('face_brow_rot_r')
        out['brow_r_ctrl'] = [(_clamp(-r, -1.0, 1.0), _clamp(y, -1.0, 1.0)) for r, y in zip(br_r, by_r)]

    if ('face_mouth_open' in allow) or ('face_mouth_x' in allow):
        mo, mx = _series('face_mouth_open'), _series('face_mouth_x')
        out['mouth_ctrl'] = [(_clamp(x, -1.0, 1.0), _clamp(o, -1.0, 1.0)) for x, o in zip(mx, mo)]
    if ('face_mouth_wide' in allow) or ('face_mouth_smile' in allow):
        mw, ms = _series('face_mouth_wide'), _series('face_mouth_smile')
        out['mouth_expr_ctrl'] = [(_clamp(w, -1.0, 1.0), _clamp(s, -1.0, 1.0)) for w, s in zip(mw, ms)]

    return out, min(1.0, max_need_ov_x)


def sparse_curves_to_face_rig_batches(
    sparse_placed: dict[str, tuple[list[int], list[float]]],
    *,
    pupil_rest_mode: int = -1,
    existing_look_x: dict[str, tuple[list[int], list[float]]] | None = None,
    span_ticks: tuple[int, int] | None = None,
) -> tuple[dict[str, tuple[list[int], list[float]]], float]:
    """Map sparse `{curve_name: (ticks, values)}` into minimal `CR_MC_Face` control/sub-channel batches.

    Writes ONLY the controls / sub-channels directly affected by `sparse_placed`, preserving unrelated
    hand-keyed controls (e.g. `apply_auto_blink` touches ONLY `eye_l_ctrl`/`eye_r_ctrl`; emotion presets
    never touch gaze or blinks unless explicitly included).

    When ONLY one horizontal eye curve (`face_look_x_l` or `face_look_x_r`) is supplied and
    `existing_look_x` provides the untouched eye's existing `(ticks, values)`, the untouched eye's
    existing keyframes inside `span_ticks` (or the edited tick range) are merged into the union so
    single-eye edits never zero out or flatten the other eye's performance.
    """
    batches: dict[str, tuple[list[int], list[float]]] = {}
    max_need_ov_x = 0.0

    if 'face_blink_l' in sparse_placed:
        ts, vs = sparse_placed['face_blink_l']
        batches['eye_l_ctrl'] = (list(ts), [-_clamp(v, 0.0, 1.0) for v in vs])
    if 'face_blink_r' in sparse_placed:
        ts, vs = sparse_placed['face_blink_r']
        batches['eye_r_ctrl'] = (list(ts), [-_clamp(v, 0.0, 1.0) for v in vs])
    if 'face_eye_wide' in sparse_placed:
        ts, vs = sparse_placed['face_eye_wide']
        clamped = [_clamp(v, -1.5, 1.5) for v in vs]
        batches['eye_both_ctrl.x'] = (list(ts), [max(0.0, -w) for w in clamped])
        batches['eye_both_ctrl.y'] = (list(ts), [max(0.0, w) for w in clamped])
    if 'face_pupil_scale' in sparse_placed:
        ts, vs = sparse_placed['face_pupil_scale']
        batches['gaze_ctrl.Pupil_Scale'] = (list(ts), [_clamp(v, -1.5, 1.5) for v in vs])

    has_l = 'face_look_x_l' in sparse_placed
    has_r = 'face_look_x_r' in sparse_placed
    if has_l or has_r:
        ts_l, vs_l = sparse_placed['face_look_x_l'] if has_l else ([], [])
        ts_r, vs_r = sparse_placed['face_look_x_r'] if has_r else ([], [])
        if has_l and has_r:
            union_ticks = sorted(set(ts_l) | set(ts_r))
        else:
            present_ts = ts_l if has_l else ts_r
            missing_key = 'face_look_x_r' if has_l else 'face_look_x_l'
            ext_ts, ext_vs = (existing_look_x or {}).get(missing_key, ([], []))
            if has_l:
                ts_r, vs_r = ext_ts, ext_vs
            else:
                ts_l, vs_l = ext_ts, ext_vs
            if span_ticks is not None:
                lo_tk, hi_tk = int(span_ticks[0]), int(span_ticks[1])
                extra = [tk for tk in ext_ts if lo_tk <= tk <= hi_tk]
            elif present_ts:
                lo_tk, hi_tk = min(present_ts), max(present_ts)
                extra = [tk for tk in ext_ts if lo_tk <= tk <= hi_tk]
            else:
                extra = list(ext_ts)
            union_ticks = sorted(set(present_ts) | set(extra))
        gx_vals, cx_vals = [], []
        for tk in union_ticks:
            a = _clamp(_eval_piecewise_linear(ts_l, vs_l, tk), -2.0, 2.0)
            b = _clamp(_eval_piecewise_linear(ts_r, vs_r, tk), -2.0, 2.0)
            max_need_ov_x = max(max_need_ov_x, _needed_overflow_x(a, b, pupil_rest_mode))
            gx_vals.append(_clamp(0.5 * (a + b), -1.0, 1.0))
            cx_vals.append(_clamp(0.5 * (a - b), -1.5, 1.5))
        batches['gaze_ctrl.x'] = (union_ticks, gx_vals)
        batches['gaze_ctrl.Eye_Cross'] = (union_ticks, cx_vals)

    if 'face_look_y' in sparse_placed:
        ts, vs = sparse_placed['face_look_y']
        batches['gaze_ctrl.y'] = (list(ts), [_clamp(v, -1.0, 1.0) for v in vs])

    for cname, selector, sign in (
        ('face_brow_rot_l', 'brow_l_ctrl.x', 1.0),
        ('face_brow_y_l', 'brow_l_ctrl.y', 1.0),
        ('face_brow_rot_r', 'brow_r_ctrl.x', -1.0),
        ('face_brow_y_r', 'brow_r_ctrl.y', 1.0),
        ('face_mouth_x', 'mouth_ctrl.x', 1.0),
        ('face_mouth_open', 'mouth_ctrl.y', 1.0),
        ('face_mouth_wide', 'mouth_expr_ctrl.x', 1.0),
        ('face_mouth_smile', 'mouth_expr_ctrl.y', 1.0),
    ):
        if cname in sparse_placed:
            ts, vs = sparse_placed[cname]
            batches[selector] = (list(ts), [_clamp(sign * float(v), -1.0, 1.0) for v in vs])

    return batches, min(1.0, max_need_ov_x)


def _quat_str(pitch: float = 0.0, yaw: float = 0.0, roll: float = 0.0) -> str:
    q = unreal.Rotator(pitch=pitch, yaw=yaw, roll=roll).quaternion()
    return f'(X={q.x:.6f},Y={q.y:.6f},Z={q.z:.6f},W={q.w:.6f})'


def _tf_str(loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0)) -> str:
    q = _quat_str(pitch=rot[0], yaw=rot[1], roll=rot[2])
    return (
        f'(Rotation={q},'
        f'Translation=(X={loc[0]:.4f},Y={loc[1]:.4f},Z={loc[2]:.4f}),'
        f'Scale3D=(X={scale[0]:.4f},Y={scale[1]:.4f},Z={scale[2]:.4f}))'
    )


def _key_str(elem_type: str, name: str) -> str:
    return f'(Type={elem_type},Name="{name}")'


def _color_str(r: float, g: float, b: float, a: float = 1.0) -> str:
    return f'(R={r:.4f},G={g:.4f},B={b:.4f},A={a:.4f})'


class _RigBuilder:
    """Thin RigVM graph builder keeping node placement and pin wiring concise."""

    def __init__(self, ctrl):
        self.ctrl = ctrl
        self.v2 = unreal.Vector2D

    def unit(self, struct_path: str, x: float, y: float, name: str = ''):
        return self.ctrl.add_unit_node_from_struct_path(struct_path, 'Execute', self.v2(x, y), name)

    def set_pin(self, node, pin: str, value: str) -> None:
        self.ctrl.set_pin_default_value(f'{node.get_name()}.{pin}', str(value), True)

    def link(self, src_node, src_pin: str, dst_node, dst_pin: str) -> None:
        self.ctrl.add_link(f'{src_node.get_name()}.{src_pin}', f'{dst_node.get_name()}.{dst_pin}')

    @staticmethod
    def exec_pin_name(node) -> str:
        for candidate in ('ExecutePin', 'ExecuteContext'):
            if node.find_pin(candidate) is not None:
                return candidate
        raise RuntimeError(f'Node {node.get_name()} has no execute pin')

    def chain(self, prev_node, next_node, *, prev_pin: str | None = None) -> object:
        p_out = prev_pin or self.exec_pin_name(prev_node)
        p_in = self.exec_pin_name(next_node)
        self.link(prev_node, p_out, next_node, p_in)
        return next_node

    def add_null(self, parent_key: str, null_name: str, loc, rot, scale, x: float, y: float, node_name: str):
        n = self.unit('/Script/ControlRig.RigUnit_HierarchyAddNull', x, y, node_name)
        self.set_pin(n, 'Parent', parent_key)
        self.set_pin(n, 'Name', null_name)
        self.set_pin(n, 'Transform', _tf_str(loc, rot, scale))
        self.set_pin(n, 'Space', 'LocalSpace')
        return n

    def add_float_ctrl(self, parent_key: str, ctrl_name: str, *, min_v: float, max_v: float,
                       shape: str, color: tuple[float, float, float], shape_scale: tuple[float, float, float],
                       shape_rot: tuple[float, float, float] = (90.0, 0.0, 0.0),
                       primary_axis: str = 'Z', x: float, y: float):
        n = self.unit('/Script/ControlRig.RigUnit_HierarchyAddControlFloat', x, y, f'Add_{ctrl_name}')
        self.set_pin(n, 'Parent', parent_key)
        self.set_pin(n, 'Name', ctrl_name)
        self.set_pin(n, 'OffsetTransform', _tf_str())
        self.set_pin(n, 'OffsetSpace', 'LocalSpace')
        self.set_pin(n, 'InitialValue', '0.0')
        shape_tf = _tf_str((0.0, 0.0, 0.0), shape_rot, shape_scale)
        settings = (
            f'(PrimaryAxis={primary_axis},bIsScale=False,'
            f'Limits=(Limit=(bMinimum=True,bMaximum=True),MinValue={min_v:.4f},MaxValue={max_v:.4f},bDrawLimits=True),'
            f'Shape=(bVisible=True,Name="{shape}",Color={_color_str(*color)},Transform={shape_tf}),'
            f'Proxy=(bIsProxy=False,ShapeVisibility=UserDefined),'
            f'bSelectable=True)'
        )
        self.set_pin(n, 'Settings', settings)
        return n

    def add_v2_ctrl(self, parent_key: str, ctrl_name: str, *, min_xy: tuple[float, float], max_xy: tuple[float, float],
                    shape: str, color: tuple[float, float, float], shape_scale: tuple[float, float, float],
                    shape_rot: tuple[float, float, float] = (90.0, 0.0, 0.0),
                    display_name: str = '', x: float, y: float):
        n = self.unit('/Script/ControlRig.RigUnit_HierarchyAddControlVector2D', x, y, f'Add_{ctrl_name}')
        self.set_pin(n, 'Parent', parent_key)
        self.set_pin(n, 'Name', ctrl_name)
        self.set_pin(n, 'OffsetTransform', _tf_str())
        self.set_pin(n, 'OffsetSpace', 'LocalSpace')
        self.set_pin(n, 'InitialValue', '(X=0.0,Y=0.0)')
        shape_tf = _tf_str((0.0, 0.0, 0.0), shape_rot, shape_scale)
        disp_part = f'DisplayName="{display_name}",' if display_name else ''
        settings = (
            f'(PrimaryAxis=X,'
            f'Limits=(LimitX=(bMinimum=True,bMaximum=True),LimitY=(bMinimum=True,bMaximum=True),'
            f'MinValue=(X={min_xy[0]:.4f},Y={min_xy[1]:.4f}),MaxValue=(X={max_xy[0]:.4f},Y={max_xy[1]:.4f}),bDrawLimits=True),'
            f'Shape=(bVisible=True,Name="{shape}",Color={_color_str(*color)},Transform={shape_tf}),'
            f'Proxy=(bIsProxy=False,ShapeVisibility=UserDefined),'
            f'{disp_part}'
            f'bSelectable=True)'
        )
        self.set_pin(n, 'Settings', settings)
        return n

    def add_float_channel(self, parent_ctrl: str, ch_name: str, *, initial: float, min_v: float, max_v: float,
                          x: float, y: float):
        n = self.unit('/Script/ControlRig.RigUnit_HierarchyAddAnimationChannelFloat', x, y, f'AddCh_{ch_name}')
        self.set_pin(n, 'Parent', _key_str('Control', parent_ctrl))
        self.set_pin(n, 'Name', ch_name)
        self.set_pin(n, 'InitialValue', f'{initial:.4f}')
        self.set_pin(n, 'MinimumValue', f'{min_v:.4f}')
        self.set_pin(n, 'MaximumValue', f'{max_v:.4f}')
        self.set_pin(n, 'LimitsEnabled', '(Enabled=(bMinimum=True,bMaximum=True))')
        return n

    def add_int_channel(self, parent_ctrl: str, ch_name: str, *, initial: int, min_v: int, max_v: int,
                        x: float, y: float):
        n = self.unit('/Script/ControlRig.RigUnit_HierarchyAddAnimationChannelInteger', x, y, f'AddCh_{ch_name}')
        self.set_pin(n, 'Parent', _key_str('Control', parent_ctrl))
        self.set_pin(n, 'Name', ch_name)
        self.set_pin(n, 'InitialValue', str(int(initial)))
        self.set_pin(n, 'MinimumValue', str(int(min_v)))
        self.set_pin(n, 'MaximumValue', str(int(max_v)))
        self.set_pin(n, 'LimitsEnabled', '(Enabled=(bMinimum=True,bMaximum=True))')
        return n

    def add_bool_channel(self, parent_ctrl: str, ch_name: str, *, initial: bool, x: float, y: float):
        n = self.unit('/Script/ControlRig.RigUnit_HierarchyAddAnimationChannelBool', x, y, f'AddCh_{ch_name}')
        self.set_pin(n, 'Parent', _key_str('Control', parent_ctrl))
        self.set_pin(n, 'Name', ch_name)
        self.set_pin(n, 'InitialValue', 'True' if initial else 'False')
        return n

    def set_vis(self, ctrl_name: str, cond_node, cond_pin: str, x: float, y: float):
        n = self.unit('/Script/ControlRig.RigUnit_SetControlVisibility', x, y, f'Vis_{ctrl_name}')
        self.set_pin(n, 'Item', _key_str('Control', ctrl_name))
        self.link(cond_node, cond_pin, n, 'bVisible')
        return n

    # --- Math & read helpers ---

    def get_b(self, ctrl_name: str, x: float, y: float, tag: str = ''):
        n = self.unit('/Script/ControlRig.RigUnit_GetControlBool', x, y, f'GetB_{tag or ctrl_name}')
        self.set_pin(n, 'Control', ctrl_name)
        return n, 'BoolValue'

    def get_i(self, ctrl_name: str, x: float, y: float, tag: str = ''):
        n = self.unit('/Script/ControlRig.RigUnit_GetControlInteger', x, y, f'GetI_{tag or ctrl_name}')
        self.set_pin(n, 'Control', ctrl_name)
        return n, 'IntegerValue'

    def get_f(self, ctrl_name: str, x: float, y: float, tag: str = ''):
        n = self.unit('/Script/ControlRig.RigUnit_GetControlFloat', x, y, f'GetF_{tag or ctrl_name}')
        self.set_pin(n, 'Control', ctrl_name)
        return n, 'FloatValue'

    def get_v2(self, ctrl_name: str, x: float, y: float, tag: str = ''):
        n = self.unit('/Script/ControlRig.RigUnit_GetControlVector2D', x, y, f'GetV2_{tag or ctrl_name}')
        self.set_pin(n, 'Control', ctrl_name)
        return n

    def get_curve(self, curve_name: str, x: float, y: float):
        n = self.unit('/Script/ControlRig.RigUnit_GetCurveValue', x, y, f'GetC_{curve_name}')
        self.set_pin(n, 'Curve', curve_name)
        return n, 'Value'

    def i_op(self, op: str, a, b, x: float, y: float, name: str = ''):
        n = self.unit(f'/Script/RigVM.RigVMFunction_MathInt{op}', x, y, name)
        if isinstance(a, tuple):
            self.link(a[0], a[1], n, 'A')
        else:
            self.set_pin(n, 'A', str(int(a)))
        if isinstance(b, tuple):
            self.link(b[0], b[1], n, 'B')
        else:
            self.set_pin(n, 'B', str(int(b)))
        return n, 'Result'

    def f_op(self, op: str, a, b, x: float, y: float, name: str = ''):
        n = self.unit(f'/Script/RigVM.RigVMFunction_MathFloat{op}', x, y, name)
        if isinstance(a, tuple):
            self.link(a[0], a[1], n, 'A')
        else:
            self.set_pin(n, 'A', f'{a:.6f}')
        if isinstance(b, tuple):
            self.link(b[0], b[1], n, 'B')
        else:
            self.set_pin(n, 'B', f'{b:.6f}')
        return n, 'Result'

    def f_neg(self, val, x: float, y: float, name: str = ''):
        n = self.unit('/Script/RigVM.RigVMFunction_MathFloatNegate', x, y, name)
        self.link(val[0], val[1], n, 'Value')
        return n, 'Result'

    def f_clamp(self, val, lo, hi, x: float, y: float, name: str = ''):
        n = self.unit('/Script/RigVM.RigVMFunction_MathFloatClamp', x, y, name)
        self.link(val[0], val[1], n, 'Value')
        if isinstance(lo, tuple):
            self.link(lo[0], lo[1], n, 'Minimum')
        else:
            self.set_pin(n, 'Minimum', f'{lo:.6f}')
        if isinstance(hi, tuple):
            self.link(hi[0], hi[1], n, 'Maximum')
        else:
            self.set_pin(n, 'Maximum', f'{hi:.6f}')
        return n, 'Result'

    def f_select(self, cond, if_true, if_false, x: float, y: float, name: str = ''):
        n = self.unit('/Script/RigVM.RigVMFunction_MathFloatSelectBool', x, y, name)
        self.link(cond[0], cond[1], n, 'Condition')
        if isinstance(if_true, tuple):
            self.link(if_true[0], if_true[1], n, 'IfTrue')
        else:
            self.set_pin(n, 'IfTrue', f'{if_true:.6f}')
        if isinstance(if_false, tuple):
            self.link(if_false[0], if_false[1], n, 'IfFalse')
        else:
            self.set_pin(n, 'IfFalse', f'{if_false:.6f}')
        return n, 'Result'


def _build_construction_event(b: _RigBuilder) -> None:
    """Spawn pure-W floating viewport controls parented to the cross-species anchor chain."""
    y0 = -1200.0
    prep = b.unit('/Script/ControlRig.RigUnit_PrepareForExecution', 0, y0, 'ConstructionEvent')

    # 1) Anchor face_panel_root on the tail of `_HEAD_ANCHOR_CHAIN` (`real_head`).
    # Any intermediate or tail bone absent on a target mesh stays at Identity local transform,
    # so `real_head` automatically tracks `head` (Steve/split), `head_parts -> head` (Horse),
    # `head -> real_head` (Wolf), or `body` (Bee/Ghast).
    cur = b.chain(prep, b.add_null(
        _key_str('Bone', _HEAD_ANCHOR_CHAIN[-1]), 'face_panel_root',
        (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 1.0, 1.0),
        340, y0, 'Add_face_panel_root',
    ))

    # 2) Master panel transform control above the head (Z = +68 clears Steve 50cm and Villager 62.5cm).
    panel_z = 68.0
    panel_ctrl = b.unit('/Script/ControlRig.RigUnit_HierarchyAddControlTransform', 700, y0, 'Add_face_panel_ctrl')
    b.set_pin(panel_ctrl, 'Parent', _key_str('Null', 'face_panel_root'))
    b.set_pin(panel_ctrl, 'Name', 'face_panel_ctrl')
    b.set_pin(panel_ctrl, 'OffsetTransform', _tf_str((0.0, 0.0, panel_z)))
    b.set_pin(panel_ctrl, 'OffsetSpace', 'LocalSpace')
    b.set_pin(panel_ctrl, 'InitialValue', _tf_str())
    panel_shape_tf = _tf_str((0.0, 0.0, 0.0), (90.0, 0.0, 0.0), (0.95, 0.95, 0.95))
    b.set_pin(
        panel_ctrl, 'Settings',
        f'(InitialSpace=LocalSpace,'
        f'Shape=(bVisible=True,Name="Hexagon_Solid",Color={_color_str(0.55, 0.25, 1.0)},Transform={panel_shape_tf}),'
        f'Proxy=(bIsProxy=False,ShapeVisibility=UserDefined),'
        f'bSelectable=True)',
    )
    cur = b.chain(cur, panel_ctrl)
    cur = b.chain(cur, b.add_bool_channel('face_panel_ctrl', 'Show_Brows', initial=True, x=1060, y=y0))
    cur = b.chain(cur, b.add_bool_channel('face_panel_ctrl', 'Show_Mouth', initial=True, x=1380, y=y0))
    cur = b.chain(cur, b.add_int_channel(
        'face_panel_ctrl', 'Pupil_Rest_Mode', initial=-1, min_v=-1, max_v=1, x=1700, y=y0,
    ))
    cur = b.chain(cur, b.add_float_channel(
        'face_panel_ctrl', 'Eye_Margin_In', initial=DEFAULT_EYE_BOUNDS['margin_in'], min_v=0.0, max_v=10.0, x=2020, y=y0,
    ))
    cur = b.chain(cur, b.add_float_channel(
        'face_panel_ctrl', 'Eye_Margin_Out', initial=DEFAULT_EYE_BOUNDS['margin_out'], min_v=0.0, max_v=10.0, x=2340, y=y0,
    ))
    cur = b.chain(cur, b.add_float_channel(
        'face_panel_ctrl', 'Pupil_Scale_Shift', initial=DEFAULT_EYE_BOUNDS['scale_shift'], min_v=0.0, max_v=3.0, x=2660, y=y0,
    ))

    # 3) Floating W-only slider & 2D joystick controls around the head perimeter (X = +27 cm).
    panel_key = _key_str('Control', 'face_panel_ctrl')
    face_x = 27.0
    x_pos = 3000.0

    # --- Unified Both-Eye 2D Control (Up = Wide, Down = Blink, Left/Outward +X = Squint) ---
    # Slot Yaw=0 maps Vector2D +X to Head +Y (Viewer Left, outward away from eye_r_ctrl) and +Y to Head +Z (Up).
    cur = b.chain(cur, b.add_null(
        panel_key, 'eye_both_ctrl_slot', (face_x, 53.0, 28.0 - panel_z), (0.0, 0.0, 0.0), (7.0, 7.0, 7.0),
        x_pos, y0, 'Add_eye_both_ctrl_slot',
    ))
    x_pos += 320.0
    cur = b.chain(cur, b.add_v2_ctrl(
        _key_str('Null', 'eye_both_ctrl_slot'), 'eye_both_ctrl',
        min_xy=(0.0, -1.0), max_xy=(1.5, 1.5),
        shape='Diamond_Solid', color=(1.0, 0.85, 0.12), shape_scale=(0.075, 0.075, 0.075),
        shape_rot=(0.0, 0.0, 0.0), x=x_pos, y=y0,
    ))
    x_pos += 340.0

    # --- Individual Eye Blink/Wink Sliders (Down-only [-1, 0], never widens the other eye) ---
    for cname, y_off in (('eye_r_ctrl', 41.0), ('eye_l_ctrl', -41.0)):
        slot = f'{cname}_slot'
        cur = b.chain(cur, b.add_null(
            panel_key, slot, (face_x, y_off, 28.0 - panel_z), (0.0, 0.0, 0.0), (7.0, 7.0, 7.0),
            x_pos, y0, f'Add_{slot}',
        ))
        x_pos += 320.0
        cur = b.chain(cur, b.add_float_ctrl(
            _key_str('Null', slot), cname, min_v=-1.0, max_v=0.0,
            shape='Circle_Solid', color=(0.15, 0.85, 1.0), shape_scale=(0.075, 0.075, 0.075),
            primary_axis='Z', x=x_pos, y=y0,
        ))
        x_pos += 340.0

    # --- 2D Joysticks (Yaw=180 aligns PrimaryAxis=X Vector2D so +X = Viewer Right [-Y], +Y = Up [+Z]) ---
    v2_specs = (
        ('gaze_ctrl',       (face_x,  48.0,  9.0 - panel_z), 6.0, (-1.0, -1.0), (1.0, 1.0), 'Arrow4_Solid',        (1.0, 0.90, 0.15), (0.12, 0.12, 0.12), ''),
        ('brow_r_ctrl',     (face_x,  46.0, 45.0 - panel_z), 5.5, (-1.0, -1.0), (1.0, 1.0), 'RoundedSquare_Solid', (0.20, 0.95, 0.35), (0.07, 0.11, 0.09), ''),
        ('brow_l_ctrl',     (face_x, -46.0, 45.0 - panel_z), 5.5, (-1.0, -1.0), (1.0, 1.0), 'RoundedSquare_Solid', (0.20, 0.95, 0.35), (0.07, 0.11, 0.09), ''),
        ('mouth_ctrl',      (face_x, -44.0,  9.0 - panel_z), 5.5, (-1.0, -1.0), (1.0, 1.0), 'Arrow4_Solid',        (1.0, 0.55, 0.12), (0.12, 0.12, 0.12), 'Mouth (Open / Shift)'),
        ('mouth_expr_ctrl', (face_x, -60.0,  9.0 - panel_z), 5.5, (-1.0, -1.0), (1.0, 1.0), 'Circle_Solid',        (1.0, 0.35, 0.55), (0.095, 0.095, 0.095), 'Mouth (Smile / Wide)'),
    )
    for cname, loc, sc, lo_xy, hi_xy, shape, color, sh_sc, disp_name in v2_specs:
        slot = f'{cname}_slot'
        cur = b.chain(cur, b.add_null(panel_key, slot, loc, (0.0, 180.0, 0.0), (sc, sc, sc), x_pos, y0, f'Add_{slot}'))
        x_pos += 320.0
        cur = b.chain(cur, b.add_v2_ctrl(
            _key_str('Null', slot), cname, min_xy=lo_xy, max_xy=hi_xy,
            shape=shape, color=color, shape_scale=sh_sc, display_name=disp_name, x=x_pos, y=y0,
        ))
        x_pos += 340.0

    # Gaze channels: Pupil_Scale, Eye_Overflow_X (0=in-socket, 0.5=half-exit, 1=full), Eye_Overflow_Y (0=locked, 1=full), Eye_Cross.
    cur = b.chain(cur, b.add_float_channel('gaze_ctrl', 'Pupil_Scale', initial=0.0, min_v=-1.5, max_v=1.5, x=x_pos, y=y0))
    x_pos += 320.0
    cur = b.chain(cur, b.add_float_channel('gaze_ctrl', 'Eye_Overflow_X', initial=_DEFAULT_OVERFLOW_X, min_v=0.0, max_v=1.0, x=x_pos, y=y0))
    x_pos += 320.0
    cur = b.chain(cur, b.add_float_channel('gaze_ctrl', 'Eye_Overflow_Y', initial=_DEFAULT_OVERFLOW_Y, min_v=0.0, max_v=1.0, x=x_pos, y=y0))
    x_pos += 320.0
    b.chain(cur, b.add_float_channel('gaze_ctrl', 'Eye_Cross', initial=0.0, min_v=-1.5, max_v=1.5, x=x_pos, y=y0))


def _wire_pupil_base_bounds(b: _RigBuilder, mode_pin, x: float, y: float, prefix: str):
    """Return `(base_lo_l, base_hi_l, base_lo_r, base_hi_r)` for `Pupil_Rest_Mode` in `{-1, 0, +1}`."""
    is_inner = b.i_op('Less', mode_pin, 0, x, y, f'{prefix}IsInner')
    is_outer = b.i_op('Greater', mode_pin, 0, x, y + 90, f'{prefix}IsOuter')
    base_lo_l = b.f_select(is_outer, -1.0, 0.0, x + 220, y, f'{prefix}BaseLoL')
    base_hi_l = b.f_select(is_inner, 1.0, 0.0, x + 220, y + 80, f'{prefix}BaseHiL')
    base_lo_r = b.f_select(is_inner, -1.0, 0.0, x + 220, y + 160, f'{prefix}BaseLoR')
    base_hi_r = b.f_select(is_outer, 1.0, 0.0, x + 220, y + 240, f'{prefix}BaseHiR')
    return base_lo_l, base_hi_l, base_lo_r, base_hi_r


def _build_forward_solve(b: _RigBuilder) -> None:
    """Map floating viewport controls -> 15 canonical `face_*` curves."""
    y0 = 0.0
    begin = b.unit('/Script/ControlRig.RigUnit_BeginExecution', 0, y0, 'ForwardSolve')

    # Panel flags, species pupil rest mode, and per-direction head-boundary margins
    show_brows = b.get_b('Show_Brows', -1200, -240, 'ShowBrows')
    show_mouth = b.get_b('Show_Mouth', -1200, -140, 'ShowMouth')
    pupil_mode = b.get_i('Pupil_Rest_Mode', -1200, -20, 'PupilMode')
    margin_in = b.get_f('Eye_Margin_In', -1200, 60, 'EyeMarginIn')
    margin_out = b.get_f('Eye_Margin_Out', -1200, 140, 'EyeMarginOut')
    scale_shift = b.get_f('Pupil_Scale_Shift', -1200, 220, 'PupilScaleShift')

    # Eyes: eye_both (X = Squint, +Y = Wide, -Y = Both Blink), eye_l/r (down-only [-1, 0] individual blink)
    eye_both = b.get_v2('eye_both_ctrl', -1200, 320, 'EyeBoth')
    eye_l = b.get_f('eye_l_ctrl', -1200, 440, 'EyeL')
    eye_r = b.get_f('eye_r_ctrl', -1200, 560, 'EyeR')

    both_blink = b.f_op('Max', b.f_neg((eye_both, 'Vector.Y'), -940, 320, 'NegBothY'), 0.0, -720, 320, 'BothBlink')
    indiv_bl = b.f_op('Max', b.f_neg(eye_l, -940, 440, 'NegEyeL'), 0.0, -720, 440, 'IndivBL')
    indiv_br = b.f_op('Max', b.f_neg(eye_r, -940, 560, 'NegEyeR'), 0.0, -720, 560, 'IndivBR')
    man_blink_l = b.f_op('Add', both_blink, indiv_bl, -460, 420, 'ManBlinkL')
    man_blink_r = b.f_op('Add', both_blink, indiv_br, -460, 540, 'ManBlinkR')

    wide_pos = b.f_op('Max', (eye_both, 'Vector.Y'), 0.0, -720, 660, 'WidePos')
    squint_pos = b.f_op('Max', (eye_both, 'Vector.X'), 0.0, -720, 760, 'SquintPos')
    man_eye_wide = b.f_op('Sub', wide_pos, squint_pos, -460, 700, 'ManEyeWide')

    # Gaze (Vector2D [-1, 1]) + channels (Pupil_Scale, Eye_Overflow_X, Eye_Overflow_Y, Eye_Cross)
    gaze = b.get_v2('gaze_ctrl', -1200, 900, 'Gaze')
    pupil_sc = b.get_f('Pupil_Scale', -1200, 1020, 'PupilScale')
    ov_x = b.f_clamp(b.get_f('Eye_Overflow_X', -1200, 1140, 'EyeOvX'), 0.0, 1.0, -940, 1140, 'ClampOvX')
    ov_y = b.f_clamp(b.get_f('Eye_Overflow_Y', -1200, 1260, 'EyeOvY'), 0.0, 1.0, -940, 1260, 'ClampOvY')
    eye_cross = b.get_f('Eye_Cross', -1200, 1380, 'EyeCross')

    # Step 1: socket + Eye_Overflow_X clamp based on Pupil_Rest_Mode
    base_lo_l, base_hi_l, base_lo_r, base_hi_r = _wire_pupil_base_bounds(b, pupil_mode, -960, -140, 'Fwd')
    lo_l = b.f_op('Sub', base_lo_l, ov_x, -520, 900, 'LimLoL')
    hi_l = b.f_op('Add', base_hi_l, ov_x, -520, 980, 'LimHiL')
    lo_r = b.f_op('Sub', base_lo_r, ov_x, -520, 1080, 'LimLoR')
    hi_r = b.f_op('Add', base_hi_r, ov_x, -520, 1160, 'LimHiR')

    raw_x_l = b.f_op('Add', (gaze, 'Vector.X'), eye_cross, -860, 900, 'RawLookXL')
    raw_x_r = b.f_op('Sub', (gaze, 'Vector.X'), eye_cross, -860, 1000, 'RawLookXR')
    step1_l = b.f_clamp(raw_x_l, lo_l, hi_l, -260, 920, 'Step1LookXL')
    step1_r = b.f_clamp(raw_x_r, lo_r, hi_r, -260, 1060, 'Step1LookXR')

    # Step 2: per-direction head-surface safety clamp adjusted for positive Pupil_Scale expansion
    pos_ps = b.f_op('Max', pupil_sc, 0.0, -940, 1020, 'PosPupilScale')
    grow = b.f_op('Mul', pos_ps, scale_shift, -740, 1020, 'PupilGrow')
    neg_m_in = b.f_neg(margin_in, -740, 60, 'NegMarginIn')
    neg_m_out = b.f_neg(margin_out, -740, 140, 'NegMarginOut')

    raw_safe_lo_l = b.f_op('Add', neg_m_in, grow, -520, 60, 'RawSafeLoL')
    raw_safe_hi_l = b.f_op('Sub', margin_out, grow, -520, 140, 'RawSafeHiL')
    mid_l = b.f_op('Mul', b.f_op('Add', raw_safe_lo_l, raw_safe_hi_l, -340, 100, 'SumSafeL'), 0.5, -180, 100, 'MidSafeL')
    safe_lo_l = b.f_op('Min', raw_safe_lo_l, mid_l, -20, 60, 'SafeLoL')
    safe_hi_l = b.f_op('Max', raw_safe_hi_l, mid_l, -20, 140, 'SafeHiL')

    raw_safe_lo_r = b.f_op('Add', neg_m_out, grow, -520, 220, 'RawSafeLoR')
    raw_safe_hi_r = b.f_op('Sub', margin_in, grow, -520, 300, 'RawSafeHiR')
    mid_r = b.f_neg(mid_l, -180, 260, 'MidSafeR')
    safe_lo_r = b.f_op('Min', raw_safe_lo_r, mid_r, -20, 220, 'SafeLoR')
    safe_hi_r = b.f_op('Max', raw_safe_hi_r, mid_r, -20, 300, 'SafeHiR')

    man_look_x_l = b.f_clamp(step1_l, safe_lo_l, safe_hi_l, 40, 920, 'LimLookXL')
    man_look_x_r = b.f_clamp(step1_r, safe_lo_r, safe_hi_r, 40, 1060, 'LimLookXR')

    neg_ov_y = b.f_neg(ov_y, -520, 1260, 'NegOvY')
    man_look_y = b.f_clamp((gaze, 'Vector.Y'), neg_ov_y, ov_y, -200, 1240, 'LimLookY')

    # Eyebrows (Vector2D): Y = height, X = mirror-symmetric tilt (inward toward nose = Angry < 0, outward = Sad > 0)
    brow_l = b.get_v2('brow_l_ctrl', -1200, 1520, 'BrowL')
    brow_r = b.get_v2('brow_r_ctrl', -1200, 1640, 'BrowR')
    man_brow_rot_r = b.f_neg((brow_r, 'Vector.X'), -860, 1640, 'ManBrowRotR')

    # Mouth 2D joysticks
    mouth = b.get_v2('mouth_ctrl', -1200, 1800, 'Mouth')
    mouth_expr = b.get_v2('mouth_expr_ctrl', -1200, 1920, 'MouthExpr')

    curves_out = {
        'face_blink_l': man_blink_l,
        'face_blink_r': man_blink_r,
        'face_eye_wide': man_eye_wide,
        'face_pupil_scale': pupil_sc,
        'face_look_x_l': man_look_x_l,
        'face_look_x_r': man_look_x_r,
        'face_look_y': man_look_y,
        'face_brow_y_l': (brow_l, 'Vector.Y'),
        'face_brow_y_r': (brow_r, 'Vector.Y'),
        'face_brow_rot_l': (brow_l, 'Vector.X'),
        'face_brow_rot_r': man_brow_rot_r,
        'face_mouth_open': (mouth, 'Vector.Y'),
        'face_mouth_wide': (mouth_expr, 'Vector.X'),
        'face_mouth_smile': (mouth_expr, 'Vector.Y'),
        'face_mouth_x': (mouth, 'Vector.X'),
    }

    cur = begin
    for idx, cname in enumerate(FACE_CURVES):
        row_y = 220.0 + idx * 120.0
        lo, hi = _CURVE_CLAMP[cname]
        clamped = b.f_clamp(curves_out[cname], lo, hi, 260.0, row_y, f'Clamp_{cname}')
        set_c = b.unit('/Script/ControlRig.RigUnit_SetCurveValue', 300.0 + idx * 240.0, y0, f'SetC_{cname}')
        b.set_pin(set_c, 'Curve', cname)
        b.link(clamped[0], clamped[1], set_c, 'Value')
        cur = b.chain(cur, set_c)

    # Apply interactive brow/mouth visibility toggles cleanly in viewport.
    vx = 300.0 + len(FACE_CURVES) * 240.0 + 120.0
    for idx, (cname, flag) in enumerate((
        ('brow_l_ctrl', show_brows),
        ('brow_r_ctrl', show_brows),
        ('mouth_ctrl', show_mouth),
        ('mouth_expr_ctrl', show_mouth),
    )):
        cur = b.chain(cur, b.set_vis(cname, flag[0], flag[1], vx + idx * 280.0, y0))


def _build_backwards_solve(b: _RigBuilder) -> None:
    """Smooth branch-free inverse mapping (exact round-trip within reachable control limits)."""
    y0 = 2300.0
    inv = b.unit('/Script/ControlRig.RigUnit_InverseExecution', 0, y0, 'BackwardsSolve')

    c = {cname: b.get_curve(cname, -1100, y0 + 180 + idx * 110) for idx, cname in enumerate(FACE_CURVES)}
    inv_mode = b.get_i('Pupil_Rest_Mode', -1100, y0 + 40, 'InvPupilMode')

    # --- Eyes: smooth continuous split (blinks ALWAYS on eye_l/r_ctrl; wide/squint on eye_both_ctrl) ---
    # Avoids any jump across `face_eye_wide == 0` when interpolating between frames!
    bl = b.f_clamp(c['face_blink_l'], 0.0, 1.0, -820, y0 + 180, 'InvClampBL')
    br = b.f_clamp(c['face_blink_r'], 0.0, 1.0, -820, y0 + 290, 'InvClampBR')
    ew = b.f_clamp(c['face_eye_wide'], -1.5, 1.5, -820, y0 + 400, 'InvClampEW')

    inv_eb_x = b.f_op('Max', b.f_neg(ew, -580, y0 + 460, 'InvNegEW'), 0.0, -340, y0 + 460, 'InvSquint')
    inv_eb_y = b.f_op('Max', ew, 0.0, -340, y0 + 360, 'InvBothY')
    inv_el = b.f_neg(bl, -340, y0 + 180, 'InvEL')
    inv_er = b.f_neg(br, -340, y0 + 270, 'InvER')

    set_eb = b.unit('/Script/ControlRig.RigUnit_SetControlVector2D', 320, y0, 'InvSet_EyeBoth')
    b.set_pin(set_eb, 'Control', 'eye_both_ctrl')
    b.link(inv_eb_x[0], inv_eb_x[1], set_eb, 'Vector.X')
    b.link(inv_eb_y[0], inv_eb_y[1], set_eb, 'Vector.Y')
    cur = b.chain(inv, set_eb)

    set_el = b.unit('/Script/ControlRig.RigUnit_SetControlFloat', 620, y0, 'InvSet_EyeL')
    b.set_pin(set_el, 'Control', 'eye_l_ctrl')
    b.link(inv_el[0], inv_el[1], set_el, 'FloatValue')
    cur = b.chain(cur, set_el)

    set_er = b.unit('/Script/ControlRig.RigUnit_SetControlFloat', 920, y0, 'InvSet_EyeR')
    b.set_pin(set_er, 'Control', 'eye_r_ctrl')
    b.link(inv_er[0], inv_er[1], set_er, 'FloatValue')
    cur = b.chain(cur, set_er)

    # --- Gaze: (gx, ly) clamped to [-1, 1], Pupil_Scale, mode-aware Eye_Overflow_X/Y, Eye_Cross ---
    lx_l, lx_r = c['face_look_x_l'], c['face_look_x_r']
    inv_gx = b.f_clamp(
        b.f_op('Mul', b.f_op('Add', lx_l, lx_r, -820, y0 + 620, 'InvAddLX'), 0.5, -580, y0 + 620, 'InvGazeXRaw'),
        -1.0, 1.0, -340, y0 + 620, 'InvGazeX',
    )
    inv_ly = b.f_clamp(c['face_look_y'], -1.0, 1.0, -340, y0 + 700, 'InvGazeY')
    inv_cx = b.f_clamp(
        b.f_op('Mul', b.f_op('Sub', lx_l, lx_r, -820, y0 + 780, 'InvSubLX'), 0.5, -580, y0 + 780, 'InvCrossXRaw'),
        -1.5, 1.5, -340, y0 + 780, 'InvCrossX',
    )

    b_lo_l, b_hi_l, b_lo_r, b_hi_r = _wire_pupil_base_bounds(b, inv_mode, -880, y0 + 880, 'Inv')
    ov_l = b.f_op(
        'Max',
        b.f_op('Sub', b_lo_l, lx_l, -420, y0 + 880, 'InvOvLLo'),
        b.f_op('Sub', lx_l, b_hi_l, -420, y0 + 960, 'InvOvLHi'),
        -200, y0 + 920, 'InvOvL',
    )
    ov_r = b.f_op(
        'Max',
        b.f_op('Sub', b_lo_r, lx_r, -420, y0 + 1040, 'InvOvRLo'),
        b.f_op('Sub', lx_r, b_hi_r, -420, y0 + 1120, 'InvOvRHi'),
        -200, y0 + 1080, 'InvOvR',
    )
    inv_ov_x = b.f_clamp(
        b.f_op('Max', b.f_op('Max', ov_l, ov_r, 0, y0 + 980, 'InvOvLR'), _DEFAULT_OVERFLOW_X, 180, y0 + 980, 'InvOvFloor'),
        0.0, 1.0, 360, y0 + 980, 'InvOvX',
    )

    set_gaze = b.unit('/Script/ControlRig.RigUnit_SetControlVector2D', 1240, y0, 'InvSet_Gaze')
    b.set_pin(set_gaze, 'Control', 'gaze_ctrl')
    b.link(inv_gx[0], inv_gx[1], set_gaze, 'Vector.X')
    b.link(inv_ly[0], inv_ly[1], set_gaze, 'Vector.Y')
    cur = b.chain(cur, set_gaze)

    set_ps = b.unit('/Script/ControlRig.RigUnit_SetControlFloat', 1540, y0, 'InvSet_PupilScale')
    b.set_pin(set_ps, 'Control', 'Pupil_Scale')
    b.link(c['face_pupil_scale'][0], c['face_pupil_scale'][1], set_ps, 'FloatValue')
    cur = b.chain(cur, set_ps)

    set_ov_x = b.unit('/Script/ControlRig.RigUnit_SetControlFloat', 1840, y0, 'InvSet_EyeOvX')
    b.set_pin(set_ov_x, 'Control', 'Eye_Overflow_X')
    b.link(inv_ov_x[0], inv_ov_x[1], set_ov_x, 'FloatValue')
    cur = b.chain(cur, set_ov_x)

    set_ov_y = b.unit('/Script/ControlRig.RigUnit_SetControlFloat', 2140, y0, 'InvSet_EyeOvY')
    b.set_pin(set_ov_y, 'Control', 'Eye_Overflow_Y')
    b.set_pin(set_ov_y, 'FloatValue', f'{_DEFAULT_OVERFLOW_Y:.4f}')
    cur = b.chain(cur, set_ov_y)

    set_cx = b.unit('/Script/ControlRig.RigUnit_SetControlFloat', 2440, y0, 'InvSet_EyeCross')
    b.set_pin(set_cx, 'Control', 'Eye_Cross')
    b.link(inv_cx[0], inv_cx[1], set_cx, 'FloatValue')
    cur = b.chain(cur, set_cx)

    # --- Eyebrows: brow_l = (rot_l, y_l), brow_r = (-rot_r, y_r) ---
    set_bl = b.unit('/Script/ControlRig.RigUnit_SetControlVector2D', 2740, y0, 'InvSet_BrowL')
    b.set_pin(set_bl, 'Control', 'brow_l_ctrl')
    b.link(c['face_brow_rot_l'][0], c['face_brow_rot_l'][1], set_bl, 'Vector.X')
    b.link(c['face_brow_y_l'][0], c['face_brow_y_l'][1], set_bl, 'Vector.Y')
    cur = b.chain(cur, set_bl)

    inv_br_x = b.f_neg(c['face_brow_rot_r'], -580, y0 + 1260, 'InvNegBrowRR')
    set_br = b.unit('/Script/ControlRig.RigUnit_SetControlVector2D', 3040, y0, 'InvSet_BrowR')
    b.set_pin(set_br, 'Control', 'brow_r_ctrl')
    b.link(inv_br_x[0], inv_br_x[1], set_br, 'Vector.X')
    b.link(c['face_brow_y_r'][0], c['face_brow_y_r'][1], set_br, 'Vector.Y')
    cur = b.chain(cur, set_br)

    # --- Mouth: mouth = (mouth_x, mouth_open), mouth_expr = (mouth_wide, mouth_smile) ---
    set_m = b.unit('/Script/ControlRig.RigUnit_SetControlVector2D', 3340, y0, 'InvSet_Mouth')
    b.set_pin(set_m, 'Control', 'mouth_ctrl')
    b.link(c['face_mouth_x'][0], c['face_mouth_x'][1], set_m, 'Vector.X')
    b.link(c['face_mouth_open'][0], c['face_mouth_open'][1], set_m, 'Vector.Y')
    cur = b.chain(cur, set_m)

    set_me = b.unit('/Script/ControlRig.RigUnit_SetControlVector2D', 3640, y0, 'InvSet_MouthExpr')
    b.set_pin(set_me, 'Control', 'mouth_expr_ctrl')
    b.link(c['face_mouth_wide'][0], c['face_mouth_wide'][1], set_me, 'Vector.X')
    b.link(c['face_mouth_smile'][0], c['face_mouth_smile'][1], set_me, 'Vector.Y')
    b.chain(cur, set_me)


def ensure_face_control_rig(destination: str = FACE_RIG_CR_PATH, *, rebuild: bool = False):
    """Ensure shared cross-species facial Control Rig `CR_MC_Face` exists."""
    if unreal is None:
        raise RuntimeError('ensure_face_control_rig requires Unreal Editor')
    lib = unreal.EditorAssetLibrary
    if lib.does_asset_exist(destination) and not rebuild:
        loaded = unreal.load_asset(destination)
        if isinstance(loaded, unreal.ControlRigBlueprint):
            actual = str(lib.get_metadata_tag(loaded, FACE_RIG_VERSION_TAG) or '').strip()
            if actual != FACE_RIG_VERSION:
                _warn_face(
                    f'面部控制绑定 {destination} 版本为 {actual or "未标记"}（当前推荐版本 v{FACE_RIG_VERSION}）。'
                    '未自动覆盖，如需更新请调用 rebuild=True。'
                )
            return loaded

    folder, _ = destination.rsplit('/', 1)
    lib.make_directory(folder)
    if lib.does_asset_exist(destination):
        cr_bp = unreal.load_asset(destination)
    else:
        cr_bp = unreal.ControlRigBlueprintFactory.create_new_control_rig_asset(destination)
    if not isinstance(cr_bp, unreal.ControlRigBlueprint):
        raise RuntimeError('无法创建面部控制绑定 ControlRig: ' + destination)

    aes = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
    aes.close_all_editors_for_asset(cr_bp)

    # Keep notifications enabled during in-place graph rebuild: UE 5.8's `suspend_notifications(True)` skips
    # `URigVMEdGraph` node-cache invalidation on `remove_node`, causing `ResendAllNotifications()` to hit
    # dangling pointers in `URigVMEdGraph::HandleModifiedEvent_Internal` on `suspend_notifications(False)`.
    cr_bp.set_auto_vm_recompile(False)
    try:
        hc = cr_bp.get_hierarchy_controller()
        for elem in list(cr_bp.get_hierarchy().get_all_keys(True)):
            hc.remove_element(elem)

        # Declare the Imported cross-species anchor chain at identity so UE auto-syncs `real_head`
        # to every bound split-head / biped / quadruped / horse / wolf / bee / ghast skeleton.
        parent_key = unreal.RigElementKey()
        for bname in _HEAD_ANCHOR_CHAIN:
            parent_key = hc.add_bone(
                bname, parent_key, unreal.Transform(),
                transform_in_global=False, bone_type=unreal.RigBoneType.IMPORTED,
            )

        # Declare all 15 canonical facial curves so SetCurveValue / GetCurveValue drive every 2D & 3D species.
        for cname in FACE_CURVES:
            hc.add_curve(cname, 0.0)

        ctrl = cr_bp.get_controller()
        existing_nodes = list(cr_bp.get_default_model().get_nodes())
        if existing_nodes:
            ctrl.remove_nodes(existing_nodes)

        builder = _RigBuilder(ctrl)
        _build_construction_event(builder)
        _build_forward_solve(builder)
        _build_backwards_solve(builder)
    finally:
        cr_bp.set_auto_vm_recompile(True)

    # Sync Blueprint.ShapeLibraries -> GeneratedClass CDO (UE 5.8 ControlRigEditor.cpp:3427 only copies
    # ShapeLibraries onto the runtime class when opened in the Control Rig editor; without this step,
    # ControlRigShapeActor spawns with no StaticMeshComponent in Sequencer).
    aes.open_editor_for_assets([cr_bp])
    cr_bp.recompile_vm()
    aes.close_all_editors_for_asset(cr_bp)

    lib.set_metadata_tag(cr_bp, FACE_RIG_VERSION_TAG, FACE_RIG_VERSION)
    if not lib.save_loaded_asset(cr_bp):
        raise RuntimeError('保存面部控制绑定失败: ' + destination)
    return cr_bp


def _resolve_face_component(target, face_component_key: str):
    """Map `describe_actor_capabilities`'s `face_component` key back to the live `SkeletalMeshComponent`."""
    if isinstance(target, unreal.SkeletalMeshComponent):
        return target
    if not isinstance(target, unreal.Actor):
        return None
    body = (
        target.skeletal_mesh_component
        if isinstance(target, unreal.SkeletalMeshActor)
        else target.get_component_by_class(unreal.SkeletalMeshComponent)
    )
    if face_component_key == 'body':
        return body
    for comp in (target.get_components_by_class(unreal.SkeletalMeshComponent) or ()):
        if face_component_key == 'head':
            if (comp != body and comp.get_name() == 'Head'
                    and comp.get_attach_parent() == body
                    and str(comp.get_attach_socket_name()) == 'head'):
                return comp
        elif comp.get_name() == face_component_key:
            return comp
    return body


def _set_channel_default(rig, ch_name: str, value) -> None:
    """Persist an Animation Channel default without adding a timeline keyframe."""
    try:
        for ch in rig.channels(ch_name):
            raw = ch.target if hasattr(ch, 'target') else ch
            raw.set_default(value)
        rig.set(ch_name, value)
    except Exception:
        pass


def find_mounted_face_rig(sequence, comp, *, rig_class: str = FACE_RIG_CR_PATH):
    """Return a `Rig` handle if `CR_MC_Face` (or `rig_class`) is already mounted on `comp` in `sequence`, else None."""
    if unreal is None or sequence is None or comp is None:
        return None
    cr_lib = getattr(unreal, 'ControlRigSequencerLibrary', None)
    eal = getattr(unreal, 'EditorAssetLibrary', None)
    ls_lib = getattr(unreal, 'LevelSequenceEditorBlueprintLibrary', None)
    if (
        cr_lib is None or not hasattr(cr_lib, 'get_control_rigs')
        or eal is None or not hasattr(eal, 'does_asset_exist')
        or ls_lib is None or not hasattr(ls_lib, 'get_bound_objects')
    ):
        return None
    import mineprep.rig as rig_mod
    import mineprep.sequencer_tools as seq_mod

    resolve_cls = getattr(rig_mod, '_resolve_rig_class', None)
    binding_id = getattr(seq_mod, '_binding_id', None)
    if resolve_cls is None or binding_id is None:
        return None

    if isinstance(rig_class, str) and not eal.does_asset_exist(rig_class):
        return None
    cls = resolve_cls(rig_class)
    for proxy in cr_lib.get_control_rigs(sequence):
        rig_inst = proxy.control_rig
        if not rig_inst or not proxy.proxy or rig_inst.get_class() != cls:
            continue
        bound_objs = ls_lib.get_bound_objects(binding_id(proxy.proxy))
        if comp in bound_objs:
            return rig_mod.Rig(comp, rig_class)
    return None


def read_mounted_face_look_x(
    rig,
    target_ticks: list[int],
    start_tick: int,
    end_tick: int,
    *,
    pupil_rest_mode: int = -1,
    eye_bounds: dict[str, float] | None = None,
) -> dict[str, tuple[list[int], list[float]]]:
    """Reconstruct existing `(face_look_x_l, face_look_x_r)` curves on a mounted `CR_MC_Face` over `[start_tick, end_tick]`."""
    if unreal is None or rig is None:
        return {}
    tick_unit = unreal.MovieSceneTimeUnit.TICK_RESOLUTION
    lo_tk, hi_tk = int(start_tick), max(int(start_tick), int(end_tick))
    sample_ticks = set(int(t) for t in target_ticks)
    for ch_name in ('gaze_ctrl.x', 'gaze_ctrl.Eye_Cross'):
        try:
            for ch in rig.channels(ch_name):
                raw = ch.target if hasattr(ch, 'target') else ch
                for key in (raw.get_keys() or ()):
                    tk = int(key.get_time(tick_unit).frame_number.value)
                    if lo_tk <= tk <= hi_tk:
                        sample_ticks.add(tk)
        except Exception:
            pass
    if not sample_ticks:
        sample_ticks.add(lo_tk)
    ordered = sorted(sample_ticks)

    def _safe_resolve(alias: str) -> str | None:
        try:
            return rig._resolve_name(alias)
        except Exception:
            return None

    eb = dict(eye_bounds) if eye_bounds is not None else dict(DEFAULT_EYE_BOUNDS)
    if eye_bounds is None:
        for ch_name, key in (
            ('face_panel_ctrl.Eye_Margin_In', 'margin_in'),
            ('face_panel_ctrl.Eye_Margin_Out', 'margin_out'),
            ('face_panel_ctrl.Pupil_Scale_Shift', 'scale_shift'),
        ):
            full = _safe_resolve(ch_name)
            if full:
                try:
                    eb[key] = float(rig._read(full, unreal.FrameNumber(ordered[0]), tick_unit))
                except Exception:
                    pass

    gaze_full = _safe_resolve('gaze_ctrl')
    cx_full = _safe_resolve('gaze_ctrl.Eye_Cross')
    ov_full = _safe_resolve('gaze_ctrl.Eye_Overflow_X')
    ps_full = _safe_resolve('gaze_ctrl.Pupil_Scale')

    l_vals: list[float] = []
    r_vals: list[float] = []
    for tk in ordered:
        fn = unreal.FrameNumber(tk)
        try:
            gx = float(rig._read(gaze_full, fn, tick_unit).x) if gaze_full else 0.0
        except Exception:
            gx = 0.0
        try:
            cx = float(rig._read(cx_full, fn, tick_unit)) if cx_full else 0.0
        except Exception:
            cx = 0.0
        try:
            ov = float(rig._read(ov_full, fn, tick_unit)) if ov_full else _DEFAULT_OVERFLOW_X
        except Exception:
            ov = _DEFAULT_OVERFLOW_X
        try:
            ps = float(rig._read(ps_full, fn, tick_unit)) if ps_full else 0.0
        except Exception:
            ps = 0.0
        lx_l, lx_r = _forward_clamp_look_x(gx, cx, pupil_rest_mode, ov, ps, eb)
        l_vals.append(lx_l)
        r_vals.append(lx_r)
    return {
        'face_look_x_l': (ordered, l_vals),
        'face_look_x_r': (ordered, r_vals),
    }


def add_face_rig(
    target,
    *,
    rig_class: str = FACE_RIG_CR_PATH,
    layered: bool = False,
    priority: int | None = None,
    auto_visibility: bool = True,
):
    """Validate facial capabilities and attach `CR_MC_Face` to an Actor or SkeletalMeshComponent.

    Designed for both Blueprint buttons (`mineprep.add_face_rig(this)`) and Python scripting:
    - Accepts an entire mob `Actor` (auto-picks `Head` on split-head mobs or the body SKM on unified mobs)
      or a specific `SkeletalMeshComponent`.
    - Inspects `Mineprep.Face*` asset metadata first, falling back to MorphTarget / material / Skeleton scanning.
    - Emits a clean `mineprep.warn(...)` and returns `None` if no Level Sequence is open or the target does
      not support standard `face_*` facial curves.
    - Defaults to `layered=False` (absolute WYSIWYG facial controls, zero additive offset/double-counting,
      while leaving all skeletal/FK body bones untouched!) and assigns a lower `priority` number than
      existing rigs on the same component (in UE 5.8 `ControlRigLayerInstanceProxy`, smaller priority
      evaluates later / on top of larger priority, e.g. `99` over UE's default `100`).
    - Auto-configures `Pupil_Rest_Mode` (`-1` inner / `0` center / `+1` outer) and auto-hides unsupported
      brow/mouth controls on freshly attached tracks.
    """
    if unreal is None:
        raise RuntimeError('add_face_rig requires Unreal Editor')
    from mineprep.rig import Rig, _resolve_rig_class
    from mineprep.sequencer_tools import _binding_id, _unwrap_target

    obj = _unwrap_target(target)
    if obj is None or not isinstance(obj, (unreal.Actor, unreal.SkeletalMeshComponent)):
        _warn_face('添加表情绑定失败：target 须为骨骼生物 Actor 或 SkeletalMeshComponent。')
        return None

    label = obj.get_actor_label() if isinstance(obj, unreal.Actor) else obj.get_name()
    sequence = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    if sequence is None:
        _warn_face(f'无法为 {label} 添加表情绑定：当前未打开 Level Sequence，请先在 Sequencer 中打开序列。')
        return None

    caps = describe_actor_capabilities(obj)
    if not caps['has_face_component']:
        _warn_face(f'{label} 当前不支持表情绑定（未检测到 2D/3D 表情元数据、表情 MorphTarget 或表情材质参数）。')
        return None

    curves = set(caps['curves'])
    if not (curves & _FACE_CURVE_SET):
        _warn_face(f'{label} 未检测到标准 face_* 表情曲线，无法挂载表情绑定。')
        return None

    comp = _resolve_face_component(obj, caps['face_component'])
    if comp is None:
        _warn_face(f'{label} 找不到可挂载表情绑定的骨骼网格体组件（{caps["face_component"]}）。')
        return None

    if rig_class == FACE_RIG_CR_PATH:
        ensure_face_control_rig(FACE_RIG_CR_PATH)

    cls = _resolve_rig_class(rig_class)
    cr_lib = unreal.ControlRigSequencerLibrary
    existing_same_comp = []
    already_attached = False
    for proxy in cr_lib.get_control_rigs(sequence):
        rig_inst = proxy.control_rig
        if not rig_inst or not proxy.proxy:
            continue
        bound_objs = unreal.LevelSequenceEditorBlueprintLibrary.get_bound_objects(_binding_id(proxy.proxy))
        if comp not in bound_objs:
            continue
        if rig_inst.get_class() == cls:
            already_attached = True
        else:
            existing_same_comp.append(proxy.track)

    rig = Rig(comp, rig_class, layered=layered)

    if priority is not None:
        rig.priority = int(priority)
    elif not already_attached:
        # In UE 5.8 ControlRigLayerInstanceProxy::SortControlRigNodes, smaller PriorityOrder evaluates LAST (on top).
        other_min = min((int(cr_lib.get_control_rig_priority_order(t)) for t in existing_same_comp), default=100)
        rig.priority = min(99, other_min - 1)

    if not already_attached and rig_class == FACE_RIG_CR_PATH:
        pupil_mode = int(caps.get('pupil_rest_mode', -1))
        eye_bounds = caps.get('eye_bounds') or DEFAULT_EYE_BOUNDS
        _set_channel_default(rig, 'face_panel_ctrl.Pupil_Rest_Mode', pupil_mode)
        _set_channel_default(rig, 'face_panel_ctrl.Eye_Margin_In', float(eye_bounds.get('margin_in', DEFAULT_EYE_BOUNDS['margin_in'])))
        _set_channel_default(rig, 'face_panel_ctrl.Eye_Margin_Out', float(eye_bounds.get('margin_out', DEFAULT_EYE_BOUNDS['margin_out'])))
        _set_channel_default(rig, 'face_panel_ctrl.Pupil_Scale_Shift', float(eye_bounds.get('scale_shift', DEFAULT_EYE_BOUNDS['scale_shift'])))
        _set_channel_default(rig, 'gaze_ctrl.Eye_Overflow_X', _DEFAULT_OVERFLOW_X)
        _set_channel_default(rig, 'gaze_ctrl.Eye_Overflow_Y', _DEFAULT_OVERFLOW_Y)
        if auto_visibility:
            has_brows = any(c.startswith('face_brow_') for c in curves)
            has_mouth = any(c.startswith('face_mouth_') for c in curves)
            _set_channel_default(rig, 'face_panel_ctrl.Show_Brows', has_brows)
            _set_channel_default(rig, 'face_panel_ctrl.Show_Mouth', has_mouth)

    return rig


def _sample_underlying_face_curves(
    sequence,
    comp,
    ordered_curves: tuple[str, ...],
    first: int,
    last: int,
    step: int,
    existing_rig=None,
) -> tuple[list[int], dict[str, list[float]]]:
    """Synchronously evaluate underlying `face_*` curves over `[first, last]` via SequencerTools.

    Uses the exact same native C++ Sequencer evaluation pipeline as `BakeToControlRig` (handling
    SkeletalAnimationTrack crossfades, play rates, FKControlRig curves, and 2D/3D drivers with zero
    1-frame staleness), while NEVER disabling the component's body animation tracks.
    """
    import uuid
    from mineprep import sequencer_tools as mcseq
    from mineprep.utils import world

    skel = comp.get_skeletal_mesh_asset().skeleton
    binding = mcseq._ensure_binding(sequence, comp)
    orig_start = int(sequence.get_playback_start())
    orig_end = int(sequence.get_playback_end())
    bounds_changed = (first, last) != (orig_start, orig_end)

    saved_section_states: list[tuple[object, bool]] = []
    temp_name = f'_MineprepFaceBakeTmp_{uuid.uuid4().hex[:8]}'
    temp_folder = '/Game/Temp'
    unreal.EditorAssetLibrary.make_directory(temp_folder)
    factory = unreal.AnimSequenceFactory()
    factory.target_skeleton = skel
    temp_anim = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        temp_name, temp_folder, unreal.AnimSequence, factory,
    )
    if temp_anim is None:
        raise RuntimeError('无法创建临时 AnimSequence 用于采样表情曲线')

    try:
        if existing_rig is not None:
            for sec in existing_rig.sections():
                saved_section_states.append((sec, bool(sec.is_active())))
                if sec.is_active():
                    sec.set_is_active(False)
        if bounds_changed:
            if first >= sequence.get_playback_end():
                sequence.set_playback_end(last)
                sequence.set_playback_start(first)
            else:
                sequence.set_playback_start(first)
                sequence.set_playback_end(last)
            mcseq._refresh_sequencer()

        opts = unreal.AnimSeqExportOption()
        opts.export_transforms = False
        opts.export_morph_targets = True
        opts.export_attribute_curves = True
        opts.export_material_curves = True
        opts.record_in_world_space = False

        ok = unreal.SequencerTools.export_anim_sequence(world(), sequence, temp_anim, opts, binding, False)
        if not ok:
            raise RuntimeError('Sequencer 底层表情曲线采样失败')

        disp = sequence.get_display_rate()
        fps = float(disp.numerator) / float(max(1, disp.denominator))
        frame_dt = 1.0 / fps
        total_keys = max(1, int(unreal.AnimationLibrary.get_num_keys(temp_anim) or 0))
        rec_dt = frame_dt
        try:
            dm = temp_anim.get_editor_property('data_model')
            if dm is not None:
                fr_rate = dm.get_frame_rate()
                if fr_rate.numerator > 0 and fr_rate.denominator > 0:
                    rec_dt = float(fr_rate.denominator) / float(fr_rate.numerator)
        except Exception:
            pass
        if abs(rec_dt - frame_dt) <= 1e-6:
            n_disp = total_keys
        else:
            max_t = max(0.0, (total_keys - 1) * rec_dt)
            n_disp = max(1, int(round(max_t / frame_dt)) + 1)

        indices = list(range(0, n_disp, step))
        if indices[-1] != n_disp - 1:
            indices.append(n_disp - 1)
        frames = [first + i for i in indices]
        target_times = [i * frame_dt for i in indices]
        sample_dt = max(frame_dt, rec_dt)

        samples: dict[str, list[float]] = {}
        for cname in ordered_curves:
            if unreal.AnimationLibrary.does_curve_exist(temp_anim, cname, unreal.RawCurveTrackTypes.RCT_FLOAT):
                raw_times, raw_vals = unreal.AnimationLibrary.get_float_keys(temp_anim, cname)
                samples[cname] = _sample_recorded_float_curve(raw_times, raw_vals, target_times, sample_dt)
            else:
                samples[cname] = [0.0] * len(indices)
        return frames, samples
    finally:
        if bounds_changed:
            if orig_start >= sequence.get_playback_end():
                sequence.set_playback_end(orig_end)
                sequence.set_playback_start(orig_start)
            else:
                sequence.set_playback_start(orig_start)
                sequence.set_playback_end(orig_end)
        for sec, was_active in saved_section_states:
            if bool(sec.is_active()) != was_active:
                sec.set_is_active(was_active)
        unreal.EditorAssetLibrary.delete_loaded_asset(temp_anim)
        mcseq._refresh_sequencer()


def bake_face_to_rig(
    target,
    *,
    start=None,
    end=None,
    step: int = 1,
    rig_class: str = FACE_RIG_CR_PATH,
    layered: bool = False,
    priority: int | None = None,
    interp: str = 'linear',
):
    """Bake underlying `face_*` curves into `CR_MC_Face` WITHOUT disabling the body's animation tracks.

    Unlike UE's `BakeToControlRig` (which calls `DisableTrack` on the component's `SkeletalAnimationTrack`
    and therefore freezes body motion on unified mobs such as Horse/Wolf/Pig), this function samples the
    live underlying facial curves across `[start, end]`, converts them cleanly via the continuous inverse
    mapping, and writes them onto `CR_MC_Face` (`layered=False` so baked keys override cleanly without
    additive double-counting) while leaving all skeletal/FK body animation active.
    """
    if unreal is None:
        raise RuntimeError('bake_face_to_rig requires Unreal Editor')
    from mineprep import sequencer_tools as mcseq
    from mineprep.sequencer_tools import _resolve_frame, _unwrap_target

    step = int(step)
    if step < 1:
        raise ValueError('step 须为 >= 1 的整数帧步长')

    obj = _unwrap_target(target)
    if obj is None or not isinstance(obj, (unreal.Actor, unreal.SkeletalMeshComponent)):
        _warn_face('烘焙表情到控制绑定失败：target 须为骨骼生物 Actor 或 SkeletalMeshComponent。')
        return None

    label = obj.get_actor_label() if isinstance(obj, unreal.Actor) else obj.get_name()
    seq_lib = unreal.LevelSequenceEditorBlueprintLibrary
    sequence = seq_lib.get_current_level_sequence()
    if sequence is None:
        _warn_face(f'无法为 {label} 烘焙表情绑定：当前未打开 Level Sequence，请先在 Sequencer 中打开序列。')
        return None

    caps = describe_actor_capabilities(obj)
    if not caps['has_face_component']:
        _warn_face(f'{label} 当前不支持表情绑定（未检测到 2D/3D 表情能力）。')
        return None
    supported = set(caps['curves']) & _FACE_CURVE_SET
    if not supported:
        _warn_face(f'{label} 未检测到标准 face_* 表情曲线，无法烘焙表情绑定。')
        return None

    comp = _resolve_face_component(obj, caps['face_component'])
    if comp is None:
        _warn_face(f'{label} 找不到可挂载表情绑定的骨骼网格体组件（{caps["face_component"]}）。')
        return None

    first = int(sequence.get_playback_start()) if start is None else _resolve_frame(start, sequence)
    last = int(sequence.get_playback_end()) if end is None else _resolve_frame(end, sequence)
    if last <= first:
        raise ValueError('烘焙结束帧必须晚于起始帧')

    existing_rig = find_mounted_face_rig(sequence, comp, rig_class=rig_class)
    ordered_curves = tuple(c for c in FACE_CURVES if c in supported)
    frames, samples = _sample_underlying_face_curves(
        sequence, comp, ordered_curves, first, last, step, existing_rig=existing_rig,
    )

    pupil_mode = int(caps.get('pupil_rest_mode', -1))
    eye_bounds = caps.get('eye_bounds') or DEFAULT_EYE_BOUNDS
    ctrl_series, need_ov_x = curves_to_face_rig_controls(
        samples, pupil_rest_mode=pupil_mode, supported_curves=supported,
    )

    rig = add_face_rig(obj, rig_class=rig_class, layered=layered, priority=priority)
    if rig is None:
        return None

    if rig_class == FACE_RIG_CR_PATH:
        _set_channel_default(rig, 'face_panel_ctrl.Pupil_Rest_Mode', pupil_mode)
        _set_channel_default(rig, 'face_panel_ctrl.Eye_Margin_In', float(eye_bounds.get('margin_in', DEFAULT_EYE_BOUNDS['margin_in'])))
        _set_channel_default(rig, 'face_panel_ctrl.Eye_Margin_Out', float(eye_bounds.get('margin_out', DEFAULT_EYE_BOUNDS['margin_out'])))
        _set_channel_default(rig, 'face_panel_ctrl.Pupil_Scale_Shift', float(eye_bounds.get('scale_shift', DEFAULT_EYE_BOUNDS['scale_shift'])))
        if need_ov_x > _DEFAULT_OVERFLOW_X + 1e-4:
            _set_channel_default(rig, 'gaze_ctrl.Eye_Overflow_X', round(min(1.0, need_ov_x), 4))

    if ctrl_series:
        ticks = [rig._time_tick(f) for f in frames]
        batches = {name: (ticks, vals) for name, vals in ctrl_series.items()}
        span_end = rig._key_tick(unreal.FrameNumber(last + 1))
        rig._key_batches(
            batches,
            interp,
            replace_span=slice(ticks[0], span_end),
            time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION,
        )

    mcseq._refresh_sequencer()
    return rig
