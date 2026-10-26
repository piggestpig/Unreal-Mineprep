"""C/E/PV height shaping, not physical erosion or Minecraft seed reproduction.

Low-frequency shaping runs on the world-aligned 8-block lattice. Land and
mountain weights gate relief and detail; oceans retain their seabed height.
"""

import cv2
import numpy as np

from ...core.fields import field
from ...core.noise import fbm2
from ...core.surface import parse_candidates


_SEDIMENT_CUT = parse_candidates([['sand', 49], ['deposit', 1]], 'ocean sediment').cuts[0]
_SHORE_CUT = parse_candidates([['sand', 3], ['deposit', 1]], 'shore sediment').cuts[0]


def select_biome(ctx):
    """Mixed worlds use normal climate boxes; presets select a stable biome ID."""
    return ctx.param('climate.single_biome') or None


@field("continentalness", res=8)
def continentalness(ctx):
    """Low-frequency continental layout, approximately [-1, 1]."""
    return np.clip(ctx.noise("terrain/continentalness", ctx.param("terrain.continental_scale"),
                             octaves=4) * 2.5, -1, 1)


@field("erosion", res=8)
def erosion(ctx):
    """Region-wide mountain suppression; larger values give gentler terrain."""
    noise = ctx.noise("terrain/erosion", ctx.param("terrain.erosion_scale"), octaves=4) * 2.5
    return np.clip(noise + ctx.param("terrain.erosion_offset"), -1, 1)


@field("weirdness", res=8)
def weirdness(ctx):
    """World-coordinate warp bends ridges without moving continents or climate."""
    scale = ctx.param("terrain.weirdness_scale")
    strength = ctx.param("terrain.warp_strength")
    if not strength:
        noise = ctx.noise("terrain/weirdness", scale, octaves=3)
    else:
        # Offsets are in blocks, sampled at the same world-aligned lattice in
        # every chunk. Never normalize by the current tile's min/max.
        wx = ctx.noise("terrain/warp_x", scale * 0.5, octaves=2) * strength
        wz = ctx.noise("terrain/warp_z", scale * 0.5, octaves=2) * strength
        noise = fbm2((ctx.x + wx) / scale, (ctx.z + wz) / scale,
                     seed=ctx.seed, salt="terrain/weirdness", octaves=3)
    return np.clip(noise * 2.5, -1, 1)


@field("peaks_valleys", deps=("weirdness",))
def peaks_valleys(ctx, weirdness):
    """PV = 1 - abs(3 * abs(W) - 2), bounded before folding."""
    return 1.0 - np.abs(3.0 * np.abs(np.clip(weirdness, -1, 1)) - 2.0)


@field("continental_offset", deps=("continentalness",), res=8)
def continental_offset(ctx, continents):
    return ctx.curve("terrain.continental_curve")(continents)


@field("land_weight", deps=("continental_offset",), res=8)
def land_weight(ctx, offset):
    """A smooth coastline gate tied to the actual continent height curve."""
    t = np.clip(offset / 12.0, 0, 1)
    return t * t * (3.0 - 2.0 * t)


@field("mountain_weight", deps=("erosion",), res=8)
def mountain_weight(ctx, erosion):
    return np.clip(ctx.curve("terrain.erosion_curve")(erosion), 0, 1)


@field("massif", res=8)
def massif(ctx):
    """Independent broad mountain bodies, not another folded ridge contour."""
    t = np.clip(0.5 + 1.6 * ctx.noise("terrain/massif", ctx.param("terrain.weirdness_scale") * 0.75,
                                    octaves=3), 0, 1)
    return t * t * (3.0 - 2.0 * t)


@field("base_height", deps=("continental_offset", "land_weight", "mountain_weight", "peaks_valleys", "massif"), res=8)
def base_height(ctx, offset, land, mountains, pv, massif):
    """Broad bodies carry variable ridges; a PV contour alone is no tall wall."""
    body = np.clip(massif, 0, 1)
    blend = ctx.param("terrain.massif_weight")
    peaks = ctx.curve("terrain.peaks_curve")(pv)
    relief = blend * (body - 0.25) + (1.0 - blend) * peaks * (0.4 + 0.6 * body)
    return (ctx.param("world.sea_level") + offset
            + np.clip(land, 0, 1) * np.clip(mountains, 0, 1)
            * relief * ctx.param("terrain.mountain_height"))


