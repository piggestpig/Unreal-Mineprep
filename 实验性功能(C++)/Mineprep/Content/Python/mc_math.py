"""方块结构的数学计算工具（不依赖 Unreal），负责旋转编码、实例坐标批量转换与 GPU 类型分组。

为了让 PCG 和 Niagara 用单个浮点数记录方块朝向，这里将旋转压缩为一个编码值：
1. 直角朝向 (0~23)：对应正方体在三维网格里的 24 种 90 度朝向，满足 id = up * 4 + twist。
   其中 up 表示方块原本的顶面 (+Z) 旋转后的朝向 (0:+Z, 1:-Z, 2:+Y, 3:-Y, 4:+X, 5:-X)，
   twist 表示绕该轴自转的角度 (0~3 分别对应 0/90/180/270 度)。
2. 任意水平偏航角（负数）：像告示牌、头颅这类非 90 度倍数的纯水平旋转（俯仰和翻滚均为零），
   直接记录为偏航角的相反数 -yaw（例如 22.5 度记为 -22.5, 0 度仍记为 0）。
"""
import math
import operator

import numpy as np

BLOCK_SIZE = 100.0
MODEL_FRAME = 'cell-center-1'
_ANGLE_EPS = 0.001
TYPE_GROUP_VERSION = 'type-groups-2'


def partition_types(names, counts, groups=1, *, max_types=None):
    """按实例数量对方块类型分组，最小化 Niagara 渲染代价 sum(每组类型数 * 每组实例总数)。

    返回 ((原始类型索引, ...), 该组实例总数) 元组，组内保持原调色板顺序。
    将类型按实例数降序排列后，最优划分必为连续区间，使用分治动态规划求解。
    max_types 可限制每组的最大类型数（例如单 Actor 最多 256 种模型），超出时自动增加分组数。
    """
    if type(groups) is not int or groups < 1:
        raise ValueError('groups must be a positive integer')
    if max_types is not None and (type(max_types) is not int or max_types < 1):
        raise ValueError('max_types must be a positive integer or None')
    names, counts = tuple(names), tuple(counts)
    if len(names) != len(counts) or any(not isinstance(n, str) for n in names):
        raise ValueError('names and counts must have equal length; names must be strings')
    weights = []
    for count in counts:
        try:
            if isinstance(count, (bool, np.bool_)):
                raise TypeError
            value = operator.index(count)
        except TypeError:
            raise ValueError('counts must be nonnegative integers') from None
        if value < 0:
            raise ValueError('counts must be nonnegative integers')
        weights.append(int(value))
    total = sum(weights)
    if not total:
        return ()
    if groups == 1 and (max_types is None or len(names) <= max_types):
        return ((tuple(range(len(names))), total),)
    order = sorted((i for i, w in enumerate(weights) if w),
                   key=lambda i: (-weights[i], names[i], i))
    size = len(order)
    capacity = size if max_types is None else max_types
    k = min(size, max(groups, (size + capacity - 1) // capacity))
    if k == size:
        return tuple(((i,), weights[i]) for i in order)
    prefix = [0]
    for i in order:
        prefix.append(prefix[-1] + weights[i])
    infinity = size * total + 1
    previous = [j * prefix[j] if j <= capacity else infinity for j in range(size + 1)]
    parents = [[0] * (size + 1)]
    for g in range(2, k + 1):
        current = [infinity] * (size + 1)
        parent = [-1] * (size + 1)

        def solve(left, right, opt_left, opt_right):
            if left > right:
                return
            j = (left + right) // 2
            best, split = infinity, -1
            for i in range(max(opt_left, j - capacity), min(opt_right, j - 1) + 1):
                cost = previous[i] + (j - i) * (prefix[j] - prefix[i])
                if cost < best:  # 代价相同时优先取靠前的切分点
                    best, split = cost, i
            current[j], parent[j] = best, split
            solve(left, j - 1, opt_left, split)
            solve(j + 1, right, split, opt_right)

        solve(g, min(size, g * capacity), g - 1, size - 1)
        previous = current
        parents.append(parent)
    result, end = [], size
    for g in range(k - 1, -1, -1):
        start = parents[g][end]
        result.append((tuple(sorted(order[start:end])), prefix[end] - prefix[start]))
        end = start
    return tuple(reversed(result))

# 24 种直角朝向对应的 UE 欧拉角 (pitch, yaw, roll)，顺序与材质/粒子中的 Rotation[24] 一致
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
    """将 UE 欧拉角 (pitch, yaw, roll) 转为四元数 (x, y, z, w)。"""
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
    """计算绕世界 Z 轴偏航角的四元数，与 HLSL 负角度分支一致。"""
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
    """若角度与 0/90/180/270 度的误差不超过 _ANGLE_EPS 则返回该直角，否则返回 None。"""
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
    """将欧拉角编码为单个浮点数：直角朝向编码为 0~23，纯水平旋转编码为 -yaw；其余情况抛出 ValueError。"""
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
    """将旋转编码还原为 (pitch, yaw, roll) 欧拉角：0~23 查表还原，负数还原为 (0.0, abs(rot), 0.0)。"""
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
    """将 MC JSON 模型顶点坐标 (0~16) 转换为以格子中心为原点的 UE 厘米坐标。"""
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
    """校验打包后的实例数据，返回连续的 float32 格式 pos/rot/scale 数组。"""
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
    """将 MC 方块格点坐标与尺寸批量转换为 UE 实例中心坐标、旋转编码与局部缩放。

    coords: 单个 (x, y, z) 或 [N, 3] 数组（MC 坐标，表示方块或合并盒的最小角）。
    sizes: 标量、(sx, sy, sz) 或 [N, 3] 数组（沿 MC 各轴跨越的格数）。
    rot: 标量或 [N] 旋转编码数组（0~23，或未合并单格方块的负偏航角）。
    origin: UE 坐标系下的整体偏移量（厘米）。
    返回包含连续 float32 数组 pos、rot、scale 的字典。
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
