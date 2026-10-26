"""Shared Nether fungus shapes, physical anchors and existing batch output."""
from functools import lru_cache
from time import perf_counter
import warnings
import numpy as np
from ...core.data import check_cancel
from ...core.features import FeatureBatch
from ...core.templates import TemplateDefinition, TemplateBatch, rotate
from ...core.volume_features import Anchors

# ID, total height, lower cap radius, thick stem, hat depth, weight.
VARIANTS = (('small',5,2,False,2,20), ('regular',8,2,False,4,30),
            ('high',11,2,False,5,20), ('wide',13,3,False,7,16),
            ('slender',21,3,False,9,8), ('thick',13,3,True,6,6))


def floor_allowed(params, y):
    """The same physical, crop-independent soil rule for materials and anchors."""
    lo,hi = params['nether.floor_y'],params['nether.roof_y']
    level = int(np.floor(params['world.sea_level']))
    minimum = level+1 if params['nether.lava_enabled'] and lo <= level and level+1 < hi else lo
    return (np.asarray(y) >= minimum) & (np.asarray(y)+1 < hi)


def shape(height, radius, thick, seed, hat_depth=None, *, organic=False, vines=True):
    """MC-style bottom-up drops, porous cap, connected stem and hanging vines."""
    rng = np.random.default_rng(int(seed))
    h = int(height)-1
    depth = min(h, int(rng.integers(0,1+h//3))+5 if hat_depth is None else hat_depth)
    bottom = max(1,h-depth)
    cells = {}
    stem_radius = int(thick)
    for x in range(-stem_radius,stem_radius+1):
        for z in range(-stem_radius,stem_radius+1):
            for y in range(h):
                if x*z == 0 or (y > 0 and rng.random() < .1):
                    cells[x,y,z] = 0
    # A missing strip through the skirt breaks long, flat side silhouettes.
    notch_side = int(rng.integers(4))
    notch_at = int(rng.integers(-1,2))
    notch_top = min(h-1,bottom+int(rng.integers(2,5)))
    if organic:
        center_x,center_z = map(int,rng.integers(-1,2,size=2))
        second_side = (notch_side+int(rng.integers(1,4)))%4
        second_at = int(rng.integers(-1,2))
        drop_layers = min(3,max(1,depth//2))
    else:
        center_x = center_z = 0
        drop_layers = 2
    for y in range(bottom,h+1):
        r = 1 if y == h else 2
        if radius > 2 and y < bottom+4:
            r = radius
        r += int(thick)
        if organic:
            # Off-centre, rounded layers with unequal axes avoid a square tube.
            minimum = 1 if y == h else 2
            rx = max(minimum,r-int(rng.random()<.25))
            rz = max(minimum,r-int(rng.random()<.25))
            cx = int(np.clip(center_x,-4+rx,4-rx))
            cz = int(np.clip(center_z,-4+rz,4-rz))
        else:
            rx = rz = r
            cx = cz = 0
        for x in range(cx-rx,cx+rx+1):
            for z in range(cz-rz,cz+rz+1):
                point = x,y,z
                if point in cells:
                    continue
                u,v = x-cx,z-cz
                if organic and (u/(rx+.45))**2+(v/(rz+.45))**2 > 1.05:
                    continue
                edge = abs(u)==rx or abs(v)==rz
                corner = abs(u)==rx and abs(v)==rz
                inside = not edge and y != h
                notch = ((u == (-rx if notch_side == 0 else rx) and v == notch_at)
                         if notch_side < 2 else
                         (v == (-rz if notch_side == 2 else rz) and u == notch_at))
                if organic and y < h-1:
                    notch |= ((u == (-rx if second_side == 0 else rx) and v == second_at)
                              if second_side < 2 else
                              (v == (-rz if second_side == 2 else rz) and u == second_at))
                if notch and y < notch_top:
                    continue
                if organic and y >= bottom+drop_layers and (u==0 or v==0):
                    # Thin ribs keep broad, uneven lobes attached even when
                    # neighbouring layers have different extents and holes.
                    keep = True
                elif y == h-1:
                    # A single shoulder joins the narrow roof to its wider
                    # skirt; the lower layers remain broken and asymmetric.
                    keep = not corner or rng.random() < .65
                elif y < bottom+drop_layers:
                    # Source grows these from below, rather than filling every
                    # column down from the roof into an almost complete box.
                    keep = not inside and ((x,y-1,z) in cells or rng.random()<.15)
                else:
                    light = .1 if inside else .01 if corner else .0005
                    keep = (.45 if organic else .2) if inside else .7 if corner else .98
                    if organic and edge:
                        keep = .78
                    if rng.random() < light:
                        cells[point] = 2
                        continue
                    keep = rng.random() < keep
                if keep:
                    cells[point] = 1
    cells[0,h,0] = 1
    # Keep the cap attached to the stem, including sparse interior decorations.
    connected = {(0,0,0)}
    pending = [(0,0,0)]
    while pending:
        x,y,z = pending.pop()
        for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
            point = x+dx,y+dy,z+dz
            if point in cells and point not in connected:
                connected.add(point);pending.append(point)
    cells = {p:t for p,t in cells.items() if p in connected}
    lights = [p for p,k in cells.items() if k == 1 and p[1] < h and (p[0],p[1]-1,p[2]) not in cells]
    if lights and 2 not in cells.values():
        cells[lights[len(lights)//2]] = 2
    # Vines share the tree recipe/model. Keep tips above the root plane,
    # so only the real stem footprint requires terrain support.
    starts = [p for p,k in cells.items() if k == 1 and p[1] > 1 and (p[0],p[1]-1,p[2]) not in cells] if vines else []
    if starts:
        chosen = [p for p in starts if rng.random() < .09]
        if not chosen:
            chosen = [starts[int(rng.integers(len(starts)))]]
        for x,y,z in chosen[:8]:
            length = int(rng.integers(1,6))*(2 if rng.integers(7)==0 else 1)
            strand = []
            for dy in range(1,min(length+1,y)):
                point = x,y-dy,z
                if point in cells:
                    break
                strand.append(point)
            for point in strand:
                cells[point] = 4
            if strand:
                cells[strand[-1]] = 3
    points = np.asarray(tuple(cells),np.int32)
    kinds = np.fromiter(cells.values(),np.uint16)
    points.setflags(write=False);kinds.setflags(write=False)
    return points,kinds


def variant(key):
    value = int(key)%100
    return int(np.searchsorted(np.cumsum([v[5] for v in VARIANTS]),value,side='right'))


def template_supported(block_defs, blocks):
    return all(block_defs[n].source == 'builtin' and block_defs[n].shape == ('cube' if i<3 else 'decor')
               and block_defs[n].scale == (1.,1.,1.) and block_defs[n].offset == (0.,0.,0.)
               for i,n in enumerate(blocks))


@lru_cache(maxsize=48)
def template(index, definitions, *, blocks, prefix, shape_seed, vines):
    sources = dict(definitions)
    name,height,radius,thick,depth,_ = VARIANTS[index]
    points,kinds = shape(height,radius,thick,shape_seed+index,depth,vines=vines)
    types = np.asarray([sources[blocks[int(k)]][0] for k in kinds],np.uint16)
    cells = tuple((*map(int,p),sources[blocks[int(k)]][1].value,()) for p,k in zip(points,kinds))
    boxes = []
    for mask in (kinds==0, (kinds!=0)&(points[:,1] < height-depth+2),
                 (kinds!=0)&(points[:,1] >= height-depth+2)):
        if mask.any():
            boxes.append([points[mask].min(0),points[mask].max(0)+1])
    return TemplateDefinition(prefix+'_'+name,points,types,np.asarray(boxes,np.int32),cells,two_sided=False,scale_jitter=True)


def library(ctx, *, blocks, prefix, shape_seed, vines):
    definitions = tuple((n,(ctx.block_ids[n],ctx.pack.block_defs[n])) for n in blocks)
    return tuple(template(i,definitions,blocks=blocks,prefix=prefix,shape_seed=shape_seed,vines=vines)
                 for i in range(len(VARIANTS)))


def shape_parameters(key):
    """Cheap candidate dimensions; do not construct rejected procedural trees."""
    rng = np.random.default_rng(int(key))
    stem_height = int(rng.integers(4,14))
    if rng.integers(12) == 0:
        stem_height *= 2
    thick = rng.random() < .06
    depth = min(stem_height-1,max(2,int(stem_height*rng.uniform(.35,.60))))
    radius = int(rng.integers(2,4)) if stem_height>=8 else 2
    return stem_height+1,radius,thick,int(rng.integers(2**63)),depth


def local_shape(params, key, block_defs, *, blocks, shape_seed, vines):
    if params['vegetation.simplified'] and template_supported(block_defs,blocks):
        i = variant(key)
        _,height,radius,thick,depth,_ = VARIANTS[i]
        return shape(height,radius,thick,shape_seed+i,depth,vines=vines)
    return shape(*shape_parameters(key),organic=True,vines=vines)


def place(ctx, xz, keys, *, blocks, prefix, shape_seed, vines):
    start = perf_counter()
    p = ctx.params
    lo,hi = p['nether.floor_y'],p['nether.roof_y']
    rock = ctx.query.profiles(xz,lo,hi)
    templates = (library(ctx,blocks=blocks,prefix=prefix,shape_seed=shape_seed,vines=vines)
                 if p['vegetation.simplified'] and template_supported(ctx.pack.block_defs,blocks) else ())
    roots,owners,feet,foot_owners = [],[],[],[]
    for i,key in enumerate(keys):
        check_cancel(getattr(ctx.resources,'cancel_event',None))
        if templates:
            offsets = templates[variant(key)].orientations[(int(key)>>8)%4][0]
            height = int(offsets[:,1].max())+1
            base = offsets[offsets[:,1]==0]
        else:
            height,_,thick,_,_ = shape_parameters(key)
            base = np.array([(0,0,0)] if not thick else [(0,0,0),(-1,0,0),(1,0,0),(0,0,-1),(0,0,1)])
        runs = [(lo+int(a),lo+int(b)) for a,b in ctx.query.air_runs(rock[:,i])
                if a>0 and b<hi-lo and b-a>=height and floor_allowed(p,lo+int(a)-1)]
        if not runs:
            continue
        y,_ = runs[(int(key)>>16)%len(runs)]
        root = np.array([xz[i,0],y,xz[i,1]],np.int64)
        feet.append(base+root-[0,1,0]);foot_owners.append(np.full(len(base),len(roots),np.intp))
        roots.append(root);owners.append(i)
    roots = np.asarray(roots,np.int64).reshape(-1,3)
    owners = np.asarray(owners,np.intp)
    if feet:
        # One batched support query, rather than a DensityContext per candidate.
        supported = ctx.query.occupied(np.concatenate(feet))
        rejected = np.unique(np.concatenate(foot_owners)[~supported])
        keep = np.ones(len(roots),bool);keep[rejected] = False
        roots,owners = roots[keep],owners[keep]
    ctx.resources.report.add('volume_'+prefix+'_candidates',len(xz))
    ctx.resources.report.add('volume_'+prefix+'_anchors',len(roots))
    ctx.resources.report.add('volume_'+prefix+'_query_seconds',perf_counter()-start)
    return Anchors(roots,owners,
                   np.full(len(roots),ctx.block_ids[prefix+'_nylium'],np.uint16),np.zeros(len(roots)))


def build(ctx, anchors, keys, *, blocks, prefix, shape_seed, vines):
    start = perf_counter()
    if ctx.params['vegetation.simplified'] and template_supported(ctx.block_defs,blocks):
        definitions = tuple((n,(ctx.block_ids[n],ctx.block_defs[n])) for n in blocks)
        result = TemplateBatch(tuple(template(i,definitions,blocks=blocks,prefix=prefix,shape_seed=shape_seed,vines=vines)
                                     for i in range(len(VARIANTS))),
                               np.asarray([variant(k) for k in keys],np.int32),
                               np.arange(len(keys),dtype=np.int32),
                               ((keys>>np.uint64(8))%np.uint64(4)).astype(np.uint8))
    else:
        if ctx.params['vegetation.simplified']:
            label = '绯红菌' if prefix == 'crimson' else '诡异菌'
            warnings.warn(label+'来源不支持整株模板，已使用逐方块模式',RuntimeWarning,stacklevel=2)
        points,types,owners = [],[],[]
        ids = np.asarray([ctx.block_ids[n] for n in blocks],np.uint16)
        for owner,key in enumerate(keys):
            check_cancel(getattr(ctx.query.resources,'cancel_event',None))
            offsets,kinds = local_shape(ctx.params,key,ctx.block_defs,blocks=blocks,shape_seed=shape_seed,vines=vines)
            points.append(rotate(offsets,(int(key)>>8)%4))
            types.append(ids[kinds]);owners.append(np.full(len(offsets),owner,np.int32))
        result = FeatureBatch(np.concatenate(points),np.concatenate(types),np.concatenate(owners))
    ctx.query.resources.report.add('volume_'+prefix+'_build_seconds',perf_counter()-start)
    return result
