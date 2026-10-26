"""Stage-local column entities: validate intervals, clip obstacles, expand once.

No candidate competition or persistent cache. Complete cells remain available
to the existing merger; surface queries use intervals instead of sorting them.
"""
from dataclasses import dataclass, replace
from types import MappingProxyType, SimpleNamespace
from time import perf_counter
import numpy as np
from .data import check_cancel
from .features import ColumnBatch, enabled
from .store import reference as reference_for
from .planning import Resources
from .surface import bound
from .water import displayed as water_displayed
from . import geometry


@dataclass(frozen=True)
class ColumnContext:
    seed: int
    params: object
    feature: object
    block_ids: object
    region: object
    reference: object
    allowed: np.ndarray
    density: float
    patch_scale: float

    def param(self, name): return self.params[name]


class ColumnIndex:
    """Intervals and output offsets; full cells need no second spatial sort."""
    def __init__(self, region, y_min, y_max, xz, lower, upper):
        self.region, self.y_min, self.span = region, y_min, y_max-y_min
        self.xz, self.lower, self.upper = xz, lower, upper
        self.cols = (xz[:,1]-region.z0)*region.width+xz[:,0]-region.x0
        self.keys = self.cols*self.span+lower-y_min
        self.starts = np.cumsum(upper-lower)-(upper-lower)
        self.total = int((upper-lower).sum())
        self.removed = np.empty(0,np.int64)
        self.start = 0

    @property
    def count(self): return self.total-len(self.removed)

    def lookup(self, points):
        found=np.zeros(len(points),bool); at=np.zeros(len(points),np.int64)
        if not len(self.keys) or not len(points): return found,at
        r=self.region
        inside=np.flatnonzero((points[:,0]>=r.x0)&(points[:,0]<r.x0+r.width)&
            (points[:,2]>=r.z0)&(points[:,2]<r.z0+r.depth)&
            (points[:,1]>=self.y_min)&(points[:,1]<self.y_min+self.span))
        q=points[inside];cols=(q[:,2]-r.z0)*r.width+q[:,0]-r.x0
        segment=np.searchsorted(self.keys,cols*self.span+q[:,1]-self.y_min,side='right')-1
        use=segment>=0
        use[use]&=(self.cols[segment[use]]==cols[use])&(q[use,1]<self.upper[segment[use]])
        ids=inside[use];s=segment[use]
        local=self.starts[s]+points[ids,1]-self.lower[s]
        removed=np.searchsorted(self.removed,local)
        alive=removed<len(self.removed)
        alive[alive]=self.removed[removed[alive]]==local[alive]
        ids,local,removed=ids[~alive],local[~alive],removed[~alive]
        found[ids]=True;at[ids]=self.start+local-removed
        return found,at

    def surfaces(self):
        local=self.starts+self.upper-self.lower-1
        removed=np.searchsorted(self.removed,local)
        blocked=removed<len(self.removed)
        blocked[blocked]=self.removed[removed[blocked]]==local[blocked]
        return self.start+local[~blocked]-removed[~blocked]


