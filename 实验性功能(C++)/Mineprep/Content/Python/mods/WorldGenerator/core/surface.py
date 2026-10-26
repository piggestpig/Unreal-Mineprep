"""Ordered surface rules: conditions on smooth fields -> blocks per column layer.

A biome's `surface` list is checked top to bottom for each layer separately:
`top` (the surface cell), `under` (the next `surface.soil_depth` cells) and
`deep` (everything below). A rule may set any subset of layers; unset layers
fall through to later rules. The last rule must be unconditional and set all
three layers.

    {"when": {"slope": {"min": 1.6, "jitter": 0.4}}, "top": "stone", "under": "stone"}
    {"when": {"altitude": [null, 2]}, "top": "sand"}
    {"top": [["sand", 3], ["sandstone", 1]], "under": "sand", "deep": "sandstone"}

`when` maps any field name to [min, max) (null = open) or {"min", "max",
"jitter"}. Jitter shifts both bounds by `jitter * smooth noise` whose scale is
`surface.boundary_scale`; the noise is shared per field, so e.g. a snow line
stays continuous across biomes. Weighted candidates form smooth patches of
about `surface.patch_scale` blocks; weights are approximate area ratios.
"""

from dataclasses import dataclass
from statistics import NormalDist
import re

import numpy as np

ROLES = ("top", "under", "deep")
_BLOCK = re.compile(r"^(?:minecraft:)?[a-z0-9_]+$")
PATCH_STD = 0.2273  # measured std of 2-octave perlin fbm2 (tests/test_noise.py checks it)


def parse_bound(value, where):
    """A number, null, or "$section.key" naming a pack parameter (resolved per spec)."""
    if value is None:
        return None
    if isinstance(value, str):
        if not re.fullmatch(r"\$[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+", value):
            raise ValueError(f"{where}: parameter references look like \"$surface.steep_slope\"")
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where}: bounds are numbers, null or \"$param.key\"")
    return float(value)


def bound(ctx, value):
    return ctx.param(value[1:]) if isinstance(value, str) else value


def block_name(name, where="block"):
    if not isinstance(name, str) or not _BLOCK.fullmatch(name):
        raise ValueError(f"{where}: invalid block id {name!r}")
    return name.removeprefix("minecraft:")


@dataclass(frozen=True)
class Candidates:
    names: tuple
    cuts: tuple = ()  # patch-noise thresholds between consecutive names


def parse_candidates(value, where):
    if isinstance(value, str):
        return Candidates((block_name(value, where),))
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f"{where}: expected a block id or [[block, weight], ...]")
    names, weights = [], []
    for entry in value:
        if isinstance(entry, str):
            entry = (entry, 1)
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            raise ValueError(f"{where}: candidates look like [\"sand\", 3]")
        weight = float(entry[1])
        if not weight > 0 or weight == float("inf"):
            raise ValueError(f"{where}: weights must be positive")
        names.append(block_name(entry[0], where))
        weights.append(weight)
    if len(names) == 1:
        return Candidates(tuple(names))
    cumulative = np.cumsum(weights) / sum(weights)
    distribution = NormalDist(0.0, PATCH_STD)
    cuts = tuple(distribution.inv_cdf(min(max(c, 1e-9), 1 - 1e-9)) for c in cumulative[:-1])
    return Candidates(tuple(names), cuts)


@dataclass(frozen=True)
class Condition:
    field: str
    lo: object = None
    hi: object = None
    jitter: float = 0.0


@dataclass(frozen=True)
class Rule:
    conditions: tuple
    roles: tuple  # ((role index, Candidates), ...)


