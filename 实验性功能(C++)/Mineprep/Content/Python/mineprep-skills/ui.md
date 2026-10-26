# Layout & PropertyGroup

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
| `button` / `operator` | `on_clicked` / `on_hovered` / `on_unhovered`, all zero-argument (`partial` to bind values); default `EditorUtilityButton`. Empty `text` skips the inner label. When a `sizebox` limits button width, prefer `text_scaling=True` to fit long labels |
| `checkbox` | `on_check_state_changed`; default `EditorUtilityCheckBox` |
| `spinbox` | `on_value_changed` / `on_value_committed`; default `EditorUtilitySpinBox` |
| `textbox` | `hint` / `on_text_changed` / `on_text_committed`; default `EditorUtilityMultiLineEditableTextBox` (multiline widget type) |
| `combo` | ComboBoxKey; `options` is a list (`key=str(item)`) or `{key: text}`; a label may be `unreal.Text`; generate defaults to `make_combo_text`; callbacks get `str`; `on_selection_changed` / `on_opening`; default `EditorUtilityComboBoxKey`; the down arrow is hidden |
| `prop(data, property=None, text=None, categories=None, properties=None, searching=False, on_property_changed=None, pass_rootname=False)` | Omit `property` → full DetailsView. Set `property` → SinglePropertyView for a simple value or supported struct header; use full Details for containers and paired inline toggles. Filters/search apply only to the full view; see **prop** below |
| `row` / `col` / `column` | Boxes |
| `splitter` | Draggable two-pane layout; add content to `.first` / `.second`, not the returned container. See below |
| `carousel` | `speed=3` sets `move_speed` and is applied only at build. `page(i)` clamps and returns the index; `index()`, `prev()`, `next()`. `next` is bound to `previous_page` and `prev` to `next_page` because the engine page direction is reversed — call these wrappers, do not rebind them to the engine names. `on_changed(carousel, index)` runs when the slide starts. Size each page; the carousel slot ignores padding and align |
| `spacer` / `overlay` / `switcher` / `scalebox` / `sizebox` / `wrapbox` / `scrollbox` | Containers; `sizebox(w, h)` fixes axes (omit = unconstrained); `wrapbox(inner_padding=6)` wraps children |
| `image` / `custom` | Media / raw widget. `image=None` is an empty placeholder; scalar `size` is square until a texture is set. `custom(widget, props=None, **kwargs)`: prefer an `EditorUtility*` subclass when one exists |
| `border` | Container + mouse; callbacks get `Layout`, not `FGeometry` — **border** below |
| `hide(state)` | Visibility — prefer over full `redraw` when toggling regions |
| `get` / `set` | Editor properties on the widget |
| `parent` / `outer` / `children` / `path` | Hierarchy |

Interactive builders default to **Editor Utility** subclasses (`EditorUtilityButton`, `EditorUtilityCheckBox`, `EditorUtilitySpinBox`, `EditorUtilityMultiLineEditableTextBox`, `EditorUtilityComboBoxKey`). They use the editor Slate style. For `layout.custom`, pick `unreal.EditorUtility…` over the raw UMG type when it exists. Override with `subclass=` only when needed.

Prefer `layout.combo` (`{key: unreal.Text}`) for localized combo labels. If you must construct `EditorUtilityComboBoxString` via `layout.custom`, call `add_option` before parenting and pass `font`, `foreground_color`, and `selected_option` in `props=`.

### Common kwargs (`**kwargs` → `add_widget`)

| Kwarg | Meaning |
|-------|---------|
| `padding` | `Margin`, `(h,v)`, or scalar |
| `align` | `(h,v)`: `0` fill, `1` left/top, `2` center, `3` right/bottom |
| `fill` | `False` = auto size. `True` / `1` / a fraction → `SlateSizeRule.FILL` with that weight. **Siblings that fill share leftover space.** See **fill** below. |
| `clip` | Clip overflow |
| `tooltip` | Hover text |
| `hidden` | Initial visibility (int → `SlateVisibility`) |

`add_widget(..., props=None)` and `layout.custom` apply `props` with `set_editor_properties` after construct and before `add_child`. Use it for values the slate widget copies only while being built (`Carousel.move_speed`, `ComboBoxString.foreground_color`, etc.). `clip` still overwrites a `clipping` entry in `props`.

Text sharing a row with other controls should be vertically centered; use `align=(1, 2)` for a left-aligned label.

For a pinned footer, use `align=(1, 3)` on the one vertical filler (`fill=1`).

### splitter

```python
split = layout.splitter(ratio=0.5, fill=1)
split.first.text('Left')
split.second.text('Right')
# vertical=True: first above second; get_ratio() / set_ratio(value) adjust the split.
split.solo(1)  # first only: left / top
split.solo(2)  # second only: right / bottom
split.solo(0)  # restore both panes and the divider; other values also restore
```

