"""Streaming, bounded orthographic diagnostics; never samples geometry."""
from dataclasses import dataclass
from time import perf_counter
import numpy as np


@dataclass(frozen=True)
class Projection:
    axis: str
    axes: tuple
    depth: np.ndarray
    rows: np.ndarray
    columns: np.ndarray
    offset: tuple = (0,0)
    steps: tuple = (1,1)
    kind: str = 'carved'


class Collector:
    def __init__(self, region, tile, params, kind='carved'):
        self.region,self.tile,self.kind = region,tile,kind
        self.origin = dict(x=region.x0,y=params['world.y_min'],z=region.z0)
        self.length = dict(x=region.width,y=params['world.y_max']-params['world.y_min'],z=region.depth)
        self.step = {a:max(1,(n+511)//512) for a,n in self.length.items()}
        self.maps={}
        for axis,axes in [('z',('y','x')),('y',('z','x')),('x',('y','z'))]:
            ranges=[]
            for a in axes:
                start,end = (self.origin[a],self.origin[a]+self.length[a]) if a=='y' else (
                    (tile.x0,tile.x0+tile.width) if a=='x' else (tile.z0,tile.z0+tile.depth))
                lo=(start-self.origin[a])//self.step[a]
                hi=(end-1-self.origin[a])//self.step[a]+1
                ranges.append((lo,hi))
            rows,cols=(self.origin[a]+np.arange(lo,hi)*self.step[a] for a,(lo,hi) in zip(axes,ranges))
            self.maps[axis]=Projection(axis,axes,np.full((len(rows),len(cols)),np.inf,np.float32),
                                       rows,cols,tuple(a for a,b in ranges),tuple(self.step[a] for a in axes),kind)
        self.cells=0; self.seconds=0.
        self.surface_parts = []
        self.surface_indices, self.shell_count = [], 0
        self.floor_halo = None  # optional support just below the crop; never a preview face

    def add_surfaces(self, xyz, types, upward):
        """Only real upward faces, using final shell materials and world-local X/Z."""
        if self.kind == 'solid' and upward.any():
            self.surface_parts.append(np.column_stack((xyz[upward], types[upward])).astype(np.int32))
            self.surface_indices.append(np.flatnonzero(upward) + self.shell_count)
        self.shell_count += len(xyz)

    def surfaces(self, types=None):
        result = (np.concatenate(self.surface_parts) if self.surface_parts else np.empty((0, 4), np.int32))
        if types is not None and self.surface_indices:
            # Terrain material overrides run after shell extraction.
            result[:, 3] = types[np.concatenate(self.surface_indices)]
        result.setflags(write=False)
        return result

    def add(self, solid, tops, sub, lo):
        started=perf_counter()
        ys=np.arange(lo,lo+solid.shape[1])[None,:,None]
        mask=solid if self.kind=='solid' else (~solid & (ys<=tops[:,None,:]))
        self.cells += int(mask.sum())
        reductions={'z':(mask.any(0),mask.argmax(0)+sub.z0-self.origin['z']),
                    'x':(mask.any(2).T,mask.argmax(2).T+sub.x0-self.origin['x']),
                    'y':(mask.any(1),self.origin['y']+self.length['y']-1-(lo+solid.shape[1]-1-mask[:,::-1,:].argmax(1)))}
        positions={'y':np.arange(lo,lo+solid.shape[1]),'x':np.arange(sub.x0,sub.x0+sub.width),
                   'z':np.arange(sub.z0,sub.z0+sub.depth)}
        for axis,(valid,depth) in reductions.items():
            image=self.maps[axis]
            a,b=image.axes
            r=(positions[a]-self.origin[a])//self.step[a]-image.offset[0]
            c=(positions[b]-self.origin[b])//self.step[b]-image.offset[1]
            rr,cc=np.nonzero(valid)
            np.minimum.at(image.depth,(r[rr],c[cc]),depth[rr,cc])
        self.seconds += perf_counter()-started

    def finish(self):
        for p in self.maps.values():
            for a in (p.depth,p.rows,p.columns): a.setflags(write=False)
        return self.maps


def merge(region,params,parts,kind='carved'):
    result=Collector(region,region,params,kind).maps
    for maps in parts:
        if not maps: continue
        for axis,p in maps.items():
            target=result[axis].depth
            r,c=p.offset; h,w=p.depth.shape
            np.minimum(target[r:r+h,c:c+w],p.depth,out=target[r:r+h,c:c+w])
    for p in result.values():
        for a in (p.depth,p.rows,p.columns): a.setflags(write=False)
    return result


def section(world,axis='y'):
    if axis not in ('x','y','z'): raise ValueError("projection axis must be 'x', 'y', or 'z'")
    maps=world.geometry_views
    if maps is None:
        maps=Collector(world.region,world.region,world.params).finish()
    p=maps[axis]
    mask=np.isfinite(p.depth); mask.setflags(write=False)
    return dict(mask=mask,depth=p.depth,axis=axis,axes=p.axes,rows=p.rows,columns=p.columns,
                steps=p.steps,kind=p.kind)
