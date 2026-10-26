"""Bounded cell-colour diagnostics for structures and scenes, without Unreal."""
from pathlib import Path
from dataclasses import replace

import numpy as np

from ..core.building import Structure
from ..core.blocks import BlockDef
from ..core.scene import Scene, _world_points
from .block_colors import color_table
from .preview import write_png


def _preview_definitions(names, definitions=None):
    result = dict(definitions or {})
    for name in names:
        block = result.get(name) or BlockDef(name, 'builtin', name, shape='decor', occludes=False, merge='none')
        if block.source == 'builtin' and block.shape == 'decor':
            source = block.value+'_post' if block.value.endswith(('_fence', '_pane')) else block.value
            block = replace(block, value=source)
        result[name] = block
    return result


def _cells(source):
    if isinstance(source, Structure):
        names = [n for n, _ in source.palette]
        return source.xyz.astype(np.int64), color_table(names, _preview_definitions(names))[source.types]
    world = source.world
    points = [_world_points(world.arrays)]
    colours = [color_table(world.arrays.names, world.pack.block_defs)[world.arrays.types]]
    table = color_table(world.pack.blocks, _preview_definitions(world.pack.blocks, world.pack.block_defs))
    from ..core.templates import rotate
    for model in world.model_instances:
        points.append(rotate(model.template.offsets, model.rotation).astype(np.int64)+model.anchor)
        colours.append(table[model.template.types])
    return np.concatenate(points), np.concatenate(colours)


def _nearest(pixels, depth, width):
    ids = pixels[:, 1]*width+pixels[:, 0]
    order = np.lexsort((depth, ids))
    end = np.r_[ids[order[1:]] != ids[order[:-1]], True]
    return order[end]


def orthographic(points, colours, axis, max_side):
    # Front looks toward +Z; right toward -X; top looks down -Y.
    axes = {'front': (0, 1, 2, -1), 'right': (2, 1, 0, 1), 'top': (0, 2, 1, 1)}
    a, b, d, sign = axes[axis]
    lo, hi = points.min(axis=0), points.max(axis=0)+1
    step = max(1, int(np.ceil(max(hi[a]-lo[a], hi[b]-lo[b])/max_side)))
    xy = np.column_stack(((points[:, a]-lo[a])//step, (hi[b]-1-points[:, b])//step))
    width, height = int(xy[:, 0].max())+1, int(xy[:, 1].max())+1
    at = _nearest(xy, points[:, d]*sign, width)
    image = np.full((height, width, 3), 238, np.uint8)
    image[xy[at, 1], xy[at, 0]] = colours[at]
    return image


def isometric(points, colours, max_side):
    """Cell cubes with painter shading; not a texture/model-geometry renderer."""
    import cv2
    p = points.astype(np.float64)-points.min(axis=0)
    p[:, 2] *= -1  # camera sees the front (-Z), the right (+X) and the top
    uv = np.column_stack((p[:, 0]-p[:, 2], .5*(p[:, 0]+p[:, 2])-p[:, 1]))
    span = np.ptp(uv, axis=0)+3
    scale = min(12., (max_side-8)/float(span.max()))
    uv = (uv-uv.min(axis=0)+[1.5, 2])*scale+4
    width, height = np.ceil(uv.max(axis=0)+2*scale+5).astype(int)
    image = np.full((height, width, 3), 238, np.uint8)
    depth = p[:, 0]+p[:, 2]+2*p[:, 1]
    # At most one cell centre per output pixel. Large solid interiors never
    # become millions of Python draw calls; image resolution bounds the work.
    pixels = np.floor(uv).astype(np.int64)
    at = _nearest(pixels, depth, width)
    at = at[np.argsort(depth[at], kind='stable')]
    faces = (((0, -1), (1, -.5), (0, 0), (-1, -.5)),
             ((-1, -.5), (0, 0), (0, 1), (-1, .5)),
             ((0, 0), (1, -.5), (1, .5), (0, 1)))
    for i in at:
        for face, shade in zip(faces, (1., .64, .82)):
            vertices = np.rint(uv[i]+np.asarray(face)*scale).astype(np.int32)
            cv2.fillConvexPoly(image, vertices, tuple(map(int, colours[i]*shade)))
    return image


def snapshot(source, path, *, box=320, extra_lines=(), views=('front', 'right', 'top', 'isometric')):
    import cv2
    if not isinstance(source, (Structure, Scene)):
        raise TypeError('building snapshot requires Structure or Scene')
    if type(box) is not int or not 64 <= box <= 2048:
        raise ValueError('box must be an integer in [64,2048]')
    if not views or len(set(views)) != len(views) or set(views)-{'front', 'right', 'top', 'isometric'}:
        raise ValueError('views must be unique front/right/top/isometric names')
    points, colours = _cells(source)
    cols, rows = min(2, len(views)), (len(views)+1)//2
    sheet = np.full((rows*(box+30)+88+20*len(extra_lines), cols*(box+12)+12, 3), 250, np.uint8)
    if len(points):
        for i, name in enumerate(views):
            image = isometric(points, colours, box) if name == 'isometric' else orthographic(points, colours, name, box)
            scale = min(box/image.shape[0], box/image.shape[1])
            size = max(1, round(image.shape[1]*scale)), max(1, round(image.shape[0]*scale))
            image = cv2.resize(image, size, interpolation=cv2.INTER_NEAREST)
            x, y = 12+(i%cols)*(box+12), 28+(i//cols)*(box+30)
            sheet[y:y+size[1], x:x+size[0]] = image
            cv2.putText(sheet, name, (x, y-8), cv2.FONT_HERSHEY_SIMPLEX, .5, (35, 35, 35), 1)
        dimensions = tuple(map(int, points.max(axis=0)-points.min(axis=0)+1))
    else:
        dimensions = (0, 0, 0)
    if isinstance(source, Structure):
        materials = len(source.palette)
    else:
        world = source.world
        used = {world.arrays.names[t] for t in np.unique(world.arrays.types)}
        for model in world.model_instances:
            used.update(world.pack.blocks[t] for t in np.unique(model.template.types))
        materials = len(used)
    lines = [f'MC XYZ / Y up | cells {len(points):,} | materials {materials} | size {dimensions}',
             'Cell-colour diagnostics; textures, partial faces and UE rendering require editor acceptance.', *extra_lines]
    for i, line in enumerate(lines):
        cv2.putText(sheet, str(line), (12, rows*(box+30)+20+i*20), cv2.FONT_HERSHEY_SIMPLEX, .38, (35, 35, 35), 1)
    return write_png(Path(path), sheet)
