"""把当前工程的 Mineprep 同步到安装包仓库，或迁移到另一个 UE 工程。"""
import os
import re
import runpy
import shutil
from pathlib import Path

import unreal
import mineprep

_SKIP_COPY = frozenset({'Intermediate', 'Saved'})
_INSTALLER_SKIP_DIRS = frozenset({'intermediate', 'saved', '__pycache__', 'cache', '.vscode'})
_INSTALLER_SKIP_EXTS = frozenset({'.pdb', '.debug', '.sym'})
_INSTALLER_PATCH = re.compile(r'\.patch_\d+\.(exe|exp|lib)$', re.IGNORECASE)
_TREES = (
    'Content/Mineprep',
    'Plugins/Mineprep',
    'Plugins/InlineMaterialInstance',
    'Plugins/MoviePipelineMaskRenderPass',
)
_PIP_LIB = 'Intermediate/PipInstall/Lib/site-packages'
_REQUIRED = frozenset({'Content/Mineprep', 'Plugins/Mineprep'})
_FILTER_FIELDS = (
    ('FilterNew', 'NewFiles'),
    ('FilterNewer', 'NewerFiles'),
    ('FilterOlder', 'OlderFiles'),
)
_MAP_FIELDS = frozenset(field for _, field in _FILTER_FIELDS)


def _filter_entry_defaults(filter_props):
    """LightingChannels 0/1/2 → 新增/变新/变旧 字典条目默认勾选。"""
    ch = getattr(filter_props, 'EntryDefault', None)
    if isinstance(ch, bool):
        v = bool(ch)
        return {'FilterNew': v, 'FilterNewer': v, 'FilterOlder': v}
    return {
        'FilterNew': bool(getattr(ch, 'channel0', True)),
        'FilterNewer': bool(getattr(ch, 'channel1', True)),
        'FilterOlder': bool(getattr(ch, 'channel2', True)),
    }


def installer_dir():
    """config Settings.installer_dir 的绝对路径；未设置时为空字符串。"""
    try:
        raw = str(mineprep.config['Settings']['installer_dir'] or '').strip()
        return os.path.abspath(raw) if raw else ''
    except Exception:
        return ''


def target_dir(props):
    """PropertyGroup 上 DirectoryPath 的绝对路径；未设置时为空字符串。"""
    raw = getattr(props, 'TargetDir', None)
    if isinstance(raw, str):
        path = raw
    else:
        path = getattr(raw, 'path', '') or ''
    path = str(path).strip().strip('"').strip("'")
    return os.path.abspath(path) if path else ''


def set_target_dir(props, path):
    inst = unreal.DirectoryPath()
    inst.set_editor_property('path', path or '')
    props.TargetDir = inst


def open_target(props):
    folder = target_dir(props)
    if os.path.isdir(folder):
        mineprep.startfile(folder)
        return folder
    mineprep.warn(mineprep.bilingual('目标文件夹不存在', 'Target folder does not exist'))
    return ''


def _project_root():
    return os.path.abspath(unreal.Paths.project_dir())


def _rel_key(abs_path, project_root):
    rel = os.path.relpath(abs_path, project_root).replace('\\', '/')
    if rel.startswith('./'):
        rel = rel[2:]
    return '/' + rel if not rel.startswith('/') else rel


def dest_abs(rel_key, dest_root, *, installer=False):
    """工程相对路径 → 目标绝对路径。"""
    parts = [p for p in rel_key.replace('\\', '/').strip('/').split('/') if p]
    if installer:
        if len(parts) >= 2 and parts[0] == 'Content' and parts[1] == 'Mineprep':
            return os.path.join(dest_root, 'Mineprep', *parts[2:])
        if parts and parts[0] == 'Plugins':
            return os.path.join(dest_root, '实验性功能(C++)', *parts[1:])
    return os.path.join(dest_root, *parts)


def _should_skip_dir(name, *, installer=False):
    if name in _SKIP_COPY:
        return True
    return installer and name.lower() in _INSTALLER_SKIP_DIRS


def _is_installer_junk(name):
    ext = os.path.splitext(name)[1].lower()
    if ext in _INSTALLER_SKIP_EXTS:
        return True
    return bool(_INSTALLER_PATCH.search(name))