`limits=(0.1, 0.9)` clamps the first pane's proportion. `handle_size=8` is the
drag hit area; `line_margin=3` leaves space at both ends of the line.
`color=unreal.LinearColor(0.1, 0.1, 0.1, 0.8)` is the default line color.
`on_changed(ratio)` reports changes; do not call `set_ratio()` from that callback.
The returned container also exposes `.divider`. Sizes follow the ratio without
a persistent tick; limits are proportions, not minimum pixel widths.

`solo(mode=0)` collapses the unused pane and the complete divider slot, so
the remaining pane fills the available space without a leftover gap. It keeps
the ratio, does not call `on_changed`, and returns the splitter for chaining.
It only changes pane-container visibility; visibility inside each pane is kept.

### fill (Slate FILL weights)

`fill` shares the leftover space in the widget's immediate parent by weight
(`True` ≡ `1`). Children in different parents do not compete for that space.

| Intent | How |
|--------|-----|
| Equal columns | Several siblings with `fill=1` |
| Unequal split | Different weights, e.g. `fill=0.75` and `fill=1` |
| Packed content, pinned footer | One FILL child, usually the last, with `align=(1, 3)` |
| Tight stack | Omit `fill` on everyone |

```python
# Packed Details with a footer pinned to the bottom-left
layout.prop(self.props)
layout.text('Ready', align=(1, 3), padding=6, fill=1)

# Equal-width columns
row = layout.row()
left = row.col(fill=1, padding=3)
right = row.col(fill=1, padding=3)
```

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

For a small browser, search and selection can update existing widgets with
`set_text`, brush changes and `hide()` instead of rebuilding the form. Rebuild
regions when their structure changes. Hiding a row does not clear selection.

Clear the previous image resource and its visibility when the next selection
has no texture; updating the label alone leaves a stale preview. Preserve aspect
ratio with `set_desired_size_override`, and reset any transparent placeholder tint
when assigning a valid image.

For Shift-click with `button(on_clicked=...)`, read modifier state inside the
callback:

```python
state = unreal.InputLibrary.get_modifier_keys_state()
shift = unreal.InputLibrary.modifier_keys_state_is_shift_down(state)
```

Python assignment does not fire the DetailsView's user-edit delegate. If related
values must change too, call the same update helper from both paths.

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
img = border.image(rt, size=unreal.Vector2D(1024, 1024), padding=0, fill=1)
img.target.set_visibility(unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE)
```

`get_mouse_local` / `get_mouse_uv` / `get_local_size` call Blueprint helpers (`AbsoluteToLocal`, `GetLocalSize`) with a `UWidget*` so `FGeometry` never crosses into Python. `get_mouse_uv` is `local / size` (zero size → `(0,0)`).

For empty PointerEvent data, use `mineprep.left_mouse_down()`, `middle_mouse_down()` or
`right_mouse_down()` on the UI main thread. They query **current** button state:
`True` = pressed, `False` = released, `None` = unavailable (not the same as released).
Windows/macOS use native queries; Linux tries SDL3 then X11. Record the drag mode
on Down (for example, `if mineprep.right_mouse_down() is True: ...`), then use that
recorded mode on Move/Up. A released button cannot identify which Up event fired;
these helpers do not expose the event's triggering button.

**Return value** (wrapper in `mc_widget.border`):

- `handled` means the mouse event is not passed to widgets below
- `unhandled` continues to pass it through
- Return an `EventReply` as-is. Truthy → `handled()`. Falsy / `None` → `unhandled()`.
- UE calls such as `capture_mouse` / `release_mouse_capture` return a tuple
  `(EventReply, reply)` in Python. The wrapper also passes through its first
  `EventReply`; do not reduce that tuple to a boolean or the capture request is lost.

For dragging, return `unreal.WidgetLibrary.capture_mouse(unreal.WidgetLibrary.handled(), w.target)`
on Down and `release_mouse_capture(handled())` on Up. Capture keeps Move/Up routed
to the Border outside its bounds; `handled()` alone does not capture. Paint tools
should separately stop outside-canvas drawing and break the stroke on re-entry.
Use Layout coordinate helpers when callbacks provide empty Geometry/PointerEvent
data. Handle capture loss and window-focus cleanup separately from normal release.

A child `Image` that is `Visible` takes the hit first. For drawing, set it `SELF_HIT_TEST_INVISIBLE` so the Border receives Down/Move/Up. Prefer `img.hide(unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE)` (or `set_visibility`). Size the Image with `set_desired_size_override`; `brush.image_size` may require a Slate vector type rather than `Vector2D`. After swapping the RT, `set_brush_resource_object(None)` then the RT again.

### Sketch RT

For color painting / PNG export; VAT bake RTs have different requirements.

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

Full DetailsView filters are set before the object is assigned. A non-empty `categories` or `properties` list limits that view; an empty list is the same as omitting it. `searching=True` turns on the details search bar. These three arguments are ignored when `property` selects a single field.

```python
layout.prop(component, categories=['Materials'], fill=1)
```

Category/property filters are installed when the details widget is first built.
Set them through `prop`, before object assignment. Changing either array later
does not refresh existing rows; assigning the same object again is a no-op.
Use native conditions or retained containers for interaction; see
[property metadata](property-metadata.md#conditions-and-inline-toggles).

For native visibility changes, check actual rows and enabled states; metadata,
whitelist arrays and widget identity alone do not prove the rendered result.

- Full Details callbacks may report a struct member (`X`, `R`, `FilePath`), or
  an inline toggle's dependent field. For top-level PropertyGroup names, use:

```python
layout.prop(props, pass_rootname=True, on_property_changed=changed)
```

This reports `Offset.X` as `Offset` and `Points[3].X` as `Points`, once per
changed top-level field. Full-view root mode requires a PropertyGroup;
`pass_rootname=False` (default) preserves native names.

- Single-property views (`layout.prop(props, 'Field')`) already report `Field`.
  Use full Details for arrays, sets, maps and paired inline toggles.
- With root mode active, call `props.sync_property_changes()` after in-place
  array/struct edits or direct writes to `props.uobject`. This synchronizes
  silently; ordinary top-level assignment and `load()` do so automatically.

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
# Named single field
layout.prop(self.options, 'HideRight', on_property_changed=self.on_options_changed)

# Whole PropertyGroup as DetailsView
left.prop(self.props, on_property_changed=self.on_props_changed)
```

