"""Sparse ceiling-to-sea/floor lava; physical profiles stay transient."""
from time import perf_counter
import numpy as np
from ...core.data import check_cancel
from ...core.features import FeatureBatch
from ...core.volume_features import Anchors

MIN_LENGTH = 12


def spans(ctx, rock):
    """Eligible inclusive bottoms/tops, bounded by actual rock on both sides."""
    p = ctx.params
    lo, hi = p['nether.floor_y'], p['nether.roof_y']
    level = int(np.floor(p['world.sea_level']))
    sea = p['nether.lava_enabled'] and lo <= level and level + 1 < hi
    for a, b in ctx.query.air_runs(rock):
        if a == 0 or b == hi - lo:
            continue
        bottom, top = int(a) + lo, int(b) + lo - 1
        if sea and bottom <= level and level + 1 <= top:
            bottom = level
        if top - bottom + 1 >= MIN_LENGTH:
            yield bottom, top


def place(ctx, xz, keys):
    start = perf_counter()
    p = ctx.params
    columns = ctx.query.profiles(xz, p['nether.floor_y'], p['nether.roof_y'])
    roots, owners = [], []
    for i, (x, z) in enumerate(xz):
        check_cancel(getattr(ctx.resources, 'cancel_event', None))
        runs = tuple(spans(ctx, columns[:, i]))
        if runs:
            _, top = runs[(int(keys[i]) >> 16) % len(runs)]
            roots.append((x, top, z))
            owners.append(i)
    ctx.resources.report.add('volume_lava_candidates', len(xz))
    ctx.resources.report.add('volume_lava_anchors', len(roots))
    ctx.resources.report.add('volume_lava_query_seconds', perf_counter() - start)
    return Anchors(np.asarray(roots, np.int64).reshape(-1, 3), np.asarray(owners, np.intp),
                   np.full(len(roots), ctx.block_ids['netherrack'], np.uint16), np.zeros(len(roots)))


def build(ctx, anchors, keys):
    start = perf_counter()
    p = ctx.params
    # Reuse the placement query; fetch only the accepted XZ profiles. No new
    # endpoint contract or long-lived occupancy cache is needed.
    columns = ctx.query.profiles(anchors[:, (0, 2)], p['nether.floor_y'], p['nether.roof_y'])
    points, owners = [], []
    for i, anchor in enumerate(anchors):
        check_cancel(getattr(ctx.query.resources, 'cancel_event', None))
        for bottom, top in spans(ctx, columns[:, i]):
            if top == anchor[1]:
                offsets = np.zeros((top - bottom + 1, 3), np.int64)
                offsets[:, 1] = -np.arange(len(offsets))
                points.append(offsets)
                owners.append(np.full(len(offsets), i, np.int32))
                break
    offsets = np.concatenate(points) if points else np.empty((0, 3), np.int64)
    ctx.query.resources.report.add('volume_lava_build_seconds', perf_counter() - start)
    return FeatureBatch(offsets, np.full(len(offsets), ctx.block_ids['lava'], np.uint16),
                        np.concatenate(owners) if owners else np.empty(0, np.int32))
