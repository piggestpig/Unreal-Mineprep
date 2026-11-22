"""Pure-Python FK contact, foot-slide, and joint-seam diagnostics and authoring helpers."""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path

from mineprep.model import glb_bone_bounds
from . import rig_rules, sampling


def _rotator_to_quat(roll: float, pitch: float, yaw: float) -> tuple[float, float, float, float]:
    """Match UE FRotator(roll, pitch, yaw).Quaternion() (XYZ in UE degrees)."""
    hr, hp, hy = math.radians(roll) * 0.5, math.radians(pitch) * 0.5, math.radians(yaw) * 0.5
    sr, cr = math.sin(hr), math.cos(hr)
    sp, cp = math.sin(hp), math.cos(hp)
    sy, cy = math.sin(hy), math.cos(hy)
    return (
        cr * sp * sy - sr * cp * cy,
        -cr * sp * cy - sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    )


def _bedrock_rot_to_quat(rotation) -> tuple[float, float, float, float]:
    """Match MCAnimConverter.biped.rotation_xyz() as a pure-Python quaternion."""
    q = _rotator_to_quat(float(rotation[0]), float(rotation[1]), float(rotation[2]))
    return (q[2], -q[0], -q[1], q[3])


def _bedrock_ctrl_transform(pos, rot, scale):
    """Match MCAnimConverter.biped.control_samples() Transform in UE cm."""
    loc = rig_rules.bedrock_pos_to_ue_cm(pos)
    quat = _bedrock_rot_to_quat(rot)
    scl = rig_rules.bedrock_scale_to_ue(scale)
    return (loc, quat, scl)


def _qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def _qconj(q):
    return (-q[0], -q[1], -q[2], q[3])


def _qrot(q, v):
    qx, qy, qz, qw = q
    vx, vy, vz = v
    tx = 2.0 * (qy * vz - qz * vy)
    ty = 2.0 * (qz * vx - qx * vz)
    tz = 2.0 * (qx * vy - qy * vx)
    return (
        vx + qw * tx + qy * tz - qz * ty,
        vy + qw * ty + qz * tx - qx * tz,
        vz + qw * tz + qx * ty - qy * tx,
    )


