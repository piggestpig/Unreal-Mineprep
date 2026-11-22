"""Minecraft 方块与物品的本地化查询模块。

依据当前资源包目录扫描可用资源，结合 ``i18n_inventory.json`` 提供四语显示名、
标签筛选与多关键词搜索，可在 UE 编辑器外独立运行；``unreal.Text`` 注册按需在
主线程批量完成。

调用示例::

    from mineprep import inventory

    entries = inventory.search_blocks("金合欢 打开", search_all=False, tag_filter={2: 1})
    ids = [entry.id for entry in entries]
    names = [entry.name for entry in entries]

    item = inventory.get_entry("Items", "minecraft:music_disc_13")
"""

from __future__ import annotations

try:
    import unreal
except ModuleNotFoundError:
    from mineprep.utils import Lazy as unreal

from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path
import pickle

import mcvars
from mineprep.localization import Internationalization

INVENTORY_FILE = Path(__file__).with_name("i18n_inventory.json")
LANGUAGES = ("zh", "en", "zh-Hant", "zh-Hant-HK")
NAMESPACES = ("Blocks", "Items")
TAG_MAP = {
    1: "👤",
    2: "🟩",
    3: "🟥",
    4: "🟨",
    5: "🌊",
    6: "📸",
    7: "💡",
    8: "👪",
    9: "✨",
    10: "🧱",
    11: "𝓕",
    12: "🔧",
}

_ACRONYMS = frozenset({"tnt", "uv", "gui", "hud"})
_TRANSLATORS: dict[str, Internationalization] = {}
_SENTINEL = object()


@dataclass(frozen=True, slots=True)
class InventoryEntry:
    """单个可用方块或物品的查询结果。"""

    id: str
    stem: str
    name: str
    tags: str
    translations: dict[str, str]


@dataclass(frozen=True, slots=True)
class _RawEntry:
    """内部预计算条目，用于当前目录扫描结果与快速过滤。"""

    id: str
    stem: str
    tags: str
    tag_chars: frozenset[str]
    translations: dict[str, str]
    id_search: str
    lang_search: dict[str, str]
    all_search: str


def _normalize_category(category: str) -> str:
    value = str(category).strip().casefold()
    if value in ("blocks", "block"):
        return "Blocks"
    if value in ("items", "item"):
        return "Items"
    raise ValueError(f"Unsupported inventory category: {category!r}")


def _normalize_id(entry_id: str) -> str:
    value = str(entry_id).strip().casefold()
    if not value:
        return ""
    return value if ":" in value else f"minecraft:{value}"


def _normalize_text(value: str) -> str:
    """规范化搜索字符串：同时保留下划线形式与空格拆词形式。"""
    lowered = " ".join(str(value).casefold().split())
    if "_" not in lowered:
        return lowered
    spaced = " ".join(lowered.replace("_", " ").split())
    return f"{lowered} {spaced}"


def _normalize_tokens(query: str) -> tuple[str, ...]:
    if not query:
        return ()
    return tuple(str(query).casefold().split())


def _fallback_english_name(stem: str) -> str:
    words = []
    for part in stem.replace("/", " / ").replace("_", " ").split():
        if part in _ACRONYMS:
            words.append(part.upper())
        elif part == "/":
            words.append("/")
        else:
            words.append(part.capitalize())
    return " ".join(words) or stem


def _fallback_culture(culture: str | None) -> str:
    if not culture:
        return "zh"
    normalized = str(culture).replace("_", "-").casefold()
    if normalized in ("zh-hant-hk", "zh-hk", "zh-mo"):
        return "zh-Hant-HK"
    if normalized.startswith("zh-hant") or normalized in ("zh-tw",):
        return "zh-Hant"
    if normalized == "zh" or normalized.startswith("zh-hans") or normalized in ("zh-cn", "zh-sg"):
        return "zh"
    if normalized == "en" or normalized.startswith("en-"):
        return "en"
    return "en"


def get_language(lang: str | None = None) -> str:
    """解析当前或指定的语言代码，回退至 LANGUAGES 之一。"""
    if lang is not None:
        return _fallback_culture(lang)
    lib = getattr(unreal, "InternationalizationLibrary", None)
    get_current = getattr(lib, "get_current_language", None)
    if callable(get_current):
        current = get_current()
        if isinstance(current, str) and current:
            suitable = getattr(lib, "get_suitable_culture", None)
            if callable(suitable):
                matched = suitable(list(LANGUAGES), current, "en")
                if isinstance(matched, str) and matched in LANGUAGES:
                    return matched
            return _fallback_culture(current)
    return "zh"


