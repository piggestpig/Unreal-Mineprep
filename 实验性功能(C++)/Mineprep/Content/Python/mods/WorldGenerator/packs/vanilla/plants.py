"""Batched two-cell plants and sparse one-to-three-cell cactus columns."""
import numpy as np
from ...core.features import FeatureBatch


def cactus(ctx, anchors, keys):
    lengths = (np.ones(len(anchors), np.int32) if ctx.param('vegetation.simplified') else
               1 + ((keys >> np.uint64(8)) % np.uint64(3)).astype(np.int32))
    owners = np.repeat(np.arange(len(anchors), dtype=np.int32), lengths)
    offsets = np.zeros((len(owners), 3), np.int32)
    offsets[:, 1] = np.arange(len(owners)) - np.repeat(np.cumsum(lengths) - lengths, lengths)
    return FeatureBatch(offsets, np.full(len(owners), ctx.block_ids['cactus'], np.uint16), owners)


def build(ctx, anchors, keys):
    n = len(anchors)
    pairs = np.asarray([ctx.block_ids[name] for name in ctx.feature.blocks], np.uint16).reshape(2, 2)
    variants = ((keys >> np.uint64(8)) & np.uint64(1)).astype(np.intp)
    return FeatureBatch(
        np.tile(np.array([[0, 0, 0], [0, 1, 0]], np.int32), (n, 1)),
        pairs[variants].reshape(-1), np.repeat(np.arange(n, dtype=np.int32), 2),
    )
