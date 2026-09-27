# Authoring Mineprep Mods

Examples marked complete include their setup. Other snippets are API or callback fragments: names such as `self`, `layout`, `mesh` and `anim` come from the surrounding task. Syntax validation alone does not make a fragment standalone.

Mods live in `Plugins/Mineprep/Content/Python/mods/`.  
Templates: `mods/template.py`, `mods/minimal.py`. Reference package: `mods/VAT_Tools/`.

This file covers kept toolbar / Mod Manager tools. One-shot panels can use `mineprep.ui` — [ui.md](ui.md). Public API changes also require checking and updating affected callers in `mods/`; scope guidance: [SKILL.md](SKILL.md).

**Sizing:** If the user only needs a one-shot panel (pick assets → click Run), use `mineprep.ui`. Create a Mod when they want a **kept** toolbar / Mod Manager entry. Prefer a **single-file** mod before a VAT_Tools-style folder package. Before writing a new folder mod, skim an existing one (`mods/minimal.py`, `mods/template.py`, `VAT_Tools` for layout, or `Skin_Editor` for a paint RT / page switcher).

## Package shapes

### Callable operations

Expose only operations with a concrete external use, such as useful domain-specific
conversions or complete automation steps. Not every function needs a friendly
public interface. Keep internal helpers simple and tailored to the mod; do not
add wrappers, configuration types, compatibility layers or extensibility hooks
solely to make them reusable. A short README using existing tools may be enough.

For operations chosen for external use, UI and scripts should share the core
implementation where practical. The following guidance applies to those public
operations, not every helper or UI callback:

- Accept explicit arguments or a plain configuration object. The panel converts
  its PropertyGroup values into inputs; core operations do not require a Mod
  instance, widgets, an open tab, or simulated clicks. UI callbacks may receive
  `self` to collect inputs and display results.
- Keep public operations few and complete: callers should not reproduce the
  panel's internal orchestration. Separate pure computation from UE operations;
  calling without a panel does not make `unreal.*` available outside the editor
  or safe on worker threads.
- Return an Actor/asset for simple operations, or a small result object for
  multiple outputs, created/reused state and warnings. Preserve exception details;
  a notification or boolean alone is insufficient for diagnosing a failed workflow.
- For long operations, put scheduling in a UI-independent job with queryable
  status/result/error and cancellation. Use optional progress callbacks; marshal
  UI updates to the game thread. Define cleanup on cancellation and who owns the
  job when the panel closes; reuse [parallel.md](parallel.md) where suitable.

Use functions in the single mod file, `ops.py`, `importer.py`, or another focused
module directly when that is clear. Add a thin **optional** `api.py` only when it
organizes several implementation modules or preserves a stable caller interface.
Do not create it just to forward every function or standardize folder layouts.
Keep package imports free of panel opening/registration side effects.

Document only the necessary public entrypoints beside the mod: a minimal script example,
inputs/results, UE or panel prerequisites, side effects and sync/async behavior.
Existing mods illustrate individual patterns, not universal architecture:
VanillaMobLoader exposes `importer.create_assets`/`place`; VAT Tools accepts direct
assets in `bake_anim_ops.bake_animation`; WorldGenerator separates pure planning
but still has import scheduling in its panel. Improve affected paths when in
scope; this guidance does not require migrating unrelated existing mods.

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

## Mod class notes

| Member | Role |
|--------|------|
| `_label_` | Tab / menu display name |
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

**Two-column tool** (VAT Tools):

```python
row = layout.row()
left = row.col(fill=1, padding=3)
right = row.col(fill=1, padding=3)
left.prop(self.bake_props, on_property_changed=...)
right.prop(self.init_props, on_property_changed=...)
# footer options on separate PropertyGroup:
layout.prop(self.options, 'AutoCleanCache', localize(...), align=(1, 3), fill=1)
layout.prop(self.options, 'HideInitSkm', localize(...), align=(1, 3),
            on_property_changed=lambda _: right.hide(self.options.HideInitSkm))
```

`left`/`right` both `fill=1` → equal **horizontal** split. Footer `fill=1` is the **only** vertical filler on `layout` (the two-column `row` and `HideInitSkm` omit `fill`). Do not also `fill=1` the Details `prop`s in that same vertical box.

**Pinned footer in one column:** Details omit `fill`; only the footer is `fill=1` + `align=(1, 3)`.

