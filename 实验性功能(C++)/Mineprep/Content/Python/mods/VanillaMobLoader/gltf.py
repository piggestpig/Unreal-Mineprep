"""生物模型 GLB 编码与刚性蒙皮头身拆分。"""
import copy
import json
import re
import struct
from .geometry import IDENTITY, mul


FORMATS = {5121: 'B', 5123: 'H', 5125: 'I', 5126: 'f'}
WIDTHS = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def inverse_rigid(m):
    r = [[m[j][i] for j in range(3)] for i in range(3)]
    return tuple(tuple(r[i])+(-sum(r[i][j]*m[j][3] for j in range(3)),)
                 for i in range(3)) + ((0., 0., 0., 1.),)


def column_major(m):
    return [m[i][j] for j in range(4) for i in range(4)]


def binding_matrices(parts):
    # 将模型像素坐标转换为 glTF 米制坐标（正交旋转 + 1/16 均匀缩放）
    basis = ((0.,0.,-1.,0.), (0.,1.,0.,0.), (1.,0.,0.,0.), (0.,0.,0.,1.))
    inverse = inverse_rigid(basis)
    result = [IDENTITY]
    for part in parts:
        m = mul(mul(basis, part['matrix']), inverse)
        result.append(tuple(tuple(row[j] / 16 if j == 3 and i < 3 else row[j]
                                  for j in range(4)) for i,row in enumerate(m)))
    return result


def encode(geometry, name):
    count = len(geometry.vertices)
    if len(geometry.vertex_parts) != count or len(geometry.parts) >= 65535:
        raise ValueError('Invalid skin vertex ownership or too many bones')
    if any(p < 0 or p >= len(geometry.parts) for p in geometry.vertex_parts):
        raise ValueError('Invalid skin joint')

    blob, views, accessors = bytearray(), [], []

    def accessor(rows, fmt, component, kind, bounds=False):
        rows = list(rows)
        flat = [v for row in rows for v in row]
        blob.extend(b'\0' * (-len(blob) % 4))
        raw = struct.pack('<' + str(len(flat)) + fmt, *flat)
        views.append(dict(buffer=0, byteOffset=len(blob), byteLength=len(raw)))
        blob.extend(raw)
        acc = dict(bufferView=len(views)-1, componentType=component, count=len(rows), type=kind)
        if bounds:
            acc.update(min=list(map(min, zip(*rows))), max=list(map(max, zip(*rows))))
        accessors.append(acc)
        return len(accessors)-1

    positions = [(x/100,z/100,y/100) for x,y,z in geometry.vertices]
    attributes = {
        'POSITION': accessor(positions,'f',5126,'VEC3',True),
        'NORMAL': accessor(((x,z,y) for x,y,z in geometry.normals),'f',5126,'VEC3'),
        'TEXCOORD_0': accessor(geometry.uv,'f',5126,'VEC2'),
        'JOINTS_0': accessor(((p+1,0,0,0) for p in geometry.vertex_parts),'H',5123,'VEC4'),
        'WEIGHTS_0': accessor(((1.,0.,0.,0.) for _ in positions),'f',5126,'VEC4')}
    primitives = []
    slot_names = ['VML_'+str(i) for i in range(len(geometry.materials))]
    if slot_names:
        if len(geometry.triangle_materials) != len(geometry.triangles):
            raise ValueError('Invalid triangle material assignments')
        for slot in range(len(slot_names)):
            tris = [t for t,m in zip(geometry.triangles,geometry.triangle_materials) if m == slot]
            indices = accessor(((i,) for t in tris for i in t),'I',5125,'SCALAR')
            primitives.append(dict(attributes=attributes, indices=indices, material=slot))
    else:
        indices = accessor(((i,) for t in geometry.triangles for i in t),'I',5125,'SCALAR')
        primitives.append(dict(attributes=attributes, indices=indices))

    worlds = binding_matrices(geometry.parts)
    ibm = accessor((column_major(inverse_rigid(m)) for m in worlds),'f',5126,'MAT4')
    nodes, used, mapping = [dict(name='root')], {'root'}, []
    for i, part in enumerate(geometry.parts):
        bone = re.sub(r'[^a-zA-Z0-9_]', '_', part['name']).strip('_') or 'part'
        bone = bone[:80]
        while bone.lower() in used:
            bone += '_' + str(i)
        used.add(bone.lower())

        parent = part['parent']+1
        if parent < 0 or parent > i:
            raise ValueError('Bones must be ordered parent before child')
        local = mul(inverse_rigid(worlds[parent]), worlds[i+1])
        nodes.append(dict(name=bone, matrix=column_major(local)))
        nodes[parent].setdefault('children', []).append(i+1)
        mapping.append(dict(part=i, original=part['name'], bone=bone))

    mesh_node = len(nodes)
    nodes.append(dict(name=name, mesh=0, skin=0))
    document = dict(asset=dict(version='2.0', generator='Mineprep VanillaMobLoader'),
                    scene=0, scenes=[dict(nodes=[0,mesh_node])], nodes=nodes,
                    skins=[dict(name=name+'_Skeleton', skeleton=0, joints=list(range(mesh_node)), inverseBindMatrices=ibm)],
                    meshes=[dict(name=name, primitives=primitives)],
                    accessors=accessors, bufferViews=views, buffers=[dict(byteLength=len(blob))])
    if slot_names:
        document['materials'] = [dict(name=n) for n in slot_names]

    text = json.dumps(document, separators=(',',':'), ensure_ascii=True).encode('utf8')
    text += b' ' * (-len(text)%4)
    blob.extend(b'\0' * (-len(blob)%4))
    glb = (struct.pack('<III',0x46546C67,2,28+len(text)+len(blob)) +
           struct.pack('<I4s',len(text),b'JSON') + text +
           struct.pack('<I4s',len(blob),b'BIN\0') + blob)
    return glb, mapping


