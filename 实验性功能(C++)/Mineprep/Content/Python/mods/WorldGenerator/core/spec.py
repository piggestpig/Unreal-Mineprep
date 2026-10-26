"""WorldSpec: the one generation input shared by UI, scripts and agents.

A spec names a Pack and a preset, then records only the parameter overrides.
Values are validated against the Pack schema by `Pack.resolve(spec)`; the spec
itself only checks structure, so it stays small, JSON-friendly and picklable.
Execution mode, backend and placement are deliberately not part of a spec.
"""

from dataclasses import dataclass, field, replace
import hashlib
import json
import math
import re
from pathlib import Path

from .data import Region, require_int

SPEC_VERSION = 2
_KEY = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
_ID = re.compile(r"^[a-z][a-z0-9_]*$")


def height_range(value, name, *, increasing=False):
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError(f'{name} must contain two finite numbers')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in value):
        raise ValueError(f'{name} must contain two finite numbers')
    result = tuple(float(v) for v in value)
    if increasing and result[0] >= result[1]:
        raise ValueError(f'{name} lower bound must be below its upper bound')
    return result


@dataclass(frozen=True)
class HeightmapInput:
    """File reference and fixed mapping bounds; configuration never decodes pixels."""
    path: str
    region: Region
    mode: str = 'faithful'
    input_range: tuple = (0., 1.)
    output_range: object = None

    def __post_init__(self):
        if not isinstance(self.path, (str, Path)) or not str(self.path).strip():
            raise ValueError('heightmap path must name a PNG or EXR file')
        path = Path(self.path).resolve()
        if path.suffix.lower() not in ('.png', '.exr'):
            raise ValueError('heightmap supports grayscale PNG or EXR')
        if not isinstance(self.region, Region):
            raise ValueError('heightmap region must be a Region')
        if self.mode not in ('faithful', 'add'):
            raise ValueError('heightmap mode must be faithful or add')
        object.__setattr__(self, 'path', str(path))
        object.__setattr__(self, 'input_range', height_range(self.input_range, 'input_range', increasing=True))
        if self.output_range is not None:
            object.__setattr__(self, 'output_range', height_range(self.output_range, 'output_range'))

    def to_dict(self):
        return dict(path=self.path, region=self.region.to_list(), mode=self.mode,
                    input_range=list(self.input_range),
                    output_range=None if self.output_range is None else list(self.output_range))

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) - {'path', 'region', 'mode', 'input_range', 'output_range'}:
            raise ValueError('invalid heightmap descriptor')
        if 'path' not in data or 'region' not in data:
            raise ValueError('heightmap requires path and fixed region')
        return cls(**{**data, 'region': Region(*data['region'])})


@dataclass(frozen=True)
class MaskInput:
    """A numeric image mapped to a fixed horizontal world region."""
    path: str
    region: Region

    def __post_init__(self):
        path = Path(self.path).resolve() if isinstance(self.path, (str, Path)) and str(self.path).strip() else None
        if path is None or path.suffix.lower() not in ('.png', '.exr'):
            raise ValueError('mask path must name a PNG or EXR file')
        if not isinstance(self.region, Region):
            raise ValueError('mask region must be a Region')
        object.__setattr__(self, 'path', str(path))

    def to_dict(self):
        return dict(path=self.path, region=self.region.to_list())

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != {'path', 'region'}:
            raise ValueError('mask requires path and fixed region')
        return cls(data['path'], Region(*data['region']))


def canonical_value(value):
    """Hashable, JSON-canonical form: ints stay ints, floats are floats, lists are tuples."""
    if isinstance(value, bool) or isinstance(value, str) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("parameter values must be finite")
        return value
    if isinstance(value, (list, tuple)):
        return tuple(canonical_value(v) for v in value)
    raise ValueError(f"unsupported parameter value: {value!r}")


def _plain(value):
    return [_plain(v) for v in value] if isinstance(value, tuple) else value


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


