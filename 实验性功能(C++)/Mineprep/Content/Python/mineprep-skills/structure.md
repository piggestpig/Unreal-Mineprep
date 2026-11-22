# MC structure / block import

Sources: `mineprep/structure.py`, `mineprep/structure_data.py`, `mineprep/blockstates.py`, `mineprep/math_tools.py`, `mineprep/importer.py`, `mineprep.settings.paths`.
`mineprep/structure_data.py` contains the Unreal-free cell container, VarInt decoder and BPT/BRT encoding/output; `cv2` is loaded only when writing EXR files.
Resources: `…/assets/minecraft/models/block` + sibling `blockstates/`.  
User file → `spawn_structure(source=path)`. For procedural structures, use `Blocks.add` → explicit `connect()` when needed → `spawn_structure(b, gpu=0/1/2)`; [api.md](api.md) has an oak example. Do not assume a matching NBT/schematic is bundled. Generator presets are a separate UI feature. Common mistakes: [pitfalls/structure.md](pitfalls/structure.md). Unsure of a model name: `mineprep.get_all_blocks`.

## Coordinate systems (critical)

For terrain/biomes, batch building recipes and composing buildings with terrain,
use [WorldGenerator](worldgenerator.md). Existing structure imports and `Blocks` remain available here.

| Space | Axes | Notes |
|-------|------|--------|
| Minecraft | Y up, X east, Z south | Blockstate `y` = rotate about **Y**; `x` = about **X** |
| JSON model | Same as MC (0–16 box) | Element faces: north/south/up/down/west/east |
| UE (Mineprep) | Z up | Position: MC `(X,Z,Y)` → UE `(X,Y,Z)` cm (`BLOCK_SIZE=100`) |

Block meshes use the fixed **cell center**: JSON `(8,8,8)` becomes UE `(0,0,0)`;
a full cube spans `[-50,50]` on every axis. Partial models retain their position
inside that cell; never recenter a slab, flower or water plane by its own bounds.
Cell `(x,y,z)` means its minimum corner, so its instance center is
`100 * (x + .5, z + .5, y + .5)`. A merged box uses half its world extents.
Mesh pivot, instance position and the whole structure's placement anchor are
separate concepts. Model scaling is about the cell center.

## Cell bounds and source dimensions

```python
b = mineprep.Blocks.from_file(path)
print(b.source_size)   # original file dimensions (X, Y, Z), including surrounding air
print(b.bounds())      # current occupied (lo, hi) in MC XYZ; hi is exclusive
```

`bounds()` scans the current non-air cells on demand without caching; an empty
or all-air container returns `None`. It excludes `air`, `cave_air` and `void_air`.
For nonempty bounds, the occupied size is `tuple(hi[i] - lo[i] for i in range(3))`.
This is a cell range, not the vertex bounds of partial block meshes.

`source_size` is a read-only tuple taken from `size` in `.nbt` / `.mcstructure`
or `Width/Height/Length` in `.schem` / `.schematic`. Ordinary `Blocks(...)`
construction (including copies from `copy_cells()`) has `source_size=None`.
This is provenance: rotations, mirrors and cell edits do not update it.
File import does not apply Sponge `Offset` or Bedrock `structure_world_origin`.
Source dimensions do not change placement, centering or baking; WorldGenerator
`api.from_blocks` continues to derive its bounds from occupied cells.

## File processing and editable cells

For large structure files (`.nbt`, `.mcstructure`, `.schem`, `.schematic`), pass the file path directly to `spawn_structure(path, ...)` or `parse_structure(path, ...)` (`mineprep/structure.py`). Use `Blocks.from_file(path)` when you need an editable sparse cell dictionary.

File import preserves native states and coordinates: only missing glass-pane links and Bedrock door-half properties are synced automatically, while trapdoor neighbour repair requires `repair_trapdoors=True`. `spawn_structure` logs CPU preparation and submission times, not GPU rendering completion.

## Connections and grid transforms

