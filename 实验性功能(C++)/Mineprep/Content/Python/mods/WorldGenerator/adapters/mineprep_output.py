"""Editor-only resource preparation and additive, undoable Actor placement."""
import re
import math
import hashlib
import json
from pathlib import Path
from time import perf_counter
import uuid
import mineprep
import numpy as np
import unreal
from ..core.data import to_ue
from ..naming import short_names, validate_output_name

_CLASSES = {
    'ism': '/Game/Mineprep/MC_Blueprint/Core/实例化方块.实例化方块',
    'pcg': '/Game/Mineprep/MC_Blueprint/PCG/PCG实例化方块.PCG实例化方块',
    'niagara': '/Game/Mineprep/MC_Blueprint/Niagara/动态地形粒子/动态结构粒子.动态结构粒子',
}
_WORLD_ROOT = '/Game/mc/WorldGenerator'
_MODEL_ROOT = _WORLD_ROOT+'/models'
_asset_index = {}  # full World texture-layout identity -> directory
_mesh_index = {}   # (full source identity, block ID) -> actual importer mesh path


def _load_assets(folder, key, tag, names):
    assets = []
    for name in names:
        path = folder+'/'+name
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            return None
        obj = unreal.load_asset(path)
        if (obj is None or not unreal.SystemLibrary.is_valid(obj)
                or unreal.EditorAssetLibrary.get_metadata_tag(obj,tag) != key):
            return None
        assets.append(obj)
    return tuple(assets)


def texture_folder(key, groups, *, name='World'):
    """One directory per geometry/partition; BCT variants remain inside it."""
    layout_key = hashlib.sha256(json.dumps((key, tuple(g.key for g in groups))).encode()).hexdigest()
    expected = {f'structure_{kind}_{i}': g.key
                for i,g in enumerate(groups,1) for kind in ('BPT','BRT')}
    candidates = []
    if layout_key in _asset_index:
        candidates.append(_asset_index[layout_key])
    for path in unreal.EditorAssetLibrary.list_assets(_WORLD_ROOT,recursive=True,include_folder=False):
        leaf = str(path)[len(_WORLD_ROOT)+1:].split('/')[0]
        match = re.fullmatch(r'.+_([0-9a-f]{8,64})',leaf)
        if match and len(match[1]) % 4 == 0 and layout_key.startswith(match[1]):
            candidates.append(_WORLD_ROOT+'/'+leaf)
    candidates.extend(_WORLD_ROOT+'/'+leaf for leaf in short_names(validate_output_name(name),layout_key))
    for folder in dict.fromkeys(candidates):
        paths = unreal.EditorAssetLibrary.list_assets(folder,recursive=True,include_folder=False)
        if paths:
            assets = [(str(p).split('.',1)[0],unreal.load_asset(p)) for p in paths]
            if any(obj is None or unreal.EditorAssetLibrary.get_metadata_tag(obj,'WGWorldKey') != layout_key
                   or (p.rsplit('/',1)[-1] in expected and unreal.EditorAssetLibrary.get_metadata_tag(
                       obj,'WGKey') != expected[p.rsplit('/',1)[-1]]) for p,obj in assets):
                continue
        _asset_index[layout_key] = folder
        return folder,layout_key
    raise FileExistsError('readable World texture directory is occupied')


def _tag_assets(assets, key, tag):
    for asset in assets:
        unreal.EditorAssetLibrary.set_metadata_tag(asset,tag,key)
    for asset in assets:
        if isinstance(asset,unreal.Texture2D):
            _save_texture(asset)
            continue
        if not unreal.EditorAssetLibrary.save_loaded_asset(asset):
            raise RuntimeError('failed to save asset: '+asset.get_path_name())