@field("detail_noise", res=2)
def detail_noise(ctx):
    if not ctx.param("terrain.detail_strength") or ctx.param("terrain.flat"):
        return 0.0
    return ctx.noise("terrain/regional_detail", ctx.param("terrain.detail_scale"), octaves=2)


@field("height_baseline", deps=("base_height", "land_weight", "mountain_weight", "detail_noise"))
def height_baseline(ctx, base, land, mountains, detail):
    """0.6.0 surface detail over the retained 0.6.1 broad mountain bodies."""
    if ctx.param("terrain.flat"):
        return ctx.param("world.flat_height")
    strength = ctx.param("terrain.detail_strength") * (0.35 + 1.65 * np.clip(mountains, 0, 1))
    return base + np.clip(land, 0, 1) * strength * detail


@field('seabed_noise', res=4)
def seabed_noise(ctx):
    if not ctx.param('water.generate') or ctx.param('terrain.flat') or not ctx.param('seabed.strength'):
        return 0.0
    return ctx.noise('terrain/seabed', ctx.param('seabed.scale'), octaves=2)


def _smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


@field('height_lowlands', deps=('height_baseline', 'base_height', 'mountain_weight'))
def height_lowlands(ctx, baseline, base, mountains):
    """Compress dry lowland bodies, retaining detail and strong mountain heights."""
    strength = ctx.param('terrain.lowland_strength')
    if ctx.param('terrain.flat') or not strength:
        return baseline
    sea = ctx.param('world.sea_level')
    q = np.maximum(base - sea, 0)
    h = ctx.param('terrain.lowland_height')
    weight = 1 - _smooth((np.clip(mountains, 0, 1) - .15) / .5)
    dry = np.ceil(np.clip(baseline, ctx.param('world.y_min'), ctx.param('world.y_max'))) > sea
    lowered = baseline - strength * weight * (q - h * q / (q + h))
    return np.where(dry, lowered, baseline)


@field('desert_dunes', res=4)
def desert_dunes(ctx):
    height = ctx.param('terrain.dune_height')
    if not height or ctx.param('terrain.flat'):
        return 0.
    scale = ctx.param('terrain.dune_scale')
    warp = ctx.noise('terrain/desert/dune_warp', scale * 2, octaves=2)
    phase = (ctx.x + .35 * ctx.z) / scale + .7 * warp
    ridges = (.5 + .5 * np.sin(2 * np.pi * phase)) ** 2
    patches = np.clip(.75 + ctx.noise('terrain/desert/dune_height', scale * 3, octaves=2), .25, 1)
    return height * ridges * patches


@field('height_custom', deps=('height_lowlands',))
def height_custom(ctx, baseline):
    """Author extension: absolute height after lowlands, before islands/water planning.

    Override in a descendant; use only upstream fields, and short-circuit flat
    mode. The same recipe receives the coarse planning and fine terrain inputs.
    """
    biome = ctx.param('climate.single_biome')
    if ctx.param('terrain.flat'):
        return baseline
    sea = ctx.param('world.sea_level')
    if biome in ('ocean', 'frozen_ocean'):
        return np.minimum(baseline, sea - 4)
    if biome:
        baseline = np.maximum(baseline, sea + 3)
        weight = float(biome == 'desert')
    elif ctx.param('terrain.dune_height'):
        temperature = ctx.get('climate_temperature_base') + ctx.param('climate.temperature_offset')
        humidity = ctx.get('climate_humidity_base') + ctx.param('climate.humidity_offset')
        weight = (_smooth((temperature - .2) / .2) * _smooth((-.2 - humidity) / .2)
                  * _smooth((baseline - sea - 1) / 5) * (1 - np.clip(ctx.get('mountain_weight'), 0, 1))
                  * (1 - _smooth(ctx.get('badlands_weight') * 2))
                  * (1 - _smooth(ctx.get('savanna_weight') * 2)))
    else:
        return baseline
    if not np.any(weight):
        return baseline
    dunes = np.clip(ctx.get('desert_dunes'), 0, ctx.param('terrain.dune_height'))
    return baseline + weight * dunes


def _seabed_height(ctx, baseline, noise):
    """The 0.10.2 height path, also the input to R3A shaping."""
    depth = np.maximum(ctx.param('world.sea_level') - baseline, 0)
    t = np.clip(depth / ctx.param('seabed.shore_fade'), 0, 1)
    delta = noise * ctx.param('seabed.strength') * t * t * (3 - 2 * t)
    return baseline + np.clip(delta, -depth * .5, depth * .5)


