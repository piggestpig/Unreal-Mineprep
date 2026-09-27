# Mineprep API reference

Examples marked complete include their setup. Other snippets are API or callback fragments: names such as `self`, `layout`, `mesh` and `anim` come from the surrounding task. Syntax validation alone does not make a fragment standalone.

Facade: `Plugins/Mineprep/Content/Python/mineprep.py`  
Prefer `mineprep.*`. Use `obj.help()` / `mineprep.help()` for on-screen tips.  
`unreal.*` class/method names: [UE5 Python API](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/) for the installed version. If a call fails or the skill is silent, read the matching source. Probe in-editor when runtime verification is in scope; keep necessary error handling, but do not hide guessed APIs behind `try/except`.

```python
import mineprep
# After editing mineprep.py / mc_*.py or a ReloadWithMineprep mod:
# mineprep.reload()
```

## Quick map

| Area | API |
|------|-----|
| Help | `mineprep.help()`, handle `.help()` |
| World | `actor` / `actors`, `component` / `components`, `materials` |
| Sequencer | `sequencer`, `bindings`, `tracks`, `sections`, `channels`, `keys`, `keyframe`, `Rig` / `actor.rig` |
| Plugin UI | `panel`, `toolbar`, `hotkey` |
| Editor UI | `Layout`, `ui(...)`, `PropertyGroup`, `save` / `load`, `_autosave_` |
| Mods | `Mod`, `mods.register` / `unregister` / `register_all` |
| Loc | `bilingual`, `localize`, `loctext`, `tooltip` |
| Spawn | `spawn_block/item/mob/preset`, `attach`, `spawn_blocks`, `spawn_structure`, `Blocks`, `structure_parts`, `get_all_blocks` |
| Mesh | `merge_skm` |
| Assets | `uasset`, `uclass`, `bpclass`, `construct`, `copy` |
| Utils | `prints`, `warn`, `throw`, `panic`, `undo`, `world`, `cast`, `enum`, `startfile`, `dialog`, file dialogs, `send2trash`, `screenshot` |
| Parallel | `delay`, `tick`, `asynctask`, `thread`, `asyncthread`, `until` — [parallel.md](parallel.md) |
| Prep | `prep_texture`, `colorize_material`, `load_mcprep_data`, `tex_to_color`, `color_to_tex`, `ColorList` |
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
```

- Subscript class filter: `mineprep.actor[unreal.StaticMeshActor]`
### Collections

Use `len(mineprep.actors())` to count actors. Collection handles support integer
indices, slices, index lists and boolean masks: `items[0]`, `items[:3]`,
`items[[0, 2]]`, `items[[True, False]]`. Masks must match the intended collection.
Class indexing such as `mineprep.actors[[0, 2]]` selects from the default collection.
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

UE 5.8.2 runtime check (2026-09-22): after track initialization, frame 24 and 1.0 seconds matched at 24 fps; omitted time read frame 0. Reads left the 18 test keys, playhead and observed skeletal bone transform unchanged. Other rig types and all control types were not exhaustively tested. UE 5.8 may emit `find_control` / control-settings deprecation warnings.

Axes, retiming, split Body/Head SKMs: [pitfalls/anim.md](pitfalls/anim.md).

## Plugin chrome (`panel` / `toolbar` / `hotkey`)

These talk to Mineprep's editor widgets / hotkey Blueprint, not to arbitrary UMG.

```python
mineprep.panel()                         # print cached widget paths (avoid under RE)
w = mineprep.panel('生成器子面板.放置方块选项')
mineprep.toolbar('SomeToolbarButton')
mineprep.hotkey('SomeFunction')
```

`panel` reads `WidgetsCache` (`public=True`, or `mcvars.DebugMode`). Lookup is exact; a miss warns with substring candidates. Remote Mod / `ui` tabs: [remote.md](remote.md) § panel. `click(-1)` is left click.

```python
mineprep.panel('生成MC天空_可右键').click(-1)
mineprep.panel('渲染输出子面板.画质预设选项').select(-1)
mineprep.panel('渲染输出子面板.ue一键渲染按钮').click(-1)
```

Sky blueprint: `/Game/Mineprep/MC_Blueprint/Core/天空/MC天空`. The button keeps a single actor of that class. `SelectActor` can fail with invalid flags, so confirm that class count, not the current selection. `yield` (or `until`) between the quality preset and the render click. One-click render writes `Saved/MovieRenders/` (observed file `MC.mp4`).

## Spawn

### Place one mob, item or block

For a simple placement request, call the matching helper directly. Example:

```python
import mineprep

