"""Blockbench .bbmodel (5.0 / free) parser, validator and Sequencer curve compiler.

Pure Python with no Unreal Engine runtime imports so unit tests can validate
metadata, skeleton matching, mixed curves, Catmull-Rom conversion and coupled
3D rotations offline.
"""

import bisect
import math
import re

from . import curves, sampling

SUPPORTED_FORMAT_VERSION = '5.0'
SUPPORTED_MODEL_FORMAT = 'free'
BB_TO_CM = 6.25
BIND_POS_TOL_CM = 1.0
BIND_ROT_TOL_DEG = 0.1
BIND_SCALE_TOL = 1e-4
DEFAULT_BEZIER_LEFT_TIME = -0.1
DEFAULT_BEZIER_RIGHT_TIME = 0.1

_FLOAT_RE = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')
_VALID_CHANNELS = frozenset(('rotation', 'position', 'scale'))
_VALID_INTERPS = frozenset(('step', 'linear', 'catmullrom', 'bezier'))
_VALID_LOOPS = frozenset((None, 'once', 'loop', 'hold'))
_UNSUPPORTED_CLIP_FIELDS = ('anim_time_update', 'blend_weight', 'start_delay', 'loop_delay')
_NEUTRAL = {'position': 0.0, 'rotation': 0.0, 'scale': 1.0}

# Blockbench (X_left, Y_up, Z_fwd) -> UE (X_fwd, Y_right, Z_up).
_AXIS_MAP = {
    'position': (
        ('Location.X', 2, -BB_TO_CM),
        ('Location.Y', 0, -BB_TO_CM),
        ('Location.Z', 1, BB_TO_CM),
    ),
    'rotation': (
        ('Rotation.X', 2, 1.0),
        ('Rotation.Y', 0, 1.0),
        ('Rotation.Z', 1, 1.0),
    ),
    'scale': (
        ('Scale.X', 2, 1.0),
        ('Scale.Y', 0, 1.0),
        ('Scale.Z', 1, 1.0),
    ),
}
_BB_TO_UE_SINGLE_ROT = {
    0: ('Rotation.Y', 'rotation', 1.0),
    1: ('Rotation.Z', 'rotation', 1.0),
    2: ('Rotation.X', 'rotation', 1.0),
}
_UE_ROT_PARTS = ('Rotation.X', 'Rotation.Y', 'Rotation.Z')


def is_bbmodel(data):
    """Return True when parsed JSON looks like a Blockbench .bbmodel document."""
    return (isinstance(data, dict)
            and isinstance(data.get('meta'), dict)
            and ('animations' in data or 'groups' in data or 'outliner' in data))


def validate_model_meta(data):
    """Require the supported .bbmodel format version and model format."""
    if not isinstance(data, dict) or not isinstance(data.get('meta'), dict):
        raise ValueError('.bbmodel 缺少 meta 对象')
    meta = data['meta']
    version = meta.get('format_version')
    if version != SUPPORTED_FORMAT_VERSION:
        raise ValueError(
            f'不支持的 .bbmodel format_version: {version!r}（当前仅支持 {SUPPORTED_FORMAT_VERSION!r}）'
        )
    model_format = meta.get('model_format')
    if model_format != SUPPORTED_MODEL_FORMAT:
        raise ValueError(
            f'不支持的 .bbmodel model_format: {model_format!r}（当前仅支持 {SUPPORTED_MODEL_FORMAT!r}）'
        )
    return meta


def parse_number(value, label='数值'):
    """Parse finite numeric literals and numeric strings; reject MoLang without eval."""
    if isinstance(value, bool):
        raise ValueError(f'{label} 不能为布尔值')
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text or not _FLOAT_RE.match(text):
            raise ValueError(f'不支持 MoLang 表达式或非数值 ({label}): {value!r}')
        number = float(text)
    else:
        raise ValueError(f'无效的数值类型 ({label}): {type(value).__name__}')
    if not math.isfinite(number):
        raise ValueError(f'{label} 必须为有限数值')
    return number


def _parse_vec3(value, label, default=None):
    if isinstance(value, dict):
        return tuple(
            default if (axis not in value and default is not None)
            else parse_number(value.get(axis), f'{label}.{axis}')
            for axis in ('x', 'y', 'z')
        )
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return tuple(parse_number(item, f'{label}[{i}]') for i, item in enumerate(value))
    raise ValueError(f'{label} 须为三维向量对象或三元组')


def _bb_vec_to_ue_cm(vec):
    return (-vec[2] * BB_TO_CM, -vec[0] * BB_TO_CM, vec[1] * BB_TO_CM)


def parse_groups(data):
    """Parse 5.0 groups + outliner hierarchy into bone records indexed by UUID and name."""
    raw_groups = data.get('groups')
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError('.bbmodel 缺少 groups 骨骼定义')
    by_uuid = {}
    for entry in raw_groups:
        if not isinstance(entry, dict):
            raise ValueError('.bbmodel groups 条目须为对象')
        uuid = entry.get('uuid')
        name = entry.get('name')
        if not isinstance(uuid, str) or not uuid or not isinstance(name, str) or not name.strip():
            raise ValueError('.bbmodel group 缺少有效的 uuid 或 name')
        if uuid in by_uuid:
            raise ValueError(f'.bbmodel 存在重复 group uuid: {uuid}')
        origin = _parse_vec3(entry.get('origin', (0.0, 0.0, 0.0)), f'{name}.origin')
        rotation = _parse_vec3(entry.get('rotation', (0.0, 0.0, 0.0)), f'{name}.rotation')
        by_uuid[uuid] = {'uuid': uuid, 'name': name, 'origin': origin, 'rotation': rotation}

    outliner = data.get('outliner')
    if not isinstance(outliner, list) or not outliner:
        raise ValueError('.bbmodel 缺少 outliner 层级定义')

    bones_by_uuid = {}
    bones_by_name = {}

    def walk(nodes, parent_uuid, parent_origin):
        for node in nodes:
            if isinstance(node, str):
                continue
            if not isinstance(node, dict):
                raise ValueError('.bbmodel outliner 节点须为元素 uuid 或分组对象')
            uuid = node.get('uuid')
            if uuid not in by_uuid:
                raise ValueError(f'.bbmodel outliner 引用了未知 group uuid: {uuid!r}')
            if uuid in bones_by_uuid:
                raise ValueError(f'.bbmodel outliner 中重复出现 group uuid: {uuid}')
            group = by_uuid[uuid]
            name = group['name']
            if name in bones_by_name:
                raise ValueError(f'.bbmodel 存在同名骨骼: {name}')
            origin = group['origin']
            local_bb = tuple(origin[i] - parent_origin[i] for i in range(3))
            parent_name = bones_by_uuid[parent_uuid]['name'] if parent_uuid else None
            record = {
                'uuid': uuid,
                'name': name,
                'parent': parent_name,
                'origin': origin,
                'local_origin': local_bb,
                'local_pos_cm': _bb_vec_to_ue_cm(local_bb),
                'rotation': group['rotation'],
            }
            bones_by_uuid[uuid] = record
            bones_by_name[name] = record
            children = node.get('children') or []
            if not isinstance(children, list):
                raise ValueError(f'.bbmodel 骨骼 {name} 的 children 须为列表')
            walk(children, uuid, origin)

    walk(outliner, None, (0.0, 0.0, 0.0))
    if len(bones_by_uuid) != len(by_uuid):
        missing = sorted(set(by_uuid) - set(bones_by_uuid))
        raise ValueError(f'.bbmodel outliner 缺少 groups 引用: {missing[0]}')
    return bones_by_uuid, bones_by_name