def _resolve_translation(translations: dict[str, str], lang: str, fallback: str) -> str:
    if translations.get(lang):
        return translations[lang]
    if lang == "zh-Hant-HK" and translations.get("zh-Hant"):
        return translations["zh-Hant"]
    if lang.startswith("zh") and translations.get("zh"):
        return translations["zh"]
    if translations.get("en"):
        return translations["en"]
    return translations.get("zh") or fallback


def _build_raw_entry(entry_id: str, stem: str, record: dict | None) -> _RawEntry:
    if record is None:
        fallback = _fallback_english_name(stem)
        translations = dict.fromkeys(LANGUAGES, fallback)
        tags = ""
    else:
        fallback = record.get("en") or record.get("zh") or _fallback_english_name(stem)
        translations = {
            lang: _resolve_translation(record, lang, fallback)
            for lang in LANGUAGES
        }
        tags = str(record.get("_tags", ""))

    id_search = _normalize_text(f"{entry_id} {stem}")
    lang_search = {lang: _normalize_text(translations[lang]) for lang in LANGUAGES}
    all_search = " ".join(lang_search.values())
    return _RawEntry(
        id=entry_id,
        stem=stem,
        tags=tags,
        tag_chars=frozenset(tags),
        translations=translations,
        id_search=id_search,
        lang_search=lang_search,
        all_search=all_search,
    )


@lru_cache(maxsize=1)
def _load_catalog() -> dict[str, dict[str, _RawEntry]]:
    if not INVENTORY_FILE.is_file():
        return {ns: {} for ns in NAMESPACES}
    data = json.loads(INVENTORY_FILE.read_text(encoding="utf-8-sig"))
    catalog: dict[str, dict[str, _RawEntry]] = {}
    for ns in NAMESPACES:
        raw_ns = data.get(ns, {})
        Internationalization._validate(raw_ns)
        entries: dict[str, _RawEntry] = {}
        for entry_id, record in raw_ns.items():
            stem = entry_id.split(":", 1)[-1]
            entries[entry_id] = _build_raw_entry(entry_id, stem, record)
        catalog[ns] = entries
    return catalog


def _resolve_pack_dir(category: str, assets_dir: str | os.PathLike | None) -> Path | None:
    if assets_dir is None:
        from mineprep.settings import paths

        base = str(paths.assets or "").strip()
    else:
        base = str(assets_dir).strip()
    if not base:
        return None
    if category == "Blocks":
        return Path(base) / "minecraft" / "models" / "block"
    return Path(base) / "minecraft" / "textures" / "item"


@lru_cache(maxsize=None)
def _fallback_raw_entry(stem: str) -> _RawEntry:
    return _build_raw_entry(f"minecraft:{stem}", stem, None)


def _scan_pack(category: str, assets_dir: str | os.PathLike | None) -> tuple[_RawEntry, ...]:
    target_dir = _resolve_pack_dir(category, assets_dir)
    if target_dir is None or not target_dir.is_dir():
        return ()

    suffix = ".json" if category == "Blocks" else ".png"
    present_stems: set[str] = set()
    with os.scandir(target_dir) as it:
        for entry in it:
            if entry.is_file() and entry.name.lower().endswith(suffix):
                present_stems.add(entry.name[: -len(suffix)])

    known = _load_catalog()[category]
    ordered: list[_RawEntry] = []
    seen: set[str] = set()
    for raw_entry in known.values():
        if raw_entry.stem in present_stems:
            ordered.append(raw_entry)
            seen.add(raw_entry.stem)

    for stem in sorted(present_stems - seen):
        ordered.append(_fallback_raw_entry(stem))

    return tuple(ordered)


