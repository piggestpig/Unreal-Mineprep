"""Offline images of a World: map views, a cross-section and a one-page contact sheet.

Image axes: row 0 = z0, columns increase x. All views are RGB uint8.
"""

from pathlib import Path
import math

import numpy as np

from .block_colors import color_table

VIEWS = ("landscape", "surface", "vegetation", "biomes", "height", "temperature", "humidity", "water_system", "caves", "cave_sections", "underground_water", "heightmap", "vegetation_mask", "clearance_mask")
OVERVIEW_VIEWS = ('landscape', 'surface', 'biomes', 'height', 'temperature', 'humidity')
TERRAIN_FIELDS = ("continentalness", "erosion", "weirdness", "peaks_valleys")
LIGHT = np.array([-1.0, 2.0, -1.0]) / np.sqrt(6.0)  # towards the light, MC x/y/z
VOID_COLOR = np.array([0, 0, 0], np.uint8)


def hillshade(heights):
    padded = np.pad(heights.astype(np.float64), 1, mode="edge")
    dx = (padded[1:-1, 2:] - padded[1:-1, :-2]) * 0.5
    dz = (padded[2:, 1:-1] - padded[:-2, 1:-1]) * 0.5
    lambert = (-dx * LIGHT[0] + LIGHT[1] - dz * LIGHT[2]) / np.sqrt(1 + dx * dx + dz * dz)
    return 0.35 + 0.65 * np.clip(lambert, 0, 1)


def _gradient(values, lo, hi, stops):
    t = np.clip((values - lo) / (hi - lo if hi > lo else 1.0), 0, 1)
    xs = np.linspace(0, 1, len(stops))
    stops = np.asarray(stops, np.float64)
    return np.stack([np.interp(t, xs, stops[:, c]) for c in range(3)], axis=-1).astype(np.uint8)


def field_rgb(name, values, sea_level):
    """Fixed diagnostic ranges make maps comparable across origins and presets."""
    if name == "height":
        ocean = _gradient(values, sea_level - 32, sea_level,
                          ((20, 45, 100), (70, 145, 185), (175, 210, 220)))
        land = _gradient(values, sea_level, sea_level + 128,
                         ((190, 195, 135), (80, 145, 85), (145, 120, 90), (245, 245, 245)))
        return np.where((values < sea_level)[..., None], ocean, land)
    palettes = {
        "continentalness": ((25, 65, 145), (215, 220, 180), (65, 140, 80)),
        "erosion": ((125, 70, 35), (235, 210, 155), (90, 155, 110)),
        "weirdness": ((95, 65, 160), (240, 240, 240), (195, 75, 65)),
        "peaks_valleys": ((35, 85, 140), (185, 170, 125), (250, 245, 235)),
    }
    if name in palettes:
        return _gradient(values, -1, 1, palettes[name])
    if name == "mountain_weight":
        return _gradient(values, 0, 1, ((70, 135, 90), (210, 165, 90), (240, 235, 225)))
    return _gradient(values, float(values.min()), float(values.max()), ((0, 0, 0), (255, 255, 255)))


def overview_views(pack):
    names = tuple(n for n in OVERVIEW_VIEWS if n not in ('temperature','humidity') or n in pack.fields)
    return (names + (('heightmap',) if getattr(pack, 'heightmap', None) is not None else ())
            + tuple(kind+'_mask' for kind in (pack.masks or {})))


def mask_rgb(data, region):
    # Input previews stay inexpensive even when the output region is large.
    width, depth = min(region.width, 512), min(region.depth, 512)
    x = region.x0 + (np.arange(width)+.5)*region.width/width-.5
    z = region.z0 + (np.arange(depth)+.5)*region.depth/depth-.5
    values = data.sample(x[None,:], z[:,None])
    if data.kind == 'clearance':
        values = (values >= .5).astype(float)
    return np.repeat(np.rint(values[...,None]*255).astype(np.uint8), 3, axis=-1)


def heightmap_rgb(data, region, params):
    """Mapped absolute heights/deltas; display contrast never changes terrain values."""
    x, z = region.coordinates()
    values = data.sample(x, z, params)
    return field_rgb('heightmap', values, params['world.sea_level'])


def reference_view(data, name):
    image = _reference_view(data, name)
    field = data.pack.reference_mask_field
    if field is not None and name in ('landscape','surface','biomes','height'):
        # Volume captions precede the map; only mask its spatial rows.
        image = image.copy()
        image[-data.region.depth:,:data.region.width][data.fields[field] < .5] = VOID_COLOR
    return image


