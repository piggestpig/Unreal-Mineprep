# Pitfalls — Control Rig / AnimSequence

Level Sequence API: [../api.md](../api.md) § Control Rig / Sequencer. `Rotator` keywords: [common.md](common.md).

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

Inspect the chosen skeleton, control space and rest pose; UE world Z-up does not
determine a bone's local axes. Confirm control names with `r.names()` and choose
root movement according to whether the requested animation uses root motion.

| Symptom | Cause | Fix |
|---------|--------|-----|
| Pose changed, Sequencer `get_num_keys()==0` | Fresh CR track may not be initialized in the creation tick | Follow the initialization and key-count check in [Control Rig](../api.md#control-rig); `Rig.key()` already uses set-then-key, but that alone does not guarantee first-tick keys |
| throw 未打开 Level Sequence | Sequencer not focused | Open / focus a Level Sequence |
| NCTRL 0 / no `head_CONTROL` | Track on Actor, not SKM | `actor.rig('Head')` or `component.rig()` |
| Path treated as component name | `rig('/Game/.../IK')` fills `target` | `rig(rig_class='/Game/.../IK')` |
| Head “yaw” nods / tilts | Bone/control local axes differ from world axes | Inspect the selected rig's gizmo and local axes |
| Retimed clip still hits old extremes | Leftover keys on the channel | `ch.remove_key(k)` on those controls, then re-`key` |

Inspect installed control-type enums instead of assuming their names. Use
`pitch=` / `yaw=` / `roll=` for `Rotator`.