def _parse_tag_filter(tag_filter: dict | None) -> tuple[frozenset[str], frozenset[str]]:
    if not tag_filter:
        return frozenset(), frozenset()
    includes: set[str] = set()
    excludes: set[str] = set()
    for key, mode in tag_filter.items():
        if not mode:
            continue
        if isinstance(key, int):
            if key not in TAG_MAP:
                raise KeyError(f"Unknown tag index: {key!r}")
            tag_char = TAG_MAP[key]
        else:
            tag_char = str(key)
        if mode == 1:
            includes.add(tag_char)
        elif mode == -1:
            excludes.add(tag_char)
    return frozenset(includes), frozenset(excludes)


def _to_public_entry(raw: _RawEntry, lang: str) -> InventoryEntry:
    return InventoryEntry(
        id=raw.id,
        stem=raw.stem,
        name=raw.translations[lang],
        tags=raw.tags,
        translations=dict(raw.translations),
    )


def search_inventory(
    category: str,
    query: str = "",
    *,
    search_all: bool = False,
    tag_filter: dict | None = None,
    lang: str | None = None,
    assets_dir: str | os.PathLike | None = None,
) -> list[InventoryEntry]:
    """按名称、全语言开关及标签条件筛选当前资源包的方块或物品。"""
    ns = _normalize_category(category)
    active_lang = get_language(lang)
    tokens = _normalize_tokens(query)
    includes, excludes = _parse_tag_filter(tag_filter)

    results: list[InventoryEntry] = []
    for raw in _scan_pack(ns, assets_dir):
        if includes and not (includes <= raw.tag_chars):
            continue
        if excludes and not excludes.isdisjoint(raw.tag_chars):
            continue
        if tokens:
            name_haystack = raw.all_search if search_all else raw.lang_search[active_lang]
            haystack = f"{raw.id_search} {name_haystack}"
            if not all(token in haystack for token in tokens):
                continue
        results.append(_to_public_entry(raw, active_lang))
    return results


def search_blocks(
    query: str = "",
    *,
    search_all: bool = False,
    tag_filter: dict | None = None,
    lang: str | None = None,
    assets_dir: str | os.PathLike | None = None,
) -> list[InventoryEntry]:
    """查询当前资源包可用方块模型（``models/block/*.json``）。"""
    return search_inventory(
        "Blocks",
        query,
        search_all=search_all,
        tag_filter=tag_filter,
        lang=lang,
        assets_dir=assets_dir,
    )


def search_items(
    query: str = "",
    *,
    search_all: bool = False,
    tag_filter: dict | None = None,
    lang: str | None = None,
    assets_dir: str | os.PathLike | None = None,
) -> list[InventoryEntry]:
    """查询当前资源包可用物品贴图（``textures/item/*.png``）。"""
    return search_inventory(
        "Items",
        query,
        search_all=search_all,
        tag_filter=tag_filter,
        lang=lang,
        assets_dir=assets_dir,
    )


def get_entry(
    category: str,
    entry_id: str,
    *,
    lang: str | None = None,
    assets_dir: str | os.PathLike | None = None,
) -> InventoryEntry | None:
    """按 canonical ID 或文件原名取当前资源包中的对应条目。"""
    ns = _normalize_category(category)
    target_id = _normalize_id(entry_id)
    if not target_id:
        return None
    active_lang = get_language(lang)
    for raw in _scan_pack(ns, assets_dir):
        if raw.id == target_id:
            return _to_public_entry(raw, active_lang)
    return None


def register_texts(category: str | None = None) -> dict[str, Internationalization]:
    """在 UE 主线程按需批量注册 ``i18n_inventory.json`` 到 PolyglotTextData。"""
    targets = NAMESPACES if category is None else (_normalize_category(category),)
    if not unreal:
        return {}
    catalog = _load_catalog()
    for ns in targets:
        if ns in _TRANSLATORS:
            continue
        records = {
            entry_id: dict(raw.translations)
            for entry_id, raw in catalog[ns].items()
        }
        _TRANSLATORS[ns] = Internationalization.from_data(records, namespace=f"Inventory.{ns}")
    return {ns: _TRANSLATORS[ns] for ns in targets}


