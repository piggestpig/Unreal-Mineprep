"""通过 Interchange 将生成的 GLB 导入为 UE 骨骼网格体与骨架资产（需在主线程调用）。"""
import json
import uuid
import unreal
from mineprep.model_assets import RECIPE, import_glb, pipeline
from mineprep import i18n
from . import importer
from .assets import CACHE
from .gltf import encode


def prerequisites():
    if not all(hasattr(unreal, n) for n in ('InterchangeManager', 'InterchangeGenericAssetsPipeline', 'ImportAssetParameters')):
        raise RuntimeError(str(i18n('请启用 Interchange 导入支持', 'Enable Interchange import support')))
    material = unreal.load_asset(importer.MATERIAL)
    if not isinstance(material, unreal.MaterialInstanceConstant):
        raise RuntimeError('Missing skin material: ' + importer.MATERIAL)
    if '纹理贴图' not in [str(n) for n in unreal.MaterialEditingLibrary.get_texture_parameter_names(material)]:
        raise RuntimeError('Skin material has no skin texture parameter')





def mark_assets(mesh, entry, keys, source, **metadata):
    lib = unreal.EditorAssetLibrary
    for asset in (mesh, mesh.skeleton):
        lib.set_metadata_tag(asset, RECIPE, entry.key)
        lib.set_metadata_tag(asset, importer.ENTRIES, json.dumps(keys))
        lib.set_metadata_tag(asset, importer.SOURCE, source)
    for key, value in metadata.items():
        lib.set_metadata_tag(mesh, 'VanillaMobLoader.' + key, value)


def create_assets(entry, version, target, geometry, *, keys, material_sources):
    folder, name, existing = target

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
        raise RuntimeError(str(i18n('无法写入模型缓存：', 'Cannot write model cache: ')) + str(exc)) from exc

    if existing:
        return reimport_asset(entry, version, target, geometry, path, mapping, material_sources, keys)

    stage = importer.BASE+'/__import_'+uuid.uuid4().hex
    created, moved, warnings = [], [], list(geometry.warnings)
    # Texture/material paths absent at entry are exclusively owned by this call.
    sources = material_sources
    owned_skin = [folder+'/'+prefix+n+suffix for _,n,_ in sources
                  for prefix,suffix in (('T_',''),('MI_',''))
                  if not lib.does_asset_exist(folder+'/'+prefix+n+suffix)]

    try:
        objects = import_glb(stage, path, pipeline())

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

        mark_assets(mesh, entry, keys, 'cem', Version=version, Model=entry.model, Name=entry.name,
                    Bones=json.dumps(mapping), Parts=json.dumps(geometry.parts))
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


def reimport_asset(entry, version, target, geometry, path, mapping, sources, keys):
    """原地重新导入骨骼网格体，保留场景组件与动画资产对原骨架的引用。"""
    folder, name, mesh = target
    lib = unreal.EditorAssetLibrary
    skeleton = mesh.skeleton
    if not skeleton or lib.get_metadata_tag(skeleton, RECIPE) != lib.get_metadata_tag(mesh, RECIPE):
        raise ValueError('Cannot update a missing or foreign skeleton')
    created, warnings = [], list(geometry.warnings)
    p = pipeline()
    p.common_skeletal_meshes_and_animations_properties.skeleton = skeleton
    p.mesh_pipeline.update_skeleton_reference_pose = True
    result = import_glb(folder, path, p, mesh)
    if not result or mesh not in result or mesh.skeleton != skeleton:
        raise RuntimeError('Skeletal mesh reimport failed; existing assets were not deleted')
    assign_materials(mesh, folder, sources, created, warnings)
    mark_assets(mesh, entry, keys, 'cem', Version=version, Model=entry.model, Name=entry.name,
                Bones=json.dumps(mapping), Parts=json.dumps(geometry.parts))
    for asset in created + [skeleton, mesh]:
        if not lib.save_loaded_asset(asset):
            raise RuntimeError('Failed to save updated asset: '+asset.get_path_name())
    return mesh, warnings


def assign_materials(mesh, folder, sources, created, warnings):
    materials = []
    for entry,name,path in sources:
        begin = len(created)
        materials.append(importer.skin_material(entry, folder, name, path, created, warnings))
        for asset in created[begin:]:
            unreal.EditorAssetLibrary.set_metadata_tag(asset, RECIPE, entry.key)
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