def load_skip_fn(script_props):
    """从脚本里取出 skip(path)->bool；无效则返回 None。"""
    if not script_props:
        return None
    text = str(getattr(script_props, 'Script', '') or '')
    if not text.strip():
        return None
    ns = {'__name__': 'versioncontrol_skip'}
    try:
        exec(text, ns)
    except Exception as extra:
        mineprep.warn(mineprep.bilingual('过滤脚本无效', 'Invalid filter script'), extra)
        return None
    fn = ns.get('skip')
    if not callable(fn):
        mineprep.warn(mineprep.bilingual(
            '过滤脚本需要 def skip(path:str)->bool',
            'Filter script needs def skip(path:str)->bool',
        ))
        return None
    return fn


def _script_skips(skip_fn, rel_path):
    if not skip_fn:
        return False
    try:
        return bool(skip_fn(rel_path))
    except Exception:
        return False


def _iter_files(root, *, installer=False):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if not _should_skip_dir(name, installer=installer)]
        for name in filenames:
            if installer and _is_installer_junk(name):
                continue
            yield os.path.join(dirpath, name)


def _source_trees():
    project = _project_root()
    trees = []
    for rel in _TREES:
        src = os.path.join(project, *rel.split('/'))
        if os.path.isdir(src):
            trees.append((src, rel))
        elif rel in _REQUIRED:
            mineprep.warn(mineprep.bilingual(
                f'源工程缺少 {rel}',
                f'Source project missing {rel}',
            ))
    return trees


def _tree_pairs(dest_root, *, installer=False):
    pairs = []
    for src, rel in _source_trees():
        dst = dest_abs('/' + rel, dest_root, installer=installer)
        pairs.append((src, dst, rel))
    return pairs


def _dest_tree_paths(dest_root, *, installer=False):
    return [dest_abs('/' + rel, dest_root, installer=installer) for rel in _TREES]


def _map_items(value):
    if not value:
        return {}
    try:
        return {str(key): bool(on) for key, on in value.items()}
    except Exception:
        return dict(value)


def filters_enabled(filter_props):
    if not filter_props:
        return False
    return any(bool(getattr(filter_props, flag)) for flag, _ in _FILTER_FIELDS)


def skipped_relpaths(filter_props):
    skip = set()
    if not filter_props:
        return skip
    for _, field in _FILTER_FIELDS:
        for key, on in _map_items(getattr(filter_props, field)).items():
            if not on:
                skip.add(key)
    return skip


def filter_counts(filter_props):
    selected = skipped = 0
    if not filter_props:
        return False, 0, 0
    enabled = filters_enabled(filter_props)
    for _, field in _FILTER_FIELDS:
        for on in _map_items(getattr(filter_props, field)).values():
            if on:
                selected += 1
            else:
                skipped += 1
    return enabled, selected, skipped


def classify_files(props, *, installer=False, skip_fn=None):
    dest_root = target_dir(props)
    project = _project_root()
    added, newer, older = [], [], []
    if not dest_root or not os.path.isdir(dest_root):
        return added, newer, older
    for src_root, _rel in _source_trees():
        for src in _iter_files(src_root, installer=installer):
            key = _rel_key(src, project)
            if _script_skips(skip_fn, key):
                continue
            dst = dest_abs(key, dest_root, installer=installer)
            if not os.path.isfile(dst):
                added.append(key)
                continue
            src_mtime = os.path.getmtime(src)
            dst_mtime = os.path.getmtime(dst)
            if src_mtime > dst_mtime:
                newer.append(key)
            elif src_mtime < dst_mtime:
                older.append(key)
    return added, newer, older


def _source_relpaths(*, installer=False, skip_fn=None):
    project = _project_root()
    keys = set()
    for src_root, _rel in _source_trees():
        for src in _iter_files(src_root, installer=installer):
            key = _rel_key(src, project)
            if _script_skips(skip_fn, key):
                continue
            keys.add(key)
    return keys


def extra_relpaths(props, *, installer=False, skip_fn=None):
    """目标有、当前工程没有的文件（工程相对路径）。"""
    dest_root = target_dir(props)
    extras = []
    if not dest_root or not os.path.isdir(dest_root):
        return extras
    source = _source_relpaths(installer=installer, skip_fn=skip_fn)
    for rel in _TREES:
        dst_root = dest_abs('/' + rel, dest_root, installer=installer)
        if not os.path.isdir(dst_root):
            continue
        for dst in _iter_files(dst_root, installer=installer):
            file_rel = os.path.relpath(dst, dst_root).replace('\\', '/')
            key = f'/{rel}/{file_rel}' if file_rel not in ('.', '') else f'/{rel}'
            if _script_skips(skip_fn, key):
                continue
            if key not in source:
                extras.append(key)
    return extras


