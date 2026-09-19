"""Independent CEM template geometry adapter (no Unreal or Blender dependency).

Format reference: Blockbench js/formats/optifine/optifine_jem.js.
Templates retain Ewan Howell's upstream rights. This adapter consumes the
Blockbench-exported template dialect, not arbitrary OptiFine runtime models.
All matrices below act on column vectors; angles use intrinsic ZYX.
"""
from dataclasses import dataclass, field
import hashlib
import math


IDENTITY = ((1., 0., 0., 0.), (0., 1., 0., 0.),
            (0., 0., 1., 0.), (0., 0., 0., 1.))
FACE_CORNERS = {
    'east': (5, 1, 2, 6), 'west': (0, 4, 7, 3),
    'down': (5, 4, 0, 1), 'up': (2, 3, 7, 6),
    'north': (1, 0, 3, 2), 'south': (4, 5, 6, 7),
}


def vec(value, default=(0., 0., 0.)):
    values = tuple(float(x) for x in (default if value is None else value))
    if len(values) != 3 or not all(math.isfinite(x) for x in values):
        raise ValueError('Invalid model vector')
    return values


def mul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(4))
                       for j in range(4)) for i in range(4))


def transform(matrix, point):
    return tuple(sum(matrix[i][j] * point[j] for j in range(3)) + matrix[i][3]
                 for i in range(3))


def local_matrix(offset, angles):
    x, y, z = (math.radians(v) for v in angles)
    cx, cy, cz, sx, sy, sz = math.cos(x), math.cos(y), math.cos(z), math.sin(x), math.sin(y), math.sin(z)
    # Rz @ Ry @ Rx, matching THREE.Euler(..., 'ZYX').
    return ((cz*cy, cz*sy*sx-sz*cx, cz*sy*cx+sz*sx, offset[0]),
            (sz*cy, sz*sy*sx+cz*cx, sz*sy*cx-cz*sx, offset[1]),
            (-sy, cy*sx, cy*cx, offset[2]), (0., 0., 0., 1.))


def to_ue(point):
    x, y, z = point
    return (-z * 6.25, x * 6.25, y * 6.25)


