"""Model recipes, GLB codecs, and editor asset output."""

from __future__ import annotations

import json
import os
import re
import struct
from collections.abc import Mapping
from dataclasses import dataclass, field
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

try:
    import numpy as np
except ModuleNotFoundError:
    np = None

try:
    import unreal
except ModuleNotFoundError:
    unreal = None


def read_glb(data):
    """Read a GLB 2.0 document and its embedded binary buffer."""
    if len(data) < 20 or struct.unpack_from('<4sII', data) != (b'glTF', 2, len(data)):
        raise ValueError('Invalid GLB header')
    json_size, json_type = struct.unpack_from('<I4s', data, 12)
    binary_header = 20 + json_size
    if json_type != b'JSON' or binary_header + 8 > len(data):
        raise ValueError('Expected GLB JSON and BIN chunks')
    document = json.loads(data[20:binary_header])
    binary_size, binary_type = struct.unpack_from('<I4s', data, binary_header)
    binary_start = binary_header + 8
    if binary_type != b'BIN\0' or binary_start + binary_size > len(data):
        raise ValueError('Invalid GLB BIN chunk')
    return document, memoryview(data)[binary_start:binary_start + binary_size]


def pack_glb(document, binary):
    """Package a JSON document and its aligned binary buffer."""
    text = json.dumps(document, separators=(',', ':')).encode('utf-8')
    text += b' ' * (-len(text) % 4)
    binary = bytes(binary)
    binary += b'\0' * (-len(binary) % 4)
    return (struct.pack('<4sII', b'glTF', 2, 28 + len(text) + len(binary))
            + struct.pack('<I4s', len(text), b'JSON') + text
            + struct.pack('<I4s', len(binary), b'BIN\0') + binary)


def embedded_base_color_surfaces(data):
    """Return (embedded image bytes, MIME type, alpha mode) by material name."""
    document, binary = read_glb(data)

    images = {}
    for material in document.get('materials', []):
        color = material.get('pbrMetallicRoughness', {}).get('baseColorTexture')
        if color is None:
            continue
        name = material.get('name')
        texture = document['textures'][color['index']]
        image = document['images'][texture['source']]
        if not name or name in images or 'bufferView' not in image:
            raise ValueError('Expected unique material names and embedded base-color images')
        view = document['bufferViews'][image['bufferView']]
        start = view.get('byteOffset', 0)
        end = start + view['byteLength']
        if view['buffer'] != 0 or not 0 <= start < end <= len(binary):
            raise ValueError('Invalid GLB image range: ' + name)
        images[name] = binary[start:end], image['mimeType'], material.get('alphaMode', 'OPAQUE')
    return images


def clean_asset_name(value):
    return re.sub(r'[^a-zA-Z0-9_]', '_', str(value)).strip('_')[:96]


def model_destination(path, name):
    path = str(path).strip().rstrip('/')
    if not re.fullmatch(r'/Game(?:/[a-zA-Z0-9_]+)*', path):
        raise ValueError('保存路径必须为合法 /Game/... 路径 / Invalid /Game path')
    name = clean_asset_name(name)
    if not name:
        raise ValueError('保存名称不能为空 / Save name is empty')
    return path+'/'+name, name


def cache_model_source(directory, filename, data):
    """Publish a versioned source file in a flat cache for editor reimport."""
    digest = sha256(data).hexdigest()[:8]
    filename = Path(filename)
    target = Path(directory) / f'{filename.stem}_{digest}{filename.suffix}'
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=target.parent) as scratch:
            temporary = Path(scratch) / target.name
            temporary.write_bytes(data)
            try:
                # Windows rename is exclusive. On POSIX, linking provides the same guarantee.
                publish = os.rename if os.name == 'nt' else os.link
                publish(temporary, target)
                return target
            except FileExistsError:
                pass
    if target.read_bytes() != data:
        raise ValueError(f'Model source cache hash collision: {target}')
    return target


@dataclass
class RigidMesh:
    """One joint per vertex, with bone transforms and geometry in UE centimetres."""

    bones: list = field(default_factory=list)  # (name, parent index, component bind matrix)
    positions: list = field(default_factory=list)
    normals: list = field(default_factory=list)
    uv: list = field(default_factory=list)
    joints: list = field(default_factory=list)
    triangles: list = field(default_factory=list)  # outward winding in the input coordinate basis
    triangle_materials: list = field(default_factory=list)


def _multiply(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)) for i in range(4))


def _inverse_rigid(matrix):
    return tuple(tuple(matrix[j][i] for j in range(3))
                 + (-sum(matrix[j][i] * matrix[j][3] for j in range(3)),)
                 for i in range(3)) + ((0., 0., 0., 1.),)


def _column_major(matrix):
    return [matrix[i][j] for j in range(4) for i in range(4)]


def encode_rigid_glb(mesh, name, surfaces):
    """Encode a rigid mesh with named embedded RGBA materials."""
    if len(mesh.bones) > 65536:
        raise ValueError('Too many bones for GLB skin indices')
    blob, views, accessors = bytearray(), [], []

    def view(data):
        blob.extend(b'\0' * (-len(blob) % 4))
        views.append(dict(buffer=0, byteOffset=len(blob), byteLength=len(data)))
        blob.extend(data)
        return len(views) - 1

    def accessor(rows, fmt, component, kind, bounds=False):
        rows = list(rows)
        flat = [v for row in rows for v in row]
        index = view(struct.pack(f'<{len(flat)}{fmt}', *flat))
        acc = dict(bufferView=index, componentType=component, count=len(rows), type=kind)
        if bounds:
            acc.update(min=list(map(min, zip(*rows))), max=list(map(max, zip(*rows))))
        accessors.append(acc)
        return len(accessors) - 1

    attributes = {
        'POSITION': accessor(((x/100, z/100, y/100) for x,y,z in mesh.positions), 'f', 5126, 'VEC3', True),
        'NORMAL': accessor(((x,z,y) for x,y,z in mesh.normals), 'f', 5126, 'VEC3'),
        'TEXCOORD_0': accessor(mesh.uv, 'f', 5126, 'VEC2'),
        'JOINTS_0': accessor(((j,0,0,0) for j in mesh.joints), 'H', 5123, 'VEC4'),
        'WEIGHTS_0': accessor(((1.,0.,0.,0.) for _ in mesh.joints), 'f', 5126, 'VEC4')}
    axes = (0, 2, 1)
    worlds, nodes = [], []
    for bone, parent, matrix in mesh.bones:
        world = tuple(tuple(matrix[i][j] for j in axes) + (matrix[i][3]/100,)
                      for i in axes) + ((0.,0.,0.,1.),)
        local = world if parent < 0 else _multiply(_inverse_rigid(worlds[parent]), world)
        if parent >= 0:
            nodes[parent].setdefault('children', []).append(len(nodes))
        worlds.append(world)
        nodes.append(dict(name=bone, matrix=_column_major(local)))
    joints = list(range(len(nodes)))
    inverse_bind = accessor((_column_major(_inverse_rigid(m)) for m in worlds), 'f', 5126, 'MAT4')
    meshes, materials, images = [], [], []
    for index, (label, png) in enumerate(surfaces.items()):
        triangles = (tri for tri, slot in zip(mesh.triangles, mesh.triangle_materials) if slot == label)
        indices = accessor(((v,) for a,b,c in triangles for v in (a,c,b)), 'I', 5125, 'SCALAR')
        mesh_name = name if len(surfaces) == 1 else f'{name}_{label}'
        nodes.append(dict(name=mesh_name, mesh=index, skin=0))
        meshes.append(dict(name=mesh_name, primitives=[dict(attributes=attributes, indices=indices, material=index)]))
        images.append(dict(bufferView=view(png), mimeType='image/png'))
        materials.append(dict(name=label, alphaMode='MASK', doubleSided=True,
                              pbrMetallicRoughness=dict(baseColorTexture=dict(index=index))))
    document = dict(asset=dict(version='2.0', generator='Mineprep'), scene=0,
                    scenes=[dict(nodes=[0, *range(len(joints), len(nodes))])], nodes=nodes, bufferViews=views,
                    accessors=accessors, buffers=[dict(byteLength=len(blob))],
                    skins=[dict(name=name+'_Skeleton', skeleton=0, joints=joints, inverseBindMatrices=inverse_bind)],
                    meshes=meshes, images=images, materials=materials,
                    samplers=[dict(magFilter=9728, minFilter=9728)],
                    textures=[dict(source=i, sampler=0) for i in range(len(images))])
    return pack_glb(document, blob)


