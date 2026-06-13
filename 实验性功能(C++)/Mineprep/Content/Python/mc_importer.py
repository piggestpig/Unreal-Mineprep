from pathlib import Path
import json
import re
import struct

import unreal
from mc_prep import prep_texture


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tga", ".bmp", ".exr"}
MESH_SUFFIXES = {".fbx", ".obj", ".gltf", ".glb", ".abc", ".usd", ".usda", ".usdc"}
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_]+")
BLOCK_SIZE_CM = 100.0
MC_UNIT_TO_CM = BLOCK_SIZE_CM / 16.0
DEFAULT_GROUP_LAYER = unreal.GeometryScriptGroupLayer()
BASE_MATERIAL_INSTANCE_PATH = "/Game/Mineprep/材质/Core/LabPBR1_基础_材质实例.LabPBR1_基础_材质实例"
BASE_TEXTURE_PARAMETER_NAME = "纹理贴图"

if not hasattr(unreal, "mineprep"):
    unreal.mineprep = type("MineprepNamespace", (), {})()


def _get_mesh_pool():
    pool = unreal.GeometryScript_MeshPoolUtility.get_global_mesh_pool()
    if pool is None:
        raise RuntimeError("Failed to get global DynamicMeshPool")
    return pool


def _request_dynamic_mesh():
    mesh = _get_mesh_pool().request_mesh()
    if mesh is None:
        raise RuntimeError("DynamicMeshPool.request_mesh() returned None")
    return mesh


def _return_dynamic_mesh(mesh):
    if mesh is None:
        return
    try:
        _get_mesh_pool().return_mesh(mesh)
    except Exception:
        pass


def _as_tuple(value):
    if isinstance(value, tuple):
        return value
    if value is None:
        return tuple()
    return (value,)


def _extract_bool(value, default=False):
    for item in _as_tuple(value):
        if isinstance(item, bool):
            return item
    return default


def _extract_first_of_type(value, unreal_type):
    for item in _as_tuple(value):
        if isinstance(item, unreal_type):
            return item
    return None


def _extract_list(value):
    for item in _as_tuple(value):
        if isinstance(item, list):
            return list(item)
        if isinstance(item, tuple):
            return list(item)
        if hasattr(item, "__iter__") and not isinstance(item, (str, bytes, bytearray)):
            try:
                return list(item)
            except TypeError:
                pass
    return []


def _asset_path(package_path, asset_name):
    return f"{package_path}/{asset_name}"


def _normalize_source_file(filepath):
    source = Path(filepath).expanduser()
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source}")
    return source.resolve()


def _normalize_package_path(destination_path):
    package_path = str(destination_path).replace("\\", "/").rstrip("/")
    if not package_path.startswith("/Game"):
        raise ValueError(f"destination_path must start with /Game: {package_path}")
    if not unreal.EditorAssetLibrary.does_directory_exist(package_path):
        unreal.EditorAssetLibrary.make_directory(package_path)
    return package_path


def _sanitize_asset_name(name):
    cleaned = SAFE_NAME_RE.sub("_", str(name)).strip("_")
    return cleaned or "GeneratedAsset"


def _mc_root_path(destination_path, category):
    category = str(category).lower()
    if category not in {"block", "item"}:
        raise ValueError(f"Unknown mc category: {category}")

    base = _normalize_package_path(destination_path)
    if base.endswith(f"/{category}"):
        return base
    return _normalize_package_path(f"{base}/{category}")


def _mc_texture_path(destination_path, category):
    return _normalize_package_path(f"{_mc_root_path(destination_path, category)}/tex")


def _mc_material_path(destination_path, category):
    return _normalize_package_path(f"{_mc_root_path(destination_path, category)}/mat")


def _mc_mesh_asset_name(name):
    return f"▣{_sanitize_asset_name(name)}"


def _mc_material_asset_name(name):
    return f"◉{_sanitize_asset_name(name)}"


def _load_asset_if_exists(asset_path, asset_type=None):
    if not unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        return None
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if asset is None:
        return None
    if asset_type is not None and not isinstance(asset, asset_type):
        raise RuntimeError(f"Existing asset has unexpected type: {asset_path}")
    return asset


def _make_import_task(source_file, destination_path, asset_name=None, replace_existing=True):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(source_file))
    task.set_editor_property("destination_path", destination_path)
    task.set_editor_property("replace_existing", replace_existing)
    task.set_editor_property("replace_existing_settings", replace_existing)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    if asset_name:
        task.set_editor_property("destination_name", asset_name)
    return task


def _run_import_task(task):
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported = list(task.get_objects())
    if not imported:
        raise RuntimeError(f"Import failed: {task.get_editor_property('filename')}")
    return imported


