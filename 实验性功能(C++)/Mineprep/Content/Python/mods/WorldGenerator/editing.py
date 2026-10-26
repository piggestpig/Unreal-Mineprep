"""Pure Python Pack drafts: immutable preview revisions and staged user-pack saves.

Retain source JSON rather than reverse engineering parsed rule noise thresholds.
No Unreal imports, new generation algorithm or WorldSpec wire format.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid

from .core.blocks import builtin_block, parse_block
from .core.pack import _read_json, find_pack, load_pack, pack_roots, register_pack_root
from .core.spec import WorldSpec, canonical_value
from .core.data import Region
from .core.surface import block_name
from .storage import SAVED_DIR as WORKSPACE, write_json as _json

_ID = re.compile(r'^[a-z][a-z0-9_]*$')


def _remove(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    if path == root or root not in path.parents:
        raise ValueError('cleanup target must be inside its workspace')
    if path.exists():
        shutil.rmtree(path)


def _digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()


def normalize_source(text, directory):
    """Canonical source mapping; never import a resource while typing."""
    value = str(text).strip()
    if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    copied = re.fullmatch(r"(?:/Script/Engine\.)?StaticMesh\s*['\"](.*?)['\"]", value)
    if copied:
        value = copied[1]
    if value.startswith('/Game/'):
        if any(c in value for c in "'\"\n\r"):
            raise ValueError('StaticMesh 引用格式无效')
        package, dot, obj = value.rpartition('.')
        if dot:
            if obj != package.rsplit('/', 1)[-1]:
                raise ValueError('StaticMesh 对象名应与包名一致')
            value = package
        return {'mesh': value}
    if value.lower().endswith('.json'):
        path = (Path(directory) / value).resolve()
        if not path.is_file():
            raise ValueError(f'JSON 文件不存在：{path}')
        return {'json': str(path)}
    return {'builtin': block_name(value)}


def _effective(pack, roots):
    data = dict(biomes={}, blocks={}, features={}, surface_overrides=[], water=None)
    for pack_id in pack.chain:
        directory = find_pack(pack_id, roots=roots)
        manifest = _read_json(directory / 'pack.json')
        for path in (directory / 'biomes').glob('*.json'):
            data['biomes'][path.stem] = _read_json(path)
        for name in ('blocks', 'features'):
            path = directory / (name + '.json')
            if path.is_file():
                items = _read_json(path)
                if name == 'blocks':
                    for item in items.values():
                        if 'json' in item['source']:
                            item['source']['json'] = str((directory / item['source']['json']).resolve())
                data[name].update(items)
        for key in ('water', 'surface_overrides'):
            if key in manifest:
                data[key] = manifest[key]
    data['biomes'] = [data['biomes'][b.id] for b in pack.biomes]
    return data


class PackDraft:
    def __init__(self, pack_id='vanilla', *, workspace=None):
        self.workspace = Path(workspace or WORKSPACE).resolve()
        from .migration import upgrade_workspace
        self.upgrade_report = upgrade_workspace(self.workspace, roots=pack_roots())
        self.user_root = self.workspace / 'packs'
        if self.user_root.is_dir():
            register_pack_root(self.user_root)
        self.roots = pack_roots()
        self.pack = load_pack(pack_id, roots=self.roots)
        self.fingerprint = self.pack.fingerprint
        self.data = _effective(self.pack, self.roots)
        self.original = deepcopy(self.data)
        self.session = uuid.uuid4().hex[:12]
        self.revision = 0
        self._last = None
        self._last_geometry = None

    @property
    def dirty(self):
        return self.data != self.original

    def _check_base(self):
        try:
            actual = load_pack(self.pack.id)
        except Exception as exc:
            raise ValueError('资源包已变化，请重新载入草稿') from exc
        if actual.fingerprint != self.fingerprint or any(
                find_pack(name) != find_pack(name, roots=self.roots) for name in self.pack.chain):
            raise ValueError('资源包已变化，请重新载入草稿')

    def block(self, block_id):
        if block_id in self.data['blocks']:
            return self.data['blocks'][block_id]
        definition = self.pack.block_defs.get(block_id) or builtin_block(block_id)
        value = dict(source={definition.source:definition.value},shape=definition.shape,
                     occludes=definition.occludes,merge=definition.merge,
                     offset=list(definition.offset),scale=list(definition.scale))
        if definition.color is not None:
            value['color'] = '#' + ''.join(f'{c:02X}' for c in definition.color)
        if definition.material:
            value['material'] = dict(definition.material)
        return value

    def input_block(self, text, *, shape='cube', definition=None):
        """Resolve a candidate to one shared ID; custom models default to no merge."""
        text = str(text).strip()
        if text in self.data['blocks']:
            return text
        source = normalize_source(text, self.pack.root)
        shorthand = 'builtin' in source and definition is None and shape == 'cube'
        builtin = builtin_block(source['builtin']) if shorthand else None
        item = deepcopy(definition) if definition is not None else dict(
            shape=shape, occludes=shape == 'cube', merge='xz' if shorthand else 'none')
        item['source'] = source
        parse_block('candidate', item, self.pack.root)
        for name, known in self.data['blocks'].items():
            canonical = deepcopy(known)
            if 'mesh' in canonical['source']:
                canonical['source'] = normalize_source(canonical['source']['mesh'], self.pack.root)
            # Optional defaults have the same meaning as explicit defaults.
            if parse_block(name, canonical, self.pack.root).__dict__ | {'id': ''} == \
                    parse_block('candidate', item, self.pack.root).__dict__ | {'id': ''}:
                return name
        if shorthand:
            return builtin.id
        name = 'custom_' + _digest(source)[:8]
        base, suffix = name, 2
        while name in self.data['blocks']:
            name, suffix = f'{base}_{suffix}', suffix + 1
        self.data['blocks'][name] = item
        return name

    def _write_content(self, directory, manifest, data=None):
        data = self.data if data is None else data
        manifest['format_version'] = 2
        base = (_effective(load_pack(manifest['extends'], roots=self.roots), self.roots)
                if manifest.get('extends') else dict(biomes=[], blocks={}, features={}))
        known = {b['id']: b for b in base['biomes']}
        manifest['biomes'] = [b['id'] for b in data['biomes']]
        for key in ('surface_overrides', 'water'):
            if data[key] != base.get(key):
                manifest[key] = data[key]
            else:
                manifest.pop(key, None)
        for b in data['biomes']:
            if not isinstance(b.get('id'), str) or not _ID.fullmatch(b['id']):
                raise ValueError('群系 ID 必须是小写字母开头的字母、数字、下划线')
            if b != known.get(b['id']):
                _json(directory / 'biomes' / (b['id'] + '.json'), b)
        for key in ('blocks', 'features'):
            changes = {k: v for k, v in data[key].items() if v != base[key].get(k)}
            path = directory / (key + '.json')
            if changes:
                _json(path, changes)
            else:
                path.unlink(missing_ok=True)
        _json(directory / 'pack.json', manifest)

    def _materialize(self, data=None, *, geometry=False):
        self._check_base()
        data = self.data if data is None else data
        digest = _digest(data)
        previous = self._last_geometry if geometry else self._last
        if previous and previous[0] == digest:
            return previous[1]
        self.revision += 1
        pack_id = f'wg_draft_{self.session}_{self.revision}'
        root = self.workspace / 'drafts'
        directory = root / pack_id
        try:
            self._write_content(directory, dict(id=pack_id, extends=self.pack.id), data)
            register_pack_root(root)
            loaded = load_pack(pack_id)
            self._check_base()
        except Exception:
            _remove(directory, root)
            raise
        if geometry:
            self._last_geometry = (digest, loaded.id)
        else:
            self._last = (digest, loaded.id)
        return loaded.id

    def _geometry_spec(self, preset='', *, seed=42, region=(0, 0, 256, 256), params=None):
        """Panel-only stable generation revision; output colours remain in the full draft."""
        self._check_base()
        data = deepcopy(self.data)
        for name, item in tuple(data['blocks'].items()):
            definition = parse_block(name,item,self.pack.root)
            initial = self.original['blocks'].get(name)
            if initial is None and name in self.pack.block_defs and replace(definition,material=()) == replace(
                    self.pack.block_defs[name],material=(),explicit=True):
                del data['blocks'][name]
                continue
            if initial and 'material' in initial:
                item['material'] = deepcopy(initial['material'])
            else:
                item.pop('material',None)
        original = {b['id']: b for b in self.original['biomes']}
        for biome in data['biomes']:
            initial = original.get(biome['id'], {})
            for field in ('vegetation_tint', 'vegetation_hsv'):
                if field in initial:
                    biome[field] = initial[field]
                else:
                    biome.pop(field, None)
        pack_id = self._materialize(data, geometry=True) if data != self.original else self.pack.id
        result = WorldSpec(pack_id, preset, seed, region if isinstance(region, Region) else Region(*region), params or {})
        load_pack(pack_id).resolve(result)
        return result

    def spec(self, preset='', *, seed=42, region=(0, 0, 256, 256), params=None):
        """Immutable temporary content version + normal WorldSpec parameter overrides."""
        self._check_base()
        pack_id = self._materialize() if self.dirty else self.pack.id
        result = WorldSpec(pack_id, preset, seed, region if isinstance(region, Region) else Region(*region), params or {})
        load_pack(pack_id).resolve(result)
        return result

    def validate(self, preset='', params=None):
        return self.spec(preset, region=(0, 0, 1, 1), params=params)

    def save(self, pack_id, *, name=None, preset='user_default', params=None, preset_name=None, section=None):
        """Publish a new derived pack, or update this managed user pack after validation."""
        if not _ID.fullmatch(pack_id) or not _ID.fullmatch(preset):
            raise ValueError('资源包与预设 ID 必须是小写字母开头的字母、数字、下划线')
        self._check_base()
        target = self.user_root / pack_id
        updating = target.resolve() == self.pack.root and self.pack.root.parent == self.user_root
        if section is not None and (not updating or self.dirty):
            raise ValueError('请先保存用户资源包及资源包规则修改，再另存本板块预设')
        if target.exists() and not updating:
            raise FileExistsError(f'资源包已存在：{pack_id}，请使用新的 ID')
        staging_root = self.workspace / '_staging' / uuid.uuid4().hex
        staged = staging_root / pack_id
        backup = staging_root / 'previous' / pack_id
        published = False
        try:
            if updating:
                shutil.copytree(target, staged, ignore=shutil.ignore_patterns('__pycache__'))
                manifest = _read_json(staged / 'pack.json')
                if section is None:
                    for old in self.original['biomes']:
                        (staged / 'biomes' / (old['id'] + '.json')).unlink(missing_ok=True)
            else:
                manifest = dict(id=pack_id, extends=self.pack.id)
            if section is None:
                manifest.update(name=name if name is not None else manifest.get('name', pack_id))
                manifest['default_preset'] = preset
                self._write_content(staged, manifest)
            values = self.pack.resolve(WorldSpec(self.pack.id, params=params or {})).to_dict() if params is None else params
            if section is None:
                values = {k: v for k, v in values.items() if k not in self.pack.params or
                          canonical_value(v) != canonical_value(self.pack.params[k].default)}
            else:
                from .core.presets import section_keys
                keys = section_keys(self.pack, section)
                resolved = self.pack.resolve(WorldSpec(self.pack.id, params=values)).to_dict()
                values = {k: resolved[k] for k in keys}
            declaration = dict(name=preset_name or preset, params=values)
            if section is not None:
                declaration['section'] = section
            _json(staged / 'presets' / (preset + '.json'), declaration)
            load_pack(pack_id, roots=(str(staging_root), *self.roots)).resolve(WorldSpec(pack_id, preset))
            self._check_base()
            self.user_root.mkdir(parents=True, exist_ok=True)
            if updating:
                backup.parent.mkdir()
                os.replace(target, backup)
            elif target.exists():
                raise FileExistsError(f'资源包已存在：{pack_id}')
            try:
                if updating and load_pack(pack_id, roots=(str(backup.parent), *self.roots)).fingerprint != self.fingerprint:
                    raise ValueError('资源包已变化，请重新载入草稿')
                os.replace(staged, target)
                published = True
            except Exception as exc:
                if backup.exists():
                    try:
                        os.replace(backup, target)
                    except Exception as restore_error:
                        raise RuntimeError(f'保存失败；原资源包保留在 {backup}，自动恢复失败：{restore_error}') from exc
                raise
        finally:
            if published or not backup.exists():
                _remove(staging_root, self.workspace)
        register_pack_root(self.user_root)
        return PackDraft(pack_id, workspace=self.workspace)

    def save_preset(self, preset, params, *, name=None, section=None):
        if not _ID.fullmatch(preset):
            raise ValueError('预设 ID 格式无效')
        if self.pack.root.parent != self.user_root:
            raise ValueError('请先另存为用户资源包，再保存预设')
        path = self.pack.root / 'presets' / (preset + '.json')
        if path.exists():
            raise FileExistsError('预设已存在，请使用新的 ID')
        return self.save(self.pack.id, name=self.pack.name, preset=preset, params=params, preset_name=name, section=section)

    def checkpoint(self, state):
        _json(self.workspace / 'session.json', dict(format_version=2, pack=self.pack.id, fingerprint=self.fingerprint,
                                                   data=self.data, state=state))

    def needs_recovery(self, state):
        """Keep only additional session edits behind the explicit recovery prompt.

        Preferences already restore committed parameters and operation settings.
        Compare their effective values, not a changed code fingerprint or curve
        export formatting. An unreadable snapshot remains protected from writes.
        """
        path = self.workspace / 'session.json'
        if not path.is_file():
            return False
        try:
            saved = _read_json(path)
            if saved['pack'] != self.pack.id or _digest(saved['data']) != _digest(self.data):
                return True
            previous = saved['state']
            if not isinstance(previous, dict):
                return True
            if previous.get('curves_pending') or previous.get('input_errors'):
                return True
            params = self.pack.resolve(WorldSpec(self.pack.id, previous['preset'],
                                                 params=previous['params'])).to_dict()
            if _digest(params) != _digest(state['params']):
                return True
            if 'custom' in previous:
                from .storage import custom_values
                previous = {**previous, 'custom': custom_values(previous['custom'])}
                state = {**state, 'custom': custom_values(state['custom'])}
            # Optional keys allow older/script checkpoints to remain readable.
            return any(_digest(previous[key]) != _digest(state[key])
                       for key in ('preset', 'page', 'view', 'range', 'output', 'custom', 'masks',
                                   'backend', 'merge', 'execution', 'global_mark', 'section_marks')
                       if key in previous)
        except (OSError, ValueError, TypeError, KeyError):
            return True

    @classmethod
    def restore(cls, *, workspace=None):
        workspace = Path(workspace or WORKSPACE)
        from .migration import upgrade_workspace
        upgrade_workspace(workspace, roots=pack_roots())
        saved = _read_json(workspace / 'session.json')
        result = cls(saved['pack'], workspace=workspace)
        if result.fingerprint != saved['fingerprint']:
            raise ValueError('上次草稿的基础资源包已变化，请重新载入')
        result.data = saved['data']
        return result, saved['state']


def fit_water_bounds(pack, values, region):
    """Panel edits keep a fixed water domain until the output no longer fits.

    Return committed parameter changes, so saving/cropping the resulting spec
    retains the same plan. Scripted specs keep their explicit fixed bounds.
    """
    keys = ('hydrology.origin_x', 'hydrology.origin_z', 'hydrology.size')
    if 'water' not in (pack.planners or {}) or not all(k in values for k in keys):
        return {}
    if not values['water.generate'] or not values['hydrology.enabled'] or values['terrain.flat']:
        return {}
    x0, z0, size = (values[k] for k in keys)
    if x0 % 16 or z0 % 16 or size % 16:
        return {}  # Leave invalid manual planning inputs to the planner's error.
    spans = ((region.x0, region.width), (region.z0, region.depth))
    size = max(size, *(((start + length + 15) // 16 - start // 16) * 16
                       for start, length in spans))
    origins = []
    for old, (start, length) in zip((x0, z0), spans):
        if old <= start and start + length <= old + size:
            origins.append(old)
        else:
            centered = (start + (length - size) // 2) // 16 * 16
            origins.append(max(centered, (start + length - size + 15) // 16 * 16))
    result = dict(zip(keys, (*origins, size)))
    return {k: pack.params[k].coerce(v) for k, v in result.items() if v != values[k]}


class PreviewSchedule:
    """Latest revision only; cancellation never schedules another request by itself."""
    def __init__(self):
        self.revision = 0
        self.enabled = True
        self.due = None
        self.curves_due = None

    def changed(self, now, *, curves_pending=False):
        self.revision += 1
        self.due = now + .3 if self.enabled and not curves_pending else None
        self.curves_due = now + .3 if curves_pending else None

    def ready(self, now, *, busy=False, cells=0):
        return not busy and cells <= 512 ** 2 and self.due is not None and now >= self.due

    def cancel(self):
        self.due = None
        self.curves_due = None

    def current(self, revision):
        return self.revision == revision