@field('seabed_basin', res=8)
def seabed_basin(ctx):
    """Independent broad ocean bodies, separate from continent contours."""
    if not ctx.param('water.generate') or ctx.param('terrain.flat') or not ctx.param('seabed.shaping'):
        return 0.0
    return np.clip(.5 + 1.5 * ctx.noise('seabed/basin', ctx.param('seabed.basin_scale'),
                                     octaves=2), 0, 1)


@field('seabed_trough', res=8)
def seabed_trough(ctx):
    """Continuous narrow troughs around the zero band of a regional field."""
    if not ctx.param('water.generate') or ctx.param('terrain.flat') or not ctx.param('seabed.shaping'):
        return 0.0
    n = ctx.noise('seabed/trough', ctx.param('seabed.basin_scale') * .75, octaves=2)
    return _smooth(1 - np.abs(3 * n) / .25)


@field('coast_offset', res=4)
def coast_offset(ctx):
    if (not ctx.param('water.generate') or ctx.param('terrain.flat') or not ctx.param('seabed.shaping')
            or not ctx.param('seabed.coast_width') or not ctx.param('seabed.coast_strength')):
        return 0.0
    return np.clip(2.5 * ctx.noise('seabed/coast', ctx.param('seabed.coast_scale'),
                                 octaves=2), -1, 1)


@field('seabed_ridge', res=8)
def seabed_ridge(ctx):
    """Broad world-aligned submarine ridges; independent of trough locations."""
    if (not ctx.param('water.generate') or ctx.param('terrain.flat')
            or not ctx.param('seabed.shaping') or not ctx.param('seabed.ridge_height')):
        return 0.0
    n = ctx.noise('seabed/ridge', ctx.param('seabed.basin_scale') * 1.25, octaves=2)
    return _smooth(1 - np.abs(2.5 * n) / .5)


@field('seabed_sediment_noise', res=8)
def seabed_sediment_noise(ctx):
    """Broad deposition noise sampled on the world-aligned eight-cell lattice."""
    if not ctx.param('water.generate'):
        return 0.0
    return ctx.noise('seabed/sediment', ctx.param('seabed.material_scale'), octaves=2)


@field('seabed_sediment', deps=('height_islands', 'seabed_sediment_noise'), halo=9)
def seabed_sediment(ctx, baseline, noise):
    """Sparse offshore deposits; only a bounded eight-cell coast band is richer."""
    wet = np.ceil(np.clip(baseline, ctx.param('world.y_min'), ctx.param('world.y_max'))) <= ctx.param('world.sea_level')
    near = _coast_blend(wet)
    cut = _SEDIMENT_CUT - (_SEDIMENT_CUT - _SHORE_CUT) * near
    return noise - cut


@field('seabed_deposit', deps=('seabed_sediment', 'height_islands'))
def seabed_deposit(ctx, sediment, baseline):
    """Nominal raised deposit height; smooth edges, sand remains underneath."""
    if (not ctx.param('water.generate') or ctx.param('terrain.flat') or not ctx.param('seabed.shaping')):
        return 0.0
    depth = np.floor(ctx.param('world.sea_level')) - baseline
    return ctx.param('seabed.deposit_height') * _smooth(sediment / .12) * _smooth(depth - 1)


@field('seabed_deposit_kind', res=8)
def seabed_deposit_kind(ctx):
    """Nonnegative selects gravel; negative selects dirt, in broad deposit bodies."""
    return ctx.noise('seabed/deposit_kind', ctx.param('seabed.material_scale') * .5, octaves=2) + _SHORE_CUT


@field('seabed_relief', res=4)
def seabed_relief(ctx):
    """Bent medium-scale sand hills and hollows rather than per-cell roughness."""
    if (not ctx.param('water.generate') or ctx.param('terrain.flat')
            or not ctx.param('seabed.shaping') or not ctx.param('seabed.relief_height')):
        return 0.0
    scale = ctx.param('seabed.relief_scale')
    wx = ctx.noise('seabed/warp_x', scale * 2, octaves=2) * scale * .7
    wz = ctx.noise('seabed/warp_z', scale * 2, octaves=2) * scale * .7
    return np.clip(2.5 * fbm2((ctx.x + wx) / scale, (ctx.z + wz) / scale,
                             seed=ctx.seed, salt='seabed/relief', octaves=2), -1, 1)


