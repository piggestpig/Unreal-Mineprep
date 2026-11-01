"""Bounded 3D occupancy sampling and six-neighbour sparse shells.

Arrays are [Z,Y,X]; coordinates are integer MC cell origins. Samplers may use
cell centres (x/y/z + .5), but the height baseline uses y < height.
Only core cells are emitted. Output-region edges, including Y bounds, are air.
"""
from time import perf_counter
from dataclasses import replace

import numpy as np

from .data import Region, check_cancel, require_int
from . import materials as wall_materials

GEOMETRY_TILE = 128
SLAB_HEIGHT = 32
MAX_SECTION_CELLS = 4_194_304
CORE_SIZE = 32
_UNSET = object()


def enabled(pack, params):
    if pack.density is not None:
        gate = pack.density.enabled_param
        return pack.density.base == 'volume' or gate is None or bool(params[gate])
    return False


def height_mode(pack):
    return pack.density is None or pack.density.base == 'height'


def density_values(pack, params, seed, x, y, z, tops, *, resources=None, field=None, solid=False):
    """Continuous recipe values or the height base when its recipe is disabled."""
    from .density import DensityContext
    if resources is None:
        from .planning import Resources
        resources = Resources(pack, params, seed)
    if pack.layout is not None:
        return _mixed_values(pack,params,seed,x,y,z,tops,resources,field,solid)
    step = pack.cell_step
    expand = None
    if step != 1:
        x,z = x//step*step,z//step*step
        if x.shape[1] == z.shape[1] == 1 and (x.shape[2] > 1 or z.shape[2] > 1):
            if x.shape[0] != 1 and np.array_equal(x,np.broadcast_to(x[:1],x.shape)): x = x[:1]
            if z.shape[2] != 1 and np.array_equal(z,np.broadcast_to(z[:,:,:1],z.shape)): z = z[:,:,:1]
        # Regular windows evaluate each coarse cell once. Water validation only
        # expands the resulting boolean mask, never a fine 3D density volume.
        if x.shape[:2] == (1,1) and z.shape[1:] == (1,1):
            ux,ix,rx = np.unique(x,return_index=True,return_inverse=True)
            uz,iz,rz = np.unique(z,return_index=True,return_inverse=True)
            if len(ux) != x.size or len(uz) != z.size:
                x,z = ux[None,None,:],uz[:,None,None]
                if y.shape[0] != 1: y = y[iz]
                if y.shape[2] != 1: y = y[:,:,ix]
                if tops is not None:
                    if tops.shape[0] != 1: tops = tops[iz]
                    if tops.shape[1] != 1: tops = tops[:,ix]
                expand = rz,rx
    ctx = DensityContext(pack, params, seed, x, y, z, tops=tops, resources=resources)
    if not enabled(pack, params):
        values = np.broadcast_to(ctx.base_density, ctx.shape).astype(np.float32)
    else:
        values = ctx.get(field or pack.density.field)
    resources.report.add('density_samples', ctx.evaluated)
    resources.report.add('density_queries', values.size)
    for name,value in ctx.timings.items():
        attr='density_'+name
        resources.report.add(attr, value)
    resources.report.add('density_interpolations', ctx.interpolations)
    for name, value in ctx.counters.items():
        attr = 'density_' + name
        resources.report.add(attr, value)
    working = ctx.work_bytes + values.nbytes
    if solid:
        values = (values > 0) & (y >= params['world.y_min']) & (y < params['world.y_max'])
    if expand is not None:
        values = values[expand[0]][:,:,expand[1]]
    return values, working + (values.nbytes if solid or expand is not None else 0)


