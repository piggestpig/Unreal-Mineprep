# MC structure / block import

Sources: `mc_structure.py`, `mc_math.py`, `mc_importer.py`, `mc_config.paths`.  
Resources: `…/assets/minecraft/models/block` + sibling `blockstates/`.  
User file → `spawn_structure(source=path)`. For procedural structures, use `Blocks.add` → `connect_fences` when needed → `spawn_structure(b, gpu=0/1/2)`; [api.md](api.md) has an oak example. Do not assume a matching NBT/schematic is bundled. Generator presets are a separate UI feature. Common mistakes: [pitfalls/structure.md](pitfalls/structure.md). Unsure of a model name: `mineprep.get_all_blocks`.

## Coordinate systems (critical)

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

## Offline batch math

`mc_math` requires NumPy but no Unreal. In the editor, the same helpers are
exposed as `mineprep.boxes_to_packed`, `encode_rotation` and `decode_rotation`.

```python
from mc_math import boxes_to_packed, encode_rotation
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

## `Blocks.bake`: one reusable model

```python
b = mineprep.Blocks(name='oak')
# Fill b with MC cells and states, just as for spawn_structure.
mesh = b.bake(destination_path='/Game/mc/baked', asset_name='SM_Oak',
              pivot=(0, 0, 0), cull='same', merge_faces=True)
```

Returns a saved `unreal.StaticMesh`; does not place it or change the cells.
`Blocks.bake()` delegates to the baking section of `mc_mesh.py`.
Unlike structure placement's minimum-corner anchor, `pivot` is the **center of
an MC cell**, in MC XYZ block units. A root cell at `(0,0,0)` with the default
pivot has its bottom at UE Z=-50cm. Place that mesh center 50cm above the ground.
Negative and fractional pivot coordinates are supported.

`cull='opaque'` (default) removes faces covered by complete, opaque neighbors.
`'same'` additionally culls between complete blocks of the same cell type, even
transparent leaves: this deliberately changes canopy transparency. `'none'`
retains all source faces. Partial models only lose declared boundary faces when
a complete opaque neighbor covers them; slabs, flowers and fence multipart
geometry are preserved. This is distinct from `spawn_structure`'s numeric cull.
Only `cull='same'` uses the double-sided LabPBR material templates
(including the animated variant); `cull='opaque'` and `'none'` keep single-sided templates.
Double-sided instances live in a separate `block/mat/two_sided` directory, with
the original material names retained for tint lookup. Existing single-sided
block assets are unaffected. Rebuild older baked assets with `reload=True`.

`merge_faces=True` greedily merges coplanar, same-material full-tile faces with
compatible UVs, repeating the texture instead of stretching it. Partial UVs,
animated textures and unsafe geometry retain their individual faces. Rotation
and blockstate uvlock are baked into explicit UVs, without single-cell shader
Alpha markers. Each unique model/state is resolved once per call. There is no
Boolean fusion, interior-cavity removal, automatic convex collision or Actor
collection. Only JSON element geometry is supported; empty input, missing
geometry, fluid/item/entity models and invalid options raise errors.

Build from surviving source faces, then merge compatible coplanar rectangles;
do not concatenate every cube mesh and run a Boolean operation to remove faces.
Material equality alone does not establish merge compatibility. Preserve the
source geometry of crossed plants and partial blocks; bounding boxes are useful
for conservative placement but do not make these models opaque full cells.

An asset with the same recipe is reused. The recipe covers cells, properties,
pivot, options, resolved geometry, source model parents, blockstates and texture
bytes. A different recipe at the same path raises `ValueError`; explicitly use
`reload=True` to rebuild in place. Unmarked existing assets are also protected.
This guards mesh reuse; texture/material assets follow the existing importer
cache. If source textures change, reimport those textures through the existing
workflow as well. Prefer baking a finite template set once, not on every tree.
Asset names use the importer's normal sanitization; the target is a `/Game`
directory (default `/Game/mc/baked`). Importing/baking requires Unreal Editor.

For a family of templates, share matching texture/material sources independently
of geometry variants instead of importing one copy per tree. Keep readable
asset names while checking the full recipe/source identity; a short display
fingerprint is not the complete reuse key. A mesh with intact references can
still have unfinished textures: follow [Texture2D completion](pitfalls/common.md#source-texture2d-completion)
rather than rebuilding healthy geometry. Instance reductions do not by
themselves prove lower CPU generation time or GPU cost, especially for masked
vegetation whose covered pixel area may remain similar.

## `spawn_structure` pipeline

```text
NBT/schem or Blocks → sparse cells → cull
         → convert_to_packed_arrays
         → import_block
         → batched add_instances (ISM)  or structure_to_tex → PCG/Niagara