def _vector3(value):
    if isinstance(value, unreal.Vector):
        return value
    if len(value) != 3:
        raise ValueError(f"Expected 3 values, got: {value}")
    return unreal.Vector(float(value[0]), float(value[1]), float(value[2]))


def _rotator(value):
    if isinstance(value, unreal.Rotator):
        return value
    if len(value) != 3:
        raise ValueError(f"Expected 3 values, got: {value}")
    return unreal.Rotator(float(value[0]), float(value[1]), float(value[2]))


def _transform(location=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0)):
    return unreal.Transform(location=_vector3(location), rotation=_rotator(rotation), scale=_vector3(scale))


def _identity_transform():
    return _transform()


def _new_dynamic_mesh():
    return _request_dynamic_mesh()


def _array_to_index_list(values, index_type):
    index_list = unreal.GeometryScriptIndexList()
    try:
        unreal.GeometryScript_List.convert_array_to_index_list(list(values), index_list, index_type)
        return index_list
    except TypeError:
        result = unreal.GeometryScript_List.convert_array_to_index_list(list(values), index_type)
        converted = _extract_first_of_type(result, unreal.GeometryScriptIndexList)
        if converted is None:
            raise RuntimeError("Failed to create GeometryScriptIndexList")
        return converted


def _array_to_uv_list(values):
    out = unreal.GeometryScriptUVList()
    try:
        result = unreal.GeometryScript_List.convert_array_to_uv_list(list(values), out)
        converted = _extract_first_of_type(result, unreal.GeometryScriptUVList)
        return converted or out
    except TypeError:
        result = unreal.GeometryScript_List.convert_array_to_uv_list(list(values))
        converted = _extract_first_of_type(result, unreal.GeometryScriptUVList)
        if converted is None:
            raise RuntimeError("Failed to create GeometryScriptUVList")
        return converted


def _index_list_to_array(index_list):
    out = []
    try:
        result = unreal.GeometryScript_List.convert_index_list_to_array(index_list, out)
        if out:
            return list(out)
        converted = _extract_list(result)
        if converted:
            return converted
    except TypeError:
        pass
    result = unreal.GeometryScript_List.convert_index_list_to_array(index_list)
    return _extract_list(result)


def _color_list_to_array(color_list):
    out = []
    try:
        result = unreal.GeometryScript_List.convert_color_list_to_array(color_list, out)
        if out:
            return list(out)
        converted = _extract_list(result)
        if converted:
            return converted
    except TypeError:
        pass
    result = unreal.GeometryScript_List.convert_color_list_to_array(color_list)
    return _extract_list(result)


def _get_texture_size(texture_asset):
    width = texture_asset.blueprint_get_size_x()
    height = texture_asset.blueprint_get_size_y()
    return max(int(width), 1), max(int(height), 1)


def _sample_texture_alpha_mask(texture_asset, alpha_threshold=0.5, max_resolution=32):
    orig_width, orig_height = _get_texture_size(texture_asset)
    
    # 保持宽高比的情况下，将最大分辨率限制在 max_resolution
    width = orig_width
    height = orig_height
    if width > max_resolution or height > max_resolution:
        if width >= height:
            height = max(1, int(round(orig_height * max_resolution / orig_width)))
            width = max_resolution
        else:
            width = max(1, int(round(orig_width * max_resolution / orig_height)))
            height = max_resolution

    sample_uvs = []
    for y_index in range(height):
        for x_index in range(width):
            sample_uvs.append(
                unreal.Vector2D(
                    (float(x_index) + 0.5) / float(width),
                    1.0 - ((float(y_index) + 0.5) / float(height)),
                )
            )

    uv_list = _array_to_uv_list(sample_uvs)
    sample_options = unreal.GeometryScriptSampleTextureOptions(
        sampling_method=unreal.GeometryScriptPixelSamplingMethod.NEAREST,
        wrap=False
    )

    color_list = unreal.GeometryScript_TextureUtils.sample_texture2d_at_uv_positions(
        uv_list,
        texture_asset,
        sample_options,
    )
    colors = _color_list_to_array(color_list)
    if len(colors) < width * height:
        raise RuntimeError(f"Texture sampling returned too few colors: {len(colors)} < {width * height}")

    opaque_mask = []
    color_index = 0
    for _y_index in range(height):
        row = []
        for _x_index in range(width):
            row.append(float(colors[color_index].a) >= float(alpha_threshold))
            color_index += 1
        opaque_mask.append(row)
    return width, height, opaque_mask


def _get_polygroup_ids(mesh):
    polygroup_ids_out = unreal.GeometryScriptIndexList()
    result = unreal.GeometryScript_PolyGroups.get_polygroup_i_ds_in_mesh(mesh, DEFAULT_GROUP_LAYER, polygroup_ids_out)
    extracted = _extract_first_of_type(result, unreal.GeometryScriptIndexList)
    if extracted is not None:
        polygroup_ids_out = extracted
    return _index_list_to_array(polygroup_ids_out)


