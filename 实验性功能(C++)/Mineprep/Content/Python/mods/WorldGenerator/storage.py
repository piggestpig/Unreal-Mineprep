"""Shared mod-local workspace and lightweight UI preferences; no Unreal imports."""
import json
import math
import os
from pathlib import Path
import uuid
import tempfile
import re

SAVED_DIR = Path(__file__).resolve().parent / 'Saved'


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _ui_values(data):
    if not isinstance(data, dict):
        data = {}
    ratio = data.get('ratio', .5)
    if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not math.isfinite(ratio):
        ratio = .5
    hidden = data.get('preview_hidden', False)
    return dict(ratio=max(.1, min(float(ratio), .9)),
                preview_hidden=hidden if isinstance(hidden, bool) else False)


def load_ui(path=None):
    try:
        data = json.loads(Path(path or SAVED_DIR / 'ui.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        data = {}
    return _ui_values(data)


def save_ui(data, path=None):
    write_json(path or SAVED_DIR / 'ui.json', _ui_values(data))


def output_values(values, size=(512, 512)):
    """Read legacy chunk size as a count; never rewrite its source snapshot."""
    from .core.data import require_int
    result = dict(values)
    if 'RenderTileSize' in result or 'ISMChunkCount' in result:
        if not isinstance(size, (list, tuple)) or len(size) != 2:
            raise ValueError('output migration needs two region dimensions')
        for name, value in zip(('width', 'depth'), size):
            require_int(name, value, 1, 2**31 - 1)
    if 'RenderTileSize' in result:
        old = result.pop('RenderTileSize')
        if 'ISMChunkCount' not in result:
            require_int('RenderTileSize', old, 0, 2**31 - 1)
            width, depth = size
            result['ISMChunkCount'] = (((width + old - 1) // old) * ((depth + old - 1) // old)
                                       if old else 1)
    if 'ISMChunkCount' in result:
        require_int('ISMChunkCount', result['ISMChunkCount'], 1, size[0] * size[1])
    if 'GPUTypeGroupCount' in result:
        require_int('GPUTypeGroupCount', result['GPUTypeGroupCount'], 1, 2**31 - 1)
    return result


def custom_values(values):
    """Validate operation metadata without reading an external input file."""
    from .core.data import Region
    from .core.spec import HeightmapInput, height_range
    defaults = dict(Enabled=False, Path='', SourceKind='file', AssetPath='', Mode='faithful', InputRange=[0., 1.],
                    AutoOutput=True, OutputRange=[0., 192.], Origin=[0, 0], Size=[512, 512])
    if not isinstance(values, dict) or set(values) - set(defaults):
        raise ValueError('unknown custom heightmap preferences')
    result = {**defaults, **values}
    if type(result['Enabled']) is not bool or type(result['AutoOutput']) is not bool:
        raise ValueError('heightmap switches must be true/false')
    if not isinstance(result['Path'], str) or result['Mode'] not in ('faithful', 'add'):
        raise ValueError('invalid heightmap path/mode')
    if result['SourceKind'] not in ('file', 'asset') or not isinstance(result['AssetPath'], str):
        raise ValueError('invalid heightmap source')
    if result['SourceKind'] == 'asset' and not result['AssetPath'].startswith('/'):
        raise ValueError('select a heightmap texture asset')
    height_range(result['InputRange'], 'input_range', increasing=True)
    height_range(result['OutputRange'], 'output_range')
    region = Region(*result['Origin'], *result['Size'])
    if result['Path']:
        HeightmapInput(result['Path'], region, result['Mode'], result['InputRange'],
                       None if result['AutoOutput'] else result['OutputRange'])
    elif result['Enabled'] and result['SourceKind'] == 'file':
        raise ValueError('select a heightmap file before enabling it')
    return result


def mask_values(values):
    from .core.spec import MaskInput
    from .core.data import Region
    defaults = dict(Enabled=False, Path='', SourceKind='file', AssetPath='', Origin=[0,0], Size=[512,512])
    if not isinstance(values, dict) or set(values)-set(defaults):
        raise ValueError('invalid mask preferences')
    result = {**defaults, **values}
    if (type(result['Enabled']) is not bool or not isinstance(result['Path'],str)
            or result['SourceKind'] not in ('file','asset') or not isinstance(result['AssetPath'],str)):
        raise ValueError('invalid mask source')
    region = Region(*result['Origin'], *result['Size'])
    if result['Path']:
        MaskInput(result['Path'], region)
    if result['Enabled'] and not (result['Path'] if result['SourceKind']=='file' else result['AssetPath'].startswith('/')):
        raise ValueError('请选择遮罩文件或纹理 / Select a mask file or texture')
    return result


def preferences(data):
    """Validate before publishing; canonical MC property names never swap axes."""
    from .ui_model import page_id
    from .core.data import Region, require_int
    if not isinstance(data, dict) or data.get('version', 2) != 2:
        raise ValueError('preferences must be an object')
    ranges = dict(Seed=42, Origin=[0,0], Size=[512,512])
    output = dict(OutputName='World', Offset=[0.,0.,0.], ISMChunkCount=1, GPUTypeGroupCount=1, Workers=4, Budgets=[2147483647,2000000],
                  BCTEnabled=True, BCTCellSize=4, BCTColorMode='rgb', BCTPower=1.)
    for label, defaults in (('range', ranges), ('output', output)):
        incoming = data.get(label, {})
        if not isinstance(incoming, dict):
            raise ValueError(f'{label} preferences must be an object')
        if label == 'output':
            incoming = output_values(incoming, ranges['Size'])
        if set(incoming)-set(defaults): raise ValueError(f'unknown {label} preferences')
        defaults.update(incoming)
    require_int('Seed', ranges['Seed'], -2**63, 2**63 - 1)
    for name,value,count in (('Origin',ranges['Origin'],2),('Size',ranges['Size'],2),('Offset',output['Offset'],3),('Budgets',output['Budgets'],2)):
        if not isinstance(value,(list,tuple)) or len(value)!=count:
            raise ValueError(f'{name}: expected {count} components')
    Region(*ranges['Origin'], *ranges['Size'])
    for value in output['Budgets']: require_int('Budgets',value,1,2**31-1)
    for key, lo, hi in (('ISMChunkCount', 1, ranges['Size'][0] * ranges['Size'][1]), ('Workers', 1, 16)):
        require_int(key, output[key], lo, hi)
    require_int('BCTCellSize', output['BCTCellSize'], 1, 16)
    if type(output['BCTEnabled']) is not bool:
        raise ValueError('BCTEnabled must be true/false')
    if output['BCTColorMode'] not in ('rgb', 'hsv'):
        raise ValueError("BCTColorMode must be 'rgb' or 'hsv'")
    if (isinstance(output['BCTPower'], bool) or not isinstance(output['BCTPower'], (int, float))
            or not math.isfinite(output['BCTPower']) or output['BCTPower'] < 0):
        raise ValueError('BCTPower must be a finite nonnegative number')
    if not isinstance(output['OutputName'], str):
        raise ValueError('OutputName must be text')
    for value in output['Offset']:
        key = 'Offset'
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'{key} must be finite')
    result = dict(version=2, content_format=2, range=ranges, output=output,
                  custom=custom_values(data.get('custom', {})))
    masks = data.get('masks', {})
    if not isinstance(masks, dict) or set(masks)-{'vegetation','clearance'}:
        raise ValueError('invalid masks preferences')
    result['masks'] = {kind: mask_values(masks.get(kind, {})) for kind in ('vegetation','clearance')}
    for key, default, choices in (('backend', 'pcg', ('pcg', 'ism', 'niagara')),
                                  ('merge', 'cuboids', ('none', 'runs', 'rectangles', 'cuboids')),
                                  ('custom_image_type', 'heightmap', ('heightmap', 'vegetation', 'clearance')),
                                  ('execution', 'processes', ('serial', 'threads', 'processes'))):
        value = data.get(key, default)
        if value not in choices:
            raise ValueError(f'invalid {key} preference')
        result[key] = value
    for key, default in (('pack', 'vanilla'), ('preset', ''), ('page', 'world'), ('view', 'landscape')):
        value = data.get(key, default)
        if not isinstance(value, str) or (value and not re.fullmatch('[a-z][a-z0-9_]*', value)):
            raise ValueError(f'invalid {key} preference')
        result[key] = page_id(value) if key == 'page' else value
    for key in ('advanced', 'folds', 'rows'):
        value = data.get(key, {})
        if not isinstance(value, dict) or any(not isinstance(k, str) or type(v) is not bool for k, v in value.items()):
            raise ValueError(f'{key} preferences must be boolean maps')
        result[key] = dict(value)
    if data.get('selection'):
        from .core.spec import WorldSpec
        from .preset_library import preset_ref
        selection = data['selection']
        if not isinstance(selection,dict) or set(selection) != {'params','global_mark','section_marks'}:
            raise ValueError('invalid preset selection state')
        WorldSpec(result['pack'],params=selection['params'])
        marks = selection['section_marks']
        if not isinstance(marks,dict):
            raise ValueError('invalid section selections')
        for mark in (selection['global_mark'],*marks.values()):
            if not isinstance(mark,dict) or 'id' not in mark or 'values' not in mark:
                raise ValueError('invalid preset selection mark')
            if mark['id']:
                preset_ref(mark['id'])
            WorldSpec(result['pack'],params=mark['values'])
            if any(not isinstance(mark.get(key,''),str) for key in ('name','digest')):
                raise ValueError('invalid preset selection metadata')
        result['selection'] = selection
    return result


def load_preferences(path=None):
    try:
        return preferences(json.loads(Path(path or SAVED_DIR / 'preferences.json').read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError):
        return preferences({})


def save_preferences(data, path=None):
    write_json(path or SAVED_DIR / 'preferences.json', preferences(data))


def _group_data(group):
    """Range/output snapshots use the public PropertyGroup JSON representation."""
    result = {}
    for name in _saved_properties(group):
        value = getattr(group, name)
        result[name] = value.export_text() if hasattr(value, 'export_text') else value
    return result


def _saved_properties(group):
    return set(type(group)._prop_names_) - getattr(type(group), '_ui_properties_', frozenset())


def _staged_group(group, data, path, validate):
    staged = type(group)()
    names = _saved_properties(group)
    for name in ('ISMChunkCount', 'GPUTypeGroupCount'):
        if name in names and name in data:
            from .core.data import require_int
            require_int(name, data[name], 1, 2**31 - 1)
    if set(data) == names:
        staged.load(str(path))
        # load() logs individual conversion failures. Roundtrip comparison stops
        # an invalid field silently reverting to its default and being accepted.
        if _group_data(staged) != data:
            raise ValueError('property snapshot did not roundtrip completely')
    else:
        raise ValueError('property snapshot fields are incomplete or unknown')
    validate(staged)
    return staged


def save_group(group, path, validate):
    """Public group.save() to a verified temporary file, then atomic publication."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        validate(group)
        group.save(str(temporary))
        data = json.loads(temporary.read_text(encoding='utf-8'))
        ui_fields = getattr(type(group), '_ui_properties_', frozenset())
        if ui_fields:
            # Public save includes reflected UI state. Strip only that known
            # state before validating and publishing the operation snapshot.
            data = {k: v for k, v in data.items() if k not in ui_fields}
            write_json(temporary, data)
        if data != _group_data(group):
            raise ValueError('property snapshot is incomplete')
        _staged_group(group, data, temporary, validate)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_group(group, path, validate, *, size=(512, 512)):
    """Invalid/partial snapshots never change the live group or source file."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return False
        names = type(group)._prop_names_
        if 'ISMChunkCount' in names and ('RenderTileSize' in data or
                ('GPUTypeGroupCount' in names and 'GPUTypeGroupCount' not in data)):
            data = output_values(data, size)
            if 'GPUTypeGroupCount' in names:
                data.setdefault('GPUTypeGroupCount', 1)
            with tempfile.TemporaryDirectory() as directory:
                converted = Path(directory) / 'output.json'
                write_json(converted, data)
                staged = _staged_group(group, data, converted, validate)
        else:
            staged = _staged_group(group, data, path, validate)
    except (OSError, ValueError, TypeError, OverflowError):
        return False
    for name in _saved_properties(group):
        setattr(group, name, getattr(staged, name))
    return True
