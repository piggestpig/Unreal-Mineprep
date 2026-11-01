"""Editor property groups. Pack parameters get a generated group, so a new entry in
pack.json appears in the panel without touching this file."""

import mineprep
import unreal
import math

from .core.spline import normalize_points, points_from_ue_text, ue_text_from_points
from .ui_model import group_pages
from .localization import bind_properties


def _components(value, count):
    return tuple(getattr(value, axis) for axis in ('x', 'y', 'z')[:count])


class _ScalarAliases:
    """Component bindings for dynamically declared parameter rows."""
    _aliases_ = {}

    def __getattr__(self, name):
        binding = type(self)._aliases_.get(name)
        if binding:
            attr, index, kind = binding
            value = _components(getattr(self, attr), index + 1)[index]
            if kind is int and (isinstance(value, float) and (not math.isfinite(value) or not value.is_integer())):
                raise ValueError(f'{name}: value must be an integer')
            return kind(value)
        return super().__getattr__(name)

    def __setattr__(self, name, value):
        binding = type(self)._aliases_.get(name)
        if binding:
            attr, index, kind = binding
            if kind is int and (isinstance(value, bool) or not isinstance(value, int)):
                raise ValueError(f'{name}: value must be an integer')
            old = getattr(self, attr)
            values = list(_components(old, 3 if hasattr(old, 'z') else 2))
            values[index] = kind(value)
            return super().__setattr__(attr, type(old)(*values))
        return super().__setattr__(name, value)


class WorldRange(mineprep.PropertyGroup):
    _autosave_ = False
    Seed: int = (42, {"NoSpinbox": True})
    Origin: unreal.IntPoint = unreal.IntPoint(0, 0)
    Size: unreal.IntPoint = (unreal.IntPoint(512, 512), {"ClampMin": 1, "UIMax": 2048})
    CellStep: int = 1
    CoreEnabled: bool = False
    CoreEmpty: bool = (False, {'EditCondition':'CoreEnabled','HideEditConditionToggle':True})
    CoreA: unreal.IntPoint = (unreal.IntPoint(0,0), {'EditCondition':'CoreEnabled','HideEditConditionToggle':True})
    CoreB: unreal.IntPoint = (unreal.IntPoint(512,512), {'EditCondition':'CoreEnabled','HideEditConditionToggle':True})
    CoreInitialized: bool = (False, {'EditCondition':'false','EditConditionHides':True})


class WorldOutput(mineprep.PropertyGroup):
    _autosave_ = False
    _ui_properties_ = frozenset({'UIIsISM', 'UIUsesWorkers'})
    UIIsISM: bool = (False, {"EditCondition": "false", "EditConditionHides": True})
    UIUsesWorkers: bool = (True, {"EditCondition": "false", "EditConditionHides": True})
    OutputName: str = "World"
    Offset: unreal.Vector = unreal.Vector(0, 0, 0)
    ISMChunkCount: int = (1, {"ClampMin": 1, "UIMax": 256,
                            "EditCondition": "UIIsISM", "EditConditionHides": True,
                            "HideEditConditionToggle": True,
                            "ToolTip": 'Spatial chunks, not Actor count; one Actor per model type'})
    GPUTypeGroupCount: int = (1, {"ClampMin": 1, "UIMax": 16,
                                "EditCondition": "!UIIsISM", "EditConditionHides": True,
                                "HideEditConditionToggle": True,
                                "ToolTip": 'Split models into output groups, one Actor per group; model types are not split'})
    Workers: int = (4, {"ClampMin": 1, "ClampMax": 16,
                        "EditCondition": "UIUsesWorkers", "HideEditConditionToggle": True})
    Budgets: unreal.Vector2D = (unreal.Vector2D(2147483647, 2000000), {"ClampMin": 1, "ClampMax": 2**40,
        "Delta": 1, "UIMax": 9_999_999_999,
        "ToolTip": 'Preprocess cells: width × depth × output height; final instances: total merged count'})
    BCTEnabled: bool = (True, {"InlineEditConditionToggle": True})
    BCTColorMode: str = 'rgb'
    BCTCellSize: int = (4, {"ClampMin": 1, "ClampMax": 16, "EditCondition": "BCTEnabled",
                           "ToolTip": 'Blocks per pixel; approximately eight-block blending'})
    BCTPower: float = (1., {'ClampMin': 0, 'UIMax': 4, 'EditCondition': 'BCTEnabled',
        'ToolTip': 'Exponent applied to positive RGB/HSV values before encoding and blending; 1 keeps defaults'})


