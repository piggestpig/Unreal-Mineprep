"""扫描资产、按 Key 合并变量显示名 CSV，并抽出待翻译行。"""
from __future__ import annotations

import csv
import os
import tempfile

import unreal
import mineprep

HEADER = ['Namespace', 'Key', 'Source String', 'zh-Hans', 'en', 'zh-Hant']
NS = 'UObjectDisplayNames'
OLD_NAME = '变量显示名_VariableDisplayNames.csv'
NEW_NAME = '新变量显示名_VariableDisplayNames.csv'
TODO_NAME = '待翻译_Untranslated.csv'
_KIND_NAMES = frozenset({
    'Blueprint',
    'EditorUtilityBlueprint',
    'WidgetBlueprint',
    'AnimBlueprint',
    'UserDefinedStruct',
    'UserDefinedEnum',
    'MaterialInstanceConstant',
    'NiagaraSystem',
})
_SKIP_CLASSES = frozenset({
    'ControlRigBlueprint',
})


def tr(zh, en):
    return mineprep.bilingual(zh, en)


def csv_dir() -> str:
    root = os.path.abspath(unreal.SystemLibrary.get_project_directory())
    return os.path.join(root, 'Content', 'Mineprep', '插件贴图')


def csv_paths() -> dict:
    folder = csv_dir()
    return {
        'folder': folder,
        'old': os.path.join(folder, OLD_NAME),
        'new': os.path.join(folder, NEW_NAME),
        'todo': os.path.join(folder, TODO_NAME),
    }


def open_csv_folder():
    folder = csv_dir()
    os.makedirs(folder, exist_ok=True)
    mineprep.startfile(folder)
    return folder


PROMPT_TEMPLATE = """请翻译虚幻引擎插件（Minecraft风格）的变量显示名，要求用词简短、地道，符合 UE 和 Minecraft 的使用习惯。

### 1. 文件与列定义
- **本地化表**：`{old_csv}`
- **临时工作表**：`{new_csv}`
- **待翻译表**：`{todo_csv}`（从工作表中提取的任一语言列为空的行）
- **列顺序（固定）**：`Namespace, Key, Source String, zh-Hans, en, zh-Hant`

### 2. 基本原则
- **严禁修改前三列**：`Namespace`、`Key`、`Source String` 必须保持原样（包括空格、大小写及特殊符号，源自引擎 `FName::NameToDisplayString`）。
- **严禁改动文件结构**：不得增减列、修改列名、新建文件或改动已有列顺序。
- **补全空白列**：只针对 `zh-Hans`、`en`、`zh-Hant` 等空白单元格翻译，已有译文若有明显错译也可改动。

### 3. 翻译规范
- **上下文对齐**：先参考工作表中已有译文对齐风格后再翻译。全表同类概念尽可能统一。
- **英文 (`en`)**：使用简短 Title Case，符合 UE 引擎习惯（如 Camera, Post Process, Skeleton, Material, Niagara, Sequencer）；专有名词/缩写保留原样（如 DLSS, FSR, Actor, Debug, CSV, RT）。
- **格式保留**：
  - `/` 连接的并列项逐段翻译并保留 `/`（如 `待机/走路/跑步` → `Idle/Walk/Run`）。
  - 括号内的单位和类型提示原样保留，如 `(m)`, `(m/s)`, `(Actor)`, `(类)`。

### 4. 执行流程
- 请自己生成/填充**临时工作表**的翻译内容（不要写机械的脚本进行批量翻译）。
- 翻译完成后，把原始**本地化表**移至回收站，**临时工作表**重命名为“变量显示名_VariableDisplayNames.csv”，成为新的本地化表，最后把临时工作表和待翻译表也移至回收站

Token 足够，条目多时可以开多个子agent"""


def make_prompt() -> str:
    paths = csv_paths()
    return PROMPT_TEMPLATE.format(
        old_csv=paths['old'],
        new_csv=paths['new'],
        todo_csv=paths['todo'],
    )


def _has_cjk(text: str) -> bool:
    return any('\u4e00' <= ch <= '\u9fff' for ch in text)


def _pad_row(row) -> list[str]:
    cells = [str(c) if c is not None else '' for c in row]
    if len(cells) < 6:
        cells.extend([''] * (6 - len(cells)))
    return cells[:6]


def _read_csv(path: str) -> list[list[str]]:
    if not os.path.isfile(path):
        return []
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    if not rows:
        return []
    body = rows[1:] if rows[0] and rows[0][0] == HEADER[0] else rows
    out = []
    for row in body:
        if len(row) < 3:
            continue
        key = str(row[1]).strip()
        if not key:
            continue
        out.append(_pad_row(row))
    return out


def _index_by_key(rows: list[list[str]]) -> dict[str, list[str]]:
    by_key = {}
    for row in rows:
        key = row[1]
        if key not in by_key:
            by_key[key] = row
    return by_key


def _write_csv(path: str, rows: list[list[str]]):
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='loc_', suffix='.csv', dir=folder, text=True)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(HEADER)
            writer.writerows(rows)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def load_working() -> dict[str, list[str]]:
    paths = csv_paths()
    new_rows = _read_csv(paths['new'])
    old_rows = _read_csv(paths['old'])
    old_by_key = _index_by_key(old_rows)
    if new_rows:
        working = _index_by_key(new_rows)
        for key, old in old_by_key.items():
            if key not in working:
                continue
            row = working[key]
            for i in (3, 4, 5):
                if not str(row[i]).strip() and str(old[i]).strip():
                    row[i] = old[i]
        return working
    return _index_by_key(old_rows)