spawned = mineprep.spawn_mob('Blaze')
```

The Chinese name is also accepted: `mineprep.spawn_mob('烈焰人')`.
These are alternatives; do not execute both for a request to place one mob.
Without `loc`, the generator Blueprint attempts placement in front of the editor
camera. Supply `loc`, `rot` or `scale` only when the user requests a particular
placement. Do not first calculate camera offsets, inspect panel state, enumerate
mob options or search for Blueprint assets when the requested mob is known.

Other helpers: `spawn_block('stone')`, `spawn_item('diamond')`,
`spawn_mob('zombie', baby=True)`, `spawn_preset(name)` and `attach(name)`.
`attach` uses the current selection. These APIs run through generator widgets;
that dependency is a troubleshooting concern, not a mandatory preflight.
After a successful call, use the returned actor as evidence; inspect its placement
only when the task calls for it.

### Recover a failed placement

- Missing-panel / cache errors: call `mineprep.open_main_panel()`. It reuses an
  existing main-panel widget or opens one, but does not wait for Blueprint cache
  registration. Let the editor run for about one second before checking the
  specific missing widget in a subsequent call. Wait on the host or schedule a
  game-thread callback; do not block the editor with `time.sleep()`.
- Retry the original placement once only after confirming it did not already
  create an actor and the missing widgets are ready. A timeout, `None` result or
  an `不存在` warning alone does not prove that nothing spawned. If the outcome
  is uncertain, inspect the relevant scene state before retrying; do not loop
  through panel opening, reload or repeated spawn calls.
- Query `mineprep.panel('生成器子面板.放置生物选项').get(list)` only when the requested name
  is unknown or fails after the generator is ready. Known names do not require
  option enumeration. Persistent errors belong in a focused diagnostic, not a
  replacement generator implementation.

For backend debugging, `spawn_helper` reads the actor from `mcvars.ActorCache`.
An actor can appear despite an error if a Blueprint writes `mineprep.ActorCache`
instead. Inspect that handshake when the symptom occurs; it is not normal setup.

### Structures and repeated blocks

These APIs still require the Unreal Editor and Mineprep assets; this is not a claim of commandlet or standalone Python support.

```python
mineprep.spawn_blocks(mesh, transforms, loc=(0, 0, 0), rot=(0, 0, 0))
mineprep.spawn_structure(
    r'C:\path\file.nbt', loc=(0, 0, 0), rot=(0, 0, 0),
    gpu=0, cull=0, merge=0, reload=False, name='', center=None)