def _pelvis_edit_glb(data, *, required, to_pelvis, to_body, optional_parents, hip_point, error,
                     required_any=(), nested_head_parents=()):
    """Insert a pelvis hip pivot and reparent limbs/torso while keeping bound geometry."""
    document, binary = read_glb(data)
    nodes = document['nodes']
    skin, = document['skins']
    joints = skin['joints']
    by_name = {nodes[i]['name']: i for i in joints}
    parents = {child: i for i in joints for child in nodes[i].get('children', [])}
    root = by_name.get('root')
    body_joint = by_name.get('body')
    must_root = ('body',) + tuple(to_pelvis)
    nested_joints = {by_name[name] for name in nested_head_parents if name in by_name}
    if (root is None or 'pelvis' in by_name or body_joint is None
            or any(b not in by_name for b in required)
            or any(not any(all(b in by_name for b in opts) for opts in group) for group in required_any)
            or any(parents.get(by_name[b]) != root for b in must_root)
            or any(any(key in nodes[i] for key in ('translation', 'rotation', 'scale')) for i in joints)):
        raise ValueError(error)
    for b in to_body:
        joint = by_name.get(b)
        if joint is None:
            continue
        p = parents.get(joint)
        if b == 'head' and p in nested_joints and parents.get(p) in (root, body_joint):
            continue
        if p not in (root, body_joint):
            raise ValueError(error)
    identity = tuple(tuple(float(i == j) for j in range(4)) for i in range(4))
    worlds = {}

    def world_of(i):
        if i not in worlds:
            values = nodes[i].get('matrix', _column_major(identity))
            local = tuple(tuple(values[col*4 + row] for col in range(4)) for row in range(4))
            worlds[i] = _multiply(world_of(parents[i]), local) if i in parents else local
        return worlds[i]

    for i in joints:
        world_of(i)

    def position(bone):
        return tuple(row[3] for row in worlds[by_name[bone]][:3])

    def at(point):
        return tuple((*row[:3], x) for row, x in zip(identity, point)) + (identity[3],)

    hip = hip_point(position)
    pelvis, body = len(nodes), body_joint
    nodes.append(dict(name='pelvis'))
    joints.append(pelvis)
    by_name['pelvis'] = pelvis
    worlds[pelvis] = worlds[body] = at(hip)
    parents[pelvis] = root
    parents[body] = pelvis
    for bone in to_pelvis:
        parents[by_name[bone]] = pelvis
    for bone in to_body:
        joint = by_name.get(bone)
        if joint is None:
            continue
        if not (bone == 'head' and parents.get(joint) in nested_joints):
            parents[joint] = body
    for bone, target in optional_parents.items():
        joint = by_name.get(bone)
        target_joint = by_name.get(target)
        if joint is not None and target_joint is not None and parents.get(joint) == root:
            parents[joint] = target_joint
    for i in joints:
        nodes[i].pop('children', None)
    for i in joints:
        if i in parents:
            parent = parents[i]
            nodes[parent].setdefault('children', []).append(i)
            nodes[i]['matrix'] = _column_major(_multiply(_inverse_rigid(worlds[parent]), worlds[i]))

    blob = bytearray(binary)
    matrices = b''.join(struct.pack('<16f', *_column_major(_inverse_rigid(worlds[i]))) for i in joints)
    document['bufferViews'].append(dict(buffer=0, byteOffset=len(blob), byteLength=len(matrices)))
    document['accessors'][skin['inverseBindMatrices']].update(
        bufferView=len(document['bufferViews'])-1, count=len(joints))
    blob.extend(matrices)
    document['buffers'][0]['byteLength'] = len(blob)
    return pack_glb(document, blob)


def humanoid_edit_glb(data):
    """Build a hip-pivot editing rig for Java humanoids (open or folded arms) and preserve bound geometry."""
    return _pelvis_edit_glb(
        data,
        required=('body', 'head', 'left_leg', 'right_leg'),
        required_any=((('left_arm', 'right_arm'), ('arms',)),),
        to_pelvis=('left_leg', 'right_leg'),
        to_body=('head', 'left_arm', 'right_arm', 'arms'),
        optional_parents={},
        hip_point=lambda pos: tuple((x + y) / 2 for x, y in zip(pos('left_leg'), pos('right_leg'))),
        error='Expected the native Mineprep Java humanoid. Use edit_rig=False for the raw rig.',
    )


def quadruped_edit_glb(data):
    """Build a hind-hip editing rig for Java quadrupeds and preserve bound geometry."""
    def hip(pos):
        left, right, body = pos('left_hind_leg'), pos('right_hind_leg'), pos('body')
        leg_mid = (left[2] + right[2]) / 2
        hip_z = min((body[2], leg_mid), key=abs)
        return ((left[0] + right[0]) / 2, (left[1] + right[1]) / 2, hip_z)

    return _pelvis_edit_glb(
        data,
        required=('body', 'head', 'left_front_leg', 'right_front_leg', 'left_hind_leg', 'right_hind_leg'),
        to_pelvis=('left_hind_leg', 'right_hind_leg'),
        to_body=('head', 'left_front_leg', 'right_front_leg'),
        optional_parents={
            'upper_body': 'body',
            'left_chest': 'body',
            'right_chest': 'body',
            'egg_belly': 'body',
            'hump': 'body',
            'head_parts': 'body',
            'neck': 'body',
            'tail': 'pelvis',
            'tail1': 'pelvis',
            'tail2': 'tail1',
        },
        nested_head_parents=('head_parts', 'neck'),
        hip_point=hip,
        error='Expected a compatible Mineprep Java quadruped. Use edit_rig=False for the raw rig.',
    )


_GLTF_COMP_FMT = {
    5120: ('b', 127.0),
    5121: ('B', 255.0),
    5122: ('h', 32767.0),
    5123: ('H', 65535.0),
    5125: ('I', None),
    5126: ('f', None),
}
_GLTF_TYPE_COMPS = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT2': 4, 'MAT3': 9, 'MAT4': 16}


def _read_glb_accessor(document, binary, accessor_index):
    """Decode a scalar, vector, or matrix glTF accessor as (n_comp, values)."""
    acc = document['accessors'][accessor_index]
    n_comp = _GLTF_TYPE_COMPS[acc['type']]
    count = int(acc['count'])
    if 'bufferView' not in acc:
        return n_comp, [0.0] * (count * n_comp)
    comp_fmt, norm_scale = _GLTF_COMP_FMT[acc['componentType']]
    bv = document['bufferViews'][acc['bufferView']]
    unpacker = struct.Struct('<' + comp_fmt * n_comp)
    stride = bv.get('byteStride', unpacker.size)
    base = bv.get('byteOffset', 0) + acc.get('byteOffset', 0)
    normalized = bool(acc.get('normalized')) and norm_scale is not None
    signed = comp_fmt in ('b', 'h')
    values = []
    for k in range(count):
        items = unpacker.unpack_from(binary, base + k * stride)
        if normalized:
            if signed:
                values.extend(max(float(v) / norm_scale, -1.0) for v in items)
            else:
                values.extend(float(v) / norm_scale for v in items)
        else:
            values.extend(items)
    return n_comp, values


