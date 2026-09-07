"""一键「烘焙动画」：MC_VAT + AnimSequence 列表 → 逐段烘焙 → 预乘 → 写入纹理集合。"""

import unreal

from .props import BakeAnimProps
from . import util as u


__all__ = [
    'BakeAnimProps',
    'bake_animation',
    'on_bake_props_changed',
    'sync_anim_seq_from_data_asset',
    'sync_copy_props_from_data_asset',
]


def _get_anim_texture_collection(mc_vat: unreal.AnimToTextureDataAsset):
    try:
        pv = mc_vat.get_editor_property('动画纹理集合')
    except Exception:
        return None
    if pv is None:
        return None
    try:
        return pv.get_editor_property('parameter_value')
    except Exception:
        return getattr(pv, 'parameter_value', None)


def _read_anims_from_mc_vat(mc_vat: unreal.AnimToTextureDataAsset) -> list:
    """读取 MC_VAT.AnimSequences 中的 AnimSequence，不足 3 个则补 None。"""
    out = []
    for info in (mc_vat.get_editor_property('anim_sequences') or []):
        anim = None
        try:
            anim = info.get_editor_property('anim_sequence')
        except Exception:
            pass
        out.append(anim if isinstance(anim, unreal.AnimSequence) else None)
    while len(out) < 3:
        out.append(None)
    return out


def _set_mc_vat_anim_at(
    mc_vat: unreal.AnimToTextureDataAsset,
    anim_index: int,
    anim: unreal.AnimSequence,
):
    """写入 MC_VAT.AnimSequences[index].AnimSequence（只填动画引用）。"""
    seqs = list(mc_vat.get_editor_property('anim_sequences') or [])
    while len(seqs) <= anim_index:
        seqs.append(unreal.AnimToTextureAnimSequenceInfo())
    info = unreal.AnimToTextureAnimSequenceInfo()
    info.set_editor_property('anim_sequence', anim)
    info.set_editor_property('enabled', True)
    seqs[anim_index] = info
    mc_vat.set_editor_property('anim_sequences', seqs)
    u.save(mc_vat)


def sync_anim_seq_from_data_asset(mod) -> None:
    """从左栏 DataAsset 读取 AnimSequences → BakeAnimProps.AnimSeq。"""
    mc_vat = u.resolve_mc_vat(mod.bake_props.DataAsset)
    if not mc_vat:
        mod.bake_props.AnimSeq = [None, None, None]
        return
    mod.bake_props.AnimSeq = _read_anims_from_mc_vat(mc_vat)


def sync_copy_props_from_data_asset(mod) -> None:
    """DataAsset 变更时刷新 TargetPath / NewName。"""
    if not getattr(mod, 'copy_props', None):
        return
    mc_vat = u.resolve_mc_vat(mod.bake_props.DataAsset)
    if not mc_vat:
        mod.copy_props.NewName = ''
        mod.copy_props.TargetPath = '/Game/mc/VAT'
        return
    name = u.strip_da_vat_prefix(mc_vat.get_name())
    mod.copy_props.NewName = name
    mod.copy_props.TargetPath = f'/Game/mc/VAT/{name}' if name else '/Game/mc/VAT'


def on_bake_props_changed(mod, property_name):
    if str(property_name) != 'DataAsset':
        return
    sync_anim_seq_from_data_asset(mod)
    sync_copy_props_from_data_asset(mod)


def _create_cache_textures(cache_dir: str, tex_base: str) -> dict[str, unreal.Texture2D]:
    factory = unreal.Texture2DFactoryNew()
    out = {}
    for key, suffix in (
        ('bpt', u.BONE_POSITION_SUFFIX),
        ('brt', u.BONE_ROTATION_SUFFIX),
        ('bwt', u.BONE_WEIGHTS_SUFFIX),
    ):
        name = f'{tex_base}_{suffix}'
        tex = u.create_asset(cache_dir, name, unreal.Texture2D, factory)
        if not isinstance(tex, unreal.Texture2D):
            raise RuntimeError(f'创建缓存纹理失败: {cache_dir}/{name}')
        out[key] = tex
    return out


_RATE_SCALE_EPS = 1e-3
_FPS_EPS = 0.5


