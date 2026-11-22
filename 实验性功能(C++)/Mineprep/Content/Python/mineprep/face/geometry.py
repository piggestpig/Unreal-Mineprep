from __future__ import annotations

import copy
import math
import struct
from mineprep.model import (
    _column_major,
    _inverse_rigid,
    _multiply,
    _read_glb_accessor,
    embedded_base_color_surfaces,
    pack_glb,
    read_glb,
)
from .protocol import (
    FACE2D_SLOT,
    FACE3D_CORRECTIVE_MORPHS,
    FACE3D_SLOT,
    FACE_CURVES,
    _BROW_BLINK_FULL_DIP,
    _MOUTH_OPEN_DN,
    _MOUTH_OPEN_UP,
    _MOUTH_PUCKER_V,
    _MOUTH_PUCKER_X,
    _MOUTH_SHIFT_X,
    _MOUTH_SMILE_X,
    _MOUTH_SMILE_Y,
    _MOUTH_WIDE_X,
    _normalize_surfaces,
    normalize_face_mode,
    normalize_face_options,
)


_NORMAL_HINTS = {
    '+x': (1.0, 0.0, 0.0),
    '-x': (-1.0, 0.0, 0.0),
    'front': (1.0, 0.0, 0.0),
    'back': (-1.0, 0.0, 0.0),
    '+y': (0.0, 0.0, 1.0),   # UE +Y (Right) == glTF +Z
    '-y': (0.0, 0.0, -1.0),  # UE -Y (Left)  == glTF -Z
    'right': (0.0, 0.0, 1.0),
    'left': (0.0, 0.0, -1.0),
    '+z': (0.0, 1.0, 0.0),   # UE +Z (Up)    == glTF +Y
    '-z': (0.0, -1.0, 0.0),
    'top': (0.0, 1.0, 0.0),
    'bottom': (0.0, -1.0, 0.0),
}

def _row_major(values):
    return tuple(tuple(float(values[c * 4 + r]) for c in range(4)) for r in range(4))


def _translation_mat(x: float, y: float, z: float):
    return (
        (1.0, 0.0, 0.0, float(x)),
        (0.0, 1.0, 0.0, float(y)),
        (0.0, 0.0, 1.0, float(z)),
        (0.0, 0.0, 0.0, 1.0),
    )


