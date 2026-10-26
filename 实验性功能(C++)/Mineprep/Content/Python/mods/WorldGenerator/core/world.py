"""Plans -> field store (2D reference once over the working domain) -> entity tiles -> assembly.

`generate_tile` is the entity unit of work for every executor. It reads the
2D reference from a field store crop and returns only compact arrays, so
results are cheap to send between processes.
"""

from dataclasses import dataclass, field, replace
import hashlib
import json
from time import perf_counter

import numpy as np

from .data import Region, check_cancel, require_int
from .fields import Context, active_passes, pass_order
from .features import scatter
from .noise import NOISE_VERSION
from .noise3 import VERSION as NOISE3_VERSION
from .density import VERSION as DENSITY_VERSION, task_scope
from .pack import PackChangedError, load_pack, pack_roots
from .shell import WorldArrays, column_shell, shell_counts
from .spec import WorldSpec
from .store import active as active_store, crop_passes, evaluate_passes, evaluate_store, join, margin, strips
from .tiles import get_executor, run_tiles
from .water import validate_levels, displayed as water_displayed
from .planning import Resources, install as install_plans, parallel_windows, window_values
from . import geometry, fluids
from . import multi_features

GENERATOR_VERSION = "r22-region-pass-windows"
VOLUME_VERSION = "r40-volume-templates-1"
DEFAULT_TILE = 256  # measured fastest single-thread size (1024² ridges: 64→1.30 s, 128→0.58 s, 256→0.47 s)
MAX_CELLS = 16_777_216
MAX_INSTANCES = 4_000_000


