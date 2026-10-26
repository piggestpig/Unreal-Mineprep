"""Eight connected chorus trees, with whole-tree or native-cell output."""
from functools import lru_cache
import numpy as np

from ...core.templates import TemplateDefinition, TemplateBatch
from ...core.volume_features import Anchors


DIRECTIONS = {'west':(-1,0,0),'east':(1,0,0),'down':(0,-1,0),
              'up':(0,1,0),'north':(0,0,-1),'south':(0,0,1)}


def _tree_cells(height, seed):
    """Short lateral steps and recursive shoots, as in Minecraft chorus growth."""
    rng = np.random.default_rng(seed)
    horizontal = ((1,0), (0,1), (-1,0), (0,-1))
    stems,flowers = {(0,0,0)},set()

    def clear(point, parent=None):
        x,y,z = point
        return point not in stems|flowers and all(
            (x+dx,y,z+dz) == parent or (x+dx,y,z+dz) not in stems|flowers
            for dx,dz in horizontal)

    def grow(base, depth):
        x,y,z = base
        rise = min(int(rng.integers(2,6))+(depth==0),height-1-y)
        tip = base
        for step in range(1,rise+1):
            point = (x,y+step,z)
            if not clear(point):
                stems.remove(tip)
                flowers.add(tip)
                return
            stems.add(point)
            tip = point
        branched = False
        if tip[1] < height-1 and depth < 5:
            count = int(rng.integers(0,4))+(depth==0)
            for direction in rng.permutation(4)[:count]:
                dx,dz = horizontal[direction]
                point = (tip[0]+dx,tip[1],tip[2]+dz)
                below = (point[0],point[1]-1,point[2])
                if max(abs(point[0]),abs(point[2])) < 6 and below not in stems|flowers and clear(point,tip):
                    stems.add(point)
                    grow(point,depth+1)
                    branched = True
        if not branched:
            stems.remove(tip)
            flowers.add(tip)

    grow((0,0,0),0)
    return stems,flowers


@lru_cache(maxsize=8)
def templates(stem_id, flower_id, cellwise=False):
    result = []
    shapes = ((8,271),(10,292),(12,312),(14,328),(16,347),(18,373),(21,389),(24,410))
    for variant,(height,seed) in enumerate(shapes):
        stems,flowers = _tree_cells(height,seed)
        cells = stems|flowers
        points = np.array(sorted(cells),np.int32)
        types = np.array([flower_id if tuple(p) in flowers else stem_id for p in points],np.uint16)
        bake = []
        for point in points:
            p = tuple(map(int,point))
            if p in flowers:
                block,props = 'chorus_flower',(('age','0'),)
            else:
                block = 'chorus_plant'
                props = tuple(sorted((name,str(tuple(a+b for a,b in zip(p,d)) in cells or
                                                (p==(0,0,0) and name=='down')).lower())
                                     for name,d in DIRECTIONS.items()))
            bake.append((*p,block,props))
        bounds = np.array([[points.min(0),points.max(0)+1]],np.int32)
        result.append(TemplateDefinition('end_chorus_'+str(variant),points,types,bounds,tuple(bake),
                                         two_sided=False,cellwise=cellwise))
    return tuple(result)


def place(ctx, xz, keys):
    p = ctx.params
    lo = int(np.floor(p['end.height']-p['end.relief']-p['end.thickness']-24))
    hi = int(np.ceil(p['end.height']+p['end.relief']+24))
    offsets = np.array([[0,0],[-1,0],[1,0],[0,-1],[0,1]],np.int64)
    probes = (xz[:,None,:]+offsets).reshape(-1,2)
    columns = ctx.query.profiles(probes,lo,hi)
    tops = np.where(columns,np.arange(lo,hi)[:,None],lo-1).max(0).reshape(-1,5)
    slopes = .5*np.hypot(tops[:,2]-tops[:,1],tops[:,4]-tops[:,3])
    chosen = np.flatnonzero((tops[:,0]>=lo)&(tops[:,0]<hi-1)&(slopes<=p['chorus.max_slope']))
    roots = np.column_stack((xz[chosen,0],tops[chosen,0]+1,xz[chosen,1]))
    return Anchors(roots,chosen,np.full(len(chosen),ctx.block_ids['end_stone'],np.uint16),slopes[chosen])


def build(ctx, anchors, keys):
    models = templates(ctx.block_ids['chorus_plant'],ctx.block_ids['chorus_flower'],not ctx.params['chorus.whole_tree'])
    return TemplateBatch(models,(keys%np.uint64(len(models))).astype(np.int32),
                         np.arange(len(anchors),dtype=np.int32),
                         ((keys>>np.uint64(8))%np.uint64(4)).astype(np.uint8))
