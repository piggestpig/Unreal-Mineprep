"""Compact bone silhouettes with bounded, physical foot extensions."""
from functools import lru_cache
import numpy as np
from mc_math import encode_rotation
from ...core.features import FeatureBatch
from ...core.templates import rotate
from ...core.volume_features import Anchors

NAMES = ('rib_cage','broken_ribs','spine','half_ribs','short_spine')
MAX_FOOT_FILL = 3


@lru_cache(maxsize=20)
def shape(variant, turn):
    cells = {}
    if variant in (2,4):
        for z in range(-4,5):
            cells[0,0,z] = 'z'
        for z in (-3,0,3):
            for x in (-2,-1,1,2):
                cells[x,0,z] = 'x'
    else:
        length = 3 if variant == 1 else 4
        for z in range(-length,length+1):
            cells[0,3,z] = 'z'
        for z in (-length+1,0,length-1):
            for side in (-1,1):
                for x,y in ((1,3),(2,3),(2,2),(3,2),(3,1),(3,0)):
                    if variant == 1 and side == 1 and z == 0 and y < 2:
                        continue
                    cells[side*x,y,z] = 'x' if y >= 3 else 'y'
    if variant == 3:
        cells = {p:a for p,a in cells.items() if p[0] > 0}
    elif variant == 4:
        cells = {p:a for p,a in cells.items() if p[2] <= 0}
    points = rotate(np.array(tuple(cells),np.int64),turn)
    axes = [({'x':'z','z':'x','y':'y'}[a] if turn%2 else a) for a in cells.values()]
    codes = {'y':0,'x':int(encode_rotation(pitch=90,yaw=0,roll=0)),
             'z':int(encode_rotation(pitch=0,yaw=0,roll=90))}
    rotations = np.array([codes[a] for a in axes],np.uint8)
    points.setflags(write=False); rotations.setflags(write=False)
    return points,rotations


def choice(key):
    key = int(key)
    return key%len(NAMES),(key >> 8)%4


def minimum_floor(params):
    lo,hi = params['nether.floor_y'],params['nether.roof_y']
    level = int(np.floor(params['world.sea_level']))
    return level+1 if params['nether.lava_enabled'] and lo <= level and level+1 < hi else lo+1


def place(ctx, xz, keys):
    p = ctx.params
    lo,hi = p['nether.floor_y'],p['nether.roof_y']
    minimum = minimum_floor(p)
    probes = (xz[:,None,:]+np.array([[0,0],[-1,0],[1,0],[0,-1],[0,1]])).reshape(-1,2)
    rock = ctx.query.profiles(probes,lo,hi).reshape(hi-lo,len(xz),5)
    roots,owners,slopes = [],[],[]
    ctx.resources.report.add('volume_candidates',len(xz))
    for i,(x,z) in enumerate(xz):
        offsets,_ = shape(*choice(keys[i]))
        height = int(offsets[:,1].max())+1
        start = lo+int((int(keys[i]) >> 16)%max(1,hi-lo-1))
        runs = [(int(a)+lo,int(b)+lo) for a,b in ctx.query.air_runs(rock[:,i,0])
                if a > 0 and b < hi-lo and b-a >= height and a+lo >= minimum and a+lo <= start]
        if not runs:
            ctx.resources.report.add('volume_no_floor',1)
            continue
        y = max(runs)[0]
        neighbour_heights = []
        for column in range(1,5):
            floors = [int(a)+lo for a,b in ctx.query.air_runs(rock[:,i,column]) if a > 0]
            neighbour_heights.append(min((abs(a-y) for a in floors),default=hi-lo))
        slope = max(neighbour_heights)
        if slope > 2:
            ctx.resources.report.add('volume_slope_rejected',1)
            continue
        footprint = offsets[offsets[:,1] == 0][:,(0,2)]+[x,z]
        lower,upper = max(lo,y-3),min(hi,y+4)
        foot_columns = ctx.query.profiles(footprint,lower,upper)
        floors = []
        for column in foot_columns.T:
            candidates = np.flatnonzero(column[:-1]&~column[1:])+lower+1
            if len(candidates):
                floors.append(int(candidates[np.argmin(abs(candidates-y))]))
        if len(floors) != len(footprint):
            ctx.resources.report.add('volume_support_rejected',1)
            continue
        anchor = np.array([x,max(floors),z],np.int64)
        if (min(floors) < minimum or max(floors)-min(floors) > MAX_FOOT_FILL
                or anchor[1]+height > hi):
            ctx.resources.report.add('volume_support_rejected',1)
            continue
        feet = np.column_stack((footprint[:,0],np.full(len(footprint),anchor[1]-1),footprint[:,1]))
        if not len(feet) or np.count_nonzero(ctx.query.occupied(feet))*3 < len(feet):
            ctx.resources.report.add('volume_support_rejected',1)
            continue
        roots.append(anchor);owners.append(i);slopes.append(slope)
    ctx.resources.report.add('volume_anchors',len(roots))
    return Anchors(np.asarray(roots,np.int64).reshape(-1,3),np.asarray(owners,np.intp),
                   np.full(len(roots),ctx.block_ids['netherrack'],np.uint16),np.asarray(slopes,float))


def grounded_shape(ctx, anchor, key):
    points,codes = shape(*choice(key))
    feet = points[points[:,1] == 0]
    steps = np.arange(1,MAX_FOOT_FILL+2)
    probes = feet[:,None,:]+anchor-np.column_stack((np.zeros(len(steps),int),steps,np.zeros(len(steps),int)))
    rock = ctx.query.occupied(probes.reshape(-1,3)).reshape(len(feet),len(steps))
    if not rock.any(axis=1).all():
        return None
    # Stop at the first physical solid. Only original ground feet are extended;
    # a broken rib ending above the base stays intentionally broken.
    first = rock.argmax(axis=1)
    take = np.arange(len(steps))[None,:] < first[:,None]
    extensions = probes[take]-anchor
    if len(extensions) and np.any(extensions[:,1]+anchor[1] < minimum_floor(ctx.params)):
        return None
    return (np.concatenate((points,extensions)),
            np.concatenate((codes,np.zeros(len(extensions),np.uint8))))


def build(ctx, anchors, keys):
    offsets,rotations,owners = [],[],[]
    for owner,key in enumerate(keys):
        result = grounded_shape(ctx,anchors[owner],key)
        if result is None:
            continue
        points,codes = result
        offsets.append(points);rotations.append(codes);owners.append(np.full(len(points),owner,np.int32))
    points = np.concatenate(offsets) if offsets else np.empty((0,3),np.int64)
    return FeatureBatch(points,np.full(len(points),ctx.block_ids['bone_block'],np.uint16),
                         np.concatenate(owners) if owners else np.empty(0,np.int32),
                         np.concatenate(rotations) if rotations else np.empty(0,np.uint8))