def extra_to_remove(extra_props):
    if not extra_props or not getattr(extra_props, 'RemoveExtra', False):
        return []
    return [key for key, on in _map_items(extra_props.ExtraFiles).items() if on]


def copy_stats(props, filter_props, extra_props=None, skip_fn=None):
    """按实际复制语义统计：新增/变新/变旧/相同、脚本跳过、多余文件。"""
    installer = bool(getattr(props, 'UpdateInstaller', False))
    clear = bool(getattr(props, 'ClearDest', False))
    skip_keys = set() if clear else skipped_relpaths(filter_props)
    dest_root = target_dir(props)
    project = _project_root()
    added_c = added_s = newer_c = newer_s = older_c = older_s = same_c = same_s = 0
    script_s = 0
    for src_root, _rel in _source_trees():
        for src in _iter_files(src_root, installer=installer):
            key = _rel_key(src, project)
            if _script_skips(skip_fn, key):
                script_s += 1
                continue
            dst = dest_abs(key, dest_root, installer=installer) if dest_root else ''
            skipped = key in skip_keys
            if not dest_root or not os.path.isfile(dst):
                if skipped:
                    added_s += 1
                else:
                    added_c += 1
                continue
            src_mtime = os.path.getmtime(src)
            dst_mtime = os.path.getmtime(dst)
            if src_mtime > dst_mtime:
                if skipped:
                    newer_s += 1
                else:
                    newer_c += 1
            elif src_mtime < dst_mtime:
                if skipped:
                    older_s += 1
                else:
                    older_c += 1
            elif skipped or not clear:
                same_s += 1
            else:
                same_c += 1
    extra_n = extra_rm = 0
    if not clear:
        extra_n = len(extra_relpaths(props, installer=installer, skip_fn=skip_fn))
        extra_rm = len(extra_to_remove(extra_props))
    copy_n = added_c + newer_c + older_c + same_c
    skip_n = added_s + newer_s + older_s + same_s + script_s
    return {
        'clear': clear,
        'added_c': added_c, 'added_s': added_s,
        'newer_c': newer_c, 'newer_s': newer_s,
        'older_c': older_c, 'older_s': older_s,
        'same_c': same_c, 'same_s': same_s,
        'script_s': script_s,
        'extra_n': extra_n, 'extra_rm': extra_rm,
        'copy_n': copy_n, 'skip_n': skip_n,
    }


def refresh_filters(filter_props, props, name=None, skip_fn=None):
    if not filter_props:
        return
    if name in _MAP_FIELDS:
        return
    flag_to_field = dict(_FILTER_FIELDS)
    if name in flag_to_field and not getattr(filter_props, name):
        setattr(filter_props, flag_to_field[name], {})
        return

    if name in flag_to_field:
        need = [(name, flag_to_field[name])]
    else:
        need = [(flag, field) for flag, field in _FILTER_FIELDS if getattr(filter_props, flag)]
    if not need:
        return

    dest = target_dir(props)
    if not dest or not os.path.isdir(dest):
        for _, field in need:
            setattr(filter_props, field, {})
        return

    added, newer, older = classify_files(props, installer=bool(props.UpdateInstaller), skip_fn=skip_fn)
    bucket = {'FilterNew': added, 'FilterNewer': newer, 'FilterOlder': older}
    defaults = _filter_entry_defaults(filter_props)
    for flag, field in need:
        default = defaults[flag]
        setattr(filter_props, field, {key: default for key in sorted(bucket[flag])})


def refresh_extras(extra_props, props, name=None, skip_fn=None):
    if not extra_props:
        return
    if name == 'ExtraFiles':
        return
    if name == 'RemoveExtra' and not extra_props.RemoveExtra:
        extra_props.ExtraFiles = {}
        return
    if name != 'RemoveExtra' and not extra_props.RemoveExtra:
        return

    dest = target_dir(props)
    if not dest or not os.path.isdir(dest):
        extra_props.ExtraFiles = {}
        return
    extras = extra_relpaths(props, installer=bool(props.UpdateInstaller), skip_fn=skip_fn)
    extra_props.ExtraFiles = {key: bool(extra_props.EntryDefault) for key in sorted(extras)}