def _anim_sample_rate(anim: unreal.AnimSequence, fallback: float = 30.0) -> float:
    """取动画序列源帧率（fps），供 AnimToTexture SampleRate 匹配采样。"""
    if not anim:
        return float(fallback)
    try:
        model = anim.get_editor_property('data_model_interface')
        if model is not None:
            fr = model.get_frame_rate()
            num = float(getattr(fr, 'numerator', 0) or 0)
            den = float(getattr(fr, 'denominator', 1) or 1)
            if num > 0 and den > 0:
                return num / den
    except Exception:
        pass
    try:
        fr = anim.get_sampling_frame_rate()
        num = float(getattr(fr, 'numerator', 0) or 0)
        den = float(getattr(fr, 'denominator', 1) or 1)
        if num > 0 and den > 0:
            return num / den
    except Exception:
        pass
    return float(fallback)


def _anim_rate_scale(anim: unreal.AnimSequence) -> float:
    try:
        return float(unreal.AnimationLibrary.get_rate_scale(anim) or 1.0)
    except Exception:
        try:
            return float(anim.get_editor_property('rate_scale') or 1.0)
        except Exception:
            return 1.0


def _delete_asset_path(path: str) -> None:
    soft = path.split('.')[0] if path and '.' in path else path
    if soft and unreal.EditorAssetLibrary.does_asset_exist(soft):
        unreal.EditorAssetLibrary.delete_asset(soft)


def _fps_compatible(a: float, b: float) -> bool:
    """AnimDataController：目标 fps 须为当前的整数倍或因子。"""
    ia, ib = max(1, int(round(a))), max(1, int(round(b)))
    return (ia <= ib and ib % ia == 0) or (ib <= ia and ia % ib == 0)


def _force_anim_frame_rate(anim: unreal.AnimSequence, fps: float) -> None:
    """把新建 AnimSequence 帧率设为目标（必要时经 LCM 中转，规避 24↔30）。"""
    if not anim or fps <= 0:
        return
    cur = _anim_sample_rate(anim)
    if abs(cur - fps) <= _FPS_EPS:
        return
    ctrl = getattr(anim, 'controller', None)
    if ctrl is None:
        return
    dst = max(1, int(round(fps)))
    src = max(1, int(round(cur)))
    # 先缩到 1 帧，避免中转帧率时出现 subframe 精度警告
    try:
        ctrl.set_number_of_frames(1, False)
    except Exception:
        pass
    fr_dst = unreal.FrameRate(dst, 1)
    if not _fps_compatible(src, dst):
        import math
        lcm = src // math.gcd(src, dst) * dst
        ctrl.set_frame_rate(unreal.FrameRate(lcm, 1), False)
    ctrl.set_frame_rate(fr_dst, False)
    u.save(anim)