def split_head(data):
    """按 head 分支拆分 Mineprep 刚性蒙皮 GLB，保留材质与身体骨架。"""
    from mc_model import read_glb, pack_glb

    original, binary = read_glb(data)
    skin, = original['skins']
    nodes = original['nodes']
    joints = skin['joints']
    parents = {child: i for i in joints for child in nodes[i].get('children', [])}
    head = next((i for i in joints if nodes[i]['name'] == 'head'), None)
    if head is None:
        raise ValueError('模型没有 head 骨骼')
    if any(any(key in nodes[i] for key in ('translation', 'rotation', 'scale')) for i in joints):
        raise ValueError('拆分需要 Mineprep GLB 的矩阵绑定姿势')
    worlds = {}

    def world(i):
        if i not in worlds:
            values = nodes[i].get('matrix', column_major(IDENTITY))
            local = tuple(tuple(values[col * 4 + row] for col in range(4)) for row in range(4))
            worlds[i] = mul(world(parents[i]), local) if i in parents else local
        return worlds[i]

    for i in joints:
        world(i)
    head_inverse = inverse_rigid(worlds[head])
    head_nodes = {head}
    pending = list(nodes[head].get('children', []))
    while pending:
        i = pending.pop()
        head_nodes.add(i)
        pending.extend(nodes[i].get('children', []))
    selected = [i for i in joints if i in head_nodes]
    head_indices = {old: new for new, old in enumerate(selected)}
    if any(abs(sum(m[k][i] * m[k][j] for k in range(3)) - float(i == j)) > 1e-5
           for m in worlds.values() for i in range(3) for j in range(3)):
        raise ValueError('拆分需要无缩放的骨骼绑定姿势')

    def read(index):
        accessor = original['accessors'][index]
        view = original['bufferViews'][accessor['bufferView']]
        fmt = '<' + FORMATS[accessor['componentType']] * WIDTHS[accessor['type']]
        stride = view.get('byteStride', struct.calcsize(fmt))
        start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
        return [struct.unpack_from(fmt, binary, start + i * stride) for i in range(accessor['count'])]

    output = {}
    for part in ('body', 'head'):
        document = copy.deepcopy(original)
        blob = bytearray(binary)

        def append(rows, component, kind):
            width = WIDTHS[kind]
            blob.extend(b'\0' * (-len(blob) % 4))
            start = len(blob)
            fmt = '<' + FORMATS[component] * width
            for row in rows:
                blob.extend(struct.pack(fmt, *row))
            view = len(document['bufferViews'])
            document['bufferViews'].append(dict(buffer=0, byteOffset=start, byteLength=len(blob)-start))
            accessor = dict(bufferView=view, componentType=component, count=len(rows), type=kind)
            if kind == 'VEC3' and rows:
                accessor.update(min=list(map(min, zip(*rows))), max=list(map(max, zip(*rows))))
            document['accessors'].append(accessor)
            return len(document['accessors']) - 1

        primitives = []
        for primitive in (p for mesh in original['meshes'] for p in mesh['primitives']):
            attributes = {name: read(index) for name, index in primitive['attributes'].items()}
            owners = []
            for ids, weights in zip(attributes['JOINTS_0'], attributes['WEIGHTS_0']):
                active = [joints[j] for j, w in zip(ids, weights) if w > 0]
                if len(active) != 1:
                    raise ValueError('头身拆分需要刚性蒙皮')
                owners.append(active[0] in head_nodes)
            indices = [row[0] for row in read(primitive['indices'])]
            kept = []
            for offset in range(0, len(indices), 3):
                triangle = indices[offset:offset+3]
                flags = [owners[v] for v in triangle]
                if any(flags) and not all(flags):
                    raise ValueError('存在跨越头身边界的三角面')
                if all(flags) == (part == 'head'):
                    kept.extend(triangle)
            if not kept:
                continue
            vertices = sorted(set(kept))
            remap = {old: new for new, old in enumerate(vertices)}
            attrs = {}
            for name, rows in attributes.items():
                values = [rows[i] for i in vertices]
                info = original['accessors'][primitive['attributes'][name]]
                if part == 'head' and name in ('POSITION', 'NORMAL'):
                    values = [tuple(sum(head_inverse[axis][j] * p[j] for j in range(3))
                                    + (head_inverse[axis][3] if name == 'POSITION' else 0)
                                    for axis in range(3)) for p in values]
                if part == 'head' and name == 'JOINTS_0':
                    values = [tuple(head_indices.get(joints[j], 0) for j in ids)
                              for ids in values]
                attrs[name] = append(values, info['componentType'], info['type'])
            result = copy.deepcopy(primitive)
            result['attributes'] = attrs
            result['indices'] = append([(remap[i],) for i in kept], 5125, 'SCALAR')
            primitives.append(result)

        if part == 'head':
            head_tree = []
            for old in selected:
                node = copy.deepcopy(nodes[old])
                node['children'] = [head_indices[c] for c in node.get('children', []) if c in head_indices]
                if old == head:
                    node['matrix'] = column_major(IDENTITY)
                head_tree.append(node)
            document['nodes'] = head_tree
            document['skins'][0]['joints'] = list(range(len(selected)))
            document['skins'][0]['skeleton'] = 0
            bind = [column_major(inverse_rigid(mul(head_inverse, worlds[i]))) for i in selected]
            document['skins'][0]['inverseBindMatrices'] = append(bind, 5126, 'MAT4')
        else:
            mapping = {old: new for new, old in enumerate(joints)}
            document['nodes'] = copy.deepcopy([nodes[i] for i in joints])
            for node in document['nodes']:
                node['children'] = [mapping[c] for c in node.get('children', []) if c in mapping]
            document['skins'][0]['joints'] = list(range(len(joints)))
            document['skins'][0]['skeleton'] = 0
        mesh_node = len(document['nodes'])
        document['nodes'].append(dict(name=part, mesh=0, skin=0))
        document['meshes'] = [dict(name=part, primitives=primitives)]
        document['scenes'] = [dict(nodes=[0, mesh_node])]
        document['scene'] = 0
        document['buffers'][0]['byteLength'] = len(blob)
        if not primitives:
            raise ValueError('模型没有可独立拆出的' + ('头部' if part == 'head' else '身体') + '几何')
        output[part] = pack_glb(document, blob)
    return output