When fields belong outside the main Details, give them a separate PropertyGroup
or use a fixed property filter when creating the view.

If a callback writes values that can trigger itself, guard against recursion.

## PropertyGroup

Prefer direct, readable declarations. See [native property metadata](property-metadata.md) for
conditions, inline toggles, numeric controls, pickers and their Python boundaries.

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

`save(path='')` / `load(path='')` persist fields to JSON (best-effort; failures log via `debug`). When `path` is omitted, the file is `{source directory}/__pycache__/{ClassName}.json` (for `ui()` classes, `{plugin Python dir}/__pycache__/{ClassName}.json`; console classes with no source file require an explicit `path`). Because `__pycache__` can hold saved `.json` configurations, do not blindly delete the entire `__pycache__` directory.

- **Default `_autosave_ = False`**. Setting `_autosave_ = True` loads the default JSON on instantiation and saves on Python `setattr` and `layout.prop` Details edits.
- **Saved fields**: all declared PropertyGroup fields (including hidden helper bools) are saved; Python-only instance attributes are not.
- **Types**: `str` fields (even strings starting with `/Game/...`) remain strings; UObject/soft fields store asset paths. `dict[K, V]` supports `str`/`int`/`bool`/`float` keys and primitive/UObject values (do not nest containers like `dict[str, list[int]]`, and do not use struct keys).

### Persistence in a temporary panel

For ordinary `ui()` panels, `_autosave_ = True` uses the existing default
`__pycache__` file. Two classes with the same name and source directory share
that filename even if their UE class GUIDs differ. Choose distinct descriptive
class names when settings should differ.

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
```

5. Renaming a field: update **all** `props.OldName`, `assign_soft_prop(..., 'OldName')`, and `on_property_changed` string compares — mismatches fail silently.
6. Access underlying UObject via `props.uobject` when UE APIs need it.

### Localization

`localize` is a **class method**, not a metadata key. Call the concrete group
class's method, for example `Options.localize('Speed', '速度', 'Speed', '速度')`,
before displaying the field. Do not write `{'localize': ...}`. The helper uses
the generated UE class name and field name as the translation key
(`GeneratedClass_GUID…:Speed`); category translations use `UObjectCategory`.
Let the helper construct these identities rather than guessing the generated name.

```python
Cls.localize('Field', zh, en, zh_tw)           # property
Cls.localize('ClassDisplay', zh, en, zh_tw)  # category-ish when not a prop name
```

## Mod `draw` order

```python
def __init__(self, context=None):
    self.props = Props()
    super().__init__(context)   # calls draw()

def draw(self, context=None):
    # build UI; close over Layout nodes for hide()/ops
    pass
```

Never `self.redraw()` from inside `draw`. Use `redraw()` only from buttons / external events when a full rebuild is required (e.g. Mod Manager advanced columns).
