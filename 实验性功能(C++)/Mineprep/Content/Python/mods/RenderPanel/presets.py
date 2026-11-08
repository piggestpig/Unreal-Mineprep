"""配置库与队列的纯数据存储；不导入 Unreal，不生成渲染资产。"""
from copy import deepcopy
import json
import re
import sys
from pathlib import Path
from uuid import uuid4

from . import encoding

# 独立 Python 中仍可使用纯数据存储，不依赖 UE 的 Text 注册。
if 'unreal' in sys.modules:
    from mineprep import i18n
else:
    def i18n(source, *texts, **languages):
        return source

STATES = {'pending': i18n('待渲染'), 'running': i18n('渲染中'), 'completed': i18n('完成'),
          'failed': i18n('失败'), 'incomplete': i18n('未完整完成'), 'interrupted': i18n('上次中断')}


def name_text(preset):
    """名称字符串原样使用；语言字典沿用 manifest 的 i18n 写法与稳定 key。"""
    name = preset['name']
    if isinstance(name, dict):
        return i18n(name['zh'], key=f"presets.{preset['id']}.name",
                    **{lang: text for lang, text in name.items() if lang != 'zh'})
    return name


def _names(preset):
    name = preset['name']
    return list(name.values()) if isinstance(name, dict) else [name]


def _output_targets(settings, kind):
    """输出文件／帧序列及帧范围；静帧与动画共享图片路径，增益图有独立后缀。"""
    folder, stem = encoding.output_name(settings['name'])
    base = '/'.join(part for part in (folder, stem) if part).casefold()
    if kind == 'hdr':
        return {base + '_gainmap.jpg': None}
    s = dict(video=1, stereo=0, vr=0, codec=0, container='mp4', hdr=0,
             stereo_format=0, image_transcode='No')
    s.update(settings, platform={'win32': 'Windows', 'darwin': 'Mac'}.get(sys.platform, 'Linux'))
    if kind == 'still':
        s.update(video=0, audio=0)
    route = encoding.routing(s)
    targets = {}
    if not route['native']:
        for bit, extension in ((1, 'png'), (2, 'jpg'), (12, 'exr')):
            if s.get('image_formats', 0) & bit:
                targets[base + '.{frame}.' + extension] = int(s.get('frame', 0)) if kind == 'still' else None
    if s['video'] == 1:
        extension = 'mov' if route['native'] and s['codec'] == 3 else s['container'].lower()
        targets[base + '.' + extension] = None
    elif s['image_transcode'] != 'No':
        key = base + ('.{frame}' if kind == 'still' else '') + '.' + s['image_transcode'].lower()
        targets[key] = int(s.get('frame', 0)) if kind == 'still' else None
    if s.get('audio') == 1:
        targets[base + '.wav'] = None
    return targets


def _overlap(first, second):
    return any(first[key] is None or second[key] is None or first[key] == second[key]
               for key in first.keys() & second.keys())