@field('seabed_depth_scale')
def seabed_depth_scale(ctx):
    """Nominal depth/relief fit factor, reserving one solid cell below the sea."""
    capacity = max(np.floor(ctx.param('world.sea_level')) - ctx.param('world.y_min') - 1, 0)
    nominal = (ctx.param('seabed.basin_depth') + ctx.param('seabed.trench_depth')
               + ctx.param('seabed.strength'))
    return min(1.0, capacity / nominal) if nominal else float(capacity > 0)


def _coast_distance(wet, width):
    """Distance to the opposite class, capped after width eight-neighbour steps."""
    if not width or wet.all() or not wet.any():
        return np.full(wet.shape, width + 1, np.uint8)
    u = np.asarray(wet, np.uint8)
    d = cv2.distanceTransform(u, cv2.DIST_C, 3) + cv2.distanceTransform(1 - u, cv2.DIST_C, 3)
    return np.minimum(d, width + 1).astype(np.uint8)


def _coast_blend(wet):
    """Smooth the discrete distance steps over one cell, requiring halo nine."""
    near = _smooth(1 - _coast_distance(wet, 8) / 8)
    p = np.pad(near, 1, mode='edge')
    return sum(p[z:z+near.shape[0], x:x+near.shape[1]] for z in range(3) for x in range(3)) / 9


@field('height_before_rivers', deps=('height_badlands', 'seabed_noise', 'seabed_basin', 'seabed_trough',
                       'coast_offset', 'seabed_ridge', 'seabed_depth_scale', 'seabed_relief', 'seabed_deposit'), halo=16)
def height_before_rivers(ctx, baseline, noise, basin, trough, coast, ridge, scale, relief, deposit):
    """Continuous submerged shores, irregular sandy beds and raised deposits."""
    if not ctx.param('water.generate') or ctx.param('terrain.flat'):
        return baseline
    original = _seabed_height(ctx, baseline, noise)
    if not ctx.param('seabed.shaping'):
        return original
    sea = ctx.param('world.sea_level')
    anchor = np.floor(sea)
    wet = np.ceil(np.clip(original, ctx.param('world.y_min'), ctx.param('world.y_max'))) <= sea
    width = ctx.param('seabed.coast_width')
    distance = _coast_distance(wet, 16)
    result = original.copy()
    if width and ctx.param('seabed.coast_strength'):
        weight = _smooth(1 - distance / width) * _smooth(1 - np.abs(original - anchor) / 3)
        result += ctx.param('seabed.coast_strength') * np.clip(coast, -1, 1) * weight
    capacity = max(anchor - ctx.param('world.y_min') - 1, 0)
    if not capacity:
        return result
    # The fractional sea level belongs to the water instance, not the solid cell.
    # Newly submerged dry land remains a bounded shallow shore: do not deepen
    # it a second time and exceed the coast adjustment budget.
    wet &= np.ceil(result) <= sea
    depth = np.maximum(anchor - result[wet], 0)
    fit = scale[wet]
    shelf = np.minimum(ctx.param('seabed.shelf_depth') * fit, capacity)
    blend = _smooth((depth - shelf) / ctx.param('seabed.slope_depth'))
    # Compare depths rather than replacing continental relief with a shallower
    # basin. Existing fine noise remains in the source and in basin-dominated
    # areas, with its original sign (positive noise raises the bed).
    basin_depth = fit * (ctx.param('seabed.basin_depth') * (.7 + .3 * np.clip(basin[wet], 0, 1))
                         - ctx.param('seabed.strength') * np.clip(noise[wet], -1, 1))
    base = np.clip(np.maximum(depth, basin_depth), 0, capacity)
    extra = fit * ctx.param('seabed.trench_depth') * np.clip(trough[wet], 0, 1)
    remaining = capacity - base
    deepen = np.divide(remaining * extra, remaining + extra,
                       out=np.zeros_like(extra), where=(remaining + extra) > 0)
    target = np.clip(base + deepen - fit * ctx.param('seabed.ridge_height')
                     * np.clip(ridge[wet], 0, 1), shelf, capacity)
    shaped = (1 - blend) * np.minimum(depth, capacity) + blend * target
    # Lowering approaches the floor smoothly; rising relief leaves one full
    # water cell. Deposits share their field with the material selection.
    variation = fit * ctx.param('seabed.relief_height') * np.clip(relief[wet], -1, 1) * _smooth(depth / 4)
    extra = np.maximum(-variation, 0)
    remaining = np.maximum(capacity - shaped, 0)
    shaped += np.divide(remaining * extra, remaining + extra, out=np.zeros_like(extra), where=remaining+extra > 0)
    rise = np.maximum(variation, 0) + fit * np.maximum(deposit[wet], 0)
    shaped -= np.minimum(rise, np.maximum(shaped - 1, 0))
    # Raise deep slope feet after shaping. The first wet column is at most one
    # block deep; by distance sixteen the envelope permits the full capacity.
    offshore = distance[wet].astype(float) - 1
    run = np.clip(2 * ctx.param('seabed.slope_depth'), 1, 15)
    limit = np.minimum(capacity, 1 + offshore * max(1, (capacity - 1) / 15)
                       + ctx.param('seabed.coast_drop') * _smooth(offshore / run))
    shaped = np.minimum(shaped, limit)
    result[wet] = anchor - shaped
    return result


