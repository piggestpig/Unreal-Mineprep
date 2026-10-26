"""Small grounded rocks and horizontal logs, using finite deterministic shapes."""
import numpy as np
from ...core.features import FeatureBatch


def _shape(kind, variant):
    if kind == 'rocks':
        base = [(0, 0, 0), (1, 0, 0), (0, 0, 1), (-1, 0, 0), (0, 0, -1)]
        count = 1 + variant % 5
        cells = base[:count]
        if variant & 8:
            cells += [(0, 1, 0)]
            if count > 1:
                cells += [(1, 1, 0)]
    else:
        length = 2 + variant % 3
        start = -(length//2)
        cells = [(i, 0, 0) for i in range(start, start + length)]
    points = np.asarray(cells, np.int32)
    if kind == 'rocks':
        for _ in range((variant >> 4) & 3):
            points[:, (0, 2)] = points[:, (2, 0)] * (-1, 1)
    elif variant & 4:
        points[:, (0, 2)] = points[:, (2, 0)]
    return points


def build(ctx, anchors, keys):
    offsets, types, owners, rotations = [], [], [], []
    variants = ((keys >> np.uint64(8)) & np.uint64(63)).astype(np.intp)
    for owner, variant in enumerate(variants):
        points = _shape(ctx.feature.id, int(variant))
        material = (int(variant) >> 2) % 3 if ctx.feature.id == 'rocks' else 0
        offsets.append(points)
        types.append(np.full(len(points), ctx.block_ids[ctx.feature.blocks[material]], np.uint16))
        owners.append(np.full(len(points), owner, np.int32))
        rotation = 0 if ctx.feature.id == 'rocks' else (8 if variant & 4 else 20)
        rotations.append(np.full(len(points), rotation, np.uint8))
    return FeatureBatch(np.concatenate(offsets) if offsets else np.empty((0, 3), np.int32),
                        np.concatenate(types) if types else np.empty(0, np.uint16),
                        np.concatenate(owners) if owners else np.empty(0, np.int32),
                        (np.concatenate(rotations) if rotations else np.empty(0, np.uint8))
                        if ctx.feature.id == 'fallen_logs' else None)
