"""Surface grounding and sparse downward foundations; no terrain mutation or UE."""
import numpy as np

from . import geometry
from .building import Placement, Structure, _state
from .data import require_int
from .scene import _WorldQuery, _keys, _members
from .templates import rotate
from .world import World, MAX_INSTANCES

_BATCH = 2048
_UNSET = object()


def _query(world):
    if not isinstance(world, World):
        raise TypeError('ground/foundation require a generated World')
    if not geometry.height_mode(world.pack):
        raise ValueError('ground/foundation require surface terrain; volume floors need an explicit layer')
    return _WorldQuery(world)


def _points(world, placement, *, check_y=True):
    if not isinstance(placement, Placement) or not placement.structure.count:
        raise ValueError('ground/foundation need nonempty Structure.at(...) placements')
    p = placement.points
    r = world.region
    outside = ((p[:, 0] < r.x0) | (p[:, 0] >= r.x0+r.width)
               | (p[:, 2] < r.z0) | (p[:, 2] >= r.z0+r.depth))
    if check_y:
        outside |= (p[:, 1] < world.params['world.y_min']) | (p[:, 1] >= world.params['world.y_max'])
    if outside.any():
        raise ValueError(f'placement exceeds generated region or output height at {p[outside][0].tolist()}')
    return p


