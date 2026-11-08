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
| World | `actor` / `actors`, `selected`, `camera`, `spawn_camera`, `component` / `components`, `materials`, `.lookat` / `.lookat_rotation` |
| Sequencer | `new_sequence`, `sequencer`, `bindings`, `tracks`, `sections`, `channels`, `keys`, `keyframe`, `keyframes`, `orbit`, `spline`, `wave`, `unwrap_angles` / `unwrap_rotations`, `Rig` / `actor.rig` |
| Rendering | RenderPanel `ops.render_preset(...)` — [images and videos](#rendering-renderpanel) |
| Plugin UI | `panel`, `toolbar`, `hotkey` |
| Editor UI | `Layout`, `ui(...)`, `PropertyGroup`, `save` / `load`, `_autosave_` |
| Mods | `Mod`, `mods.register` / `unregister` / `register_all` |
| Optional localization | [localization.md](localization.md): `i18n`, `I18N`, `collect_i18n`, `check_i18n` |
| Spawn | `spawn_block/item/mob/preset`, `attach`, `spawn_blocks`, `spawn_structure`, `Blocks`, `structure_parts`, `get_all_blocks` |
| Mesh | `merge_skm`, `Blocks.bake` |
| Low-poly | `LowPolyModel`: groups, centered boxes/cylinders/cones, assets and batch ISM; [contracts](lowpoly.md) |
| Assets & Config | `uasset`, `uclass`, `bpclass`, `construct`, `copy`, `config`, `paths` |
| Blueprint libs | `BPLib`, `EditorBPLib`, `BPLibCaller` — call a Blueprint function library by function, attribute, or subscript. Not `unreal.mineprep` |
| Utils | `prints`, `warn`, `throw`, `panic`, `undo`, `world`, `cast`, `enum`, `startfile`, `dialog`, file dialogs, `send2trash`, `screenshot` |
| Mouse state | `left_mouse_down()`, `middle_mouse_down()`, `right_mouse_down()` → `bool` or unavailable `None`; current state, UI main thread; [drag usage](ui.md#border--mouse) |
| Parallel | `delay`, `tick`, `asynctask`, `thread`, `asyncthread`, `until` — [parallel.md](parallel.md) |
| Prep & Textures | `prep_texture`, `colorize_material`, `load_mcprep_data`, `tex_to_color`, `color_to_tex`, `ColorList`, `tex_source_files`, `export_tex_cache`, `import_data_tex`, `register_biome_tex`, `clear_biome_tex` |
| Experimental C++ | `unreal.mineprep.*` — last resort after `mineprep.*`; [cpp.md](cpp.md) |

## Handles (actors / components / materials)

Call form returns a **handle** (unknown attrs forward to `.target`). Class
subscripts return a **raw UObject or List**, and instance subscripts select handles.

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

`actor('Name')` and `a.comp('Name')` prefer exact names among wildcard
candidates. `actor(None)` and `actors(None)` return empty handles. Omit the
argument for the default actor query.

`selected()` and `selected(unreal.Actor)` are the current editor selection. A class, label wildcard, or callable filters that selection and does not search the rest of the level. `selected(0)`, `selected(-1)`, and `selected(0.5)` return an `actor` handle at that index; `actors(n)` does the same for the default actor collection, and `components(n)` returns a `component`. Class subscript `[0]` stays the raw object. Call it on the game thread. An empty selection is an empty `actors` handle; a numeric call on an empty collection wraps `None`.

- Subscript class filter: `mineprep.actor[unreal.StaticMeshActor]`
### Collections & batch calls

```python
raw = mineprep.actors[0]              # native UObject for a UE API
first = mineprep.actors()[0]          # actor handle (numeric index -> element handle)
subset = mineprep.actors()[:3]        # actors handle (slice / mask -> collection handle)
marked = mineprep.actors[lambda a: a.actor_has_tag('camera')]  # raw List
```

- **Instance subscripts** (`items[i]`, `items[:3]`, `items[mask]`) return handles: numeric indices on `actors`/`components` return a single `actor`/`component` handle; slices and masks preserve collection type and provenance (e.g. `seq.tracks()[:2].sections()`).
- **Class subscripts** (`mineprep.actors[0]`, `mineprep.actors[[0, 2]]`) return raw UObjects or a raw `List`. Float indices use a `0..1` UV ratio (`floor((u % 1) * n)`).
- **Truthiness & iteration**: `if items` checks non-empty collection or `handle.target is not None` (`len()` is only supported on collection handles). Iterating a collection handle yields raw `.target` elements.
- **Batch calls**: `items(fn, *args)` runs `fn(item, *args)` on each target; attribute access and method calls broadcast across targets. Scalar comparisons on `List` return boolean masks.

### Look at (`lookat` / `lookat_rotation`)

```python
steve = mineprep.actor('Steve')
cam = mineprep.actor('Camera')
steve.lookat(cam, pitch=False)                         # rotate in place (+X toward target), return handle
rot = steve.lookat_rotation(cam, pitch=False, roll=0)  # read-only Rotator (no scene edit)

# Sample along a path without moving the camera first:
rotations = [cam.lookat_rotation(steve, origin=pos) for pos in positions]
cam.keyframes('Rotation', times, rotations, interp='linear', unwrap=True)
```

- Supported on `actor`, `actors`, `camera`, `component`, `components`. `target` accepts an Actor, SceneComponent, single-object handle, world `unreal.Vector`, or `(x, y, z)` in UE cm.
- `pitch=False` zeroes world pitch (horizontal-only yaw); `roll` sets world-view tilt in degrees.
- Actor results use world `Rotation`; component results convert to parent/socket-relative rotation (using current parent transform). `origin=` overrides the source world position in `lookat_rotation()` only.

## `copy`

```python
mineprep.copy(actor, (x, y, z))          # duplicate an actor; target is a location
mineprep.copy('/Game/Mineprep/Render/MC关卡序列', '/Game/demo')
```

Assets: `target` is a package path (auto-suffixed `_2`, `_3` if taken; omit `target` to duplicate beside source). Actor copy takes a location tuple/Vector.

## Sequencer (Level Sequence)

Chain: `sequencer` → `bindings` → `tracks` → `sections` → `channels` → `keys`.
Animation examples use a 60 fps sequence.

### Create sequences, cameras and cuts

```python
seq = mineprep.new_sequence('Seagull_Orbit', fps=60, duration=5.0, open=True)
cam = mineprep.spawn_camera('OrbitCam', location=(1500, 0, 600), fov=70, aperture=22.0)
cam.lookat((0, 0, 330)).fov(70).focus(1200.0).aperture(2.8)
seq.set_frame(0).camera_cut(cam, start=0, end=300, lock_viewport=True)

horizontal_degrees = cam.fov()
f_stop = cam.aperture()
```

- **`new_sequence(name='Sequence', *, fps=60, duration=5.0, open=False)`**: creates a Level Sequence and returns a `sequencer` handle. Short names go under `/Game/Cinematics` (or pass a `/Game/...` path); existing names auto-suffix `_2`, `_3`. `duration` (and all Sequencer time args) treats `int` as display-rate frames and `float` as seconds.
- **`spawn_camera(name='CineCamera', *, location=None, rotation=None, fov=70.0, aperture=22.0, focus_distance=1000.0)`**: spawns a `CineCameraActor` (tagged `'camera'`, 36×20.25 mm filmback, aperture range `f/0.01–f/22`) at the given pose or current viewport, returning a `camera` handle.
- **`mineprep.camera(target)`** wraps an existing `CineCameraActor`. Name and callback searches only consider movie cameras. Name lookup prefers an exact label, then falls back to wildcard matches.
- **`camera` lens methods**:
  - `cam.fov(degrees=None)` / `cam.aperture(f_stop=None)` read the current float with no argument or set it and return `cam`. The default `f/22` generally reduces blur. The amount also depends on focal length, focus distance and subject distance. With manual physical exposure, changing the aperture can affect brightness.
  - `cam.focus(target)`: manual distance in `cm` (`int`/`float`), tracking (Actor, Actor handle or label), or `None` to disable DOF (`CameraFocusMethod.DISABLE`).
- **`sequencer` controls**:
  - `seq.set_range(start, end, *, fps=None)`: sets playback `[start, end)` (changing `fps` keeps key times in seconds).
  - `seq.set_frame(frame)`, `seq.play()`, `seq.pause()`: require `seq` to be the focused sequence. Read playhead via `mineprep.sequencer.frame()` / `.time()`.
  - `seq.camera_cut(camera, *, start=None, end=None, lock_viewport=False)`: accepts any Actor with a `CameraComponent` (including `CineCameraActor` and `MC摄像机` Blueprint Actors). Defaults `start` to current frame (requires focused sequence if omitted) and `end` to playback end. Exact `[start, end)` updates in place; disjoint ranges add a cut; partial overlaps raise `ValueError`.
- **`bindings.actor()`**: `mineprep.sequencer(seq).bindings('MC摄像机').actor()` returns the bound level Actor when the sequence is open/focused and the filter matches a single resolved binding (right after `open_level_sequence`, wait with `until` — [parallel.md](parallel.md)).

### Interpolation and batch keys (Actor / SceneComponent)

```python
mineprep.actor('Steve').key('Location', unreal.Vector(0, 0, 100), 8, interp='linear')
written = mineprep.actor('Steve').keyframes(
    'Location.Z', times=[0, 8, 16], values=[0., 100., 0.], interp='auto')
```

- **Entry points**: `handle.key(prop='', value=None, time=None, *, interp='auto', sequence=None, relative=False)` (or `mineprep.keyframe(...)`) keys the property at one time and returns `bool` for a single target. `handle.keyframes(prop, times, values, *, interp='auto', sequence=None, relative=False, unwrap=False)` (or `mineprep.keyframes(...)`) returns a `mineprep.keys` handle. Pass explicit times when writing to a non-focused sequence.
- **Properties & axes**: `prop=''` or `'Transform'` writes all 9 channels; `'Location'`, `'Rotation'`, `'Scale'` write 3 channels; `'Location.X'`, `'Rotation.X'` (`roll`), `'Rotation.Y'` (`pitch`), `'Rotation.Z'` (`yaw`), `'Scale.X'` write 1 channel. Location and Scale groups accept a Vector or `(x, y, z)`. Actor Location is world cm; Component Location is parent-relative cm. Ordinary properties require their native UE property name (e.g. `'CurrentFocalLength'`, not Python snake_case `'current_focal_length'`).
- **Snapshots & defaults**: a batch captures the starting pose/property once per object; `None` samples write that starting snapshot. Newly created Transform/property sections initialize all channel defaults from the starting pose so single-axis edits preserve other axes.
- **`interp` modes**: `'constant'` (`0`), `'linear'` (`1`), `'auto'` (`2`, default), `'smart_auto'` (`3`), `'user'` (`4`), `'break'` (`5`), or `MovieSceneKeyInterpolation` / `RichCurveInterpMode`.

### Relative keys

```python
wing.keyframes('Rotation.X', [0, 12, 24], [-15., 30., -15.], relative=True)
wing.key('Scale.X', 0.2, 12, relative=True)  # channel default + 0.2 (additive)
```

With `relative=True`, explicit Float/Double values write **channel default + input delta** (including `Scale`, where `0.0` keeps the default; `None` still writes the starting snapshot). Since deltas add to the stored channel default rather than the current pose, re-running a script never accumulates offsets. Full `unreal.Transform` and discrete channels (`bool`/`int`/`str`) do not support `relative=True`.

### Rotation continuity (explicit unwrap)

```python
angles = mineprep.unwrap_angles([178., -178., -170.])  # [178.0, 182.0, 190.0]
continuous = mineprep.unwrap_rotations(rotations, axes='py')
cam.keyframes('Rotation', times, rotations, unwrap=True, interp='linear')
wing.keyframes('Rotation.X', times, rolls, unwrap='r')
```

- Batch `keyframes(..., unwrap=...)` accepts `False` (default: preserves authored multi-turn values like `0 -> 360 -> 720`), `True` (unwrap yaw `'y'`), or any `'r'`/`'p'`/`'y'` combination (single-axis `Rotation.X/Y/Z` accepts only its matching letter `'r'`/`'p'`/`'y'`). Requires strictly increasing display frames.
- `unwrap_angles(values)` and `unwrap_rotations(rotations, *, axes='y')` are pure helpers that remove `±180°` wrap jumps by choosing shortest adjacent angle deltas.

### Wave samples

```python
times = list(range(0, 121, 6))  # 2 seconds at 60 fps
values = mineprep.wave(times, period=60, amplitude=15, offset=0.0, phase=0.0, shape='sine')
wing.keyframes('Rotation.X', times, values, relative=True, interp='auto')
wing.channels('Rotation.X').loop('cycle')
```

`wave(times, *, period, amplitude=1.0, offset=0.0, phase=0.0, shape='sine')` is a pure-math helper returning `list[float]`. `times` and `period` share the **same unit** (both frames or both seconds — no `int`/`float` conversion); `phase` is in degrees. Supported `shape` values: `'sine'`, `'triangle'` (starts at 0, rising), `'square'` (`+1` then `-1`, use `interp='constant'`), and `'saw'` (`-1` to `+1`).

### Orbit and spline paths

```python
# Sparse keys + analytical velocity tangents (smooth circular/spiral arc with few keys):
times = list(range(0, 241, 30))  # 0..4s at 60 fps
positions, rotations, velocities = mineprep.orbit(
    (0, 0, 150), times, radius=(1400, 950), height=(300, 500), turns=1, duration=4.0)
cam.keyframes('Location', times, positions).tangents(velocities)
cam.keyframes('Rotation', times, rotations, interp='linear')

# Alternative shot with Catmull-Rom position and velocity samples:
waypoints = [(1200, -600, 400), (600, -800, 360), (-500, -600, 280)]
positions, velocities = mineprep.spline(waypoints, times, uniform_speed=True, duration=4.0)
cam.keyframes('Location', times, positions).tangents(velocities)
```

- **`orbit(center, samples, *, radius, height=0, turns=1, start_angle=0, roll=0, duration=None)`**: returns `(positions, rotations)` looking at `center` (or `(positions, rotations, velocities)` in `cm/s` when `duration` in seconds is given). `radius` (`> 0`) and `height` (relative to `center.z`) accept a scalar or `(start, end)` pair. Starts on `+X` at `0°`; positive `turns` move toward `+Y`; yaw is already continuous.
- **`spline(points, samples, *, closed=False, uniform_speed=False, tangents=False, duration=None)`**: centripetal Catmull–Rom curve through `points` (`>=2` for open, `>=3` distinct for closed; `uniform_speed=True` reparameterizes by arc length). Returns `positions`, `(positions, unit_directions)` when `tangents=True`, or `(positions, velocities_cm_per_s)` when `duration` (seconds) is passed.
- `samples` can be an integer count (`>=0`) or a strictly increasing iterable of times (normalized from first to last). Match `duration` to the actual key span in seconds. Choose either `tangents=True` or `duration` for spline output.

### Select and edit existing keys & tangents

```python
ks = mineprep.actor('Steve').channels('Location.Z').keys()
ks[ks.value < 0] = 0.0                  # scalar assignment on masked keys
ks[ks.time > 10] += 100                 # in-place +=, -=, *=, /= on key values
ks[ks.frame < 24] >> 6                  # shift later by 6 display frames
ks[ks.time > 12] << 0.5                 # shift earlier by 0.5 seconds
ks[ks.frame == 0].remove()              # delete selected keys from their channels

ks.tangents(120.0)                      # User mode: set both arrive & leave slopes (units/sec)
ks[ks.frame == 24].tangents(leave=0.0)  # Break mode: set arrive and/or leave slopes (units/sec)
slopes = ks.arrive_tangent              # read arrive_tangent / leave_tangent (List in units/sec)
```

- **Properties**: `ks.value` (native values), `ks.frame` (`int` display frames), `ks.time` (`float` seconds), `ks.arrive_tangent` and `ks.leave_tangent` (`float` units/sec) all return `List` objects supporting mask comparisons (`ks[ks.time > 3]`).
- **Tangents (`ks.tangents(slopes=None, *, arrive=None, leave=None)`)**: accepts channel units per second (internally converted to per-tick slopes and set to cubic `USER` or `BREAK` mode). Pass a scalar, a 1D sequence matching `len(ks)`, or a sequence of `unreal.Vector` / `unreal.Rotator` matching a 3-axis `Location` / `Rotation` key batch.
  For vector or rotator samples, use the complete XYZ groups returned by `keyframes()`, in sample order. A channel query can return keys grouped by axis.

### Channel loops and retiming

```python
curve = wing.channels('Rotation.X', sequence=None)
curve.loop('cycle').retime(offset=6, scale=0.5, pivot=0)
curve.clear()                           # remove all keys, keep channel defaults & sections
merged = mineprep.channels([curves_a, curves_b])  # deduplicated with section ownership
```

- **`actor/component.channels(prop='', *, sequence=None)`**: read-only query of existing channels (retains section ownership across sequences without creating tracks).
- **`channels.loop(mode='cycle', *, before=False, after=True)`**: sets pre/post-infinity extrapolation on Float/Double channels. Modes: `'cycle'`, `'cycle_with_offset'` / `'offset'`, `'oscillate'` / `'pingpong'`, `'linear'`, `'constant'`, `'none'`, or `RichCurveExtrapolation`.
  The section and sequence playback range must cover the frames where you want to see the loop.
- **`channels.retime(offset=0, scale=1.0, pivot=0)`**: maps key times to `pivot + (old - pivot) * scale + offset` (`int` frames / `float` seconds; `scale > 0`).
- **`channels.clear()`**: deletes all keys on the selected channels while preserving channel defaults and extrapolation settings.

**Not AnimSequence bone tracks.** Listing / clearing skeletal animation curves is engine API — [pitfalls/anim.md](pitfalls/anim.md).

**Not Control Rig.** `keyframe()` does not write CR channels. Use `actor.rig` below.

## Control Rig

Needs an **open** Level Sequence (`throw` if none). The track hangs on the **SkeletalMeshComponent** possessable, not the Actor. `rig_class=None` → `FKControlRig`. Existing tracks keep their layered flag; **new** tracks are layered.

```python
r = mineprep.actor('Steve').rig()                 # first SKM → FK
r = mineprep.actor('Steve').rig(layered=False)    # create a non-layered FK track
r = mineprep.actor('Steve').rig('Head')           # named SKM
r = mineprep.actor('Steve').rig(
    rig_class='/Game/Path/MC_IK绑定')             # custom IK — keyword, not positional
r.names()
r.set('head', unreal.Rotator(pitch=0, yaw=0, roll=30))
r.key('head', unreal.Rotator(pitch=28, yaw=0, roll=0), 8)  # int=frame, float=seconds
```

After creating a fresh rig, let the editor process a frame before the first
batch. In a later console/MCP call, write a 60 fps movement:

```python
r.keyframes('head', [0, 30, 60], [
    unreal.Rotator(yaw=-20),
    unreal.Rotator(yaw=20),
    unreal.Rotator(yaw=-20),
])
# Write multiple controls by pose in one undo transaction.
r.poses({
    0: {'head': unreal.Rotator(), 'rightArm': unreal.Rotator()},
    24: {'head': unreal.Rotator(yaw=20)},
    48: {'rightArm': unreal.Rotator(pitch=45)},
}, interp='linear')
head_keys = r.keys('head')
# r.clear('head') removes only head keys. r.clear() removes all track keys.
```

`keyframes(name, times, values)` returns `r` and writes a batch with one
transaction and refresh. Times are explicit integer frames or float seconds.
The batch reads original values at each target frame before writing. For FK
EulerTransform controls, Rotator values keep that frame's location and scale,
and Vector values keep its rotation and scale. Each `None` keys the original
value at its target frame. Full EulerTransform values write directly.
Position and Scale controls also accept `(x, y, z)`.
Explicit Euler angles preserve multi-turn values. Warm-up alone does not
guarantee keys on the rig's creation tick. Requery channels to confirm first writes.

`poses({time: {control: value}})` and `poses([(time, {control: value}), ...])`
use the same rules. They return the Rig, write only the listed controls,
and use one transaction and refresh for the batch.

`key()`, `keyframes()` and `poses()` default to `interp=None` (UE's current
behavior). Pass `'constant'`, `'linear'` or `'auto'` on a single-section
track to set interpolation on the continuous keys at the written frames.
`r.channels(name='')` and `r.keys(name='')` query existing curves across
sections. Pass a control name, a group such as `leg1.Rotation`, or one axis
such as `leg1.Rotation.Y` (Pitch). Location and Scale support the same
group and XYZ selectors. Rotation also accepts Roll, Pitch, and Yaw.
`r.clear(name)` uses the same selection and preserves sections and defaults.

```python
pitch_keys = r.keys('leg1.Rotation.Y')      # on a pig rig
pitch_keys += 5                            # pitch values in degrees
pitch_keys.tangents(0.0)                   # scalar slope in degrees per second
r.clear('waist.Location')                  # on a player rig
```

- `actor.rig(target=SKM, rig_class=None, *, layered=None)` forwards to the SKM component's `rig()`.
  `layered` selects the mode when creating a track. `None` keeps the layered default for new tracks.
- Names: full path, last segment, strip `_CONTROL` / `_CURVE_CONTROL`, case-insensitive; ambiguous → throw
- FK bones are `EulerTransform`; pass `Rotator` / `Vector` / `Transform` / `EulerTransform`
- `Rig.key()` uses the same write path as the batch methods.

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
```

Sky blueprint: `/Game/Mineprep/MC_Blueprint/Core/天空/MC天空`. The button keeps a single
actor of that class; selection alone does not prove creation. Allow an editor
frame for Blueprint-created objects before using them.

## Rendering (RenderPanel)

Pass a preset filename (with or without `.json`), ID or name for fixed-resolution output, or as an alternative when
MCP scene capture fails. Neither the RenderPanel nor the legacy panel needs to be open.

| Preset | Default output |
|--------|----------------|
| `quick_image` | 1920×1080 PNG |
| `quick_video` | 1280×720, 30 fps, native MP4 |

```python
from mods.RenderPanel import ops
task = ops.render_preset('quick_image', viewport=True, name='AgentPreview/Still', notify=False)
task
```

Video is a separate call, after the previous task finishes:

```python
from mods.RenderPanel import ops
task = ops.render_preset('quick_video', viewport=True, name='AgentPreview/Video', notify=False)
task
```

`viewport=True` uses the temporary sequence aligned to the current view; video
uses that sequence's playback range. For authored animation, omit it and use
`sequence='/Game/MySequence'`. Optional `width`, `height`, `warmup` and integer
`fps` override this call only. Choose a fresh output name under `Saved/MovieRenders/`.

Submit one render at a time. Check `task.done` on a later MCP call; once done,
check `task.error` before reading `task.result['success']` and the files in
`task.result['output_dir']`. Rendering runs MRQ in PIE, saves dirty packages and
replaces the editor MRQ queue. Full options and HDR workflows:
[RenderPanel README](../mods/RenderPanel/README.md).

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

Localization is optional. For multilingual text, property translations, catalog
files and offline tools, read [localization.md](localization.md).

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
mineprep.warn(f'导入方块失败: {path}', exc)         # Exception → full traceback in log
mineprep.throw('fatal')                             # on-screen error, then raise
mineprep.panic('title', 'message', default=False)   # Yes → continue; No → throw
mineprep.dialog('title', 'message', default=True)   # Yes/No bool
```

- `panic(title, message='', *, default=False)` and `dialog(title, message='', *, default=True)` localize built-in titles/prompts.
- When `mcvars.PyUseDialogDefaults=True` (enabled automatically during synchronous MCP `mcptools.PythonTools.run` calls), both skip the modal window, log a warning, and use `default` (`panic` raises on `False`; `dialog` returns `default`). Native `unreal.EditorDialog` and file pickers remain interactive.

## File dialogs

`askopenfilename`, `askopenfilenames` (returns `tuple[str, ...]`, or `()` on cancel), `askdirectory`, and `asksaveasfilename` use localized default titles when `title=None`.

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

Authoring never requires a live connection for Q&A. Arbitrary in-editor Python: MCP `mcptools.PythonTools.run` ([remote.md](remote.md)). Viewport capture: [remote.md](remote.md) § screenshot. Open Mod / `ui` tabs: [remote.md](remote.md) § panel.