def extract_bind_trs(ref_entry, name):
    """Extract (translation, rotation_rpy_deg, scale) tuples from a describe_skeleton entry."""
    if not isinstance(ref_entry, dict) or 'local' not in ref_entry:
        raise ValueError(f'目标骨架条目无效: {name}')
    local = ref_entry['local']
    if hasattr(local, 'translation'):
        t = local.translation
        r = local.rotation.rotator()
        s = local.scale3d
        return (
            (float(t.x), float(t.y), float(t.z)),
            (float(r.roll), float(r.pitch), float(r.yaw)),
            (float(s.x), float(s.y), float(s.z)),
        )
    if isinstance(local, (tuple, list)) and len(local) == 9:
        return tuple(local[:3]), tuple(local[3:6]), tuple(local[6:9])
    if isinstance(local, dict):
        return (
            tuple(local.get('translation', (0.0, 0.0, 0.0))),
            tuple(local.get('rotation', (0.0, 0.0, 0.0))),
            tuple(local.get('scale', (1.0, 1.0, 1.0))),
        )
    raise ValueError(f'不支持的目标骨架局部变换类型: {name}')


def reference_case_map(reference):
    """Build casefold -> canonical target bone lookup, flagging case collisions as ambiguous."""
    by_case = {}
    ambiguous = set()
    for name in reference:
        key = name.casefold()
        if key in ambiguous:
            continue
        if key in by_case:
            del by_case[key]
            ambiguous.add(key)
        else:
            by_case[key] = name
    return by_case, ambiguous


def validate_target_skeleton(bones_by_name, reference, *, pos_tol=BIND_POS_TOL_CM):
    """Ensure every .bbmodel bone matches parent and bind pose on the target UE skeleton."""
    for name, bone in bones_by_name.items():
        if max(abs(angle) for angle in bone['rotation']) > BIND_ROT_TOL_DEG:
            raise ValueError(f'暂不支持带非零静态旋转的 .bbmodel 骨骼: {name} {bone["rotation"]}')
        if name not in reference:
            raise ValueError(f'目标 UE 骨架缺少 .bbmodel 骨骼: {name}')
        ref = reference[name]
        if ref.get('parent') != bone['parent']:
            raise ValueError(f'骨骼父级不匹配: {name} (bb={bone["parent"]!r}, ue={ref.get("parent")!r})')
        ue_pos, ue_rot, ue_scale = extract_bind_trs(ref, name)
        if max(abs(a) for a in ue_rot) > BIND_ROT_TOL_DEG:
            raise ValueError(f'目标 UE 骨骼绑定旋转非零: {name} {ue_rot}')
        if max(abs(s - 1.0) for s in ue_scale) > BIND_SCALE_TOL:
            raise ValueError(f'目标 UE 骨骼绑定缩放非单位值: {name} {ue_scale}')
        bb_pos = bone['local_pos_cm']
        diff = max(abs(ue_pos[i] - bb_pos[i]) for i in range(3))
        if diff > pos_tol:
            raise ValueError(
                f'骨骼绑定位置超出容差 ({pos_tol} cm): {name} bb={bb_pos} ue={ue_pos}'
            )


def _anim_header_info(anim, index):
    name = anim.get('name')
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f'.bbmodel 第 {index} 个动画缺少有效 name')
    loop = anim.get('loop')
    if loop not in _VALID_LOOPS:
        raise ValueError(f'动画 {name} 的 loop 模式无效: {loop!r}')
    return {
        'clip': name,
        'loop': loop == 'loop',
        'loop_mode': loop or 'once',
    }


def resolve_clips(data):
    """Validate .bbmodel meta + groups and return tagged per-clip payloads by name."""
    validate_model_meta(data)
    parse_groups(data)
    raw_anims = data.get('animations')
    if not isinstance(raw_anims, list) or not raw_anims:
        raise ValueError('.bbmodel 缺少 animations 片段列表')
    clips = {}
    for index, anim in enumerate(raw_anims):
        if not isinstance(anim, dict):
            raise ValueError(f'.bbmodel animations[{index}] 须为对象')
        header = _anim_header_info(anim, index)
        name = header['clip']
        if name in clips:
            raise ValueError(f'.bbmodel 存在重复动画名: {name}')
        clips[name] = {
            '_format': 'bbmodel',
            'model': data,
            'animation': anim,
            'loop': header['loop'],
        }
    return clips