class WorldCustom(mineprep.PropertyGroup):
    _autosave_ = False
    Enabled: bool = False
    Path: str = ''
    SourceKind: str = 'file'
    AssetPath: str = ''
    Mode: str = 'faithful'
    InputRange: unreal.Vector2D = unreal.Vector2D(0., 1.)
    AutoOutput: bool = (True, {"InlineEditConditionToggle": True})
    OutputRange: unreal.Vector2D = (unreal.Vector2D(0., 192.), {"EditCondition": "!AutoOutput"})
    Origin: unreal.IntPoint = unreal.IntPoint(0, 0)
    Size: unreal.IntPoint = (unreal.IntPoint(512, 512), {'ClampMin': 1})


class HeightmapTexture(mineprep.PropertyGroup):
    _autosave_ = False
    Texture: unreal.Texture2D = None


class MapPaintTools(mineprep.PropertyGroup):
    _autosave_ = False
    Value: float = 16.
    Diameter: float = (32., {'ClampMin': .1, 'ClampMax': 65536., 'UIMin': 1., 'UIMax': 256.})
    Hardness: float = (.5, {'ClampMin': 0., 'ClampMax': 1., 'Delta': .05})
    Strength: float = (1., {'ClampMin': 0., 'ClampMax': 1., 'Delta': .05})
    Visible: bool = True




class MaskOptions(mineprep.PropertyGroup):
    _autosave_ = False
    Enabled: bool = False
    Path: str = ''
    SourceKind: str = 'file'
    AssetPath: str = ''
    Origin: unreal.IntPoint = unreal.IntPoint(0, 0)
    Size: unreal.IntPoint = (unreal.IntPoint(512, 512), {'ClampMin': 1})






class BiomeMapOptions(mineprep.PropertyGroup):
    _autosave_ = False
    Enabled: bool = False
    Path: str = ''
    Palette: str = ''
    Tolerance: int = (32, {'ClampMin': 0, 'ClampMax': 255})
    Origin: unreal.IntPoint = unreal.IntPoint(0, 0)
    Size: unreal.IntPoint = (unreal.IntPoint(512, 512), {'ClampMin': 1})


class BiomeMapColor(mineprep.PropertyGroup):
    _autosave_ = False
    Color: unreal.LinearColor = ((1, 0, 0, 1), {'HideAlphaChannel': True, 'ClampMin': 0, 'ClampMax': 1})


class LandscapeView(mineprep.PropertyGroup):
    """Image-only ceiling; excluded from operation values and generation requests."""
    _autosave_ = False
    MaxY: int = 127




class CaveSlice(mineprep.PropertyGroup):
    """Preview-only world coordinates; never included in a Spec or preparation key."""
    _autosave_ = False
    VerticalY: int = 0
    VerticalX: int = 0
    HorizontalZ: int = 0






WorldRange.localize(tooltip=True)
WorldOutput.localize(tooltip=True)
WorldCustom.localize(tooltip=True)
HeightmapTexture.localize(tooltip=True)
MapPaintTools.localize(tooltip=True)
MaskOptions.localize(tooltip=True)
BiomeMapOptions.localize(tooltip=True)
BiomeMapColor.localize(tooltip=True)
LandscapeView.localize(tooltip=True)
CaveSlice.localize(tooltip=True)


def prop_name(key):
    """'terrain.erosion_scale' -> 'terrain__erosion_scale' (UE property names are identifiers)."""
    return key.replace(".", "__")


_groups = {}


def operation_values(group):
    """Native compound operation properties, serialized as numeric arrays."""
    result={}
    for name in type(group)._prop_names_ - getattr(type(group), '_ui_properties_', frozenset()):
        value=getattr(group,name)
        result[name]=list(_components(value,3 if hasattr(value,'z') else 2)) if hasattr(value,'x') else value
    return result