def _cached_mesh(resource):
    identity = resource.fingerprint,resource.block.id
    def load(path):
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            return None
        mesh = unreal.load_asset(path)
        return mesh if (isinstance(mesh,unreal.StaticMesh) and unreal.SystemLibrary.is_valid(mesh)
            and unreal.EditorAssetLibrary.get_metadata_tag(mesh,'WGSourceKey')==identity[0]
            and unreal.EditorAssetLibrary.get_metadata_tag(mesh,'WGBlockID')==identity[1]) else None
    path = _mesh_index.get(identity)
    if path:
        mesh = load(path)
        if mesh:
            return mesh
        _mesh_index.pop(identity,None)
    for path in sorted(unreal.EditorAssetLibrary.list_assets(_MODEL_ROOT,recursive=True,include_folder=False)):
        parts = str(path)[len(_MODEL_ROOT)+1:].split('/')
        match = re.fullmatch(r'.+_([0-9a-f]{8,64})',parts[0])
        if (not match or len(match[1])%4 or not resource.fingerprint.startswith(match[1])
                or any(p.startswith('refresh_') for p in parts[1:])):
            continue
        # The public importer chooses category folders and mesh names. Inspect
        # the registry class instead of assuming its current naming convention.
        if str(unreal.EditorAssetLibrary.find_asset_data(path).asset_class_path.asset_name) != 'StaticMesh':
            continue
        mesh = load(path)
        if mesh:
            _mesh_index[identity] = str(path)
            return mesh
    return None


def _model_folder(resource):
    cached = _cached_mesh(resource)
    if cached:
        leaf = cached.get_path_name()[len(_MODEL_ROOT)+1:].split('/')[0]
        return _MODEL_ROOT+'/'+leaf
    for leaf in short_names(resource.block.id,resource.fingerprint):
        folder = _MODEL_ROOT+'/'+leaf
        if not unreal.EditorAssetLibrary.does_directory_exist(folder):
            return folder
    raise FileExistsError('readable model directory is occupied')


def editor_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def level_path():
    return editor_world().get_path_name()


def prepare_class(backend):
    cls = mineprep.uclass(_CLASSES[backend])
    if cls is None:
        raise RuntimeError(f'{backend} Actor class missing: {_CLASSES[backend]}')
    _biome_properties(cls, backend)
    return cls


def _biome_properties(cls, backend):
    names = ('生物群系纹理',) if backend == 'ism' else ('生物群系纹理', '边界点A', '边界点B')
    try:
        default = unreal.get_default_object(cls)
        for name in names:
            default.get_editor_property(name)
    except Exception as exc:
        raise ValueError(f'{backend} output blueprint requires {", ".join(names)}') from exc


def validate_backend(data, backend, groups=None):
    if backend == 'ism' or not data.count:
        return
    layouts = ((len(g.type_ids), g.instance_count) for g in groups) if groups else ((len(data.names), data.count),)
    limit = (unreal.SystemLibrary.get_console_variable_int_value('fx.MaxNiagaraGPUParticlesSpawnPerFrame')
             if backend == 'niagara' else 0)
    for i, (types, count) in enumerate(layouts, 1):
        side = math.ceil(math.sqrt(count))
        if side > 16384 or types > 2**24:
            raise ValueError(f'group {i}: {count:,} instances exceed the texture dimension/type-ID encoding limits')
        if limit > 0 and side*side > limit:
            names = ', '.join(data.names[t] for t in groups[i-1].type_ids) if groups else ', '.join(data.names)
            raise ValueError(f'Niagara group {i} ({names}): {count:,} instances require {side*side:,} spawn slots; '
                             f'fx.MaxNiagaraGPUParticlesSpawnPerFrame={limit:,}; types are indivisible')


def model_directory():
    import mc_config
    return mc_config.paths.blocks


