"""RGB multipliers or negative HSV adjustments -> half-float EXR, without UE."""
import hashlib
from collections.abc import Mapping
import json
import math
import os
from pathlib import Path
from time import perf_counter

import numpy as np

from ..core.data import check_cancel, require_int
from ..core.biomes import vegetation_tint, vegetation_hsv as validate_hsv
from ..core.world import World, Overview

# OpenCV snapshots this option when cv2 is imported, not when EXR is written.
# Match init_unreal, but preserve an explicit caller override.
os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR', '1')
VERSION = 'bct-linear-half-box9-hdr-1'
MAX_SIDE = 16384


def colour_power(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('biome_color_power must be a finite nonnegative number')
    return float(value)


def dimensions(region, cell_size=4):
    require_int('biome_cell_size', cell_size, 1, 16)
    width = (region.width + cell_size - 1) // cell_size
    height = (region.depth + cell_size - 1) // cell_size
    if max(width, height) > MAX_SIDE:
        raise ValueError('BCT exceeds 16384 pixels; increase biome_cell_size')
    return width, height


def palette(pack, overrides=None, *, biome_color_mode='rgb'):
    """Freeze a complete ID-ordered colour table without changing the pack."""
    if biome_color_mode not in ('rgb', 'hsv'):
        raise ValueError("biome_color_mode must be 'rgb' or 'hsv'")
    field = 'vegetation_tint' if biome_color_mode == 'rgb' else 'vegetation_hsv'
    option = 'vegetation_tints' if biome_color_mode == 'rgb' else 'vegetation_hsv'
    validate = vegetation_tint if biome_color_mode == 'rgb' else validate_hsv
    if overrides is not None and not isinstance(overrides, Mapping):
        raise TypeError(f'{option} must be a biome ID -> three-component mapping')
    overrides = dict(overrides or {})
    unknown = overrides.keys() - {b.id for b in pack.biomes}
    if unknown:
        raise ValueError(f'unknown {option} biome IDs: {sorted(unknown, key=str)}')
    return tuple((b.id, validate(overrides.get(b.id, getattr(b, field)), b.id))
                 for b in pack.biomes)


def _inputs(source, cell_size, vegetation_tints, vegetation_hsv, biome_color_mode, biome_color_power, frozen):
    if not isinstance(source, (World, Overview)):
        raise TypeError('BCT source must be a World or Overview snapshot')
    size = dimensions(source.region, cell_size)
    if biome_color_mode not in ('rgb', 'hsv'):
        raise ValueError("biome_color_mode must be 'rgb' or 'hsv'")
    colours = frozen if frozen is not None else palette(source.pack,
        vegetation_tints if biome_color_mode == 'rgb' else vegetation_hsv,
        biome_color_mode=biome_color_mode)
    values = np.asarray([rgb for _, rgb in colours], np.float32)
    power = colour_power(biome_color_power)
    if power != 1:
        with np.errstate(over='ignore', invalid='ignore'):
            values = np.power(values, power, dtype=np.float64)
        if not np.all(np.isfinite(values)) or np.any(values > 65504):
            raise ValueError('powered biome colours exceed finite FP16 range [0, 65504]')
        values = values.astype(np.float32)
        if biome_color_mode == 'hsv' and np.any(values[:,0].astype(np.float16) == 0):
            raise ValueError('powered HSV hue underflows FP16; reduce biome_color_power')
    return size, -values if biome_color_mode == 'hsv' else values


def texture_key(source, cell_size=4, *, vegetation_tints=None, biome_color_mode='rgb',
                vegetation_hsv=None, biome_color_power=1., _palette=None):
    size, colours = _inputs(source, cell_size, vegetation_tints, vegetation_hsv, biome_color_mode, biome_color_power, _palette)
    identity = (VERSION, source.biome_ids.shape, size, cell_size)
    if biome_color_mode == 'hsv':
        identity += ('hsv-negative-1',)
    if biome_color_power != 1:
        identity += ('power', float(biome_color_power))
    digest = hashlib.sha256(json.dumps(identity).encode())
    digest.update(colours.tobytes())
    digest.update(source.biome_ids.tobytes())
    return digest.hexdigest()


def pixels(source, cell_size=4, *, vegetation_tints=None, biome_color_mode='rgb',
           vegetation_hsv=None, biome_color_power=1., cancel=None, _palette=None):
    import cv2
    size, colours = _inputs(source, cell_size, vegetation_tints, vegetation_hsv, biome_color_mode, biome_color_power, _palette)
    check_cancel(cancel)
    rgb = colours[source.biome_ids]
    # One temporary RGB grid; border replication never resamples the world.
    cv2.boxFilter(rgb, -1, (9, 9), dst=rgb, normalize=True,
                  borderType=cv2.BORDER_REPLICATE)
    check_cancel(cancel)
    return cv2.resize(rgb, size, interpolation=cv2.INTER_AREA)


def write(source, path, *, cell_size=4, vegetation_tints=None, biome_color_mode='rgb',
          vegetation_hsv=None, biome_color_power=1., cancel=None, _palette=None, _key=None):
    import cv2
    path = Path(path)
    if path.suffix.lower() != '.exr':
        raise ValueError('BCT path must end in .exr')
    started = perf_counter()
    if not isinstance(source, (World, Overview)):
        raise TypeError('BCT source must be a World or Overview snapshot')
    frozen = _palette if _palette is not None else palette(source.pack,
        vegetation_tints if biome_color_mode == 'rgb' else vegetation_hsv,
        biome_color_mode=biome_color_mode)
    rgb = pixels(source, cell_size, biome_color_mode=biome_color_mode, biome_color_power=biome_color_power,
                 cancel=cancel, _palette=frozen)
    mapped = perf_counter()
    # OpenCV uses BGR; this changes channels, never the horizontal/vertical axes.
    try:
        ok, encoded = cv2.imencode('.exr', rgb[..., ::-1],
                                  [cv2.IMWRITE_EXR_TYPE, cv2.IMWRITE_EXR_TYPE_HALF])
    except cv2.error as exc:
        raise RuntimeError('BCT EXR encoding failed; enable OPENCV_IO_ENABLE_OPENEXR=1 '
                           'before importing cv2 (restart an existing interpreter)') from exc
    if not ok:
        raise RuntimeError('BCT EXR encoding failed')
    check_cancel(cancel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded.tobytes())
    return dict(path=str(path.resolve()), width=rgb.shape[1], height=rgb.shape[0],
                cell_size=cell_size, biome_color_mode=biome_color_mode,
                biome_color_power=float(biome_color_power),
                key=_key or texture_key(source, cell_size, biome_color_mode=biome_color_mode,
                                       biome_color_power=biome_color_power, _palette=frozen),
                map_seconds=mapped-started, encode_seconds=perf_counter()-mapped,
                seconds=perf_counter()-started)
