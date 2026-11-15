# Pitfalls — Control Rig / AnimSequence

Level Sequence API: [../api.md](../api.md) § Control Rig / Sequencer. Character motion craft & Bedrock axes: [../anim-biped.md](../anim-biped.md). `Rotator` keywords: [common.md](common.md).

Mineprep `sequencer` / `keyframe` / `Rig` edit **Level Sequence**. Skeletal curves on an `AnimSequence` asset use engine APIs — not `actor.rig`.

## AnimSequence bone tracks (≠ Level Sequence)

| Goal | Do | Do not |
|------|----|--------|
| List track names | `unreal.AnimationLibrary.get_animation_track_names(anim)` | |
| Clip key count | `unreal.AnimationLibrary.get_num_keys(anim)` (whole clip, not per-bone) | |
| Delete the whole bone track | `unreal.AnimationLibrary.remove_bone_animation(anim, bone_name=..., include_children=False, finalize=True)` | |
| Clear keys but keep CONTROL channels / constant defaults | Remove keys on MovieScene channels; if `not ch.has_default()`, `ch.set_default(keys[0].get_value())` | `remove_bone_animation` — track gone, bone count drops, defaults vanish |
| Per-bone keys with `AnimationSequencerDataModel` | `asd = unreal.load_object(None, anim.data_model_interface.get_path_name())`; ControlRig section channels `"{bone}_CONTROL.*"` → `ch.get_num_keys()` | Raw bone-track reads when the asset is backed by Sequencer controls |

Zero-key channels can still hold a constant Loc/Rot/Scale (`ch.has_default()` / `ch.get_default()`).

```python
# AnimationSequencerDataModel keys. Zero-key + has_default() → constant pose.
asd = unreal.load_object(None, anim.data_model_interface.get_path_name())
section = list(asd.get_tracks()[0].get_sections())[0]
for ch in section.get_all_channels():
    nkeys = ch.get_num_keys()
    if nkeys == 0 and ch.has_default():
        val = ch.get_default()
```

## Control Rig (Level Sequence, ≠ AnimSequence)

`actor.rig` / `Rig.key` write Control Rig on the **open** Level Sequence — [../api.md](../api.md) § Control Rig. `mineprep.keyframe()` is Actor/Component Transform + properties only.

Hang the track on the **SKM** possessable (Actor-level CR → empty hierarchy). Split characters (Body + Head SKMs): `rig('Head')` vs default body. FK names: `{bone}_CONTROL` (UI may show `head`). Custom IK: `rig(rig_class=...)` — a positional path is a component filter.

Inspect the chosen skeleton, control space and rest pose (`rig.describe()`); UE world Z-up does not determine a bone's local axes. Use keyword arguments (`pitch=`, `yaw=`, `roll=`) for `Rotator`.

| Symptom | Cause | Fix |
|---------|--------|-----|
| Pose changed, Sequencer `get_num_keys()==0` | Fresh CR track is not ready in the creation tick | Yield an editor frame after creating the track before calling `key()` / `keyframes()` / `poses()` |
| throw 未打开 Level Sequence | Sequencer not focused | Open / focus a Level Sequence |
| NCTRL 0 / no `head_CONTROL` | Track on Actor, not SKM | `actor.rig('Head')` or `component.rig()` |
| Path treated as component name | `rig('/Game/.../IK')` fills `target` | `rig(rig_class='/Game/.../IK')` |
| Head “yaw” nods / tilts | Bone/control local axes differ from world axes | Check `rig.describe()` or the selected control's local axes |
| Retimed clip still hits old extremes | Leftover keys on the channel | `rig.clear('bone')` or `ch.remove_key(k)`, then re-key |

## MCAnimConverter (Java, Bedrock & Blockbench clips)

`mods.MCAnimConverter.ops.apply_animation(json_path, actor, *, sequence, clip=None, time_scale=1.0, start_time=0, resize_playback=False, save=False, bones=None, ignore_missing_bones=False, skeleton_mode=None)` imports a Java `.clip.json`, Bedrock `.animation.json`, or Blockbench `.bbmodel` clip (`5.0 / free`) onto a single-section FK Replace Control Rig track; `mods.MCAnimConverter.library.catalog(...)` and `library.info(clip)` merge `Anim/custom/index.json` (distributed, includes `walk_mojang`, `run_mojang`, `quadruped.walk_mojang`, `quadruped.run_mojang`) and optional `Anim/vanilla/index.json` (local-only, erroring on duplicate `clip` IDs) and query `source`, `skeleton`, `loop`, and `source_version` metadata:

- **Dict input contract**: Passing a full `animations` container `dict` auto-selects only a single clip and requires `clip=...` when multiple clips exist; passing a single animation body `dict` (with `bones` and no `animations`/`frames`) requires an explicit `clip=...`. File and dict inputs share `library.resolve_clips()`.
- **Time & range contract**: `start_time` treats `int` as display-rate frames and `float` as seconds; `time_scale` is a duration multiplier (`2.0` doubles clip duration, including Bedrock `pre/post` steps and `.bbmodel` keys). Newly created sequences are set to exact `[start_frame, end_frame)` bounds (including negative starts); existing sequences only expand when `resize_playback=True` and are never shortened. Returns `start_frame`, `end_frame` (half-open in sequence display frames), `keys`, `channel_keys`, `matched_bones`, and `skipped_bones`.
- **Self-contained Java & `.bbmodel` clips**: Java `.clip.json` stores ordered `bones`, reference `bind` matrices, and sampled `frames`; `.bbmodel` (`format_version="5.0"`, `model_format="free"`) preserves sparse/weighted Bezier & mixed-mode scalar curves (`step`/`linear`/`catmullrom`/`bezier`) without needing Curve Editor open (`sync_key_tick_resolution`). Catmull-Rom interval endpoints with dual `pre/post` values are rejected. Both require matching skeleton hierarchy/bind poses (`skeleton_mode` and `ignore_missing_bones` must stay default `None` / `False`).
- **Bedrock `skeleton_mode` (`biped` vs `quadruped` vs `local`)**: Indexed `quadruped` entries default to `'quadruped'` (component-space retargeting onto flat quadrupeds and `quadruped_edit` rigs, rejecting `pelvis` keys); `bedrock_player`, external Bedrock files, and raw dicts default to `'biped'` unless `skeleton_mode='quadruped'` or `'local'` is passed explicitly (`'local'` applies raw target-local offsets, e.g. hand-authored `quadruped_edit` `pelvis -> body` motion). Never expect automatic fallback between modes.
  - **`biped`**: `root` -> `waist`/`hip` -> `body` -> `head`/`leftArm`/`rightArm` and `root` -> `leftLeg`/`rightLeg` (accepts `left_arm`/`right_arm`/`left_leg`/`right_leg`), `position` in MC px (`1 px = 6.25 cm`, `UE = (-pz, -px, py) * 6.25`), ZYX Euler degrees, positive uniform `scale`; retargeted via `retarget.transfer`.
  - **`local`**: generic/quadruped local offsets mapped by exact, casefold, camelCase/snake_case, or explicit alias (`left_back_leg`/`left_rear_leg` -> `left_hind_leg`, `right_back_leg`/`right_rear_leg` -> `right_hind_leg`, `torso` -> `body`), requiring target `EulerTransform` controls with zero bind rotation (`<= 0.1` deg) and unit bind scale.
- **Shared-bone mask (`bones`) & `ignore_missing_bones`**: `bones` preflights target control names before opening/creating a sequence; for Bedrock `biped`, the full parent chain is solved first and only selected controls are keyed (useful for upper-body overlays). `ignore_missing_bones=True` (Bedrock only) skips extra source bones after target validation and reports them in `skipped_bones`. Passing a non-matching skeleton (e.g. a `pig` to a `biped` clip) still errors loudly even when `ignore_missing_bones=True`.
- **Mojang custom loop speeds (for `RenderPanel` / actor translation)**: Pair in-place `Anim/custom/` loops with matching forward actor speed (`walk_mojang` `1.00s` ~ `1.7 blocks/s`, `run_mojang` `0.60s` ~ `4.8 blocks/s`, `quadruped.walk_mojang` `0.90s` ~ `0.7 blocks/s` pig / `0.8 blocks/s` wolf, `quadruped.run_mojang` `0.60s` ~ `1.4 blocks/s` pig / `1.7 blocks/s` wolf). Sampled clips key exact `source_times * time_scale` sequence ticks and align `loop` end frames without an extra held seam frame.
- **FK Replace offsets, span replacement & split heads**: `Location` is an offset from bind pose and `Scale` is a multiplier. Keys replace only mapped/selected controls inside `[start_frame, end_frame)`. Split `Head` receives matching descendant controls with matching bind poses, preserving root `head` and face-only bones.
- **Baking**: `bake_animation(actor, sequence, output_path, *, start=None, end=None)` accepts optional half-open `[start, end)` bounds, restores the original sequence bounds via `try/finally`, and returns `{'body': AnimSequence, 'head': AnimSequence or None}`. Play both assets over the same range via `mineprep.actor(actor).play_anim(assets, start=0, end=..., sequence=seq)`.
- **Direct headless export**: `export_anim_sequence(json_path, target, output_path, *, clip=None, fps=60, time_scale=1.0, save=True, bones=None, ignore_missing_bones=False, skeleton_mode=None)` is synchronous and needs no Level Actor or open Sequencer. `target` accepts `SkeletalMesh`, `SkeletalMeshComponent`, `USkeleton` (with PreviewMesh), asset path, `Actor`/handle, or `(body, head)` / `{'body', 'head'}`. Writes full-bone local TRS (preserving bind pose on un-animated bones and aligning `PlatformTargetFrameRate == DataModel.FrameRate`) and returns `{'body', 'head', ...}` compatible with `play_anim`.

```python
from mods.MCAnimConverter.ops import apply_animation, bake_animation, export_anim_sequence

# Overlay upper-body wave onto existing locomotion, or apply quadruped gait across mobs
apply_animation('animation.mineprep.quadruped.walk_mojang', wolf_actor,
                sequence=seq.target, ignore_missing_bones=True, resize_playback=True)
apply_animation('animation.overhead_wave', player_actor,
                sequence=seq.target, bones=['head', 'right_arm'])
```

See [MCAnimConverter README](../../mods/MCAnimConverter/README.md) for `Anim/custom/` vs `Anim/vanilla/` indices, bone conventions and baking.
