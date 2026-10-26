"""Sparse upward columns on real warped floors; one physical segment per XZ."""
from time import perf_counter
import numpy as np
from ...core.data import check_cancel
from ...core.features import FeatureBatch
from ...core.volume_features import Anchors
from .fungi import floor_allowed


def length(key):
    rng = np.random.default_rng(int(key))
    group = int(rng.integers(15))
    return int(rng.integers(1,9)) if group < 10 else int(rng.integers(2,17)) if group < 12 else 1


def floors(ctx, rock):
    p = ctx.params
    lo,hi = p['nether.floor_y'],p['nether.roof_y']
    return [(lo+int(a),lo+int(b)) for a,b in ctx.query.air_runs(rock)
            if a > 0 and floor_allowed(p,lo+int(a)-1)]


def place(ctx, xz, keys):
    start = perf_counter()
    p = ctx.params
    rock = ctx.query.profiles(xz,p['nether.floor_y'],p['nether.roof_y'])
    roots,owners = [],[]
    for i,key in enumerate(keys):
        check_cancel(getattr(ctx.resources,'cancel_event',None))
        runs = floors(ctx,rock[:,i])
        if runs:
            bottom,_ = runs[(int(key)>>16)%len(runs)]
            roots.append((xz[i,0],bottom,xz[i,1]));owners.append(i)
    ctx.resources.report.add('volume_twisting_vines_candidates',len(xz))
    ctx.resources.report.add('volume_twisting_vines_anchors',len(roots))
    ctx.resources.report.add('volume_twisting_vines_query_seconds',perf_counter()-start)
    return Anchors(np.asarray(roots,np.int64).reshape(-1,3),np.asarray(owners,np.intp),
                   np.full(len(roots),ctx.block_ids['warped_nylium'],np.uint16),np.zeros(len(roots)))


def build(ctx, anchors, keys):
    start = perf_counter()
    p = ctx.params
    rock = ctx.query.profiles(anchors[:,(0,2)],p['nether.floor_y'],p['nether.roof_y'])
    points,types,owners = [],[],[]
    for i,(anchor,key) in enumerate(zip(anchors,keys)):
        check_cancel(getattr(ctx.query.resources,'cancel_event',None))
        for bottom,top in floors(ctx,rock[:,i]):
            if bottom != anchor[1]:
                continue
            count = min(length(key),top-bottom)
            offsets = np.zeros((count,3),np.int32);offsets[:,1] = np.arange(count)
            kinds = np.full(count,ctx.block_ids['twisting_vines_plant'],np.uint16)
            kinds[-1] = ctx.block_ids['twisting_vines']
            points.append(offsets);types.append(kinds);owners.append(np.full(count,i,np.int32))
            break
    ctx.query.resources.report.add('volume_twisting_vines_build_seconds',perf_counter()-start)
    return FeatureBatch(np.concatenate(points) if points else np.empty((0,3),np.int32),
                        np.concatenate(types) if types else np.empty(0,np.uint16),
                        np.concatenate(owners) if owners else np.empty(0,np.int32))
