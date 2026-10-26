"""Deterministic surface placement of shared structures, independent of Unreal."""
from dataclasses import dataclass
from collections.abc import Mapping
from numbers import Real

import numpy as np

from .building import Structure
from .data import Region, require_int
from .grounding import (_query, _points, _bottoms, _ground_y, _translated,
                        _support_depths, _foundation_cells)
from . import geometry
from .multi_features import _thin
from .noise3 import hash01
from .scene import _keys, _members
from .templates import rotate


@dataclass(frozen=True)
class ScatterResult:
    placements: tuple
    stats: dict


@dataclass(frozen=True)
class _Shape:
    structure: Structure
    rotation: int
    points: np.ndarray
    bottom: np.ndarray
    supports: np.ndarray
    bounds: np.ndarray


def _number(value, label):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not np.isfinite(value):
        raise ValueError(f'{label} must be a finite real number')
    return float(value)


def _choices(structures, rotations, max_cells):
    entries = [structures] if isinstance(structures, Structure) else list(structures)
    if not entries:
        raise ValueError('scatter needs at least one nonempty Structure')
    shapes, weights, cache = [], [], {}
    for entry in entries:
        s, weight = (entry, 1.) if isinstance(entry, Structure) else entry
        weight = _number(weight, 'structure weight')
        if not isinstance(s, Structure) or not s.count or weight <= 0:
            raise ValueError('scatter needs nonempty Structures with positive weights')
        if s.count > max_cells:
            raise ValueError(f'structure exceeds max_cells={max_cells:,}')
        orientations = []
        for rotation in rotations:
            key = s.key, rotation
            if key not in cache:
                p = rotate(s.xyz, rotation//90).astype(np.int64)
                cache[key] = _Shape(s, rotation, p, _bottoms(p), p[p[:, 1] == p[:, 1].min()],
                                    np.array([p.min(axis=0), p.max(axis=0)+1]))
            orientations.append(cache[key])
        shapes.append(orientations)
        weights.append(weight)
    weights = np.asarray(weights)/max(weights)
    return shapes, np.cumsum(weights)/weights.sum()


def _conditions(world, biomes, where):
    mask = np.ones(world.region.shape, bool)
    if biomes is not None:
        names = [b.id for b in world.pack.biomes]
        wanted = [biomes] if isinstance(biomes, str) else list(biomes)
        if any(n not in names for n in wanted):
            raise ValueError('scatter biomes contain an unknown biome ID')
        mask &= np.isin(world.biome_ids, [names.index(n) for n in wanted])
    if where is not None and not isinstance(where, Mapping):
        raise ValueError('where must map field names to min/max conditions')
    for name, bounds in (where or {}).items():
        if not isinstance(bounds, Mapping) or not bounds or set(bounds)-{'min','max'}:
            raise ValueError('where requires field: {min: number, max: number}')
        limits = {k:_number(v, name+'.'+k) for k,v in bounds.items()}
        if 'min' in limits and 'max' in limits and limits['min'] >= limits['max']:
            raise ValueError(f'{name}: min must be less than max')
        if name != 'height' and name not in world.fields:
            raise ValueError(f'field {name!r} was not retained; generate with keep_fields=({name!r},)')
        values = world.heights if name == 'height' else world.fields[name]
        mask &= np.isfinite(values)
        if 'min' in limits:
            mask &= values >= limits['min']
        if 'max' in limits:
            mask &= values < limits['max']
    return mask


def scatter(world, structures, *, region=None, spacing=16, density=1.,
            biomes=None, where=None, avoid_water=True, rotations=(0,90,180,270),
            max_depth=0, existing=(), seed=None, salt='scatter',
            max_candidates=65_536, max_cells=4_000_000):
    query = _query(world)
    require_int('spacing', spacing, 1, 2**31-1)
    require_int('max_depth', max_depth, 0, 2**31-1)
    require_int('max_candidates', max_candidates, 1, 2**63-1)
    require_int('max_cells', max_cells, 1, 2**63-1)
    seed = world.spec.seed if seed is None else seed
    require_int('seed', seed, -(2**63), 2**63-1)
    if not isinstance(salt, str) or type(avoid_water) is not bool:
        raise ValueError('salt must be a string and avoid_water a bool')
    rotations = tuple(dict.fromkeys(rotations))
    if not rotations or any(type(r) is not int or r not in (0,90,180,270) for r in rotations):
        raise ValueError('rotations must contain 0, 90, 180 or 270')
    choices, cuts = _choices(structures, rotations, max_cells)
    conditions = _conditions(world, biomes, where)
    probability = np.asarray(density)
    if (probability.shape not in ((), world.region.shape) or probability.dtype.kind not in 'fiu'
            or not np.isfinite(probability).all() or np.any((probability<0)|(probability>1))):
        raise ValueError('density must be [0,1], scalar or a world-aligned [Z,X] array')
    r = world.region if region is None else region if isinstance(region, Region) else Region(*region)
    world.region.slices(r)
    existing = tuple(existing)
    old = [_points(world, p) for p in existing]
    old_keys = np.unique(_keys(np.concatenate(old))) if old else np.empty(0, dtype=np.dtype((np.void,24)))
    radius = max(int(np.abs(s.bounds[:, [0,2]]).max()) for row in choices for s in row)
    halo = max(2*radius, spacing)
    wr = world.region
    x0, z0 = max(wr.x0,r.x0-halo), max(wr.z0,r.z0-halo)
    x1, z1 = min(wr.x0+wr.width,r.x0+r.width+halo), min(wr.z0+wr.depth,r.z0+r.depth+halo)
    nx, nz = (x1-1)//spacing-x0//spacing+1, (z1-1)//spacing-z0//spacing+1
    if nx*nz > max_candidates:
        raise ValueError(f'scatter exceeds max_candidates={max_candidates:,}; increase spacing or narrow region')
    cx,cz = np.meshgrid(np.arange(x0//spacing,(x1-1)//spacing+1),
                        np.arange(z0//spacing,(z1-1)//spacing+1))
    cx,cz = cx.ravel(),cz.ravel()
    def draw(channel):
        return hash01(cx,np.zeros_like(cx),cz,seed,salt+'/'+channel)
    x = cx*spacing+np.floor(draw('x')*spacing).astype(np.int64)
    z = cz*spacing+np.floor(draw('z')*spacing).astype(np.int64)
    inside = (x>=x0)&(x<x1)&(z>=z0)&(z<z1)
    cx,cz,x,z = cx[inside],cz[inside],x[inside],z[inside]
    n = len(x)
    owned = (x>=r.x0)&(x<r.x0+r.width)&(z>=r.z0)&(z<r.z0+r.depth)
    ix,iz = x-wr.x0,z-wr.z0
    valid, reasons = np.ones(n,bool), np.full(n,'accepted',dtype='<U12')
    def keep(test, reason):
        reasons[valid & ~test] = reason
        valid[:] &= test
    probs = probability if probability.ndim == 0 else probability[iz,ix]
    keep(draw('density') < probs, 'density')
    keep(conditions[iz,ix], 'conditions')
    variants = np.minimum(np.searchsorted(cuts,draw('variant'),side='right'),len(choices)-1)
    turns = np.minimum((draw('rotation')*len(rotations)).astype(np.intp),len(rotations)-1)
    shape_ids = variants*len(rotations)+turns
    shapes = [s for row in choices for s in row]
    anchors = np.column_stack((x,np.zeros(n,np.int64),z))
    counts = np.array([s.structure.count for s in shapes])[shape_ids]
    bounds = np.array([s.bounds for s in shapes])[shape_ids]+anchors[:,None,:]
    keep((bounds[:,0,0]>=wr.x0)&(bounds[:,1,0]<=wr.x0+wr.width)
         &(bounds[:,0,2]>=wr.z0)&(bounds[:,1,2]<=wr.z0+wr.depth),'bounds')
    work_cells = int(counts[valid].sum())
    if work_cells > max_cells:
        raise ValueError(f'scatter candidate geometry exceeds max_cells={max_cells:,}')
    density_bounds = (geometry.plan_bounds(world.pack,world.params,world.spec.seed,wr,query.resources)
                      if valid.any() else ())
    foot_depths = [None]*n
    collision_bounds = np.zeros((n,2,3),np.int64)
    wet = world.wet_mask if world.wet_mask is not None else world.water_mask
    for index, shape in enumerate(shapes):
        ids = np.flatnonzero(valid & (shape_ids==index))
        if not len(ids):
            continue
        y, supported = _ground_y(query,shape.bottom,anchors[ids][:,[0,2]],density_bounds)
        anchors[ids[supported],1] = y[supported]
        good = supported.copy()
        good[supported] &= ((y[supported]+shape.bounds[0,1]>=world.params['world.y_min'])
                            &(y[supported]+shape.bounds[1,1]<=world.params['world.y_max']))
        valid[ids[~good]],reasons[ids[~good]] = False,'ground'
        ids = ids[good]
        if not len(ids):
            continue
        if avoid_water:
            blocked = np.zeros(len(ids),bool)
            for owners,p in _translated(shape.bottom,anchors[ids]):
                blocked[owners[wet[p[:,2]-wr.z0,p[:,0]-wr.x0]]] = True
            valid[ids[blocked]],reasons[ids[blocked]] = False,'water'
            ids = ids[~blocked]
        if not len(ids):
            continue
        blocked = np.zeros(len(ids),bool)
        for owners,p in _translated(shape.points,anchors[ids]):
            hit = query.terrain(p) | _members(p,old_keys)
            for mask in query.obstacles(p).values():
                hit |= mask
            blocked[owners[hit]] = True
        valid[ids[blocked]],reasons[ids[blocked]] = False,'collision'
        ids = ids[~blocked]
        depths = np.empty((len(ids),len(shape.supports)),np.int64)
        cursor = 0
        for owners,p in _translated(shape.supports,anchors[ids]):
            d = _support_depths(query,p,max_depth)
            depths.ravel()[cursor:cursor+len(d)] = d
            cursor += len(d)
        good = (depths>=0).all(axis=1)
        valid[ids[~good]],reasons[ids[~good]] = False,'support'
        ids,depths = ids[good],depths[good]
        work_cells += int(depths.sum())
        if work_cells > max_cells:
            raise ValueError(f'scatter candidate geometry exceeds max_cells={max_cells:,}')
        blocked = np.zeros(len(ids),bool)
        cursor = 0
        for owners,p in _translated(shape.supports,anchors[ids]):
            d = depths.ravel()[cursor:cursor+len(p)]
            cursor += len(p)
            for foot_owners,q in _foundation_cells(p,d):
                hit = _members(q,old_keys)
                for mask in query.obstacles(q).values():
                    hit |= mask
                blocked[owners[foot_owners[hit]]] = True
        valid[ids[blocked]],reasons[ids[blocked]] = False,'support'
        for row,i in enumerate(ids):
            foot_depths[i] = depths[row]
            collision_bounds[i] = shape.bounds+anchors[i]
            collision_bounds[i,0,1] -= int(depths[row].max())
    ids = np.flatnonzero(valid)
    cached = {}
    def cells(i):
        if i not in cached:
            shape = shapes[shape_ids[i]]
            parts = [shape.points+anchors[i]]
            parts.extend(p for _,p in _foundation_cells(shape.supports+anchors[i],foot_depths[i]))
            p = np.concatenate(parts)
            cached[i] = p,np.unique(_keys(p))
        return cached[i]
    def overlap(a,b):
        ia,ib = ids[a],ids[b]
        delta = anchors[ia][:,[0,2]]-anchors[ib][:,[0,2]]
        hit = np.hypot(delta[:,0],delta[:,1]) < spacing
        possible = (~hit & np.all(collision_bounds[ia,0]<collision_bounds[ib,1],axis=1)
                    & np.all(collision_bounds[ib,0]<collision_bounds[ia,1],axis=1))
        for row in np.flatnonzero(possible):
            hit[row] = _members(cells(int(ia[row]))[0],cells(int(ib[row]))[1]).any()
        return hit
    if len(ids):
        boxes = collision_bounds[ids].copy()
        pad = (spacing+1)//2
        boxes[:,0][:,[0,2]] = np.minimum(boxes[:,0][:,[0,2]],anchors[ids][:,[0,2]]-pad)
        boxes[:,1][:,[0,2]] = np.maximum(boxes[:,1][:,[0,2]],anchors[ids][:,[0,2]]+pad+1)
        boxes[:,0,1],boxes[:,1,1] = world.params['world.y_min'],world.params['world.y_max']
        retained = _thin(boxes.reshape(-1,6),draw('priority')[ids],overlap=overlap)
        reasons[ids[~retained]] = 'competition'
        ids = ids[retained & owned[ids]]
    placements = tuple(shapes[shape_ids[i]].structure.at(tuple(map(int,anchors[i])),shapes[shape_ids[i]].rotation) for i in ids)
    rejected = {str(reason):int(np.count_nonzero(owned & (reasons==reason)))
                for reason in np.unique(reasons[owned]) if reason!='accepted'}
    templates = {}
    for p in placements:
        templates[p.structure.key] = templates.get(p.structure.key,0)+1
    stats = dict(candidates=int(owned.sum()),queried_candidates=n,accepted=len(placements),
                 rejected=rejected,templates=templates,checked_cells=work_cells,seed=seed)
    return ScatterResult(placements,stats)
