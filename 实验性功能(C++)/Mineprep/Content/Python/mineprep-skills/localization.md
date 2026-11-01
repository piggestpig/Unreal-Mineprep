# Optional localization

Read this when adding multilingual support, translating a tool or maintaining
existing localized text. Personal panels and mods can use ordinary strings and
`DisplayName` metadata without a catalog or `localize()` call.

## Ordinary text

Use `i18n` for Chinese-native text and `I18N` for English-native text. Ordinary
`bilingual('中文', 'English')` calls can become `i18n('中文', 'English')`.

```python
from mineprep import i18n, I18N

title = i18n('开始')                            # source text is sufficient
cancel = i18n('取消', 'Cancel')                 # optional initial translation
message = i18n('已完成 {count} 项').format(count=3)
english_source = I18N('Start')
```

Executed calls collect texts into the mod root's `i18n.json`. Maintain translations
in JSON afterward; existing JSON values take priority. A source-only call preserves
translations already in JSON. Missing translations fall back to parent-language
or native text. Reload through the normal flow after editing JSON.

Use `i18n.queue.start('开始')` for a stable dotted key and
`i18n['Shared'].cancel('取消')` to select a namespace. Chinese resources use `zh`
as the common fallback; `zh-Hant` is Taiwan Traditional Chinese, and `zh-Hant-HK`
needs only Hong Kong wording differences. Records use `_native` for their source
language (omitted means `zh`); `I18N` creates English-native records.

Manifest arrays and language dictionaries use the same catalog; see
[manifest text syntax](../mods/ModManager/MANIFEST.md#文本写法).
`bilingual`, `localize` and `loctext` remain available for existing callers.
See the [Internationalization docstring](../mc_localization.py) for other options.

## Formatting

The result is `unreal.Text`: pass it directly to widgets, use `.format(...)` for
values, and convert to `str` for concatenation or `join`. Keep localization
templates stable; f-strings inside `i18n(...)` create a different key per value.

`unreal.Text.format` uses UE formatting, not Python's `{x:.1f}` syntax. Pre-format
values when fixed decimal precision is needed:

```python
x = 12.345
position = i18n('位置 {x}').format(x=f'{x:.1f}')
```

Keep the same placeholders in every translation. See
[UE text formatting](https://dev.epicgames.com/documentation/en-us/unreal-engine/text-localization-in-unreal-engine)
for advanced syntax.

## Property groups

For multilingual property sets, call the `localize` **class method** after the
declaration, before or after instantiation. It collects field display names and
categories into `i18n.json`, using English as the default source language.
`localize` is not a metadata key.

```python
Settings.localize()                              # labels and categories
# Choose one alternative when needed:
# Settings.localize(tooltip=True)                # also collect English tips
# Settings.localize(tooltip='zh')                # English labels, Chinese tips
# Settings.localize(i18n)                        # Chinese-native labels
# Settings.localize(I18N['Shared'].options)      # namespace and key prefix
```

`ToolTip` / `ShortTooltip` are skipped by default; `tooltip` chooses their source
language independently of the labels. Existing JSON remains authoritative.
UE categories share translations globally by name.

When migrating old explicit `localize('Field', ...)` calls, run them before the
automatic call to retain their translations. For additional options, see the
[localize docstring](../mc_widget.py).

## Explicit catalog files

Use `file=` to collect into a specific JSON file, including from UE's Python
console or a Blueprint Execute Python Script node:

```python
from mineprep import Internationalization

loc = Internationalization(namespace='MyTool', file=r'E:\Translations\tool.json')
title = loc.start('开始', 'Start')
```

`file` accepts a string or Path and means a JSON file, not a Python source file.
Relative paths resolve against the working directory at construction. The first
collected entry creates the file and missing parent directories; construction or
an empty call creates nothing. Chained nodes, namespace/key overrides and
`Settings.localize(loc.params)` retain the path. Without `file`, mod-root discovery
is automatic; non-file scripts remain memory-only.

The default namespace is the file's parent folder (`Core` for the plugin Python
directory). Prefer an explicit, stable namespace: paths control storage, while
namespace and key identify UE texts. Resource inheritance and derived display
entries should use `from_data()` rather than being collected into a child catalog.

## Read-only memory catalogs

For resource data loaded by your own code, supply a flat `{key: record}` dictionary:

```python
from mineprep import Internationalization

entries = {'biomes.badlands.name': {'_native': 'en', 'en': 'Badlands', 'zh': '恶地'}}
loc = Internationalization.from_data(entries, namespace='MyMod.pack.example')
name = loc.biomes.badlands.name('badlands')
```

Use a stable, unique namespace. This copies input and batch-registers texts without
file access. Existing keys return cached Text; the first argument only provides
a missing-key fallback. Without a fallback, a missing key displays the key itself.
Lookups do not collect texts or register fallbacks.

Calling `from_data()` again with the same namespace replaces its snapshot; old
instances and chained nodes see updates. Unchanged records keep their cached Text.
Invalid data warns and preserves the old snapshot. Removing a key affects future
lookups, not Text objects already held elsewhere.

For properties, pass `Settings.localize(loc.params, tooltip='en')`; after refreshing
the snapshot, call `localize()` again to update bindings. Missing property records
use metadata as fallback without changing the catalog. File loading, inheritance
and binding aliases remain the caller's responsibility.

## Offline localization tools

Inspect a mod folder or Python file without importing or running it:

```python
from mc_localization import collect_i18n, check_i18n

preview = collect_i18n('mods/MyMod')             # read only
report = check_i18n('mods/MyMod')               # read only
# collect_i18n('mods/MyMod', write=True)         # explicitly merge additions
```

Outside UE, put the plugin Python directory on `sys.path` and import
`mc_localization` directly for a standard-library-only process. Both helpers are
also exported by `mineprep`.

Reports contain `added`, `untranslated`, `unused`, `dynamic` and `errors` lists.
Standard `i18n` / `I18N` / `mineprep.i18n` / `mineprep.I18N` names are recognized;
aliases and wrappers such as `tr(...)` may be missed entirely, without appearing
in `dynamic`. Custom instances and explicit file paths are not statically expanded.

`check_i18n` defaults to `zh` and `en`; use `languages=[...]` to inspect others.
`untranslated=0` does not prove the whole UI is localized: unwrapped strings are
not fully detected. Review source and `added` / `dynamic` separately. `unused`
entries are candidates only; legacy calls and missed references can cause false
positives. Check callers before deleting entries. Writes preserve existing JSON
values and skip conflicts or invalid files; reload afterward. See the
[helper docstrings](../mc_localization.py) for details.