def prepare_mesh(resource, *, refresh=False):
    block = resource.block
    if block.material:
        cached = None if refresh else _cached_mesh(resource)
        if cached:
            if block.merge == 'xyz':
                validate_cube_mesh(cached, block.id)
            return cached
        from dataclasses import replace
        from .resources import resolve_resource
        base = resolve_resource(replace(block, material=()), model_directory())
        original = prepare_mesh(base, refresh=refresh)
        folder = _model_folder(resource)
        if refresh:
            folder += '/refresh_' + uuid.uuid4().hex
        mesh = unreal.EditorAssetLibrary.duplicate_asset(original.get_path_name(), folder+'/model')
        if not isinstance(mesh, unreal.StaticMesh):
            raise RuntimeError('failed to create material mesh variant')
        slots = original.get_editor_property('static_materials')
        if not slots:
            raise ValueError(f'block {block.id}: material override requires material slots')
        for index, slot in enumerate(slots):
            parent = slot.get_editor_property('material_interface')
            if parent is None:
                raise ValueError(f'block {block.id}: empty material slot {index}')
            mesh.set_material(index, _override_material(parent, dict(block.material), folder+'/mat'))
        if block.merge == 'xyz':
            validate_cube_mesh(mesh, block.id)
        unreal.EditorAssetLibrary.set_metadata_tag(mesh,'WGBlockID',block.id)
        _tag_assets((mesh,),resource.fingerprint,'WGSourceKey')
        if not refresh:
            _mesh_index[(resource.fingerprint,block.id)] = mesh.get_path_name()
        return mesh
    if block.source == 'mesh':
        mesh = unreal.load_asset(resource.path)
    else:
        tag,key = 'WGSourceKey',resource.fingerprint
        cached = None if refresh else _cached_mesh(resource)
        if cached:
            mesh = cached
        else:
            folder = _model_folder(resource)
            if refresh:
                folder = next((folder+'/'+leaf for leaf in short_names('refresh',uuid.uuid4().hex)
                               if not unreal.EditorAssetLibrary.does_directory_exist(folder+'/'+leaf)),None)
                if folder is None:
                    raise FileExistsError('model refresh directory is occupied')
            mesh = mineprep.import_block(resource.path,asset_name=block.id,destination_path=folder,reload=refresh)
            if not isinstance(mesh,unreal.StaticMesh):
                raise ValueError('model import did not return a StaticMesh')
            unreal.EditorAssetLibrary.set_metadata_tag(mesh,'WGBlockID',block.id)
            _tag_assets((mesh,),key,tag)
            if not refresh:
                _mesh_index[(key,block.id)] = mesh.get_path_name()
    if not isinstance(mesh, unreal.StaticMesh):
        raise ValueError(f'block {block.id} source {block.source}:{resource.path}: missing StaticMesh')
    if block.merge == 'xyz':
        validate_cube_mesh(mesh,block.id)
    return mesh


def validate_cube_mesh(mesh, name):
    """XYZ scales assume a 100cm cube about the fixed cell center."""
    bounds = mesh.get_bounding_box()
    for actual, expected in ((bounds.min,(-50.,-50.,-50.)),(bounds.max,(50.,50.,50.))):
        if any(not math.isclose(float(getattr(actual,axis)),value,abs_tol=.01)
               for axis,value in zip('xyz',expected)):
            raise ValueError(f'block {name}: xyz merge requires a 100cm cube with a cell-center origin')


def cached_textures(key, *, folder, index):
    return _load_assets(folder,key,'WGKey',tuple(f'structure_{kind}_{index}' for kind in ('BPT','BRT')))


def import_textures(files, key, *, folder, index, world_key):
    import mc_importer
    from pprint import pformat
    textures = []
    for kind in ('BPT','BRT'):
        task = mc_importer._make_import_task(files[kind],folder,f'structure_{kind}_{index}')
        texture = mc_importer._run_import_task(task)[0]
        mineprep.prep_texture(texture,unreal.TextureCompressionSettings.TC_HDR_F32)
        unreal.EditorAssetLibrary.set_metadata_tag(texture,'WGTextureSize',json.dumps([files['side']]*2))
        unreal.EditorAssetLibrary.set_metadata_tag(texture,'方块映射',pformat(files['mapping']))
        unreal.EditorAssetLibrary.set_metadata_tag(texture,'WGWorldKey',world_key)
        _tag_assets((texture,),key,'WGKey')
        textures.append(texture)
    return tuple(textures)


def cached_biome_texture(key, *, folder):
    _,texture = _shared_path(folder+'/biome_colors','structure_BCT',key,'WGBCTKey')
    return texture if isinstance(texture,unreal.Texture2D) and unreal.SystemLibrary.is_valid(texture) else None