```python
b = mineprep.Blocks('railing')
b.add('oak_fence', 0, 0, 0).add('oak_fence', 1, 0, 0)
b.add('stone', 2, 0, 0)
b.connect()                     # batch once, after building
b.rotate(90, pivot=(0, 0, 0))    # coordinates AND block states
b.mirror('x', pivot=0.5)         # reflect, without keeping the original half
```

These methods mutate `b` in place and return it (use `mineprep.Blocks('copy', b.copy_cells())` to keep a copy):

- `rotate(rotation=90, pivot=(0, 0, 0))`: multiples of 90°; positive turns map north → east → south → west around an MC cell-center pivot.
- `mirror(axis='x', pivot=0)`: reflects across an `'x'` (east↔west) or `'z'` (north↔south) plane in cell-center coordinates (integer or half-integer `pivot`), flipping door hinges and stair corners.
- `connect(families=None, positions=None)`: recomputes `'fence'`, `'gate'`, `'pane'`, `'wall'`, and `'stairs'` states in place (`connect_fences()` is the fence/pane/iron-bars subset). Neither `spawn_structure` nor `bake` calls `connect()` implicitly.
- State-only helpers: `mineprep.rotate_state(name, props, turns=1)` and `mineprep.mirror_state(name, props, axis='x')` return new property dicts. Offline code can also call `mineprep.blockstates.connect(cells, is_full_cube=..., families=..., positions=...)`, `rotate_cells`, and `mirror_cells`.

## Offline batch math

`mineprep.math_tools` requires NumPy but no Unreal. In the editor, the same helpers are
exposed as `mineprep.boxes_to_packed`, `encode_rotation` and `decode_rotation`.

`mineprep.math_tools.partition_types(names, counts, groups=1, *, max_types=None)` returns tuples of
`(original_type_ids, instance_count)`. It minimizes `sum(types * instances)`
exactly, without splitting a type. Counts are nonnegative integers; zero-count
types are omitted for multiple groups. The single-group path preserves the
original palette, including zero-count entries; all-zero input returns `()`.
`max_types` optionally limits each group's palette and raises the group count
to fit; the same cost is minimized under that limit. The default is uncapped.

```python
from mineprep.math_tools import boxes_to_packed, encode_rotation
payload = boxes_to_packed(
    coords=[[0, 0, 0]], sizes=[4, 1, 1],
    rot=encode_rotation(pitch=0, yaw=90, roll=90))
# pos=[[200,50,50]], rot=[20], local scale=[[1,1,4]]
```

`coords` is a triple or `[N,3]` in MC XYZ; `sizes` is a positive scalar,
triple or `[N,3]` in MC world axes; `rot` is a scalar or `[N]` encoded code.
`origin=(0,0,0)` is a UE XYZ translation in cm; `block_size=100` is positive.
The returned dict has contiguous float32 `pos[N,3]`, `rot[N]`, `scale[N,3]`.
Empty `[0,3]` coordinates return empty arrays. Invalid shapes, non-finite values,
non-positive extents and invalid codes raise `ValueError`. Negative yaw is for
unmerged unit cells, not a stretched world-aligned box. Decode returns
`(pitch,yaw,roll)`; pass those values to named Rotator arguments.

**Rotation mapping after mesh bake** (geometry already remapped into UE):

- MC blockstate `y` → UE **Yaw** (about Z)
- MC blockstate `x` → UE **Roll** (about X)

A user's three numbers are roll, pitch, yaw. Full rule: [pitfalls/common.md](pitfalls/common.md). Always construct rotators with **keywords**:

```python
unreal.Rotator(pitch=0.0, yaw=90.0, roll=0.0)
# WRONG: unreal.Rotator(0, 90, 0)  → UE Python positional is (roll, pitch, yaw)
```

## Texture animation metadata

Material import automatically reads `<texture>.png.mcmeta` for vertical square-frame animated strips (`frametime`, `interpolate`, forward or ping-pong `frames`, plus `lava_flow` / `water_flow` 2-column flow strips). Source PNG dimensions determine whether the static or animated parent material is used. Pass `reload=True` to `import_block` or `bake` to refresh existing cached materials after `.mcmeta` changes.

