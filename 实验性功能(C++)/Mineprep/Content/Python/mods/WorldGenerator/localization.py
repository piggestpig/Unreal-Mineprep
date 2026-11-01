"""Pack text data and the small, lazy bridge to Mineprep's public i18n API.

TextKey is plain immutable data, safe in offline Packs. Only localized() and
bind_properties() use Unreal, on the editor thread. Numeric generation ignores
catalog files; callers refresh catalogs explicitly when loading or editing text.
"""
from dataclasses import dataclass
from collections import OrderedDict
from pathlib import Path
import json


def namespace(pack_id):
    return f'WorldGenerator.pack.{pack_id}'


def read_entries(directory, pack_id):
    path = Path(directory) / 'i18n.json'
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    entries = data.get(namespace(pack_id)) if isinstance(data, dict) else None
    if not isinstance(entries, dict):
        raise ValueError(f'{path}: expected {namespace(pack_id)!r} text catalog')
    for key, record in entries.items():
        native = record.get('_native', 'zh') if isinstance(record, dict) else None
        if (not isinstance(key, str) or not isinstance(native, str) or not native or native.startswith('_')
                or not record.get(native) or not isinstance(record[native], str)
                or any(not isinstance(v, str) for k, v in record.items() if not k.startswith('_'))):
            raise ValueError(f'{path}: {key!r} needs its native source text')
    return entries


def write_entries(directory, pack_id, entries):
    from .storage import write_json
    write_json(Path(directory) / 'i18n.json', {namespace(pack_id): entries})


def record_text(record, language=None, fallback=''):
    native = record.get('_native', 'zh')
    language = language or native
    while language:
        if record.get(language):
            return record[language]
        language = language.rpartition('-')[0]
    return record.get(native, fallback)


def literal(value):
    """A user name has one source language; missing translations use that source."""
    return {'_native': 'en', 'en': str(value)}


@dataclass(frozen=True)
class TextKey:
    owner: str
    sources: tuple
    key: str
    fallback: str = ''

    def __str__(self):
        return source_text(self)


class Catalog:
    def __init__(self, owner, sources):
        self.owner, self.sources = owner, sources
        self.entries, self.aliases = {}, {}
        self.stamp = None
        self._translator = None
        self.refresh()

    def refresh(self):
        stamp = []
        for ident, directory in self.sources:
            path = Path(directory) / 'i18n.json'
            stat = path.stat() if path.exists() else None
            stamp.append((str(path), stat.st_mtime_ns, stat.st_size) if stat else (str(path),))
        stamp = tuple(stamp)
        if stamp == self.stamp:
            return False
        entries = {}
        for ident, directory in self.sources:
            entries.update(read_entries(directory, ident))
        self.entries, self.stamp = entries, stamp
        self.aliases.clear()
        self._translator = None
        return True

    def translator(self):
        if self._translator is None:
            from mineprep import Internationalization
            self._translator = Internationalization.from_data(
                {**self.entries, **self.aliases}, namespace=namespace(self.owner))
        return self._translator


_catalogs = OrderedDict()


def catalog(reference):
    identity = reference.owner, reference.sources
    if identity not in _catalogs:
        _catalogs[identity] = Catalog(*identity)
        if len(_catalogs) > 32:
            _catalogs.popitem(last=False)
    _catalogs.move_to_end(identity)
    return _catalogs[identity]


def source_text(value, language=None):
    if not isinstance(value, TextKey):
        return str(value)
    return record_text(catalog(value).entries.get(value.key, {}), language, value.fallback)


def current_language():
    import unreal
    return unreal.InternationalizationLibrary.get_current_language()


def localized(value):
    if not isinstance(value, TextKey):
        return str(value)
    return catalog(value).translator()(value.fallback or value.key, key=value.key)


def plain(value):
    """JSON-friendly display metadata, without importing Unreal or Mineprep."""
    if isinstance(value, TextKey):
        return source_text(value)
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return tuple(plain(v) for v in value)
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value


def property_entries(pack):
    """Pure-data projection; native categories retain the stable host pack ID."""
    texts = catalog(pack.name)
    aliases = {}

    def add(target, reference, fallback=' '):
        aliases['params.' + target] = texts.entries.get(reference.key, literal(reference.fallback or fallback))

    for key, definition in pack.params.items():
        attr = key.replace('.', '__')
        add(attr, definition.label, key)
        add(attr + '.tooltip', definition.tooltip)
    for row in pack.ui_rows:
        attr = 'Row__' + row.id
        add(attr, row.label, row.id)
        record = {}
        for language in ('zh', 'en', 'zh-Hant', 'zh-Hant-HK'):
            hints = []
            for axis, component, key in zip(('X', 'Y', 'Z'), row.components, row.keys):
                d = pack.params[key]
                hints.append(f'{axis}: {source_text(component, language)} [{d.min}, {d.max}] '
                             f'{source_text(d.tooltip, language)}'.rstrip())
            record[language] = '\n'.join(hints)
        aliases[f'params.{attr}.tooltip'] = record
    for page, reference in pack.pages.items():
        add(f'category.WG_{pack.id}_{page}', reference, page)
    shared = json.loads((Path(__file__).parent / 'i18n.json').read_text(encoding='utf-8-sig'))['WorldGenerator']
    aliases['params.ShowAdvanced'] = shared['controls.advanced']
    aliases[f'params.category.WG_{pack.id}_controls'] = shared['controls.parameters']
    return aliases


def bind_properties(cls, pack):
    """Bind a native property class through Mineprep's existing batch API."""
    texts = catalog(pack.name)
    if not texts.aliases:
        texts.aliases = property_entries(pack)
        texts._translator = None
    cls.localize(texts.translator().params, tooltip='en')