def confirm_copy(props, filter_props, extra_props=None, skip_fn=None):
    stats = copy_stats(props, filter_props, extra_props, skip_fn=skip_fn)
    lines = []
    if stats['clear']:
        lines.append(str(mineprep.bilingual(
            '将清空目标路径再复制。',
            'Destination trees will be cleared then copied.',
        )))
    lines.append(str(mineprep.bilingual(
        f"新增：复制 {stats['added_c']}，跳过 {stats['added_s']}",
        f"New: copy {stats['added_c']}, skip {stats['added_s']}",
    )))
    lines.append(str(mineprep.bilingual(
        f"变新：复制 {stats['newer_c']}，跳过 {stats['newer_s']}",
        f"Newer: copy {stats['newer_c']}, skip {stats['newer_s']}",
    )))
    lines.append(str(mineprep.bilingual(
        f"变旧：复制 {stats['older_c']}，跳过 {stats['older_s']}",
        f"Older: copy {stats['older_c']}, skip {stats['older_s']}",
    )))
    lines.append(str(mineprep.bilingual(
        f"相同文件：{stats['same_s']}",
        f"Unchanged: {stats['same_s']}",
    )))
    if stats['script_s']:
        lines.append(str(mineprep.bilingual(
            f"脚本跳过：{stats['script_s']}\n",
            f"Skipped by script: {stats['script_s']}\n",
        )))
    lines.append(str(mineprep.bilingual(
        f"共计复制 {stats['copy_n']}",
        f"Total copy {stats['copy_n']}",
    )))
    if not stats['clear']:
        lines.append(str(mineprep.bilingual(
            f"目标路径有多余文件 {stats['extra_n']}，将移除 {stats['extra_rm']}。",
            f"Destination has extra files {stats['extra_n']}, remove {stats['extra_rm']}.",
        )))
    if not getattr(props, 'UpdateInstaller', False) and getattr(props, 'CopyPythonLib', False):
        lines.append(str(mineprep.bilingual(
            '将复制 Python 库（Intermediate/PipInstall/Lib/site-packages）。',
            'Python libraries will be copied (Intermediate/PipInstall/Lib/site-packages).',
        )))
    lines.append(str(mineprep.bilingual('是否继续？', 'Continue?')))
    return mineprep.dialog(
        str(mineprep.bilingual('确认复制', 'Confirm copy')),
        '\n'.join(lines),
    )


def _copy_ignore_with_skip(project_root, skip, *, installer=False, skip_fn=None, src_root=None, dst_root=None):
    skip = skip or set()

    def ignore(directory, names):
        ignored = [name for name in names if _should_skip_dir(name, installer=installer)]
        for name in names:
            if name in ignored:
                continue
            full = os.path.join(directory, name)
            if os.path.isdir(full):
                continue
            if installer and _is_installer_junk(name):
                ignored.append(name)
                continue
            key = _rel_key(full, project_root)
            if _script_skips(skip_fn, key):
                ignored.append(name)
                continue
            if key in skip:
                ignored.append(name)
                continue
            if src_root and dst_root:
                dest_file = os.path.join(dst_root, os.path.relpath(full, src_root))
                if os.path.isfile(dest_file):
                    try:
                        if os.path.getmtime(full) == os.path.getmtime(dest_file):
                            ignored.append(name)
                    except OSError:
                        pass
        return ignored

    return ignore


def _copy_tree(src, dst, label, skip=None, project_root=None, installer=False, skip_fn=None):
    if not os.path.isdir(src):
        mineprep.panic(f'工程缺少源文件夹: {label}', src)
        return False
    ignore = _copy_ignore_with_skip(
        project_root or _project_root(), skip, installer=installer, skip_fn=skip_fn,
        src_root=src, dst_root=dst,
    )
    try:
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore)
    except Exception as err:
        mineprep.panic(f'复制失败: {label}', err)
        return False
    if not os.path.isdir(dst):
        mineprep.panic(f'复制后目标不存在: {label}', dst)
        return False
    return True


def _trash_dir(path):
    if not os.path.isdir(path):
        return True
    try:
        mineprep.send2trash(path)
    except Exception as extra:
        mineprep.panic(f'移至回收站失败: {path}', extra)
    if os.path.exists(path):
        mineprep.panic('文件夹仍存在，是否强制删除？', path)
        if os.path.exists(path):
            try:
                mineprep.send2trash(path, delete=True)
            except Exception as extra:
                mineprep.panic(f'强制删除仍失败: {path}', extra)
    return not os.path.exists(path)


