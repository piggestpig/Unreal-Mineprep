"""Narrow native-cell bridges; Mineprep is imported only for editor-only operations."""
from os import PathLike

import numpy as np

from ..core.building import Structure, _state


def to_blocks(structure):
    if not isinstance(structure, Structure):
        raise TypeError('to_blocks requires a Structure')
    from mineprep import Blocks
    cells = {tuple(map(int, point)): {'name': structure.palette[t][0],
                                    'properties': dict(structure.palette[t][1])}
             for point, t in zip(structure.xyz, structure.types)}
    return Blocks(structure.name, cells=cells, copy=False)


def from_blocks(source, *, name=None, repair_trapdoors=False):
    if isinstance(source, (str, PathLike)):
        from mineprep import Blocks
        source = Blocks.from_file(source, repair_trapdoors=repair_trapdoors)
    cells = source.copy_cells()
    points, types, palette, ids = [], [], [], {}
    for point, cell in cells.items():
        state = _state(cell['name'], cell.get('properties') or {})
        if state[0] == 'air':
            continue
        if state not in ids:
            ids[state] = len(palette)
            palette.append(state)
        points.append(point)
        types.append(ids[state])
    xyz = np.asarray(points) if points else np.empty((0, 3), np.int32)
    lo = xyz.min(axis=0) if len(xyz) else np.zeros(3, np.int64)
    size = xyz.max(axis=0)-lo+1 if len(xyz) else np.ones(3, np.int64)
    order = sorted(range(len(palette)), key=palette.__getitem__)
    remap = np.empty(len(order), np.int64)
    remap[order] = np.arange(len(order))
    return Structure(source.name if name is None else name, tuple(lo), tuple(size),
                     tuple(palette[i] for i in order), xyz, remap[types])