def _mixed_values(pack,params,seed,x,y,z,tops,resources,field,solid):
    """Coarse raw samples plus a fine rectangle; irregular support probes stay bounded."""
    from .density import DensityContext
    layout = pack.layout
    node = pack.densities[field or pack.density.field] if enabled(pack,params) else None
    # Occupancy-dependent nodes map their base first, then operate on physical
    # query coordinates. Their plans must never be built by a raw coarse/fine pack.
    after_mapping = node is not None and getattr(node.fn,'_after_mapping',False)
    if after_mapping: field = node.deps[0]
    fine = layout.inside(x,z) & (not layout.empty)
    raw = replace(pack,layout=None,cell_step=layout.outer_step)
    if fine.all():
        values,working = density_values(replace(raw,cell_step=1),params,seed,x,y,z,tops,
                                       resources=resources,field=field)
    else:
        values,working = density_values(raw,params,seed,x,y,z,tops,resources=resources,field=field)
    if fine.any() and not fine.all():
        values = values.copy()
        if x.shape[:2] == (1,1) and z.shape[1:] == (1,1):
            ix = np.flatnonzero(fine.any(axis=(0,1)))
            iz = np.flatnonzero(fine.any(axis=(1,2)))
            yy = y[iz] if y.shape[0] != 1 else y
            if yy.shape[2] != 1: yy = yy[:,:,ix]
            tt = None if tops is None else np.broadcast_to(tops,values.shape[::2])[np.ix_(iz,ix)]
            patch,work = density_values(replace(raw,cell_step=1),params,seed,x[:,:,ix],yy,z[iz],tt,
                                       resources=resources,field=field)
            values[np.ix_(iz,np.arange(values.shape[1]),ix)] = patch
        else:
            xx,zz = np.broadcast_arrays(x,z)
            iz,ix = np.nonzero(fine[:,0,:])
            yy = np.broadcast_to(y,values.shape)[iz,:,ix][:,:,None]
            tt = None if tops is None else np.broadcast_to(tops,values.shape[::2])[iz,ix][:,None]
            patch,work = density_values(replace(raw,cell_step=1),params,seed,
                xx[iz,0,ix][:,None,None],yy,zz[iz,0,ix][:,None,None],tt,resources=resources,field=field)
            values[iz,:,ix] = patch[:,:,0]
        working += work + values.nbytes
    if after_mapping:
        ctx = DensityContext(pack,params,seed,x,y,z,tops=tops,resources=resources)
        values = node.fn(ctx,values)
        working += values.nbytes
    if layout.empty:
        values = np.where(layout.terrain(x,z),values,-1.).astype(np.float32)
    if solid:
        values = (values>0) & (y>=params['world.y_min']) & (y<params['world.y_max'])
    return values,working+values.nbytes


def sample(pack, params, seed, x, y, z, tops, *, resources=None, field=None):
    """Sample uncut world geometry; output-boundary clipping is a caller concern."""
    if pack.density is not None and enabled(pack, params):
        return density_values(pack, params, seed, x, y, z, tops, resources=resources,field=field,solid=True)
    base = np.broadcast_to((y <= tops[:, None, :]) & (y >= params['world.y_min'])
                           & (y < params['world.y_max']), np.broadcast_shapes(x.shape, y.shape, z.shape)).copy()
    if pack.layout is not None: base &= pack.layout.terrain(x,z)
    return base, base.nbytes


def _shell_sample(pack, params, seed, x, y, z, tops, resources, depth, cache=None, floor_halo=False):
    if not depth:
        occupied, working = sample(pack, params, seed, x, y, z, tops, resources=resources)
        return occupied, working, None
    # Sample physical density before the output-height mask. Extra Y values
    # only support local material depth; the emitted slab remains unchanged.
    extended = np.arange(int(y.min()) - depth + 1 - int(floor_halo), int(y.max()) + depth, dtype=np.int32)[None,:,None]
    previous = cache.get('tail') if cache is not None else None
    reuse = previous is not None and previous[0] == int(extended[0,0,0])
    query = extended[:,previous[1].shape[1]:,:] if reuse else extended
    values, working = density_values(pack, params, seed, x, query, z, tops, resources=resources)
    natural = np.concatenate((previous[1],values > 0),axis=1) if reuse else values > 0
    tail_bytes = 0
    if cache is not None:
        tail = natural[:,-2*depth:,:].copy()
        cache['tail'] = (int(extended[0,-1,0])+1-tail.shape[1],tail)
        tail_bytes = tail.nbytes
    begin = depth - 1 + int(floor_halo)
    strip = natural[:,begin:begin+y.shape[1],:]
    occupied = strip & (y >= params['world.y_min']) & (y < params['world.y_max'])
    return occupied, working + natural.nbytes + occupied.nbytes + tail_bytes, natural


