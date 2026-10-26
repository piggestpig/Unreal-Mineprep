"""Multiple climate boxes per biome, nearest-box selection and explicit fallback.

Intervals are closed; conditions inside a box intersect, boxes form a union.
Overlapping boxes and equal distances use Pack order. Fallback only takes
columns outside every ordinary box; without it the nearest biome wins.
"""

from dataclasses import dataclass, field
import math
import re

import numpy as np

from .surface import bound, parse_bound, parse_rules
from .features import parse_placements

_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _label(value, fallback):
    if isinstance(value, dict):
        zh = str(value.get("zh") or value.get("en") or fallback)
        return zh, str(value.get("en") or zh)
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return str(value[0]), str(value[1])
    return (str(value), str(value)) if value else (fallback, fallback)


@dataclass(frozen=True)
class Biome:
    id: str
    name: tuple          # (zh, en)
    color: tuple         # (r, g, b)
    climate: tuple       # boxes: tuple of ((parameter, lo, hi), ...)
    surface: tuple       # Rule objects, see surface.py
    fallback: bool = False
    features: dict = field(default_factory=dict)
    vegetation_tint: tuple = (1.0, 1.0, 1.0)  # linear RGB multiplier, not map colour
    vegetation_hsv: tuple = (1.0, 1.0, 1.0)  # hue adjustment (1 = neutral), saturation/value multipliers

    @property
    def blocks(self):
        return tuple(dict.fromkeys(n for rule in self.surface for _, c in rule.roles for n in c.names))


def parse_biome(data, parameters, source="biome"):
    if not isinstance(data, dict):
        raise ValueError(f"{source}: biome must be a JSON object")
    unknown = set(data) - {"id", "name", "color", "climate", "fallback", "surface", "notes", "features", "vegetation_tint", "vegetation_hsv"}
    if unknown:
        raise ValueError(f"{source}: unknown keys {sorted(unknown)}")
    biome_id = data.get("id")
    if not isinstance(biome_id, str) or not _ID.fullmatch(biome_id):
        raise ValueError(f"{source}: invalid biome id {biome_id!r}")
    color = data.get("color", "#808080")
    if not isinstance(color, str) or not _COLOR.fullmatch(color):
        raise ValueError(f"{source}: color must look like #RRGGBB")
    fallback = data.get("fallback", False)
    if type(fallback) is not bool:
        raise ValueError(f"{source}: fallback must be true/false")
    raw = data.get("climate")
    if not isinstance(raw, list):
        raise ValueError(f"{source}: migrate climate to a list of boxes; "
                         'fallback requires "fallback": true, "climate": []')
    if fallback and raw or not fallback and not raw:
        raise ValueError(f"{source}: ordinary climate needs non-empty boxes; fallback needs climate: []")
    climate = []
    for index, box in enumerate(raw):
        at = f"{source}: climate[{index}]"
        if not isinstance(box, dict) or not box:
            raise ValueError(f"{at}: needs a non-empty box object")
        conditions = []
        for name, bounds in box.items():
            if name not in parameters:
                raise ValueError(f"{at}: climate parameter {name!r} is not in pack biome_parameters "
                                 f"{sorted(parameters)}")
            if not isinstance(bounds, list) or len(bounds) != 2:
                raise ValueError(f"{at}.{name}: must be [min, max] (null = unbounded)")
            lo, hi = (parse_bound(b, f"{at}.{name}") for b in bounds)
            _check_interval(lo, hi, f"{at}.{name}")
            conditions.append((name, lo, hi))
        climate.append(tuple(conditions))
    rules = parse_rules(data.get("surface"), f"{source}.surface")
    rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
    return Biome(biome_id, _label(data.get("name"), biome_id), rgb, tuple(climate), rules, fallback,
                 parse_placements(data.get('features', {}), source),
                 vegetation_tint(data.get('vegetation_tint', [1, 1, 1]), source),
                 vegetation_hsv(data.get('vegetation_hsv', [1, 1, 1]), source))


def vegetation_tint(value, source='biome'):
    if (not isinstance(value, (list, tuple)) or len(value) != 3
            or any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) or not 0 <= v <= 65504 for v in value)):
        raise ValueError(f'{source}: vegetation_tint must be three finite RGB multipliers in [0, 65504]')
    return tuple(float(v) for v in value)


def vegetation_hsv(value, source='biome'):
    values = vegetation_tint(value, source)
    if not .5 <= values[0] <= 1.5:
        raise ValueError(f'{source}: vegetation_hsv hue must be in [0.5, 1.5]; 1 is neutral')
    return values


def _check_interval(lo, hi, where):
    for value in (lo, hi):
        if value is not None and not isinstance(value, str) and not math.isfinite(value):
            raise ValueError(f"{where}: bounds must be finite or null")
    if all(v is not None and not isinstance(v, str) for v in (lo, hi)) and lo > hi:
        raise ValueError(f"{where}: min > max")


def validate_climate(biomes, params):
    """Check intervals after defaults, presets and spec overrides are resolved."""
    for biome in biomes:
        for index, box in enumerate(biome.climate):
            for name, lo, hi in box:
                lo, hi = (params[v[1:]] if isinstance(v, str) else v for v in (lo, hi))
                _check_interval(lo, hi, f"biome {biome.id}: climate[{index}].{name}")


def select_biomes(ctx, biomes, parameters):
    """uint16[Z,X] index into `biomes`; `parameters` maps field name -> distance scale."""
    if len(biomes) == 1:
        return np.zeros(ctx.shape, np.uint16)
    fallbacks = [i for i, b in enumerate(biomes) if b.fallback]
    if fallbacks:
        ids = np.full(ctx.shape, fallbacks[-1], np.uint16)
        remaining = np.ones(ctx.shape, bool)
        values = {}
        for index, biome in enumerate(biomes):
            if biome.fallback:
                continue
            matched = np.zeros(ctx.shape, bool)
            for box in biome.climate:
                inside = remaining & ~matched
                for name, lo, hi in box:
                    if not inside.any():
                        break
                    if name not in values:
                        values[name] = ctx.get(name)
                    v = values[name]
                    if lo is not None:
                        inside &= v >= bound(ctx, lo)
                    if hi is not None:
                        inside &= v <= bound(ctx, hi)
                matched |= inside
            ids[matched] = index
            remaining &= ~matched
            if not remaining.any():
                break
        return ids
    values = {name: ctx.get(name) for name in parameters}
    best = np.full(ctx.shape, np.inf)
    ids = np.zeros(ctx.shape, np.uint16)
    fallback = None
    for index, biome in enumerate(biomes):
        if biome.fallback:
            fallback = index
            continue
        distance = np.full(ctx.shape, np.inf)
        for box in biome.climate:
            box_distance = np.zeros(ctx.shape)
            for name, lo, hi in box:
                v = values[name]
                gap = np.zeros(ctx.shape)
                if lo is not None:
                    gap = np.maximum(gap, bound(ctx, lo) - v)
                if hi is not None:
                    gap = np.maximum(gap, v - bound(ctx, hi))
                box_distance += (gap / parameters[name]) ** 2
            np.minimum(distance, box_distance, out=distance)
        closer = distance < best  # strict: earlier biomes win ties
        best = np.where(closer, distance, best)
        ids[closer] = index
    if fallback is not None:
        ids[best > 0] = fallback
    return ids
