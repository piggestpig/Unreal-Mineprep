"""Immutable file heights, bounded decoding reuse and request-local field binding.

Only Source (metadata) crosses worker boundaries. Each process retains at most
two decoded inputs; Worlds retain their own snapshot even after cache eviction.
"""
from collections import OrderedDict
from dataclasses import dataclass, field, replace
import hashlib
import json
import os
from pathlib import Path
import struct
import threading
from time import perf_counter

import numpy as np

from .data import check_cancel
from .fields import FieldDef, check_graph
from .pack import PackChangedError

VERSION = 'heightmap-2-red'
MAX_PIXELS = 16_777_216
_cache = OrderedDict()
_lock = threading.RLock()


def _stamp(path):
    s = Path(path).stat()
    return (s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _image_dimensions(raw, suffix):
    """Check dimensions before allocating decoded PNG/EXR pixels."""
    if suffix == '.png' and raw[:8] == b'\x89PNG\r\n\x1a\n' and len(raw) >= 24:
        return struct.unpack('>II', raw[16:24])
    if suffix == '.exr' and raw[:4] == b'v/1\x01':
        offset = 8
        while offset < len(raw) and raw[offset]:
            end = raw.index(0, offset)
            name = raw[offset:end]
            offset = raw.index(0, end + 1) + 1
            length = struct.unpack_from('<I', raw, offset)[0]
            offset += 4
            if name == b'dataWindow' and length == 16:
                x0, y0, x1, y1 = struct.unpack_from('<4i', raw, offset)
                return x1 - x0 + 1, y1 - y0 + 1
            offset += length
    raise ValueError('heightmap has an invalid PNG/EXR header')


def _read(path):
    started = perf_counter()
    stamp = _stamp(path)
    raw = Path(path).read_bytes()
    read_seconds = perf_counter() - started
    started = perf_counter()
    digest = hashlib.sha256(raw).hexdigest()
    hash_seconds = perf_counter() - started
    return raw, digest, stamp, read_seconds, hash_seconds


@dataclass(frozen=True)
class Source:
    path: str
    digest: str
    stamp: tuple
    read_seconds: float = 0.
    hash_seconds: float = 0.
    decode_seconds: float = 0.

    def checked(self, *, full=False):
        try:
            if _stamp(self.path) != self.stamp:
                raise PackChangedError()
            if full and hashlib.sha256(Path(self.path).read_bytes()).hexdigest() != self.digest:
                raise PackChangedError()
        except OSError as exc:
            raise PackChangedError() from exc


@dataclass(frozen=True)
class Snapshot:
    source: Source
    values: np.ndarray
    dtype: str
    normalized: bool
    config: object = None
    sample_stats: dict = field(default_factory=lambda: dict(seconds=0., points=0.), compare=False)

    def output_range(self, params):
        if self.config.output_range is not None:
            return self.config.output_range
        return ((params['world.y_min'], params['world.y_max']) if self.normalized else (0., 1.))

    def sample(self, x, z, params):
        started = perf_counter()
        region = self.config.region
        depth, width = self.values.shape
        u = np.clip((np.asarray(x) + .5 - region.x0) * width / region.width - .5, 0, width - 1)
        v = np.clip((np.asarray(z) + .5 - region.z0) * depth / region.depth - .5, 0, depth - 1)
        ix, iz = np.floor(u).astype(np.intp), np.floor(v).astype(np.intp)
        fx, fz = u - ix, v - iz
        right, bottom = np.minimum(ix + 1, width - 1), np.minimum(iz + 1, depth - 1)
        top = self.values[iz, ix] * (1 - fx) + self.values[iz, right] * fx
        low = self.values[bottom, ix] * (1 - fx) + self.values[bottom, right] * fx
        result = top * (1 - fz) + low * fz
        a, b = self.config.input_range
        lo, hi = self.output_range(params)
        result = lo + (result - a) * ((hi - lo) / (b - a))
        with _lock:
            self.sample_stats['seconds'] += perf_counter() - started
            self.sample_stats['points'] += result.size
        return result

    def info(self, params):
        a, b = self.config.input_range
        lo, hi = self.output_range(params)
        bounds = [lo + (float(v) - a) * (hi - lo) / (b - a)
                  for v in (self.values.min(), self.values.max())]
        return dict(width=self.values.shape[1], depth=self.values.shape[0], dtype=self.dtype,
                    normalized=self.normalized, input_min=float(self.values.min()),
                    input_max=float(self.values.max()), mapped_min=min(bounds), mapped_max=max(bounds),
                    output_range=list(self.output_range(params)), array_bytes=self.values.nbytes,
                    clipped=min(bounds) < params['world.y_min'] or max(bounds) > params['world.y_max'])


def capture(config, *, cancel_event=None):
    check_cancel(cancel_event)
    raw, digest, stamp, reading, hashing = _read(config.path)
    source = Source(config.path, digest, stamp, reading, hashing)
    snapshot = decoded(source, raw=raw)
    check_cancel(cancel_event)
    return replace(source, decode_seconds=snapshot.source.decode_seconds)


def decoded(source, *, raw=None):
    key = (VERSION, source.path, source.digest)
    with _lock:
        cached = _cache.get(key)
        if cached is not None:
            _cache.move_to_end(key)
            return replace(cached, source=replace(source, decode_seconds=0.))
        if raw is None:
            raw, digest, _, _, _ = _read(source.path)
            if digest != source.digest:
                raise PackChangedError()
        started = perf_counter()
        try:
            width, depth = _image_dimensions(raw, Path(source.path).suffix.lower())
        except (ValueError, struct.error, IndexError) as exc:
            raise ValueError('heightmap has an invalid PNG/EXR header') from exc
        if width < 1 or depth < 1 or width * depth > MAX_PIXELS:
            raise ValueError(f'heightmap exceeds {MAX_PIXELS:,} pixels')
        os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR', '1')
        import cv2
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
        if image is None or image.shape[:2] != (depth, width):
            raise ValueError('cannot decode heightmap PNG/EXR')
        if image.ndim == 3:
            if image.shape[2] not in (3, 4):
                raise ValueError('heightmap requires a single channel or RGB/RGBA image')
            image = image[..., 2]  # OpenCV decodes BGR/BGRA; heights use red, never luminance.
        normalized = image.dtype in (np.dtype('uint8'), np.dtype('uint16'))
        if (Path(source.path).suffix.lower() == '.png' and not normalized) or (
                Path(source.path).suffix.lower() == '.exr' and image.dtype.kind != 'f'):
            raise ValueError('heightmap requires integer PNG or floating EXR')
        dtype = str(image.dtype)
        values = image.astype(np.float32)
        if normalized:
            values /= np.iinfo(image.dtype).max
        if not np.isfinite(values).all():
            raise ValueError('heightmap pixels must be finite')
        values.setflags(write=False)
        source = replace(source, decode_seconds=perf_counter() - started)
        snapshot = Snapshot(source, values, dtype, normalized)
        _cache[key] = snapshot
        while len(_cache) > 2:
            _cache.popitem(last=False)
        return snapshot


def snapshot(config, source):
    return replace(decoded(source), config=config, sample_stats=dict(seconds=0., points=0.))


def input_key(config, source):
    raw = json.dumps([VERSION, source.digest, config.to_dict()], sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def supported(pack):
    chain = ('height_lowlands', 'height_custom', 'height_islands', 'height_badlands',
             'height_before_rivers', 'height')
    return ('vanilla' in pack.chain and pack.height_field == 'height'
            and all(n in pack.fields for n in chain)
            and all(chain[i] in pack.fields[chain[i + 1]].deps for i in range(len(chain) - 1)))


def bind(pack, config, source, *, flat=False):
    if not supported(pack):
        raise ValueError('heightmap requires vanilla or a derived pack retaining its height chain')
    data = snapshot(config, source)
    fields = dict(pack.fields)
    def mapped(ctx):
        return data.sample(ctx.x, ctx.z, ctx.params)
    fields['heightmap_value'] = FieldDef('heightmap_value', mapped)
    if config.mode == 'add':
        fields['height_custom_base'] = replace(fields['height_custom'], name='height_custom_base')
        def add(ctx, base, delta):
            if ctx.param('terrain.flat'):
                base = ctx.param('world.flat_height')
            return base + delta
        fields['height_custom'] = FieldDef('height_custom', add, ('height_custom_base', 'heightmap_value'))
    else:
        fields['height_custom'] = FieldDef('height_custom', lambda ctx, value: value, ('heightmap_value',))
    # Flat file inputs bypass the ordinary guard without imposing vanilla's
    # function signature on a derived height_islands implementation.
    if flat:
        fields['height_islands'] = FieldDef('height_islands', lambda ctx, height: height, ('height_custom',))
    if config.mode == 'faithful':
        for name, dependency in (('height_islands', 'height_custom'), ('height_badlands', 'height_islands'),
                                 ('height_before_rivers', 'height_badlands'), ('height', 'height_before_rivers')):
            fields[name] = FieldDef(name, lambda ctx, height: height, (dependency,))
    check_graph(fields)
    generation = hashlib.sha256((pack.generation_fingerprint + input_key(config, source)).encode()).hexdigest()
    return replace(pack, fields=fields, heightmap=data,
                   _generation_stamp=(pack.fingerprint, generation))


def effective_values(data, values):
    if data.config.mode == 'faithful':
        for key, value in (('hydrology.enabled', False), ('islands.enabled', False),
                           ('seabed.shaping', False), ('badlands.height', 0.),
                           ('river.enabled', False), ('lakes.enabled', False), ('ponds.enabled', False)):
            if key in values:
                values[key] = value


def metrics(source, data):
    return dict(read_seconds=source.read_seconds, hash_seconds=source.hash_seconds,
                decode_seconds=source.decode_seconds, sample_seconds=data.sample_stats['seconds'],
                sample_points=int(data.sample_stats['points']), array_bytes=data.values.nbytes)