def _parse_keyframe(kf, bone_name, neutral, index):
    if not isinstance(kf, dict):
        raise ValueError(f'{bone_name} 第 {index} 个关键帧须为对象')
    if kf.get('quaternion_interpolation'):
        raise ValueError(f'暂不支持四元数插值标记: {bone_name}')
    channel = kf.get('channel')
    if channel not in _VALID_CHANNELS:
        raise ValueError(f'不支持的关键帧通道 {channel!r} ({bone_name})')
    interp = kf.get('interpolation', 'linear')
    if interp not in _VALID_INTERPS:
        raise ValueError(f'不支持的关键帧插值方式 {interp!r} ({bone_name}.{channel})')
    time = parse_number(kf.get('time'), f'{bone_name}.{channel}.time')
    if time < 0.0:
        raise ValueError(f'关键帧时间不能为负数: {bone_name}.{channel} t={time}')
    data_points = kf.get('data_points')
    if not isinstance(data_points, list) or len(data_points) not in (1, 2):
        raise ValueError(f'{bone_name}.{channel} data_points 须包含 1 或 2 个点')
    label = f'{bone_name}.{channel}@{time}'
    pre = _parse_vec3(data_points[0], f'{label}[0]', default=neutral)
    post = _parse_vec3(data_points[-1], f'{label}[1]', default=neutral)
    left_time = _parse_vec3(
        (DEFAULT_BEZIER_LEFT_TIME,) * 3 if kf.get('bezier_left_time') is None else kf.get('bezier_left_time'),
        f'{label}.bezier_left_time')
    left_val = _parse_vec3(
        (0.0, 0.0, 0.0) if kf.get('bezier_left_value') is None else kf.get('bezier_left_value'),
        f'{label}.bezier_left_value')
    right_time = _parse_vec3(
        (DEFAULT_BEZIER_RIGHT_TIME,) * 3 if kf.get('bezier_right_time') is None else kf.get('bezier_right_time'),
        f'{label}.bezier_right_time')
    right_val = _parse_vec3(
        (0.0, 0.0, 0.0) if kf.get('bezier_right_value') is None else kf.get('bezier_right_value'),
        f'{label}.bezier_right_value')
    return {
        'channel': channel,
        'interp': interp,
        'time': time,
        'pre': pre,
        'post': post,
        'split': len(data_points) == 2,
        'jump': len(data_points) == 2 and any(post[i] != pre[i] for i in range(3)),
        'left_time': left_time,
        'left_value': left_val,
        'right_time': right_time,
        'right_value': right_val,
    }


def _parse_animation_channels(model, anim, bones_by_uuid):
    name = anim['name']
    loop = anim.get('loop')
    if loop not in _VALID_LOOPS:
        raise ValueError(f'动画 {name} 的 loop 模式无效: {loop!r}')
    if anim.get('rotation_global') or anim.get('quaternion_interpolation'):
        raise ValueError(f'暂不支持片段级全局旋转或四元数插值设置 ({name})')
    for field in _UNSUPPORTED_CLIP_FIELDS:
        val = anim.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            continue
        raise ValueError(f'暂不支持 MoLang / 时间控制字段 {field}: {val!r} ({name})')
    length = parse_number(anim.get('length', 0.0), f'{name}.length')
    if length <= 0.0:
        raise ValueError(f'动画 {name} 的 length 必须大于 0')

    animators = anim.get('animators')
    if animators is None:
        animators = {}
    if not isinstance(animators, dict):
        raise ValueError(f'动画 {name} 的 animators 须为对象')

    channels = {}
    max_time = 0.0
    for uuid_key, animator in animators.items():
        if not isinstance(animator, dict):
            raise ValueError(f'动画 {name} 的 animator {uuid_key} 须为对象')
        raw_kfs = animator.get('keyframes') or []
        if not isinstance(raw_kfs, list):
            raise ValueError(f'animator {uuid_key} 的 keyframes 须为列表')
        anim_type = animator.get('type', 'bone')
        if raw_kfs and anim_type != 'bone':
            raise ValueError(f'暂不支持非骨骼动画器 {anim_type!r}: {animator.get("name", uuid_key)}')
        if not raw_kfs:
            continue
        if animator.get('rotation_global') or animator.get('quaternion_interpolation'):
            raise ValueError(f'暂不支持骨骼全局旋转或四元数插值: {animator.get("name", uuid_key)}')
        if uuid_key not in bones_by_uuid:
            raise ValueError(f'动画 {name} 引用了未知骨骼 UUID: {uuid_key}')
        bone_name = bones_by_uuid[uuid_key]['name']
        grouped = {'rotation': [], 'position': [], 'scale': []}
        for idx, kf in enumerate(raw_kfs):
            ch_name = kf.get('channel') if isinstance(kf, dict) else None
            if ch_name not in _VALID_CHANNELS:
                raise ValueError(f'不支持的关键帧通道 {ch_name!r} ({bone_name})')
            parsed = _parse_keyframe(kf, bone_name, _NEUTRAL[ch_name], idx)
            max_time = max(max_time, parsed['time'])
            grouped[ch_name].append(parsed)
        for ch_name, items in grouped.items():
            if not items:
                continue
            items.sort(key=lambda item: item['time'])
            for first, second in zip(items, items[1:]):
                if second['time'] <= first['time']:
                    raise ValueError(
                        f'{bone_name}.{ch_name} 存在重复或乱序关键帧时间: {first["time"]} / {second["time"]}'
                    )
                # Blockbench trims spline neighbors for two-data-point keys,
                # even if pre == post. The ordinary four-point conversion is
                # not equivalent; reject this combination before editing UE.
                if _segment_mode(first, second) == 'catmullrom' and (first['split'] or second['split']):
                    raise ValueError(
                        f'{bone_name}.{ch_name}: 暂不支持 Catmull-Rom 区间端点的双值 pre/post；'
                        '请将该区间改为 linear / bezier，或先烘焙为采样动画'
                    )
            channels[(bone_name, ch_name)] = items

    return {
        'clip': name,
        'duration': max(length, max_time),
        'is_loop': loop == 'loop',
        'channels': channels,
    }


def _segment_mode(k0, k1):
    m0, m1 = k0['interp'], k1['interp']
    if m0 == 'step':
        return 'constant'
    if m0 == 'linear' and m1 in ('linear', 'step'):
        return 'linear'
    if 'catmullrom' in (m0, m1):
        return 'catmullrom'
    if 'bezier' in (m0, m1):
        return 'bezier'
    return 'linear'


