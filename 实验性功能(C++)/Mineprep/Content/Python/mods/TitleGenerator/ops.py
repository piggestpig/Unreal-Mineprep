"""标题生成、资源刷新与材质/网格资产构建操作。"""
import json
import math
import re
from time import perf_counter
import uuid

from . import catalog as sources
from . import geometry, output, texture

DEFAULTS = dict(font='minecraft-ten', layout='top', source='premade', texture='flat', overlay='none',
                file='', gradient_top='#FFCF76', gradient_bottom='#DA371E', tint='#FFFFFF',
                overlay_tint='#FFFFFF', overlay_opacity=1., overlay_blend='overlay',
                edge_brightness=35., border_color='', height_cm=100., thickness=1.,
                character_spacing=0., row_spacing=0., row=None, terminators=False,
                disable_shifting=False, lighting='unlit', output_mode='actors', name='', location=(0., 0., 0.))
ROOT_TAG = 'MineprepTitleGenerator='
_active = set()
_parents = set()
_refreshing = False


def catalog(font='minecraft-ten'):
    """读取本地已缓存的字体、贴图与叠加层选项；未下载素材时返回空字典。"""
    fonts = sources.entries()
    selected = font if font in fonts else next(iter(fonts), '')
    metadata = sources.font(selected) if selected else {}
    return dict(font=selected, fonts={key: v['name'] for key, v in fonts.items()},
                textures=sources.choices(metadata, 'textures'), overlays=sources.choices(metadata, 'overlays'))


def _launch(operation, on_done):
    import mineprep
    holder = []

    def tracked():
        try:
            yield  # 首帧先返回句柄，下一帧再开始执行任务
            result = yield from operation()
            return result
        finally:
            _active.discard(holder[0])

    runner = mineprep.asynctask(callback=on_done)(tracked)()
    holder.append(runner)
    _active.add(runner)
    return runner


def refresh_catalog(*, font='minecraft-ten', refresh=True, progress=None, on_done=None):
    """在线下载并缓存全部字体资源包；refresh=False 时仅读取本地缓存。"""
    import mineprep
    from threading import Event
    cancel = Event()

    def operation():
        global _refreshing
        if not refresh:
            return catalog(font)
        if _refreshing:
            raise ValueError('已有资源刷新任务，请等待完成。')
        _refreshing = True
        try:
            summary = yield from mineprep.asyncthread(sources.refresh_all)(progress=progress, cancel=cancel)
            return dict(catalog(font), resources=summary)
        finally:
            cancel.set()
            _refreshing = False

    return _launch(operation, on_done)


def find_root(actor):
    """从选中的标题根物体或其子字形 Actor 向上查找标题根物体。"""
    while actor is not None:
        if any(str(t).startswith(ROOT_TAG) for t in actor.tags):
            return actor
        actor = actor.get_attach_parent_actor()
    raise ValueError('请选中本模组生成的标题空物体或其中一个字。')


def _state(root):
    return json.loads(next(str(t)[len(ROOT_TAG):] for t in root.tags if str(t).startswith(ROOT_TAG)))


def _prepare(text, options):
    started = perf_counter()
    font, base, overlay = sources.resolve(options['font'], options)
    load_seconds = perf_counter()-started
    started = perf_counter()
    glyphs, row_span = geometry.layout_lines(text, font, options)
    geometry_seconds = perf_counter()-started
    started = perf_counter()
    plan = output.prepare(glyphs, options['output_mode'])
    plan['row_span'] = row_span
    token = uuid.uuid4().hex
    plan['textures'] = output.write_textures(plan, sources.cache_dir()/'instances'/token) if plan['groups'] else []
    output_seconds = perf_counter()-started
    started = perf_counter()
    image = texture.compose(texture.read(base), font, options, texture.read(overlay) if overlay else None)
    path = sources.cache_dir() / 'atlases' / (token+'.png')
    texture.write(path, image)
    return plan, path, dict(load_seconds=load_seconds, layout_seconds=geometry_seconds,
                           output_seconds=output_seconds, atlas_seconds=perf_counter()-started)


_save = output.save


