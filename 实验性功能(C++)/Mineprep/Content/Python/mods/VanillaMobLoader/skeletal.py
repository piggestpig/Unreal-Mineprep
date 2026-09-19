"""Interchange skeletal import; all Unreal operations run on the editor thread."""
import json
import uuid
import unreal
from . import importer
from .assets import CACHE
from .gltf import encode


def prerequisites():
    if not all(hasattr(unreal, n) for n in ('InterchangeManager', 'InterchangeGenericAssetsPipeline', 'ImportAssetParameters')):
        raise RuntimeError(importer.message('请启用 Interchange 导入支持', 'Enable Interchange import support'))
    material = unreal.load_asset(importer.MATERIAL)
    if not isinstance(material, unreal.MaterialInstanceConstant):
        raise RuntimeError('Missing skin material: ' + importer.MATERIAL)
    if '纹理贴图' not in [str(n) for n in unreal.MaterialEditingLibrary.get_texture_parameter_names(material)]:
        raise RuntimeError('Skin material has no skin texture parameter')


def pipeline():
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

    p.common_meshes_properties.keep_sections_separate = True
    p.common_meshes_properties.recompute_normals = False
    p.common_meshes_properties.recompute_tangents = True
    p.common_meshes_properties.use_full_precision_u_vs = True
    p.common_skeletal_meshes_and_animations_properties.skeleton = None
    p.common_skeletal_meshes_and_animations_properties.use_t0_as_ref_pose = False
    return p


def create_assets(entry, version, target, geometry, skin_path=None, reload=False, material_sources=None):
    folder, name, existing = target
    if existing and not reload:
        return existing, []

    lib = unreal.EditorAssetLibrary
    destinations = [folder+'/SKM_'+name, folder+'/SK_'+name]
    if not existing and any(lib.does_asset_exist(p) for p in destinations):
        raise ValueError('Conflicting skeletal assets: ' + folder)

    data, mapping = encode(geometry, 'SKM_'+name)
    path = CACHE/'resources'/'generated'/('SKM_'+name+'.glb')
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_bytes(data)
        temporary.replace(path)
    except OSError as exc:
        raise RuntimeError(importer.message('无法写入模型缓存：', 'Cannot write model cache: ') + str(exc)) from exc

    if existing:
        return reimport_asset(entry, version, target, geometry, skin_path, path, mapping, material_sources)

    stage = importer.BASE+'/__import_'+uuid.uuid4().hex
    created, moved, warnings = [], [], list(geometry.warnings)
    # Texture/material paths absent at entry are exclusively owned by this call.
    sources = material_sources or [(entry, name, skin_path, geometry)]
    owned_skin = [folder+'/'+prefix+n+suffix for _,n,_,_ in sources
                  for prefix,suffix in (('T_',''),('MI_',''))
                  if not lib.does_asset_exist(folder+'/'+prefix+n+suffix)]

    try:
        p = pipeline()  # Keep a strong reference until synchronous import completes.
        parameters = unreal.ImportAssetParameters()
        parameters.is_automated = True
        parameters.replace_existing = False
        parameters.override_pipelines = [unreal.SoftObjectPath(p.get_path_name())]
        manager = unreal.InterchangeManager.get_interchange_manager_scripted()
        source = unreal.InterchangeManager.create_source_data(str(path))
        objects = manager.import_asset(stage, source, parameters) or []

        meshes = [o for o in objects if isinstance(o, unreal.SkeletalMesh)]
        skeletons = [o for o in objects if isinstance(o, unreal.Skeleton)]
        if len(meshes) != 1 or len(skeletons) != 1 or len(objects) != 2:
            raise RuntimeError('Expected one SkeletalMesh and one Skeleton')
        mesh, skeleton = meshes[0], skeletons[0]
        if mesh.skeleton != skeleton or mesh.physics_asset:
            raise RuntimeError('Invalid imported skeleton or unexpected PhysicsAsset')

        assign_materials(mesh, folder, sources, created, warnings)

        for asset, destination in zip((mesh,skeleton), destinations):
            if not lib.rename_asset(asset.get_path_name(), destination):
                raise RuntimeError('Could not move imported asset: '+destination)
            moved.append(destination)
        created += [skeleton,mesh]

        for asset in (mesh, skeleton):
            lib.set_metadata_tag(asset, importer.KEY, entry.key)
        for key,value in {'Version':version, 'Model':entry.model, 'Name':entry.name,
                          'Bones':json.dumps(mapping), 'Parts':json.dumps(geometry.parts)}.items():
            lib.set_metadata_tag(mesh, 'VanillaMobLoader.'+key, value)
        for asset in created:
            if not lib.save_loaded_asset(asset):
                raise RuntimeError('Failed to save '+asset.get_path_name())
        lib.set_metadata_tag(mesh, importer.COMPLETE, '1')
        if not lib.save_loaded_asset(mesh):
            raise RuntimeError('Failed to save completion marker')
        return mesh, warnings
    except Exception:
        for p in moved + list(reversed(owned_skin)):
            if lib.does_asset_exist(p):
                lib.delete_asset(p)
        raise
    finally:
        # Only the UUID staging directory belongs to this call, including redirectors.
        if lib.does_directory_exist(stage):
            lib.delete_directory(stage)