def _catmull_bezier_points(kfs, index, axis, is_loop, scale=1.0, time_offset=0.0, time_scale=1.0):
    k0, k1 = kfs[index], kfs[index + 1]
    t0 = time_offset + k0['time'] * time_scale
    t1 = time_offset + k1['time'] * time_scale
    v0 = k0['post'][axis] * scale
    v1 = k1['pre'][axis] * scale
    if index > 0:
        p_prev = kfs[index - 1]['post'][axis] * scale
    elif is_loop and len(kfs) >= 3:
        p_prev = kfs[-2]['post'][axis] * scale
    else:
        p_prev = v0
    if index + 2 < len(kfs):
        p_next = kfs[index + 2]['pre'][axis] * scale
    elif is_loop and len(kfs) >= 3:
        p_next = kfs[1]['pre'][axis] * scale
    else:
        p_next = v1
    dt = t1 - t0
    return (
        (t0, v0),
        (t0 + dt / 3.0, v0 + (v1 - p_prev) / 6.0),
        (t1 - dt / 3.0, v1 - (p_next - v0) / 6.0),
        (t1, v1),
    )


def _bezier_points(kfs, index, axis, scale=1.0, time_offset=0.0, time_scale=1.0):
    k0, k1 = kfs[index], kfs[index + 1]
    t0 = time_offset + k0['time'] * time_scale
    t1 = time_offset + k1['time'] * time_scale
    v0 = k0['post'][axis] * scale
    v1 = k1['pre'][axis] * scale
    p1x = min(max(t0 + k0['right_time'][axis] * time_scale, t0), t1)
    p2x = min(max(t1 + k1['left_time'][axis] * time_scale, t0), t1)
    return (
        (t0, v0),
        (p1x, v0 + k0['right_value'][axis] * scale),
        (p2x, v1 + k1['left_value'][axis] * scale),
        (t1, v1),
    )


def _segment_spec(kfs, index, axis, is_loop, scale=1.0, time_offset=0.0, time_scale=1.0):
    k0, k1 = kfs[index], kfs[index + 1]
    mode = _segment_mode(k0, k1)
    jump = bool(index > 0 and k0['jump'])
    t0 = time_offset + k0['time'] * time_scale
    t1 = time_offset + k1['time'] * time_scale
    if mode == 'constant':
        return {'mode': 'constant', 'points': ((t0, k0['post'][axis] * scale), (t1, k1['pre'][axis] * scale)), 'jump': jump}
    if mode == 'linear':
        return {'mode': 'linear', 'points': ((t0, k0['post'][axis] * scale), (t1, k1['pre'][axis] * scale)), 'jump': jump}
    if mode == 'catmullrom':
        return {
            'mode': 'bezier',
            'points': _catmull_bezier_points(kfs, index, axis, is_loop, scale, time_offset, time_scale),
            'allow_weighted': False,
            'jump': jump,
        }
    return {
        'mode': 'bezier',
        'points': _bezier_points(kfs, index, axis, scale, time_offset, time_scale),
        'allow_weighted': True,
        'jump': jump,
    }


def _bezier_min_y(points):
    ys = [p[1] for p in points]
    best = min(ys[0], ys[-1])
    if min(ys) > 0.0:
        return best
    # Sample + solve dy/du = 0 analytically so negative cubic overshoots are caught accurately.
    y0, y1, y2, y3 = ys
    a = 3.0 * (-y0 + 3.0 * y1 - 3.0 * y2 + y3)
    b = 6.0 * (y0 - 2.0 * y1 + y2)
    c = 3.0 * (y1 - y0)
    roots = []
    if abs(a) < 1e-12:
        if abs(b) > 1e-12:
            roots.append(-c / b)
    else:
        disc = b * b - 4.0 * a * c
        if disc >= 0.0:
            root = math.sqrt(disc)
            roots.extend(((-b - root) / (2.0 * a), (-b + root) / (2.0 * a)))
    for u in roots:
        if 0.0 < u < 1.0:
            best = min(best, curves._point(points, u)[1])
    return best


def _validate_positive_scale(bone_name, kfs, is_loop):
    for kf in kfs:
        for vec in (kf['pre'], kf['post']):
            if any(v <= 0.0 for v in vec):
                raise ValueError(f'缩放通道 {bone_name} 包含非正关键帧值 {vec}（UE 不支持零或负缩放）')
    for i in range(len(kfs) - 1):
        mode = _segment_mode(kfs[i], kfs[i + 1])
        if mode in ('constant', 'linear'):
            continue
        for axis in range(3):
            spec = _segment_spec(kfs, i, axis, is_loop)
            if _bezier_min_y(spec['points']) <= 0.0:
                raise ValueError(
                    f'缩放通道 {bone_name} 在第 {i} 段曲线过冲产生非正值（UE 不支持零或负缩放）'
                )


def _active_axes(kfs, channel_name):
    neutral = _NEUTRAL[channel_name]
    has_bezier = any(kf['interp'] == 'bezier' for kf in kfs)
    axes = []
    for axis in range(3):
        values_active = any(
            abs(kf['pre'][axis] - neutral) > 1e-12 or abs(kf['post'][axis] - neutral) > 1e-12
            for kf in kfs
        )
        handles_active = has_bezier and any(
            abs(kf['left_value'][axis]) > 1e-12 or abs(kf['right_value'][axis]) > 1e-12
            for kf in kfs
        )
        if values_active or handles_active:
            axes.append(axis)
    return axes


def _is_flat_spec(spec):
    mode = spec['mode']
    if mode == 'constant':
        return True
    pts = spec['points']
    y0 = pts[0][1]
    return all(pt[1] == y0 for pt in pts[1:])


def _eval_spec(spec, t_sec):
    pts = spec['points']
    p0, p1 = pts[0], pts[-1]
    if t_sec <= p0[0]:
        return p0[1]
    if t_sec >= p1[0]:
        return p1[1]
    mode = spec['mode']
    if mode == 'constant':
        return p0[1]
    y0, y1 = p0[1], p1[1]
    if mode == 'linear':
        if y0 == y1:
            return y0
        u = (t_sec - p0[0]) / (p1[0] - p0[0])
        return y0 + (y1 - y0) * u
    if all(pt[1] == y0 for pt in pts[1:]):
        return y0
    lo, hi = 0.0, 1.0
    for _ in range(52):
        u = (lo + hi) * 0.5
        if curves._point(pts, u)[0] < t_sec:
            lo = u
        else:
            hi = u
    return curves._point(pts, (lo + hi) * 0.5)[1]


