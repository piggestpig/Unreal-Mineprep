"""Static asset creation and placement. Call only from the editor/game thread."""
import hashlib
import json
import math
import re

import unreal
import mineprep

BASE = '/Game/mc/mob'
MATERIAL = '/Game/Mineprep/材质/皮肤/Core/皮肤_Steve'
KEY = 'VanillaMobLoader.Selection'
COMPLETE = 'VanillaMobLoader.Complete'


def message(zh, en):
    return str(mineprep.bilingual(zh, en))


def slug(ident):
    value = re.sub(r'[^a-zA-Z0-9_]', '_', ident).strip('_') or 'entity'
    return value[:96]


def asset_target(entry, catalog, skeletal=False):
    prefix = 'SKM_' if skeletal else 'SM_'
    asset_class = unreal.SkeletalMesh if skeletal else unreal.StaticMesh
    name = slug(entry.id)
    if sum(slug(e.id).lower() == name.lower() for e in catalog.entries) > 1:
        name += '_' + hashlib.sha256(entry.key.encode()).hexdigest()[:10]

    folder = BASE + '/' + name
    path = folder + '/' + prefix + name
    existing = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if existing and unreal.EditorAssetLibrary.get_metadata_tag(existing, KEY) != entry.key:
        name += '_' + hashlib.sha256(entry.key.encode()).hexdigest()[:10]
        folder = BASE + '/' + name
        path = folder + '/' + prefix + name
        existing = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None

    if existing:
        if not isinstance(existing, asset_class) or unreal.EditorAssetLibrary.get_metadata_tag(existing, KEY) != entry.key:
            raise ValueError(message('目标资产名称被占用：', 'Asset name is occupied: ') + path)
        if unreal.EditorAssetLibrary.get_metadata_tag(existing, COMPLETE) != '1':
            raise ValueError(message('存在未完成的资产，请先在内容浏览器检查：', 'Inspect the incomplete asset in the Content Browser: ') + path)
    return folder, name, existing


def prerequisites():
    required = ('GeometryScript_MeshEdits', 'GeometryScript_NewAssetUtils', 'GeometryScriptSimpleMeshBuffers')
    if not all(hasattr(unreal, name) for name in required):
        raise RuntimeError(message('请启用 Geometry Script 插件', 'Enable the Geometry Script plugin'))
    material = unreal.load_asset(MATERIAL)
    if not isinstance(material, unreal.MaterialInstanceConstant):
        raise RuntimeError(message('找不到模板材质：', 'Missing template material: ') + MATERIAL)
    if '纹理贴图' not in [str(n) for n in unreal.MaterialEditingLibrary.get_texture_parameter_names(material)]:
        raise RuntimeError(message('模板材质缺少“纹理贴图”参数', 'Template material has no skin texture parameter'))


def composition_target(entry, folder, name, reload=False):
    path = folder+'/SKM_'+name
    lib = unreal.EditorAssetLibrary
    existing = unreal.load_asset(path) if lib.does_asset_exist(path) else None
    if existing:
        if not isinstance(existing, unreal.SkeletalMesh) or not lib.get_metadata_tag(existing, KEY):
            raise ValueError(message('目标路径被外部资产占用：', 'Foreign asset at destination: ')+path)
        if lib.get_metadata_tag(existing, COMPLETE) != '1':
            raise ValueError('Incomplete asset: '+path)
        if lib.get_metadata_tag(existing, KEY) != entry.key and not reload:
            raise ValueError(message('已有资产配方不同，请重新加载生物或更换保存名称',
                                     'Recipe differs; reload the entity or change the save name'))
    return folder,name,existing


def skin_name(entry, folder, base, reserved=()):
    """Reuse owned names; allocate a readable numeric suffix on collision."""
    lib = unreal.EditorAssetLibrary
    suffix = 0
    while True:
        name = base if suffix == 0 else base+'_'+str(suffix)
        occupied = name.casefold() in reserved
        for prefix, cls in (('T_', unreal.Texture2D), ('MI_', unreal.MaterialInstanceConstant)):
            path = folder+'/'+prefix+name
            if lib.does_asset_exist(path):
                asset = unreal.load_asset(path)
                occupied |= not isinstance(asset, cls) or lib.get_metadata_tag(asset, KEY) != entry.key
        if not occupied:
            return name
        suffix += 1


def surface_material(entry, folder, name, skin_path, created, warnings, geometry):
    return skin_material(entry, folder, name, skin_path, created, warnings)


def skin_material(entry, folder, name, skin_path, created, warnings):
    paths = [None, folder + '/T_' + name, folder + '/MI_' + name]
    existing = {}
    for path, cls in ((paths[1], unreal.Texture2D), (paths[2], unreal.MaterialInstanceConstant)):
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            asset = unreal.load_asset(path)
            if not isinstance(asset, cls) or unreal.EditorAssetLibrary.get_metadata_tag(asset, KEY) != entry.key:
                raise ValueError("Conflicting skin asset: " + path)
            existing[path] = asset

    if skin_path is not None and paths[2] in existing:
        return existing[paths[2]]
    if not skin_path or not skin_path.is_file():
        warnings.append(message("未使用皮肤：已分配默认中性材质", "No skin: using the default neutral material"))
        return unreal.load_asset("/Engine/EngineMaterials/DefaultMaterial")

    texture = existing.get(paths[1])
    if texture is None:
        task = unreal.AssetImportTask()
        task.set_editor_property('filename', str(skin_path))
        task.set_editor_property('destination_path', folder)
        task.set_editor_property('destination_name', 'T_' + name)
        task.set_editor_property('automated', True)
        task.set_editor_property('save', False)
        task.set_editor_property('replace_existing', False)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        texture = unreal.load_asset(paths[1])
        if not isinstance(texture, unreal.Texture2D):
            raise RuntimeError(message('皮肤 PNG 导入失败', 'Skin PNG import failed'))
        created.append(texture)
        mineprep.prep_texture(texture)

    material = unreal.EditorAssetLibrary.duplicate_asset(MATERIAL, paths[2])
    if not material:
        raise RuntimeError('Failed to duplicate skin material')
    created.append(material)

    # UE 5.7's setter always returns false; verify the actual parameter.
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material, '纹理贴图', texture)
    if unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(material, '纹理贴图') != texture:
        raise RuntimeError('Failed to assign skin texture')
    return material