def _glb_node_local_mat4(node):
    """Return a glTF node's local 4x4 row-major transform matrix in meters."""
    if 'matrix' in node:
        m = node['matrix']
        return tuple(tuple(float(m[col * 4 + row]) for col in range(4)) for row in range(4))
    tx, ty, tz = (float(v) for v in node.get('translation', (0.0, 0.0, 0.0)))
    qx, qy, qz, qw = (float(v) for v in node.get('rotation', (0.0, 0.0, 0.0, 1.0)))
    sx, sy, sz = (float(v) for v in node.get('scale', (1.0, 1.0, 1.0)))
    xx, yy, zz = qx * qx, qy * qy, qz * qz
    xy, xz, yz = qx * qy, qx * qz, qy * qz
    wx, wy, wz = qw * qx, qw * qy, qw * qz
    return (
        ((1.0 - 2.0 * (yy + zz)) * sx, 2.0 * (xy - wz) * sy, 2.0 * (xz + wy) * sz, tx),
        (2.0 * (xy + wz) * sx, (1.0 - 2.0 * (xx + zz)) * sy, 2.0 * (yz - wx) * sz, ty),
        (2.0 * (xz - wy) * sx, 2.0 * (yz + wx) * sy, (1.0 - 2.0 * (xx + yy)) * sz, tz),
        (0.0, 0.0, 0.0, 1.0),
    )


def _gltf_mat4_to_ue_cm(m):
    """Convert a glTF row-major matrix (meters, Y-up) to UE row-major (cm, Z-up)."""
    axes = (0, 2, 1)
    rows = [[float(m[axes[r]][axes[c]]) for c in range(3)] + [float(m[axes[r]][3]) * 100.0] for r in range(3)]
    rows.append([0.0, 0.0, 0.0, 1.0])
    return rows


def glb_bone_bounds(source, *, dominant_weight_only=True):
    """Compute per-bone UE local bounds (cm) directly from a skinned GLB payload or path."""
    data = Path(source).read_bytes() if isinstance(source, (str, os.PathLike)) else source
    document, binary = read_glb(data)
    nodes = document.get('nodes') or []
    skins = document.get('skins') or []
    meshes = document.get('meshes') or []
    if not skins or not skins[0].get('joints'):
        raise ValueError('GLB 缺少蒙皮骨骼信息')

    skin = skins[0]
    joints = list(skin['joints'])
    joint_set = set(joints)
    parent_of = {child: idx for idx, node in enumerate(nodes) for child in node.get('children', ())}
    worlds = {}

    def world_of(idx):
        if idx not in worlds:
            local = _glb_node_local_mat4(nodes[idx])
            worlds[idx] = _multiply(world_of(parent_of[idx]), local) if idx in parent_of else local
        return worlds[idx]

    if 'inverseBindMatrices' in skin:
        _, ibm_vals = _read_glb_accessor(document, binary, skin['inverseBindMatrices'])
        if len(ibm_vals) < len(joints) * 16:
            raise ValueError('GLB inverseBindMatrices 数量不足')
        ibms = [
            tuple(tuple(float(ibm_vals[k * 16 + col * 4 + row]) for col in range(4)) for row in range(4))
            for k in range(len(joints))
        ]
    else:
        ibms = [_inverse_rigid(world_of(node_idx)) for node_idx in joints]

    n_joints = len(joints)
    mins = [[float('inf'), float('inf'), float('inf')] for _ in range(n_joints)]
    maxs = [[float('-inf'), float('-inf'), float('-inf')] for _ in range(n_joints)]
    counts = [0] * n_joints

    mesh_bindings = [
        (mesh_idx, world_of(node_idx))
        for node_idx, node in enumerate(nodes)
        if 'mesh' in node and node.get('skin', 0) == 0
        for mesh_idx in (node['mesh'],)
    ] or [(mesh_idx, ((1., 0., 0., 0.), (0., 1., 0., 0.), (0., 0., 1., 0.), (0., 0., 0., 1.)))
          for mesh_idx in range(len(meshes))]

    for mesh_idx, mesh_world in mesh_bindings:
        if mesh_idx < 0 or mesh_idx >= len(meshes):
            continue
        to_joints = [_multiply(ibm, mesh_world) for ibm in ibms]
        for prim in meshes[mesh_idx].get('primitives', ()):
            attrs = prim.get('attributes', {})
            if 'POSITION' not in attrs or 'JOINTS_0' not in attrs:
                continue
            _, pos_vals = _read_glb_accessor(document, binary, attrs['POSITION'])
            j_comp, j_vals = _read_glb_accessor(document, binary, attrs['JOINTS_0'])
            n_verts = len(pos_vals) // 3
            if 'WEIGHTS_0' in attrs:
                w_comp, w_vals = _read_glb_accessor(document, binary, attrs['WEIGHTS_0'])
            else:
                w_comp, w_vals = 4, [1.0, 0.0, 0.0, 0.0] * n_verts
            if 'indices' in prim:
                _, idx_vals = _read_glb_accessor(document, binary, prim['indices'])
                vert_indices = set(int(v) for v in idx_vals)
            else:
                vert_indices = range(n_verts)

            for v in vert_indices:
                if v < 0 or v >= n_verts:
                    continue
                px, py, pz = pos_vals[v * 3], pos_vals[v * 3 + 1], pos_vals[v * 3 + 2]
                j_base, w_base = v * j_comp, v * w_comp
                if dominant_weight_only:
                    best_slot, best_w = -1, 0.0
                    for k in range(min(4, j_comp, w_comp)):
                        w = float(w_vals[w_base + k])
                        s = int(j_vals[j_base + k])
                        if w > best_w and 0 <= s < n_joints:
                            best_slot, best_w = s, w
                    slots = (best_slot,) if best_slot >= 0 else ()
                else:
                    slots = {
                        int(j_vals[j_base + k])
                        for k in range(min(4, j_comp, w_comp))
                        if float(w_vals[w_base + k]) > 1e-6 and 0 <= int(j_vals[j_base + k]) < n_joints
                    }
                for slot in slots:
                    m = to_joints[slot]
                    lx = m[0][0] * px + m[0][1] * py + m[0][2] * pz + m[0][3]
                    ly = m[1][0] * px + m[1][1] * py + m[1][2] * pz + m[1][3]
                    lz = m[2][0] * px + m[2][1] * py + m[2][2] * pz + m[2][3]
                    ux, uy, uz = lx * 100.0, lz * 100.0, ly * 100.0
                    bmin, bmax = mins[slot], maxs[slot]
                    if ux < bmin[0]: bmin[0] = ux
                    if uy < bmin[1]: bmin[1] = uy
                    if uz < bmin[2]: bmin[2] = uz
                    if ux > bmax[0]: bmax[0] = ux
                    if uy > bmax[1]: bmax[1] = uy
                    if uz > bmax[2]: bmax[2] = uz
                    counts[slot] += 1

    records = []
    seen = set()
    for slot, node_idx in enumerate(joints):
        parent_idx = parent_of.get(node_idx)
        in_skin = parent_idx in joint_set
        parent_name = str(nodes[parent_idx].get('name', '')) if in_skin else ''
        local_gltf = _glb_node_local_mat4(nodes[node_idx]) if in_skin else world_of(node_idx)
        bone_name = str(nodes[node_idx].get('name', ''))
        if bone_name in seen:
            continue
        seen.add(bone_name)
        has_bounds = counts[slot] > 0
        records.append({
            'bone_name': bone_name,
            'parent_name': parent_name,
            'local_mat4': _gltf_mat4_to_ue_cm(local_gltf),
            'local_min': list(mins[slot]) if has_bounds else [0.0, 0.0, 0.0],
            'local_max': list(maxs[slot]) if has_bounds else [0.0, 0.0, 0.0],
            'vertex_count': counts[slot],
            'has_bounds': has_bounds,
        })
    return records


# Low-poly recipes and their editor outputs.

COLOR_MATERIAL = '/Game/Mineprep/材质/Core/纯色实例材质'
_CACHE_ROOT = '/Game/mc/LowPoly'
_OWNER = 'Mineprep.LowPoly.Owner:'
_GROUP = 'Mineprep.LowPoly.Group:'
_ROOT = 'Mineprep.LowPoly.Root.v2:'
_RECIPE = 'Mineprep.LowPoly.Geometry'
_DEFAULTS = np.array([1, 1, 1, 1, 0, .5, .65, 0], dtype=np.float32) if np is not None else None