```

ISM and PCG/Niagara both start from packed arrays. ISM then turns each model into `unreal.Transform` in batches of 8192 and calls `add_instances`. `spawn_blocks` and `Blocks.types()` still take a full transform list.

`Blocks` (`add` / `connect_fences` / `types()`) is the public cell container. PCG (`gpu=1`) and Niagara (`gpu=2`) use packed arrays, not `types()`. One cell can expand to multiple meshes via `structure_parts`. Never place `oak_fence_side` as its own grid cell.

**Placement defaults:** `spawn_structure(..., name='', center=False)` preserves grid coordinates for both files and `Blocks`; `loc` is the position of the MC origin cell's minimum corner. `center=True` anchors the original logical grid bounds at their bottom-center, before culling or merging. Source names are used unless overridden. Empty structures return `[]` without creating textures or Actors. `Blocks.types()` skips a model with no JSON, or when `import_block` returns `None`, and does not warn. `spawn_structure` looks up a same-name or `name_` inventory fallback when the exact JSON is missing, and warns only when that fallback is also missing.

`blocks.spawn(gpu=1, merge=3)` is the same editor operation as
`mineprep.spawn_structure(blocks, gpu=1, merge=3)`. The public facade re-exports
`mc_structure.spawn_structure`; `Blocks.spawn()` calls that same implementation
directly, without importing `mineprep`. It forwards the same named options,
defaults to `center=False`, returns an Actor list, and leaves cells unchanged.
Importing, preparing and placing resources still require Unreal.

**Cull** (before merge): solid = model has `from=[0,0,0] to=[16,16,16]` with six faces.  
`cull=1` per-type interior; `cull=2` unified solid interior; `cull=3` = 2 then drop AABB side+bottom faces (keep top).

**Merge** (after cull; only **full cubes**, not leaves/stairs/fences/…): greedy meshing per `(model, rot_id)` for rotation codes 0–23. A negative yaw stays 1×1×1 and is not merged.  
`merge=0` off; `1` 1D runs (X→Z→Y); `2` 2D quads per Y layer; `3` 2D then stack +Y.  
Instance **location** = world box center (UE), independent of rotation;
**Scale3D** = world extents permuted into the model's local axes; same `rot_id`.
There is no bottom-pivot translation or extra half-cell adjustment after packing.

**GPU BRT:** RGB = local scale (X,Y,Z) in **block multiples** (e.g. 3 = three blocks). **A** is a rotation code: integer **0–23** (`id = up * 4 + twist`, see `mc_math.py`) or a **negative UE yaw in degrees** (pure horizontal rotation; `0°` stays `0`). Sample with nearest filtering. Decode negatives before indexing `Rotation[24]`.

**GPU BPT:** RGB = location in meters (`cm/100`, may be fractional; merged centers are often `*.5`); A = mesh type index (`<0` = empty).

Current encoding is `bpt-brt-f32-3`: BPT locations are cell/box centers.
Hand-authored block meshes must use this same frame. A water face formerly at
local Z=93.7cm becomes Z=43.7cm; the instance center supplies the other 50cm,
preserving the physical water height. Do not compensate through water parameters.

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
| `grass_path` | alias → `dirt_path` (1.17 rename) |
| `grass` | alias → `short_grass` |
| `tall_grass` / `peony` (double-high) | `half` → `*_bottom` / `*_top` |
| `snow` | `layers` → `snow_height{2*n}` / `snow_block` |
| `*_wall` | currently `*_wall_inventory` (no connection info) |
| `*_trapdoor` | `half`/`open` → `_bottom`/`_top`/`_open`; when open, yaw = vanilla blockstate `y`; if facing disagrees with adjacent solids, auto-correct |
| `*_slab` | `type=top` → `*_top`; `type=double` → full block from blockstate (e.g. `stone_bricks`) |
| `anvil` | facing → vanilla `y`: south=0, west=90, north=180, east=270 |
| `*_bed` / legacy `bed` | `part` or `head_piece_bit` → `*_head` / `*_foot`. Bedrock `bed` color is the block entity `color` dye index (0 = white), not a block state. `direction` 0–3 is south/west/north/east, then the same yaw as Java `facing` |
| classic `.schematic` | MCEdit `Blocks`+`Data` + `mc_default/.../legacy_block_ids.json` (by suffix) |
| Sponge `.schem` | by suffix; v2=`Palette`+`BlockData`, v3=`Blocks.Palette`+`Blocks.Data` |
| fluids | synthesized cube; still/flow textures |

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

Place decorations after writing the main volume so an early `return` does not skip them. If placement is uncertain during requested editor work, use a focused visual check under [remote.md](remote.md)'s testing guidance.

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

Mineprep approach: material corrects UV from instance orientation; importer marks faces via **vertex color Alpha** (`create_color_seam=True`):

- `uvlock` if blockstate has `uvlock:true` **or** model contains a 0–16 six-face cube (**except** `*_leaves`)
- Alpha by **UE** face axis: X(east/west)=**0.94**, Y(north/south)=**0.96**, Z(up/down)=**0.98**
- No write → default Alpha 1 (no lock)

Re-import with `import_block(..., reload=True)` if the StaticMesh already exists (skip path otherwise). An existing **block** mesh whose `MineprepModelFrame` tag is not `cell-center-1` raises `ValueError` when the source is JSON and `reload=False`; pass `reload=True` or clear that mesh. Item meshes are not checked. In the same editor session, a missing target asset of the same style is duplicated from an existing mesh and only its materials are replaced, so collision is not rebuilt.

## Resource paths

```python
# mc_config
paths.blocks      # …/models/block
paths.blockstates # …/blockstates  (sibling of models/)
# Prefer mineprep.get_all_blocks(filter) over listing this directory yourself
```
