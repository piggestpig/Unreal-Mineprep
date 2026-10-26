"""Crimson entrypoints retain the original seeds, materials and hanging vines."""
from . import fungi
from .fungi import VARIANTS, floor_allowed, shape, variant, shape_parameters

BLOCKS = ('crimson_stem', 'nether_wart_block', 'shroomlight', 'weeping_vines', 'weeping_vines_plant')
RECIPE = dict(blocks=BLOCKS,prefix='crimson',shape_seed=58100,vines=True)


def template_supported(block_defs):
    return fungi.template_supported(block_defs,BLOCKS)


def template(index, definitions):
    return fungi.template(index,definitions,**RECIPE)


def library(ctx):
    return fungi.library(ctx,**RECIPE)


def local_shape(params, key, block_defs):
    return fungi.local_shape(params,key,block_defs,blocks=BLOCKS,shape_seed=58100,vines=True)


def place(ctx, xz, keys):
    return fungi.place(ctx,xz,keys,**RECIPE)


def build(ctx, anchors, keys):
    return fungi.build(ctx,anchors,keys,**RECIPE)
