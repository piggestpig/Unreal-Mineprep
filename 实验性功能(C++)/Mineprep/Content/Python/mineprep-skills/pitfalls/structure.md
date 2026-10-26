# Pitfalls — spawn / MC structure

Use with [../structure.md](../structure.md); [../api.md](../api.md) contains an optional oak example. Rotator keywords (all UE Python): [common.md](common.md).

## Spawn helpers

| Symptom | Cause | Fix |
|---------|--------|-----|
| Missing generator widgets during a simple spawn | Main-panel widgets have not registered | Follow [placement recovery](../api.md#recover-a-failed-placement): open the main panel, allow registration, and verify the previous outcome before retrying |
| Same warning after `reload()`, but the actor is in the level | Handshake wrote `mineprep.ActorCache` (wrong module after adopt) | Blueprint / nested Python: `mcvars.ActorCache`. [../api.md](../api.md) § Spawn |
| `mineprep.panel` miss on a Mod widget | `_public_=False`; cache only if `public` or `DebugMode`; lookup is the full key | DebugMode, redraw, use the cached path; DebugMode off after — [../remote.md](../remote.md) § panel |
| Guessed `campfire` / `cobblestone` missing | Never listed JSON, or cell never written | `mineprep.get_all_blocks(r'campfire|cobble')`; then confirm the sparse dict |

## Rotator / MC structure (easy to get wrong)

| Symptom | Cause | Fix |
|---------|--------|-----|
| Fence rails stand vertical | `Rotator(0, 90, 0)` → Pitch 90 | `Rotator(pitch=0, yaw=90, roll=0)` — positional is **(roll, pitch, yaw)** |
| Stair corners blocky | Ignored `shape` | Map to `*_stairs_inner` / `*_outer`; Yaw from vanilla tables |
| Pane edge texture near center | west/east U flipped after MC Z→UE Y | `FACE_UV_CORNER_ROLES` east/west use `tr,tl,bl,br` (horizontal flip) |
| Roof wood grain spins with facing | No uvlock | Vertex Color A by axis (0.94/0.96/0.98); material fixes UV — [../structure.md](../structure.md) |
| Fence looks like disconnected inventory props | Used `*_fence_inventory` or placed `*_fence_side` as its own cell | One fence cell; NESW from neighbors; `structure_parts` → post + sides |
| Roof stairs inside-out (vertical back faces the eave) | Cell-facing, model and intended slope disagree | Verify a representative stair; see the conditional roof example in [../structure.md](../structure.md). Do not apply a global 180° correction without checking |
| Unintended gaps / floating stair roof | Roof composition omitted connecting cells | Add connecting planks/slabs where the design requires them; hollow roofs are valid too |
| `lilac_bottom` / `peony_top` as cell names | Those are model stems | Cell `lilac` + `half=lower`; `structure_parts` emits `*_bottom` |
| Wrong compass after “copy MC y degrees” | Confused Blender/MC/UE up axes | Pos MC(X,Z,Y)→UE(X,Y,Z); rot MC y→Yaw, MC x→Roll |
| Rotated or merged blocks shift half a cell | Used a bottom-pivot mesh or added compensation after packing | Use cell-center meshes (`[-50,50]³` for full cubes) and packed centers directly |
| Slabs or flower halves no longer line up | Centered each model by its actual bounds | All block geometry shares the fixed JSON `(8,8,8)` cell origin |
| Structure not centered on `loc` | `center=False` is the default for both files and `Blocks` | Pass `center=True` to anchor the structure's original grid bounds at their bottom-center |
| Local scales are swapped on a horizontal log | Treated MC world extents as model-local scale | Use `boxes_to_packed`; for MC X log length 4, code 20 yields local scale `(1,1,4)` |

uvlock Alpha on shared verts with the top face: `create_color_seam=True` — [mesh.md](mesh.md) (Geometry Script) / [../structure.md](../structure.md) § uvlock.
