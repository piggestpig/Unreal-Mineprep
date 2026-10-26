"""The exact shared 2D reference evaluation; no additional persistent cache."""
from dataclasses import dataclass
import numpy as np
from time import perf_counter
from .biomes import select_biomes
from .surface import apply_surface
from .water import sample_water


def slope(height):
    result = np.zeros_like(height)
    dx = (height[1:-1, 2:] - height[1:-1, :-2]) * .5
    dz = (height[2:, 1:-1] - height[:-2, 1:-1]) * .5
    result[1:-1, 1:-1] = np.hypot(dx, dz)
    return result


def biomes_for(ctx, pack):
    selected = pack.biome_selector(ctx) if pack.biome_selector is not None else None
    if selected is None:
        return select_biomes(ctx, pack.biomes, pack.biome_parameters)
    if isinstance(selected, str):
        ids = [b.id for b in pack.biomes]
        if selected not in ids:
            raise ValueError(f'pack {pack.id}: unknown selected biome {selected!r}')
        return np.full(ctx.shape, ids.index(selected), np.uint16)
    values = np.asarray(selected)
    if values.shape != ctx.shape or values.dtype.kind not in 'iu' or np.any(values < 0) or np.any(values >= len(pack.biomes)):
        raise ValueError('biome_selector must return integer biome indices with the context shape')
    return values.astype(np.uint16, copy=False)


@dataclass(frozen=True)
class Reference:
    ctx: object
    raw: object
    height: object
    levels: object
    wet: object
    biomes: object
    columns: object
    stages: dict
    soil_depth: object = None


def soil_depth_for(ctx,pack):
    """A scalar for legacy packs, otherwise a validated stage-local byte grid."""
    if pack.soil_depth_field is None: return ctx.param('surface.soil_depth')
    try:
        value=np.asarray(ctx.get(pack.soil_depth_field))
    except ValueError as error:
        raise ValueError(f'soil_depth_field {pack.soil_depth_field}: {error}') from error
    if value.shape!=ctx.shape or not np.isfinite(value).all() or np.any((value<0)|(value>32)|(value!=np.floor(value))):
        raise ValueError(f'soil_depth_field {pack.soil_depth_field}: expected integer depths 0..32 with reference shape')
    if np.all(value==value.flat[0]): return int(value.flat[0])
    value=value.astype(np.uint8);value.setflags(write=False)
    return value


def evaluate(ctx, pack, *, include_surface=True):
    started = perf_counter()
    if include_surface and pack.reference_halo:
        # Material neighbourhoods would otherwise resample this entire height
        # rectangle. Prime their widest context once and use its exact crop.
        h = pack.reference_halo
        expanded = ctx._expanded(h)
        raw = expanded.get(pack.height_field)
        expanded.put(pack.height_field,np.clip(raw,ctx.params['world.y_min'],ctx.params['world.y_max']))
        for name in pack.reference_inputs: expanded.get(name)
        for name,value in expanded._cache.items():
            # Only declared spatial fields: private recipe caches stay local.
            if name in pack.fields and isinstance(value,np.ndarray) and value.shape==expanded.shape:
                ctx.put(name,value[h:-h:ctx.step,h:-h:ctx.step])
        # Keep raw diagnostics, while mask fields see the same clipped height
        # as the ordinary pipeline. Shore queries clip their input themselves.
        expanded.put(pack.height_field,raw)
        ctx.put(pack.height_field,raw[h:-h:ctx.step,h:-h:ctx.step])
    raw = ctx.get(pack.height_field)
    height = np.clip(raw, ctx.params['world.y_min'], ctx.params['world.y_max'])
    ctx.put(pack.height_field, height)
    ctx.put('slope', slope(height))
    fields_seconds = perf_counter() - started
    started = perf_counter()
    levels, wet = sample_water(ctx, pack, height)
    water_seconds = perf_counter() - started
    started = perf_counter()
    biomes = biomes_for(ctx, pack) if include_surface else None
    columns = apply_surface(ctx, biomes, pack.biomes, {n:i for i,n in enumerate(pack.blocks)}, pack.surface_overrides) if include_surface else None
    if include_surface and pack.terrain_materials is not None:
        from .materials import colour_tops
        columns = colour_tops(ctx, pack, biomes, height, columns)
    soil_depth=soil_depth_for(ctx,pack) if include_surface else None
    return Reference(ctx, raw, height, levels, wet, biomes, columns,
                     dict(fields=fields_seconds, water=water_seconds, surface=perf_counter()-started),soil_depth)
