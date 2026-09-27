"""安装/卸载模组；文件选择、确认和面板刷新由调用方负责。"""
import importlib
import keyword
import shutil
import sys
import zipfile
from pathlib import Path

import mineprep
from mc_mod import unregister_mod

MODS_DIR = Path(__file__).resolve().parent.parent


def _stem(name):
    name = str(name).removeprefix('mods.')
    if not name.isidentifier() or keyword.iskeyword(name) or name == '__init__':
        raise ValueError(f'无效模组名: {name}')
    return name


def _target(root, relative):
    parts = str(relative).replace('\\', '/').split('/')
    if any(p in ('', '.', '..') or ':' in p or p.endswith((' ', '.')) for p in parts):
        raise ValueError(f'无效相对路径: {relative}')
    target = root.joinpath(*parts).resolve()
    if not target.is_relative_to(root) or target == root or target != root.joinpath(*parts):
        raise ValueError(f'路径超出模组目录: {relative}')
    return target


def install_mod(path, *, mods_dir=MODS_DIR, overwrite=False):
    """安装 .py 或 .zip；默认拒绝同名覆盖，不导入或启用模组。"""
    src, root = Path(path).resolve(), Path(mods_dir).resolve()
    if not src.is_file():
        raise FileNotFoundError(src)
    archive = zipfile.ZipFile(src) if src.suffix.lower() == '.zip' else None
    try:
        if archive:
            entries = [(i.filename.rstrip('/'), i) for i in archive.infolist()]
        elif src.suffix.lower() == '.py':
            entries = [(src.name, None)]
        else:
            raise ValueError(f'不支持的文件类型: {src.suffix}')
        if not entries:
            raise ValueError('压缩包为空')
        targets, names = [], set()
        for relative, info in entries:
            target = _target(root, relative)
            top = relative.replace('\\', '/').split('/')[0]
            names.add(_stem(top[:-3] if top.endswith('.py') else top))
            if info and (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f'不支持压缩包符号链接: {relative}')
            if target == src:
                raise ValueError('安装源与目标相同')
            targets.append((target, info))
        conflicts = [name for name in sorted(names)
                     if (root / name).exists() or (root / (name + '.py')).exists()]
        if conflicts and not overwrite:
            raise FileExistsError('同名模组已存在: ' + ', '.join(conflicts))
        # 校验完整个压缩包后才写文件；overwrite 保留原先的合并覆盖行为。
        written = []
        for target, info in targets:
            if info and info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if archive:
                with archive.open(info) as source, target.open('wb') as dest:
                    shutil.copyfileobj(source, dest)
            else:
                shutil.copy2(src, target)
            written.append(str(target))
        importlib.invalidate_caches()
        return dict(modules=['mods.' + n for n in sorted(names)], paths=written,
                    overwritten=conflicts)
    finally:
        if archive:
            archive.close()


def uninstall_mod(name, *, mods_dir=MODS_DIR):
    """注销并移除模组；移除失败抛异常，保留模块缓存供诊断。"""
    stem, root = _stem(name), Path(mods_dir).resolve()
    module_name = 'mods.' + stem
    candidates = [_target(root, stem + '.py'), _target(root, stem)]
    existing = [p for p in candidates if p.exists()]
    if len(existing) != 1:
        raise ValueError(f'需有唯一的模组文件或目录: {stem}')
    target = existing[0]
    mod = sys.modules.get(module_name)
    if mod:
        module_file = Path(mod.__file__).resolve()
        if module_file != target and not (target.is_dir() and module_file.is_relative_to(target)):
            raise ValueError('已加载模组与待卸载路径不一致')
        if not unregister_mod(mod):
            raise RuntimeError(f'注销模组失败，未移除文件: {module_name}')
    mineprep.send2trash(target)
    if target.exists():
        raise OSError(f'未能移除模组: {target}')
    for key in list(sys.modules):
        if key == module_name or key.startswith(module_name + '.'):
            sys.modules.pop(key, None)
    parent = sys.modules.get('mods')
    if parent and mod is not None and getattr(parent, stem, None) is mod:
        delattr(parent, stem)
    importlib.invalidate_caches()
    return dict(module=module_name, path=str(target), removed=True)