def _material(lit):
    import unreal as ue
    name = 'M_TitleLit' if lit else 'M_TitleUnlit'
    folder = '/Game/mc/titles/_Materials'
    path = folder+'/'+name
    if ue.EditorAssetLibrary.does_asset_exist(path):
        material = ue.load_asset(path)
        if not isinstance(material, ue.Material):
            raise TypeError(f'标题母材质路径被其他类型占用：{path}')
        return material
    material = ue.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, ue.Material, ue.MaterialFactoryNew())
    if material is None:
        raise RuntimeError(f'无法创建母材质：{path}')
    material.set_editor_property('blend_mode', ue.BlendMode.BLEND_MASKED)
    material.set_editor_property('two_sided', False)
    material.set_editor_property('shading_model', ue.MaterialShadingModel.MSM_DEFAULT_LIT if lit else ue.MaterialShadingModel.MSM_UNLIT)
    edit = ue.MaterialEditingLibrary
    atlas = edit.create_material_expression(material, ue.MaterialExpressionTextureSampleParameter2D, -350, 0)
    atlas.set_editor_property('parameter_name', 'Atlas')
    atlas.set_editor_property('texture', ue.load_asset('/Engine/EngineResources/WhiteSquareTexture'))
    target = ue.MaterialProperty.MP_BASE_COLOR if lit else ue.MaterialProperty.MP_EMISSIVE_COLOR
    if not edit.connect_material_property(atlas, 'RGB', target) or not edit.connect_material_property(atlas, 'A', ue.MaterialProperty.MP_OPACITY_MASK):
        raise RuntimeError('无法连接标题材质图。')
    if lit:
        for prop, value in ((ue.MaterialProperty.MP_ROUGHNESS, 1.), (ue.MaterialProperty.MP_SPECULAR, 0.)):
            node = edit.create_material_expression(material, ue.MaterialExpressionConstant, -350, 200)
            node.set_editor_property('r', value)
            edit.connect_material_property(node, '', prop)
    edit.recompile_material(material)
    return _save(material)


def _materials(atlas_path, folder, lit, mode):
    import unreal as ue
    task = ue.AssetImportTask()
    task.filename, task.destination_path, task.destination_name = str(atlas_path), folder, 'T_Atlas'
    task.automated, task.save = True, True
    ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    objects = task.get_objects()
    if not objects or not isinstance(objects[0], ue.Texture2D):
        raise RuntimeError(f'图集导入失败：{atlas_path}')
    atlas = objects[0]
    atlas.set_editor_property('srgb', True)
    atlas.set_editor_property('filter', ue.TextureFilter.TF_NEAREST)
    atlas.set_editor_property('mip_gen_settings', ue.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    atlas.set_editor_property('compression_settings', ue.TextureCompressionSettings.TC_EDITOR_ICON)
    _save(atlas)
    result = []
    for is_lit in ((True, False) if lit else (False,)):
        name = 'MI_Lit' if is_lit else 'MI_Unlit'
        instance = ue.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, ue.MaterialInstanceConstant, ue.MaterialInstanceConstantFactoryNew())
        if instance is None:
            raise RuntimeError(f'无法创建材质实例：{folder}/{name}')
        material = _material(is_lit)
        usage = ('used_with_instanced_static_meshes', ue.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES) if mode in ('ism', 'pcg') else (
            ('used_with_niagara_mesh_particles', ue.MaterialUsage.MATUSAGE_NIAGARA_MESH_PARTICLES) if mode == 'niagara' else None)
        if usage and not material.get_editor_property(usage[0]):
            ue.MaterialEditingLibrary.set_base_material_usage(material, usage[1])
            ue.MaterialEditingLibrary.recompile_material(material)
            _save(material)
        ue.MaterialEditingLibrary.set_material_instance_parent(instance, material)
        # UE 5.8 的 setter 可能在设置成功后仍返回 False，因此通过回读参数确认
        ue.MaterialEditingLibrary.set_material_instance_texture_parameter_value(instance, 'Atlas', atlas)
        if ue.MaterialEditingLibrary.get_material_instance_texture_parameter_value(instance, 'Atlas') != atlas:
            raise RuntimeError('无法绑定标题图集。')
        ue.MaterialEditingLibrary.update_material_instance(instance)
        result.append(_save(instance))
    return (result if lit else [result[0], result[0]]), atlas