def get_text(
    category: str,
    entry_id: str,
    *,
    lang: str | None = None,
    assets_dir: str | os.PathLike | None = _SENTINEL,
):
    """返回指定条目的 ``unreal.Text``；离线环境返回本地化字符串回退。"""
    ns = _normalize_category(category)
    target_id = _normalize_id(entry_id)
    if not unreal:
        active_lang = get_language(lang)
        raw = _load_catalog()[ns].get(target_id)
        if raw is not None:
            return raw.translations[active_lang]
        if assets_dir is not _SENTINEL:
            found = get_entry(ns, target_id, lang=active_lang, assets_dir=assets_dir)
            if found is not None:
                return found.name
        stem = target_id.split(":", 1)[-1]
        return _fallback_english_name(stem) if stem else ""

    translator = register_texts(ns)[ns]
    if target_id in _load_catalog()[ns]:
        return translator | target_id
    if assets_dir is not _SENTINEL:
        found = get_entry(ns, target_id, lang="en", assets_dir=assets_dir)
        if found is not None:
            return unreal.Text(found.name)
    stem = target_id.split(":", 1)[-1]
    return unreal.Text(_fallback_english_name(stem) if stem else "")


def clear_cache() -> None:
    """清空词典与回退词条缓存。"""
    _load_catalog.cache_clear()
    _fallback_raw_entry.cache_clear()
    _load_pickle_table.cache_clear()
    _TRANSLATORS.clear()


def format_option_labels(entries: list[InventoryEntry]) -> list[str]:
    """生成下拉选项展示名；仅在同一列表出现重名时追加 ``[id]`` 区分。"""
    counts = Counter(entry.name for entry in entries)
    return [
        f"{entry.name} [{entry.id}]" if counts[entry.name] > 1 else entry.name
        for entry in entries
    ]


def _combo_key(combo, tag: str) -> str:
    if combo is not None:
        get_path = getattr(combo, "get_path_name", None)
        if callable(get_path):
            path = get_path()
            if isinstance(path, str) and path:
                return f"{tag}:{path}"
        return f"{tag}:{id(combo)}"
    return tag


def _get_widget(container, attr_name: str, explicit=None):
    if explicit is not None:
        return explicit
    if container is None:
        return None
    get_prop = getattr(container, "get_editor_property", None)
    if callable(get_prop):
        try:
            value = get_prop(attr_name)
            if value is not None:
                return value
        except Exception:
            pass
    return getattr(container, attr_name, None)


def _combo_selected_index(combo) -> int:
    idx = combo.get_selected_index()
    return idx if isinstance(idx, int) else -1


def _combo_option_count(combo) -> int | None:
    get_count = getattr(combo, "get_option_count", None)
    if callable(get_count):
        count = get_count()
        return count if isinstance(count, int) else None
    return None


def _repopulate_combo(combo, key: str, ids: tuple[str, ...], options: tuple[str, ...]) -> list[str]:
    """按 ID 保留选中项刷新 ComboBoxString；选项未变时跳过重建。"""
    state = mcvars.InventoryComboCache.setdefault(key, {})
    prev_ids = state.get("ids", ())
    prev_idx = _combo_selected_index(combo)
    prev_id = prev_ids[prev_idx] if 0 <= prev_idx < len(prev_ids) else state.get("last_id")
    target_idx = ids.index(prev_id) if prev_id in ids else (0 if ids else -1)

    option_count = _combo_option_count(combo)
    unchanged = (
        state.get("ids") == ids
        and state.get("options") == options
        and (option_count is None or option_count == len(options))
    )
    if unchanged:
        state["last_id"] = ids[target_idx] if target_idx >= 0 else None
        if target_idx >= 0 and prev_idx != target_idx:
            combo.set_selected_index(target_idx)
        return list(ids)

    # 先清空缓存中的 ids，避免 clear_options 同步触发的 OnSelectionChanged 读到旧映射
    state["ids"] = ()
    state["options"] = ()
    combo.clear_options()
    for label in options:
        combo.add_option(label)

    # 在 set_selected_index 之前写入新映射，保证同步触发的 OnSelectionChanged 立即读取到新 ID
    state["ids"] = ids
    state["options"] = options
    state["last_id"] = ids[target_idx] if target_idx >= 0 else None
    if target_idx >= 0:
        combo.set_selected_index(target_idx)
    elif hasattr(combo, "clear_selection"):
        combo.clear_selection()
    return list(ids)


@lru_cache(maxsize=4)
def _load_pickle_table(path_str: str):
    with open(path_str, "rb") as f:
        return pickle.load(f)


