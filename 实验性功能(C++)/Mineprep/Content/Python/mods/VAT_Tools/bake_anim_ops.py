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
        'num_bone_influences', unreal.AnimToTextureNumBoneInfluences.FOUR
    )
    da.set_editor_property('sample_rate', float(sample_rate or 60.0))
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


def _bake_one_slot(
    mc_vat: unreal.AnimToTextureDataAsset,
    skm: unreal.SkeletalMesh,
    sm: unreal.StaticMesh,
    tc: unreal.TextureCollection,
    anim: unreal.AnimSequence,
    anim_index: int,
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
    sample_rate = float(mc_vat.get_editor_property('sample_rate') or 60.0)
    _configure_temp_da(temp_da, skm, sm, anim, textures, sample_rate)

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
    u.notify(f'#{anim_index} 烘焙完成: bones={num_bones}, frames={num_frames}')

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
    # NumFrames = W.a + 1  ⇒  W.a = frames - 1
    bwt_size = u.int_xy_to_linear(max(num_frames - 1, 0))
    premul_bwt = _premul_to_directory(
        bwt, out_dir, f'{tex_base}_{u.BONE_WEIGHTS_SUFFIX}{u.PREMUL_SUFFIX}',
        u.int_xy_to_linear(num_bones), bwt_size, mat_bwt,
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
    if props is not None:
        if mc_vat is None:
            mc_vat = props.DataAsset
        if anims is None:
            anims = props.AnimSeq

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
    for anim_index, anim in bake_slots:
        if _bake_one_slot(mc_vat, skm, sm, tc, anim, anim_index):
            ok_count += 1

    if auto_clean_cache:
        cache_dir = f'{u.package_dir(mc_vat)}/cache'
        if u.delete_dir(cache_dir):
            u.notify(f'已删除缓存目录: {cache_dir}')

    if bake_slots:
        u.notify(f'烘焙结束: 成功 {ok_count}/{len(bake_slots)}')
        return ok_count > 0
    u.notify('未烘焙（AnimSeq 均为空），已清空对应纹理组')
    return True
