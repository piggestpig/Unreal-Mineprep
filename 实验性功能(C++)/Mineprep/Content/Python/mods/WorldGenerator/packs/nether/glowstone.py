"""Small connected ceiling clusters with bounded growth and physical anchors."""
from time import perf_counter
import numpy as np
from ...core.features import FeatureBatch
from ...core.volume_features import Anchors

DIRECTIONS = ((-1,0,0),(1,0,0),(0,-1,0),(0,1,0),(0,0,-1),(0,0,1))


def shape(key):
    rng = np.random.default_rng(int(key))
    length = int(rng.integers(4,8))
    target = int(rng.integers(24,65))
    cells = {(0,-y,0) for y in range(length)}
    frontier = set()
    def neighbours(p):
        return [tuple(a+b for a,b in zip(p,d)) for d in DIRECTIONS]
    def allowed(p):
        x,y,z = p
        depth = -y
        radius = 0 if depth == 0 else (1 if depth == length-1 else 3)
        return 0 <= depth < length and abs(x)+abs(z) <= radius
    for p in sorted(cells):
        frontier.update(q for q in neighbours(p) if q not in cells and allowed(q))
    for attempt in range(256):
        if len(cells) >= target or not frontier:
            break
        ordered = sorted(frontier)
        p = ordered[int(rng.integers(len(ordered)))];frontier.remove(p)
        adjacent = [q for q in neighbours(p) if q in cells]
        # Keep the cluster open and branched instead of growing a buried solid bulb.
        if len(adjacent) > 2 or any(sum(n in cells for n in neighbours(q)) >= 4 for q in adjacent):
            continue
        cells.add(p)
        frontier.update(q for q in neighbours(p) if q not in cells and allowed(q))
    points = np.array(sorted(cells),np.int64)
    points.setflags(write=False)
    return points


def place(ctx, xz, keys):
    start = perf_counter()
    p = ctx.params
    lo,hi = p['nether.floor_y'],p['nether.roof_y']
    level = int(np.floor(p['world.sea_level']))
    minimum = level+1 if p['nether.lava_enabled'] and lo <= level and level+1 < hi else lo+1
    columns = ctx.query.profiles(xz,lo,hi)
    roots,owners = [],[]
    for i,(x,z) in enumerate(xz):
        runs = [(int(a),int(b)) for a,b in ctx.query.air_runs(columns[:,i])
                if a > 0 and b < hi-lo and b-a >= 12 and b+lo-7 >= minimum]
        if runs:
            a,b = runs[(int(keys[i]) >> 16)%len(runs)]
            roots.append((x,b+lo-1,z));owners.append(i)
    ctx.resources.report.add('volume_glowstone_candidates',len(xz))
    ctx.resources.report.add('volume_glowstone_anchors',len(roots))
    ctx.resources.report.add('volume_glowstone_seconds',perf_counter()-start)
    materials = np.full(len(roots),ctx.block_ids['netherrack'],np.uint16)
    if roots and p['basalt.enabled']:
        from .basalt import selected
        delta = selected(ctx.pack,p,ctx.seed,np.asarray(roots)[:,(0,2)],ctx.resources)
        materials[delta] = ctx.block_ids['basalt']
    return Anchors(np.asarray(roots,np.int64).reshape(-1,3),np.asarray(owners,np.intp),materials,np.zeros(len(roots)))


def build(ctx, anchors, keys):
    start = perf_counter()
    points,owners = [],[]
    for i,key in enumerate(keys):
        offsets = shape(key)
        points.append(offsets);owners.append(np.full(len(offsets),i,np.int32))
    offsets = np.concatenate(points) if points else np.empty((0,3),np.int64)
    ctx.query.resources.report.add('volume_glowstone_seconds',perf_counter()-start)
    return FeatureBatch(offsets,np.full(len(offsets),ctx.block_ids['glowstone'],np.uint16),
                        np.concatenate(owners) if owners else np.empty(0,np.int32))
