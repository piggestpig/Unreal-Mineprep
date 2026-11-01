"""World-aligned horizontal sampling and boxes; vertical cells remain one block."""
from dataclasses import replace
import numpy as np
from .data import Region, require_int
from .shell import column_shell, shell_counts

VERSION = 'coarse-5-partial-surfaces'


def capabilities(pack):
    supported = pack.density is None or pack.density.base in ('height','volume')
    return dict(horizontal_steps=[1,2,4] if supported else [1], fixed_regions=supported)


def validate(pack, step):
    if step not in capabilities(pack)['horizontal_steps']:
        raise ValueError('cell_step is not supported by this geometry recipe')


def bind(pack, spec):
    if spec.core is None and spec.cell_step == 1:
        return pack
    pack.resolve(spec)
    if spec.core is not None:
        from .layout import Layout,intersection
        return replace(pack,cell_step=spec.cell_step,
                       layout=Layout(intersection(spec.region,spec.core_region),spec.cell_step,spec.core_empty))
    return replace(pack, cell_step=spec.cell_step, features=tuple(f for f in pack.features if not f.detail_only))


def aligned(region, step):
    x0, z0 = region.x0//step*step, region.z0//step*step
    x1 = -(-(region.x0+region.width)//step)*step
    z1 = -(-(region.z0+region.depth)//step)*step
    return Region(x0, z0, x1-x0, z1-z0)


def tiles(region, size, step):
    require_int('tile_size',size,1,4096)
    size = max(step, size//step*step)
    for tile in aligned(region, step).tiles(size):
        x0, z0 = max(tile.x0, region.x0), max(tile.z0, region.z0)
        x1, z1 = min(tile.x0+tile.width, region.x0+region.width), min(tile.z0+tile.depth, region.z0+region.depth)
        yield Region(x0, z0, x1-x0, z1-z0)


def axes(tile, step):
    r = aligned(tile, step)
    x = np.arange(r.x0, r.x0+r.width, step)
    z = np.arange(r.z0, r.z0+r.depth, step)
    lo_x, lo_z = np.maximum(x,tile.x0), np.maximum(z,tile.z0)
    widths = np.minimum(x+step,tile.x0+tile.width)-lo_x
    depths = np.minimum(z+step,tile.z0+tile.depth)-lo_z
    return x, z, lo_x, lo_z, widths, depths


def sizes(xyz, region, step, *, clip=None):
    """Actual clipped footprint of shell cells (Y remains one)."""
    p = xyz[:,[0,2]] + [region.x0,region.z0]
    clip = region if clip is None else clip
    end = np.minimum((p//step+1)*step,[clip.x0+clip.width,clip.z0+clip.depth])
    result = np.ones(xyz.shape,np.int32)
    result[:,[0,2]] = end-p
    return result


def shell(reference, tile, world_region, params, step, max_instances):
    x,z,lx,lz,widths,depths = axes(tile,step)
    c = reference.ctx
    xx = np.r_[x[0]-step,x,x[-1]+step]-int(c.x[0,0])
    zz = np.r_[z[0]-step,z,z[-1]+step]-int(c.z[0,0])
    # The reference halo spans at least one coarse cell.
    tops = np.ceil(reference.height[zz[:,None],xx]).astype(np.int32)-1
    ax,az = np.meshgrid(np.r_[x[0]-step,x,x[-1]+step],np.r_[z[0]-step,z,z[-1]+step])
    outside = ((ax+step<=world_region.x0)|(ax>=world_region.x0+world_region.width)|
               (az+step<=world_region.z0)|(az>=world_region.z0+world_region.depth))
    tops[outside] = params['world.y_min']-1
    soil = reference.soil_depth
    if np.ndim(soil):
        soil = soil[zz[1:-1,None],xx[1:-1]]
    counted = shell_counts(tops,params['world.y_min'])
    if counted[2].sum() > max_instances:
        raise ValueError('coarse shell exceeds max_instances before allocation')
    col,y,role = column_shell(tops,params['world.y_min'],soil,counted=counted)
    iz,ix = col//len(x),col%len(x)
    xyz = np.column_stack((lx[ix]-world_region.x0,y,lz[iz]-world_region.z0)).astype(np.int32)
    sizes = np.column_stack((widths[ix],np.ones(len(col),np.int32),depths[iz])).astype(np.int32)
    columns = reference.columns[zz[1:-1,None],xx[1:-1]].reshape(-1,3)
    solid = int((np.maximum(tops[1:-1,1:-1]-params['world.y_min']+1,0)*depths[:,None]*widths).sum())
    return xyz,columns[col,role],solid,sizes


def horizontal(mask, ys, tile, world_region, step):
    """Coarse horizontal cells; only a partially occluded cell expands to unit cells."""
    x,z,lx,lz,widths,depths = axes(tile,step)
    ix,iz = lx-tile.x0,lz-tile.z0
    counts = np.add.reduceat(np.add.reduceat(mask.astype(np.int32),iz,axis=0),ix,axis=1)
    full = counts == depths[:,None]*widths
    a,b = np.nonzero(full)
    xyz = np.column_stack((lx[b]-world_region.x0,ys[iz[a],ix[b]],lz[a]-world_region.z0)).astype(np.int32)
    sizes = np.column_stack((widths[b],np.ones(len(a),np.int32),depths[a])).astype(np.int32)
    partial = np.repeat(np.repeat((counts>0)&~full,depths,axis=0),widths,axis=1)
    a,b = np.nonzero(mask & partial)
    if len(a):
        xyz = np.r_[xyz,np.column_stack((b+tile.x0-world_region.x0,ys[a,b],a+tile.z0-world_region.z0)).astype(np.int32)]
        sizes = np.r_[sizes,np.ones((len(a),3),np.int32)]
    return xyz,sizes


def tops(points, sizes, use, region, y_min):
    """Rasterize only horizontal footprints, never a 3D occupancy volume."""
    result = np.full(region.cells,y_min-1,np.int64)
    p = points[use]
    if sizes is None:
        np.maximum.at(result,(p[:,2]-region.z0)*region.width+p[:,0]-region.x0,p[:,1])
    else:
        s = sizes[use]
        for dz in range(int(s[:,2].max(initial=0))):
            for dx in range(int(s[:,0].max(initial=0))):
                valid = (s[:,0]>dx)&(s[:,2]>dz)
                q = p[valid]
                np.maximum.at(result,(q[:,2]+dz-region.z0)*region.width+q[:,0]+dx-region.x0,q[:,1]+s[valid,1]-1)
    return result


def split_water(world, index):
    """Cut coarse water around fine column features without leaving square holes."""
    data = world.arrays
    candidates = np.flatnonzero(np.array([b.shape=='surface' for b in data.block_defs],bool)[data.types] &
                                ((data.sizes[:,0]>1)|(data.sizes[:,2]>1)))
    if not len(candidates):
        return world
    p,s = data.xyz[candidates],data.sizes[candidates]
    points,owners,hits = [],[],[]
    for dz in range(world.spec.cell_step):
        for dx in range(world.spec.cell_step):
            use = np.flatnonzero((s[:,0]>dx)&(s[:,2]>dz))
            q = p[use]+[dx,0,dz]
            hit,_ = index.lookup(q+[world.region.x0,0,world.region.z0])
            points.append(q);owners.append(use);hits.append(hit)
    points,owners,hits = np.concatenate(points),np.concatenate(owners),np.concatenate(hits)
    affected = np.zeros(len(candidates),bool)
    affected[owners[hits]] = True
    if not affected.any():
        return world
    use = affected[owners] & ~hits
    sources = candidates[owners[use]]
    keep = np.ones(data.count,bool);keep[candidates[affected]] = False
    arrays = replace(data,xyz=np.r_[points[use],data.xyz[keep]],types=np.r_[data.types[sources],data.types[keep]],
                     sizes=np.r_[np.ones((len(sources),3),np.int32),data.sizes[keep]],
                     rotations=None if data.rotations is None else np.r_[data.rotations[sources],data.rotations[keep]],
                     instance_y_offsets=None if data.instance_y_offsets is None else
                         np.r_[data.instance_y_offsets[sources],data.instance_y_offsets[keep]])
    soft = None if world.soft_mask is None else np.r_[world.soft_mask[sources],world.soft_mask[keep]]
    return replace(world,arrays=arrays,soft_mask=soft)