## `Blocks.bake`: one reusable model

```python
b = mineprep.Blocks(name='oak')
# Fill b with MC cells and states, just as for spawn_structure.
mesh = b.bake(destination_path='/Game/mc/baked', asset_name='SM_Oak',
              pivot=(0, 0, 0), cull='same', merge_faces=True)
```

Bakes `b` into a single saved `unreal.StaticMesh` (default `/Game/mc/baked`) without placing Actors or mutating `b` (`mineprep/mesh.py`):

- **`pivot`**: cell-center coordinate in MC `(X, Y, Z)` block units (unlike `spawn_structure`'s minimum-corner anchor). A root cell at `(0, 0, 0)` with `pivot=(0, 0, 0)` has its bottom at UE `Z = -50` cm, so place the mesh 50 cm above the ground.
- **`cull`**: `'opaque'` (default, culls faces covered by complete opaque neighbors), `'same'` (also culls faces between identical complete blocks, e.g. leaves), or `'none'`.
- **`two_sided`**: `None` (default) uses double-sided materials only when `cull='same'`. Pass `True` or `False` to override material sidedness independently of face culling (e.g. `b.bake(cull='same', two_sided=False)` for vines).
- **`merge_faces=True`**: greedily merges coplanar, same-material full-tile faces with compatible UVs and bakes `uvlock` directly into vertex UVs. Only JSON element models are supported (not fluids/items/entities).
- **Asset reuse & `reload`**: if an asset at the target path already has the same bake recipe, it is returned directly. If an existing asset at that path has a different recipe (or no recipe tag), `bake` raises `ValueError` unless `reload=True` is passed.

## `spawn_structure` pipeline

```text
NBT/schem or Blocks → sparse cells → cull
         → convert_to_packed_arrays
         → import_block
         → batched add_instances (ISM)  or structure_to_tex → PCG/Niagara
```

ISM and PCG/Niagara both start from packed arrays. ISM then turns each model into `unreal.Transform` in batches of 8192 and calls `add_instances`. `spawn_blocks` and `Blocks.types()` still take a full transform list.

`Blocks` (`add` / `connect` / `types()`) is the public cell container. PCG (`gpu=1`) and Niagara (`gpu=2`) use packed arrays, not `types()`. One cell can expand to multiple meshes via `structure_parts`. Never place `oak_fence_side` as its own grid cell.

**Placement defaults:** `spawn_structure(..., name='', center=False, repair_trapdoors=False)` (or `blocks.spawn(...)`) preserves grid coordinates for both files and `Blocks`; `loc` is the position of the MC origin cell's minimum corner. `center=True` anchors the original logical grid bounds at their bottom-center before culling or merging. `repair_trapdoors=True` opts into neighbour-based facing repair for faulty file exports.

**GPU groups:** `spawn_structure(..., gpu=1, groups=4)` requests four groups (ISM accepts only `groups=1`). Both PCG (`gpu=1`, balanced by type count) and Niagara (`gpu=2`, minimizes `sum(types * instances)`) allow at most **256 model types per Actor**, automatically increasing `groups` with `mineprep.warn` when needed. Each group writes its own BPT/BRT (`name_1_BPT.exr`, etc.), and subsequent Actors attach to the first.

**Cull** (before merge):
- `cull=1`: removes interiors within each complete block type (`[0,0,0]..[16,16,16]` six-face cube).
- `cull=2`: complete opaque blocks occlude other complete blocks; complete transparent blocks only occlude the same type (water uses its same-fluid interior rule).
- `cull=3`: mode 2 + drops AABB side and bottom boundary blocks (keeps top).

**Merge** (after cull; only **full cubes**, not leaves/stairs/fences/…): greedy meshing per `(model, rot_id)` for rotation codes 0–23. A negative yaw stays 1×1×1 and is not merged.  
`merge=0` off; `1` 1D runs (X→Z→Y); `2` 2D quads per Y layer; `3` 2D then stack +Y.  
Instance **location** = world box center (UE), independent of rotation;
**Scale3D** = world extents permuted into the model's local axes; same `rot_id`.
There is no bottom-pivot translation or extra half-cell adjustment after packing.

**GPU BRT:** RGB = local scale (X,Y,Z) in **block multiples** (e.g. 3 = three blocks). **A** is a rotation code: integer **0–23** (`id = up * 4 + twist`, see `mineprep/math_tools.py`) or a **negative UE yaw in degrees** (pure horizontal rotation; `0°` stays `0`). Sample with nearest filtering. Decode negatives before indexing `Rotation[24]`.

**GPU BPT:** RGB = location in meters (`cm/100`, may be fractional; merged centers are often `*.5`); A = mesh type index (`<0` = empty).

Current encoding is `bpt-brt-f32-3`: BPT locations are cell/box centers.
Hand-authored block meshes must use the same cell-center frame, including partial models.

PCG sampling after merge:

```hlsl
// PosTex: do not use int3 — merged centers are often 1.5 etc.
float3 Position = PosColor.xyz * BlockSize;  // BlockSize=100 → cm
Out_SetScale(..., RotColor.xyz);             // already a multiple; or BlockSize*RotColor.xyz/100 when BlockSize==100
// RotColor.a < 0 is yaw degrees; 0..23 indexes Rotation[24]. Do not add 0.5 before the sign test.
Out_SetRotation(..., BlockOrientation(RotColor.a));
```

`int3(PosColor.xyz)*BlockSize` truncates merged centers → misaligned / thin / overlapping instances.

Java `.nbt` palettes: DataVersion 1935 uses `Name` / `Properties`. 26.3 (DataVersion 5023) uses `id` / `properties`. Both are read. Sponge `.schem` keeps the block id in the palette string, so that rename does not apply.

## Model name mapping (`_structure_model_name` / `_structure_parts`)

| Block | Mapping |
|-------|---------|
| `*_stairs` | `shape` or Bedrock `minecraft:corner` → `name` / `name_inner` / `name_outer` (left/right = Yaw). Bedrock `weirdo_direction` 0–3 is east/west/south/north; `upside_down_bit` is `half` |
| `*_door` | `half`+`hinge`+`open` → `name_bottom_left`, `name_top_right_open`, …. Legacy Bedrock `wooden_door` is `oak_door`. Hinge (`door_hinge_bit`) is copied from the upper half. Facing is the lower half's `minecraft:cardinal_direction` (upper half is often stuck on south), then turned 90° counter-clockwise so the 3px slab sits on the outer wall; `direction` 0–3 is east/south/west/north before that turn |
| `wooden_pressure_plate` / `*_pressure_plate` | legacy name is `oak_pressure_plate`. `redstone_signal` 0 or `powered=false` is the raised model; any other signal uses `*_down` |
| `fence_gate` / `*_fence_gate` | legacy name is `oak_fence_gate`. `open_bit` / `in_wall_bit` → `_open` / `_wall`. `minecraft:cardinal_direction` is Java `facing` (south=0, west=90, north=180, east=270) |
| `torch` | Bedrock `torch_facing_direction` points at the attached block. Horizontal values become `wall_torch` facing the opposite way. `top` stays the standing torch |
| `*_fence` | **multipart**: always `name_post`; each of N/E/S/W if true → `name_side` + Yaw. Bedrock stores the same links as `minecraft:connection_north` (and east/south/west) `0`/`1` |
| `*_pane` | multipart: `post` + per direction `side`/`side_alt` or `noside`/`noside_alt` |
| `iron_bars` | multipart: `post_ends`, isolated `post`, single-link `cap`/`cap_alt`, connected `side`/`side_alt` |
| `grass_path` | alias → `dirt_path` (1.17 rename) |
| `grass` | alias → `short_grass` |
| `tall_grass` / `peony` (double-high) | `half` → `*_bottom` / `*_top` |
| `snow` | `layers` → `snow_height{2*n}` / `snow_block` |
| `*_wall` | explicit `up` / NESW → `post`, `side` (`low`), `side_tall` (`tall`); no state info → `inventory` |
| `*_trapdoor` | `half`/`open` → `_bottom`/`_top`/`_open`; when open, yaw = vanilla blockstate `y`; neighbour-based import repair only with `repair_trapdoors=True` |
| `*_slab` | `type=top` → `*_top`; `type=double` → full block from blockstate (e.g. `stone_bricks`) |
| `anvil` | facing → vanilla `y`: south=0, west=90, north=180, east=270 |
| `*_bed` / legacy `bed` | `part` or `head_piece_bit` → `*_head` / `*_foot`. Bedrock `bed` color is the block entity `color` dye index (0 = white), not a block state. `direction` 0–3 is south/west/north/east, then the same yaw as Java `facing` |
| classic `.schematic` | MCEdit `Blocks`+`Data` + `mc_default/.../legacy_block_ids.json` (by suffix) |
| Sponge `.schem` | by suffix; v2=`Palette`+`BlockData`, v3=`Blocks.Palette`+`Blocks.Data` |
| fluids | synthesized cube; still/flow textures; same axis vertex-color Alpha |

### Glass pane (vanilla multipart)

NBT: `north/east/south/west` (+ `waterlogged`). Always `*_post`, then per direction:

| Dir | Connected | Disconnected |
|-----|-----------|--------------|
| north | `side` yaw 0 | `noside` yaw 0 |
| east | `side` yaw 90 | `noside_alt` yaw 0 |
| south | `side_alt` yaw 0 | `noside_alt` yaw 90 |
| west | `side_alt` yaw 90 | `noside` yaw 270 |

Same pattern for `*_stained_glass_pane`.

### Fence (vanilla multipart)

Java uses `north/east/south/west`. Bedrock `.mcstructure` stores the same links as `minecraft:connection_north` (and east/south/west) `0`/`1`, including links into solid blocks. Default `fence_side` extends **MC north (−Z)**. Blockstate → UE Yaw:

| Connection | Yaw |
|------------|-----|
| north | 0 |
| east | 90 |
| south | 180 |
| west | 270 |

Do **not** use `*_fence_inventory` for structures.

### Stairs

Java NBT has `facing`, `half`, `shape`. Bedrock `.mcstructure` stairs use `weirdo_direction` (0 east, 1 west, 2 south, 3 north), `upside_down_bit`, and `minecraft:corner` (`none` → straight). Those map onto the same yaw tables as vanilla `blockstates/*_stairs.json`. `half=top` → Roll 180.

For a normal bottom straight stair, `facing` points toward the **high / full-height side** (east is +MC X in the default model). Always go through `structure_parts`; do not invent yaw.

### Roof example (compose, no NBT)

One solid roof pattern uses filled strips inset one cell per Y layer: opposite-facing stairs at the eaves, planks/slabs between them, and appropriate inner/outer stairs at corners. A hollow roof is also valid when the design calls for it; choose the construction rather than imposing this example on every house.

For a roof rising toward its center, the west eave faces east and the east eave
faces west in MC coordinates. Use `structure_parts` for the state transforms and
check a representative stair before repeating the pattern.

### Double plants

Cell name is vanilla (`lilac`, `peony`, `rose_bush`, …) plus `half=lower|upper`. `structure_parts` emits `*_bottom` / `*_top`. Do not put `lilac_bottom` in the cell dict.

## `get_all_blocks`

```python
mineprep.get_all_blocks()                 # all models/block/*.json stems
mineprep.get_all_blocks(r'campfire|cobble')
mineprep.get_all_blocks(r'^oak_log$')      # exact name; 'oak_log' also matches dark_oak_log
```

Use this instead of globbing `paths.blocks` or grepping the plugin for `.nbt`. Filter is `re.search` on the stem; `''` returns everything sorted.

## uvlock

Recorded only in **`blockstates/*.json`** (`"uvlock": true`), **not** in NBT.

Mineprep separates texture scale compensation from top/bottom direction locking.
The importer writes white RGB and per-face **vertex color Alpha**, using
`create_color_seam=True` so neighbouring faces keep independent values:

| Alpha | Meaning |
| --- | --- |
| 1 / unmarked | Original UV; also used by `Blocks.bake`, which already bakes UV transforms |
| 0.92 | Top/bottom: compensate XY scale, follow the model's orientation |
| 0.94 | UE X-normal faces (east/west): compensate YZ scale |
| 0.96 | UE Y-normal faces (north/south): compensate XZ scale |
| 0.98 | Top/bottom: compensate XY scale and request direction locking |

A model referenced by any `uvlock:true` blockstate gets locked top/bottom faces.
Otherwise a model containing a complete 0–16 six-face cube gets scale compensation
only. Leaves also get scale compensation, with unlocked top/bottom faces. Other
models keep original UV unless selected by the blockstate rule. This is a
model-level default, not an exact per-placement blockstate selection. Renaming the
output asset does not change its UV policy. Synthesized water/lava cubes always
use locked top/bottom faces, including nonzero `fluid_level`.

JSON block meshes are reused when metadata matches both `MineprepModelFrame=cell-center-1` and `MineprepMeshStyleVersion=4` (pass `reload=True` to `import_block` to rebuild stale meshes).

## Resource paths (`mineprep.paths`)

`import_block` accepts a model name or a JSON/external mesh file path. `import_item` accepts an item texture name or an image file path; it extrudes the image rather than interpreting item model JSON. Names are lowercase, optionally prefixed by a namespace:

```python
import mineprep

mineprep.import_block("stone")
mineprep.import_block("minecraft:oak_planks")
mineprep.import_item("diamond_sword")
mineprep.import_block("example:building/stone")
mineprep.import_item("D:/pack/assets/minecraft/textures/item/diamond.png")
```

Names resolve under `paths.assets` to `<namespace>/models/block/<name>.json` or `<namespace>/textures/item/<name>.png`; the default namespace is `minecraft`. Names refer to individual resources, not blockstate combinations. File paths retain their existing behavior; use a `Path` object to explicitly pass an extensionless file. Custom namespace names get a namespace prefix in the default asset name and a namespace subfolder under `destination_path`, including textures and materials. `asset_name` still overrides the mesh name. Missing resources call `throw` with the searched file path, showing an error and raising `RuntimeError`.

`import_item(..., max_resolution=128)` samples alpha to form the extruded outline.
`thickness` is the extrusion depth in those outline pixels and defaults to `1` (`size / max(sampled width, sampled height)` centimeters per pixel).
Front/back faces are generated per opaque pixel and sides only along exposed edges;
vertices, normals and UVs are submitted to Geometry Script in one buffer batch.
The texture keeps its original resolution. If either source dimension exceeds
`max_resolution`, `mineprep.dialog` asks whether to use the original outline resolution:
Yes keeps it; No scales the sampling dimensions proportionally to the limit.
Existing mesh reuse (`reload=False`) skips both sampling and the dialog.
`import_block` uses the same default when forwarding generated-item models.
Synchronous MCP calls use the dialog's default No through `PyUseDialogDefaults`.

Material emission uses `load_mcprep_data()['blocks']['emit']`, matching texture source names/relative paths and setting `发光亮度=0.1` on new or `reload=True` materials.

Default resource pack location is configured via `Settings.default_resource_pack` in `Mineprep_config.txt` (falling back to the default pack under `paths.installer`). `Settings.texture_pack_path` is managed separately by Blueprint tools. Always read resource paths from `mineprep.paths` rather than hardcoding the installer directory:

```python
import mineprep

mineprep.paths.assets       # active resource pack's .../assets directory
mineprep.paths.textures     # .../assets/minecraft/textures
mineprep.paths.blocks       # .../assets/minecraft/models/block
mineprep.paths.blockstates  # .../assets/minecraft/blockstates
# Prefer mineprep.get_all_blocks(filter) over listing paths.blocks manually
```