def _axes(tile, step, layout=None):
    from .coarse import axes
    x,z,lx,lz,w,d = axes(tile,step)
    if layout is not None:
        return (np.r_[tile.x0-1,lx,tile.x0+tile.width][None,:],
                np.r_[tile.z0-1,lz,tile.z0+tile.depth][:,None],lx,lz,d[:,None]*w)
    return (np.r_[x[0]-step,x,x[-1]+step][None,:],
            np.r_[z[0]-step,z,z[-1]+step][:,None],lx,lz,d[:,None]*w)


def _visible(occupied):
    """Six neighbours on the sampling grid, shared by slabs and local blocks."""
    visible = occupied[:-2,1:-1,1:-1].copy()
    visible &= occupied[2:,1:-1,1:-1]
    visible &= occupied[1:-1,:-2,1:-1]
    visible &= occupied[1:-1,2:,1:-1]
    visible &= occupied[1:-1,1:-1,:-2]
    visible &= occupied[1:-1,1:-1,2:]
    np.logical_not(visible,out=visible)
    visible &= occupied[1:-1,1:-1,1:-1]
    return visible


def _seam_neighbors(occupied,pack,params,seed,tile,y,resources):
    """A coarse face is hidden only when its whole physical neighbour is solid."""
    if pack.layout is None or pack.cell_step==1:
        return occupied
    from .layout import intersection
    if intersection(tile.expanded(1),pack.layout.core) is None:
        return occupied
    from .coarse import axes
    _,_,x,z,w,d = axes(tile,pack.cell_step)
    occupied = occupied.copy()
    for axis,edges,along,origin,length in ((0,(tile.x0-1,tile.x0+tile.width),z,tile.z0,tile.depth),
                                          (2,(tile.z0-1,tile.z0+tile.depth),x,tile.x0,tile.width)):
        for side,edge in zip((0,-1),edges):
            neighbor = Region(edge,origin,1,length) if axis==0 else Region(origin,edge,length,1)
            if intersection(neighbor,pack.layout.core) is None:
                continue
            line = np.arange(origin,origin+length)
            xx,zz = (np.array([[[edge]]]),line[:,None,None]) if axis==0 else (line[None,None,:],np.array([[[edge]]]))
            rock,_ = density_values(pack,params,seed,xx,y,zz,None,resources=resources,solid=True)
            full = np.logical_and.reduceat(rock[:,:,0] if axis==0 else rock[0].T,along-origin,axis=0)
            if axis==0: occupied[1:-1,:,side] = full
            else: occupied[side,:,1:-1] = full.T
    return occupied


