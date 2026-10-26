"""Bounded single-source verification and sparse approved geometry.

Surface reservoirs terminate the flood; unknown underground edges never do.
This module knows no cave recipe, hydrology planner or output crop.
"""
from dataclasses import dataclass
import numpy as np
from .cache import Memo
from .data import check_cancel

_cache=Memo(limit=512)


def clear_cache():
    _cache.clear()


def memo(key,build,resources):
    check_cancel(getattr(resources,'cancel_event',None))
    return _cache.get(key,build)


def count(resources,name,value=1):
    key='water_connection_'+name
    resources.report.add(key, value)


@dataclass(frozen=True)
class Connection:
    body: object
    origin: tuple             # Z,Y,X of the fixed verification window
    shape: tuple
    bounds: tuple             # XYZ half-open actual carve bounds
    starts: np.ndarray        # sorted linear wet-column intervals for carving
    ends: np.ndarray

    @property
    def nbytes(self):
        return self.body.xyz.nbytes+self.body.runs.nbytes+self.starts.nbytes+self.ends.nbytes

    @property
    def influence_bounds(self):
        r=self.body.runs;b=self.bounds
        return (min(b[0],int(r[:,0].min())),min(b[1],int(r[:,2].min())),min(b[2],int(r[:,1].min())),
                max(b[3],int(r[:,0].max())+1),max(b[4],int(r[:,3].max())),max(b[5],int(r[:,1].max())+1))

    def mask(self,x,y,z):
        z0,y0,x0=self.origin;nz,ny,nx=self.shape
        ix,iy,iz=np.broadcast_arrays(np.asarray(x,dtype=np.int64)-x0,
                                    np.asarray(y,dtype=np.int64)-y0,np.asarray(z,dtype=np.int64)-z0)
        valid=(ix>=0)&(ix<nx)&(iy>=0)&(iy<ny)&(iz>=0)&(iz<nz)
        code=(iz*nx+ix)*ny+iy
        index=np.searchsorted(self.starts,code,side='right')-1
        return valid&(index>=0)&(code<self.ends[np.maximum(index,0)])


def approved(body,carve,origin):
    from .fluids import compress_runs
    runs=compress_runs(carve,origin)
    z0,y0,x0=origin;nz,ny,nx=carve.shape
    starts=((runs[:,1].astype(np.int64)-z0)*nx+runs[:,0]-x0)*ny+runs[:,2]-y0
    ends=starts+runs[:,3]-runs[:,2]
    for a in (starts,ends):a.setflags(write=False)
    bounds=(int(runs[:,0].min()),int(runs[:,2].min()),int(runs[:,1].min()),
            int(runs[:,0].max())+1,int(runs[:,3].max()),int(runs[:,1].max())+1)
    return Connection(body,origin,carve.shape,bounds,starts,ends)


def verify(air,cutoff,seed,trusted,other,dry_surface,cancel=None):
    """Six-neighbor flood at/below the source's surface cell.

    trusted/other are known surface-water nodes. They are inspected but never
    traversed. Only underground unknown rims reject; no whole-reservoir flood.
    Return (component, reason), with a full-window component on success.
    """
    if any(n>64 for n in air.shape) or not 0<cutoff<=air.shape[1]:
        raise ValueError('connection verification is limited to 64 cubed')
    shape=(air.shape[0],cutoff,air.shape[2])
    if not all(0<=c<n for c,n in zip(seed,shape)):return None,'target_level'
    allowed=np.ascontiguousarray(air[:,:cutoff,:]&~trusted[:,:cutoff,:]).ravel()
    start=np.ravel_multi_index(seed,shape)
    if not allowed[start]:return None,'target_solid'
    seen=np.zeros(shape,bool);flat=seen.ravel()
    frontier=np.array([start],np.int64);flat[frontier]=True
    known=np.ascontiguousarray(trusted[:,:cutoff,:]).ravel()
    foreign=np.ascontiguousarray(other[:,:cutoff,:]).ravel()
    dry=np.ascontiguousarray(dry_surface[:,:cutoff,:]).ravel()
    contacted=False
    strides=(shape[1]*shape[2],shape[2],1)
    while frontier.size:
        check_cancel(cancel)
        z,y,x=np.unravel_index(frontier,shape)
        if foreign[frontier].any():return None,'other_source'
        if dry[frontier].any():return None,'dry_outlet'
        if np.any((z==0)|(z==shape[0]-1)|(x==0)|(x==shape[2]-1)|(y==0)):
            return None,'unknown_edge'
        neighbors=[]
        for c,n,stride in zip((z,y,x),shape,strides):
            neighbors.extend((frontier[c>0]-stride,frontier[c<n-1]+stride))
        candidates=np.unique(np.concatenate(neighbors))
        if foreign[candidates].any():return None,'other_source'
        contacted|=bool(known[candidates].any())
        frontier=candidates[allowed[candidates]&~flat[candidates]]
        flat[frontier]=True
    if not contacted:return None,'no_source'
    result=np.zeros_like(air);result[:,:cutoff,:]=seen
    return result,None
