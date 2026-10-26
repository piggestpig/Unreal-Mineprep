"""Surface fields and wildflowers/grass for the refined Valley Outpost."""
import numpy as np
from ...core.fields import field
from ...core.noise import perlin2
from ...core.postprocess import SurfacePatch
from .layout import clearings, river_x, road_distance, support_distance, worn_ground


@field('outpost_clearing')
def clearing(ctx):
    return clearings(ctx.x, ctx.z, ctx.param('outpost.size'), ctx.seed).astype(float)


@field('outpost_path_core')
def path_core(ctx):
    core, _ = worn_ground(ctx.x, ctx.z, ctx.param('outpost.size'), ctx.seed)
    return core.astype(float)


@field('outpost_path_edge')
def path_edge(ctx):
    _, fringe = worn_ground(ctx.x, ctx.z, ctx.param('outpost.size'), ctx.seed)
    return fringe.astype(float)


@field('outpost_shore', deps=('height',))
def shore(ctx, h):
    size = ctx.param('outpost.size')
    dist = np.abs(ctx.x - river_x(ctx.z, size))
    noise = perlin2(ctx.x/5, ctx.z/5, seed=ctx.seed, salt='outpost/shore')
    mask = (dist < max(4.2, size*.030) + 4.5 + 1.5*noise) & (h >= 30.5) & (h <= 34.2) & (np.abs(ctx.z) > 5)
    return mask.astype(float)


@field('outpost_cliff', deps=('height', 'slope'))
def cliff(ctx, h, slope):
    noise = perlin2(ctx.x/8, ctx.z/8, seed=ctx.seed, salt='outpost/cliff')
    return ((h > 50 + 4*noise) & (slope > 1.18)).astype(float)


@field('outpost_alpine', deps=('height', 'slope'))
def alpine(ctx, h, slope):
    noise = perlin2(ctx.x/9, ctx.z/9, seed=ctx.seed, salt='outpost/alpine')
    return ((h > 78 + 5*noise) & (slope <= 1.35)).astype(float)


def yard_grass(ctx, surfaces):
    """Natural meadow grass in the clearing, framing roads and buildings without blocking steps."""
    eligible = ((surfaces.kind == 0) & surfaces.sky_open &
                (surfaces.types == ctx.block_ids['outpost_grass']))
    points = surfaces.xyz[eligible]
    if not len(points):
        return SurfacePatch(np.empty((0, 3), np.int32), np.empty(0, np.uint16), np.empty(0, bool))
    x, z = points[:, 0], points[:, 2]
    size = ctx.params['outpost.size']
    d = support_distance(x, z, size)
    rd = road_distance(x, z, size, ctx.seed)
    noise = perlin2(x*1.5, z*1.5, seed=ctx.seed, salt='outpost/yard-grass')
    bridge = (np.abs(x) <= 21) & (np.abs(z) <= 6)
    use = ((d > 1.8) & (rd > 3.2) & ~bridge &
           (noise > .46 - .14*np.minimum(d/10, 1)))
    added = points[use].copy()
    added[:, 1] += 1
    added = added[~ctx.query.occupied(added)]
    return SurfacePatch(added, np.full(len(added), ctx.block_ids['short_grass'], np.uint16),
                        np.zeros(len(added), bool))
