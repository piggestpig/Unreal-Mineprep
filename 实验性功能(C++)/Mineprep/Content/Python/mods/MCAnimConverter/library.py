"""Animation index loading and JSON/dict/.bbmodel clip resolution."""
import json
from pathlib import Path

from . import bbmodel

ROOT = Path(__file__).with_name('Anim')
SOURCES = (('custom', ROOT / 'custom'), ('vanilla', ROOT / 'vanilla'))


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def resolve_clips(data, clip=None):
    """Normalize a loaded Java clip, Bedrock container/clip dict, or .bbmodel project."""
    if not isinstance(data, dict):
        raise ValueError('动画数据须为 JSON 对象')
    if 'frames' in data:
        name = data.get('clip')
        if not isinstance(name, str) or not name.strip():
            raise ValueError('Java 动画缺少 clip 名称')
        return {name: data}
    if bbmodel.is_bbmodel(data):
        return bbmodel.resolve_clips(data)
    if 'animations' in data:
        animations = data['animations']
        if (not isinstance(animations, dict) or not animations
                or not all(isinstance(k, str) and k.strip() and isinstance(v, dict)
                           for k, v in animations.items())):
            raise ValueError('Bedrock animations 须为映射片段名到动画对象的非空字典')
        return animations
    if 'bones' in data:
        if not isinstance(data.get('bones'), dict):
            raise ValueError('单个动画定义的 bones 须为对象')
        if not isinstance(clip, str) or not clip.strip():
            raise ValueError('直接传入单个动画定义时必须提供 clip 名称')
        return {clip: data}
    raise ValueError('无法识别的动画格式：需要 animations、frames、bones 或 .bbmodel')


def clips(path, clip=None):
    return resolve_clips(read(path), clip=clip)


def _relative_path(folder, relative):
    rel = Path(relative)
    if not relative or rel.is_absolute() or '..' in rel.parts:
        raise ValueError(f'索引路径须相对所属目录: {relative}')
    return folder / rel


def _index_entries():
    entries = []
    seen = {}
    for source, folder in SOURCES:
        index = folder / 'index.json'
        if not index.is_file():
            continue
        raw = read(index)
        if not isinstance(raw, list):
            raise ValueError(f'动画索引须为列表: {index}')
        for item in raw:
            if (not isinstance(item, dict) or not isinstance(item.get('file'), str)
                    or not isinstance(item.get('clip'), str)):
                raise ValueError(f'动画索引条目缺少 file 或 clip: {index}')
            clip = item['clip']
            if not clip.strip():
                raise ValueError(f'动画索引 clip 键不能为空: {index}')
            path = _relative_path(folder, item['file'])
            if clip in seen:
                raise ValueError(f"动画索引中存在重复 clip 键: {clip} ({seen[clip]} 与 {source}/{item['file']})")
            seen[clip] = f"{source}/{item['file']}"
            entries.append((source, path, item))
    return entries


def _clip_data(path, cache, clip=None):
    if not path.is_file():
        return {}
    if cache is not None and path in cache:
        return cache[path]
    data = clips(path, clip=clip)
    if cache is not None:
        cache[path] = data
    return data


def _entry_record(source, path, item, cache=None):
    record = {
        'source': source,
        'path': path,
        'file': item['file'],
        'clip': item['clip'],
        'skeleton': item.get('skeleton'),
        'skeleton_mode': item.get('skeleton_mode'),
        'loop': item.get('loop'),
        'source_version': item.get('source_version'),
    }
    if any(record[key] is None for key in ('skeleton', 'loop', 'source_version')):
        data = _clip_data(path, cache, clip=record['clip']).get(record['clip'], {})
        if record['skeleton'] is None:
            record['skeleton'] = data.get('model_layer')
        if record['loop'] is None and isinstance(data.get('loop'), bool):
            record['loop'] = data['loop']
        if record['source_version'] is None:
            record['source_version'] = data.get('source_version')
    return record


def catalog(*, skeleton=None, loop=None):
    """Return local index metadata dicts (source, clip, path, file, skeleton, loop, source_version)."""
    cache = {}
    records = [_entry_record(source, path, item, cache) for source, path, item in _index_entries()]
    if skeleton is not None:
        records = [item for item in records if item['skeleton'] == skeleton]
    if loop is not None:
        records = [item for item in records if item['loop'] is loop]
    return records


def entries():
    return [(path, item['clip']) for _, path, item in _index_entries()]


def info(clip):
    """Return metadata for an unambiguous full clip key in the local index."""
    matches = [item for item in catalog() if item['clip'] == clip]
    if len(matches) != 1:
        raise ValueError(f'Expected one local file for {clip}, found {len(matches)}')
    return matches[0]


def find(clip):
    """Return the file for an unambiguous full clip key in the local index."""
    for _, path, item in _index_entries():
        if item['clip'] == clip:
            return path
    raise ValueError(f'Expected one local file for {clip}, found 0')


def match_entry(path=None, clip=None):
    """Return raw local-index metadata if (path, clip) matches an indexed clip."""
    target_path = Path(path).resolve() if path is not None else None
    for source, entry_path, item in _index_entries():
        if clip is not None and item['clip'] != clip:
            continue
        if target_path is not None and entry_path.resolve() != target_path:
            continue
        return {
            'source': source,
            'path': entry_path,
            'file': item['file'],
            'clip': item['clip'],
            'skeleton': item.get('skeleton'),
            'skeleton_mode': item.get('skeleton_mode'),
            'loop': item.get('loop'),
            'source_version': item.get('source_version'),
        }
    return None