```python
layout.prop(self.props, on_property_changed=...)
self._log = layout.text(..., align=(1, 3), padding=6, fill=1)
```

See [ui.md](ui.md) § fill.

**Page switcher** (Skin Editor): top tab buttons + `layout.switcher(align=(0, 0), fill=1)` then `pages.col(align=(0, 0))`. `functools.partial(self.show_page, i)` for clicks. Dim inactive tabs (`set_render_opacity`). Paint page: left `fill` canvas (`border` + Image); right no-fill Details + action buttons.

**Mod keys / close:** override `on_key_down` / `on_key_up` / `destruct`. The EUW template looks up `mcvars.WidgetModMap[layout.outer]`. Default `on_key_down`: Pause/Break (`unreal.Key` name `Pause`) opens the folder of the Mod class's `.py`; overrides must call `super().on_key_down(key)` to keep it. Peek-original needs panel keyboard focus. Unbind selection (and similar) in `destruct` — a closed DetailsView makes `SystemLibrary.is_valid` throw instead of returning False.

**Paint RT:** [ui.md](ui.md) § Sketch RT; [pitfalls/ui.md](pitfalls/ui.md). Pattern: `mods/Skin_Editor/paint.py`.

**Button then fields under a footnote** (keep Details order correct):

```python
left.prop(self.bake_props, ...)           # DataAsset / AnimSeq
left.text('0: Idle, 1: Walk, 2: Run', ...)
left.button('复制数据集', on_clicked=self.on_copy_clicked)  # UI adapter to the operation
left.prop(self.copy_props)                # separate PG — NOT fields on bake_props
```

For this VAT layout, a second `PropertyGroup` puts TargetPath/NewName below the footnote. Other tools should group fields for their own workflow.

**State:** keep PropertyGroup instances on `self`, not shared mutable state on the
PropertyGroup class. Pass operation inputs as described in [Callable operations](#callable-operations).

**VAT-specific sync example** on Soft path change (DataAsset → AnimSeq / TargetPath / NewName): handle in `on_property_changed` when `name == 'DataAsset'`. After programmatic `assign_soft_prop`, also call the same sync helpers. TargetPath defaults to `/Game/mc/VAT/{strippedName}`.

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

`Mod.unregister()` uses `EditorUtilitySubsystem.get_tab_id_from_blueprint`
and `unregister_tab_by_id`. On window close the current Blueprint template
removes the widget's instance from `WidgetModMap`, then calls its `destruct()`:

```python
# Blueprint close-event fragment; `this` is that event's widget.
import mcvars
mod = mcvars.WidgetModMap.pop(this, None)
if mod:
    mod.destruct()
```

Python `unregister()` does not proactively destruct all mapped instances.
That API returns the blueprint `RegistrationName`, not “None whenever the live
tab is closed”: after `spawn_and_register_tab_with_id` the ID is
`bp.get_path_name() + str(requested_id)`, and it stays set after the user
closes the tab. `None` means this session never registered that blueprint.
Do not hardcode the prefixed path in a mod's `unregister()`.

For mods owning callbacks/tasks, keep `destruct()` idempotent: mark closed,
unregister tick/delegates, cancel pending work and discard late results before
they access widgets. Cancellation does not forcibly stop a running worker. UE
objects and UI remain main-thread work. Reuse `mc_parallel` where appropriate;
do not assume its handles are automatically owned by the Mod.

`_unique_` tabs are closed by this path. Non-unique (`_unique_=False`) extras
use a new random requested ID each open; only the last `RegistrationName` is
unregistered. Remaining mapped instances produce a warning and their layouts
are cleared best-effort; that is not window closure or completed destruction.
The user must close those extra windows manually. To use a panel after reload,
reopen it from the Mineprep menu.

Lifecycle guidance is based on the current Python source and Blueprint close
callback. Multi-window close events have not been fully tested.

## Testing

Test a public operation directly without opening/registering its panel, then
verify the UI delegates to that same operation. Keep pure-data tests independent
of Unreal; editor checks should inspect actual assets/actors and warnings. For
jobs, cover completion, failure, cancellation and panel-close cleanup. Scale
tests to the changed behavior; no mandatory `run_test()` API is needed. A minimal
script example should use the real public entrypoint, not a test-only wrapper.

Agent iterative in-editor runs (MCP / Remote Execution): [remote.md](remote.md) + policy in [SKILL.md](SKILL.md). Open Mod tab: [remote.md](remote.md) § panel.
