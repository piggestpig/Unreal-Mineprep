"""复制 MC_VAT 数据集（可选连同静态网格体 / 材质 / 纹理 / 纹理集合）。"""

import unreal

from . import bake_anim_ops
from . import util as u


def _tc_from_mc_vat(mc_vat, prop_name: str):
    try:
        pv = mc_vat.get_editor_property(prop_name)
    except Exception:
        return None
    if pv is None:
        return None
    try:
        return pv.get_editor_property('parameter_value')
    except Exception:
        return getattr(pv, 'parameter_value', None)


def _set_tc_on_mc_vat(mc_vat, prop_name: str, tc: unreal.TextureCollection):
    pv = unreal.TextureCollectionParameterValue()
    info = pv.get_editor_property('parameter_info')
    info.set_editor_property('name', prop_name)
    pv.set_editor_property('parameter_info', info)
    pv.set_editor_property('parameter_value', tc)
    mc_vat.set_editor_property(prop_name, pv)


def _sm_materials(sm: unreal.StaticMesh) -> list:
    mats = []
    try:
        for entry in (sm.get_editor_property('static_materials') or []):
            mat = entry.get_editor_property('material_interface')
            if mat and mat not in mats:
                mats.append(mat)
    except Exception:
        pass
    if mats:
        return mats
    for i in range(16):
        try:
            mat = sm.get_material(i)
        except Exception:
            break
        if mat and mat not in mats:
            mats.append(mat)
    return mats


def _textures_from_tc(tc) -> list[unreal.Texture2D]:
    if not isinstance(tc, unreal.TextureCollection):
        return []
    return [
        t for t in (tc.get_editor_property('textures') or [])
        if isinstance(t, unreal.Texture2D)
    ]


def _validate_copy_path(path: str) -> str | None:
    path = (path or '').strip().rstrip('/')
    if not path:
        u.notify('目标路径为空')
        return None
    if path != '/Game' and not path.startswith('/Game/'):
        u.notify(f'目标路径必须在 /Game 下: {path}')
        return None
    try:
        directory = u.ensure_dir(path)
    except Exception as e:
        u.notify(f'无法创建目标目录: {path} ({e})')
        return None
    if not unreal.EditorAssetLibrary.does_directory_exist(directory):
        u.notify(f'无法创建目标目录: {directory}')
        return None
    return directory


def _duplicate_or_use(directory: str, name: str, original: unreal.Object):
    """复制资产；目标已存在则加载复用并继续。"""
    if not original:
        return None
    existing = u.load_or_none(directory, name)
    if existing:
        u.notify(f'目标已存在，复用: {directory}/{name}')
        return existing
    asset = u.asset_tools().duplicate_asset(name, directory, original)
    if not asset:
        u.notify(f'复制失败: {name} → {directory}')
        return None
    u.save(asset)
    return asset


def _rewire_tc_textures(tc: unreal.TextureCollection, remap: dict):
    slots = list(tc.get_editor_property('textures') or [])
    changed = False
    for i, tex in enumerate(slots):
        if tex in remap:
            slots[i] = remap[tex]
            changed = True
    if changed:
        tc.set_editor_property('textures', slots)
        u.save(tc)


def _rewire_mic(mic: unreal.MaterialInstanceConstant, remap: dict):
    """重绑材质上的纹理集合参数（材质内贴图参数保持原引用）。"""
    try:
        values = list(mic.get_editor_property('texture_collection_parameter_values') or [])
        dirty = False
        for i, pv in enumerate(values):
            tc = pv.get_editor_property('parameter_value')
            if tc in remap:
                pv.set_editor_property('parameter_value', remap[tc])
                values[i] = pv
                dirty = True
        if dirty:
            mic.set_editor_property('texture_collection_parameter_values', values)
    except Exception:
        pass
    u.save(mic)