def _get_all_triangle_ids(mesh):
    result = unreal.GeometryScript_MeshQueries.get_all_triangle_i_ds(mesh)
    triangle_id_list = _extract_first_of_type(result, unreal.GeometryScriptIndexList)
    if triangle_id_list is None:
        for item in _as_tuple(result):
            if isinstance(item, unreal.GeometryScriptIndexList):
                triangle_id_list = item
                break
    if triangle_id_list is None:
        raise RuntimeError("Failed to query triangle IDs")
    return _index_list_to_array(triangle_id_list)


def _get_triangles_in_polygroup(mesh, polygroup_id):
    triangle_ids_out = unreal.GeometryScriptIndexList()
    result = unreal.GeometryScript_PolyGroups.get_triangles_in_polygroup(
        mesh,
        DEFAULT_GROUP_LAYER,
        polygroup_id,
        triangle_ids_out,
    )
    extracted = _extract_first_of_type(result, unreal.GeometryScriptIndexList)
    if extracted is not None:
        triangle_ids_out = extracted
    return _index_list_to_array(triangle_ids_out)


def _get_triangle_normal(mesh, triangle_id):
    result = unreal.GeometryScript_MeshQueries.get_triangle_face_normal(mesh, triangle_id)
    normal = _extract_first_of_type(result, unreal.Vector)
    if normal is None:
        for item in _as_tuple(result):
            if isinstance(item, unreal.Vector):
                normal = item
                break
    if normal is None:
        raise RuntimeError(f"Failed to query triangle normal: {triangle_id}")
    return normal


def _get_triangle_uvs(mesh, triangle_id, uv_set=0):
    result = unreal.GeometryScript_MeshQueries.get_triangle_u_vs(mesh, uv_set, triangle_id)
    uv_values = [item for item in _as_tuple(result) if isinstance(item, unreal.Vector2D)]
    if len(uv_values) != 3 or not _extract_bool(result, default=bool(uv_values)):
        raise RuntimeError(f"Failed to query triangle UVs: {triangle_id}")
    return uv_values


def _set_triangle_uvs(mesh, triangle_id, uv_values, uv_set=0):
    uv_triangle = unreal.GeometryScriptUVTriangle(uv0=uv_values[0], uv1=uv_values[1], uv2=uv_values[2])
    result = unreal.GeometryScript_UVs.set_mesh_triangle_u_vs(mesh, uv_set, triangle_id, uv_triangle)
    if isinstance(result, tuple) and not _extract_bool(result, default=True):
        raise RuntimeError(f"Failed to set triangle UVs: {triangle_id}")


def _set_material_id_on_triangles(mesh, triangle_ids, material_id):
    if not triangle_ids:
        return
    triangle_list = _array_to_index_list(triangle_ids, unreal.GeometryScriptIndexType.TRIANGLE)
    unreal.GeometryScript_Materials.set_material_id_on_triangles(mesh, triangle_list, int(material_id))


def _delete_triangles(mesh, triangle_ids):
    if not triangle_ids:
        return
    triangle_list = _array_to_index_list(triangle_ids, unreal.GeometryScriptIndexType.TRIANGLE)
    unreal.GeometryScript_MeshEdits.delete_triangles_from_mesh(mesh, triangle_list)


def _pixel_uv_rect(x_index, y_index, width, height):
    u_min = float(x_index) / float(width)
    u_max = float(x_index + 1) / float(width)
    v_max = 1.0 - (float(y_index) / float(height))
    v_min = 1.0 - (float(y_index + 1) / float(height))
    return u_min, v_min, u_max, v_max


def _append_polygon3d(mesh, vertices, uv_rect, material_id=0):
    existing_triangle_ids = set(_get_all_triangle_ids(mesh))

    primitive_options = unreal.GeometryScriptPrimitiveOptions()
    primitive_options.polygroup_mode = unreal.GeometryScriptPrimitivePolygroupMode.PER_FACE
    primitive_options.material_id = int(material_id)
    primitive_options.uv_mode = unreal.GeometryScriptPrimitiveUVMode.SCALE_TO_FILL

    unreal.GeometryScript_Primitives.append_triangulated_polygon3d(
        mesh,
        primitive_options,
        _identity_transform(),
        list(vertices),
    )

    triangle_ids = [triangle_id for triangle_id in _get_all_triangle_ids(mesh) if triangle_id not in existing_triangle_ids]
    if not triangle_ids:
        raise RuntimeError("Failed to identify appended polygon triangles")

    if int(material_id) > 0:
        _set_material_id_on_triangles(mesh, triangle_ids, material_id)
    _apply_uv_rect_to_triangles(mesh, triangle_ids, uv_rect, 0)