def create_assets(entry, version, target, geometry, skin_path=None):
    folder, name, existing = target
    if existing:
        return existing, []

    paths = [folder + '/SM_' + name, folder + '/T_' + name, folder + '/MI_' + name]
    if unreal.EditorAssetLibrary.does_asset_exist(paths[0]):
        raise ValueError(message('目标目录存在冲突资产，未覆盖：', 'Conflicting assets; nothing overwritten: ') + folder)
    owned = [p for p in paths if not unreal.EditorAssetLibrary.does_asset_exist(p)]
    created = []
    warnings = list(geometry.warnings)

    try:
        material = surface_material(entry, folder, name, skin_path, created, warnings, geometry)

        mesh = unreal.DynamicMesh()
        buffers = unreal.GeometryScriptSimpleMeshBuffers(
            vertices=[unreal.Vector(*p) for p in geometry.vertices],
            triangles=[unreal.IntVector(*t) for t in geometry.triangles],
            normals=[unreal.Vector(*n) for n in geometry.normals],
            uv0=[unreal.Vector2D(*uv) for uv in geometry.uv],
            tri_group_i_ds=geometry.groups,
            vertex_colors=[unreal.LinearColor(1,1,1,1)] * len(geometry.vertices))
        unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(mesh, buffers)

        options = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
        static_mesh, outcome = unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(mesh, paths[0], options)
        if not static_mesh or outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
            raise RuntimeError('StaticMesh creation failed')
        created.append(static_mesh)
        static_mesh.set_material(0, material)

        for asset in created:
            unreal.EditorAssetLibrary.set_metadata_tag(asset, KEY, entry.key)
        metadata = {'VanillaMobLoader.Version': version,
                    'VanillaMobLoader.Model': entry.model,
                    'VanillaMobLoader.Name': entry.name,
                    'VanillaMobLoader.Parts': json.dumps(geometry.parts, ensure_ascii=True),
                    COMPLETE: '1'}
        for key, value in metadata.items():
            unreal.EditorAssetLibrary.set_metadata_tag(static_mesh, key, value)
        for asset in created:
            if not unreal.EditorAssetLibrary.save_loaded_asset(asset):
                raise RuntimeError('Failed to save ' + asset.get_path_name())
        return static_mesh, warnings
    except Exception:
        # Paths were checked absent before construction. Only this transaction's
        # newly created assets can be removed; pre-existing assets are untouched.
        for path in (paths[0], paths[3], paths[2], paths[1]):
            if path in owned and unreal.EditorAssetLibrary.does_asset_exist(path):
                unreal.EditorAssetLibrary.delete_asset(path)
        raise


def placement_target():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    camera = editor.get_level_viewport_camera_info()
    if not camera or camera[0] is None:
        raise RuntimeError(message('没有有效的关卡视口，无法放置', 'No valid level viewport for placement'))

    location, rotation = camera
    direction = unreal.MathLibrary.get_forward_vector(rotation)
    hit = unreal.SystemLibrary.line_trace_single(
        mineprep.world(), location, location + direction * 100000,
        unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [], unreal.DrawDebugTrace.NONE)
    if hit:
        values = hit.to_tuple()
        if values[0]:
            return values[5], True
    return location + direction * 500, False


def place(mesh, scale=1., target=None):
    scale = float(scale)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('Scale must be positive')

    position, grounded = target or placement_target()
    skeletal = isinstance(mesh, unreal.SkeletalMesh)
    if grounded:
        if skeletal:
            bounds = mesh.get_bounds()
            bottom = bounds.origin.z - bounds.box_extent.z
        else:
            bottom = mesh.get_bounding_box().min.z
        position = unreal.Vector(position.x, position.y, position.z - bottom * scale)

    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    with unreal.ScopedEditorTransaction(message('放置原版生物', 'Place vanilla entity')):
        actor = subsystem.spawn_actor_from_class(unreal.SkeletalMeshActor if skeletal else unreal.StaticMeshActor, position, unreal.Rotator())
        if not actor:
            raise RuntimeError('Failed to spawn StaticMeshActor')
        try:
            if skeletal:
                actor.skeletal_mesh_component.set_skeletal_mesh_asset(mesh)
            else:
                actor.static_mesh_component.set_static_mesh(mesh)
            actor.set_actor_scale3d(unreal.Vector(scale, scale, scale))
            actor.set_actor_label(unreal.EditorAssetLibrary.get_metadata_tag(mesh, 'VanillaMobLoader.Name') or mesh.get_name())
            subsystem.set_selected_level_actors([actor])
        except Exception:
            subsystem.destroy_actor(actor)
            raise
    return actor
