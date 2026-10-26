import re
from collections import defaultdict
from dataclasses import dataclass, replace
from hashlib import sha256
import json
import math
from pathlib import Path
from mc_math import _rotate, rotator_quaternion
try:
    import unreal
except ModuleNotFoundError:
    from mc_utils import Lazy as unreal
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
    return child.get_world_transform() * root.get_world_transform().inverse()


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
    # 将骨架骨骼信息拷贝到工作网格（仅合并静态物品时同样需要骨架）
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


# 方块结构烘焙：面剔除、同材质矩形合批与静态网格资产生成
BAKE_VERSION = "blocks-bake-3"
RECIPE_TAG = "Mineprep.BakeRecipe"
STATS_TAG = "Mineprep.BakeStats"
_DIRECTIONS = {
    "east": (1, 0, 0), "west": (-1, 0, 0),
    "south": (0, 1, 0), "north": (0, -1, 0),
    "up": (0, 0, 1), "down": (0, 0, -1),
}


@dataclass(frozen=True)
class Face:
    points: tuple                 # UE 坐标系，以格子中心为原点，单位为格 (1 格 = 100cm)
    uvs: tuple
    texture: str
    direction: str | None = None
    cullable: bool = False
    repeatable: bool = False


@dataclass(frozen=True)
class Prototype:
    faces: tuple
    full: bool
    opaque: bool


@dataclass
class BakeGeometry:
    quads: list                   # [(顶点厘米坐标, UV 坐标, 贴图路径), ...]
    textures: list
    recipe: str
    stats: dict


def _axis_face(points):
    """判断面是否贴合单格边界（坐标位于 ±0.5），返回朝向名称或 None。"""
    for name, normal in _DIRECTIONS.items():
        axis = next(i for i, n in enumerate(normal) if n)
        if all(abs(p[axis] - normal[axis] * .5) < 1e-6 for p in points):
            return name
    return None


def _normal_direction(points):
    """根据顶点顺序计算轴对齐法线方向（含半砖、楼梯等位于格子内部的面）。"""
    u = tuple(points[1][i] - points[0][i] for i in range(3))
    v = tuple(points[2][i] - points[0][i] for i in range(3))
    normal = (v[1]*u[2]-v[2]*u[1], v[2]*u[0]-v[0]*u[2], v[0]*u[1]-v[1]*u[0])
    axis = max(range(3), key=lambda i: abs(normal[i]))
    if abs(normal[axis]) < 1e-8 or any(abs(normal[i]) > abs(normal[axis])*1e-6
                                      for i in range(3) if i != axis):
        return None
    return next(name for name, n in _DIRECTIONS.items() if n[axis]*normal[axis] > 0)


def _tangents(direction):
    axis = next(i for i, n in enumerate(_DIRECTIONS[direction]) if n)
    return tuple(i for i in range(3) if i != axis)


def _full_face(points, direction):
    if direction is None:
        return False
    a, b = _tangents(direction)
    return {(round(p[a], 6), round(p[b], 6)) for p in points} == {
        (-.5, -.5), (-.5, .5), (.5, -.5), (.5, .5)}


def _within_cell_face(points, direction):
    return direction is not None and all(-.500001 <= p[i] <= .500001
                                         for p in points for i in _tangents(direction))


def _affine_uv(points, uvs, axes):
    """求解面内 UV 对平面坐标的仿射梯度，非仿射四边形返回 None。"""
    a, b = axes
    x1, y1 = points[1][a] - points[0][a], points[1][b] - points[0][b]
    x2, y2 = points[2][a] - points[0][a], points[2][b] - points[0][b]
    det = x1 * y2 - x2 * y1
    if abs(det) < 1e-8:
        return None
    gradients = []
    for k in range(2):
        d1, d2 = uvs[1][k] - uvs[0][k], uvs[2][k] - uvs[0][k]
        gradients.append(((d1 * y2 - d2 * y1) / det,
                          (x1 * d2 - x2 * d1) / det))
    origin = tuple(uvs[0][k] - gradients[k][0] * (points[0][a] + .5)
                   - gradients[k][1] * (points[0][b] + .5) for k in range(2))
    if any(abs(uvs[i][k] - origin[k]
               - gradients[k][0] * (points[i][a] + .5)
               - gradients[k][1] * (points[i][b] + .5)) > 1e-6
           for i in range(4) for k in range(2)):
        return None
    return origin, tuple(gradients)


