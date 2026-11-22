"""MC 方块连接与状态变换规则（纯 Python 实现，不依赖 Unreal）。

方块字典格式为 {(x, y, z): {'name': name, 'properties': {...}}}。
支持根据邻格自动计算栅栏、栅栏门、玻璃板、铁栏杆、石墙和楼梯的连接状态，
以及对方块坐标和朝向属性进行 90 度旋转与镜像翻转。
"""
from functools import lru_cache
import math
import operator


DIRECTIONS = ('north', 'east', 'south', 'west')
_OFFSETS = ((0, 0, -1), (1, 0, 0), (0, 0, 1), (-1, 0, 0))
_FAMILIES = frozenset(('fence', 'gate', 'pane', 'wall', 'stairs'))
_CONNECTION_EXCEPTIONS = frozenset((
    'barrier', 'carved_pumpkin', 'jack_o_lantern', 'melon', 'pumpkin', 'shulker_box'))


def _name(cell):
    return str(cell['name']).lower().removeprefix('minecraft:') if cell else ''


def _props(cell):
    return (cell.get('properties') or {}) if cell else {}


def family(name):
    """返回方块所属的连接类别 ('fence' / 'gate' / 'pane' / 'wall' / 'stairs')，普通方块返回空字符串。"""
    name = str(name).lower().removeprefix('minecraft:')
    if name == 'fence_gate' or name.endswith('_fence_gate'):
        return 'gate'
    if name.endswith('_fence'):
        return 'fence'
    if name == 'iron_bars' or name.endswith('_pane'):
        return 'pane'
    if name.endswith('_wall'):
        return 'wall'
    if name.endswith('_stairs'):
        return 'stairs'
    return ''


def _transform_properties(name, properties):
    """在旋转或镜像前，按默认朝向补全省略的方位属性。"""
    name = str(name).lower().removeprefix('minecraft:')
    result = dict(properties)
    kind = family(name)
    if kind == 'stairs':
        result.setdefault('facing', 'east')
    elif kind == 'gate' or name.endswith('_anvil') or name == 'anvil':
        result.setdefault('facing', 'south')
    elif name.endswith(('_door', '_trapdoor', '_bed')) or name == 'bed':
        result.setdefault('facing', 'north')
    if name.endswith('_door'):
        result.setdefault('hinge', 'left')
    if 'wall_' not in name and (name == 'sign' or name.endswith(('_sign', '_banner', '_head', '_skull'))):
        result.setdefault('rotation', '0')
    return result


def rotate_state(name, properties, turns=1):
    """旋转方块状态属性并返回新字典；turns=1 表示顺时针旋转 90 度（北 -> 东）。"""
    turns = operator.index(turns) % 4
    if not turns:
        return dict(properties)
    mapping = {d: DIRECTIONS[(i + turns) % 4] for i, d in enumerate(DIRECTIONS)}
    result = {mapping.get(k, k): v for k, v in _transform_properties(name, properties).items()}
    if 'facing' in result:
        result['facing'] = mapping.get(result['facing'], result['facing'])
    for key in ('axis', 'pillar_axis'):
        if turns % 2 and result.get(key) in ('x', 'z'):
            result[key] = 'z' if result[key] == 'x' else 'x'
    if 'rotation' in result:
        result['rotation'] = str((int(result['rotation']) + 4 * turns) % 16)
    return result


def mirror_state(name, properties, axis='x'):
    """沿 X 轴（东西翻转）或 Z 轴（南北翻转）镜像方块状态属性，同时翻转门合页与楼梯左右拐角。"""
    if axis not in ('x', 'z'):
        raise ValueError("mirror axis must be 'x' or 'z'")
    a, b = ('east', 'west') if axis == 'x' else ('north', 'south')
    mapping = {a: b, b: a}
    result = {mapping.get(k, k): v for k, v in _transform_properties(name, properties).items()}
    if 'facing' in result:
        result['facing'] = mapping.get(result['facing'], result['facing'])
    if result.get('hinge') in ('left', 'right'):
        result['hinge'] = 'right' if result['hinge'] == 'left' else 'left'
    if family(name) == 'stairs':
        shape = result.get('shape', 'straight')
        if shape.endswith(('_left', '_right')):
            stem, side = shape.rsplit('_', 1)
            result['shape'] = stem + ('_right' if side == 'left' else '_left')
    if 'rotation' in result:
        result['rotation'] = str(((0 if axis == 'x' else 8) - int(result['rotation'])) % 16)
    return result


def _grid_point(point):
    if len(point) != 3 or any(not math.isfinite(v) or int(v) != v for v in point):
        raise ValueError('transform must preserve integer MC grid coordinates')
    return tuple(map(int, point))