def _mat3_to_quat(m) -> tuple[float, float, float, float]:
    """Extract unit quaternion from upper-left 3x3 orthonormal row-major matrix."""
    m00, m01, m02 = m[0][0], m[0][1], m[0][2]
    m10, m11, m12 = m[1][0], m[1][1], m[1][2]
    m20, m21, m22 = m[2][0], m[2][1], m[2][2]
    trace = m00 + m11 + m22
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        return ((m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s, 0.25 * s)
    if m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        return (0.25 * s, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s)
    if m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        return ((m01 + m10) / s, 0.25 * s, (m12 + m21) / s, (m02 - m20) / s)
    s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
    return ((m02 + m20) / s, (m12 + m21) / s, 0.25 * s, (m10 - m01) / s)


def _t_mul(first, second):
    """Match UE Transform.multiply(other): applies `first`, then `second`."""
    l1, q1, s1 = first
    l2, q2, s2 = second
    scaled_l1 = (s2[0] * l1[0], s2[1] * l1[1], s2[2] * l1[2])
    rl1 = _qrot(q2, scaled_l1)
    return (
        (rl1[0] + l2[0], rl1[1] + l2[1], rl1[2] + l2[2]),
        _qmul(q2, q1),
        (s1[0] * s2[0], s1[1] * s2[1], s1[2] * s2[2]),
    )


def _t_inv(xf):
    loc, quat, scl = xf
    iq = _qconj(quat)
    iscl = (1.0 / scl[0], 1.0 / scl[1], 1.0 / scl[2])
    rloc = _qrot(iq, loc)
    return ((-rloc[0] * iscl[0], -rloc[1] * iscl[1], -rloc[2] * iscl[2]), iq, iscl)


def _t_point(xf, p):
    loc, quat, scl = xf
    sp = (p[0] * scl[0], p[1] * scl[1], p[2] * scl[2])
    rp = _qrot(quat, sp)
    return (rp[0] + loc[0], rp[1] + loc[1], rp[2] + loc[2])


def _bounds_list(glb_source) -> list[dict]:
    if isinstance(glb_source, (list, tuple)):
        return list(glb_source)
    return glb_bone_bounds(glb_source, dominant_weight_only=True)


def _load_clip_entry(clip_source, clip=None) -> tuple[str, dict]:
    if isinstance(clip_source, (str, Path)):
        data = json.loads(Path(clip_source).read_text(encoding='utf-8-sig'))
    elif isinstance(clip_source, dict):
        data = clip_source
    else:
        raise ValueError('clip_source 须为 Bedrock 动画路径或字典')

    if 'animations' in data:
        animations = data['animations']
        if not isinstance(animations, dict) or not animations:
            raise ValueError('Bedrock animations 为空或格式无效')
        if clip is not None:
            if clip not in animations:
                raise ValueError(f'未找到动画片段: {clip}')
            return clip, animations[clip]
        if len(animations) != 1:
            raise ValueError('包含多个动画片段时请显式指定 clip 名称')
        name, body = next(iter(animations.items()))
        return name, body
    if 'bones' in data:
        return clip or 'clip', data
    raise ValueError('无法识别的 Bedrock 动画格式')


def _biped_control_name(bone: str) -> str | None:
    return rig_rules.biped_control_name(bone)


def _resolve_quadruped_bone(bone: str, exact: set[str], by_case: dict[str, str]) -> str | None:
    return rig_rules.resolve_aliased_bone(bone, exact, by_case.get)


def _detect_mode(by_name: dict[str, dict], clip_bones: dict) -> str:
    if 'pelvis' in clip_bones or 'pelvis' in {k.casefold() for k in clip_bones}:
        return 'local'
    if 'left_front_leg' in by_name and 'left_hind_leg' in by_name:
        return 'quadruped'
    if 'left_leg' in by_name and any(_biped_control_name(k) in ('waist', 'leftarm', 'rightarm', 'leftleg', 'rightleg')
                                     and k not in by_name for k in clip_bones):
        return 'biped'
    if 'left_leg' in by_name and ('waist' in clip_bones or 'hip' in clip_bones):
        return 'biped'
    return 'local'


def _reference_transforms(records: list[dict]) -> tuple[dict, dict, dict]:
    by_name = {r['bone_name']: r for r in records}
    local_xf = {}
    world_xf = {}

    def _local(name: str):
        if name not in local_xf:
            m = by_name[name]['local_mat4']
            loc = (float(m[0][3]), float(m[1][3]), float(m[2][3]))
            sx = math.hypot(m[0][0], m[1][0], m[2][0]) or 1.0
            sy = math.hypot(m[0][1], m[1][1], m[2][1]) or 1.0
            sz = math.hypot(m[0][2], m[1][2], m[2][2]) or 1.0
            rot_m = [
                [m[0][0] / sx, m[0][1] / sy, m[0][2] / sz],
                [m[1][0] / sx, m[1][1] / sy, m[1][2] / sz],
                [m[2][0] / sx, m[2][1] / sy, m[2][2] / sz],
            ]
            local_xf[name] = (loc, _mat3_to_quat(rot_m), (sx, sy, sz))
        return local_xf[name]

    def _world(name: str):
        if name not in world_xf:
            parent = by_name[name]['parent_name']
            lx = _local(name)
            world_xf[name] = _t_mul(lx, _world(parent)) if parent and parent in by_name else lx
        return world_xf[name]

    for r in records:
        _world(r['bone_name'])
    return by_name, local_xf, world_xf


def _sample_controls(samples: dict, count: int) -> dict[str, list]:
    return {
        bone: [
            _bedrock_ctrl_transform(ch['position'][i], ch['rotation'][i], ch['scale'][i])
            for i in range(count)
        ]
        for bone, ch in samples.items()
    }


def _evaluate_local_frames(by_name, local_xf, world_xf, controls, count):
    ident = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0))
    by_case = {k.casefold(): k for k in by_name}
    ctrl_by_bone = {}
    for src, xfs in controls.items():
        tgt = src if src in by_name else by_case.get(src.casefold())
        if tgt is not None:
            ctrl_by_bone[tgt] = xfs
    names = list(by_name)
    frames = []
    ctrl_xfs = []
    for idx in range(count):
        poses = {}
        cframe = {}

        def _pose(name: str):
            if name not in poses:
                ctrl = ctrl_by_bone[name][idx] if name in ctrl_by_bone else ident
                parent = by_name[name]['parent_name']
                base = _t_mul(local_xf[name], _pose(parent)) if parent and parent in by_name else local_xf[name]
                cframe[name] = (base[1], base[2])
                poses[name] = _t_mul(ctrl, base)
            return poses[name]

        for name in names:
            _pose(name)
        frames.append(poses)
        ctrl_xfs.append(cframe)
    return frames, {name: by_name[name]['parent_name'] or None for name in names}, ctrl_xfs, 1.0


