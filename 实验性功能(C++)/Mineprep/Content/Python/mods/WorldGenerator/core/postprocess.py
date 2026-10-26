"""Bounded batch surface extensions, applied after final entity assembly, before merging.

MC XYZ throughout. Terrain/reference heights and physical wet masks are untouched.
There is no full-volume allocation or arbitrary stage graph.
"""
from dataclasses import dataclass, replace
from types import MappingProxyType
from time import perf_counter
import numpy as np
from .data import Region, check_cancel
from .shell import WorldArrays


@dataclass(frozen=True)
class SurfaceProcessor:
    id: str
    function: str
    blocks: tuple
    radius: int
    enabled_param: object
    fn: object
    sky_only: bool = False
    category: str = ''
    volume: bool = False


@dataclass(frozen=True)
class SurfaceBatch:
    xyz: np.ndarray       # absolute MC XYZ, support cells (not the cell above)
    types: np.ndarray     # pack block IDs
    kind: np.ndarray      # 0 terrain, 1 feature, 2 displayed horizontal surface
    biomes: np.ndarray
    sky_open: np.ndarray
    water_levels: np.ndarray  # logical level; NaN for entities


@dataclass(frozen=True)
class SurfacePatch:
    xyz: np.ndarray
    types: np.ndarray
    replace: np.ndarray   # bool[N]; replace an emitted cell, or add in empty space


def _keys(points):
    return np.ascontiguousarray(points, dtype=np.int64).view(np.dtype([('x','<i8'),('y','<i8'),('z','<i8')])).reshape(-1)


class _PointIndex:
    """One stage's sparse coordinates; bounded scalar keys, with an exact wide-range fallback."""
    def __init__(self, points, exclude_mask=None):
        self.minimum = points.min(axis=0) if len(points) else np.zeros(3, np.int64)
        self.maximum = points.max(axis=0) if len(points) else self.minimum
        spans = [int(b)-int(a)+1 for a,b in zip(self.minimum,self.maximum)]
        self.scalar = spans[0]*spans[1]*spans[2] <= np.iinfo(np.int64).max
        self.strides = (spans[1], spans[2])
        keys = self._keys(points)
        self.order = np.argsort(keys) if self.scalar else np.lexsort((points[:,2],points[:,1],points[:,0]))
        if exclude_mask is not None: self.order=self.order[~exclude_mask[self.order]]
        self.keys = keys[self.order]

    def _keys(self, points):
        if not self.scalar:
            return _keys(points)
        p = np.asarray(points, np.int64)-self.minimum
        return (p[:,0]*self.strides[0]+p[:,1])*self.strides[1]+p[:,2]

    def lookup(self, points):
        found = np.zeros(len(points), bool)
        indices = np.zeros(len(points), np.int64)
        if not len(self.keys) or not len(points):
            return found, indices
        inside = np.flatnonzero(((points>=self.minimum)&(points<=self.maximum)).all(axis=1))
        wanted = self._keys(points[inside])
        positions = np.searchsorted(self.keys, wanted)
        use = positions < len(self.keys)
        use[use] &= self.keys[positions[use]] == wanted[use]
        found[inside[use]] = True
        indices[inside[use]] = self.order[positions[use]]
        return found, indices


def _lookup(points, queries):
    return _PointIndex(points).lookup(queries)


class _EntityIndex:
    """Sparse ordinary entities plus column intervals, preserving output indices."""
    def __init__(self, points, columns=None, soft_mask=None):
        self.columns=columns
        if columns is None:
            self.sparse=_PointIndex(points,soft_mask);self.mapping=None
        else:
            self.mapping=(np.arange(len(points)) if columns is None else
                          np.r_[np.arange(columns.start),np.arange(columns.start+columns.count,len(points))])
            if soft_mask is not None: self.mapping=self.mapping[~soft_mask[self.mapping]]
            self.sparse=_PointIndex(points[self.mapping])

    def lookup(self, points):
        found,at=self.sparse.lookup(points)
        if self.mapping is not None:
            at[found]=self.mapping[at[found]]
            if self.columns is not None:
                remaining=np.flatnonzero(~found)
                filled,indices=self.columns.lookup(points[remaining])
                found[remaining[filled]]=True;at[remaining[filled]]=indices[filled]
        return found,at


