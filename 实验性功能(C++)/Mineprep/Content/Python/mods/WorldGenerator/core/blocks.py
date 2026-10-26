"""Shared block declarations. Cells store IDs; sources never enter worker payloads."""
from dataclasses import dataclass, asdict
import math
from pathlib import Path
import re

from .surface import block_name


@dataclass(frozen=True)
class BlockDef:
    id: str
    source: str
    value: str
    shape: str = 'cube'
    occludes: bool = True
    merge: str = 'xz'
    color: object = None
    offset: tuple = (0., 0., 0.)  # MC world XYZ translation, independent of rotation/extents
    scale: tuple = (1., 1., 1.)   # model-local MC XYZ scale about the cell center
    explicit: bool = False
    material: tuple = ()  # sorted (emission/lighting, value); output only

    def describe(self):
        data = asdict(self)
        data['source'] = {self.source: data.pop('value')}
        if self.material:
            data['material'] = dict(self.material)
        else:
            data.pop('material')
        return data


def material_values(raw, *, allow_none=False):
    if not isinstance(raw, dict) or set(raw) - {'emission', 'lighting'}:
        raise ValueError('material: only emission and lighting are supported')
    result = {}
    for name, value in sorted(raw.items()):
        if value is None and allow_none:
            result[name] = None
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f'material.{name}: requires a finite nonnegative number')
        else:
            result[name] = float(value)
    return result


def _triple(raw, name, positive=False):
    if not isinstance(raw, (list, tuple)) or len(raw) != 3 or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            or (positive and v <= 0) for v in raw):
        raise ValueError(f'{name}: needs three finite {"positive " if positive else ""}numbers')
    return tuple(float(v) for v in raw)


def parse_block(name, raw, directory):
    name = block_name(name)
    keys = {'source', 'shape', 'occludes', 'merge', 'color', 'offset', 'scale', 'material'}
    if not isinstance(raw, dict) or set(raw) - keys or not {'source', 'shape', 'occludes', 'merge'} <= raw.keys():
        raise ValueError(f'block {name}: needs source/shape/occludes/merge; keys are {sorted(keys)}')
    source = raw['source']
    if not isinstance(source, dict) or len(source) != 1 or next(iter(source)) not in ('builtin', 'json', 'mesh'):
        raise ValueError(f'block {name}: source must contain exactly one of builtin/json/mesh')
    kind, value = next(iter(source.items()))
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'block {name}: empty source')
    if kind == 'builtin':
        value = block_name(value)
    elif kind == 'json':
        value = str((Path(directory) / value).resolve())
    else:
        if not value.startswith('/Game/') or "'" in value:
            raise ValueError(f'block {name}: mesh needs a /Game/ package or object path')
    shape, occludes, merge = raw['shape'], raw['occludes'], raw['merge']
    if shape not in ('cube', 'surface', 'decor') or type(occludes) is not bool or merge not in ('none', 'xz', 'xyz'):
        raise ValueError(f'block {name}: invalid shape/occludes/merge')
    offset = _triple(raw.get('offset', (0, 0, 0)), f'block {name}.offset')
    scale = _triple(raw.get('scale', (1, 1, 1)), f'block {name}.scale', True)
    if occludes and (shape != 'cube' or offset != (0, 0, 0) or scale != (1, 1, 1)):
        raise ValueError(f'block {name}: only a complete unshifted opaque cube may occlude')
    if shape == 'decor' and merge != 'none':
        raise ValueError(f'block {name}: decor must not merge')
    if merge == 'xyz' and (not occludes or shape != 'cube' or offset != (0, 0, 0) or scale != (1, 1, 1)):
        raise ValueError(f'block {name}: xyz merging requires a complete unshifted opaque cube')
    color = raw.get('color')
    if color is not None:
        if not isinstance(color, str) or not re.fullmatch('#[0-9a-fA-F]{6}', color):
            raise ValueError(f'block {name}: color must be #RRGGBB')
        color = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
    material = tuple(material_values(raw.get('material', {})).items())
    return BlockDef(name, kind, value, shape, occludes, merge, color, offset, scale, True, material)


def builtin_block(name):
    """Undeclared block names use builtin opaque cubes, checked at preparation."""
    name = block_name(name)
    if any(s in name for s in ('glass', 'leaves', 'grass', 'flower', 'slab', 'stairs', 'fence', 'bush')) and name != 'grass_block' or name in ('air', 'water', 'ice'):
        raise ValueError(f'block {name}: non-cube blocks require an explicit blocks.json declaration')
    return BlockDef(name, 'builtin', name, merge='xyz')
