# Model authoring with LowPolyModel and SkeletalModel

Use `mineprep.LowPolyModel` for instanced static meshes and
`mineprep.SkeletalModel` for rigidly skinned box models.
Both are implemented in [mc_model.py](../mc_model.py).
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
  or `[N,3]`; each angle scalar or `[N]`.
- `add`, `add_many` and primitives accept `pivot=None`: an optional rotation
  center in the current group's coordinates (`[3]` or `[N,3]` for add_many).
  It rotates the supplied position about that point, without creating a group.
  Geometry size/scale stays about the mesh's own origin; it does not scale the
  distance to pivot.
- `LowPolyModel.from_blocks(blocks, cell_size=1, cull=2, merge=3)` copies and
  expands existing Blocks through the MC pipeline, converts Y-up to Z-up, and
  preserves the MC origin cell's minimum corner as the model origin. Cell size
  scales both positions and geometry. Existing Blocks are not modified.

Free instances append without grid occupancy, face culling or boolean merging (use `Blocks` first when occupancy/culling/merging is needed). Author non-overlapping boundaries to avoid coplanar z-fighting.

## Appearance: fixed eight-float layout

The shared color material is `/Game/Mineprep/材质/Core/纯色实例材质` (Masked + two-sided by default):

| Index | Value | Default |
|---|---|---|
| 0..3 | Linear RGBA | 1, 1, 1, 1 |
| 4 | Metallic | 0 |
| 5 | Specular | 0.5 |
| 6 | Roughness | 0.65 |
| 7 | Emissive strength | 0 |

`color` accepts `#RRGGBB`, `#RRGGBBAA`, or 0..1 sRGB(A), including `[N,3/4]`
for `add_many`. RGB is converted to linear; alpha is not. `metallic`, `specular`,
`roughness` accept 0..1 and `emissive` accepts finite nonnegative values (scalar or `[N]`).
Primitive helpers default to white; imported assets keep their original materials
unless appearance is overridden. `material` accepts a MaterialInterface object/path
or a slot-ordered sequence (mutually exclusive with color/surface overrides).

## LowPolyModel skeletal output

`bake_skeletal(name=None, *, destination_path='/Game/mc/entity')` saves a
Skeletal Mesh and Skeleton and returns the mesh. Each named group becomes a
bone with its local pivot and reference rotation. Boxes bind rigidly to their
own group, with RGBA colours stored in an embedded palette. Use a new asset name
for each bake. This path supports coloured boxes with default PBR parameters
and uniformly scaled groups. Use the existing Sequencer Rig API to animate
the resulting mesh.

## SkeletalModel

`mineprep.SkeletalModel` is a box recipe with rigid bindings. Positions and
pivots use the same units as LowPolyModel. Each bone takes parent-local pitch,
yaw, roll and positive uniform scale. Bone names are case-insensitively unique
ASCII names containing letters, digits or underscores.

```python
model = mineprep.SkeletalModel('Bird')
model.root.box(size=(.8, .4, .3), color='#f1efdc')
wing = model.bone('wing_left', pivot=(0, -.2, .06), roll=10)
wing.box(position=(0, -.25, 0), size=(.35, .5, .08), color='#838fa3')
mesh = model.bake()
```

- `set_skin(path_or_png_bytes)` attaches a PNG. Pass `uv=` to a box with a
  rectangle `(u, v, width, height)` for each local face `+X`, `-X`, `+Y`,
  `-Y`, `+Z`, and `-Z`. The image origin is top left. Looking at a face from
  outside, +Z is up on the sides and +X is up on the top and bottom. Colour
  and UV boxes can share a model and use separate LabPBR slots.
- For a box net, pass `uv=(u, v)` with the top-left pixel origin.
  `pixels_per_unit=16` sets the pixel density for this shorthand. Box
  dimensions are rounded to the nearest pixel with a minimum of one pixel
  per dimension. Bone scale affects the mesh and keeps the assigned UVs.
- `model.uv_layout()` returns the minimum PNG `size`, the local `up` and
  `right` directions for each face in `face_axes`, and the pixel rectangles
  for textured `boxes`. Each box record includes its bone and zero-based index
  on that bone. `flip_u` tells whether the box reads those rectangles from
  right to left. Use the layout to paint a PNG before calling `set_skin()`.

- `describe()` returns parent names, parent-local pivot, pitch/yaw/roll,
  uniform scale, model-space pivot and box count for each bone.
  `reparent(name, parent)` keeps the branch in place in the reference pose.
- `model.mirror_bone('wing_left', 'wing_right')` copies the whole branch across
  the model-space XZ plane and returns the new root bone. Use `parent=` to place
  that root under a different bone. Descendant names swap a lowercase
  `left_` / `right_` prefix or `_left` / `_right` suffix. Other names gain
  `_mirror`. The copy shares the same skin pixels, swaps the two Y faces
  and reverses each face's horizontal UV direction.
- `SkeletalModel.from_lowpoly(recipe)` and `model.to_lowpoly()` round-trip
  coloured box recipes. Use default PBR values and uniform group scales.
  A per-face UV box has no equivalent LowPolyModel recipe.
- `to_glb()` returns GLB bytes without the editor.
  `bake(name=None, *, destination_path='/Game/mc/entity', reload=False)`
  creates a Skeletal Mesh and Skeleton in a new named folder. Open a Level
  Sequence and use Rig to animate it.
- To replace the skin or edit geometry on a prior bake, call
  `model.bake(reload=True)` with the same name and destination. This updates
  the existing mesh and keeps its Skeleton. The bone names, parents and
  local reference transforms must match. If you change the reference rig,
  bake under a new name.

```python
model = mineprep.SkeletalModel('SkinnedBox')
model.root.box(size=(.5, .75, 1), uv=(0, 0))
layout = model.uv_layout()
# Draw the face rectangles in layout['boxes'][0]['faces'] onto a PNG
# with at least layout['size'] pixels, then call model.set_skin(png).
```

## LowPolyModel component output

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

Ownership is stored in Actor/component tags, so `update(root)` works across map reloads and preserves untagged user-attached components. Delete the root Actor to remove the model. `collision=True` enables the `BlockAll` profile on generated components (`False` by default).