def _resolve_legacy_table(table_data=None, table_path=None):
    if table_data is not None:
        return table_data
    if table_path is not None:
        return _load_pickle_table(str(Path(table_path).resolve()))
    if mcvars.LocalizationCache:
        return mcvars.LocalizationCache
    from mineprep.settings import paths

    default_pickle = Path(str(paths.mineprep)) / "插件贴图" / "语言本地化_language_localization.pickle"
    if default_pickle.is_file():
        return _load_pickle_table(str(default_pickle.resolve()))
    return None


def search_legacy_column(
    block: int,
    query: str = "",
    *,
    search_all: bool = False,
    type_filter: dict | None = None,
    lang: str | None = None,
    table_data=None,
    table_path=None,
) -> list[str]:
    """复用旧 CSV/pickle 表（如生物、附加组件、预设素材段）的筛选逻辑。"""
    data = _resolve_legacy_table(table_data=table_data, table_path=table_path)
    if not data:
        return []

    col = 0
    block_count = 1
    lang_count = -1
    for i, column in enumerate(data):
        if not column:
            if lang_count == -1:
                lang_count = i - 1
            if i + 1 < len(data) and data[i + 1]:
                block_count += 1
        if block_count == block:
            col = i + 1
            break
    if col <= 0 or lang_count <= 0:
        return []

    active_lang = get_language(lang)
    lang_offset = LANGUAGES.index(active_lang) + 1
    if col + lang_offset >= len(data):
        return []

    items = data[col + lang_offset]
    all_items = data[col : col + lang_count + 1] if search_all else [items]
    includes, excludes = _parse_tag_filter(type_filter)
    types = list(data[col]) if (includes or excludes) else []
    if types and len(types) < len(items):
        types.extend([""] * (len(items) - len(types)))

    query_lower = str(query or "").casefold()
    names: list[str] = []
    for i in range(1, len(items)):
        if types:
            tag_set = set(types[i] or "")
            if includes and not (includes <= tag_set):
                continue
            if excludes and not excludes.isdisjoint(tag_set):
                continue
        for lang_col in all_items:
            cell = lang_col[i] if i < len(lang_col) else ""
            if cell and query_lower in cell.casefold():
                if items[i]:
                    names.append(items[i].split("#")[0])
                break

    if block not in (6, 7):
        names.sort()
    return names


def refresh_combo(
    combo,
    category: str,
    query: str = "",
    *,
    search_all: bool = False,
    tag_filter: dict | None = None,
    lang: str | None = None,
    assets_dir: str | os.PathLike | None = None,
) -> list[str]:
    """用最新查询结果刷新单个方块或物品 ComboBoxString，返回平行 ID 列表。"""
    ns = _normalize_category(category)
    entries = search_inventory(
        ns,
        query,
        search_all=search_all,
        tag_filter=tag_filter,
        lang=lang,
        assets_dir=assets_dir,
    )
    ids = tuple(entry.id for entry in entries)
    options = tuple(format_option_labels(entries))
    return _repopulate_combo(combo, _combo_key(combo, ns), ids, options)


def refresh_generator(
    generator=None,
    query: str | None = None,
    search_all: bool | None = None,
    type_filter: dict | None = None,
    *,
    block_combo=None,
    item_combo=None,
    attach_combo=None,
    mob_combo=None,
    preset_combo=None,
    lang: str | None = None,
    assets_dir: str | os.PathLike | None = None,
    table_data=None,
    table_path=None,
) -> dict[str, list[str]]:
    """一次刷新生成器下拉框（方块/物品走新查询层，可选兼管旧表第 2/3/4 段）。"""
    if query is None and generator is not None:
        tb = _get_widget(generator, "过滤名称文本框")
        query = str(tb.get_text()) if tb is not None else ""
    query = query or ""

    if search_all is None and generator is not None:
        cb = _get_widget(generator, "🔲全语言搜索")
        search_all = bool(cb.is_checked()) if cb is not None else False
    search_all = bool(search_all)

    if type_filter is None and generator is not None:
        type_filter = _get_widget(generator, "过滤器缓存")

    results: dict[str, list[str]] = {}

    b_combo = _get_widget(generator, "放置方块选项", block_combo)
    if b_combo is not None:
        results["Blocks"] = refresh_combo(
            b_combo, "Blocks", query, search_all=search_all,
            tag_filter=type_filter, lang=lang, assets_dir=assets_dir,
        )

    i_combo = _get_widget(generator, "放置物品选项", item_combo)
    if i_combo is not None:
        results["Items"] = refresh_combo(
            i_combo, "Items", query, search_all=search_all,
            tag_filter=type_filter, lang=lang, assets_dir=assets_dir,
        )

    for seg_id, attr_name, explicit, result_key in (
        (2, "放置生物选项", mob_combo, "Mobs"),
        (3, "预设素材选项", preset_combo, "Presets"),
        (4, "附加组件选项", attach_combo, "Attach"),
    ):
        legacy_combo = _get_widget(generator, attr_name, explicit)
        if legacy_combo is not None:
            names = tuple(search_legacy_column(
                seg_id, query, search_all=search_all, type_filter=type_filter,
                lang=lang, table_data=table_data, table_path=table_path,
            ))
            results[result_key] = _repopulate_combo(
                legacy_combo, _combo_key(legacy_combo, result_key), names, names,
            )

    return results