def row_name(row):
    return 'Row__' + row.id


def restore_operations(group, values, validate, *, size=(512, 512)):
    staged = type(group)()
    current = operation_values(group)
    if 'ISMChunkCount' in current:
        from .storage import output_values
        values = output_values(values, size)
    if set(values) - set(current):
        raise ValueError('unknown operation properties')
    for name, value in {**current, **values}.items():
        old=getattr(staged,name)
        setattr(staged,name,type(old)(*value) if hasattr(old,'x') else value)
    validate(staged)
    for name in current:
        setattr(group, name, getattr(staged, name))


def visible_properties(group, pack, page, *, exclude=(), advanced=True, show_advanced=True):
    if page in ('range', 'output', 'slice', 'custom'):
        result = set(type(group)._prop_names_) - getattr(type(group), '_ui_properties_', frozenset())
        return result - set(exclude)
    if page.startswith('__controls:'):
        section = next(s for s in pack.ui_sections if s.id == page.split(':', 1)[1])
        return {type(group)._bindings_[k][0] for k in section.controls if k in type(group)._bindings_}
    result = set()
    for key, definition in pack.params.items():
        if definition.page == page and key not in exclude and (advanced or not definition.advanced):
            binding = type(group)._bindings_.get(key)
            if binding:
                result.add(binding[0])
    return result


def params_group(pack, page=None):
    """One reusable property schema per page; curves are native editor properties."""
    pages = group_pages(pack, page)
    cache_key = (pack.id, pages)
    cached = _groups.get(cache_key)
    if cached and cached[0] == pack.fingerprint:
        bind_properties(cached[1], pack)
        return cached[1]
    annotations = {"ShowAdvanced": bool}
    namespace = {"ShowAdvanced": (False, {"Category": f"WG_{pack.id}_controls"}), "_autosave_": False}
    types = {"float": float, "int": int, "bool": bool, "curve": unreal.RuntimeFloatCurve, "str": str}
    rows = {key: row for row in pack.ui_rows for key in row.keys}
    bindings, aliases = {}, {}
    for key, d in pack.params.items():
        if page is not None and d.page not in pages:
            continue
        meta = {"Category": f"WG_{pack.id}_{d.page}"}
        if d.min is not None and d.type != "bool":
            meta["ClampMin"] = d.min
        if d.max is not None and d.type != "bool":
            meta["ClampMax"] = d.max
        meta['DisplayName'] = d.label.key
        meta['ToolTip'] = d.tooltip.key
        if d.advanced:
            meta.update(EditCondition="ShowAdvanced", EditConditionHides=True)
        if d.enabled_param:
            gate = prop_name(d.enabled_param)
            meta.update(EditCondition=f'ShowAdvanced && {gate}' if d.advanced else gate,
                        EditConditionHides=True)
        row = rows.get(key)
        if row:
            attr = row_name(row)
            index = row.keys.index(key)
            bindings[key] = (attr, index)
            aliases[prop_name(key)] = (attr, index, int if d.type == 'int' else float)
            if index:
                continue
            definitions = [pack.params[k] for k in row.keys]
            # Component-specific bounds are normalized in the callback. A shared
            # native clamp is safe only when every component has the same bound.
            for name, values in (('ClampMin', [v.min for v in definitions]),
                                 ('ClampMax', [v.max for v in definitions])):
                meta.pop(name, None)
                if len(set(values)) == 1 and values[0] is not None:
                    meta[name] = values[0]
            integer_row = all(v.type == 'int' for v in definitions)
            kind = unreal.IntPoint if integer_row else (
                unreal.Vector2D if len(row.keys) == 2 else unreal.Vector)
            if integer_row and len(row.keys) != 2:
                kind = unreal.IntVector
            annotations[attr] = kind
            namespace[attr] = (kind(*(v.default for v in definitions)), meta)
            meta['DisplayName'] = row.label.key
            meta['ToolTip'] = row.label.key + '.tooltip'
            continue
        attr = prop_name(key)
        bindings[key] = (attr, None)
        annotations[attr] = types[d.type]
        default = d.default
        if d.type == 'curve':
            default = unreal.RuntimeFloatCurve()
            default.import_text(ue_text_from_points(d.default))
        namespace[attr] = (default, meta)
    namespace['_bindings_'], namespace['_aliases_'] = bindings, aliases
    namespace["__annotations__"] = annotations
    namespace["__module__"] = __name__
    cls = type(f"WGParams_{pack.id}", (_ScalarAliases, mineprep.PropertyGroup), namespace)
    bind_properties(cls, pack)
    _groups[cache_key] = (pack.fingerprint, cls)
    return cls


