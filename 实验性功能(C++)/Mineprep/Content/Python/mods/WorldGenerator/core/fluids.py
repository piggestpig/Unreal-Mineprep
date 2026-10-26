"""Bounded static basins; world coordinates, sparse surfaces and vertical wet runs.

Air below a candidate level must be enclosed on X/Z and the window bottom.
The water-level plane is not a leakage boundary. Verification windows never
depend on the requested output crop; adjacent windows are separated by rock/dry
space because accepted wet components cannot touch their verification rim.
"""
from dataclasses import dataclass
import hashlib
from time import perf_counter
import numpy as np
from .cache import Memo
from .data import Region, check_cancel

_cache = Memo(limit=512)
MAX_WINDOW_CELLS = 128**3


@dataclass(frozen=True)
class StaticFluids:
    sampler: object
    block: str
    enabled_param: object = None
    requires: tuple = ()


@dataclass(frozen=True)
class FluidSource:
    kind: str
    id: int
    level: float


@dataclass(frozen=True)
class FluidBody:
    id: str
    level: float
    xyz: np.ndarray       # world XYZ surface cell origins
    runs: np.ndarray      # world X,Z,Y0,Y1; half-open conceptual wet volume
    source: object = None # FluidSource for approved surface-connected water


@dataclass(frozen=True)
class FluidLayers:
    xyz: np.ndarray
    levels: np.ndarray
    body_indices: np.ndarray
    bodies: tuple


def empty():
    arrays = [np.empty((0,3),np.int32), np.empty(0,np.float64), np.empty(0,np.uint32)]
    for a in arrays:a.setflags(write=False)
    return FluidLayers(*arrays,())


def enabled(pack, params):
    cfg = pack.fluids
    return (cfg is not None and (cfg.enabled_param is None or bool(params[cfg.enabled_param]))
            and all(bool(params[k]) for k in cfg.requires))


def clear_cache():
    _cache.clear()


def enclosed_component(air, level, seed, cancel=None):
    """NumPy frontier flood, air[Z,Y,X], integer local water-level boundary.

    Return None for a leaking component. No clipping may seal a candidate.
    Every horizontal and bottom face is checked, including routes around shelves.
    """
    if not 0 < level < air.shape[1]:return None
    shape = (air.shape[0],level,air.shape[2])
    if not (0<=seed[0]<shape[0] and 0<=seed[1]<shape[1] and 0<=seed[2]<shape[2]):return None
    allowed = np.ascontiguousarray(air[:,:level,:]).ravel()
    if not allowed[np.ravel_multi_index(seed,shape)]:return None
    seen=np.zeros(shape,bool);flat=seen.ravel()
    frontier=np.array([np.ravel_multi_index(seed,shape)],np.int64);flat[frontier]=True
    strides=(shape[1]*shape[2],shape[2],1)
    while frontier.size:
        check_cancel(cancel)
        z,y,x=np.unravel_index(frontier,shape)
        if np.any((z==0)|(z==shape[0]-1)|(x==0)|(x==shape[2]-1)|(y==0)):return None
        neighbors=[]
        for c,size,stride in zip((z,y,x),shape,strides):
            neighbors.extend((frontier[c>0]-stride,frontier[c<size-1]+stride))
        candidates=np.unique(np.concatenate(neighbors))
        frontier=candidates[allowed[candidates]&~flat[candidates]]
        flat[frontier]=True
    return seen


def body_from_component(component, air, origin, level, ident):
    """level is the water block origin; the flood may include that cell."""
    z0,y0,x0=origin
    z,x=np.nonzero(component[:,-1,:]&air[:,level,:])
    xyz=np.column_stack((x+x0,np.full(len(x),y0+level),z+z0)).astype(np.int32)
    runs=compress_runs(component,origin)
    xyz.setflags(write=False)
    return FluidBody(ident,float(y0+level),xyz,runs)


def compress_runs(component, origin):
    """Compact a bounded boolean [Z,Y,X] mask, never retain a voxel world."""
    z0,y0,x0=origin
    padded=np.pad(component,((0,0),(1,1),(0,0)))
    starts=np.argwhere(padded[:,1:]&~padded[:,:-1])
    ends=np.argwhere(~padded[:,1:]&padded[:,:-1])
    # np.argwhere orders by Z,Y,X; match endpoints by column then Y.
    a=np.lexsort((starts[:,1],starts[:,2],starts[:,0]));b=np.lexsort((ends[:,1],ends[:,2],ends[:,0]))
    starts,ends=starts[a],ends[b]
    runs=np.column_stack((starts[:,2]+x0,starts[:,0]+z0,starts[:,1]+y0,ends[:,1]+y0)).astype(np.int32)
    runs.setflags(write=False)
    return runs


