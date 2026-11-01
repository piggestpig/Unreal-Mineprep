"""Static rectangular detail/exclusion. Coordinates never depend on a camera."""
from dataclasses import dataclass
import numpy as np
from .data import Region

VERSION = 'fixed-core-3-water'


def intersection(a,b):
    if a is None or b is None:
        return None
    x,z = max(a.x0,b.x0),max(a.z0,b.z0)
    ex,ez = min(a.x0+a.width,b.x0+b.width),min(a.z0+a.depth,b.z0+b.depth)
    return Region(x,z,ex-x,ez-z) if x<ex and z<ez else None


def difference(region,cut):
    """Disjoint rectangles; their edges may cut through canonical coarse cells."""
    c = intersection(region,cut)
    if c is None: return (region,)
    parts = ((region.x0,region.z0,region.width,c.z0-region.z0),
             (region.x0,c.z0+c.depth,region.width,region.z0+region.depth-c.z0-c.depth),
             (region.x0,c.z0,c.x0-region.x0,c.depth),
             (c.x0+c.width,c.z0,region.x0+region.width-c.x0-c.width,c.depth))
    return tuple(Region(*p) for p in parts if p[2]>0 and p[3]>0)


@dataclass(frozen=True)
class Layout:
    core: object  # output intersection, or None; the Spec retains the original corners
    outer_step: int
    empty: bool = False

    def identity(self):
        return VERSION,self.core.to_list() if self.core is not None else None,self.outer_step,self.empty

    def inside(self,x,z):
        r = self.core
        if r is None:
            return np.zeros(np.broadcast_shapes(np.shape(x),np.shape(z)),bool)
        return (x>=r.x0)&(x<r.x0+r.width)&(z>=r.z0)&(z<r.z0+r.depth)

    def steps(self,x,z):
        return np.where(self.inside(x,z),0 if self.empty else 1,self.outer_step)

    def origins(self,x,z):
        """Density coordinates, before output-box clipping; both axes stay world aligned."""
        fine = self.inside(x,z) & (not self.empty)
        return np.where(fine,x,x//self.outer_step*self.outer_step),np.where(fine,z,z//self.outer_step*self.outer_step)

    def terrain(self,x,z):
        return ~self.inside(x,z) if self.empty else np.ones(np.broadcast_shapes(np.shape(x),np.shape(z)),bool)

    def anchors(self,detail_only,x,z):
        step = self.steps(x,z)
        return step==1 if detail_only else step!=0

    def tasks(self,region,size,radius):
        from .coarse import tiles
        for part in difference(region,self.core):
            for tile in tiles(part,size,self.outer_step): yield tile,self.outer_step
        core = intersection(region,self.core)
        if core is not None:
            parts = (core,)
            if self.empty and self.core.width>2*radius and self.core.depth>2*radius:
                inner = Region(self.core.x0+radius,self.core.z0+radius,self.core.width-2*radius,self.core.depth-2*radius)
                parts = difference(core,inner)
            for part in parts:
                for tile in tiles(part,size,self.outer_step if self.empty else 1):
                    yield tile,self.outer_step if self.empty else 1

    def box_origins(self,points,region):
        q = points.copy()
        for part in difference(region,self.core):
            use = ((points[:,0]>=part.x0)&(points[:,0]<part.x0+part.width)&
                   (points[:,2]>=part.z0)&(points[:,2]<part.z0+part.depth))
            q[use,0] = np.maximum(points[use,0]//self.outer_step*self.outer_step,part.x0)
            q[use,2] = np.maximum(points[use,2]//self.outer_step*self.outer_step,part.z0)
        return q


def validate(pack,params):
    from .coarse import capabilities
    if not capabilities(pack)['fixed_regions']:
        raise ValueError('Fixed core regions require a height or volume geometry recipe')


def column_tops(reference,tile,world,params,layout,step):
    """Analytic column bounds, including every physical neighbour at mixed seams."""
    from .coarse import axes
    x,z,lx,lz,w,d = axes(tile,step)
    c = reference.ctx
    ox,oz = int(c.x[0,0]),int(c.z[0,0])
    ymin = params['world.y_min']
    def tops(xx,zz):
        h = np.ceil(reference.height[zz-oz,xx-ox]).astype(np.int32)-1
        inside = ((xx>=world.x0)&(xx<world.x0+world.width)&(zz>=world.z0)&(zz<world.z0+world.depth))
        return np.where(inside & layout.terrain(xx,zz),h,ymin-1)
    top = tops(lx[None,:],lz[:,None])
    low_neighbor = np.full(top.shape,np.iinfo(np.int32).max,np.int32)
    for offset in range(step):
        for xx,zz,valid in ((lx[None,:]-1,lz[:,None]+offset,d[:,None]>offset),
                            (lx[None,:]+w,lz[:,None]+offset,d[:,None]>offset),
                            (lx[None,:]+offset,lz[:,None]-1,w[None,:]>offset),
                            (lx[None,:]+offset,lz[:,None]+d[:,None],w[None,:]>offset)):
            np.minimum(low_neighbor,np.where(valid,tops(xx,zz),np.iinfo(np.int32).max),out=low_neighbor)
    low = np.maximum(ymin,np.minimum(top,low_neighbor+1))
    return top,low


def shell(reference,tile,world,params,layout,step,max_instances):
    """Existing column shell with full physical edge queries at mixed seams."""
    from .coarse import axes
    from .shell import column_shell
    x,z,lx,lz,w,d = axes(tile,step)
    c = reference.ctx
    ox,oz = int(c.x[0,0]),int(c.z[0,0])
    ymin = params['world.y_min']
    top,low = column_tops(reference,tile,world,params,layout,step)
    counts = np.maximum(top-low+1,0).ravel().astype(np.int64)
    if counts.sum()>max_instances: raise ValueError('fixed core shell exceeds max_instances before allocation')
    soil = reference.soil_depth
    ix,iz = lx-ox,lz-oz
    if np.ndim(soil): soil = soil[iz[:,None],ix]
    padded = np.pad(top,1,constant_values=ymin-1)
    col,y,role = column_shell(padded,ymin,soil,counted=(top,low,counts))
    a,b = col//len(x),col%len(x)
    xyz = np.column_stack((lx[b]-world.x0,y,lz[a]-world.z0)).astype(np.int32)
    sizes = np.column_stack((w[b],np.ones(len(col),np.int32),d[a])).astype(np.int32)
    columns = reference.columns[iz[:,None],ix].reshape(-1,3)
    solid = int((np.maximum(top-ymin+1,0)*d[:,None]*w).sum())
    return xyz,columns[col,role],solid,sizes