def _evaluate_segment_scalar(kfs, index, axis, is_loop, t_sec, time_offset=0.0, time_scale=1.0):
    spec = _segment_spec(kfs, index, axis, is_loop, 1.0, time_offset, time_scale)
    return _eval_spec(spec, t_sec)


def evaluate_channel(kfs, time_sec, *, is_loop=False):
    """Evaluate a sorted 3-axis keyframe channel at source seconds (exact Blockbench rules)."""
    if time_sec <= kfs[0]['time']:
        return kfs[0]['pre']
    if len(kfs) == 1:
        return kfs[0]['post']
    if time_sec >= kfs[-1]['time']:
        return kfs[-1]['pre'] if time_sec == kfs[-1]['time'] else kfs[-1]['post']
    for i in range(len(kfs) - 1):
        if kfs[i]['time'] <= time_sec < kfs[i + 1]['time']:
            if time_sec == kfs[i]['time'] and i > 0 and kfs[i]['jump']:
                return kfs[i]['pre']
            return tuple(_evaluate_segment_scalar(kfs, i, ax, is_loop, time_sec) for ax in range(3))
    return kfs[-1]['pre']


# ---- 3D rotation matrices / quaternions (exact Blockbench ZYX -> UE Yaw*Pitch*Roll) ----

def _mat_mul(a, b):
    return tuple(
        tuple(a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j] for j in range(3))
        for i in range(3)
    )


def _rot_x(rad):
    c, s = math.cos(rad), math.sin(rad)
    return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))


def _rot_y(rad):
    c, s = math.cos(rad), math.sin(rad)
    return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))


def _rot_z(rad):
    c, s = math.cos(rad), math.sin(rad)
    return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))


def _bb_rot_to_ue_mat(rx_deg, ry_deg, rz_deg):
    """Convert Blockbench intrinsic XYZ (Rz*Ry*Rx) rotation to UE basis rotation matrix."""
    r_bb = _mat_mul(_rot_z(math.radians(rz_deg)),
                    _mat_mul(_rot_y(math.radians(ry_deg)), _rot_x(math.radians(rx_deg))))
    # Similarity transform P @ R_bb @ P^T for v_ue = (-z, -x, y).
    return (
        (r_bb[2][2], r_bb[2][0], -r_bb[2][1]),
        (r_bb[0][2], r_bb[0][0], -r_bb[0][1]),
        (-r_bb[1][2], -r_bb[1][0], r_bb[1][1]),
    )


def _ue_euler_to_mat(roll_deg, pitch_deg, yaw_deg):
    """Build UE basis rotation matrix for FRotator (Yaw * Pitch * Roll)."""
    return _mat_mul(_rot_z(math.radians(yaw_deg)),
                    _mat_mul(_rot_y(math.radians(-pitch_deg)), _rot_x(math.radians(-roll_deg))))


def _mat_to_quat(m):
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0.0:
        s = math.sqrt(tr + 1.0) * 2.0
        w = 0.25 * s
        x = (m[2][1] - m[1][2]) / s
        y = (m[0][2] - m[2][0]) / s
        z = (m[1][0] - m[0][1]) / s
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2.0
        w = (m[2][1] - m[1][2]) / s
        x = 0.25 * s
        y = (m[0][1] + m[1][0]) / s
        z = (m[0][2] + m[2][0]) / s
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2.0
        w = (m[0][2] - m[2][0]) / s
        x = (m[0][1] + m[1][0]) / s
        y = 0.25 * s
        z = (m[1][2] + m[2][1]) / s
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2.0
        w = (m[1][0] - m[0][1]) / s
        x = (m[0][2] + m[2][0]) / s
        y = (m[1][2] + m[2][1]) / s
        z = 0.25 * s
    norm = math.sqrt(w * w + x * x + y * y + z * z)
    return (w / norm, x / norm, y / norm, z / norm)


def _quat_angle_deg(q1, q2):
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    # Relative quaternion q1 * conj(q2).
    dw = w1 * w2 + x1 * x2 + y1 * y2 + z1 * z2
    dx = -w1 * x2 + x1 * w2 - y1 * z2 + z1 * y2
    dy = -w1 * y2 + x1 * z2 + y1 * w2 - z1 * x2
    dz = -w1 * z2 - x1 * y2 + y1 * x2 + z1 * w2
    return 2.0 * math.degrees(math.atan2(math.sqrt(dx * dx + dy * dy + dz * dz), abs(dw)))


def _wrap_near(angle, ref):
    return ref + ((angle - ref + 180.0) % 360.0 - 180.0)


def _ue_mat_to_euler(m, prev=None):
    """Extract continuous UE (Roll, Pitch, Yaw) in degrees closest to prev."""
    sp = min(1.0, max(-1.0, m[2][0]))
    pitch = math.degrees(math.asin(sp))
    if abs(sp) < 1.0 - 1e-7:
        roll = math.degrees(math.atan2(-m[2][1], m[2][2]))
        yaw = math.degrees(math.atan2(m[1][0], m[0][0]))
        candidates = (
            (roll, pitch, yaw),
            (roll + 180.0, 180.0 - pitch, yaw + 180.0),
        )
    else:
        # Gimbal lock at Pitch = +-90 deg: Roll and Yaw share one axis.
        sign = 1.0 if sp > 0 else -1.0
        roll0 = prev[0] if prev is not None else 0.0
        combined = math.degrees(math.atan2(-m[0][1], m[1][1]))
        yaw0 = combined + sign * roll0
        candidates = ((roll0, 90.0 * sign, yaw0),)
    if prev is None:
        return tuple(_wrap_near(a, 0.0) for a in candidates[0])
    best = None
    best_dist = math.inf
    for cand in candidates:
        wrapped = tuple(_wrap_near(cand[i], prev[i]) for i in range(3))
        dist = sum((wrapped[i] - prev[i]) ** 2 for i in range(3))
        if dist < best_dist:
            best_dist = dist
            best = wrapped
    return best