def _add3(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub3(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale3(v, s: float):
    return (v[0] * s, v[1] * s, v[2] * s)


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm3(v):
    length = math.sqrt(_dot(v, v))
    return (v[0] / length, v[1] / length, v[2] / length) if length > 1e-12 else (1.0, 0.0, 0.0)


def _lerp3(a, b, t: float):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _lerp2(a, b, t: float):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _bilerp3(c00, c10, c11, c01, s: float, t: float):
    return _lerp3(_lerp3(c00, c10, s), _lerp3(c01, c11, s), t)


def _read_acc_rows(doc, blob, index):
    n_comp, values = _read_glb_accessor(doc, blob, index)
    return [tuple(values[i:i + n_comp]) for i in range(0, len(values), n_comp)]


# Safe default vertex color: R=1.0 (front/skin), R=0.0 (3D oral cavity -> MouthCavityColor), G/B=0.5, A=1.0 (static)
_COL_STATIC = (1.0, 0.5, 0.5, 1.0)
_COL_CAVITY = (0.0, 0.5, 0.5, 1.0)


class _Vert:
    __slots__ = ('pos', 'nrm', 'uv0', 'uv1', 'color', 'joint', 'morphs')

    def __init__(self, pos, nrm, uv0, uv1, joint, morphs=None, color=_COL_STATIC):
        self.pos = (float(pos[0]), float(pos[1]), float(pos[2]))
        self.nrm = (float(nrm[0]), float(nrm[1]), float(nrm[2]))
        self.uv0 = (float(uv0[0]), float(uv0[1]))
        self.uv1 = (float(uv1[0]), float(uv1[1]))
        self.color = (float(color[0]), float(color[1]), float(color[2]), float(color[3]))
        self.joint = int(joint)
        self.morphs = dict(morphs) if morphs else {}

    def clone(self):
        return _Vert(self.pos, self.nrm, self.uv0, self.uv1, self.joint, self.morphs, self.color)

    def add_morph(self, curve: str, dx: float, dy: float, dz: float):
        prev = self.morphs.get(curve, (0.0, 0.0, 0.0))
        self.morphs[curve] = (prev[0] + dx, prev[1] + dy, prev[2] + dz)


class _FaceSurface:
    """Arbitrary oriented planar face quad with exact local (U_dir, V_dir, N_dir) pixel basis."""

    __slots__ = ('u0', 'v0', 'u1', 'v1', 'c00', 'c10', 'c11', 'c01',
                 'u_dir', 'v_dir', 'n_dir', 'px_u', 'px_v', 'px_avg', 'bone_slot', 'bone_name', 'clean_uv')

    def __init__(self, verts, quad, uv_rect, tw: float, th: float, bone_slot: int, bone_name: str, skin_uv):
        self.u0, self.v0, self.u1, self.v1 = (float(x) for x in uv_rect)
        self.c00, self.c10, self.c11, self.c01 = _ordered_front_corners(verts, quad, uv_rect, tw, th)
        du = max(self.u1 - self.u0, 1e-4)
        dv = max(self.v1 - self.v0, 1e-4)
        u_vec = _sub3(self.c10, self.c00)
        v_vec = _sub3(self.c01, self.c00)
        u_len = math.sqrt(_dot(u_vec, u_vec))
        v_len = math.sqrt(_dot(v_vec, v_vec))
        self.u_dir = _norm3(u_vec)
        self.v_dir = _norm3(v_vec)
        self.n_dir = _norm3(quad['nrm'])
        self.px_u = u_len / du
        self.px_v = v_len / dv
        self.px_avg = 0.5 * (self.px_u + self.px_v)
        self.bone_slot = bone_slot
        self.bone_name = bone_name
        self.clean_uv = ((float(skin_uv[0]) + 0.5) / tw, (float(skin_uv[1]) + 0.5) / th)

    def pos_at(self, u_px: float, v_px: float, depth_m: float = 0.0):
        s = (u_px - self.u0) / max(self.u1 - self.u0, 1e-4)
        t = (v_px - self.v0) / max(self.v1 - self.v0, 1e-4)
        p = _bilerp3(self.c00, self.c10, self.c11, self.c01, s, t)
        if depth_m != 0.0:
            p = _add3(p, _scale3(self.n_dir, depth_m))
        return p

    def clamp_u(self, u_val: float, margin: float = 0.005) -> float:
        return max(self.u0 + margin, min(self.u1 - margin, u_val))

    def clamp_v(self, v_val: float, margin: float = 0.005) -> float:
        return max(self.v0 + margin, min(self.v1 - margin, v_val))

    def px_vec(self, du_px: float = 0.0, dv_px: float = 0.0, dn_px: float = 0.0):
        return (
            du_px * self.px_u * self.u_dir[0] + dv_px * self.px_v * self.v_dir[0] + dn_px * self.px_avg * self.n_dir[0],
            du_px * self.px_u * self.u_dir[1] + dv_px * self.px_v * self.v_dir[1] + dn_px * self.px_avg * self.n_dir[1],
            du_px * self.px_u * self.u_dir[2] + dv_px * self.px_v * self.v_dir[2] + dn_px * self.px_avg * self.n_dir[2],
        )

    def add_px_morph(self, vtx: _Vert, curve: str, du_px: float = 0.0, dv_px: float = 0.0, dn_px: float = 0.0):
        vtx.add_morph(curve, *self.px_vec(du_px, dv_px, dn_px))

    def add_rot_morph(self, vtx: _Vert, curve: str, pivot, angle_rad: float, *, sq_curve: str | None = None):
        """Rotate `vtx.pos` rigidly around `pivot` in this surface's (U_dir, V_dir) plane (axis = N_dir).

        Splits exact rotation into symmetric odd tangent (`curve`, linear in weight `w`) plus even radial
        pullback (`sq_curve`, driven by `w^2` in `CR_MineprepFace3DSolver`), eliminating inward ballooning
        and keeping length/thickness strictly invariant at both `w = +1` and `w = -1`.
        """
        rel = _sub3(vtx.pos, pivot)
        su = _dot(rel, self.u_dir)
        sv = _dot(rel, self.v_dir)
        ca, sa = math.cos(angle_rad), math.sin(angle_rad)
        # Positive angle lifts inner +U end upward (-V_dir) on right brow, matching legacy +X sign.
        dsu = sv * sa
        dsv = -su * sa
        vtx.add_morph(
            curve,
            dsu * self.u_dir[0] + dsv * self.v_dir[0],
            dsu * self.u_dir[1] + dsv * self.v_dir[1],
            dsu * self.u_dir[2] + dsv * self.v_dir[2],
        )
        if sq_curve:
            c1 = ca - 1.0
            qsu, qsv = su * c1, sv * c1
            vtx.add_morph(
                sq_curve,
                qsu * self.u_dir[0] + qsv * self.v_dir[0],
                qsu * self.u_dir[1] + qsv * self.v_dir[1],
                qsu * self.u_dir[2] + qsv * self.v_dir[2],
            )

    def ue_uv_gradients(self, tw: float, th: float):
        """Return (FaceU_Grad, FaceV_Grad) in UE cm-space (UV units per cm) for UVSlideMode=1."""
        # glTF (x, y, z) meters -> UE (x, z, y) cm; 1 m = 100 cm
        u_ue = (self.u_dir[0], self.u_dir[2], self.u_dir[1])
        v_ue = (self.v_dir[0], self.v_dir[2], self.v_dir[1])
        u_scale = 1.0 / max(self.px_u * 100.0 * tw, 1e-6)
        v_scale = 1.0 / max(self.px_v * 100.0 * th, 1e-6)
        return _scale3(u_ue, u_scale), _scale3(v_ue, v_scale)


def _detect_winding_sign(verts, tris) -> float:
    for a, b, c, _ in tris:
        cr = _cross(_sub3(verts[b].pos, verts[a].pos), _sub3(verts[c].pos, verts[a].pos))
        d = _dot(cr, verts[a].nrm)
        if abs(d) > 1e-9:
            return 1.0 if d > 0.0 else -1.0
    return 1.0


def _emit_quad(verts_list, tris_list, v0, v1, v2, v3, mat_name: str, wind_sign: float):
    base = len(verts_list)
    verts_list.extend((v0, v1, v2, v3))
    cr = _cross(_sub3(v1.pos, v0.pos), _sub3(v2.pos, v0.pos))
    if _dot(cr, v0.nrm) * wind_sign >= 0.0:
        tris_list.append((base, base + 1, base + 2, mat_name))
        tris_list.append((base, base + 2, base + 3, mat_name))
    else:
        tris_list.append((base, base + 2, base + 1, mat_name))
        tris_list.append((base, base + 3, base + 2, mat_name))


def _group_bone_quads(verts, tris, joint_slot: int):
    """Group co-planar triangle pairs sharing 4 vertices on `joint_slot` into quads."""
    by_vset = {}
    for ti, (a, b, c, mat) in enumerate(tris):
        if verts[a].joint != joint_slot or verts[b].joint != joint_slot or verts[c].joint != joint_slot:
            continue
        nrm = verts[a].nrm
        matched = None
        for key, item in by_vset.items():
            if len(item['tris']) == 1 and item['mat'] == mat and len(item['vset'] | {a, b, c}) == 4:
                if _dot(item['nrm'], nrm) > 0.99:
                    matched = key
                    break
        if matched is not None:
            by_vset[matched]['tris'].append(ti)
            by_vset[matched]['vset'].update((a, b, c))
        else:
            by_vset[ti] = {'tris': [ti], 'vset': {a, b, c}, 'nrm': nrm, 'mat': mat}
    quads = []
    for item in by_vset.values():
        if len(item['vset']) == 4 and len(item['tris']) == 2:
            vs = sorted(item['vset'])
            pts = [verts[v].pos for v in vs]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            zs = [p[2] for p in pts]
            quads.append({
                'tris': item['tris'],
                'verts': vs,
                'nrm': _norm3(item['nrm']),
                'mat': item['mat'],
                'min': (min(xs), min(ys), min(zs)),
                'max': (max(xs), max(ys), max(zs)),
                'center': (0.25 * sum(xs), 0.25 * sum(ys), 0.25 * sum(zs)),
            })
    return quads


def _reconstruct_cuboids(verts, quads):
    """Reconstruct oriented or axis-aligned 6-face cuboids by pairing opposite-normal quads."""
    # Group quads into connected components by shared vertex positions (handles arbitrary tilt!)
    tol = 3e-4
    q_pts = [[verts[vi].pos for vi in q['verts']] for q in quads]

    def share_corner(pa, pb):
        return any(
            abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol and abs(a[2] - b[2]) <= tol
            for a in pa for b in pb
        )

    # First try clean axis-aligned pairing (exact for merged overlapping boxes like wolf snout/head)
    pos_x = [q for q in quads if q['nrm'][0] > 0.9]
    neg_x = [q for q in quads if q['nrm'][0] < -0.9]
    used_neg = set()
    cuboids = []
    for pq in pos_x:
        y0, z0, y1, z1 = pq['min'][1], pq['min'][2], pq['max'][1], pq['max'][2]
        partner = None
        for ni, nq in enumerate(neg_x):
            if ni in used_neg:
                continue
            if (abs(nq['min'][1] - y0) <= tol and abs(nq['max'][1] - y1) <= tol
                    and abs(nq['min'][2] - z0) <= tol and abs(nq['max'][2] - z1) <= tol
                    and nq['min'][0] < pq['max'][0] - tol):
                partner = (ni, nq)
                break
        if partner is None:
            continue
        used_neg.add(partner[0])
        x0, x1 = partner[1]['min'][0], pq['max'][0]
        members = []
        for q in quads:
            mn, mx = q['min'], q['max']
            if (mn[0] >= x0 - tol and mx[0] <= x1 + tol
                    and mn[1] >= y0 - tol and mx[1] <= y1 + tol
                    and mn[2] >= z0 - tol and mx[2] <= z1 + tol):
                on_bound = (
                    (abs(mn[0] - x0) <= tol and abs(mx[0] - x0) <= tol)
                    or (abs(mn[0] - x1) <= tol and abs(mx[0] - x1) <= tol)
                    or (abs(mn[1] - y0) <= tol and abs(mx[1] - y0) <= tol)
                    or (abs(mn[1] - y1) <= tol and abs(mx[1] - y1) <= tol)
                    or (abs(mn[2] - z0) <= tol and abs(mx[2] - z0) <= tol)
                    or (abs(mn[2] - z1) <= tol and abs(mx[2] - z1) <= tol)
                )
                if on_bound:
                    members.append(q)
        cuboids.append({'min': (x0, y0, z0), 'max': (x1, y1, z1), 'plus_x': pq, 'quads': members})

    if cuboids:
        return cuboids

    # Fallback for tilted cuboids: group 6 connected faces sharing corners
    visited = set()
    for i in range(len(quads)):
        if i in visited:
            continue
        comp = []
        stack = [i]
        visited.add(i)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for j in range(len(quads)):
                if j not in visited and share_corner(q_pts[cur], q_pts[j]):
                    visited.add(j)
                    stack.append(j)
        members = [quads[idx] for idx in comp]
        front = max(members, key=lambda q: q['nrm'][0])
        xs = [p[0] for idx in comp for p in q_pts[idx]]
        ys = [p[1] for idx in comp for p in q_pts[idx]]
        zs = [p[2] for idx in comp for p in q_pts[idx]]
        cuboids.append({
            'min': (min(xs), min(ys), min(zs)),
            'max': (max(xs), max(ys), max(zs)),
            'plus_x': front,
            'quads': members,
        })
    return cuboids


def _quad_uv_px_bounds(verts, quad, tw: float, th: float):
    us = [verts[v].uv0[0] * tw for v in quad['verts']]
    vs = [verts[v].uv0[1] * th for v in quad['verts']]
    return (min(us), min(vs), max(us), max(vs))


def _rect_matches(actual, expected, tol: float = 0.15) -> bool:
    return all(abs(float(a) - float(b)) <= tol for a, b in zip(actual, expected))


def _ordered_front_corners(verts, quad, rect_uv, tw: float, th: float):
    """Return (c00, c10, c11, c01) positions corresponding to (u0,v0), (u1,v0), (u1,v1), (u0,v1)."""
    u0, v0, u1, v1 = (float(x) for x in rect_uv)
    out = []
    for tu, tv in ((u0, v0), (u1, v0), (u1, v1), (u0, v1)):
        best = min(
            quad['verts'],
            key=lambda vi: (verts[vi].uv0[0] * tw - tu) ** 2 + (verts[vi].uv0[1] * th - tv) ** 2,
        )
        out.append(verts[best].pos)
    return tuple(out)


def _find_matching_quad(verts, quads, uv_rect, tw: float, th: float, normal_hint=None):
    """Match a quad by UV bounds first, breaking ties with optional `normal_hint`."""
    candidates = [q for q in quads if _rect_matches(_quad_uv_px_bounds(verts, q, tw, th), uv_rect)]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    hint_vec = None
    if isinstance(normal_hint, str):
        hint_vec = _NORMAL_HINTS.get(normal_hint.strip().lower())
    elif isinstance(normal_hint, (list, tuple)) and len(normal_hint) == 3:
        hint_vec = _norm3(tuple(float(x) for x in normal_hint))
    if hint_vec is not None:
        return max(candidates, key=lambda q: _dot(q['nrm'], hint_vec))
    return max(candidates, key=lambda q: q['nrm'][0])


def _mouth_morph_px(r_idx: int, c_idx: int, col_u, segs: int, mc_u: float, half_w: float):
    """Return (xn, signed_w_ring, {curve: (du_px, dv_px)}) in face-local pixel coordinates.

    Only the inner mouth opening rim (`r_idx in (2, 3)`) deforms; outer rows (`0, 1, 4, 5`) stay
    100% static so the surrounding nose, cheeks, beard border, and chin never arch or stretch.
    """
    if r_idx not in (2, 3) or c_idx in (0, segs + 2):
        return 0.0, 0.0, {}
    xn = max(-1.0, min(1.0, (col_u[c_idx] - mc_u) / max(half_w, 0.5)))
    arch = max(0.22, 1.0 - 0.70 * xn * xn)
    w_mag = 1.0
    sw = 1.0 if r_idx == 2 else -1.0
    open_dv = (-_MOUTH_OPEN_UP if sw >= 0.0 else _MOUTH_OPEN_DN) * arch * w_mag
    pucker_dv = (_MOUTH_PUCKER_V if sw >= 0.0 else -_MOUTH_PUCKER_V) * w_mag
    deltas = {
        'face_mouth_open': (0.0, open_dv),
        '_mc_mouth_neg_cancel': (-xn * _MOUTH_PUCKER_X * w_mag, open_dv + pucker_dv),
        'face_mouth_wide': (xn * _MOUTH_WIDE_X * w_mag, 0.0),
        'face_mouth_smile': (xn * _MOUTH_SMILE_X * w_mag, -(xn * xn - 0.25) * _MOUTH_SMILE_Y * w_mag),
        'face_mouth_x': (_MOUTH_SHIFT_X * w_mag, 0.0),
    }
    return xn, sw, deltas


def _encode_slide_color(xn: float, sw: float) -> tuple[float, float, float, float]:
    """Encode (R=1.0, G=xn, B=signed_w, A=0.0 -> slide=1.0) into linear COLOR_0."""
    return (1.0, 0.5 * (max(-1.0, min(1.0, xn)) + 1.0), 0.5 * (max(-1.0, min(1.0, sw)) + 1.0), 0.0)


# ---------------------------------------------------------------------------
# Main GLB Upgrader (2D & Bone-Invariant 3D Solution A)
# ---------------------------------------------------------------------------

def upgrade_face_glb(data: bytes, spec: dict, *, mode: str = '2d', options: dict | None = None) -> bytes:
    """Upgrade a rigid-skinned GLB (full-body or split-head) with 2D or 3D facial geometry & Morphs."""
    mode = normalize_face_mode(mode)
    if mode == 'none':
        return data
    if mode == '3d' and not spec.get('supports_3d', False):
        raise ValueError('该生物当前仅支持 2d 表情模式，请使用 face="2d"')
    opts = normalize_face_options(options)

    doc, blob = read_glb(data)
    doc = copy.deepcopy(doc)
    nodes = doc['nodes']
    skin = doc['skins'][0]
    joints = list(skin['joints'])
    joint_by_name = {nodes[n]['name']: slot for slot, n in enumerate(joints)}
    parents = {child: idx for idx in joints for child in nodes[idx].get('children', ())}
    worlds = {}

    def world_of(node_idx):
        if node_idx not in worlds:
            local = _row_major(nodes[node_idx]['matrix']) if 'matrix' in nodes[node_idx] else _translation_mat(0.0, 0.0, 0.0)
            worlds[node_idx] = _multiply(world_of(parents[node_idx]), local) if node_idx in parents else local
        return worlds[node_idx]

    for n in joints:
        world_of(n)

    def ensure_joint(name: str, parent_name: str, world_pivot_gltf: tuple[float, float, float]) -> int:
        if name in joint_by_name:
            return joint_by_name[name]
        parent_slot = joint_by_name[parent_name]
        parent_node = joints[parent_slot]
        w_mat = _translation_mat(*world_pivot_gltf)
        local_mat = _multiply(_inverse_rigid(world_of(parent_node)), w_mat)
        node_idx = len(nodes)
        nodes.append({'name': name, 'matrix': _column_major(local_mat)})
        nodes[parent_node].setdefault('children', []).append(node_idx)
        parents[node_idx] = parent_node
        worlds[node_idx] = w_mat
        slot = len(joints)
        joints.append(node_idx)
        joint_by_name[name] = slot
        return slot

    head_bone = spec.get('head_bone', 'head')
    if head_bone not in joint_by_name:
        raise ValueError(f'模型缺少面部宿主骨骼: {head_bone}')

    tw, th = (float(spec['tex_size'][0]), float(spec['tex_size'][1]))
    mat_names = [m.get('name', f'Mat_{i}') for i, m in enumerate(doc.get('materials', ()))] or ['Skin']
    primary_mat = mat_names[0]

    verts: list[_Vert] = []
    tris: list[tuple[int, int, int, str]] = []
    for mesh in doc['meshes']:
        for prim in mesh['primitives']:
            attrs = prim['attributes']
            pos_rows = _read_acc_rows(doc, blob, attrs['POSITION'])
            nrm_rows = _read_acc_rows(doc, blob, attrs['NORMAL'])
            uv0_rows = _read_acc_rows(doc, blob, attrs['TEXCOORD_0'])
            uv1_rows = _read_acc_rows(doc, blob, attrs['TEXCOORD_1']) if 'TEXCOORD_1' in attrs else uv0_rows
            j_rows = _read_acc_rows(doc, blob, attrs['JOINTS_0'])
            w_rows = _read_acc_rows(doc, blob, attrs['WEIGHTS_0'])
            idx_rows = _read_acc_rows(doc, blob, prim['indices'])
            mname = mat_names[prim.get('material', 0)]
            base_v = len(verts)
            for p, n, u0, u1, j, w in zip(pos_rows, nrm_rows, uv0_rows, uv1_rows, j_rows, w_rows):
                best_k = max(range(min(len(j), len(w))), key=lambda k: w[k])
                verts.append(_Vert(p, n, u0, u1, int(j[best_k])))
            for k in range(0, len(idx_rows), 3):
                tris.append((
                    base_v + int(idx_rows[k][0]),
                    base_v + int(idx_rows[k + 1][0]),
                    base_v + int(idx_rows[k + 2][0]),
                    mname,
                ))

    wind_sign = _detect_winding_sign(verts, tris)

    # 1. Promote merged cuboids (e.g. wolf/pig/cat/cow snout -> nose, ears -> ear_l/ear_r)
    for rule in spec.get('promote_cuboids', ()):
        src_bone = rule['source_bone']
        if src_bone not in joint_by_name:
            continue
        src_slot = joint_by_name[src_bone]
        quads = _group_bone_quads(verts, tris, src_slot)
        for cub in _reconstruct_cuboids(verts, quads):
            uv_px = _quad_uv_px_bounds(verts, cub['plus_x'], tw, th)
            if not _rect_matches(uv_px, rule['plus_x_uv']):
                continue
            mn, mx = cub['min'], cub['max']
            mid_z = 0.5 * (mn[2] + mx[2])  # glTF Z == UE Y (Right > 0, Left < 0)
            side = rule.get('side_y')
            if side == 'positive' and mid_z <= 0.0:
                continue
            if side == 'negative' and mid_z >= 0.0:
                continue
            anchor = rule.get('pivot_anchor', 'center')
            if anchor == 'back_center':
                piv = (mn[0], 0.5 * (mn[1] + mx[1]), mid_z)
            elif anchor == 'bottom_center':
                piv = (0.5 * (mn[0] + mx[0]), mn[1], mid_z)
            else:
                piv = (0.5 * (mn[0] + mx[0]), 0.5 * (mn[1] + mx[1]), mid_z)
            dst_slot = ensure_joint(rule['target_bone'], src_bone, piv)
            for q in cub['quads']:
                for vi in q['verts']:
                    verts[vi].joint = dst_slot

    # 2. Split 3D visor eyebrows (e.g. breeze outer visor box along symmetry plane glTF Z = 0)
    visor_cfg = spec.get('split_visor_brows')
    if visor_cfg:
        v_uv = visor_cfg['front_uv']
        removed_tris = set()
        for bname in visor_cfg.get('bones', ()):
            if bname not in joint_by_name:
                continue
            bslot = joint_by_name[bname]
            for cub in _reconstruct_cuboids(verts, _group_bone_quads(verts, tris, bslot)):
                if not _rect_matches(_quad_uv_px_bounds(verts, cub['plus_x'], tw, th), v_uv):
                    continue
                mn, mx = cub['min'], cub['max']
                split_z = 0.5 * (mn[2] + mx[2])
                ensure_joint('face_root', head_bone, (mx[0], 0.5 * (mn[1] + mx[1]), split_z))
                piv_r = (0.5 * (mn[0] + mx[0]), 0.5 * (mn[1] + mx[1]), split_z + 0.25 * (mx[2] - split_z))
                piv_l = (0.5 * (mn[0] + mx[0]), 0.5 * (mn[1] + mx[1]), split_z + 0.25 * (mn[2] - split_z))
                slot_r = ensure_joint('brow_r', 'face_root', piv_r)
                slot_l = ensure_joint('brow_l', 'face_root', piv_l)

                def apply_visor_morphs(v: _Vert, is_right: bool):
                    pivot = piv_r if is_right else piv_l
                    side = 'r' if is_right else 'l'
                    v.add_morph(f'face_brow_y_{side}', 0.0, 0.0625, 0.0)
                    ang = math.radians(18.0) * (1.0 if is_right else -1.0)
                    ca, sa = math.cos(ang), math.sin(ang)
                    dy, dz = v.pos[1] - pivot[1], v.pos[2] - pivot[2]
                    v.add_morph(f'face_brow_rot_{side}', 0.0, -dz * sa, dy * sa)
                    c1 = ca - 1.0
                    v.add_morph(f'_mc_brow_rot_sq_{side}', 0.0, dy * c1, dz * c1)

                for q in cub['quads']:
                    removed_tris.update(q['tris'])
                    qmat = q['mat']
                    zs = [verts[vi].pos[2] for vi in q['verts']]
                    if min(zs) >= split_z - 1e-5:
                        clones = [verts[vi].clone() for vi in q['verts']]
                        for cv in clones:
                            cv.joint = slot_r
                            apply_visor_morphs(cv, True)
                        base = len(verts)
                        verts.extend(clones)
                        local_map = {old: base + k for k, old in enumerate(q['verts'])}
                        for ti in q['tris']:
                            ta, tb, tc, _ = tris[ti]
                            tris.append((local_map[ta], local_map[tb], local_map[tc], qmat))
                    elif max(zs) <= split_z + 1e-5:
                        clones = [verts[vi].clone() for vi in q['verts']]
                        for cv in clones:
                            cv.joint = slot_l
                            apply_visor_morphs(cv, False)
                        base = len(verts)
                        verts.extend(clones)
                        local_map = {old: base + k for k, old in enumerate(q['verts'])}
                        for ti in q['tris']:
                            ta, tb, tc, _ = tris[ti]
                            tris.append((local_map[ta], local_map[tb], local_map[tc], qmat))
                    else:
                        vs = [verts[vi] for vi in q['verts']]
                        pos_vs = sorted([v for v in vs if v.pos[2] > split_z], key=lambda v: (v.pos[0], v.pos[1]))
                        neg_vs = sorted([v for v in vs if v.pos[2] < split_z], key=lambda v: (v.pos[0], v.pos[1]))
                        if len(pos_vs) == 2 and len(neg_vs) == 2:
                            mids = []
                            for pv, nv in zip(pos_vs, neg_vs):
                                t = (pv.pos[2] - split_z) / (pv.pos[2] - nv.pos[2])
                                mids.append(_Vert(
                                    _lerp3(pv.pos, nv.pos, t), pv.nrm,
                                    _lerp2(pv.uv0, nv.uv0, t), _lerp2(pv.uv1, nv.uv1, t), slot_r,
                                ))
                            r_verts = [pos_vs[0].clone(), pos_vs[1].clone(), mids[1].clone(), mids[0].clone()]
                            for rv in r_verts:
                                rv.joint = slot_r
                                apply_visor_morphs(rv, True)
                            _emit_quad(verts, tris, *r_verts, qmat, wind_sign)

                            l_verts = [mids[0].clone(), mids[1].clone(), neg_vs[1].clone(), neg_vs[0].clone()]
                            for lv in l_verts:
                                lv.joint = slot_l
                                apply_visor_morphs(lv, False)
                            _emit_quad(verts, tris, *l_verts, qmat, wind_sign)
        if removed_tris:
            tris = [t for i, t in enumerate(tris) if i not in removed_tris]

    # 3. Drop duplicate overlaid front quads if configured (e.g. breeze `eyes` inner quad)
    drop_bones = {joint_by_name[b] for b in spec.get('drop_duplicate_front_bones', ()) if b in joint_by_name}
    if drop_bones and spec.get('front_uv'):
        drop_tris = set()
        for dslot in drop_bones:
            for q in _group_bone_quads(verts, tris, dslot):
                if _rect_matches(_quad_uv_px_bounds(verts, q, tw, th), spec['front_uv']):
                    drop_tris.update(q['tris'])
        if drop_tris:
            tris = [t for i, t in enumerate(tris) if i not in drop_tris]

    # 4. Locate all configured face surface quads across arbitrary orientations & host bones
    surface_defs = _normalize_surfaces(spec)
    matched_surfaces: list[tuple[dict, _FaceSurface]] = []
    remove_face_tris = set()
    quad_cache: dict[int, list] = {}
    for sdef in surface_defs:
        bname = sdef['bone']
        if bname not in joint_by_name:
            raise ValueError(f'模型缺少面部宿主骨骼: {bname}')
        bslot = joint_by_name[bname]
        if bslot not in quad_cache:
            quad_cache[bslot] = _group_bone_quads(verts, tris, bslot)
        fquad = _find_matching_quad(verts, quad_cache[bslot], sdef['uv'], tw, th, sdef.get('normal'))
        if fquad is None:
            raise ValueError(f"{bname}: 找不到匹配 {sdef['uv']} 的面部网格片")
        remove_face_tris.update(fquad['tris'])
        matched_surfaces.append((sdef, _FaceSurface(verts, fquad, sdef['uv'], tw, th, bslot, bname, sdef['skin_uv'])))

    tris = [t for i, t in enumerate(tris) if i not in remove_face_tris]

    def in_rect(u_val: float, v_val: float, rect) -> bool:
        return rect[0] <= u_val <= rect[2] and rect[1] <= v_val <= rect[3]

    if mode == '2d':
        for sdef, surf in matched_surfaces:
            erase_rects = list(sdef['erase_rects'])
            for side in sdef['eyes']:
                if spec.get(f'eye_{side}'):
                    erase_rects.append(spec[f'eye_{side}'])
            if sdef['use_brows'] and spec.get('use_brows') and spec.get('brow_l') and spec.get('brow_r'):
                erase_rects.extend((spec['brow_l'], spec['brow_r']))
            mouth_rect = spec['mouth'] if (sdef['use_mouth'] and spec.get('mouth')) else None
            if mouth_rect:
                erase_rects.append(mouth_rect)

            u0, v0, u1, v1 = surf.u0, surf.v0, surf.u1, surf.v1
            extra_us = ()
            extra_vs = ()
            if mouth_rect:
                mx0, my0, mx1, my1 = (float(x) for x in mouth_rect)
                mc_u = 0.5 * (mx0 + mx1)
                extra_us = (max(u0, min(u1, mc_u)),)
                extra_vs = tuple(float(rv) for rv in range(int(math.ceil(my0)), int(math.floor(my1)) + 1) if v0 < rv < v1)
            us = sorted({u0, u1, *extra_us, *(max(u0, min(u1, float(r[0]))) for r in erase_rects),
                         *(max(u0, min(u1, float(r[2]))) for r in erase_rects)})
            vs = sorted({v0, v1, *extra_vs, *(max(v0, min(v1, float(r[1]))) for r in erase_rects),
                         *(max(v0, min(v1, float(r[3]))) for r in erase_rects)})
            for ia in range(len(us) - 1):
                ua, ub = us[ia], us[ia + 1]
                if ub - ua <= 1e-5:
                    continue
                for ib in range(len(vs) - 1):
                    va, vb = vs[ib], vs[ib + 1]
                    if vb - va <= 1e-5:
                        continue
                    cu, cv = 0.5 * (ua + ub), 0.5 * (va + vb)
                    in_mouth = bool(mouth_rect and in_rect(cu, cv, mouth_rect))
                    erased = in_mouth or any(in_rect(cu, cv, r) for r in erase_rects)
                    if in_mouth:
                        # Sample mouth-adjacent left/right pixels (e.g. Steve's dark beard, Alex's chin)
                        left_u = (mx0 - 0.5) if (mx0 - 1.0 >= u0 - 1e-4) else (u0 + 0.5)
                        right_u = (mx1 + 0.5) if (mx1 + 1.0 <= u1 + 1e-4) else (u1 - 0.5)
                        bg_v = min(v1 - 0.5, max(v0 + 0.5, math.floor(cv) + 0.5))
                        fill_uv = ((left_u if cu < mc_u else right_u) / tw, bg_v / th)
                    else:
                        fill_uv = surf.clean_uv
                    corners_uv = ((ua / tw, va / th), (ub / tw, va / th), (ub / tw, vb / th), (ua / tw, vb / th))
                    corners_pos = (surf.pos_at(ua, va), surf.pos_at(ub, va), surf.pos_at(ub, vb), surf.pos_at(ua, vb))
                    qverts = [
                        _Vert(p, surf.n_dir, uv_i, fill_uv if erased else uv_i, surf.bone_slot)
                        for p, uv_i in zip(corners_pos, corners_uv)
                    ]
                    _emit_quad(verts, tris, *qverts, FACE2D_SLOT, wind_sign)
    else:
        # 3D Mode (Bone-Invariant Analytic Solution A):
        # - ONLY 1 UV channel (`TEXCOORD_0`), zero extra UV channels.
        # - `COLOR_0` encodes `(R=cavity_shade, G=xn, B=signed_w, A=1.0 static / 0.0 slide)`.
        # - Every face uses its exact local (U_dir, V_dir, N_dir) basis -> works on +X, ±Y, and tilted heads!
        head_slot = joint_by_name[head_bone]
        head_node_idx = joints[head_slot]
        head_subtree_nodes = {head_node_idx}
        stack = list(nodes[head_node_idx].get('children', ()))
        while stack:
            nid = stack.pop()
            head_subtree_nodes.add(nid)
            stack.extend(nodes[nid].get('children', ()))
        head_subtree_slots = {slot for slot, nid in enumerate(joints) if nid in head_subtree_nodes}
        for vtx in verts:
            vtx.color = _COL_STATIC
        tris = [
            (a, b, c, FACE3D_SLOT if (verts[a].joint in head_subtree_slots and m == primary_mat) else m)
            for a, b, c, m in tris
        ]

        # Create `face_root` at the midpoint of all face surfaces
        centers = [surf.pos_at(0.5 * (surf.u0 + surf.u1), 0.5 * (surf.v0 + surf.v1)) for _, surf in matched_surfaces]
        face_center = tuple(sum(c[i] for c in centers) / len(centers) for i in range(3))
        ensure_joint('face_root', head_bone, face_center)

        use_teeth = bool(opts.get('use_teeth', False))
        brow_blink_follow = bool(opts.get('brow_blink_follow', False))
        z0_zero = (0.0, 0.0)
        first_sclera_uv = matched_surfaces[0][1].clean_uv

        def emit_recess_walls(surf: _FaceSurface, rx0, ry0, rx1, ry1, depth, slot_id, wall_uv, *, eye_wide_up: float = 0.0):
            d_collar = -min(0.0005, 0.25 * depth)
            pad = 0.03
            ax0 = surf.clamp_u(rx0 - pad) if rx0 <= surf.u0 + 0.05 else rx0 - pad
            ax1 = surf.clamp_u(rx1 + pad) if rx1 >= surf.u1 - 0.05 else rx1 + pad
            ay0 = surf.clamp_v(ry0 - pad) if ry0 <= surf.v0 + 0.05 else ry0 - pad
            ay1 = surf.clamp_v(ry1 + pad) if ry1 >= surf.v1 - 0.05 else ry1 + pad
            f00, f10 = surf.pos_at(ax0, ay0, d_collar), surf.pos_at(ax1, ay0, d_collar)
            f11, f01 = surf.pos_at(ax1, ay1, d_collar), surf.pos_at(ax0, ay1, d_collar)
            b00, b10 = surf.pos_at(ax0, ay0, -depth), surf.pos_at(ax1, ay0, -depth)
            b11, b01 = surf.pos_at(ax1, ay1, -depth), surf.pos_at(ax0, ay1, -depth)
            n_top, n_bot = surf.v_dir, _scale3(surf.v_dir, -1.0)
            n_u0, n_u1 = surf.u_dir, _scale3(surf.u_dir, -1.0)
            top_vs = [_Vert(p, n_top, wall_uv, z0_zero, slot_id) for p in (f00, f10, b10, b00)]
            bot_vs = [_Vert(p, n_bot, wall_uv, z0_zero, slot_id) for p in (b01, b11, f11, f01)]
            u0_vs = [_Vert(p, n_u0, wall_uv, z0_zero, slot_id) for p in (b00, b01, f01, f00)]
            u1_vs = [_Vert(p, n_u1, wall_uv, z0_zero, slot_id) for p in (f10, f11, b11, b10)]
            if eye_wide_up > 1e-4:
                # Driven by `_mc_eye_wide_pos = max(face_eye_wide, 0)` so walls ONLY lift when widening
                # and stay 100% rigid during squints (`face_eye_wide < 0`).
                for vtx in (*top_vs, u0_vs[0], u0_vs[3], u1_vs[0], u1_vs[3]):
                    surf.add_px_morph(vtx, '_mc_eye_wide_pos', dv_px=-eye_wide_up)
            _emit_quad(verts, tris, *top_vs, FACE3D_SLOT, wind_sign)
            _emit_quad(verts, tris, *bot_vs, FACE3D_SLOT, wind_sign)
            _emit_quad(verts, tris, *u0_vs, FACE3D_SLOT, wind_sign)
            _emit_quad(verts, tris, *u1_vs, FACE3D_SLOT, wind_sign)

        def emit_3d_brows(surf: _FaceSurface):
            if not (spec.get('brow_l') and spec.get('brow_r')):
                return
            brow_thick = opts['brow_thickness'] * surf.px_avg
            brow_h_px = opts['brow_height']
            bl_raw = [float(x) for x in spec['brow_l']]
            br_raw = [float(x) for x in spec['brow_r']]
            is_unibrow = bool(spec.get('use_brows') and abs(bl_raw[0] - br_raw[2]) < 0.15)
            eye_top_v = min(float(spec['eye_l'][1]), float(spec['eye_r'][1]))
            if brow_thick <= 1e-5:
                for side, raw_b in (('l', bl_raw), ('r', br_raw)):
                    ensure_joint(f'brow_{side}', 'face_root', surf.pos_at(0.5 * (raw_b[0] + raw_b[2]), 0.5 * (raw_b[1] + raw_b[3])))
                return

            brow_src_uv = spec.get('brow_3d_uv')
            n_top, n_bot = _scale3(surf.v_dir, -1.0), surf.v_dir
            n_u0, n_u1 = _scale3(surf.u_dir, -1.0), surf.u_dir
            sh_eye_ref = max(0.5, 0.5 * ((float(spec['eye_l'][3]) - float(spec['eye_l'][1]))
                                         + (float(spec['eye_r'][3]) - float(spec['eye_r'][1]))))
            brow_wide_up = min(0.45 * sh_eye_ref, max(0.0, eye_top_v - surf.v0 - 0.15))

            def emit_brow_box(bx0, by0, bx1, by1, uv_rect, bslot, *, omit_inner_cap=None):
                uv_a = (float(uv_rect[0]) / tw, float(uv_rect[1]) / th)
                uv_b = (float(uv_rect[2]) / tw, float(uv_rect[1]) / th)
                uv_c = (float(uv_rect[2]) / tw, float(uv_rect[3]) / th)
                uv_d = (float(uv_rect[0]) / tw, float(uv_rect[3]) / th)
                f00, f10 = surf.pos_at(bx0, by0, brow_thick), surf.pos_at(bx1, by0, brow_thick)
                f11, f01 = surf.pos_at(bx1, by1, brow_thick), surf.pos_at(bx0, by1, brow_thick)
                k00, k10 = surf.pos_at(bx0, by0, 0.0), surf.pos_at(bx1, by0, 0.0)
                k11, k01 = surf.pos_at(bx1, by1, 0.0), surf.pos_at(bx0, by1, 0.0)
                s_idx = len(verts)
                _emit_quad(verts, tris, _Vert(f00, surf.n_dir, uv_a, z0_zero, bslot), _Vert(f10, surf.n_dir, uv_b, z0_zero, bslot),
                           _Vert(f11, surf.n_dir, uv_c, z0_zero, bslot), _Vert(f01, surf.n_dir, uv_d, z0_zero, bslot), FACE3D_SLOT, wind_sign)
                _emit_quad(verts, tris, _Vert(k00, n_top, uv_a, z0_zero, bslot), _Vert(k10, n_top, uv_b, z0_zero, bslot),
                           _Vert(f10, n_top, uv_b, z0_zero, bslot), _Vert(f00, n_top, uv_a, z0_zero, bslot), FACE3D_SLOT, wind_sign)
                _emit_quad(verts, tris, _Vert(f01, n_bot, uv_d, z0_zero, bslot), _Vert(f11, n_bot, uv_c, z0_zero, bslot),
                           _Vert(k11, n_bot, uv_c, z0_zero, bslot), _Vert(k01, n_bot, uv_d, z0_zero, bslot), FACE3D_SLOT, wind_sign)
                if omit_inner_cap != 'u0':
                    _emit_quad(verts, tris, _Vert(k00, n_u0, uv_a, z0_zero, bslot), _Vert(f00, n_u0, uv_a, z0_zero, bslot),
                               _Vert(f01, n_u0, uv_d, z0_zero, bslot), _Vert(k01, n_u0, uv_d, z0_zero, bslot), FACE3D_SLOT, wind_sign)
                if omit_inner_cap != 'u1':
                    _emit_quad(verts, tris, _Vert(f10, n_u1, uv_b, z0_zero, bslot), _Vert(k10, n_u1, uv_b, z0_zero, bslot),
                               _Vert(k11, n_u1, uv_c, z0_zero, bslot), _Vert(f11, n_u1, uv_c, z0_zero, bslot), FACE3D_SLOT, wind_sign)
                return verts[s_idx:]

            if is_unibrow:
                mid_u = bl_raw[0]
                by1 = min(max(bl_raw[3], br_raw[3]), eye_top_v - 0.05)
                by0 = by1 - brow_h_px
                uni_wide_up = min(0.42 * sh_eye_ref, brow_wide_up)
                mid_piv = surf.pos_at(mid_u, 0.5 * (by0 + by1), 0.5 * brow_thick)
                half_span = max(abs(mid_u - br_raw[0]) * surf.px_u, 1e-4)
                for side, raw_b, omit_cap in (('r', br_raw, 'u1'), ('l', bl_raw, 'u0')):
                    bslot = ensure_joint(f'brow_{side}', 'face_root', mid_piv)
                    b_verts = emit_brow_box(raw_b[0], by0, raw_b[2], by1, raw_b, bslot, omit_inner_cap=omit_cap)
                    for bv in b_verts:
                        su = _dot(_sub3(bv.pos, mid_piv), surf.u_dir)
                        t_lr = max(0.0, min(1.0, 0.5 + 0.5 * su / half_span))
                        surf.add_px_morph(bv, 'face_brow_y_r', dv_px=-(1.0 - t_lr) * 1.15)
                        surf.add_px_morph(bv, 'face_brow_y_l', dv_px=-t_lr * 1.15)
                        if brow_blink_follow:
                            dip = _BROW_BLINK_FULL_DIP * sh_eye_ref
                            surf.add_px_morph(bv, 'face_blink_r', dv_px=(1.0 - t_lr) * dip)
                            surf.add_px_morph(bv, 'face_blink_l', dv_px=t_lr * dip)
                        if uni_wide_up > 1e-4:
                            surf.add_px_morph(bv, 'face_eye_wide', dv_px=-uni_wide_up)
                        dist_ratio = abs(su) / half_span
                        surf.add_px_morph(bv, 'face_brow_rot_r', dv_px=-(0.28 - (0.85 * dist_ratio if side == 'r' else 0.0)))
                        surf.add_px_morph(bv, 'face_brow_rot_l', dv_px=-(0.28 - (0.85 * dist_ratio if side == 'l' else 0.0)))
            else:
                for side, br_key in (('l', 'brow_l'), ('r', 'brow_r')):
                    bx0, _, bx1, raw_by1 = (float(x) for x in spec[br_key])
                    by1 = min(raw_by1, eye_top_v - 0.12)
                    by0 = by1 - brow_h_px
                    uv_rect = spec[br_key] if spec.get('use_brows') or not brow_src_uv else brow_src_uv
                    bpiv = surf.pos_at(0.5 * (bx0 + bx1), 0.5 * (by0 + by1), 0.5 * brow_thick)
                    bslot = ensure_joint(f'brow_{side}', 'face_root', bpiv)
                    b_verts = emit_brow_box(bx0, by0, bx1, by1, uv_rect, bslot)
                    ang = math.radians(20.0) * (1.0 if side == 'r' else -1.0)
                    for bv in b_verts:
                        surf.add_px_morph(bv, f'face_brow_y_{side}', dv_px=-0.85)
                        if brow_blink_follow:
                            surf.add_px_morph(bv, f'face_blink_{side}', dv_px=_BROW_BLINK_FULL_DIP * sh_eye_ref)
                        if brow_wide_up > 1e-4:
                            surf.add_px_morph(bv, 'face_eye_wide', dv_px=-brow_wide_up)
                        surf.add_rot_morph(
                            bv, f'face_brow_rot_{side}', bpiv, ang, sq_curve=f'_mc_brow_rot_sq_{side}',
                        )

        for sdef, surf in matched_surfaces:
            u0, v0, u1, v1 = surf.u0, surf.v0, surf.u1, surf.v1
            eye_depth = opts['eye_depth'] * surf.px_avg
            mouth_depth = opts['mouth_depth'] * surf.px_avg
            eye_sides = [s for s in sdef['eyes'] if spec.get(f'eye_{s}')]
            eye_holes = [spec[f'eye_{s}'] for s in eye_sides]
            eye_bot = max((float(h[3]) for h in eye_holes), default=v0)
            has_mouth = bool(sdef['use_mouth'] and spec.get('mouth') and float(spec['mouth'][1]) > eye_bot + 0.25)
            v_split = max(eye_bot + 0.1, float(spec['mouth'][1]) - 0.65) if has_mouth else v1
            erase_2d_brows = ([spec['brow_l'], spec['brow_r']]
                              if (sdef['use_brows'] and spec.get('use_brows') and spec.get('brow_l') and spec.get('brow_r'))
                              else [])
            erase_extra = list(sdef['erase_rects'])

            mouth_segs = 6
            extra_us = ()
            if has_mouth:
                mx0_s, _, mx1_s, _ = (float(x) for x in spec['mouth'])
                extra_us = tuple(mx0_s + (mx1_s - mx0_s) * (k / mouth_segs) for k in range(mouth_segs + 1))

            cut_rects = list(eye_holes) + list(erase_2d_brows) + list(erase_extra)
            eye_wide_specs = []
            extra_eye_vs = []
            for h in eye_holes:
                hx0, hy0, hx1, hy1 = (float(x) for x in h)
                sh_h = max(0.5, hy1 - hy0)
                up_h = min(0.42 * sh_h, max(0.0, hy0 - v0 - 0.08))
                eye_wide_specs.append((hx0, hy0, hx1, hy1, up_h))
                cut_v = hy0 - max(0.60, up_h + 0.18)
                if cut_v > v0 + 1e-4:
                    extra_eye_vs.append(cut_v)

            def corner_eye_wide_up(u_pt: float, v_pt: float) -> float:
                best = 0.0
                for hx0, hy0, hx1, _, up_h in eye_wide_specs:
                    if up_h > best and abs(v_pt - hy0) <= 1e-4 and (hx0 - 1e-4 <= u_pt <= hx1 + 1e-4):
                        best = up_h
                return best

            us = sorted({u0, u1, *extra_us,
                         *(max(u0, min(u1, float(r[0]))) for r in cut_rects),
                         *(max(u0, min(u1, float(r[2]))) for r in cut_rects)})
            vs = sorted({v0, v_split, *extra_eye_vs,
                         *(max(v0, min(v_split, float(r[1]))) for r in cut_rects),
                         *(max(v0, min(v_split, float(r[3]))) for r in cut_rects)})

            # 4a. Upper face skin [u0..u1] x [v0..v_split] (eye-rim corners lift cleanly with UV slide)
            for ia in range(len(us) - 1):
                ua, ub = us[ia], us[ia + 1]
                if ub - ua <= 1e-5:
                    continue
                for ib in range(len(vs) - 1):
                    va, vb = vs[ib], vs[ib + 1]
                    if vb - va <= 1e-5:
                        continue
                    cu, cv = 0.5 * (ua + ub), 0.5 * (va + vb)
                    if any(in_rect(cu, cv, h) for h in eye_holes):
                        continue
                    erased = any(in_rect(cu, cv, r) for r in (*erase_2d_brows, *erase_extra))
                    # ONLY the quad directly above an eye hole (`hx0 <= cu <= hx1` and bottom edge `vb == hy0`)
                    # lifts its bottom edge cleanly on `_mc_eye_wide_pos = max(face_eye_wide, 0)`.
                    # Bridge between eyes, temples, and forehead stay 100% static -> zero notch/distortion!
                    above_eye_up = 0.0
                    for hx0, hy0, hx1, _, up_h in eye_wide_specs:
                        if up_h > above_eye_up and (hx0 - 1e-4 <= cu <= hx1 + 1e-4) and abs(vb - hy0) <= 1e-4:
                            above_eye_up = up_h
                    corners_grid = ((ua, va), (ub, va), (ub, vb), (ua, vb))
                    corners_up = [
                        (above_eye_up if abs(gv - vb) <= 1e-4 else 0.0) if above_eye_up > 1e-4 else 0.0
                        for _, gv in corners_grid
                    ]
                    has_eye_slide = (not erased) and above_eye_up > 1e-4
                    corners_uv = (
                        surf.clean_uv if erased else (ua / tw, va / th),
                        surf.clean_uv if erased else (ub / tw, va / th),
                        surf.clean_uv if erased else (ub / tw, vb / th),
                        surf.clean_uv if erased else (ua / tw, vb / th),
                    )
                    # Micro-recess (-0.025 cm) on moving bottom-edge vertices prevents UE Interchange's
                    # position-based FVertexID welding from merging them with adjacent static bridge/temple corners!
                    eye_rim_dn = -min(0.00025, 0.12 * eye_depth)
                    corners_pos = tuple(
                        surf.pos_at(gu, gv, eye_rim_dn if up_i > 1e-4 else 0.0)
                        for (gu, gv), up_i in zip(corners_grid, corners_up)
                    )
                    qverts = []
                    for p, uv_i, up_i in zip(corners_pos, corners_uv, corners_up):
                        # COLOR_0.A = 0.5 signals eye-wide UP-only UV slide (B = up_px / 2.0)
                        vcol = (1.0, 1.0, max(0.0, min(1.0, up_i * 0.5)), 0.5) if has_eye_slide else _COL_STATIC
                        vtx = _Vert(p, surf.n_dir, uv_i, z0_zero, surf.bone_slot, color=vcol)
                        if up_i > 1e-4:
                            surf.add_px_morph(vtx, '_mc_eye_wide_pos', dv_px=-up_i)
                        qverts.append(vtx)
                    _emit_quad(verts, tris, *qverts, FACE3D_SLOT, wind_sign)

            # 4b. 3D Recessed Eyes on this surface (edge-clamped + true wide-eye + upper/lower eyelids + pupil scale!)
            for side in eye_sides:
                ex0, ey0, ex1, ey1 = (float(x) for x in spec[f'eye_{side}'])
                px0, py0, px1, py1 = (float(x) for x in spec[f'pupil_{side}'])
                sh_eye = max(0.5, ey1 - ey0)
                eye_wide_up = min(0.42 * sh_eye, max(0.0, ey0 - v0 - 0.08))
                if px0 > ex0 + 0.1:
                    sclera_u = 0.5 * (ex0 + px0)
                elif px1 < ex1 - 0.1:
                    sclera_u = 0.5 * (px1 + ex1)
                else:
                    sclera_u = 0.5 * (ex0 + ex1)
                if py0 > ey0 + 0.1:
                    sclera_v = 0.5 * (ey0 + py0)
                elif py1 < ey1 - 0.1:
                    sclera_v = 0.5 * (py1 + ey1)
                else:
                    sclera_v = 0.5 * (ey0 + ey1)
                if ex1 - ex0 >= 1.0:
                    sclera_u = min(ex1 - 0.5, max(ex0 + 0.5, math.floor(sclera_u) + 0.5))
                if ey1 - ey0 >= 1.0:
                    sclera_v = min(ey1 - 0.5, max(ey0 + 0.5, math.floor(sclera_v) + 0.5))
                sclera_uv = (sclera_u / tw, sclera_v / th)
                first_sclera_uv = sclera_uv

                eye_slot = ensure_joint(f'eye_{side}', 'face_root', surf.pos_at(0.5 * (ex0 + ex1), 0.5 * (ey0 + ey1)))
                p_depth = -0.60 * eye_depth
                pupil_center = surf.pos_at(0.5 * (px0 + px1), 0.5 * (py0 + py1), p_depth)
                pupil_slot = ensure_joint(f'pupil_{side}', f'eye_{side}', pupil_center)

                emit_recess_walls(surf, ex0, ey0, ex1, ey1, eye_depth, eye_slot, surf.clean_uv, eye_wide_up=eye_wide_up)

                su0, su1 = surf.clamp_u(ex0 - 0.15), surf.clamp_u(ex1 + 0.15)
                sv0, sv1 = surf.clamp_v(ey0 - max(0.20, eye_wide_up + 0.15)), surf.clamp_v(ey1 + 0.15)
                sc_verts = [
                    _Vert(surf.pos_at(su0, sv0, -eye_depth), surf.n_dir, sclera_uv, z0_zero, eye_slot),
                    _Vert(surf.pos_at(su1, sv0, -eye_depth), surf.n_dir, sclera_uv, z0_zero, eye_slot),
                    _Vert(surf.pos_at(su1, sv1, -eye_depth), surf.n_dir, sclera_uv, z0_zero, eye_slot),
                    _Vert(surf.pos_at(su0, sv1, -eye_depth), surf.n_dir, sclera_uv, z0_zero, eye_slot),
                ]
                _emit_quad(verts, tris, *sc_verts, FACE3D_SLOT, wind_sign)

                p_uvs = ((px0 / tw, py0 / th), (px1 / tw, py0 / th), (px1 / tw, py1 / th), (px0 / tw, py1 / th))
                p_pts = (surf.pos_at(px0, py0, p_depth), surf.pos_at(px1, py0, p_depth),
                         surf.pos_at(px1, py1, p_depth), surf.pos_at(px0, py1, p_depth))
                p_verts = [_Vert(pt, surf.n_dir, puv, z0_zero, pupil_slot) for pt, puv in zip(p_pts, p_uvs)]
                look_x_range = min(0.999, max(0.5, (ex1 - ex0) - (px1 - px0)))
                look_y_range = min(0.45, max(0.22, (ey1 - ey0) - (py1 - py0), 0.35 * (ey1 - ey0)))
                for pv in p_verts:
                    surf.add_px_morph(pv, f'face_look_x_{side}', du_px=look_x_range)
                    surf.add_px_morph(pv, 'face_look_y', dv_px=-look_y_range)
                    rel = _sub3(pv.pos, pupil_center)
                    pv.add_morph('face_pupil_scale', 0.35 * rel[0], 0.35 * rel[1], 0.35 * rel[2])
                _emit_quad(verts, tris, *p_verts, FACE3D_SLOT, wind_sign)

                lid_depth = -max(0.0008, 0.18 * eye_depth)
                lu0, lu1 = surf.clamp_u(ex0 - 0.06), surf.clamp_u(ex1 + 0.06)
                lv0 = surf.clamp_v(ey0 - max(0.25, eye_wide_up + 0.18))
                lid_lip = 0.015
                eye_h_px = (ey1 - (ey0 + lid_lip)) + 0.04
                ul_pts = (surf.pos_at(lu0, lv0, lid_depth), surf.pos_at(lu1, lv0, lid_depth),
                          surf.pos_at(lu1, ey0 + lid_lip, lid_depth), surf.pos_at(lu0, ey0 + lid_lip, lid_depth))
                ul_verts = [_Vert(pt, surf.n_dir, surf.clean_uv, z0_zero, eye_slot) for pt in ul_pts]
                lid_wide_up = max(eye_wide_up, 0.40 * sh_eye)
                for idx_v in (2, 3):
                    surf.add_px_morph(ul_verts[idx_v], f'face_blink_{side}', dv_px=eye_h_px)
                    surf.add_px_morph(ul_verts[idx_v], 'face_eye_wide', dv_px=-lid_wide_up)
                    # Bilinear corrective morph (driven by clamp(blink,0,1) * max(0, eye_wide)) guarantees 0-gap seal
                    surf.add_px_morph(ul_verts[idx_v], f'_mc_blink_wide_{side}', dv_px=lid_wide_up)
                _emit_quad(verts, tris, *ul_verts, FACE3D_SLOT, wind_sign)

                # 3D Lower Eyelid: rises smoothly on `face_eye_wide < 0` for symmetric squint / `^_^` laugh!
                lv1 = surf.clamp_v(ey1 + 0.25)
                ll_pts = (surf.pos_at(lu0, ey1 - lid_lip, lid_depth), surf.pos_at(lu1, ey1 - lid_lip, lid_depth),
                          surf.pos_at(lu1, lv1, lid_depth), surf.pos_at(lu0, lv1, lid_depth))
                ll_verts = [_Vert(pt, surf.n_dir, surf.clean_uv, z0_zero, eye_slot) for pt in ll_pts]
                for idx_v in (0, 1):
                    surf.add_px_morph(ll_verts[idx_v], 'face_eye_wide', dv_px=0.40 * sh_eye)
                _emit_quad(verts, tris, *ll_verts, FACE3D_SLOT, wind_sign)

            # 4c. Sleek 3D Eyebrows on this surface
            if sdef['use_brows']:
                emit_3d_brows(surf)

            # 4d. True Recessed 3D Mouth Ring + Bone-Invariant Analytic COLOR_0 UV Compensation
            if has_mouth:
                mx0, my0, mx1, my1 = (float(x) for x in spec['mouth'])
                mc_u, mc_v = 0.5 * (mx0 + mx1), 0.5 * (my0 + my1)
                half_w = 0.5 * (mx1 - mx0)
                mouth_uv = (mc_u / tw, mc_v / th)
                mslot = ensure_joint('mouth', 'face_root', surf.pos_at(mc_u, mc_v))

                segs = mouth_segs
                slit = 0.025
                r_my0 = max(v_split + 0.05, min(my0, mc_v - 0.35))
                r_my1 = min(v1 - 0.05, max(my1, mc_v + 0.35))
                col_u = [u0, *(mx0 + (mx1 - mx0) * (k / segs) for k in range(segs + 1)), u1]
                row_v = [v_split, r_my0, mc_v - slit, mc_v + slit, r_my1, v1]

                def make_front_ring_vert(r_idx: int, c_idx: int):
                    gu = col_u[c_idx]
                    gv = (v_split + (v1 - v_split) * (r_idx / 5.0)) if c_idx in (0, segs + 2) else row_v[r_idx]
                    xn, sw, deltas = _mouth_morph_px(r_idx, c_idx, col_u, segs, mc_u, half_w)
                    vcol = _encode_slide_color(xn, sw)
                    vtx = _Vert(surf.pos_at(gu, gv, 0.0), surf.n_dir, (gu / tw, gv / th), z0_zero, surf.bone_slot, color=vcol)
                    for m_name, (du_p, dv_p) in deltas.items():
                        surf.add_px_morph(vtx, m_name, du_px=du_p, dv_px=dv_p)
                    return vtx

                cav_collar = -min(0.0006, 0.25 * mouth_depth)
                cav_pad = 0.04

                def make_cavity_vert(r_idx: int, c_idx: int, depth_m: float, nrm_vec):
                    gu = col_u[c_idx] + (-cav_pad if c_idx == 1 else (cav_pad if c_idx == segs + 1 else 0.0))
                    gv = row_v[r_idx] + (-cav_pad if r_idx == 2 else (cav_pad if r_idx == 3 else 0.0))
                    _, _, deltas = _mouth_morph_px(r_idx, c_idx, col_u, segs, mc_u, half_w)
                    vtx = _Vert(surf.pos_at(gu, gv, depth_m), nrm_vec, mouth_uv, z0_zero, mslot, color=_COL_CAVITY)
                    for m_name, (du_p, dv_p) in deltas.items():
                        surf.add_px_morph(vtx, m_name, du_px=du_p, dv_px=dv_p)
                    return vtx

                for r_i in range(5):
                    for c_i in range(segs + 2):
                        if r_i == 2 and 1 <= c_i <= segs:
                            continue
                        q_v = [
                            make_front_ring_vert(r_i, c_i),
                            make_front_ring_vert(r_i, c_i + 1),
                            make_front_ring_vert(r_i + 1, c_i + 1),
                            make_front_ring_vert(r_i + 1, c_i),
                        ]
                        _emit_quad(verts, tris, *q_v, FACE3D_SLOT, wind_sign)

                n_top, n_bot = surf.v_dir, _scale3(surf.v_dir, -1.0)
                n_u0, n_u1 = surf.u_dir, _scale3(surf.u_dir, -1.0)
                for c_i in range(1, segs + 1):
                    _emit_quad(verts, tris,
                               make_cavity_vert(2, c_i, cav_collar, n_top),
                               make_cavity_vert(2, c_i + 1, cav_collar, n_top),
                               make_cavity_vert(2, c_i + 1, -mouth_depth, n_top),
                               make_cavity_vert(2, c_i, -mouth_depth, n_top), FACE3D_SLOT, wind_sign)
                    _emit_quad(verts, tris,
                               make_cavity_vert(3, c_i, -mouth_depth, n_bot),
                               make_cavity_vert(3, c_i + 1, -mouth_depth, n_bot),
                               make_cavity_vert(3, c_i + 1, cav_collar, n_bot),
                               make_cavity_vert(3, c_i, cav_collar, n_bot), FACE3D_SLOT, wind_sign)
                    _emit_quad(verts, tris,
                               make_cavity_vert(2, c_i, -mouth_depth, surf.n_dir),
                               make_cavity_vert(2, c_i + 1, -mouth_depth, surf.n_dir),
                               make_cavity_vert(3, c_i + 1, -mouth_depth, surf.n_dir),
                               make_cavity_vert(3, c_i, -mouth_depth, surf.n_dir), FACE3D_SLOT, wind_sign)

                _emit_quad(verts, tris,
                           make_cavity_vert(2, 1, -mouth_depth, n_u0),
                           make_cavity_vert(3, 1, -mouth_depth, n_u0),
                           make_cavity_vert(3, 1, cav_collar, n_u0),
                           make_cavity_vert(2, 1, cav_collar, n_u0), FACE3D_SLOT, wind_sign)
                _emit_quad(verts, tris,
                           make_cavity_vert(2, segs + 1, cav_collar, n_u1),
                           make_cavity_vert(3, segs + 1, cav_collar, n_u1),
                           make_cavity_vert(3, segs + 1, -mouth_depth, n_u1),
                           make_cavity_vert(2, segs + 1, -mouth_depth, n_u1), FACE3D_SLOT, wind_sign)

                if use_teeth:
                    teeth_d = -max(0.0012, 0.28 * mouth_depth)
                    for c_i in range(1, segs + 1):
                        def make_tooth_v(ci: int, is_bottom: bool):
                            gu = col_u[ci]
                            gv = row_v[2] + (0.008 if is_bottom else 0.0)
                            _, _, deltas = _mouth_morph_px(2, ci, col_u, segs, mc_u, half_w)
                            vtx = _Vert(surf.pos_at(gu, gv, teeth_d), surf.n_dir, first_sclera_uv, z0_zero, mslot)
                            for m_name, (du_p, dv_p) in deltas.items():
                                surf.add_px_morph(vtx, m_name, du_px=du_p, dv_px=dv_p)
                            if is_bottom:
                                xn_t = (gu - mc_u) / max(half_w, 0.5)
                                tooth_arch = max(0.0, 1.0 - 0.85 * xn_t * xn_t)
                                surf.add_px_morph(vtx, 'face_mouth_open', dv_px=0.28 * tooth_arch)
                                surf.add_px_morph(vtx, '_mc_mouth_neg_cancel', dv_px=0.28 * tooth_arch)
                            return vtx

                        _emit_quad(verts, tris,
                                   make_tooth_v(c_i, False), make_tooth_v(c_i + 1, False),
                                   make_tooth_v(c_i + 1, True), make_tooth_v(c_i, True), FACE3D_SLOT, wind_sign)

    return _pack_upgraded_glb(doc, blob, nodes, joints, worlds, verts, tris, mode=mode)


def _pack_upgraded_glb(doc, old_blob, nodes, joints, worlds, verts: list[_Vert], tris, *, mode: str = '2d') -> bytes:
    """Serialize updated skeleton, UV/VertexColor primitives, embedded images, and glTF Morph Targets."""
    surfs = embedded_base_color_surfaces(pack_glb(doc, old_blob))
    used_slots = {mname for _, _, _, mname in tris}
    slot_order = [s for s in surfs if s in used_slots]
    for _, _, _, mname in tris:
        if mname not in slot_order:
            slot_order.append(mname)

    out_blob = bytearray()
    views = []
    accessors = []

    def add_view(raw_bytes: bytes) -> int:
        out_blob.extend(b'\x00' * (-len(out_blob) % 4))
        idx = len(views)
        views.append({'buffer': 0, 'byteOffset': len(out_blob), 'byteLength': len(raw_bytes)})
        out_blob.extend(raw_bytes)
        return idx

    def add_acc(rows, fmt: str, comp_type: int, kind: str, *, with_bounds: bool = False) -> int:
        rows = list(rows)
        flat = [x for r in rows for x in r]
        v_idx = add_view(struct.pack(f'<{len(flat)}{fmt}', *flat))
        acc = {'bufferView': v_idx, 'componentType': comp_type, 'count': len(rows), 'type': kind}
        if with_bounds and rows:
            acc['min'] = [float(min(col)) for col in zip(*rows)]
            acc['max'] = [float(max(col)) for col in zip(*rows)]
        accessors.append(acc)
        return len(accessors) - 1

    has_morphs = any(bool(v.morphs) for v in verts)
    active_morphs = {cname for v in verts for cname in v.morphs}
    ordered_morphs = list(FACE_CURVES) + (list(FACE3D_CORRECTIVE_MORPHS) if mode == '3d' else [])
    target_names = [cname for cname in ordered_morphs if cname in active_morphs]
    images, materials, textures = [], [], []
    primary_png, primary_mime, primary_alpha = next(iter(surfs.values()))

    for mat_idx, slot_name in enumerate(slot_order):
        if slot_name in surfs:
            png, mime, alpha_mode = surfs[slot_name]
        elif slot_name in (FACE2D_SLOT, FACE3D_SLOT):
            png, mime, alpha_mode = primary_png, primary_mime, 'MASK'
        else:
            png, mime, alpha_mode = primary_png, primary_mime, primary_alpha
        images.append({'bufferView': add_view(bytes(png)), 'mimeType': mime})
        textures.append({'source': mat_idx, 'sampler': 0})
        materials.append({
            'name': slot_name,
            'alphaMode': alpha_mode,
            'doubleSided': True,
            'pbrMetallicRoughness': {'baseColorTexture': {'index': mat_idx}},
        })

    use_single_uv_vcol = (mode == '3d')
    primitives = []
    for mat_idx, slot_name in enumerate(slot_order):
        slot_tris = [(a, b, c) for a, b, c, m in tris if m == slot_name]
        used_v = sorted({v for tri in slot_tris for v in tri})
        remap = {old: new for new, old in enumerate(used_v)}
        sub_verts = [verts[old] for old in used_v]

        attrs = {
            'POSITION': add_acc((v.pos for v in sub_verts), 'f', 5126, 'VEC3', with_bounds=True),
            'NORMAL': add_acc((v.nrm for v in sub_verts), 'f', 5126, 'VEC3'),
            'TEXCOORD_0': add_acc((v.uv0 for v in sub_verts), 'f', 5126, 'VEC2'),
        }
        if use_single_uv_vcol:
            attrs['COLOR_0'] = add_acc((v.color for v in sub_verts), 'f', 5126, 'VEC4')
        else:
            attrs['TEXCOORD_1'] = add_acc((v.uv1 for v in sub_verts), 'f', 5126, 'VEC2')
        attrs['JOINTS_0'] = add_acc(((v.joint, 0, 0, 0) for v in sub_verts), 'H', 5123, 'VEC4')
        attrs['WEIGHTS_0'] = add_acc(((1.0, 0.0, 0.0, 0.0) for _ in sub_verts), 'f', 5126, 'VEC4')
        ind_acc = add_acc(((remap[i],) for tri in slot_tris for i in tri), 'I', 5125, 'SCALAR')
        prim = {'attributes': attrs, 'indices': ind_acc, 'material': mat_idx}
        if has_morphs:
            # Share one zero-delta VEC3 accessor for NORMAL and any inactive morph curve on this primitive!
            zero_acc = add_acc(((0.0, 0.0, 0.0) for _ in sub_verts), 'f', 5126, 'VEC3', with_bounds=True)
            targets = []
            for cname in target_names:
                if any(cname in v.morphs for v in sub_verts):
                    deltas = [v.morphs.get(cname, (0.0, 0.0, 0.0)) for v in sub_verts]
                    pos_acc = add_acc(deltas, 'f', 5126, 'VEC3', with_bounds=True)
                else:
                    pos_acc = zero_acc
                targets.append({'POSITION': pos_acc, 'NORMAL': zero_acc})
            prim['targets'] = targets
        primitives.append(prim)

    old_to_new_node = {old_idx: new_idx for new_idx, old_idx in enumerate(joints)}
    clean_nodes, ibms = [], []
    for old_idx in joints:
        nd = copy.deepcopy(nodes[old_idx])
        kids = [old_to_new_node[c] for c in nd.get('children', ()) if c in old_to_new_node]
        if kids:
            nd['children'] = kids
        else:
            nd.pop('children', None)
        clean_nodes.append(nd)
        ibms.append(_column_major(_inverse_rigid(worlds[old_idx])))

    ibm_acc = add_acc(ibms, 'f', 5126, 'MAT4')
    mesh_name = doc['meshes'][0].get('name', 'Model')
    mesh_obj = {'name': mesh_name, 'primitives': primitives}
    if has_morphs:
        mesh_obj['extras'] = {'targetNames': list(target_names)}
        mesh_obj['weights'] = [0.0] * len(target_names)

    mesh_node_idx = len(clean_nodes)
    clean_nodes.append({'name': mesh_name, 'mesh': 0, 'skin': 0})

    out_doc = {
        'asset': {'version': '2.0', 'generator': 'Mineprep FaceBuilder'},
        'scene': 0,
        'scenes': [{'nodes': [0, mesh_node_idx]}],
        'nodes': clean_nodes,
        'skins': [{
            'name': doc['skins'][0].get('name', mesh_name + '_Skeleton'),
            'skeleton': 0,
            'joints': list(range(len(joints))),
            'inverseBindMatrices': ibm_acc,
        }],
        'meshes': [mesh_obj],
        'materials': materials,
        'textures': textures,
        'images': images,
        'samplers': [{'magFilter': 9728, 'minFilter': 9728}],
        'accessors': accessors,
        'bufferViews': views,
        'buffers': [{'byteLength': len(out_blob)}],
    }
    return pack_glb(out_doc, out_blob)