def _reference_view(data, name):
    """Shared reference rendering; deliberately does not inspect entity output."""
    if name not in overview_views(data.pack):
        raise ValueError(f'view {name!r} requires a full preview or an available reference field')
    if name == 'heightmap':
        return heightmap_rgb(data.pack.heightmap, data.region, data.params)
    if name in ('vegetation_mask','clearance_mask'):
        return mask_rgb(data.pack.masks[name.removesuffix('_mask')], data.region)
    shade = hillshade(data.heights)[..., None]
    if name in ('landscape','surface'):
        colors = color_table(data.pack.blocks, data.pack.block_defs).astype(np.float64)
        rgb = np.clip(colors[data.columns[...,0]] * shade, 0, 255)
        if name == 'landscape' and data.pack.water:
            water = colors[data.pack.blocks.index(data.pack.water['block'])]
            rgb[data.water_mask] = .75 * water + .25 * rgb[data.water_mask]
        image = rgb.astype(np.uint8)
        if name == 'landscape' and data.pack.density is not None and data.pack.density.base == 'volume':
            import cv2
            caption = np.full((24, max(240, image.shape[1]), 3), 245, np.uint8)
            cv2.putText(caption, '2D reference only - no volume', (2, 16),
                        cv2.FONT_HERSHEY_SIMPLEX, .35, (30, 30, 30), 1)
            padded = np.full((image.shape[0], caption.shape[1], 3), 245, np.uint8)
            padded[:, :image.shape[1]] = image
            image = np.concatenate((caption, padded), axis=0)
        return image
    if name == 'biomes':
        colors = np.array([b.color for b in data.pack.biomes], np.float64)
        return np.clip(colors[data.biome_ids] * (.55 + .45 * shade), 0, 255).astype(np.uint8)
    if name == 'height':
        return np.clip(field_rgb(name, data.heights, data.params['world.sea_level']) * shade, 0, 255).astype(np.uint8)
    if name == 'temperature':
        return _gradient(data.fields[name], -1, 1, ((60,90,220),(240,240,240),(220,70,40)))
    return _gradient(data.fields[name], -1, 1, ((200,160,90),(240,240,240),(40,120,200)))