def validate(batch, feature, ctx):
    if not isinstance(batch,ColumnBatch): raise ValueError(f'{feature.id}: must return ColumnBatch')
    xz,lo,hi,types=map(np.asarray,(batch.xz,batch.lower,batch.upper,batch.types))
    n=len(xz)
    if xz.shape!=(n,2) or xz.dtype.kind not in 'iu' or any(a.shape!=(n,) or a.dtype.kind not in 'iu' for a in (lo,hi,types)):
        raise ValueError(f'{feature.id}: invalid column arrays')
    r=ctx.region
    if np.any((xz[:,0]<r.x0)|(xz[:,0]>=r.x0+r.width)|(xz[:,1]<r.z0)|(xz[:,1]>=r.z0+r.depth)):
        raise ValueError(f'{feature.id}: columns exceed output bounds')
    if np.any(hi<=lo) or np.any(hi-lo>feature.max_height):
        raise ValueError(f'{feature.id}: invalid column height')
    if not np.isin(types,[ctx.block_ids[b] for b in feature.blocks]).all():
        raise ValueError(f'{feature.id}: undeclared column material')
    order=np.lexsort((lo,xz[:,0],xz[:,1]));xz,lo,hi,types=xz[order],lo[order],hi[order],types[order]
    if n>1 and np.any(np.all(xz[1:]==xz[:-1],axis=1)&(lo[1:]<hi[:-1])):
        raise ValueError(f'{feature.id}: overlapping column intervals')
    if n:
        starts=np.flatnonzero(np.r_[True,np.any(xz[1:]!=xz[:-1],axis=1)])
        ends=np.r_[starts[1:]-1,n-1]
        if np.any(hi[ends]-lo[starts]>feature.max_height):
            raise ValueError(f'{feature.id}: combined column height exceeds declaration')
    ref=ctx.reference;rr=ref.ctx
    xx=xz[:,0]-int(rr.x[0,0]);zz=xz[:,1]-int(rr.z[0,0])
    use=ctx.allowed[zz,xx]
    floor=np.ceil(ref.raw[zz,xx]).astype(np.int64)
    lo=np.maximum(lo,np.maximum(floor,ctx.params['world.y_min']))
    hi=np.minimum(hi,ctx.params['world.y_max'])
    if feature.habitat=='underwater': hi=np.minimum(hi,np.floor(ref.levels[zz,xx]).astype(np.int64))
    use&=hi>lo
    return xz[use].astype(np.int64),lo[use].astype(np.int64),hi[use].astype(np.int64),types[use].astype(np.uint16)


def _batches(pack,params,seed,r,resources,biome_ids=None,wet_mask=None):
    features=[f for f in pack.features if f.type=='column_field' and
              enabled(f,params)]
    ids=MappingProxyType({n:i for i,n in enumerate(pack.blocks)})
    values=SimpleNamespace(param=params.__getitem__)
    chunks=[];reports={}
    for f in features:
        density=bound(values,f.density)
        patch_scale=bound(values,f.patch_scale)
        max_slope=bound(values,f.max_slope)
        if not 0<=density<=1 or not np.isfinite((density,patch_scale,max_slope)).all() or patch_scale<=0 or max_slope<0:
            raise ValueError(f'{f.id}: invalid placement parameters')
        if not density or (f.habitat=='water_surface' and not water_displayed(pack,params)): continue
        report=reports.setdefault(f.id,dict(columns=0,cells=0,independent_candidates=0,continuous_columns=0,interval_bytes=0))
        # validate() requires each emitted column to be allowed in its output
        # biome. No matching output biome proves this recipe cannot add cells,
        # including shapes anchored outside the region; skip reference work.
        output_allowed=None
        if biome_ids is not None:
            output_allowed=np.isin(biome_ids,[i for i,b in enumerate(pack.biomes) if b.id in f.biomes])
            if wet_mask is not None: output_allowed &= wet_mask if f.habitat in ('underwater','water_surface') else ~wet_mask
            if not output_allowed.any(): continue
        for tile in r.tiles(256):
            check_cancel(getattr(resources,'cancel_event',None))
            if output_allowed is not None and not output_allowed[r.slices(tile)].any(): continue
            ref=reference_for(pack,params,seed,tile.expanded(f.radius),resources);c=ref.ctx
            allowed=np.isin(ref.biomes,[i for i,b in enumerate(pack.biomes) if b.id in f.biomes])
            material=np.full(c.shape,ids[pack.water['block']],np.uint16) if f.habitat=='water_surface' else ref.columns[:,:,0]
            allowed&=np.isin(material,[ids[n] for n in f.surface])
            if f.habitat=='water_surface':
                level=np.floor(ref.levels)
                allowed&=ref.wet & (level>=params['world.y_min'])&(level<params['world.y_max'])
            else: allowed&=ref.wet if f.habitat=='underwater' else ~ref.wet
            allowed&=c.get('slope')<=max_slope if f.habitat!='water_surface' else True
            if not allowed.any(): continue
            allowed.setflags(write=False)
            for a in (ref.raw,ref.height,ref.levels,ref.wet,ref.biomes,ref.columns): a.setflags(write=False)
            ctx=ColumnContext(seed,params,f,ids,tile,ref,allowed,density,patch_scale)
            batch=f.fn(ctx);chunk=validate(batch,f,ctx)
            chunks.append((f.id,chunk))
            report['columns']+=int(bool(len(chunk[0])))+int(np.any(chunk[0][1:]!=chunk[0][:-1],axis=1).sum())
            report['cells']+=int((chunk[2]-chunk[1]).sum())
            report['interval_bytes']+=sum(a.nbytes for a in chunk)
            for key in ('independent_candidates','continuous_columns'):
                value=batch.diagnostics.get(key,0)
                if not isinstance(value,(int,np.integer)) or value<0: raise ValueError(f'{f.id}: invalid diagnostic {key}')
                report[key]+=int(value)
    return chunks,reports


