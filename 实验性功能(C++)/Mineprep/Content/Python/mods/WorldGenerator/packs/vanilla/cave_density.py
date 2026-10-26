"""Continuous caves. Positive cavity is air; final positive density is rock.
Main composition happens on a 4x8x4 lattice. Fine operands interpolate
separately before their intersection. Guides add access to natural cavities.
"""
import numpy as np
from ...core.density import density, WindowFields
from ...core.planning import SurfaceTiles


def noise(ctx,salt,scale,planar=False):
    x,y,z=ctx.x+.5,ctx.y+.5,ctx.z+.5
    if planar: y=np.zeros((1,1,1))
    return ctx.noise('network/'+salt,scale,coords=(.8*x+.6*z,y,-.6*x+.8*z))*2.5


@density('cave_cheese')
def cheese(ctx):
    p=ctx.params; grand=p['caves.style']==1
    return noise(ctx,'grand' if grand else 'cheese',
                 (p['caves.chamber_width']*(2.1 if grand else 1.3),
                  p['caves.chamber_height']*(2.25 if grand else 1.5),
                  p['caves.chamber_depth']*(2.1 if grand else 1.3))).astype(np.float32)


@density('cave_a')
def band_a(ctx):
    r=ctx.param('caves.tunnel_radius')
    return noise(ctx,'band-a',(r*7,r*6,r*7)).astype(np.float32)


@density('cave_b')
def band_b(ctx):
    r=ctx.param('caves.tunnel_radius')
    return noise(ctx,'band-b',(r*8,r*7,r*6)).astype(np.float32)


@density('cave_layer',axes='xz',res=(4,8,4))
def layer(ctx):
    p=ctx.params
    return noise(ctx,'layer',(p['caves.chamber_width']*1.7,1,p['caves.chamber_depth']*1.7),True).astype(np.float32)


@density('cave_elevation',axes='xz',res=(4,8,4))
def elevation(ctx):
    return noise(ctx,'elevation',(96,1,96),True).astype(np.float32)


@density('cave_pillar',axes='xz',res=(4,8,4))
def pillars(ctx):
    return noise(ctx,'pillars',(13,1,13),True).astype(np.float32)


@density('cave_main',deps=('cave_cheese','cave_a','cave_b','cave_layer','cave_elevation'),res=(4,8,4))
def main(ctx,cheese,a,b,layer,elevation):
    p=ctx.params; grand=p['caves.style']==1; amount=p['caves.density']
    cavity=(cheese-(.48-.42*amount if grand else .58-.38*amount)+layer*p['caves.irregularity']*.1)*12
    width=(.22 if grand else .17)*(.45+amount)
    tubes=(width-np.maximum(np.abs(a),np.abs(b)))*20
    period=p['caves.chamber_height']*(2.25 if grand else 2.)
    level=ctx.y+.5-p['world.y_min']-p['caves.depth']-elevation*period*.6
    dy=np.abs((level+period*.5)%period-period*.5)
    layered=np.minimum((.22-np.abs(layer))*18,(4.5 if grand else 3.5)-dy)
    result=np.maximum(cavity,np.maximum(tubes,layered))
    strength=p['caves.pillars']*(.45 if grand else 1.)
    pillar=ctx.get('cave_pillar') if strength else 0.
    result=np.minimum(result,(.55-strength*3*np.maximum(pillar,0))*18)
    return np.broadcast_to(result,ctx.shape).astype(np.float32)


@density('cave_fine_a',res=(4,8,4))
def fine_a(ctx):
    return noise(ctx,'fine-a',(27,22,31)).astype(np.float32)


@density('cave_fine_b',res=(4,8,4))
def fine_b(ctx):
    return noise(ctx,'fine-b',(31,26,25)).astype(np.float32)