def _evaluate_quadruped_frames(by_name, local_xf, world_xf, controls, count):
    ident = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0))
    exact = set(by_name)
    by_case = {k.casefold(): k for k in by_name}
    mapped = {}
    for src, xfs in controls.items():
        tgt = _resolve_quadruped_bone(src, exact, by_case)
        if tgt is not None:
            mapped[tgt] = xfs

    edit_rig = 'pelvis' in by_name
    src_parents = rig_rules.quadruped_source_parents(
        {name: by_name[name]['parent_name'] or None for name in by_name},
        mapped,
        edit_rig=edit_rig,
    )
    active_bones = list(src_parents)
    src_ref = {name: (world_xf[name][0], (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0)) for name in active_bones}
    src_local = {
        name: (src_ref[name] if src_parents[name] is None else _t_mul(src_ref[name], _t_inv(src_ref[src_parents[name]])))
        for name in active_bones
    }
    retarget_bind = {name: _t_mul(world_xf[name], _t_inv(src_ref[name])) for name in active_bones}
    frames = []
    ctrl_xfs = []
    for idx in range(count):
        src_poses = {}

        def _src_pose(name: str):
            if name not in src_poses:
                ctrl = mapped[name][idx] if name in mapped else ident
                local = _t_mul(ctrl, src_local[name])
                parent = src_parents[name]
                src_poses[name] = local if parent is None else _t_mul(local, _src_pose(parent))
            return src_poses[name]

        for name in active_bones:
            _src_pose(name)
        poses = {name: _t_mul(retarget_bind[name], src_poses[name]) for name in active_bones}
        cframe = {
            name: (ident[1], ident[2]) if src_parents[name] is None else (src_poses[src_parents[name]][1], src_poses[src_parents[name]][2])
            for name in active_bones
        }
        if edit_rig:
            poses['pelvis'] = _t_mul(local_xf['pelvis'], poses['root'])
            cframe['pelvis'] = (poses['root'][1], poses['root'][2])
        frames.append(poses)
        ctrl_xfs.append(cframe)
    return frames, src_parents, ctrl_xfs, 1.0


def _biped_source_layout(world_xf):
    positions, scale = rig_rules.biped_source_layout(
        world_xf['root'][0],
        world_xf['pelvis'][0] if 'pelvis' in world_xf else world_xf['root'][0],
        world_xf['head'][0] if 'head' in world_xf else None,
        {name: world_xf[name][0] for name in ('head', 'left_arm', 'right_arm', 'left_leg', 'right_leg') if name in world_xf},
    )
    return {name: (loc, (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0)) for name, loc in positions.items()}, scale