def _copy_pairs(pairs, *, skip=None, installer=False, skip_fn=None):
    project = _project_root()
    for src, dst, label in pairs:
        if not os.path.isdir(src):
            if label in _REQUIRED:
                mineprep.panic(f'工程缺少源文件夹: {label}', src)
            else:
                mineprep.prints(mineprep.bilingual(
                    f'跳过（源工程没有）: {label}',
                    f'Skip (not in source): {label}',
                ))
            continue
        _copy_tree(
            src, dst, label, skip=skip, project_root=project,
            installer=installer, skip_fn=skip_fn,
        )


def _remove_extra_files(extra_props, dest_root, *, installer=False):
    for key in extra_to_remove(extra_props):
        path = dest_abs(key, dest_root, installer=installer)
        if not os.path.isfile(path):
            continue
        try:
            mineprep.send2trash(path)
        except Exception as extra:
            mineprep.panic(f'删除多余文件失败: {key}', extra)


def _sync_trees(props, filter_props, extra_props, dest_root, *, installer=False, skip_fn=None):
    pairs = _tree_pairs(dest_root, installer=installer)
    if getattr(props, 'ClearDest', False):
        for dst in _dest_tree_paths(dest_root, installer=installer):
            _trash_dir(dst)
        _copy_pairs(pairs, installer=installer, skip_fn=skip_fn)
        return
    _copy_pairs(
        pairs, skip=skipped_relpaths(filter_props), installer=installer, skip_fn=skip_fn,
    )
    _remove_extra_files(extra_props, dest_root, installer=installer)


def _has_uproject(folder):
    try:
        return any(name.endswith('.uproject') for name in os.listdir(folder))
    except OSError:
        return False


def path_warnings(props, *, require_uproject=False):
    """目标路径的提示：无效、无 uproject、非 ASCII。无问题时返回空字符串。"""
    folder = target_dir(props)
    notes = []
    if not folder or not os.path.isdir(folder):
        notes.append(mineprep.bilingual('路径无效', 'Path is invalid'))
    elif require_uproject and not _has_uproject(folder):
        notes.append(mineprep.bilingual('未找到 .uproject', '.uproject not found'))
    if folder and not all(ord(ch) < 128 for ch in folder):
        notes.append(mineprep.bilingual(
            '路径含有中文或非 ASCII 字符',
            'Path contains non-ASCII characters',
        ))
    return '\n'.join(str(note) for note in notes)


_UE_INI_COMMANDS = '+-!.@*^'
_UE_INI_SECTION = re.compile(r'^\s*\[(.+)\]\s*$')
_UE_INI_KV = re.compile(rf'^(\s*)([{re.escape(_UE_INI_COMMANDS)}])?(.+?)(\s*=\s*)(.*)$')


def _ue_ini_map(sections):
    out = {}
    for section, opts in (sections or {}).items():
        bucket = out.setdefault(section.casefold(), {'name': section, 'keys': {}})
        items = opts.items() if isinstance(opts, dict) else ((key, None) for key in opts)
        for key, value in items:
            bucket['keys'][key.casefold()] = (key, value)
    return out


def _patch_ue_ini_text(text, sets=None, removes=None):
    want, drop = _ue_ini_map(sets), _ue_ini_map(removes)
    nl = '\r\n' if '\r\n' in text else '\n'
    ended = text.endswith('\n') or text.endswith('\r\n')
    lines, out, i, seen = text.splitlines(), [], 0, set()

    def append_remaining(sec_cf):
        bucket = want.get(sec_cf)
        if not bucket:
            return
        for orig_key, value in bucket['keys'].values():
            if value is not None:
                out.append(f'{orig_key}={value}')
        bucket['keys'].clear()

    while i < len(lines):
        line = lines[i]
        header = _UE_INI_SECTION.match(line)
        if not header:
            out.append(line)
            i += 1
            continue
        name = header.group(1)
        sec_cf = name.casefold()
        seen.add(sec_cf)
        out.append(line)
        i += 1
        while i < len(lines) and not _UE_INI_SECTION.match(lines[i]):
            line = lines[i]
            parsed = None
            if line.strip() and not line.lstrip().startswith(';'):
                parsed = _UE_INI_KV.match(line)
            if parsed is None:
                out.append(line)
                i += 1
                continue
            indent, cmd, key, eq, value = parsed.groups()
            cmd, key = cmd or '', key.rstrip()
            key_cf = key.casefold()
            if key_cf in drop.get(sec_cf, {}).get('keys', {}):
                i += 1
                continue
            bucket = want.get(sec_cf)
            if bucket and not cmd and key_cf in bucket['keys']:
                _, new_value = bucket['keys'].pop(key_cf)
                out.append(f'{indent}{cmd}{key}{eq}{new_value}')
                i += 1
                continue
            out.append(line)
            i += 1
        append_remaining(sec_cf)

    missing = [want[k] for k in want if k not in seen and want[k]['keys']]
    if missing:
        if out and out[-1].strip():
            out.append('')
        for bucket in missing:
            out.append(f'[{bucket["name"]}]')
            append_remaining(bucket['name'].casefold())
    body = nl.join(out)
    if ended or text == '' or missing:
        return body + nl
    return body