def _numbers(value, label):
    result = np.asarray(value, dtype=np.float64)
    if not np.isfinite(result).all():
        raise ValueError(f'{label} must contain finite numbers')
    return result


def _xyz(value, label, *, positive=False):
    result = np.broadcast_to(_numbers(value, label), (3,)).copy()
    if positive and np.any(result <= 0):
        raise ValueError(f'{label} must be positive')
    return result


def _array(value, shape, label, *, positive=False):
    result = np.broadcast_to(_numbers(value, label), shape).copy()
    if positive and np.any(result <= 0):
        raise ValueError(f'{label} must be positive')
    return result


def _appearance(count, color, metallic, specular, roughness, emissive):
    values = np.broadcast_to(_DEFAULTS, (count, 8)).copy()
    if color is not None:
        if isinstance(color, str):
            text = color.removeprefix('#')
            if len(text) not in (6, 8):
                raise ValueError('color requires #RRGGBB or #RRGGBBAA')
            color = [int(text[i:i+2], 16) / 255 for i in range(0, len(text), 2)]
        rgb = _numbers(color, 'color')
        if rgb.ndim == 0 or rgb.shape[-1] not in (3, 4) or np.any((rgb < 0) | (rgb > 1)):
            raise ValueError('color requires sRGB(A) values in 0..1')
        width = rgb.shape[-1]
        values[:, :width] = np.broadcast_to(rgb, (count, width))
        srgb = values[:, :3]
        values[:, :3] = np.where(srgb <= .04045, srgb / 12.92, ((srgb + .055) / 1.055) ** 2.4)
    for index, label, value in ((4, 'metallic', metallic), (5, 'specular', specular),
                                (6, 'roughness', roughness), (7, 'emissive', emissive)):
        if value is not None:
            data = _array(value, (count,), label)
            if np.any(data < 0) or (index != 7 and np.any(data > 1)):
                raise ValueError(f'{label} is outside its supported range')
            values[:, index] = data
    if not np.isfinite(values).all():
        raise ValueError('appearance exceeds float32 range')
    return values


@dataclass(frozen=True)
class _Source:
    kind: str
    value: object


@dataclass
class _Part:
    source: _Source
    positions: np.ndarray
    angles: np.ndarray                 # pitch, yaw, roll; degrees
    scales: np.ndarray
    values: np.ndarray                 # linear RGBA, metallic, specular, roughness, emissive
    material: object
    colored: bool


class _Group:
    def __init__(self, name='Model', pivot=(0, 0, 0), *, pitch=0, yaw=0, roll=0, scale=1):
        if np is None:
            raise ModuleNotFoundError('LowPolyModel requires NumPy')
        self.name = str(name)
        if not self.name or '/' in self.name:
            raise ValueError('group names must be nonempty and cannot contain /')
        self.pivot = tuple(_xyz(pivot, 'pivot'))
        self.pitch, self.yaw, self.roll = map(float, _numbers((pitch, yaw, roll), 'rotation'))
        self.scale = tuple(_xyz(scale, 'scale', positive=True))
        self.groups = {}
        self._parts = []

    def group(self, name, pivot=(0, 0, 0), *, pitch=0, yaw=0, roll=0, scale=1):
        """Create a named child; its pivot is in this group's local coordinates."""
        name = str(name)
        if name in self.groups:
            raise ValueError(f'duplicate group: {name}')
        child = _Group(name, pivot, pitch=pitch, yaw=yaw, roll=roll, scale=scale)
        self.groups[child.name] = child
        return child

    def clear(self):
        """Clear this group's recipe, without touching any placed output."""
        self._parts.clear()
        self.groups.clear()
        return self

    def add(self, source, position=(0, 0, 0), *, scale=1, pitch=0, yaw=0, roll=0,
            color=None, material=None, metallic=None, specular=None, roughness=None, emissive=None, pivot=None):
        """Add an asset or MC model at its original pivot. Scale is dimensionless."""
        return self.add_many(source, [_xyz(position, 'position')], scale=scale,
                             pitch=pitch, yaw=yaw, roll=roll, color=color, material=material,
                             metallic=metallic, specular=specular, roughness=roughness, emissive=emissive, pivot=pivot)

    def add_many(self, source, positions, *, scale=1, pitch=0, yaw=0, roll=0,
                 color=None, material=None, metallic=None, specular=None, roughness=None, emissive=None, pivot=None):
        """Append numeric arrays; positions [N,3], scale scalar/XYZ/[N,3], angles scalar/[N]."""
        points = _numbers(positions, 'positions')
        if points.ndim != 2 or points.shape[1] != 3:
            raise ValueError('positions requires [N,3], including for empty input')
        count = len(points)
        scales = _array(scale, (count, 3), 'scale', positive=True)
        angles = np.column_stack([_array(v, (count,), k) for k, v in
                                  (('pitch', pitch), ('yaw', yaw), ('roll', roll))])
        if pivot is not None:
            origin = _array(pivot, (count, 3), 'pivot')
            # UE Rotator quaternion, vectorized; scaling stays about each mesh's origin.
            sp, sy, sr = np.sin(np.radians(angles / 2)).T
            cp, cy, cr = np.cos(np.radians(angles / 2)).T
            q = np.column_stack((cr*sp*sy-sr*cp*cy, -cr*sp*cy-sr*cp*sy,
                                 cr*cp*sy-sr*sp*cy))
            w = cr*cp*cy+sr*sp*sy
            delta = points-origin
            cross = 2*np.cross(q, delta)
            points = origin+delta+w[:, None]*cross+np.cross(q, cross)
        colored = any(v is not None for v in (color, metallic, specular, roughness, emissive))
        if material is not None and colored:
            raise ValueError('material and color/surface overrides are mutually exclusive')
        values = _appearance(count, color, metallic, specular, roughness, emissive)
        source = source if isinstance(source, _Source) else _Source('asset', source)
        if count:
            self._parts.append(_Part(source, points.copy(), angles, scales, values, material, colored))
        return self

    def box(self, position=None, size=None, *, bounds=None, **options):
        """Centered solid box; size is a length or XYZ lengths in model units."""
        position, size = _box_geometry(position, size, bounds)
        options.setdefault('color', '#ffffff' if options.get('material') is None else None)
        return self.add(_Source('box', 0), position, scale=size, **options)

    def cylinder(self, position=(0, 0, 0), radius=.5, height=1, segments=8, **options):
        return self._round('cylinder', position, radius, height, segments, options)

    def cone(self, position=(0, 0, 0), radius=.5, height=1, segments=8, **options):
        return self._round('cone', position, radius, height, segments, options)

    def frustum(self, position=(0, 0, 0), radius=.5, top_radius=.25, height=1, segments=8, **options):
        """Centered capped frustum; radius is the bottom radius, top may be zero."""
        top = float(_numbers(top_radius, 'top_radius'))
        if top < 0:
            raise ValueError('top_radius must be nonnegative')
        return self._round('frustum', position, radius, height, segments, options, top)

    def _round(self, kind, position, radius, height, segments, options, top=None):
        if type(segments) is not int or not 3 <= segments <= 256:
            raise ValueError('segments must be an integer in 3..256')
        size = _xyz((2 * radius, 2 * radius, height), 'dimensions', positive=True)
        options.setdefault('color', '#ffffff' if options.get('material') is None else None)
        value = segments if top is None else (segments, float(top / radius).hex())
        return self.add(_Source(kind, value), position, scale=size, **options)

    def _walk(self, path=''):
        yield path, self
        for name, child in self.groups.items():
            yield from child._walk(f'{path}/{name}' if path else name)


def _ue():
    if unreal is None:
        raise RuntimeError('LowPolyModel placement requires Unreal Editor')
    return unreal


def _model_rotation(angles):
    pitch, yaw, roll = np.radians(angles)
    cp, cy, cr = np.cos((pitch, yaw, roll))
    sp, sy, sr = np.sin((pitch, yaw, roll))
    return np.array(((cy*cp, cy*sp*sr-sy*cr, -cy*sp*cr-sy*sr),
                     (sy*cp, sy*sp*sr+cy*cr, -sy*sp*cr+cy*sr),
                     (sp, -cp*sr, cp*cr)))