def bodies_touch(a,b):
    """Six-neighbor wet-run intersection, including vertically adjacent runs."""
    columns={}
    for x,z,lo,hi in a.runs:columns.setdefault((int(x),int(z)),[]).append((lo,hi))
    for x,z,lo,hi in b.runs:
        for dx,dz in ((0,0),(1,0),(-1,0),(0,1),(0,-1)):
            for al,ah in columns.get((int(x)+dx,int(z)+dz),()):
                if max(lo,al)<min(hi,ah) or (dx==dz==0 and max(lo,al)==min(hi,ah)):return True
    return False


def layers(bodies, region, y_min, y_max):
    points=[];levels=[];indices=[];used=[]
    for body in sorted(bodies,key=lambda b:b.id):
        p=body.xyz
        keep=(p[:,0]>=region.x0)&(p[:,0]<region.x0+region.width)&(p[:,2]>=region.z0)&(p[:,2]<region.z0+region.depth)&(p[:,1]>=y_min)&(p[:,1]<y_max)
        runs=body.runs
        wet_inside=(runs[:,0]>=region.x0)&(runs[:,0]<region.x0+region.width)&(runs[:,1]>=region.z0)&(runs[:,1]<region.z0+region.depth)&(runs[:,2]<y_max)&(runs[:,3]>y_min)
        if not keep.any() and not wet_inside.any():continue
        points.append(p[keep]);levels.append(np.full(int(keep.sum()),body.level))
        indices.append(np.full(int(keep.sum()),len(used),np.uint32));used.append(body)
    if not points:return empty()
    result=FluidLayers(np.concatenate(points),np.concatenate(levels),np.concatenate(indices),tuple(used))
    _,first,inverse,counts=np.unique(result.xyz,axis=0,return_index=True,return_inverse=True,return_counts=True)
    if np.any(counts>1):
        for group in np.flatnonzero(counts>1):
            owners=result.body_indices[inverse==group]
            sources=[used[int(i)].source for i in owners]
            if sources[0] is None or any(s!=sources[0] for s in sources):
                raise ValueError('overlapping static fluid surfaces')
        first=np.sort(first)
        result=FluidLayers(result.xyz[first],result.levels[first],result.body_indices[first],tuple(used))
    for a in (result.xyz,result.levels,result.body_indices):a.setflags(write=False)
    return result


def combine(parts, region, params):
    bodies={}
    for part in parts:
        if part is not None:
            for b in part.bodies:
                if b.id in bodies and (b.level!=bodies[b.id].level or b.source!=bodies[b.id].source or not np.array_equal(b.xyz,bodies[b.id].xyz)
                                       or not np.array_equal(b.runs,bodies[b.id].runs)):
                    raise ValueError('inconsistent static fluid body across tiles')
                bodies[b.id]=b
    return layers(bodies.values(),region,params['world.y_min'],params['world.y_max'])


def occlude_surfaces(part, opaque_points, model_index=None):
    """Hide render planes claimed by structures; preserve conceptual wet runs."""
    if not len(part.xyz):
        return part, np.empty((0,3),np.int32)
    blocked = set(map(tuple, opaque_points))
    hit = np.fromiter((tuple(p) in blocked for p in part.xyz),bool,len(part.xyz))
    if model_index is not None:
        hit |= model_index.occupied(part.xyz)
    if not hit.any():
        return part, np.empty((0,3),np.int32)
    arrays = [a[~hit] for a in (part.xyz,part.levels,part.body_indices)]
    for a in arrays:
        a.setflags(write=False)
    return FluidLayers(*arrays,part.bodies), part.xyz[hit]