@field("altitude", deps=("height",))
def altitude(ctx, height):
    """Blocks above sea level (negative under the sea)."""
    return height - ctx.param("world.sea_level")


@field('foothill_rock', deps=('altitude',))
def foothill_rock(ctx, altitude):
    """Negative selects soil on gentle mountain feet; nonnegative selects rock."""
    u = np.clip((altitude - ctx.param('climate.mountain_height'))
                / ctx.param('surface.foothill_height'), 0, 1)
    threshold = np.clip(.5 + 1.5 * ctx.noise('surface/foothill', ctx.param('surface.foothill_scale'),
                                           octaves=2), .05, .95)
    return u - threshold


@field('shore_depth', deps=('height', 'water_level', 'water_presence'))
def shore_depth(ctx, height, levels, presence):
    """Water-anchor depth with a smooth sediment boundary; dry columns return -1."""
    depth = levels - np.ceil(np.clip(height, ctx.param('world.y_min'), ctx.param('world.y_max')))
    wet = (presence > 0) & (depth >= 0)
    if not wet.any():
        return np.full(ctx.shape, -1.)
    shift = .75 * np.clip(ctx.noise('surface/shore_depth', ctx.param('surface.boundary_scale'),
                                   octaves=2), -1, 1)
    return np.where(wet, np.maximum(depth + shift, 0), -1.)


CLIMATE_GAIN = 2.5  # 4-octave fBm has std ~0.19; this spreads climate to about [-1, 1]


def _climate_displacement(ctx, axis):
    strength = ctx.param('climate.warp_strength')
    if not strength:
        return 0.
    scale = ctx.param('climate.warp_scale')
    main = ctx.noise('climate/warp_'+axis, scale, octaves=2)
    detail = ctx.noise('climate/warp_detail_'+axis, scale/4, octaves=2)
    return strength * (np.clip(main*CLIMATE_GAIN, -1, 1)
                       + np.clip(detail*CLIMATE_GAIN, -1, 1)/6)


@field('climate_warp_x', res=16)
def climate_warp_x(ctx):
    return _climate_displacement(ctx, 'x')


@field('climate_warp_z', res=16)
def climate_warp_z(ctx):
    return _climate_displacement(ctx, 'z')


def _climate_noise(ctx, salt, scale, octaves):
    if not ctx.param('climate.warp_strength'):
        return ctx.noise(salt, scale, octaves=octaves)
    # Reuse equal warped samples in this immutable grid/parameter context.
    key = ('climate_noise', salt, float(scale), octaves)
    result = ctx._cache.get(key)
    if result is None:
        result = fbm2((ctx.x+ctx.get('climate_warp_x'))/scale,
                      (ctx.z+ctx.get('climate_warp_z'))/scale,
                      seed=ctx.seed, salt=salt, octaves=octaves)
        ctx._cache[key] = result
    return result


@field('forest_region_base', res=16)
def forest_region_base(ctx):
    """Broad forest bodies; tree patch noise supplies the smaller clearings."""
    return np.clip(_climate_noise(ctx, 'climate/forest_region', ctx.param('forest.region_scale'),
                                 2) * CLIMATE_GAIN, -1, 1)