def world_key(spec, pack=None, *, _source=None, _mask_sources=None):
    """Cache key over everything that changes blocks: code versions, pack files, resolved params."""
    pack = pack or load_pack(spec.pack)
    image_key = None
    if spec.heightmap is not None:
        from .heightmap import capture, input_key
        image_key = input_key(spec.heightmap, _source or capture(spec.heightmap))
    from . import masks
    mask_keys = masks.keys(spec, masks.sources(spec) if _mask_sources is None else _mask_sources)
    raw = json.dumps({"generator": GENERATOR_VERSION, "noise": NOISE_VERSION, "noise3": NOISE3_VERSION,
                      **({'volume': VOLUME_VERSION} if pack.density is not None and pack.density.base == 'volume' else {}),
                      "density": DENSITY_VERSION, "pack": spec.pack,
                      "fingerprint": pack.generation_fingerprint, "seed": spec.seed,
                      "region": spec.region.to_list(), "params": pack.resolve(spec).to_dict(),
                      **({'heightmap': image_key} if image_key is not None else {}),
                      **({'masks': mask_keys} if mask_keys else {})},
                     sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class _GenerationInput:
    """Request snapshot; only plain values and a WorldSpec cross process boundaries.

    The pack is loaded once per process and request. A worker refuses to run
    if the pack files changed after the request was captured.
    """
    spec: WorldSpec
    roots: tuple
    fingerprint: str
    key: str
    heightmap_source: object = None
    plans: tuple = ()  # Resources.shared(), so worker processes skip eager planning
    region_passes: object = ()  # precomputed (Region, ndarray) map for @region_pass fields
    mask_sources: object = field(default_factory=dict)

    @classmethod
    def capture(cls, spec, *, defer_heightmap=False, cancel_event=None):
        roots = pack_roots()
        pack = load_pack(spec.pack, roots=roots)
        has_masks = spec.vegetation_mask is not None or spec.clearance_mask is not None
        source = None
        if spec.heightmap is not None:
            from .heightmap import capture, supported
            if not supported(pack):
                raise ValueError('heightmap requires vanilla or a derived pack retaining its height chain')
            if defer_heightmap:
                return cls(spec, roots, pack.fingerprint, '')
            source = capture(spec.heightmap, cancel_event=cancel_event)
        if defer_heightmap and has_masks:
            return cls(spec, roots, pack.fingerprint, '')
        from . import masks
        inputs = masks.sources(spec, cancel_event=cancel_event)
        request = cls(spec, roots, pack.fingerprint,
                      world_key(spec, pack, _source=source, _mask_sources=inputs), source, mask_sources=inputs)
        if source is None and not inputs:
            object.__setattr__(request, '_pack', pack)
        return request

    def resolved(self, cancel_event=None):
        """Resolve deferred editor input on a worker before any result cache lookup."""
        if ((self.spec.heightmap is None or self.heightmap_source is not None)
                and all(getattr(self.spec, kind+'_mask') is None or kind in self.mask_sources
                        for kind in ('vegetation','clearance'))):
            return self
        from .heightmap import capture
        source = self.heightmap_source
        if self.spec.heightmap is not None and source is None:
            source = capture(self.spec.heightmap, cancel_event=cancel_event)
        from . import masks
        inputs = masks.sources(self.spec, cancel_event=cancel_event)
        return replace(self, key=world_key(self.spec, self.pack, _source=source, _mask_sources=inputs),
                       heightmap_source=source, mask_sources=inputs)

    def __getstate__(self):
        return {k: v for k, v in self.__dict__.items() if k != '_pack'}

    @property
    def pack(self):
        pack = self.__dict__.get('_pack')
        if pack is None:
            pack = load_pack(self.spec.pack, roots=self.roots)
            if pack.fingerprint != self.fingerprint:
                raise PackChangedError()
            if self.heightmap_source is not None:
                from .heightmap import bind
                flat = self.spec.overrides.get('terrain.flat', pack.preset_values(self.spec.preset).get(
                    'terrain.flat', pack.params['terrain.flat'].default))
                pack = bind(pack, self.spec.heightmap, self.heightmap_source, flat=flat)
            if self.mask_sources:
                from .masks import bind as bind_masks
                pack = bind_masks(pack, self.spec, self.mask_sources)
            object.__setattr__(self, '_pack', pack)
        return pack


def check_budgets(spec, max_cells, max_instances):
    """Check every request, including requests that will reuse cached data."""
    if not isinstance(spec, WorldSpec):
        raise ValueError("spec must be a WorldSpec")
    require_int("max_cells", max_cells, 1, 2**40)
    require_int("max_instances", max_instances, 1, 2**40)
    region = spec.region
    if region.cells > max_cells:
        raise ValueError(f"region {region.width}×{region.depth}={region.cells:,} cells exceeds "
                         f"max_cells={max_cells:,}")


@dataclass(frozen=True)
class TileResult:
    region: Region
    xyz: np.ndarray         # int32[N,3], relative to the world region origin
    types: np.ndarray       # uint16[N] pack block IDs
    solid: int
    plants: object = None
    stages: dict = field(default_factory=dict)
    diagnostics: dict = field(default_factory=dict)
    geometry_views: object = None
    fluid_layers: object = None
    feature_data: object = None
    feature_candidates: int = 0
    feature_unsupported: tuple = ()
    feature_removed_plants: int = 0
    scatter_counts: tuple = ()
    soft_mask: object = None  # aligned ordinary output cells
    plant_owners: object = None  # pack feature ID + 1, aligned with plants
    landscape_surfaces: object = None  # sparse true upward faces, local X/Y/Z + pack block ID
    floor_scatter: object = None  # sparse all-layer single-cell decorations
    surface_blocked: object = None  # volume_features.blocked_tops, absolute XYZ


def displayed_water(pack, params, levels, wet):
    water_y = np.floor(levels)
    return wet & (water_y >= params['world.y_min']) & (water_y < params['world.y_max']) & water_displayed(pack, params)


def _filter_plants(plants, owners, height, data, pack, tile, world_region, y_min, y_max):
    """Batch exact hard-cell exclusion; scatter never enters box competition."""
    categories = {f.id: f.category for f in pack.feature_defs}
    for owner, feature in enumerate(pack.feature_defs, 1):
        if feature.type != 'surface_scatter':
            continue
        use = (owners == owner) & (plants != 0)
        if not use.any():
            continue
        overlap = feature.allow_overlap_categories
        if len(data.xyz):
            blocked = np.array([categories[item.id[0]] not in overlap for item in data.instances], bool)
            p = data.xyz[blocked[data.owners]]
            x, z = p[:, 0] - tile.x0 + world_region.x0, p[:, 2] - tile.z0 + world_region.z0
            hit = p[:, 1] == np.ceil(height[z, x])
            selected = use[z[hit], x[hit]]
            plants[z[hit][selected], x[hit][selected]] = 0
        models = tuple(m for m in data.models if categories[m.id[0]] not in overlap)
        if models:
            from .templates import ModelIndex
            z, x = np.nonzero(use & (plants != 0))
            p = np.column_stack((x + tile.x0, np.ceil(height[z, x]).astype(np.int64), z + tile.z0))
            hit = ModelIndex(models, y_min, y_max).occupied(p)
            plants[z[hit], x[hit]] = 0


def generate_tile(spec, tile, world_region, keep_fields=(), *, _input=None, max_instances=MAX_INSTANCES,
                  cancel_event=None, _store=None):
    """Pure entity stage over one tile; the 2D reference comes from a field store covering it."""
    check_cancel(cancel_event)
    request = _input or _GenerationInput.capture(spec)
    pack = request.pack
    params = pack.resolve(spec)
    passes = request.region_passes
    if not passes and any(f.region_pass for f in pack.fields.values()):
        if _store is not None:
            passes = {k: (_store.region, _store.arrays[k]) for k, f in pack.fields.items()
                      if f.region_pass and k in _store.arrays}
        else:
            r = Resources(pack, params, spec.seed, region=world_region)
            passes = evaluate_passes(pack, params, spec.seed, world_region, r)
            passes = evaluate_passes(pack, params, spec.seed, world_region, r, passes, with_resources=True)
    with active_passes(passes, world_region):
        store = _store if _store is not None else evaluate_store(
            pack, params, spec.seed, tile.expanded(margin(pack)),
            Resources(pack, params, spec.seed, region=world_region))
        with active_store(store), task_scope(request.key):
            return _tile_entities(request, pack, params, store, tile, world_region, max_instances, cancel_event)


def _tile_shell(pack, params, seed, tile, world_region, reference, visible_water, plants, soft, feature_data,
                max_instances, cancel_event):
    """Extract 3D carved/volume shell or 2D column shell, and apply terrain materials."""
    core = (slice(1, -1), slice(1, -1))
    ctx = reference.ctx
    raw, height, columns, biome_ids = reference.raw, reference.height, reference.columns, reference.biomes
    soil_depth = reference.soil_depth[core] if np.ndim(reference.soil_depth) else reference.soil_depth
    y_min = params['world.y_min']
    padded = tile.expanded(1)
    tops = np.ceil(height).astype(np.int32) - 1
    x, z = padded.coordinates()
    outside = ((x < world_region.x0) | (x >= world_region.x0 + world_region.width)
               | (z < world_region.z0) | (z >= world_region.z0 + world_region.depth))
    extras_count = int(visible_water.sum()) + int(np.count_nonzero(plants)) + len(feature_data.xyz)
    diagnostics, geometry_seconds, collector = {}, {}, None
    if geometry.enabled(pack, params):
        from .projection import Collector
        collector = Collector(world_region, tile, params, kind='carved' if geometry.height_mode(pack) else 'solid')
        layout_start = perf_counter()
        bounds = geometry.plan_bounds(pack, params, seed, padded, ctx.resources)
        layout_seconds = perf_counter() - layout_start
        if bounds != () and plants.any():
            support, _ = geometry.sample(pack, params, seed, x[:, None, :], tops[:, None, :],
                                         z[:, None, :], tops, resources=ctx.resources)
            plants[~support[1:-1, 0, 1:-1]] = 0
            if (soft & (plants != 0)).any():
                check_cancel(cancel_event)
                occupied, _ = geometry.sample(pack, params, seed, x[:, None, :], (tops + 1)[:, None, :],
                                              z[:, None, :], tops, resources=ctx.resources)
                plants[soft & occupied[1:-1, 0, 1:-1]] = 0
        extras_count = int(visible_water.sum()) + int(np.count_nonzero(plants)) + len(feature_data.xyz)
        if extras_count > max_instances:
            raise ValueError(f'visible cells {extras_count:,} exceed max_instances={max_instances:,} before sparse allocation')
        ref_tops = (np.ceil(raw).astype(np.int64) - 1 if pack.shell_materials is not None
                    and (pack.shell_materials.enabled_param is None or params[pack.shell_materials.enabled_param]) else None)
        xyz, types, solid_count, geometry_seconds, diagnostics = geometry.shell(
            pack, params, seed, tile, world_region, tops, columns[core],
            max_instances=max_instances - extras_count, wet=reference.wet, cancel_event=cancel_event,
            resources=ctx.resources, bounds=bounds, projection=collector, biomes=biome_ids[core],
            soil_depth=soil_depth, reference_tops=ref_tops)
        geometry_seconds['layout'] = layout_seconds
        geometry_seconds['projection'] = collector.seconds
        diagnostics['cavity_volume'] = collector.cells if geometry.height_mode(pack) else 0
    else:
        tops[outside] = y_min - 1
        counted = shell_counts(tops, y_min)
        if int(counted[2].sum()) + extras_count > max_instances:
            raise ValueError(f'visible cells exceed max_instances={max_instances:,} before sparse allocation')
        col, y, role = column_shell(tops, y_min, soil_depth, counted=counted)
        cols = columns[core].reshape(-1, columns.shape[-1])
        xyz = np.empty((len(col), 3), np.int32)
        xyz[:, 0] = col % tile.width + (tile.x0 - world_region.x0)
        xyz[:, 1] = y
        xyz[:, 2] = col // tile.width + (tile.z0 - world_region.z0)
        types = cols[col, role]
        solid_count = int(np.maximum(tops[core].astype(np.int64) - y_min + 1, 0).sum())
    if pack.terrain_materials is not None:
        from .materials import apply_terrain
        types = apply_terrain(pack, params, seed, xyz, types, ctx, biome_ids,
                              origin=(world_region.x0, world_region.z0))
    return xyz, types, solid_count, tops[core], collector, geometry_seconds, diagnostics


def _tile_entities(request, pack, params, store, tile, world_region, max_instances, cancel_event):
    spec = request.spec
    y_min, y_max = params['world.y_min'], params['world.y_max']
    padded = tile.expanded(1)
    resources = Resources(pack, params, spec.seed, region=world_region)
    resources.cancel_event = cancel_event
    reference = store.reference(padded, pack, params, spec.seed, resources)
    ctx = reference.ctx
    height, columns, biome_ids = reference.height, reference.columns, reference.biomes
    levels, wet = reference.levels, reference.wet
    core = (slice(1, -1), slice(1, -1))
    water = displayed_water(pack, params, levels, wet)[core]
    water_y = np.floor(levels)[core]

    started = perf_counter()
    feature_data, feature_candidates, feature_unsupported = multi_features.generate(
        pack, params, spec.seed, tile, world_region, ctx.resources, max_instances)
    feature_seconds = perf_counter() - started

    started = perf_counter()
    scatter_owners = np.zeros(ctx.shape, np.uint16)
    plants = scatter(ctx, pack, biome_ids, columns, height, wet_mask=wet if pack.water else None,
                     water_levels=levels, owners=scatter_owners)[core].copy()
    owners = scatter_owners[core].copy()
    before = int(np.count_nonzero(plants))
    _filter_plants(plants, owners, height[core], feature_data, pack, tile, world_region, y_min, y_max)
    feature_removed_plants = before - int(np.count_nonzero(plants))
    soft = np.array([False, *(getattr(f, 'soft', False) for f in pack.feature_defs)], bool)[owners]
    plant_seconds = perf_counter() - started

    started = perf_counter()
    visible_water = water
    if len(feature_data.xyz) and water.any():
        full = np.array([pack.block_defs[n].occludes for n in pack.blocks])
        p = feature_data.xyz[full[feature_data.types]]
        xx, zz = p[:, 0] - tile.x0 + world_region.x0, p[:, 2] - tile.z0 + world_region.z0
        on_plane = p[:, 1] == water_y[zz, xx]
        visible_water = water.copy()
        visible_water[zz[on_plane], xx[on_plane]] = False
    replaced_surfaces = int(water.sum() - visible_water.sum())

    xyz, types, solid_count, top, collector, geometry_seconds, diagnostics = _tile_shell(
        pack, params, spec.seed, tile, world_region, reference, visible_water, plants, soft,
        feature_data, max_instances, cancel_event)
    surfaces = collector.surfaces(types) if collector and not geometry.height_mode(pack) else None

    fluid_start = perf_counter()
    fluid_layers = fluids.sample_layers(pack, params, spec.seed, tile, ctx.resources)
    fluid_seconds = perf_counter() - fluid_start if fluids.enabled(pack, params) else 0.
    diagnostics['feature_replaced_surface_cells'] = replaced_surfaces

    extras = []
    for mask, ys, ids in ((visible_water, water_y, pack.blocks.index(pack.water['block']) if pack.water else 0),
                          (plants != 0, top + 1, plants.astype(np.int32) - 1)):
        zz, xx = np.nonzero(mask)
        points = np.empty((len(xx), 3), np.int32)
        points[:, 0] = xx + tile.x0 - world_region.x0
        points[:, 2] = zz + tile.z0 - world_region.z0
        points[:, 1] = ys if np.isscalar(ys) else ys[mask]
        values = np.full(len(xx), ids, np.uint16) if np.isscalar(ids) else ids[mask].astype(np.uint16)
        extras.append((points, values))
    if len(fluid_layers.xyz) and water_displayed(pack, params):
        points = fluid_layers.xyz.copy()
        points[:, 0] -= world_region.x0
        points[:, 2] -= world_region.z0
        extras.append((points, np.full(len(points), pack.blocks.index(pack.fluids.block), np.uint16)))

    floor_scatter, scatter_seconds = None, 0.
    from .floor_scatter import active, scatter as scatter_floors
    if active(pack, params):
        scatter_start = perf_counter()
        supports = surfaces
        halo = collector.floor_halo
        if halo is not None and len(halo):
            if pack.terrain_materials is not None:
                from .materials import apply_terrain
                halo[:, 3] = apply_terrain(pack, params, spec.seed, halo[:, :3], halo[:, 3], ctx, biome_ids,
                                           origin=(world_region.x0, world_region.z0))
            supports = np.concatenate((supports, halo))
        floor_scatter = scatter_floors(ctx, pack, tile, world_region, supports, biome_ids[core],
                                       water, water_y, feature_data, max_instances=max_instances - len(xyz)
                                       - len(feature_data.xyz) - sum(len(p) for p, _ in extras))
        scatter_seconds = perf_counter() - scatter_start

    surface_blocked = None
    if not geometry.height_mode(pack):
        from .volume_features import blocked_tops
        cells = (feature_data, *(() if floor_scatter is None else (floor_scatter,)))
        surface_blocked = blocked_tops(pack, params, spec.seed, world_region, np.concatenate([c.xyz for c in cells]),
                                       np.concatenate([c.types for c in cells]).astype(np.intp), feature_data.models,
                                       ctx.resources)
    if len(xyz) + sum(len(p) for p, _ in extras) + len(feature_data.xyz) > max_instances:
        raise ValueError(f'visible cells exceed max_instances={max_instances:,}')
    if any(len(p) for p, _ in extras):
        plant_start = len(xyz) + len(extras[0][0])
        xyz = np.concatenate([xyz, *(p for p, _ in extras)])
        types = np.concatenate([types, *(t for _, t in extras)])
    soft_mask = None
    if (soft & (plants != 0)).any():
        soft_mask = np.zeros(len(xyz), bool)
        soft_mask[plant_start:plant_start + len(extras[1][0])] = soft[plants != 0]
    owners[plants == 0] = 0
    shell_seconds = perf_counter() - started
    for name, value in ctx.resources.report.values.items():
        if name.endswith('_seconds') or name in ('groundwater_sampling', 'groundwater_connectivity',
                                                 'density_noise', 'density_interpolation'):
            geometry_seconds[name] = value
        else:
            diagnostics[name] = value
    return TileResult(
        tile, xyz, types, solid_count, plants,
        dict(vegetation=plant_seconds, features=feature_seconds, shell=shell_seconds,
             floor_scatter=scatter_seconds, groundwater=fluid_seconds, **geometry_seconds),
        diagnostics, collector.finish() if collector else None, fluid_layers,
        feature_data, feature_candidates, feature_unsupported, feature_removed_plants,
        tuple((pack.feature_defs[int(owner) - 1].id, int(count)) for owner, count in
              zip(*np.unique(owners[plants != 0], return_counts=True)))
        + (floor_scatter.counts if floor_scatter is not None else ()), soft_mask, owners,
        surfaces, floor_scatter, surface_blocked)


@dataclass(frozen=True)
class World:
    """Everything one generation produced; arrays are read-only snapshots."""
    spec: WorldSpec
    key: str
    pack: object            # Pack (biomes, blocks, labels)
    params: object          # Params
    heights: np.ndarray     # float32[Z,X]
    biome_ids: np.ndarray   # uint16[Z,X]
    columns: np.ndarray     # uint16[Z,X,3] into pack.blocks
    fields: dict            # name -> float32[Z,X]
    arrays: WorldArrays     # visible cells, types index arrays.names
    stats: dict
    water_mask: np.ndarray
    plant_ids: np.ndarray   # zero = empty, otherwise pack block ID + 1
    water_levels: object = None  # float64[Z,X], semantic local water elevations
    wet_mask: object = None      # bool[Z,X], independent of water visibility
    geometry_views: object = None
    fluid_layers: object = None
    feature_instances: tuple = ()
    feature_cells: object = None  # read-only WorldArrays views; same names/type IDs as arrays
    column_index: object = None  # stage-local interval occupancy; no persistent cache
    model_instances: tuple = ()  # complete render models, anchor-owned and immutable
    model_index: object = None   # logical template column occupancy, never render cells
    soft_mask: object = None    # read-only, aligned with ordinary arrays; soft decoration
    plant_owners: object = None  # read-only pack feature ID + 1 per scattered plant
    landscape_surfaces: object = None  # preview-only sparse faces; no dense occupancy retained

    @property
    def region(self):
        return self.spec.region

    def biome_fractions(self):
        counts = np.bincount(self.biome_ids.ravel(), minlength=len(self.pack.biomes))
        return {b.id: float(c / self.biome_ids.size) for b, c in zip(self.pack.biomes, counts)}


@dataclass(frozen=True)
class Overview:
    """Exact reference maps, deliberately without output cells or preparation state."""
    spec: WorldSpec
    key: str
    pack: object
    params: object
    heights: np.ndarray
    biome_ids: np.ndarray
    columns: np.ndarray
    fields: dict
    stats: dict
    water_mask: np.ndarray
    water_levels: np.ndarray
    wet_mask: np.ndarray

    @property
    def region(self):
        return self.spec.region

    def biome_fractions(self):
        return World.biome_fractions(self)


def _field_store(request, domain, executor, *, keep_fields=(), cancel_event=None, progress=None, validate=False):
    """Evaluate the 2D reference over domain once, as row strips on the executor."""
    pieces = strips(domain, executor.workers)
    parts = []
    def collect(task, result):
        parts.append(result)
        if progress:
            progress(len(parts), len(pieces))
    base = replace(request, region_passes=())
    pad = 1 + request.pack.reference_halo + max(pass_order(request.pack.fields)[1].values(), default=0)
    run_tiles(executor, _strip_task, ((replace(base, region_passes=crop_passes(request.region_passes, s.expanded(pad))),
                                       s, validate, keep_fields) for s in pieces),
              on_result=collect, cancel_event=cancel_event)
    check_cancel(cancel_event)
    return join(domain, parts)


def _reference_maps(request, store, keep_fields):
    """Output-region reference arrays, copied out of the field store."""
    pack, spec = request.pack, request.spec
    params = pack.resolve(spec)
    if pack.reference_mask_field is not None:
        keep_fields = tuple(dict.fromkeys((*keep_fields,pack.reference_mask_field)))
    with active_passes(request.region_passes, spec.region):
        ref = store.reference(spec.region, pack, params, spec.seed, Resources(pack, params, spec.seed, region=spec.region, validate=False))
        maps = dict(heights=ref.height.astype(np.float32), biome_ids=ref.biomes.copy(),
                    columns=np.ascontiguousarray(ref.columns),
                    water_mask=displayed_water(pack, params, ref.levels, ref.wet), water_levels=ref.levels.copy(),
                    wet_mask=ref.wet.copy(), fields={n: ref.ctx.get(n).astype(np.float32) for n in keep_fields},
                    clipped=int(np.count_nonzero(ref.height != ref.raw)))
        if pack.reference_mask_field is not None:
            mask = maps['fields'][pack.reference_mask_field]
            if not np.isfinite(mask).all() or np.any((mask < 0) | (mask > 1)):
                raise ValueError('reference_mask_field must contain finite values in 0..1')
    for a in (*(v for k, v in maps.items() if k not in ('fields', 'clipped')), *maps['fields'].values()):
        a.setflags(write=False)
    return maps


def _plan_and_passes(request, pack, params, region, executor, cancel_event, *, overview=False):
    resources = Resources(pack, params, request.spec.seed, region=region, validate=False)
    passes = evaluate_passes(pack, params, request.spec.seed, region, resources)
    request = replace(request, region_passes=passes)
    with active_passes(passes, region):
        if executor.mode == 'processes':
            with parallel_windows(_window_runner(request, executor, cancel_event)):
                if overview:
                    for name in sorted({r for f in pack.fields.values() for r in f.resources}):
                        resources.get(name)
                else:
                    resources.validate_region(region)
            request = replace(request, plans=resources.shared())
        elif not overview or any(f.region_pass and (f.resources or any(pack.fields[d].resources for d in f.deps))
                                 for f in pack.fields.values()):
            resources.validate_region(region)
    passes = evaluate_passes(pack, params, request.spec.seed, region, resources, passes, with_resources=True)
    return replace(request, region_passes=passes), resources


def build_overview(spec, *, execution='serial', workers=4, keep_fields=(), cancel_event=None, progress=None,
                   max_cells=MAX_CELLS, _input=None):
    """Evaluate exact 2D references only; no automatic upgrade to a complete World."""
    check_budgets(spec, max_cells, MAX_INSTANCES)
    check_cancel(cancel_event)
    started = perf_counter()
    request = (_input or _GenerationInput.capture(spec, cancel_event=cancel_event)).resolved(cancel_event)
    pack = request.pack
    params = pack.resolve(spec)
    names = tuple(keep_fields)
    for name in names:
        if name not in pack.fields and name != 'slope':
            raise ValueError(f'unknown field {name!r}')
    executor = get_executor(execution, workers)
    request, _ = _plan_and_passes(request, pack, params, spec.region, executor, cancel_event, overview=True)
    store = _field_store(request, spec.region, executor, keep_fields=names, cancel_event=cancel_event,
                         progress=progress, validate=spec.region)
    m = _reference_maps(request, store, names)
    arrays = (m['heights'], m['biome_ids'], m['columns'], m['water_mask'], m['water_levels'], m['wet_mask'],
              *m['fields'].values())
    result = Overview(spec, request.key, pack, params, m['heights'], m['biome_ids'], m['columns'], m['fields'],
                      dict(reference=True, seconds=perf_counter()-started, stages=store.stages,
                           height_min=float(m['heights'].min()), height_max=float(m['heights'].max()),
                           array_bytes=sum(a.nbytes for a in arrays)),
                      m['water_mask'], m['water_levels'], m['wet_mask'])
    if pack.heightmap is not None:
        from .heightmap import metrics
        result.stats['heightmap'] = metrics(request.heightmap_source, pack.heightmap)
        result.stats['heightmap'].update(sample_seconds=store.stages.get('heightmap_sampling', 0.),
                                        sample_points=int(store.heightmap_points))
    return result


def build_world(spec, *, execution="serial", workers=4, tile_size=DEFAULT_TILE, keep_fields=None,
                cancel_event=None, max_cells=MAX_CELLS, max_instances=MAX_INSTANCES, progress=None,
                on_stage=None, on_phase=None, _input=None):
    """Generate a region. Progress/phase callbacks run only in this calling thread.

    progress(done,total) describes entity tiles; on_phase(name) announces the
    surrounding root phases. phase_seconds measures non-overlapping wall time,
    including reference publication callbacks, not summed parallel tile work.
    """
    started = perf_counter()
    phase_seconds = {}
    phase_name, phase_started = None, started

    def phase(name):
        nonlocal phase_name, phase_started
        now = perf_counter()
        if phase_name is not None:
            phase_seconds[phase_name] = now - phase_started
        phase_name, phase_started = name, now
        if name is not None:
            check_cancel(cancel_event)
            if on_phase is not None:
                on_phase(name)
            check_cancel(cancel_event)

    phase('heightmap' if spec.heightmap is not None else 'planning')
    check_budgets(spec, max_cells, max_instances)
    request = (_input or _GenerationInput.capture(spec, cancel_event=cancel_event)).resolved(cancel_event)
    if spec.heightmap is not None:
        phase('planning')
    region = spec.region
    pack = request.pack
    params = pack.resolve(spec)
    if geometry.enabled(pack, params):
        require_int('tile_size', tile_size, 1, 4096)
        tile_size = min(tile_size, geometry.GEOMETRY_TILE)
    keep_fields = tuple(pack.biome_parameters) if keep_fields is None else tuple(keep_fields)
    planning_started = perf_counter()
    executor = get_executor(execution, workers)
    request, resources = _plan_and_passes(request, pack, params, region, executor, cancel_event)
    planning_seconds = perf_counter() - planning_started
    for name in keep_fields:
        if name not in pack.fields and name != "slope":
            raise ValueError(f"unknown field {name!r}")
    key = request.key
    plants = np.empty(region.shape, np.uint16)
    plant_owners = np.empty(region.shape, np.uint16)
    stages = dict(fields=0., surface=0., water=0., vegetation=0., shell=0.)
    tiles = list(region.tiles(tile_size))
    parts = [None] * len(tiles)
    projection_parts = [None] * len(tiles)
    surface_parts = [None] * len(tiles)
    fluid_parts = [None] * len(tiles)
    feature_parts = [None] * len(tiles)
    floor_parts = [None] * len(tiles)
    blocked_parts = [np.empty((0, 3), np.int64)]
    soft_parts = [None] * len(tiles)
    scatter_counts = []
    feature_instances, model_instances, unsupported = {}, {}, set()
    feature_candidates = 0
    feature_removed_plants = 0
    totals = dict(instances=0, solid=0, done=0)
    diagnostics = dict(geometry_slabs=0, geometry_voxels=0, geometry_work_array_bytes=0,
                       material_candidates=0, material_ore_noise_samples=0, material_ore_kind_samples=0,
                       terrain_material_candidates=0)

    def on_result(task, result):
        nonlocal feature_candidates, feature_removed_plants
        index = task[4]
        target = region.slices(result.region)
        plants[target] = result.plants
        plant_owners[target] = result.plant_owners
        for name, seconds in result.stages.items():
            stages[name] = stages.get(name, 0.) + seconds
        for name, value in result.diagnostics.items():
            diagnostics[name] = max(diagnostics.get(name, 0), value) if name.endswith('_bytes') else diagnostics.get(name, 0) + value
        parts[index] = (result.xyz, result.types)
        soft_parts[index] = result.soft_mask
        projection_parts[index] = result.geometry_views
        surface_parts[index] = result.landscape_surfaces
        fluid_parts[index] = result.fluid_layers
        feature_parts[index] = result.feature_data
        floor_parts[index] = result.floor_scatter
        if result.surface_blocked is not None:
            blocked_parts.append(result.surface_blocked)
        scatter_counts.extend(result.scatter_counts)
        feature_candidates += result.feature_candidates
        feature_removed_plants += result.feature_removed_plants
        unsupported.update(result.feature_unsupported)
        for item in result.feature_data.instances:
            previous = feature_instances.get(item.id)
            feature_instances[item.id] = multi_features.FeatureInstance(item.id, item.anchor, item.bounds,
                item.block_count + (previous.block_count if previous else 0))
        for item in result.feature_data.models: model_instances[item.id]=item
        totals["instances"] += (len(result.xyz) + len(result.feature_data.xyz) + len(result.feature_data.models)
                                + (len(result.floor_scatter.xyz) if result.floor_scatter is not None else 0))
        totals["solid"] += result.solid
        totals["done"] += 1
        if totals["instances"] > max_instances:
            raise ValueError(f"visible cells exceed max_instances={max_instances:,}; "
                             "reduce the region or raise the visible-cell budget")
        if progress:
            progress(totals["done"], len(tiles))

    task_cancel = cancel_event if execution != 'processes' else None
    phase('reference')
    reference_started = perf_counter()
    border = margin(pack)
    store = _field_store(request, region.expanded(border), executor, keep_fields=keep_fields, cancel_event=cancel_event)
    stages.update(store.stages)
    m = _reference_maps(request, store, keep_fields)
    heights, biome_ids, columns = m['heights'], m['biome_ids'], m['columns']
    water, levels, wet, fields = m['water_mask'], m['water_levels'], m['wet_mask'], m['fields']
    reference_seconds = perf_counter() - reference_started
    if on_stage is not None:
        empty = WorldArrays(region, np.empty((0,3),np.int32), np.empty(0,np.uint32), (), 0)
        no_plants = np.zeros(region.shape,np.uint16)
        for a in (no_plants, empty.xyz, empty.types):
            a.setflags(write=False)
        reference_world = World(spec,key,pack,params,heights,biome_ids,columns,fields,empty,
            dict(reference=True,seconds=perf_counter()-started,reference_seconds=reference_seconds,
                 planning_seconds=planning_seconds,height_min=float(heights.min()),
                 height_max=float(heights.max())),water,no_plants,levels,wet)
        phase('reference_publish')
        on_stage('reference', reference_world)
        check_cancel(cancel_event)
    phase('entities')
    tile_req = replace(request, region_passes=())
    pass_pad = 1 + pack.reference_halo + max(pass_order(pack.fields)[1].values(), default=0)
    def entity_tasks():
        for i, tile in enumerate(tiles):
            request_tile = tile_req
            if request.region_passes:
                window = tile.expanded(border)
                if geometry.enabled(pack, params):
                    window = resources.surface_region(window)
                request_tile = replace(tile_req, region_passes=crop_passes(request.region_passes, window.expanded(pass_pad)))
            yield request_tile, tile, region, max_instances, i, task_cancel, store.crop(tile.expanded(border))
    run_tiles(executor, _tile_task, entity_tasks(),
              on_result=on_result, cancel_event=cancel_event)
    check_cancel(cancel_event)
    compute = perf_counter() - started
    phase('assembly')
    from .templates import output_models
    models = output_models(tuple(model_instances[k] for k in sorted(model_instances)),region)
    model_index = None
    if models:
        from .templates import ModelIndex,definitions
        definitions(models)
        model_index = ModelIndex(models,params['world.y_min'],params['world.y_max'])
        if not geometry.height_mode(pack):
            from .floor_scatter import filter_models
            for i,part in enumerate(floor_parts):
                if part is not None and len(part.xyz):
                    filtered = filter_models(part,model_index,region,pack)
                    if filtered is not part:
                        scatter_counts.extend((name,-count) for name,count in part.counts)
                        scatter_counts.extend(filtered.counts)
                        floor_parts[i] = filtered
    active_features = [p for p in feature_parts if len(p.xyz)]
    active_floors = [p for p in floor_parts if p is not None and len(p.xyz)]
    fluid_layers=fluids.combine(fluid_parts,region,params)
    if len(fluid_layers.xyz) and (active_features or model_index is not None):
        opaque = np.array([pack.block_defs[n].occludes for n in pack.blocks],bool)
        claimed = [p.xyz[opaque[p.types]] for p in active_features]
        points = np.concatenate(claimed) if claimed else np.empty((0,3),np.int32)
        fluid_layers, removed = fluids.occlude_surfaces(
            fluid_layers,points+[region.x0,0,region.z0],model_index)
        if len(removed):
            removed = set(map(tuple,removed-[region.x0,0,region.z0]))
            fluid_id = pack.blocks.index(pack.fluids.block)
            for i,(points,types) in enumerate(parts):
                keep = np.ones(len(points),bool)
                ids = np.flatnonzero(types == fluid_id)
                keep[ids] = np.fromiter((tuple(p) not in removed for p in points[ids]),bool,len(ids))
                parts[i] = points[keep],types[keep]
                if soft_parts[i] is not None:
                    soft_parts[i] = soft_parts[i][keep]
    feature_start = sum(len(p[0]) for p in parts)
    xyz = np.concatenate([*(p[0] for p in parts), *(p.xyz for p in active_features), *(p.xyz for p in active_floors)])
    block_ids = np.concatenate([*(p[1] for p in parts), *(p.types for p in active_features), *(p.types for p in active_floors)])
    rotations = None
    if any(p.rotations is not None for p in active_features):
        rotations = np.zeros(len(xyz), np.uint8)
        start = feature_start
        for p in active_features:
            if p.rotations is not None:
                rotations[start:start+len(p.xyz)] = p.rotations
            start += len(p.xyz)
        rotations.setflags(write=False)
    used = np.unique(block_ids)
    # Validate across tile boundaries as well as inside padded tile contexts.
    validate_levels(levels, wet)
    fractions = levels[water] - np.floor(levels[water])
    uniform_offset = float(fractions[0]) if len(fractions) else 0.
    instance_offsets = None
    if len(fractions) and np.any(fractions != uniform_offset):
        instance_offsets = np.zeros(len(xyz), np.float64)
        is_water = block_ids == pack.blocks.index(pack.water['block'])
        positions = xyz[is_water]
        local = levels[positions[:, 2], positions[:, 0]]
        instance_offsets[is_water] = local - np.floor(local)
        uniform_offset = 0.
    if len(fluid_layers.xyz):
        # Underground surfaces can share a model with surface water, but never its
        # per-column elevation. Encode each surface's own fractional level.
        instance_offsets=np.zeros(len(xyz),np.float64)
        if pack.water:
            is_water=block_ids==pack.blocks.index(pack.water['block'])
            positions=xyz[is_water]
            surface=water[positions[:,2],positions[:,0]] & (positions[:,1]==np.floor(levels[positions[:,2],positions[:,0]]))
            ids=np.flatnonzero(is_water)[surface]
            instance_offsets[ids]=levels[xyz[ids,2],xyz[ids,0]]-np.floor(levels[xyz[ids,2],xyz[ids,0]])
        lookup={tuple(p-np.array([region.x0,0,region.z0])):float(v-np.floor(v)) for p,v in zip(fluid_layers.xyz,fluid_layers.levels)}
        mask=block_ids==pack.blocks.index(pack.fluids.block)
        for i in np.flatnonzero(mask):
            offset=lookup.get(tuple(xyz[i]))
            if offset is not None:instance_offsets[i]=offset
        if not np.any(instance_offsets):instance_offsets=None
        uniform_offset=0.
    remap = np.zeros(len(pack.blocks), np.uint32)
    remap[used] = np.arange(len(used), dtype=np.uint32)
    arrays = WorldArrays(region, xyz, remap[block_ids], tuple(pack.blocks[i] for i in used),
                         totals["solid"], block_defs=tuple(pack.block_defs[pack.blocks[i]] for i in used),
                         y_offsets=tuple(uniform_offset if pack.water and pack.blocks[i] == pack.water['block'] else 0.
                                         for i in used), instance_y_offsets=instance_offsets, rotations=rotations)
    soft_mask=None
    if any(mask is not None for mask in soft_parts) or any(p.soft.any() for p in active_floors):
        soft_mask=np.r_[np.concatenate([np.zeros(len(part[0]),bool) if mask is None else mask
                                        for part,mask in zip(parts,soft_parts)]),
                         np.zeros(sum(len(p.xyz) for p in active_features),bool),
                         *(p.soft for p in active_floors)]
        soft_mask.setflags(write=False)
    if instance_offsets is not None:
        instance_offsets.setflags(write=False)
    for array in (heights, biome_ids, columns, water, levels, wet, plants, plant_owners, arrays.xyz, arrays.types, *fields.values()):
        array.setflags(write=False)
    feature_cells = WorldArrays(region, arrays.xyz[feature_start:], arrays.types[feature_start:], arrays.names,
                                0, block_defs=arrays.block_defs,
                                rotations=None if rotations is None else rotations[feature_start:])
    stats = dict(seconds=perf_counter() - started, planning_seconds=planning_seconds, compute_seconds=compute, tiles=len(tiles),
                 reference_seconds=reference_seconds, reference_wait_seconds=planning_seconds+reference_seconds,
                 tile_size=tile_size, execution=executor.mode, workers=executor.workers,
                 visible=int(len(xyz)), solid=totals["solid"], clipped=m["clipped"],
                 height_min=float(heights.min()), height_max=float(heights.max()))
    stats.update(water=int(water.sum()), wet=int(wet.sum()), vegetation=int(np.count_nonzero(plants)), stages=stages)
    stats.update(diagnostics)
    feature_counts = np.bincount(feature_cells.types.astype(np.intp), minlength=len(arrays.names))
    stats.update(feature_candidates=feature_candidates, feature_instances=len(feature_instances),
                 feature_cells=feature_cells.count, feature_unsupported=tuple(sorted(unsupported)),
                 feature_removed_plants=feature_removed_plants,
                 feature_added_instances=feature_cells.count+len(models)-feature_removed_plants,
                 feature_block_counts={n: int(c) for n, c in zip(arrays.names, feature_counts) if c})
    from .feature_stats import summarize
    stats.update(summarize(pack, feature_parts, feature_instances.values(),
                           scatter_counts))
    stats.update(groundwater_bodies=len(fluid_layers.bodies),groundwater_surface_cells=len(fluid_layers.xyz),
                 groundwater_wet_runs=sum(len(b.runs) for b in fluid_layers.bodies),
                 surface_connected_bodies=sum(b.source is not None for b in fluid_layers.bodies))
    views = None
    if geometry.enabled(pack, params):
        from .projection import merge
        views = merge(region, params, projection_parts, kind='carved' if geometry.height_mode(pack) else 'solid')
        stats['projection_bytes'] = sum(p.depth.nbytes for p in views.values())
    surfaces = None
    if not geometry.height_mode(pack):
        surfaces = np.concatenate([p for p in surface_parts if p is not None])
        from .volume_features import add_surfaces
        surface_started=perf_counter()
        surfaces = add_surfaces(pack,params,spec.seed,region,surfaces,feature_cells,model_index,
                                blocked=np.concatenate(blocked_parts))
        stats['stages']['landscape_surfaces']=perf_counter()-surface_started
        surfaces.setflags(write=False)
        stats['landscape_surface_bytes'] = surfaces.nbytes
    world = World(spec, key, pack, params, heights, biome_ids, columns, fields, arrays, stats, water, plants, levels, wet, views,fluid_layers,
                  tuple(feature_instances[k] for k in sorted(feature_instances)), feature_cells,
                  model_instances=models,model_index=model_index,soft_mask=soft_mask,
                  plant_owners=plant_owners, landscape_surfaces=surfaces)
    from .postprocess import apply_world
    from .column_features import apply_world as apply_columns
    with active_passes(request.region_passes, region), active_store(store), task_scope(request.key):
        phase('column_features')
        world = apply_columns(world, max_instances=max_instances, cancel_event=cancel_event)
        phase('surface_processing')
        world = apply_world(world, max_instances=max_instances, cancel_event=cancel_event)
    del store
    phase('finalize')
    world.stats.update(model_instances=len(world.model_instances),
        soft_plants=0 if world.soft_mask is None else int(world.soft_mask.sum()),
        output_model_types=len(np.unique(world.arrays.types))+len({m.template.id for m in world.model_instances}),
        model_templates=len({i.template.id for i in world.model_instances}),
        model_logical_cells=sum(i.block_count for i in world.model_instances),
        model_array_bytes=0 if world.model_index is None else world.model_index.array_bytes,
        output_instances=world.arrays.count+len(world.model_instances))
    if world.stats['output_instances']>max_instances: raise ValueError('world model output exceeds max_instances')
    phase(None)
    world.stats.update(phase_seconds=phase_seconds,build_wall_seconds=perf_counter()-started)
    if pack.heightmap is not None:
        from .heightmap import metrics
        world.stats['heightmap'] = metrics(request.heightmap_source, pack.heightmap)
        world.stats['heightmap']['sample_seconds'] += stages.get('heightmap_sampling', 0.)
    return world


def _window_runner(request, executor, cancel_event):
    """Spread planner field windows over the pool, interleaved for balance, in input order."""
    def run(name, windows):
        values = [None] * len(windows)
        def collect(task, result):
            for i, value in zip(task[2], result):
                values[i] = value
        groups = (range(i, len(windows), executor.workers) for i in range(executor.workers))
        run_tiles(executor, _window_task, ((request, name, tuple(g), [windows[i] for i in g]) for g in groups if len(g)),
                  on_result=collect, cancel_event=cancel_event)
        return values
    return run


def _window_task(request, name, indices, windows):
    pack = request.pack
    params = pack.resolve(request.spec)
    with active_passes(request.region_passes, request.spec.region):
        return [window_values(pack, params, request.spec.seed, name, w) for w in windows]


def _strip_task(request, strip, validate=False, keep_fields=()):
    install_plans(request.plans)
    pack = request.pack
    params = pack.resolve(request.spec)
    with active_passes(request.region_passes, request.spec.region), task_scope(request.key):
        return evaluate_store(pack, params, request.spec.seed, strip,
                              Resources(pack, params, request.spec.seed, region=request.spec.region, validate=bool(validate)),
                              keep_fields)


def _tile_task(request, tile, region, max_instances, index, cancel_event=None, store=None):
    install_plans(request.plans)
    return generate_tile(request.spec, tile, region, _input=request, max_instances=max_instances,
                         cancel_event=cancel_event, _store=store)


def sample_fields(spec, names, region=None, *, tile_size=DEFAULT_TILE):
    """Evaluate named pack fields over a region (no surface, no shell); float32 arrays."""
    request = _GenerationInput.capture(spec)
    pack = request.pack
    params = pack.resolve(spec)
    region = region or spec.region
    resources = Resources(pack, params, spec.seed, region=region, validate=False)
    passes = evaluate_passes(pack, params, spec.seed, region, resources)
    # Only fields using resources need planning. Ordinary diagnostic fields stay cheap.
    def needs_resource(name):
        definition = pack.fields.get(name)
        if definition is None:
            return False
        return bool(definition.resources) or any(needs_resource(d) for d in (
            *definition.deps, *((definition.outside,) if isinstance(definition.outside, str) else ())))
    with active_passes(passes, region):
        if any(needs_resource(n) for n in names):
            resources.validate_region(region)
            passes = evaluate_passes(pack, params, spec.seed, region, resources, passes, with_resources=True)
    with active_passes(passes, region):
        output = {name: np.empty(region.shape, np.float32) for name in names}
        for tile in region.tiles(tile_size):
            ctx = Context.for_region(pack.fields, params, spec.seed, tile, resources=resources)
            target = region.slices(tile)
            for name in names:
                output[name][target] = ctx.get(name)
        return output
