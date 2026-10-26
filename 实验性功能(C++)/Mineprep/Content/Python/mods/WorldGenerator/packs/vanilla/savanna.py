"""Broad warm/dry regions and bare patches; physical terrain is unchanged."""
import numpy as np
from ...core.fields import field
from .terrain import _climate_noise, _smooth, CLIMATE_GAIN


@field('savanna_weight', res=16)
def weight(ctx):
    """Macro climate includes offsets, without fine edges or altitude cooling."""
    if ctx.param('savanna.coverage') == 0:
        return 0.
    biome = ctx.param('climate.single_biome')
    if biome:
        return 1. if biome == 'savanna' else 0.
    scale = ctx.param('savanna.region_scale')
    temp = (_climate_noise(ctx, 'climate/temperature', scale, 2) * CLIMATE_GAIN
            + ctx.param('climate.temperature_offset'))
    humidity = (_climate_noise(ctx, 'climate/humidity', scale, 2) * CLIMATE_GAIN
                + ctx.param('climate.humidity_offset'))
    threshold = 1 - ctx.param('savanna.coverage')
    return _smooth((np.minimum(temp, -humidity) - threshold + .05) / .1)


@field('savanna_mask')
def mask(ctx):
    if ctx.param('savanna.coverage') == 0:
        return 0.
    return np.clip(ctx.grid_sample('savanna_weight',
                                  strength=ctx.param('climate.boundary_detail')), 0, 1)


@field('savanna_bare', res=4)
def bare_ground(ctx):
    return np.clip(2.5 * ctx.noise('savanna/bare', ctx.param('savanna.bare_scale'),
                                 octaves=2), -1, 1)
