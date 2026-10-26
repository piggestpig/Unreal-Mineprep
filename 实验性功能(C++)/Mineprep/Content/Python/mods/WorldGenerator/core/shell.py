"""Visible-shell cell arrays. Coordinates are local X/Z (region origin), absolute MC Y.

A column's continuous height h is the top boundary: the cell at integer Y is
solid exactly when Y < h. Lower cells are emitted only where a neighbouring
column is shorter; outside the world region counts as air, so region borders
show walls down to y_min.
"""

from dataclasses import dataclass

import numpy as np
from mc_math import boxes_to_packed, validate_packed, partition_types

from .data import BLOCK_CM, require_int, to_ue
from .noise3 import hash01


def shell_counts(tops, y_min):
    """Count before allocating sparse shell arrays."""
    top = tops[1:-1, 1:-1]
    neighbor = np.minimum.reduce((tops[1:-1, :-2], tops[1:-1, 2:], tops[:-2, 1:-1], tops[2:, 1:-1]))
    low = np.maximum(y_min, np.minimum(top, neighbor + 1))
    counts = np.maximum(top - low + 1, 0).ravel().astype(np.int64)
    return top, low, counts


def layer_roles(depth,soil_depth):
    return np.where(depth==0,0,np.where((depth>0)&(depth<=soil_depth),1,2)).astype(np.intp)


def column_shell(tops, y_min, soil_depth, *, counted=None):
    """tops: int32[Z+2,X+2] with a one-cell ring. Returns (col, y, role) for the core."""
    top, low, counts = shell_counts(tops, y_min) if counted is None else counted
    total = int(counts.sum())
    col = np.repeat(np.arange(counts.size), counts)
    starts = np.cumsum(counts) - counts
    y = low.ravel()[col] + (np.arange(total) - starts[col])
    depth = top.ravel()[col] - y
    limit=soil_depth if np.ndim(soil_depth)==0 else soil_depth.ravel()[col]
    role = layer_roles(depth,limit)
    return col, y.astype(np.int32), role


@dataclass(frozen=True)
class WorldArrays:
    region: object          # Region; xyz are relative to its (x0, z0)
    xyz: np.ndarray         # int32[N,3]
    types: np.ndarray       # uint32[N] index into names
    names: tuple
    solid_count: int
    sizes: object = None    # int32[N,3] extents after merging, else None
    visible_count: object = None
    block_defs: tuple = ()   # shared declarations aligned with names
    y_offsets: tuple = ()    # per type fractional MC Y, e.g. fractional sea level
    instance_y_offsets: object = None  # optional per-instance additive MC Y offsets
    rotations: object = None  # optional uint8[N] orientation codes; None means identity
    scale_jitter_types: tuple = ()  # output-only template type IDs, never logical cell sizes

    @property
    def count(self):
        return len(self.xyz)

    @property
    def array_bytes(self):
        return (self.xyz.nbytes + self.types.nbytes + (0 if self.sizes is None else self.sizes.nbytes)
                + (0 if self.instance_y_offsets is None else self.instance_y_offsets.nbytes)
                + (0 if self.rotations is None else self.rotations.nbytes))

    def groups(self, chunk_count=1):
        """Yield (spatial chunk ID, type ID, indices); empty regions emit no groups."""
        for chunk, type_id, indices, _ in self.spatial_groups(chunk_count):
            yield chunk, type_id, indices

    def spatial_groups(self, chunk_count=1):
        """As groups(), with the logical chunk's local (X, Z) corner appended."""
        require_int('chunk_count', chunk_count, 1, self.region.cells)
        if not self.count:
            return
        chunks = np.zeros(self.count, np.int64)
        pending = [(0, 0, self.region.width, self.region.depth, chunk_count,
                    np.arange(self.count))]
        next_id = 0
        origins = []
        while pending:
            x, z, width, depth, count, indices = pending.pop()
            if count == 1:
                chunks[indices] = next_id
                origins.append((x, z))
                next_id += 1
                continue
            axis = 0 if width >= depth else 2
            length, cross = (width, depth) if axis == 0 else (depth, width)
            half = length // 2
            capacity = half * cross
            other_capacity = (length - half) * cross
            left_count = max(1, count - other_capacity,
                             min(count - 1, capacity, count * capacity // (width * depth)))
            lower = indices[self.xyz[indices, axis] < (x if axis == 0 else z) + half]
            upper = indices[self.xyz[indices, axis] >= (x if axis == 0 else z) + half]
            if axis == 0:
                left = (x, z, half, depth, left_count, lower)
                right = (x + half, z, width - half, depth, count - left_count, upper)
            else:
                left = (x, z, width, half, left_count, lower)
                right = (x, z + half, width, depth - half, count - left_count, upper)
            pending.extend((right, left))  # low-coordinate side receives IDs first
        keys = chunks * len(self.names) + self.types
        order = np.argsort(keys, kind='stable')
        boundaries = np.flatnonzero(np.diff(keys[order])) + 1
        for indices in np.split(order, boundaries):
            key = int(keys[indices[0]])
            chunk, type_id = divmod(key, len(self.names))
            yield chunk, type_id, indices, origins[chunk]

    def type_groups(self, count=1):
        """Return exact minimum-cost whole-type GPU groups from final instances."""
        require_int('type_group_count', count, 1, 2**31 - 1)
        if not self.count:
            return ()
        if count == 1:
            # Preserve the legacy model palette, including unused entries.
            return ((tuple(range(len(self.names))), self.count),)
        counts = np.bincount(self.types, minlength=len(self.names))
        return partition_types(self.names, counts, count)

    def type_indices(self):
        """One stable index allocation; returned per-type arrays are views."""
        order = np.argsort(self.types, kind='stable')
        counts = np.bincount(self.types, minlength=len(self.names))
        return tuple(np.split(order, np.cumsum(counts)[:-1]))

    def payload(self, indices, *, origin=(0, 0, 0)):
        points = self.xyz[indices]
        if any(origin):
            # Rebase integers before packing into float32 UE centimetres.
            points = points.astype(np.int64) - np.asarray(origin, np.int64)
        payload = boxes_to_packed(points, 1 if self.sizes is None else self.sizes[indices],
                                  0 if self.rotations is None else self.rotations[indices])
        pos, scale = payload['pos'], payload['scale']
        ids = self.types[indices]
        if self.block_defs:
            offsets = to_ue(np.array([b.offset for b in self.block_defs], np.float32)).astype(np.float32)
            scales = to_ue(np.array([b.scale for b in self.block_defs], np.float32), 1).astype(np.float32)
            pos += offsets[ids]  # model offset is independent of merged extents
            scale *= scales[ids]
        if self.y_offsets:
            pos[:, 2] += np.asarray(self.y_offsets, np.float32)[ids] * BLOCK_CM
        if self.instance_y_offsets is not None:
            pos[:, 2] += self.instance_y_offsets[indices].astype(np.float32) * BLOCK_CM
        if self.scale_jitter_types:
            use = np.isin(ids, self.scale_jitter_types)
            if use.any():
                p = points[use].astype(np.int64) + np.asarray(origin, np.int64) + [self.region.x0, 0, self.region.z0]
                shrink = (.999 + .001*hash01(p[:,0], p[:,1], p[:,2], 0, 'tree-scale')).astype(np.float32)
                scale[use] *= shrink[:,None]
                # Keep the root cell's bottom fixed while scaling about its centre.
                pos[use, 2] += (shrink-1)*(BLOCK_CM*.5)
        return validate_packed(payload)

    def payload_map(self):
        return {self.names[t]: self.payload(indices) for _, t, indices in self.groups()}
