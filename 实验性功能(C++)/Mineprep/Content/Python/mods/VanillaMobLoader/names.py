"""实体名称、组合译名和搜索词；仅 register/text/description 需要 UE 主线程。"""
from functools import lru_cache
import json
from pathlib import Path
import re

LANGUAGES = ('en', 'zh', 'zh-Hant', 'zh-Hant-HK')
BABIES = {
    'chick': 'chicken', 'calf': 'cow', 'foal': 'horse', 'ghastling': 'ghast',
    'gurgle': 'drowned', 'kitten': 'cat', 'lamb': 'sheep', 'piglet': 'pig',
    'puppy': 'wolf', 'snifflet': 'sniffer', 'squirt': 'squid',
}
SUFFIXES = {
    ' wool undercoat': 'wool_undercoat', ' saddle': 'saddle', ' armor': 'armor',
    ' collar': 'collar', ' decor': 'decor', ' wool': 'wool', ' patch': 'tag.patch',
}
_records = {}
_texts = None


def normalize(value):
    return ' '.join(value.casefold().replace('_', ' ').split())


@lru_cache(maxsize=1)
def _catalogs():
    folder = Path(__file__).parent
    shared = folder.parents[1] / 'i18n_entities.json'
    entities = json.loads(shared.read_text(encoding='utf-8-sig'))['Entities'] if shared.is_file() else {}
    templates = json.loads((folder / 'i18n.json').read_text(encoding='utf-8-sig'))['VanillaMobLoader']
    return entities, templates


def _record(record, fallback):
    return {lang: record.get(lang) or record.get('en') or fallback for lang in LANGUAGES}


def _apply(template, base):
    record = _catalogs()[1]['names.' + template]
    return {lang: record[lang].format(name=base[lang]) for lang in LANGUAGES}


@lru_cache(maxsize=None)
def translations(name):
    """只读生成四语字符串；未知名称保留英文，不收集或写入词典。"""
    entities, templates = _catalogs()
    norm = normalize(name)
    if norm in entities:
        return _record(entities[norm], name)
    if norm in ('sheep wool', 'sheep wool undercoat'):
        return _record(templates['names.' + norm.replace(' ', '_')], name)
    if ' + ' in name:
        parts = [translations(part) for part in name.split(' + ')]
        return {lang: ' + '.join(part[lang] for part in parts) for lang in LANGUAGES}
    tag = re.fullmatch(r'(.+?)\s*\[([^\[\]]+)\]', name.strip())
    if tag:
        base = translations(tag[1].strip())
        key = 'tag.' + normalize(tag[2]).replace(' ', '_')
        if 'names.' + key in templates:
            return _apply(key, base)
        return {lang: base[lang] + ' [' + tag[2] + ']' for lang in LANGUAGES}
    for suffix, template in SUFFIXES.items():
        if norm.endswith(suffix):
            return _apply(template, translations(norm[:-len(suffix)]))
    if norm.startswith(('warm baby ', 'cold baby ')):
        climate, _, rest = norm.split(' ', 2)
        return translations('baby ' + climate + ' ' + rest)
    if norm.startswith('baby '):
        adult = norm[5:]
        child = next((child for child, parent in BABIES.items() if parent == adult), None)
        if child and child in entities:
            return translations(child)
        return _apply('baby', translations(adult))
    fallback = name.title() if name.islower() else name
    return dict.fromkeys(LANGUAGES, fallback)


def search_text(name, ident, filename, parent=None):
    """预计算跨语言搜索文本；幼体专名同时保留通用名称。"""
    words = [name, ident, filename, *translations(name).values()]
    norm = normalize(name)
    for child, adult in BABIES.items():
        if re.search(r'\b(?:' + re.escape(child) + '|baby ' + re.escape(adult) + r')\b', norm):
            words.extend(('baby ' + adult, *translations(child).values(),
                          *_apply('baby', translations(adult)).values()))
    if parent:
        words.append(parent.search_text)
    return normalize(' '.join(words))


def _register(records):
    global _texts
    if any(_records.get(key) != value for key, value in records.items()):
        from mineprep import Internationalization
        _records.update(records)
        _texts = Internationalization.from_data(_records, namespace='VanillaMobLoader.Entities')


def register(catalog):
    """在主线程批量注册目录译名；下载线程只构建 Catalog。"""
    _register({entry.name: entry.translations for entry in catalog.entries})


def text(name):
    """当前语言的 Text；组合模型或独立资产可直接用英文名称查找。"""
    if name not in _records:
        _register({name: translations(name)})
    return _texts(name, key=name)


def description(entry):
    return entry.description.replace('{0}', str(text(entry.name)))