def _model_angles(matrix):
    horizontal = np.hypot(matrix[0, 0], matrix[1, 0])
    pitch = np.arctan2(matrix[2, 0], horizontal)
    if horizontal > 1e-10:
        yaw = np.arctan2(matrix[1, 0], matrix[0, 0])
        roll = np.arctan2(-matrix[2, 1], matrix[2, 2])
    else:
        yaw, roll = np.arctan2(-matrix[0, 1], matrix[1, 1]), 0.
    return tuple(map(float, np.degrees((pitch, yaw, roll))))


def _box_geometry(position, size, bounds):
    if bounds is not None:
        if position is not None or size is not None:
            raise ValueError('bounds is exclusive with position/size')
        low, high = _array(bounds, (2, 3), 'bounds')
        position, size = (low+high)/2, high-low
    else:
        position = (0, 0, 0) if position is None else position
        size = 1 if size is None else size
    return position, _xyz(size, 'size', positive=True)


_FACES = ('-X', '+X', '-Y', '+Y', '-Z', '+Z')
_MIRROR_Y = (1, -1, 1)


@dataclass(frozen=True)
class _BoxUV:
    faces: dict
    flip_u: bool = False

    def mirror(self):
        opposite = {'-Y': '+Y', '+Y': '-Y'}
        faces = {face: self.faces[opposite.get(face, face)] for face in _FACES}
        return _BoxUV(faces, not self.flip_u)


def _check_bone_name(name, used):
    if (not re.fullmatch(r'[A-Za-z0-9_]{1,80}', name)
            or name.casefold() == 'none' or name.casefold() in used):
        raise ValueError(f'Invalid or duplicate bone name: {name}')


def _mirrored_bone_name(name):
    for side, other in (('left', 'right'), ('right', 'left')):
        if name.startswith(side+'_'):
            return other+name[len(side):]
        if name.endswith('_'+side):
            return name[:-len(side)]+other
    return name+'_mirror'


def _face_axes(index):
    axis, sign = index//2, 2*(index%2)-1
    normal = np.eye(3, dtype=int)[axis]*sign
    up = np.eye(3, dtype=int)[0 if axis == 2 else 2]
    return normal, up, np.cross(up, normal)


def _box_uv(uv, size, pixels_per_unit):
    anchor = _numbers(uv, 'Box UV origin')
    if anchor.shape != (2,) or np.any(anchor < 0) or np.any(anchor != np.floor(anchor)):
        raise ValueError('Box UV origin must contain two nonnegative integer pixel offsets')
    density = _numbers(pixels_per_unit, 'pixels_per_unit')
    if density.ndim != 0 or density <= 0:
        raise ValueError('pixels_per_unit must be a positive number')
    u, v = map(int, anchor)
    depth, width, height = (max(1, int(n+.5)) for n in _numbers(size*density, 'Box UV dimensions'))
    return {
        '+Z': (u+depth, v, width, depth),
        '-Z': (u+depth+width, v, width, depth),
        '-Y': (u, v+depth, depth, height),
        '+X': (u+depth, v+depth, width, height),
        '+Y': (u+depth+width, v+depth, depth, height),
        '-X': (u+2*depth+width, v+depth, width, height),
    }


class _SkeletalBone:
    def __init__(self, name, parent, pose):
        self._name = name
        self._parent = parent
        self._pose = pose
        self._face_uvs = []

    @property
    def name(self):
        return self._name

    def box(self, position=None, size=None, *, bounds=None, color=None, uv=None,
            pitch=0, yaw=0, roll=0, pivot=None, pixels_per_unit=16):
        """Add a box rigidly attached to this bone."""
        if uv is not None:
            if color is not None:
                raise ValueError(f'{self.name}: UV and colour are mutually exclusive')
            if not isinstance(uv, Mapping):
                position, size = _box_geometry(position, size, bounds)
                bounds = None
                uv = _box_uv(uv, size, pixels_per_unit)
            if set(uv) != set(_FACES):
                raise ValueError(f'{self.name}: UV requires six face rectangles and no colour')
            rectangles = {}
            for face in _FACES:
                rect = _numbers(uv[face], f'{self.name} {face} UV')
                if (rect.shape != (4,) or np.any(rect[:2] < 0) or np.any(rect[2:] <= 0)
                        or np.any(rect != np.floor(rect))):
                    raise ValueError(f'{self.name} {face}: expected integer pixel offsets and positive sizes')
                rectangles[face] = tuple(map(int, rect))
            uv = _BoxUV(rectangles)
        self._pose.box(position, size, bounds=bounds, color='#ffffff' if color is None else color,
                       pitch=pitch, yaw=yaw, roll=roll, pivot=pivot)
        self._face_uvs.append(uv)
        return self