def _prepare_bake_anim(
    anim: unreal.AnimSequence,
    skm: unreal.SkeletalMesh,
    cache_dir: str,
    *,
    override_fps: bool = False,
    target_fps: float = 60.0,
) -> unreal.AnimSequence:
    """必要时 Sequencer 重采样到 cache：消化 RateScale，并可选重载目标帧率。

    - RateScale≠1：按墙钟时长重采样（RateScale→1），慢放加密 / 快放抽稀
    - bOverrideFramerate：以 Framerate 为目标 fps；源已是该帧率则不因帧率单独缓存
    - 两者同时启用时，RateScale 重采样也使用 Framerate
    """
    rs = _anim_rate_scale(anim)
    if abs(rs) <= 1e-8:
        u.notify(f'RateScale={rs:g} 无效，按 1 处理')
        rs = 1.0

    src_fps = _anim_sample_rate(anim, fallback=30.0)
    bake_fps = float(target_fps) if override_fps else src_fps
    if bake_fps <= 0:
        bake_fps = src_fps

    need_rs = abs(rs - 1.0) > _RATE_SCALE_EPS
    need_fps = override_fps and abs(src_fps - bake_fps) > _FPS_EPS
    if not need_rs and not need_fps:
        return anim

    play_len = float(anim.get_play_length() or 0.0)
    wall_len = play_len / abs(rs)
    end_frame = max(1, int(round(wall_len * bake_fps)))
    fr = unreal.FrameRate(max(1, int(round(bake_fps))), 1)

    src_keys = int(unreal.AnimationLibrary.get_num_keys(anim) or 0)
    out_name = f'{u.display_name(anim)}_Cache'
    ls_name = f'LS_Cache_{u.display_name(anim)}'
    reasons = []
    if need_rs:
        reasons.append(f'RateScale={rs:g}')
    if need_fps:
        reasons.append(f'fps {src_fps:g}→{bake_fps:g}')
    u.notify(
        f'缓存重采样 ({", ".join(reasons)}): {src_keys} keys → ~{end_frame + 1} keys '
        f'({wall_len:.4g}s @ {bake_fps:g}fps) → cache/{out_name}'
    )

    tools = u.asset_tools()
    _delete_asset_path(f'{cache_dir}/{ls_name}')
    _delete_asset_path(f'{cache_dir}/{out_name}')

    ls = tools.create_asset(
        ls_name, cache_dir, unreal.LevelSequence, unreal.LevelSequenceFactoryNew()
    )
    if not ls:
        raise RuntimeError(f'创建临时 LevelSequence 失败: {cache_dir}/{ls_name}')

    unreal.MovieSceneSequenceExtensions.set_display_rate(ls, fr)
    unreal.MovieSceneSequenceExtensions.set_playback_start(ls, 0)
    unreal.MovieSceneSequenceExtensions.set_playback_end(ls, end_frame)

    world = u.world()
    actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = actor_sub.spawn_actor_from_class(
        unreal.SkeletalMeshActor, unreal.Vector(0.0, 0.0, -100000.0)
    )
    try:
        actor.skeletal_mesh_component.set_skeletal_mesh_asset(skm)
        binding = ls.add_possessable(actor)
        track = unreal.MovieSceneBindingExtensions.add_track(
            binding, unreal.MovieSceneSkeletalAnimationTrack
        )
        section = track.add_section()
        section.set_range(0, end_frame)
        params = section.get_editor_property('params')
        params.set_editor_property('animation', anim)
        section.set_editor_property('params', params)

        factory = unreal.AnimSequenceFactory()
        factory.set_editor_property('target_skeleton', skm.skeleton)
        out_anim = tools.create_asset(
            out_name, cache_dir, unreal.AnimSequence, factory
        )
        if not isinstance(out_anim, unreal.AnimSequence):
            raise RuntimeError(f'创建重采样动画失败: {cache_dir}/{out_name}')

        # 空序列默认多为 30fps；导出结束时 SetFrameRate 要求倍数/因子关系。
        # 先对齐目标帧率，再只靠 Sequencer DisplayRate 采样（不用 custom_frame_rate）。
        _force_anim_frame_rate(out_anim, bake_fps)

        opt = unreal.AnimSeqExportOption()
        opt.set_editor_property('export_transforms', True)
        opt.set_editor_property('export_morph_targets', False)
        opt.set_editor_property('export_attribute_curves', False)
        opt.set_editor_property('export_material_curves', False)
        opt.set_editor_property('record_in_world_space', False)
        opt.set_editor_property('evaluate_all_skeletal_mesh_components', False)
        opt.set_editor_property('use_custom_frame_rate', False)
        opt.set_editor_property('transact_recording', False)

        ok = unreal.SequencerTools.export_anim_sequence(
            world, ls, out_anim, opt, binding, False
        )
        if not ok:
            raise RuntimeError('SequencerTools.export_anim_sequence 失败')

        unreal.AnimationLibrary.set_rate_scale(out_anim, 1.0)
        u.save(out_anim)
        got = int(unreal.AnimationLibrary.get_num_keys(out_anim) or 0)
        u.notify(
            f'重采样完成: keys={got}, length={out_anim.get_play_length():.4g}s, '
            f'fps={bake_fps:g}, RateScale=1'
        )
        return out_anim
    finally:
        try:
            actor_sub.destroy_actor(actor)
        except Exception:
            pass
        _delete_asset_path(u.package_path(ls) if ls else f'{cache_dir}/{ls_name}')


def _configure_temp_da(
    da: unreal.AnimToTextureDataAsset,
    skm: unreal.SkeletalMesh,
    sm: unreal.StaticMesh,
    anim: unreal.AnimSequence,
    textures: dict[str, unreal.Texture2D],
    sample_rate: float,
):
    """临时 cache DA：始终只塞入当前这一段动画。"""
    seq_infos = da.get_editor_property('anim_sequences')
    seq_infos.clear()
    info = unreal.AnimToTextureAnimSequenceInfo()
    info.set_editor_property('anim_sequence', anim)
    info.set_editor_property('enabled', True)
    seq_infos.append(info)
    da.set_editor_property('anim_sequences', seq_infos)

    da.set_editor_property('skeletal_mesh', skm)
    da.set_editor_property('static_mesh', sm)
    da.set_editor_property('mode', unreal.AnimToTextureMode.BONE)
    da.set_editor_property('max_height', 4096)
    da.set_editor_property('max_width', 4096)
    da.set_editor_property('precision', unreal.AnimToTexturePrecision.SIXTEEN_BITS)
    da.set_editor_property('auto_play', True)
    da.set_editor_property(
        'num_bone_influences', unreal.AnimToTextureNumBoneInfluences.TWO
    )
    da.set_editor_property('sample_rate', float(sample_rate or 30.0))
    da.set_editor_property('bone_position_texture', textures['bpt'])
    da.set_editor_property('bone_rotation_texture', textures['brt'])
    da.set_editor_property('bone_weight_texture', textures['bwt'])
    u.save(da)


