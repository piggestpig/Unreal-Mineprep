"""FieldStore: one generation's 2D reference, evaluated once over its working domain.

The domain is the output region plus the widest margin any consumer reads
(feature competition, column features, surface processors). Entity tiles,
features, column features, surface processing and cave/fluid surface queries
slice it instead of evaluating fields again. Fields are pure functions of
world position, so a slice equals a direct evaluation; requests outside the
domain fall back to direct evaluation.
"""
from contextlib import contextmanager
import contextvars
from dataclasses import dataclass, field, replace

import numpy as np

from .data import Region
from .fields import Context, _active_passes, active_passes, pass_order
from .reference import Reference, evaluate

REFERENCE = ('raw', 'levels', 'wet', 'biomes', 'columns')
_active = contextvars.ContextVar('worldgen_field_store', default=None)


def margin(pack):
    """Blocks around a tile or region that downstream consumers read."""
    features = [max(abs(v) for row in f.bounds for v in (row[0], row[2]))
                for f in pack.features if f.type == 'multi_block']
    # Anchors extend by r, their competitors by 2r more, and the surface window by r+1.
    feature = 4 * max(features) + 2 if features else 0
    columns = max((f.radius for f in pack.features if f.type == 'column_field'), default=0)
    processors = max((p.radius for p in pack.surface_processors), default=0)
    return max(feature, columns + 1, processors + 1, 2)