class SurfaceQuery:
    def __init__(self, world, points, types, allowed, *, point_index=None, resources=None, terrain_tops=None,
                 skyline=None):
        from .planning import Resources
        self.world, self.points, self.types, self.allowed = world, points, types, allowed
        self.skyline = skyline
        self.point_index = point_index if point_index is not None else _EntityIndex(points,getattr(world,'column_index',None),getattr(world,'soft_mask',None))
        self.resources = resources if resources is not None else Resources(world.pack, world.params, world.spec.seed)
        self.terrain_tops = terrain_tops
        self._tops_complete = terrain_tops is not None and np.all(terrain_tops >= world.params['world.y_min'])

    def _check(self, points):
        r = self.allowed
        if np.any((points[:,0]<r.x0)|(points[:,0]>=r.x0+r.width)|(points[:,2]<r.z0)|(points[:,2]>=r.z0+r.depth)):
            raise ValueError('surface query exceeds declared radius')

    def reference(self, region, *, include_surface=True):
        self._check(np.array([[region.x0,0,region.z0], [region.x0+region.width-1,0,region.z0+region.depth-1]]))
        from .store import reference
        w = self.world
        return reference(w.pack, w.params, w.spec.seed, region, self.resources, include_surface=include_surface)

    def occupied(self, points):
        from . import geometry
        points = np.asarray(points)
        if points.ndim != 2 or points.shape[1] != 3 or points.dtype.kind not in 'iu':
            raise ValueError('occupied requires integer XYZ[N,3]')
        self._check(points)
        found, _ = self.point_index.lookup(points)
        if self.world.model_index is not None:
            found |= self.world.model_index.occupied(points)
        remaining = np.flatnonzero(~found)
        if self.skyline is not None and len(remaining):
            # Shells emit every solid cell below air, so nothing above the
            # highest emitted cube of a column can be terrain.
            p, r = points[remaining], self.world.region
            above = (p[:,0]>=r.x0)&(p[:,0]<r.x0+r.width)&(p[:,2]>=r.z0)&(p[:,2]<r.z0+r.depth)
            at = np.flatnonzero(above)
            above[at] = p[at,1] > self.skyline[(p[at,2]-r.z0)*r.width+p[at,0]-r.x0]
            remaining = remaining[~above]
        # Exact integer tops belong to this entity stage, never to a persistent
        # cache. Standalone queries retain the float32 uncertainty fallback.
        if len(remaining) and geometry.height_mode(self.world.pack) and not geometry.enabled(self.world.pack,self.world.params):
            p = points[remaining]
            r = self.world.region
            inside = ((p[:,0]>=r.x0)&(p[:,0]<r.x0+r.width)&(p[:,2]>=r.z0)&(p[:,2]<r.z0+r.depth))
            if self.terrain_tops is not None and not self._tops_complete:
                # No emitted terrain cube means no proven integer top (for
                # example a custom non-cube terrain material). Query exactly.
                at = np.flatnonzero(inside)
                inside[at] &= self.terrain_tops[p[at,2]-r.z0,p[at,0]-r.x0] >= self.world.params['world.y_min']
            q = p[inside]
            valid_y = (q[:,1]>=self.world.params['world.y_min'])&(q[:,1]<self.world.params['world.y_max'])
            if self.terrain_tops is not None:
                top = self.terrain_tops[q[:,2]-r.z0,q[:,0]-r.x0]
                found[remaining[inside]] = (q[:,1]<=top)&valid_y
                uncertain = np.zeros(len(q), bool)
            else:
                height = self.world.heights[q[:,2]-r.z0,q[:,0]-r.x0]
                found[remaining[inside]] = (q[:,1]<height)&valid_y
                uncertain = (np.abs(q[:,1]-height.astype(np.float64))<=np.abs(np.spacing(height)))&valid_y
            remaining = np.concatenate((remaining[~inside],remaining[inside][uncertain]))
        if len(remaining):
            q = points[remaining]
            # World-aligned bounded reference queries, even for widely spaced samples.
            groups = np.unique(q[:,[0,2]]//64, axis=0)
            for tx,tz in groups:
                use = (q[:,0]//64==tx)&(q[:,2]//64==tz)
                p = q[use]
                r = Region(int(tx)*64, int(tz)*64,64,64)
                from .planning import SurfaceTiles
                tops = np.ceil(SurfaceTiles(self.resources).values(p[:,0], p[:,2])[0]).astype(np.int64)-1
                solid,_ = geometry.sample(self.world.pack,self.world.params,self.world.spec.seed,
                                           p[:,0,None,None],p[:,1,None,None],p[:,2,None,None],tops[:,None],resources=self.resources)
                found[remaining[use]] = solid.reshape(-1)
                world_region = self.world.region
                outside = ((p[:,0] < world_region.x0) | (p[:,0] >= world_region.x0+world_region.width) |
                           (p[:,2] < world_region.z0) | (p[:,2] >= world_region.z0+world_region.depth))
                if outside.any():
                    from .multi_features import generate
                    radius=max((max(abs(v) for row in f.bounds for v in (row[0],row[2]))
                                for f in self.world.pack.features if f.type=='multi_block'),default=0)
                    roots=Region(r.x0-radius,r.z0-radius,r.width+2*radius,r.depth+2*radius)
                    features, _, _ = generate(self.world.pack, self.world.params, self.world.spec.seed,
                                              roots, world_region, self.resources, 4000000)
                    fp = features.xyz.astype(np.int64)
                    fp[:,0] += world_region.x0; fp[:,2] += world_region.z0
                    occupied, _ = _lookup(fp, p)
                    found[remaining[use]] |= occupied
                    if features.models:
                        from .templates import ModelIndex
                        found[remaining[use]] |= ModelIndex(features.models,self.world.params['world.y_min'],
                                                           self.world.params['world.y_max']).occupied(p)
                    from .column_features import query_occupied
                    found[remaining[use]] |= query_occupied(self.world.pack,self.world.params,
                        self.world.spec.seed,r,p,self.resources)
        return found


@dataclass(frozen=True)
class SurfaceContext:
    pack: object
    params: object
    seed: int
    region: object
    block_ids: object
    query: object


def _cubes(world, types):
    shapes = np.array([world.pack.block_defs[n].shape for n in world.pack.blocks])
    cubes = shapes[types] == 'cube'
    columns=getattr(world,'column_index',None)
    if columns is not None:
        cubes[columns.start:columns.start+columns.count]=False
        tops=columns.surfaces()
        cubes[tops]=shapes[types[tops]]=='cube'
    return cubes, shapes[types] == 'surface'


def _skyline(world, points, types):
    """Highest emitted cube per column, including interval and model tops."""
    cubes, _ = _cubes(world, types)
    col=(points[:,2]-world.region.z0)*world.region.width+points[:,0]-world.region.x0
    top=np.full(world.region.cells,world.params['world.y_min']-1,np.int64)
    np.maximum.at(top,col[cubes],points[cubes,1])
    if world.model_index is not None: world.model_index.add_tops(top,world.region)
    return top


def _surfaces(world, points, types, offsets, query, feature_at, *, sky_only=False, diagnostics=None):
    cubes, water = _cubes(world, types)
    # A sky-only processor never consumes underground/covered surfaces, so
    # discard those before re-entering potentially expensive 3D occupancy.
    col=(points[:,2]-world.region.z0)*world.region.width+points[:,0]-world.region.x0
    if query.skyline is None:
        query.skyline=_skyline(world,points,types)
    top=query.skyline
    candidates = np.flatnonzero(cubes)
    water_candidates = np.flatnonzero(water)
    before = len(candidates) + len(water_candidates)
    if sky_only:
        candidates = candidates[points[candidates,1] >= top[col[candidates]]]
        water_candidates = water_candidates[points[water_candidates,1] >= top[col[water_candidates]]]
    if diagnostics is not None:
        diagnostics['surface_candidates_before'] += before
        diagnostics['surface_candidates_after'] += len(candidates) + len(water_candidates)
        diagnostics['surface_probe_points'] += len(candidates)
    above = points[candidates].copy(); above[:,1] += 1
    # A side-only shell cell may have implicit terrain above it, even if absent from the sparse shell.
    if len(candidates):
        candidates=candidates[~query.occupied(above)]
    selected = np.concatenate((candidates,water_candidates))
    p,t = points[selected],types[selected]
    kind=np.where(water[selected],2,0).astype(np.uint8)
    features=world.feature_cells
    if features is not None and features.count:
        is_feature=np.zeros(len(points),bool);is_feature[feature_at]=True
        kind[(kind!=2)&is_feature[selected]]=1
    index=(p[:,2]-world.region.z0)*world.region.width+p[:,0]-world.region.x0
    sky=p[:,1]>=top[index]
    biomes=world.biome_ids[p[:,2]-world.region.z0,p[:,0]-world.region.x0]
    levels=np.full(len(p),np.nan)
    use = kind == 2
    levels[use] = p[use,1] + offsets[selected[use]]
    for a in (p,t,kind,biomes,sky,levels):a.setflags(write=False)
    return SurfaceBatch(p,t,kind,biomes,sky,levels)


def apply_world(world, *, max_instances, cancel_event=None):
    from . import geometry
    processors=[p for p in world.pack.surface_processors if p.enabled_param is None or world.params[p.enabled_param]]
    if not processors:
        return world
    if not geometry.height_mode(world.pack):
        world=replace(world,stats=dict(world.stats,surface_unsupported=tuple(p.id for p in processors if not p.volume)))
        processors=[p for p in processors if p.volume]
        if not processors:
            return world
    started=perf_counter()
    pack=world.pack; index={n:i for i,n in enumerate(pack.blocks)}
    points=world.arrays.xyz.astype(np.int64);points[:,0]+=world.region.x0;points[:,2]+=world.region.z0
    types=np.array([index[n] for n in world.arrays.names],np.uint16)[world.arrays.types].copy()
    rotations=np.zeros(len(points),np.uint8) if world.arrays.rotations is None else world.arrays.rotations.copy()
    offsets=np.array(world.arrays.y_offsets)[world.arrays.types].copy()
    if world.arrays.instance_y_offsets is not None:offsets+=world.arrays.instance_y_offsets
    added=replaced_count=0
    features=world.feature_cells
    column_index=getattr(world,'column_index',None)
    soft_mask=getattr(world,'soft_mask',None)
    point_index=_EntityIndex(points,column_index,soft_mask)
    feature_at=None
    if features is not None and features.count:
        if column_index is not None:
            feature_at=np.arange(len(points)-features.count,len(points))
        elif soft_mask is not None:
            feature_at=np.arange(len(points)-features.count,len(points))
        else:
            fp=features.xyz.astype(np.int64);fp[:,0]+=world.region.x0;fp[:,2]+=world.region.z0
            _,feature_at=point_index.lookup(fp)
    terrain_tops = None
    if not geometry.enabled(pack, world.params):
        cubes = np.array([pack.block_defs[n].shape == 'cube' for n in pack.blocks])[types]
        if feature_at is not None:
            cubes[feature_at] = False
        col = (points[:,2]-world.region.z0)*world.region.width+points[:,0]-world.region.x0
        terrain_tops = np.full(world.region.cells,world.params['world.y_min']-1,np.int64)
        np.maximum.at(terrain_tops,col[cubes],points[cubes,1])
        # A cube scatter cell is emitted immediately above its terrain column.
        plant_shapes = np.array([False, *(pack.block_defs[n].shape == 'cube' for n in pack.blocks)])
        terrain_tops -= plant_shapes[world.plant_ids.reshape(-1)]
        terrain_tops = terrain_tops.reshape(world.region.shape)
        terrain_tops.setflags(write=False)
    phase_query=SurfaceQuery(world,points,types,world.region,point_index=point_index,terrain_tops=terrain_tops)
    diagnostics=dict(surface_candidates_before=0,surface_candidates_after=0,surface_probe_points=0)
    for stage, processor in enumerate(processors):
        check_cancel(cancel_event)
        phase_query.skyline=None
        surfaces=_surfaces(world,points,types,offsets,phase_query,feature_at,
                           sky_only=processor.sky_only,diagnostics=diagnostics)
        patches=[]
        for tile in world.region.tiles(256):
            check_cancel(cancel_event)
            r=tile.expanded(processor.radius)
            use=(surfaces.xyz[:,0]>=r.x0)&(surfaces.xyz[:,0]<r.x0+r.width)&(surfaces.xyz[:,2]>=r.z0)&(surfaces.xyz[:,2]<r.z0+r.depth)
            batch=SurfaceBatch(*(getattr(surfaces,k)[use] for k in SurfaceBatch.__dataclass_fields__))
            for a in batch.__dict__.values():a.setflags(write=False)
            query=SurfaceQuery(world,points,types,r,point_index=point_index,resources=phase_query.resources,
                               terrain_tops=terrain_tops,skyline=phase_query.skyline)
            context=SurfaceContext(pack,world.params,world.spec.seed,tile,MappingProxyType(index),query)
            patch=processor.fn(context,batch)
            if not isinstance(patch,SurfacePatch):raise ValueError(f'{processor.id}: must return SurfacePatch')
            q,t,flags=map(np.asarray,(patch.xyz,patch.types,patch.replace))
            if q.ndim!=2 or q.shape[1]!=3 or q.dtype.kind not in 'iu' or t.shape!=(len(q),) or t.dtype.kind not in 'iu' or flags.shape!=(len(q),) or flags.dtype!=bool:
                raise ValueError(f'{processor.id}: invalid patch arrays')
            if np.any((q[:,0]<tile.x0)|(q[:,0]>=tile.x0+tile.width)|(q[:,2]<tile.z0)|(q[:,2]>=tile.z0+tile.depth)
                      |(q[:,1]<world.params['world.y_min'])|(q[:,1]>=world.params['world.y_max'])):
                raise ValueError(f'{processor.id}: patch exceeds output bounds')
            if not np.isin(t,[index[n] for n in processor.blocks]).all():raise ValueError(f'{processor.id}: undeclared output block')
            patch_keys=_PointIndex(q).keys
            if np.any(patch_keys[1:]==patch_keys[:-1]):raise ValueError(f'{processor.id}: duplicate patch cells')
            emitted,at=point_index.lookup(q)
            if np.any(flags&~emitted) or np.any(query.occupied(q[~flags])):
                raise ValueError(f'{processor.id}: replacement missing or addition occupied')
            from .masks import active, weight
            if any(active(pack, kind, processor.category) for kind in ('vegetation','clearance')):
                from .noise3 import hash01
                use = hash01(*q.T, world.spec.seed, 'masks/'+processor.id) < weight(pack, processor.category, q[:,0], q[:,2])
                q,t,flags,at = q[use],t[use],flags[use],at[use]
            patches.append((q.copy(),t.copy(),flags.copy(),at))
        count=sum(np.count_nonzero(~flags) for _,_,flags,_ in patches)
        if len(points)+count+len(world.model_instances)>max_instances:raise ValueError('surface processing exceeds max_instances')
        for q,t,flags,at in patches:
            types[at[flags]]=t[flags];offsets[at[flags]]=0;rotations[at[flags]]=0
            replaced_count+=int(flags.sum());added+=int((~flags).sum())
        if count:
            points=np.concatenate([points,*(q[~flags] for q,_,flags,_ in patches)])
            types=np.concatenate([types,*(t[~flags] for _,t,flags,_ in patches)])
            offsets=np.concatenate((offsets,np.zeros(count)));rotations=np.concatenate((rotations,np.zeros(count,np.uint8)))
            if soft_mask is not None: soft_mask=np.r_[soft_mask,np.zeros(count,bool)]
            if stage+1<len(processors):
                point_index=_EntityIndex(points,column_index,soft_mask)
                phase_query=SurfaceQuery(world,points,types,world.region,point_index=point_index,resources=phase_query.resources,terrain_tops=terrain_tops)
    if not added and not replaced_count:
        elapsed=perf_counter()-started
        stats=dict(world.stats,surface_added=0,surface_replaced=0,**diagnostics)
        stats['stages']=dict(stats.get('stages',{}),surface_processing=elapsed)
        stats['seconds']+=elapsed
        return replace(world,stats=stats)
    used=np.unique(types); remap=np.zeros(len(pack.blocks),np.uint32);remap[used]=np.arange(len(used))
    names=tuple(pack.blocks[i] for i in used)
    local=points.copy();local[:,0]-=world.region.x0;local[:,2]-=world.region.z0
    arrays=WorldArrays(world.region,local.astype(np.int32),remap[types],names,world.arrays.solid_count,
                       block_defs=tuple(pack.block_defs[n] for n in names),y_offsets=(0.,)*len(names),
                       instance_y_offsets=offsets if np.any(offsets) else None,
                       rotations=rotations if np.any(rotations) else None)
    if features is not None:
        at=feature_at if feature_at is not None else np.empty(0,np.int64)
        features=replace(features,types=remap[types[at]],names=names,block_defs=arrays.block_defs,
                         y_offsets=arrays.y_offsets,instance_y_offsets=offsets[at] if np.any(offsets[at]) else None,
                         rotations=rotations[at] if np.any(rotations[at]) else None)
        for a in (features.types, features.instance_y_offsets, features.rotations):
            if a is not None: a.setflags(write=False)
    for a in (arrays.xyz,arrays.types,arrays.instance_y_offsets,arrays.rotations):
        if a is not None:a.setflags(write=False)
    stats=dict(world.stats,visible=arrays.count,surface_added=added,surface_replaced=replaced_count,**diagnostics)
    stats['stages']=dict(stats.get('stages',{}),surface_processing=perf_counter()-started)
    stats['seconds']+=perf_counter()-started
    if soft_mask is not None: soft_mask.setflags(write=False)
    return replace(world,arrays=arrays,feature_cells=features,stats=stats,soft_mask=soft_mask)
