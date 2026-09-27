# Layout & PropertyGroup

Examples marked complete include their setup. Other snippets are API or callback fragments: names such as `self`, `layout`, `mesh` and `anim` come from the surrounding task. Syntax validation alone does not make a fragment standalone.

Source: `mc_widget.py`. Export: `mineprep.Layout`, `mineprep.PropertyGroup`, `mineprep.ui`.

## Delivery: `ui` vs `Layout` vs Mod

| Form | When |
|------|------|
| `mineprep.ui("""...""")` | Temporary / one-shot panel — assets + button, no menu entry needed |
| `mineprep.Layout()` | Inside `Mod.draw`, or tiny console experiments (still spawns a tab) |
| `mineprep.Mod` subclass | Persistent tool (toolbar, reload, Mod Manager) — see [mods.md](mods.md) |

For small tasks prefer **`mineprep.ui`**. Read [mods.md](mods.md) when a kept tool or lifecycle details are relevant; `VAT_Tools` is a larger-tool example. Reading `mc_widget.py` to verify behavior does not imply changing the plugin.

### Temporary panel (`mineprep.ui`) - complete example

The string runs with `layout` already bound to the EUW root. Define `PropertyGroup`, instantiate it, bind buttons / `prop`.

```python
import mineprep
import unreal

mineprep.ui("""
import mineprep
import unreal

class MeshListProps(mineprep.PropertyGroup):
    Meshes: list[unreal.StaticMesh] = [None]
    Prefix: str = ''

props = MeshListProps()  # instance, not the class

def run():
    n = 0
    for mesh in props.Meshes:
        if not mesh:
            continue
        mineprep.prints(f'{props.Prefix}{mesh.get_name()}')
        n += 1
    mineprep.prints(f'done ({n})')

layout.button('Run', on_clicked=run)
layout.prop(props)
""")
```