def generate(text, *, parent=None, options=None, on_done=None):
    """生成或向已有标题追加文字；parent 可为标题根物体或旗下任意字形 Actor。"""
    settings = {**DEFAULTS, **(options or {})}
    output.validate_mode(settings['output_mode'])
    unknown = set(settings)-set(DEFAULTS)
    if unknown:
        raise ValueError('未知标题选项：'+', '.join(sorted(unknown)))
    if settings['layout'] not in ('top', 'bottom', 'small') or settings['source'] not in ('premade', 'gradient', 'file'):
        raise ValueError('请选择有效的布局与贴图来源。')
    if settings['lighting'] not in ('unlit', 'lit'):
        raise ValueError('lighting 使用 unlit 或 lit。')
    lines = geometry.text_lines(text)
    actor_label = settings['name'].strip() or lines[0][1].strip()[:16]
    if not math.isfinite(settings['height_cm']) or settings['height_cm'] <= 0 or not math.isfinite(settings['thickness']) or settings['thickness'] <= 0:
        raise ValueError('字号和厚度必须为正数。')
    import mineprep
    import unreal as ue
    cls = output.actor_class(settings['output_mode'])
    root = find_root(parent) if parent is not None else None
    state = _state(root) if root is not None else {'rows': {}, 'path': ''}
    parent_key = root.get_path_name() if root is not None else None
    if parent_key is not None and parent_key in _parents:
        raise ValueError('此标题已有生成任务，请等待完成后再追加。')
    kind = settings['layout']
    auto_row = settings['row'] is None
    row = state['rows'].get(kind, 0) if auto_row else settings['row']
    if type(row) is not int or row < 0:
        raise ValueError('行号必须为非负整数。')
    settings['row'] = row

    def operation():
        if parent_key is not None and parent_key in _parents:
            raise ValueError('此标题已有生成任务，请等待完成后再追加。')
        created, assets, folder = [], [], None
        actors = ue.get_editor_subsystem(ue.EditorActorSubsystem)
        if parent_key is not None:
            _parents.add(parent_key)
        try:
            if root is not None:
                if root not in actors.get_all_level_actors():
                    raise ValueError('追加目标已被删除。')
                state.update(_state(root))
            row = state['rows'].get(kind, 0) if auto_row else settings['row']
            settings['row'] = row
            plan, atlas_file, timings = yield from mineprep.asyncthread(_prepare)(text, settings)
            output.validate_gpu(plan)
            if root is not None and root not in actors.get_all_level_actors():
                raise ValueError('追加目标已被删除。')
            tools = ue.AssetToolsHelpers.get_asset_tools()
            label = re.sub(r'[^a-zA-Z0-9_]', '_', actor_label).strip('_') or 'Title'
            output_path = state['path'] or tools.create_unique_asset_name('/Game/mc/titles/'+label, '')[0]
            if not state['path']:
                # 目录可能已存在但内部尚无同名资产，需额外检查目录名冲突
                base, suffix = output_path, 2
                while ue.EditorAssetLibrary.does_directory_exist(output_path):
                    output_path, suffix = base+'_'+str(suffix), suffix+1
            folder = tools.create_unique_asset_name(output_path+'/Line', '')[0]
            base, suffix = folder, 2
            while ue.EditorAssetLibrary.does_directory_exist(folder):
                folder, suffix = base+'_'+str(suffix), suffix+1
            ue.EditorAssetLibrary.make_directory(folder)
            started = perf_counter()
            materials, atlas = _materials(atlas_file, folder, settings['lighting'] == 'lit', settings['output_mode'])
            assets.extend([atlas.get_path_name(), *(m.get_path_name() for m in set(materials))])
            yield
            target = root
            if target is None:
                target = actors.spawn_actor_from_class(mineprep.uclass('/Game/Mineprep/MC_Blueprint/Core/空物体'), settings['location'])
                if target is None:
                    raise RuntimeError('无法创建标题空物体。')
                created.append(target)
                mineprep.set_actor_label(target, actor_label)
                target.set_folder_path(output_path.removeprefix('/Game/mc/titles/'))
                target.root_component.set_mobility(ue.ComponentMobility.MOVABLE)
            meshes = []
            for i, glyph in enumerate(plan['models'], 1):
                asset = output.mesh(glyph, folder+f'/SM_{i:03}', materials)
                meshes.append(asset)
                assets.append(asset.get_path_name())
                yield
            textures = output.import_textures(plan['textures'], folder)
            assets.extend(t.get_path_name() for pair in textures for t in pair)
            if target not in actors.get_all_level_actors():
                raise ValueError('标题根物体已被删除。')
            result = output.place(plan, meshes, textures, target, actor_label, cls, created)
            state['path'] = output_path
            state['rows'][kind] = max(state['rows'].get(kind, 0), row+plan['row_span'])
            target.tags = [t for t in target.tags if not str(t).startswith(ROOT_TAG)] + [ROOT_TAG+json.dumps(state)]
            timings.update(import_seconds=perf_counter()-started, characters=plan['character_count'],
                           unique_meshes=len(meshes), output_actors=len(result['actors']))
            actors.set_selected_level_actors([target])
            return dict(result, root=target, asset_path=output_path, line_path=folder, assets=assets, timings=timings)
        except BaseException as exc:
            live_actors = actors.get_all_level_actors()
            for actor in reversed(created):
                if actor in live_actors:
                    actors.destroy_actor(actor)
            if folder is not None and isinstance(exc, Exception):
                raise RuntimeError(f'{exc}\n本次资产目录：{folder}（已写入资产保留）') from exc
            raise
        finally:
            if parent_key is not None:
                _parents.discard(parent_key)

    return _launch(operation, on_done)


def cancel_all():
    for runner in tuple(_active):
        runner.destroy()
    _active.clear()