def _copy_with_deps(mc_vat, directory: str, new_name: str):
    """复制 SM / 材质 / 纹理 / TC，再复制 DA 并重绑（不含 SKM、AnimSeq）。"""
    sm = mc_vat.get_editor_property('static_mesh') or mc_vat.bp_get_static_mesh()
    anim_tc = _tc_from_mc_vat(mc_vat, '动画纹理集合')
    skin_tc = _tc_from_mc_vat(mc_vat, '皮肤纹理集合')

    mats = _sm_materials(sm) if isinstance(sm, unreal.StaticMesh) else []
    # 只复制「动画纹理集合」里的 VAT 贴图，不复制材质参数纹理
    textures: list[unreal.Texture2D] = list(_textures_from_tc(anim_tc))

    remap: dict = {}

    for tex in textures:
        copied = _duplicate_or_use(directory, tex.get_name(), tex)
        if not copied:
            return None
        remap[tex] = copied

    for tc in (anim_tc, skin_tc):
        if not isinstance(tc, unreal.TextureCollection):
            continue
        copied = _duplicate_or_use(directory, tc.get_name(), tc)
        if not copied:
            return None
        remap[tc] = copied
        _rewire_tc_textures(copied, remap)

    for mat in mats:
        copied = _duplicate_or_use(directory, mat.get_name(), mat)
        if not copied:
            return None
        remap[mat] = copied
        if isinstance(copied, unreal.MaterialInstanceConstant):
            _rewire_mic(copied, remap)

    new_sm = None
    if isinstance(sm, unreal.StaticMesh):
        new_sm = _duplicate_or_use(directory, sm.get_name(), sm)
        if not new_sm:
            return None
        remap[sm] = new_sm
        # 按原始槽位重绑，勿用去重后的 mats 列表当下标
        try:
            for i, entry in enumerate(sm.get_editor_property('static_materials') or []):
                mat = entry.get_editor_property('material_interface')
                if mat in remap:
                    new_sm.set_material(i, remap[mat])
        except Exception:
            for i, mat in enumerate(mats):
                if mat in remap:
                    try:
                        new_sm.set_material(i, remap[mat])
                    except Exception:
                        pass
        u.save(new_sm)

    new_da = _duplicate_or_use(directory, new_name, mc_vat)
    if not new_da:
        return None

    if new_sm:
        new_da.set_editor_property('static_mesh', new_sm)
    if anim_tc in remap:
        _set_tc_on_mc_vat(new_da, '动画纹理集合', remap[anim_tc])
    if skin_tc in remap:
        _set_tc_on_mc_vat(new_da, '皮肤纹理集合', remap[skin_tc])
    u.save(new_da)
    return new_da


def copy_data_asset(mod) -> unreal.Object | None:
    """左栏「复制数据集」：按 CopyProps 复制当前 MC_VAT（可选依赖）。"""
    mc_vat = u.resolve_mc_vat(mod.bake_props.DataAsset)
    if not mc_vat:
        u.notify('请先指定有效的动画数据集')
        return None

    target_path = _validate_copy_path(mod.copy_props.TargetPath or '')
    if not target_path:
        return None

    new_name = (mod.copy_props.NewName or '').strip()
    if not new_name:
        u.notify('新名称不能为空')
        return None

    copy_deps = bool(mod.copy_props.CopyDeps)
    if copy_deps:
        u.notify(f'复制数据集及依赖 → {target_path}/{new_name}')
        new_da = _copy_with_deps(mc_vat, target_path, new_name)
    else:
        u.notify(f'复制数据集 → {target_path}/{new_name}')
        new_da = _duplicate_or_use(target_path, new_name, mc_vat)

    if not new_da:
        return None

    u.assign_soft_prop(mod.bake_props, 'DataAsset', new_da)
    bake_anim_ops.sync_anim_seq_from_data_asset(mod)
    bake_anim_ops.sync_copy_props_from_data_asset(mod)
    u.notify(f'已复制并填入左栏: {new_da.get_name()} @ {target_path}')
    return new_da
