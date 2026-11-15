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

## Generated meshes and skeletal import

- Use one consistent basis change across vertices, normals, bone transforms, and full 4×4 inverse bind matrices (`world_bind × inverse_bind = identity`). Determine triangle winding from the basis determinant and avoid a second automatic flip.
- For generated GLB, a single mesh/skin can have multiple primitives with distinct material slots. Use a temporary `InterchangeGenericAssetsPipeline` instance to configure materials, animations, PhysicsAsset and scaling rather than mutating global import settings.
- In UE 5.7+, `MaterialEditingLibrary.set_material_instance_texture_parameter_value` can return `False` even when assignment succeeds; read back `get_material_instance_texture_parameter_value` to confirm.
- To update an existing SkeletalMesh in place without breaking scene references, reimport onto the existing mesh and keep its `Skeleton` asset (requires matching bone names and hierarchy).