def import_biome_texture(files, *, folder, world_key):
    import mc_importer
    key = files['key']
    path,_ = _shared_path(folder+'/biome_colors','structure_BCT',key,'WGBCTKey')
    destination,_,asset_name = path.rpartition('/')
    texture = mc_importer._run_import_task(mc_importer._make_import_task(files['path'],destination,asset_name))[0]
    texture.set_editor_properties(dict(srgb=False, compression_settings=unreal.TextureCompressionSettings.TC_HDR,
        filter=unreal.TextureFilter.TF_BILINEAR, address_x=unreal.TextureAddress.TA_CLAMP,
        address_y=unreal.TextureAddress.TA_CLAMP, mip_gen_settings=unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS,
        never_stream=True))
    unreal.EditorAssetLibrary.set_metadata_tag(texture,'WGTextureSize',json.dumps([files['width'],files['height']]))
    unreal.EditorAssetLibrary.set_metadata_tag(texture,'WGWorldKey',world_key)
    _tag_assets((texture,),key,'WGBCTKey')
    return texture


def valid_base(prepared):
    """Model references only; output partition and colour resources are independent."""
    return (all(unreal.SystemLibrary.is_valid(o)
                    and unreal.EditorAssetLibrary.does_asset_exist(o.get_path_name())
                    for o in prepared.meshes)
            and len(prepared.mesh_keys) == len(prepared.meshes)
            and all(identity is None or (
                    unreal.EditorAssetLibrary.get_metadata_tag(mesh,'WGSourceKey') == identity[0]
                    and unreal.EditorAssetLibrary.get_metadata_tag(mesh,'WGBlockID') == identity[1])
                    for mesh,identity in zip(prepared.meshes,prepared.mesh_keys))
            and _template_textures_valid(prepared.meshes))


def valid_group(group, *, folder=None, index=None):
    return (len(group.textures) == 2 and all(
        unreal.SystemLibrary.is_valid(t)
        and unreal.EditorAssetLibrary.does_asset_exist(t.get_path_name())
        and unreal.EditorAssetLibrary.get_metadata_tag(t, 'WGKey') == group.key for t in group.textures)
        and (folder is None or tuple(t.get_path_name().split('.',1)[0] for t in group.textures)
             == tuple(f'{folder}/structure_{kind}_{index}' for kind in ('BPT','BRT'))))


def valid_prepared(prepared):
    if not unreal.SystemLibrary.is_valid(prepared.actor_class) or not valid_base(prepared):
        return False
    try:
        _biome_properties(prepared.actor_class, prepared.backend)
    except ValueError:
        return False
    groups = prepared.type_groups
    if prepared.backend != 'ism' and prepared.data.count and not groups:
        return False
    if groups:
        if (prepared.textures != tuple(t for group in groups for t in group.textures)
                or any(len(group.textures) != 2 for group in groups)):
            return False
        tagged = ((texture, group.key) for group in groups for texture in group.textures)
    else:
        tagged = ((texture, prepared.key) for texture in prepared.textures)
    return (all(unreal.SystemLibrary.is_valid(t)
                and unreal.EditorAssetLibrary.does_asset_exist(t.get_path_name()) for t in prepared.all_textures)
            and all(unreal.EditorAssetLibrary.get_metadata_tag(t, 'WGKey') == key for t, key in tagged)
            and ((prepared.biome_texture is not None
                  and unreal.EditorAssetLibrary.get_metadata_tag(prepared.biome_texture,'WGBCTKey') == prepared.biome_key)
                 if prepared.biome_enabled and prepared.data.count else prepared.biome_texture is None))


_TEMPLATE_MATERIAL_POLICY = 'source-animation-2'


def template_resources(instances,models_dir,*,block_names=(),block_materials=None):
    from mc_mesh import BAKE_VERSION
    from mc_structure import structure_parts
    from .resources import capture_templates
    return capture_templates(instances,models_dir,structure_parts,BAKE_VERSION+':wg-'+_TEMPLATE_MATERIAL_POLICY,
                             block_names=block_names,block_materials=block_materials)


