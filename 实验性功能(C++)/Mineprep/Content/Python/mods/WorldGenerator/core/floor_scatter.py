"""Single-cell decorations on final, sparse volume floors; no air-volume scan."""
from dataclasses import dataclass
import numpy as np
from .data import check_cancel
from .features import enabled
from .noise3 import hash01


@dataclass(frozen=True)
class ScatterTile:
    xyz: np.ndarray          # world-region-local X/Z, absolute MC Y
    types: np.ndarray        # pack block IDs
    soft: np.ndarray
    counts: tuple            # feature ID / accepted cells; no per-cell objects
    owners: np.ndarray       # feature-definition indices, retained for global model filtering


def active(pack, params):
    result = []
    for f in pack.features:
        if f.type != 'surface_scatter' or f.placement != 'volume_floor' or not enabled(f, params):
            continue
        density = params[f.density[1:]] if isinstance(f.density, str) else f.density
        if not np.isfinite(density) or not 0 <= density <= 1:
            raise ValueError(f'feature {f.id}: density must be in [0,1]')
        if density:
            result.append(f)
    return tuple(result)


def lower_supports(pack, params, seed, natural, depth, tile, region, tops, columns,
                   biomes, resources, soil_depth):
    """Read only the first slab's existing physical halo, including final materials."""
    from . import materials
    from .shell import layer_roles
    mask = natural[1:-1, depth, 1:-1] & ~natural[1:-1, depth+1, 1:-1]
    iz, ix = np.nonzero(mask)
    xyz = np.column_stack((ix+tile.x0-region.x0, np.full(len(ix), params['world.y_min']-1),
                           iz+tile.z0-region.z0)).astype(np.int32)
    burial = tops[1:-1, 1:-1][iz, ix] - xyz[:, 1]
    role = layer_roles(burial, soil_depth if np.ndim(soil_depth) == 0 else soil_depth[iz, ix])
    types = columns[iz, ix, role]
    if len(xyz) and materials.active(pack, params):
        indices = (iz+1, np.full(len(ix), depth), ix+1)
        faces = np.zeros(len(ix), np.uint8)
        for bit, (dz, dy, dx) in enumerate(((0,0,-1),(0,0,1),(0,-1,0),(0,1,0),(-1,0,0),(1,0,0))):
            faces |= (~natural[indices[0]+dz, indices[1]+dy, indices[2]+dx]).astype(np.uint8) << bit
        cap = materials.surface_depth(pack, params)
        nearby = materials.depths(natural, indices, cap) if cap else None
        absolute = xyz.astype(np.int64) + [region.x0, 0, region.z0]
        ids = biomes[iz, ix] if biomes is not None else np.zeros(len(ix), np.uint16)
        types = materials.apply(pack, params, seed, absolute, types, burial, faces, faces,
                                ids, resources, natural_depths=nearby)
    return np.column_stack((xyz, types)).astype(np.int32)


def scatter(ctx, pack, tile, region, supports, biomes, water, levels, features, *, max_instances):
    """Independent coordinate draws; final support IDs decide the decoration type."""
    from .postprocess import _PointIndex
    selected = np.full(len(supports), -1, np.int32)
    bindings = active(pack, ctx.params)
    x = supports[:, 0] + region.x0 - tile.x0
    z = supports[:, 2] + region.z0 - tile.z0
    y = supports[:, 1] + 1
    ids = {name: i for i, name in enumerate(pack.blocks)}
    check_cancel(getattr(ctx.resources, 'cancel_event', None))
    for owner, f in enumerate(pack.feature_defs):
        for binding in (v for v in bindings if v.id == f.id):
            density = ctx.params[binding.density[1:]] if isinstance(binding.density, str) else binding.density
            mask = ((selected < 0) & (y >= ctx.params['world.y_min']) & (y < ctx.params['world.y_max'])
                    & np.isin(supports[:, 3], [ids[n] for n in binding.surface])
                    & np.isin(biomes[z, x], [i for i, b in enumerate(pack.biomes) if b.id in binding.biomes])
                    & (~water[z, x] | (y > levels[z, x])))
            chosen = np.flatnonzero(mask)
            p = supports[chosen, :3].astype(np.int64) + [region.x0, 1, region.z0]
            draw = hash01(*p.T, ctx.seed, f'features/{f.id}/volume-floor')
            from .masks import weight
            selected[chosen[draw < density * weight(pack, f.category, p[:,0], p[:,2])]] = owner
    chosen = np.flatnonzero(selected >= 0)
    points = supports[chosen, :3].copy()
    points[:, 1] += 1
    if len(points) and len(features.xyz):
        blocked, _ = _PointIndex(features.xyz).lookup(points)
        chosen, points = chosen[~blocked], points[~blocked]
    if len(points) and features.models:
        from .templates import ModelIndex
        absolute = points.astype(np.int64) + [region.x0, 0, region.z0]
        blocked = ModelIndex(features.models, ctx.params['world.y_min'], ctx.params['world.y_max']).occupied(absolute)
        chosen, points = chosen[~blocked], points[~blocked]
    check_cancel(getattr(ctx.resources, 'cancel_event', None))
    if len(points) > max_instances:
        raise ValueError(f'visible cells exceed max_instances while adding volume_floor scatter')
    owners = selected[chosen]
    used, sizes = np.unique(owners, return_counts=True)
    type_ids = np.zeros(len(pack.feature_defs), np.uint16)
    for owner in used:
        type_ids[owner] = ids[pack.feature_defs[int(owner)].block]
    types = type_ids[owners]
    soft = np.asarray([getattr(f, 'soft', False) for f in pack.feature_defs], bool)[owners]
    counts = tuple((pack.feature_defs[int(owner)].id, int(count)) for owner, count in
                   zip(used, sizes))
    ctx.resources.report.peak('floor_scatter_work_bytes', supports.nbytes+selected.nbytes+x.nbytes+z.nbytes+y.nbytes+points.nbytes)
    for array in (points, types, soft):
        array.setflags(write=False)
    owners.setflags(write=False)
    return ScatterTile(points, types, soft, counts, owners)


def filter_models(tile, model_index, region, pack):
    """Final global ownership catches a model anchored across a tile boundary."""
    from dataclasses import replace
    absolute = tile.xyz.astype(np.int64)+[region.x0,0,region.z0]
    keep = ~model_index.occupied(absolute)
    if keep.all():
        return tile
    owners = tile.owners[keep]
    used,sizes = np.unique(owners,return_counts=True)
    result = replace(tile,xyz=tile.xyz[keep],types=tile.types[keep],soft=tile.soft[keep],owners=owners,
                     counts=tuple((pack.feature_defs[int(i)].id,int(n)) for i,n in zip(used,sizes)))
    for array in (result.xyz,result.types,result.soft,result.owners):
        array.setflags(write=False)
    return result