def _full_shell(pack, params, seed, tile, region, tops, columns, *, max_instances,
          wet=None, slab_height=SLAB_HEIGHT, cancel_event=None, resources=None, projection=None, biomes=None,
          reference_tops=None,soil_depth=None):
    """Extract bounded slabs; materials follow the original column depth."""
    require_int('slab_height', slab_height, 1, SLAB_HEIGHT)
    from .shell import layer_roles
    if soil_depth is None: soil_depth=params['surface.soil_depth']
    if tile.width > GEOMETRY_TILE or tile.depth > GEOMETRY_TILE:
        raise ValueError('3D geometry tiles must be at most 128 by 128')
    step = pack.cell_step
    xx,zz,lx,lz,area = _axes(tile,step,pack.layout)
    x, z = xx[:, None, :], zz[:, None, :]
    inside = ((x+step > region.x0) & (x < region.x0 + region.width)
              & (z+step > region.z0) & (z < region.z0 + region.depth))
    if pack.layout is not None:
        inside = (x>=region.x0)&(x<region.x0+region.width)&(z>=region.z0)&(z<region.z0+region.depth)
    y_min, y_max = params['world.y_min'], params['world.y_max']
    points, materials = [], []
    count, solid_count = 0, 0
    stats = dict(geometry_slabs=0, geometry_voxels=0, geometry_work_array_bytes=0)
    seconds = dict(geometry_sampling=0., geometry_culling=0., geometry_materials=0.)
    material_on = wall_materials.active(pack, params)
    depth_limit = wall_materials.surface_depth(pack, params)
    from .floor_scatter import active, lower_supports
    collect_floor = not height_mode(pack) and bool(active(pack, params))
    sample_depth = max(depth_limit, 1) if collect_floor else depth_limit
    reference_tops = tops if reference_tops is None else reference_tops
    slab_cache = {}
    for lo in range(y_min, y_max, slab_height):
        check_cancel(cancel_event)
        hi = min(lo + slab_height, y_max)
        y = np.arange(lo - 1, hi + 1, dtype=np.int32)[None, :, None]
        start = perf_counter()
        floor_halo = collect_floor and lo == y_min
        occupied, working, natural = _shell_sample(pack, params, seed, x, y, z, tops, resources,
                                                   sample_depth, slab_cache, floor_halo)
        if floor_halo and projection is not None:
            projection.floor_halo = lower_supports(pack, params, seed, natural, sample_depth, tile, region,
                reference_tops, columns, biomes, resources, soil_depth)
        # Legacy/custom recipes protect wet beds here. Opt-in density recipes
        # own that protection and may admit only validated water-bottom mouths.
        if (height_mode(pack) and wet is not None and wet.any()
                and (pack.density is None or pack.density.wet_protection == 'shell')):
            occupied |= wet[:, None, :] & (y <= tops[:, None, :]) & (y >= y_min) & (y < y_max)
        occupied = _seam_neighbors(occupied,pack,params,seed,tile,y,resources)
        raw_occupied = occupied
        if material_on:
            occupied = occupied & inside
        else:
            occupied &= inside
        seconds['geometry_sampling'] += perf_counter() - start
        start = perf_counter()
        core = occupied[1:-1, 1:-1, 1:-1]
        if projection is not None:
            projection.add(core,tops[1:-1,1:-1],tile,lo,step)
        solid_count += int(core.sum()) if step == 1 else int((core.sum(axis=1)*area).sum())
        hidden = _visible(occupied)
        n = int(hidden.sum())
        if count + n > max_instances:
            raise ValueError(f'visible cells exceed max_instances={max_instances:,} before sparse allocation')
        iz, iy, ix = np.nonzero(hidden)
        xyz = np.empty((n, 3), np.int32)
        xyz[:, 0] = lx[ix] - region.x0
        xyz[:, 1] = iy + lo
        xyz[:, 2] = lz[iz] - region.z0
        material_start = perf_counter()
        depth = tops[1:-1, 1:-1][iz, ix] - xyz[:, 1]
        role = layer_roles(depth,soil_depth if np.ndim(soil_depth)==0 else soil_depth[iz,ix])
        points.append(xyz)
        types = columns[iz, ix, role]
        if material_on:
            exposed, carved = wall_materials.faces(raw_occupied, reference_tops, y, (iz,iy,ix), params, height_mode=height_mode(pack))
            coords = xyz.astype(np.int64)
            coords[:,0] += region.x0
            coords[:,2] += region.z0
            if step != 1: coords[:,[0,2]] = coords[:,[0,2]]//step*step
            ids = biomes[iz,ix] if biomes is not None else np.zeros(n,np.uint16)
            burial = reference_tops[1:-1,1:-1][iz,ix] - xyz[:,1]
            nearby = (wall_materials.depths(natural, (iz+1, iy+sample_depth+int(floor_halo), ix+1), depth_limit)
                      if depth_limit else None)
            types = wall_materials.apply(pack,params,seed,coords,types,burial,exposed,carved,ids,resources,
                                        natural_depths=nearby)
        materials.append(types)
        if projection is not None and not height_mode(pack):
            upward = ~occupied[iz + 1, iy + 2, ix + 1] & (xyz[:, 1] + 1 < y_max)
            projection.add_surfaces(xyz, types, upward)
        material_seconds = perf_counter() - material_start
        seconds['geometry_materials'] += material_seconds
        count += n
        seconds['geometry_culling'] += perf_counter() - start - material_seconds
        stats['geometry_slabs'] += 1
        stats['geometry_voxels'] += core.size
        stats['geometry_work_array_bytes'] = max(stats['geometry_work_array_bytes'], working + hidden.nbytes
                                               + (occupied.nbytes if material_on else 0))
        # Explicitly release slab buffers before sampling the next one.
        del occupied, raw_occupied, natural, core, hidden, iz, iy, ix
    return (np.concatenate(points), np.concatenate(materials), solid_count, seconds, stats)