def _shared_path(root, label, key, tag):
    for name in short_names(label,key):
        path=root+'/'+name
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            return path,None
        asset=unreal.load_asset(path)
        if unreal.EditorAssetLibrary.get_metadata_tag(asset,tag)==key:
            return path,asset
    raise FileExistsError('shared asset identity is occupied: '+label)


def texture_ready(texture):
    """Reject empty Mips and the compiler's 32x32 stand-in."""
    if not isinstance(texture,unreal.Texture2D) or not unreal.SystemLibrary.is_valid(texture):return False
    size=(texture.blueprint_get_size_x(),texture.blueprint_get_size_y())
    expected=unreal.EditorAssetLibrary.get_metadata_tag(texture,'WGTextureSize')
    return (min(size)>0 and texture.blueprint_get_memory_size()>0
            and (not expected or size==tuple(json.loads(expected))))


def _save_texture(texture):
    # only_if_is_dirty=False runs PreSave. PreSave finishes an in-flight compile.
    # modify() must not be used for that wait: UTexture::Modify cancels the compile
    # and can leave the 32x32 stand-in after the texture has left the compiler queue.
    if not unreal.EditorAssetLibrary.save_loaded_asset(texture,only_if_is_dirty=False):
        raise RuntimeError('failed to finish texture: '+texture.get_path_name())


def native_texture_finish():
    return getattr(getattr(unreal,'mineprep',None),'finish_build_texture',None)


def finish_texture(texture, native):
    """Complete one unready resource; fallback is called only after a real frame."""
    if texture_ready(texture):return
    if native is not None:
        native(texture)
    else:
        texture.set_editor_property('compression_cache_id',unreal.GuidLibrary.new_guid())
    _save_texture(texture)


def _template_textures(meshes):
    textures={}
    for mesh in meshes:
        if not unreal.EditorAssetLibrary.get_metadata_tag(mesh,'WGBlockID').startswith('template_'):
            continue
        import mc_importer
        for slot in mesh.get_editor_property('static_materials'):
            material=slot.material_interface
            if material is None or not unreal.SystemLibrary.is_valid(material):
                raise ValueError('template material is missing: '+mesh.get_path_name())
            texture=unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(
                material,mc_importer.BASE_TEXTURE_PARAMETER_NAME)
            if (not isinstance(texture,unreal.Texture2D) or not unreal.SystemLibrary.is_valid(texture)
                    or not unreal.EditorAssetLibrary.does_asset_exist(texture.get_path_name())):
                raise ValueError('template texture is missing: '+mesh.get_path_name())
            textures[texture.get_path_name()]=texture
    return tuple(textures.values())


def _template_textures_valid(meshes):
    try:_template_textures(meshes)
    except ValueError:return False
    return True


def unready_textures(meshes, textures):
    """Pure readiness query over this preparation's resources, with no shared queue."""
    unique={t.get_path_name():t for t in _template_textures(meshes)}
    for texture in textures:
        if (not isinstance(texture,unreal.Texture2D) or not unreal.SystemLibrary.is_valid(texture)
                or not unreal.EditorAssetLibrary.does_asset_exist(texture.get_path_name())):
            raise ValueError('structure texture is missing')
        unique[texture.get_path_name()]=texture
    return tuple(t for t in unique.values() if not texture_ready(t))


