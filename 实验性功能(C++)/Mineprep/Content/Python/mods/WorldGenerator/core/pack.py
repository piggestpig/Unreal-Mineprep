"""Content packs: JSON data (parameters, presets, biomes) plus Python fields.

    packs/<id>/pack.json        id, name, params schema, pages, biome order...
    packs/<id>/presets/*.json   {"name": ..., "params": {"terrain.mountain_height": 20}}
    packs/<id>/biomes/*.json    one biome per file, see biomes.py / surface.py
    packs/<id>/<module>.py      @field functions listed in pack.json "modules"

A pack may `"extends": "<base>"`: it inherits content and overrides by key
(parameter definitions merge key by key, fields and biomes by id, presets
by file name). planning_params cache contracts require a local opt-in and
are not inherited. Loading is cached by file stamps; any edit changes
`Pack.fingerprint`, which is part of every generation cache key.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from collections import OrderedDict
import hashlib
import json
import math
from pathlib import Path
import re
import threading

from .biomes import Biome, _label, parse_biome, validate_climate
from .blocks import builtin_block, parse_block
from .features import parse_feature, compile_placements
from .fields import FieldDef, check_graph
from .density import DensityDef, DensityRecipe
from .materials import ShellMaterials
from .fluids import StaticFluids
from .spline import Spline, normalize_points
from .surface import ROLES, referenced_params, rule_fields, parse_rules
from . import pack_modules
from .ui_metadata import parse_sections, section_id
from types import SimpleNamespace
from types import MappingProxyType

PACKS_DIR = Path(__file__).resolve().parents[1] / "packs"
PACK_ROOTS = [PACKS_DIR]
ROOT_PACKAGE = __package__.rpartition(".")[0]  # "WorldGenerator" or "mods.WorldGenerator"
PIPELINE_FIELDS = ("slope",)  # computed by world.py with a halo, usable in rules
REQUIRED_PARAMS = ("world.y_min", "world.y_max", "world.sea_level", "surface.soil_depth",
                   "surface.boundary_scale", "surface.patch_scale")
TYPES = ("float", "int", "bool", "curve", "str")
_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_PACK_KEYS = {"id", "version", "name", "description", "extends", "modules", "height_field",
              "biome_parameters", "biomes", "default_preset", "pages", "params", "surface_overrides", "water", "planners", "planning_params", "ui_rows", "density", "shell_materials", "fluids", "format_version", "planner_gates", "feature_metrics", "biome_selector", "surface_processors", "mask_categories"}
_PACK_KEYS.update(('ui_sections','soil_depth_field','terrain_materials','block_order','preset_menu','reference_mask_field'))
_PARAM_KEYS = {"type", "default", "min", "max", "label", "tooltip", "page", "advanced", "enabled_param"}
_lock = threading.RLock()
_cache = OrderedDict()
CACHE_LIMIT = 32
_loading = []  # (roots, pack id) being loaded (guarded by _lock), for extends cycles


class PackChangedError(RuntimeError):
    """A request must be restarted rather than mixing two versions of its pack."""
    def __init__(self):
        super().__init__("资源包已变化，请重新生成")


@dataclass(frozen=True)
class ParamDef:
    key: str
    type: str
    default: object
    min: object = None
    max: object = None
    label: tuple = ("", "")
    tooltip: tuple = ("", "")
    page: str = ""
    advanced: bool = False
    enabled_param: object = None

    @property
    def section(self):
        return self.key.partition(".")[0]

    def coerce(self, value):
        where = f"parameter {self.key}"
        if self.type == "str":
            if not isinstance(value, str):
                raise ValueError(f"{where} must be text")
            return value
        if self.type == "bool":
            if type(value) is not bool:
                raise ValueError(f"{where} must be true/false")
            return value
        if self.type == "curve":
            return normalize_points(value)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{where} must be a number")
        if self.type == "int":
            if isinstance(value, float) and not value.is_integer():
                raise ValueError(f"{where} must be an integer")
            value = int(value)
        else:
            value = float(value)
            if value != value or value in (float("inf"), float("-inf")):
                raise ValueError(f"{where} must be finite")
        if self.min is not None and value < self.min or self.max is not None and value > self.max:
            raise ValueError(f"{where}={value} is outside [{self.min}, {self.max}]")
        return value


class Params(Mapping):
    """Resolved, validated parameters for one spec (defaults < preset < overrides)."""

    def __init__(self, values):
        self._values = dict(values)
        self._curves = {}

    def __getitem__(self, key):
        try:
            return self._values[key]
        except KeyError:
            raise KeyError(f"unknown parameter {key!r}") from None

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def curve(self, key):
        spline = self._curves.get(key)
        if spline is None:
            spline = self._curves[key] = Spline(self[key])
        return spline

    def to_dict(self):
        return {k: [list(p) for p in v] if isinstance(v, tuple) else v
                for k, v in sorted(self._values.items())}


@dataclass(frozen=True)
class Preset:
    id: str
    name: tuple
    params: dict
    section: object = None


@dataclass(frozen=True)
class UIRow:
    label: tuple
    keys: tuple
    components: tuple = ()


def parse_ui_rows(raw, params):
    """Display grouping only; every component retains its scalar definition."""
    if not isinstance(raw, (list, tuple)):
        raise ValueError('ui_rows must be a list')
    rows, seen = [], set()
    for item in raw:
        if not isinstance(item, dict) or not {'label', 'keys'} <= set(item) or set(item) - {'label', 'keys', 'components'}:
            raise ValueError('ui_rows entries require label and keys')
        keys = item['keys']
        if not isinstance(keys, (list, tuple)) or len(keys) not in (2, 3):
            raise ValueError('ui_rows need two or three numeric keys')
        if any(not isinstance(k, str) or k not in params or params[k].type not in ('int', 'float') for k in keys):
            raise ValueError('ui_rows must reference existing numeric parameters')
        if len(set(keys)) != len(keys) or seen.intersection(keys):
            raise ValueError('ui_rows components must appear only once')
        if len({(params[k].page, params[k].advanced) for k in keys}) != 1:
            raise ValueError('ui_rows must share a page and advanced visibility')
        components = item.get('components', [params[k].label for k in keys])
        if len(components) != len(keys):
            raise ValueError('ui_rows component labels must match keys')
        rows.append(UIRow(_label(item['label'], keys[0]), tuple(keys),
                          tuple(_label(v, k) for k, v in zip(keys, components))))
        seen.update(keys)
    return tuple(rows)


@dataclass(frozen=True)
class Pack:
    id: str
    name: tuple
    description: tuple
    root: Path
    chain: tuple               # (base id, ..., own id)
    params: dict               # key -> ParamDef, in declaration order
    pages: dict                # page id -> (zh, en)
    presets: dict              # id -> Preset
    default_preset: str
    biomes: tuple              # Biome, priority order
    biome_parameters: dict     # field -> distance scale
    fields: dict               # name -> FieldDef
    height_field: str
    blocks: tuple              # block table; surface IDs index into it
    fingerprint: str
    block_defs: dict
    surface_overrides: tuple
    water: object
    features: tuple
    planners: object = None
    ui_rows: tuple = ()
    density: object = None
    densities: object = None
    _generation_stamp: tuple = ()
    shell_materials: object = None
    fluids: object = None
    planning_params: object = None  # local opt-in cache dependencies; never inherited
    feature_defs: tuple = ()  # geometry registry; features contains compiled biome placements
    planner_gates: object = None
    feature_metrics: object = None
    biome_selector: object = None
    surface_processors: tuple = ()
    ui_sections: tuple = ()
    soil_depth_field: object = None
    reference_halo: int = 0
    reference_inputs: tuple = ()
    terrain_materials: object = None
    inactive_biomes: tuple = ()  # local files excluded from this snapshot's final order
    heightmap: object = None  # request-local immutable input; never loaded from pack files
    block_order: tuple = ()  # opt-in stable prefix; remaining referenced types append
    preset_menu: object = None  # local ordered quick-menu IDs; None shows all presets
    mask_categories: object = None
    masks: object = None  # request-local snapshots; do not change terrain planner identity
    reference_mask_field: object = None  # optional 0..1 presence of a reference surface

    @property
    def generation_fingerprint(self):
        """Preset labels/files do not change geometry once params are resolved."""
        return self._generation_stamp[1] if self._generation_stamp and self._generation_stamp[0] == self.fingerprint else self.fingerprint

    def preset_values(self, preset=""):
        preset = preset or self.default_preset
        if preset and preset not in self.presets:
            raise ValueError(f"pack {self.id!r} has no preset {preset!r}; "
                             f"choose from {sorted(self.presets)}")
        return self.presets[preset].params if preset else {}

    def resolve(self, spec):
        """Params for a WorldSpec; unknown keys and out-of-range values are errors."""
        if spec.pack != self.id:
            raise ValueError(f"spec is for pack {spec.pack!r}, not {self.id!r}")
        values = {k: d.default for k, d in self.params.items()}
        overrides = {**self.preset_values(spec.preset), **spec.overrides}
        unknown = sorted(set(overrides) - set(values))
        if unknown:
            raise ValueError(f"unknown parameters for pack {self.id!r}: {unknown}")
        values.update(overrides)
        values = {k: self.params[k].coerce(v) for k, v in values.items()}
        if self.heightmap is not None:
            from .heightmap import effective_values
            effective_values(self.heightmap, values)
        if not values["world.y_min"] < values["world.y_max"]:
            raise ValueError("world.y_min must be below world.y_max")
        volume = self.density is not None and self.density.base == 'volume'
        if not volume and not values["world.y_min"] <= values["world.sea_level"] < values["world.y_max"]:
            raise ValueError("world.sea_level must be inside [y_min, y_max)")
        validate_climate(self.biomes, values)
        return Params(values)


# -- loading ---------------------------------------------------------------

def register_pack_root(path):
    """Add a directory that contains <pack id>/pack.json folders (searched first)."""
    path = Path(path).resolve()
    with _lock:
        if path not in PACK_ROOTS:
            PACK_ROOTS.insert(0, path)


def pack_roots():
    """Serializable, absolute roots in priority order; never mutate worker globals."""
    with _lock:
        return tuple(str(Path(root).resolve()) for root in PACK_ROOTS)


def find_pack(pack_id, *, roots=None):
    roots = pack_roots() if roots is None else roots
    for root in map(Path, roots):
        if (root / pack_id / "pack.json").is_file():
            return root / pack_id
    raise ValueError(f"pack {pack_id!r} not found in {[str(r) for r in roots]}")


def list_packs():
    seen = {}
    for root in PACK_ROOTS:
        if root.is_dir():
            for entry in sorted(root.iterdir()):
                if (entry / "pack.json").is_file() and _ID.fullmatch(entry.name):
                    seen.setdefault(entry.name, entry)
    builtins = {'vanilla':0,'nether':1,'end':2}
    return sorted(seen,key=lambda name:(builtins.get(name,3),name))


def _files(directory):
    return sorted(p for p in directory.rglob("*")
                  if p.is_file() and p.suffix in (".json", ".py") and "__pycache__" not in p.parts)


def _stamp(directory):
    return tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in _files(directory))


def load_pack(pack_id, *, roots=None):
    """Load a pack and its bases using the same ordered directory list."""
    with _lock:
        roots = pack_roots() if roots is None else tuple(str(Path(r).resolve()) for r in roots)
        key = (roots, pack_id)
        directory = find_pack(pack_id, roots=roots)
        stamp = _stamp(directory)
        cached = _cache.get(key)
        if cached and cached[0] == stamp and cached[1].root == directory:
            base_ok = all(load_pack(b, roots=roots).fingerprint == f for b, f in cached[2])
            if base_ok:
                _cache[key] = cached  # recursive base checks may evict this entry
                _cache.move_to_end(key)
                while len(_cache) > CACHE_LIMIT:
                    _cache.popitem(last=False)
                return cached[1]
        if key in _loading:
            raise ValueError(f"pack extends cycle: {' -> '.join(k[1] for k in _loading + [key])}")
        _loading.append(key)
        try:
            pack, bases, context = _load(pack_id, directory, roots)
            if _stamp(directory) != stamp or any(
                    load_pack(b, roots=roots).fingerprint != f for b, f in bases):
                raise PackChangedError()
            context.committed = True
        except Exception:
            pack_modules.discard_uncommitted()
            raise
        finally:
            _loading.pop()
        _cache[key] = (stamp, pack, bases)
        _cache.move_to_end(key)
        while len(_cache) > CACHE_LIMIT:
            _cache.popitem(last=False)
        return pack


def catalog():
    """Report failures per pack without making healthy content unavailable."""
    result = []
    for pack_id in list_packs():
        try:
            pack = load_pack(pack_id)
            result.append(dict(id=pack_id, name=pack.name, status='ready', error=None))
        except Exception as exc:
            result.append(dict(id=pack_id, name=(pack_id, pack_id), status='error', error=str(exc)))
    return tuple(result)


def _read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{path.name}: duplicate key {key!r}")
            result[key] = value
        return result
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: {exc}") from None


def _planning_params(raw, params, planners, where):
    """Resolve exact keys or section.* selectors for this pack's cache contract."""
    if not isinstance(raw, dict):
        raise ValueError(f'{where}: planning_params must be a resource-to-list mapping')
    result = {}
    for resource, selectors in raw.items():
        if resource not in {*planners, 'surface', 'density'}:
            raise ValueError(f'{where}: planning_params has unknown resource {resource!r}')
        if not isinstance(selectors, list):
            raise ValueError(f'{where}: planning_params {resource} must be a list')
        keys = set()
        for selector in selectors:
            if not isinstance(selector, str):
                raise ValueError(f'{where}: planning_params selectors must be parameter names or section.*')
            if selector.endswith('.*') and '*' not in selector[:-1]:
                matches = {key for key in params if key.startswith(selector[:-1])}
            else:
                matches = {selector} if selector in params else set()
            if not matches:
                raise ValueError(f'{where}: planning_params {resource} has unknown selector {selector!r}')
            keys.update(matches)
        result[resource] = tuple(sorted(keys))
    return MappingProxyType(result)


