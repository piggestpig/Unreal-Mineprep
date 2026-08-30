import re
import unreal
from mc_utils import warn


def _unwrap(ret):
    if isinstance(ret, (list, tuple)) and ret and isinstance(ret[0], unreal.DynamicMesh):
        return ret[0]
    return ret


def _enable_mats(dm):
    return _unwrap(unreal.GeometryScript_Materials.enable_material_i_ds(dm))


def _mats_from_skm(skm):
    return [
        s.get_editor_property('material_interface')
        for s in (skm.get_editor_property('materials') or [])
    ]


def _mats_from_sm_comp(comp):
    sm = comp.get_editor_property('static_mesh')
    n = len(sm.get_editor_property('static_materials') or []) if sm else 0
    out = []
    for i in range(max(n, 1)):
        mi = comp.get_material(i)
        if mi:
            out.append(mi)
    if out:
        return out
    if not sm:
        return []
    return [
        s.get_editor_property('material_interface')
        for s in (sm.get_editor_property('static_materials') or [])
    ]


def _collect_children(root):
    kids = list(root.get_children_components(True) or [])
    skms = [
        c for c in kids
        if isinstance(c, unreal.SkeletalMeshComponent) and c.get_skeletal_mesh_asset()
    ]
    sms = [
        c for c in kids
        if isinstance(c, unreal.StaticMeshComponent) and c.get_editor_property('static_mesh')
    ]
    return skms, sms


def _xf_to_root(root, child):
    sock = str(child.get_attach_socket_name() or '')
    if sock and child.get_attach_parent() == root:
        return child.get_relative_transform() * root.get_socket_transform(
            sock, unreal.RelativeTransformSpace.RTS_COMPONENT
        )
    return root.get_world_transform().inverse() * child.get_world_transform()


def _paint_bone(dm, bone_name, body_dm, bone_opts):
    dm = _unwrap(unreal.GeometryScript_BoneWeights.copy_bones_from_mesh(body_dm, dm, bone_opts))
    has = unreal.GeometryScript_BoneWeights.mesh_has_bone_weights(dm)
    has_w = has[1] if isinstance(has, (list, tuple)) else bool(has)
    if not has_w:
        dm = _unwrap(unreal.GeometryScript_BoneWeights.mesh_create_bone_weights(dm, True))
    idx_ret = unreal.GeometryScript_BoneWeights.get_bone_index(dm, bone_name)
    idx = int(idx_ret[-1]) if isinstance(idx_ret, (list, tuple)) else int(idx_ret)
    bw = unreal.GeometryScriptBoneWeight()
    bw.set_editor_property('bone_index', idx)
    bw.set_editor_property('weight', 1.0)
    return _unwrap(unreal.GeometryScript_BoneWeights.set_all_vertex_bone_weights(dm, [bw]))


def _append(target_dm, mats, append_dm, append_mats, xf, append_opts, compact):
    return unreal.GeometryScript_MeshEdits.append_mesh_with_materials(
        target_dm, mats, append_dm, append_mats, xf, False, append_opts, compact
    )


def _mat_remap(target_mats, append_mats, compact):
    """与 Geometry Script AppendMaterials 相同：compact 只对照追加前的 target 列表。"""
    remap = []
    out = list(target_mats)
    for m in append_mats:
        hit = None
        if compact:
            for i, t in enumerate(target_mats):
                if t == m:
                    hit = i
                    break
        if hit is None:
            hit = len(out)
            out.append(m)
        remap.append(hit)
    return remap


def _remap_ids(dm, remap):
    """把追加网格本地材质 ID 改到已有全局槽（两遍，避免 ID 互相覆盖）。"""
    if not remap:
        return dm
    gs = unreal.GeometryScript_Materials
    tmp = 1 << 16
    for src, dst in enumerate(remap):
        dm = _unwrap(gs.remap_material_i_ds(dm, int(src), int(tmp + dst)))
    for dst in remap:
        dm = _unwrap(gs.remap_material_i_ds(dm, int(tmp + dst), int(dst)))
    return dm