def _evaluate_biped_frames(by_name, local_xf, world_xf, controls, count):
    ident = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0))
    ctrl_by_src = {}
    for src, xfs in controls.items():
        name = _biped_control_name(src)
        if name is not None:
            ctrl_by_src[name] = xfs
    src_local, trans_scale = _biped_source_layout(world_xf)
    src_ref = {}
    for name, parent in rig_rules.BIPED_PARENTS.items():
        lx = src_local[name]
        src_ref[name] = lx if parent is None else _t_mul(lx, src_ref[parent])
    retarget_bind = {
        tgt: _t_mul(world_xf[tgt], _t_inv(src_ref[src]))
        for tgt, src in rig_rules.BIPED_TARGETS.items()
        if tgt in by_name
    }
    scale_trans = abs(trans_scale - 1.0) > 1e-6
    frames = []
    ctrl_xfs = []
    for idx in range(count):
        src_poses = {}
        for name, parent in rig_rules.BIPED_PARENTS.items():
            ctrl = ctrl_by_src[name][idx] if name in ctrl_by_src else ident
            if scale_trans:
                p, q, sc = ctrl
                ctrl = ((p[0] * trans_scale, p[1] * trans_scale, p[2] * trans_scale), q, sc)
            lx = _t_mul(ctrl, src_local[name])
            src_poses[name] = lx if parent is None else _t_mul(lx, src_poses[parent])
        poses = {}
        cframe = {}
        for tgt, src in rig_rules.BIPED_TARGETS.items():
            if tgt in retarget_bind:
                poses[tgt] = _t_mul(retarget_bind[tgt], src_poses[src])
                sp = rig_rules.BIPED_PARENTS[src]
                cframe[tgt] = (ident[1], ident[2]) if sp is None else (src_poses[sp][1], src_poses[sp][2])

        def _fill(bone_name: str):
            if bone_name not in poses:
                parent = by_name[bone_name]['parent_name']
                base = _t_mul(local_xf[bone_name], _fill(parent)) if parent in by_name else world_xf[bone_name]
                poses[bone_name] = base
                cframe[bone_name] = (base[1], base[2])
            return poses[bone_name]

        for name in by_name:
            _fill(name)
        frames.append(poses)
        ctrl_xfs.append(cframe)
    src_parents = {
        name: rig_rules.BIPED_PARENTS[rig_rules.BIPED_TARGETS[name]] if name in rig_rules.BIPED_TARGETS else (by_name[name]['parent_name'] or None)
        for name in by_name
    }
    return frames, src_parents, ctrl_xfs, trans_scale


def evaluate_fk(glb_source, clip_source, *, clip=None, fps=60.0, mode=None) -> dict:
    """Evaluate exact per-bone world transforms and 8-corner AABBs across sampled frames."""
    records = _bounds_list(glb_source)
    by_name, local_xf, world_xf = _reference_transforms(records)
    clip_name, clip_dict = _load_clip_entry(clip_source, clip=clip)
    duration, times, samples, _pre = sampling.compile_animation(clip_name, clip_dict, fps)
    count = len(times)
    resolved_mode = mode or _detect_mode(by_name, clip_dict.get('bones', {}))
    controls = _sample_controls(samples, count)

    if resolved_mode == 'biped':
        frames, src_parents, ctrl_xfs, trans_scale = _evaluate_biped_frames(by_name, local_xf, world_xf, controls, count)
    elif resolved_mode == 'quadruped':
        frames, src_parents, ctrl_xfs, trans_scale = _evaluate_quadruped_frames(by_name, local_xf, world_xf, controls, count)
    elif resolved_mode == 'local':
        frames, src_parents, ctrl_xfs, trans_scale = _evaluate_local_frames(by_name, local_xf, world_xf, controls, count)
    else:
        raise ValueError(f'不支持的 FK 模式: {resolved_mode}')

    bones_out = {}
    for name, rec in by_name.items():
        xfs = [frame[name] for frame in frames]
        entry = {
            'parent_name': rec['parent_name'],
            'source_parent': src_parents.get(name),
            'has_bounds': bool(rec.get('has_bounds')),
            'rest_world': world_xf[name],
            'world_transforms': xfs,
            'ctrl_parent_xfs': [cframe[name] for cframe in ctrl_xfs],
            'positions': [xf[0] for xf in xfs],
        }
        if entry['has_bounds']:
            bmin, bmax = rec['local_min'], rec['local_max']
            local_corners = tuple(
                (x, y, z)
                for x in (bmin[0], bmax[0])
                for y in (bmin[1], bmax[1])
                for z in (bmin[2], bmax[2])
            )
            entry['corners'] = [tuple(_t_point(xf, c) for c in local_corners) for xf in xfs]
        bones_out[name] = entry

    return {
        'clip': clip_name,
        'mode': resolved_mode,
        'translation_scale': float(trans_scale),
        'duration': duration,
        'fps': float(fps),
        'frame_count': count,
        'times': times,
        'pre_indices': sorted(_pre),
        'bounds_records': records,
        'bones': bones_out,
    }


