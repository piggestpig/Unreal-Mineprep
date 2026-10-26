"""Colour existing visible rock cells in batches; never sample a dense volume."""
import numpy as np
from ...core.noise3 import fbm3
from ...core.noise import fbm2
from .minerals import paint


def soul_patch(ctx, selected):
    """Tile-local float64 XZ noise; reuse across cave layers without quantizing."""
    x,z = ctx.x[selected],ctx.z[selected]
    cache = getattr(ctx.resources,'_nether_soul_patch',None)
    if cache is not None:
        x0,z0,values = cache
        if x.min() >= x0 and z.min() >= z0 and x.max() < x0+values.shape[1] and z.max() < z0+values.shape[0]:
            return values[z-z0,x-x0]
    x0,z0 = int(ctx.x.min()),int(ctx.z.min())
    width,depth = int(ctx.x.max())-x0+1,int(ctx.z.max())-z0+1
    if ctx.resources is None or width*depth > 65536:
        ctx.record('soul_samples',len(x)*2)
        return fbm2(x/24,z/24,seed=ctx.seed,salt='nether/soul-surface',octaves=2)
    xx,zz = np.meshgrid(np.arange(x0,x0+width),np.arange(z0,z0+depth))
    values = fbm2(xx.ravel()/24,zz.ravel()/24,seed=ctx.seed,
                  salt='nether/soul-surface',octaves=2).reshape(depth,width)
    ctx.resources._nether_soul_patch = x0,z0,values
    ctx.record('soul_samples',values.size*2)
    return values[z-z0,x-x0]


def sample(ctx):
    result = ctx.materials.copy()
    p = ctx.params
    if p['nether.rock_variation']:
        noise = fbm3(ctx.x / 24, ctx.y / 12, ctx.z / 24,
                     seed=ctx.seed, salt='nether/materials', octaves=2)
        low = ctx.y < (p['nether.floor_y'] + p['nether.blackstone_depth'] + 8 * noise)
        result[low & (noise > .12)] = ctx.block_index['blackstone']
        if p['nether.basalt_enabled']:
            result[~low & (noise > .30)] = ctx.block_index['basalt']
        ctx.record('rock_noise_samples', len(result) * 2)
    if p['soul.enabled']:
        valley = ctx.biomes == next(i for i,b in enumerate(ctx.pack.biomes) if b.id == 'soul_sand_valley')
        # Ignore physical exterior air; the depths were sampled before output cuts.
        floor = (ctx.floor_depth < p['soul.surface_depth']) & (ctx.y+ctx.floor_depth+1 < p['nether.roof_y'])
        ceiling = (ctx.ceiling_depth < p['soul.surface_depth']) & (ctx.y-ctx.ceiling_depth-1 >= p['nether.floor_y'])
        selected = np.flatnonzero(valley & (floor | ceiling))
        if len(selected):
            patches = soul_patch(ctx,selected)
            result[selected] = np.where(patches > .08, ctx.block_index['soul_sand'], ctx.block_index['soul_soil'])
            if p['nether.lava_enabled']:
                shore = ((abs(ctx.y[selected]-p['world.sea_level']) <= 2) & floor[selected] & (patches < -.18))
                result[selected[shore]] = ctx.block_index['gravel']
        if p['soul.pillars_enabled'] and p['soul.pillar_density'] > 0:
            plan = ctx.resources.get('soul_pillars')
            added = plan.mask(ctx.x,ctx.y,ctx.z,resources=ctx.resources)
            result[added] = ctx.block_index['basalt']
    if p['basalt.enabled']:
        delta = ctx.biomes == next(i for i,b in enumerate(ctx.pack.biomes) if b.id == 'basalt_deltas')
        selected = np.flatnonzero(delta & (ctx.carved_faces != 0))
        if len(selected):
            patch = fbm2(ctx.x[selected]/12, ctx.z[selected]/12, seed=ctx.seed,
                         salt='nether/basalt-surface', octaves=2)
            floor = (ctx.carved_faces[selected] & 8) != 0
            result[selected] = ctx.block_index['basalt']
            result[selected[floor & (patch > -.05)]] = ctx.block_index['blackstone']
            result[selected[~floor & (patch < -.4)]] = ctx.block_index['netherrack']
        if p['basalt.columns_density'] > 0:
            added = ctx.resources.get('basalt_columns').mask(ctx.x,ctx.y,ctx.z,resources=ctx.resources)
            result[added] = ctx.block_index['basalt']
    result = paint(ctx,result)
    if p['crimson.enabled']:
        from .crimson import floor_allowed
        forest = ctx.biomes == next(i for i,b in enumerate(ctx.pack.biomes) if b.id == 'crimson_forest')
        floor = ((ctx.carved_faces & 8) != 0) & floor_allowed(p,ctx.y)
        result[forest & floor] = ctx.block_index['crimson_nylium']
    if p['warped.enabled']:
        from .fungi import floor_allowed
        forest = ctx.biomes == next(i for i,b in enumerate(ctx.pack.biomes) if b.id == 'warped_forest')
        if forest.any():
            floor = ((ctx.carved_faces & 8) != 0) & floor_allowed(p,ctx.y)
            result[forest & floor] = ctx.block_index['warped_nylium']
    if p['basalt.enabled'] and p['basalt.pools_enabled'] and p['basalt.pools_density'] > 0:
        rim = ctx.resources.get('basalt_pools').mask(ctx.x,ctx.y,ctx.z,resources=ctx.resources,rim=True)
        result[rim] = ctx.block_index['magma_block']
    return result.astype(np.uint16, copy=False)