def _ground_tops(query, xz, bounds=_UNSET):
    """Highest physical terrain cell; only changed columns need density queries."""
    w = query.world
    lo, hi = w.params['world.y_min'], w.params['world.y_max']
    heights = w.heights[xz[:, 1]-w.region.z0, xz[:, 0]-w.region.x0]
    tops = np.clip(np.ceil(heights).astype(np.int64)-1, lo-1, hi-1)
    boxes = (geometry.plan_bounds(w.pack, w.params, w.spec.seed, w.region, query.resources)
             if bounds is _UNSET else bounds)
    upper = tops.copy()
    changed = np.zeros(len(xz), bool)
    if boxes is None:
        changed[:] = True
        upper[:] = hi-1
    else:
        for x0, y0, z0, x1, y1, z1 in boxes:
            use = (xz[:, 0] >= x0) & (xz[:, 0] < x1) & (xz[:, 1] >= z0) & (xz[:, 1] < z1)
            changed |= use
            upper[use] = np.maximum(upper[use], min(y1-1, hi-1))
    ids = np.flatnonzero(changed)
    tops[ids] = lo-1
    # Descending slabs find the first solid without a full XYZ volume.
    for start in range(0, len(ids), _BATCH//32):
        active = ids[start:start+_BATCH//32]
        y = upper[active].copy()
        while len(active):
            levels = y[:, None]-np.arange(32)
            p = np.empty((len(active), 32, 3), np.int64)
            p[:, :, 0], p[:, :, 2] = xz[active, 0, None], xz[active, 1, None]
            p[:, :, 1] = levels
            solid = query.terrain(p.reshape(-1, 3)).reshape(levels.shape) & (levels >= lo)
            found = solid.any(axis=1)
            tops[active[found]] = levels[found, solid[found].argmax(axis=1)]
            use = ~found & (y-32 >= lo)
            active, y = active[use], y[use]-32
    return tops


def _bottoms(points):
    p = points[np.lexsort((points[:, 1], points[:, 2], points[:, 0]))]
    return p[np.r_[True, np.any(p[1:, [0, 2]] != p[:-1, [0, 2]], axis=1)]]


def _translated(points, anchors):
    """Yield bounded cell batches and their anchor owners, without an N*M grid."""
    for start in range(0, len(points)*len(anchors), _BATCH):
        flat = np.arange(start, min(start+_BATCH, len(points)*len(anchors)))
        owners, local = np.divmod(flat, len(points))
        yield owners, points[local].astype(np.int64)+anchors[owners]


def _ground_y(query, bottom, anchors, bounds=_UNSET):
    w = query.world
    if bounds is _UNSET:
        bounds = geometry.plan_bounds(w.pack, w.params, w.spec.seed, w.region, query.resources)
    y = np.full(len(anchors), np.iinfo(np.int64).min, np.int64)
    supported = np.zeros(len(anchors), bool)
    roots = np.column_stack((anchors[:, 0], np.zeros(len(anchors), np.int64), anchors[:, 1]))
    for owners, p in _translated(bottom, roots):
        tops = _ground_tops(query, p[:, [0, 2]], bounds)
        valid = tops >= w.params['world.y_min']
        supported[owners[valid]] = True
        np.maximum.at(y, owners[valid], tops[valid]+1-p[valid, 1])
    return y, supported


def _support_depths(query, supports, max_depth):
    """First terrain below each support; -1 means the depth/range was exhausted."""
    depths = np.full(len(supports), -1, np.int64)
    for start in range(0, len(supports), _BATCH):
        active = np.arange(start, min(start+_BATCH, len(supports)))
        p = supports[active].copy()
        for depth in range(max_depth+1):
            p[:, 1] -= 1
            solid = query.terrain(p)
            depths[active[solid]] = depth
            keep = ~solid & (p[:, 1] >= query.world.params['world.y_min'])
            active, p = active[keep], p[keep]
            if not len(active):
                break
    return depths


def _foundation_cells(supports, depths):
    ends = np.cumsum(depths)
    starts = np.r_[0, ends[:-1]]
    for start in range(0, int(ends[-1]) if len(ends) else 0, _BATCH):
        flat = np.arange(start, min(start+_BATCH, int(ends[-1])))
        owners = np.searchsorted(ends, flat, side='right')
        p = supports[owners].copy()
        p[:, 1] -= flat-starts[owners]+1
        yield owners, p


def ground(world, placement):
    """Preserve X/Z and rotation; choose the lowest Y above the terrain skyline."""
    query = _query(world)
    _points(world, placement, check_y=False)
    bottom = _bottoms(rotate(placement.structure.xyz, placement.rotation//90))
    y, supported = _ground_y(query, bottom, np.array([placement.position])[..., [0, 2]])
    if not supported[0]:
        raise ValueError('no terrain beneath placement in the generated height range')
    result = placement.structure.at((placement.position[0], int(y[0]), placement.position[2]), placement.rotation)
    _points(world, result)
    return result


def foundation(world, *placements, block='stone', max_depth=16, max_cells=MAX_INSTANCES, **states):
    """Fill beneath each model's lowest occupied layer; return one world-coordinate Structure."""
    query = _query(world)
    require_int('max_depth', max_depth, 0, 2**31-1)
    require_int('max_cells', max_cells, 1, 2**63-1)
    material = _state(block, states)
    if material[0] == 'air':
        raise ValueError('foundation needs a non-air block')
    footprints, supports, bodies = {}, [], []
    for placement in placements:
        bodies.append(_points(world, placement))
        key = placement.structure.key, placement.rotation
        if key not in footprints:
            s = placement.structure
            footprints[key] = rotate(s.xyz[s.xyz[:, 1] == s.xyz[:, 1].min()], placement.rotation//90)
        supports.append(footprints[key].astype(np.int64)+placement.position)
    parts, count = [], 0
    if supports:
        supports = np.unique(np.concatenate(supports), axis=0)
        depths = _support_depths(query, supports, max_depth)
        if np.any(depths < 0):
            at = supports[depths < 0][0].copy()
            at[1] = max(at[1]-max_depth-1, world.params['world.y_min']-1)
            raise ValueError(f'foundation max_depth={max_depth} found no terrain below {at.tolist()}')
        count = int(depths.sum())
        if count > max_cells:
            raise ValueError(f'foundation exceeds max_cells={max_cells:,}')
        parts = [p for _, p in _foundation_cells(supports, depths)]
    if not parts:
        return Structure('Foundation', (0, 0, 0), (1, 1, 1), (), np.empty((0, 3), np.int32), np.empty(0, np.uint16))
    xyz = np.unique(np.concatenate(parts), axis=0)
    body_keys = np.unique(_keys(np.concatenate(bodies)))
    for start in range(0, len(xyz), _BATCH):
        p = xyz[start:start+_BATCH]
        blocked = _members(p, body_keys)
        for kind, mask in query.obstacles(p).items():
            if mask.any():
                raise ValueError(f'foundation collides with {kind} at {p[mask][0].tolist()}')
        if blocked.any():
            raise ValueError(f'foundation collides with a placement at {p[blocked][0].tolist()}')
    lo, hi = xyz.min(axis=0), xyz.max(axis=0)+1
    return Structure('Foundation', tuple(lo), tuple(hi-lo), (material,), xyz, np.zeros(len(xyz), np.uint16))
