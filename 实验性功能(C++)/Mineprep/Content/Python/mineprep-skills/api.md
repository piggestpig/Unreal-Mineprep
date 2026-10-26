# Mineprep API reference

Facade: `Plugins/Mineprep/Content/Python/mineprep.py`  
Prefer `mineprep.*`. Use `obj.help()` / `mineprep.help()` for on-screen tips.  
`unreal.*` class/method names: [UE5 Python API](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/) for the installed version. If a call fails or the skill is silent, read the matching source.

```python
import mineprep
# After editing mineprep.py / mc_*.py or a ReloadWithMineprep mod:
# mineprep.reload()
```

Outside Unreal, the public modules use `mc_utils.Lazy` as an `unreal` placeholder and skip editor config loading so pure-Python helpers and tests can import them offline. Functions that touch Unreal still require the editor runtime.

## Quick map

| Area | API |
|------|-----|
| Help | `mineprep.help()`, handle `.help()` |
| World | `actor` / `actors`, `selected`, `component` / `components`, `materials` |
| Sequencer | `sequencer`, `bindings`, `tracks`, `sections`, `channels`, `keys`, `keyframe`, `Rig` / `actor.rig` |
| Plugin UI | `panel`, `toolbar`, `hotkey` |
| Editor UI | `Layout`, `ui(...)`, `PropertyGroup`, `save` / `load`, `_autosave_` |
| Mods | `Mod`, `mods.register` / `unregister` / `register_all` |
| Loc | `bilingual`, `localize`, `loctext`, `tooltip` |
| Spawn | `spawn_block/item/mob/preset`, `attach`, `spawn_blocks`, `spawn_structure`, `Blocks`, `structure_parts`, `get_all_blocks` |
| Mesh | `merge_skm`, `Blocks.bake` |
| Assets & Config | `uasset`, `uclass`, `bpclass`, `construct`, `copy`, `config`, `paths` |
| Blueprint libs | `BPLib`, `EditorBPLib`, `BPLibCaller` — call a Blueprint function library by function, attribute, or subscript. Not `unreal.mineprep` |
| Utils | `prints`, `warn`, `throw`, `panic`, `undo`, `world`, `cast`, `enum`, `startfile`, `dialog`, file dialogs, `send2trash`, `screenshot` |
| Mouse state | `left_mouse_down()`, `middle_mouse_down()`, `right_mouse_down()` → `bool` or unavailable `None`; current state, UI main thread; [drag usage](ui.md#border--mouse) |
| Parallel | `delay`, `tick`, `asynctask`, `thread`, `asyncthread`, `until` — [parallel.md](parallel.md) |
| Prep & Textures | `prep_texture`, `colorize_material`, `load_mcprep_data`, `tex_to_color`, `color_to_tex`, `ColorList`, `tex_source_files`, `export_tex_cache`, `import_data_tex`, `register_biome_tex`, `clear_biome_tex` |
| Experimental C++ | `unreal.mineprep.*` — last resort after `mineprep.*`; [cpp.md](cpp.md) |

## Handles (actors / components / materials)

Call form returns a **handle** (unknown attrs forward to `.target`). Class subscript returns the **raw UObject**.

```python
a = mineprep.actor('MyActor')           # label / wildcard / type / callable → handle
raw = mineprep.actor['Steve']           # same lookup, .target (UObject)
mineprep.actors('Cube*').set('hidden', True)   # collections broadcast
a.comp(unreal.StaticMeshComponent)      # by type; same as a.component(...)
a.comp('Body*')                         # by component object name / wildcard
a.comp()                                # root component
a.comps()                               # all components
a.mats()
a.get('prop'); a.set('prop', value)     # int may coerce to enum
a.key('prop', value, time)             # int=display-rate frame, float=seconds; not Control Rig
a.rig()                                 # Control Rig on default SKM; a.rig('Head') for a named SKM
sel = mineprep.selected()                      # selected actors, same actors handle
mineprep.selected[0]                           # first selected actor (raw UObject)
mineprep.selected(0)                           # actor handle; -1 last, 0.5 proportional
mineprep.actors(0.5)                           # actor handle from the default actor collection
mineprep.selected(unreal.SkeletalMeshActor)    # type / label / callable, selection only
```

`selected()` and `selected(unreal.Actor)` are the current editor selection. A class, label wildcard, or callable filters that selection and does not search the rest of the level. `selected(0)`, `selected(-1)`, and `selected(0.5)` return an `actor` handle at that index; `actors(n)` does the same for the default actor collection, and `components(n)` returns a `component`. Class subscript `[0]` stays the raw object. Call it on the game thread. An empty selection is an empty `actors` handle; a numeric call on an empty collection wraps `None`.

- Subscript class filter: `mineprep.actor[unreal.StaticMeshActor]`
### Collections

Use `len(mineprep.actors())` to count actors. Collection handles support integer
indices, slices, index lists and boolean masks: `items[0]`, `items[:3]`,
`items[[0, 2]]`, `items[[True, False]]`. Masks must match the intended collection.
Class indexing such as `mineprep.actors[[0, 2]]` selects from the default collection.
A float class index uses the same 0–1 ratio as `List`: `mineprep.selected[0.5]` is `floor(0.5 * n)`.
Multi-axis indexing requires nested indexable elements; see ColorList below.

Use `if items` / `if not items` to test whether a collection is nonempty / empty.
For a single-object handle, `if handle` means `handle.target is not None`;
`len()` is not supported. Wrapped values such as `0` or `False` still count as
present. This does not check whether an Unreal object has been destroyed.

### Batch calls

`items(fn, *args)` applies `fn(item, *args)` to each target. Attribute access and
method calls also forward to the targets. In contrast, `mineprep.actors(predicate)`
filters actors during lookup. Scalar comparisons on the underlying List produce
masks; comparing two lists follows normal Python list comparison.

- Prefer handles for `get` / `set` / `key` / `comp`. Under RE, if you need a UObject method that the handle does not wrap, use `.target` or the class subscript.

## `copy`

```python
mineprep.copy(actor, (x, y, z))          # duplicate an actor; target is a location
mineprep.copy('/Game/Mineprep/Render/MC关卡序列', '/Game/demo')
```

Assets: `target` is a package path. The first free path is `target`, then `target_2`, `target_3`, …. A string source is used as given. A missing source returns `None`. Omit `target` to duplicate beside the source; that lands on `…/Name_2` because the source path is already taken. Actor copy takes a coordinate, not a path.

## Sequencer (Level Sequence)

```python
mineprep.sequencer()                              # current Level Sequence handle
mineprep.sequencer(seq).bindings('MC摄像机').actor()  # bound level Actor, or None
mineprep.keyframe(target, prop, value, time=None) # Actor/Component Transform + properties
```

`bindings.actor()` needs the sequence open and focused. It returns the Actor only when the name matches exactly one binding and that binding has resolved. Right after `open_level_sequence`, wait with `until` — [parallel.md](parallel.md). `binding.binding_id` is a Guid; the handle builds `MovieSceneObjectBindingID` itself.

`key` / `keyframe` time: an `int` is a frame at the sequence **display rate**, a `float` is seconds. Read `get_display_rate()` before reusing frame numbers from another rate. Preset `/Game/Mineprep/Render/MC关卡序列` is 60 fps and already contains the `MC摄像机` binding. `LevelSequenceFactoryNew` does not. Rotation keys use `Rotation.X` roll, `Y` pitch, `Z` yaw — [pitfalls/common.md](pitfalls/common.md).

Chain: `bindings` → `tracks` → `sections` → `channels` → `keys`.

**Not AnimSequence bone tracks.** Listing / clearing skeletal animation curves is engine API — [pitfalls/anim.md](pitfalls/anim.md).

**Not Control Rig.** `keyframe()` does not write CR channels. Use `actor.rig` below.

## Control Rig

Needs an **open** Level Sequence (`throw` if none). The track hangs on the **SkeletalMeshComponent** possessable, not the Actor. `rig_class=None` → `FKControlRig`. Existing tracks keep their layered flag; **new** tracks are layered.

```python
r = mineprep.actor('Steve').rig()                 # first SKM → FK
r = mineprep.actor('Steve').rig('Head')           # named SKM
r = mineprep.actor('Steve').rig(
    rig_class='/Game/Path/MC_IK绑定')             # custom IK — keyword, not positional
r.names()
r.set('head', unreal.Rotator(pitch=0, yaw=0, roll=30))
r.key('head', unreal.Rotator(pitch=28, yaw=0, roll=0), 8)  # int=frame, float=seconds
```

- `actor.rig(target=SKM, rig_class=None)` → `component(target).rig(rig_class)` (SKM only)
- Names: full path, last segment, strip `_CONTROL` / `_CURVE_CONTROL`, case-insensitive; ambiguous → throw
- FK bones are `EulerTransform`; pass `Rotator` / `Vector` / `Transform` / `EulerTransform`
- `Rig.key` does `set` then `set_key=True` (a lone first `set_key` on a fresh track misses Sequencer)

`r.get(name, time=None)` returns the control value through the same name resolution and time conversion as `set` / `key`: integer = frame, float = seconds at the sequence display rate, omitted / `None` = current local playhead. It does not call setters or add keys. UE's getter evaluates the sequence at the requested time; it is not a passive dictionary lookup.

On a newly created Control Rig track, even `Rig.key()` can return before any keys exist when creation and first keying happen in the same editor tick. Let the editor process a frame (for example, use a subsequent MCP call), then key and inspect the actual channels. Do not recreate tracks repeatedly or report success from the return value alone.

Axes, retiming, split Body/Head SKMs: [pitfalls/anim.md](pitfalls/anim.md).

## Plugin chrome (`panel` / `toolbar` / `hotkey`)

`panel` and `toolbar` talk to Mineprep's editor widgets / hotkey Blueprint, not to arbitrary UMG. `hotkey()` with no name prints every shortcut (chord, tooltip). `hotkey(name)` runs the Editor Shortcuts mod (`execute_shortcut`): saved Python when that shortcut has code, otherwise the same-named function on `/Mineprep/Mineprep自定义快捷键`.

```python
mineprep.panel()                         # print cached widget paths (avoid under RE)
w = mineprep.panel('生成器子面板.放置方块选项')
mineprep.toolbar('SomeToolbarButton')
mineprep.hotkey()                        # print every shortcut
mineprep.hotkey('放置空物体')
```

`panel` reads `WidgetsCache` (`public=True`, or `mcvars.DebugMode`). Lookup is exact; a miss warns with substring candidates. Remote Mod / `ui` tabs: [remote.md](remote.md) § panel. `click(-1)` is left click.

```python
mineprep.panel('生成MC天空_可右键').click(-1)
mineprep.panel('渲染输出子面板.画质预设选项').select(-1)
mineprep.panel('渲染输出子面板.ue一键渲染按钮').click(-1)
```

Sky blueprint: `/Game/Mineprep/MC_Blueprint/Core/天空/MC天空`. The button keeps a single
actor of that class; selection alone does not prove creation. Allow an editor
frame after changing the quality preset before starting a render. One-click
render uses `Saved/MovieRenders/`; inspect the active output settings for filenames.
`MoviePipelineQueueSubsystem.is_rendering() == False` means idle, not necessarily
a successful render. Check completion/error information and the requested output.

## Spawn

### Place one mob, item or block

Call the matching helper directly (English or Chinese names both work):

```python
import mineprep

spawned = mineprep.spawn_mob('Blaze')  # or '烈焰人'
```

Without `loc`, the generator places in front of the editor camera; pass `loc`, `rot`, or `scale` for explicit placement. Other helpers: `spawn_block('stone')`, `spawn_item('diamond')`, `spawn_mob('zombie', baby=True)`, `spawn_preset(name)`, `attach(name)` (attaches to current selection).

### Recover a failed placement

1. **Missing generator panel / cache**: call `mineprep.open_main_panel()`, let the editor run ~1s in a separate call (do not block UE with `time.sleep()`), then verify the widget is cached.
2. **Verify before retrying**: a `None` return or `不存在` warning can still happen if a Blueprint wrote `mineprep.ActorCache` instead of `mcvars.ActorCache`. Check the level before calling `spawn_*` again.
3. **Unknown mob name**: once the generator is ready, query `mineprep.panel('生成器子面板.放置生物选项').get(list)`. If the species is not in that list and no actor was created, fall back to `mods.VanillaMobLoader` ([README](../mods/VanillaMobLoader/README.md)) across separate editor calls:

```python
# 1. Start catalog job
from mods.VanillaMobLoader import api as mob_api, importer as mob_importer
mob_catalog_job = mob_api.load_catalog()
```

```python
# 2. When mob_catalog_job.state == 'completed', search by English name
mob_catalog = mob_catalog_job.result['catalog']
mob_matches = mob_catalog.search(category='ALL', query='nautilus')
[(e.key, e.id, e.name) for e in mob_matches]
```

```python
# 3. Build the chosen entry
assert len(mob_matches) == 1, 'Select the intended entry from the matches first'
mob_build_job = mob_api.build_entity(mob_catalog, [mob_matches[0].key])
```

```python
# 4. When mob_build_job.state == 'completed', place once (pass target=(loc, False) for explicit position)
placed_mob = mob_importer.place(mob_build_job.result['mesh'])
placed_mob
```

If the cached catalog has no match, try `mob_api.load_catalog(refresh=True)` once. Never busy-wait on running jobs.

### Structures and repeated blocks

These APIs still require the Unreal Editor and Mineprep assets; this is not a claim of commandlet or standalone Python support.

```python
mineprep.spawn_blocks(mesh, transforms, loc=(0, 0, 0), rot=(0, 0, 0))
mineprep.spawn_structure(
    r'C:\path\file.nbt', loc=(0, 0, 0), rot=(0, 0, 0),
    gpu=0, cull=0, merge=0, reload=False, name='', center=False, groups=1,
    repair_trapdoors=False)
# source: file path or Blocks (not filepath=)
# gpu=0 ISM instances, 1=PCG actor, 2=Niagara actor
# groups: PCG balances type counts; Niagara optimizes rendering cost
# GPU palettes cap at 256 types/actor; groups increases automatically with warn
# see structure.md for per-group texture naming/overwrite behavior
# cull=0 off, 1=per-type, 2=opaque + same-type transparent interior,
# 3=2+AABB sides&bottom (keep top); water keeps its same-fluid interior rule
# merge=0 off, 1=1D runs, 2=2D quads, 3=3D boxes (full cubes only; after cull)
# reload=True re-imports JSON meshes that already exist under /Game/mc/...
# name overrides the source name used for actor labels/folders and GPU textures
# center=False: files and Blocks both preserve grid coordinates
# center=True: anchor original grid bounds at their bottom-center before cull/merge
# Blocks also offers b.spawn(gpu=1, merge=3), returning the same Actor list
# repair_trapdoors=True opts into neighbour-based repair for faulty file exports
mineprep.import_block(path, asset_name='oak_stairs', reload=False)
mineprep.import_item(path)
mineprep.resolve_block_json_path('oak_stairs')  # models/block/*.json
mineprep.get_all_blocks()                      # sorted stems in models/block
mineprep.get_all_blocks(r'^(campfire|cobblestone)$')  # re.search; '' = all
```

`get_all_blocks` lists **model JSON stems**, not NBT. Vanilla cell names (`lilac` + `half=lower`, `oak_fence` + NESW) still go through `structure_parts` → stems like `lilac_bottom` / `oak_fence_post`. JSON exists ≠ it was placed.

NBT→mesh details (coords, stairs/fence multipart, uvlock): [structure.md](structure.md).
`blocks.bake(...)` creates one reusable StaticMesh without placing Actors;
see [baking options, cell-center pivot and asset reuse](structure.md#blocksbake-one-reusable-model).

Pure batch math is available offline as `mc_math.boxes_to_packed(coords, sizes=1,
rot=0, origin=(0,0,0))`; editor alias: `mineprep.boxes_to_packed`. It returns a
float32 dict of instance **centers**, encoded rotation and local scale. The
fixed model pivot is MC `(8,8,8)`, not each model's actual bounds center.
See the [offline example](structure.md#offline-batch-math).

For procedural structures, use a supplied file or `Blocks` → `spawn_structure(source=...)`; do not assume a matching tree/house NBT is bundled. Terrain, biomes and buildings composed with terrain use [WorldGenerator](worldgenerator.md); its presets are not file sources for `spawn_structure`.

Example oak — two 5×5 canopy layers (corners off) plus two 5-leaf cross layers on top (`r=1` also skips corners). This is one composition example, not a required starting shape for other structures. Execute only when editor work is requested; otherwise provide the snippet (Output Log, console = **Python**):

```python
import mineprep

loc = (0, 0, 0)
gpu = 0  # 0=ISM, 1=PCG, 2=Niagara
h = 5

b = mineprep.Blocks(name='oak')
for y in range(h):
    b.add('oak_log', 0, y, 0, axis='y')
for y, r in ((h - 2, 2), (h - 1, 2), (h, 1), (h + 1, 1)):
    for x in range(-r, r + 1):
        for z in range(-r, r + 1):
            if x == 0 and z == 0 and y < h:
                continue
            if abs(x) == r and abs(z) == r:
                continue
            b.add('oak_leaves', x, y, z)
out = mineprep.spawn_structure(b, loc=loc, gpu=gpu)
print('ACTORS', len(out))  # actor count, not block count or proof all models imported
```

ISM-only alternative: `for mesh, transforms in b.types(): mineprep.spawn_blocks(mesh, transforms, loc=loc)`. GPU (`gpu=1|2`) must use `spawn_structure`, not `types()`.

Houses / wells can use `Blocks` + loops; choose geometry for the requested design. Oriented blocks below; roof example in [structure.md](structure.md). Use a visual reference if it helps resolve the design.

**Oriented blocks** (stairs, fence, pane, door, logs): vanilla properties on `Blocks.add`. Do not guess yaw. Logs and the other column blocks (`axis` / Bedrock `pillar_axis`) keep their end grain: `y` upright, `z` along UE Y, `x` along UE X. Standing signs, banners and heads use `rotation` 0–15 as a 22.5° yaw (0 faces south).

```python
b.add('oak_stairs', 0, 0, 0, facing='east', shape='straight', half='bottom')
b.add('oak_fence', 1, 0, 0)
b.connect()  # fences/panes/bars/walls, gate in_wall and stair corners
```

User-supplied `.nbt` → `spawn_structure(source=path)` (or `Blocks.from_file`).
Direct file placement uses numeric palette data; `Blocks.from_file` creates
editable cells. See [file processing](structure.md#file-processing-and-editable-cells).
`b.bounds()` returns current non-air `(lo, hi)` in MC XYZ (exclusive hi), or
`None`; read-only `b.source_size` retains original file dimensions, or `None`
for ordinary construction. See [bounds and source dimensions](structure.md#cell-bounds-and-source-dimensions).
`Blocks.from_file`, `parse_structure` and `spawn_structure` default to
`repair_trapdoors=False`, preserving authored trapdoor facing.
`b.connect(families=None, positions=None)` can limit recomputation by family
and existing cell positions while reading neighbours from the full container.

`Blocks.rotate(90, pivot=(0,0,0))` and `Blocks.mirror('x', pivot=0.5)` transform
cells and Java states in place. Positive rotation maps north to east; pivots use
MC cell-centre coordinates. `connect_fences()` remains the fence/pane/bar-only
entry. Full contracts, offline `mc_blockstates` and state-only
`rotate_state` / `mirror_state`: [structure.md](structure.md#connections-and-grid-transforms).


## `merge_skm`

Exported as `mineprep.merge_skm` (implemented in `mc_mesh.py`).

```python
mineprep.merge_skm(root, save_path=None, name=None,
                   merge_mat=True, skm=True, sm=True, overwrite=False)
```

| Flag | Meaning |
|------|---------|
| `skm` / `sm` | Keep skeletal / static children (and root body when `skm`) |
| `skm=False, sm=True` | Items only on skeleton — still needs root SKM for bones |
| `overwrite=False` | Dest exists → `warn` + `None` |
| `overwrite=True` | Update existing SKM via `copy_mesh_to_skeletal_mesh` (no delete) |

Geometry Script traps (mat IDs, compact, vertex color, transforms): [pitfalls/mesh.md](pitfalls/mesh.md).

## Texture utilities (`mc_material.py`)

### `tex_to_color` / `color_to_tex` / `ColorList`

`mineprep.tex_to_color(tex)` reads a `Texture2D` or `TextureRenderTarget2D` into a 2D `ColorList` (`[y][x]` of `LinearColor` in `0..1`). `mineprep.color_to_tex(colors, width=0)` converts a 1D or 2D color sequence into a transient nearest-filtered sRGB `Texture2D` (2D uses row length as width; 1D uses `width=` if given, else a square or single row).

Use `ColorList.from_rows(rows)` for a manually constructed 2D pixel table so 3- or 4-element grayscale rows are not treated as a single RGB/RGBA tuple:

```python
import mineprep

grid = mineprep.ColorList.from_rows([
    [0, 0, 0, 1],
    [1, 0, 0, 1],
])
grid[0, 1] = (0, 1, 0)  # RGB pixel
```

`ColorList` supports `List` indexing: `grid[y, x]`, slices, boolean masks, and UV float indices (`grid[:0.5, :]` top half, `grid[:, 0.5:]` right half; integer `-1` is the last item, while float `-1.0` wraps to `0.0`).

```python
grid = mineprep.tex_to_color(tex)  # ColorList of ColorList
grid[y, x] = (1, 0, 0)             # assign gray, RGB/RGBA tuple, Color, or LinearColor
grid[:, 0.5:] = (1, 0, 0)          # broadcast across a slice
tex = mineprep.color_to_tex(grid)
tex = mineprep.color_to_tex(flat, width=64)
```

### Source and data texture helpers

Run these on the editor game thread (`mc_material.py`):

| Function | Purpose & return value | Scope / notes |
|----------|------------------------|---------------|
| `mineprep.tex_source_files(texture)` | Returns `tuple[Path, ...]` of absolute source file paths recorded on a `Texture2D` (`()` if none) | Keeps recorded paths even if the file is missing on disk |
| `mineprep.export_tex_cache(texture, path='')` | Exports a `Texture2D`'s source data to `.png` or `.exr` (default `<project>/cache/`) and returns its `Path` | Reuses the cached file when source data is unchanged; requires valid `TextureSource` (no virtual textures) |
| `mineprep.import_data_tex(path)` | Imports a `.png` or `.exr` file as a transient `Texture2D` | Configured as linear (`srgb=False`), `TF_NEAREST`, `TA_CLAMP`; caller must retain a strong reference |

### `register_biome_tex` / `clear_biome_tex`

- `mineprep.register_biome_tex(source) -> int`: looks up `source` (`unreal.Texture`) in `/Game/Mineprep/材质/Core/生物群系纹理集合` and returns its slot index. If absent, writes into the first `None` slot or appends to the end, then saves the asset. Returns `-1` on invalid input or missing collection.
- `mineprep.clear_biome_tex(target=None) -> bool`: cleans up the biome texture collection and saves if changed:
  - `None`: removes empty slots and duplicates (keeps first occurrence).
  - `int`: sets that slot index to `None` (`-1` = last slot) without shrinking.
  - `Texture`: sets all matching slots to `None`.
  - `True`: keeps only the first two slots (`False` is rejected).

## Localization

```python
mineprep.bilingual('中文', 'English')                 # mod_info / short labels
mineprep.localize(source, zh, en, zh_tw, ...)       # multi-lang UI
# PropertyGroup fields: Cls.localize('FieldName', zh, en, zh_tw)
```

`bilingual` / `localize` / `loctext` return **`unreal.Text`**, not `str`:

```python
message = str(label) + '\n'  # convert to str before + or join
widget.set_text(label)       # set_text and f-strings accept unreal.Text directly
```

Args after `source` follow `mcvars.Languages` order. Pass the **Python attribute name** as the field key on `Cls.localize`. `loctable_col` reads `mcvars.LocalizationCache`.

## Reload

Use **only** after editing plugin Python (`mineprep.py` / `mc_*.py`) or a `ReloadWithMineprep` mod. Ordinary `ui()` / console snippets do not reload first.

```python
mineprep.reload()
```

- Updates the existing `mineprep` module object in place (console `mineprep.reload()` is enough) and re-registers mods with `ReloadWithMineprep=True`
- Prefer this over `importlib.reload(mineprep)` — duplicate `Layout`/`PropertyGroup` class objects cause `KeyError` / stale Props
- Mod submodule removal, re-registration and panel cleanup: [Reload workflow](mods.md#reload-workflow).
- `from mineprep import func` leaves a separate binding: re-import it after reload, or use `mineprep.func`. Assigning the return value to `mineprep` does not refresh that separate binding.
- MCP `run` keeps one namespace for the editor process. `mineprep` is injected on every call. An earlier `import mc_structure` (any `mc_*` except `mcvars`) stays on the module from before `reload()`. Re-import that name in the snippet, or use the `mineprep` attribute. [remote.md](remote.md) § MCP Python.
- Full reload clears the Props registry; `_unique_` does not preserve state or
  migrate objects/callbacks. Follow the panel cleanup rules linked above.
- `mcvars` is **not** unloaded. Handshake caches belong there (`ActorCache`, `SpawnNameCache`, `SpawnIDCache`, `LocalizationCache`; `WidgetsCache` is on `mc_widget` and is copied). Do not store Blueprint-written globals on `mineprep.py`: `_adopt_module` copies function objects whose `__globals__` still point at the discarded new module.

## Warn / errors

```python
mineprep.warn('simple message')
mineprep.warn(f'导入方块失败: {path}', exc)  # Exception → full traceback in log
mineprep.throw('fatal')                      # on-screen error, then raise
mineprep.panic('title', 'message')           # Yes → continue; No → throw
```

## Undo

`@mineprep.undo` / `undo('Transaction Name')` wraps editor transactions. Many handle mutators already use it.

## Delay / tick / thread

`delay`, `tick`, `asynctask`, `thread`, `asyncthread`, `until` live in `mc_parallel.py`. Choose a decorator and the game-thread rules: [parallel.md](parallel.md). `until` is the `yield from` wait inside `@asynctask`.

```python
@mineprep.delay(0.5)
def later():
    mineprep.prints('0.5s')

@mineprep.asynctask
def task():
    yield 0.5
    return 'done'
```

Do not call `unreal.*` or `mineprep.prints` from `@thread` / `@asyncthread` workers. Do not poll a `Future` with ticker `delay=0`.

## Live editor (MCP / Remote Execution)

Authoring never requires a live connection for Q&A. Editor work and live test policy: [SKILL.md](SKILL.md) § Testing. Arbitrary in-editor Python: MCP `mcptools.PythonTools.run` ([remote.md](remote.md)). Viewport capture: [remote.md](remote.md) § screenshot. Open Mod / `ui` tabs: [remote.md](remote.md) § panel.
