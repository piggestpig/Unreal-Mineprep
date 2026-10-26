# Authoring Mineprep Mods

Mods live in `Plugins/Mineprep/Content/Python/mods/`.  
Templates: `mods/template.py`, `mods/minimal.py`. Reference package: `mods/VAT_Tools/`.

Every mod declares `mod_info`. Folder mods may add a manifest; the canonical
format and build rules are in [Mod manifest](../mods/ModManager/MANIFEST.md).
Manifest-backed disabled mods are listed without importing their code; enabling
syncs `mod_info` from the manifest.

This file covers kept toolbar / Mod Manager tools. One-shot panels can use `mineprep.ui` — [ui.md](ui.md). Public API changes also require checking and updating affected callers in `mods/`.

**Sizing:** Use `mineprep.ui` for a one-shot panel and a Mod for a kept tool. Start from `mods/minimal.py` or `mods/template.py`; split into a folder package when complexity warrants it.

## Package shapes

### Callable operations

When a mod has operations useful from scripts as well as UI, share the core implementation between the panel and direct callers:

- **Explicit inputs**: the panel reads its `PropertyGroup` and passes plain arguments/config to the core operation. Core operations must not require a `Mod` instance, live widgets, an open tab, or simulated button clicks.
- **Return useful results**: return created Actors, assets, or job handles. Separate pure-Python computation from `unreal.*` game-thread calls.
- **Async work**: expose completion/result and cancellation behavior (reusing [parallel.md](parallel.md) where suitable).
- **Module layout**: put operations in the single mod file, `ops.py`, or `importer.py`. Add an optional `api.py` only when coordinating multiple submodules. Keep package imports free of panel-opening side effects.

### Single file (`mods/my_mod.py`) - complete example

```python
import mineprep

mod_info = {
    'Name': mineprep.bilingual('名称', 'Name'),
    'Description': mineprep.bilingual('说明', 'Desc'),
    'Version': '1.0',
    'CreatedBy': '',
    'EnabledByDefault': False,
    'ReloadWithMineprep': True,  # re-register on mineprep.reload()
    # 'Priority': 0,  # larger loads first; omit → 0. Mod Manager uses 100
    # 'Advanced': True,  # hide in Mod Manager until "Show Advanced Options"
}

class MyMod(mineprep.Mod):
    _label_ = mineprep.localize('标题', '标题', 'Title', '標題')
    # _unique_ = True  # one Editor tab; requested ID = class name

    def draw(self, context=None):
        self.layout.button('Open', on_clicked=lambda: mineprep.startfile(__file__))

def register():
    MyMod.register()       # register(True) also opens the panel

def unregister():
    MyMod.unregister()
```

### Folder package (only when the tool has multiple surfaces / ops files)

```
mods/MyMod/
  __init__.py    # mod_info, register/unregister
  panel.py       # Mod subclass + draw
  props.py       # PropertyGroup(s)
  ops.py         # callable operations (or a focused importer/bake module)
  api.py         # optional stable entrypoints across implementation modules
  util.py        # shared helpers, if needed
```

```python
# __init__.py
def register():
    from . import panel
    panel.MyMod.register()

def unregister():
    from . import panel
    panel.MyMod.unregister()
```

Enable via Mod Manager, `EnabledByDefault`, or `mineprep.mods.register(module)`.
`register` / `unregister` also accept a full name such as `"mods.WorldGenerator"`
and return success. `EnabledByDefault` is a startup default; query
`name in mcvars.EnabledMods` for current enabled state. Full `mineprep.reload()`
preserves the currently enabled set.

## Mod class notes

| Member | Role |
|--------|------|
| `_label_` | Tab / menu display name |
| `_public_` | Default `False`. Panel cache only when this is true or `DebugMode` — [remote.md](remote.md) § panel |
| `_menu_` | Toolbar section. Default `'mods'`. `register` and `unregister` both use it |
| `_unique_` | `True` → one Editor tab, requested ID = class name. UE's registered ID differs; see lifecycle below. Default `False` → new random requested ID each open |
| `_root_` | Child widget name on template (default `'Root'`) |
| `_template_` | EUW asset to copy under `/Game/mc/mods/{ClassName}` |
| `self.layout` | Scroll-root `Layout` |
| `draw()` | Build UI (called from `__init__`) |
| `redraw()` | Clear children + `draw` again — **never** from inside `draw` |
| `register(open=False)` | Create/update BP and menu entry; `open=True` opens after mods initialization. During initialization, opening is suppressed unless `open=2` |
| `unregister()` | Close the blueprint's registered tab, warn about leftovers, remove registry/menu entry; the Blueprint close event calls `destruct()` |

