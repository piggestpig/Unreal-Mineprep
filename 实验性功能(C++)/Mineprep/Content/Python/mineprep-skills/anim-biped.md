# Character Animation Guide (MC Biped & Bedrock Loops)

MCAnimConverter & Control Rig details: [pitfalls/anim.md](pitfalls/anim.md). Rig/sequence API: [api.md](api.md).

## Biped reference and coordinate checks

- **Two distinct hierarchies**: the Bedrock player source is `root` -> `waist`/`hip` -> `body` -> `head` / `leftArm` / `rightArm`, with legs under `root`. The Mineprep UE biped is `root` -> `pelvis` -> `body`, `left_leg`, `right_leg`, with head/arms under `body`. Torso and legs are siblings; translating/rotating `body` does not move leg attachments. Inspect `rig.describe()` and the reference pose before authoring.
- **Units and pivots**: Bedrock `position` is in MC pixels (`1 px = 6.25 cm`), mapped as `UE (cm) = (-pz, -px, py) * 6.25`. The standard adult player has 75 cm legs/arms and a torso half-depth of 12.5 cm; slim/custom meshes and clothing require their own geometry checks. The converter's source `body` reference is at 150 cm, whereas UE `body` is at the 75 cm hip pivot. Copying rotation/translation values across these pivots is not pose equivalence.
- **Signs for this Bedrock player path** (`rotation` in degrees, ZYX order; verify on the actual target):
  - **Pitch `rot[0]`**: negative `-` swings hanging arms/legs **forward** (`-40°..-65°`); positive `+` leans `body` **forward** or swings arms/legs **backward** (`+45°..+82°`).
  - **Yaw `rot[1]`**: positive `+` turns the **left** side **forward** (e.g. `body` `[19, +8.5, 0]` advances the left shoulder). Blender bone-local Euler components depend on rest axes and rotation mode; Z-up alone does not imply any component/sign mapping. Convert through the inspected bases/reference poses and compare native evaluated poses.
  - **Roll `rot[2]`**: outward arm flare uses `leftArm` `-7°..-9°`, `rightArm` `+7°..+9°`.

## Build the main action before secondary motion

Start with a reference the user likes. Preserve its timing and main poses before
adding embellishment. A previous accepted clip or hand-keyed Blender action is
more useful than repeatedly inventing a new waveform. Inspect the actual source
bone hierarchy; the existing Blender run uses a multi-bone UE-style skeleton,
even though its action mostly keys thighs, upper arms, pelvis and chest.

- **Timing and weight**: establish contact, weight acceptance, passing/recovery and the next contact. Running can include flight; walking should transfer support without unintended flight. Judge the complete two-step cycle in seconds, at the intended playback rate. Adjust cadence with the user before multiplying variants.
- **Stable attachments**: compute the moving torso's lower seam in the target pose and place each hip around it, then add the intended reach/tuck offset. A zero leg translation only anchors it to `pelvis`, not to a displaced `body`. Do not rotate the whole leg action just to repair its connection.
- **Rigid limb expression**: use controlled fore/aft reach and vertical recovery with a clear silhouette. Keep hip caps embedded at the seam throughout the cycle; large translations can detach the limb. Arm flare/shoulder translation can provide sleeve clearance, but their size is mesh-dependent.
- **Secondary motion**: add small chest recoil, shoulder reach and lag after the basic gait works. Check the accumulated head pose through its parent chain; adding independent head/waist/body oscillations can compound wobble instead of stabilizing the gaze. Avoid automatically adding motion on every axis.
- **Smoothness**: periodic functions or hand-keyed curves are both usable. Keep transitions continuous and inspect interpolation between keys. Per-frame min/max contact clamps and abrupt phase switches can create visible jerks; use a smooth support/flight trajectory or fit the correction. Higher sample density does not repair bad timing or poses.

For the current run's torso/leg siblings, a position-only attachment correction
in their common parent space can be written as:

```python
# body_offset and body_rotation are evaluated UE target offsets, not raw JSON.
# rest_hip is the target leg's reference translation; keep its existing motion.
hip_delta = body_offset + body_rotation.rotate_vector(rest_hip) - rest_hip
# Invert UE (cm) = (-pz, -px, py) * 6.25 when adding this delta to Bedrock position.
```

This is a clip-authoring correction for matching attachments, not a change to
the converter's general retargeting contract. Other skeletons need their own
attachment points and reference spaces.

## Check geometry and the moving result

The simplified sole estimate
`75 + root_z + leg_z - (75*cos(angle) + 12.5*abs(sin(angle)))`
only covers a single-axis, unscaled standard leg without parent rotation or
clothing. Use radians and cm. It is an estimate, not proof of contact: measure
the actual mesh sole corners through the evaluated bone chain, including pants.
During support, check both sole height and horizontal foot drift against actor
travel. A sole always above the floor can still hover, and a low minimum over
the whole clip says nothing about sustained contact.

Preview several cycles at normal speed from side and front/three-quarter views.
Check hip seams, arm/torso intersections, weight transfer, flight/recovery and
head stability. A few pose screenshots aid diagnosis but cannot establish motion
quality. Numeric checks support this review; user acceptance decides whether
the animation looks good. Finish one human gait before spreading its recipe to
other clips; quadrupeds require their own support timing and limb proportions.

## Authoring a clip

Use sparse `catmullrom` or sampled numeric JSON as appropriate. Loops need matching
endpoint poses and compatible motion across the seam; recheck actual playback
and baked duration. Keep a reusable authoring source when available instead of
repeatedly editing large generated JSON by hand. Minimal dict import:

```python
from mods.MCAnimConverter.ops import apply_animation, bake_animation

clip_dict = {
    'animation_length': 1.0,
    'loop': True,
    'bones': {
        'body': {'rotation': {'0.0': [5, 0, 0], '0.5': [5, 0, 0], '1.0': [5, 0, 0]}},
        'rightArm': {'rotation': {
            '0.0': [0, 0, 8],
            '0.5': {'lerp_mode': 'catmullrom', 'post': [-85, 0, 10]},
            '1.0': [0, 0, 8],
        }},
    },
}
job = apply_animation(clip_dict, player_actor, clip='custom_wave',
                      sequence='/Game/mc/anim/LS_Wave', resize_playback=True)
```
