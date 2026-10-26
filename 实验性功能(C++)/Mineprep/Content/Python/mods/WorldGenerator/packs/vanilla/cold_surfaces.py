"""Static snow, inland ice and ocean floes in one batch surface pass."""
import numpy as np
from ...core.postprocess import SurfacePatch


def apply(ctx, surfaces):
    layers = ctx.params['cold.snow_layers']
    r = ctx.region
    points = surfaces.xyz
    inside = ((points[:, 0] >= r.x0) & (points[:, 0] < r.x0 + r.width) &
              (points[:, 2] >= r.z0) & (points[:, 2] < r.z0 + r.depth))
    eligible = inside & surfaces.sky_open
    empty = np.empty((0, 3), np.int32)
    sea_freeze = ctx.params['frozen_ocean.enabled'] and ctx.params['frozen_ocean.freeze']
    if not eligible.any() or (not layers and not ctx.params['cold.freeze'] and not sea_freeze):
        return SurfacePatch(empty, np.empty(0, np.uint16), np.empty(0, bool))

    reference = ctx.query.reference(r,include_surface=False)
    iz, ix = points[:, 2] - r.z0, points[:, 0] - r.x0
    cold = reference.ctx.get('snow_cover')[iz, ix] >= .5
    eligible &= cold
    parts, types, replacements = [], [], []
    if layers:
        leaves = [ctx.block_ids[name] for name in ('oak_leaves', 'birch_leaves', 'spruce_leaves')
                  if name in ctx.block_ids]
        canopy = np.isin(surfaces.types, leaves)
        dry = ~reference.wet[iz, ix] | (points[:, 1] > reference.levels[iz, ix])
        use = (eligible & (surfaces.kind != 2) & dry &
               ~np.isin(surfaces.types, [ctx.block_ids.get(n,-1) for n in ('packed_ice','snow_block')]) &
               (points[:, 1] + 1 < ctx.params['world.y_max']) &
               (~canopy | ctx.params['cold.canopy']))
        added = points[use].copy()
        added[:, 1] += 1
        added = added[~ctx.query.occupied(added)] if len(added) else added
        parts.append(added)
        types.append(np.full(len(added), ctx.block_ids[f'snow_layer_{layers}'], np.uint16))
        replacements.append(np.zeros(len(added), bool))
    if ctx.params['cold.freeze'] or sea_freeze:
        inland = np.isin(reference.ctx.get('water_kind')[iz, ix], (2, 3, 4))
        use = inland & ctx.params['cold.freeze']
        if sea_freeze and ctx.params['frozen_ocean.ice_coverage'] > 0:
            sea = np.isin(surfaces.biomes, [i for i,b in enumerate(ctx.pack.biomes) if b.id=='frozen_ocean'])
            coverage = ctx.params['frozen_ocean.ice_coverage']
            if coverage < 1 and sea.any():
                sea &= reference.ctx.get('ocean_ice_patch')[iz,ix] >= 1-2*coverage
            use |= sea
        frozen = points[eligible & (surfaces.kind == 2) & use &
                        (surfaces.types == ctx.block_ids['water_surface'])].copy()
        parts.append(frozen)
        types.append(np.full(len(frozen), ctx.block_ids['ice'], np.uint16))
        replacements.append(np.ones(len(frozen), bool))
    return SurfacePatch(np.concatenate(parts), np.concatenate(types), np.concatenate(replacements))
