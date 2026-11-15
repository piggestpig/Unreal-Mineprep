from __future__ import annotations

import math
import re

BIPED_LIMB_BONES = (
    'body',
    'head',
    'left_arm',
    'right_arm',
    'left_leg',
    'right_leg',
)

BIPED_PROXY_BONES = ('root', 'pelvis')
BIPED_REQUIRED_BONES = BIPED_PROXY_BONES + BIPED_LIMB_BONES

HEAD_PRIMARY_BONES = ('head',)

_JOINT_LIMITS = (
    # (child, parent, swing1_deg, swing2_deg, twist_deg)
    ('body', 'pelvis', 35.0, 35.0, 25.0),
    ('left_leg', 'pelvis', 60.0, 35.0, 25.0),
    ('right_leg', 'pelvis', 60.0, 35.0, 25.0),
    ('head', 'body', 40.0, 35.0, 45.0),
    ('left_arm', 'body', 75.0, 65.0, 40.0),
    ('right_arm', 'body', 75.0, 65.0, 40.0),
)

_MIN_BOX_SIZE_CM = 1.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _mat4_identity() -> list[list[float]]:
    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _mat4_mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [
            a[r][0] * b[0][c] + a[r][1] * b[1][c] + a[r][2] * b[2][c] + a[r][3] * b[3][c]
            for c in range(4)
        ]
        for r in range(4)
    ]


def _mat4_transform_point(m: list[list[float]], p: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = p
    return (
        m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
        m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
        m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3],
    )