def rotate_cells(cells, rotation=90, *, pivot=(0, 0, 0)):
    """将稀疏方块字典绕 pivot（MC 格子中心坐标）顺时针旋转 90 度的倍数，同步更新坐标与方块状态。"""
    if rotation % 90 != 0:
        raise ValueError('rotation must be a multiple of 90 degrees')
    turns = int(rotation // 90) % 4
    px, _, pz = pivot
    result = {}
    for (x, y, z), cell in cells.items():
        dx, dz = x - px, z - pz
        for _ in range(turns):
            dx, dz = -dz, dx
        point = _grid_point((px + dx, y, pz + dz))
        result[point] = {**cell, 'properties': rotate_state(cell['name'], _props(cell), turns)}
    return result


def mirror_cells(cells, axis='x', *, pivot=0):
    """将稀疏方块字典沿 X 或 Z 轴镜像翻转（pivot 可为整数或半整数），同步更新坐标与方块状态。"""
    if axis not in ('x', 'z') or not math.isfinite(pivot) or int(2 * pivot) != 2 * pivot:
        raise ValueError("mirror needs an X/Z axis and an integer or half-integer pivot")
    index = 0 if axis == 'x' else 2
    result = {}
    for point, cell in cells.items():
        reflected = list(point)
        reflected[index] = 2 * pivot - reflected[index]
        result[_grid_point(reflected)] = {
            **cell, 'properties': mirror_state(cell['name'], _props(cell), axis)}
    return result


def _neighbour(cells, point, direction):
    return cells.get(tuple(p + d for p, d in zip(point, _OFFSETS[direction % 4])))


def _stairs_shape(cells, point, props):
    facing = DIRECTIONS.index(props.get('facing', 'east'))
    half = props.get('half', 'bottom')
    for direction, corner in ((facing, 'outer'), (facing + 2, 'inner')):
        other = _neighbour(cells, point, direction)
        if family(_name(other)) != 'stairs' or _props(other).get('half', 'bottom') != half:
            continue
        turn = DIRECTIONS.index(_props(other).get('facing', 'east'))
        if (turn - facing) % 2 == 0:
            continue
        guard = _neighbour(cells, point, turn + (2 if corner == 'outer' else 0))
        if (family(_name(guard)) == 'stairs' and _props(guard).get('facing', 'east') == DIRECTIONS[facing]
                and _props(guard).get('half', 'bottom') == half):
            continue
        return corner + ('_left' if turn == (facing - 1) % 4 else '_right')
    return 'straight'


def connect(cells, *, is_full_cube, families=None, positions=None):
    """根据邻格就地更新栅栏、栅栏门、玻璃板/铁栏杆、石墙和楼梯的连接属性，并返回 cells。

    is_full_cube(name, properties) 用于判断方块是否为完整正方体。
    families 可指定只更新部分类别；positions 可指定只更新部分坐标（仍从完整 cells 读取邻格）。
    """
    families = _FAMILIES if families is None else frozenset(families)
    if not families <= _FAMILIES:
        raise ValueError('unknown connection family')

    @lru_cache(maxsize=None)
    def full_cube(name, properties):
        props = dict(properties)
        if name.endswith('_slab'):
            return props.get('type', 'bottom') == 'double'
        return bool(is_full_cube(name, props))

    def full(cell):
        return bool(cell) and full_cube(_name(cell), tuple(sorted(_props(cell).items())))

    def support(cell):
        name = _name(cell)
        return (name not in _CONNECTION_EXCEPTIONS and not name.endswith(('_leaves', '_shulker_box'))
                and full(cell))

    def gate(cell, direction):
        return (family(_name(cell)) == 'gate'
                and DIRECTIONS.index(_props(cell).get('facing', 'south')) % 2 != direction % 2)

    def write(point, props):
        cells[point] = {**cells[point], 'properties': props}

    walls = []
    for point in cells if positions is None else positions:
        cell = cells[point]
        name = _name(cell)
        kind = family(name)
        if kind not in families:
            continue
        props = dict(_props(cell))
        if kind == 'wall':
            walls.append(point)
            continue
        if kind == 'stairs':
            props['shape'] = _stairs_shape(cells, point, props)
        elif kind == 'gate':
            direction = DIRECTIONS.index(props.get('facing', 'south'))
            props['in_wall'] = str(any(family(_name(_neighbour(cells, point, d))) == 'wall'
                                      for d in (direction - 1, direction + 1))).lower()
        else:
            for direction, key in enumerate(DIRECTIONS):
                other = _neighbour(cells, point, direction)
                neighbour_kind = family(_name(other))
                if kind == 'fence':
                    same = (neighbour_kind == 'fence'
                            and (name == 'nether_brick_fence') == (_name(other) == 'nether_brick_fence'))
                    joined = same or gate(other, direction) or support(other)
                else:
                    joined = neighbour_kind in ('pane', 'wall') or support(other)
                props[key] = str(bool(joined)).lower()
        write(point, props)

    # 石墙是否生成立柱受上方石墙影响，因此按高度从上往下依次计算
    for point in sorted(walls, key=lambda p: p[1], reverse=True):
        props = dict(_props(cells[point]))
        above = cells.get((point[0], point[1] + 1, point[2]))
        covered = full(above) or (_name(above).endswith('_slab')
                                  and _props(above).get('type', 'bottom') == 'bottom')
        for direction, key in enumerate(DIRECTIONS):
            other = _neighbour(cells, point, direction)
            joined = family(_name(other)) in ('wall', 'pane') or gate(other, direction) or support(other)
            props[key] = ('tall' if covered else 'low') if joined else 'none'
        n, e, s, w = (props[d] == 'none' for d in DIRECTIONS)
        corner = (n and e and s and w) or n != s or e != w
        above_post = family(_name(above)) == 'wall' and str(_props(above).get('up', 'true')).lower() == 'true'
        props['up'] = str(bool(above_post or corner)).lower()
        write(point, props)
    return cells