def _shared_material(source, root, *, two_sided=True):
    import mc_importer
    from mc_prep import load_mcprep_data, colorize_material, _apply_emission_default
    from .resources import template_texture_key
    source=Path(source);key=template_texture_key(source)
    path,texture=_shared_path(root+'/tex',source.stem,key,'WGTextureKey')
    if texture is not None:
        size=json.dumps(mc_importer._image_size(source))
        if unreal.EditorAssetLibrary.get_metadata_tag(texture,'WGTextureSize')!=size:
            unreal.EditorAssetLibrary.set_metadata_tag(texture,'WGTextureSize',size)
            _save_texture(texture)
    if texture is None:
        # Reimport only an absent/broken resource, never once per template.
        task=mc_importer._make_import_task(source,root+'/tex',path.rsplit('/',1)[1])
        texture=mc_importer._run_import_task(task)[0]
        normal=source.stem.endswith('_n')
        texture.set_editor_properties(dict(filter=unreal.TextureFilter.TF_NEAREST,
            compression_settings=(unreal.TextureCompressionSettings.TC_NORMALMAP if normal
                                  else unreal.TextureCompressionSettings.TC_EDITOR_ICON),
            oodle_preserve_extremes=True,srgb=not normal,
            lod_group=(unreal.TextureGroup.TEXTUREGROUP_WORLD_NORMAL_MAP if normal
                       else unreal.TextureGroup.TEXTUREGROUP_WORLD)))
        unreal.EditorAssetLibrary.set_metadata_tag(texture,'WGTextureSize',json.dumps(mc_importer._image_size(source)))
        unreal.EditorAssetLibrary.set_metadata_tag(texture,'WGTextureKey',key)
        _save_texture(texture)
    parent=mc_importer._material_instance_path_for_texture(texture,two_sided=two_sided,texture_source=source)
    tint=load_mcprep_data()['blocks']['desaturated'].get(source.stem)
    material_key=hashlib.sha256(json.dumps((key,parent,tint,_TEMPLATE_MATERIAL_POLICY)).encode()).hexdigest()
    path,material=_shared_path(root+'/mat',source.stem,material_key,'WGMaterialKey')
    if material is None:
        material=unreal.EditorAssetLibrary.duplicate_asset(parent,path)
        if not isinstance(material,unreal.MaterialInstanceConstant):
            raise RuntimeError('failed to create shared template material: '+path)
        unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
            material,mc_importer.BASE_TEXTURE_PARAMETER_NAME,texture)
        # Hashed asset names no longer match the importer's tint lookup by name.
        if tint is not None:colorize_material(material,unreal.LinearColor(*tint,1.0))
        mc_importer._apply_texture_animation(material,source)
        _apply_emission_default(material,source)
        _tag_assets((material,),material_key,'WGMaterialKey')
    if unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(
            material,mc_importer.BASE_TEXTURE_PARAMETER_NAME)!=texture:
        raise ValueError('shared template material has a mismatched texture: '+path)
    return material


def _override_material(parent, values, root):
    """One immutable child per parent/style; source materials are never edited."""
    key = hashlib.sha256(json.dumps(('block-material-1',parent.get_path_name(),values),sort_keys=True).encode()).hexdigest()
    path, material = _shared_path(root,'material',key,'WGMaterialKey')
    if material is None:
        folder, name = path.rsplit('/',1)
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name,folder,unreal.MaterialInstanceConstant,unreal.MaterialInstanceConstantFactoryNew())
        if not isinstance(material,unreal.MaterialInstanceConstant):
            raise RuntimeError('failed to create material override: '+path)
        library = unreal.MaterialEditingLibrary
        library.set_material_instance_parent(material,parent)
        for name, value in values.items():
            parameter = {'emission':'发光亮度','lighting':'照明强度'}[name]
            library.set_material_instance_scalar_parameter_value(material,parameter,value)
        _tag_assets((material,),key,'WGMaterialKey')
    return material


def _template_geometry(resource):
    import mc_mesh
    from dataclasses import replace
    cells = {(x,y,z):dict(name=name,properties=dict(props))
             for x,y,z,name,props in resource.template.bake_cells}
    if not getattr(resource,'materials',()):
        return mc_mesh.resolve_geometry(cells,pivot=(0,0,0),cull='same',merge_faces=True)
    resolver = mc_mesh._SourceResolver()
    aliases = {}
    for record, values in zip(resource.template.bake_cells,resource.materials):
        x,y,z,name,props = record
        alias = name + '_wg_' + hashlib.sha256(json.dumps(values).encode()).hexdigest()[:16]
        aliases[alias] = name,values
        cells[x,y,z]['name'] = alias
    def resolve(name, props):
        original, values = aliases[name]
        prototype = resolver(original,props)
        if not values:
            return prototype
        suffix = '\0'+json.dumps(dict(values),sort_keys=True)
        return replace(prototype,faces=tuple(replace(face,texture=face.texture+suffix) for face in prototype.faces))
    geometry = mc_mesh.build_geometry(cells,resolve,pivot=(0,0,0),cull='same',merge_faces=True)
    geometry.recipe = hashlib.sha256((geometry.recipe+json.dumps(sorted(resolver.files.items()),separators=(',',':'))).encode()).hexdigest()
    return geometry