def merge_entry(working: dict[str, list[str]], old_by_key: dict[str, list[str]],
                key: str, source: str) -> str:
    """Update working table. Returns 'added' or 'reused'."""
    if key in working:
        working[key][2] = source
        return 'reused'
    if key in old_by_key:
        row = _pad_row(old_by_key[key])
        row[2] = source
        working[key] = row
        return 'reused'
    working[key] = [NS, key, source, '', '', '']
    return 'added'


def fill_chinese(working: dict[str, list[str]]):
    for row in working.values():
        source = str(row[2])
        if not str(row[3]).strip() and _has_cjk(source):
            row[3] = source


def untranslated_rows(working: dict[str, list[str]]) -> list[list[str]]:
    todo = []
    for row in working.values():
        if any(not str(row[i]).strip() for i in (3, 4, 5)):
            todo.append(row)
    return todo


def working_rows(working: dict[str, list[str]]) -> list[list[str]]:
    return list(working.values())


def write_tables(working: dict[str, list[str]], *, fill: bool) -> dict:
    if fill:
        fill_chinese(working)
    paths = csv_paths()
    rows = working_rows(working)
    todo = untranslated_rows(working)
    _write_csv(paths['new'], rows)
    _write_csv(paths['todo'], todo)
    return {
        'new_path': paths['new'],
        'todo_path': paths['todo'],
        'total': len(rows),
        'untranslated': len(todo),
    }


def refresh_todo() -> dict:
    paths = csv_paths()
    if not os.path.isfile(paths['new']) and not os.path.isfile(paths['old']):
        mineprep.throw(str(tr('找不到变量显示名 CSV', 'Variable display-name CSV not found')))
    working = load_working()
    stats = write_tables(working, fill=True)
    mineprep.prints(tr(
        f"已刷新待翻译表：{stats['untranslated']} / {stats['total']} 行",
        f"Refreshed untranslated table: {stats['untranslated']} / {stats['total']} rows",
    ))
    return stats


def _wanted_asset(asset_data) -> bool:
    name = str(getattr(asset_data.asset_class_path, 'asset_name', '') or '')
    if name in _SKIP_CLASSES:
        return False
    return name in _KIND_NAMES or name.endswith('Blueprint')


def list_scan_assets(scan_path: str) -> list[str]:
    folder = (scan_path or '').strip().rstrip('/')
    if not folder:
        mineprep.throw(str(tr('扫描路径为空', 'Scan path is empty')))
    if not folder.startswith('/'):
        folder = '/' + folder
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    assets = registry.get_assets_by_path(folder, recursive=True) or []
    paths = []
    seen = set()
    for data in assets:
        if not _wanted_asset(data):
            continue
        package = str(data.package_name)
        if not package or package in seen:
            continue
        seen.add(package)
        paths.append(package)
    return paths


def has_cpp_gather() -> bool:
    return bool(
        hasattr(unreal, 'mineprep')
        and hasattr(unreal.mineprep, 'gather_property_names')
    )


def gather_names(obj, set_enum_key: bool) -> tuple[list[str], list[str], list[str]]:
    result = unreal.mineprep.gather_property_names(obj, bool(set_enum_key))
    if result is None:
        return [], [], []
    kinds, keys, names = result
    return [str(x) for x in kinds], [str(x) for x in keys], [str(x) for x in names]


def iter_gather(props, on_status, is_closed, out=None):
    """Yield 0 each asset so asynctask can cancel. Calls on_status(text).

    ``out`` is filled with the same stats dict so cancel (GeneratorExit) can
    still report after ``yield from`` is aborted.
    """
    if not has_cpp_gather():
        mineprep.throw(str(tr(
            '未找到 C++ 函数 unreal.mineprep.gather_property_names',
            'C++ function unreal.mineprep.gather_property_names not found',
        )))
    scan_path = str(getattr(props, 'ScanPath', '') or '')
    assets = list_scan_assets(scan_path)
    old_by_key = _index_by_key(_read_csv(csv_paths()['old']))
    working = load_working()
    added = reused = scanned = failed = 0
    total = len(assets)
    set_enum_key = bool(getattr(props, 'SetEnumKey', True))
    committed = False

    def commit(cancelled):
        nonlocal committed
        stats = write_tables(working, fill=True)
        stats.update(
            added=added, reused=reused, scanned=scanned, failed=failed,
            cancelled=cancelled)
        if out is not None:
            out.clear()
            out.update(stats)
        committed = True
        return stats

    try:
        if not total:
            on_status(str(tr('没有可扫描的资产', 'No matching assets to scan')))
            return commit(False)

        for i, path in enumerate(assets):
            if is_closed():
                scanned = i
                return commit(True)
            on_status(str(tr(
                f'收集中 {i + 1}/{total}  新增 {added}  复用 {reused}  失败 {failed}\n{path}',
                f'Gathering {i + 1}/{total}  added {added}  reused {reused}  failed {failed}\n{path}',
            )))
            try:
                obj = unreal.EditorAssetLibrary.load_asset(path)
                if obj:
                    _types, keys, names = gather_names(obj, set_enum_key)
                    for key, name in zip(keys, names):
                        key = (key or '').strip()
                        if not key:
                            continue
                        kind = merge_entry(working, old_by_key, key, name)
                        if kind == 'added':
                            added += 1
                        else:
                            reused += 1
            except Exception as exc:
                failed += 1
                mineprep.warn(f'LocalizationBoard {path}', exc)
            scanned = i + 1
            yield

        return commit(False)
    except GeneratorExit:
        if not committed and not is_closed():
            commit(True)
        raise