def _in_window(t: float, t0: float, t1: float, eps: float = 1e-6) -> bool:
    if t0 <= t1:
        return (t0 - eps) <= t <= (t1 + eps)
    return t >= (t0 - eps) or t <= (t1 + eps)


def _window_elapsed(t: float, t0: float, t1: float, duration: float) -> float:
    if t0 <= t1 or t >= t0 - 1e-6:
        return t - t0
    return t + duration - t0


def _sole_metrics(corners: tuple[tuple[float, float, float], ...]) -> tuple[float, float, float]:
    min_z = min(p[2] for p in corners)
    sole = [p for p in corners if p[2] <= min_z + 0.5]
    cx = sum(p[0] for p in sole) / len(sole)
    cy = sum(p[1] for p in sole) / len(sole)
    return min_z, cx, cy


def _default_limbs(bones: dict[str, dict]) -> tuple[str, ...]:
    quad = tuple(b for b in ('left_front_leg', 'right_front_leg', 'left_hind_leg', 'right_hind_leg')
                 if b in bones and bones[b]['has_bounds'])
    if quad:
        return quad
    return tuple(b for b in ('left_leg', 'right_leg') if b in bones and bones[b]['has_bounds'])


def _default_attachments(bones: dict[str, dict]) -> tuple[tuple[str, str], ...]:
    candidates = (
        ('left_leg', 'body'),
        ('right_leg', 'body'),
        ('left_arm', 'body'),
        ('right_arm', 'body'),
        ('arms', 'body'),
        ('left_hind_leg', 'pelvis'),
        ('right_hind_leg', 'pelvis'),
        ('left_front_leg', 'body'),
        ('right_front_leg', 'body'),
        ('head_parts', 'body'),
        ('neck', 'body'),
        ('head', 'body'),
    )
    return tuple((c, p) for c, p in candidates if c in bones and p in bones)