def parse_rules(data, where, *, complete=True):
    if not isinstance(data, list) or not data:
        raise ValueError(f"{where}: needs a non-empty list of rules")
    rules = []
    for index, raw in enumerate(data):
        at = f"{where}[{index}]"
        if not isinstance(raw, dict) or set(raw) - {"when", "notes", *ROLES}:
            raise ValueError(f"{at}: rule keys are when/top/under/deep")
        conditions = []
        for name, bounds in (raw.get("when") or {}).items():
            if not isinstance(name, str) or not name.isidentifier():
                raise ValueError(f"{at}: invalid field name {name!r}")
            if isinstance(bounds, dict):
                if set(bounds) - {"min", "max", "jitter"}:
                    raise ValueError(f"{at}.when.{name}: keys are min/max/jitter")
                lo, hi, jitter = bounds.get("min"), bounds.get("max"), float(bounds.get("jitter", 0))
            elif isinstance(bounds, (list, tuple)) and len(bounds) == 2:
                (lo, hi), jitter = bounds, 0.0
            else:
                raise ValueError(f"{at}.when.{name}: use [min, max] or {{min, max, jitter}}")
            if lo is None and hi is None:
                raise ValueError(f"{at}.when.{name}: needs min or max")
            conditions.append(Condition(name, parse_bound(lo, f"{at}.when.{name}"),
                                        parse_bound(hi, f"{at}.when.{name}"), jitter))
        roles = tuple((i, parse_candidates(raw[role], f"{at}.{role}"))
                      for i, role in enumerate(ROLES) if role in raw)
        if not roles:
            raise ValueError(f"{at}: sets no layer")
        rules.append(Rule(tuple(conditions), roles))
    last = rules[-1]
    if complete and (last.conditions or len(last.roles) != len(ROLES)):
        raise ValueError(f"{where}: the last rule must be unconditional and set top/under/deep")
    return tuple(rules)


def rule_fields(biomes):
    return tuple(dict.fromkeys(c.field for b in biomes for r in b.surface for c in r.conditions))


def referenced_params(biomes):
    values = [v for b in biomes for r in b.surface for c in r.conditions for v in (c.lo, c.hi)]
    values += [v for b in biomes for box in b.climate for _, lo, hi in box for v in (lo, hi)]
    return tuple(dict.fromkeys(v[1:] for v in values if isinstance(v, str)))


def apply_surface(ctx, biome_ids, biomes, block_index, overrides=()):
    """uint16[Z,X,3] block IDs (pack block table) for top/under/deep layers."""
    output = np.zeros((*ctx.shape, len(ROLES)), np.uint16)
    boundary = ctx.param("surface.boundary_scale")
    patch = ctx.param("surface.patch_scale")
    for b, biome in enumerate(biomes):
        in_biome = biome_ids == b
        if not in_biome.any():
            continue
        open_roles = np.repeat(in_biome[..., None], len(ROLES), axis=-1)
        for r, rule in enumerate(biome.surface):
            match = in_biome & np.any(open_roles[..., [role for role, _ in rule.roles]],axis=-1)
            if not match.any(): continue
            for c in rule.conditions:
                value = ctx.get(c.field)
                shift = c.jitter * ctx.noise(f"surface/jitter/{c.field}", boundary, octaves=2) if c.jitter else 0.0
                if c.lo is not None:
                    match &= value >= bound(ctx, c.lo) + shift
                if c.hi is not None:
                    match &= value < bound(ctx, c.hi) + shift
                if not match.any(): break
            for role, candidates in rule.roles:
                target = match & open_roles[..., role]
                if not target.any():
                    continue
                ids = np.array([block_index[n] for n in candidates.names], np.uint16)
                if len(ids) == 1:
                    output[..., role][target] = ids[0]
                else:
                    noise = ctx.noise(f"surface/patch/{biome.id}/{r}/{ROLES[role]}", patch, octaves=2)
                    output[..., role][target] = ids[np.searchsorted(candidates.cuts, noise[target])]
                open_roles[..., role] &= ~target
    # Separate salt namespace: adding overrides must not shift existing biome patches.
    open_roles = np.ones_like(output, bool)
    for r, rule in enumerate(overrides):
        match = np.any(open_roles[..., [role for role, _ in rule.roles]],axis=-1)
        if not match.any(): continue
        for c in rule.conditions:
            value = ctx.get(c.field)
            shift = c.jitter * ctx.noise(f'surface/jitter/{c.field}', boundary, octaves=2) if c.jitter else 0
            if c.lo is not None:
                match &= value >= bound(ctx, c.lo) + shift
            if c.hi is not None:
                match &= value < bound(ctx, c.hi) + shift
            if not match.any(): break
        for role, candidates in rule.roles:
            target = match & open_roles[..., role]
            if target.any():
                ids = np.array([block_index[n] for n in candidates.names], np.uint16)
                if len(ids) == 1:
                    output[..., role][target] = ids[0]
                else:
                    noise = ctx.noise(f'surface/override/{r}/{ROLES[role]}', patch, octaves=2)
                    output[..., role][target] = ids[np.searchsorted(candidates.cuts, noise[target])]
                open_roles[..., role] &= ~target
    return output