def _read(path, key, ids=None):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if data['schema_version'] != 1:
            raise ValueError(i18n('不支持的文件格式'))
        rows = [{k: v for k, v in data.items() if k != 'schema_version'}] if key == 'preset' else data[key]
        if not isinstance(rows, list):
            raise ValueError(i18n('不支持的文件格式'))
        ids = set() if ids is None else ids
        for row in rows:
            if row['id'] in ids or row['backend'] not in ('MRQ', 'MRG') or not isinstance(row['settings'], dict):
                raise ValueError(i18n('配置 ID、后端或参数格式有误'))
            name = row['label' if key == 'queue' else 'name']
            localized = key != 'queue' and isinstance(name, dict) and bool(name.get('zh')) and all(
                re.fullmatch(r'[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*', lang) and isinstance(text, str)
                for lang, text in name.items())
            if not isinstance(name, str) and not localized:
                raise ValueError(i18n('配置名称格式有误'))
            if not all(isinstance(row['settings'][field], str) for field in ('name', 'sequence', 'map')):
                raise ValueError(i18n('输出名、序列或地图路径格式有误'))
            ids.add(row['id'])
            if key == 'queue' and (row['state'] not in STATES or type(row['enabled']) is not bool):
                raise ValueError(i18n('队列状态有误'))
            if row.get('kind', 'animation') not in ('animation', 'still', 'hdr'):
                raise ValueError(i18n('队列任务类型有误'))
            if row.get('context') not in (None, 'current') or (
                    'slug' in row and not re.fullmatch(r'[a-z][a-z0-9_]*', row['slug'])):
                raise ValueError(i18n('配置 ID、后端或参数格式有误'))
        return rows
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(i18n('无法读取 {path}：{exc}；原文件已保留').format(path=str(path), exc=str(exc))) from exc


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class Store:
    def __init__(self, project_dir, *, presets_dir=None):
        root = Path(project_dir)
        self.presets_dir = Path(presets_dir) if presets_dir is not None else Path(__file__).with_name('presets')
        self.queue_path = root / 'Saved/Mineprep/RenderPanel/queue.json'
        self.presets, self._preset_files = [], {}
        ids = set()
        for path in sorted(self.presets_dir.glob('*.json')):
            row = _read(path, 'preset', ids)[0]
            self.presets.append(row)
            self._preset_files[row['id']] = path
        self.queue = _read(self.queue_path, 'queue')
        legacy = root / 'Config/Mineprep/RenderPanel/presets.json'
        if legacy.exists():
            for row in _read(legacy, 'presets'):
                if row['id'] not in self._preset_files:
                    self._save_preset(row)
            # Only retire the old collection after every record is safely on disk.
            for row in self.presets:
                if _read(self._preset_files[row['id']], 'preset')[0] != row:
                    raise RuntimeError(i18n('预设迁移校验失败，旧文件已保留'))
            backup = self.queue_path.with_name('presets.legacy.json')
            if backup.exists():
                backup = backup.with_name('presets.legacy.' + uuid4().hex + '.json')
            backup.parent.mkdir(parents=True, exist_ok=True)
            legacy.replace(backup)
        for row in self.queue:
            if row['state'] == 'running':
                row.update(state='interrupted', error=str(i18n('上次运行中断，请手动重新排队')))

    def _commit(self, key, rows):
        _write(getattr(self, key + '_path'), dict(schema_version=1, **{key: rows}))
        setattr(self, key, rows)

    def _save_preset(self, record):
        # Keep display names readable while making them safe on Windows and Unix.
        stem = record.get('slug') or re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', _names(record)[0]).rstrip(' .') or 'Preset'
        if stem.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
            stem = '_' + stem
        path = self.presets_dir / (stem + '.json')
        previous = self._preset_files.get(record['id'])
        if path != previous and path.exists():
            raise ValueError(i18n('预设文件已存在：{path}').format(path=str(path)))
        _write(path, dict(schema_version=1, **record))
        if previous is not None and previous != path:
            try:
                previous.unlink()
            except OSError:
                path.unlink()
                raise
        self._preset_files[record['id']] = path
        rows = [deepcopy(record) if row['id'] == record['id'] else row for row in self.presets]
        if previous is None:
            rows.append(deepcopy(record))
        self.presets = rows

    def preset(self, preset_id):
        return next(row for row in self.presets if row['id'] == preset_id)

    def find_preset(self, identifier):
        """优先 ID、实际文件名（可省略 .json），最后按任一语言的名称查找。"""
        for row in self.presets:
            if row['id'] == identifier:
                return row
        matches = [row for row in self.presets
                   if identifier in (self._preset_files[row['id']].name, self._preset_files[row['id']].stem)]
        if not matches:
            matches = [row for row in self.presets if identifier in _names(row)]
        if len(matches) != 1:
            raise ValueError(i18n('找不到唯一的渲染预设：{preset}').format(preset=str(identifier)))
        return matches[0]

    def item(self, item_id):
        return next(row for row in self.queue if row['id'] == item_id)

    def _name(self, name, exclude=None):
        name = str(name).strip()
        if not name:
            raise ValueError(i18n('请填写配置名称'))
        if any(name.casefold() in (text.casefold() for text in _names(row))
               and row['id'] != exclude for row in self.presets):
            raise ValueError(i18n('配置名称已存在，请换一个名称或使用覆盖'))
        return name

    def save_preset(self, name, backend, settings, preset_id=None, *, kind='animation'):
        name = self._name(name, preset_id)
        if backend not in ('MRQ', 'MRG') or kind not in ('animation', 'still', 'hdr'):
            raise ValueError(i18n('请选择 MRQ 或 MRG'))
        if preset_id:
            self.preset(preset_id)
        record = dict(id=preset_id or uuid4().hex, name=name, backend=backend,
                      kind=kind, settings=deepcopy(settings))
        if preset_id:
            old = self.preset(preset_id)
            if name == str(name_text(old)):
                record['name'] = deepcopy(old['name'])
            for key in ('context', 'slug'):
                if key in old:
                    record[key] = old[key]
        if record.get('context') == 'current':
            record['settings'].update(map='', sequence='', sequence_fallback='')
            record['settings'].pop('frame', None)
        self._save_preset(record)
        return record['id']

    def rename_preset(self, preset_id, name):
        name = self._name(name, preset_id)
        old = self.preset(preset_id)
        self._save_preset(dict(old, name=old['name'] if name == str(name_text(old)) else name))

    def delete_preset(self, preset_id):
        self.preset(preset_id)
        self._preset_files[preset_id].unlink(missing_ok=True)
        del self._preset_files[preset_id]
        self.presets = [row for row in self.presets if row['id'] != preset_id]

    def enqueue(self, preset_id):
        preset = self.preset(preset_id)
        return self.enqueue_settings(str(name_text(preset)), preset['backend'], preset['settings'],
                                     kind=preset.get('kind', 'animation'), preset_id=preset_id)

    def enqueue_settings(self, label, backend, settings, *, kind='animation', preset_id=None):
        """将参数副本加入队列；HDR 双次渲染作为一个完整任务保存。"""
        if backend not in ('MRQ', 'MRG') or kind not in ('animation', 'still', 'hdr'):
            raise ValueError(i18n('队列后端或任务类型有误'))
        settings = deepcopy(settings)
        folder, stem = encoding.output_name(settings['name'])
        leaf = str(settings['name']).replace('\\', '/').rsplit('/', 1)[-1].strip()
        extension = leaf[len(stem):]
        used = [_output_targets(row['settings'], row.get('kind', 'animation'))
                for row in self.queue if row['state'] in ('pending', 'running')]
        name = '/'.join(part for part in (folder, stem) if part)
        number = 2
        while any(_overlap(_output_targets(settings, kind), targets) for targets in used):
            name = '/'.join(part for part in (folder, f'{stem}_{number:02d}') if part)
            settings['name'] = name + extension
            number += 1
        # 保留原扩展名，使含多个点的干名不会在 build_config 中被再次截断。
        settings['name'] = name + extension
        row = dict(id=uuid4().hex, preset_id=preset_id, label=label, backend=backend, kind=kind,
                   settings=settings, output_name=name + '_Gainmap.jpg' if kind == 'hdr' else name,
                   enabled=True, state='pending', result=None, error=None)
        self._commit('queue', deepcopy(self.queue) + [row])
        return row['id']

    def copy_item(self, item_id):
        row = self.item(item_id)
        return self.enqueue_settings(row['label'], row['backend'], row['settings'],
                                     kind=row.get('kind', 'animation'), preset_id=row.get('preset_id'))

    def update_item(self, item_id, **changes):
        rows = deepcopy(self.queue)
        next(row for row in rows if row['id'] == item_id).update(deepcopy(changes))
        self._commit('queue', rows)

    def move_item(self, item_id, delta):
        rows = deepcopy(self.queue)
        index = next(i for i, row in enumerate(rows) if row['id'] == item_id)
        row = rows.pop(index)
        rows.insert(max(0, min(len(rows), index + delta)), row)
        self._commit('queue', rows)

    def remove_item(self, item_id):
        self.item(item_id)
        self._commit('queue', [deepcopy(row) for row in self.queue if row['id'] != item_id])

    def requeue(self, item_id):
        if self.item(item_id)['state'] == 'running':
            raise ValueError(i18n('当前任务仍在运行'))
        self.update_item(item_id, state='pending', result=None, error=None)

    def clear_finished(self):
        self._commit('queue', [deepcopy(row) for row in self.queue if row['state'] in ('pending', 'running')])
