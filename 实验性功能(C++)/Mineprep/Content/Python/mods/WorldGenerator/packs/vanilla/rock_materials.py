"""Animation-oriented rocks and optional shared-field ore patches; no buried veins."""
from time import perf_counter
import numpy as np
from ...core.noise3 import fbm3, perlin3, hash01

ORES = ('coal','iron','copper','gold','redstone','lapis','diamond','emerald')


def sample(ctx):
    result = ctx.materials.copy()
    p, ids = ctx.params, ctx.block_index
    if not p['caves.enabled']:
        return result
    host = np.isin(result,[ids['stone'],ids['deepslate']]) & (ctx.depth > p['surface.soil_depth'])
    index = np.flatnonzero(host)
    if not len(index):
        return result
    x,y,z,depth = (v[index] for v in (ctx.x,ctx.y,ctx.z,ctx.depth))
    if p['cave_materials.rocks']:
        started = perf_counter()
        scale = p['cave_materials.patch_scale']
        noise = fbm3(x/scale,y/(scale*.7),z/scale,seed=ctx.seed,salt='rocks/patch',octaves=2)
        ctx.record('rock_noise_samples',len(index)*2)
        ctx.record('rock_noise_seconds',perf_counter()-started)
        # The parameter marks the start, not the centre, of the transition.
        transition = (np.clip(noise,-1,1)+1)*.5*p['cave_materials.transition']
        deep = depth >= p['cave_materials.deep_depth'] + transition
        result[index[deep]] = ids['deepslate']
        strength = p['cave_materials.variation']
        threshold = .5-strength*.6
        patch = np.abs(noise) > threshold if strength else np.zeros(len(index),bool)
        # Smooth field bands define every rock boundary; no hard lattice palette seams.
        kind = np.where(np.abs(noise) > threshold+.1,2,np.where(noise < 0,1,0))
        rock_ids = np.array([ids['andesite'],ids['granite'],ids['diorite']],np.uint16)
        result[index[patch & ~deep]] = rock_ids[kind[patch & ~deep]]
        result[index[patch & deep]] = ids['tuff']
    if not p['ores.enabled'] or not p['ores.amount']:
        return result
    weights = np.array([p[f'ores.{name}.weight'] if p[f'ores.{name}.enabled'] else 0. for name in ORES])
    if not weights.any():
        return result
    # One noise field for all ores, only over the remaining sparse hosts.
    eligible = np.isin(result[index],[ids['stone'],ids['deepslate']])
    index=index[eligible]
    if not len(index):
        return result
    x,y,z,depth = (v[index] for v in (ctx.x,ctx.y,ctx.z,ctx.depth))
    started = perf_counter()
    scale = p['ores.cluster_scale']
    noise = perlin3(x/scale,y/scale,z/scale,seed=ctx.seed,salt='ores/patch')
    ctx.record('ore_noise_samples',len(index))
    ctx.record('ore_noise_seconds',perf_counter()-started)
    index = index[noise > .5-.4*p['ores.amount']]
    if not len(index):
        return result
    depth=ctx.depth[index]
    # A small N-by-8 table, allocated for ore patches only; no per-kind noise.
    allowed = np.ones((len(index),len(ORES)),bool)
    allowed[:,0] = depth < 64
    allowed[:,2] = depth < 48
    allowed[:,3] = depth >= 24
    allowed[:,4] = depth >= 40
    allowed[:,5] = depth >= 24
    allowed[:,6] = depth >= 48
    mountains = [i for i,b in enumerate(ctx.pack.biomes) if b.id=='mountains']
    allowed[:,7] = np.isin(ctx.biomes[index],mountains)
    cumulative = np.cumsum(allowed*weights,axis=1)
    total=cumulative[:,-1]
    valid=total>0
    index,cumulative,total=index[valid],cumulative[valid],total[valid]
    cell=[np.floor(v[index]/(scale*2)).astype(np.int64) for v in (ctx.x,ctx.y,ctx.z)]
    draw=hash01(*cell,ctx.seed,'ores/kind')*total
    kind=np.sum(draw[:,None]>=cumulative,axis=1)
    ctx.record('ore_kind_samples',len(index))
    normal=np.array([ids[name+'_ore'] for name in ORES],np.uint16)
    deep=np.array([ids['deepslate_'+name+'_ore'] for name in ORES],np.uint16)
    result[index]=np.where(result[index]==ids['deepslate'],deep[kind],normal[kind])
    ctx.record('ore_cells',len(index))
    return result
