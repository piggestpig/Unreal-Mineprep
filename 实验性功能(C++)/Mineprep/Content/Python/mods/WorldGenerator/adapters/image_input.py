"""Pixel columns from images: a flat back, optional relief, no dense 3D volume."""
import numpy as np

from ..core.building import Structure
from ..core.data import require_int
from ..core.pixelart import image_types
from .mesh_input import image_rgba, palette_colors


def image_structure(source, *, size=128, depth=1, axis='z', palette=None,
                    resample='box', colors=None, smooth=0., alpha_cutoff=0.5,
                    name='Image', max_cells=4_000_000):
    require_int('max_cells', max_cells, 1, 2**63-1)
    if axis not in ('x', 'y', 'z'):
        raise ValueError('axis must be x, y or z')
    if not np.isfinite(alpha_cutoff) or not 0 <= alpha_cutoff <= 1:
        raise ValueError('alpha_cutoff must be in 0..1')
    if colors is not None:
        require_int('colors', colors, 1, 65535)
    if not np.isfinite(smooth) or not 0 <= smooth <= 1:
        raise ValueError('smooth must be in 0..1')
    image = image_rgba(source, size=size, resample=resample)
    height, width = image.shape[:2]
    if callable(depth):
        depth = depth(image.copy())
    elif isinstance(depth, tuple) and len(depth) == 2:
        ends = np.asarray(depth, float)
        if not np.isfinite(ends).all() or np.any(ends < 0):
            raise ValueError('depth endpoints must be finite and nonnegative')
        # sRGB luma, with literal black/white endpoint depths, not observed min/max.
        luma = image[..., :3] @ np.array((.2126, .7152, .0722))/255.
        depth = ends[0] + (ends[1]-ends[0])*luma
    values = np.asarray(depth, float)
    if (values.shape not in ((), (height, width)) or not np.isfinite(values).all()
            or np.any(values < 0) or np.any(values > 2**31-4)):
        raise ValueError('depth requires a finite nonnegative scalar or [height,width] map')
    depths = np.broadcast_to(np.floor(values+.5).astype(np.int64), (height, width))
    alpha = image[..., 3]/255.
    visible = (alpha > 0) & (alpha >= alpha_cutoff) & (depths > 0)
    rows, cols = np.nonzero(visible)
    lengths = depths[rows, cols]
    count = int(lengths.sum())
    if count > max_cells:
        raise ValueError(f'image structure exceeds max_cells: {count} > {max_cells}')
    names, palette_rgb = palette_colors(palette)
    pixel_types = image_types(image, visible, palette_rgb, colors=colors, smooth=smooth)
    # Repeat only occupied columns; colour matching happens once per source pixel.
    pixels = np.repeat(np.arange(len(rows)), lengths)
    starts = np.cumsum(lengths)-lengths
    along = np.arange(count)-np.repeat(starts, lengths)
    horizontal, vertical = cols[pixels], height-1-rows[pixels]
    order = {'z': (horizontal, vertical, along),
             'y': (horizontal, along, vertical),
             'x': (along, vertical, horizontal)}[axis]
    extent = max(1, int(lengths.max())) if len(lengths) else 1
    bounds = {'z': (width, height, extent), 'y': (width, extent, height),
              'x': (extent, height, width)}[axis]
    return Structure(name, (0, 0, 0), bounds, tuple((n, ()) for n in names),
                     np.column_stack(order), pixel_types[pixels])