def _compile_coupled_rotation(kfs, is_loop, *, time_offset, time_scale, tick_rate, tolerance):
    """Fit a coupled multi-axis Blockbench rotation to UE (Roll, Pitch, Yaw) sparse Hermite curves."""
    seg_specs = [
        tuple(_segment_spec(kfs, i, ax, is_loop, 1.0, time_offset, time_scale) for ax in range(3))
        for i in range(len(kfs) - 1)
    ]
    segments = []
    for i in range(len(kfs) - 1):
        raw_mode = _segment_mode(kfs[i], kfs[i + 1])
        is_flat = raw_mode == 'constant' or all(_is_flat_spec(spec) for spec in seg_specs[i])
        mode = 'constant' if is_flat else 'cubic'
        t0 = time_offset + kfs[i]['time'] * time_scale
        t1 = time_offset + kfs[i + 1]['time'] * time_scale
        jump_before = i > 0 and bool(kfs[i]['jump'])
        segments.append((t0, t1, mode, jump_before))

    def eval_bb(seg_index, t_sec, side):
        if side == 'start':
            t_q = time_offset + kfs[seg_index]['time'] * time_scale
            if abs(t_sec - t_q) < 1e-12:
                return kfs[seg_index]['post']
        elif side == 'end':
            t_q = time_offset + kfs[seg_index + 1]['time'] * time_scale
            if abs(t_sec - t_q) < 1e-12:
                return kfs[seg_index + 1]['pre']
        specs = seg_specs[seg_index]
        return tuple(_eval_spec(specs[ax], t_sec) for ax in range(3))

    # Pre-trace a sequential Euler trajectory per continuous span so Euler unwrapping
    # near gimbal lock stays branch-consistent while keeping flat segments O(1).
    anchors = []
    chain_prev = None
    for seg_index, (t0, t1, mode, jump_before) in enumerate(segments):
        if jump_before:
            chain_prev = None
        if mode == 'constant':
            t_list = [t0, t1]
            eu0 = _ue_mat_to_euler(_bb_rot_to_ue_mat(*eval_bb(seg_index, t0, 'start')), chain_prev)
            eu1 = _ue_mat_to_euler(_bb_rot_to_ue_mat(*eval_bb(seg_index, t1, 'end')), eu0)
            eu_list = [eu0, eu1]
            chain_prev = eu1
            anchors.append((t_list, eu_list))
            continue

        count = max(16, int(math.ceil((t1 - t0) / 0.01)))
        samples = []
        for step in range(count + 1):
            t_step = t0 + (t1 - t0) * step / count
            side = 'start' if step == 0 else ('end' if step == count else None)
            mat = _bb_rot_to_ue_mat(*eval_bb(seg_index, t_step, side))
            samples.append((t_step, mat, _mat_to_quat(mat)))

        refined = []
        stack = [(samples[k], samples[k + 1], 0) for k in range(len(samples) - 2, -1, -1)]
        while stack:
            left, right, depth = stack.pop()
            if depth < 10 and (right[0] - left[0]) > 1e-6 and _quat_angle_deg(left[2], right[2]) > 15.0:
                t_mid = 0.5 * (left[0] + right[0])
                mat_mid = _bb_rot_to_ue_mat(*eval_bb(seg_index, t_mid, None))
                mid = (t_mid, mat_mid, _mat_to_quat(mat_mid))
                stack.append((mid, right, depth + 1))
                stack.append((left, mid, depth + 1))
            else:
                refined.append(left)
        refined.append(samples[-1])

        t_list = []
        eu_list = []
        for t_step, mat, _q in refined:
            eu = _ue_mat_to_euler(mat, chain_prev)
            t_list.append(t_step)
            eu_list.append(eu)
            chain_prev = eu
        anchors.append((t_list, eu_list))

    def _seed_at(seg_index, t_sec):
        t_list, eu_list = anchors[seg_index]
        if t_sec <= t_list[0]:
            return eu_list[0]
        if t_sec >= t_list[-1]:
            return eu_list[-1]
        idx = bisect.bisect_right(t_list, t_sec) - 1
        ta, tb = t_list[idx], t_list[idx + 1]
        frac = (t_sec - ta) / (tb - ta) if tb > ta else 0.0
        a, b = eu_list[idx], eu_list[idx + 1]
        return tuple(a[k] + (b[k] - a[k]) * frac for k in range(3))

    def sample_ue(seg_index, t_sec, prev_state, boundary):
        t0, t1, mode, _jump = segments[seg_index]
        bb_c = eval_bb(seg_index, t_sec, boundary)
        seed = prev_state if (boundary == 'start' and prev_state is not None) else _seed_at(seg_index, t_sec)
        eu = _ue_mat_to_euler(_bb_rot_to_ue_mat(*bb_c), seed)
        if mode == 'constant':
            return eu, (0.0, 0.0, 0.0)
        eps = min(1e-5, (t1 - t0) * 1e-3)
        if boundary == 'start':
            bb2 = eval_bb(seg_index, min(t1, t_sec + eps), None)
            eu2 = _ue_mat_to_euler(_bb_rot_to_ue_mat(*bb2), eu)
            dt = max(1e-12, min(t1, t_sec + eps) - t_sec)
            slope = tuple((eu2[i] - eu[i]) / dt for i in range(3))
        elif boundary == 'end':
            bb1 = eval_bb(seg_index, max(t0, t_sec - eps), None)
            eu1 = _ue_mat_to_euler(_bb_rot_to_ue_mat(*bb1), eu)
            dt = max(1e-12, t_sec - max(t0, t_sec - eps))
            slope = tuple((eu[i] - eu1[i]) / dt for i in range(3))
        else:
            tl = max(t0, t_sec - eps)
            tr = min(t1, t_sec + eps)
            eu1 = _ue_mat_to_euler(_bb_rot_to_ue_mat(*eval_bb(seg_index, tl, None)), eu)
            eu2 = _ue_mat_to_euler(_bb_rot_to_ue_mat(*eval_bb(seg_index, tr, None)), eu)
            slope = tuple((eu2[i] - eu1[i]) / (tr - tl) for i in range(3))
        return eu, slope

    def error_ue(seg_index, t_sec, herm_euler):
        bb_ref = eval_bb(seg_index, t_sec, None)
        q_ref = _mat_to_quat(_bb_rot_to_ue_mat(*bb_ref))
        q_ue = _mat_to_quat(_ue_euler_to_mat(*herm_euler))
        return _quat_angle_deg(q_ref, q_ue)

    init_pre = None
    if any(kfs[0]['pre'][i] != kfs[0]['post'][i] for i in range(3)):
        init_pre = _ue_mat_to_euler(_bb_rot_to_ue_mat(*kfs[0]['pre']), anchors[0][1][0])
    end_post = None
    if any(kfs[-1]['post'][i] != kfs[-1]['pre'][i] for i in range(3)):
        end_post = _ue_mat_to_euler(_bb_rot_to_ue_mat(*kfs[-1]['post']), chain_prev)
    end_mode = {'step': 'constant', 'linear': 'linear'}.get(kfs[-1]['interp'], 'cubic')

    prepared_axes = curves.fit_sampled_vector_curve(
        segments, sample_ue, error_ue, tick_rate, tolerance=tolerance,
        initial_pre=init_pre, end_post=end_post, end_mode=end_mode,
    )
    return [
        (part_name, 'rotation', prepared)
        for part_name, prepared in zip(_UE_ROT_PARTS, prepared_axes)
    ]