def _repeat_frame(face):
    if not face.repeatable or not _full_face(face.points, face.direction):
        return None
    frame = _affine_uv(face.points, face.uvs, _tangents(face.direction))
    if frame is None:
        return None
    origin, gradients = frame
    # 仅当 UV 恰好覆盖整张 0~1 贴图且方向轴对齐时，才允许跨格重复拼接
    flat = tuple(round(v, 6) for row in gradients for v in row)
    if (any(v not in (-1, 0, 1) for v in flat)
            or any(sum(abs(v) for v in row) != 1 for row in gradients)
            or any(sum(abs(row[i]) for row in gradients) != 1 for i in range(2))
            or any(abs(v - round(v)) > 1e-6 for v in origin)
            or any(abs(min(uv[k] for uv in face.uvs)) > 1e-6
                   or abs(max(uv[k] for uv in face.uvs) - 1) > 1e-6 for k in range(2))):
        return None
    return tuple(round(v, 6) for v in origin), flat


def _rectangles(pairs):
    """将共面相邻的单位格贪婪合并为矩形 (u, v, width, height)。"""
    remaining = set(pairs)
    for u, v in sorted(remaining):
        if (u, v) not in remaining:
            continue
        width = 1
        while (u + width, v) in remaining:
            width += 1
        height = 1
        while all((u + du, v + height) in remaining for du in range(width)):
            height += 1
        for dv in range(height):
            remaining.difference_update((u + du, v + dv) for du in range(width))
        yield u, v, width, height


def _validate_options(pivot, cull, merge_faces):
    if cull not in {"none", "opaque", "same"}:
        raise ValueError("cull must be 'none', 'opaque' or 'same'")
    if not isinstance(merge_faces, bool):
        raise ValueError("merge_faces must be bool")
    try:
        pivot = tuple(float(v) for v in pivot)
    except (TypeError, ValueError) as exc:
        raise ValueError("pivot must contain three finite MC coordinates") from exc
    if len(pivot) != 3 or not all(math.isfinite(v) for v in pivot):
        raise ValueError("pivot must contain three finite MC coordinates")
    return pivot


def build_geometry(cells, resolve, *, pivot=(0, 0, 0), cull="opaque",
                   merge_faces=True, dependencies=()):
    """将稀疏方块字典烘焙为合并后的几何面数据（纯几何计算，不依赖 Unreal）。

    resolve(name, properties) 负责解析每种方块状态的几何原型（每种状态只解析一次）。
    支持邻格遮挡剔除 (cull) 与共面同材质贪婪合批 (merge_faces)，并生成用于校验资产复用的配方哈希。
    """
    pivot = _validate_options(pivot, cull, merge_faces)
    if not cells:
        raise ValueError("Cannot bake empty Blocks")
    states, prototypes, normalized = {}, {}, []
    for pos, cell in sorted(cells.items()):
        if (len(pos) != 3 or any(isinstance(v, bool) or not isinstance(v, int) for v in pos)):
            raise ValueError(f"Invalid integer cell coordinate: {pos!r}")
        name = str(cell["name"]).lower().removeprefix("minecraft:")
        props = dict(cell.get("properties") or {})
        key = name, tuple(sorted((str(k), str(v)) for k, v in props.items()))
        if key not in prototypes:
            proto = resolve(name, dict(key[1]))
            if not proto.faces:
                raise ValueError(f"No JSON geometry for {name}")
            prototypes[key] = proto
        states[pos] = key
        normalized.append((pos, key))

    prepared = {key: tuple((face, _repeat_frame(face) if merge_faces else None)
                           for face in proto.faces)
                for key, proto in prototypes.items()}
    quads, groups = [], defaultdict(dict)
    raw_count = visible_count = 0
    ue_pivot = pivot[0], pivot[2], pivot[1]
    for pos, key in states.items():
        proto = prototypes[key]
        center = pos[0], pos[2], pos[1]
        for face, frame in prepared[key]:
            raw_count += 1
            if cull != "none" and face.cullable and face.direction:
                n = _DIRECTIONS[face.direction]
                neighbor = states.get((pos[0] + n[0], pos[1] + n[2], pos[2] + n[1]))
                if neighbor is not None:
                    other = prototypes[neighbor]
                    if other.full and (other.opaque or
                            (cull == "same" and proto.full and key[0] == neighbor[0])):
                        continue
            visible_count += 1
            if frame is not None:
                a, b = _tangents(face.direction)
                normal_axis = next(i for i, v in enumerate(_DIRECTIONS[face.direction]) if v)
                group = face.texture, face.direction, center[normal_axis], frame
                pair = center[a], center[b]
                if pair not in groups[group]:
                    groups[group][pair] = face
                    continue
                # 同一格同一朝向若有多个共面图层，多余图层直接保留，避免被集合去重覆盖
            points = tuple(tuple(100 * (p[i] + center[i] - ue_pivot[i])
                                 for i in range(3)) for p in face.points)
            quads.append((points, face.uvs, face.texture))

    for (_, direction, plane, frame), pairs in sorted(groups.items()):
        a, b = _tangents(direction)
        for u, v, width, height in _rectangles(pairs):
            face = pairs[u, v]
            points, uvs = [], []
            for point in face.points:
                local = list(point)
                local[a] = u - .5 + (point[a] + .5) * width
                local[b] = v - .5 + (point[b] + .5) * height
                normal_axis = next(i for i, n in enumerate(_DIRECTIONS[direction]) if n)
                local[normal_axis] += plane
                points.append(tuple(100 * (local[i] - ue_pivot[i]) for i in range(3)))
                origin, gradient = frame
                du, dv = (point[a] + .5) * width, (point[b] + .5) * height
                uvs.append((origin[0] + gradient[0] * du + gradient[1] * dv,
                            origin[1] + gradient[2] * du + gradient[3] * dv))
            quads.append((tuple(points), tuple(uvs), face.texture))

    if not quads:
        raise ValueError("Baking produced no visible faces")
    source_faces = [(key, proto.full, proto.opaque,
                     [(f.points, f.uvs, f.texture, f.direction, f.cullable, f.repeatable)
                      for f in proto.faces]) for key, proto in sorted(prototypes.items())]
    recipe_data = (BAKE_VERSION, pivot, cull, merge_faces, normalized,
                   source_faces, sorted(dependencies))
    recipe = sha256(json.dumps(recipe_data, separators=(",", ":"),
                               ensure_ascii=True, allow_nan=False).encode()).hexdigest()
    textures = sorted({q[2] for q in quads})
    return BakeGeometry(quads, textures, recipe, {
        "version": BAKE_VERSION, "cells": len(cells), "raw_faces": raw_count,
        "visible_faces": visible_count, "quads": len(quads),
        "triangles": len(quads) * 2, "materials": len(textures)})