def _patch_ini(file_path, sections, removes=None):
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding='utf-8') if path.exists() else ''
    path.write_text(_patch_ue_ini_text(text, sections, removes), encoding='utf-8')
    return path


def _setting(key, default=''):
    try:
        value = mineprep.config['Settings'][key]
        return default if value is None else value
    except Exception:
        return default


def _write_project_ini(dest_root):
    ffmpeg = str(_setting('ffmpeg_path') or '').strip()
    cli = {}
    if ffmpeg:
        cli['ExecutablePath'] = f'"{os.path.normpath(ffmpeg)}"'
    cli.update({
        'VideoCodec': 'libx265',
        'AudioCodec': 'aac',
        'OutputFileExtension': 'mp4',
        'CommandLineFormat': r'"-hide_banner -y -loglevel error {AdditionalLocalArgs}"',
    })
    _patch_ini(os.path.join(dest_root, 'Config', 'DefaultEngine.ini'), {
        '/Script/MovieRenderPipelineCore.MoviePipelineCommandLineEncoderSettings': cli,
        '/Script/Engine.RendererSettings': {
            'r.DefaultFeature.AutoExposure': 'False',
            'r.RayTracing': 'True',
            'r.RayTracing.Shadows': 'True',
            'r.Lumen.HardwareRayTracing': 'True',
            'r.AllowStaticLighting': 'False',
            'r.CustomDepth': '3',
            'r.PostProcessing.PropagateAlpha': 'True',
            'r.Deferred.SupportPrimitiveAlphaHoldout': 'True',
            'r.SkinCache.SceneMemoryLimitInMB': '1024.0',
            'rhi.Bindless.Resources': 'Enabled',
            'rhi.Bindless.Samplers': 'Enabled',
            'rhi.Bindless': 'Enabled',
            'r.Translucency.HeterogeneousVolumes': 'True',
            'r.Substrate': 'True',
            'r.GenerateMeshDistanceFields': 'True',
        },
        '/Script/Engine.GarbageCollectionSettings': {
            'gc.AssetClustreringEnabled': 'True',
            'gc.ActorClusteringEnabled': 'True',
        },
        '/Script/Engine.Engine': {
            'GenerateDefaultTimecodeFrameRate': '(Numerator=60,Denominator=1)',
        },
        '/Script/WaterAdvanced.ShallowWaterSettings': {
            'UseDefaultShallowWaterSubsystem': 'True',
            'ShallowWaterSimParameters': '(WorldGridSize=5000,ResolutionMaxAxis=768)',
        },
        '/Script/DLSS.DLSSSettings': {
            'bEnableDLSSInEditorViewports': 'True',
            'bEnableDLSSInPlayInEditorViewports': 'True',
        },
        '/Script/PythonScriptPlugin.PythonScriptPluginSettings': {
            'bRemoteExecution': 'True',
        },
    }, removes={
        '/Script/DLSS.DLSSSettings': ['bEnableDLSSInEditorViewport'],
    })
    _patch_ini(os.path.join(dest_root, 'Config', 'DefaultInput.ini'), {
        '/Script/EnhancedInput.EnhancedInputDeveloperSettings': {
            'bEnableUserSettings': 'True',
        },
    })
    _patch_ini(os.path.join(dest_root, 'Config', 'DefaultEditor.ini'), {
        '/Script/UnrealEd.BlueprintEditorProjectSettings': {
            'bAllowImpureToPureNodeConversion': 'True',
        },
    })
    _patch_ini(os.path.join(dest_root, 'Config', 'DefaultEditorSettings.ini'), {
        '/Script/UnrealEd.EditorPerformanceSettings': {
            'bShowFrameRateAndMemory': 'True',
        },
    })
    _patch_ini(os.path.join(dest_root, 'Config', 'DefaultEditorPerProjectUserSettings.ini'), {
        '/Script/UnrealEd.EditorLoadingSavingSettings': {
            'LoadLevelAtStartup': 'LastOpened',
        },
        '/Script/AvalancheEditor.AvaEditorSettings': {
            'bAutoActivateMotionDesignViewport': 'False',
        },
    })
    _patch_ini(os.path.join(dest_root, 'Config', 'Windows', 'WindowsEngine.ini'), {
        'ShaderPlatformConfig PCD3D_SM6': {
            'BindlessConfiguration': 'Minimal',
        },
    })


