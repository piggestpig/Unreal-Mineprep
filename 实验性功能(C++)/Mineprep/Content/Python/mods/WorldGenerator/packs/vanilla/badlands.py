"""Animation scenery: broad mesas and seeded clay bands, not MC seed parity.

All relief is in the existing 2D height chain. Bands recolour sparse shell
cells; there are no solid feature volumes, voxel noise or global RNG state.
"""
import hashlib
import numpy as np
from ...core.fields import field
from .terrain import _climate_noise, _smooth, CLIMATE_GAIN


def enabled(ctx):
    return ctx.param('badlands.enabled') and ctx.param('badlands.coverage') > 0


@field('badlands_region_base', res=16)
def region(ctx):
    if not enabled(ctx):
        return -1.
    scale = ctx.param('badlands.region_scale')
    temp = (_climate_noise(ctx, 'climate/temperature', scale, 2) * CLIMATE_GAIN
            + ctx.param('climate.temperature_offset'))
    humidity = (_climate_noise(ctx, 'climate/humidity', scale, 2) * CLIMATE_GAIN
                + ctx.param('climate.humidity_offset'))
    return np.minimum(temp, -humidity)


@field('badlands_weight', res=16)
def weight(ctx):
    """One broad warm/dry region; fine climate cannot cut its interior apart."""
    if not enabled(ctx):
        return 0.
    biome = ctx.param('climate.single_biome')
    if biome:
        return 1. if biome == 'badlands' else 0.
    threshold = 1 - ctx.param('badlands.coverage')
    return _smooth((ctx.get('badlands_region_base') - threshold + .05) / .1)


@field('badlands_mask')
def mask(ctx):
    if not enabled(ctx):
        return 0.
    return np.clip(ctx.grid_sample('badlands_weight', strength=ctx.param('climate.boundary_detail')), 0, 1)


@field('badlands_body', res=8)
def body(ctx):
    u = .5 + CLIMATE_GAIN * ctx.noise('terrain/badlands/body', ctx.param('badlands.plateau_scale'), octaves=2)
    return _smooth((u-.25)/.35)


@field('height_badlands', deps=('height_islands',))
def height(ctx, baseline):
    if not enabled(ctx) or ctx.param('terrain.flat') or not ctx.param('badlands.height'):
        return baseline
    sea = ctx.param('world.sea_level')
    single = ctx.param('climate.single_biome') == 'badlands'
    shore = (baseline > sea) if single else _smooth((baseline-sea-2)/8)
    if not shore.any():
        return baseline
    blend = np.clip(ctx.get('badlands_weight'), 0, 1) * shore
    if not blend.any():
        return baseline
    mesa = ctx.get('badlands_body')
    valley = sea + (3 if single else 6) + .25 * np.maximum(baseline-sea, 0)
    detail = 1.5 * np.clip(ctx.get('detail_noise') * CLIMATE_GAIN, -1, 1)
    target = valley + ctx.param('badlands.height') * mesa + detail
    return baseline + blend * (target-baseline)


@field('badlands_band_shift', res=16)
def shift(ctx):
    return 4 * np.clip(ctx.noise('surface/badlands/bands', 128, octaves=2)*CLIMATE_GAIN, -1, 1)


def bands(seed, ids):
    """Small per-batch table; MC-inspired spacing, no persistent shape cache."""
    key = hashlib.sha256(f'badlands/bands/{seed}'.encode()).digest()[:8]
    rng = np.random.default_rng(int.from_bytes(key, 'little'))
    result = np.full(192, ids['terracotta'], np.uint16)
    at = 0
    while at < len(result):
        at += int(rng.integers(1, 6))
        if at < len(result): result[at] = ids['orange_terracotta']
        at += 1
    for name, base in (('yellow_terracotta',1),('brown_terracotta',2),('red_terracotta',1)):
        for _ in range(int(rng.integers(6, 16))):
            at = int(rng.integers(192)); width = base + int(rng.integers(3))
            result[at:at+width] = ids[name]
    at = 0
    for _ in range(int(rng.integers(9, 16))):
        at += int(rng.integers(4, 20))
        if at >= len(result): break
        result[at] = ids['white_terracotta']
        if at and rng.integers(2): result[at-1] = ids['light_gray_terracotta']
        if at+1 < len(result) and rng.integers(2): result[at+1] = ids['light_gray_terracotta']
    return result


def sample(ctx):
    offset = np.rint(ctx.fields['badlands_band_shift'][ctx.column_index]).astype(np.int64)
    index = ((ctx.y + offset) // ctx.params['badlands.band_thickness']) % 192
    return bands(ctx.seed, ctx.block_index)[index]