def _canonical_uv(direction, p):
    # 与 mc_importer 一致的未旋转整面标准 UV 映射
    x, y, z = (v + .5 for v in p)
    return {"north": (x, 1-z), "south": (x, 1-z),
            "east": (1-y, 1-z), "west": (y, 1-z),
            "up": (x, y), "down": (x, y)}[direction]


def _locked_uvs(original, transformed, uvs, source_dir, target_dir):
    """烘焙模型时直接将 uvlock 变换写入顶点 UV，无需依赖实例材质的顶点色标记。"""
    source = [_canonical_uv(source_dir, p) + (0,) for p in original]
    # _affine_uv 内部对坐标加了 0.5，这里先减 0.5 对齐到 [0, 1] 范围
    shifted = [(p[0] - .5, p[1] - .5, 0) for p in source]
    frame = _affine_uv(shifted, uvs, (0, 1))
    if frame is None:
        return uvs
    origin, gradients = frame
    return tuple(tuple(origin[k] + gradients[k][0] * uv[0]
                       + gradients[k][1] * uv[1] for k in range(2))
                 for uv in (_canonical_uv(target_dir, p) for p in transformed))


class _SourceResolver:
    """单次烘焙的模型、贴图与方块状态解析器，同时记录依赖文件的哈希值。"""
    def __init__(self):
        import mc_importer
        import mc_structure
        self.importer, self.structure = mc_importer, mc_structure
        self.models, self.textures, self.files, self.blockstates = {}, {}, {}, {}

    def _remember(self, path):
        path = Path(path).resolve()
        key = str(path)
        if key not in self.files:
            self.files[key] = sha256(path.read_bytes()).hexdigest()

    def _parents(self, path, visited=None):
        visited = set() if visited is None else visited
        path = Path(path).resolve()
        if path in visited:
            raise ValueError(f"Cyclic model parents: {path}")
        visited.add(path)
        self._remember(path)
        parent = json.loads(path.read_text(encoding="utf-8")).get("parent")
        if parent and not parent.startswith(("builtin/", "item/generated")):
            self._parents(self.importer._resolve_model_reference(path, parent), visited)

    def _texture(self, path):
        path = Path(path).resolve()
        key = str(path)
        if key not in self.textures:
            from PIL import Image
            self._remember(path)
            metadata = Path(str(path) + ".mcmeta")
            if metadata.exists():
                self._remember(metadata)
            with Image.open(path) as image:
                opaque = image.convert("RGBA").getchannel("A").getextrema()[0] == 255
                square = image.width == image.height
            animated = metadata.exists() and "animation" in json.loads(metadata.read_text(encoding="utf-8"))
            self.textures[key] = opaque, square and not animated
        return key, self.textures[key]

    def _uvlock(self, name, model, rotation):
        if name not in self.blockstates:
            path = self.importer._blockstates_dir() / (name + ".json")
            nodes = []
            def visit(value):
                if isinstance(value, dict):
                    if "model" in value:
                        nodes.append(value)
                    for item in value.values():
                        visit(item)
                elif isinstance(value, list):
                    for item in value:
                        visit(item)
            if path.exists():
                self._remember(path)
                visit(json.loads(path.read_text(encoding="utf-8")))
            self.blockstates[name] = nodes
        pitch, yaw, roll = rotation
        return any(n.get("uvlock") is True and n["model"].split("/")[-1].split(":")[-1] == model
                   and abs(pitch) < 1e-6
                   and (float(n.get("y", 0)) - yaw) % 360 == 0
                   and (float(n.get("x", 0)) - roll) % 360 == 0
                   for n in self.blockstates[name])

    def __call__(self, name, properties):
        faces, opacity = [], []
        for model, pitch, yaw, roll in self.structure.structure_parts(name, properties):
            if model not in self.models:
                path = self.structure.resolve_block_json_path(model)
                if path is None:
                    raise ValueError(f"No JSON model for {name}: {model}")
                path = Path(path)
                self._parents(path)
                data = self.importer._load_mc_model(path)
                collected = self.importer._collect_block_model(path, data, model)
                if not collected or collected[0] != "block":
                    raise ValueError(f"Baking requires JSON elements: {model}")
                # 标记了 force_translucent 的贴图按半透明处理，不遮挡邻格
                translucent = any(isinstance(value, dict) and value.get("force_translucent")
                                  for value in (data.get("textures") or {}).values())
                self.models[model] = collected[2], bool(translucent)
            quaternion = rotator_quaternion(pitch, yaw, roll)
            locked = self._uvlock(name, model, (pitch, yaw, roll))
            source_faces, translucent = self.models[model]
            for source in source_faces:
                original = tuple((v.x / 100, v.y / 100, v.z / 100) for v in source["vertices"])
                points = tuple(tuple(round(v, 9) for v in _rotate(quaternion, p)) for p in original)
                direction = _axis_face(points)
                source_dir, target_dir = _normal_direction(original), _normal_direction(points)
                uvs = tuple((v.x, v.y) for v in source["uv_corners"])
                if locked and target_dir and source_dir:
                    uvs = _locked_uvs(original, points, uvs, source_dir, target_dir)
                texture, (opaque, repeatable) = self._texture(source["texture_file"])
                full = _full_face(points, direction)
                # 旋转后仍贴合单格边界的 cullface 面才允许被相邻完整方块剔除
                declared = (source.get("cullface") == source_dir and source_dir is not None
                            and direction == target_dir and _within_cell_face(points, direction))
                faces.append(Face(points, uvs, texture, direction,
                                  declared,
                                  full and repeatable))
                opacity.append(opaque and not translucent)
        full = (len(faces) == 6 and {f.direction for f in faces} == set(_DIRECTIONS)
                and all(_full_face(f.points, f.direction) for f in faces))
        if full:
            faces = [replace(face, cullable=True) for face in faces]
        return Prototype(tuple(faces), full, full and all(opacity))


