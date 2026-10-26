"""Sparse ocean landforms in the shared 2D height chain; no feature objects."""
import numpy as np
from ...core.fields import field
from .terrain import _smooth, CLIMATE_GAIN


def enabled(ctx):
    return (ctx.param('islands.enabled') and ctx.param('islands.coverage') > 0
            and ctx.param('islands.height') > 0 and not ctx.param('terrain.flat'))


@field('island_shape', res=8)
def shape(ctx):
    if not enabled(ctx):
        return 0.
    return np.clip(CLIMATE_GAIN * ctx.noise('terrain/islands/shape',
                   ctx.param('islands.scale'), octaves=2), -1, 1)


@field('island_region', res=16)
def region(ctx):
    if not enabled(ctx):
        return -1.
    return np.clip(CLIMATE_GAIN * ctx.noise('terrain/islands/region',
                   ctx.param('islands.scale') * 4, octaves=2), -1, 1)


def _custom_height(ctx, baseline, custom):
    if ctx.param('terrain.flat') or custom is baseline:
        return baseline
    # height_custom is an author extension point: reject broken content clearly.
    if not np.isfinite(custom).all():
        raise ValueError('height_custom must return finite heights')
    return custom


@field('island_weight', deps=('height_lowlands', 'height_custom'))
def weight(ctx, baseline, custom):
    if not enabled(ctx):
        return 0.
    baseline = _custom_height(ctx, baseline, custom)
    ocean = _smooth((ctx.param('world.sea_level') - baseline - 2) / 6)
    if not ocean.any():
        return 0.
    body = _smooth((np.clip(ctx.get('island_shape'), -1, 1) - .05) / .45)
    threshold = 1 - ctx.param('islands.coverage')
    location = _smooth((np.clip(ctx.get('island_region'), -1, 1) - threshold + .1) / .2)
    return ocean * body * location


@field('height_islands', deps=('height_lowlands', 'height_custom', 'island_weight'))
def height(ctx, baseline, custom, weight):
    baseline = _custom_height(ctx, baseline, custom)
    if not np.any(weight):
        return baseline
    peak = ctx.param('world.sea_level') + ctx.param('islands.height') * (
        .25 + .75 * np.clip(ctx.get('massif'), 0, 1))
    return baseline + weight * (peak - baseline)