def _run_installer_script(installer):
    script = os.path.join(installer, 'Readme素材', '自动化处理脚本.py')
    if not os.path.isfile(script):
        mineprep.panic('找不到自动化处理脚本', script)
    if os.path.isfile(script):
        try:
            runpy.run_path(script, run_name='__main__')
        except Exception as extra:
            mineprep.panic('自动化处理脚本失败', extra)


def update_installer(props, filter_props=None, extra_props=None, script_props=None):
    """出问题会 panic，用户选「是」则继续下一步，「否」则中止。"""
    installer = target_dir(props) or installer_dir()
    try:
        assert os.path.isdir(installer), f'安装包路径{installer}不存在'
    except Exception as extra:
        mineprep.panic('安装包路径不存在', extra)
        return ''

    dest_content = os.path.join(installer, 'Mineprep')
    dest_plugin = os.path.join(installer, '实验性功能(C++)', 'Mineprep')
    for label, path in (
        ('installer_dir/Mineprep', dest_content),
        ('installer_dir/实验性功能(C++)/Mineprep', dest_plugin),
    ):
        if not os.path.isdir(path):
            mineprep.panic(f'仓库缺少 {label}', path)

    skip_fn = load_skip_fn(script_props)
    if not confirm_copy(props, filter_props, extra_props, skip_fn=skip_fn):
        return ''

    _sync_trees(
        props, filter_props, extra_props, installer,
        installer=True, skip_fn=skip_fn,
    )
    if getattr(props, 'RunScript', True):
        _run_installer_script(installer)
    mineprep.prints(f'已更新{installer}')
    return installer


def _copy_python_libs(dest):
    src = os.path.join(_project_root(), *_PIP_LIB.split('/'))
    dst = os.path.join(dest, *_PIP_LIB.split('/'))
    if not os.path.isdir(src):
        mineprep.panic('找不到 Python 库', src)
        return False
    try:
        shutil.copytree(src, dst, dirs_exist_ok=True)
    except Exception as extra:
        mineprep.panic('复制 Python 库失败', extra)
        return False
    return True


def migrate_plugin(props, filter_props=None, extra_props=None, script_props=None):
    """把当前工程的 Mineprep 与实验性插件复制到另一个工程，并写入 ini。"""
    dest = target_dir(props)
    try:
        assert dest and os.path.isdir(dest), f'目标文件夹{dest}不存在'
    except Exception as extra:
        mineprep.panic('目标文件夹不存在', extra)
        return ''
    if not _has_uproject(dest):
        mineprep.panic(
            mineprep.bilingual('未找到 .uproject，请选择工程根目录', 'No .uproject found; pick the project root'),
            dest,
        )
        if not _has_uproject(dest):
            return ''

    src_root = _project_root()
    if os.path.normcase(os.path.normpath(dest)) == os.path.normcase(os.path.normpath(src_root)):
        mineprep.panic(
            mineprep.bilingual('不能迁移到当前工程', 'Cannot migrate onto the current project'),
            dest,
        )
        return ''

    skip_fn = load_skip_fn(script_props)
    if not confirm_copy(props, filter_props, extra_props, skip_fn=skip_fn):
        return ''

    _sync_trees(
        props, filter_props, extra_props, dest,
        installer=False, skip_fn=skip_fn,
    )
    if getattr(props, 'CopyPythonLib', False):
        _copy_python_libs(dest)
    _write_project_ini(dest)
    mineprep.prints(mineprep.bilingual(f'已迁移到 {dest}，务必要先关闭当前工程，再打开新工程文件',
                    f'Migrated to {dest}. Close the current project first and then open the new project.'))
    return dest