def view(world, name):
    if name in ('vegetation_mask','clearance_mask'):
        return mask_rgb(world.pack.masks[name.removesuffix('_mask')], world.region)
    if name == 'landscape' and world.pack.density is not None and world.pack.density.base == 'volume':
        return volume_landscape(world) if hasattr(world, 'arrays') else reference_view(world, name)
    if name == 'heightmap':
        if world.pack.heightmap is None:
            raise ValueError('this snapshot has no heightmap input')
        return heightmap_rgb(world.pack.heightmap, world.region, world.params)
    """RGB uint8[Z,X] for one of VIEWS (or any kept field name)."""
    if name == 'caves':
        return cave_view(world)
    if name == 'cave_sections':
        return cave_sections(world)
    if name == 'underground_water':
        rgb=np.full((*world.region.shape,3),235,np.uint8)
        data=world.fluid_layers
        if data is not None and len(data.xyz):
            colors=_gradient(data.levels,world.params['world.y_min'],world.params['world.y_max'],((25,80,145),(110,215,240)))
            order=np.argsort(data.levels,kind='stable')
            for i in order:
                x,y,z=data.xyz[i];rgb[z-world.region.z0,x-world.region.x0]=colors[i]
        return rgb
    if name in OVERVIEW_VIEWS and name != 'landscape':
        return reference_view(world, name)
    shade = hillshade(world.heights)[..., None]
    if name == 'water_system':
        from ..api import plan_water
        import cv2
        plan = plan_water(world.spec)
        kinds = world.fields.get('water_kind')
        if kinds is None:
            from ..api import fields
            kinds = fields(world.spec, ('water_kind',))['water_kind'] if 'water_kind' in world.pack.fields else world.wet_mask
        palette = np.array(((218, 222, 196), (37, 91, 153), (42, 150, 205), (70, 108, 185), (89, 165, 156)), np.uint8)
        rgb = (palette[np.clip(kinds.astype(int), 0, 4)] * (.65 + .35 * shade)).astype(np.uint8)
        if plan is not None and hasattr(plan, 'node_positions'):
            for nodes, color in ((plan.sources, (225, 180, 65)), (plan.junctions, (210, 80, 155)),
                                 (tuple(i for i, k in plan.outlets if k == 'sea'), (240, 105, 65)),
                                 (tuple(i for i, k in plan.outlets if k == 'boundary'), (220, 50, 35))):
                for i in nodes:
                    px, pz = plan.node_positions[i] - (world.region.x0, world.region.z0)
                    if 0 <= px < world.region.width and 0 <= pz < world.region.depth:
                        cv2.circle(rgb, (int(px), int(pz)), 3, color, -1)
        return rgb
    if name in ('surface', 'landscape', 'vegetation'):
        colors = color_table(world.pack.blocks, world.pack.block_defs).astype(np.float64)
        rgb = np.clip(colors[world.columns[..., 0]] * shade, 0, 255)
        if name == 'landscape':
            if world.geometry_views is not None:
                actual, materials = actual_surface(world)
                rgb = np.clip(colors[materials] * hillshade(actual)[..., None], 0, 255)
            if world.pack.water:
                water = colors[world.pack.blocks.index(world.pack.water['block'])]
                rgb[world.water_mask] = .75 * water + .25 * rgb[world.water_mask]
            mask = world.plant_ids != 0
            rgb[mask] = colors[world.plant_ids[mask] - 1]
        elif name == 'vegetation':
            rgb *= .35
            mask = world.plant_ids != 0
            rgb[mask] = colors[world.plant_ids[mask] - 1]
        if name in ('landscape', 'vegetation') and world.feature_cells is not None and world.feature_cells.count:
            data = world.feature_cells
            order = np.lexsort((data.xyz[:, 1], data.xyz[:, 2], data.xyz[:, 0]))
            p, ids = data.xyz[order], data.types[order]
            last = np.r_[np.any(p[1:, (0, 2)] != p[:-1, (0, 2)], axis=1), True]
            highest = p[last]
            tint = color_table(data.names, world.pack.block_defs)[ids[last]].astype(np.float64)
            if name == 'landscape' and world.pack.water:
                submerged = world.water_mask[highest[:, 2], highest[:, 0]] & (highest[:, 1] < np.floor(world.water_levels[highest[:, 2], highest[:, 0]]))
                tint[submerged] = .55 * tint[submerged] + .45 * colors[world.pack.blocks.index(world.pack.water['block'])]
            rgb[highest[:, 2], highest[:, 0]] = tint
        if name == 'landscape' and (world.stats.get('surface_added',0) or world.stats.get('surface_replaced',0)):
            # Project final output for processor materials, including thin covers
            # and replaced water. Preserve the existing shading of other columns.
            arrays=world.arrays
            shape=np.array([d.shape in ('cube','surface') for d in arrays.block_defs])
            use=shape[arrays.types]
            p,t=arrays.xyz[use],arrays.types[use]
            if len(p):
                order=np.lexsort((p[:,1],p[:,2],p[:,0]));p,t=p[order],t[order]
                highest=np.r_[np.any(p[1:,(0,2)]!=p[:-1,(0,2)],axis=1),True]
                p,t=p[highest],t[highest]
                outputs={n for processor in world.pack.surface_processors for n in processor.blocks}
                changed=np.array([n in outputs for n in arrays.names])[t]
                p,t=p[changed],t[changed]
                tint=color_table(arrays.names,world.pack.block_defs)[t]
                rgb[p[:,2],p[:,0]]=tint*shade[p[:,2],p[:,0]]
        if name in ('landscape','vegetation'):
            for model in getattr(world,'model_instances',()):
                roof,ids=model.template.tops[model.rotation]
                p=roof+np.asarray(model.anchor)
                x,z=p[:,0]-world.region.x0,p[:,2]-world.region.z0
                inside=(x>=0)&(x<world.region.width)&(z>=0)&(z<world.region.depth)
                rgb[z[inside],x[inside]]=colors[ids[inside]]
        return rgb.astype(np.uint8)
    values = world.fields[name]
    return field_rgb(name, values, world.params['world.sea_level'])


def actual_surface(world):
    """Highest opaque terrain cells/materials from the unmerged sparse shell."""
    r, arrays = world.region, world.arrays
    tops = np.full(r.cells, world.params['world.y_min'] - 1, np.int32)
    materials = np.full(r.cells, world.pack.blocks.index(world.pack.blocks[0]), np.uint16)
    terrain = np.array([d.occludes for d in arrays.block_defs], bool)[arrays.types]
    if world.feature_cells is not None and world.feature_cells.count:
        from ..core.postprocess import _PointIndex
        found,at=_PointIndex(arrays.xyz).lookup(world.feature_cells.xyz)
        terrain[at[found]]=False
    xyz, types = arrays.xyz[terrain], arrays.types[terrain]
    columns = xyz[:, 2] * r.width + xyz[:, 0]
    np.maximum.at(tops, columns, xyz[:, 1])
    highest = xyz[:, 1] == tops[columns]
    ids = np.array([world.pack.blocks.index(n) for n in arrays.names], np.uint16)
    materials[columns[highest]] = ids[types[highest]]
    return tops.reshape(r.shape), materials.reshape(r.shape)


def _model_slice(world,axis,at):
    """Expand only cells intersecting a diagnostic plane, never the whole forest."""
    normal={'x':0,'y':1,'z':2}[axis];points=[];types=[]
    for m in world.model_instances:
        if not m.bounds[0][normal]<=at<m.bounds[1][normal]:continue
        p=m.template.orientations[m.rotation][0]
        use=p[:,normal]+m.anchor[normal]==at
        points.append(p[use]+np.asarray(m.anchor));types.append(m.template.types[use])
    return (np.concatenate(points),np.concatenate(types)) if points else (np.empty((0,3),np.int32),np.empty(0,np.uint16))