def _bake_temp(da: unreal.AnimToTextureDataAsset, sm: unreal.StaticMesh) -> bool:
    da.set_editor_property('static_mesh', sm)
    lod_index = int(da.get_editor_property('static_lod_index') or 0)
    unreal.AnimToTextureBPLibrary.set_light_map_index(sm, lod_index, 2, True)
    ok = unreal.AnimToTextureBPLibrary.animation_to_texture(da)
    if not ok:
        return False
    u.save(da)
    u.save(sm)
    return True


def _premul_to_directory(
    source_tex: unreal.Texture2D,
    out_dir: str,
    out_name: str,
    min_bbox: unreal.LinearColor,
    size_bbox: unreal.LinearColor,
    calc_material: unreal.MaterialInterface,
    scalars: dict[str, float] | None = None,
) -> unreal.Texture2D | None:
    if not source_tex or not calc_material:
        return None

    # AnimToTexture 写完后 GPU Resource 可能未就绪，立刻采样会得到黑图
    unreal.LandmassBlueprintFunctionLibrary.force_update_texture(source_tex)

    world = u.world()
    mid = unreal.MaterialLibrary.create_dynamic_material_instance(world, calc_material)
    mid.set_texture_parameter_value('Tex', source_tex)
    mid.set_vector_parameter_value('MinBBox', min_bbox)
    mid.set_vector_parameter_value('SizeBBox', size_bbox)
    for name, value in (scalars or {}).items():
        mid.set_scalar_parameter_value(str(name), float(value))

    w, h = u.texture_size(source_tex)
    rt = unreal.RenderingLibrary.create_render_target2d(
        world,
        w,
        h,
        unreal.TextureRenderTargetFormat.RTF_RGBA16F,
        unreal.LinearColor(0.0, 0.0, 0.0, 1.0),
        False,
        False,
    )
    rt.set_editor_property('lod_group', unreal.TextureGroup.TEXTUREGROUP_16_BIT_DATA)
    unreal.RenderingLibrary.draw_material_to_render_target(world, rt, mid)

    out_tex = u.load_or_none(out_dir, out_name)
    if not isinstance(out_tex, unreal.Texture2D):
        out_tex = u.asset_tools().duplicate_asset(out_name, out_dir, source_tex)
    if not isinstance(out_tex, unreal.Texture2D):
        u.notify(f'预乘纹理创建失败: {out_dir}/{out_name}')
        return None

    unreal.RenderingLibrary.convert_render_target_to_texture2d_editor_only(
        world, rt, out_tex
    )
    out_tex.set_editor_property(
        'mip_gen_settings', unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS
    )
    out_tex.set_editor_property(
        'lod_group', unreal.TextureGroup.TEXTUREGROUP_16_BIT_DATA
    )
    u.save(out_tex)
    return out_tex


def _write_texture_collection(
    tc: unreal.TextureCollection,
    anim_index: int,
    bpt: unreal.Texture2D | None = None,
    brt: unreal.Texture2D | None = None,
    bwt: unreal.Texture2D | None = None,
):
    """写入或清空动画组：每组 3 张 (BPT/BRT/BWT)；传 None 即清空该组。"""
    slots = list(tc.get_editor_property('textures') or [])
    need = (int(anim_index) + 1) * 3
    while len(slots) < need:
        slots.append(None)
    base = int(anim_index) * 3
    slots[base] = bpt
    slots[base + 1] = brt
    slots[base + 2] = bwt
    tc.set_editor_property('textures', slots)
    u.save(tc)


