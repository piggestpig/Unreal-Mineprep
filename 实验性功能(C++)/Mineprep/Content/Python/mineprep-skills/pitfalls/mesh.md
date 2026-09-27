# Pitfalls — mesh import / merge_skm / Geometry Script

Call `mineprep.merge_skm` — [../api.md](../api.md). Implementation: `mc_mesh.py`. Common `Rotator` / `force_update`: [common.md](common.md).

## GeometryScript Python bindings

| Symptom | Cause | Fix |
|---------|--------|-----|
| `convert_index_array_to_mesh_selection() takes at most 3 arguments` | Out-param `Selection` not passed in Python | Call with `(mesh, ids, type)`; take selection from **return** |
| `GeometryScriptColorFlags` has no `b_red` | C++ `bRed` ≠ Python attr | Use defaults `GeometryScriptColorFlags()` (all channels on) |
| Side faces pick up uvlock Alpha | Shared verts with top | `create_color_seam=True` on triangle selection |

## merge_skm / DynamicMesh

| Symptom | Fix |
|---------|-----|
| Extra mesh shows root skin atlas | `enable_material_i_ds` on every DynamicMesh **before** append; `append_mesh_with_materials` |
| SM / extra mats vanish into one slot | `compact_appended_materials=False` so slots always append |
| Child SKM should share root mats | `append_mats = root_mats[:shared] + child_mats[shared:]` with `shared = min(len(root), len(child))` |
| Head/item wrong pose | Direct child on socket: `relative * socket(RTS_COMPONENT)` (UE Python `*` order). Nested: `child.get_world_transform() * root.get_world_transform().inverse()` |
| `get_component_transform` missing | Use `get_world_transform` on components |
| Static mesh skinning | `copy_bones_from_mesh` → create weights if needed → `set_all_vertex_bone_weights` to attach socket bone |
| Dest asset already there | `overwrite=False` → `warn` + `None`; `overwrite=True` → `copy_mesh_to_skeletal_mesh` (does not delete) |
| Items only, no body | `merge_skm(root, skm=False, sm=True)` — still needs root SKM for skeleton |
| SM vertex colors look dark on merged SKM | SM Build=`ToFColor(true)`, SKM=`ToFColor(false)`; Geometry Script then SRGB→Linear. Before save: `convert_mesh_vertex_colors_linear_to_srgb` |
| Triangle mat IDs | `GeometryScript_List.convert_array_to_index_list`; `set_all_triangle_material_i_ds` wants an IndexList, not a bare int. Verify: copy mesh back → `get_all_triangle_material_i_ds` → `convert_index_list_to_array` |
| New SKM asset | `GeometryScript_NewAssetUtils.create_new_skeletal_mesh_asset_from_mesh` + `Map[int, MaterialInterface]` on create options |

Dest exists on **VAT DA copy** is the opposite policy (load + reuse) — [vat.md](vat.md). Do not mix the two.

## Generated meshes and skeletal import — verified UE 5.7

VanillaMobLoader demonstrates pure Python geometry/GLB generation followed by
Interchange skeletal import and UE material assignment. Its CEM axis mapping,
box UV layout, inflation and skin choices belong to that adapter, not to the
general Mineprep API. Recheck translator behavior after engine upgrades.

- Test geometry outside UE where possible. Use an asymmetric box with six
  marked faces; assert **position-to-UV corner pairs**, not only UV ranges or
  sets. Separate box-atlas layout from per-face UVs and explicit UV mirroring.
  A correct silhouette and winding do not prove a correct texture orientation.
- Use one consistent basis change for vertices, normals, bones and full inverse
  bind matrices. Check world-bind × inverse-bind = identity; rotated/nested
  parts need more than inverse translation. Determine winding from the basis
  determinant and the target importer, then verify in UE; avoid a second
  automatic flip. Do not transfer Blender's V convention to UE by habit.
- To validate actual deformation, rotate a test bone, allow an editor tick,
  then copy the component using `GeometryScriptCopyMeshFromComponentOptions`
  with `requested_lod=GeometryScriptMeshReadLOD(lod_type=GeometryScriptLODType.RENDER_DATA)`.
  Default/source mesh reads can return the bind pose. Check vertices from each
  expected material section, then restore the pose or remove the test actor.
- For generated GLB, a single mesh/skin can have multiple primitives with
  distinct slot identifiers. Verify imported slot names/indices before assigning
  materials; use a temporary pipeline to control materials, animations,
  PhysicsAsset and scaling rather than changing global import settings.
- Validate actual imported object types/counts, skeleton and material references,
  save results and Actor count. Stage new assets in an operation-owned directory;
  mark completion only after success. Reimport in place when scene references
  must survive. A failed reimport is not automatically transactional; do not
  claim rollback merely because existing assets were not deleted.

With reused assets, separate ownership from the complete build recipe. Recipe
identity may depend on ordered inputs and options; a matching destination name
alone is insufficient. Cleanup should touch only assets created by that operation.
For material setters, verify the resulting reference: UE 5.7's
`set_material_instance_texture_parameter_value` returned false in this workflow
even when `get_material_instance_texture_parameter_value` confirmed assignment.
