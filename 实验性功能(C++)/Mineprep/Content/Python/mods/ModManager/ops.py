"""模组的安装、卸载与打包操作。"""
import importlib
import keyword
import shutil
import sys
import tempfile
import os
import zipfile
from pathlib import Path

import mineprep
from mc_mod import unregister_mod, MANIFEST_NAME, read_manifest, PathPatternMatch

MODS_DIR = Path(__file__).resolve().parent.parent
SKIP_DIRS = {'.git', '.hg', '.svn', '__pycache__', '.pytest_cache'}


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


def package_mod(name, output, *, mods_dir=MODS_DIR, overwrite=False):
    """根据模组清单规则将模组打包为 .zip 压缩包。"""
    stem, root = _stem(name), Path(mods_dir).resolve()
    candidates = [_target(root, stem + '.py'), _target(root, stem)]
    existing = [p for p in candidates if p.exists()]
    if len(existing) != 1:
        raise ValueError(f'需有唯一的模组文件或目录: {stem}')
    source, output = existing[0], Path(output).absolute()
    if output.suffix.lower() != '.zip':
        raise ValueError('输出文件须为 .zip')
    if output.is_symlink() or output.resolve() != output:
        raise ValueError(f'输出路径包含链接: {output}')
    if output.is_relative_to(source):
        raise ValueError('压缩包须保存在模组目录外')
    if output.exists() and not overwrite:
        raise FileExistsError(f'文件已存在: {output}')

    files = []
    if source.is_file():
        files.append((source, source.name))
    else:
        manifest_path = _target(source, MANIFEST_NAME)
        data = read_manifest(manifest_path)
        build = data.get('build', {}) if data is not None else {}
        matcher = PathPatternMatch(build.get('paths_exclude_pattern', []))

        def skipped(relative):
            return (bool(set(relative.parts) & SKIP_DIRS)
                    or relative.suffix.lower() in ('.pyc', '.pyo'))

        def scan(folder):
            for path in sorted(folder.iterdir()):
                relative = path.relative_to(source)
                if skipped(relative):
                    continue
                is_dir = path.is_dir()
                if matcher.test_path(relative.as_posix() + ('/' if is_dir else '')):
                    continue
                path = _target(source, relative.as_posix())
                if is_dir:
                    scan(path)
                elif path.is_file():
                    files.append((path, stem + '/' + relative.as_posix()))

        if 'paths' in build:
            for relative in build['paths']:
                if skipped(Path(relative)):
                    continue
                path = _target(source, relative)
                if not path.is_file():
                    raise ValueError(f'paths 须列出已有文件，不展开目录或通配符: {relative}')
                files.append((path, stem + '/' + relative))
        else:
            scan(source)
        if data is not None:
            files.append((manifest_path, stem + '/' + MANIFEST_NAME))
        if not any(path == source / '__init__.py' for path, _ in files):
            raise ValueError('打包结果缺少 __init__.py，请检查构建规则')

    unique = {}
    for path, relative in files:
        key = relative.casefold()
        if key in unique and unique[key][0] != path:
            raise ValueError(f'压缩包路径重名: {relative}')
        unique[key] = (path, relative)
    files = sorted(unique.values(), key=lambda item: item[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=output.stem + '.', suffix='.tmp', delete=False) as f:
            temporary = Path(f.name)
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path, relative in files:
                archive.write(path, relative)
        # 未开启覆盖时先独占创建目标文件，防止覆盖已有文件
        reserved = False
        try:
            if not overwrite:
                with output.open('xb'):
                    reserved = True
            os.replace(temporary, output)
        except OSError:
            if reserved:
                output.unlink()
            raise
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return dict(path=str(output), files=[relative for _, relative in files],
                source_bytes=sum(path.stat().st_size for path, _ in files), archive_bytes=output.stat().st_size)


def install_mod(path, *, mods_dir=MODS_DIR, overwrite=False):
    """从 .py 或 .zip 安装模组到 mods 目录（默认不覆盖同名模组）。"""
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
        # 全部条目校验通过后再解压写入文件
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
    """注销模组并将其文件移至回收站，同时清理已加载的模块缓存。"""
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
