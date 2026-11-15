"""Editor-side publishing for Mineprep's skinned GLBs with embedded base colours."""

import hashlib
import json
from pathlib import Path
from uuid import uuid4

import unreal

from mc_model import cache_model_source, embedded_base_color_surfaces
from mc_prep import prep_texture

SKIN_MATERIAL = '/Game/Mineprep/材质/皮肤/Core/皮肤_Steve'
TRANSLUCENT_SKIN = '/Game/Mineprep/材质/半透明Core/LabPBR半透明1_Inst'
RECIPE = 'Mineprep.Model.Recipe'
COMPLETE = 'Mineprep.Model.Complete'
SOURCE = 'Mineprep.Model.Source'
CONTENT_HASH = 'Mineprep.Model.ContentHash'


def pipeline(*, combine_by_skeleton=False):
    p = unreal.InterchangeGenericAssetsPipeline()
    p.asset_type_sub_folders = False
    p.scene_name_sub_folder = False
    p.import_offset_uniform_scale = 1
    p.import_offset_rotation = unreal.Rotator()
    p.import_offset_translation = unreal.Vector()

    p.mesh_pipeline.import_static_meshes = False
    p.mesh_pipeline.import_skeletal_meshes = True
    p.mesh_pipeline.create_physics_asset = False
    p.animation_pipeline.import_animations = False
    p.material_pipeline.import_materials = False
    p.material_pipeline.texture_pipeline.import_textures = False
    if combine_by_skeleton:
        p.mesh_pipeline.combine_skeletal_meshes_behavior = unreal.InterchangeCombineSkeletalMeshesBehavior.BY_SKELETON

    p.common_meshes_properties.keep_sections_separate = True
    p.common_meshes_properties.recompute_normals = False
    p.common_meshes_properties.recompute_tangents = True
    p.common_meshes_properties.use_full_precision_u_vs = True
    p.common_skeletal_meshes_and_animations_properties.skeleton = None
    p.common_skeletal_meshes_and_animations_properties.use_t0_as_ref_pose = False
    return p


def import_glb(folder, path, pipeline, mesh=None):
    parameters = unreal.ImportAssetParameters()
    parameters.is_automated = True
    parameters.replace_existing = mesh is not None
    if mesh is not None:
        parameters.reimport_asset = mesh
    parameters.override_pipelines = [unreal.SoftObjectPath(pipeline.get_path_name())]
    manager = unreal.InterchangeManager.get_interchange_manager_scripted()
    source = unreal.InterchangeManager.create_source_data(str(path))
    return manager.import_asset(folder, source, parameters) or []


def _import_texture(folder, image, mime):
    suffix = {'image/png': '.png', 'image/jpeg': '.jpg'}[mime]
    cache = Path(unreal.Paths.project_intermediate_dir()) / 'MineprepModels'
    path = cache_model_source(cache, 'Skin' + suffix, image)
    task = unreal.AssetImportTask()
    task.filename = str(path)
    task.destination_path = folder
    task.automated = True
    task.save = False
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    textures = task.get_objects()
    if len(textures) != 1 or not isinstance(textures[0], unreal.Texture2D):
        raise RuntimeError('Failed to import GLB skin: ' + str(path))
    return textures[0]


def skin_instance(texture, destination, created, template=SKIN_MATERIAL):
    material = unreal.EditorAssetLibrary.duplicate_asset(template, destination)
    if not material:
        raise RuntimeError('Failed to duplicate skin material')
    created.append(material)

    # UE 5.7+ 的 setter 可能恒返回 False，需通过回读参数确认是否绑定成功
    unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material, '纹理贴图', texture)
    if unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(material, '纹理贴图') != texture:
        raise RuntimeError('Failed to assign skin texture')
    return material


def _reference_bones(mesh):
    component = unreal.SkeletalMeshComponent()
    component.set_skeletal_mesh_asset(mesh)
    result = {}
    for index in range(component.get_num_bones()):
        bone = component.get_bone_name(index)
        result[str(bone)] = (str(component.get_parent_bone(bone)), component.get_ref_pose_transform(index))
    return result


def _check_reimport(existing, preview, allow_pose_change):
    before, after = _reference_bones(existing), _reference_bones(preview)
    if {name: parent for name, (parent, _) in before.items()} != {
            name: parent for name, (parent, _) in after.items()}:
        raise ValueError('骨骼名称或层级有变化，请更换保存名称 / Bone hierarchy changed. Choose a new save name.')
    if not allow_pose_change and any(not pose.is_near_equal(after[name][1])
                                     for name, (_, pose) in before.items()):
        raise ValueError('Bone reference pose changed. Choose a new save name.')


def _tag(asset, metadata):
    for key, value in metadata.items():
        unreal.EditorAssetLibrary.set_metadata_tag(asset, key, value)


