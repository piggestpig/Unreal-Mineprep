"""World-anchored volume; physical boundaries never follow an output crop."""
import numpy as np
from ...core.fields import field
from ...core.density import density, intersect


def limits(ctx):
    floor, roof = ctx.param('nether.floor_y'), ctx.param('nether.roof_y')
    thickness = ctx.param('nether.boundary_thickness')
    if roof - floor < 2 * thickness + 8:
        raise ValueError('Nether roof - floor must be at least 2 * boundary thickness + 8 blocks')
    return floor, roof, thickness


@field('height')
def height(ctx):
    """2D reference floor only; never an upper bound on volume occupancy."""
    floor, _, thickness = limits(ctx)
    return floor + thickness + 4 * ctx.noise('nether/floor', 64, octaves=2)


@field('lava_presence')
def lava_presence(ctx):
    lo, hi, _ = limits(ctx)
    level = np.floor(ctx.param('world.sea_level'))
    return np.full(ctx.shape, float(lo <= level and level + 1 < hi), np.float32)


@density('nether_macro', res=4)
def macro(ctx):
    scales = tuple(ctx.param('nether.scale_' + a) for a in 'xyz')
    return ctx.noise('nether/lower', scales, octaves=3)


@density('nether_upper', res=4)
def upper(ctx):
    scales = tuple(ctx.param('nether.scale_' + a) * factor for a, factor in zip('xyz', (1.5, .75, 1.5)))
    return ctx.noise('nether/upper', scales, octaves=3)


@density('nether_selector', res=4)
def selector(ctx):
    scales = tuple(ctx.param('nether.scale_' + a) * 3 for a in 'xyz')
    return np.clip(.5 + 2 * ctx.noise('nether/selector', scales, octaves=1), 0, 1)


@density('nether_detail', res=4)
def detail(ctx):
    return ctx.noise('nether/detail', (24, 12, 24), octaves=1)


@density('nether_floor', res=4, axes='xz')
def floor_height(ctx):
    floor, _, thickness = limits(ctx)
    return (np.zeros(ctx.shape, np.float32) + floor + thickness
            + 4 * ctx.noise('nether/floor', (64, 64, 64), octaves=2))


@density('nether_roof', res=4, axes='xz')
def roof_height(ctx):
    _, roof, thickness = limits(ctx)
    return (np.zeros(ctx.shape, np.float32) + roof - thickness
            + 4 * ctx.noise('nether/roof', (64, 64, 64), octaves=2))


@density('nether_base', deps=('nether_macro', 'nether_upper', 'nether_selector',
                              'nether_detail', 'nether_floor', 'nether_roof'))
def solid(ctx, macro, upper, selector, detail, floor, roof):
    lo, hi, _ = limits(ctx)
    y = ctx.y + .5
    rock = macro + selector * (upper - macro)
    rock += ctx.param('nether.detail_strength') * detail - ctx.param('nether.cavern_bias')
    # MC-style slides, calibrated for normalized fBm rather than MC density units.
    # Keep asymmetric targets and separate physical boundaries, never crop bounds.
    span = min(24., (hi - lo) / 4)
    bottom = np.clip((floor + span - y) / span, 0, 1)
    top = np.clip((y - roof + span) / span, 0, 1)
    bottom = bottom * bottom * (3 - 2 * bottom)
    top = top * top * (3 - 2 * top)
    enclosed = rock * (1 - bottom) + .65 * bottom
    enclosed = enclosed * (1 - top) + .45 * top
    return intersect(enclosed, intersect(y - lo, hi - y)).astype(np.float32)


@field('soul_noise', res=8)
def soul_noise(ctx):
    return ctx.noise('nether/soul-region', ctx.param('soul.biome_scale'), octaves=2)


@field('soul_region', deps=('soul_noise',))
def soul_region(ctx, noise):
    # Clamp after interpolation, so threshold -1 really selects every column.
    return np.clip(noise, -1, 1) if ctx.param('soul.enabled') else np.full(ctx.shape, -2.)


@field('crimson_region', res=8)
def crimson_region(ctx):
    if not ctx.param('crimson.enabled'):
        return np.full(ctx.shape,-2.)
    return np.clip(ctx.noise('nether/crimson-region',ctx.param('crimson.biome_scale'),octaves=2),-1,1)


@field('warped_region', res=8)
def warped_region(ctx):
    if not ctx.param('warped.enabled'):
        return np.full(ctx.shape,-2.)
    return np.clip(ctx.noise('nether/warped-region',ctx.param('warped.biome_scale'),octaves=2),-1,1)


def add_pillars(ctx, base):
    if not (ctx.param('soul.enabled') and ctx.param('soul.pillars_enabled')
            and ctx.param('soul.pillar_density') > 0):
        return base
    plan = ctx.resource('soul_pillars')
    mask = plan.mask(ctx.x, ctx.y, ctx.z, resources=ctx.resources)
    return np.where(mask, np.maximum(base, 1), base).astype(np.float32)


@field('basalt_noise', res=8)
def basalt_noise(ctx):
    return ctx.noise('nether/basalt-region', ctx.param('basalt.biome_scale'), octaves=2)


@field('basalt_region', deps=('basalt_noise',))
def basalt_region(ctx, noise):
    return np.clip(noise, -1, 1) if ctx.param('basalt.enabled') else np.full(ctx.shape, -2.)


@density('nether_pillared', deps=('nether_base',), resources=('soul_pillars',))
def pillared(ctx, base):
    return add_pillars(ctx, base)


@density('nether_solid', deps=('nether_base',), resources=('soul_pillars', 'basalt_pools', 'basalt_columns'))
def with_deltas(ctx, base):
    result = add_pillars(ctx, base)
    if not ctx.param('basalt.enabled'):
        return result
    if ctx.param('basalt.columns_density') > 0:
        added = ctx.resource('basalt_columns').mask(ctx.x, ctx.y, ctx.z, resources=ctx.resources)
        result = np.where(added, np.maximum(result, 1), result)
    if ctx.param('basalt.pools_enabled') and ctx.param('basalt.pools_density') > 0:
        carved = ctx.resource('basalt_pools').mask(ctx.x, ctx.y, ctx.z, resources=ctx.resources)
        result = np.where(carved, -1., result)
    return result.astype(np.float32, copy=False)