def _resolve_target_entry(
    category: str,
    target: str,
    *,
    lang: str | None = None,
    assets_dir: str | os.PathLike | None = None,
) -> InventoryEntry | None:
    ns = _normalize_category(category)
    direct = get_entry(ns, target, lang=lang, assets_dir=assets_dir)
    if direct is not None:
        return direct
    target_cf = str(target).strip().casefold()
    if not target_cf:
        return None
    active_lang = get_language(lang)
    all_entries = search_inventory(ns, "", lang=active_lang, assets_dir=assets_dir)
    for entry in all_entries:
        if entry.name.casefold() == target_cf:
            return entry
    for entry in all_entries:
        if any(text.casefold() == target_cf for text in entry.translations.values()):
            return entry
    return None


def select_option_by_target(
    combo,
    category: str,
    target: str,
    *,
    lang: str | None = None,
    assets_dir: str | os.PathLike | None = None,
) -> str:
    """按 canonical ID、文件原名或译名定位并选中下拉项；返回解析后的 ID。"""
    ns = _normalize_category(category)
    entry = _resolve_target_entry(ns, target, lang=lang, assets_dir=assets_dir)
    if entry is None:
        return ""
    if combo is not None:
        state = mcvars.InventoryComboCache.get(_combo_key(combo, ns))
        if state:
            ids = state.get("ids", ())
            if entry.id in ids:
                idx = ids.index(entry.id)
                state["last_id"] = entry.id
                combo.set_selected_index(idx)
    return entry.id


def get_selected_id(
    category: str,
    combo=None,
    *,
    lang: str | None = None,
    assets_dir: str | os.PathLike | None = None,
) -> str:
    """读取当前选中的 canonical ID；优先兼容 ``mcvars.SpawnNameCache``。"""
    ns = _normalize_category(category)
    if mcvars.SpawnNameCache:
        entry = _resolve_target_entry(ns, mcvars.SpawnNameCache, lang=lang, assets_dir=assets_dir)
        return entry.id if entry is not None else ""

    if combo is None:
        return ""
    state = mcvars.InventoryComboCache.get(_combo_key(combo, ns))
    if not state:
        return ""
    ids = state.get("ids", ())
    idx = _combo_selected_index(combo)
    if 0 <= idx < len(ids):
        selected_id = ids[idx]
        state["last_id"] = selected_id
        return selected_id
    return ""


def get_selection_info(
    category: str,
    combo=None,
    *,
    lang: str | None = None,
    assets_dir: str | os.PathLike | None = None,
) -> tuple[str, str, str]:
    """返回 ``(model_id, tooltip_text, preview_texture_path)`` 供 EventGraph 使用。"""
    ns = _normalize_category(category)
    model_id = get_selected_id(ns, combo, lang=lang, assets_dir=assets_dir)
    if not model_id:
        return "", "", ""

    entry = get_entry(ns, model_id, lang=lang, assets_dir=assets_dir)
    if entry is None:
        return model_id, model_id, ""

    tooltip_text = f"{entry.name}\n{entry.id}"
    preview_path = ""
    if ns == "Items":
        pack_dir = _resolve_pack_dir("Items", assets_dir)
        if pack_dir is not None:
            candidate = pack_dir / f"{entry.stem}.png"
            if candidate.is_file():
                preview_path = str(candidate)
    return model_id, tooltip_text, preview_path