@dataclass
class FieldStore:
    region: Region
    arrays: dict              # REFERENCE plus pack field arrays; the height field holds clipped heights
    soil_depth: object = None  # scalar, or None when arrays['soil_depth'] varies
    stages: dict = field(default_factory=dict)
    heightmap_points: int = 0
    step: int = 1

    def sample(self, name, region):
        if self.step == 1:
            return self.arrays[name][self.region.slices(region)]
        x = (np.arange(region.x0,region.x0+region.width)-self.region.x0)//self.step
        z = (np.arange(region.z0,region.z0+region.depth)-self.region.z0)//self.step
        return self.arrays[name][z[:,None],x]

    def covers(self, region):
        r = self.region
        return (r.x0 <= region.x0 and r.z0 <= region.z0 and region.x0 + region.width <= r.x0 + r.width
                and region.z0 + region.depth <= r.z0 + r.depth)

    def crop(self, region):
        if self.step != 1:
            from .coarse import aligned
            region = aligned(region,self.step)
            index = tuple(slice(s.start//self.step,s.stop//self.step) for s in self.region.slices(region))
            return FieldStore(region,{k:v[index] for k,v in self.arrays.items()},self.soil_depth,step=self.step)
        index = self.region.slices(region)
        return FieldStore(region, {k: v[index] for k, v in self.arrays.items()}, self.soil_depth)

    def context(self, region, pack, params, seed, resources=None):
        """A Context over region whose cache already holds every stored field."""
        ctx = Context.for_region(pack.fields, params, seed, region, resources=resources)
        for name, value in self.arrays.items():
            if name not in REFERENCE:
                ctx.put(name, self.sample(name,region))
        return ctx

    def reference(self, region, pack, params, seed, resources=None):
        ctx = self.context(region, pack, params, seed, resources)
        a = {k: self.sample(k,region) for k in REFERENCE}
        soil = self.sample('soil_depth',region) if self.soil_depth is None else self.soil_depth
        return Reference(ctx, a['raw'], ctx.get(pack.height_field), a['levels'], a['wet'], a['biomes'],
                         a['columns'], {}, soil)


class MixedStore(FieldStore):
    """One coarse source plus a local fine patch; no expanded persistent fields."""
    def __init__(self,base,fine):
        self.base,self.fine = base,fine
        self.region,self.arrays,self.step = base.region,base.arrays,base.step
        self.soil_depth = None
        self.stages = dict(base.stages)
        self.heightmap_points = base.heightmap_points + fine.heightmap_points
        for k,v in fine.stages.items(): self.stages[k] = self.stages.get(k,0.)+v

    def sample(self,name,region):
        def read(store,r):
            if name=='soil_depth' and store.soil_depth is not None:
                return np.full(r.shape,store.soil_depth,np.uint8)
            return store.sample(name,r)
        result = read(self.base,region)
        from .layout import intersection
        patch = intersection(region,self.fine.region)
        if patch is not None:
            result = result.copy()
            result[region.slices(patch)] = read(self.fine,patch)
        return result

    def crop(self,region):
        from .layout import intersection
        base = self.base.crop(region)
        patch = intersection(base.region,self.fine.region)
        return base if patch is None else MixedStore(base,self.fine.crop(patch))


def mixed_reference(pack,params,seed,region,resources,fields=()):
    """Standalone queries use the same pure sources as the generation's overlay."""
    from .coarse import aligned
    from .layout import intersection
    from .planning import Resources
    step = pack.layout.outer_step
    raw = replace(pack,layout=None,cell_step=step)
    res = Resources(raw,params,seed,region=resources.region,validate=False)
    base = evaluate_store(raw,params,seed,aligned(region,step),res,fields,step=step)
    patch = intersection(region,pack.layout.core) if not pack.layout.empty and step!=1 else None
    if patch is not None:
        fine_pack = replace(raw,cell_step=1)
        fields = tuple(dict.fromkeys((*fields,*(k for k in base.arrays if k in pack.fields))))
        fine = evaluate_store(fine_pack,params,seed,patch,Resources(fine_pack,params,seed,region=res.region,validate=False),fields)
        base = MixedStore(base,fine)
    return base.reference(region,pack,params,seed,resources)


def evaluate_passes(pack, params, seed, region, resources=None, passes=None, *, with_resources=False):
    """Evaluate whole-region passes in topological order over the working domain."""
    if not any(f.region_pass for f in pack.fields.values()):
        return {}
    order, pads, uses_res = pass_order(pack.fields)
    passes = dict(passes or {})
    domain = region.expanded(margin(pack)) if region is not None else None
    with active_passes(passes, region):
        for name in order:
            if name in passes or uses_res[name] != with_resources:
                continue
            definition = pack.fields[name]
            target = definition.region or (
                domain.expanded(1 + pack.reference_halo + pads[name]) if domain is not None else None)
            if target is not None:
                ctx = Context.for_region(pack.fields, params, seed, target, resources=resources)
                ctx.get(name)
                passes[name] = ctx._passes[name]
    return passes


def crop_passes(passes, region):
    """Slice pass windows, retaining prepared markers for disjoint domains."""
    if not passes:
        return ()
    out = {}
    for name, (r, arr) in passes.items():
        out[name] = (None, None)
        if r is None:
            continue
        x0, z0 = max(r.x0, region.x0), max(r.z0, region.z0)
        x1, z1 = min(r.x0 + r.width, region.x0 + region.width), min(r.z0 + r.depth, region.z0 + region.depth)
        if x0 < x1 and z0 < z1:
            sub = Region(x0, z0, x1 - x0, z1 - z0)
            out[name] = (sub, arr[r.slices(sub)])
    return out


def evaluate_store(pack, params, seed, region, resources, keep_fields=(), *, step=1):
    """Evaluate the complete reference over region.

    The pipeline slope has no neighbours on a context's outer ring, so the
    context is one cell wider and that ring is dropped, as tiles always did.
    """
    if _active_passes.get() is None and any(f.region_pass for f in pack.fields.values()):
        domain = (resources.region if resources is not None and resources.region is not None else region)
        passes = evaluate_passes(pack, params, seed, domain, resources)
        passes = evaluate_passes(pack, params, seed, domain, resources, passes, with_resources=True)
        with active_passes(passes, domain):
            return evaluate_store(pack, params, seed, region, resources, keep_fields, step=step)
    ctx = Context.for_region(pack.fields, params, seed, region.expanded(step), resources=resources,step=step)
    ref = evaluate(ctx, pack)
    for name in (*(k for k, f in pack.fields.items() if f.region_pass), *keep_fields):
        ctx.get(name)
    core = (slice(1, -1), slice(1, -1))
    arrays = {k: v[core] for k, v in ctx._cache.items()
              if isinstance(k, str) and isinstance(v, np.ndarray) and v.shape == ctx.shape}
    arrays.update(raw=ref.raw[core], levels=ref.levels[core], wet=ref.wet[core],
                  biomes=ref.biomes[core], columns=ref.columns[core])
    soil = ref.soil_depth
    if np.ndim(soil):
        arrays['soil_depth'] = soil[core]
        soil = None
    points = pack.heightmap.sample_stats['points'] if pack.heightmap is not None else 0
    return FieldStore(region, arrays, soil, dict(ref.stages), points, step)


def join(region, parts):
    """Assemble strip stores into one domain store."""
    first = parts[0]
    step = first.step
    arrays = {}
    slices = [tuple(slice(s.start//step,s.stop//step) for s in region.slices(p.region)) for p in parts]
    for name in tuple(set.intersection(*(set(p.arrays) for p in parts))):
        value = first.arrays[name]
        target = np.empty((region.depth//step,region.width//step,*value.shape[2:]), value.dtype)
        for part, index in zip(parts, slices):
            target[index] = part.arrays.pop(name)
        arrays[name] = target
    soil = first.soil_depth if all(p.soil_depth == first.soil_depth for p in parts) else None
    if soil is None and 'soil_depth' not in arrays:
        target = np.empty((region.depth//step,region.width//step), np.uint8)
        for part, index in zip(parts, slices):
            target[index] = part.arrays.pop('soil_depth', part.soil_depth)
        arrays['soil_depth'] = target
    stages = {}
    for part in parts:
        for name, seconds in part.stages.items():
            stages[name] = stages.get(name, 0.) + seconds
    return FieldStore(region, arrays, soil, stages, sum(p.heightmap_points for p in parts),step)


def strips(region, count):
    """Split region into about count row strips."""
    rows = -(-region.depth // max(1, count))
    return [Region(region.x0, z, region.width, min(rows, region.z0 + region.depth - z))
            for z in range(region.z0, region.z0 + region.depth, rows)]


@contextmanager
def active(store):
    """Make store the job's field store for surface queries in this thread."""
    token = _active.set(store)
    try:
        yield store
    finally:
        _active.reset(token)


def current():
    return _active.get()


def biomes(pack, params, seed, region, resources=None):
    """Biome indices over region: a store slice when available, else evaluated."""
    store = current()
    if store is not None and store.covers(region):
        return store.sample('biomes',region)
    if pack.layout is not None:
        from .layout import intersection
        raw = replace(pack,layout=None,cell_step=pack.layout.outer_step)
        result = biomes(raw,params,seed,region,resources)
        patch = None if pack.layout.empty else intersection(region,pack.layout.core)
        if patch is not None:
            result = result.copy()
            result[region.slices(patch)] = biomes(replace(raw,cell_step=1),params,seed,patch,resources)
        return result
    from .reference import biomes_for
    if pack.cell_step != 1:
        from .coarse import aligned
        source = aligned(region,pack.cell_step)
        values = biomes_for(Context.for_region(pack.fields,params,seed,source,resources=resources,step=pack.cell_step),pack)
        x = (np.arange(region.x0,region.x0+region.width)-source.x0)//pack.cell_step
        z = (np.arange(region.z0,region.z0+region.depth)-source.z0)//pack.cell_step
        return values[z[:,None],x]
    return biomes_for(Context.for_region(pack.fields, params, seed, region, resources=resources), pack)


def reference(pack, params, seed, region, resources=None, *, include_surface=True):
    """The exact 2D reference over region: a store slice when available, else evaluated."""
    store = current()
    if store is not None and store.covers(region):
        return store.reference(region, pack, params, seed, resources)
    if pack.layout is not None:
        from .planning import Resources
        return mixed_reference(pack,params,seed,region,resources or Resources(pack,params,seed))
    if pack.cell_step != 1:
        from .coarse import aligned
        source = evaluate_store(pack,params,seed,aligned(region,pack.cell_step),resources,step=pack.cell_step)
        return source.reference(region,pack,params,seed,resources)
    ctx = Context.for_region(pack.fields, params, seed, region, resources=resources)
    return evaluate(ctx, pack, include_surface=include_surface)
