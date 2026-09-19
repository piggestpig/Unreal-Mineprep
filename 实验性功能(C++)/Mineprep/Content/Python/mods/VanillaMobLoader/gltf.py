"""Dependency-free rigid skin GLB writer. Matrices act on column vectors."""
import json
import re
import struct
from .geometry import IDENTITY, mul


def inverse_rigid(m):
    r = [[m[j][i] for j in range(3)] for i in range(3)]
    return tuple(tuple(r[i])+(-sum(r[i][j]*m[j][3] for j in range(3)),)
                 for i in range(3)) + ((0., 0., 0., 1.),)


def column_major(m):
    return [m[i][j] for j in range(4) for i in range(4)]


def binding_matrices(parts):
    # Model pixels -> glTF metres, a proper rotation followed by uniform scale.
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