def analyze_contacts(glb_source, clip_source, *, clip=None, fps=60.0, mode=None,
                     stance_windows=None, travel_speed_cm_s=0.0,
                     limbs=None, attachments=None) -> dict:
    """Measure sole Z, stance-phase ground sliding, and proximal socket seam drift."""
    fk = evaluate_fk(glb_source, clip_source, clip=clip, fps=fps, mode=mode)
    bones = fk['bones']
    times = fk['times']
    duration = fk['duration']
    limb_names = tuple(limbs) if limbs is not None else _default_limbs(bones)
    att_pairs = tuple(attachments) if attachments is not None else _default_attachments(bones)
    stance_map = stance_windows or {}

    limb_report = {}
    for limb in limb_names:
        info = bones.get(limb)
        if not info or not info.get('has_bounds'):
            raise ValueError(f'骨骼缺少包围盒或不存在: {limb}')
        sole = [_sole_metrics(cs) for cs in info['corners']]
        zs = [item[0] for item in sole]
        windows_out = []
        for t0, t1 in stance_map.get(limb, ()):
            idxs = [i for i, t in enumerate(times) if _in_window(t, float(t0), float(t1))]
            if not idxs:
                continue
            wzs = [sole[i][0] for i in idxs]
            gxs = [sole[i][1] + float(travel_speed_cm_s) * _window_elapsed(times[i], float(t0), float(t1), duration)
                   for i in idxs]
            gys = [sole[i][2] for i in idxs]
            gx0, gy0 = gxs[0], gys[0]
            xy_drift = max(math.hypot(gx - gx0, gy - gy0) for gx, gy in zip(gxs, gys))
            windows_out.append({
                'window': (float(t0), float(t1)),
                'samples': len(idxs),
                'min_z_cm': round(min(wzs), 4),
                'max_z_cm': round(max(wzs), 4),
                'mean_z_cm': round(sum(wzs) / len(wzs), 4),
                'x_span_cm': round(max(gxs) - min(gxs), 4),
                'y_span_cm': round(max(gys) - min(gys), 4),
                'xy_drift_cm': round(xy_drift, 4),
            })
        limb_report[limb] = {
            'min_sole_z_cm': round(min(zs), 4),
            'max_sole_z_cm': round(max(zs), 4),
            'stance': windows_out,
        }

    seam_report = {}
    for child, parent in att_pairs:
        if child not in bones or parent not in bones:
            continue
        c_rest = bones[child]['rest_world']
        p_rest = bones[parent]['rest_world']
        anchor_on_parent = _t_point(_t_inv(p_rest), c_rest[0])
        p_xfs = bones[parent]['world_transforms']
        c_xfs = bones[child]['world_transforms']
        gaps = []
        max_idx = 0
        max_delta = (0.0, 0.0, 0.0)
        max_gap = -1.0
        for i, (pxf, cxf) in enumerate(zip(p_xfs, c_xfs)):
            expected = _t_point(pxf, anchor_on_parent)
            actual = cxf[0]
            delta = (actual[0] - expected[0], actual[1] - expected[1], actual[2] - expected[2])
            gap = math.sqrt(delta[0] * delta[0] + delta[1] * delta[1] + delta[2] * delta[2])
            gaps.append(gap)
            if gap > max_gap:
                max_gap = gap
                max_idx = i
                max_delta = delta
        seam_report[f'{child}->{parent}'] = {
            'max_gap_cm': round(max_gap, 4),
            'mean_gap_cm': round(sum(gaps) / len(gaps), 4),
            'max_time': round(times[max_idx], 4),
            'max_delta_cm': tuple(round(v, 4) for v in max_delta),
        }

    return {
        'clip': fk['clip'],
        'mode': fk['mode'],
        'duration': fk['duration'],
        'fps': fk['fps'],
        'frame_count': fk['frame_count'],
        'limbs': limb_report,
        'seams': seam_report,
    }


def _time_key(t: float) -> str:
    return f'{round(float(t), 5):g}'


def _smoothstep(u: float) -> float:
    u = max(0.0, min(1.0, float(u)))
    return u * u * (3.0 - 2.0 * u)