def surface(ctx):
    """Exact reference height and wet columns, also for scattered support."""
    if hasattr(ctx,'_surface_values'): return ctx._surface_values
    xx,zz=np.broadcast_arrays(ctx.x,ctx.z)
    ix,iz=np.floor(xx).astype(np.int64),np.floor(zz).astype(np.int64)
    tiles=SurfaceTiles(ctx.resources)
    keys=np.stack((ix.ravel()//64,iz.ravel()//64),axis=1)
    unique,inverse=np.unique(keys,axis=0,return_inverse=True)
    values=tiles.get_many(tuple(map(int,key)) for key in unique)
    h=np.empty(ix.size); wet=np.empty(ix.size,bool)
    for i,key in enumerate(unique):
        chosen=inverse==i; hh,ww=values[tuple(key)]
        x,z=ix.ravel()[chosen]%64,iz.ravel()[chosen]%64
        h[chosen]=hh[z,x]; wet[chosen]=ww[z,x]
    ctx._surface_values=h.reshape(xx.shape),wet.reshape(xx.shape)
    return ctx._surface_values


@density('cave_background')
def background(ctx):
    p=ctx.params
    if p['caves.density']==0: return np.full(ctx.shape,-10000.,np.float32)
    h,wet=surface(ctx)
    active=(~wet)&(ctx.y+.5<h-8)&(ctx.y+.5>p['world.y_min']+4)
    # Exact protection, not an eight-corner sign heuristic. Surface support and
    # complete protected slabs need no underground noise/interpolation at all.
    if not active.any(): return np.full(ctx.shape,-10000.,np.float32)
    result=ctx.get('cave_main')
    if p['caves.fine_passages']:
        a,b=ctx.get('cave_fine_a'),ctx.get('cave_fine_b')
        result=np.maximum(result,(.095-np.maximum(np.abs(a),np.abs(b)))*20)
    result=np.minimum(result,np.minimum(h-8-(ctx.y+.5),ctx.y+.5-p['world.y_min']-4))
    return np.where(wet,-10000.,result).astype(np.float32)


@density('cave_solid',resources=('caves',))
def solid(ctx):
    p=ctx.params
    result=ctx.get('cave_background').copy()
    plan=ctx.resource('caves')
    bounds=(float(ctx.x.min()),float(ctx.y.min()),float(ctx.z.min()),
            float(ctx.x.max())+1,float(ctx.y.max())+1,float(ctx.z.max())+1)
    cartesian=(ctx.x.ndim==ctx.y.ndim==ctx.z.ndim==3
               and ctx.x.shape[:2]==(1,1) and ctx.y.shape[::2]==(1,1) and ctx.z.shape[1:]==(1,1))
    if cartesian:
        ax,ay,az=ctx.x[0,0]+.5,ctx.y[0,:,0]+.5,ctx.z[:,0,0]+.5
    else:
        xyz=np.broadcast_arrays(ctx.x+.5,ctx.y+.5,ctx.z+.5)
    heights,wets=surface(ctx)
    heights,wets=np.broadcast_to(heights,ctx.shape),np.broadcast_to(wets,ctx.shape)
    selected=[]
    need_main='cave_main' not in ctx._memo and p['caves.irregularity']!=0
    windows={name:[] for name in ('cave_wall_a','cave_wall_b','cave_wall_layer',*(('cave_main',) if need_main else ()))}
    for item in plan.query(bounds):
        for index,obj in enumerate(item.primitives):
            if not all(obj.bounds[i]<=bounds[i+3] and obj.bounds[i+3]>=bounds[i] for i in range(3)):
                continue
            if cartesian:
                ix=np.flatnonzero((ax>=obj.bounds[0])&(ax<=obj.bounds[3]))
                iy=np.flatnonzero((ay>=obj.bounds[1])&(ay<=obj.bounds[4]))
                iz=np.flatnonzero((az>=obj.bounds[2])&(az<=obj.bounds[5]))
                if not (len(ix) and len(iy) and len(iz)):
                    continue
                target=((int(iz[0]),int(iz[-1])+1),(int(iy[0]),int(iy[-1])+1),(int(ix[0]),int(ix[-1])+1))
            else:
                mask=np.ones(ctx.shape,bool)
                for axis,coordinate in enumerate(xyz):
                    mask &= (coordinate>=obj.bounds[axis])&(coordinate<=obj.bounds[axis+3])
                if not mask.any():
                    continue
                positions=[np.flatnonzero(mask.any(axis=tuple(j for j in range(3) if j!=i))) for i in range(3)]
                target=tuple((int(a[0]),int(a[-1])+1) for a in positions)
            selected.append((index,item,obj,target))
            if obj.kind=='ravine':
                for name in ('cave_wall_a','cave_wall_b','cave_wall_layer'): windows[name].append(target)
            elif need_main:
                windows['cave_main'].append(target)
    fields=WindowFields(ctx,windows)
    for index,item,obj,target in selected:
        slices=tuple(slice(a,b) for a,b in target)
        x,y,z=(ax[None,None,slices[2]],ay[None,slices[1],None],az[slices[0],None,None]) if cartesian else (a[slices] for a in xyz)
        h,wet=heights[slices],wets[slices]
        dx,dy,dz=np.subtract(obj.b,obj.a)
        if obj.kind=='ravine': dy=0
        t=np.clip(((x-obj.a[0])*dx+(y-obj.a[1])*dy+(z-obj.a[2])*dz)/max(dx*dx+dy*dy+dz*dz,1e-12),0,1)
        radius=obj.radius[0]+t*(obj.radius[1]-obj.radius[0])
        if obj.kind=='tube':
            d2=(x-obj.a[0]-t*dx)**2+(y-obj.a[1]-t*dy)**2+(z-obj.a[2]-t*dz)**2
            distance=np.sqrt(d2)
            lower=(y<h-8)&(~wet)
            if lower.any() and p['caves.irregularity']!=0:
                main_slice=fields.get('cave_main',target) if need_main else ctx.get('cave_main')[slices]
                detail=np.where(lower,np.clip(main_slice,-1,1)*p['caves.irregularity']*.7,0)
            else:
                detail=0.
            cavity=np.maximum(radius+detail-distance,3.2-distance)
            if index<len(item.primitives)-2: cavity=np.minimum(cavity,h-8-y)
        else:
            a,b,layer=(fields.get(name,target) for name in ('cave_wall_a','cave_wall_b','cave_wall_layer'))
            side=(-(x-obj.a[0])*dz+(z-obj.a[2])*dx)/max(np.hypot(dx,dz),1e-12)
            raw=((x-obj.a[0])*dx+(z-obj.a[2])*dz)/max(dx*dx+dz*dz,1e-12)
            over=np.abs(raw-t)*np.hypot(dx,dz)
            taper=np.clip(1-over/np.maximum(radius*.4,1e-9),0,1)
            ir=p['caves.irregularity']
            left=radius*(.68+.16*ir*a+.12*ir*layer)*taper
            right=radius*(.68+.16*ir*b-.12*ir*layer)*taper
            offset=radius*.10*ir*layer
            floor=np.maximum(p['world.y_min']+4,obj.a[1]+t*(obj.b[1]-obj.a[1])+radius*.25*ir*b)
            cavity=np.minimum(np.minimum(left+side-offset,right-side+offset),np.minimum(y-floor,obj.bounds[4]-y))
            cavity=np.minimum(cavity,radius*.4-over)
        result[slices]=np.maximum(result[slices],cavity)
    y_full=(ctx.y+.5) if cartesian else xyz[1]
    result=np.where(wets,-10000.,np.minimum(result,y_full-p['world.y_min']-4))
    return np.minimum(np.broadcast_to(ctx.base_density,ctx.shape),-result).astype(np.float32)


def wall_noise(ctx,salt,scale):
    x,y,z=ctx.x+.5,ctx.y+.5,ctx.z+.5
    return ctx.noise(salt,scale,coords=(.8*x+.6*z,y,-.6*x+.8*z))


@density('cave_connected_solid',deps=('cave_solid',))
def connected_solid(ctx,base):
    from .water_connections import query, enabled
    from ...core.data import Region
    if not enabled(ctx.pack,ctx.params):return base
    x0,z0=int(ctx.x.min()),int(ctx.z.min())
    region=Region(x0,z0,int(ctx.x.max())-x0+1,int(ctx.z.max())-z0+1)
    result=None
    for entry in query(ctx.pack,ctx.params,ctx.seed,region,ctx.resources):
        if entry.bounds[1]>ctx.y.max() or entry.bounds[4]<=ctx.y.min():continue
        mask=entry.mask(ctx.x,ctx.y,ctx.z)
        if mask.any():
            if result is None:result=base.copy()
            result[mask]=-1.
    return base if result is None else result


@density('cave_wall_a',res=2)
def wall_a(ctx):
    return wall_noise(ctx,'cave/band-a',(13,11,13))


@density('cave_wall_b',res=2)
def wall_b(ctx):
    return wall_noise(ctx,'cave/band-b',(17,9,17))


@density('cave_wall_layer',res=4)
def wall_layer(ctx):
    return wall_noise(ctx,'cave/layers',(38,7,38))