def _compile_scalar_axis(kfs, axis, ch_name, is_loop, *,
                         time_offset, time_scale, tick_rate, scale_factor,
                         weighted, tolerance):
    if len(kfs) == 1:
        t0 = time_offset + kfs[0]['time'] * time_scale
        v_pre = kfs[0]['pre'][axis] * scale_factor
        v_post = kfs[0]['post'][axis] * scale_factor
        mode = 'constant' if kfs[0]['interp'] == 'step' else 'linear'
        return curves.prepare_mixed_curve(
            [], tick_rate, kind=ch_name, tolerance=tolerance, weighted=weighted,
            initial=(t0, v_post, mode), initial_pre=v_pre,
        )
    specs = [
        _segment_spec(kfs, i, axis, is_loop, scale_factor, time_offset, time_scale)
        for i in range(len(kfs) - 1)
    ]
    end_mode = {'step': 'constant', 'linear': 'linear'}.get(kfs[-1]['interp'], 'cubic')
    return curves.prepare_mixed_curve(
        specs, tick_rate, kind=ch_name, tolerance=tolerance, weighted=weighted,
        initial_pre=kfs[0]['pre'][axis] * scale_factor,
        end_mode=end_mode,
        end_post=kfs[-1]['post'][axis] * scale_factor,
    )


def _prepare_clip_model(data, reference):
    if not isinstance(data, dict) or data.get('_format') != 'bbmodel':
        raise ValueError('内部 .bbmodel 编译需要经 resolve_clips 解析的片段结构')
    model = data['model']
    anim = data['animation']
    validate_model_meta(model)
    bones_by_uuid, bones_by_name = parse_groups(model)
    validate_target_skeleton(bones_by_name, reference)
    parsed = _parse_animation_channels(model, anim, bones_by_uuid)

    # Pre-validate all scale channels across every curve point before emitting anything.
    for (bone_name, ch_name), kfs in parsed['channels'].items():
        if ch_name == 'scale':
            _validate_positive_scale(bone_name, kfs, parsed['is_loop'])
    return bones_by_name, parsed


def compile_clip(data, reference, tick_rate, *, start_time=0.0, time_scale=1.0,
                 weighted=True, tolerance=None):
    """Compile one validated .bbmodel clip into per-scalar-channel Sequencer curve writes."""
    if isinstance(time_scale, bool) or not isinstance(time_scale, (int, float)) or not math.isfinite(time_scale) or time_scale <= 0:
        raise ValueError('time_scale 必须为正有限数')
    if not curves._is_number(tick_rate) or tick_rate <= 0:
        raise ValueError('tick_rate 必须为正有限数')
    if not curves._is_number(start_time):
        raise ValueError('start_time 必须为有限数值')

    bones_by_name, parsed = _prepare_clip_model(data, reference)

    compiled = []
    for (bone_name, ch_name), kfs in parsed['channels'].items():
        active = _active_axes(kfs, ch_name)
        if ch_name == 'rotation' and len(active) > 1:
            if len(kfs) == 1:
                t0 = float(start_time) + kfs[0]['time'] * float(time_scale)
                ue_euler = _ue_mat_to_euler(_bb_rot_to_ue_mat(*kfs[0]['post']))
                ue_pre = _ue_mat_to_euler(_bb_rot_to_ue_mat(*kfs[0]['pre']), ue_euler)
                mode = 'constant' if kfs[0]['interp'] == 'step' else 'linear'
                rot_entries = [
                    (part_name, 'rotation', curves.prepare_mixed_curve(
                        [], float(tick_rate), kind='rotation', tolerance=tolerance,
                        weighted=weighted, initial=(t0, ue_euler[idx], mode),
                        initial_pre=ue_pre[idx]))
                    for idx, part_name in enumerate(_UE_ROT_PARTS)
                ]
            else:
                rot_entries = _compile_coupled_rotation(
                    kfs, parsed['is_loop'], time_offset=float(start_time), time_scale=float(time_scale),
                    tick_rate=float(tick_rate), tolerance=tolerance,
                )
            for part_name, kind, prepared in rot_entries:
                compiled.append({
                    'bone': bone_name,
                    'selector': f'{bone_name}.{part_name}',
                    'kind': kind,
                    'prepared': prepared,
                })
            continue
        target_axes = active if active else [0, 1, 2]
        if ch_name == 'rotation':
            for axis in target_axes:
                part_name, kind, sign = _BB_TO_UE_SINGLE_ROT[axis]
                prepared = _compile_scalar_axis(
                    kfs, axis, ch_name, parsed['is_loop'],
                    time_offset=float(start_time), time_scale=float(time_scale),
                    tick_rate=float(tick_rate), scale_factor=sign,
                    weighted=weighted, tolerance=tolerance,
                )
                compiled.append({
                    'bone': bone_name,
                    'selector': f'{bone_name}.{part_name}',
                    'kind': kind,
                    'prepared': prepared,
                })
        else:
            axis_table = _AXIS_MAP[ch_name]
            for part_name, axis, factor in axis_table:
                if axis not in target_axes:
                    continue
                prepared = _compile_scalar_axis(
                    kfs, axis, ch_name, parsed['is_loop'],
                    time_offset=float(start_time), time_scale=float(time_scale),
                    tick_rate=float(tick_rate), scale_factor=factor,
                    weighted=weighted, tolerance=tolerance,
                )
                compiled.append({
                    'bone': bone_name,
                    'selector': f'{bone_name}.{part_name}',
                    'kind': ch_name,
                    'prepared': prepared,
                })

    return {
        'clip': parsed['clip'],
        'duration': parsed['duration'],
        'is_loop': parsed['is_loop'],
        'bones': bones_by_name,
        'channels': compiled,
    }


