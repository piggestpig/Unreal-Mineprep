"""从骨骼网格体一键创建 MC_VAT 脚手架（SM / 纹理集合 / MIC），供左栏烘焙使用。"""

import unreal

from . import bake_anim_ops
from . import util as u


def default_vat_save_path(
    skm: unreal.SkeletalMesh | None,
    is_item: bool = False,
) -> str:
    """骨骼网格体旁边的文件夹：物品 VAT_{名称}，否则 DA_VAT_{名称}。"""
    if not isinstance(skm, unreal.SkeletalMesh):
        return ''
    prefix = 'VAT_' if is_item else 'DA_VAT_'
    return f'{u.package_dir(skm)}/{prefix}{u.display_name(skm)}'


def on_init_props_changed(mod, property_name):
    """SKM / bIsItem 变更时重设 SavePath。"""
    if str(property_name) not in ('SKM', 'bIsItem'):
        return
    path = default_vat_save_path(
        mod.init_props.SKM,
        bool(getattr(mod.init_props, 'bIsItem', False)),
    )
    if path:
        mod.init_props.SavePath = path


def skin_texture_from_skm(skm: unreal.SkeletalMesh | None) -> unreal.Texture2D | None:
    """若 SKM 槽 0 材质是 MIC 且含「纹理贴图」参数，则提取该纹理。"""
    if not skm:
        return None
    materials = skm.get_editor_property('materials') or []
    if not materials:
        return None
    mat = materials[0].get_editor_property('material_interface')
    if not isinstance(mat, unreal.MaterialInstanceConstant):
        u.notify(f'骨骼材质不是材质实例，跳过默认皮肤: {mat}')
        return None
    tex = unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(
        mat, '纹理贴图'
    )
    if isinstance(tex, unreal.Texture2D):
        return tex
    u.notify(f'材质实例无「纹理贴图」参数: {mat.get_name()}')
    return None


def _set_texture_collection_param(owner: unreal.Object, prop_name: str, tc: unreal.TextureCollection):
    pv = unreal.TextureCollectionParameterValue()
    info = pv.get_editor_property('parameter_info')
    info.set_editor_property('name', prop_name)
    pv.set_editor_property('parameter_info', info)
    pv.set_editor_property('parameter_value', tc)
    owner.set_editor_property(prop_name, pv)


def _set_mic_texture_collection(
    mic: unreal.MaterialInstanceConstant,
    param_name: str,
    tc: unreal.TextureCollection,
):
    values = list(mic.get_editor_property('texture_collection_parameter_values') or [])
    updated = False
    for i, pv in enumerate(values):
        info = pv.get_editor_property('parameter_info')
        if str(info.get_editor_property('name')) == param_name:
            pv.set_editor_property('parameter_value', tc)
            values[i] = pv
            updated = True
            break
    if not updated:
        pv = unreal.TextureCollectionParameterValue()
        info = pv.get_editor_property('parameter_info')
        info.set_editor_property('name', param_name)
        pv.set_editor_property('parameter_info', info)
        pv.set_editor_property('parameter_value', tc)
        values.append(pv)
    mic.set_editor_property('texture_collection_parameter_values', values)


