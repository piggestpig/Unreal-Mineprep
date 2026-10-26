"""Read-only editor bridge: capture a mesh/CPU pose and source-backed base color."""
from pathlib import Path

import numpy as np

from ..core.data import from_ue
from ..core.voxel import MeshData


def texture_file(source):
    """Export actual TextureSource, rejecting source-less transient textures."""
    import unreal
    import mineprep

    texture = unreal.load_asset(str(source)) if isinstance(source, (str, Path)) else source
    if not isinstance(texture, unreal.Texture2D) or not texture.blueprint_get_texture_source_id_string():
        raise ValueError('image requires a source-backed UE Texture2D')
    cache = Path(unreal.Paths.project_intermediate_dir())/'WorldGeneratorMeshCache'
    return mineprep.export_tex_cache(texture, str(cache))


def read_unreal(source, *, textures=None):
    import unreal
    from .mesh_input import image_rgba

    source = unreal.load_asset(str(source)) if isinstance(source, (str, Path)) else source
    dm = unreal.DynamicMesh()
    component = isinstance(source, (unreal.StaticMeshComponent, unreal.SkinnedMeshComponent))
    if component:
        dm, _, outcome = unreal.GeometryScript_SceneUtils.copy_mesh_from_component(
            source, dm, unreal.GeometryScriptCopyMeshFromComponentOptions(), True)
        materials = [source.get_material(i) for i in range(source.get_num_materials())]
    elif isinstance(source, unreal.SkeletalMesh):
        dm, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
            source, dm, unreal.GeometryScriptCopyMeshFromAssetOptions(), unreal.GeometryScriptMeshReadLOD())
        materials = [m.material_interface for m in source.materials]
    elif isinstance(source, unreal.StaticMesh):
        dm, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(
            source, dm, unreal.GeometryScriptCopyMeshFromAssetOptions(), unreal.GeometryScriptMeshReadLOD())
        materials = [m.material_interface for m in source.static_materials]
    else:
        raise TypeError('source requires a StaticMesh/SkeletalMesh asset or mesh component')
    if outcome != unreal.GeometryScriptOutcomePins.SUCCESS or not dm.get_triangle_count():
        raise ValueError('UE mesh extraction failed')

    queries, lists = unreal.GeometryScript_MeshQueries, unreal.GeometryScript_List
    positions = lists.convert_vector_list_to_array(queries.get_all_vertex_positions(dm, False)[1])
    raw_triangles = lists.convert_triangle_list_to_array(queries.get_all_triangle_indices(dm, False)[1])
    vertices = from_ue([(p.x, p.y, p.z) for p in positions])
    triangles = np.array([(t.x, t.y, t.z) for t in raw_triangles], np.int64)
    valid = np.all(triangles >= 0, axis=1)
    tids = np.flatnonzero(valid)
    _, idlist, has_ids = unreal.GeometryScript_Materials.get_all_triangle_material_i_ds(dm)
    ids = np.asarray(lists.convert_index_list_to_array(idlist), np.int64)[valid] if has_ids else np.zeros(len(tids), np.int64)

    # Fast bulk path when there are no UV seams; otherwise read triangle corners.
    _, uvlist, uv_valid, _, split = unreal.GeometryScript_UVs.get_mesh_per_vertex_u_vs(dm, 0)
    uv = None
    if uv_valid and not split:
        values = lists.convert_uv_list_to_array(uvlist)
        uv = np.array([(p.x, p.y) for p in values])[triangles[valid]]
    elif uv_valid:
        values = [queries.get_triangle_u_vs(dm, 0, int(i)) for i in tids]
        if not all(v[3] for v in values):
            raise ValueError('UE mesh contains unset UV corners')
        uv = np.array([[(p.x, p.y) for p in v[:3]] for v in values])
    colors = None
    if queries.get_has_vertex_colors(dm):
        values = [queries.get_triangle_vertex_colors(dm, int(i)) for i in tids]
        if not all(v[4] for v in values):
            raise ValueError('UE mesh contains unset vertex colors')
        colors = np.array([[(c.r, c.g, c.b, c.a) for c in v[1:4]] for v in values])

    captured = []
    for i, material in enumerate(materials):
        if i in (textures or {}):
            captured.append({})
            continue
        if material is None:
            raise ValueError(f'material slot {i} is empty; supply textures={{slot: image}}')
        names = unreal.MaterialEditingLibrary.get_texture_parameter_names(material)
        if '纹理贴图' not in map(str, names):
            raise ValueError(f'provide base color via textures for material slot {i}: {material.get_path_name()}')
        texture = unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(material, '纹理贴图')
        path = texture_file(texture)
        wrap = tuple({'TA_WRAP':'repeat', 'TA_CLAMP':'clamp', 'TA_MIRROR':'mirror'}[
            texture.get_editor_property(axis).name] for axis in ('address_x', 'address_y'))
        captured.append(dict(image=image_rgba(path), wrap=wrap))
    return MeshData(vertices, triangles[valid], uv, ids, captured, colors)