class SkeletalModel:
    """Editable rigid box recipe with explicit reference bones and optional PNG skin."""

    def __init__(self, name='Model'):
        self.name = str(name)
        self.root = _SkeletalBone('root', None, _Group('root'))
        self._bones = {'root': self.root}
        self._skin = None
        self._skin_size = None

    def bone(self, name, parent='root', pivot=(0, 0, 0), *, pitch=0, yaw=0, roll=0, scale=1):
        name = str(name)
        _check_bone_name(name, self._bones)
        ancestor = self._find(parent)
        pose = _Group(name, pivot, pitch=pitch, yaw=yaw, roll=roll, scale=scale)
        if len(set(pose.scale)) != 1:
            raise ValueError(f'{name}: skeletal bones require uniform scale')
        bone = _SkeletalBone(name, ancestor, pose)
        self._bones[name.casefold()] = bone
        return bone

    def _find(self, name):
        bone = self._bones.get(str(name).casefold())
        if bone is None:
            raise ValueError(f'Unknown bone: {name}')
        return bone

    def uv_layout(self):
        """Return the minimum PNG size, local face axes, and each textured box's rectangles."""
        boxes = []
        width, height = 0, 0
        for bone in self._bones.values():
            for index, uv in enumerate(bone._face_uvs):
                if uv is None:
                    continue
                boxes.append(dict(bone=bone.name, box=index, faces=dict(uv.faces), flip_u=uv.flip_u))
                for u, v, w, h in uv.faces.values():
                    width, height = max(width, u+w), max(height, v+h)

        def direction(vector):
            axis = int(np.flatnonzero(vector)[0])
            return _FACES[2*axis+int(vector[axis] > 0)]

        axes = {}
        for index, face in enumerate(_FACES):
            _, up, right = _face_axes(index)
            axes[face] = dict(up=direction(up), right=direction(right))
        return dict(size=(width, height), face_axes=axes, boxes=boxes)

    def set_skin(self, png):
        from io import BytesIO
        from PIL import Image

        data = bytes(png) if isinstance(png, (bytes, bytearray, memoryview)) else Path(png).read_bytes()
        with Image.open(BytesIO(data)) as image:
            if image.format != 'PNG':
                raise ValueError('Skin must be a PNG')
            image.load()
            self._skin_size = image.size
        self._skin = data
        return self

    def _worlds(self):
        children = {bone: [] for bone in self._bones.values()}
        for bone in self._bones.values():
            if bone._parent is not None:
                children[bone._parent].append(bone)
        worlds = {}
        pending = [self.root]
        while pending:
            bone = pending.pop()
            pose = bone._pose
            world, scale = np.eye(4), 1.
            if bone._parent is not None:
                parent, scale = worlds[bone._parent]
                local = np.eye(4)
                local[:3, :3] = _model_rotation((pose.pitch, pose.yaw, pose.roll))
                local[:3, 3] = np.asarray(pose.pivot) * scale * 100
                world = parent @ local
                scale *= pose.scale[0]
            worlds[bone] = world, scale
            pending.extend(reversed(children[bone]))
        return worlds

    def describe(self):
        return {b.name: dict(parent=b._parent.name if b._parent else None,
                             pivot=b._pose.pivot, rotation=(b._pose.pitch, b._pose.yaw, b._pose.roll),
                             scale=b._pose.scale[0], model_pivot=tuple(float(x)/100 for x in world[:3, 3]),
                             boxes=sum(len(p.positions) for p in b._pose._parts))
                for b, (world, _) in self._worlds().items()}

    def reparent(self, name, parent):
        bone, target = self._find(name), self._find(parent)
        ancestor = target
        while ancestor is not None:
            if ancestor is bone:
                raise ValueError(f'{name}: reparenting would create a cycle')
            ancestor = ancestor._parent
        if bone is self.root:
            raise ValueError('Cannot reparent the root bone')
        if target is bone._parent:
            return self
        if any(b._parent is target and b._pose.name == bone._pose.name for b in self._bones.values()):
            raise ValueError(f'{name}: the destination already has group {bone._pose.name}')
        worlds = self._worlds()
        world, scale = worlds[bone]
        parent_world, parent_scale = worlds[target]
        local = np.asarray(_inverse_rigid(parent_world)) @ world
        pose = bone._pose
        pose.pivot = tuple(local[:3, 3] / (100 * parent_scale))
        pose.scale = (scale / parent_scale,) * 3
        pose.pitch, pose.yaw, pose.roll = _model_angles(local)
        bone._parent = target
        return self

    def mirror_bone(self, name, new_name, *, parent=None):
        """Copy a branch across the model's XZ plane and return its new root bone."""
        source = self._find(name)
        if source is self.root:
            raise ValueError('Cannot mirror the root bone')
        target = source._parent if parent is None else self._find(parent)
        new_name = str(new_name)
        worlds = self._worlds()
        world, scale = worlds[source]
        parent_world, parent_scale = worlds[target]
        reflection = np.diag((*_MIRROR_Y, 1))
        local = np.asarray(_inverse_rigid(parent_world)) @ reflection @ world @ reflection
        mirrored, used = {}, set(self._bones)
        for bone in worlds:
            pose = bone._pose
            if bone is source:
                clone_parent, clone_name = target, new_name
                pivot = local[:3, 3] / (100 * parent_scale)
                angles = _model_angles(local)
                local_scale = scale / parent_scale
            elif bone._parent in mirrored:
                clone_parent, clone_name = mirrored[bone._parent], _mirrored_bone_name(bone.name)
                pivot = np.asarray(pose.pivot) * _MIRROR_Y
                angles = (pose.pitch, -pose.yaw, -pose.roll)
                local_scale = pose.scale[0]
            else:
                continue
            _check_bone_name(clone_name, used)
            used.add(clone_name.casefold())
            pitch, yaw, roll = angles
            clone_pose = _Group(clone_name, pivot, pitch=pitch, yaw=yaw, roll=roll, scale=local_scale)
            clone_pose._parts = deepcopy(pose._parts)
            for part in clone_pose._parts:
                part.positions *= _MIRROR_Y
                part.angles *= (1, -1, -1)
            clone = _SkeletalBone(clone_name, clone_parent, clone_pose)
            clone._face_uvs = [uv.mirror() if uv is not None else None for uv in bone._face_uvs]
            mirrored[bone] = clone
        self._bones.update((bone.name.casefold(), bone) for bone in mirrored.values())
        return mirrored[source]

    @classmethod
    def from_lowpoly(cls, model):
        if not isinstance(model, LowPolyModel):
            raise TypeError('Expected a LowPolyModel')
        result = cls(model.name)
        by_path = {'': result.root}
        for path, group in model._walk():
            bone = result.root
            if path:
                if len(set(group.scale)) != 1:
                    raise ValueError(f'{path}: skeletal conversion requires uniform group scale')
                base = re.sub(r'[^a-zA-Z0-9_]', '_', path)[:76].strip('_') or 'part'
                name, index = base, 1
                while name.casefold() == 'none' or name.casefold() in result._bones:
                    name = f'{base}_{index}'
                    index += 1
                bone = result.bone(name, by_path[path.rpartition('/')[0]].name, group.pivot,
                                   pitch=group.pitch, yaw=group.yaw, roll=group.roll, scale=group.scale)
                bone._pose.name = group.name
                by_path[path] = bone
            for part in group._parts:
                if part.source.kind != 'box' or part.material is not None:
                    raise ValueError(f"{path or 'root'}: skeletal conversion requires coloured boxes")
                if not np.all(part.values[:, 4:] == _DEFAULTS[4:]):
                    raise ValueError(f"{path or 'root'}: skeletal conversion requires default PBR parameters")
            bone._pose._parts = deepcopy(group._parts)
            bone._face_uvs = [None] * len(group._parts)
        return result

    def to_lowpoly(self):
        result = LowPolyModel(self.name)
        groups = {self.root: result}
        for bone in self._worlds():
            if any(uv is not None for uv in bone._face_uvs):
                raise ValueError(f'{bone.name}: LowPolyModel cannot preserve per-face skin UVs')
            pose = bone._pose
            if bone._parent is not None:
                groups[bone] = groups[bone._parent].group(
                    pose.name, pose.pivot, pitch=pose.pitch, yaw=pose.yaw, roll=pose.roll, scale=pose.scale)
            groups[bone]._parts = deepcopy(pose._parts)
        return result

    def to_glb(self):
        return self._encode(self.name)

    def _encode(self, name):
        mesh, surfaces = _skeletal_recipe(self)
        return encode_rigid_glb(mesh, name, surfaces)

    def bake(self, name=None, *, destination_path='/Game/mc/entity', reload=False):
        """Save a new mesh, or explicitly update a prior bake with the same reference skeleton."""
        from mineprep.model_assets import COMPLETE, RECIPE, SOURCE, publish_skinned_glb

        ue = _ue()
        lib = ue.EditorAssetLibrary
        folder, asset_name = model_destination(destination_path, self.name if name is None else name)
        destination = folder + '/SKM_' + asset_name
        owner = {SOURCE: 'skeletal_model', RECIPE: 'skeletal_model:' + folder}
        existing = None
        if reload and lib.does_asset_exist(destination):
            existing = ue.load_asset(destination)
            if (not isinstance(existing, ue.SkeletalMesh)
                    or lib.get_metadata_tag(existing, COMPLETE) != '1'
                    or not existing.skeleton
                    or any(lib.get_metadata_tag(asset, tag) != value
                           for asset in (existing, existing.skeleton) for tag, value in owner.items())):
                raise ValueError(f'Cannot update a foreign or incomplete SkeletalModel bake: {destination}')
        elif lib.does_directory_have_assets(folder):
            raise ValueError(f'Asset folder is occupied. Choose a different name: {folder}')
        data = self._encode(asset_name)
        cache = Path(ue.Paths.project_dir()) / 'Intermediate' / 'MineprepModels'
        path = cache_model_source(cache, asset_name + '.glb', data)
        return publish_skinned_glb((folder, asset_name, existing), path, owner=owner)