def create_vat_from_skm(mod) -> unreal.Object | None:
    """
    右栏主流程：
    SKM → SM + MC_VAT + 空动画/皮肤纹理集合 + MIC → 填入左栏 DataAsset。
    资产写到 init_props.SavePath（默认 SKM 旁 DA_VAT_{名称}/ 或物品 VAT_{名称}/）。
    """
    skm = mod.init_props.SKM
    if not isinstance(skm, unreal.SkeletalMesh):
        u.notify('请先指定骨骼网格体')
        return None

    is_item = bool(getattr(mod.init_props, 'bIsItem', False))
    save_path = (mod.init_props.SavePath or '').strip()
    if not save_path:
        save_path = default_vat_save_path(skm, is_item)
        mod.init_props.SavePath = save_path
    try:
        directory = u.ensure_dir(save_path)
    except ValueError as e:
        u.notify(str(e))
        return None

    skm_name = u.display_name(skm)
    sm_name = f'SM_{skm_name}'
    da_name = f'VAT_{skm_name}' if is_item else f'DA_VAT_{skm_name}'
    vat_tc_name = f'VAT{skm_name}_纹理集合'
    skin_tc_name = f'皮肤_{skm_name}_纹理集合'
    mic_name = f'VAT_{skm_name}_Inst'

    # --- 1) Static Mesh ---
    overwrite_sm = bool(getattr(mod.init_props, 'bOverwriteModel', False))
    sm_path = f'{directory}/{sm_name}'
    sm_exists = unreal.EditorAssetLibrary.does_asset_exist(sm_path)
    if sm_exists and not overwrite_sm:
        sm = unreal.load_asset(sm_path)
    else:
        sm = unreal.AnimToTextureBPLibrary.convert_skeletal_mesh_to_static_mesh(
            skm, sm_path, 0
        )
        u.save(sm)
    if not isinstance(sm, unreal.StaticMesh):
        u.notify(f'创建静态网格体失败: {sm_name}')
        return None
    if sm_exists and overwrite_sm:
        u.notify(f'已覆写静态网格体: {sm.get_name()} @ {directory}')
    else:
        u.notify(f'静态网格体: {sm.get_name()} @ {directory}')

    # --- 2) MC_VAT ---
    mc_cls = unreal.load_object(None, u.MC_VAT_CLASS_PATH)
    if not mc_cls:
        u.notify(f'找不到 MC_VAT 类: {u.MC_VAT_CLASS_PATH}')
        return None
    mc_vat = u.create_asset(directory, da_name, mc_cls)
    if not mc_vat:
        u.notify(f'创建 MC_VAT 失败: {da_name}')
        return None

    # --- 3) 空 TextureCollection ---
    vat_tc = u.create_asset(directory, vat_tc_name, unreal.TextureCollection)
    skin_tc = u.create_asset(directory, skin_tc_name, unreal.TextureCollection)
    if isinstance(vat_tc, unreal.TextureCollection):
        slots = list(vat_tc.get_editor_property('textures') or [])
        if len(slots) < 3:
            vat_tc.set_editor_property('textures', [None, None, None])
            u.save(vat_tc)

    # --- 4) MIC + 从 SKM 提取「纹理贴图」→ 默认皮肤 ---
    skin_tex = skin_texture_from_skm(skm)
    mic_template = unreal.load_asset(u.MIC_TEMPLATE)
    if mic_template:
        mic = u.duplicate_or_load(directory, mic_name, mic_template)
        if isinstance(mic, unreal.MaterialInstanceConstant):
            if skin_tex:
                unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(
                    mic, '默认皮肤', skin_tex
                )
                u.notify(f'默认皮肤 ← {skin_tex.get_name()}')
            else:
                u.notify('未找到「纹理贴图」，默认皮肤保持模板值')
            if is_item:
                unreal.MaterialEditingLibrary.set_material_instance_static_switch_parameter_value(
                    mic, '物品', True
                )
            if isinstance(vat_tc, unreal.TextureCollection):
                _set_mic_texture_collection(mic, '动画纹理集合', vat_tc)
            if isinstance(skin_tc, unreal.TextureCollection):
                _set_mic_texture_collection(mic, '皮肤纹理集合', skin_tc)
            unreal.MaterialEditingLibrary.update_material_instance(mic)
            u.save(mic)
            sm.set_material(0, mic)
            u.save(sm)

    # --- 5) 写回 MC_VAT ---
    mc_vat.set_editor_property('skeletal_mesh', skm)
    mc_vat.set_editor_property('static_mesh', sm)
    mc_vat.set_editor_property('sample_rate', 60.0)
    mc_vat.set_editor_property('mode', unreal.AnimToTextureMode.BONE)
    try:
        bounds = sm.get_bounds()
        extents = sorted([
            float(bounds.box_extent.x),
            float(bounds.box_extent.y),
            float(bounds.box_extent.z),
        ])
        mc_vat.set_editor_property('碰撞箱大小', extents[1])
    except Exception:
        pass
    if isinstance(vat_tc, unreal.TextureCollection):
        _set_texture_collection_param(mc_vat, '动画纹理集合', vat_tc)
    if isinstance(skin_tc, unreal.TextureCollection):
        _set_texture_collection_param(mc_vat, '皮肤纹理集合', skin_tc)
    u.save(mc_vat)

    # --- 6) 填入左栏 DataAsset，并同步 AnimSeq ---
    u.assign_soft_prop(mod.bake_props, 'DataAsset', mc_vat)
    bake_anim_ops.sync_anim_seq_from_data_asset(mod)
    bake_anim_ops.sync_copy_props_from_data_asset(mod)
    u.notify(f'已创建并填入左栏: {mc_vat.get_name()}')
    return mc_vat