Panel asset path: `/Game/mc/mods/{ClassName}`. Toolbar under Mineprep main menu. Remember last Details values: PropertyGroup `_autosave_ = True` — [ui.md](ui.md).

Script-only operations need no Mod instance; import their public functions
directly. Minimal UI mods can use `mineprep.ui(...)` in `register()`.

## UI composition patterns

Keep PropertyGroup instances on the Mod, and retain Layout nodes when callbacks
need to update them. For example, a two-column form can hide one column directly:

```python
row = layout.row()
left = row.col(fill=1, padding=3)
right = row.col(fill=1, padding=3)
left.prop(self.left_props)
right.prop(self.right_props)
layout.prop(self.options, 'HideRight',
            on_property_changed=lambda _: right.hide(self.options.HideRight))
```

Sizing, footers and page containers: [Layout](ui.md#layout).
Build the required structure in `draw()`; update existing controls when the
structure has not changed. A full redraw remains appropriate for a real rebuild.

**Mod keys / close:** override `on_key_down` / `on_key_up` / `destruct` as needed.
Default `on_key_down` opens the Mod folder on Pause/Break; call
`super().on_key_down(key)` to retain that shortcut. Key events need panel focus.
Unbind any owned selection callbacks in `destruct` before their widgets disappear.

**Paint RT:** [ui.md](ui.md) § Sketch RT; [pitfalls/ui.md](pitfalls/ui.md).

VAT Tools' asset synchronization rules belong in [pitfalls/vat.md](pitfalls/vat.md).

## Localization

- `bilingual(zh, en)` / `localize(...)` → **`unreal.Text`**, not `str`; convert before concatenation / `join`, not before every `set_text` or f-string
- `bilingual(zh, en)` → `mod_info` / short labels
- `localize(...)` → panel titles, buttons, footnotes
- `Cls.localize('Field', ...)` → Details display names (attribute name as key)

## Reload workflow

After editing this mod (or plugin Python), in the Editor console:

```python
mineprep.reload()
```

This full reload attempts to close loaded `ReloadWithMineprep=True` panels
through `Mod.unregister()`, removes those modules **and all their submodules**,
then imports them again and re-registers previously enabled mods. Ordinary
`register(True)` does not reopen during reload (`ModsInitialized` is false).
Inspect the returned logs: if Mineprep warns that not all mod panels closed,
tell the user to close the remaining windows manually. Do not repeatedly reload
or add custom tab-closing code to compensate. Do not claim all instances were
cleaned up when that warning appears. The user can reopen a needed panel from
the Mineprep menu. Never reload inside a mod's `register()` or `draw()`.

`mineprep.mods.register(module)` calls the existing module's registration function; it does **not** read edited Python from disk. Use it to enable a newly imported mod, not as a replacement for reload.

For a custom unload/re-import workflow outside full `mineprep.reload()`, clear affected module entries and cached package attributes, then re-import in dependency order. Some existing mods do this in `unregister`; it is a lifecycle choice, not a requirement of full reload. Removing `sys.modules` entries alone does not update references held by open panels or other consumers.

### Panel lifecycle — UE 5.8

- **Closing & `destruct()`**: `Mod.unregister()` calls `close()` on each open instance (using its saved `tab_id`), and the widget's Blueprint close event pops `mcvars.WidgetModMap` and calls `mod.destruct()`.
- **Cleanup in `destruct()`**: release owned tick/delegate handles and pending tasks in `destruct()`. Any callback that can outlive the panel must guard against destroyed widgets. Note that `mc_parallel` handles are not auto-destroyed by `Mod`, and `runner.destroy()` on a `@thread` cancels the game-thread callback/polling without stopping the background worker thread itself.
- **Unclosed windows on reload**: if an instance remains in `WidgetModMap` after `close()`, Mineprep warns and clears its layout best-effort; ask the user to close that leftover window manually and reopen from the Mineprep menu.

## Testing

Choose checks for the change: pure-data logic outside Unreal, public operations
without a panel, and UI behavior in the editor when relevant. For changed async
lifecycle code, include failure/cancellation and panel-close cleanup. No mandatory
test API or full suite is required. Examples should use the real public entrypoint.

Agent iterative in-editor runs (MCP / Remote Execution): [remote.md](remote.md) + policy in [SKILL.md](SKILL.md). Open Mod tab: [remote.md](remote.md) § panel.
