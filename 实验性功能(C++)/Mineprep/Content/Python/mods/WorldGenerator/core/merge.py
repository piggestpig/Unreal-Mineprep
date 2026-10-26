"""Fast deterministic horizontal merging; no Unreal or per-cell dictionaries."""
from dataclasses import replace
import numpy as np
from .data import check_cancel

MERGE_VERSION = 'cuboids-5'
MERGE_TILE = 128
MODES = ('none', 'runs', 'rectangles', 'cuboids')


def merge_arrays(data, mode='rectangles', cancel_event=None):
    if mode not in MODES:
        raise ValueError('merge must be none, runs, rectangles or cuboids')
    check_cancel(cancel_event)
    if data.sizes is not None:
        raise ValueError('merge_arrays requires unmerged visible cells')
    if mode == 'none' or not data.count:
        return replace(data, visible_count=data.count)
    nx = (data.region.width + MERGE_TILE - 1) // MERGE_TILE
    keys = data.xyz[:, 2].astype(np.int64) // MERGE_TILE * nx + data.xyz[:, 0] // MERGE_TILE
    order = np.argsort(keys, kind='stable')
    boundaries = np.flatnonzero(np.diff(keys[order])) + 1
    chunks = []
    mergeable = np.array([b.merge in ('xz', 'xyz') for b in data.block_defs], bool) if data.block_defs else np.ones(len(data.names), bool)
    vertical = np.array([b.merge == 'xyz' for b in data.block_defs], bool) if data.block_defs else np.ones(len(data.names), bool)
    for indices in np.split(order, boundaries):
        check_cancel(cancel_event)
        p, t = data.xyz[indices], data.types[indices]
        offsets = (np.zeros(len(p)) if data.instance_y_offsets is None
                   else data.instance_y_offsets[indices])
        rotations = (np.zeros(len(p), np.uint8) if data.rotations is None else data.rotations[indices])
        # Sort by type, Y, Z, X, then identify uninterrupted X runs.
        sort = np.lexsort((p[:, 0], p[:, 2], offsets, p[:, 1], rotations, t))
        p, t, offsets, rotations = p[sort], t[sort], offsets[sort], rotations[sort]
        eligible = mergeable[t]
        breaks = ((t[1:] != t[:-1]) | (p[1:, 1] != p[:-1, 1])
                  | (p[1:, 2] != p[:-1, 2]) | (p[1:, 0] != p[:-1, 0] + 1)
                  | (offsets[1:] != offsets[:-1]) | ~eligible[1:] | ~eligible[:-1])
        breaks |= rotations[1:] != rotations[:-1]
        starts = np.r_[0, np.flatnonzero(breaks) + 1]
        widths = np.diff(np.r_[starts, len(p)])
        p, t, offsets, rotations = p[starts], t[starts], offsets[starts], rotations[starts]
        sizes = np.ones_like(p)
        sizes[:, 0] = widths
        if mode in ('rectangles', 'cuboids'):
            # Only identical X intervals can join across consecutive Z rows.
            sort = np.lexsort((p[:, 2], widths, p[:, 0], offsets, p[:, 1], rotations, t))
            p, t, sizes, offsets, rotations = p[sort], t[sort], sizes[sort], offsets[sort], rotations[sort]
            eligible = mergeable[t]
            breaks = ((t[1:] != t[:-1]) | (p[1:, 1] != p[:-1, 1])
                      | (p[1:, 0] != p[:-1, 0]) | (sizes[1:, 0] != sizes[:-1, 0])
                      | (offsets[1:] != offsets[:-1])
                      | (p[1:, 2] != p[:-1, 2] + 1) | ~eligible[1:] | ~eligible[:-1])
            breaks |= rotations[1:] != rotations[:-1]
            starts = np.r_[0, np.flatnonzero(breaks) + 1]
            depths = np.diff(np.r_[starts, len(p)])
            p, t, sizes, offsets, rotations = p[starts], t[starts], sizes[starts], offsets[starts], rotations[starts]
            sizes[:, 2] = depths
        if mode == 'cuboids':
            sort = np.lexsort((p[:, 1], sizes[:, 2], sizes[:, 0], p[:, 2], p[:, 0], offsets, rotations, t))
            p, t, sizes, offsets, rotations = p[sort], t[sort], sizes[sort], offsets[sort], rotations[sort]
            eligible = vertical[t]
            breaks = ((t[1:] != t[:-1]) | (offsets[1:] != offsets[:-1])
                      | (p[1:, 0] != p[:-1, 0]) | (p[1:, 2] != p[:-1, 2])
                      | (sizes[1:, 0] != sizes[:-1, 0]) | (sizes[1:, 2] != sizes[:-1, 2])
                      | (p[1:, 1] != p[:-1, 1] + 1) | ~eligible[1:] | ~eligible[:-1])
            breaks |= rotations[1:] != rotations[:-1]
            starts = np.r_[0, np.flatnonzero(breaks) + 1]
            heights = np.diff(np.r_[starts, len(p)])
            p, t, sizes, offsets, rotations = p[starts], t[starts], sizes[starts], offsets[starts], rotations[starts]
            sizes[:, 1] = heights
        chunks.append((p, t, sizes, offsets, rotations))
    check_cancel(cancel_event)
    xyz, types, sizes = (np.concatenate([chunk[i] for chunk in chunks]) for i in range(3))
    for array in (xyz, types, sizes):
        array.setflags(write=False)
    offsets = None if data.instance_y_offsets is None else np.concatenate([c[3] for c in chunks])
    if offsets is not None:
        offsets.setflags(write=False)
    rotations = None if data.rotations is None else np.concatenate([c[4] for c in chunks])
    if rotations is not None:
        rotations.setflags(write=False)
    return replace(data, xyz=xyz, types=types, sizes=sizes, visible_count=data.count,
                   instance_y_offsets=offsets, rotations=rotations)