def sample_layers(pack, params, seed, region, resources):
    if not enabled(pack,params):return empty()
    check_cancel(getattr(resources,'cancel_event',None))
    bodies=pack.fluids.sampler(pack,params,seed,region,resources)
    if not isinstance(bodies,(tuple,list)):raise ValueError('fluid sampler must return FluidBody records')
    ids=set(); validated=[]; wet_columns={}
    for b in bodies:
        if not isinstance(b,FluidBody):raise ValueError('invalid static fluid body')
        if b.source is not None and (not isinstance(b.source,FluidSource) or b.source.kind not in ('lake','ocean')
                                    or type(b.source.id) is not int or b.source.level!=b.level):
            raise ValueError('invalid static fluid source')
        if (not isinstance(b.id,str) or not b.id or b.id in ids
                or not isinstance(b.level,(int,float,np.integer,np.floating)) or isinstance(b.level,(bool,np.bool_))
                or not np.isfinite(b.level) or not isinstance(b.xyz,np.ndarray) or b.xyz.ndim!=2 or b.xyz.shape[1]!=3
                or b.xyz.dtype.kind not in 'iu' or not isinstance(b.runs,np.ndarray) or b.runs.ndim!=2 or b.runs.shape[1]!=4
                or b.runs.dtype.kind not in 'iu' or np.any(b.runs[:,3]<=b.runs[:,2])
                or np.any(b.xyz[:,1]!=np.floor(b.level))):raise ValueError('invalid static fluid body')
        for array in (b.xyz,b.runs):
            if array.size and (array.min()<np.iinfo(np.int32).min or array.max()>np.iinfo(np.int32).max):
                raise ValueError('static fluid coordinates exceed int32')
        own={}
        for x,z,lo,hi in b.runs:
            x,z,lo,hi=map(int,(x,z,lo,hi))
            if hi>np.floor(b.level)+1:raise ValueError('wet run exceeds static fluid block')
            own.setdefault((x,z),[]).append((lo,hi))
        for x,y,z in b.xyz:
            if not any(lo<=y and hi in (y,y+1) for lo,hi in own.get((int(x),int(z)),())):
                raise ValueError('static fluid surface has no supporting wet run')
        for (x,z),intervals in own.items():
            for dx,dz in ((0,0),(1,0),(-1,0),(0,1),(0,-1)):
                for lo,hi in intervals:
                    for other_lo,other_hi,source in wet_columns.get((x+dx,z+dz),()):
                        if source is not None and source==b.source:continue
                        if max(lo,other_lo)<min(hi,other_hi) or (dx==dz==0 and max(lo,other_lo)==min(hi,other_hi)):
                            raise ValueError('separate static fluid bodies touch or overlap')
        for column,intervals in own.items():wet_columns.setdefault(column,[]).extend((lo,hi,b.source) for lo,hi in intervals)
        arrays=[]
        for array in (b.xyz,b.runs):
            frozen=array.copy() if array.flags.writeable else array
            frozen.setflags(write=False);arrays.append(frozen)
        validated.append(FluidBody(b.id,float(b.level),*arrays,b.source))
        ids.add(b.id)
    return layers(validated,region,params['world.y_min'],params['world.y_max'])


def section_mask(world,axis,at):
    """Exact conceptual wet-volume slice from sparse runs, without density calls."""
    r=world.region;p=world.params
    axes={'z':('y','x'),'x':('y','z'),'y':('z','x')}
    if axis not in axes:raise ValueError('invalid fluid section axis')
    limits=dict(x=(r.x0,r.width),z=(r.z0,r.depth),y=(p['world.y_min'],p['world.y_max']-p['world.y_min']))
    a,b=axes[axis];mask=np.zeros((limits[a][1],limits[b][1]),bool)
    if world.fluid_layers is None:return mask
    for body in world.fluid_layers.bodies:
        for x,z,y0,y1 in body.runs:
            if not (r.x0<=x<r.x0+r.width and r.z0<=z<r.z0+r.depth):continue
            if axis=='y':
                if y0<=at<y1:mask[z-r.z0,x-r.x0]=True
            elif (z if axis=='z' else x)==at:
                low=max(int(y0),p['world.y_min']);high=min(int(y1),p['world.y_max'])
                col=int(x-r.x0) if axis=='z' else int(z-r.z0)
                mask[low-p['world.y_min']:high-p['world.y_min'],col]=True
        for x,y,z in body.xyz:
            if not(r.x0<=x<r.x0+r.width and r.z0<=z<r.z0+r.depth and p['world.y_min']<=y<p['world.y_max']):continue
            if (z if axis=='z' else x if axis=='x' else y)!=at:continue
            row=int(z-r.z0) if axis=='y' else int(y-p['world.y_min'])
            col=int(x-r.x0) if axis!='x' else int(z-r.z0)
            mask[row,col]=True
    return mask