def _append_child(target_dm, mats, append_dm, append_mats, xf, append_opts,
                  compact, cache, mesh):
    """同一 SKM/SM 资产的后续实例复用首次材质槽，不再追加。"""
    key = mesh.get_path_name() if mesh else None
    if key and key in cache:
        append_dm = _remap_ids(append_dm, cache[key])
        return unreal.GeometryScript_MeshEdits.append_mesh(
            target_dm, append_dm, xf, False, append_opts
        ), mats
    remap = _mat_remap(mats, append_mats, compact)
    target_dm, mats = _append(
        target_dm, mats, append_dm, append_mats, xf, append_opts, compact
    )
    if key:
        cache[key] = remap
    return target_dm, mats


def _make_opts():
    from_opts = unreal.GeometryScriptCopyMeshFromAssetOptions()
    lod = unreal.GeometryScriptMeshReadLOD()
    bone_opts = unreal.GeometryScriptCopyBonesFromMeshOptions()
    try:
        bone_opts.set_editor_property('reindex_weights', True)
    except Exception:
        pass
    append_opts = unreal.GeometryScriptAppendMeshOptions()
    try:
        append_opts.set_editor_property(
            'combine_mode', unreal.GeometryScriptCombineAttributesMode.ENABLE_ALL_MATCHING
        )
    except Exception:
        pass
    return from_opts, lod, bone_opts, append_opts


def _prepare_vertex_colors_for_skm(dm):
    """写入骨骼网格前校正顶点色，使材质观感与静态网格一致。

    Geometry Script 写 MeshDescription 时默认 SRGB→Linear（为 StaticMesh 的
    ToFColor(true) 配对）。SkeletalMesh Build 使用 ToFColor(false)，不再抬回
    sRGB，导致原 SM 顶点色在材质里偏暗。写入前先 Linear→sRGB，抵消该变换。
    """
    try:
        has = unreal.GeometryScript_MeshQueries.get_has_vertex_colors(dm)
        if isinstance(has, (list, tuple)):
            has = has[-1] if has else False
        if not has:
            return dm
    except Exception:
        pass
    return _unwrap(
        unreal.GeometryScript_VertexColors.convert_mesh_vertex_colors_linear_to_srgb(dm)
    )


def _save_skm(body_dm, skeleton, mats, out_path, existing=None):
    """新建或覆写骨骼网格资产。existing 非空时用 copy_mesh_to_skeletal_mesh，不删除。"""
    body_dm = _prepare_vertex_colors_for_skm(body_dm)
    mat_list = [m for m in mats if m]

    if existing:
        copy_opts = unreal.GeometryScriptCopyMeshToAssetOptions(
            replace_materials=bool(mat_list),
            new_materials=mat_list,
        )
        write_lod = unreal.GeometryScriptMeshWriteLOD()
        _, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_to_skeletal_mesh(
            body_dm, existing, copy_opts, write_lod
        )
        if outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
            warn(f'merge_skm: overwrite failed: {out_path} ({outcome})')
            return None
        try:
            existing.set_editor_property('skeleton', skeleton)
        except Exception:
            pass
        unreal.EditorAssetLibrary.save_loaded_asset(existing)
        return existing

    create_opts = unreal.GeometryScriptCreateNewSkeletalMeshAssetOptions()
    mmap = unreal.Map(int, unreal.MaterialInterface)
    for i, m in enumerate(mat_list):
        mmap[i] = m
    create_opts.set_editor_property('materials', mmap)
    new_mesh, outcome = unreal.GeometryScript_NewAssetUtils.create_new_skeletal_mesh_asset_from_mesh(
        body_dm, skeleton, out_path, create_opts
    )
    if not new_mesh or outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
        warn(f'merge_skm: create failed: {out_path} ({outcome})')
        return None
    unreal.EditorAssetLibrary.save_loaded_asset(new_mesh)
    return new_mesh


#########################################################################