def subtract(a, b):
    return tuple(x-y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def uv_rects(box, size, mirror=False):
    if 'textureOffset' not in box:
        return {name: tuple(float(v) for v in box['uv'+name.title()])
                for name in FACE_CORNERS if 'uv'+name.title() in box}

    u, v = map(float, box['textureOffset'])
    w, h, d = size
    rects = {'east': (u, v+d, u+d, v+d+h),
            'north': (u+d, v+d, u+d+w, v+d+h),
            'west': (u+d+w, v+d, u+2*d+w, v+d+h),
            'south': (u+2*d+w, v+d, u+2*(d+w), v+d+h),
            'up': (u+d+w, v+d, u+d, v),
            'down': (u+d+2*w, v, u+d+w, v+d)}
    if mirror:
        rects = {face: (c,b,a,d) for face,(a,b,c,d) in rects.items()}
        rects['east'], rects['west'] = rects['west'], rects['east']
    return rects


@dataclass
class MeshData:
    vertices: list = field(default_factory=list)
    triangles: list = field(default_factory=list)
    uv: list = field(default_factory=list)
    normals: list = field(default_factory=list)
    groups: list = field(default_factory=list)
    parts: list = field(default_factory=list)
    vertex_parts: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    single_sided: bool = False
    triangle_materials: list = field(default_factory=list)
    materials: list = field(default_factory=list)


def named_delta(name, amount):
    """Deterministic [-amount, amount] from a part name; 0 when amount is 0."""
    if not amount:
        return 0.
    n = int.from_bytes(hashlib.sha256(str(name).casefold().encode('utf-8')).digest()[:8], 'big')
    return n / 18446744073709551615. * 2. * amount - amount


def build_geometry(model, alpha=None, expansion=0., random_scale=0.):
    """Bake the default editor pose; optional alpha(rect, texture_size) tests paint.

    Each face owns its vertices, preserving UV seams and hard edges. Thin
    cuboids retain painted faces with the default two-sided material. Opposite
    painted faces get a tiny separation, as in Blockbench's zero-size display.
    random_scale adds a name-stable extra inflate/deflate per part.
    """
    result = MeshData()
    if not math.isfinite(expansion) or expansion < 0:
        raise ValueError('Expansion must be finite and non-negative')
    if not math.isfinite(random_scale) or random_scale < 0:
        raise ValueError('Random scale must be finite and non-negative')
    texture_size = tuple(float(v) for v in model.get('textureSize', (64, 64)))
    if len(texture_size) != 2 or not all(math.isfinite(v) and v > 0 for v in texture_size):
        raise ValueError('Invalid textureSize')

    def box_faces(box, origin, matrix, root, mirror, part_index, delta=0.):
        coords = tuple(float(v) for v in box['coordinates'])
        if len(coords) != 6 or not all(math.isfinite(v) for v in coords):
            raise ValueError('Invalid box coordinates')
        low, size = coords[:3], coords[3:]
        if any(v < 0 for v in size):
            raise ValueError('Negative box dimensions are not supported')
        if root:
            low = subtract(low, origin)

        inflate = float(box.get('sizeAdd', 0))
        if not math.isfinite(inflate):
            raise ValueError('Invalid sizeAdd')
        if 'sizesAdd' in box:
            raise ValueError('Per-axis sizesAdd is outside the template dialect')

        lo = [v-inflate for v in low]
        hi = [v+s+inflate for v, s in zip(low, size)]
        if any(b < a for a, b in zip(lo, hi)):
            raise ValueError('sizeAdd inverted a box')
        grow = expansion + delta
        flat = any(abs(b-a) < 1e-8 for a,b in zip(lo,hi))
        if not flat:
            lo = [v-grow for v in lo]
            hi = [v+grow for v in hi]

        x, y, z = lo
        X, Y, Z = hi
        points = [(x,y,z),(X,y,z),(X,Y,z),(x,Y,z),
                  (x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z)]
        rects = uv_rects(box, size, mirror)

        candidates = []
        for name, indices in FACE_CORNERS.items():
            rect = rects.get(name)
            if rect is None:
                continue
            if len(rect) != 4 or not all(math.isfinite(v) for v in rect):
                raise ValueError('Invalid face UV')
            area = sum(v*v for v in cross(subtract(points[indices[1]], points[indices[0]]),
                                         subtract(points[indices[2]], points[indices[0]])))
            if area < 1e-16:
                continue
            candidates.append((name, indices, rect))

        thin = any(abs(b-a) < 1e-8 for a, b in zip(lo, hi))
        if thin and candidates:
            usable = [f for f in candidates if abs((f[2][2]-f[2][0])*(f[2][3]-f[2][1])) > 1e-8]
            if alpha:
                usable = [f for f in usable if alpha(f[2], texture_size)]
            if not usable:
                return
            result.single_sided = True
            candidates = usable

        for face, indices, rect in candidates:
            u1, v1, u2, v2 = rect
            tw, th = texture_size
            # Blockbench setShape corner mapping, in image-space V coordinates.
            if face in ('up', 'down'):
                uv = [(u2/tw,v1/th),(u1/tw,v1/th),(u1/tw,v2/th),(u2/tw,v2/th)]
            else:
                uv = [(u1/tw,v2/th),(u2/tw,v2/th),(u2/tw,v1/th),(u1/tw,v1/th)]
            pts = [to_ue(transform(matrix, points[i])) for i in indices]

            # Coordinate conversion has det=-1. Mirroring affects UVs only.
            pts.reverse()
            uv.reverse()

            n = cross(subtract(pts[1], pts[0]), subtract(pts[2], pts[0]))
            length = math.sqrt(sum(v*v for v in n))
            n = tuple(v/length for v in n)
            if thin:
                offset = max(grow, .0005 if len(candidates)>1 else 0.)
                pts = [tuple(p[i]+n[i]*offset*6.25 for i in range(3)) for p in pts]
            start = len(result.vertices)
            result.vertices.extend(pts)
            result.vertex_parts.extend([part_index]*4)
            result.uv.extend(uv)
            result.normals.extend([n]*4)

            # UE's front-face winding is opposite the mathematical cross product.
            # Keep outward normals and corner UVs, reverse only triangle indices.
            result.triangles.extend([(start,start+2,start+1),(start,start+3,start+2)])
            result.groups.extend([part_index]*2)

    def walk(part, parent_origin=(0.,0.,0.), parent_matrix=IDENTITY, parent=-1, depth=0):
        if depth > 64:
            raise ValueError('Model nesting exceeds 64')
        if part.get('model') or part.get('sprites') or part.get('texture') or part.get('scale', 1) != 1:
            raise ValueError('External parts, sprites, per-part textures and scale are not supported in this stage')
        if part.get('invertAxis') not in (None, 'xy'):
            raise ValueError('Not a Blockbench-exported template: invertAxis')

        t = vec(part.get('translate'))
        if depth == 0:
            origin = tuple(-v for v in t)
        elif depth == 1:
            origin = t
        else:
            origin = tuple(a+b for a,b in zip(parent_origin,t))

        rotation = vec(part.get('rotate'))
        matrix = mul(parent_matrix, local_matrix(subtract(origin,parent_origin), rotation))
        index = len(result.parts)
        name = str(part.get('part') or part.get('id') or f'part_{index}')
        result.parts.append(dict(name=name, parent=parent, origin=origin, rotation=rotation, matrix=matrix))
        mirror = 'u' in str(part.get('mirrorTexture', ''))
        delta = named_delta(name, random_scale)

        for box in part.get('boxes', []):
            box_faces(box, origin, matrix, depth == 0, mirror, index, delta)
        for child in part.get('submodels', []):
            walk(child, origin, matrix, index, depth+1)

    for part in model.get('models', []):
        walk(part)
    if not result.triangles:
        raise ValueError('Template has no renderable faces')
    result.warnings = list(dict.fromkeys(result.warnings))
    return result
