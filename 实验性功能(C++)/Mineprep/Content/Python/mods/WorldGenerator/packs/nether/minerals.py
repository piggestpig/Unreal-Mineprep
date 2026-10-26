"""Paint sparse, naturally exposed netherrack only; no buried ore volumes."""
from time import perf_counter
import numpy as np
from ...core.noise3 import perlin3,hash01


def paint(ctx, result):
    p,ids = ctx.params,ctx.block_index
    weights = np.array([p['ores.'+name+'.weight'] if p['ores.'+name+'.enabled'] else 0.
                        for name in ('quartz','gold')])
    ores = p['ores.enabled'] and p['ores.amount'] > 0 and weights.any()
    magma = p['nether.magma_enabled'] and p['nether.magma_amount'] > 0
    if not (ores or magma):
        return result
    eligible = (result == ids['netherrack']) & (ctx.carved_faces != 0)
    level = int(np.floor(p['world.sea_level']))
    if p['nether.lava_enabled'] and p['nether.floor_y'] <= level and level+1 < p['nether.roof_y']:
        eligible &= ctx.y > level
    if magma:
        selected = np.flatnonzero(eligible & (abs(ctx.y-p['world.sea_level']) <= 5)
                                  & ((ctx.carved_faces & 4) == 0))
        if len(selected):
            start = perf_counter()
            scale = p['nether.magma_scale']
            noise = perlin3(*(v[selected]/scale for v in (ctx.x,ctx.y,ctx.z)),
                            seed=ctx.seed,salt='nether/magma')
            chosen = selected[noise > .5-.4*p['nether.magma_amount']]
            result[chosen] = ids['magma_block']
            eligible[chosen] = False
            ctx.record('magma_noise_samples',len(selected))
            ctx.record('magma_cells',len(chosen))
            ctx.record('magma_seconds',perf_counter()-start)
    selected = np.flatnonzero(eligible) if ores else ()
    if len(selected):
        start = perf_counter()
        scale = p['ores.cluster_scale']
        noise = perlin3(*(v[selected]/scale for v in (ctx.x,ctx.y,ctx.z)),
                        seed=ctx.seed,salt='nether/ores')
        ctx.record('ore_noise_samples',len(selected))
        chosen = selected[noise > .5-.4*p['ores.amount']]
        cell = [np.floor(v[chosen]/(2*scale)).astype(np.int64) for v in (ctx.x,ctx.y,ctx.z)]
        draw = hash01(*cell,ctx.seed,'nether/ores/kind')*weights.sum()
        ctx.record('ore_kind_samples',len(chosen))
        # Thin quartz patches without reallocating them to gold or changing its positions.
        keep = (draw >= weights[0]) | (draw < weights[0]*p['ores.quartz.density'])
        chosen,draw = chosen[keep],draw[keep]
        palette = np.array([ids['nether_quartz_ore'],ids['nether_gold_ore']],np.uint16)
        result[chosen] = palette[(draw >= weights[0]).astype(np.intp)]
        ctx.record('ore_cells',len(chosen))
        ctx.record('ore_noise_seconds',perf_counter()-start)
    return result