def merge_skm(root: unreal.SkeletalMeshComponent, save_path: str = None,
              name=None, merge_mat=True, skm=True, sm=True, overwrite=False):
    """合并根骨骼网格组件及其子网格为单个骨骼网格资产。

    skm / sm: 是否在最终资产中保留骨骼网格 / 静态网格（含子组件）。
    skm=False 且 sm=True 时只烘焙挂在骨架上的物品（无身体几何）。
    overwrite=False 且目标已存在时 warn 并返回 None；
    overwrite=True 时用 copy_mesh_to_skeletal_mesh 直接覆写几何与材质（不先删除）。
    merge_mat=True 时，子 SKM 前 N 个槽使用根材质（N=共有槽数），多余槽追加；
    相同子网格（同一 SKM/SM 资产）共用首次材质槽，与 merge_mat 无关。
    静态网格材质槽首次追加在后（不与已有槽 compact）。
    """
    if not skm and not sm:
        warn('merge_skm: both skm=False and sm=False, nothing to merge')
        return None

    root_skm = root.get_skeletal_mesh_asset()
    if not root_skm:
        warn('merge_skm: root has no skeletal mesh (need skeleton)')
        return None

    pkg = root_skm.get_path_name().rsplit('.', 1)[0]
    if not save_path:
        save_path = pkg.rsplit('/', 1)[0]
    if not name:
        name = re.sub(r'(?i)_Body$', '', root_skm.get_name())
    out_path = f"{str(save_path).rstrip('/')}/{name}"

    existing = None
    if unreal.EditorAssetLibrary.does_asset_exist(out_path):
        if not overwrite:
            warn(f'merge_skm: asset exists, skip: {out_path}')
            return None
        existing = unreal.EditorAssetLibrary.load_asset(out_path)
        if not isinstance(existing, unreal.SkeletalMesh):
            warn(f'merge_skm: existing asset is not SkeletalMesh: {out_path}')
            return None

    skeleton = root_skm.get_editor_property('skeleton')
    root_mats = _mats_from_skm(root_skm) if skm else []
    from_opts, lod, bone_opts, append_opts = _make_opts()

    body_dm = unreal.DynamicMesh()
    mats = []

    if skm:
        body_dm, _ = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
            root_skm, body_dm, from_opts, lod
        )
        mats = list(root_mats)
    # Always bind skeleton bones onto the working mesh (empty OK for items-only)
    body_dm = _unwrap(unreal.GeometryScript_BoneWeights.copy_bones_from_skeleton(
        skeleton, body_dm, bone_opts
    ))
    body_dm = _enable_mats(body_dm)

    skm_kids, sm_kids = _collect_children(root)
    if not skm:
        skm_kids = []
    if not sm:
        sm_kids = []

    slot_cache = {}

    for child in skm_kids:
        cmesh = child.get_skeletal_mesh_asset()
        child_mats = _mats_from_skm(cmesh)
        dm = unreal.DynamicMesh()
        dm, _ = unreal.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
            cmesh, dm, from_opts, lod
        )
        try:
            dm = _unwrap(unreal.GeometryScript_BoneWeights.copy_bones_from_mesh(
                body_dm, dm, bone_opts
            ))
        except Exception:
            pass
        dm = _enable_mats(dm)
        if merge_mat and root_mats:
            shared = min(len(root_mats), len(child_mats))
            append_mats = list(root_mats[:shared]) + list(child_mats[shared:])
        else:
            append_mats = list(child_mats)
        body_dm, mats = _append_child(
            body_dm, mats, dm, append_mats, _xf_to_root(root, child),
            append_opts, True, slot_cache, cmesh,
        )

    for child in sm_kids:
        sm_asset = child.get_editor_property('static_mesh')
        sock = str(child.get_attach_socket_name() or '')
        dm = unreal.DynamicMesh()
        dm, _ = unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(
            sm_asset, dm, from_opts, lod
        )
        if sock:
            dm = _paint_bone(dm, sock, body_dm, bone_opts)
        dm = _enable_mats(dm)
        body_dm, mats = _append_child(
            body_dm, mats, dm, _mats_from_sm_comp(child),
            _xf_to_root(root, child), append_opts, False, slot_cache, sm_asset,
        )

    if body_dm.get_triangle_count() <= 0:
        warn(f'merge_skm: no geometry to save (skm={skm}, sm={sm})')
        return None

    return _save_skm(body_dm, skeleton, mats, out_path, existing=existing)