def _recompile_sm_mics(sm: unreal.StaticMesh):
    """烘焙后刷新静态网格上的材质实例（贴图集合参数才生效）。"""
    mats = []
    try:
        for entry in (sm.get_editor_property('static_materials') or []):
            mat = entry.get_editor_property('material_interface')
            if mat and mat not in mats:
                mats.append(mat)
    except Exception:
        pass
    if not mats:
        for i in range(8):
            try:
                mat = sm.get_material(i)
            except Exception:
                break
            if mat and mat not in mats:
                mats.append(mat)
    n = 0
    for mat in mats:
        if not isinstance(mat, unreal.MaterialInstanceConstant):
            continue
        unreal.MaterialEditingLibrary.update_material_instance(mat)
        u.save(mat)
        n += 1
    if n:
        u.notify(f'已重新编译静态网格上的 {n} 个材质实例')


def _bake_one_slot(
    mc_vat: unreal.AnimToTextureDataAsset,
    skm: unreal.SkeletalMesh,
    sm: unreal.StaticMesh,
    tc: unreal.TextureCollection,
    anim: unreal.AnimSequence,
    anim_index: int,
    *,
    override_fps: bool = False,
    target_fps: float = 60.0,
) -> bool:
    """对单个动画槽位：cache 单段烘焙 → 预乘 → 写入纹理集合 + MC_VAT。"""
    out_dir = u.package_dir(mc_vat)
    cache_dir = u.ensure_dir(f'{out_dir}/cache')
    anim_name = u.display_name(anim)
    tex_base = anim_name
    da_name = f'DA_VAT_cache_{anim_name}'

    u.notify(f'烘焙动画组 #{anim_index}: {anim_name} → cache/{da_name}')

    temp_da = u.create_asset(cache_dir, da_name, unreal.AnimToTextureDataAsset)
    if not temp_da:
        u.notify(f'创建临时 DataAsset 失败: {cache_dir}/{da_name}')
        return False

    textures = _create_cache_textures(cache_dir, tex_base)
    try:
        bake_anim = _prepare_bake_anim(
            anim, skm, cache_dir,
            override_fps=override_fps,
            target_fps=target_fps,
        )
    except Exception as e:
        u.notify(f'#{anim_index} 动画缓存重采样失败: {e}')
        return False
    fallback_rate = float(mc_vat.get_editor_property('sample_rate') or 30.0)
    if override_fps and float(target_fps) > 0:
        sample_rate = float(target_fps)
    else:
        sample_rate = _anim_sample_rate(bake_anim, fallback=fallback_rate)
    _configure_temp_da(temp_da, skm, sm, bake_anim, textures, sample_rate)

    if not _bake_temp(temp_da, sm):
        u.notify(f'#{anim_index} AnimationToTexture 失败，注意不同生物需要设置兼容骨架才能共享动画')
        return False

    bpt = temp_da.bp_get_bone_position_texture() or textures['bpt']
    brt = temp_da.bp_get_bone_rotation_texture() or textures['brt']
    bwt = temp_da.bp_get_bone_weight_texture() or textures['bwt']
    bone_min = u.vec3_to_linear(temp_da.get_editor_property('bone_min_b_box'))
    bone_size = u.vec3_to_linear(temp_da.get_editor_property('bone_size_b_box'))
    num_bones = int(temp_da.get_editor_property('num_bones') or 0)
    num_frames = int(temp_da.get_editor_property('num_frames') or 0)
    u.notify(
        f'#{anim_index} 烘焙完成: bones={num_bones}, frames={num_frames}, '
        f'fps={sample_rate:g}, influences=2'
    )
    mat_bpt = unreal.load_asset(u.MAT_BPT)
    mat_brt = unreal.load_asset(u.MAT_BRT)
    mat_bwt = unreal.load_asset(u.MAT_BWT)
    zero = unreal.LinearColor(0.0, 0.0, 0.0, 1.0)

    premul_bpt = _premul_to_directory(
        bpt, out_dir, f'{tex_base}_{u.BONE_POSITION_SUFFIX}{u.PREMUL_SUFFIX}',
        bone_min, bone_size, mat_bpt,
    )
    premul_brt = _premul_to_directory(
        brt, out_dir, f'{tex_base}_{u.BONE_ROTATION_SUFFIX}{u.PREMUL_SUFFIX}',
        zero, zero, mat_brt,
    )
    # BWT 材质：FPS / NumBones / NumFrames 为独立标量；FPS=烘焙 SampleRate
    # NumFrames 与旧编码一致：材质侧 NumFrames = W.a + 1 ⇒ 写入 frames - 1
    premul_bwt = _premul_to_directory(
        bwt, out_dir, f'{tex_base}_{u.BONE_WEIGHTS_SUFFIX}{u.PREMUL_SUFFIX}',
        zero, zero, mat_bwt,
        scalars={
            'FPS': sample_rate,
            'NumBones': float(num_bones),
            'NumFrames': float(max(num_frames - 1, 0)),
        },
    )

    if not all(isinstance(t, unreal.Texture2D) for t in (premul_bpt, premul_brt, premul_bwt)):
        u.notify(f'#{anim_index} 预乘纹理生成失败')
        return False

    _write_texture_collection(tc, anim_index, premul_bpt, premul_brt, premul_bwt)
    _set_mc_vat_anim_at(mc_vat, anim_index, anim)
    u.notify(
        f'已写入 {tc.get_name()} 槽位 {anim_index * 3}-{anim_index * 3 + 2}: '
        f'{premul_bpt.get_name()}, {premul_brt.get_name()}, {premul_bwt.get_name()}'
    )
    return True