def _import(target, path, owner, metadata, allow_pose_change, shared_materials):
    folder, name, existing = target
    lib = unreal.EditorAssetLibrary
    if not existing and lib.does_asset_exist(folder + '/SK_' + name):
        raise ValueError('Skeleton name is occupied. Choose a different save name.')
    surfaces = embedded_base_color_surfaces(path.read_bytes())
    stage = '/Game/mc/entity/__import_' + uuid4().hex
    moved = []
    attached = False

    def publish(asset, destination):
        if not lib.rename_asset(asset.get_path_name(), destination):
            raise RuntimeError('Could not move imported asset to ' + destination)
        moved.append(destination)
        return asset

    try:
        objects = import_glb(stage, path, pipeline(combine_by_skeleton=True))
        meshes = [o for o in objects if isinstance(o, unreal.SkeletalMesh)]
        skeletons = [o for o in objects if isinstance(o, unreal.Skeleton)]
        if len(meshes) != 1 or len(skeletons) != 1 or meshes[0].skeleton != skeletons[0]:
            raise RuntimeError('Expected one Skeletal Mesh and one shared Skeleton')
        preview = meshes[0]
        if existing:
            _check_reimport(existing, preview, allow_pose_change)

        slot_names = [str(slot.material_slot_name) for slot in preview.materials]
        if not slot_names or len(set(slot_names)) != len(slot_names) or not surfaces.keys() >= set(slot_names):
            raise RuntimeError('GLB material slots do not match embedded base-color surfaces')

        def save(asset, content_hash):
            _tag(asset, {SOURCE: owner[SOURCE], RECIPE: owner[RECIPE], CONTENT_HASH: content_hash})
            if not lib.save_loaded_asset(asset):
                raise RuntimeError('Failed to save ' + asset.get_path_name())

        def reuse(destination, cls, content_hash):
            if not lib.does_asset_exist(destination):
                return None
            asset = unreal.load_asset(destination)
            if (not isinstance(asset, cls) or lib.get_metadata_tag(asset, SOURCE) != owner[SOURCE]
                    or lib.get_metadata_tag(asset, RECIPE) != owner[RECIPE]):
                raise ValueError('GLB material or texture name is occupied. Choose a different save name: ' + destination)
            if lib.get_metadata_tag(asset, CONTENT_HASH) != content_hash:
                raise ValueError('GLB asset hash collision. Choose a different save name: ' + destination)
            return asset

        slot_materials = ({slot: shared_materials[slot] for slot in slot_names}
                          if shared_materials is not None else {})
        published_textures = {}
        for slot in (slot_names if shared_materials is None else ()):
            image, mime, alpha_mode = surfaces[slot]
            texture_hash = hashlib.sha256(image).hexdigest()
            texture = published_textures.get(texture_hash)
            if texture is None:
                texture_dst = f'{folder}/T_{name}_{texture_hash[:8]}'
                texture = reuse(texture_dst, unreal.Texture2D, texture_hash)
                if texture is None:
                    source_texture = _import_texture(stage, image, mime)
                    prep_texture(source_texture)
                    texture = publish(source_texture, texture_dst)
                    save(texture, texture_hash)
                published_textures[texture_hash] = texture
            template = TRANSLUCENT_SKIN if alpha_mode == 'BLEND' else SKIN_MATERIAL
            recipe = json.dumps([template, texture_hash])
            material_hash = hashlib.sha256(recipe.encode('utf-8')).hexdigest()
            material_dst = f'{folder}/MI_{name}_{material_hash[:8]}'
            instance = reuse(material_dst, unreal.MaterialInstanceConstant, material_hash)
            if instance is None:
                created = []
                try:
                    instance = skin_instance(texture, material_dst, created, template)
                finally:
                    moved.extend(asset.get_path_name().split('.')[0] for asset in created)
                save(instance, material_hash)
            slot_materials[slot] = instance

        if existing:
            mesh, skeleton = existing, existing.skeleton
            p = pipeline(combine_by_skeleton=True)
            p.common_skeletal_meshes_and_animations_properties.skeleton = skeleton
            p.mesh_pipeline.update_skeleton_reference_pose = allow_pose_change
            result = import_glb(folder, path, p, mesh)
            if mesh not in result or mesh.skeleton != skeleton:
                raise RuntimeError('GLB reimport did not retain the existing mesh and Skeleton')
        else:
            mesh, skeleton = preview, preview.skeleton
            publish(skeleton, folder + '/SK_' + name)
            publish(mesh, folder + '/SKM_' + name)

        slots = list(mesh.materials)
        if {str(slot.material_slot_name) for slot in slots} != slot_materials.keys():
            raise RuntimeError('GLB material slots changed during reimport')
        for slot in slots:
            slot.material_interface = slot_materials[str(slot.material_slot_name)]
        mesh.set_editor_property('materials', slots)
        attached = existing is not None

        _tag(skeleton, owner)
        _tag(mesh, {**owner, **metadata, COMPLETE: '1'})
        for asset in (skeleton, mesh):
            if not lib.save_loaded_asset(asset):
                raise RuntimeError('Failed to save ' + asset.get_path_name())
        return mesh
    except Exception:
        if not attached:
            for destination in reversed(moved):
                lib.delete_asset(destination)
        raise
    finally:
        if lib.does_directory_exist(stage):
            lib.delete_directory(stage)


def publish_skinned_glb(target, path, *, owner, metadata=None, allow_pose_change=False,
                        shared_materials=None):
    """Publish a GLB; shared_materials maps slot names to existing material instances."""
    try:
        return _import(target, path, owner, metadata or {}, allow_pose_change, shared_materials)
    except Exception as exc:
        raise RuntimeError(f'{path}: {exc}') from exc