@dataclass(frozen=True)
class WorldSpec:
    pack: str = "vanilla"
    preset: str = ""  # empty: the pack's default preset
    seed: int = 42
    region: Region = Region(0, 0, 256, 256)
    params: tuple = field(default=())  # sorted ((dotted.key, value), ...) overrides
    heightmap: object = None  # HeightmapInput; bytes stay outside the serializable spec
    vegetation_mask: object = None
    clearance_mask: object = None

    def __post_init__(self):
        if not isinstance(self.pack, str) or not _ID.fullmatch(self.pack):
            raise ValueError(f"invalid pack id: {self.pack!r}")
        if not isinstance(self.preset, str) or (self.preset and not _ID.fullmatch(self.preset)):
            raise ValueError(f"invalid preset id: {self.preset!r}")
        require_int("seed", self.seed, -(2**63), 2**63 - 1)
        if not isinstance(self.region, Region):
            raise ValueError("region must be a Region")
        if self.heightmap is not None and not isinstance(self.heightmap, HeightmapInput):
            raise ValueError('heightmap must be a HeightmapInput or None')
        for name in ('vegetation_mask', 'clearance_mask'):
            if getattr(self, name) is not None and not isinstance(getattr(self, name), MaskInput):
                raise ValueError(f'{name} must be a MaskInput or None')
        items = self.params.items() if isinstance(self.params, dict) else self.params
        params = {}
        for key, value in items:
            if not isinstance(key, str) or not _KEY.fullmatch(key):
                raise ValueError(f"parameter keys look like 'section.name': {key!r}")
            params[key] = canonical_value(value)
        object.__setattr__(self, "params", tuple(sorted(params.items())))

    @property
    def overrides(self):
        return dict(self.params)

    def with_params(self, values=None, **kwargs):
        """New spec with more overrides; `section__name=v` keywords mean 'section.name'."""
        merged = self.overrides
        merged.update(values or {})
        merged.update({k.replace("__", "."): v for k, v in kwargs.items()})
        return replace(self, params=tuple(merged.items()))

    def without_params(self, *keys):
        return replace(self, params=tuple((k, v) for k, v in self.params if k not in keys))

    def replace(self, **changes):
        if "region" in changes and not isinstance(changes["region"], Region):
            changes["region"] = Region(*changes["region"])
        return replace(self, **changes)

    def to_dict(self):
        return {"version": SPEC_VERSION, "pack": self.pack, "preset": self.preset,
                "seed": self.seed, "region": self.region.to_list(),
                "params": {k: _plain(v) for k, v in self.params},
                "heightmap": None if self.heightmap is None else self.heightmap.to_dict(),
                **{name: getattr(self, name).to_dict() for name in ('vegetation_mask', 'clearance_mask')
                   if getattr(self, name) is not None}}

    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True,
                          indent=indent, allow_nan=False) + "\n"

    @property
    def key(self):
        """SHA256 of the canonical spec (not of the Pack files; see pack.world_key)."""
        raw = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("spec must be a JSON object")
        unknown = set(data) - {"version", "pack", "preset", "seed", "region", "params", "heightmap",
                               "vegetation_mask", "clearance_mask"}
        if unknown:
            raise ValueError(f"unknown spec keys: {sorted(unknown)}")
        if data.get("version", SPEC_VERSION) not in (1, SPEC_VERSION):
            raise ValueError(f"unsupported spec version: {data.get('version')!r}")
        if data.get('version') == 1 and data.get('heightmap') is not None:
            raise ValueError('WorldSpec 1 cannot contain a heightmap')
        region = data.get("region", [0, 0, 256, 256])
        if isinstance(region, dict):
            region = Region(**region)
        elif isinstance(region, (list, tuple)) and len(region) == 4:
            region = Region(*region)
        else:
            raise ValueError("region must be [x0, z0, width, depth]")
        params = data.get("params", {})
        if not isinstance(params, dict):
            raise ValueError("params must be an object of dotted keys")
        return cls(pack=data.get("pack", "vanilla"), preset=data.get("preset", ""),
                   seed=data.get("seed", 42), region=region, params=tuple(params.items()),
                   heightmap=None if data.get('heightmap') is None else HeightmapInput.from_dict(data['heightmap']),
                   **{name: None if data.get(name) is None else MaskInput.from_dict(data[name])
                      for name in ('vegetation_mask', 'clearance_mask')})

    @classmethod
    def from_json(cls, text):
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object))