def plan_bounds(pack, params, seed, region, resources):
    """Validate optional half-open XYZ change boxes. None means unknown."""
    if not enabled(pack, params):
        return ()
    bounds_fn = pack.density.bounds if pack.density is not None else None
    if bounds_fn is None:
        return None
    if resources is None:
        from .planning import Resources
        resources = Resources(pack, params, seed)
    step = pack.cell_step if pack.layout is None else pack.layout.outer_step
    if step != 1:
        from .coarse import aligned
        region = aligned(region,step)
    boxes = bounds_fn(pack, params, seed, region, resources)
    if boxes is None:
        return None
    if not isinstance(boxes, tuple):
        raise ValueError('density bounds must return None or a tuple of integer XYZ boxes')
    for box in boxes:
        if (not isinstance(box, tuple) or len(box) != 6 or any(type(v) is not int for v in box)
                or any(box[i] >= box[i + 3] for i in range(3))):
            raise ValueError('density bounds boxes must be nonempty integer half-open XYZ tuples')
    if step != 1:
        # Queries at any point inside a coarse cell see its sampled origin.
        # Feature support/clearance must include that entire changed footprint.
        boxes = tuple((a//step*step,b,c//step*step,-(-d//step)*step,e,-(-f//step)*step)
                      for a,b,c,d,e,f in boxes)
    return boxes


def shell(pack, params, seed, tile, region, tops, columns, *, max_instances,
          wet=None, slab_height=SLAB_HEIGHT, cancel_event=None, resources=None, bounds=_UNSET, projection=None, biomes=None,
          reference_tops=None,soil_depth=None,background=None):
    """Analytic background plus disjoint world-aligned 32-cube replacements.

    Budget counts only the final shell. Baseline solid counts are corrected by
    each replacement; horizontal and vertical crop faces remain sealed.
    """
    require_int('slab_height', slab_height, 1, SLAB_HEIGHT)
    step = pack.cell_step
    if bounds is _UNSET:
        bounds = plan_bounds(pack, params, seed, tile.expanded(step), resources)
    if bounds is None:
        return _full_shell(pack, params, seed, tile, region, tops, columns,
                           max_instances=max_instances, wet=wet, slab_height=slab_height,
                           cancel_event=cancel_event, resources=resources, projection=projection, biomes=biomes,
                           reference_tops=reference_tops,soil_depth=soil_depth)
    from .shell import shell_counts,layer_roles
    if soil_depth is None: soil_depth=params['surface.soil_depth']
    depth_limits=soil_depth if np.ndim(soil_depth)==0 else soil_depth.ravel()
    if tile.width > GEOMETRY_TILE or tile.depth > GEOMETRY_TILE:
        raise ValueError('3D geometry tiles must be at most 128 by 128')
    y_min, y_max = params['world.y_min'], params['world.y_max']
    started = perf_counter()
    active = set()
    # Expansion protects unchanged cells whose neighbour was changed.
    for box in bounds:
        low = (max(box[0] - step, tile.x0), max(box[1] - 1, y_min), max(box[2] - step, tile.z0))
        high = (min(box[3] + step, tile.x0 + tile.width), min(box[4] + 1, y_max), min(box[5] + step, tile.z0 + tile.depth))
        if any(a >= b for a, b in zip(low, high)):
            continue
        for bz in range(low[2] // CORE_SIZE, (high[2] - 1) // CORE_SIZE + 1):
            for by in range(low[1] // slab_height, (high[1] - 1) // slab_height + 1):
                for bx in range(low[0] // CORE_SIZE, (high[0] - 1) // CORE_SIZE + 1):
                    active.add((bx, by, bz))
    xx,zz,lx,lz,area = _axes(tile,step,pack.layout)
    shape = len(lz),len(lx)
    cells = len(lz)*len(lx)
    outside = ((xx+step <= region.x0) | (xx >= region.x0 + region.width)
               | (zz+step <= region.z0) | (zz >= region.z0 + region.depth))
    clipped = tops.copy()
    clipped[outside] = y_min - 1
    if pack.layout is not None:
        clipped[~np.broadcast_to(pack.layout.terrain(xx,zz),clipped.shape)] = y_min-1
    top, low, _ = shell_counts(clipped, y_min)
    if background is not None: top,low = background
    top, low = top.ravel(), low.ravel()
    cols = columns.reshape(-1, 3)
    bx = np.broadcast_to((xx[:, 1:-1] // CORE_SIZE), shape).ravel()
    bz = np.broadcast_to((zz[1:-1] // CORE_SIZE), shape).ravel()
    points, materials, count = [], [], 0
    solid_count = int((np.maximum(top.astype(np.int64) - y_min + 1, 0)*area.ravel()).sum())
    stats = dict(geometry_slabs=0, geometry_voxels=0, geometry_work_array_bytes=0)
    seconds = dict(background_shell=perf_counter() - started, geometry_sampling=0., geometry_culling=0., geometry_materials=0.)
    material_on = wall_materials.active(pack,params)
    depth_limit = wall_materials.surface_depth(pack, params)
    reference_tops = tops if reference_tops is None else reference_tops

    def emit(col, ys, exposed=None, carved=None, upward=None, nearby=None):
        nonlocal count
        n = len(col)
        if count + n > max_instances:
            raise ValueError(f'visible cells exceed max_instances={max_instances:,} before sparse allocation')
        xyz = np.empty((n, 3), np.int32)
        xyz[:, 0] = lx[col % shape[1]] - region.x0
        xyz[:, 1] = ys
        xyz[:, 2] = lz[col // shape[1]] - region.z0
        material_start = perf_counter()
        depth = top[col] - ys
        role = layer_roles(depth,depth_limits if np.ndim(depth_limits)==0 else depth_limits[col])
        points.append(xyz)
        types = cols[col, role]
        if exposed is not None:
            coords = xyz.astype(np.int64)
            coords[:,0] += region.x0
            coords[:,2] += region.z0
            if step != 1: coords[:,[0,2]] = coords[:,[0,2]]//step*step
            ids = biomes.ravel()[col] if biomes is not None else np.zeros(n,np.uint16)
            burial = reference_tops[1:-1,1:-1].ravel()[col] - ys
            types = wall_materials.apply(pack,params,seed,coords,types,burial,exposed,carved,ids,resources,
                                        natural_depths=nearby)
        materials.append(types)
        seconds['geometry_materials'] += perf_counter() - material_start
        if projection is not None and not height_mode(pack):
            if upward is None:
                upward = ys == top[col]
            projection.add_surfaces(xyz, types, upward & (ys + 1 < y_max))
        count += n

    for by in range(y_min // slab_height, (y_max - 1) // slab_height + 1):
        check_cancel(cancel_event)
        lo, hi = max(y_min, by * slab_height), min(y_max, (by + 1) * slab_height)
        started = perf_counter()
        material_before = seconds['geometry_materials']
        selected = [(ax, az) for ax, ay, az in sorted(active) if ay == by]
        background = np.ones(cells, bool)
        for ax, az in selected:
            background &= ~((bx == ax) & (bz == az))
        start = np.maximum(low, lo)
        lengths = np.maximum(np.minimum(top, hi - 1) - start + 1, 0) * background
        bottom = background & (top >= y_min) & (low > y_min) if lo == y_min else np.zeros(cells, bool)
        n = int(lengths.sum()) + int(bottom.sum())
        if count + n > max_instances:
            raise ValueError(f'visible cells exceed max_instances={max_instances:,} before sparse allocation')
        col = np.repeat(np.arange(cells), lengths)
        offsets = np.repeat(np.cumsum(lengths) - lengths, lengths)
        emit(col, start[col] + np.arange(len(col)) - offsets)
        emit(np.flatnonzero(bottom), np.full(int(bottom.sum()), y_min))
        seconds['background_shell'] += perf_counter() - started - (seconds['geometry_materials'] - material_before)
        for ax, az in selected:
            check_cancel(cancel_event)
            x0, z0 = max(tile.x0, ax * CORE_SIZE), max(tile.z0, az * CORE_SIZE)
            x1, z1 = min(tile.x0 + tile.width, (ax + 1) * CORE_SIZE), min(tile.z0 + tile.depth, (az + 1) * CORE_SIZE)
            sub = Region(x0, z0, x1 - x0, z1 - z0)
            subx,subz,_,_,subarea = _axes(sub,step,pack.layout)
            ix0,iz0 = int(np.searchsorted(xx[0,1:-1],subx[0,1])),int(np.searchsorted(zz[1:-1,0],subz[1,0]))
            sz,sx = slice(iz0,iz0+subz.size),slice(ix0,ix0+subx.size)
            h = tops[sz, sx]
            x,z = subx,subz
            x, z = x[:, None, :], z[:, None, :]
            y = np.arange(lo - 1, hi + 1, dtype=np.int32)[None, :, None]
            started = perf_counter()
            material_before = seconds['geometry_materials']
            occupied, working, natural = _shell_sample(pack, params, seed, x, y, z, h, resources, depth_limit)
            if (height_mode(pack) and wet is not None
                    and (pack.density is None or pack.density.wet_protection == 'shell')):
                occupied |= wet[sz,sx][:,None,:] & (y<=h[:,None,:]) & (y>=y_min) & (y<y_max)
            raw_occupied = occupied
            if pack.layout is not None:
                occupied = _seam_neighbors(occupied,pack,params,seed,sub,y,resources)
                raw_occupied = occupied
            inside = (x+step > region.x0) & (x < region.x0 + region.width) & (z+step > region.z0) & (z < region.z0 + region.depth)
            if pack.layout is not None:
                inside = (x>=region.x0)&(x<region.x0+region.width)&(z>=region.z0)&(z<region.z0+region.depth)
            if material_on:
                occupied = occupied & inside
            else:
                occupied &= inside
            seconds['geometry_sampling'] += perf_counter() - started
            started = perf_counter()
            core = occupied[1:-1, 1:-1, 1:-1]
            if projection is not None:
                projection.add(core, h[1:-1, 1:-1], sub, lo, step)
            base = np.maximum(np.minimum(h[1:-1, 1:-1], hi - 1) - lo + 1, 0)
            solid_count += int(((core.sum(axis=1)-base)*subarea).sum())
            visible = _visible(occupied)
            iz, iy, ix = np.nonzero(visible)
            col = (iz+iz0)*shape[1]+ix+ix0
            if material_on:
                material_start = perf_counter()
                exposed, carved = wall_materials.faces(raw_occupied,reference_tops[sz,sx],y,(iz,iy,ix),params,
                                                      height_mode=height_mode(pack))
                seconds['geometry_materials'] += perf_counter() - material_start
                emit(col,iy+lo,exposed,carved,
                     ~occupied[iz+1,iy+2,ix+1] if not height_mode(pack) else None,
                     wall_materials.depths(natural, (iz+1, iy+depth_limit, ix+1), depth_limit)
                     if depth_limit else None)
            else:
                emit(col, iy + lo, upward=~occupied[iz+1,iy+2,ix+1] if not height_mode(pack) else None)
            stats['geometry_slabs'] += 1
            stats['geometry_voxels'] += core.size
            stats['geometry_work_array_bytes'] = max(stats['geometry_work_array_bytes'], working + visible.nbytes
                                                   + (occupied.nbytes if material_on else 0))
            seconds['geometry_culling'] += perf_counter() - started - (seconds['geometry_materials'] - material_before)
            del occupied, raw_occupied, natural, core, visible
    return np.concatenate(points), np.concatenate(materials), solid_count, seconds, stats


def section(spec, axis='z', at=None, *, field='solid'):
    """Read-only occupancy slice. Rows/columns increase along returned axes.

    z -> [Y,X], x -> [Y,Z], y -> [Z,X]. No region-edge walls are fabricated.
    The height field remains the baseline, while occupancy includes geometry.
    """
    from .world import _GenerationInput
    from .fields import Context, active_passes
    from .planning import Resources
    from .store import evaluate_passes
    from .data import Region
    if axis not in ('x', 'y', 'z'):
        raise ValueError("axis must be 'x', 'y', or 'z' (MC coordinates)")
    if field not in ('solid', 'density'):
        raise ValueError("section field must be 'solid' or 'density'")
    request = _GenerationInput.capture(spec)
    pack = request.pack
    params, r = pack.resolve(spec), spec.region
    bounds = {'x': (r.x0, r.x0 + r.width), 'z': (r.z0, r.z0 + r.depth),
              'y': (params['world.y_min'], params['world.y_max'])}
    lo, hi = bounds[axis]
    at = (lo + hi) // 2 if at is None else at
    require_int('at', at, lo, hi - 1)
    axes = {'z': ('y', 'x'), 'x': ('y', 'z'), 'y': ('z', 'x')}[axis]
    row_bounds, col_bounds = bounds[axes[0]], bounds[axes[1]]
    if (row_bounds[1] - row_bounds[0]) * (col_bounds[1] - col_bounds[0]) > MAX_SECTION_CELLS:
        raise ValueError('section exceeds the 4,194,304-cell diagnostic budget; reduce the region or Y range')
    rows = np.arange(*row_bounds, dtype=np.int64)
    cols = np.arange(*col_bounds, dtype=np.int64)
    horizontal = Region(at, r.z0, 1, r.depth) if axis == 'x' else Region(r.x0, at, r.width, 1) if axis == 'z' else r
    resources = Resources(pack, params, spec.seed, region=r, validate=False)
    passes = evaluate_passes(pack, params, spec.seed, r, resources)
    with active_passes(passes, r):
        resources.validate_region(horizontal)
        passes = evaluate_passes(pack, params, spec.seed, r, resources, passes, with_resources=True)
    with active_passes(passes, r):
        if pack.layout is not None:
            from .store import reference
            height = reference(pack,params,spec.seed,horizontal,resources,include_surface=False).height
        else:
            source_region = horizontal
            if spec.cell_step != 1:
                from .coarse import aligned
                source_region = aligned(horizontal,spec.cell_step)
            ctx = Context.for_region(pack.fields, params, spec.seed, source_region, resources=resources,step=spec.cell_step)
            height = np.clip(ctx.get(pack.height_field), params['world.y_min'], params['world.y_max'])
            if spec.cell_step != 1:
                ix = (np.arange(horizontal.x0,horizontal.x0+horizontal.width)-source_region.x0)//spec.cell_step
                iz = (np.arange(horizontal.z0,horizontal.z0+horizontal.depth)-source_region.z0)//spec.cell_step
                height = height[iz[:,None],ix]
        tops = np.ceil(height).astype(np.int32) - 1
        xx, zz = horizontal.coordinates()
        ys = np.array([at]) if axis == 'y' else rows
        sampler = density_values if field == 'density' else sample
        occupied, _ = sampler(pack, params, spec.seed, xx[:, None, :], ys[None, :, None], zz[:, None, :], tops,
                              resources=resources)
    data = occupied[0] if axis == 'z' else occupied[:, :, 0].T if axis == 'x' else occupied[:, 0, :]
    for array in (data, rows, cols):
        array.setflags(write=False)
    return {field: data, 'axis': axis, 'at': at, 'axes': axes, 'rows': rows, 'columns': cols}