- Spawns an Editor Utility tab (template asset title often 「MOD自定义面板」).
- Execution and console fallback: [remote.md](remote.md#prefer-order).
- Already-open panel: [remote.md](remote.md) § panel.
- Optional `mineprep.ui(script, save_path='MyPanel')` saves under `/Game/mc/mods/` and registers a tab from that asset.
- Keep the script string **self-contained**: imports used inside callbacks (`from collections import defaultdict`, etc.) must appear **inside** the `ui("""...""")` string — outer-scope imports are not visible to the panel script.
- Each `ui()` execution has its own Python namespace. Top-level `props`, paths,
  helpers and callback bindings belong to that execution; rerunning the script
  does not replace the variables seen by old buttons.
- This isolates name assignments, not mutable objects deliberately shared through
  imported modules or registries. PropertyGroup GUIDs distinguish UE classes;
  persistence and `_unique_` behavior remain unchanged. Use descriptive class
  names for different tools, not a random name on every run.
- Newly saved widget assets use the same isolated execution path on each opening.
  Existing assets keep their previously stored script until explicitly resaved.

AnimSequence bone tracks (asset CONTROL channels): [pitfalls/anim.md](pitfalls/anim.md). Level Sequence character keys: [api.md](api.md) § Control Rig — not a Layout concern.

## Layout

```python
layout = mineprep.Layout()                 # or Mod.self.layout (scroll root)
# mineprep.ui('layout.button("Hi")')       # one-liner / temporary panel (above)
```

Unknown names forward to the UWidget: `pages.set_active_widget_index(i)`, not `pages.target.…`. Use `.target` only when you need the raw object.

`switcher` + page `col`: `align=(0, 0)` so the page fills. Default packs to the top and a footer cannot sit bottom-left.

### Builders

| Method | Notes |
|--------|--------|
| `text` / `title` / `label` | `text(..., wrap=True)` auto-wraps to slot width. Text slots always H-fill; `align=(2, v)` / `(3, v)` set `TextJustify` center/right. `title` defaults center |
| `button` / `operator` | `on_clicked`; default `EditorUtilityButton`. Empty `text` skips the inner label |
| `checkbox` | `on_check_state_changed`; default `EditorUtilityCheckBox` |
| `spinbox` | `on_value_changed` / `on_value_committed`; default `EditorUtilitySpinBox` |
| `textbox` | `hint` / `on_text_changed` / `on_text_committed`; default `EditorUtilityEditableTextBox` |
| `combo` | ComboBoxKey; `options` is a list (`key=str(item)`) or `{key: text}`; generate defaults to `make_combo_text`; callbacks get `str`; `on_selection_changed` / `on_opening`; default `EditorUtilityComboBoxKey` |
| `prop(data, property=None, text=None, on_property_changed=None)` | Omit `property` → full DetailsView. Set `property` → `SinglePropertyView` (**scalars only** — not `list` / `Array` / `set` / `map`) |
| `row` / `col` / `column` | Boxes |
| `spacer` / `overlay` / `switcher` / `scalebox` / `sizebox` / `wrapbox` / `scrollbox` | Containers; `sizebox(w, h)` fixes axes (omit = unconstrained); `wrapbox(inner_padding=6)` wraps children |
| `image` / `custom` | Media / raw widget. `image=None` is an empty placeholder; scalar `size` is square until a texture is set. `custom`: prefer an `EditorUtility*` subclass when one exists |
| `border` | Container + mouse; callbacks get `Layout`, not `FGeometry` — **border** below |
| `hide(state)` | Visibility — prefer over full `redraw` when toggling regions |
| `get` / `set` | Editor properties on the widget |
| `parent` / `outer` / `children` / `path` | Hierarchy |

Interactive builders default to **Editor Utility** subclasses (`EditorUtilityButton`, `EditorUtilityCheckBox`, `EditorUtilitySpinBox`, `EditorUtilityEditableTextBox`, `EditorUtilityComboBoxKey`). They use the editor Slate style. For `layout.custom`, pick `unreal.EditorUtility…` over the raw UMG type when it exists (`EditorUtilityEditableTextBox` not `EditableTextBox`, `EditorUtilityComboBoxKey` not `ComboBoxKey` / `ComboBoxString`). Do not restyle EU widgets to look like raw UMG unless the user asks. Override with `subclass=` only when needed. Localized combo items: `layout.combo`, not `ComboBoxString`.

### Common kwargs (`**kwargs` → `add_widget`)

| Kwarg | Meaning |
|-------|---------|
| `padding` | `Margin`, `(h,v)`, or scalar |
| `align` | `(h,v)`: `0` fill, `1` left/top, `2` center, `3` right/bottom |
| `fill` | `False` = auto size. `True` / `1` / a fraction → `SlateSizeRule.FILL` with that weight. **Siblings that fill share leftover space.** See **fill** below. |
| `clip` | Clip overflow |
| `tooltip` | Hover text |
| `hidden` | Initial visibility (int → `SlateVisibility`) |

Example footer layout (Mod Manager / VAT Tools / Skin Editor log): `align=(1, 3)` on the **one** vertical filler (`fill=1`).

### fill (Slate FILL weights)

`fill` is **not** “make this widget look bigger”. `mc_widget.add_widget` maps a truthy `fill` to `SlateChildSize(float(fill), SlateSizeRule.FILL)`. Leftover space in **that parent only** is split among FILL children by weight (`True` ≡ `1`). Children of `left` never compete with children of `right`.

Use several fills **only when you want that split**. One parent, one leftover pool.

| Intent | How | In-tree example |
|--------|-----|-----------------|
| Equal columns | Several **siblings** `fill=1` | VAT `left`/`right` `col(fill=1)`; Mod Manager header/row `scalebox(..., fill=1)` |
| Unequal split | Different weights | Mod Manager uninstall column `fill=0.75` next to `fill=1` |
| Pack content, pin a footer to a corner | **At most one** FILL child in that vertical box — usually the last — plus `align=(1, 3)` | Skin Editor log; Mod Manager advanced checkbox; VAT `AutoCleanCache` |
| Tight stack (no leftover) | Omit `fill` on everyone | Footer sits immediately under the widget above, not in the corner |

```python
# Vertical — one filler: Details packed, log pinned bottom-left (Skin Editor)
layout.prop(self.props)
layout.text(..., align=(1, 3), padding=6, fill=1)

# WRONG — two fillers split leftover height → large blank above the log
layout.prop(self.props, fill=1)
layout.text(..., align=(1, 3), fill=1)

# WRONG — no filler: log hugs the Details instead of the bottom-left corner
layout.prop(self.props)
layout.text(..., align=(1, 3), padding=6)

# Horizontal — several fillers: even columns (wanted)
row = layout.row()
left = row.col(fill=1, padding=3)
right = row.col(fill=1, padding=3)
# props inside left/right omit fill unless that column itself needs a footer
```

VAT Tools: the **row** has two `col(fill=1)`; the Details inside those cols omit `fill`. On the root `layout`, only `AutoCleanCache` is `fill=1` (`HideInitSkm` under it has none).

`overlay(..., fill=True)` defaults to FILL so it covers the parent — that is a single child, not a split.

### Visibility without redraw

```python
right = row.col(fill=1, padding=3)
# ... populate right ...
layout.prop(
    self.options, 'HideRight',
    localize('隐藏右栏', '隐藏右栏', 'Hide Right', '隱藏右欄'),
    align=(1, 3),
    on_property_changed=lambda _: right.hide(self.options.HideRight),
)
```

`Layout.hide(state)`:

- `bool` / `int` → `enum(SlateVisibility)[int(state)]`  
  - `False`/`0` → Visible  
  - `True`/`1` → Collapsed (typical “hide column”)
- Or pass `unreal.SlateVisibility` directly

Keep a **Python reference** to the `Layout` node (`right`) from `draw()`; callbacks close over it. No need to `redraw()` the whole panel.

### Cached browser / selection panels

Create cards and detail widgets once per data revision. Search, selection and
variant expansion update existing text, brush resources, colors and `hide()`;
rebuild when the underlying entries change. Keep ordered selection keys separate
from visible rows: whether filtering clears selection is a product decision,
not a consequence of hiding a widget. Use stable identities, not display names.

Clear the previous image resource and its visibility when the next selection
has no texture; updating the label alone leaves a stale preview. Preserve aspect
ratio with `set_desired_size_override`. Reset any transparent placeholder tint
when assigning a valid image. Collapsed cards still exist in memory; this is
widget reuse, not virtualization.

For Shift-click with `button(on_clicked=...)`, read modifier state inside the
callback (verified UE 5.7):

```python
state = unreal.InputLibrary.get_modifier_keys_state()
shift = unreal.InputLibrary.modifier_keys_state_is_shift_down(state)
```

Programmatic PropertyGroup updates and user edits should share a state-update
helper when dependent fields or persistence must also change. Do not assume a
Python assignment fires the DetailsView's user-edit delegate.

### border / mouse

`layout.border(..., on_mouse_button_down=..., on_mouse_move=..., on_mouse_button_up=...)` binds UMG `Border` pointer events. The engine callback is `(FGeometry, FPointerEvent)` — **do not use those structs in Python** ([pitfalls/ui.md](pitfalls/ui.md) § UMG Geometry). Mineprep passes the **Border’s `Layout`** instead.

```python
def down(w):
    uv = w.get_mouse_uv()          # 0..1 in this widget
    # local = w.get_mouse_local()  # pixels
    return True

def move(w):
    if not drawing:
        return False
    ...
    return True

border = layout.border(fill=1, align=(0, 0),
    on_mouse_button_down=down, on_mouse_button_up=up, on_mouse_move=move)
img = border.image(rt, size=unreal.Vector2D(1024, 1024), padding=0, align=(0, 0), fill=1)
img.target.set_visibility(unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE)
```

`get_mouse_local` / `get_mouse_uv` / `get_local_size` call Blueprint helpers (`AbsoluteToLocal`, `GetLocalSize`) with a `UWidget*` so `FGeometry` never crosses into Python. `get_mouse_uv` is `local / size` (zero size → `(0,0)`).

**Return value** (wrapper in `mc_widget.border`):

- `handled` means the mouse event is not passed to widgets below
- `unhandled` continues to pass it through
- Return an `EventReply` as-is. Truthy → `handled()`. Falsy / `None` → `unhandled()`.

A child `Image` that is `Visible` takes the hit first. For drawing, set it `SELF_HIT_TEST_INVISIBLE` so the Border receives Down/Move/Up. Prefer `img.hide(unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE)` (or `set_visibility`). **Do not** assign `brush.image_size = Vector2D(...)` — UE 5.7 raises `TypeError: DeprecateSlateVector2D`. Size the Image with `set_desired_size_override`. After swapping the RT, `set_brush_resource_object(None)` then the RT again.

### Sketch RT (Skin Editor)

Lived-in recipe: `mods/Skin_Editor/paint.py`. Color skins / PNG export — **not** VAT bake RTs.

```python
rt = unreal.RenderingLibrary.create_render_target2d(
    world, w, h, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB, CLEAR)
# nearest + clamp; force_update_texture **only** here / after resize — never after a canvas draw
unreal.RenderingLibrary.resize_render_target2d(rt, w, h)  # no Python rt.resize_target
```

| Do | Don't |
|----|--------|
| `RTF_RGBA8_SRGB` for color that will be shown in UMG or exported as PNG | `RTF_RGBA8` (linear U8). `ExportRenderTarget` writes those bytes as-is → dark PNG |
| Eyedrop: `read_render_target_pixel` is sRGB `FColor`; `LinearColor.set_from_srgb` into the Color picker | `LinearColor(r/255, g/255, b/255)` — treats encoded bytes as linear; pick is too bright |
| `force_update_texture` on the **source Texture2D** before blit | `force_update_texture` on the canvas RT after `begin_draw_canvas` / blit / before save — `UpdateResource()` wipes GPU to clear color |
| One stroke = snapshot base RT + opaque coverage stamps + **one** translucent composite of the user's color. `WriteAlpha`: stamp ink with `BLEND_OPAQUE` onto the display RT (replace RGBA, including a=0 erase) | `draw_line` for alpha paint. `K2_DrawLine` is always opaque, skips zero-length (click ≠ drag), and restamps every move → irregular stacking |
| Square stamp: `draw_texture(white, ..., MASK, BLEND_TRANSLUCENT)`; round: `draw_polygon` | Mixing line + end caps with different blend modes |
| Export: `RenderingLibrary.export_render_target(world, rt, dir, name.png)`; default `Paths.project_saved_dir()` + texture name | Content-dir PNG as the default |
| Restore with no source tex: `load(None)` / clear the RT | Early-out that makes Restore a no-op when Texture is empty |
| `begin_draw_canvas_to_render_target` size: if `size.x < 1`, fall back to RT width/height | Assume the returned size is always valid |

Translucent paint: on mouse down, copy the display RT → `base`, clear a `cover` RT, stamp the stroke in **opaque white** on `cover` (spacing along the segment). Each move: copy `base` → display, then `draw_texture(cover, ink, BLEND_TRANSLUCENT)` **once**. Click / drag / hold / round / square then share the same glaze.

Mod keys (peek original): override `on_key_down` / `on_key_up` (`unreal.Key`). Call `super()` so Pause/Break still opens the mod folder — [mods.md](mods.md). The EUW template forwards them via `WidgetModMap`. The panel needs keyboard focus. PropertyGroup `Key` defaults cannot be a string — `unreal.Key()` + `import_text('LeftAlt')`. LinearColor: `Color: unreal.LinearColor = ((0, 0, 0, 1), {})`.

`draw_material_to_render_target` draws a full material quad and sets the render target binding each call. This is not an unconditional clear: output depends on the material and resource state. For incremental strokes, use the canvas/coverage recipe above.

### `prop` callbacks

- Full Details (`layout.prop(props)`): `on_property_changed` receives the **property name** (`'SKM'`, `'DataAsset'`, …).
- Single-property view (`layout.prop(props, 'Field')`): same; compare against the annotation name. **Only scalars** (bool, str, int, float, object references). `list[T]` / `unreal.Array` / set / map → 「不支持的属性」.
- Two columns of arrays: **two PropertyGroups**, each shown as a whole DetailsView:

```python
class SkinProps(mineprep.PropertyGroup):
    Materials: list[unreal.MaterialInterface] = [None]
class HeadProps(mineprep.PropertyGroup):
    Materials: list[unreal.MaterialInterface] = [None]
skin, head = SkinProps(), HeadProps()
left.prop(skin)    # OK — full Details; omit fill unless this col has no footer
right.prop(head)
# WRONG: left.prop(skin, 'Materials')  → SinglePropertyView cannot display arrays
# Even split belongs on the columns: left = row.col(fill=1); right = row.col(fill=1)
```

- UI synchronization callbacks may receive `self` (mod). Core operations take
  explicit inputs; see [Callable operations](mods.md#callable-operations).

```python
# Named single field (footer checkbox) — scalar only; does not dump entire Details
layout.prop(self.options, 'AutoCleanCache', localize(...), align=(1, 3), fill=1)

# Whole PropertyGroup as DetailsView (required for arrays)
left.prop(self.bake_props, on_property_changed=lambda n: ops.on_bake_props_changed(self, n))
```

**Optional split:** when fields should stay out of the main Details, use a separate `PropertyGroup` (e.g. VAT Tools `VATToolsOptions`), not on the bake/init props shown as a full DetailsView.

## PropertyGroup

```python
class Props(mineprep.PropertyGroup):
    Mesh: unreal.SkeletalMesh
    Path: str = ''
    Index: int = (0, {'ClampMin': 0})
    Json: unreal.FilePath = (
        unreal.FilePath(file_path=''),
        {'FilePathFilter': 'json'},  # Details ellipsis; `json` → `*.json`
    )
    Data: unreal.SoftObjectPath = (None, {
        'AllowedClasses': '/Game/.../MyBP.MyBP_C',  # Blueprint → Generated Class _C
    })
    Anims: list[unreal.AnimSequence] = [None, None, None]

Props.localize('Mesh', '网格', 'Mesh', '網格')  # OK before instantiate
p = Props()   # REQUIRED
p.Mesh = skm
```

`save()` / `load(path='')` dump fields to JSON, best-effort (failures `debug`, no throw). Empty path uses `inspect.getfile(type(self))` → `{source directory}/__pycache__/{ClassName}.json` (`mkdir` on save). Ordinary `ui()` classes belong to `mc_widget`, so their default is the plugin Python directory's `__pycache__`, not a no-op. A console class with no resolvable source file has no default path. Explicit path always selects that file for the call. Soft/struct fields go through `export_text` / `import_text`; UObject refs as asset paths.

`_autosave_ = True` → `load()` on instantiate (default json); `save()` on Python setattr and on `layout.prop` Details edits. `load()` writes via `set_editor_property`, so it does not re-save. Default `_autosave_ = False`. `str` fields stay strings even if they look like `/Game/...` — do not `load_asset` those (would nativize a Texture2D into `SavePath`). Object fields still restore from asset paths.

### Persistence in a temporary panel

For ordinary `ui()` panels, `_autosave_ = True` uses the existing default
`__pycache__` file. Two classes with the same name and source directory share
that filename even if their UE class GUIDs differ. Choose distinct descriptive
class names when settings should differ. No settings migration is needed.

For an explicitly chosen file, pass the same path to `load` and `save`, keep
`_autosave_` off (it would still use the default file), and wire saves to Details
changes or a button. Programmatic changes must also invoke that save helper.
`ui(save_path=...)` saves a widget asset, not a PropertyGroup state file. Complete
example using an explicit file in the existing cache directory:

```python
import mineprep

mineprep.ui("""
from pathlib import Path
import mineprep

class SavedPanelProps(mineprep.PropertyGroup):
    Prefix: str = ''

state_path = str(Path(mineprep.__file__).parent / '__pycache__' / 'SavedPanel.json')
props = SavedPanelProps()
props.load(state_path)

def save_state(name=None):
    props.save(state_path)

layout.prop(props, on_property_changed=save_state)
layout.button('Save settings', on_clicked=save_state)
""")
```

Choose a distinct filename for each tool. Because save/load are best-effort, verify the file and restored values when persistence is part of the task; a callback returning without an exception is not proof of a successful write.

### Rules

1. Annotate types (`list[T]` → `unreal.Array(T)`). Defaults: `name: T = value` or `(default, {meta})`. Some structs like `FKey` has no string default — use `import_text` first:

```python
k = unreal.Key()
k.import_text('LeftControl')
class MyProps(mineprep.PropertyGroup):
    a: unreal.Key = k
    Color: unreal.LinearColor = ((0, 0, 0, 1), {})
```

2. **Always instantiate** before `layout.prop` / getattr / setattr.
3. `_unique_ = True` → reuse an instance while the matching entry remains in `mcvars.Props` (Mod Manager style). Full `mineprep.reload()` clears that registry; this flag does not guarantee state or schema migration across a full reload. Prefer **per-mod** instances in `Mod.__init__` for tool panels.
   `_autosave_ = True` → restore default json on construct; persist on setattr / Details.
4. `_softcast_ = True` is the **default**: annotate `Actor: unreal.Actor` so Details picks a **level actor** (stored as `SoftObjectPath`). Transient PropertyGroup objects cannot hard-reference world actors. Reads auto-resolve.

```python
sp = unreal.SoftObjectPath()
sp.import_text(asset.get_path_name())
props.uobject.set_editor_property('Data', sp)
# VAT Tools helper pattern: util.assign_soft_prop(props, 'DataAsset', asset)
```

5. Renaming a field: update **all** `props.OldName`, `assign_soft_prop(..., 'OldName')`, and `on_property_changed` string compares — mismatches fail silently.
6. Access underlying UObject via `props.uobject` when UE APIs need it.

### Localization

```python
Cls.localize('Field', zh, en, zh_tw)           # property
Cls.localize('ClassDisplay', zh, en, zh_tw)  # category-ish when not a prop name
```

## Mod `draw` order

```python
def __init__(self, context=None):
    self.bake_props = BakeAnimProps()
    self.init_props = InitSkmProps()
    self.options = VATToolsOptions()
    super().__init__(context)   # calls draw()

def draw(self, context=None):
    # build UI; close over Layout nodes for hide()/ops
    pass
```

Never `self.redraw()` from inside `draw`. Use `redraw()` only from buttons / external events when a full rebuild is required (e.g. Mod Manager advanced columns).