def _template_material(source, pool, *, two_sided=True):
    path, _, raw = source.partition('\0')
    material = _shared_material(path,pool,two_sided=two_sided)
    return _override_material(material,json.loads(raw),pool+'/mat/overrides') if raw else material


def prepare_template(resource, *, refresh=False, pool_revision=None):
    """Whole-model assets are immutable versions; never overwrite a running world's mesh."""
    import mc_mesh
    identity=(resource.fingerprint,'template_'+resource.template.id)
    root=_WORLD_ROOT+'/templates'
    pool=root if not refresh else root+'/refresh_'+(pool_revision or uuid.uuid4().hex[:12])
    label=resource.template.id
    if re.fullmatch(r'cell_[0-9a-f]{16}',label) and len(resource.template.bake_cells)==1:
        label=resource.template.bake_cells[0][3]
    path,mesh=_shared_path(pool,'SM_'+label,identity[0],'WGSourceKey')
    if mesh is None:
        geometry=_template_geometry(resource)
        materials=[_template_material(p,pool,two_sided=resource.template.two_sided) for p in geometry.textures]
        unreal.EditorAssetLibrary.make_directory(pool)
        mesh,outcome=unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(
            mc_mesh._dynamic_mesh(geometry),path,unreal.GeometryScriptCreateNewStaticMeshAssetOptions())
        if mesh is None or outcome!=unreal.GeometryScriptOutcomePins.SUCCESS:
            raise RuntimeError('failed to write template mesh: '+path)
        for slot,material in enumerate(materials):mesh.set_material(slot,material)
        unreal.EditorAssetLibrary.set_metadata_tag(mesh,mc_mesh.RECIPE_TAG,geometry.recipe)
        unreal.EditorAssetLibrary.set_metadata_tag(mesh,mc_mesh.STATS_TAG,json.dumps(geometry.stats,sort_keys=True))
        resource.checked()
        unreal.EditorAssetLibrary.set_metadata_tag(mesh,'WGSourceKey',identity[0])
        unreal.EditorAssetLibrary.set_metadata_tag(mesh,'WGBlockID',identity[1])
        if not unreal.EditorAssetLibrary.save_loaded_asset(mesh):raise RuntimeError('failed to save template identity')
    if (not isinstance(mesh,unreal.StaticMesh) or
            unreal.EditorAssetLibrary.get_metadata_tag(mesh,'WGSourceKey')!=identity[0] or
            unreal.EditorAssetLibrary.get_metadata_tag(mesh,'WGBlockID')!=identity[1]):
        raise ValueError('invalid or mismatched baked template asset: '+path)
    if not _template_textures_valid((mesh,)):
        # Repair missing references without rebuilding an otherwise healthy mesh.
        geometry=_template_geometry(resource)
        for p in geometry.textures:_template_material(p,pool,two_sided=resource.template.two_sided)
        if not _template_textures_valid((mesh,)):
            raise RuntimeError('template material/texture resources are invalid: '+path)
    return mesh


class PlacementError(RuntimeError):
    def __init__(self, message, residual):
        super().__init__(message)
        self.result = dict(residual_actor_paths=residual, warnings=['placement failed'])


def cleanup(actors, destroy=None):
    """Return exact remaining paths; never silently discard a failed deletion."""
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    destroy = destroy or subsystem.destroy_actor
    residual = []
    for actor in reversed(actors):
        if not unreal.SystemLibrary.is_valid(actor):
            continue
        path = actor.get_path_name()
        try:
            if not destroy(actor):
                residual.append(path)
        except Exception:
            residual.append(path)
    return residual


