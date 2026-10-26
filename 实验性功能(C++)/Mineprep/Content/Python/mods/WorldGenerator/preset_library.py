"""Independent parameter recipes. No UE objects, executable content or Pack writes."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from . import storage
from .core.pack import load_pack, ParamDef
from .core.presets import section_keys
from .core.spec import WorldSpec, _unique_object
from .ui_model import page_id
from .naming import short_names

VERSION = 1
_ID = re.compile(r'[a-z][a-z0-9_]*\Z')
_FIELDS = {'version', 'id', 'name', 'pack', 'section', 'params', 'definitions'}


def preset_ref(value):
    if not isinstance(value, str):
        raise ValueError('preset reference must be text')
    source, ident = value.split(':', 1) if ':' in value else ('pack', value)
    if source not in ('pack', 'library') or not _ID.fullmatch(ident):
        raise ValueError(f'invalid preset reference: {value!r}')
    return f'{source}:{ident}'


def _name(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('预设名称不能为空 / Preset name must not be empty')
    return value.strip()


def _read(path):
    return _validate(json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=_unique_object))


def _validate(raw):
    if not isinstance(raw, dict) or set(raw) != _FIELDS or type(raw['version']) is not int or raw['version'] != VERSION:
        raise ValueError('unsupported preset-library JSON format')
    for key in ('id', 'pack'):
        if not isinstance(raw[key], str) or not _ID.fullmatch(raw[key]):
            raise ValueError(f'invalid preset {key}')
    if raw['pack'].startswith('wg_draft_'):
        raise ValueError('preset must belong to a stable content pack')
    section = raw['section']
    if section is not None and (not isinstance(section,str) or not _ID.fullmatch(section)
                                or section in ('blocks','output')):
        raise ValueError('invalid generation section')
    section = page_id(section) if section else None
    values, definitions = raw['params'], raw['definitions']
    if not isinstance(values,dict) or not isinstance(definitions,dict) or set(values) != set(definitions):
        raise ValueError('preset parameters and definitions must have matching keys')
    WorldSpec(raw['pack'], params=values)  # key syntax, finite JSON values
    normalized, schema = {}, {}
    for key,value in values.items():
        definition = definitions[key]
        if (not isinstance(definition,dict) or set(definition) != {'type','page'}
                or definition['type'] not in ('bool','int','float','curve','str')
                or not isinstance(definition['page'],str) or not _ID.fullmatch(definition['page'])):
            raise ValueError(f'invalid definition for {key}')
        page = page_id(definition['page'])
        if page in ('blocks','output') or section is not None and page != section:
            raise ValueError(f'{key} does not belong to preset section {section!r}')
        normalized[key] = ParamDef(key,definition['type'],value).coerce(value)
        schema[key] = dict(type=definition['type'],page=page)
    if section is not None and not values:
        raise ValueError('local preset requires parameters')
    return dict(version=VERSION,id=raw['id'],name=_name(raw['name']),pack=raw['pack'],
                section=section,params=normalized,definitions=schema)


def _digest(record):
    return hashlib.sha256(json.dumps(record,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def _definitions(pack, keys):
    return {k:dict(type=pack.params[k].type,page=page_id(pack.params[k].page, pack)) for k in keys}


class PresetLibrary:
    def __init__(self, root=None, *, pack_id='vanilla'):
        self.root = Path(root) if root is not None else storage.SAVED_DIR / 'presets'
        self.pack_id = pack_id
        self._index_stamp = None

    def stamp(self):
        result = []
        for p in sorted(self.root.glob('*.json')):
            try:
                stat = p.stat()
                result.append((p.name,stat.st_mtime_ns,stat.st_size))
            except OSError:
                continue
        return tuple(result)

    def _index(self):
        stamp = self.stamp()
        if stamp == self._index_stamp:
            return
        rows, counts = [], {}
        for path in sorted(self.root.glob('*.json')):
            try:
                record = _read(path)
                counts[record['id']] = counts.get(record['id'],0)+1
                rows.append((path,record,None))
            except (OSError,ValueError,TypeError) as exc:
                rows.append((path,None,str(exc)))
        self._paths, self._records, self._rows, self._invalid = {}, {}, [], set()
        self._duplicates = {ident for ident,count in counts.items() if count>1}
        for path,record,error in rows:
            if record and record['id'] in self._duplicates:
                error = f"重复预设 ID / Duplicate preset ID: {record['id']}"
            if error:
                # A damaged file has no trustworthy ID. Give its path a deletable handle.
                ident = 'file_'+hashlib.sha256(path.name.encode('utf8')).hexdigest()
                while ident in counts or ident in self._paths:
                    ident += '_'
                record = dict(id=ident,name=path.name)
                self._invalid.add(ident)
            ident = record['id']
            self._paths[ident] = path
            self._records[ident] = record
            self._rows.append((record,error))
        self._index_stamp = stamp

    def scan(self):
        self._index()
        return deepcopy(self._rows)

    def _path(self, ref):
        source,ident = preset_ref(ref).split(':',1)
        if source != 'library':
            raise ValueError('资源包预设只读 / Pack presets are read-only')
        self._index()
        if ident in self._duplicates:
            raise ValueError(f'duplicate preset ID: {ident}')
        if ident not in self._paths:
            raise FileNotFoundError(f'preset not found: {ident}')
        return self._paths[ident]

    def get(self, ref, *, pack=None):
        source,ident = preset_ref(ref).split(':',1)
        if source == 'library':
            path = self._path(ref)
            record = self._records[ident]
            if ident in self._invalid:
                raise ValueError(f'invalid preset file: {path}')
            return deepcopy(record)
        pack = pack or load_pack(self.pack_id)
        if ident not in pack.presets:
            raise ValueError(f'unknown pack preset: {ident}')
        preset = pack.presets[ident]
        name = preset.name[0] if isinstance(preset.name,(tuple,list)) else preset.name
        return _validate(dict(version=VERSION,id=ident,name=name,pack=pack.id,section=preset.section,
                              params=preset.params,definitions=_definitions(pack,preset.params)))

    @staticmethod
    def patch(record, pack, section=None):
        if record['pack'] not in pack.chain:
            raise ValueError(f'预设属于 {record["pack"]}，当前资源包不继承它 / Unrelated content pack')
        if section is None:
            if record['section'] is not None:
                raise ValueError('local preset requires its section')
            keys = tuple(record['params'])
        else:
            section = page_id(section, pack)
            section_keys(pack,section)
            if record['section'] not in (None,section):
                raise ValueError('local preset belongs to another section')
            keys = tuple(k for k,d in record['definitions'].items() if d['page'] == section)
            if not keys:
                raise ValueError('preset has no parameters in this section')
        for key in keys:
            definition = pack.params.get(key)
            if definition is None:
                raise ValueError(f'unknown parameter: {key}')
            expected = record['definitions'][key]
            if definition.type != expected['type'] or page_id(definition.page, pack) != expected['page']:
                raise ValueError(f'parameter definition changed: {key}')
        return {k:pack.params[k].coerce(record['params'][k]) for k in keys}

    def apply(self, spec, ref, section=None, *, pack=None):
        pack = pack or load_pack(spec.pack)
        record = self.get(ref,pack=pack)
        patch = self.patch(record,pack,section)
        values = ({k:d.default for k,d in pack.params.items()} if section is None else pack.resolve(spec).to_dict())
        values.update(patch)
        source,ident = preset_ref(ref).split(':',1)
        base = ident if source == 'pack' and section is None else (spec.preset or pack.default_preset)
        result = spec.replace(preset=base,params=values)
        pack.resolve(result)
        return result

    def entries(self, pack=None, section=None, *, include_all=False):
        pack = pack or load_pack(self.pack_id)
        candidates = [(self.get('pack:'+k,pack=pack),'pack',None) for k in pack.presets]
        candidates += [(r,'library',error) for r,error in self.scan()]
        result = []
        for record,source,error in candidates:
            valid = not error
            own = record.get('section')
            sections = tuple(dict.fromkeys(d['page'] for d in record.get('definitions',{}).values()))
            if not error and section != '*':
                if section is None and own is not None:
                    continue
                if section is not None and (page_id(section, pack) not in sections or own not in (None,page_id(section, pack))):
                    continue
            if not error:
                try:
                    scope = own if section == '*' else section
                    self.patch(record,pack,scope)
                    if scope is None:
                        self.apply(WorldSpec(pack.id),source+':'+record['id'],pack=pack)
                except (OSError,ValueError,TypeError) as exc:
                    error = str(exc)
            if error and not include_all:
                continue
            ref = source+':'+record['id']
            result.append(dict(ref=ref,id=record['id'],name=record['name'],source=source,
                               pack=record.get('pack',''),section=own,sections=sections,
                               compatible=not error,valid=valid,error=error or '',digest=_digest(record),
                               params=deepcopy(record.get('params',{})),
                               path=str(self._path(ref)) if source=='library' else None))
        return result

    def _new_path(self, record, current=None):
        ident = record['id']
        digest = ident[2:] if re.fullmatch(r'p_[0-9a-f]{32}',ident) else hashlib.sha256(ident.encode()).hexdigest()
        occupied = {p.name.casefold():p for p in self.root.glob('*')}
        for name in short_names(record['name'],digest,'.json'):
            other = occupied.get(name.casefold())
            if other is None or other == current:
                return self.root/name
        raise FileExistsError('readable preset filename is occupied')

    def _create(self, record, path=None):
        self._index()
        if path is None and (record['id'] in self._paths or record['id'] in self._duplicates):
            raise ValueError('duplicate preset ID')
        path = path or self._new_path(record)
        temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
        try:
            storage.write_json(temporary,record)
            # Windows rename is exclusive; POSIX rename replaces, so use a hard link there.
            if os.name == 'nt':
                os.rename(temporary,path)
            else:
                os.link(temporary,path)
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def _snapshot(self, spec, name, section=None, *, origin=None):
        target = load_pack(spec.pack)
        source = load_pack(origin) if origin else target
        if target.id.startswith('wg_draft_') or source.id not in target.chain:
            raise ValueError('preset must belong to a stable original or ancestor pack')
        section = page_id(section, source) if section else None
        keys = section_keys(source,section) if section else tuple(k for k,d in source.params.items()
                                                               if page_id(d.page, source) not in ('blocks','output'))
        values = target.resolve(spec).to_dict()
        record = _validate(dict(version=VERSION,id='p_'+uuid.uuid4().hex,name=name,pack=source.id,
                                section=section,params={k:values[k] for k in keys},
                                definitions=_definitions(source,keys)))
        self.patch(record,target,section)
        source_values = {k:values[k] for k in source.params}
        source.resolve(WorldSpec(source.id,params=source_values))
        return record

    def save(self, spec, name, section=None):
        record = self._snapshot(spec,name,section)
        self._create(record)
        return 'library:'+record['id']

    def update(self, ref, spec):
        path = self._path(ref)
        old = self.get(ref)
        self.patch(old,load_pack(spec.pack),old['section'])
        record = self._snapshot(spec,old['name'],old['section'],origin=old['pack'])
        record['id'] = old['id']
        storage.write_json(path,record)
        return preset_ref(ref)

    def rename(self, ref, name):
        path = self._path(ref)
        record = self.get(ref)
        record['name'] = _name(name)
        target = self._new_path(record,current=path)
        if target == path:
            storage.write_json(path,record)
        else:
            self._create(record,target)
            try:
                path.unlink()
            except OSError:
                target.unlink()
                raise
        return preset_ref(ref)

    def copy(self, ref, name):
        record = self.get(ref)
        record.update(id='p_'+uuid.uuid4().hex, name=_name(name))
        self._create(record)
        return 'library:'+record['id']

    def delete(self, ref):
        self._path(ref).unlink()

    def import_json(self, path):
        record = _read(path)
        names = {r['name'] for r,error in self.scan() if not error}
        base = record['name']
        index = 2
        while record['name'] in names:
            record['name'] = f'{base} ({index})'
            index += 1
        record['id'] = 'p_'+uuid.uuid4().hex
        self._create(record)
        return 'library:'+record['id']

    def export_json(self, ref, path, overwrite=False):
        record = self.get(ref)
        path = Path(path)
        if path.exists() and not overwrite:
            raise FileExistsError(f'文件已存在 / File exists: {path}')
        storage.write_json(path,record)
        return str(path)
