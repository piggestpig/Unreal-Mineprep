"""Lazy, process-local planning resources, independent of output crops.

A pack declares {"planners": {"water": "module:function"}}. The function
receives (pack, resolved_params, seed), and returns an immutable resource.
Fields declare resources=("water",) and call ctx.resource("water"). Planners
must not depend on an output Region. Each worker builds a key at most once.

Optional pack-local planning_params declarations limit cache parameters for
planners and density nodes. Missing declarations use all generation
parameters; descendants must opt in independently.
"""
from contextlib import contextmanager
import contextvars
import hashlib
import json
import pickle

import numpy as np
from .cache import Memo

VERSION = 'planning-2'
SURFACE_TILE = 64
_cache = Memo(limit=8)
_surface = Memo(limit=4096)  # about 150 MB of 64² height/wet tiles outside any field store


def clear_cache():
    from .fluids import clear_cache as clear_fluid_cache
    clear_fluid_cache()
    from .connections import clear_cache as clear_connection_cache
    clear_connection_cache()
    _cache.clear()
    _surface.clear()


class Resources:
    def __init__(self, pack, params, seed, *, region=None, validate=None):
        from .fields import active_region
        from .reports import StageReport
        self.report = StageReport()
        self.pack, self.params, self.seed = pack, params, seed
        self.region = region if region is not None else active_region()
        self._validate = (region is not None) if validate is None else bool(validate)
        self._local = {}
        self._keys = {}

    def key(self, name):
        if name in self._keys:
            return self._keys[name]
        from .world import GENERATOR_VERSION
        from .noise import NOISE_VERSION
        from .noise3 import VERSION as NOISE3_VERSION
        from .density import VERSION as DENSITY_VERSION
        # Function/source identity still comes from the complete generation
        # fingerprint. Only explicitly reviewed parameter dependencies narrow.
        resource = 'density' if name.startswith('density/') else name
        keys = (getattr(self.pack, 'planning_params', None) or {}).get(resource)
        params = (dict((key, self.params[key]) for key in keys) if keys is not None
                  else {k: v for k, v in self.params.to_dict().items()
                        if k != (self.pack.water.get('enabled_param') if self.pack.water else None)})
        raw = json.dumps([VERSION, GENERATOR_VERSION, NOISE_VERSION, NOISE3_VERSION, DENSITY_VERSION, self.pack.generation_fingerprint,
                          self.seed, name, params,
                          *([self.region.to_list() if self.region is not None else None]
                            if any(f.region_pass and f.region is None for f in self.pack.fields.values()) else [])],
                         sort_keys=True)
        self._keys[name] = hashlib.sha256(raw.encode()).hexdigest()
        return self._keys[name]

    def get(self, name):
        if any(not self.params[k] for k in (self.pack.planner_gates or {}).get(name, ())):
            return None
        if name not in (self.pack.planners or {}):
            raise ValueError(f'pack {self.pack.id!r} has no planner {name!r}')
        if name in self._local:
            return self._local[name]
        def build():
            from .fields import _active_passes, active_passes
            from .store import evaluate_passes
            if _active_passes.get() is None and any(f.region_pass for f in self.pack.fields.values()):
                with active_passes(evaluate_passes(self.pack, self.params, self.seed, self.region, self), self.region):
                    return self.pack.planners[name](self.pack, self.params, self.seed)
            return self.pack.planners[name](self.pack, self.params, self.seed)
        result = _cache.get(self.key(name), build)
        if self._validate and self.region is not None and result is not None and hasattr(result, 'validate_region'):
            result.validate_region(self.region)
        self._local[name] = result
        return self._local[name]

    def validate_region(self, region):
        if self.region is None:
            self.region = region
        for name in self.pack.planners or {}:
            resource = self.get(name)
            if resource is not None and hasattr(resource, 'validate_region'):
                resource.validate_region(region)

    def shared(self):
        """Pickled eager plans for worker processes; lazy plans (locks, pack functions) rebuild there."""
        items = []
        for name, value in self._local.items():
            try:
                items.append((self.key(name), pickle.dumps(value, pickle.HIGHEST_PROTOCOL)))
            except (TypeError, pickle.PicklingError):
                pass
        return tuple(items)

    def surface_region(self, region):
        """Cover density support, planner queries and whole SurfaceTiles blocks."""
        from .data import Region
        from .density import BLOCK
        step = max((max(d.steps[0], d.steps[2]) for d in (self.pack.densities or {}).values()), default=1)
        region = region.expanded(BLOCK + 2 * step)
        x0, z0 = region.x0, region.z0
        x1, z1 = x0 + region.width, z0 + region.depth
        for plan in self._local.values():
            query_region = getattr(plan, 'surface_region', None)
            if query_region is not None:
                r = query_region(region)
                x0, z0 = min(x0, r.x0), min(z0, r.z0)
                x1, z1 = max(x1, r.x0 + r.width), max(z1, r.z0 + r.depth)
        block = 2 * SURFACE_TILE
        x0, z0 = x0 // block * block, z0 // block * block
        x1, z1 = -(-x1 // block) * block, -(-z1 // block) * block
        return Region(x0, z0, x1 - x0, z1 - z0)


_window_runner = contextvars.ContextVar('worldgen_window_runner', default=None)


@contextmanager
def parallel_windows(runner):
    """Let planners hand FieldWindows.prefetch to generation workers: runner(name, windows) -> arrays."""
    token = _window_runner.set(runner)
    try:
        yield
    finally:
        _window_runner.reset(token)


def window_values(pack, params, seed, name, window):
    from .fields import Context
    x0, z0, x1, z1 = window
    x = np.arange(x0, x1 + 1, dtype=np.float64)[None, :]
    z = np.arange(z0, z1 + 1, dtype=np.float64)[:, None]
    return Context(pack.fields, params, seed, x, z).get(name)


class FieldWindows:
    """One field over inclusive integer (x0, z0, x1, z1) windows, rows Z and columns X.

    prefetch evaluates many independent windows on worker processes when a
    generation provides them, and does nothing otherwise; get is always exact.
    """
    def __init__(self, pack, params, seed, name):
        self.pack, self.params, self.seed, self.name = pack, params, seed, name
        self._values = {}

    def prefetch(self, windows):
        runner = _window_runner.get()
        if runner is not None:
            windows = [w for w in dict.fromkeys(tuple(map(int, w)) for w in windows) if w not in self._values]
            self._values.update(zip(windows, runner(self.name, windows)))

    def get(self, window):
        window = tuple(map(int, window))
        value = self._values.get(window)
        return window_values(self.pack, self.params, self.seed, self.name, window) if value is None else value


def install(shared):
    """Worker side of Resources.shared: seed the process cache once per plan."""
    for key, data in shared:
        if key not in _cache:
            _cache.put(key, pickle.loads(data))


class SurfaceTiles:
    """Exact raw height and wet mask at integer world cells.

    Reads the active field store where it covers a query; elsewhere evaluates
    world-aligned 128-square blocks once per process and keeps their 64-square tiles.
    """
    def __init__(self, resources):
        self.resources = resources
        self.key = resources.key('surface')

    def _evaluate(self, bx, bz):
        from .data import Region
        from .fields import Context
        from .water import sample_water
        r = self.resources
        region = Region(bx * 2 * SURFACE_TILE, bz * 2 * SURFACE_TILE, 2 * SURFACE_TILE, 2 * SURFACE_TILE)
        ctx = Context.for_region(r.pack.fields, r.params, r.seed, region, resources=r)
        height = ctx.get(r.pack.height_field)
        clipped = np.clip(height, r.params['world.y_min'], r.params['world.y_max'])
        ctx.put(r.pack.height_field, clipped)
        _, wet = sample_water(ctx, r.pack, clipped)
        tiles = {}
        for dz in range(2):
            for dx in range(2):
                tile = (slice(dz * SURFACE_TILE, (dz + 1) * SURFACE_TILE), slice(dx * SURFACE_TILE, (dx + 1) * SURFACE_TILE))
                key = (2 * bx + dx, 2 * bz + dz)
                arrays = height[tile].copy(), wet[tile].copy()
                for a in arrays:
                    a.setflags(write=False)
                tiles[key] = _surface.put((self.key, *key), arrays)
        return tiles

    def get_many(self, coordinates):
        from .data import Region
        from .store import current
        store = current()
        result = {}
        for tx, tz in dict.fromkeys(coordinates):
            region = Region(tx * SURFACE_TILE, tz * SURFACE_TILE, SURFACE_TILE, SURFACE_TILE)
            if store is not None and store.covers(region):
                index = store.region.slices(region)
                result[(tx, tz)] = store.arrays['raw'][index], store.arrays['wet'][index]
                continue
            result[(tx, tz)] = _surface.get((self.key, tx, tz), lambda: self._evaluate(tx // 2, tz // 2)[(tx, tz)])
        return result

    def get(self, tx, tz):
        return self.get_many(((tx, tz),))[(tx, tz)]

    def values(self, x, z):
        """Raw heights and wet flags at broadcast integer cells."""
        x, z = np.broadcast_arrays(np.asarray(x), np.asarray(z))
        ix = np.floor(x).astype(np.int64).ravel()
        iz = np.floor(z).astype(np.int64).ravel()
        heights, wet = np.empty(len(ix)), np.empty(len(ix), bool)
        keys = np.stack((ix // SURFACE_TILE, iz // SURFACE_TILE), axis=1)
        unique, inverse = np.unique(keys, axis=0, return_inverse=True)
        tiles = self.get_many(tuple(map(int, key)) for key in unique)
        for i, key in enumerate(unique):
            chosen = inverse.ravel() == i
            h, w = tiles[tuple(map(int, key))]
            heights[chosen] = h[iz[chosen] % SURFACE_TILE, ix[chosen] % SURFACE_TILE]
            wet[chosen] = w[iz[chosen] % SURFACE_TILE, ix[chosen] % SURFACE_TILE]
        return heights.reshape(x.shape), wet.reshape(x.shape)

    def rectangle(self, x0, z0, x1, z1):
        """Exact min/max raw height and wet count over integer half-open world cells."""
        from .data import Region
        from .store import current
        store, region = current(), Region(x0, z0, x1 - x0, z1 - z0)
        if store is not None and store.covers(region):
            index = store.region.slices(region)
            h = store.arrays['raw'][index]
            return float(h.min()), float(h.max()), int(np.count_nonzero(store.arrays['wet'][index]))
        lo, hi, wet_count = float('inf'), -float('inf'), 0
        for tz in range(z0 // SURFACE_TILE, (z1 - 1) // SURFACE_TILE + 1):
            for tx in range(x0 // SURFACE_TILE, (x1 - 1) // SURFACE_TILE + 1):
                h, w = self.get(tx, tz)
                a, b = max(x0 - tx * SURFACE_TILE, 0), min(x1 - tx * SURFACE_TILE, SURFACE_TILE)
                c, d = max(z0 - tz * SURFACE_TILE, 0), min(z1 - tz * SURFACE_TILE, SURFACE_TILE)
                lo, hi = min(lo, float(h[c:d, a:b].min())), max(hi, float(h[c:d, a:b].max()))
                wet_count += int(np.count_nonzero(w[c:d, a:b]))
        return lo, hi, wet_count
