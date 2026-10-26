"""Keep the paths and buildings clear while retaining vanilla's scenery."""
import numpy as np
from ...core.fields import field
from ...core.noise import perlin2
from ...core.postprocess import SurfacePatch
from .layout import clearings, road_distance, support_distance, worn_ground


@field('outpost_clearing')
def clearing(ctx):
    return clearings(ctx.x, ctx.z, ctx.param('outpost.size'), ctx.seed).astype(float)


@field('outpost_path')
def path(ctx):
    return worn_ground(ctx.x, ctx.z, ctx.param('outpost.size'), ctx.seed).astype(float)


def yard_grass(ctx, surfaces):
    """Sparse native grass in the tree-free yard, away from steps and doorways."""
    eligible = ((surfaces.kind == 0) & surfaces.sky_open &
                (surfaces.types == ctx.block_ids['outpost_grass']))
    points = surfaces.xyz[eligible]
    x, z = points[:, 0], points[:, 2]
    size = ctx.params['outpost.size']
    d = support_distance(x, z, size)
    noise = perlin2(x*1.7, z*1.7, seed=ctx.seed, salt='outpost/yard-grass')
    use = ((d > 1.5) & (road_distance(x, z, size) > 3) &
           (noise > .52-.12*np.minimum(d/10, 1)))
    added = points[use].copy()
    added[:, 1] += 1
    added = added[~ctx.query.occupied(added)]
    return SurfacePatch(added, np.full(len(added), ctx.block_ids['short_grass'], np.uint16),
                        np.zeros(len(added), bool))