def _read_png_size(source):
    with source.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Not a PNG file")
    width, height = struct.unpack(">II", header[16:24])
    return int(width), int(height)


def _read_jpeg_size(source):
    with source.open("rb") as handle:
        if handle.read(2) != b"\xff\xd8":
            raise ValueError("Not a JPEG file")
        while True:
            marker_prefix = handle.read(1)
            if not marker_prefix:
                break
            if marker_prefix != b"\xff":
                continue
            marker = handle.read(1)
            while marker == b"\xff":
                marker = handle.read(1)
            if marker in {b"\xc0", b"\xc1", b"\xc2", b"\xc3", b"\xc5", b"\xc6", b"\xc7", b"\xc9", b"\xca", b"\xcb", b"\xcd", b"\xce", b"\xcf"}:
                handle.read(3)
                height, width = struct.unpack(">HH", handle.read(4))
                return int(width), int(height)
            length = struct.unpack(">H", handle.read(2))[0]
            handle.seek(length - 2, 1)
    raise ValueError("Could not read JPEG size")


def _image_size(source):
    suffix = source.suffix.lower()
    try:
        if suffix == ".png":
            return _read_png_size(source)
        if suffix in {".jpg", ".jpeg"}:
            return _read_jpeg_size(source)
    except Exception:
        pass
    return 16, 16


def _import_texture_asset(source, texture_package_path, asset_name=None):
    texture_name = _sanitize_asset_name(asset_name or source.stem)
    imported = _run_import_task(_make_import_task(source, texture_package_path, texture_name))
    texture_asset = imported[0]
    prep_texture(texture_asset)
    return texture_asset


def _create_texture_material(texture_asset, destination_path, asset_name):
    material_name = _mc_material_asset_name(asset_name)
    material_path = _asset_path(destination_path, material_name)
    material = _load_asset_if_exists(material_path, unreal.MaterialInstanceConstant)
    if material is None:
        material = unreal.EditorAssetLibrary.duplicate_asset(BASE_MATERIAL_INSTANCE_PATH, material_path)
        if not material:
            raise RuntimeError(f"Failed to duplicate material instance asset: {material_path}")

    material = unreal.MaterialInstanceConstant.cast(material)
    if material is None:
        raise RuntimeError(f"Duplicated asset is not a MaterialInstanceConstant: {material_path}")

    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
        material,
        BASE_TEXTURE_PARAMETER_NAME,
        texture_asset,
    )

    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return material


def _create_static_mesh_asset(dynamic_mesh, asset_path, materials=None):
    static_mesh = _load_asset_if_exists(asset_path, unreal.StaticMesh)
    if static_mesh is None:
        create_options = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
        static_mesh, _ = unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(
            dynamic_mesh,
            asset_path,
            create_options,
        )
        if static_mesh is None:
            raise RuntimeError(f"Failed to create Static Mesh asset: {asset_path}")

    copy_options = unreal.GeometryScriptCopyMeshToAssetOptions(
        replace_materials = True if materials else False,
        new_materials = list(materials) if materials else None,
    )

    write_lod = unreal.GeometryScriptMeshWriteLOD()
    unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(dynamic_mesh, static_mesh, copy_options, write_lod)

    unreal.EditorAssetLibrary.save_loaded_asset(static_mesh)
    return static_mesh


def _infer_face_direction(mesh, polygroup_id):
    triangle_ids = _get_triangles_in_polygroup(mesh, polygroup_id)
    if not triangle_ids:
        raise RuntimeError(f"Polygroup has no triangles: {polygroup_id}")

    normal = _get_triangle_normal(mesh, triangle_ids[0])
    ax = abs(normal.x)
    ay = abs(normal.y)
    az = abs(normal.z)

    if az >= ax and az >= ay:
        return "up" if normal.z >= 0.0 else "down"
    if ax >= ay:
        return "east" if normal.x >= 0.0 else "west"
    return "south" if normal.y >= 0.0 else "north"