def resolve_geometry(cells, **options):
    resolver = _SourceResolver()
    # 解析过程中会收集依赖文件哈希，完成后将其一并混入配方签名
    geometry = build_geometry(cells, resolver, **options)
    geometry.recipe = sha256((geometry.recipe + json.dumps(sorted(resolver.files.items()),
                                                          separators=(",", ":"))).encode()).hexdigest()
    return geometry


def _dynamic_mesh(geometry):
    mesh = unreal.DynamicMesh()
    unreal.GeometryScript_Materials.enable_material_i_ds(mesh)
    by_texture = defaultdict(list)
    for quad in geometry.quads:
        by_texture[quad[2]].append(quad)
    for slot, texture in enumerate(geometry.textures):
        vertices, triangles, normals, uv0 = [], [], [], []
        for points, uvs, _ in by_texture[texture]:
            offset = len(vertices)
            u = tuple(points[1][i] - points[0][i] for i in range(3))
            v = tuple(points[2][i] - points[0][i] for i in range(3))
            cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
            length = math.sqrt(sum(n*n for n in cross))
            if length < 1e-8:
                raise ValueError("Degenerate source face")
            # UE 左手系顺时针正面对应笛卡尔叉积的反方向
            normal = unreal.Vector(*(-n / length for n in cross))
            vertices.extend(unreal.Vector(*p) for p in points)
            normals.extend([normal] * 4)
            uv0.extend(unreal.Vector2D(*uv) for uv in uvs)
            triangles.extend((unreal.IntVector(offset, offset+1, offset+2),
                              unreal.IntVector(offset, offset+2, offset+3)))
        buffers = unreal.GeometryScriptSimpleMeshBuffers(
            vertices=vertices, triangles=triangles, normals=normals, uv0=uv0,
            vertex_colors=[unreal.LinearColor(1, 1, 1, 1)] * len(vertices))
        unreal.GeometryScript_MeshEdits.append_buffers_to_mesh(mesh, buffers, material_id=slot)
    if mesh.get_triangle_count() != geometry.stats["triangles"]:
        raise RuntimeError("Incomplete baked mesh buffers")
    return mesh