def query_occupied(pack,params,seed,region,points,resources):
    """Bounded neighbour queries reuse the same recipe and clipping semantics."""
    chunks,_=_batches(pack,params,seed,region,resources)
    found=np.zeros(len(points),bool)
    for _,chunk in chunks:
        if len(chunk[0]):
            index=ColumnIndex(region,params['world.y_min'],params['world.y_max'],*chunk[:3])
            found|=index.lookup(points)[0]
    return found


def apply_world(world, *, max_instances, cancel_event=None):
    features=[f for f in world.pack.features if f.type=='column_field' and
              enabled(f,world.params)]
    if not features: return world
    if not geometry.height_mode(world.pack):
        return replace(world,stats=dict(world.stats,feature_unsupported=tuple(sorted(set(world.stats.get('feature_unsupported',()))|{f.id for f in features}))))
    started=perf_counter();pack=world.pack;r=world.region;params=world.params
    ids={n:i for i,n in enumerate(pack.blocks)}
    resources=Resources(pack,params,world.spec.seed);resources.cancel_event=cancel_event
    chunks,reports=_batches(pack,params,world.spec.seed,r,resources,world.biome_ids,world.wet_mask)
    nonempty=[(name,chunk) for name,chunk in chunks if len(chunk[0])]
    if not nonempty:
        stats=dict(world.stats,column_features=reports)
        stats['stages']=dict(stats['stages'],column_features=perf_counter()-started)
        stats['seconds']+=perf_counter()-started
        return replace(world,stats=stats)
    xz,lo,hi,types=[np.concatenate([chunk[i] for _,chunk in nonempty]) for i in range(4)]
    owners=np.concatenate([np.full(len(chunk[0]),name) for name,chunk in nonempty])
    order=np.lexsort((lo,xz[:,0],xz[:,1]));xz,lo,hi,types=xz[order],lo[order],hi[order],types[order]
    owners=owners[order]
    if len(xz)>1 and np.any(np.all(xz[1:]==xz[:-1],axis=1)&(lo[1:]<hi[:-1])):
        raise ValueError('column features overlap; combine overlapping recipes in their generator')
    index=ColumnIndex(r,params['world.y_min'],params['world.y_max'],xz,lo,hi)
    points=world.arrays.xyz.astype(np.int64);points[:,0]+=r.x0;points[:,2]+=r.z0
    found,at=index.lookup(points)
    surface=np.array([b.shape=='surface' for b in world.arrays.block_defs])[world.arrays.types]
    decor=np.array([b.shape=='decor' for b in world.arrays.block_defs])[world.arrays.types]
    keep=~(found&(surface|decor))
    if getattr(world, 'soft_mask', None) is not None:
        from .features import remove_soft_plants
        world = remove_soft_plants(world, points[world.soft_mask & ~keep])
    index.removed=np.sort(at[found & keep])
    index.start=int(keep.sum())
    if index.start+index.count+len(world.model_instances)>max_instances: raise ValueError('column features exceed max_instances before expansion')
    check_cancel(cancel_event)
    lengths=hi-lo;columns=np.repeat(np.arange(len(xz)),lengths)
    y=np.arange(index.total)-np.repeat(index.starts,lengths)+lo[columns]
    added=np.column_stack((xz[columns,0]-r.x0,y,xz[columns,1]-r.z0)).astype(np.int32)
    added_types=types[columns]
    if world.model_index is not None:
        absolute=added.astype(np.int64);absolute[:,0]+=r.x0;absolute[:,2]+=r.z0
        blocked=world.model_index.occupied(absolute)
        index.removed=np.union1d(index.removed,np.flatnonzero(blocked))
    alive=np.empty(0,bool)
    if len(index.removed):
        alive=np.ones(index.total,bool);alive[index.removed]=False
        added,added_types=added[alive],added_types[alive]
    old_ids=np.array([ids[n] for n in world.arrays.names],np.uint16)[world.arrays.types]
    block_ids=np.r_[old_ids[keep],added_types];used=np.unique(block_ids)
    remap=np.zeros(len(pack.blocks),np.uint32);remap[used]=np.arange(len(used))
    names=tuple(pack.blocks[i] for i in used)
    offsets=None;rotations=None
    if world.arrays.instance_y_offsets is not None:
        offsets=np.r_[world.arrays.instance_y_offsets[keep],np.zeros(len(added))]
    if world.arrays.rotations is not None: rotations=np.r_[world.arrays.rotations[keep],np.zeros(len(added),np.uint8)]
    arrays=replace(world.arrays,xyz=np.r_[world.arrays.xyz[keep],added],types=remap[block_ids],names=names,
        block_defs=tuple(pack.block_defs[n] for n in names),
        y_offsets=tuple(world.arrays.y_offsets[world.arrays.names.index(n)] if world.arrays.y_offsets and n in world.arrays.names else 0. for n in names),
        instance_y_offsets=offsets,rotations=rotations)
    old_features=world.feature_cells
    old_count=0 if old_features is None else old_features.count
    kept_features=int(keep[len(keep)-old_count:].sum()) if old_count else 0
    start=arrays.count-kept_features-len(added)
    feature_cells=replace(arrays,xyz=arrays.xyz[start:],types=arrays.types[start:],solid_count=0,
        rotations=None if rotations is None else rotations[start:],
        instance_y_offsets=None if offsets is None else offsets[start:])
    soft_mask=getattr(world,'soft_mask',None)
    if soft_mask is not None:
        soft_mask=np.r_[soft_mask[keep],np.zeros(len(added),bool)]
        soft_mask.setflags(write=False)
    for a in (arrays.xyz,arrays.types,offsets,rotations,xz,lo,hi,types,index.removed):
        if a is not None: a.setflags(write=False)
    work_bytes=sum(a.nbytes for a in (points,found,at,surface,decor,keep,xz,lo,hi,types,columns,y,added,added_types,alive,block_ids,arrays.xyz,arrays.types))
    stats=dict(world.stats,visible=arrays.count,column_features=reports,
        column_replaced_decor=int((found & decor).sum()),
        feature_replaced_surface_cells=world.stats.get('feature_replaced_surface_cells',0)+int((found & surface).sum()),
        column_array_bytes=sum(a.nbytes for a in (added,added_types,xz,lo,hi,types)),column_work_array_bytes=work_bytes,feature_cells=feature_cells.count)
    by_id={k:dict(v,blocks=dict(v['blocks'])) for k,v in stats['feature_counts'].items()}
    remaining=hi-lo
    if len(index.removed):
        removed_segments=np.searchsorted(index.starts,index.removed,side='right')-1
        remaining=remaining-np.bincount(removed_segments,minlength=len(remaining))
    for name,report in reports.items():
        report['cells']=int(remaining[owners==name].sum())
        by_id[name]['cells']+=report['cells']
        for block in np.unique(types[owners==name]):
            n=pack.blocks[block];count=int(remaining[(owners==name)&(types==block)].sum())
            by_id[name]['blocks'][n]=by_id[name]['blocks'].get(n,0)+count
    from .feature_stats import aggregate
    stats.update(aggregate(pack,by_id))
    counts=np.bincount(feature_cells.types.astype(np.intp),minlength=len(names))
    stats['feature_block_counts']={n:int(c) for n,c in zip(names,counts) if c}
    stats['feature_added_instances']=feature_cells.count-stats['feature_removed_plants']
    stats['stages']=dict(stats['stages'],column_features=perf_counter()-started)
    stats['seconds']+=perf_counter()-started
    return replace(world,arrays=arrays,feature_cells=feature_cells,stats=stats,column_index=index,soft_mask=soft_mask)