def basin_candidates(pack, params, seed, region, resources):
    """Vanilla recipe helper; one fixed window/anchor, at most two isolated pools."""
    from .geometry import sample, enabled as geometry_enabled
    from .water import generated as water_generated
    from .planning import SurfaceTiles
    cancel=getattr(resources,'cancel_event',None)
    if not water_generated(pack,params) or not geometry_enabled(pack,params):return ()
    size=params['groundwater.check_size'];spacing=max(128,size+32)
    radius=size//2
    key=resources.key('groundwater')
    out=[]
    def build(ax,az):
        raw=hashlib.sha256(f'closed-pools-1:{seed}:{ax}:{az}'.encode()).digest()
        rng=np.random.default_rng(int.from_bytes(raw[:8],'little'))
        if rng.random()>=params['groundwater.amount']:return ()
        sub=Region(ax*spacing+spacing//2-radius,az*spacing+spacing//2-radius,size,size)
        terrain=SurfaceTiles(resources);h=np.empty(sub.shape);wet=np.empty(sub.shape,bool)
        tiles=terrain.get_many((tx,tz) for tz in range(sub.z0//64,(sub.z0+size-1)//64+1)
                                     for tx in range(sub.x0//64,(sub.x0+size-1)//64+1))
        for (tx,tz),(hh,ww) in tiles.items():
            x0,x1=max(sub.x0,tx*64),min(sub.x0+size,(tx+1)*64)
            z0,z1=max(sub.z0,tz*64),min(sub.z0+size,(tz+1)*64)
            h[z0-sub.z0:z1-sub.z0,x0-sub.x0:x1-sub.x0]=hh[z0-tz*64:z1-tz*64,x0-tx*64:x1-tx*64]
            wet[z0-sub.z0:z1-sub.z0,x0-sub.x0:x1-sub.x0]=ww[z0-tz*64:z1-tz*64,x0-tx*64:x1-tx*64]
        if wet.all():return ()
        hi=min(params['world.y_max']-1,int(np.ceil(h.max()))-8)
        lo=max(params['world.y_min'],hi-128)
        if hi-lo<8:return ()
        shape=(size,hi-lo,size)
        if np.prod(shape)>MAX_WINDOW_CELLS:raise ValueError('static fluid verification window exceeds budget')
        solid=np.empty(shape,bool);x,z=sub.coordinates();tops=np.ceil(h).astype(np.int32)-1
        peak=solid.nbytes
        started=perf_counter()
        for y in range(lo,hi,32):
            check_cancel(cancel)
            yy=np.arange(y,min(y+32,hi),dtype=np.int32)[None,:,None]
            chunk,work=sample(pack,params,seed,x[:,None,:],yy,z[:,None,:],tops,resources=resources)
            solid[:,y-lo:y-lo+len(yy.ravel()),:]=chunk;peak=max(peak,work+solid.nbytes)
        resources.report.add('groundwater_sampling', perf_counter()-started)
        resources.report.add('groundwater_samples', solid.size)
        resources.report.peak('groundwater_work_bytes', peak)
        air=~solid
        floor=air[:,1:,:]&solid[:,:-1,:]
        floor &= (~wet[:,None,:]) & (np.arange(lo+1,hi)[None,:,None]+params['groundwater.depth']<h[:,None,:]-8)
        seeds=np.argwhere(floor);seeds[:,1]+=1
        if not len(seeds):return ()
        # Deterministic sample of actual floor cells, not output-crop-specific retries.
        seeds=seeds[rng.permutation(len(seeds))[:32]]
        occupied=np.zeros_like(air);bodies=[]
        started=perf_counter()
        for sz,sy,sx in seeds:
            check_cancel(cancel)
            if occupied[sz,sy,sx]:continue
            for depth in range(params['groundwater.depth'],0,-1):
                # Water is an ordinary cell with its native face just below the
                # cell top. Include that entire cell in conservative leak checks.
                level=int(sy)+depth-1
                boundary=level+1
                component=enclosed_component(air,boundary,(int(sz),int(sy),int(sx)),cancel)
                if component is None or np.any(occupied[:,:boundary,:]&component):continue
                surface=component[:,-1,:]&air[:,level,:]
                zz,xx=np.nonzero(surface)
                if len(xx)<12 or np.ptp(xx)+1>params['groundwater.span'] or np.ptp(zz)+1>params['groundwater.span']:continue
                if np.any(wet[zz,xx]) or np.any(lo+level>=h[zz,xx]-8):continue
                ident=hashlib.sha256(f'{key}:{ax}:{az}:{int(sz)}:{int(sy)}:{int(sx)}:{level}'.encode()).hexdigest()
                bodies.append(body_from_component(component,air,(sub.z0,lo,sub.x0),level,ident))
                occupied[:,:boundary,:]|=component
                break
            if len(bodies)==2:break
        resources.report.add('groundwater_connectivity', perf_counter()-started)
        resources.report.peak('groundwater_work_bytes', peak+air.nbytes*5)
        return tuple(bodies)
    for az in range((region.z0-radius-spacing//2)//spacing,(region.z0+region.depth+radius-spacing//2)//spacing+1):
        for ax in range((region.x0-radius-spacing//2)//spacing,(region.x0+region.width+radius-spacing//2)//spacing+1):
            check_cancel(cancel)
            # Only inspect anchors whose full canonical verification window intersects the crop.
            cx,cz=ax*spacing+spacing//2,az*spacing+spacing//2
            if cx+radius<=region.x0 or cx-radius>=region.x0+region.width or cz+radius<=region.z0 or cz-radius>=region.z0+region.depth:continue
            out.extend(_cache.get((key,ax,az),lambda:build(ax,az)))
            check_cancel(cancel)
    return tuple(out)
