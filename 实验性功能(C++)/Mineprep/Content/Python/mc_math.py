"""方块朝向的编码。本模块不依赖 Unreal，结构导入和 GPU 纹理共用。

0 到 23 表示把方块摆进格子的 24 种直角朝向，编号是 id = up * 4 + twist。
up 看未旋转时的顶面（局部 +Z）最后朝哪：0 朝上，1 朝下，2 朝 +Y，3 朝 −Y，4 朝 +X，5 朝 −X。
twist 是绕这根轴再转 0°、90°、180° 或 270°，取 0 到 3。

水平方向上不是 90° 倍数的角度写成负数，绝对值就是绕世界 Z 的偏航角（度），俯仰和滚转都是 0。
正好 0° 仍用编号 0，不写成负数。
"""
import math

import numpy as np

BLOCK_SIZE = 100.0
MODEL_FRAME = 'cell-center-1'
_ANGLE_EPS = 0.001

# 规范欧拉角 (pitch, yaw, roll)。与 Rotation[24] 同一顺序。
_ROT_EULER = (
    (0.0, 0.0, 0.0),
    (0.0, 90.0, 0.0),
    (0.0, 180.0, 0.0),
    (0.0, 270.0, 0.0),
    (0.0, 0.0, 180.0),
    (0.0, 270.0, 180.0),
    (0.0, 180.0, 180.0),
    (0.0, 90.0, 180.0),
    (0.0, 0.0, 90.0),
    (270.0, 0.0, 90.0),
    (0.0, 180.0, 270.0),
    (90.0, 0.0, 90.0),
    (0.0, 0.0, 270.0),
    (90.0, 0.0, 270.0),
    (0.0, 180.0, 90.0),
    (270.0, 0.0, 270.0),
    (270.0, 0.0, 0.0),
    (0.0, 90.0, 270.0),
    (90.0, 0.0, 180.0),
    (0.0, 270.0, 90.0),
    (0.0, 90.0, 90.0),
    (270.0, 0.0, 180.0),
    (0.0, 270.0, 270.0),
    (90.0, 0.0, 0.0),
)


def rotator_quaternion(pitch, yaw, roll):
    """Unreal FRotator 四元数 (x, y, z, w)。"""
    def sc(deg):
        half = math.radians(float(deg)) * 0.5
        return math.sin(half), math.cos(half)

    sp, cp = sc(pitch)
    sy, cy = sc(yaw)
    sr, cr = sc(roll)
    return (
        cr * sp * sy - sr * cp * cy,
        -cr * sp * cy - sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    )


def yaw_quaternion(degrees):
    """绕世界 Z 的偏航，与 HLSL 负角度分支同一公式。"""
    half = math.radians(abs(float(degrees))) * 0.5
    return (0.0, 0.0, math.sin(half), math.cos(half))


def _rotate(q, v):
    x, y, z, w = q
    cx = y * v[2] - z * v[1]
    cy = z * v[0] - x * v[2]
    cz = x * v[1] - y * v[0]
    tx, ty, tz = 2.0 * cx, 2.0 * cy, 2.0 * cz
    return (
        v[0] + w * tx + (y * tz - z * ty),
        v[1] + w * ty + (z * tx - x * tz),
        v[2] + w * tz + (x * ty - y * tx),
    )


def _snap_axis(v):
    axis = max(range(3), key=lambda i: abs(v[i]))
    out = [0, 0, 0]
    out[axis] = 1 if v[axis] > 0.0 else -1
    return tuple(out)


def _basis(pitch, yaw, roll):
    q = rotator_quaternion(pitch, yaw, roll)
    return (
        _snap_axis(_rotate(q, (1.0, 0.0, 0.0))),
        _snap_axis(_rotate(q, (0.0, 1.0, 0.0))),
        _snap_axis(_rotate(q, (0.0, 0.0, 1.0))),
    )


_ID_TO_AXES = tuple(_basis(*euler) for euler in _ROT_EULER)
_AXIS_TO_ID = {axes: rot_id for rot_id, axes in enumerate(_ID_TO_AXES)}


def _fold360(deg):
    folded = float(deg) % 360.0
    if folded < 0.0:
        folded += 360.0
    return folded


def _nearest_right(deg):
    """离 0/90/180/270 不超过 _ANGLE_EPS 时返回该直角，否则 None。"""
    folded = _fold360(deg)
    target = (int(round(folded / 90.0)) % 4) * 90.0
    distance = abs(folded - target)
    if target == 0.0:
        distance = min(distance, abs(folded - 360.0))
    if distance <= _ANGLE_EPS:
        return target
    return None


def _near_zero(deg):
    folded = _fold360(deg)
    return min(folded, 360.0 - folded) <= _ANGLE_EPS


def encode_rotation(pitch, yaw, roll):
    """欧拉角 → 0..23，或纯 yaw 的相反数。无法表示时抛 ValueError。"""
    try:
        pitch, yaw, roll = float(pitch), float(yaw), float(roll)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('rotation: finite numeric pitch/yaw/roll required') from exc
    if not all(math.isfinite(v) for v in (pitch, yaw, roll)):
        raise ValueError(f'non-finite rotation ({pitch}, {yaw}, {roll})')
    right = (_nearest_right(pitch), _nearest_right(yaw), _nearest_right(roll))
    if all(angle is not None for angle in right):
        axes = _basis(*right)
        rot_id = _AXIS_TO_ID.get(axes)
        if rot_id is None:
            raise ValueError(f'unmapped cube rotation ({pitch}, {yaw}, {roll})')
        return float(rot_id)
    if _near_zero(pitch) and _near_zero(roll):
        folded = _fold360(yaw)
        if folded <= _ANGLE_EPS or folded >= 360.0 - _ANGLE_EPS:
            return 0.0
        return -folded
    raise ValueError(
        f'rotation ({pitch}, {yaw}, {roll}) is not a cube orientation or a pure yaw'
    )