# source: file path or Blocks (not filepath=)
# gpu=0 ISM instances, 1=PCG actor, 2=Niagara actor
# cull=0 off, 1=per-type, 2=unified interior, 3=2+AABB sides&bottom (keep top)
# merge=0 off, 1=1D runs, 2=2D quads, 3=3D boxes (full cubes only; after cull)
# reload=True re-imports JSON meshes that already exist under /Game/mc/...
# name overrides the source name used for actor labels/folders and GPU textures
# center=None: file input is bottom-centered; Blocks input preserves cell coordinates
# center=True/False explicitly selects centering for either source type
mineprep.import_block(path, asset_name='oak_stairs', reload=False)
mineprep.import_item(path)
mineprep.resolve_block_json_path('oak_stairs')  # models/block/*.json
mineprep.get_all_blocks()                      # sorted stems in models/block
mineprep.get_all_blocks(r'^(campfire|cobblestone)$')  # re.search; '' = all
```

`get_all_blocks` lists **model JSON stems**, not NBT. Vanilla cell names (`lilac` + `half=lower`, `oak_fence` + NESW) still go through `structure_parts` → stems like `lilac_bottom` / `oak_fence_post`. JSON exists ≠ it was placed.

NBT→mesh details (coords, stairs/fence multipart, uvlock): [structure.md](structure.md).

For procedural structures, use a supplied file or `Blocks` → `spawn_structure(source=...)`; do not assume a matching tree/house NBT is bundled. Generator presets are a separate UI feature, not a file source for `spawn_structure`.

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

**Oriented blocks** (stairs, fence, pane, door): vanilla properties on `Blocks.add`. Do not guess yaw.

```python
b.add('oak_stairs', 0, 0, 0, facing='east', shape='straight', half='bottom')
b.add('oak_fence', 1, 0, 0)
b.connect_fences()
```

User-supplied `.nbt` → `spawn_structure(source=path)` (or `Blocks.from_file`).


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

## `tex_to_color` / `color_to_tex`

Exported as `mineprep.tex_to_color` / `mineprep.color_to_tex` / `mineprep.ColorList` (`mc_material.py`). Texture2D is blitted to a temporary `RTF_RGBA8_SRGB` target first (GPU decompress). Existing RTs are read in place. Result is a 2D `ColorList` (`[y][x]` `LinearColor` in 0–1); 8-bit RTs are divided from UE's 0–255 raw samples. Do not `force_update` a painted canvas RT after draw — this helper only force-updates the **source** Texture2D and a **fresh** temp RT.

Use `ColorList.from_rows(rows)` for a manually constructed 2D pixel table.
Each row stays a row, including rows of three or four gray values:

```python
import mineprep

grid = mineprep.ColorList.from_rows([
    [0, 0, 0, 1],
    [1, 0, 0, 1],
])
grid[0, 1] = (0, 1, 0)  # RGB pixel
```

Pixels accept gray numbers, RGB/RGBA sequences, Color or LinearColor. Rows may be
generators and retain their lengths; strings and scalar rows are invalid.
The original `ColorList(...)` constructor still recognizes a sequence of three
or four numbers as one color, so `ColorList([[0,0,0,1], [1,0,0,1]])` is a 1D
list of two colors.

ColorList inherits List indexing: `grid[y, x]`, `grid[y, x:x2]` and boolean masks.
Assigning one color to a slice broadcasts it. Float indices are UV coordinates:
`grid[:0.5, :]` selects the top half and `grid[:, 0.5:]` the right half;
`grid[1.25]` wraps to `grid[0.25]`. Integer `-1` selects the last item;
float `-1.0` wraps to the first.

`color_to_tex` coerces the input through `ColorList`, packs `LinearColor` into a 32-bit BMP, and uses `import_buffer_as_texture2d` (UE Python has no mip lock / `texture_set_data`). 2D arrays keep row length as width; 1D uses `width=` if given, otherwise a perfect square, otherwise a single row.

```python
grid = mineprep.tex_to_color(tex)  # ColorList of ColorList
grid[y][x] = 1                     # gray
grid[y, x] = (1, 0, 0)             # same, numpy-style
grid[:0.5, :]                      # top half (UV)
grid[:, 0.5:] = (1, 0, 0)          # paint right half
grid[y, x:x + 2] = grid[y, x + 2]  # broadcast one pixel across a slice
c = grid[y][x]
tex = mineprep.color_to_tex(grid)
tex = mineprep.color_to_tex(flat, width=64)
```

## Localization

```python
mineprep.bilingual('中文', 'English')                 # mod_info / short labels
mineprep.localize(source, zh, en, zh_tw, ...)       # multi-lang UI
# PropertyGroup fields: Cls.localize('FieldName', zh, en, zh_tw)  # key = generated UE class name (including GUID) + :prop
```

`bilingual` / `localize` / `loctext` return **`unreal.Text`**, not `str`. Convert with `str(text)` for concatenation or `str.join`; `set_text` accepts Text directly, and ordinary f-string interpolation does not require a separate conversion. A helper accepting Text cannot rescue `text + '\n'` that fails before the helper is called.

Args after `source` follow `mcvars.Languages` order. Use **Python attribute names** as keys for PropertyGroup fields (not display strings).

`loctable_col` reads **`mcvars.LocalizationCache`**. The generator Blueprint fills that table; do not assign `mineprep.LocalizationCache` after reload.

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
