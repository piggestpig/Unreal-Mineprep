"""生物材质和关卡视口放置辅助（需在主线程调用）。"""
import json
import math

import unreal
import mineprep
from mineprep import i18n
from mineprep.model_assets import COMPLETE, RECIPE, SOURCE, SKIN_MATERIAL as MATERIAL, skin_instance
from . import names

BASE = '/Game/mc/mob'
ENTRIES = 'VanillaMobLoader.Entries'
BASE_ACTOR = '/Game/Mineprep/生物模型rigs/Core/基础生物模型'
SPLIT_ACTOR = '/Game/Mineprep/生物模型rigs/Core/头身分离绑定基础生物模型'


def composition_target(recipe, folder, name, source, keys, reload=False):
    path = folder+'/SKM_'+name
    lib = unreal.EditorAssetLibrary
    existing = unreal.load_asset(path) if lib.does_asset_exist(path) else None
    if existing:
        if not isinstance(existing, unreal.SkeletalMesh) or lib.get_metadata_tag(existing, SOURCE) != source:
            raise ValueError(str(i18n('目标资产名称被占用，请更换保存名称：',
                                      'Destination is occupied. Choose a different save name: '))+path)
        if lib.get_metadata_tag(existing, COMPLETE) != '1':
            raise ValueError('Incomplete asset: '+path)
        if lib.get_metadata_tag(existing, ENTRIES) != json.dumps(keys):
            raise ValueError(str(i18n('目标资产的条目不同，请更换保存名称',
                                     'Existing asset uses a different selection. Choose a different save name.')))
        if not reload and lib.get_metadata_tag(existing, RECIPE) != recipe:
            raise ValueError(str(i18n('目标资产的导入选项不同，请重新导入或更换保存名称',
                                     'Import options changed. Reimport or choose a different save name.')))
        skeleton = existing.skeleton
        if (not skeleton or lib.get_metadata_tag(skeleton, SOURCE) != source
                or lib.get_metadata_tag(skeleton, ENTRIES) != json.dumps(keys)):
            raise ValueError('Missing or foreign Skeleton: ' + path)
    return folder,name,existing


def skin_name(entry, folder, base, reserved=()):
    """生成皮肤纹理与材质实例的资产名；发生命名冲突时自动追加数字后缀。"""
    lib = unreal.EditorAssetLibrary
    suffix = 0
    while True:
        name = base if suffix == 0 else base+'_'+str(suffix)
        occupied = name.casefold() in reserved
        for prefix, cls in (('T_', unreal.Texture2D), ('MI_', unreal.MaterialInstanceConstant)):
            path = folder+'/'+prefix+name
            if lib.does_asset_exist(path):
                asset = unreal.load_asset(path)
                occupied |= not isinstance(asset, cls) or lib.get_metadata_tag(asset, RECIPE) != entry.key
        if not occupied:
            return name
        suffix += 1


def skin_material(entry, folder, name, skin_path, created, warnings):
    paths = [None, folder + '/T_' + name, folder + '/MI_' + name]
    existing = {}
    for path, cls in ((paths[1], unreal.Texture2D), (paths[2], unreal.MaterialInstanceConstant)):
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            asset = unreal.load_asset(path)
            if not isinstance(asset, cls) or unreal.EditorAssetLibrary.get_metadata_tag(asset, RECIPE) != entry.key:
                raise ValueError("Conflicting skin asset: " + path)
            existing[path] = asset

    if skin_path is not None and paths[2] in existing:
        return existing[paths[2]]
    if not skin_path or not skin_path.is_file():
        warnings.append(str(i18n('未包含皮肤贴图，已使用默认材质', 'No skin texture; assigned default material')))
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
            raise RuntimeError(str(i18n('皮肤 PNG 导入失败', 'Skin PNG import failed')))
        created.append(texture)
        mineprep.prep_texture(texture)

    return skin_instance(texture, paths[2], created)





def placement_target():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    camera = editor.get_level_viewport_camera_info()
    if not camera or camera[0] is None:
        raise RuntimeError(str(i18n('没有有效的关卡视口，无法放置', 'No valid level viewport for placement')))

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


def place(mesh, scale=1., target=None, *, head_mesh=None):
    scale = float(scale)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('Scale must be positive')

    position, grounded = target or placement_target()
    skeletal = isinstance(mesh, unreal.SkeletalMesh)
    if head_mesh is not None and (not skeletal or not isinstance(head_mesh, unreal.SkeletalMesh)):
        raise ValueError('头身分离需要身体和头部两个 SkeletalMesh')
    actor_class = unreal.StaticMeshActor
    if skeletal:
        blueprint = SPLIT_ACTOR if head_mesh is not None else BASE_ACTOR
        actor_class = unreal.load_class(None, blueprint + '.' + blueprint.rsplit('/', 1)[-1] + '_C')
    if actor_class is None:
        raise RuntimeError('找不到生物基础蓝图')
    if grounded:
        if skeletal:
            bounds = mesh.get_bounds()
            bottom = bounds.origin.z - bounds.box_extent.z
        else:
            bottom = mesh.get_bounding_box().min.z
        position = unreal.Vector(position.x, position.y, position.z - bottom * scale)

    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    with unreal.ScopedEditorTransaction(str(i18n('放置原版生物', 'Place Vanilla Mob'))):
        actor = subsystem.spawn_actor_from_class(actor_class, position, unreal.Rotator())
        if not actor:
            raise RuntimeError('Failed to spawn mob Actor')
        try:
            if skeletal:
                actor.skeletal_mesh_component.set_skeletal_mesh_asset(mesh)
                if head_mesh is not None:
                    head = next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent)
                                if c.get_name() == 'Head')
                    head.set_anim_instance_class(None)
                    head.set_skeletal_mesh_asset(head_mesh)
                    head.set_animation_mode(unreal.AnimationMode.ANIMATION_CUSTOM_MODE)
                    head.set_relative_transform(unreal.Transform(), False, True)
            else:
                actor.static_mesh_component.set_static_mesh(mesh)
            actor.set_actor_scale3d(unreal.Vector(scale, scale, scale))
            source_name = unreal.EditorAssetLibrary.get_metadata_tag(mesh, 'VanillaMobLoader.Name') or mesh.get_name()
            actor.set_actor_label(str(names.text(source_name)))
            subsystem.set_selected_level_actors([actor])
        except Exception:
            subsystem.destroy_actor(actor)
            raise
    return actor