def decode_rotation(rot):
    """0..23 → 规范欧拉角；负数 → (0, abs(rot), 0)。"""
    try:
        rot = float(rot)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('rotation code: finite number required') from exc
    if not math.isfinite(rot):
        raise ValueError(f'non-finite rotation code {rot}')
    if rot < 0.0:
        return (0.0, abs(rot), 0.0)
    nearest = int(round(rot))
    if rot != nearest or nearest < 0 or nearest > 23:
        raise ValueError(f'rotation code {rot} is outside 0..23')
    return _ROT_EULER[nearest]


_SCALE_AXES = np.argmax(np.abs(np.asarray(_ID_TO_AXES)), axis=2)
_SCALE_AXES.setflags(write=False)


def _numbers(value, name):
    try:
        array = np.asarray(value)
        if array.dtype.kind not in 'iuf':
            raise ValueError('numeric values required')
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{name}: finite numeric values required') from exc
    if not np.isfinite(array).all():
        raise ValueError(f'{name}: non-finite values')
    return array


def _block_size(value):
    array = _numbers(value, 'block_size')
    if array.ndim != 0 or array <= 0:
        raise ValueError('block_size: positive scalar required')
    return float(array)


def _points(value, name):
    array = _numbers(value, name)
    if array.shape == (3,):
        array = array[None, :]
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError(f'{name}: needs a triple or [N,3] array')
    return array.astype(np.float64, copy=False)


def model_vertices_to_ue(points, *, block_size=BLOCK_SIZE):
    """JSON model vertices (MC 0..16) → UE cm about the fixed cell center."""
    vertices = _points(points, 'model vertices')
    return (vertices[:, (0, 2, 1)] - 8.0) * (_block_size(block_size) / 16.0)


def _rotation_codes(value, count):
    rot = _numbers(value, 'rot')
    nearest = np.round(rot)
    discrete = rot >= 0
    if np.any(discrete & ((rot != nearest) | (nearest > 23))):
        raise ValueError('rot: needs an integer code 0..23 or negative UE yaw')
    if rot.ndim == 0:
        rot = np.broadcast_to(rot, (count,))
    if rot.shape != (count,):
        raise ValueError('rot: needs a scalar or [N] array')
    return rot


def validate_packed(payload):
    """Validate before writes; return contiguous float32 pos/rot/scale arrays."""
    if not isinstance(payload, dict) or not {'pos', 'rot'} <= payload.keys():
        raise ValueError('packed payload: pos and rot required')
    pos = _numbers(payload['pos'], 'pos')
    if pos.ndim != 2 or pos.shape[1] != 3:
        raise ValueError('pos: needs [N,3] array')
    count = len(pos)
    if np.asarray(payload['rot']).shape != (count,):
        raise ValueError('packed rot: needs [N] array')
    rot = _rotation_codes(payload['rot'], count)
    scale = _numbers(payload['scale'] if 'scale' in payload else np.ones((count, 3), np.float32), 'scale')
    if scale.shape != (count, 3) or np.any(scale <= 0):
        raise ValueError('scale: needs positive [N,3] array')
    if np.any((rot < 0) & np.any(scale != 1, axis=1)):
        raise ValueError('negative yaw: only unmerged unit-cell scales are supported')
    with np.errstate(over='ignore', invalid='ignore'):
        result = {name: np.ascontiguousarray(a, dtype=np.float32)
                  for name, a in (('pos', pos), ('rot', rot), ('scale', scale))}
    if not all(np.isfinite(a).all() for a in result.values()):
        raise ValueError('packed payload: values exceed float32 range')
    if np.any(result['scale'] <= 0):
        raise ValueError('packed payload: scale underflows float32')
    return result


def boxes_to_packed(coords, sizes=1, rot=0, *, origin=(0, 0, 0), block_size=BLOCK_SIZE):
    """MC minimum corners/world extents → center positions/local scales in UE.

    coords: triple or [N,3]; sizes: scalar, triple or [N,3]; rot: scalar or [N].
    origin is a UE XYZ translation in cm. All outputs are contiguous float32.
    A negative yaw represents an unmerged unit cell, not a world-aligned box.
    """
    coords = _points(coords, 'coords')
    count = len(coords)
    size = _numbers(sizes, 'sizes').astype(np.float64, copy=False)
    if size.ndim == 0 or size.shape == (3,):
        if np.any(size <= 0):
            raise ValueError('sizes: positive extents required')
        size = np.broadcast_to(size, (count, 3))
    if size.shape != (count, 3) or np.any(size <= 0):
        raise ValueError('sizes: needs positive scalar, triple or [N,3] array')
    origin = _numbers(origin, 'origin')
    if origin.shape != (3,):
        raise ValueError('origin: needs a UE XYZ triple in cm')
    block_size = _block_size(block_size)
    rot = _rotation_codes(rot, count)
    discrete = rot >= 0
    if np.any(~discrete & np.any(size != 1, axis=1)):
        raise ValueError('negative yaw: only unmerged unit cells are supported')
    world_size = size[:, (0, 2, 1)]
    axes = _SCALE_AXES[np.where(discrete, rot, 0).astype(np.intp)]
    scale = np.take_along_axis(world_size, axes, axis=1)
    with np.errstate(over='ignore', invalid='ignore'):
        pos = (coords[:, (0, 2, 1)] + world_size * 0.5) * block_size + origin
    return validate_packed(dict(pos=pos, rot=rot, scale=scale))