def _load_module(context, pack_id, directory, name):
    if f'{context.prefix}.{pack_id}.{name}' not in context.sources:
        raise ValueError(f"pack {pack_id}: module {name}.py not found")
    module = context.module(pack_id, name)
    return {(type(v), v.name): v for v in vars(module).values() if isinstance(v, (FieldDef, DensityDef))}


def _callable(context, pack_id, directory, target):
    if not isinstance(target, str) or target.count(':') != 1:
        raise ValueError('extension function must be module:function')
    module, name = target.split(':')
    if not module.isidentifier() or not name.isidentifier():
        raise ValueError('invalid extension module/function')
    _load_module(context, pack_id, directory, module)
    fn = getattr(context.module(pack_id, module), name, None)
    if not callable(fn):
        raise ValueError(f'extension {target!r} must be callable')
    return fn


def _param_def(key, raw, base, where):
    if key in {'caves.branches', 'caves.spacing', 'caves.tunnel_length'}:
        raise ValueError(f'{where}: removed parameter {key}')
    if not isinstance(raw, dict) or set(raw) - _PARAM_KEYS:
        raise ValueError(f"{where}: parameter {key} keys are {sorted(_PARAM_KEYS)}")
    merged = {} if base is None else {
        "type": base.type, "default": base.default, "min": base.min, "max": base.max,
        "label": base.label, "tooltip": base.tooltip, "page": base.page, "advanced": base.advanced,
        "enabled_param": base.enabled_param}
    merged.update(raw)
    if merged.get("type") not in TYPES:
        raise ValueError(f"{where}: parameter {key} type must be one of {TYPES}")
    definition = ParamDef(key, merged["type"], merged.get("default"), merged.get("min"),
                          merged.get("max"), _label(merged.get("label"), key),
                          _label(merged.get("tooltip"), ""), merged.get("page") or key.partition(".")[0],
                          bool(merged.get("advanced", False)), merged.get('enabled_param'))
    return ParamDef(**{**definition.__dict__, "default": definition.coerce(definition.default)})


