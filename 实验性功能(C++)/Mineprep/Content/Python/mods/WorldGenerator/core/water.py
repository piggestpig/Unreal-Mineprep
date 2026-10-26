"""Shared semantic water and planar connected-surface validation."""
import numpy as np


def validate_levels(levels, wet):
    if not np.isfinite(levels).all():
        raise ValueError('water levels must be finite')
    for a, b, wa, wb in ((levels[:, :-1], levels[:, 1:], wet[:, :-1], wet[:, 1:]),
                         (levels[:-1], levels[1:], wet[:-1], wet[1:])):
        if np.any(wa & wb & (a != b)):
            raise ValueError('four-neighbour connected wet cells must have the same water level')


def generated(pack, params):
    gate = pack.water.get('generate_param') if pack.water else None
    return pack.water is not None and (gate is None or bool(params[gate]))


def displayed(pack, params):
    gate = pack.water.get('enabled_param') if pack.water else None
    return gate is None or bool(params[gate])


def sample_water(ctx, pack, height):
    if not generated(pack, ctx.params):
        return np.full(ctx.shape, ctx.param('world.sea_level')), np.zeros(ctx.shape, bool)
    levels = (ctx.get(pack.water['level_field']) if pack.water and 'level_field' in pack.water
              else np.full(ctx.shape, ctx.param('world.sea_level')))
    candidate = (ctx.get(pack.water['mask_field']) > 0 if pack.water and 'mask_field' in pack.water
                 else np.ones(ctx.shape, bool))
    if pack.density is not None and pack.density.base == 'volume':
        # A volume has no single surface height. Query its uncut fluid plane,
        # including the cell above: a ceiling must not receive a fluid face.
        from .geometry import density_values
        y = np.floor(levels)[:, None, :]
        x, z = ctx.x[:, None, :], ctx.z[:, None, :]
        tops = np.ceil(height).astype(np.int32) - 1
        if np.all(levels == levels.flat[0]):
            # A constant plane is a regular two-layer grid, not two scattered
            # queries. Reuse the existing separable interpolation and samples.
            plane = np.floor(levels.flat[0])
            ys = np.array([plane, plane + 1], dtype=y.dtype)[None, :, None]
            values, _ = density_values(pack, ctx.params, ctx.seed, x, ys, z, tops, resources=ctx.resources)
            wet = candidate & (values[:, 0, :] <= 0) & (values[:, 1, :] <= 0)
        else:
            below, _ = density_values(pack, ctx.params, ctx.seed, x, y, z, tops, resources=ctx.resources)
            above, _ = density_values(pack, ctx.params, ctx.seed, x, y + 1, z, tops, resources=ctx.resources)
            wet = candidate & (below[:, 0, :] <= 0) & (above[:, 0, :] <= 0)
    else:
        wet = candidate & (np.ceil(height) <= levels) if pack.water else np.zeros(ctx.shape, bool)
    return levels, wet
