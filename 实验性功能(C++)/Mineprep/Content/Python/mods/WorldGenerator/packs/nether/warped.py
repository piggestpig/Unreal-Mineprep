"""Six independent warped fungi or richer voxel caps; no hanging vines."""
from . import fungi
from .fungi import VARIANTS, floor_allowed, shape, variant, shape_parameters

BLOCKS = ('warped_stem', 'warped_wart_block', 'shroomlight')
RECIPE = dict(blocks=BLOCKS,prefix='warped',shape_seed=59100,vines=False)


def template_supported(block_defs):
    return fungi.template_supported(block_defs,BLOCKS)


def template(index, definitions):
    return fungi.template(index,definitions,**RECIPE)


def library(ctx):
    return fungi.library(ctx,**RECIPE)


def local_shape(params, key, block_defs):
    return fungi.local_shape(params,key,block_defs,blocks=BLOCKS,shape_seed=59100,vines=False)


def place(ctx, xz, keys):
    return fungi.place(ctx,xz,keys,**RECIPE)


def build(ctx, anchors, keys):
    return fungi.build(ctx,anchors,keys,**RECIPE)