def _load(pack_id, directory, roots):
    where = f"pack {pack_id}"
    data = _read_json(directory / "pack.json")
    if data.get('format_version', 2) != 2:
        raise ValueError(f'{where}: run the one-time content upgrade to format_version 2')
    if data.get("id") != pack_id:
        raise ValueError(f"{where}: pack.json id must equal its folder name")
    unknown = set(data) - _PACK_KEYS
    if unknown:
        raise ValueError(f"{where}: unknown pack.json keys {sorted(unknown)}")
    base = load_pack(data["extends"], roots=roots) if data.get("extends") else None
    directories = [(name, str(find_pack(name, roots=roots)))
                   for name in ((base.chain if base else ()) + (pack_id,))]
    files = [(name, str(path), path.read_bytes()) for name, folder in directories
             for path in _files(Path(folder))]
    context = pack_modules.context(ROOT_PACKAGE, tuple(roots), directories,
                                   [f for f in files if Path(f[1]).suffix == '.py'],
                                   [(name, path, hashlib.sha256(content).hexdigest())
                                    for name, path, content in files])

    params = dict(base.params) if base else {}
    for key, raw in (data.get("params") or {}).items():
        params[key] = _param_def(key, raw, params.get(key), where)
    missing = [k for k in REQUIRED_PARAMS if k not in params]
    if missing:
        raise ValueError(f"{where}: missing required parameters {missing}")
    pages = dict(base.pages) if base else {}
    pages.update({k: _label(v, k) for k, v in (data.get("pages") or {}).items()})
    for definition in params.values():
        pages.setdefault(definition.page, (definition.page, definition.page))
    ui_sections = parse_sections(data.get('ui_sections', {}), pages, params, base.ui_sections if base else ())
    for definition in params.values():
        gate = definition.enabled_param
        if gate is not None and (gate not in params or params[gate].type != 'bool' or gate == definition.key):
            raise ValueError(f'{where}: invalid parameter enable gate {gate!r}')
        if gate is not None:
            section = next(s for s in ui_sections if definition.page in s.pages)
            schema_pages = section.pages if section.shared_group else (definition.page,)
            if params[gate].page not in schema_pages:
                raise ValueError(f'{where}: enable gate must share a native parameter schema')
    inherited_rows = [{'label': {'zh': r.label[0], 'en': r.label[1]}, 'keys': list(r.keys), 'components': r.components}
                      for r in base.ui_rows] if base else []
    ui_rows = parse_ui_rows(data.get('ui_rows', inherited_rows), params)

    presets = dict(base.presets) if base else {}
    for path in sorted((directory / "presets").glob("*.json")):
        raw = _read_json(path)
        if set(raw) - {"name", "params", "notes", "section"} or not isinstance(raw.get("params", {}), dict):
            raise ValueError(f"{where}: preset {path.name} keys are name/params")
        unknown = sorted(set(raw.get("params", {})) - set(params))
        if unknown:
            raise ValueError(f"{where}: preset {path.stem} sets unknown parameters {unknown}")
        values = {k: params[k].coerce(v) for k, v in raw.get("params", {}).items()}
        section = raw.get('section')
        if section is not None:
            from ..ui_model import page_id
            section = section_id(section, ui_sections)
            if not isinstance(section, str) or section in ('blocks', 'output'):
                raise ValueError(f'{where}: invalid preset section {section!r}')
            if not values or any(section_id(params[k].page, ui_sections) != section for k in values):
                raise ValueError(f'{where}: local preset must contain only {section} parameters')
        presets[path.stem] = Preset(path.stem, _label(raw.get("name"), path.stem), values, section)
    # Revalidate inherited presets against a child pack's parameter pages.
    from ..ui_model import page_id
    for preset in presets.values():
        if preset.section is not None and any(section_id(params[k].page, ui_sections) != preset.section for k in preset.params):
            raise ValueError(f'{where}: inherited local preset has incompatible parameter pages')
    default_preset = data.get("default_preset", base.default_preset if base else "")
    if default_preset and default_preset not in presets:
        raise ValueError(f"{where}: default_preset {default_preset!r} not found")
    if default_preset and presets[default_preset].section is not None:
        raise ValueError(f'{where}: default_preset must be a whole preset')
    preset_menu = data.get('preset_menu')
    if preset_menu is not None:
        if (not isinstance(preset_menu, list) or any(not isinstance(k,str) for k in preset_menu)
                or len(set(preset_menu)) != len(preset_menu)
                or any(k not in presets or presets[k].section is not None for k in preset_menu)):
            raise ValueError(f'{where}: preset_menu must list unique whole-preset IDs')
        preset_menu = tuple(preset_menu)

    fields = dict(base.fields) if base else {}
    densities = dict(base.densities or {}) if base else {}
    for name in data.get("modules", []):
        definitions = _load_module(context, pack_id, directory, name)
        fields.update({v.name: v for v in definitions.values() if isinstance(v, FieldDef)})
        densities.update({v.name: v for v in definitions.values() if isinstance(v, DensityDef)})
    planners = dict(base.planners or {}) if base else {}
    declaration = data.get('planners', {})
    if not isinstance(declaration, dict):
        raise ValueError(f'{where}: planners must map resource names to module:function')
    for resource, target in declaration.items():
        if not isinstance(resource, str) or not resource.isidentifier():
            raise ValueError(f'{where}: invalid planner resource name')
        if target is None:
            planners.pop(resource, None)
            continue
        if not isinstance(target, str) or target.count(':') != 1:
            raise ValueError(f'{where}: planner must be module:function')
        module_name, function_name = target.split(':')
        if not module_name.isidentifier() or not function_name.isidentifier():
            raise ValueError(f'{where}: invalid planner module/function')
        _load_module(context, pack_id, directory, module_name)
        function = getattr(context.module(pack_id, module_name), function_name, None)
        if not callable(function):
            raise ValueError(f'{where}: planner {target!r} is not callable')
        planners[resource] = function
    planner_gates = dict(base.planner_gates or {}) if base else {}
    declaration = data.get('planner_gates', {})
    if not isinstance(declaration, dict):
        raise ValueError(f'{where}: planner_gates must be a mapping')
    planner_gates.update(declaration)
    for resource, gates in planner_gates.items():
        if not isinstance(gates, (list, tuple)) or any(k not in params or params[k].type != 'bool' for k in gates):
            raise ValueError(f'{where}: planner_gates must contain boolean parameter names')
    planner_gates = {k: tuple(v) for k, v in planner_gates.items() if k in planners}
    # A descendant may replace fields/densities used indirectly by a planner.
    # It must explicitly review dependencies instead of inheriting exclusions.
    planning_params = _planning_params(data.get('planning_params', {}), params, planners, where)
    for definition in fields.values():
        if set(definition.resources) - planners.keys():
            raise ValueError(f'{where}: field {definition.name} requires undeclared resources')
    height_field = data.get("height_field", base.height_field if base else "height")
    soil_depth_field = data.get('soil_depth_field',base.soil_depth_field if base else None)
    if soil_depth_field is not None and (not isinstance(soil_depth_field,str) or not soil_depth_field.isidentifier()):
        raise ValueError(f'{where}: soil_depth_field must name a field or be null')
    recipe = base.density if base else None
    if 'density' in data:
        raw = data['density']
        recipe = None
        if raw is not None:
            if (not isinstance(raw, dict) or set(raw) - {'field', 'base', 'enabled_param', 'bounds', 'wet_protection'}
                    or raw.get('field') not in densities or raw.get('base', 'height') not in ('height', 'volume')):
                raise ValueError(f'{where}: density requires a registered field and height/volume base')
            gate = raw.get('enabled_param')
            if gate is not None and (not isinstance(gate,str) or gate not in params or params[gate].type != 'bool'):
                raise ValueError(f'{where}: density enabled_param must name a boolean parameter')
            if raw.get('base') == 'volume' and (gate is not None or raw.get('bounds') is not None):
                raise ValueError(f'{where}: volume density has no enabled_param or local bounds')
            bounds_fn = None
            target = raw.get('bounds')
            if target is not None:
                if not isinstance(target, str) or target.count(':') != 1:
                    raise ValueError(f'{where}: density bounds must be module:function')
                module_name, function_name = target.split(':')
                if not module_name.isidentifier() or not function_name.isidentifier():
                    raise ValueError(f'{where}: invalid density bounds module/function')
                _load_module(context, pack_id, directory, module_name)
                bounds_fn = getattr(context.module(pack_id, module_name), function_name, None)
                if not callable(bounds_fn):
                    raise ValueError(f'{where}: density bounds must be callable')
            protection = raw.get('wet_protection', 'shell')
            if protection not in ('shell', 'density'):
                raise ValueError(f'{where}: wet_protection must be shell or density')
            recipe = DensityRecipe(raw['field'], raw.get('base', 'height'), gate, bounds_fn, protection)
    check_graph(densities)
    for definition in densities.values():
        if any(set(densities[n].axes) - set(definition.axes) for n in definition.deps):
            raise ValueError(f'{where}: density {definition.name} dependency uses undeclared axes')
    if recipe is not None:
        def validate_density(name):
            definition = densities[name]
            if set(definition.resources) - planners.keys():
                raise ValueError(f'{where}: density {name} requires undeclared resources')
            for dependency in definition.deps:
                validate_density(dependency)
        validate_density(recipe.field)
    shell_materials = base.shell_materials if base else None
    if 'shell_materials' in data:
        raw = data['shell_materials']
        shell_materials = None
        if raw is not None:
            if (not isinstance(raw, dict) or set(raw) - {'sampler','blocks','enabled_param','surface_depth','surface_depth_enabled_param'}
                    or not isinstance(raw.get('sampler'),str) or raw['sampler'].count(':') != 1
                    or not isinstance(raw.get('blocks'),list) or not raw['blocks']
                    or any(not isinstance(n,str) for n in raw['blocks'])
                    or len(set(raw['blocks'])) != len(raw['blocks'])):
                raise ValueError(f'{where}: shell_materials requires sampler and unique output blocks')
            gate = raw.get('enabled_param')
            if gate is not None and (gate not in params or params[gate].type != 'bool'):
                raise ValueError(f'{where}: shell_materials enabled_param must name a boolean')
            module_name, function_name = raw['sampler'].split(':')
            if not module_name.isidentifier() or not function_name.isidentifier():
                raise ValueError(f'{where}: invalid shell_materials module/function')
            _load_module(context, pack_id, directory, module_name)
            function = getattr(context.module(pack_id, module_name), function_name, None)
            if not callable(function):
                raise ValueError(f'{where}: shell_materials sampler must be callable')
            depth = raw.get('surface_depth', 0)
            if type(depth) is not int or not 0 <= depth <= 4:
                raise ValueError(f'{where}: surface_depth must be an integer in [0, 4]')
            depth_gate = raw.get('surface_depth_enabled_param')
            if depth_gate is not None and (depth_gate not in params or params[depth_gate].type != 'bool'):
                raise ValueError(f'{where}: surface_depth_enabled_param must name a boolean')
            shell_materials = ShellMaterials(function,tuple(raw['blocks']),gate,depth,depth_gate)
    terrain_materials = base.terrain_materials if base else None
    if 'terrain_materials' in data:
        from .materials import TerrainMaterials
        raw = data['terrain_materials']; terrain_materials = None
        if raw is not None:
            if not isinstance(raw, dict) or not {'sampler','inputs','blocks'} <= raw.keys() or set(raw)-{'sampler','inputs','blocks','fields','enabled_param'}:
                raise ValueError(f'{where}: terrain_materials requires sampler, inputs and blocks')
            for name in ('inputs','blocks','fields'):
                values = raw.get(name, [])
                if (not isinstance(values, list) or any(not isinstance(n,str) for n in values)
                        or len(set(values)) != len(values) or (name != 'fields' and not values)):
                    raise ValueError(f'{where}: terrain_materials {name} must be a unique list')
            if any(n not in fields and n not in PIPELINE_FIELDS for n in raw.get('fields', [])):
                raise ValueError(f'{where}: terrain_materials has unknown reference fields')
            gate = raw.get('enabled_param')
            if gate is not None and (gate not in params or params[gate].type != 'bool'):
                raise ValueError(f'{where}: terrain_materials enabled_param must name a boolean')
            terrain_materials = TerrainMaterials(_callable(context,pack_id,directory,raw['sampler']),
                tuple(raw['inputs']),tuple(raw['blocks']),tuple(raw.get('fields',[])),gate)
    fluids = base.fluids if base else None
    if 'fluids' in data:
        raw = data['fluids']; fluids = None
        if raw is not None:
            if (not isinstance(raw,dict) or set(raw)-{'sampler','block','enabled_param','requires'}
                    or not isinstance(raw.get('sampler'),str) or raw['sampler'].count(':')!=1
                    or not isinstance(raw.get('block'),str) or not isinstance(raw.get('requires',[]),list)):
                raise ValueError(f'{where}: fluids requires sampler and surface block')
            gate=raw.get('enabled_param');requires=raw.get('requires',[])
            if any(not isinstance(k,str) or k not in params or params[k].type!='bool'
                   for k in (*requires,*((gate,) if gate is not None else ()))):
                raise ValueError(f'{where}: fluids gates must name boolean parameters')
            module_name,function_name=raw['sampler'].split(':')
            if not module_name.isidentifier() or not function_name.isidentifier():raise ValueError(f'{where}: invalid fluids sampler')
            _load_module(context,pack_id,directory,module_name)
            function=getattr(context.module(pack_id,module_name),function_name,None)
            if not callable(function):raise ValueError(f'{where}: fluids sampler must be callable')
            fluids=StaticFluids(function,raw['block'],gate,tuple(requires))
    biome_parameters = dict(base.biome_parameters) if base else {}
    for name, scale in (data.get("biome_parameters") or {}).items():
        if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0:
            raise ValueError(f"{where}: biome_parameters.{name} must be a finite positive distance scale")
        biome_parameters[name] = float(scale)

    own = {}
    for path in sorted((directory / "biomes").glob("*.json")):
        biome = parse_biome(_read_json(path), biome_parameters, f"{pack_id}/biomes/{path.name}")
        if biome.id != path.stem:
            raise ValueError(f"{where}: biomes/{path.name} id must equal its file name")
        own[biome.id] = biome
    known = {b.id: b for b in base.biomes} if base else {}
    known.update(own)
    order = data.get("biomes", [b.id for b in base.biomes] if base else sorted(own))
    if not order or any(b not in known for b in order) or len(set(order)) != len(order):
        raise ValueError(f"{where}: biomes list must name existing biome files once each")
    biomes = tuple(known[b] for b in order)
    if sum(b.fallback for b in biomes) > 1:
        raise ValueError(f"{where}: biomes list may contain at most one fallback")

    overrides = base.surface_overrides if base else ()
    if 'surface_overrides' in data:
        overrides = parse_rules(data['surface_overrides'], f'{where}.surface_overrides', complete=False) if data['surface_overrides'] else ()
    rule_sources = (*biomes, SimpleNamespace(surface=overrides, climate=()))
    definitions = {k: v for k, v in base.block_defs.items() if v.explicit} if base else {}
    block_path = directory / 'blocks.json'
    if block_path.is_file():
        raw = _read_json(block_path)
        if not isinstance(raw, dict):
            raise ValueError(f'{where}: blocks.json must be a mapping')
        for name, definition in raw.items():
            item = parse_block(name, definition, directory)
            definitions[item.id] = item
    water = data.get('water', base.water if base else None)
    if water is not None and (not isinstance(water, dict) or 'block' not in water
                             or set(water) - {'block', 'level_field', 'mask_field', 'generate_param', 'enabled_param'}
                             or water['block'] not in definitions):
        raise ValueError(f'{where}: water needs a declared block and optional level_field/mask_field')
    for key in ('level_field', 'mask_field'):
        if water and key in water and (not isinstance(water[key], str) or water[key] not in fields):
            raise ValueError(f'{where}: water.{key} must reference a registered field')
    for key in ('generate_param', 'enabled_param'):
        gate = water.get(key) if water else None
        if gate is not None and (gate not in params or params[gate].type != 'bool'):
            raise ValueError(f'{where}: water.{key} must name a boolean parameter')
    features = {f.id: f for f in base.feature_defs} if base else {}
    feature_path = directory / 'features.json'
    if feature_path.is_file():
        raw = _read_json(feature_path)
        if not isinstance(raw, dict):
            raise ValueError(f'{where}: features.json must be a mapping')
        from dataclasses import replace
        for name, item in raw.items():
            definition = parse_feature(name, item)
            features[name] = replace(definition, owner=pack_id) if definition.type in ('multi_block','column_field') else definition
    for f in features.values():
        if f.type == 'surface_scatter' and (f.block not in definitions or definitions[f.block].shape != 'decor'):
            raise ValueError(f'feature {f.id}: block must be declared decor')
        if f.type == 'surface_scatter' and f.placement == 'volume_floor' and (recipe is None or recipe.base != 'volume'):
            raise ValueError(f'feature {f.id}: volume_floor requires volume density')
        if f.type in ('multi_block','column_field'):
            from dataclasses import replace
            if f.type == 'multi_block' and f.collision == 'cells' and (recipe is None or recipe.base != 'volume'):
                raise ValueError(f'feature {f.id}: cell collision requires volume density')
            if f.type == 'multi_block' and f.support == 'ceiling' and (
                    recipe is None or recipe.base != 'volume' or f.placement is None):
                raise ValueError(f'feature {f.id}: ceiling support requires volume density and placement')
            if f.type == 'multi_block' and isinstance(f.cell_size,str):
                key = f.cell_size[1:]
                if key not in params or params[key].type != 'int' or not 1 <= params[key].default <= 1024:
                    raise ValueError(f'feature {f.id}: cell_size requires an integer parameter in [1,1024]')
            if any(n not in definitions or definitions[n].shape not in ('cube', 'decor') for n in f.blocks):
                raise ValueError(f'feature {f.id}: blocks must be declared cubes or decor')
            if f.type == 'column_field' and any(not definitions[n].occludes for n in f.blocks):
                raise ValueError(f'feature {f.id}: column materials must be complete occluding cubes')
            module_name, function_name = f.generator.split(':')
            owners = (f.owner, *((base.chain[::-1]) if base else ()))
            owner = next((name for name in owners if f'{context.prefix}.{name}.{module_name}' in context.sources), f.owner)
            _load_module(context, owner, directory, module_name)
            function = getattr(context.module(owner, module_name), function_name, None)
            if not callable(function):
                raise ValueError(f'feature {f.id}: generator {f.generator!r} is not callable')
            import inspect
            arguments = 1 if f.type == 'column_field' else 3
            if len(inspect.signature(function).parameters) != arguments:
                raise ValueError(f'feature {f.id}: generator takes '+('ctx' if arguments == 1 else 'ctx, anchors, keys'))
            features[f.id] = replace(f, owner=owner, fn=function)
            if getattr(f,'placement',None) is not None:
                placement_module = f.placement.split(':')[0]
                placement_owner = next((name for name in owners
                    if f'{context.prefix}.{name}.{placement_module}' in context.sources),f.owner)
                placement = _callable(context,placement_owner,directory,f.placement)
                if len(inspect.signature(placement).parameters) != 3:
                    raise ValueError(f'feature {f.id}: placement takes ctx, candidate_xz, keys')
                features[f.id] = replace(features[f.id],placement_fn=placement)
    feature_defs = tuple(features.values())
    placements = compile_placements(features, biomes, params)
    selector = base.biome_selector if base else None
    if 'biome_selector' in data:
        selector = _callable(context, pack_id, directory, data['biome_selector']) if data['biome_selector'] is not None else None
    processors = base.surface_processors if base else ()
    if 'surface_processors' in data:
        from .postprocess import SurfaceProcessor
        processors = []
        raw = data['surface_processors']
        if not isinstance(raw, list):
            raise ValueError(f'{where}: surface_processors must be an ordered list')
        for item in raw:
            if (not isinstance(item, dict) or not {'id','function','blocks','radius'} <= item.keys()
                    or set(item)-{'id','function','blocks','radius','enabled_param','sky_only','category','volume'}
                    or not isinstance(item.get('category',''), str)
                    or (item.get('category') and not item['category'].isidentifier())
                    or type(item.get('sky_only',False)) is not bool
                    or type(item.get('volume',False)) is not bool
                    or not isinstance(item['id'], str) or not item['id'].isidentifier()
                    or not isinstance(item['blocks'], list) or not item['blocks']
                    or any(n not in definitions for n in item['blocks'])
                    or type(item['radius']) is not int or not 0 <= item['radius'] <= 64):
                raise ValueError(f'{where}: invalid surface_processors declaration')
            gate = item.get('enabled_param')
            if gate is not None and (gate not in params or params[gate].type != 'bool'):
                raise ValueError(f'{where}: surface processor gate must be a boolean')
            processors.append(SurfaceProcessor(item['id'],item['function'],tuple(item['blocks']),item['radius'],gate,
                                               _callable(context,pack_id,directory,item['function']),
                                               sky_only=item.get('sky_only',False), category=item.get('category',''),volume=item.get('volume',False)))
        if len({p.id for p in processors}) != len(processors):
            raise ValueError(f'{where}: duplicate surface processor IDs')
        processors = tuple(processors)
    metrics = dict(base.feature_metrics or {}) if base else {}
    metrics.update(data.get('feature_metrics', {}))
    for name, rule in metrics.items():
        if (not isinstance(name, str) or not name.isidentifier() or not isinstance(rule, dict)
                or set(rule) != {'category', 'blocks'} or not isinstance(rule['category'], str)
                or not isinstance(rule['blocks'], list) or any(not isinstance(n, str) for n in rule['blocks'])):
            raise ValueError(f'{where}: invalid feature_metrics declaration')
    if water and (definitions[water['block']].shape != 'surface' or definitions[water['block']].occludes):
        raise ValueError(f'{where}: water requires a non-occluding surface')

    all_fields = {**fields}
    check_graph(all_fields)
    needed = [height_field, *biome_parameters, *rule_fields(rule_sources)]
    unknown = sorted({n for n in needed if n not in all_fields and n not in PIPELINE_FIELDS})
    if unknown:
        raise ValueError(f"{where}: fields referenced but not defined: {unknown}")
    if height_field not in all_fields:
        raise ValueError(f"{where}: height_field {height_field!r} is not a field")
    if soil_depth_field is not None and soil_depth_field not in all_fields:
        raise ValueError(f'{where}: soil_depth_field {soil_depth_field!r} is not a field')
    reference_mask_field = data.get('reference_mask_field', base.reference_mask_field if base else None)
    if reference_mask_field is not None and (not isinstance(reference_mask_field,str) or reference_mask_field not in all_fields):
        raise ValueError(f'{where}: reference_mask_field {reference_mask_field!r} is not a field')
    def reference_halo(name):
        # Height already owns its own dependency halos. Only material consumers
        # need extra height coverage; compute it once per immutable Pack.
        if name == height_field or name not in all_fields: return 0
        definition = all_fields[name]
        return definition.halo + max((reference_halo(n) for n in definition.deps),default=0)
    halo = max((reference_halo(n) for n in (*rule_fields(rule_sources),soil_depth_field)),default=0)
    inputs = {n for n in rule_fields(rule_sources) if n in fields and fields[n].resources}
    if water: inputs.update(water[n] for n in ('level_field','mask_field') if n in water)
    unknown = sorted(k for k in referenced_params(rule_sources) if k not in params)
    if unknown:
        raise ValueError(f"{where}: biome rules reference unknown parameters {unknown}")
    wrong = sorted(k for k in referenced_params(rule_sources) if params[k].type not in ("float", "int"))
    if wrong:
        raise ValueError(f"{where}: rule bounds must reference numeric parameters: {wrong}")
    validate_climate(biomes, {k: d.default for k, d in params.items()})

    terrain_blocks = tuple(dict.fromkeys(n for b in biomes for n in b.blocks))
    terrain_blocks += tuple(n for r in overrides for _, c in r.roles for n in c.names)
    # Append opt-in floor decorations after the legacy palette, preserving
    # existing material IDs/order when the new decorations are disabled.
    floor_placements = tuple(f for f in placements if f.type == 'surface_scatter' and f.placement == 'volume_floor')
    blocks = tuple(dict.fromkeys((*terrain_blocks, *(n for f in placements if f not in floor_placements for n in (*f.surface, *f.blocks)),
                                 *((water['block'],) if water else ()),
                                 *(shell_materials.blocks if shell_materials else ()),
                                 *( (*terrain_materials.inputs,*terrain_materials.blocks) if terrain_materials else ()),
                                 *(n for p in processors for n in p.blocks),
                                 *((fluids.block,) if fluids else ()),
                                 *(n for f in floor_placements for n in (*f.surface, *f.blocks)))))
    block_order = data.get('block_order',list(base.block_order) if base else [])
    if (not isinstance(block_order,list) or any(not isinstance(n,str) for n in block_order)
            or len(set(block_order)) != len(block_order)
            or any(n not in definitions and n not in blocks for n in block_order)):
        raise ValueError(f'{where}: block_order must list unique known block IDs')
    if block_order:
        selected = set(block_order)
        blocks = tuple(n for n in block_order if n in blocks) + tuple(n for n in blocks if n not in selected)
    if len(blocks) >= 65535:
        raise ValueError(f'{where}: too many block types')
    for name in blocks:
        if name not in definitions:
            definitions[name] = builtin_block(name)
    if fluids and (definitions[fluids.block].shape!='surface' or definitions[fluids.block].occludes
                   or definitions[fluids.block].merge not in ('none','xz')):
        raise ValueError(f'{where}: fluids requires a non-occluding horizontal surface')
    for name in (*terrain_blocks, *(shell_materials.blocks if shell_materials else ()),
                 *((*terrain_materials.inputs,*terrain_materials.blocks) if terrain_materials else ())):
        b = definitions[name]
        if b.shape != 'cube' or not b.occludes:
            raise ValueError(f'block {name}: height columns require complete opaque cubes')
    digest = hashlib.sha256()
    generation_digest = hashlib.sha256()
    for path in _files(directory):
        relative = path.relative_to(directory)
        content = path.read_bytes()
        digest.update(relative.as_posix().encode() + b"\0" + content + b"\0")
        if relative.parts[0] == 'presets':
            continue
        if relative.as_posix() == 'pack.json':
            manifest = _read_json(path)
            manifest.pop('default_preset',None)
            manifest.pop('preset_menu',None)
            content = json.dumps(manifest,sort_keys=True,ensure_ascii=False).encode()
        elif relative.as_posix() == 'blocks.json':
            # Shader overrides change prepared resources, never numeric generation.
            definitions_for_key = _read_json(path)
            content = json.dumps({name: {k:v for k,v in item.items() if k != 'material'}
                                  for name,item in definitions_for_key.items()},
                                 sort_keys=True,ensure_ascii=False).encode()
        generation_digest.update(relative.as_posix().encode()+b'\0'+content+b'\0')
    if base:
        digest.update(base.fingerprint.encode())
        generation_digest.update(base.generation_fingerprint.encode())
    pack = Pack(pack_id, _label(data.get("name"), pack_id), _label(data.get("description"), ""),
                directory, (base.chain if base else ()) + (pack_id,), params, pages, presets,
                default_preset, biomes, biome_parameters, fields, height_field, blocks,
                digest.hexdigest(), definitions, overrides, water, tuple(features.values()), planners, ui_rows, recipe, densities,
                (digest.hexdigest(),generation_digest.hexdigest()), shell_materials, fluids, planning_params,
                feature_defs, planner_gates, metrics, selector, processors)
    from dataclasses import replace
    mask_categories = dict(base.mask_categories or {}) if base else {}
    groups = data.get('mask_categories', {})
    if not isinstance(groups, dict) or set(groups)-{'vegetation','clearance'}:
        raise ValueError(f'{where}: mask_categories supports vegetation and clearance')
    for kind, categories in groups.items():
        if (not isinstance(categories, list) or any(not isinstance(c,str) or not c.isidentifier() for c in categories)
                or len(set(categories)) != len(categories)):
            raise ValueError(f'{where}: mask categories must be unique category names')
        mask_categories[kind] = tuple(categories)
    pack = replace(pack, features=placements, ui_sections=ui_sections,soil_depth_field=soil_depth_field,reference_halo=halo,
                   reference_inputs=tuple(sorted(inputs)),terrain_materials=terrain_materials,
                   inactive_biomes=tuple(sorted(own.keys() - set(order))),block_order=tuple(block_order),
                   preset_menu=preset_menu, mask_categories=mask_categories,reference_mask_field=reference_mask_field)
    bases = ((base.id, base.fingerprint),) if base else ()
    return pack, bases, context


__all__ = ["Pack", "ParamDef", "Params", "Preset", "Biome", "ROLES", "PACKS_DIR",
           "load_pack", "list_packs", "register_pack_root", "find_pack"]