def section(world, row=None, height_px=None):
    """Side view of one z row, with water at each column's local elevation."""
    row = world.region.depth // 2 if row is None else row
    if world.pack.density is not None:
        return occupancy_rgb(world.spec, 'z', world.region.z0 + row, world=world, features=True)
    heights = world.heights[row]
    tops = np.ceil(heights).astype(np.int64) - 1
    levels = (world.water_levels[row] if world.water_levels is not None
              else np.full(len(tops), world.params['world.sea_level']))
    visible = world.water_mask[row]
    feature = world.feature_cells
    tree_row = feature.xyz[:, 2] == row if feature is not None else np.empty(0, bool)
    tree_high = int(feature.xyz[tree_row, 1].max()) if tree_row.any() else int(tops.max())
    models,model_types=_model_slice(world,'z',world.region.z0+row)
    if len(models):tree_high=max(tree_high,int(models[:,1].max()))
    y_hi = int(max(tops.max(), np.ceil(levels[visible]).max() if visible.any() else tops.max(), tree_high)) + 3
    y_lo = max(world.params["world.y_min"], int(tops.min()) - world.params["surface.soil_depth"] - 6)
    ys = np.arange(y_hi, y_lo - 1, -1)[:, None]
    depth = tops[None, :] - ys
    soil = world.params["surface.soil_depth"]
    role = np.where(depth == 0, 0, np.where(depth <= soil, 1, 2))
    colors = color_table(world.pack.blocks, world.pack.block_defs)
    blocks = world.columns[row][np.arange(len(tops))[None, :], role]
    image = np.where((depth >= 0)[..., None], colors[blocks], np.array([235, 240, 248], np.uint8))
    xx = np.flatnonzero(visible & (levels >= y_lo) & (levels <= y_hi))
    if world.pack.water:
        image[y_hi - np.floor(levels[xx]).astype(np.intp), xx] = colors[world.pack.blocks.index(world.pack.water['block'])]
    plant_mask = world.plant_ids[row] != 0
    xx = np.flatnonzero(plant_mask)
    image[y_hi - tops[xx] - 1, xx] = colors[world.plant_ids[row, xx] - 1]
    image = image.astype(np.uint8)
    if tree_row.any():
        p = feature.xyz[tree_row]
        inside = (p[:, 1] >= y_lo) & (p[:, 1] <= y_hi)
        image[y_hi-p[inside, 1], p[inside, 0]] = color_table(feature.names, world.pack.block_defs)[feature.types[tree_row][inside]]
    if len(models):
        x=models[:,0]-world.region.x0
        inside=(x>=0)&(x<world.region.width)&(models[:,1]>=y_lo)&(models[:,1]<=y_hi)
        image[y_hi-models[inside,1],x[inside]]=colors[model_types[inside]]
    if height_px:
        import cv2
        scale = max(1, height_px // image.shape[0])
        image = cv2.resize(image, (image.shape[1], image.shape[0] * scale), interpolation=cv2.INTER_NEAREST)
    return image


def occupancy_rgb(spec, axis='z', at=None, *, world=None, features=False, materials=False):
    """Actual geometry, with MC Y increasing upward in vertical images."""
    from ..api import section as sample_section
    cut = sample_section(spec, axis, at)
    rgb = np.where(cut['solid'][..., None], np.array([115, 113, 108], np.uint8),
                   VOID_COLOR).astype(np.uint8)
    if world is not None:
        if materials:
            colors = color_table(world.pack.blocks, world.pack.block_defs)
            rgb[cut['solid']] = colors[world.columns[0, 0, 0]]
            xyz = world.arrays.xyz
            indices = {'x': 0, 'y': 1, 'z': 2}
            offsets = {'x': world.region.x0, 'y': 0, 'z': world.region.z0}
            chosen = np.flatnonzero(xyz[:, indices[axis]] == cut['at'] - offsets[axis])
            points = xyz[chosen]
            rows, cols = (points[:, indices[a]] - (world.params['world.y_min'] if a == 'y' else 0)
                          for a in cut['axes'])
            palette = color_table(world.arrays.names, world.pack.block_defs)
            rgb[rows, cols] = palette[world.arrays.types[chosen]]
        from ..core.fluids import section_mask
        rgb[section_mask(world,axis,cut['at'])&~cut['solid']]=(35,155,205)
        data = world.feature_cells
        if features and data is not None and data.count and axis in ('x', 'z'):
            normal = 0 if axis == 'x' else 2
            horizontal = 2 if axis == 'x' else 0
            origin = world.region.x0 if axis == 'x' else world.region.z0
            use = data.xyz[:, normal] + origin == cut['at']
            p = data.xyz[use]
            rgb[p[:, 1]-world.params['world.y_min'], p[:, horizontal]] = color_table(data.names, world.pack.block_defs)[data.types[use]]
        if features:
            p,t=_model_slice(world,axis,cut['at'])
            indices={'x':0,'y':1,'z':2};origins={'x':world.region.x0,'z':world.region.z0,'y':world.params['world.y_min']}
            rows,cols=(p[:,indices[a]]-origins[a] for a in cut['axes'])
            inside=(rows>=0)&(rows<rgb.shape[0])&(cols>=0)&(cols<rgb.shape[1])
            rgb[rows[inside],cols[inside]]=color_table(world.pack.blocks,world.pack.block_defs)[t[inside]]
    return rgb[::-1].copy() if cut['axes'][0] == 'y' else rgb


def volume_surface(world, max_y=None):
    """Skip the initial solid run; first real air -> solid transition wins.

    A face at Y needs its air cell Y+1 inside the view, so Y < max_y.
    Candidates were collected from actual occupancy during shell extraction.
    """
    from ..core.data import require_int
    lo, hi = world.params['world.y_min'], world.params['world.y_max']
    max_y = hi - 1 if max_y is None else max_y
    require_int('preview height', max_y, lo, hi - 1)
    heights = np.full(world.region.shape, lo - 1, np.int32)
    materials = np.zeros(world.region.shape, np.uint16)
    points = world.landscape_surfaces
    if points is not None and len(points):
        p = points[points[:, 1] < max_y]
        x, y, z, t = p.T
        np.maximum.at(heights, (z, x), y)
        chosen = heights[z, x] == y
        materials[z[chosen], x[chosen]] = t[chosen]
    valid = heights >= lo
    lava = np.zeros(world.region.shape, bool)
    if world.pack.water:
        plane = np.floor(world.water_levels).astype(np.int32)
        lava = world.water_mask & (plane <= max_y) & (plane >= heights)
        heights[lava] = plane[lava]
        materials[lava] = world.pack.blocks.index(world.pack.water['block'])
        valid |= lava
    local = world.fluid_layers
    if world.pack.fluids is not None and local is not None and len(local.xyz):
        x,y,z = (local.xyz-[world.region.x0,0,world.region.z0]).T
        use = (y <= max_y) & (y >= heights[z,x])
        x,y,z = x[use],y[use],z[use]
        np.maximum.at(heights,(z,x),y)
        highest = heights[z,x] == y
        x,z = x[highest],z[highest]
        materials[z,x] = world.pack.blocks.index(world.pack.fluids.block)
        valid[z,x] = lava[z,x] = True
    return heights, materials, valid, lava


def volume_landscape(world, max_y=None):
    """Mineways-style roof removal, material colours and inexpensive relief."""
    heights, materials, valid, fluid = volume_surface(world, max_y)
    # Missing neighbours use the column itself, never an artificial zero floor.
    neighbours = np.pad(heights, 1, mode='edge')
    known = np.pad(valid, 1, mode='edge')
    west = np.where(known[1:-1, :-2], neighbours[1:-1, :-2], heights)
    north = np.where(known[:-2, 1:-1], neighbours[:-2, 1:-1], heights)
    relief = np.clip(.93 + .06 * np.clip(heights - west, -4, 2)
                     + .035 * np.clip(heights - north, -4, 2), .58, 1.05)
    lo, hi = world.params['world.y_min'], world.params['world.y_max']
    elevation = .90 + .10 * np.clip((heights - lo) / max(1, hi - lo), 0, 1)
    shade = np.maximum(.55, relief * elevation)
    shade[fluid] = 1.
    colors = color_table(world.pack.blocks, world.pack.block_defs)
    image = np.clip(colors[materials] * shade[..., None], 0, 255).astype(np.uint8)
    image[~valid] = VOID_COLOR
    # Non-occluding floor decorations mark only the selected floor, never a
    # different cave layer or a replacement opaque top surface.
    names = {f.block for f in world.pack.feature_defs if f.type == 'surface_scatter'
             and f.placement == 'volume_floor'}
    cells = getattr(world, 'feature_cells', None)
    if names and cells is not None and cells.count:
        mask = np.asarray([n in names for n in cells.names])[cells.types]
        p, t = cells.xyz[mask], cells.types[mask]
        x, y, z = p.T
        upper = world.params['world.y_max']-1 if max_y is None else max_y
        visible = valid[z, x] & ~fluid[z, x] & (y == heights[z, x]+1) & (y <= upper)
        palette = color_table(cells.names, world.pack.block_defs)
        image[z[visible], x[visible]] = palette[t[visible]]
    return image


def ravine_diagnostic(world):
    """Baseline height/wet map with accepted dry paths; not a rendered scene."""
    import cv2
    from ..api import plan_caves
    r = world.region
    height = world.heights
    value = 80 + 130 * (height - height.min()) / max(float(np.ptp(height)), 1.)
    image = np.repeat(value[..., None], 3, axis=2).astype(np.uint8)
    image[world.wet_mask] = (90, 145, 205)
    plan = plan_caves(world.spec)
    if plan is None:
        return image
    pixel = lambda c: (int(round(c[0] - r.x0)), int(round(c[2] - r.z0)))
    for ravine in plan.ravines(r):
        for obj in ravine.primitives:
            cv2.line(image, pixel(obj.a), pixel(obj.b), (245, 135, 45), 2)
    for system in plan.guides(r):
        cv2.circle(image, pixel(system.center), 3, (170, 70, 80), -1)
        for entry in system.entrances:
            cv2.circle(image, pixel(entry), 2, (245, 220, 80), -1)
    return image


def cave_positions(world):
    """Prefer an in-crop chamber connected to an in-crop entrance, then any chamber."""
    from ..api import plan_caves
    r = world.region
    p = world.params
    contains = lambda point: r.x0 <= point[0] < r.x0 + r.width and r.z0 <= point[2] < r.z0 + r.depth
    plan = plan_caves(world.spec)
    if plan is not None:
        candidates = [s for s in plan.guides(r) if contains(s.center)]
        if candidates:
            middle = (r.x0 + r.width / 2, r.z0 + r.depth / 2)
            def rank(s):
                b = s.primitives[0].bounds
                complete = r.x0 <= b[0] and b[3] < r.x0 + r.width and r.z0 <= b[2] and b[5] < r.z0 + r.depth
                return (not any(contains(e) for e in s.entrances), not complete,
                        (s.center[0] - middle[0]) ** 2 + (s.center[2] - middle[1]) ** 2)
            center = min(candidates, key=rank).center
            return (int(np.clip(round(center[2]), r.z0, r.z0 + r.depth - 1)),
                    int(np.clip(round(center[1]), p['world.y_min'], p['world.y_max'] - 1)))
        ravines = plan.ravines(r)
        if ravines:
            # Prefer a real in-crop path point, including paths whose anchor is
            # outside the crop. A slice stays useful in a ravine-only scene.
            points = [o.a for s in ravines for o in s.primitives if contains(o.a)]
            if points:
                center = min(points, key=lambda c: (c[0] - r.x0 - r.width / 2) ** 2 + (c[2] - r.z0 - r.depth / 2) ** 2)
                return int(np.clip(round(center[2]), r.z0, r.z0 + r.depth - 1)), int(np.clip(math.ceil(center[1]) + 1, p['world.y_min'], p['world.y_max'] - 1))
    return r.z0 + r.depth // 2, (p['world.y_min'] + p['world.y_max']) // 2


def _horizontal_panels(cuts, labels, footer=''):
    import cv2
    fitted=[]
    panel_height=min(512,max(128,min(c.shape[0] for c in cuts)))
    for cut in cuts:
        scale=min(panel_height/cut.shape[0],512/cut.shape[1])
        fitted.append(cv2.resize(cut,(max(1,round(cut.shape[1]*scale)),max(1,round(cut.shape[0]*scale))),interpolation=cv2.INTER_NEAREST))
    widths=[max(240,c.shape[1]) for c in fitted]
    canvas=np.full((max(c.shape[0] for c in fitted)+64,sum(widths)+16,3),250,np.uint8)
    column=0
    for cut,label,width in zip(fitted,labels,widths):
        cv2.putText(canvas,label,(column+4,18),cv2.FONT_HERSHEY_SIMPLEX,.4,(30,30,30),1)
        canvas[28:28+cut.shape[0],column:column+cut.shape[1]]=cut
        column+=width+8
    cv2.putText(canvas,footer,(4,canvas.shape[0]-12),cv2.FONT_HERSHEY_SIMPLEX,.42,(30,30,30),1)
    return canvas


def cave_view(world, positions=None):
    """Whole-crop carved voids: front, top and side, with nearest-depth shading."""
    from ..api import projection
    cuts=[]; labels=[]
    lengths=dict(x=world.region.width,z=world.region.depth,y=world.params['world.y_max']-world.params['world.y_min'])
    for axis,label in (('z','Front +Z: Y up / X'),('y','Top -Y: Z / X'),('x','Side +X: Y up / Z')):
        p=projection(world,axis)
        depth=np.where(p['mask'],p['depth'],0)
        rgb=_gradient(depth,0,lengths[axis],((30,65,120),(180,210,240)))
        rgb[~p['mask']]=(244,244,240)
        data=world.fluid_layers
        if data is not None and len(data.xyz):
            positions=data.xyz; indices=dict(x=0,y=1,z=2)
            a,b=p['axes'];rows=(positions[:,indices[a]]-p['rows'][0])//p['steps'][0]
            cols=(positions[:,indices[b]]-p['columns'][0])//p['steps'][1]
            valid=(rows>=0)&(rows<rgb.shape[0])&(cols>=0)&(cols<rgb.shape[1])
            rgb[rows[valid],cols[valid]]=(35,185,210)
        cuts.append(rgb[::-1] if p['axes'][0]=='y' else rgb)
        labels.append(label)
    footer='Near = dark blue; far = pale blue. Projection overlap does not imply connection.'
    if world.fluid_layers is not None and len(world.fluid_layers.xyz):footer='Cyan = underground water surfaces. Projection overlap does not imply connection.'
    return _horizontal_panels(cuts,labels,footer)


def cave_positions3(world):
    if world.fluid_layers is not None and len(world.fluid_layers.xyz):
        x,y,z=world.fluid_layers.xyz[len(world.fluid_layers.xyz)//2]
        return int(z),int(y),int(x)
    z,y=cave_positions(world)
    from ..api import plan_caves
    plan=plan_caves(world.spec)
    systems=() if plan is None else plan.guides(world.region)
    candidates=[s for s in systems if round(s.center[2])==z and round(s.center[1])==y]
    x=round(candidates[0].center[0]) if candidates else world.region.x0+world.region.width//2
    return z,y,int(np.clip(x,world.region.x0,world.region.x0+world.region.width-1))


def cave_sections(world, positions=None):
    z,y,*rest=cave_positions3(world) if positions is None else positions
    x=rest[0] if rest else world.region.x0+world.region.width//2
    volume = world.pack.density is not None and world.pack.density.base == 'volume'
    return _horizontal_panels([occupancy_rgb(world.spec,a,p,world=world,materials=volume) for a,p in [('z',z),('y',y),('x',x)]],
                              [f'Front slice Z={z}; Y up / X',f'Top slice Y={y}; Z / X',f'Side slice X={x}; Y up / Z'],
                              ('Exact planes; shell material colours; solid interior = base colour.' if volume else
                               'Gray = solid; pale = air; cyan = underground water. Exact planes.'))


def write_png(path, rgb):
    """cv2 PNG via bytes, so non-ASCII Windows paths work."""
    import cv2
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", np.ascontiguousarray(rgb[..., ::-1]))
    if not ok:
        raise RuntimeError(f"PNG encoding failed: {path}")
    path.write_bytes(encoded.tobytes())
    return str(path)


def write_overview_views(overview, directory, names=('landscape',), max_side=512):
    """Offline PNGs from an Overview; never starts generation for missing views."""
    return _write_images(((n,reference_view(overview,n)) for n in names), directory, max_side)


def _write_images(images, directory, max_side):
    import cv2
    paths = {}
    for name, image in images:
        scale = max_side / max(image.shape[:2])
        if scale < 1 and name not in ('caves','cave_sections'):
            size = (max(1, round(image.shape[1] * scale)), max(1, round(image.shape[0] * scale)))
            image = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
        paths[name] = write_png(Path(directory) / f'{name}.png', image)
    return paths


def write_views(world, directory, names=VIEWS, max_side=512, *, cave_positions_=None):
    """One RGB PNG per view (UE's texture loader needs RGB); returns {name: path}."""
    names = (n for n in names if not (n in ('caves','cave_sections') and world.pack.density is None)
             and not (n in ('temperature','humidity') and n not in world.pack.fields)
             and not (n == 'heightmap' and world.pack.heightmap is None)
             and not (n in ('vegetation_mask','clearance_mask') and n.removesuffix('_mask') not in (world.pack.masks or {}))
             and (n in VIEWS or n in world.fields))
    return _write_images(((n,cave_sections(world,cave_positions_) if n == 'cave_sections' else view(world,n))
                          for n in names), directory, max_side)


def _fit(image, box):
    import cv2
    scale = min(box / image.shape[0], box / image.shape[1])
    size = (max(1, round(image.shape[1] * scale)), max(1, round(image.shape[0] * scale)))
    mode = cv2.INTER_NEAREST if scale >= 1 else cv2.INTER_AREA
    fitted = cv2.resize(image, size, interpolation=mode)
    canvas = np.full((box, box, 3), 250, np.uint8)
    canvas[:fitted.shape[0], :fitted.shape[1]] = fitted
    return canvas


def contact_sheet(world, path, *, box=320, extra_lines=()):
    """Everything an agent needs to judge a change, in one PNG."""
    import cv2
    names = [n for n in ('landscape', 'surface', 'vegetation', "biomes", "height", "temperature", "humidity", "water_system", "slope", *TERRAIN_FIELDS)
             if n in ('landscape', 'vegetation', "surface", "biomes", "height", "water_system") or n in world.fields]
    if world.pack.density is not None:
        names.append('caves')
    pad, label_h = 8, 22
    cols = 3
    rows = (len(names) + cols - 1) // cols
    width = cols * box + (cols + 1) * pad
    cut = section(world)
    cut = cv2.resize(cut, (width - 2 * pad, min(220, max(60, cut.shape[0] * 3))), interpolation=cv2.INTER_NEAREST)
    lines = _summary(world) + list(extra_lines)
    height = rows * (box + label_h + pad) + pad + label_h + cut.shape[0] + pad + 18 * len(lines) + pad
    sheet = np.full((height, width, 3), 255, np.uint8)
    text = lambda s, x, y, scale=0.45, color=(30, 30, 30): cv2.putText(
        sheet, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color[::-1], 1, cv2.LINE_AA)
    for i, name in enumerate(names):
        r, c = divmod(i, cols)
        x, y = pad + c * (box + pad), pad + r * (box + label_h + pad)
        text(name, x, y + 15, 0.5)
        sheet[y + label_h:y + label_h + box, x:x + box] = _fit(view(world, name), box)[..., ::-1]
    y = pad + rows * (box + label_h + pad)
    text(f"section UE Y={world.region.z0 + world.region.depth // 2} blocks; height Z (blue: local water)", pad, y + 15, 0.5)
    y += label_h
    sheet[y:y + cut.shape[0], pad:pad + cut.shape[1]] = cut[..., ::-1]
    y += cut.shape[0] + pad
    for line in lines:
        if isinstance(line, tuple):
            swatch, line = line
            cv2.rectangle(sheet, (pad, y + 4), (pad + 12, y + 16), tuple(int(v) for v in swatch[::-1]), -1)
            text(line, pad + 18, y + 15)
        else:
            text(line, pad, y + 15)
        y += 18
    ok, encoded = cv2.imencode(".png", sheet)
    if not ok:
        raise RuntimeError("contact sheet encoding failed")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(encoded.tobytes())
    return str(path)


def diagnostic_sheet(spec, fields, path, *, sea_level, box=512):
    """Continental maps without allocating block shells or running the UE backend."""
    import cv2
    names = (*TERRAIN_FIELDS, "height", "mountain_weight")
    pad, label_h = 10, 36
    width, height = 3 * box + 4 * pad, 2 * (box + label_h + pad) + 80
    sheet = np.full((height, width, 3), 255, np.uint8)
    for i, name in enumerate(names):
        r, c = divmod(i, 3)
        x, y = pad + c * (box + pad), pad + r * (box + label_h + pad)
        values = fields[name]
        rgb = field_rgb(name, values, sea_level)
        if name == 'height':
            rgb = np.clip(rgb * hillshade(values)[..., None], 0, 255).astype(np.uint8)
        label = f'{name}: {values.min():.2f} .. {values.max():.2f}'
        cv2.putText(sheet, label, (x, y + 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 30, 30), 1)
        sheet[y + label_h:y + label_h + box, x:x + box] = _fit(rgb, box)
    y = 2 * (box + label_h + pad) + 25
    text = (f'seed {spec.seed}   region {spec.region.to_list()}   sea level {sea_level:g}   '
            f'below sea {(fields["height"] < sea_level).mean():.1%} (seabed, no water)')
    cv2.putText(sheet, text, (pad, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 30, 30), 1)
    return write_png(path, sheet)


def _summary(world):
    s, spec = world.stats, world.spec
    lines = [f"pack {spec.pack}  preset {spec.preset or world.pack.default_preset}  seed {spec.seed}  "
             f"UE XY origin/size (blocks) {spec.region.to_list()}  key {world.key[:8]}",
             f"height {s['height_min']:.1f}..{s['height_max']:.1f}  clipped {s['clipped']}  "
             f"visible {s['visible']:,}  solid {s['solid']:,}  blocks {len(world.arrays.names)}",
             f"{s['seconds']:.3f}s  {s['tiles']} tiles of {s['tile_size']}  {s['execution']} x{s['workers']}"]
    if spec.params:
        lines.append("overrides " + ", ".join(f"{k}={v}" for k, v in spec.params)[:150])
    if 'feature_instances' in s:
        lines.append(f"features {s['feature_instances']}  cells {s['feature_cells']}  "
                     f"added {s['feature_added_instances']}  stage {s['stages'].get('features', 0.):.3f}s")
    if s.get('feature_unsupported'):
        lines.append('height-surface features unsupported in volume: '+', '.join(s['feature_unsupported']))
    fractions = world.biome_fractions()
    for biome in world.pack.biomes:
        lines.append((biome.color, f"{biome.name[1]} ({biome.id}) {fractions[biome.id]:.1%}"))
    return lines
