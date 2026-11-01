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


def expand_surfaces(faces):
    """Expand only a caller's bounded surface window; columns 4/5 are X/Z spans."""
    if faces.shape[1] == 4:
        return faces
    area = faces[:,4]*faces[:,5]
    ids = np.repeat(np.arange(len(faces)),area)
    offsets = np.arange(len(ids))-np.repeat(np.cumsum(area)-area,area)
    result = faces[ids,:4].copy()
    result[:,0] += offsets % faces[ids,4]
    result[:,2] += offsets // faces[ids,4]
    return result


class Collector:
    def __init__(self, region, tile, params, kind='carved', cell_step=1,layout=None):
        self.region,self.tile,self.kind = region,tile,kind
        self.cell_step = cell_step
        self.layout = layout
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
            faces = np.column_stack((xyz[upward], types[upward])).astype(np.int32)
            if self.cell_step != 1 or self.layout is not None:
                from .coarse import sizes
                faces = np.column_stack((faces,sizes(xyz[upward],self.region,self.cell_step,clip=self.tile)[:,[0,2]]))
            self.surface_parts.append(faces)
            self.surface_indices.append(np.flatnonzero(upward) + self.shell_count)
        self.shell_count += len(xyz)

    def surfaces(self, types=None):
        result = (np.concatenate(self.surface_parts) if self.surface_parts else
                  np.empty((0,4 if self.cell_step==1 and self.layout is None else 6),np.int32))
        if types is not None and self.surface_indices:
            # Terrain material overrides run after shell extraction.
            result[:, 3] = types[np.concatenate(self.surface_indices)]
        result.setflags(write=False)
        return result

    def add(self, solid, tops, sub, lo, cell_step=1):
        started=perf_counter()
        ys=np.arange(lo,lo+solid.shape[1])[None,:,None]
        mask=solid if self.kind=='solid' else (~solid & (ys<=tops[:,None,:]))
        if self.layout is not None and self.layout.empty:
            from .coarse import axes
            _,_,xx,zz,_,_ = axes(sub,cell_step)
            mask &= self.layout.terrain(xx[None,None,:],zz[:,None,None])
        if cell_step == 1:
            xs,zs = np.arange(sub.x0,sub.x0+sub.width),np.arange(sub.z0,sub.z0+sub.depth)
            widths,depths = np.ones(len(xs),int),np.ones(len(zs),int)
            self.cells += int(mask.sum())
        else:
            from .coarse import axes
            _,_,xs,zs,widths,depths = axes(sub,cell_step)
            self.cells += int((mask.sum(axis=1)*depths[:,None]*widths).sum())
        reductions={'z':(mask.any(0),zs[mask.argmax(0)]-self.origin['z']),
                    'x':(mask.any(2).T,xs[mask.argmax(2).T]-self.origin['x']),
                    'y':(mask.any(1),self.origin['y']+self.length['y']-1-(lo+solid.shape[1]-1-mask[:,::-1,:].argmax(1)))}
        positions={'y':np.arange(lo,lo+solid.shape[1]),'x':xs,'z':zs}
        spans={'y':np.ones(solid.shape[1],int),'x':widths,'z':depths}
        for axis,(valid,depth) in reductions.items():
            image=self.maps[axis]
            a,b=image.axes
            rr,cc=np.nonzero(valid)
            for da in range(int(spans[a].max())):
                for db in range(int(spans[b].max())):
                    use=(spans[a][rr]>da)&(spans[b][cc]>db)
                    r=(positions[a][rr[use]]+da-self.origin[a])//self.step[a]-image.offset[0]
                    c=(positions[b][cc[use]]+db-self.origin[b])//self.step[b]-image.offset[1]
                    np.minimum.at(image.depth,(r,c),depth[rr[use],cc[use]])
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