def _palette_png(palette):
    from io import BytesIO
    from PIL import Image

    width = min(256, len(palette))
    height = (len(palette)+width-1)//width
    width, height = (1 << (n-1).bit_length() for n in (width, height))
    image = Image.new('RGBA', (width, height))
    for rgba, index in palette.items():
        image.putpixel((index%width, index//width), rgba)
    out = BytesIO()
    image.save(out, format='PNG')
    return out.getvalue(), width, height


def _skeletal_recipe(model):
    mesh = RigidMesh()
    indices, palette, palette_vertices = {}, {}, []
    surfaces = {}
    face_axes = tuple(_face_axes(i) for i in range(len(_FACES)))
    for bone, (matrix, scale) in model._worlds().items():
        joint = len(mesh.bones)
        indices[bone] = joint
        mesh.bones.append((bone.name, indices.get(bone._parent, -1), matrix))
        for part, face_uv in zip(bone._pose._parts, bone._face_uvs):
            if face_uv is not None:
                if model._skin_size is None:
                    raise ValueError(f'{bone.name}: set a PNG skin before exporting UV boxes')
                width, height = model._skin_size
                for face, (u, v, w, h) in face_uv.faces.items():
                    if u+w > width or v+h > height:
                        raise ValueError(f'{bone.name} {face}: UV exceeds the skin dimensions')
                surfaces['Skin'] = model._skin
            for point, angles, size, values in zip(part.positions, part.angles, part.scales, part.values):
                if face_uv is None:
                    rgb = values[:3]
                    srgb = np.where(rgb <= .0031308, rgb*12.92, 1.055*rgb**(1/2.4)-.055)
                    rgba = tuple(np.rint(np.clip([*srgb, values[3]], 0, 1)*255).astype(int))
                    color = palette.setdefault(rgba, len(palette))
                basis = matrix[:3, :3] @ _model_rotation(angles)
                origin = matrix[:3, :3] @ (point*scale*100) + matrix[:3, 3]
                for face, (normal, up, right) in zip(_FACES, face_axes):
                    start = len(mesh.positions)
                    if face_uv is not None:
                        u, v, w, h = face_uv.faces[face]
                    for s, t in ((-1,-1), (1,-1), (1,1), (-1,1)):
                        corner = normal + s*right + t*up
                        mesh.positions.append(origin + basis @ (corner*size*scale*50))
                        mesh.normals.append(basis @ normal)
                        if face_uv is None:
                            palette_vertices.append((len(mesh.uv), color))
                            mesh.uv.append(None)
                        else:
                            use_right = (s > 0) != face_uv.flip_u
                            mesh.uv.append(((u + (w if use_right else 0))/width,
                                            (v + (h if t < 0 else 0))/height))
                    mesh.joints.extend([joint]*4)
                    mesh.triangles.extend(((start,start+1,start+2), (start,start+2,start+3)))
                    mesh.triangle_materials.extend(['Skin' if face_uv is not None else 'Palette']*2)
    if not mesh.positions:
        raise ValueError('Skeletal model requires at least one box')
    if palette:
        surfaces['Palette'], width, height = _palette_png(palette)
        for vertex, color in palette_vertices:
            mesh.uv[vertex] = ((color%width+.5)/width, (color//width+.5)/height)
    return mesh, surfaces


def _transform(position, angles=(0, 0, 0), scale=1):
    ue = _ue()
    point = _xyz(position, 'position') * 100
    pitch, yaw, roll = _numbers(angles, 'rotation')
    return ue.Transform(location=ue.Vector(*map(float, point)),
                        rotation=ue.Rotator(pitch=float(pitch), yaw=float(yaw), roll=float(roll)),
                        scale=ue.Vector(*map(float, _xyz(scale, 'scale', positive=True))))


def _primitive(source):
    ue = _ue()
    if source.kind == 'box':
        return ue.load_asset('/Engine/BasicShapes/Cube')
    recipe = f'lowpoly-1:{source.kind}:{source.value}:center:facet:uniform-uv'
    path = f'{_CACHE_ROOT}/SM_{source.kind}_{sha256(recipe.encode()).hexdigest()[:8]}'
    if ue.EditorAssetLibrary.does_asset_exist(path):
        mesh = ue.load_asset(path)
        if not isinstance(mesh, ue.StaticMesh) or ue.EditorAssetLibrary.get_metadata_tag(mesh, _RECIPE) != recipe:
            raise ValueError(f'Unowned or incompatible geometry asset: {path}')
        return mesh
    mesh = ue.DynamicMesh()
    options = ue.GeometryScriptPrimitiveOptions()
    segments = source.value[0] if source.kind == 'frustum' else source.value
    common = dict(radial_steps=segments, height_steps=0,
                  origin=ue.GeometryScriptPrimitiveOriginMode.CENTER, capped=True)
    if source.kind == 'cylinder':
        ue.GeometryScript_Primitives.append_cylinder(mesh, options, ue.Transform(), radius=50, height=100, **common)
    else:
        top = 50 * float.fromhex(source.value[1]) if source.kind == 'frustum' else 0
        ue.GeometryScript_Primitives.append_cone(mesh, options, ue.Transform(), base_radius=50, top_radius=top, height=100, **common)
    ue.GeometryScript_Normals.set_per_face_normals(mesh)
    result, outcome = ue.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(
        mesh, path, ue.GeometryScriptCreateNewStaticMeshAssetOptions())
    if result is None or outcome != ue.GeometryScriptOutcomePins.SUCCESS:
        raise RuntimeError(f'Cannot build geometry: {path}')
    ue.EditorAssetLibrary.set_metadata_tag(result, _RECIPE, recipe)
    if not ue.EditorAssetLibrary.save_loaded_asset(result):
        raise RuntimeError(f'Cannot save geometry: {path}')
    return result


def _asset(source, expected):
    ue = _ue()
    if isinstance(source, str):
        if source.startswith('/') and not source.endswith('.json'):
            source = ue.load_asset(source)
        elif expected == ue.StaticMesh:
            from mineprep.importer import import_block
            source = import_block(source)
    if not isinstance(source, expected):
        raise ValueError(f'Expected {expected.__name__}, got {source}')
    return source


@dataclass
class _Draw:
    mesh: object
    materials: tuple
    colored: bool
    parts: list

    def transforms(self):
        for part in self.parts:
            for point, angles, scale in zip(part.positions, part.angles, part.scales):
                yield _transform(point, angles, scale)


def _prepare(model):
    ue = _ue()
    sources, materials, prepared = {}, {}, {}
    for path, group in model._walk():
        draws = prepared[path] = {}
        for part in group._parts:
            if part.source not in sources:
                sources[part.source] = (_asset(part.source.value, ue.StaticMesh) if part.source.kind == 'asset'
                                        else _primitive(part.source))
            mesh = sources[part.source]
            slots = max(1, len(mesh.get_editor_property('static_materials')))
            if part.colored:
                if 'color' not in materials:
                    materials['color'] = _asset(COLOR_MATERIAL, ue.MaterialInterface)
                overrides = (materials['color'],) * slots
            elif part.material is not None:
                refs = part.material if isinstance(part.material, (list, tuple)) else [part.material] * slots
                if len(refs) != slots:
                    raise ValueError('material list must match the mesh material slot count')
                overrides = tuple(_asset(ref, ue.MaterialInterface) for ref in refs)
            else:
                overrides = ()
            key = mesh.get_path_name(), tuple(m.get_path_name() for m in overrides), part.colored
            if key not in draws:
                draws[key] = _Draw(mesh, overrides, part.colored, [])
            draws[key].parts.append(part)
    return prepared


def _write_custom_data(component, values):
    """Prefer the optional bulk bridge; official UE Python is a complete fallback."""
    ue = _ue()
    bulk = getattr(getattr(ue, 'mineprep', None), 'set_ism_custom_data', None)
    if bulk is not None:
        if not bulk(component, values.ravel().tolist(), 8):
            raise RuntimeError('Cannot write LowPoly instance data')
        return
    _write_custom_data_python(component, values)


def _write_custom_data_python(component, values):
    """Official Python fallback; upload all channels and refresh only at the end."""
    component.modify()
    component.set_num_custom_data_floats(8)
    last = len(values) - 1
    for index, row in enumerate(values):
        for channel, value in enumerate(row):
            if not component.set_custom_data_value(index, channel, float(value), index == last and channel == 7):
                raise RuntimeError('Cannot write LowPoly instance data')


def _tag(actor, prefix):
    tags = actor.tags if isinstance(actor, _ue().Actor) else actor.component_tags
    return next((str(t)[len(prefix):] for t in tags if str(t).startswith(prefix)), None)


def _mark(actor, owner, path=None):
    actor.component_tags = [*actor.component_tags, _OWNER + owner] + ([] if path is None else [_GROUP + path])


def _attach(component, parent, *, keep_world=False):
    ue = _ue()
    rule = ue.AttachmentRule.KEEP_WORLD if keep_world else ue.AttachmentRule.KEEP_RELATIVE
    if not component.attach_to_component(parent, '', rule, rule, rule, False):
        raise RuntimeError('Cannot attach LowPoly component')


def _rename_component(component, label):
    """Names share the Actor's namespace, including pending-destruction objects."""
    base = re.sub(r'\W', '_', label) or 'Part'
    name, suffix = base, 1
    while (existing := _ue().find_object(component.get_outer(), name)) is not None and existing != component:
        name, suffix = f'{base}_{suffix}', suffix+1
    component.modify()
    if not component.rename(name):
        raise RuntimeError(f'Cannot name LowPoly component: {name}')


def _component(root, parent, cls, label):
    """Official editor component creation: registered, transactional and serialized."""
    ue = _ue()
    subsystem = ue.get_engine_subsystem(ue.SubobjectDataSubsystem)
    library = ue.SubobjectDataBlueprintFunctionLibrary
    handles = subsystem.k2_gather_subobject_data_for_instance(root)
    handle = next(h for h in handles if library.get_associated_object(library.get_data(h)) == parent)
    root.modify()
    added, reason = subsystem.add_new_subobject(ue.AddNewSubobjectParams(parent_handle=handle, new_class=cls))
    component = library.get_associated_object(library.get_data(added))
    if not isinstance(component, cls):
        raise RuntimeError(f'Cannot create LowPoly component: {reason}')
    component.modify()
    component.set_mobility(ue.ComponentMobility.MOVABLE)
    _rename_component(component, label)
    return component


def _owned(root, owner):
    return [a for a in root.get_components_by_class(_ue().SceneComponent)
            if _tag(a, _OWNER) == owner]


class LowPolyModel(_Group):
    """Static low-poly recipe. Asset size/pivot is preserved; group pivots are local origins.

    Pure color data: linear RGBA, metallic, specular, roughness, emissive (8 floats).
    Color input is sRGB(A); material overrides and color/surface overrides are exclusive.
    Geometry sources and shared material assets are prepared before editing the level.
    """
    def __init__(self, name='Model'):
        super().__init__(name)

    def bake_skeletal(self, name=None, *, destination_path='/Game/mc/entity'):
        """Create a rigidly skinned Skeletal Mesh from this coloured box recipe."""
        return SkeletalModel.from_lowpoly(self).bake(name, destination_path=destination_path)

    @classmethod
    def from_blocks(cls, blocks, *, cell_size=1, cull=2, merge=3):
        from mineprep.structure import Blocks, _apply_cull, convert_to_packed_arrays
        from mineprep.math_tools import decode_rotation
        if not isinstance(blocks, Blocks):
            raise TypeError('from_blocks requires Blocks')
        unit = float(_xyz(cell_size, 'cell_size', positive=True)[0])
        if np.asarray(cell_size).ndim != 0 or cull not in (0, 1, 2, 3) or merge not in (0, 1, 2, 3):
            raise ValueError('cell_size must be scalar; cull and merge must be in 0..3')
        result = cls(blocks.name)
        for name, data in convert_to_packed_arrays(_apply_cull(blocks.copy_cells(), cull), merge=merge).items():
            angles = np.asarray([decode_rotation(float(code)) for code in data['rot']])
            result.add_many(name, data['pos'] * (unit / 100), scale=data['scale'] * unit,
                            pitch=angles[:, 0], yaw=angles[:, 1], roll=angles[:, 2])
        return result

    def spawn(self, *, position=(0, 0, 0), pitch=0, yaw=0, roll=0, scale=1, collision=False):
        ue = _ue()
        pose = _transform(position, (pitch, yaw, roll), scale)
        prepared = _prepare(self)
        if not any(prepared.values()):
            return None
        subsystem = ue.get_editor_subsystem(ue.EditorActorSubsystem)
        with ue.ScopedEditorTransaction('Create LowPoly model'):
            root = subsystem.spawn_actor_from_class(ue.Actor, ue.Vector())
            if root is None:
                raise RuntimeError('Cannot create LowPoly Actor')
            root.tags = [*root.tags, _ROOT + uuid4().hex]
            try:
                if root.root_component is None:
                    _component(root, root, ue.SceneComponent, 'Root')
                root.root_component.set_mobility(ue.ComponentMobility.MOVABLE)
                from mineprep.utils import set_actor_label
                set_actor_label(root, self.name)
                root.set_actor_transform(pose, False, False)
                root.set_folder_path(self.name)
                self._replace(root, prepared, collision)
            except Exception:
                subsystem.destroy_actor(root)
                raise
        return root

    def update(self, root, *, collision=False):
        """Keep the root pose and group identities; replace only owned render batches."""
        ue = _ue()
        if not isinstance(root, ue.Actor) or not ue.SystemLibrary.is_valid(root) or _tag(root, _ROOT) is None:
            raise ValueError('update requires a live LowPolyModel root Actor')
        if root.get_world() != ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world():
            raise ValueError('root must belong to the current editor world')
        prepared = _prepare(self)
        with ue.ScopedEditorTransaction('Update LowPoly model'):
            self._replace(root, prepared, collision)
        return root

    @staticmethod
    def component(root, path=''):
        """按持久化分组路径取组件句柄；空路径为根，不依赖组件对象名。"""
        owner = _tag(root, _ROOT)
        if owner is None:
            raise ValueError('component requires a LowPolyModel root Actor')
        from mineprep.handles import component
        if not path:
            return component(root.root_component)
        for group in _owned(root, owner):
            if _tag(group, _GROUP) == path:
                return component(group)
        raise KeyError(path)

    def _replace(self, root, prepared, collision):
        ue = _ue()
        from mineprep.structure import _add_transform_instances
        owner = _tag(root, _ROOT)
        old = _owned(root, owner)
        anchors = {_tag(a, _GROUP): a for a in old if _tag(a, _GROUP) is not None}
        anchors[''] = root.root_component
        created, snapshots, names = [], [], []
        try:
            for path, group in self._walk():
                if path and path not in anchors:
                    actor = _component(root, anchors[path.rpartition('/')[0]], ue.SceneComponent, path.replace('/', '_'))
                    created.append(actor)
                    _mark(actor, owner, path)
                    anchors[path] = actor
                for index, draw in enumerate(prepared[path].values()):
                    actor = _component(root, anchors[path], ue.InstancedStaticMeshComponent, f'LowPolyBuild_{uuid4().hex}')
                    created.append(actor)
                    names.append((actor, f'{path.replace("/", "_") or group.name}_{draw.mesh.get_name()}_{index}'))
                    _mark(actor, owner)
                    actor.set_visibility(False)
                    actor.set_static_mesh(draw.mesh)
                    actor.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
                    actor.set_editor_property('can_ever_affect_navigation', bool(collision))
                    _add_transform_instances(actor, draw.transforms(), update_navigation=collision)
                    for slot, material in enumerate(draw.materials):
                        actor.set_material(slot, material)
                    if draw.colored:
                        _write_custom_data(actor, np.concatenate([p.values for p in draw.parts]))
                    _attach(actor, anchors[path])
            # Commit poses only after all render batches have been populated.
            active = dict(self._walk())
            for path, group in active.items():
                if path:
                    actor = anchors[path]
                    snapshots.append((actor, actor.get_attach_parent(), actor.get_relative_transform()))
                    actor.modify()
                    _attach(actor, anchors[path.rpartition('/')[0]])
                    actor.set_relative_transform(
                        _transform(group.pivot, (group.pitch, group.yaw, group.roll), group.scale), False, False)
        except Exception:
            for actor, parent, pose in reversed(snapshots):
                if parent is not None:
                    _attach(actor, parent)
                actor.set_relative_transform(pose, False, False)
            for actor in reversed(created):
                actor.destroy_component(root)
            raise
        retained = {a for path, a in anchors.items() if path in active}
        obsolete = [a for a in old if a not in retained]
        # User attachments survive even when their generated parent is removed.
        for actor in obsolete:
            for child in actor.get_children_components(False):
                if _tag(child, _OWNER) != owner:
                    child.modify()
                    _attach(child, root.root_component, keep_world=True)
        for actor in reversed(obsolete):
            actor.modify()
            _rename_component(actor, f'LowPolyOld_{uuid4().hex}')
            actor.destroy_component(root)
        for actor, label in names:
            _rename_component(actor, label)
        for actor in created:
            actor.set_visibility(True)
