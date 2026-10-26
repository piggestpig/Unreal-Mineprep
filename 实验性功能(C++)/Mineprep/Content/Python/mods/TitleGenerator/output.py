"""标题输出数据组装与 UE 静态网格/实例放置适配器。"""
import math

import numpy as np

MODES = ('merged', 'actors', 'ism', 'pcg', 'niagara')
CLASSES = {
    'ism': '/Game/Mineprep/MC_Blueprint/Core/实例化方块',
    'pcg': '/Game/Mineprep/MC_Blueprint/PCG/PCG实例化方块',
    'niagara': '/Game/Mineprep/MC_Blueprint/Niagara/动态地形粒子/动态结构粒子',
}


def validate_mode(mode):
    if mode not in MODES:
        raise ValueError('output_mode 使用 '+', '.join(MODES)+'。')


def is_letter(glyph):
    return glyph['char'] not in ('', '\u200b', ' ')


def prepare(glyphs, mode):
    """按所选输出模式整理字形模型与实例位置数据（五种模式保持相同的厘米坐标）。"""
    validate_mode(mode)
    character_count = sum(is_letter(g) for g in glyphs)
    lines = dict.fromkeys(g.get('line', 0) for g in glyphs)
    points = np.array([np.asarray(q)+g['pivot'] for g in glyphs for q, _, _ in g['quads']]).reshape(-1, 3)
    lo, hi = points.min(axis=0), points.max(axis=0)
    if mode == 'merged':
        merged = []
        for line in lines:
            items = [g for g in glyphs if g.get('line', 0) == line]
            points = np.array([np.asarray(q)+g['pivot'] for g in items for q, _, _ in g['quads']]).reshape(-1, 3)
            low, high = points.min(axis=0), points.max(axis=0)
            pivot = ((low[0]+high[0])/2, (low[1]+high[1])/2, low[2])
            quads = [([(np.asarray(p)+g['pivot']-pivot).tolist() for p in q], uv, slot)
                     for g in items for q, uv, slot in g['quads']]
            merged.append(dict(char='', pivot=pivot, quads=quads, line=line, row=items[0].get('row', 0)))
        glyphs = merged
    models, ids, lookup = [], [], {}
    for i, glyph in enumerate(glyphs):
        key = glyph['char'] or ('border', i)
        if key not in lookup:
            lookup[key] = len(models)
            models.append(glyph)
        ids.append(lookup[key])
    ids = np.asarray(ids)
    pivots = np.asarray([g['pivot'] for g in glyphs], np.float32)
    payloads = {}
    for i in range(len(models)):
        pos = pivots[ids == i]
        payloads[str(i)] = dict(pos=pos, rot=np.zeros(len(pos), np.float32), scale=np.ones((len(pos), 3), np.float32))
    groups = ()
    if mode in ('pcg', 'niagara'):
        names = tuple(payloads)
        counts = [len(p['pos']) for p in payloads.values()]
        count = (len(names)+255)//256
        if mode == 'pcg':
            groups = tuple(tuple(int(v) for v in ids) for ids in np.array_split(np.arange(len(names)), count))
        else:
            from mc_math import partition_types
            groups = tuple(ids for ids, _ in partition_types(names, counts, max_types=256))
    return dict(output_mode=mode, glyphs=glyphs, models=models, ids=ids.tolist(), payloads=payloads,
                groups=groups, character_count=character_count, line_count=len(lines), bounds=(lo.tolist(), hi.tolist()))


def write_textures(plan, directory):
    """后台线程：将 GPU 分组实例数据编码写成 BPT/BRT EXR 贴图。"""
    from mc_structure_tex import write_structure_textures
    return [write_structure_textures({str(i): plan['payloads'][str(i)] for i in group}, directory,
                                    name=f'Instances_{n}') for n, group in enumerate(plan['groups'], 1)]


def actor_class(mode):
    import mineprep
    import unreal as ue
    validate_mode(mode)
    cls = mineprep.uclass(CLASSES[mode]) if mode in CLASSES else ue.StaticMeshActor
    if cls is None:
        raise RuntimeError(f'{mode} 输出蓝图不可用：{CLASSES[mode]}')
    return cls


def validate_gpu(plan):
    import mineprep
    import unreal as ue
    if plan['output_mode'] not in ('pcg', 'niagara'):
        return
    if len(plan['groups']) > 1:
        mineprep.warn(f"{plan['output_mode']}: {len(plan['models'])} 种模型，已自动分为 {len(plan['groups'])} 组（每组最多 256 种）。")
    limit = ue.SystemLibrary.get_console_variable_int_value('fx.MaxNiagaraGPUParticlesSpawnPerFrame') if plan['output_mode'] == 'niagara' else 0
    for group in plan['groups']:
        count = sum(len(plan['payloads'][str(i)]['pos']) for i in group)
        side = math.isqrt(count-1)+1
        if side > 16384 or limit > 0 and side*side > limit:
            raise ValueError(f'GPU 输出需要 {side}×{side} 个槽位，超过当前纹理／粒子容量。')


def save(asset):
    import unreal as ue
    if not ue.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError(f'保存失败：{asset.get_path_name()}')
    return asset