def _rotate_uv(u_value, v_value, rotation_deg):
    turns = (int(rotation_deg) // 90) % 4
    for _ in range(turns):
        u_value, v_value = v_value, 1.0 - u_value
    return u_value, v_value


def _face_uv_rect(face_name, face_uv, bounds_from, bounds_to):
    if face_uv is None:
        if face_name in {"north", "south"}:
            face_uv = [bounds_from[0], 16 - bounds_to[1], bounds_to[0], 16 - bounds_from[1]]
        elif face_name in {"west", "east"}:
            face_uv = [bounds_from[2], 16 - bounds_to[1], bounds_to[2], 16 - bounds_from[1]]
        elif face_name in {"up", "down"}:
            face_uv = [bounds_from[0], bounds_from[2], bounds_to[0], bounds_to[2]]
        else:
            face_uv = [0, 0, 16, 16]

    u_min = float(face_uv[0]) / 16.0
    u_max = float(face_uv[2]) / 16.0
    v_min = 1.0 - (float(face_uv[3]) / 16.0)
    v_max = 1.0 - (float(face_uv[1]) / 16.0)
    return u_min, v_min, u_max, v_max


def _apply_uv_rect_to_triangles(mesh, triangle_ids, uv_rect, rotation_deg):
    current_by_triangle = {}
    all_uvs = []
    for triangle_id in triangle_ids:
        tri_uvs = _get_triangle_uvs(mesh, triangle_id)
        current_by_triangle[triangle_id] = tri_uvs
        all_uvs.extend(tri_uvs)

    if not all_uvs:
        return

    src_u_min = min(value.x for value in all_uvs)
    src_u_max = max(value.x for value in all_uvs)
    src_v_min = min(value.y for value in all_uvs)
    src_v_max = max(value.y for value in all_uvs)

    src_u_range = src_u_max - src_u_min if src_u_max != src_u_min else 1.0
    src_v_range = src_v_max - src_v_min if src_v_max != src_v_min else 1.0

    dst_u_min, dst_v_min, dst_u_max, dst_v_max = uv_rect
    dst_u_range = dst_u_max - dst_u_min
    dst_v_range = dst_v_max - dst_v_min

    for triangle_id, tri_uvs in current_by_triangle.items():
        mapped = []
        for uv_value in tri_uvs:
            u_norm = (uv_value.x - src_u_min) / src_u_range
            v_norm = (uv_value.y - src_v_min) / src_v_range
            u_norm, v_norm = _rotate_uv(u_norm, v_norm, rotation_deg)
            mapped.append(
                unreal.Vector2D(
                    dst_u_min + (u_norm * dst_u_range),
                    dst_v_min + (v_norm * dst_v_range),
                )
            )
        _set_triangle_uvs(mesh, triangle_id, mapped)


def _find_assets_root(source_file):
    for parent in source_file.parents:
        if parent.name == "assets":
            return parent.parent
    raise RuntimeError(f"Could not find assets root for: {source_file}")


def _resolve_model_reference(model_path, model_ref):
    if model_ref.startswith("."):
        return (model_path.parent / model_ref).with_suffix(".json").resolve()
    if ":" in model_ref:
        namespace, relative_path = model_ref.split(":", 1)
    else:
        namespace, relative_path = "minecraft", model_ref
    return (_find_assets_root(model_path) / "assets" / namespace / "models" / f"{relative_path}.json").resolve()


def _resolve_texture_reference(model_path, textures, texture_key):
    texture_ref = textures[texture_key]
    while texture_ref.startswith("#"):
        texture_ref = textures[texture_ref[1:]]

    if texture_ref.startswith("."):
        texture_path = (model_path.parent / texture_ref).resolve()
    else:
        if ":" in texture_ref:
            namespace, relative_path = texture_ref.split(":", 1)
        else:
            namespace, relative_path = "minecraft", texture_ref
        texture_path = _find_assets_root(model_path) / "assets" / namespace / "textures" / relative_path

    if texture_path.suffix:
        return texture_path
    return texture_path.with_suffix(".png")


def _load_mc_model(model_path):
    with model_path.open("r", encoding="utf-8") as handle:
        model_data = json.load(handle)

    result = {
        "parent": model_data.get("parent"),
        "textures": {},
        "elements": None,
    }

    parent_ref = model_data.get("parent")
    if parent_ref and parent_ref not in {"builtin/generated", "item/generated", "builtin/entity"}:
        parent_data = _load_mc_model(_resolve_model_reference(model_path, parent_ref))
        result["textures"].update(parent_data.get("textures") or {})
        result["elements"] = parent_data.get("elements")
        if result["parent"] is None:
            result["parent"] = parent_data.get("parent")

    result["textures"].update(model_data.get("textures") or {})
    if model_data.get("elements") is not None:
        result["elements"] = model_data.get("elements")

    return result


def _mc_to_ue_center(bounds_from, bounds_to):
    return (
        ((float(bounds_from[0]) + float(bounds_to[0])) * 0.5 - 8.0) * MC_UNIT_TO_CM,
        ((float(bounds_from[2]) + float(bounds_to[2])) * 0.5 - 8.0) * MC_UNIT_TO_CM,
        ((float(bounds_from[1]) + float(bounds_to[1])) * 0.5) * MC_UNIT_TO_CM,
    )


def _mc_to_ue_dimensions(bounds_from, bounds_to):
    return (
        max((float(bounds_to[0]) - float(bounds_from[0])) * MC_UNIT_TO_CM, 0.01),
        max((float(bounds_to[2]) - float(bounds_from[2])) * MC_UNIT_TO_CM, 0.01),
        max((float(bounds_to[1]) - float(bounds_from[1])) * MC_UNIT_TO_CM, 0.01),
    )


def _build_item_dynamic_mesh(width_cm, height_cm, thickness_cm, opaque_mask):
    pixel_height = len(opaque_mask)
    pixel_width = len(opaque_mask[0]) if pixel_height else 0
    if pixel_width <= 0 or pixel_height <= 0:
        raise RuntimeError("Item texture has invalid dimensions")

    mesh = _new_dynamic_mesh()

    thickness_value = max(float(thickness_cm), 0.1)
    half_thickness = thickness_value * 0.5
    pixel_width_cm = float(width_cm) / float(pixel_width)
    pixel_height_cm = float(height_cm) / float(pixel_height)
    half_width_cm = float(width_cm) * 0.5
    half_height_cm = float(height_cm) * 0.5

    def is_opaque(x_index, y_index):
        if x_index < 0 or y_index < 0 or x_index >= pixel_width or y_index >= pixel_height:
            return False
        return bool(opaque_mask[y_index][x_index])

    for y_index in range(pixel_height):
        for x_index in range(pixel_width):
            if not is_opaque(x_index, y_index):
                continue

            y_min = -half_width_cm + (float(x_index) * pixel_width_cm)
            y_max = y_min + pixel_width_cm
            z_max = half_height_cm - (float(y_index) * pixel_height_cm)
            z_min = z_max - pixel_height_cm
            uv_rect = _pixel_uv_rect(x_index, y_index, pixel_width, pixel_height)

            _append_polygon3d(
                mesh,
                [
                    unreal.Vector(y_min, z_min, half_thickness),
                    unreal.Vector(y_max, z_min, half_thickness),
                    unreal.Vector(y_max, z_max, half_thickness),
                    unreal.Vector(y_min, z_max, half_thickness),
                ],
                uv_rect,
                0,
            )
            _append_polygon3d(
                mesh,
                [
                    unreal.Vector(y_min, z_max, -half_thickness),
                    unreal.Vector(y_max, z_max, -half_thickness),
                    unreal.Vector(y_max, z_min, -half_thickness),
                    unreal.Vector(y_min, z_min, -half_thickness),
                ],
                uv_rect,
                0,
            )

            if not is_opaque(x_index - 1, y_index):
                _append_polygon3d(
                    mesh,
                    [
                        unreal.Vector(y_min, z_min, -half_thickness),
                        unreal.Vector(y_min, z_min, half_thickness),
                        unreal.Vector(y_min, z_max, half_thickness),
                        unreal.Vector(y_min, z_max, -half_thickness),
                    ],
                    uv_rect,
                    0,
                )
            if not is_opaque(x_index + 1, y_index):
                _append_polygon3d(
                    mesh,
                    [
                        unreal.Vector(y_max, z_max, -half_thickness),
                        unreal.Vector(y_max, z_max, half_thickness),
                        unreal.Vector(y_max, z_min, half_thickness),
                        unreal.Vector(y_max, z_min, -half_thickness),
                    ],
                    uv_rect,
                    0,
                )
            if not is_opaque(x_index, y_index - 1):
                _append_polygon3d(
                    mesh,
                    [
                        unreal.Vector(y_min, z_max, -half_thickness),
                        unreal.Vector(y_min, z_max, half_thickness),
                        unreal.Vector(y_max, z_max, half_thickness),
                        unreal.Vector(y_max, z_max, -half_thickness),
                    ],
                    uv_rect,
                    0,
                )
            if not is_opaque(x_index, y_index + 1):
                _append_polygon3d(
                    mesh,
                    [
                        unreal.Vector(y_min, z_min, -half_thickness),
                        unreal.Vector(y_max, z_min, -half_thickness),
                        unreal.Vector(y_max, z_min, half_thickness),
                        unreal.Vector(y_min, z_min, half_thickness),
                    ],
                    uv_rect,
                    0,
                )

    return mesh


def _material_context_for_texture(texture_cache, material_cache, texture_source, texture_package, material_package):
    texture_key = str(texture_source).lower()
    if texture_key not in texture_cache:
        texture_cache[texture_key] = _import_texture_asset(texture_source, texture_package, texture_source.stem)
    if texture_key not in material_cache:
        material_cache[texture_key] = _create_texture_material(
            texture_cache[texture_key],
            material_package,
            texture_source.stem,
        )
    return texture_cache[texture_key], material_cache[texture_key]


def _build_block_dynamic_mesh(model_path, destination_path, asset_name):
    model_data = _load_mc_model(model_path)
    elements = model_data.get("elements") or []
    textures = model_data.get("textures") or {}

    category = "item" if model_data.get("parent") in {"item/generated", "builtin/generated"} else "block"

    if not elements and category == "item" and "layer0" in textures:
        item_texture = _resolve_texture_reference(model_path, textures, "layer0")
        return "item", item_texture

    if not elements:
        raise RuntimeError(f"Model has no renderable elements: {model_path}")

    texture_package = _mc_texture_path(destination_path, category)
    material_package = _mc_material_path(destination_path, category)

    target_mesh = _new_dynamic_mesh()
    imported_textures = {}
    created_materials = {}
    material_slots = []
    material_slot_index_by_texture = {}

    def get_material_index(texture_file):
        texture_asset, material_asset = _material_context_for_texture(
            imported_textures,
            created_materials,
            texture_file,
            texture_package,
            material_package,
        )
        texture_key = str(texture_file).lower()
        if texture_key not in material_slot_index_by_texture:
            material_slot_index_by_texture[texture_key] = len(material_slots)
            material_slots.append(material_asset)
        return material_slot_index_by_texture[texture_key], texture_asset, material_asset

    for element in elements:
        bounds_from = element.get("from")
        bounds_to = element.get("to")
        if not bounds_from or not bounds_to:
            continue

        box_mesh = _new_dynamic_mesh()
        try:
            primitive_options = unreal.GeometryScriptPrimitiveOptions()
            primitive_options.polygroup_mode = unreal.GeometryScriptPrimitivePolygroupMode.PER_FACE
            primitive_options.material_id = 0
            primitive_options.uv_mode = unreal.GeometryScriptPrimitiveUVMode.UNIFORM

            unreal.GeometryScript_Primitives.append_box(
                box_mesh,
                primitive_options,
                _transform(location=_mc_to_ue_center(bounds_from, bounds_to)),
                *_mc_to_ue_dimensions(bounds_from, bounds_to),
                0,
                0,
                0,
                unreal.GeometryScriptPrimitiveOriginMode.CENTER,
            )
            unreal.GeometryScript_UVs.set_num_uv_sets(box_mesh, 1)

            faces = element.get("faces") or {}
            polygroup_ids = _get_polygroup_ids(box_mesh)
            face_groups = {}
            for polygroup_id in polygroup_ids:
                face_groups[_infer_face_direction(box_mesh, polygroup_id)] = polygroup_id

            for face_name, polygroup_id in face_groups.items():
                triangle_ids = _get_triangles_in_polygroup(box_mesh, polygroup_id)
                face_data = faces.get(face_name)
                if not face_data:
                    _delete_triangles(box_mesh, triangle_ids)
                    continue

                texture_ref = face_data.get("texture")
                if not texture_ref:
                    _delete_triangles(box_mesh, triangle_ids)
                    continue

                if texture_ref.startswith("#"):
                    texture_file = _resolve_texture_reference(model_path, textures, texture_ref[1:])
                else:
                    texture_file = _resolve_texture_reference(model_path, {"direct": texture_ref}, "direct")

                material_index, _, _ = get_material_index(texture_file)
                _set_material_id_on_triangles(box_mesh, triangle_ids, material_index)
                uv_rect = _face_uv_rect(face_name, face_data.get("uv"), bounds_from, bounds_to)
                _apply_uv_rect_to_triangles(box_mesh, triangle_ids, uv_rect, face_data.get("rotation", 0))

            unreal.GeometryScript_MeshEdits.append_mesh(target_mesh, box_mesh, _identity_transform())
        finally:
            _return_dynamic_mesh(box_mesh)

    if not material_slots:
        raise RuntimeError(f"Model produced no materials: {model_path}")

    return category, target_mesh, material_slots


def _first_static_mesh(imported_assets):
    return next((asset for asset in imported_assets if isinstance(asset, unreal.StaticMesh)), None)

def _generate_collision(mesh, count=4, verts=16, precision=100000):
    mesh_subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    mesh_subsystem.set_convex_decomposition_collisions(
        mesh, 
        hull_count=count, 
        max_hull_verts=verts, 
        hull_precision=precision
    )
    

def import_item(
    filepath,
    destination_path="/Game/mc",
    asset_name=None,
    size=100.0,
    thickness=6.25,
    alpha_threshold=0.5,
    max_resolution=32,  # 默认上限设为 32x32
    reload=False,       # 新增：是否重新导入
):
    source = _normalize_source_file(filepath)
    if source.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError(f"import_item only supports image files: {source}")

    item_root = _mc_root_path(destination_path, "item")
    base_name = _sanitize_asset_name(asset_name or source.stem)
    
    # 提前计算目标静态网格体资产路径并检查
    target_mesh_path = _asset_path(item_root, _mc_mesh_asset_name(base_name))
    if not reload:
        existing_mesh = _load_asset_if_exists(target_mesh_path, unreal.StaticMesh)
        if existing_mesh:
            unreal.log(f"import_item: Asset already exists, skipping: {target_mesh_path}")
            return existing_mesh

    texture_package = _mc_texture_path(destination_path, "item")
    material_package = _mc_material_path(destination_path, "item")
    texture_name = _sanitize_asset_name(source.stem)

    texture_asset = _import_texture_asset(source, texture_package, texture_name)
    material_asset = _create_texture_material(texture_asset, material_package, texture_name)

    dynamic_mesh = None
    try:
        image_width, image_height, opaque_mask = _sample_texture_alpha_mask(texture_asset, alpha_threshold, max_resolution)
        if image_width >= image_height:
            width_cm = float(size)
            height_cm = float(size) * (float(image_height) / float(max(image_width, 1)))
        else:
            height_cm = float(size)
            width_cm = float(size) * (float(image_width) / float(max(image_height, 1)))

        dynamic_mesh = _build_item_dynamic_mesh(width_cm, height_cm, thickness, opaque_mask)
        mesh_asset = _create_static_mesh_asset(
            dynamic_mesh,
            target_mesh_path,
            [material_asset],
        )

        unreal.log(f"import_item created: {mesh_asset.get_path_name()}")
        _generate_collision(mesh_asset)
        return mesh_asset
    finally:
        _return_dynamic_mesh(dynamic_mesh)


def import_block(
    filepath,
    destination_path="/Game/mc",
    asset_name=None,
    max_resolution=32,  # 添加 max_resolution 参数传给生成的 item
    reload=False,       # 新增：是否重新导入
):
    source = _normalize_source_file(filepath)
    suffix = source.suffix.lower()
    base_name = _sanitize_asset_name(asset_name or source.stem)

    if suffix == ".json":
        # 针对 JSON 的轻量级预判（只读配置，不触发生成逻辑）
        model_data = _load_mc_model(source)
        elements = model_data.get("elements") or []
        textures = model_data.get("textures") or {}
        category = "item" if model_data.get("parent") in {"item/generated", "builtin/generated"} else "block"

        # 判断最终的 category 存放夹
        if not elements and category == "item" and "layer0" in textures:
            target_root = _mc_root_path(destination_path, "item")
        else:
            target_root = _mc_root_path(destination_path, category)

        target_mesh_path = _asset_path(target_root, _mc_mesh_asset_name(base_name))
        
        if not reload:
            existing_mesh = _load_asset_if_exists(target_mesh_path, unreal.StaticMesh)
            if existing_mesh:
                unreal.log(f"import_block (json): Asset already exists, skipping: {target_mesh_path}")
                return existing_mesh

        # 若资产不存在或 reload=True，正常进入构建工作流
        built = _build_block_dynamic_mesh(source, destination_path, base_name)

        if built[0] == "item" and len(built) == 2:
            return import_item(
                built[1],
                destination_path=destination_path,
                asset_name=base_name,
                max_resolution=max_resolution,
                reload=reload,  # 向下传递 reload 状态
            )

        category, dynamic_mesh, materials = built
        model_root = _mc_root_path(destination_path, category)

        try:
            mesh_asset = _create_static_mesh_asset(
                dynamic_mesh,
                _asset_path(model_root, _mc_mesh_asset_name(base_name)),
                materials,
            )
            _generate_collision(mesh_asset)
            unreal.log(f"import_block created from json: {mesh_asset.get_path_name()}")
            return mesh_asset
        finally:
            _return_dynamic_mesh(dynamic_mesh)

    if suffix not in MESH_SUFFIXES:
        raise ValueError(f"import_block only supports json or mesh files: {source}")

    block_root = _mc_root_path(destination_path, "block")
    target_mesh_path = _asset_path(block_root, _mc_mesh_asset_name(base_name))
    
    # 常规模型外部导入文件（FBX/OBJ）的提前截断
    if not reload:
        existing_mesh = _load_asset_if_exists(target_mesh_path, unreal.StaticMesh)
        if existing_mesh:
            unreal.log(f"import_block (mesh): Asset already exists, skipping: {target_mesh_path}")
            return existing_mesh

    imported_assets = _run_import_task(_make_import_task(source, block_root, _mc_mesh_asset_name(base_name)))
    mesh_asset = _first_static_mesh(imported_assets)
    if mesh_asset is None:
        raise RuntimeError(f"No StaticMesh was imported from: {source}")

    _generate_collision(mesh_asset)
    unreal.log(f"import_block imported: {mesh_asset.get_path_name()}")
    return mesh_asset