def reimport_asset(entry, version, target, geometry, skin_path, path, mapping, material_sources):
    """Reimport in place so scene components and animation references survive."""
    folder, name, mesh = target
    lib = unreal.EditorAssetLibrary
    skeleton = mesh.skeleton
    if not skeleton or lib.get_metadata_tag(skeleton, importer.KEY) != lib.get_metadata_tag(mesh, importer.KEY):
        raise ValueError('Cannot update a missing or foreign skeleton')
    created, warnings = [], list(geometry.warnings)
    sources = material_sources or [(entry, name, skin_path, geometry)]
    p = pipeline()
    p.common_skeletal_meshes_and_animations_properties.skeleton = skeleton
    p.mesh_pipeline.update_skeleton_reference_pose = True
    parameters = unreal.ImportAssetParameters()
    parameters.is_automated = True
    parameters.replace_existing = True
    parameters.reimport_asset = mesh
    parameters.override_pipelines = [unreal.SoftObjectPath(p.get_path_name())]
    manager = unreal.InterchangeManager.get_interchange_manager_scripted()
    source = unreal.InterchangeManager.create_source_data(str(path))
    result = manager.import_asset(folder, source, parameters)
    if not result or mesh not in result or mesh.skeleton != skeleton:
        raise RuntimeError('Skeletal mesh reimport failed; existing assets were not deleted')
    assign_materials(mesh, folder, sources, created, warnings)
    for asset in (mesh,skeleton):
        lib.set_metadata_tag(asset, importer.KEY, entry.key)
    for key,value in {'Version':version, 'Model':entry.model, 'Name':entry.name,
                      'Bones':json.dumps(mapping), 'Parts':json.dumps(geometry.parts)}.items():
        lib.set_metadata_tag(mesh, 'VanillaMobLoader.'+key, value)
    for asset in created + [skeleton, mesh]:
        if not lib.save_loaded_asset(asset):
            raise RuntimeError('Failed to save updated asset: '+asset.get_path_name())
    return mesh, warnings


def assign_materials(mesh, folder, sources, created, warnings):
    materials = []
    for entry,name,path,geo in sources:
        begin = len(created)
        materials.append(importer.surface_material(entry, folder, name, path, created, warnings, geo))
        for asset in created[begin:]:
            unreal.EditorAssetLibrary.set_metadata_tag(asset, importer.KEY, entry.key)
    slots = list(mesh.materials)
    if len(materials) == 1 and len(slots) == 1:
        slots[0].material_interface = materials[0]
    else:
        if len(slots) != len(materials):
            raise RuntimeError('Imported material slot count does not match composition')
        used = set()
        for slot in slots:
            label = str(slot.material_slot_name)
            if not label.startswith('VML_') or not label[4:].isdigit():
                raise RuntimeError('Unrecognized imported material slot: '+label)
            index = int(label[4:])
            if index >= len(materials) or index in used:
                raise RuntimeError('Invalid imported material slot: '+label)
            used.add(index)
            slot.material_interface = materials[index]
    mesh.set_editor_property('materials', slots)