def _smooth_stance_deltas(post_times: list[float], active_deltas: list[float | None],
                          *, duration: float, is_loop: bool, blend_sec: float) -> list[float]:
    """Compute world-Z compensation offsets with C1 ramps outside active stance windows."""
    if not any(v is not None for v in active_deltas):
        return [0.0] * len(post_times)
    if blend_sec <= 0.0 or all(v is not None for v in active_deltas):
        return [0.0 if v is None else v for v in active_deltas]

    if is_loop and len(post_times) > 1 and duration > 0.0:
        ring = list(active_deltas[:-1])
        ring_times = list(post_times[:-1])
        if active_deltas[0] is not None and active_deltas[-1] is None:
            ring[0] = active_deltas[0]
        elif active_deltas[-1] is not None and active_deltas[0] is None:
            ring[0] = active_deltas[-1]
        n = len(ring)
        active_idxs = [j for j, v in enumerate(ring) if v is not None]
        out = [0.0] * n
        for pos, j in enumerate(active_idxs):
            out[j] = ring[j]
            nxt = active_idxs[(pos + 1) % len(active_idxs)]
            gap = (ring_times[nxt] - ring_times[j]) % duration
            if gap <= 0.0:
                continue
            v_prev, v_next = ring[j], ring[nxt]
            k = (j + 1) % n
            while k != nxt:
                d_prev = (ring_times[k] - ring_times[j]) % duration
                d_next = gap - d_prev
                if gap <= blend_sec:
                    s = _smoothstep(d_prev / gap)
                    out[k] = (1.0 - s) * v_prev + s * v_next
                else:
                    eff_b = min(blend_sec, 0.5 * gap)
                    if d_prev < eff_b:
                        out[k] = _smoothstep(1.0 - d_prev / eff_b) * v_prev
                    elif d_next < eff_b:
                        out[k] = _smoothstep(1.0 - d_next / eff_b) * v_next
                k = (k + 1) % n
        return out + [out[0]]

    out = [0.0 if v is None else v for v in active_deltas]
    n = len(post_times)
    active_idxs = [j for j, v in enumerate(active_deltas) if v is not None]
    first, last = active_idxs[0], active_idxs[-1]
    for k in range(first):
        d_next = post_times[first] - post_times[k]
        if d_next < blend_sec:
            out[k] = _smoothstep(1.0 - d_next / blend_sec) * active_deltas[first]
    for pos in range(len(active_idxs) - 1):
        j, nxt = active_idxs[pos], active_idxs[pos + 1]
        gap = post_times[nxt] - post_times[j]
        v_prev, v_next = active_deltas[j], active_deltas[nxt]
        for k in range(j + 1, nxt):
            d_prev = post_times[k] - post_times[j]
            d_next = gap - d_prev
            if gap <= blend_sec:
                s = _smoothstep(d_prev / gap)
                out[k] = (1.0 - s) * v_prev + s * v_next
            else:
                eff_b = min(blend_sec, 0.5 * gap)
                if d_prev < eff_b:
                    out[k] = _smoothstep(1.0 - d_prev / eff_b) * v_prev
                elif d_next < eff_b:
                    out[k] = _smoothstep(1.0 - d_next / eff_b) * v_next
    for k in range(last + 1, n):
        d_prev = post_times[k] - post_times[last]
        if d_prev < blend_sec:
            out[k] = _smoothstep(1.0 - d_prev / blend_sec) * active_deltas[last]
    return out


def compensate_stance_root_z(glb_source, clip_data, *, stance_windows, fps=60.0,
                             mode=None, limbs=None, target_z_cm=0.0, blend_sec=0.06) -> dict:
    """Return a copy of `clip_data` with `root.position` adjusted so active stance soles meet `target_z_cm`."""
    blend = float(blend_sec)
    if blend < 0.0:
        raise ValueError(f'blend_sec 须为非负数: {blend_sec}')
    out = deepcopy(clip_data)
    clip_name, clip_dict = _load_clip_entry(out)
    fk = evaluate_fk(glb_source, clip_dict, clip=clip_name, fps=fps, mode=mode)
    bones = fk['bones']
    times = fk['times']
    duration = fk['duration']
    trans_scale = fk['translation_scale']
    root_ctrl_xfs = bones['root']['ctrl_parent_xfs']
    limb_names = tuple(limbs) if limbs is not None else tuple(stance_windows)
    sole_z = {
        limb: [min(p[2] for p in bones[limb]['corners'][i]) for i in range(len(times))]
        for limb in limb_names
    }

    bones_dict = clip_dict.setdefault('bones', {})
    root_entry = bones_dict.setdefault('root', {})
    pos_keys = sampling.channel(root_entry.get('position', [0.0, 0.0, 0.0]), f'{clip_name}/root/position')
    pre_set = set(fk['pre_indices'])
    post_indices = [i for i in range(len(times)) if i not in pre_set]
    post_times = [times[i] for i in post_indices]
    active_deltas: list[float | None] = []
    for i in post_indices:
        t = times[i]
        active = [
            limb for limb in limb_names
            if any(_in_window(t, float(t0), float(t1)) for t0, t1 in stance_windows.get(limb, ()))
        ]
        if active:
            min_z = min(sole_z[limb][i] for limb in active)
            active_deltas.append(float(target_z_cm) - min_z)
        else:
            active_deltas.append(None)

    is_loop = bool(clip_dict.get('loop', False)) and duration > 0.0
    deltas_cm = _smooth_stance_deltas(
        post_times, active_deltas, duration=duration, is_loop=is_loop, blend_sec=blend,
    )
    timeline = {}
    for i, dz_cm in zip(post_indices, deltas_cm):
        t = times[i]
        base = list(sampling.evaluate(pos_keys, t, (0.0, 0.0, 0.0)))
        if abs(dz_cm) > 1e-9:
            rq, rs = root_ctrl_xfs[i]
            local_delta = _qrot(_qconj(rq), (0.0, 0.0, dz_cm))
            local_delta = (local_delta[0] / rs[0], local_delta[1] / rs[1], local_delta[2] / rs[2])
            add_bedrock = rig_rules.ue_cm_to_bedrock_pos(local_delta, scale=trans_scale)
            base = [base[ax] + add_bedrock[ax] for ax in range(3)]
        timeline[_time_key(t)] = [round(v, 4) for v in base]
    if is_loop:
        timeline[_time_key(duration)] = list(timeline[_time_key(0.0)])
    root_entry['position'] = timeline
    return out


