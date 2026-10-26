"""Sparse submerged plants; kelp stems use the original plant/tip models."""
import numpy as np
from ...core.features import FeatureBatch


def build(ctx, anchors, keys):
    n = len(anchors)
    if ctx.feature.id == 'kelp':
        ceiling = ctx.param('aquatic.kelp_height')
        lengths = 2 + (keys % np.uint64(ceiling - 1)).astype(np.int32)
        lengths = np.maximum(0, np.minimum(lengths, ctx.water_depths)).astype(np.int32)
        names = ('kelp_plant', 'kelp')
    else:
        # Insufficient water rejects an entire two-cell owner in the core.
        lengths = np.where((keys >> np.uint64(8)) % np.uint64(5) < 2, 2, 1).astype(np.int32)
        names = ('tall_seagrass_bottom', 'tall_seagrass_top')
    owners = np.repeat(np.arange(n, dtype=np.int32), lengths)
    starts = np.cumsum(lengths) - lengths
    ys = np.arange(len(owners), dtype=np.int32) - np.repeat(starts, lengths)
    offsets = np.zeros((len(owners), 3), np.int32); offsets[:, 1] = ys
    ids = np.array([ctx.block_ids[name] for name in names], np.uint16)
    types = ids[(ys == lengths[owners] - 1).astype(np.intp)]
    if ctx.feature.id != 'kelp':
        types[lengths[owners] == 1] = ctx.block_ids['seagrass']
    return FeatureBatch(offsets, types, owners)