def place(prepared, location, groups, name):
    """One synchronous transaction. No imports, encoding or yields inside it."""
    started = perf_counter()
    data, backend = prepared.data, prepared.backend
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    origin = unreal.Vector(*(np.asarray(location, np.float64) + to_ue((data.region.x0, 0, data.region.z0))).tolist())
    actors, job_id = [], uuid.uuid4().hex[:8]
    biome_properties = {'生物群系纹理': prepared.biome_texture}
    if backend != 'ism':
        biome_properties.update({'边界点A': unreal.Vector(0,0,0),
                                 '边界点B': unreal.Vector(*to_ue((data.region.width,
                                     prepared.world.params['world.y_max']-prepared.world.params['world.y_min'],
                                     data.region.depth)).tolist())})
    if not data.count:
        return dict(actors=(), actor_paths=[], instance_count=0, seconds=0,
                    warnings=[], render_state='empty', job_id=job_id)
    folder = name
    with unreal.ScopedEditorTransaction('WorldGenerator: place ' + name) as transaction:
        try:
            def spawn(label, at=origin):
                actor = subsystem.spawn_actor_from_class(prepared.actor_class, at, unreal.Rotator())
                if actor is None:
                    raise RuntimeError('Actor creation failed')
                actors.append(actor)
                actor.modify()
                actor.set_folder_path(folder)
                mineprep.set_actor_label(actor, label)
                return actor

            actual = 0
            if backend == 'ism':
                y_min = prepared.world.params['world.y_min']
                for chunk_id, type_id, indices, (x, z) in groups:
                    local_origin = (x, y_min, z)
                    at = unreal.Vector(*(np.array((origin.x, origin.y, origin.z)) + to_ue(local_origin)).tolist())
                    actor = spawn(f'{name}_{chunk_id}_{data.names[type_id]}', at)
                    actor.set_editor_properties(biome_properties)
                    ism = actor.root_component
                    ism.modify()
                    ism.set_editor_property('StaticMesh', prepared.meshes[type_id])
                    ism.clear_instances()
                    for start in range(0, len(indices), 8192):
                        mineprep.add_packed_instances(ism, data.payload(indices[start:start+8192], origin=local_origin))
                    if ism.get_instance_count() != len(indices):
                        raise RuntimeError('ISM instance count does not match prepared data')
                    actual += ism.get_instance_count()
                if actual != data.count:
                    raise RuntimeError('total ISM instance count mismatch')
            else:
                for i, group in enumerate(prepared.type_groups, 1):
                    label = name if prepared.type_group_count == 1 else f'{name}_{i}'
                    actor = spawn(label)
                    meshes = [prepared.meshes[t] for t in group.type_ids]
                    if backend == 'pcg':
                        # Construction sees one complete matching palette and texture pair.
                        actor.set_editor_properties({**biome_properties,
                            'Blocks': [unreal.SystemLibrary.get_soft_object_path(m) for m in meshes],
                            'PosTex': group.textures[0], 'RotTex': group.textures[1]})
                    else:
                        actor.set_editor_properties({**biome_properties, '方块': meshes})
                        component = actor.root_component
                        component.modify()
                        component.set_variable_texture('方块位置纹理', group.textures[0])
                        component.set_variable_texture('方块旋转纹理', group.textures[1])
                if len(actors) > 1:
                    # Attach after construction, which may replace root components.
                    actors[0].root_component.modify()
                    keep = unreal.AttachmentRule.KEEP_WORLD
                    for actor in actors[1:]:
                        actor.root_component.modify()
                        if not actor.attach_to_actor(parent_actor=actors[0], socket_name='',
                                location_rule=keep, rotation_rule=keep, scale_rule=keep,
                                weld_simulated_bodies=False):
                            raise RuntimeError('Failed to attach output Actor to the first group')
        except Exception as exc:
            residual = cleanup(actors)
            if not residual:
                transaction.cancel()
            raise PlacementError(str(exc), residual) from exc
    return dict(actors=tuple(actors), actor_paths=[a.get_path_name() for a in actors],
                instance_count=data.count if backend == 'ism' else None,
                expected_instances=data.count, seconds=perf_counter()-started,
                warnings=[] if backend == 'ism' else ['Actor configured; GPU generation is asynchronous'],
                render_state='ready' if backend == 'ism' else 'pending',
                job_id=job_id, folder=folder, backend=backend)