def bake_animation(
    props: BakeAnimProps | None = None,
    *,
    mc_vat=None,
    anims=None,
    auto_clean_cache: bool = False,
) -> bool:
    """一键烘焙：按 AnimSeq 下标逐段 cache 烘焙 → 预乘 → 写入集合并回写 MC_VAT。"""
    override_fps = False
    target_fps = 60.0
    if props is not None:
        if mc_vat is None:
            mc_vat = props.DataAsset
        if anims is None:
            anims = props.AnimSeq
        override_fps = bool(getattr(props, 'bOverrideFramerate', False))
        try:
            target_fps = float(getattr(props, 'Framerate', 60) or 60)
        except Exception:
            target_fps = 60.0

    mc_vat = u.resolve_mc_vat(mc_vat)
    if not mc_vat:
        u.notify('请指定有效的动画数据集资产')
        return False

    anims = list(anims or [])
    bake_slots = [
        (i, a) for i, a in enumerate(anims) if isinstance(a, unreal.AnimSequence)
    ]
    empty_slots = [
        i for i, a in enumerate(anims) if not isinstance(a, unreal.AnimSequence)
    ]
    if not bake_slots and not empty_slots:
        u.notify('请至少指定一个动画序列')
        return False

    skm = mc_vat.get_editor_property('skeletal_mesh') or mc_vat.bp_get_skeletal_mesh()
    sm = mc_vat.get_editor_property('static_mesh') or mc_vat.bp_get_static_mesh()
    tc = _get_anim_texture_collection(mc_vat)
    if not isinstance(skm, unreal.SkeletalMesh):
        u.notify('MC_VAT 缺少骨骼网格体')
        return False
    if not isinstance(sm, unreal.StaticMesh):
        u.notify('MC_VAT 缺少静态网格体')
        return False
    if not isinstance(tc, unreal.TextureCollection):
        u.notify('MC_VAT 缺少「动画纹理集合」')
        return False

    for anim_index in empty_slots:
        _write_texture_collection(tc, anim_index)
        u.notify(
            f'#{anim_index} AnimSeq 为空，已清空纹理集合槽位 '
            f'{anim_index * 3}-{anim_index * 3 + 2}'
        )

    ok_count = 0
    reuse = {}
    for anim_index, anim in bake_slots:
        key = anim.get_path_name()
        src = reuse.get(key)
        if src is not None:
            slots = list(tc.get_editor_property('textures') or [])
            base = int(src) * 3
            bpt = slots[base] if len(slots) > base else None
            brt = slots[base + 1] if len(slots) > base + 1 else None
            bwt = slots[base + 2] if len(slots) > base + 2 else None
            _write_texture_collection(tc, anim_index, bpt, brt, bwt)
            _set_mc_vat_anim_at(mc_vat, anim_index, anim)
            u.notify(
                f'#{anim_index} 与 #{src} 为同一动画序列，复用纹理槽 '
                f'{anim_index * 3}-{anim_index * 3 + 2}'
            )
            ok_count += 1
            continue
        if _bake_one_slot(
            mc_vat, skm, sm, tc, anim, anim_index,
            override_fps=override_fps,
            target_fps=target_fps,
        ):
            reuse[key] = anim_index
            ok_count += 1

    _recompile_sm_mics(sm)

    if auto_clean_cache:
        cache_dir = f'{u.package_dir(mc_vat)}/cache'
        if u.delete_dir(cache_dir):
            u.notify(f'已删除缓存目录: {cache_dir}')

    if bake_slots:
        u.notify(f'烘焙结束: 成功 {ok_count}/{len(bake_slots)}')
        return ok_count > 0
    u.notify('未烘焙（AnimSeq 均为空），已清空对应纹理组')
    return True
