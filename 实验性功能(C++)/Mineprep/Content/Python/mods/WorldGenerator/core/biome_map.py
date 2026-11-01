"""Request-local categorical images sharing the existing immutable image snapshots."""
from dataclasses import dataclass, replace
import hashlib
import json
from time import perf_counter
import numpy as np

from .heightmap import capture as capture_image, decoded
from .water import sample_water

VERSION = 'biome-map-2'
WATER_BIOMES = frozenset(('ocean', 'frozen_ocean', 'river', 'lake', 'pond'))
MARKERS = ('#ff0000', '#00ff00', '#0000ff', '#ffff00', '#00ffff', '#ff00ff',
           '#800000', '#008000', '#000080', '#808000', '#008080', '#800080')


def supported(pack):
    return 'vanilla' in pack.chain


def palette(pack):
    """Drawing markers are independent of biome map colours and translations."""
    land = [b.id for b in pack.biomes if b.id not in WATER_BIOMES]
    first = [b for b in ('forest', 'grassland', 'desert') if b in land]
    return dict(zip(MARKERS, first + [b for b in land if b not in first]))


def validate(pack, config):
    if not supported(pack):
        raise ValueError('biome map requires vanilla or a derived pack')
    known = {b.id for b in pack.biomes} - WATER_BIOMES
    unknown = {biome for _, biome in config.palette} - known
    if unknown:
        raise ValueError(f'biome map requires existing land biome IDs: {sorted(unknown)}')


def capture(config, *, cancel_event=None):
    return capture_image(config, color=True, cancel_event=cancel_event)


def input_key(config, source):
    raw = json.dumps([VERSION, source.digest, config.to_dict()], sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class BiomeMap:
    config: object
    source: object
    values: np.ndarray  # int32[Z,X]; -1 means use the existing selection
    matched_pixels: int
    transparent_pixels: int
    classify_seconds: float

    def info(self):
        return dict(width=self.values.shape[1], depth=self.values.shape[0],
                    matched_pixels=self.matched_pixels, pixels=self.values.size,
                    transparent_pixels=self.transparent_pixels,
                    unmatched_pixels=self.values.size-self.matched_pixels-self.transparent_pixels,
                    palette=dict(self.config.palette), tolerance=self.config.tolerance,
                    classify_seconds=self.classify_seconds)

    def sample(self, x, z):
        r, a = self.config.region, self.values
        x, z = np.broadcast_arrays(x, z)
        inside = (x >= r.x0) & (x < r.x0+r.width) & (z >= r.z0) & (z < r.z0+r.depth)
        ix = np.clip(np.floor((x+.5-r.x0)*a.shape[1]/r.width).astype(np.intp), 0, a.shape[1]-1)
        iz = np.clip(np.floor((z+.5-r.z0)*a.shape[0]/r.depth).astype(np.intp), 0, a.shape[0]-1)
        return np.where(inside, a[iz, ix], -1)

    def apply(self, ctx, pack, natural, wet=None):
        chosen = self.sample(ctx.x, ctx.z)
        if wet is None:
            height = np.clip(ctx.get(pack.height_field), ctx.param('world.y_min'), ctx.param('world.y_max'))
            wet = sample_water(ctx, pack, height)[1]
        protected = [i for i, b in enumerate(pack.biomes) if b.id in WATER_BIOMES]
        use = (chosen >= 0) & ~wet & ~np.isin(natural, protected)
        return np.where(use, chosen, natural).astype(np.uint16)


def bind(pack, config, source):
    validate(pack, config)
    image = decoded(source, color=True).values
    started = perf_counter()
    colors = ((image[..., 0].astype(np.uint32) << 16)
              | (image[..., 1].astype(np.uint32) << 8) | image[..., 2])
    indices = {b.id: i for i, b in enumerate(pack.biomes)}
    ordered = sorted((int(color[1:], 16), indices[biome]) for color, biome in config.palette)
    values = np.full(colors.shape, -1, np.int32)
    visible = image[..., 3] != 0
    if ordered:
        keys, targets = (np.asarray(v) for v in zip(*ordered))
        at = np.searchsorted(keys, colors)
        clipped = np.minimum(at, len(keys)-1)
        exact = (at < len(keys)) & (keys[clipped] == colors) & visible
        values[exact] = targets[clipped[exact]]
        if config.tolerance:
            # Only non-exact, visible pixels need distance tests. Bound temporary
            # arrays by chunk size, rather than pixels times palette size.
            pixels, output = image.reshape(-1,4), values.reshape(-1)
            markers = [(np.array([(key >> 16) & 255, (key >> 8) & 255, key & 255], np.int32), target)
                       for key,target in ordered]
            for start in range(0, len(output), 65536):
                chunk = output[start:start+65536]
                rgba = pixels[start:start+65536]
                pending = np.flatnonzero((chunk < 0) & (rgba[:,3] != 0))
                if not pending.size:
                    continue
                rgb = rgba[pending,:3].astype(np.int32)
                best = np.full(len(pending), 2**31-1, np.int32)
                winner = np.full(len(pending), -1, np.int32)
                tied = np.zeros(len(pending), bool)
                for color,target in markers:
                    delta = rgb-color
                    distance = np.einsum('ij,ij->i', delta, delta)
                    eligible = np.max(np.abs(delta), axis=1) <= config.tolerance
                    better = eligible & (distance < best)
                    equal = eligible & (distance == best)
                    best[better] = distance[better]
                    winner[better] = target
                    tied[better] = False
                    tied[equal] = True
                chunk[pending] = np.where(tied, -1, winner)
    values.setflags(write=False)
    return replace(pack, biome_map=BiomeMap(config, source, values,
        int(np.count_nonzero(values >= 0)), int(np.count_nonzero(~visible)), perf_counter()-started))