def _mat4_transform_vector(m: list[list[float]], v: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = v
    return (
        m[0][0] * x + m[0][1] * y + m[0][2] * z,
        m[1][0] * x + m[1][1] * y + m[1][2] * z,
        m[2][0] * x + m[2][1] * y + m[2][2] * z,
    )


def _quat_to_rot3(qx: float, qy: float, qz: float, qw: float) -> list[list[float]]:
    norm = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    if norm <= 1e-12:
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    x, y, z, w = qx / norm, qy / norm, qz / norm, qw / norm
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return [
        [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
        [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
        [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
    ]


def _ue_transform_to_mat4(transform) -> list[list[float]]:
    """Build column-vector local-to-parent 4x4 matrix M = T * R * S."""
    t = transform.translation
    q = transform.rotation
    s = transform.scale3d
    rot = _quat_to_rot3(float(q.x), float(q.y), float(q.z), float(q.w))
    sx, sy, sz = float(s.x), float(s.y), float(s.z)
    return [
        [rot[0][0] * sx, rot[0][1] * sy, rot[0][2] * sz, float(t.x)],
        [rot[1][0] * sx, rot[1][1] * sy, rot[1][2] * sz, float(t.y)],
        [rot[2][0] * sx, rot[2][1] * sy, rot[2][2] * sz, float(t.z)],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _mat4_inverse_affine(m: list[list[float]]) -> list[list[float]]:
    """Invert a 4x4 affine matrix whose last row is [0, 0, 0, 1]."""
    a00, a01, a02, tx = m[0]
    a10, a11, a12, ty = m[1]
    a20, a21, a22, tz = m[2]

    c00 = a11 * a22 - a12 * a21
    c01 = -(a10 * a22 - a12 * a20)
    c02 = a10 * a21 - a11 * a20
    det = a00 * c00 + a01 * c01 + a02 * c02
    if abs(det) <= 1e-12:
        raise ValueError('Singular bone transform matrix cannot be inverted')
    inv_det = 1.0 / det

    r00 = c00 * inv_det
    r01 = (-(a01 * a22 - a02 * a21)) * inv_det
    r02 = (a01 * a12 - a02 * a11) * inv_det

    r10 = c01 * inv_det
    r11 = (a00 * a22 - a02 * a20) * inv_det
    r12 = (-(a00 * a12 - a02 * a10)) * inv_det

    r20 = c02 * inv_det
    r21 = (-(a00 * a21 - a01 * a20)) * inv_det
    r22 = (a00 * a11 - a01 * a10) * inv_det

    itx = -(r00 * tx + r01 * ty + r02 * tz)
    ity = -(r10 * tx + r11 * ty + r12 * tz)
    itz = -(r20 * tx + r21 * ty + r22 * tz)
    return [
        [r00, r01, r02, itx],
        [r10, r11, r12, ity],
        [r20, r21, r22, itz],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _compute_component_matrices(bounds_records: list[dict]) -> dict[str, list[list[float]]]:
    """Reconstruct component-space 4x4 transform per bone from parent-relative poses."""
    by_name = {rec['bone_name']: rec for rec in bounds_records}
    cache: dict[str, list[list[float]]] = {}

    def resolve(name: str, visiting: set[str]) -> list[list[float]]:
        if name in cache:
            return cache[name]
        if name in visiting:
            raise ValueError(f'Cycle in bone hierarchy at {name}')
        rec = by_name[name]
        parent = rec.get('parent_name')
        local_m = rec['local_mat4']
        if parent and parent in by_name:
            visiting.add(name)
            parent_m = resolve(parent, visiting)
            visiting.remove(name)
            comp_m = _mat4_mul(parent_m, local_m)
        else:
            comp_m = local_m
        cache[name] = comp_m
        return comp_m

    for name in by_name:
        resolve(name, set())
    return cache


def _box_corners(bmin: list[float], bmax: list[float]):
    for x in (bmin[0], bmax[0]):
        for y in (bmin[1], bmax[1]):
            for z in (bmin[2], bmax[2]):
                yield (x, y, z)


def _local_box_to_component_aabb(bmin: list[float], bmax: list[float], comp_m: list[list[float]]):
    cmin = [float('inf'), float('inf'), float('inf')]
    cmax = [float('-inf'), float('-inf'), float('-inf')]
    for corner in _box_corners(bmin, bmax):
        wx, wy, wz = _mat4_transform_point(comp_m, corner)
        cmin[0] = min(cmin[0], wx)
        cmin[1] = min(cmin[1], wy)
        cmin[2] = min(cmin[2], wz)
        cmax[0] = max(cmax[0], wx)
        cmax[1] = max(cmax[1], wy)
        cmax[2] = max(cmax[2], wz)
    return cmin, cmax


def _detect_primary_axis(bmin: list[float], bmax: list[float]) -> int:
    ext = [bmax[i] - bmin[i] for i in range(3)]
    center = [0.5 * (bmin[i] + bmax[i]) for i in range(3)]
    return max(range(3), key=lambda i: (round(ext[i], 2), abs(center[i])))


def _shrink_initial_limb_box(bone_name: str, bmin: list[float], bmax: list[float],
                             comp_m: list[list[float]], inv_comp_m: list[list[float]],
                             torso_comp_center: list[float],
                             char_height: float) -> tuple[list[float], list[float]]:
    """Compute shrunk local AABB [min, max] preserving foot ground reach and joint clearance."""
    lmin = list(bmin)
    lmax = list(bmax)
    ext = [max(lmax[i] - lmin[i], _MIN_BOX_SIZE_CM) for i in range(3)]

    if bone_name == 'body':
        # Slightly narrower laterally than vertically so shoulders/hips clear neighboring limbs
        ux, uy, uz = _mat4_transform_vector(inv_comp_m, (0.0, 0.0, 1.0))
        up_axis = max(range(3), key=lambda k: abs((ux, uy, uz)[k]))
        for i in range(3):
            scale = 0.90 if i == up_axis else 0.85
            half_inset = 0.5 * (1.0 - scale) * ext[i]
            lmin[i] += half_inset
            lmax[i] -= half_inset
        return _clamp_min_box_extents(lmin, lmax, bmin, bmax, min_frac=0.35)

    if bone_name == 'arms':
        # Crossed/folded illager arms across upper chest: keep clean chest protrusion without over-bulging.
        for i in range(3):
            half_inset = 0.5 * 0.10 * ext[i]
            lmin[i] += half_inset
            lmax[i] -= half_inset
        return _clamp_min_box_extents(lmin, lmax, bmin, bmax, min_frac=0.50)

    if bone_name == 'head':
        # Pull back neck (torso-facing) face more than top; shrink lateral faces slightly.
        ux, uy, uz = _mat4_transform_vector(inv_comp_m, (0.0, 0.0, 1.0))
        up_axis = max(range(3), key=lambda k: abs((ux, uy, uz)[k]))
        for i in range(3):
            if i == up_axis:
                continue
            half_inset = 0.5 * 0.10 * ext[i]
            lmin[i] += half_inset
            lmax[i] -= half_inset

        local_center = [0.5 * (lmin[i] + lmax[i]) for i in range(3)]
        c_low = list(local_center)
        c_low[up_axis] = lmin[up_axis]
        c_high = list(local_center)
        c_high[up_axis] = lmax[up_axis]
        w_low = _mat4_transform_point(comp_m, tuple(c_low))
        w_high = _mat4_transform_point(comp_m, tuple(c_high))
        neck_is_min = w_low[2] <= w_high[2]
        if neck_is_min:
            lmin[up_axis] += 0.10 * ext[up_axis]
            lmax[up_axis] -= 0.04 * ext[up_axis]
        else:
            lmax[up_axis] -= 0.10 * ext[up_axis]
            lmin[up_axis] += 0.04 * ext[up_axis]
        return _clamp_min_box_extents(lmin, lmax, bmin, bmax, min_frac=0.35)

    # Arms & legs: identify primary limb axis and proximal (joint) vs distal end.
    p_axis = _detect_primary_axis(lmin, lmax)
    cross_shrink = 0.20  # keep ~80% cross-section for limb bending room
    for i in range(3):
        if i == p_axis:
            continue
        half_inset = 0.5 * cross_shrink * ext[i]
        lmin[i] += half_inset
        lmax[i] -= half_inset

    is_leg = bone_name in ('left_leg', 'right_leg')
    # Determine which face along p_axis is proximal (pivot side vs distal hand/foot).
    if lmin[p_axis] < -1.0 and lmax[p_axis] > 1.0:
        # Mesh straddles pivot along p_axis (e.g., iron_golem legs rising above hip pivot):
        # Measure which face center is closer to the torso center in component space.
        local_center = [0.5 * (lmin[i] + lmax[i]) for i in range(3)]
        c_low = list(local_center)
        c_low[p_axis] = lmin[p_axis]
        c_high = list(local_center)
        c_high[p_axis] = lmax[p_axis]
        w_low = _mat4_transform_point(comp_m, tuple(c_low))
        w_high = _mat4_transform_point(comp_m, tuple(c_high))
        d_low = sum((w_low[i] - torso_comp_center[i]) ** 2 for i in range(3))
        d_high = sum((w_high[i] - torso_comp_center[i]) ** 2 for i in range(3))
        proximal_is_min = d_low < d_high
    else:
        proximal_is_min = abs(lmin[p_axis]) <= abs(lmax[p_axis])

    prox_frac = 0.14
    dist_frac = 0.015 if is_leg else 0.05
    if proximal_is_min:
        lmin[p_axis] += prox_frac * ext[p_axis]
        lmax[p_axis] -= dist_frac * ext[p_axis]
        # Clamp overshoot behind pivot (when leg/arm protrudes past pivot toward parent)
        if lmin[p_axis] < 0.0 < lmax[p_axis] and abs(lmin[p_axis]) < abs(lmax[p_axis]):
            lmin[p_axis] = max(lmin[p_axis], min(0.08 * char_height, 0.04 * ext[p_axis]))
    else:
        lmax[p_axis] -= prox_frac * ext[p_axis]
        lmin[p_axis] += dist_frac * ext[p_axis]
        if lmin[p_axis] < 0.0 < lmax[p_axis] and abs(lmax[p_axis]) < abs(lmin[p_axis]):
            lmax[p_axis] = min(lmax[p_axis], -min(0.08 * char_height, 0.04 * ext[p_axis]))

    return _clamp_min_box_extents(lmin, lmax, bmin, bmax, min_frac=0.30)


def _clamp_min_box_extents(lmin: list[float], lmax: list[float],
                           orig_min: list[float], orig_max: list[float],
                           *, min_frac: float) -> tuple[list[float], list[float]]:
    out_min = list(lmin)
    out_max = list(lmax)
    for i in range(3):
        min_len = max(_MIN_BOX_SIZE_CM, min_frac * (orig_max[i] - orig_min[i]))
        if out_max[i] - out_min[i] < min_len:
            mid = 0.5 * (out_min[i] + out_max[i])
            out_min[i] = mid - 0.5 * min_len
            out_max[i] = mid + 0.5 * min_len
    return out_min, out_max


def _trim_box_along_component_axis(bmin: list[float], bmax: list[float],
                                   comp_m: list[list[float]], inv_comp_m: list[list[float]],
                                   comp_axis: int, delta: float, trim_min_face: bool,
                                   min_local_ext: list[float]) -> float:
    """Shift the component-min or component-max face inward by up to `delta` cm.

    Returns actual separation gained in component space along `comp_axis`.
    """
    if delta <= 0.0:
        return 0.0
    # Express component axis unit vector in bone local space.
    dir_comp = [0.0, 0.0, 0.0]
    dir_comp[comp_axis] = 1.0 if trim_min_face else -1.0
    lx, ly, lz = _mat4_transform_vector(inv_comp_m, tuple(dir_comp))
    local_dir = (lx, ly, lz)
    dom_axis = max(range(3), key=lambda k: abs(local_dir[k]))
    proj = local_dir[dom_axis]
    if abs(proj) <= 1e-6:
        return 0.0

    # Local unit step per unit shift along component axis direction.
    avail = (bmax[dom_axis] - bmin[dom_axis]) - min_local_ext[dom_axis]
    if avail <= 0.0:
        return 0.0

    cmin_before, cmax_before = _local_box_to_component_aabb(bmin, bmax, comp_m)
    before_edge = cmin_before[comp_axis] if trim_min_face else cmax_before[comp_axis]

    local_step = delta / abs(proj)
    applied_local = min(avail, local_step)
    if proj > 0.0:
        # Positive movement along dom_axis shrinks from bmin[dom_axis]
        bmin[dom_axis] += applied_local
    else:
        bmax[dom_axis] -= applied_local

    cmin_after, cmax_after = _local_box_to_component_aabb(bmin, bmax, comp_m)
    after_edge = cmin_after[comp_axis] if trim_min_face else cmax_after[comp_axis]
    gained = (after_edge - before_edge) if trim_min_face else (before_edge - after_edge)
    return max(0.0, gained)


def _resolve_component_overlaps(limb_boxes: dict[str, tuple[list[float], list[float]]],
                                orig_bounds: dict[str, tuple[list[float], list[float]]],
                                comp_mats: dict[str, list[list[float]]],
                                inv_comp_mats: dict[str, list[list[float]]],
                                target_gap: float,
                                *,
                                min_frac: float = 0.30,
                                max_trim_ratio: float = 0.85,
                                trim_against: str = 'sum',
                                trim_resistance: dict[str, float] | None = None,
                                skip_pairs: set[tuple[str, str]] | None = None,
                                require_resolvable: bool = False) -> None:
    """Resolve remaining rest-pose component-space overlaps/near-touches across colliding limbs."""
    names = list(limb_boxes.keys())
    min_local_ext = {
        name: [
            max(_MIN_BOX_SIZE_CM, min_frac * (orig_bounds[name][1][i] - orig_bounds[name][0][i]))
            for i in range(3)
        ]
        for name in names
    }
    if trim_resistance is None:
        # Higher weight => avoid trimming this bone when paired with an appendage (e.g. body vs head/arms).
        trim_resistance = {
            'body': 1.4,
            'head': 1.15,
            'arms': 1.0,
            'left_arm': 0.85,
            'right_arm': 0.85,
            'left_leg': 0.90,
            'right_leg': 0.90,
        }
    normalized_skip = {tuple(sorted(pair)) for pair in (skip_pairs or ())}

    for _pass in range(10):
        changed = False
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                if tuple(sorted((a, b))) in normalized_skip:
                    continue
                amin, amax = limb_boxes[a]
                bmin, bmax = limb_boxes[b]
                acmin, acmax = _local_box_to_component_aabb(amin, amax, comp_mats[a])
                bcmin, bcmax = _local_box_to_component_aabb(bmin, bmax, comp_mats[b])

                # Check if at least one axis already has >= target_gap separation
                clearances = [
                    max(bcmin[ax] - acmax[ax], acmin[ax] - bcmax[ax])
                    for ax in range(3)
                ]
                if max(clearances) >= target_gap - 1e-3:
                    continue

                # Pick the axis that requires the least trimming to reach `target_gap`
                best_axis = None
                best_needed = float('inf')
                for ax in range(3):
                    # Distance needed to push acmax below bcmin - gap OR bcmax below acmin - gap
                    pen_ab = (acmax[ax] + target_gap) - bcmin[ax]
                    pen_ba = (bcmax[ax] + target_gap) - acmin[ax]
                    needed = min(pen_ab, pen_ba)
                    # Only trim along an axis if each box isn't thicker than trivial
                    a_span = max(acmax[ax] - acmin[ax], 1e-3)
                    b_span = max(bcmax[ax] - bcmin[ax], 1e-3)
                    ref_span = min(a_span, b_span) if trim_against == 'min' else (a_span + b_span)
                    if needed >= max_trim_ratio * ref_span or needed >= best_needed:
                        continue
                    if require_resolvable:
                        # Avoid carving angled/crowded AABBs when minimum-extent clamps prevent reaching target_gap.
                        dir_comp = [1.0 if k == ax else 0.0 for k in range(3)]
                        la = _mat4_transform_vector(inv_comp_mats[a], tuple(dir_comp))
                        lb = _mat4_transform_vector(inv_comp_mats[b], tuple(dir_comp))
                        dom_a = max(range(3), key=lambda k: abs(la[k]))
                        dom_b = max(range(3), key=lambda k: abs(lb[k]))
                        slack_a = max(0.0, (amax[dom_a] - amin[dom_a]) - min_local_ext[a][dom_a]) * abs(la[dom_a])
                        slack_b = max(0.0, (bmax[dom_b] - bmin[dom_b]) - min_local_ext[b][dom_b]) * abs(lb[dom_b])
                        if slack_a + slack_b < 0.75 * needed:
                            continue
                    best_needed = needed
                    best_axis = ax

                if best_axis is None or best_needed <= 0.0:
                    continue

                # Decide direction: A below B vs B below A along best_axis
                a_mid = 0.5 * (acmin[best_axis] + acmax[best_axis])
                b_mid = 0.5 * (bcmin[best_axis] + bcmax[best_axis])
                ra = trim_resistance.get(a, 1.0)
                rb = trim_resistance.get(b, 1.0)
                # Share proportional to inverse resistance
                frac_a = (1.0 / ra) / ((1.0 / ra) + (1.0 / rb))
                delta_a = best_needed * frac_a
                delta_b = best_needed - delta_a

                if a_mid <= b_mid:
                    # Trim max of A and min of B along best_axis
                    gained_a = _trim_box_along_component_axis(
                        amin, amax, comp_mats[a], inv_comp_mats[a],
                        best_axis, delta_a, False, min_local_ext[a]
                    )
                    rem = max(0.0, best_needed - gained_a)
                    gained_b = _trim_box_along_component_axis(
                        bmin, bmax, comp_mats[b], inv_comp_mats[b],
                        best_axis, max(delta_b, rem), True, min_local_ext[b]
                    )
                    if gained_a + gained_b < best_needed - 1e-2:
                        _trim_box_along_component_axis(
                            amin, amax, comp_mats[a], inv_comp_mats[a],
                            best_axis, best_needed - gained_a - gained_b, False, min_local_ext[a]
                        )
                else:
                    gained_b = _trim_box_along_component_axis(
                        bmin, bmax, comp_mats[b], inv_comp_mats[b],
                        best_axis, delta_b, False, min_local_ext[b]
                    )
                    rem = max(0.0, best_needed - gained_b)
                    gained_a = _trim_box_along_component_axis(
                        amin, amax, comp_mats[a], inv_comp_mats[a],
                        best_axis, max(delta_a, rem), True, min_local_ext[a]
                    )
                    if gained_a + gained_b < best_needed - 1e-2:
                        _trim_box_along_component_axis(
                            bmin, bmax, comp_mats[b], inv_comp_mats[b],
                            best_axis, best_needed - gained_a - gained_b, False, min_local_ext[b]
                        )
                changed = True
        if not changed:
            break


def _collect_bone_subtree(by_name: dict[str, dict], root_bone: str) -> list[str]:
    """Return `root_bone` and all descendant bone names present in `by_name`."""
    if root_bone not in by_name:
        return []
    children_map: dict[str, list[str]] = {}
    for name, rec in by_name.items():
        parent = rec.get('parent_name')
        if parent:
            children_map.setdefault(parent, []).append(name)
    subtree: list[str] = []
    seen = {root_bone}
    stack = [root_bone]
    while stack:
        cur = stack.pop()
        subtree.append(cur)
        for child in children_map.get(cur, ()):
            if child not in seen:
                seen.add(child)
                stack.append(child)
    return subtree


def _merge_folded_arms_bounds(by_name: dict[str, dict], comp_mats: dict[str, list[list[float]]],
                              inv_comp_mats: dict[str, list[list[float]]]) -> tuple[list[float], list[float]]:
    """Return merged local AABB of `arms` and any bound descendants (e.g. `left_shoulder`, `right_hand`)."""
    umin = [float('inf'), float('inf'), float('inf')]
    umax = [float('-inf'), float('-inf'), float('-inf')]
    found = False
    for name in _collect_bone_subtree(by_name, 'arms'):
        rec = by_name[name]
        if not rec.get('has_bounds'):
            continue
        found = True
        if name == 'arms':
            pts = _box_corners(rec['local_min'], rec['local_max'])
        else:
            xform = _mat4_mul(inv_comp_mats['arms'], comp_mats[name])
            pts = [_mat4_transform_point(xform, c) for c in _box_corners(rec['local_min'], rec['local_max'])]
        for lx, ly, lz in pts:
            umin[0] = min(umin[0], lx)
            umin[1] = min(umin[1], ly)
            umin[2] = min(umin[2], lz)
            umax[0] = max(umax[0], lx)
            umax[1] = max(umax[1], ly)
            umax[2] = max(umax[2], lz)
    if not found:
        raise ValueError("Missing vertex bounds for 'arms' subtree")
    return umin, umax


def compute_biped_physics_layout(bounds_records: list[dict], *,
                                 use_folded_arms: bool | None = None) -> dict:
    """Compute boxes, joints, and disabled collision pairs for standard MC bipeds.

    `bounds_records` items:
      {'bone_name', 'parent_name', 'local_mat4', 'local_min', 'local_max', 'vertex_count', 'has_bounds'}
    `use_folded_arms`: if True (or None when `arms` subtree has geometry), box folded `arms`
      (and descendants such as `left_shoulder` / `right_hand` / `middlearm_r1`) across the chest
      instead of open hanging `left_arm`/`right_arm`.
    Returns {'boxes': [...], 'joints': [...], 'disabled_pairs': [...], 'char_height': float}.
    Raises ValueError if required bones or limb bounds are missing.
    """
    by_name = {rec['bone_name']: rec for rec in bounds_records}
    arms_subtree = _collect_bone_subtree(by_name, 'arms')
    has_arms_bounds = any(by_name[n].get('has_bounds') for n in arms_subtree)
    has_folded_arms = has_arms_bounds if use_folded_arms is None else (bool(use_folded_arms) and has_arms_bounds)
    active_limbs = ('body', 'head', 'arms', 'left_leg', 'right_leg') if has_folded_arms else BIPED_LIMB_BONES
    missing = [b for b in (BIPED_PROXY_BONES + active_limbs) if b not in by_name]
    if missing:
        raise ValueError(f'Missing required biped bones: {missing}')

    no_bounds = [
        b for b in active_limbs
        if not (has_arms_bounds if b == 'arms' else by_name[b].get('has_bounds'))
    ]
    if no_bounds:
        raise ValueError(f'Missing vertex bounds for limb bones: {no_bounds}')

    comp_mats = _compute_component_matrices(bounds_records)
    inv_comp_mats = {name: _mat4_inverse_affine(m) for name, m in comp_mats.items()}

    orig_bounds = {}
    for b in active_limbs:
        if b == 'arms':
            orig_bounds[b] = _merge_folded_arms_bounds(by_name, comp_mats, inv_comp_mats)
        else:
            orig_bounds[b] = (list(by_name[b]['local_min']), list(by_name[b]['local_max']))

    comp_all_z = []
    for b in active_limbs:
        cmin, cmax = _local_box_to_component_aabb(orig_bounds[b][0], orig_bounds[b][1], comp_mats[b])
        comp_all_z.extend([cmin[2], cmax[2]])
    char_height = max(max(comp_all_z) - min(comp_all_z), 20.0)

    # Robed/coated bipeds (e.g. evoker/pillager/vindicator/illusioner/zombie_villager) have long `body`
    # robes extending past the pelvis around the legs. Trim the lower skirt from `body` so torso and legs
    # keep full blocky widths instead of being crushed horizontally against each other.
    ll_cmin, ll_cmax = _local_box_to_component_aabb(*orig_bounds['left_leg'], comp_mats['left_leg'])
    rl_cmin, rl_cmax = _local_box_to_component_aabb(*orig_bounds['right_leg'], comp_mats['right_leg'])
    hip_z = max(ll_cmax[2], rl_cmax[2])
    leg_h = max(1.0, hip_z - min(ll_cmin[2], rl_cmin[2]))
    torso_cmin, torso_cmax = _local_box_to_component_aabb(
        orig_bounds['body'][0], orig_bounds['body'][1], comp_mats['body']
    )
    body_h = max(1.0, torso_cmax[2] - torso_cmin[2])
    if (hip_z - torso_cmin[2]) > 0.30 * leg_h and (torso_cmax[2] - hip_z) >= 0.45 * body_h:
        ux, uy, uz = _mat4_transform_vector(inv_comp_mats['body'], (0.0, 0.0, 1.0))
        up_axis = max(range(3), key=lambda k: abs((ux, uy, uz)[k]))
        tx = 0.5 * (torso_cmin[0] + torso_cmax[0])
        ty = 0.5 * (torso_cmin[1] + torso_cmax[1])
        local_hip = _mat4_transform_point(inv_comp_mats['body'], (tx, ty, hip_z))
        bmin, bmax = orig_bounds['body']
        if (ux, uy, uz)[up_axis] >= 0.0:
            bmin[up_axis] = max(bmin[up_axis], local_hip[up_axis])
        else:
            bmax[up_axis] = min(bmax[up_axis], local_hip[up_axis])
        torso_cmin, torso_cmax = _local_box_to_component_aabb(bmin, bmax, comp_mats['body'])

    torso_center = [0.5 * (torso_cmin[i] + torso_cmax[i]) for i in range(3)]

    limb_boxes = {}
    for b in active_limbs:
        bmin, bmax = orig_bounds[b]
        limb_boxes[b] = _shrink_initial_limb_box(
            b, bmin, bmax, comp_mats[b], inv_comp_mats[b], torso_center, char_height
        )

    target_gap = _clamp(0.015 * char_height, 1.5, 3.5)
    skip_pairs = {('arms', 'body')} if has_folded_arms else None
    _resolve_component_overlaps(
        limb_boxes, orig_bounds, comp_mats, inv_comp_mats, target_gap, skip_pairs=skip_pairs
    )

    # Estimate limb mass order of magnitude (volume in m^3 * 1000 * 0.25 mass_scale) for proxy mass matching
    limb_masses = []
    for b in active_limbs:
        lmin, lmax = limb_boxes[b]
        vol_cm3 = max(1.0, (lmax[0] - lmin[0]) * (lmax[1] - lmin[1]) * (lmax[2] - lmin[2]))
        limb_masses.append((vol_cm3 / 1_000_000.0) * 1000.0 * 0.25)
    avg_limb_mass = sum(limb_masses) / max(len(limb_masses), 1)
    pelvis_mass_override = _clamp(avg_limb_mass * 0.50, 2.0, 12.0)
    root_mass_override = _clamp(avg_limb_mass * 0.35, 1.5, 8.0)

    proxy_size = _clamp(0.015 * char_height, 1.5, 4.0)
    boxes = [
        {
            'bone_name': 'root',
            'center': (0.0, 0.0, 0.0),
            'rotation': (0.0, 0.0, 0.0),
            'size': (proxy_size, proxy_size, proxy_size),
            'collision_enabled': True,
            'consider_for_bounds': True,
            'physics_mode': 'default',
            'mass_scale': 0.25,
            'mass_override_kg': root_mass_override,
            'linear_damping': 0.01,
            'angular_damping': 0.01,
        },
        {
            'bone_name': 'pelvis',
            'center': (0.0, 0.0, 0.0),
            'rotation': (0.0, 0.0, 0.0),
            'size': (proxy_size, proxy_size, proxy_size),
            'collision_enabled': False,
            'consider_for_bounds': False,
            'physics_mode': 'default',
            'mass_scale': 0.25,
            'mass_override_kg': pelvis_mass_override,
            'linear_damping': 0.01,
            'angular_damping': 0.01,
        },
    ]

    for b in active_limbs:
        lmin, lmax = limb_boxes[b]
        center = tuple(0.5 * (lmin[i] + lmax[i]) for i in range(3))
        size = tuple(max(_MIN_BOX_SIZE_CM, lmax[i] - lmin[i]) for i in range(3))
        boxes.append({
            'bone_name': b,
            'center': center,
            'rotation': (0.0, 0.0, 0.0),
            'size': size,
            'collision_enabled': True,
            'consider_for_bounds': True,
            'physics_mode': 'default',
            'mass_scale': 0.25,
            'mass_override_kg': 0.0,
            'linear_damping': 0.01,
            'angular_damping': 0.01,
        })

    if has_folded_arms:
        joint_specs = [
            spec for spec in _JOINT_LIMITS if spec[0] not in ('left_arm', 'right_arm')
        ] + [('arms', 'body', 20.0, 15.0, 15.0)]
    else:
        joint_specs = list(_JOINT_LIMITS)

    joints = [
        {
            'joint_name': child,
            'child_bone': child,
            'parent_bone': parent,
            'swing1_motion': 'limited',
            'swing1_limit_degrees': s1,
            'swing2_motion': 'limited',
            'swing2_limit_degrees': s2,
            'twist_motion': 'limited',
            'twist_limit_degrees': tw,
            'disable_collision': (has_folded_arms and child == 'arms' and parent == 'body'),
            'enable_projection': True,
        }
        for child, parent, s1, s2, tw in joint_specs
    ]

    # Disable internal collision for root against every other body while keeping mutual limb collision enabled.
    # Folded `arms` hug `body` directly so self-collision between them is also disabled.
    # (pelvis already sets collision_enabled=False globally.)
    disabled_pairs = [
        tuple(sorted(('root', b['bone_name'])))
        for b in boxes
        if b['bone_name'] != 'root'
    ]
    if has_folded_arms:
        disabled_pairs.append(('arms', 'body'))

    return {
        'boxes': boxes,
        'joints': joints,
        'disabled_pairs': disabled_pairs,
        'char_height': char_height,
    }


def compute_head_physics_layout(bounds_records: list[dict]) -> dict:
    """Compute a single inner-head collision box for split head SkeletalMesh."""
    by_name = {rec['bone_name']: rec for rec in bounds_records}
    head_rec = by_name.get('head')
    if not head_rec or not head_rec.get('has_bounds'):
        raise ValueError("Missing vertex bounds for 'head' bone")

    lmin = list(head_rec['local_min'])
    lmax = list(head_rec['local_max'])
    ext = [max(lmax[i] - lmin[i], _MIN_BOX_SIZE_CM) for i in range(3)]
    shrink = 0.06
    for i in range(3):
        half_inset = 0.5 * shrink * ext[i]
        lmin[i] += half_inset
        lmax[i] -= half_inset
    lmin, lmax = _clamp_min_box_extents(
        lmin, lmax, head_rec['local_min'], head_rec['local_max'], min_frac=0.40
    )
    center = tuple(0.5 * (lmin[i] + lmax[i]) for i in range(3))
    size = tuple(max(_MIN_BOX_SIZE_CM, lmax[i] - lmin[i]) for i in range(3))
    return {
        'boxes': [{
            'bone_name': 'head',
            'center': center,
            'rotation': (0.0, 0.0, 0.0),
            'size': size,
            'collision_enabled': True,
            'consider_for_bounds': True,
            'physics_mode': 'default',
            'mass_scale': 0.25,
            'mass_override_kg': 0.0,
            'linear_damping': 0.01,
            'angular_damping': 0.01,
        }],
        'joints': [],
        'disabled_pairs': [],
    }


_OVERLAY_WORDS = frozenset({
    'hat', 'headwear', 'jacket', 'coat', 'bodywear', 'sleeve', 'pants',
    'overlay', 'outer', 'saddle', 'bridle', 'collar', 'helmet', 'chestplate',
    'leggings', 'boots', 'cape', 'cloak', 'apron', 'goggles', 'mask',
    'bandana', 'crown',
})

_DECOR_WORDS = frozenset({
    'nose', 'mouth', 'eye', 'eyes', 'pupil', 'eyebrow', 'eyebrows',
    'whisker', 'whiskers', 'tooth', 'teeth', 'fang', 'tongue', 'tendril',
    'antenna', 'antennae', 'feeler', 'ribcage', 'spike', 'spikes', 'gill',
    'gills', 'wattle', 'comb', 'mane', 'snout', 'jaw', 'beak', 'earring',
    'plume', 'crest', 'tuft', 'horn', 'horns',
})

_TRUNK_WORDS = frozenset({'body', 'torso', 'pelvis', 'abdomen', 'chest', 'cube', 'hull', 'bottom', 'base', 'frame'})
_NECK_WORDS = frozenset({'neck', 'waist', 'hip', 'hips'})
_HEAD_WORDS = frozenset({'head', 'skull'})
_STRUCTURAL_LIMB_WORDS = frozenset({
    'body', 'torso', 'pelvis', 'abdomen', 'chest', 'head', 'skull', 'neck',
    'leg', 'legs', 'arm', 'arms', 'wing', 'wings', 'tail', 'tails',
    'tentacle', 'tentacles', 'fin', 'fins', 'flipper', 'flippers',
    'claw', 'claws', 'ear', 'ears', 'segment', 'paddle',
})


def _make_box_spec(bone_name: str, center: tuple[float, float, float],
                   size: tuple[float, float, float], *,
                   collision_enabled: bool = True,
                   consider_for_bounds: bool = True,
                   mass_override_kg: float = 0.0) -> dict:
    return {
        'bone_name': bone_name,
        'center': center,
        'rotation': (0.0, 0.0, 0.0),
        'size': size,
        'collision_enabled': collision_enabled,
        'consider_for_bounds': consider_for_bounds,
        'physics_mode': 'default',
        'mass_scale': 0.25,
        'mass_override_kg': float(mass_override_kg),
        'linear_damping': 0.01,
        'angular_damping': 0.01,
    }


def _make_joint_spec(child_bone: str, parent_bone: str,
                     limits: tuple[float, float, float], *,
                     motion: str = 'limited',
                     disable_collision: bool = False) -> dict:
    s1, s2, tw = limits
    return {
        'joint_name': child_bone,
        'child_bone': child_bone,
        'parent_bone': parent_bone,
        'swing1_motion': motion,
        'swing1_limit_degrees': s1,
        'swing2_motion': motion,
        'swing2_limit_degrees': s2,
        'twist_motion': motion,
        'twist_limit_degrees': tw,
        'disable_collision': disable_collision,
        'enable_projection': True,
    }


def _tokenize_bone_name(name: str) -> set[str]:
    split_camel = re.sub(r'([a-z])([A-Z])', r'\1_\2', name)
    return set(re.findall(r'[a-z]+', split_camel.lower()))


def _tokens_with_empty_ancestors(bone_name: str, by_name: dict[str, dict]) -> set[str]:
    tokens = _tokenize_bone_name(bone_name)
    cur = by_name[bone_name].get('parent_name')
    while cur and cur in by_name:
        if cur == 'root' or by_name[cur].get('has_bounds'):
            break
        tokens |= _tokenize_bone_name(cur)
        cur = by_name[cur].get('parent_name')
    return tokens


def _safe_box_volume(bmin: list[float], bmax: list[float], *, floor_cm: float = 0.25) -> float:
    return (
        max(floor_cm, bmax[0] - bmin[0])
        * max(floor_cm, bmax[1] - bmin[1])
        * max(floor_cm, bmax[2] - bmin[2])
    )


def _estimate_box_mass_kg(lmin: list[float], lmax: list[float]) -> float:
    sx = max(_MIN_BOX_SIZE_CM, lmax[0] - lmin[0])
    sy = max(_MIN_BOX_SIZE_CM, lmax[1] - lmin[1])
    sz = max(_MIN_BOX_SIZE_CM, lmax[2] - lmin[2])
    return (sx * sy * sz / 1_000_000.0) * 1000.0 * 0.25


def _box_containment_fraction(inner_min: list[float], inner_max: list[float],
                              outer_min: list[float], outer_max: list[float]) -> float:
    frac = 1.0
    for ax in range(3):
        span = inner_max[ax] - inner_min[ax]
        if span <= 0.25:
            mid = 0.5 * (inner_min[ax] + inner_max[ax])
            if not (outer_min[ax] - 0.15 <= mid <= outer_max[ax] + 0.15):
                return 0.0
        else:
            inter = max(0.0, min(inner_max[ax], outer_max[ax]) - max(inner_min[ax], outer_min[ax]))
            frac *= min(1.0, inter / span)
    return frac


def _aabb_surface_gap(amin: list[float], amax: list[float],
                      bmin: list[float], bmax: list[float]) -> float:
    sq = 0.0
    for ax in range(3):
        d = max(0.0, bmin[ax] - amax[ax], amin[ax] - bmax[ax])
        sq += d * d
    return math.sqrt(sq)


def _aabb_clearances(amin: list[float], amax: list[float],
                     bmin: list[float], bmax: list[float]) -> list[float]:
    return [max(bmin[ax] - amax[ax], amin[ax] - bmax[ax]) for ax in range(3)]


def _point_to_aabb_distance(pt: tuple[float, float, float],
                            bmin: list[float], bmax: list[float]) -> float:
    sq = 0.0
    for ax in range(3):
        if pt[ax] < bmin[ax]:
            d = bmin[ax] - pt[ax]
        elif pt[ax] > bmax[ax]:
            d = pt[ax] - bmax[ax]
        else:
            d = 0.0
        sq += d * d
    return math.sqrt(sq)


def _generic_role_tier(bone_name: str, by_name: dict[str, dict]) -> int:
    tokens = _tokens_with_empty_ancestors(bone_name, by_name)
    if tokens & _OVERLAY_WORDS or tokens & _DECOR_WORDS:
        return 3
    if tokens & _TRUNK_WORDS:
        return 0
    if tokens & _NECK_WORDS:
        return 1
    if tokens & _HEAD_WORDS:
        return 2
    return 3


def _generic_joint_limits(bone_name: str, by_name: dict[str, dict]) -> tuple[float, float, float]:
    tokens = _tokens_with_empty_ancestors(bone_name, by_name)
    if tokens & _HEAD_WORDS:
        return (40.0, 35.0, 45.0)
    if tokens & {'arm', 'arms', 'wing', 'wings', 'flipper', 'claw', 'claws'}:
        return (70.0, 55.0, 35.0)
    if tokens & {'leg', 'legs', 'foot', 'feet', 'hind', 'front'}:
        return (60.0, 40.0, 25.0)
    if tokens & {'tail', 'neck', 'spine', 'tentacle', 'segment', 'body', 'torso'}:
        return (40.0, 40.0, 25.0)
    return (45.0, 45.0, 30.0)


def _nearest_ancestor_in(bone_name: str, candidate_set: set[str], by_name: dict[str, dict]) -> str | None:
    cur = by_name[bone_name].get('parent_name')
    while cur and cur in by_name:
        if cur in candidate_set:
            return cur
        cur = by_name[cur].get('parent_name')
    return None


def _classify_generic_bones(active_bones: list[str], raw_comp_aabbs: dict[str, tuple[list[float], list[float]]],
                            raw_vols: dict[str, float], by_name: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Partition active skinned bones into primary structural bones vs overlay/decor/contained accessories."""
    if len(active_bones) <= 1:
        return list(active_bones), []

    tokens_by_bone = {b: _tokenize_bone_name(b) for b in active_bones}
    is_named_accessory = {
        b: bool(tokens_by_bone[b] & (_OVERLAY_WORDS | _DECOR_WORDS))
        for b in active_bones
    }
    accessories = {b for b in active_bones if is_named_accessory[b]}

    # Also treat non-structural boxes strictly enclosed (>=85%) inside a larger structural bone as inner accessories
    # (e.g., slime inner cube inside outer translucent cube), while preserving explicit limb bones (e.g. armadillo_baby legs).
    for b in active_bones:
        if b in accessories:
            continue
        if tokens_by_bone[b] & _STRUCTURAL_LIMB_WORDS:
            continue
        bcmin, bcmax = raw_comp_aabbs[b]
        for h in active_bones:
            if h == b or is_named_accessory[h]:
                continue
            if raw_vols[h] <= 1.05 * raw_vols[b]:
                continue
            hcmin, hcmax = raw_comp_aabbs[h]
            if _box_containment_fraction(bcmin, bcmax, hcmin, hcmax) >= 0.85:
                accessories.add(b)
                break

    # Any bone with a primary descendant must stay primary so the hierarchy remains connected.
    changed = True
    while changed:
        changed = False
        primary_set = {b for b in active_bones if b not in accessories}
        for p in list(primary_set):
            cur = by_name[p].get('parent_name')
            while cur and cur in by_name:
                if cur in accessories:
                    accessories.remove(cur)
                    changed = True
                cur = by_name[cur].get('parent_name')

    primary = [b for b in active_bones if b not in accessories]
    if not primary:
        return list(active_bones), []
    return primary, [b for b in active_bones if b in accessories]


def _pick_accessory_host(acc: str, primary_bones: list[str],
                         raw_comp_aabbs: dict[str, tuple[list[float], list[float]]],
                         raw_vols: dict[str, float],
                         by_name: dict[str, dict]) -> str:
    acmin, acmax = raw_comp_aabbs[acc]
    ac_center = [0.5 * (acmin[i] + acmax[i]) for i in range(3)]
    acc_tokens = _tokens_with_empty_ancestors(acc, by_name)
    acc_vol = max(raw_vols[acc], 1e-3)

    best_host = primary_bones[0]
    best_score = None
    for p in primary_bones:
        pcmin, pcmax = raw_comp_aabbs[p]
        inter = 1.0
        for ax in range(3):
            span = max(0.25, min(acmax[ax], pcmax[ax]) - max(acmin[ax], pcmin[ax])) if (
                min(acmax[ax], pcmax[ax]) >= max(acmin[ax], pcmin[ax]) - 0.15
            ) else 0.0
            inter *= span
        overlap_frac = inter / acc_vol
        gap = _aabb_surface_gap(acmin, acmax, pcmin, pcmax)
        p_tokens = _tokens_with_empty_ancestors(p, by_name)
        head_match = 1 if (
            (acc_tokens & {'headwear', 'hat', 'nose', 'mouth', 'eye', 'eyes', 'jaw', 'beak', 'snout', 'tongue', 'tooth', 'teeth', 'horn', 'horns', 'ear', 'earring'})
            and (p_tokens & _HEAD_WORDS)
        ) else 0
        body_match = 1 if (
            (acc_tokens & {'bodywear', 'jacket', 'coat', 'ribcage', 'mane', 'saddle', 'bridle', 'collar'})
            and (p_tokens & _TRUNK_WORDS)
        ) else 0
        semantic_match = (head_match + body_match) if gap <= 5.0 else 0
        p_center = [0.5 * (pcmin[i] + pcmax[i]) for i in range(3)]
        center_dist = math.sqrt(sum((ac_center[i] - p_center[i]) ** 2 for i in range(3)))
        score = (-semantic_match, -round(overlap_frac, 4), round(gap, 3), center_dist, -raw_vols[p], p)
        if best_score is None or score < best_score:
            best_score = score
            best_host = p
    return best_host


def compute_generic_physics_layout(bounds_records: list[dict]) -> dict:
    """Compute blocky box bodies, proximity-MST joints, and collision rules for any skeletal mesh.

    Supports non-humanoid GLBs (including `quadruped_edit`), `edit_rig=False` raw rigs, single/complex CEM models, and combined
    CEM entities without hardcoding a skeleton archetype. Keeps the unconstrained `root` proxy box when
    an empty `root` bone is present so Blueprints calling `SetAllBodiesBelowSimulatePhysics("root", ...)`
    behave uniformly across biped and non-biped mobs.
    """
    by_name = {rec['bone_name']: rec for rec in bounds_records}
    active_bones = [rec['bone_name'] for rec in bounds_records if rec.get('has_bounds')]
    if not active_bones:
        raise ValueError('No skeletal bones with vertex bounds found')

    comp_mats = _compute_component_matrices(bounds_records)
    inv_comp_mats = {name: _mat4_inverse_affine(m) for name, m in comp_mats.items()}

    raw_comp_aabbs = {
        b: _local_box_to_component_aabb(by_name[b]['local_min'], by_name[b]['local_max'], comp_mats[b])
        for b in active_bones
    }
    raw_vols = {
        b: _safe_box_volume(raw_comp_aabbs[b][0], raw_comp_aabbs[b][1])
        for b in active_bones
    }

    primary_bones, accessory_bones = _classify_generic_bones(active_bones, raw_comp_aabbs, raw_vols, by_name)
    primary_set = set(primary_bones)
    role_tiers = {b: _generic_role_tier(b, by_name) for b in primary_bones}

    all_cmin = [min(raw_comp_aabbs[b][0][ax] for b in primary_bones) for ax in range(3)]
    all_cmax = [max(raw_comp_aabbs[b][1][ax] for b in primary_bones) for ax in range(3)]
    char_scale = max(all_cmax[0] - all_cmin[0], all_cmax[1] - all_cmin[1], all_cmax[2] - all_cmin[2], 20.0)
    global_min_z = all_cmin[2]

    orig_bounds: dict[str, tuple[list[float], list[float]]] = {}
    limb_boxes: dict[str, tuple[list[float], list[float]]] = {}
    for b in primary_bones:
        bmin = list(by_name[b]['local_min'])
        bmax = list(by_name[b]['local_max'])
        # Ensure degenerate flat/zero-thickness meshes have >= _MIN_BOX_SIZE_CM thickness first.
        for i in range(3):
            if bmax[i] - bmin[i] < _MIN_BOX_SIZE_CM:
                mid = 0.5 * (bmin[i] + bmax[i])
                bmin[i] = mid - 0.5 * _MIN_BOX_SIZE_CM
                bmax[i] = mid + 0.5 * _MIN_BOX_SIZE_CM
        orig_bounds[b] = (list(bmin), list(bmax))

        lmin, lmax = list(bmin), list(bmax)
        # Proportional silhouette-preserving inset for breathing room; preserve ground reach on feet.
        keep_bottom = abs(raw_comp_aabbs[b][0][2] - global_min_z) <= 2.0
        for i in range(3):
            ext = lmax[i] - lmin[i]
            if ext > 4.0:
                inset = 0.14 * ext
                lmin[i] += 0.5 * inset
                lmax[i] -= 0.5 * inset
        if keep_bottom:
            dir_down = _mat4_transform_vector(inv_comp_mats[b], (0.0, 0.0, -1.0))
            dom_z = max(range(3), key=lambda k: abs(dir_down[k]))
            if dir_down[dom_z] > 0.0:
                lmax[dom_z] = bmax[dom_z]
            elif dir_down[dom_z] < 0.0:
                lmin[dom_z] = bmin[dom_z]
        limb_boxes[b] = _clamp_min_box_extents(lmin, lmax, bmin, bmax, min_frac=0.60)

    # Identify top-level primary bones (no primary RefSkeleton ancestor -> sit under root / empty pivots)
    p_anc = {b: _nearest_ancestor_in(b, primary_set, by_name) for b in primary_bones}
    top_roots = [b for b in primary_bones if p_anc[b] is None]
    hub = min(
        top_roots,
        key=lambda b: (role_tiers[b], -raw_vols[b], b),
    )

    trim_resistance = {}
    for b in primary_bones:
        if b == hub or role_tiers[b] == 0:
            trim_resistance[b] = 1.6
        elif role_tiers[b] in (1, 2):
            trim_resistance[b] = 1.2
        else:
            trim_resistance[b] = 0.9

    target_gap = _clamp(0.015 * char_scale, 0.75, 5.0)
    if len(primary_bones) > 1:
        _resolve_component_overlaps(
            limb_boxes,
            orig_bounds,
            comp_mats,
            inv_comp_mats,
            target_gap,
            min_frac=0.60,
            max_trim_ratio=0.35,
            trim_against='min',
            trim_resistance=trim_resistance,
            require_resolvable=True,
        )

    # Disable internal collision for tightly packed neighbors that would pinch on bending/landing.
    final_aabbs = {
        b: _local_box_to_component_aabb(limb_boxes[b][0], limb_boxes[b][1], comp_mats[b])
        for b in primary_bones
    }
    close_margin = _clamp(0.025 * char_scale, 1.5, 45.0)
    disabled_set: set[tuple[str, str]] = set()
    for i in range(len(primary_bones)):
        for j in range(i + 1, len(primary_bones)):
            a, b = primary_bones[i], primary_bones[j]
            clearances = _aabb_clearances(final_aabbs[a][0], final_aabbs[a][1],
                                          final_aabbs[b][0], final_aabbs[b][1])
            if max(clearances) < close_margin:
                disabled_set.add(tuple(sorted((a, b))))

    # Build a single connected tree across all primary_bones rooted at `hub`.
    primary_edges: list[tuple[str, str]] = []  # (child, parent)
    tokens_with_anc = {b: _tokens_with_empty_ancestors(b, by_name) for b in primary_bones}
    visited = {hub}
    depth = {hub: 0}
    unvisited = set(top_roots) - visited
    while unvisited:
        best_choice = None
        best_cost = None
        for u in visited:
            u_cmin, u_cmax = raw_comp_aabbs[u]
            u_tier_pen = (0.0 if role_tiers[u] <= 2 else 3.5) + 0.15 * role_tiers[u]
            for v in unvisited:
                v_cmin, v_cmax = raw_comp_aabbs[v]
                gap_uv = _aabb_surface_gap(u_cmin, u_cmax, v_cmin, v_cmax)
                v_pivot = (comp_mats[v][0][3], comp_mats[v][1][3], comp_mats[v][2][3])
                piv_dist = _point_to_aabb_distance(v_pivot, u_cmin, u_cmax)
                anatomical_bonus = (
                    -2.5
                    if (gap_uv <= 5.0 and role_tiers[u] == 2 and (tokens_with_anc[v] & {'ear', 'ears', 'horn', 'horns'}))
                    else 0.0
                )
                cost = (
                    gap_uv + u_tier_pen + 0.6 * role_tiers[v] + 0.25 * depth[u] + 0.05 * piv_dist + anatomical_bonus,
                    -raw_vols[u],
                    u,
                    v,
                )
                if best_cost is None or cost < best_cost:
                    best_cost = cost
                    best_choice = (v, u)
        child_v, parent_u = best_choice
        primary_edges.append((child_v, parent_u))
        visited.add(child_v)
        unvisited.remove(child_v)
        depth[child_v] = depth[parent_u] + 1

    for b in primary_bones:
        if p_anc[b] is not None:
            primary_edges.append((b, p_anc[b]))

    # Mass balancing so tiny wings/segments never exceed ~14:1 mass ratio against the heaviest trunk/limb.
    raw_masses = {b: _estimate_box_mass_kg(*limb_boxes[b]) for b in primary_bones}
    max_primary_mass = max(raw_masses.values())
    min_box_mass = max(0.25, max_primary_mass / 14.0)
    eff_masses = {
        b: max(raw_masses[b], min_box_mass)
        for b in primary_bones
    }

    boxes: list[dict] = []
    empty_root_proxy = ('root' in by_name) and ('root' not in set(active_bones))
    if empty_root_proxy:
        proxy_size = _clamp(0.015 * char_scale, 1.5, 4.0)
        root_mass = max(min_box_mass, _clamp(eff_masses[hub] * 0.35, 1.5, max(8.0, eff_masses[hub] * 0.35)))
        boxes.append(_make_box_spec(
            'root', (0.0, 0.0, 0.0), (proxy_size, proxy_size, proxy_size),
            collision_enabled=True, consider_for_bounds=True, mass_override_kg=root_mass,
        ))

    for b in primary_bones:
        lmin, lmax = limb_boxes[b]
        center = tuple(0.5 * (lmin[i] + lmax[i]) for i in range(3))
        size = tuple(max(_MIN_BOX_SIZE_CM, lmax[i] - lmin[i]) for i in range(3))
        override = eff_masses[b] if raw_masses[b] < min_box_mass - 1e-6 else 0.0
        boxes.append(_make_box_spec(
            b, center, size,
            collision_enabled=True, consider_for_bounds=True, mass_override_kg=override,
        ))

    for child_b, parent_b in primary_edges:
        disabled_set.add(tuple(sorted((child_b, parent_b))))

    joints: list[dict] = [
        _make_joint_spec(
            child_b,
            parent_b,
            _generic_joint_limits(child_b, by_name),
            motion='limited',
            disable_collision=(tuple(sorted((child_b, parent_b))) in disabled_set),
        )
        for child_b, parent_b in primary_edges
    ]

    # Accessory bones with a primary RefSkeleton ancestor are omitted (UE carries them rigidly via parent).
    # Accessories sitting under empty `root`/pivots get non-colliding helper bodies locked to their host.
    for acc in accessory_bones:
        if _nearest_ancestor_in(acc, primary_set, by_name) is not None:
            continue
        host = _pick_accessory_host(acc, primary_bones, raw_comp_aabbs, raw_vols, by_name)
        amin = list(by_name[acc]['local_min'])
        amax = list(by_name[acc]['local_max'])
        for i in range(3):
            if amax[i] - amin[i] < _MIN_BOX_SIZE_CM:
                mid = 0.5 * (amin[i] + amax[i])
                amin[i] = mid - 0.5 * _MIN_BOX_SIZE_CM
                amax[i] = mid + 0.5 * _MIN_BOX_SIZE_CM
        center = tuple(0.5 * (amin[i] + amax[i]) for i in range(3))
        size = tuple(max(_MIN_BOX_SIZE_CM, amax[i] - amin[i]) for i in range(3))
        acc_mass = _clamp(_estimate_box_mass_kg(amin, amax), min_box_mass, max(min_box_mass, 0.25 * eff_masses[host]))
        boxes.append(_make_box_spec(
            acc, center, size,
            collision_enabled=False, consider_for_bounds=False, mass_override_kg=acc_mass,
        ))
        joints.append(_make_joint_spec(
            acc, host, (0.0, 0.0, 0.0), motion='locked', disable_collision=True,
        ))
        disabled_set.add(tuple(sorted((acc, host))))

    if empty_root_proxy:
        for box in boxes:
            if box['bone_name'] != 'root':
                disabled_set.add(tuple(sorted(('root', box['bone_name']))))

    return {
        'boxes': boxes,
        'joints': joints,
        'disabled_pairs': sorted(disabled_set),
        'char_scale': char_scale,
    }


# ---------------------------------------------------------------------------
# Unreal Engine integration (Editor only; pure-math functions above need no UE)
# ---------------------------------------------------------------------------

def _mineprep_cpp_available() -> bool:
    import unreal
    mod = getattr(unreal, 'mineprep', None)
    return bool(mod is not None and hasattr(mod, 'build_box_physics_asset'))


def _resolve_base_name_and_folder(folder: str, asset_name: str, full_mesh=None) -> tuple[str, str]:
    target_folder = (folder or '').rstrip('/')
    if not target_folder and full_mesh is not None:
        mesh_path = full_mesh.get_path_name().rsplit('.', 1)[0]
        target_folder = mesh_path.rsplit('/', 1)[0]
    explicit = (asset_name or '').strip()
    if explicit:
        return explicit, target_folder
    if full_mesh is None:
        return '', target_folder
    mesh_name = full_mesh.get_name().strip()
    return (mesh_name[4:] if mesh_name.startswith('SKM_') else mesh_name), target_folder


def _get_mesh_physics_asset(mesh):
    if mesh is None:
        return None
    return mesh.get_editor_property('physics_asset')


def _is_physics_asset_compatible(mesh, physics_asset) -> bool:
    if mesh is None or physics_asset is None:
        return False
    import unreal
    subsys = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    return bool(subsys.is_physics_asset_compatible(mesh, physics_asset))


def _assign_physics_asset_if_needed(mesh, physics_asset, *, warnings: list[str], label: str) -> bool:
    if mesh is None or physics_asset is None:
        return False
    if _get_mesh_physics_asset(mesh) == physics_asset:
        return True
    import unreal
    subsys = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    if not _is_physics_asset_compatible(mesh, physics_asset):
        warnings.append(f'物理资产与骨骼不兼容，未绑定 {label}: {physics_asset.get_path_name()}')
        return False
    ok = bool(subsys.assign_physics_asset(mesh, physics_asset))
    if not ok:
        warnings.append(f'分配物理资产失败（{label}）: {physics_asset.get_path_name()}')
    return ok


def _mesh_bone_names(skeletal_mesh) -> set[str] | None:
    try:
        from mc_model_assets import _reference_bones
        bones = _reference_bones(skeletal_mesh)
        return set(bones) if bones else None
    except Exception:
        return None


def _query_ue_bone_bounds(skeletal_mesh) -> list[dict]:
    import unreal
    raw_bounds, err = unreal.mineprep.get_bone_local_bounds(skeletal_mesh, 0, True)
    if err or not raw_bounds:
        raise RuntimeError(err or f'GetBoneLocalBounds returned empty bounds for {skeletal_mesh.get_name()}')
    records = []
    for entry in raw_bounds:
        records.append({
            'bone_name': str(entry.bone_name),
            'parent_name': str(entry.parent_bone_name) if str(entry.parent_bone_name) != 'None' else '',
            'local_mat4': _ue_transform_to_mat4(entry.local_transform),
            'local_min': [float(entry.local_min.x), float(entry.local_min.y), float(entry.local_min.z)],
            'local_max': [float(entry.local_max.x), float(entry.local_max.y), float(entry.local_max.z)],
            'vertex_count': int(entry.vertex_count),
            'has_bounds': bool(entry.has_bounds),
        })
    return records


def _query_bone_bounds(skeletal_mesh) -> list[dict]:
    """Query per-bone local bounds from the linked GLB first, then optional C++ fallback."""
    from pathlib import Path
    import unreal
    from mc_model import glb_bone_bounds

    if skeletal_mesh is not None:
        try:
            imp = skeletal_mesh.get_editor_property('asset_import_data')
            sources = imp.extract_filenames() if imp is not None else ()
        except Exception:
            sources = ()
        expected_bones = None
        checked_names = False
        for src in sources:
            path = Path(str(src))
            if path.suffix.lower() != '.glb' or not path.is_file():
                continue
            try:
                records = glb_bone_bounds(path, dominant_weight_only=True)
            except Exception:
                continue
            if not records:
                continue
            if not checked_names:
                expected_bones = _mesh_bone_names(skeletal_mesh)
                checked_names = True
            if not expected_bones or expected_bones <= {r['bone_name'] for r in records}:
                return records

    mod = getattr(unreal, 'mineprep', None)
    if mod is not None and hasattr(mod, 'get_bone_local_bounds'):
        return _query_ue_bone_bounds(skeletal_mesh)
    mesh_name = skeletal_mesh.get_name() if skeletal_mesh is not None else '<None>'
    raise RuntimeError(f'无法获取骨骼局部包围盒（无匹配 GLB 且缺少 get_bone_local_bounds）: {mesh_name}')


def _to_ue_physics_mode(mode: str):
    import unreal
    return {
        'default': unreal.MineprepBodyPhysicsMode.DEFAULT,
        'kinematic': unreal.MineprepBodyPhysicsMode.KINEMATIC,
        'simulated': unreal.MineprepBodyPhysicsMode.SIMULATED,
    }[mode]


def _to_ue_angular_motion(motion: str):
    import unreal
    return {
        'locked': unreal.MineprepAngularMotion.LOCKED,
        'limited': unreal.MineprepAngularMotion.LIMITED,
        'free': unreal.MineprepAngularMotion.FREE,
    }[motion]


def _build_ue_physics_asset_from_layout(reference_mesh, pa_path: str, layout: dict,
                                        *, overwrite: bool):
    import unreal
    ue_boxes = []
    for b in layout['boxes']:
        box = unreal.MineprepPhysicsBox()
        box.bone_name = b['bone_name']
        box.center = unreal.Vector(*b['center'])
        box.rotation = unreal.Rotator(*b['rotation'])
        box.size = unreal.Vector(*b['size'])
        box.collision_enabled = bool(b['collision_enabled'])
        box.consider_for_bounds = bool(b['consider_for_bounds'])
        box.physics_mode = _to_ue_physics_mode(b['physics_mode'])
        box.mass_scale = float(b['mass_scale'])
        box.mass_override_kg = float(b['mass_override_kg'])
        box.linear_damping = float(b['linear_damping'])
        box.angular_damping = float(b['angular_damping'])
        ue_boxes.append(box)

    ue_joints = []
    for j in layout['joints']:
        joint = unreal.MineprepPhysicsJoint()
        joint.joint_name = j['joint_name']
        joint.child_bone = j['child_bone']
        joint.parent_bone = j['parent_bone']
        joint.swing1_motion = _to_ue_angular_motion(j['swing1_motion'])
        joint.swing1_limit_degrees = float(j['swing1_limit_degrees'])
        joint.swing2_motion = _to_ue_angular_motion(j['swing2_motion'])
        joint.swing2_limit_degrees = float(j['swing2_limit_degrees'])
        joint.twist_motion = _to_ue_angular_motion(j['twist_motion'])
        joint.twist_limit_degrees = float(j['twist_limit_degrees'])
        joint.disable_collision = bool(j['disable_collision'])
        joint.enable_projection = bool(j['enable_projection'])
        ue_joints.append(joint)

    ue_pairs = []
    for a, b in layout['disabled_pairs']:
        pair = unreal.MineprepDisabledBodyPair()
        pair.body_a = a
        pair.body_b = b
        ue_pairs.append(pair)

    pa, err = unreal.mineprep.build_box_physics_asset(
        reference_mesh, pa_path, ue_boxes, ue_joints, ue_pairs, overwrite
    )
    if pa is None:
        raise RuntimeError(err or f'BuildBoxPhysicsAsset returned None for {pa_path}')
    return pa


def _allocate_available_pa_path(preferred_pa_path: str) -> str:
    import unreal
    lib = unreal.EditorAssetLibrary
    if not lib.does_asset_exist(preferred_pa_path):
        return preferred_pa_path
    index = 1
    while True:
        candidate = f'{preferred_pa_path}_{index}'
        if not lib.does_asset_exist(candidate):
            return candidate
        index += 1


def _fallback_create_physics_asset(mesh, preferred_pa_path: str, *, warnings: list[str],
                                   label: str, warn_if_conflict: bool = True):
    import unreal
    subsys = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    lib = unreal.EditorAssetLibrary

    created_pa = subsys.create_physics_asset(mesh, False, 0)
    if created_pa is None:
        raise RuntimeError(f'SkeletalMeshEditorSubsystem.create_physics_asset failed for {mesh.get_name()}')

    created_pkg = created_pa.get_path_name().rsplit('.', 1)[0]
    dest_path = _allocate_available_pa_path(preferred_pa_path)
    if dest_path != preferred_pa_path and warn_if_conflict:
        warnings.append(f'已有资产占用 {preferred_pa_path}，已保留原资产，{label}改为使用 {dest_path}')
    if created_pkg != dest_path:
        if lib.rename_asset(created_pkg, dest_path):
            renamed = lib.load_asset(dest_path)
            if renamed is not None:
                created_pa = renamed
        else:
            warnings.append(f'默认物理资产未能重命名为 {dest_path}，已保留 {created_pkg}')
    return created_pa


def _load_existing_asset(asset_path: str, expected_cls):
    import unreal
    if not asset_path or not unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        return None
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    return asset if isinstance(asset, expected_cls) else None


def _save_assets(assets: list, warnings: list[str]) -> None:
    import unreal
    seen = set()
    for asset in assets:
        if asset is None:
            continue
        path = asset.get_path_name().rsplit('.', 1)[0]
        if path in seen:
            continue
        seen.add(path)
        try:
            ok = bool(unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=True))
        except Exception as exc:
            warnings.append(f'保存资产失败 {path}: {exc}')
            continue
        if not ok:
            warnings.append(f'保存资产失败 {path}: save_loaded_asset 返回 False')


def snapshot_existing_physics_assets(folder: str, asset_name: str,
                                     full_mesh=None, body_mesh=None, head_mesh=None) -> dict:
    """Capture existing PA references prior to reload reimport so rebuild_physics=False can preserve them."""
    import unreal
    clean_name, base_folder = _resolve_base_name_and_folder(folder, asset_name, full_mesh)
    if full_mesh is None and base_folder and clean_name:
        full_mesh = _load_existing_asset(f'{base_folder}/SKM_{clean_name}', unreal.SkeletalMesh)
    if body_mesh is None and base_folder and clean_name:
        body_mesh = _load_existing_asset(f'{base_folder}/SKM_{clean_name}_body', unreal.SkeletalMesh)
    if head_mesh is None and base_folder and clean_name:
        head_mesh = _load_existing_asset(f'{base_folder}/SKM_{clean_name}_head', unreal.SkeletalMesh)

    main_path = f'{base_folder}/PA_{clean_name}' if base_folder and clean_name else ''
    head_path = f'{base_folder}/PA_{clean_name}_head' if base_folder and clean_name else ''

    main_pa = _get_mesh_physics_asset(body_mesh) or _get_mesh_physics_asset(full_mesh)
    if main_pa is None and main_path:
        main_pa = _load_existing_asset(main_path, unreal.PhysicsAsset)

    head_pa = _get_mesh_physics_asset(head_mesh)
    if head_pa is None and head_path:
        head_pa = _load_existing_asset(head_path, unreal.PhysicsAsset)

    return {'main_pa': main_pa, 'head_pa': head_pa}


def _has_opaque_glb_bone(glb_path: str, bone_names: set[str]) -> bool | None:
    """Return True/False if GLB image has opaque pixels on `bone_names`, or None if unreadable."""
    import io
    from pathlib import Path
    from mc_model import _read_glb_accessor, read_glb

    path = Path(glb_path)
    if not path.is_file():
        return None
    try:
        g, blob = read_glb(path.read_bytes())
    except Exception:
        return None

    images = g.get('images') or []
    meshes = g.get('meshes') or []
    skins = g.get('skins') or []
    if not images or not meshes or not skins:
        return None

    from PIL import Image
    alpha_cache: dict[int, tuple[int, int, bytes] | None] = {}

    def _get_alpha_image(img_idx: int) -> tuple[int, int, bytes] | None:
        if img_idx in alpha_cache:
            return alpha_cache[img_idx]
        if img_idx < 0 or img_idx >= len(images) or 'bufferView' not in images[img_idx]:
            alpha_cache[img_idx] = None
            return None
        try:
            img_bv = g['bufferViews'][images[img_idx]['bufferView']]
            img_off = img_bv.get('byteOffset', 0)
            img_bytes = blob[img_off:img_off + img_bv['byteLength']]
            with Image.open(io.BytesIO(img_bytes)) as im:
                alpha = im.convert('RGBA').getchannel('A')
                w, h = alpha.size
                res = (w, h, alpha.tobytes()) if w > 0 and h > 0 else None
        except Exception:
            res = None
        alpha_cache[img_idx] = res
        return res

    materials = g.get('materials') or []
    textures = g.get('textures') or []
    node_names = [n.get('name', '') for n in g.get('nodes', [])]
    skin_joints = skins[0].get('joints') or []
    if not skin_joints:
        return None

    saw_bone_tri = False
    for mesh in meshes:
        for prim in mesh.get('primitives', []):
            attrs = prim.get('attributes', {})
            if 'TEXCOORD_0' not in attrs or 'JOINTS_0' not in attrs or 'indices' not in prim:
                continue

            img_idx = 0
            mat_idx = prim.get('material')
            if isinstance(mat_idx, int) and 0 <= mat_idx < len(materials):
                tex_info = (materials[mat_idx].get('pbrMetallicRoughness') or {}).get('baseColorTexture') or {}
                tex_idx = tex_info.get('index')
                if isinstance(tex_idx, int) and 0 <= tex_idx < len(textures):
                    src_idx = textures[tex_idx].get('source')
                    if isinstance(src_idx, int):
                        img_idx = src_idx

            alpha_info = _get_alpha_image(img_idx)
            if alpha_info is None:
                continue
            w, h, alpha_bytes = alpha_info

            try:
                uv_stride, uv_vals = _read_glb_accessor(g, blob, attrs['TEXCOORD_0'])
                j_stride, j_vals = _read_glb_accessor(g, blob, attrs['JOINTS_0'])
                _, idx_vals = _read_glb_accessor(g, blob, prim['indices'])
            except Exception:
                continue

            for t in range(0, len(idx_vals) - 2, 3):
                v0 = int(idx_vals[t])
                b_idx = int(j_vals[v0 * j_stride])
                if b_idx < 0 or b_idx >= len(skin_joints):
                    continue
                node_idx = skin_joints[b_idx]
                if node_idx < 0 or node_idx >= len(node_names):
                    continue
                if node_names[node_idx] not in bone_names:
                    continue
                saw_bone_tri = True
                us = [uv_vals[int(idx_vals[t + k]) * uv_stride] for k in range(3)]
                vs = [uv_vals[int(idx_vals[t + k]) * uv_stride + 1] for k in range(3)]
                u0 = max(0, min(w - 1, int(min(us) * w)))
                u1 = max(u0 + 1, min(w, int(math.ceil(max(us) * w))))
                v0p = max(0, min(h - 1, int(min(vs) * h)))
                v1p = max(v0p + 1, min(h, int(math.ceil(max(vs) * h))))
                for py in range(v0p, v1p):
                    row_off = py * w
                    for px in range(u0, u1):
                        if alpha_bytes[row_off + px] > 10:
                            return True
    return False if saw_bone_tri else None


def _detect_folded_arms(ref_mesh, bounds_records: list[dict]) -> bool:
    """Detect whether a biped with an `arms` bone actually uses folded chest arms (e.g. villager/evoker)."""
    by_name = {rec['bone_name']: rec for rec in bounds_records}
    arms_subtree = _collect_bone_subtree(by_name, 'arms')
    if not any(by_name[n].get('has_bounds') for n in arms_subtree):
        return False
    if 'left_arm' not in by_name or 'right_arm' not in by_name:
        return True

    try:
        imp = ref_mesh.get_editor_property('asset_import_data') if ref_mesh is not None else None
        for src in (imp.extract_filenames() if imp is not None else ()):
            res = _has_opaque_glb_bone(str(src), set(arms_subtree))
            if res is not None:
                return res
    except Exception:
        pass

    import unreal
    tokens = [ref_mesh.get_name()] if ref_mesh is not None else []
    if ref_mesh is not None:
        try:
            tags = unreal.EditorAssetLibrary.get_metadata_tag_values(ref_mesh) or {}
            for key in ('VanillaMobLoader.Entries', 'Mineprep.Model.Recipe', 'VanillaMobLoader.Model'):
                if key in tags:
                    tokens.append(str(tags[key]))
        except Exception:
            pass
    return 'pillager' not in ' '.join(tokens).lower()


def _ensure_single_physics_asset(*, ref_mesh, assign_targets: list[tuple[str, object]],
                                 preferred_pa_path: str, snap_pa,
                                 rebuild_physics: bool, layout_fn, custom_mode: str,
                                 custom_fallback_prefix: str, fail_prefix: str, label: str,
                                 warnings: list[str], dirty_to_save: list):
    import unreal

    target_meshes = [m for _, m in assign_targets]

    def _compatible_with_all(candidate) -> bool:
        return candidate is not None and all(_is_physics_asset_compatible(m, candidate) for m in target_meshes)

    pa = None
    mode = 'reused'
    if not rebuild_physics:
        candidates = [_get_mesh_physics_asset(m) for m in reversed(target_meshes)]
        candidates.extend([snap_pa, _load_existing_asset(preferred_pa_path, unreal.PhysicsAsset)])
        for cand in candidates:
            if _compatible_with_all(cand):
                pa = cand
                break

    if pa is None:
        has_conflict = (not rebuild_physics) and unreal.EditorAssetLibrary.does_asset_exist(preferred_pa_path)
        target_pa_path = _allocate_available_pa_path(preferred_pa_path) if has_conflict else preferred_pa_path
        if has_conflict:
            warnings.append(f'已有不兼容资产 {preferred_pa_path}，已保留原资产并新建 {target_pa_path}')

        if _mineprep_cpp_available():
            try:
                bounds_records = _query_bone_bounds(ref_mesh)
                layout = layout_fn(bounds_records)
                pa = _build_ue_physics_asset_from_layout(
                    ref_mesh, target_pa_path, layout, overwrite=rebuild_physics and not has_conflict
                )
                mode = custom_mode
            except Exception as exc:
                warnings.append(f'{custom_fallback_prefix}: {exc}')
                pa = None
        else:
            warnings.append(f'未检测到 unreal.mineprep C++ 绑定，{label}已回退引擎默认物理资产')

        if pa is None:
            try:
                pa = _fallback_create_physics_asset(
                    ref_mesh, target_pa_path,
                    warnings=warnings, label=label, warn_if_conflict=not has_conflict,
                )
                mode = 'engine_fallback'
            except Exception as exc:
                warnings.append(f'{fail_prefix}: {exc}')
                mode = 'failed'

    if pa is not None:
        for assign_label, mesh in assign_targets:
            if _assign_physics_asset_if_needed(mesh, pa, warnings=warnings, label=assign_label):
                dirty_to_save.append(mesh)
        if mode != 'reused':
            dirty_to_save.append(pa)

    return pa, mode


def ensure_entity_physics(full_mesh, body_mesh=None, head_mesh=None, *,
                          asset_name: str = '', folder: str = '',
                          rig_profile: str | None = None,
                          physics: bool = True, rebuild_physics: bool = False,
                          save: bool = True, pre_reload_snapshot: dict | None = None) -> dict:
    """Ensure PA_<Name> (and PA_<Name>_head if split) exist and are assigned cleanly.

    Policy:
      - `physics=False`: skip creation/assignment and return current references.
      - `rebuild_physics=False`: preserve/restore existing compatible PA (including across reload=True);
        if preferred PA_<Name> exists and is incompatible, keep it untouched and allocate a unique PA path.
      - `rebuild_physics=True`: rebuild custom PA in place at `PA_<Name>` / `PA_<Name>_head`; fallback
        creation preserves existing assets at `PA_<Name>` rather than deleting them.
    """
    warnings: list[str] = []
    if not physics or full_mesh is None:
        return {
            'physics_asset': _get_mesh_physics_asset(body_mesh or full_mesh),
            'head_physics_asset': _get_mesh_physics_asset(head_mesh),
            'warnings': warnings,
            'physics_mode': 'disabled',
        }

    base_name, target_folder = _resolve_base_name_and_folder(folder, asset_name, full_mesh)
    main_pa_path = f'{target_folder}/PA_{base_name}'
    head_pa_path = f'{target_folder}/PA_{base_name}_head'

    snap = pre_reload_snapshot or {}
    dirty_to_save = []

    main_targets = [('完整网格', full_mesh)]
    if body_mesh is not None and body_mesh != full_mesh:
        main_targets.append(('拆分身体', body_mesh))

    is_biped = (rig_profile == 'biped')
    main_layout_fn = (
        (lambda recs: compute_biped_physics_layout(recs, use_folded_arms=_detect_folded_arms(full_mesh, recs)))
        if is_biped else compute_generic_physics_layout
    )
    main_pa, main_mode = _ensure_single_physics_asset(
        ref_mesh=full_mesh,
        assign_targets=main_targets,
        preferred_pa_path=main_pa_path,
        snap_pa=snap.get('main_pa'),
        rebuild_physics=rebuild_physics,
        layout_fn=main_layout_fn,
        custom_mode='custom_biped' if is_biped else 'custom_generic',
        custom_fallback_prefix=(
            f'定制物理资产退回引擎默认生成 ({base_name})'
            if is_biped else f'通用盒体物理资产退回引擎默认生成 ({base_name})'
        ),
        fail_prefix=f'生成物理资产失败 ({base_name})',
        label='身体网格',
        warnings=warnings,
        dirty_to_save=dirty_to_save,
    )

    head_pa = None
    head_mode = 'none'
    if head_mesh is not None:
        head_pa, head_mode = _ensure_single_physics_asset(
            ref_mesh=head_mesh,
            assign_targets=[('拆分头部', head_mesh)],
            preferred_pa_path=head_pa_path,
            snap_pa=snap.get('head_pa'),
            rebuild_physics=rebuild_physics,
            layout_fn=compute_head_physics_layout if is_biped else compute_generic_physics_layout,
            custom_mode='custom_head' if is_biped else 'custom_generic_head',
            custom_fallback_prefix=f'拆分头部物理资产退回默认生成 ({base_name}_head)',
            fail_prefix=f'生成拆分头部物理资产失败 ({base_name}_head)',
            label='拆分头部',
            warnings=warnings,
            dirty_to_save=dirty_to_save,
        )

    if save and dirty_to_save:
        _save_assets(dirty_to_save, warnings)

    return {
        'physics_asset': main_pa,
        'head_physics_asset': head_pa,
        'warnings': warnings,
        'physics_mode': main_mode,
        'head_physics_mode': head_mode,
    }
