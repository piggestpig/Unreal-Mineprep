# Pitfalls — Layout / PropertyGroup / paint RT

Open with [../ui.md](../ui.md). Common reload / instantiate / `force_update`: [common.md](common.md).

## PropertyGroup / SoftObjectPath

| Symptom | Cause | Fix |
|---------|--------|-----|
| Soft path set but resolves `None` | `SoftObjectPath(str)` empty on some UE builds | `import_text` / `uobject.set_editor_property` |
| `FilePath` autosave loads empty | `import_text` of a bare OS path is empty | PropertyGroup accepts a bare path; or `import_text('(FilePath="...")')` |
| Want a level Actor picker / hard `unreal.Actor` stays `None` | Transient PG UObject cannot hard-ref world actors | Keep `_softcast_ = True` (default); annotate `Actor: unreal.Actor` |
| Picker shows wrong assets | Blueprint filter without `_C` | `AllowedClasses`: `.../Asset.Asset_C` |
| Auto-fill / callback silent no-op | Renamed field; UI still compares old name | Grep old name across panel/ops/util |
| `TypeError` converting `str` to `Key` / other struct | Class default `'LeftControl'` is a Python `str` | `k = unreal.Key(); k.import_text('LeftControl'); a: unreal.Key = k` — [../ui.md](../ui.md) § PropertyGroup |
| `Cannot nativize 'Texture2D' as 'SavePath' (StrProperty)` on `load` | `/Game/...` **string** field treated as an asset | Keep `str` as text. Only `load_asset` when the field is a UObject / Soft path |

## Layout / UI

| Symptom | Cause | Fix |
|---------|--------|-----|
| Want hide column but whole UI flashes | Calling `redraw()` | Keep `Layout` ref; `right.hide(flag)` |
| Footer bool also in Details | Same PG as `layout.prop(props)` | Separate options PropertyGroup, or a fixed property filter for the main view |
| Footer log sits under a large empty gap | Details `prop` and footer `text` both `fill=1` in the same vertical box — they split leftover height | Omit `fill` on the `prop`; only the footer gets `fill=1` + `align=(1, 3)` |
| Footer hugs content inside a `switcher` page | switcher/page default packs to the top | `layout.switcher(align=(0, 0), fill=1)` then `pages.col(align=(0, 0))`; footer `fill=1` + `align=(1, 3)` |
| 「不支持的属性」 in a column | SinglePropertyView cannot display container rows | Use full `left.prop(group)`; split groups or fixed view filters for separate columns |
| Inline toggle missing beside a value | SinglePropertyView does not display paired inline controls | Full `layout.prop(group)` — [metadata](../property-metadata.md#conditions-and-inline-toggles) |
| `module 'unreal' has no attribute 'is_valid'` | There is no `unreal.is_valid` | `unreal.SystemLibrary.is_valid(obj)` |
| `SystemLibrary.is_valid(DetailsView)` throws `ObjectInstance is null` | Destroyed/stale UMG widget: validity checks may raise | Guard the check; unbind selection callbacks in `Mod.destruct` |
| Python delegate callback stops after garbage collection | The temporary delegate wrapper was released | Keep the delegate itself (`self.delegate = obj.on_event`), then call `add_callable_unique`; remove the callable and release that reference when its owner closes or unregisters. Keeping only the Python function or a bound flag is insufficient |
| `TypeError: DeprecateSlateVector2D` on Image | `brush.image_size = Vector2D` | `set_desired_size_override(size)` |
| `Text + str` or `str.join(notes)` raises `TypeError` | `bilingual()` / `localize()` return `unreal.Text` | Convert before concatenation / join; `set_text` accepts Text directly |
| Mod Manager-style toggle needs full rebuild | Structural rows depend on flag | `on_property_changed=lambda _: self.redraw()` (OK **outside** `draw`) |
| `ZeroDivisionError` on Border mouse / `get_local_size` is `(0,0)` | Python `FGeometry` is an empty copy — **UMG Geometry** below | `layout.border` callback `Layout`; `get_mouse_local` / `get_mouse_uv` |
| `NameError: name 'Layout' is not defined` on `reload()` | `Callable[[Layout], ...]` inside `class Layout` is evaluated while the class is still being created | `Callable[['Layout'], ...]` (quotes) |
| Image on a paint Border never gets Down/Move | Child `Image` is `Visible` and eats the hit | `SELF_HIT_TEST_INVISIBLE` on the Image |
| `EditorUtilityComboBoxString` text is black | Python `construct` is not an editor widget, so `foreground_color` stays `(0,0,0)` and is copied only in `RebuildWidget` | Set it in `custom(..., props=)` before parenting. A later change needs `remove_from_parent` and add again. Not a localization widget — [../ui.md](../ui.md) |

`Layout.hide(True)` → Collapsed; `hide(False)` → Visible (bool cast to `SlateVisibility` index).

## UMG Geometry (Python empty struct)

`FGeometry` size/transform fields are not reflected to Python, so `widget.get_cached_geometry()` and pointer-event `FGeometry` arguments arrive in Python with local size `(0, 0)`.

- **Do**: use `layout.border` (callbacks receive the Border's `Layout`) and call `w.get_mouse_local()`, `w.get_mouse_uv()`, and `w.get_local_size()`. EventReply rules: [../ui.md](../ui.md) § border.
- **Do not**: call `SlateLibrary.absolute_to_local` / `get_local_size` on `FGeometry` in Python, or pass `FGeometry` from Python into Blueprint functions.

## Paint / sketch RT

Painting recipe: [../ui.md](../ui.md#sketch-rt).

| Symptom | Cause | Fix |
|---------|--------|-----|
| `rt.resize_target` missing | Not bound in Python | `unreal.RenderingLibrary.resize_render_target2d(rt, w, h)` |
| Click / drag / round brush glaze differently; trails blotchy | `draw_line` is opaque and skips zero-length; each move composites line + 2 caps | Coverage RT + one translucent composite — [../ui.md](../ui.md) § Sketch RT |

Dark exports and canvas loss after refresh: [Textures / RT](common.md#textures--rt).
VAT bake RTs (AnimToTexture cache, premul): [vat.md](vat.md) — not this file.
