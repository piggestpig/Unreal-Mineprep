"""Optional short lake/ocean mouths, validated against unmodified cave air.

Every anchor owns at most one proposal. A rejected proposal changes nothing.
The base probe explicitly samples cave_solid, never the connected final field.
"""
import hashlib
import math
from time import perf_counter
import numpy as np
from ...core import connections
from ...core.data import Region, check_cancel
from ...core.density import DensityContext
from ...core.fluids import FluidBody, FluidSource, compress_runs, enabled as fluids_enabled
from ...core.store import reference


def enabled(pack,p):
    return (p.get('groundwater.connect_surface',False) and p.get('groundwater.enabled',False)
            and fluids_enabled(pack,p)
            and p.get('groundwater.connection_amount',0)>0 and p.get('water.generate',True)
            and p.get('caves.enabled',False) and pack.density is not None
            and pack.density.field=='cave_connected_solid' and pack.density.wet_protection=='density')


def surface(pack,p,seed,r,res):
    ref=reference(pack,p,seed,r,res,include_surface=False)
    return ref.raw,ref.wet,ref.ctx.get('water_kind'),ref.ctx.get('water_body_id'),ref.ctx.get('water_level')


def probe(pack,p,seed,r,lo,hi,h,res):
    """Slabs bounded to 32 layers; no recursive final-density evaluation."""
    air=np.empty((r.depth,hi-lo,r.width),bool)
    xx=np.arange(r.x0,r.x0+r.width)[None,None,:]
    zz=np.arange(r.z0,r.z0+r.depth)[:,None,None]
    tops=np.ceil(np.clip(h,p['world.y_min'],p['world.y_max'])).astype(np.int32)-1
    peak=0;started=perf_counter()
    for y0 in range(lo,hi,32):
        check_cancel(getattr(res,'cancel_event',None))
        yy=np.arange(y0,min(y0+32,hi))[None,:,None]
        ctx=DensityContext(pack,p,seed,xx,yy,zz,tops=tops,resources=res)
        values=ctx.get('cave_solid')
        air[:,y0-lo:y0-lo+values.shape[1],:]=values<=0
        connections.count(res,'samples',values.size)
        peak=max(peak,ctx.work_bytes+air.nbytes)
    connections.count(res,'sampling_seconds',perf_counter()-started)
    res.water_connection_work_bytes=max(getattr(res,'water_connection_work_bytes',0),peak)
    return air


def candidate(pack,p,seed,res,mouth,source,ident):
    mx,my,mz=mouth
    r=Region(mx-32,mz-32,64,64)
    h,wet,kind,ids,levels=surface(pack,p,seed,r,res)
    plane=int(math.floor(source.level))
    hi=min(p['world.y_max'],plane+5)
    lo=max(p['world.y_min'],hi-64)
    if not lo+4<=my<hi or not lo<plane<hi:return None,'source_level'
    air=probe(pack,p,seed,r,lo,hi,h,res)
    xx=np.arange(r.x0,r.x0+64)[None,None,:]
    zz=np.arange(r.z0,r.z0+64)[:,None,None]
    yy=np.arange(lo,hi)[None,:,None]
    underground=(yy<np.ceil(h)[:,None,:])&(~wet[:,None,:])
    distance=(xx-mx)**2+(yy-my)**2+(zz-mz)**2
    possible=air&underground&(distance<=16**2)&(yy<=plane)&(yy>=p['world.y_min']+4)
    where=np.flatnonzero(possible)
    if not len(where):return None,'no_cave'
    target=np.unravel_index(where[np.argmin(np.broadcast_to(distance,air.shape).ravel()[where])],air.shape)
    tz,ty,tx=target
    end=(r.x0+tx,lo+ty,r.z0+tz)
    # Restrict existing wall-noise evaluation to the short connection box.
    bounds=tuple(max(a,b-4) for a,b in zip((r.x0,lo,r.z0),map(min,zip(mouth,end))))+tuple(
        min(a,b+5) for a,b in zip((r.x0+64,hi,r.z0+64),map(max,zip(mouth,end))))
    bx,by,bz,ex,ey,ez=bounds
    cx=np.arange(bx,ex)[None,None,:];cy=np.arange(by,ey)[None,:,None];cz=np.arange(bz,ez)[:,None,None]
    dx,dy,dz=np.subtract(end,mouth)
    t=np.clip(((cx-mx)*dx+(cy-my)*dy+(cz-mz)*dz)/max(dx*dx+dy*dy+dz*dz,1),0,1)
    d=np.sqrt((cx-mx-t*dx)**2+(cy-my-t*dy)**2+(cz-mz-t*dz)**2)
    ctx=DensityContext(pack,p,seed,cx,cy,cz,resources=res)
    detail=np.clip(ctx.get('cave_main'),-1,1)*p['caves.irregularity']*.7
    radius=np.maximum(2.5,3+detail)
    carve=np.zeros_like(air)
    window=np.s_[bz-r.z0:ez-r.z0,by-lo:ey-lo,bx-r.x0:ex-r.x0]
    carve[window]=(d<=radius)&(cy>=p['world.y_min']+4)&~air[window]
    if not carve.any():return None,'no_carve'
    proposed=air|carve
    surface_air=yy>=np.ceil(h)[:,None,:]
    own=wet&(kind==(1 if source.kind=='ocean' else 3))&(ids==source.id)&(levels==source.level)
    trusted=surface_air&own[:,None,:]
    other=surface_air&(wet&~own)[:,None,:]
    dry=surface_air&(~wet[:,None,:])
    started=perf_counter()
    component,reason=connections.verify(proposed,plane-lo+1,target,trusted,other,dry,
                                        getattr(res,'cancel_event',None))
    connections.count(res,'connectivity_seconds',perf_counter()-started)
    # Upper bound on live validation masks/frontier plus retained base sampling.
    res.water_connection_work_bytes=max(getattr(res,'water_connection_work_bytes',0),air.nbytes*20+ctx.work_bytes)
    if reason:return None,reason
    z,x=np.nonzero(component[:,plane-lo,:]&~wet)
    xyz=np.column_stack((x+r.x0,np.full(len(x),plane),z+r.z0)).astype(np.int32)
    xyz.setflags(write=False)
    body=FluidBody(ident,source.level,xyz,compress_runs(component,(r.z0,lo,r.x0)),source)
    return connections.approved(body,carve,(r.z0,lo,r.x0)),None