def sample_clip_offsets(data, reference, output_fps, *, bone_mask=None):
    """Evaluate validated .bbmodel animation channels directly into per-frame UE FK offsets."""
    if not curves._is_number(output_fps) or output_fps <= 0:
        raise ValueError('output_fps 必须为正有限数')
    _bones_by_name, parsed = _prepare_clip_model(data, reference)
    channels = parsed['channels']
    is_loop = parsed['is_loop']
    duration = parsed['duration']
    animated_bones = list(dict.fromkeys(bone for bone, _ in channels))
    if bone_mask is not None:
        animated_bones = [bone for bone in animated_bones if bone in bone_mask]
        if not animated_bones:
            raise ValueError('所选 bones 与动画包含的骨骼通道无交集')

    times = sampling.regular_times(duration, float(output_fps))
    offsets = {}
    for bone_name in animated_bones:
        pos_kfs = channels.get((bone_name, 'position'))
        rot_kfs = channels.get((bone_name, 'rotation'))
        scl_kfs = channels.get((bone_name, 'scale'))
        samples = []
        prev_eu = None
        for t in times:
            loc = _bb_vec_to_ue_cm(evaluate_channel(pos_kfs, t, is_loop=is_loop)) if pos_kfs else (0.0, 0.0, 0.0)
            if rot_kfs:
                rx, ry, rz = evaluate_channel(rot_kfs, t, is_loop=is_loop)
                eu = _ue_mat_to_euler(_bb_rot_to_ue_mat(rx, ry, rz), prev_eu)
                prev_eu = eu
            else:
                eu = (0.0, 0.0, 0.0)
            if scl_kfs:
                bb_scl = evaluate_channel(scl_kfs, t, is_loop=is_loop)
                if min(bb_scl) <= 0.0:
                    raise ValueError(f'{bone_name}.scale 包含非正缩放样本: {bb_scl}')
                scl = (bb_scl[2], bb_scl[0], bb_scl[1])
            else:
                scl = (1.0, 1.0, 1.0)
            samples.append((loc, eu, scl))
        offsets[bone_name] = samples

    return {
        'clip': parsed['clip'],
        'duration': duration,
        'is_loop': is_loop,
        'times': times,
        'offsets': offsets,
    }


def evaluate_clip_world_matrices(model, clip_name, times):
    """Evaluate Blockbench local channels & world 4x4 column-major matrices for test verification."""
    clips = resolve_clips(model)
    if clip_name not in clips:
        raise KeyError(clip_name)
    clip = clips[clip_name]
    bones_by_uuid, bones_by_name = parse_groups(clip['model'])
    parsed = _parse_animation_channels(clip['model'], clip['animation'], bones_by_uuid)

    # Order bones topologically (parents first) from outliner order.
    ordered_bones = list(bones_by_name.values())

    def _mat4_mul(a, b):
        return [
            sum(a[row + k * 4] * b[k + col * 4] for k in range(4))
            for col in range(4) for row in range(4)
        ]

    def _local_mat4(tx, ty, tz, rx, ry, rz, sx, sy, sz):
        r = _mat_mul(_rot_z(math.radians(rz)),
                     _mat_mul(_rot_y(math.radians(ry)), _rot_x(math.radians(rx))))
        return [
            r[0][0] * sx, r[1][0] * sx, r[2][0] * sx, 0.0,
            r[0][1] * sy, r[1][1] * sy, r[2][1] * sy, 0.0,
            r[0][2] * sz, r[1][2] * sz, r[2][2] * sz, 0.0,
            tx, ty, tz, 1.0,
        ]

    samples = []
    for t in times:
        world_mats = {}
        chan_vals = {}
        for bone in ordered_bones:
            bname = bone['name']
            ch_out = {}
            pos = (0.0, 0.0, 0.0)
            rot = (0.0, 0.0, 0.0)
            scl = (1.0, 1.0, 1.0)
            if (bname, 'position') in parsed['channels']:
                pos = evaluate_channel(parsed['channels'][(bname, 'position')], t, is_loop=parsed['is_loop'])
                ch_out['position'] = list(pos)
            if (bname, 'rotation') in parsed['channels']:
                rot = evaluate_channel(parsed['channels'][(bname, 'rotation')], t, is_loop=parsed['is_loop'])
                ch_out['rotation'] = list(rot)
            if (bname, 'scale') in parsed['channels']:
                scl = evaluate_channel(parsed['channels'][(bname, 'scale')], t, is_loop=parsed['is_loop'])
                ch_out['scale'] = list(scl)
            lo = bone['local_origin']
            local_m = _local_mat4(lo[0] + pos[0], lo[1] + pos[1], lo[2] + pos[2],
                                  rot[0], rot[1], rot[2], scl[0], scl[1], scl[2])
            if bone['parent'] is None:
                world_mats[bname] = local_m
            else:
                world_mats[bname] = _mat4_mul(world_mats[bone['parent']], local_m)
            chan_vals[bname] = ch_out
        samples.append({'time': t, 'channels': chan_vals, 'matrices': world_mats})
    return samples
