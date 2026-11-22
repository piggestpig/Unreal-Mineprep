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
See the [Internationalization docstring](../mineprep/localization.py) for other options.

## Read-only calls

Use `read_only=True` to look up a text without collecting entries or translations:

```python
text = i18n.start('开始', 'Start', read_only=True)
english = I18N.start('Start', read_only=True)
existing = loc.start(read_only=True)
```

For one string, `|` is equivalent to a `read_only=True` call:

```python
text = i18n | '开始'
english = I18N | 'Start'
keyed = i18n.start | '备用文本'
custom = i18n['Shared'] @ path | '开始'
formatted = (i18n | '已完成 {count} 项').format(count=3)
```

Only a string is accepted; other types raise `TypeError`. The string is the source
and missing-key fallback, not a reverse search across translations. A node's key
takes precedence. Keep parentheses around `|` when formatting its returned Text.

A hit returns the catalog's cached Text. A miss returns `unreal.Text(source or key)`;
additional translations are ignored, and the fallback is not registered or added
to catalog/search caches. An empty call returns empty Text. `check` is ignored.
The normal initial catalog load and registration still occur when needed.

The flag applies to one call and works with namespace/key overrides and `@` files.
Default `read_only=False` collects as usual, including after a read-only miss.
It never makes a `from_data()` catalog writable. This is separate from
`check=False`, which only changes source-difference checks.

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
[localize docstring](../mineprep/widgets.py).

## Explicit catalog files

Use `file=` to collect into a specific JSON file, including from UE's Python
console or a Blueprint Execute Python Script node:

```python
from mineprep import Internationalization

loc = Internationalization(namespace='MyTool', file=r'E:\Translations\tool.json')
title = loc.start('开始', 'Start')
```

Alternatively, use `@` on `i18n`, `I18N` or an existing node:

```python
loc = i18n @ r'E:\Translations\tool.json'
settings = I18N['MyTool'].settings @ r'E:\Translations\settings.json'
speed = settings.Speed('Speed', '速度')
```

`@` returns a copy, retaining languages, namespace and key without changing the
original node. Use parentheses for an immediate call: `(i18n @ path).start('开始')`.
On a `from_data()` node, it selects file collection without exporting the memory catalog.

`file` accepts a string or Path and means a JSON file, not a Python source file.
Relative paths resolve against the working directory at construction or when `@`
is used. The first collected entry creates the file and missing parent directories; construction or
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

## Iteration and translation search

Iteration and membership inspect the current catalog's **current namespace**:

```python
import re
from mineprep import i18n

loc = i18n['MyMod'] @ 'translations/i18n.json'
for key, translations in loc:
    print(key, translations)              # 'start', {'zh': '开始', 'en': 'Start'}
for language, text in loc.start:
    print(language, text)                 # 'zh', '开始'; 'en', 'Start'

exact = 'Start' in loc                    # full, case-sensitive text equality
partial = re.compile('start', re.IGNORECASE) in loc
entry_only = 'Start' in loc.start
```

A key selects only its exact record, even when dotted child keys exist. Missing
keys or namespaces give empty iteration and no matches. Order follows the catalog;
underscore metadata is excluded. Returned language dictionaries are copies.
Iterators retain the snapshot from their creation; subsequent iterations see updates.
For a dictionary, use `dict(iter(loc))`: `dict(loc)` can invoke the dynamic `keys`
attribute. Methods such as `keys` and `items` remain available as localization keys.

Search examines stored source and translation values, including explicitly empty
strings. It does not match keys, metadata, language fallback or formatted output.
Compiled text regexes use `search()` with their flags; other types, including bytes
regexes, raise `TypeError`.

Queries do not collect or write entries or check source differences. File catalogs
use the normal initial load and registration; later queries read cached data.
Namespace-wide exact searches lazily share a text index, invalidated when that
namespace changes. A selected key scans only its languages; regex searches stop at
the first match without building an index. JSON edits still need the normal reload.

## Offline localization tools

Inspect a mod folder or Python file without importing or running it:

```python
from mineprep.localization import collect_i18n, check_i18n

preview = collect_i18n('mods/MyMod')             # read only
report = check_i18n('mods/MyMod')               # read only
# collect_i18n('mods/MyMod', write=True)         # explicitly merge additions
```

Outside UE, put the plugin Python directory on `sys.path` and import
`mineprep.localization` directly for a standard-library-only process. Both helpers are
also exported by `mineprep`.

Reports contain `added`, `untranslated`, `unused`, `dynamic` and `errors` lists.
Standard `i18n` / `I18N` / `mineprep.i18n` / `mineprep.I18N` names are recognized;
aliases and wrappers such as `tr(...)` may be missed entirely, without appearing
in `dynamic`. Custom instances and explicit file paths are not statically expanded.
Recognized `read_only=True` calls and `|` expressions count as references but do not
supply collection candidates; ordinary calls to the same key can still supply
translations. Dynamic right operands of recognized `|` expressions appear in `dynamic`.

`check_i18n` defaults to `zh` and `en`; use `languages=[...]` to inspect others.
`untranslated=0` does not prove the whole UI is localized: unwrapped strings are
not fully detected. Review source and `added` / `dynamic` separately. `unused`
entries are candidates only; legacy calls and missed references can cause false
positives. Check callers before deleting entries. Writes preserve existing JSON
values and skip conflicts or invalid files; reload afterward. See the
[helper docstrings](../mineprep/localization.py) for details.