@field('ice_region_base', res=16)
def ice_region_base(ctx):
    """Ice-spike regions within the snowy-plains fallback; disabled means absent."""
    if not ctx.param('ice_spikes.enabled'):
        return -1.
    return np.clip(_climate_noise(ctx, 'climate/ice_region', ctx.param('ice_spikes.region_scale'),
                                 2) * CLIMATE_GAIN, -1, 1)


@field('frozen_ocean_mask', deps=('snow_cover',))
def frozen_ocean_mask(ctx, snow):
    return (snow >= .5) if ctx.param('frozen_ocean.enabled') else 0.


@field('ocean_ice_patch', res=16)
def ocean_ice_patch(ctx):
    return np.clip(ctx.noise('climate/frozen_ocean/floes', ctx.param('frozen_ocean.ice_scale'),
                             octaves=2) * CLIMATE_GAIN, -1, 1)


@field("climate_temperature_base", res=8)
def climate_temperature_base(ctx):
    return _climate_noise(ctx, "climate/temperature", ctx.param("climate.scale"), 4) * CLIMATE_GAIN


@field("climate_humidity_base", res=8)
def climate_humidity_base(ctx):
    return _climate_noise(ctx, "climate/humidity", ctx.param("climate.scale"), 4) * CLIMATE_GAIN


@field("edge_t", res=2)
def edge_t(ctx):
    return ctx.param("climate.edge_noise") * ctx.noise("climate/edge_t", ctx.param("climate.edge_scale"), octaves=2) * 3.0


@field("edge_h", res=2)
def edge_h(ctx):
    return ctx.param("climate.edge_noise") * ctx.noise("climate/edge_h", ctx.param("climate.edge_scale"), octaves=2) * 3.0


@field("temperature", deps=("climate_temperature", "edge_t", "altitude"))
def temperature(ctx, climate, edge, altitude):
    """About [-1, 1] at sea level, cooling with height."""
    cooling = ctx.param("climate.cooling") * altitude.clip(min=0) / 128.0
    return climate + edge + ctx.param("climate.temperature_offset") - cooling


@field("humidity", deps=("climate_humidity", "edge_h"))
def humidity(ctx, climate, edge):
    return climate + edge + ctx.param("climate.humidity_offset")


@field('regional_temperature_base', res=16)
def regional_temperature_base(ctx):
    """Broad climate only: no elevation cooling or boundary jitter."""
    return (_climate_noise(ctx, 'climate/temperature', ctx.param('climate.snow_scale'), 2)
             * CLIMATE_GAIN + ctx.param('climate.temperature_offset'))


def _boundary(ctx, name):
    return ctx.grid_sample(name+'_base', strength=ctx.param('climate.boundary_detail'))


@field('regional_temperature')
def regional_temperature(ctx): return _boundary(ctx, 'regional_temperature')


@field('climate_temperature')
def climate_temperature(ctx): return _boundary(ctx, 'climate_temperature')


@field('climate_humidity')
def climate_humidity(ctx): return _boundary(ctx, 'climate_humidity')


@field('forest_region')
def forest_region(ctx): return _boundary(ctx, 'forest_region')


@field('ice_region')
def ice_region(ctx): return _boundary(ctx, 'ice_region')


@field('snow_line_noise', res=2)
def snow_line_noise(ctx):
    return ctx.noise('climate/snow_line', 48, octaves=2)


@field('snow_line_variation', deps=('snow_line_noise',))
def snow_line_variation(ctx, noise):
    # Clamp after interpolation: cubic interpolation can overshoot coarse bounds.
    return 4 * np.clip(noise * 2.5, -1, 1)


@field('snow_cover', deps=('regional_temperature', 'mountain_weight', 'altitude',
                          'snow_line_variation', 'temperature'))
def snow_cover(ctx, regional, mountains, altitude, variation, temperature):
    """Cold regions or qualified mountain summits; independent of crop size."""
    biome = ctx.param('climate.single_biome')
    if biome in ('snowy_taiga', 'snowy_plains', 'ice_spikes', 'frozen_ocean'):
        return 1.
    if biome == 'mountains':
        return (mountains >= .3) & (altitude >= ctx.param('climate.snow_height') + variation)
    if biome:
        return 0.
    if not ctx.param('climate.snow_refinement'):
        return temperature <= -.5
    snow_line = ctx.param('climate.snow_height') + 32 * regional + variation
    return ((regional <= -.5)
            | ((mountains >= .55) & (regional <= .25) & (altitude >= snow_line)))
