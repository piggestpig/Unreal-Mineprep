# LowPolyModel: static low-poly recipes

Public entry: `mineprep.LowPolyModel`; implementation: `../mc_lowpoly.py`.
No PCG, Niagara, polygon editor, whole-model bake or animation is involved.
Recipes and data validation work without Unreal; placement and asset preparation
require the editor. Do not install extra packages.

## Coordinates and construction

All positions and primitive dimensions use UE XYZ, Z up, **1 unit = 100 cm**.
Geometry is centered: `box(size=1)` spans -0.5..0.5. Asset references preserve
their original pivot and size. Scale is a positive scalar or XYZ triple; rotations
are named UE `pitch`, `yaw`, `roll` in degrees and are not packed rotation codes.
Nonuniform hierarchical scaling follows UE native transforms; there is no shear correction.

```python
import mineprep

model = mineprep.LowPolyModel('Dragon')
model.box(position=(0, 0, 1.5), size=(4, 1.2, 1), color='#668c55')
wing = model.group('wing_left', pivot=(0, -.5, 2), roll=20)
wing.box(position=(0, -1, 0), size=(2, 2, .1), color='#8fa86b')
wing.cone(radius=.2, height=.5, segments=6)
root = model.spawn(position=(320, 80, 10), yaw=23, scale=1)
# Edit the recipe, then explicitly update this output:
model.update(root)
```

`group()` creates a uniquely named child and returns it. Its `pivot` is the
location of its local origin in the parent; children are authored relative to
that origin. Edit the group's `pivot`, `pitch`, `yaw`, `roll`, or `scale` before
updating. Geometry methods return the current group/model. `clear()` removes
that group's recipe and child groups, without changing placed output.

- `box(position=(0,0,0), size=1, **appearance_and_rotation)`; alternatively
  `box(bounds=(min_xyz, max_xyz), ...)` defines opposite corners before rotation.
  Bounds cannot be combined with position/size. Each maximum must exceed its minimum.
- `cylinder(position=(0,0,0), radius=.5, height=1, segments=8, **options)`.
- `cone(...)` uses the same arguments, with a zero-radius tip.
- `frustum(position=(0,0,0), radius=.5, top_radius=.25, height=1, segments=8, ...)`
  defines bottom/top radii. Top may be zero or greater than bottom. It is solid,
  not a hollow bucket. Equal radius ratios share cached geometry without rounding.
- Round primitives are capped, Z-aligned, centered, faceted, and support 3..256 sides.
- `add(source, position=(0,0,0), scale=1, pitch=0, yaw=0, roll=0, ...)` accepts a
  block model name/JSON path, StaticMesh asset path or actual StaticMesh.
- `add_many(source, positions, ...)`: positions `[N,3]`; scale scalar, shared XYZ
  or `[N,3]`; each angle scalar or `[N]`. Input arrays are copied. No full list of
  Unreal Transforms is retained; submission batches hold at most 8192 transforms.
- `add`, `add_many` and primitives accept `pivot=None`: an optional rotation
  center in the current group's coordinates (`[3]` or `[N,3]` for add_many).
  It rotates the supplied position about that point, without creating a group.
  Geometry size/scale stays about the mesh's own origin; it does not scale the
  distance to pivot. Imported mesh origins remain unchanged.
- `LowPolyModel.from_blocks(blocks, cell_size=1, cull=2, merge=3)` copies and
  expands existing Blocks through the MC pipeline, converts Y-up to Z-up, and
  preserves the MC origin cell's minimum corner as the model origin. Cell size
  scales both positions and geometry. Existing Blocks are not modified.

Free instances append; they do not overwrite occupied cells, auto-connect,
auto-cull, merge, perform booleans or eliminate coplanar overlaps. Use `Blocks`
first when occupancy/culling/merging is needed. Author non-overlapping boundaries
to avoid z-fighting. Future polygon sources can join the geometry resolver while
keeping group poses, appearance and output ownership unchanged; future meshes
must retain corner UV/normal seams and per-face material assignments.

## Appearance: fixed eight-float layout

The shared color material is `/Game/Mineprep/材质/Core/纯色实例材质`.
The API consumes it; it does not rewrite the user's graph or change its blend mode.
The agreed default material is Masked + two-sided; opacity is a mask, not smooth
transparency. A translucent variant needs alpha connected to Opacity and an
appropriate lighting mode. Different material variants form different batches.

| Index | Value | Default |
|---|---|---|
| 0..3 | Linear RGBA | 1, 1, 1, 1 |
| 4 | Metallic | 0 |
| 5 | Specular | 0.5 |
| 6 | Roughness | 0.65 |
| 7 | Emissive strength | 0 |

`color` accepts `#RRGGBB`, `#RRGGBBAA`, or 0..1 sRGB(A), including `[N,3/4]`
for `add_many`. RGB is converted to linear; alpha is not. `metallic`, `specular`,
`roughness` accept 0..1 and `emissive` accepts finite nonnegative values. Each can
be scalar or `[N]`. Primitive helpers default to white; imported assets keep
their original materials unless appearance is explicitly overridden.

