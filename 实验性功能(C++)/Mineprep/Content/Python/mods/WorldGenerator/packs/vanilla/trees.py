"""Finite oak, birch, spruce and acacia variants; no game updates."""
from functools import lru_cache
import numpy as np
from ...core.features import FeatureBatch
from ...core.templates import tree_template, TemplateBatch, rotate


@lru_cache(maxsize=128)
def _template(height, variant, kind, layers, block_ids, block_defs):
    offsets,kinds=_shape(height,variant,kind)
    name = f'savanna_acacia_h{height}' if kind == 'acacia' and not layers else f'{kind}_h{height}_v{variant}_snow{layers}'
    return tree_template(name,
                         offsets[kinds==0], offsets[kinds==1],
                         trunk_block=kind+'_log', foliage_block=kind+'_leaves',
                         block_ids=dict(block_ids), block_defs=dict(block_defs),
                         snow_layer=layers)


def _templates(ctx,anchors,keys,kind,height_param):
    height=int(ctx.params[height_param]);layers=0
    if kind != 'acacia' and ctx.params['cold.enabled'] and ctx.params['cold.canopy']:layers=int(ctx.params['cold.snow_layers'])
    ids=tuple(ctx.block_ids.items())
    names=[kind+'_log',kind+'_leaves']+(['snow_layer_'+str(layers)] if layers else [])
    sources=tuple((n,ctx.block_defs[n]) for n in names)
    low = height if kind == 'acacia' else height-1
    definitions=[_template(low,0,kind,0,ids,sources),
                 _template(height+1,4,kind,0,ids,sources)]
    selected=(keys%np.uint64(2)).astype(np.int32)
    if layers:
        definitions.extend((_template(height-1,0,kind,layers,ids,sources),
                            _template(height+1,4,kind,layers,ids,sources)))
        r=ctx.reference
        cold=r.get('snow_cover')[anchors[:,2]-int(r.z[0,0]),anchors[:,0]-int(r.x[0,0])]>=.5
        selected+=cold.astype(np.int32)*2
    return TemplateBatch(tuple(definitions),selected,np.arange(len(anchors),dtype=np.int32),
                         ((keys>>np.uint64(8))%np.uint64(4)).astype(np.uint8))


@lru_cache(maxsize=512)
def _shape(height, variant, kind='oak'):
    if kind == 'acacia':
        trunk, foliage = [], []
        previous = 0
        for y in range(height):
            x = min(2, max(0, y - (height - 3)))
            trunk.extend((xx, y, 0) for xx in range(previous, x + 1))
            previous = x
        trunk.extend((x, height - 2, 0) for x in range(-1, 2))
        trunk.append((-1, height - 2, 1))
        for cx, cz, y, radius in ((2, 0, height, 3), (2, 0, height + 1, 2),
                                  (-1, 1, height - 1, 2), (-1, 1, height, 1)):
            foliage.extend((cx + x, y, cz + z)
                           for x in range(-radius, radius + 1)
                           for z in range(-radius, radius + 1)
                           if abs(x) + abs(z) <= radius + 1)
        points = np.asarray(trunk + foliage, np.int32)
        _, first = np.unique(points, axis=0, return_index=True)
        first.sort()  # input order and trunk precedence match tree_template
        offsets = rotate(points[first], variant % 4)
        kinds = (first >= len(trunk)).astype(np.uint16)
        offsets.setflags(write=False)
        kinds.setflags(write=False)
        return offsets, kinds
    radius = 3 if kind == 'oak' and height >= 7 else 2
    trunk = np.column_stack((np.zeros(height, np.int32), np.arange(height, dtype=np.int32), np.zeros(height, np.int32)))
    parts = [trunk]
    if kind == 'spruce':
        layers = []
        for y in range(max(1, height//3), height+2):
            r = min(3, (height+2-y)//3)
            if r > 1 and (y+variant) % 3 == 1:
                r -= 1
            layers.append((y, r))
    else:
        layers = ((height-2, radius), (height-1, radius), (height, 1), (height+1, 1))
    for layer, (y, r) in enumerate(layers):
        x, z = np.meshgrid(np.arange(-r, r+1), np.arange(-r, r+1))
        x, z = x.ravel(), z.ravel()
        corners = (np.abs(x) == r) & (np.abs(z) == r)
        omit = (corners & (r > 0) if kind == 'spruce' else
                corners & ((y == height+1) | (((x > 0).astype(int) + 2*(z > 0) + layer + variant//4) % 2 == 0)))
        use = ~omit & ~((x == 0) & (z == 0) & (y < height))
        parts.append(np.column_stack((x[use], np.full(use.sum(), y), z[use])).astype(np.int32))
    offsets = np.concatenate(parts)
    for _ in range(variant % 4):
        offsets[:, [0, 2]] = offsets[:, [2, 0]] * (1, -1)
    kinds = np.r_[np.zeros(height, np.uint16), np.ones(len(offsets)-height, np.uint16)]
    offsets.setflags(write=False); kinds.setflags(write=False)
    return offsets, kinds


def _build(ctx, anchors, keys, kind, height_param):
    # Blocks.bake resolves native model names. Preserve descendant mesh/JSON
    # overrides and transformed models through their existing voxel path.
    if (ctx.params.get('vegetation.simplified',False) and ctx.block_defs is not None and
            all(ctx.block_defs[kind+s].source=='builtin' and ctx.block_defs[kind+s].shape=='cube'
                and ctx.block_defs[kind+s].scale==(1.,1.,1.) and ctx.block_defs[kind+s].offset==(0.,0.,0.)
                for s in ('_log','_leaves'))):
        return _templates(ctx,anchors,keys,kind,height_param)
    parts, kinds, owners = [], [], []
    ids = np.array([ctx.block_ids[kind+'_log'], ctx.block_ids[kind+'_leaves']], np.uint16)
    for i, key in enumerate(keys):
        variation = int(key % np.uint64(2)) if kind == 'acacia' else int(key % np.uint64(3)) - 1
        height = int(ctx.params[height_param]) + variation
        offsets, types = _shape(height, int((key >> np.uint64(8)) % np.uint64(16)), kind)
        parts.append(offsets); kinds.append(ids[types]); owners.append(np.full(len(offsets), i, np.int32))
    if not parts:
        return FeatureBatch(np.empty((0, 3), np.int32), np.empty(0, np.uint16), np.empty(0, np.int32))
    return FeatureBatch(np.concatenate(parts), np.concatenate(kinds), np.concatenate(owners))


def build(ctx, anchors, keys):
    return _build(ctx, anchors, keys, 'oak', 'trees.height')


def birch(ctx, anchors, keys):
    return _build(ctx, anchors, keys, 'birch', 'trees.birch_height')


def spruce(ctx, anchors, keys):
    return _build(ctx, anchors, keys, 'spruce', 'trees.spruce_height')


def acacia(ctx, anchors, keys):
    return _build(ctx, anchors, keys, 'acacia', 'trees.acacia_height')