def mesh(glyph, path, materials):
    import unreal as ue
    dynamic = ue.DynamicMesh()
    ue.GeometryScript_Materials.enable_material_i_ds(dynamic)
    for slot in (0, 1):
        vertices, triangles, normals, uv0 = [], [], [], []
        for points, uvs, material in glyph['quads']:
            if material != slot:
                continue
            u = [points[1][i]-points[0][i] for i in range(3)]
            v = [points[2][i]-points[0][i] for i in range(3)]
            cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
            length = math.sqrt(sum(n*n for n in cross))
            if length < 1e-9:
                continue
            base = len(vertices)
            vertices.extend(ue.Vector(*p) for p in points)
            normals.extend([ue.Vector(*(-n/length for n in cross))]*4)
            uv0.extend(ue.Vector2D(*uv) for uv in uvs)
            triangles.extend((ue.IntVector(base, base+1, base+2), ue.IntVector(base, base+2, base+3)))
        if vertices:
            ue.GeometryScript_MeshEdits.append_buffers_to_mesh(dynamic, ue.GeometryScriptSimpleMeshBuffers(
                vertices=vertices, triangles=triangles, normals=normals, uv0=uv0), material_id=slot)
    asset, outcome = ue.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(dynamic, path,
        ue.GeometryScriptCreateNewStaticMeshAssetOptions(enable_recompute_tangents=True, enable_collision=False))
    if asset is None or outcome != ue.GeometryScriptOutcomePins.SUCCESS:
        raise RuntimeError(f'网格创建失败：{path} ({outcome})')
    for slot, material in enumerate(materials):
        asset.set_material(slot, material)
    subsystem = ue.get_editor_subsystem(ue.StaticMeshEditorSubsystem)
    # 启用全精度 UV，避免 1 像素宽的侧面采样漂移到相邻透明像素
    build = subsystem.get_lod_build_settings(asset, 0)
    build.use_full_precision_u_vs = True
    subsystem.set_lod_build_settings(asset, 0, build)
    for section in range(asset.get_num_sections(0)):
        material_index = subsystem.get_lod_material_slot(asset, 0, section)
        subsystem.enable_section_cast_shadow(asset, material_index == 0 and materials[0] != materials[1], 0, section)
        subsystem.enable_section_affect_distance_field_lighting(asset, False, 0, section)
    return save(asset)


def import_textures(files, folder):
    from mc_structure import import_structure_textures
    result = []
    for item in files:
        pair = import_structure_textures(item, destination=folder)[:2]
        for texture in pair:
            save(texture)
            if (texture.blueprint_get_size_x(), texture.blueprint_get_size_y()) != (item['side'], item['side']):
                raise RuntimeError('GPU 结构纹理尺寸与编码结果不一致。')
        result.append(pair)
    return result


def place(plan, meshes, textures, parent, label, cls, created):
    """在单个撤销事务中生成并挂载标题输出 Actor。"""
    import mineprep
    import unreal as ue
    mode = plan['output_mode']
    subsystem = ue.get_editor_subsystem(ue.EditorActorSubsystem)
    actors, letters, decorations = [], [], []

    def spawn():
        actor = subsystem.spawn_actor_from_class(cls, parent.get_actor_location(), parent.get_actor_rotation())
        if actor is None:
            raise RuntimeError('无法创建标题输出 Actor。')
        created.append(actor)
        actors.append(actor)
        actor.set_actor_scale3d(parent.get_actor_scale3d())
        mineprep.set_actor_label(actor, label)
        actor.set_folder_path(parent.get_folder_path())
        return actor

    def attach(actor, pivot=(0, 0, 0)):
        # 蓝图构造脚本可能替换根组件，因此先完成属性配置再挂载到父 Actor
        for component in actor.get_components_by_class(ue.SceneComponent):
            component.set_mobility(ue.ComponentMobility.MOVABLE)
        keep = ue.AttachmentRule.KEEP_WORLD
        if not actor.attach_to_actor(parent, '', keep, keep, keep, False):
            raise RuntimeError('无法附加输出到标题根物体。')
        actor.set_actor_relative_transform(ue.Transform(location=ue.Vector(*pivot)), False, True)

    with ue.ScopedEditorTransaction('Generate Minecraft title'):
        if mode in ('actors', 'merged'):
            for glyph, model_id in zip(plan['glyphs'], plan['ids']):
                letter = is_letter(glyph)
                actor = spawn()
                actor.static_mesh_component.set_static_mesh(meshes[model_id])
                attach(actor, glyph['pivot'])
                if mode == 'actors':
                    (letters if letter else decorations).append(actor)
        elif mode == 'ism':
            for i, asset in enumerate(meshes):
                actor = spawn()
                component = actor.root_component
                component.set_static_mesh(asset)
                component.clear_instances()
                mineprep.add_packed_instances(component, plan['payloads'][str(i)])
                if component.get_instance_count() != len(plan['payloads'][str(i)]['pos']):
                    raise RuntimeError('标题实例数量与排版结果不一致。')
                attach(actor)
        else:
            for ids, pair in zip(plan['groups'], textures):
                actor = spawn()
                palette = [meshes[index] for index in ids]
                if mode == 'pcg':
                    actor.set_editor_properties(dict(Blocks=[ue.SystemLibrary.get_soft_object_path(m) for m in palette],
                                                     PosTex=pair[0], RotTex=pair[1]))
                else:
                    actor.set_editor_property('方块', palette)
                    actor.root_component.set_variable_texture('方块位置纹理', pair[0])
                    actor.root_component.set_variable_texture('方块旋转纹理', pair[1])
                    lo, hi = plan['bounds']
                    bounds = ue.Box(min=ue.Vector(*lo), max=ue.Vector(*hi))
                    bounds.is_valid = True
                    actor.root_component.set_system_fixed_bounds(bounds)
                attach(actor)
    return dict(actors=actors, characters=letters, decorations=decorations,
                output_mode=mode, character_count=plan['character_count'], line_count=plan['line_count'],
                render_state='pending' if mode in ('pcg', 'niagara') else 'ready')
