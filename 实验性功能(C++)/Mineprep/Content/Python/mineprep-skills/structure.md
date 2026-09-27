# MC structure / block import

Sources: `mc_structure.py`, `mc_importer.py`, `mc_config.paths`.  
Resources: `…/assets/minecraft/models/block` + sibling `blockstates/`.  
User file → `spawn_structure(source=path)`. For procedural structures, use `Blocks.add` → `connect_fences` when needed → `spawn_structure(b, gpu=0/1/2)`; [api.md](api.md) has an oak example. Do not assume a matching NBT/schematic is bundled. Generator presets are a separate UI feature. Common mistakes: [pitfalls/structure.md](pitfalls/structure.md). Unsure of a model name: `mineprep.get_all_blocks`.

## Coordinate systems (critical)

| Space | Axes | Notes |
|-------|------|--------|
| Minecraft | Y up, X east, Z south | Blockstate `y` = rotate about **Y**; `x` = about **X** |
| JSON model | Same as MC (0–16 box) | Element faces: north/south/up/down/west/east |
| UE (Mineprep) | Z up | Position: MC `(X,Z,Y)` → UE `(X,Y,Z)` cm (`BLOCK_SIZE=100`) |

**Rotation mapping after mesh bake** (geometry already remapped into UE):

- MC blockstate `y` → UE **Yaw** (about Z)
- MC blockstate `x` → UE **Roll** (about X)

A user's three numbers are roll, pitch, yaw. Full rule: [pitfalls/common.md](pitfalls/common.md). Always construct rotators with **keywords**:

```python
unreal.Rotator(pitch=0.0, yaw=90.0, roll=0.0)
# WRONG: unreal.Rotator(0, 90, 0)  → UE Python positional is (roll, pitch, yaw)
#         fence sides became Pitch=90 (rails stood vertical)
```

Stairs / doors already use keywords in `_block_rotation`. Fence sides must too.

## `spawn_structure` pipeline

```text
NBT/schem or Blocks → sparse cells → cull
         → convert_to_packed_arrays
         → import_block
         → batched add_instances (ISM)  or structure_to_tex → PCG/Niagara
```

ISM and PCG/Niagara both start from packed arrays. ISM then turns each model into `unreal.Transform` in batches of 8192 and calls `add_instances`. `spawn_blocks` and `Blocks.types()` still take a full transform list.

`Blocks` (`add` / `connect_fences` / `types()`) is the public cell container. PCG (`gpu=1`) and Niagara (`gpu=2`) use packed arrays, not `types()`. One cell can expand to multiple meshes via `structure_parts`. Never place `oak_fence_side` as its own grid cell.

**Placement defaults:** `spawn_structure(..., name='', center=None)` derives the output name from the source unless overridden. With `center=None`, a file input is bottom-centered, while a `Blocks` input preserves cell coordinates. Set `center=True` or `False` explicitly to make placement consistent when switching between file and procedural inputs. Output is a list of actors; missing models can produce partial output with warnings.

**Cull** (before merge): solid = model has `from=[0,0,0] to=[16,16,16]` with six faces.  
`cull=1` per-type interior; `cull=2` unified solid interior; `cull=3` = 2 then drop AABB side+bottom faces (keep top).

**Merge** (after cull; only **full cubes**, not leaves/stairs/fences/…): greedy meshing per `(model, rot_id)`.  
`merge=0` off; `1` 1D runs (X→Z→Y); `2` 2D quads per Y layer; `3` 2D then stack +Y.  
Instance **location** = box bottom-center (UE); **Scale3D** = local integer extents; same `rot_id`.

**GPU BRT:** RGB = local scale (X,Y,Z) in **block multiples** (e.g. 3 = three blocks); **A = rot id 0..7** → HLSL `Rotation[id]`.

**GPU BPT:** RGB = location in meters (`cm/100`, may be fractional; merged centers are often `*.5`); A = mesh type index (`<0` = empty).

PCG sampling after merge:

```hlsl
// PosTex: do not use int3 — merged centers are often 1.5 etc.
float3 Position = PosColor.xyz * BlockSize;  // BlockSize=100 → cm
Out_SetScale(..., RotColor.xyz);             // already a multiple; or BlockSize*RotColor.xyz/100 when BlockSize==100
Out_SetRotation(..., Rotation[(int)(RotColor.a + 0.5)]);
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

Re-import with `import_block(..., reload=True)` if the StaticMesh already exists (skip path otherwise). In the same editor session, a missing target asset of the same style is duplicated from an existing mesh and only its materials are replaced, so collision is not rebuilt.

## Resource paths

```python
# mc_config
paths.blocks      # …/models/block
paths.blockstates # …/blockstates  (sibling of models/)
# Prefer mineprep.get_all_blocks(filter) over listing this directory yourself
```