def compensate_limb_attachment(glb_source, clip_data, *, child_bone, parent_bone,
                               fps=60.0, mode=None) -> dict:
    """Return a copy of `clip_data` solving `child_bone.position` to stay seated against `parent_bone`."""
    out = deepcopy(clip_data)
    clip_name, clip_dict = _load_clip_entry(out)
    fk = evaluate_fk(glb_source, clip_dict, clip=clip_name, fps=fps, mode=mode)
    bones = fk['bones']
    if child_bone not in bones or parent_bone not in bones:
        raise ValueError(f'骨骼不存在: {child_bone} / {parent_bone}')

    c_rest = bones[child_bone]['rest_world']
    p_rest = bones[parent_bone]['rest_world']
    anchor_on_parent = _t_point(_t_inv(p_rest), c_rest[0])
    child_ctrl_xfs = bones[child_bone]['ctrl_parent_xfs']
    trans_scale = fk['translation_scale']
    p_xfs = bones[parent_bone]['world_transforms']
    c_xfs = bones[child_bone]['world_transforms']
    times = fk['times']
    duration = fk['duration']

    bones_dict = clip_dict.setdefault('bones', {})
    # Match exact source bone key casing if already authored in camelCase (e.g. leftLeg).
    target_key = next((k for k in bones_dict if k.casefold() == child_bone.casefold()
                       or (_biped_control_name(k) == child_bone.replace('_', ''))), child_bone)
    child_entry = bones_dict.setdefault(target_key, {})
    pos_keys = sampling.channel(child_entry.get('position', [0.0, 0.0, 0.0]), f'{clip_name}/{target_key}/position')

    pre_set = set(fk['pre_indices'])
    timeline = {}
    for i, t in enumerate(times):
        if i in pre_set:
            continue
        base = list(sampling.evaluate(pos_keys, t, (0.0, 0.0, 0.0)))
        desired_world = _t_point(p_xfs[i], anchor_on_parent)
        actual_world = c_xfs[i][0]
        world_delta = (
            desired_world[0] - actual_world[0],
            desired_world[1] - actual_world[1],
            desired_world[2] - actual_world[2],
        )
        cq, cs = child_ctrl_xfs[i]
        local_delta = _qrot(_qconj(cq), world_delta)
        local_delta = (local_delta[0] / cs[0], local_delta[1] / cs[1], local_delta[2] / cs[2])
        add_bedrock = rig_rules.ue_cm_to_bedrock_pos(local_delta, scale=trans_scale)
        timeline[_time_key(t)] = [round(base[ax] + add_bedrock[ax], 4) for ax in range(3)]
    if clip_dict.get('loop', False) and duration > 0.0:
        timeline[_time_key(duration)] = list(timeline[_time_key(0.0)])
    child_entry['position'] = timeline
    return out