def read_params(props, pack, *, curves=True):
    """{key: value} for every UI-editable parameter (floats rounded from UE's float32)."""
    values = {}
    for key, d in pack.params.items():
        if key not in type(props)._bindings_:
            continue
        if d.type == 'curve':
            if not curves:
                continue
            text = getattr(props, prop_name(key)).export_text()
            points = normalize_points(points_from_ue_text(text))
            original = getattr(props, '_curve_original', {}).get(key, d.default)
            if text == getattr(props, '_curve_text', {}).get(key):
                points = original
            values[key] = points
        else:
            value = getattr(props, prop_name(key))
            values[key] = float(f"{value:.7g}") if d.type == "float" else value
    return values


def write_params(props, pack, values):
    for key, value in values.items():
        d = pack.params.get(key)
        if d is not None and key in type(props)._bindings_:
            if d.type == 'curve':
                curve = unreal.RuntimeFloatCurve()
                curve.import_text(ue_text_from_points(value))
                props._curve_original = {**getattr(props, '_curve_original', {}), key: normalize_points(value)}
                value = curve
            setattr(props, prop_name(key), value)
            if d.type == 'curve':
                props._curve_text = {**getattr(props, '_curve_text', {}),
                                     key: getattr(props, prop_name(key)).export_text()}


def normalize_group(group, pack=None):
    """Clamp components separately; reject nonfinite values without coercing ints."""
    if pack is None:
        values = operation_values(group)
        for name,value in values.items():
            parts=value if isinstance(value,list) else [value]
            if any(isinstance(v,float) and not math.isfinite(v) for v in parts):
                raise ValueError(f'{name}: value must be finite')
        for name in ('Size','Budgets'):
            if name in values:
                old=getattr(group,name)
                setattr(group,name,type(old)(*(max(1,int(v)) for v in values[name])))
        if 'Workers' in values: group.Workers=max(1,min(group.Workers,16))
        if 'CellStep' in values and values['CellStep'] not in (1,2,4):
            raise ValueError('CellStep must be 1, 2 or 4')
        if 'ISMChunkCount' in values: group.ISMChunkCount=max(1,group.ISMChunkCount)
        if 'GPUTypeGroupCount' in values: group.GPUTypeGroupCount=max(1,group.GPUTypeGroupCount)
        return operation_values(group)
    values = read_params(group, pack, curves=False)
    for key, value in values.items():
        d = pack.params[key]
        if d.type not in ('int', 'float'):
            continue
        if not math.isfinite(value):
            raise ValueError(f'{key}: value must be finite')
        if d.min is not None:
            value = max(d.min, value)
        if d.max is not None:
            value = min(d.max, value)
        setattr(group, prop_name(key), int(value) if d.type == 'int' else value)
    return read_params(group, pack, curves=False)


def overrides(ui_values, baseline, pack):
    """Only keys whose UI value differs from the preset baseline (float32-tolerant)."""
    result = {}
    for key, value in ui_values.items():
        base = baseline[key]
        if pack.params[key].type == "float":
            if abs(value - base) <= 1e-6 * max(1.0, abs(base)):
                continue
        elif pack.params[key].type == 'curve' and normalize_points(value) == normalize_points(base):
            continue
        elif value == base:
            continue
        result[key] = value
    return result


__all__ = ["WorldRange", "WorldOutput", "params_group", "read_params", "write_params",
           "overrides", "prop_name"]