def bake_blocks(blocks, *, destination_path="/Game/mc/baked", asset_name=None,
                pivot=(0, 0, 0), cull="opaque", merge_faces=True, reload=False,
                two_sided=None):
    """将 Blocks 烘焙并保存为单个 StaticMesh 资产；若目标路径已存在相同配方的资产则直接复用。"""
    import mc_importer
    if not isinstance(reload, bool):
        raise ValueError("reload must be bool")
    if two_sided is not None and type(two_sided) is not bool:
        raise ValueError("two_sided must be bool or None")
    legacy_sidedness = cull == "same"
    two_sided = legacy_sidedness if two_sided is None else two_sided
    destination_path = str(destination_path).rstrip("/")
    if not re.fullmatch(r"/Game(?:/\w+)*", destination_path):
        raise ValueError("destination_path must be a /Game package directory")
    asset_name = mc_importer._sanitize_asset_name(asset_name or blocks.name)
    asset_path = destination_path + "/" + asset_name
    geometry = resolve_geometry(blocks.copy_cells(), pivot=pivot, cull=cull, merge_faces=merge_faces)
    if two_sided != legacy_sidedness:
        # 默认材质单双面策略未改变时保持原配方哈希兼容
        geometry.recipe = sha256(json.dumps((geometry.recipe, "two-sided-1", two_sided)).encode()).hexdigest()
    existing = unreal.load_asset(asset_path) if unreal.EditorAssetLibrary.does_asset_exist(asset_path) else None
    if existing is not None:
        if not isinstance(existing, unreal.StaticMesh):
            raise ValueError(f"Target is not a StaticMesh: {asset_path}")
        recipe = unreal.EditorAssetLibrary.get_metadata_tag(existing, RECIPE_TAG)
        if recipe == geometry.recipe and not reload:
            return existing
        if not reload:
            raise ValueError(f"Different bake recipe at {asset_path}; use reload=True to replace")
    dynamic_mesh = _dynamic_mesh(geometry)
    # 几何校验通过后再创建材质、贴图与静态网格资产
    materials = mc_importer._materials_for_files(
        [Path(p) for p in geometry.textures], destination_path, two_sided=two_sided, reload=reload)
    if any(material is None for material in materials):
        raise RuntimeError("Baking failed to resolve a material")
    if not unreal.EditorAssetLibrary.does_directory_exist(destination_path):
        if not unreal.EditorAssetLibrary.make_directory(destination_path):
            raise RuntimeError(f"Cannot create asset directory: {destination_path}")
    # 新建或覆写目标静态网格资产，并检查写入结果
    if existing is None:
        mesh, outcome = unreal.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(
            dynamic_mesh, asset_path, unreal.GeometryScriptCreateNewStaticMeshAssetOptions())
    else:
        mesh = existing
        _, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(
            dynamic_mesh, mesh, unreal.GeometryScriptCopyMeshToAssetOptions(
                replace_materials=True, new_materials=materials), unreal.GeometryScriptMeshWriteLOD())
    if mesh is None or outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
        raise RuntimeError(f"Failed to write baked mesh: {asset_path} ({outcome})")
    for slot, material in enumerate(materials):
        mesh.set_material(slot, material)
    unreal.EditorAssetLibrary.set_metadata_tag(mesh, RECIPE_TAG, geometry.recipe)
    unreal.EditorAssetLibrary.set_metadata_tag(mesh, STATS_TAG, json.dumps(geometry.stats, sort_keys=True))
    if not unreal.EditorAssetLibrary.save_loaded_asset(mesh):
        raise RuntimeError(f"Failed to save baked mesh: {asset_path}")
    return mesh
