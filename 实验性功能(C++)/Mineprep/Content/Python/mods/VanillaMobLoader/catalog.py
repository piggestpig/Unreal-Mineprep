"""CEM catalog adapter. Format/source: Ewan Howell's CEM Template Loader.

https://github.com/ewanhowell5195/blockbenchPlugins/tree/main/cem_template_loader
Independent Mineprep implementation; downloaded data retains its upstream rights.
"""
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import json


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in ('br', 'p', 'div'):
            self.parts.append('\n')


def plain(value):
    parser = _Text()
    parser.feed(str(value or ''))
    return unescape(''.join(parser.parts)).strip()


def display(entry):
    return str(entry.get('name') or entry.get('file') or entry['id']).replace('_', ' ')


@dataclass(frozen=True)
class Entry:
    key: str
    id: str
    name: str
    category: str
    group: str
    parent_key: str
    parent_name: str
    model: str
    filename: str
    description: str
    textureless: bool


class Catalog:
    def __init__(self, data):
        if not isinstance(data, dict) or not isinstance(data.get('categories'), list):
            raise ValueError('Invalid CEM catalog')
        self.data = data
        self.version = str(data.get('version', '?'))
        self.categories = []
        self.entries = []
        self.by_key = {}
        self.variants = {}
        self.source_entries = {}
        popups = data.get('popups') or {}

        for category in data['categories']:
            if category.get('type') or not category.get('name'):
                continue
            name = str(category['name'])
            self.categories.append(name)
            group = ''
            for item in category.get('entities', []):
                if item.get('type'):
                    group = plain(item.get('text'))
                    continue
                if not item.get('id'):
                    continue
                base = self._entry(item, name, group, None, popups)
                self.variants[base.key] = []
                for variant in item.get('variants', []):
                    if variant.get('id'):
                        child = self._entry(variant, name, group, base, popups)
                        self.variants[base.key].append(child)

        if not self.entries:
            raise ValueError('Empty CEM catalog')

    def _entry(self, item, category, group, parent, popups):
        ident = str(item['id'])
        key = json.dumps([category, parent.id if parent else '', ident], ensure_ascii=True)
        popup = item.get('popup', '')
        args = [display(item)]

        if isinstance(popup, list):
            args += popup[1:]
            popup = popups.get(popup[0], popup[0]) if popup else ''
        elif isinstance(popup, str):
            popup = popups.get(popup, popup)
        if isinstance(popup, dict):
            popup = popup.get('message', '')
        for i, value in enumerate(args):
            popup = str(popup).replace('{' + str(i) + '}', str(value))

        entry = Entry(key, ident, display(item), category, group,
                      parent.key if parent else '', parent.name if parent else '',
                      str(item.get('model') or (parent.model if parent else ident)),
                      str(item.get('file') or ident), plain(popup), bool(item.get('textureless')))
        if key in self.by_key:
            raise ValueError('Duplicate catalog entry')
        self.entries.append(entry)
        self.by_key[key] = entry
        self.source_entries[key] = item
        return entry

    def model_data(self, entry):
        value = self.data.get('models', {}).get(entry.model)
        if not isinstance(value, dict) or not isinstance(value.get('model'), str):
            raise ValueError('Template model is missing: ' + entry.model)
        return json.loads(value['model'])

    def texture_count(self, entry):
        value = self.source_entries[entry.key].get('vanilla_textures')
        return len(value) if isinstance(value, list) else 1

    def search(self, category='Regular', query=''):
        tokens = query.lower().replace('_', ' ').split()
        return [e for e in self.entries
                if (category == 'ALL' or e.category == category)
                and (bool(tokens) or not e.parent_key)
                and all(t in (e.name + ' ' + e.id).lower().replace('_', ' ') for t in tokens)]

    def family(self, entry):
        base = self.by_key[entry.parent_key] if entry.parent_key else entry
        return [base] + self.variants.get(base.key, [])

    def browse(self, category='Regular', query='', expanded=()):
        if query.strip():
            return self.search(category, query)
        return [e for e in self.entries
                if (category == 'ALL' or e.category == category)
                and (not e.parent_key or e.parent_key in expanded)]