`material` accepts a MaterialInterface object/path, or a complete slot-ordered
list/tuple. A single material replaces every slot. It is mutually exclusive with
color/surface overrides. Pure color replaces the source materials; it does not
attempt to tint an arbitrary shader. MC vertex-alpha UV metadata stays unchanged.

Colored batches always allocate and write all eight values, including defaults.
The optional `unreal.mineprep.set_ism_custom_data` C++ function uploads the whole
buffer. If absent, official UE Python setters provide the same result, requesting
a render refresh only on the last value; large buffers are slower on this fallback.
There is no experimental-C++ dependency for recipe construction or placement.

## Output and update

`spawn(position=(0,0,0), pitch=0, yaw=0, roll=0, scale=1, collision=False)` returns
a raw root Actor, or `None` for an empty recipe. Each model is **one Actor**:
the root and named groups are movable SceneComponents, and render batches are
ISM components attached with identity relative transform. The editor may add an
editor-only root icon. Batching respects group, mesh, material and
custom-data usage. Different colors share a batch. Cylinder/cone topology is
cached under `/Game/mc/LowPoly`, independently of size and color.
Generated mesh names end with an eight-character recipe hash.
Conflicting unowned assets are rejected instead of overwritten.

`update(root, collision=False)` requires a live component-format root from this API in the current
editor world. Root transform, label, folder and attachment are preserved. Named
group components retain identity; their poses come from the recipe. Generated render
components and their instance indices may change. User edits on those render components
are not preserved. Named groups can be animated with the component Sequencer API below.
Component names use full group paths joined with underscores; occupied names get
a numeric suffix. Render batches receive their final names after old batches are
retired, so repeated updates retain readable names. Tags identify groups, not names.

### Group animation

`model.component(root, path='')` returns a `mineprep.component` handle for a
generated group via persistent ownership/path tags (`path=''` returns the root
component; missing path raises `KeyError`). It works across recipe recreation
and map reloads without depending on component object names.

```python
wing = model.component(root, 'body/wing_left')
times = list(range(0, 121, 6))  # 2 seconds at 60 fps
wing.keyframes('Rotation.X', times,
               mineprep.wave(times, period=60, amplitude=15), relative=True)
wing.channels('Rotation.X').loop('cycle')
```

- **Units & axes**: recipe coordinates use model units (`1 unit = 100 cm`), while Sequencer `Location` keys on components use parent-relative UE centimeters. `Rotation.X` / `Y` / `Z` are `roll` / `pitch` / `yaw`.
- **Bind to named groups**: part-level `pivot` is baked into ISM instance transforms and cannot be animated independently. Bind animation to `group()` components, which preserve identity across `model.update(root)` (whereas ISM render batches and instance indices may be replaced).
- **Defaults & relative keys**: new Transform sections initialize all 9 channel defaults from the group's starting local pose, so single-axis keys preserve pivot offsets and other axes. Use `relative=True` to add offsets onto channel defaults without accumulating on re-runs, and `.channels(...).clear()` to remove keys while restoring the base pose.
- **Tilted spinning wheels**: place the fixed mounting orientation on a parent group and animate Euler keys (`0 → 360`, `interp='linear'`, `loop('offset')`) on a child spin group's local axis with quaternion interpolation disabled.
- Full keyframe, wave, tangent and channel contracts: [Sequencer in api.md](api.md#sequencer-level-sequence).

Ownership is stored in Actor/component tags, so update works after saving/reopening a map
and recreating the Python recipe. Untagged user attachments survive; when their
generated parent disappears, they move to the root with world transform preserved.
Resources/new batches are prepared before replacing old output. Failures during
preparation clean new components and retain old output; group rollback restores
local transforms. There is one editor transaction
per create/update. It never automatically saves maps or deletes source assets.

Component creation uses the official editor SubobjectDataSubsystem, including
registration, serialization and undo. It does not require experimental Mineprep
C++ functions. The optional bulk data writer and its Python fallback are unchanged.
Delete the root Actor to remove a complete model, or reuse it via `update(root)`.
Legacy outputs made from multiple Actors are left untouched; recreate those from
their recipes in a new map. They are not accepted by the new `update` method.

`collision=False` disables collision/navigation; `True` enables the component's
BlockAll profile. This does not create collision geometry for an asset lacking it.
`spawn_blocks()` retains its existing UE-centimeter/local-Transform contract and
raw Actor return type; it also accepts Transform iterators and optional `collision`.

Validate recipe math offline and component lifetime in the editor, choosing the
most convenient route and batching checks. A data check does not prove rendered
appearance. The API does not eliminate overlapping surfaces: author clean joints
and avoid coincident faces with different colors. Baking, mesh mirroring and
WorldGenerator StaticMesh scattering are not delivered by this API.