def query(pack,p,seed,region,res):
    if not enabled(pack,p):return ()
    key=res.key('water_connections/1')
    out=[]
    def build(ax,az):
        token=hashlib.sha256(f'{seed}:water-mouth:{ax}:{az}'.encode()).digest()
        rng=np.random.default_rng(int.from_bytes(token[:8],'little'))
        if rng.random()>=p['groundwater.connection_amount']:return None
        started=perf_counter()
        r=Region(ax*128-1,az*128-1,130,130)
        h,wet,kind,ids,levels=surface(pack,p,seed,r,res)
        shore=(wet[1:-1,1:-1]&((kind[1:-1,1:-1]==1)|(kind[1:-1,1:-1]==3))
               &(~wet[:-2,1:-1]|~wet[2:,1:-1]|~wet[1:-1,:-2]|~wet[1:-1,2:]))
        points=np.argwhere(shore)
        connections.count(res,'layout_seconds',perf_counter()-started)
        if not len(points):connections.count(res,'reject_no_shore');return None
        for index in rng.permutation(len(points))[:4]:
            check_cancel(getattr(res,'cancel_event',None))
            z,x=map(int,points[index]+1)
            mouth=(r.x0+x,int(math.ceil(h[z,x]))-1,r.z0+z)
            source=FluidSource('ocean' if kind[z,x]==1 else 'lake',int(ids[z,x]),float(levels[z,x]))
            ident=hashlib.sha256(f'{key}:{ax}:{az}:{x}:{z}'.encode()).hexdigest()
            connections.count(res,'candidates')
            entry,reason=candidate(pack,p,seed,res,mouth,source,ident)
            if entry is not None:
                connections.count(res,'accepted')
                return entry
            connections.count(res,'reject_'+reason)
        return None
    for az in range((region.z0-32)//128,(region.z0+region.depth+31)//128+1):
        for ax in range((region.x0-32)//128,(region.x0+region.width+31)//128+1):
            entry=connections.memo((key,ax,az),lambda:build(ax,az),res)
            if entry is not None:
                b=entry.influence_bounds
                if b[0]<region.x0+region.width and b[3]>region.x0 and b[2]<region.z0+region.depth and b[5]>region.z0:
                    # Independent base probes cannot approve two different
                    # reservoirs whose later carves may interact. Conservatively
                    # reject both when their verification windows overlap.
                    # Inspect raw neighboring proposals, never recursively query
                    # final density; symmetric rejection is crop/order invariant.
                    conflict=False
                    for nz in range(az-1,az+2):
                        for nx in range(ax-1,ax+2):
                            if (nx,nz)==(ax,az):continue
                            other=connections.memo((key,nx,nz),lambda:build(nx,nz),res)
                            if other is None or other.body.source==entry.body.source:continue
                            if all(a<n+size and n<a+length for a,length,n,size in
                                   zip(entry.origin,entry.shape,other.origin,other.shape)):
                                conflict=True;break
                        if conflict:break
                    if conflict:
                        connections.count(res,'reject_entry_conflict')
                        continue
                    out.append(entry)
    return tuple(out)
