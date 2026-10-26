"""Image, array-mesh and UV-box inputs; Unreal is loaded only at its bridge."""
from os import PathLike
from time import perf_counter

import numpy as np

from ..core.building import COLORS, _state
from ..core.data import require_int
from ..core.voxel import MeshData, structure


def _resize_image(image, size, resample):
    """Resize in Pillow before exposing full-resolution image data to NumPy."""
    from PIL import Image
    if size is None:
        return image
    if type(size) is int:
        require_int('image size', size, 1, 2**31-4)
        ratio = min(1., size/max(image.size))
        target = tuple(max(1, round(value*ratio)) for value in image.size)
    else:
        if len(size) != 2:
            raise ValueError('size requires a longest-edge integer or (width, height)')
        for value in size:
            require_int('image size', value, 1, 2**31-4)
        target = tuple(size)
    if target == image.size:
        return image
    method = Image.Resampling.NEAREST if resample == 'nearest' else Image.Resampling.BOX
    return image.resize(target, method)


def image_rgba(source, *, size=None, resample='nearest'):
    if resample not in ('nearest', 'box'):
        raise ValueError('resample must be nearest or box')
    if (hasattr(source, 'get_path_name') or isinstance(source, str)
            and source.startswith(('/Game/', '/Engine/', '/Mineprep/'))):
        from .mesh_unreal import texture_file
        source = texture_file(source)
    if isinstance(source, (str, PathLike)):
        from PIL import Image
        with Image.open(source) as image:
            return np.asarray(_resize_image(image.convert('RGBA'), size, resample)).copy()
    image = np.asarray(source)
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] not in (3, 4) or not all(image.shape[:2]):
        raise ValueError('image requires a nonempty uint8 RGB/RGBA array or file')
    if size is not None:
        from PIL import Image
        image = np.asarray(_resize_image(Image.fromarray(image), size, resample))
    if image.shape[2] == 3:
        image = np.concatenate((image, np.full((*image.shape[:2], 1), 255, np.uint8)), axis=2)
    return image


def palette_colors(palette):
    from .resources import resolve_resource, default_models_dir
    from .block_colors import _texture_color, TINTS
    from ..core.blocks import BlockDef
    names = ([f'{c}_{family}' for family in ('concrete', 'wool', 'terracotta') for c in COLORS]
             if palette is None else list(palette))
    if not names or len(names) > 65535 or isinstance(palette, str):
        raise ValueError('palette requires a nonempty sequence/mapping of block names')
    names = list(dict.fromkeys(_state(n, {})[0] for n in names))
    colors = []
    models_dir = default_models_dir()
    for name in names:
        if name == 'air':
            raise ValueError('palette cannot contain air')
        resource = resolve_resource(BlockDef(name, 'builtin', name), models_dir)
        refs = dict(resource.textures)
        path = next((refs[k] for k in ('top', 'up', 'end', 'all', 'particle', 'cross') if k in refs), None)
        color = _texture_color(path) if path else None
        if color is None:
            raise ValueError(f'palette texture unavailable: {name}')
        if name in TINTS:
            color *= np.asarray(TINTS[name])/255.
        colors.append(np.rint(color).astype(np.uint8))
    return names, np.asarray(colors)


def validated(mesh, textures=None):
    """Check external arrays once; keep per-corner seams and source ordering."""
    if isinstance(mesh, dict):
        mesh = MeshData(**mesh)
    v = np.asarray(mesh.vertices, np.float64)
    t = np.asarray(mesh.triangles)
    if (v.ndim != 2 or v.shape[1:] != (3,) or not len(v) or not np.isfinite(v).all()
            or t.ndim != 2 or t.shape[1:] != (3,) or t.dtype.kind not in 'iu' or not len(t)
            or np.any(t < 0) or np.any(t >= len(v))):
        raise ValueError('mesh requires finite vertices and valid integer triangle indices')
    uv = np.zeros((len(t), 3, 2)) if mesh.uv is None else np.asarray(mesh.uv, float)
    ids = np.zeros(len(t), np.int64) if mesh.material_ids is None else np.asarray(mesh.material_ids)
    if (uv.shape != (len(t), 3, 2) or not np.isfinite(uv).all() or ids.shape != (len(t),)
            or ids.dtype.kind not in 'iu' or np.any(ids < 0) or np.any(ids >= len(mesh.materials))):
        raise ValueError('mesh UVs/material indices do not match triangles')
    overrides = dict(textures or {})
    if any(type(i) is not int or i < 0 or i >= len(mesh.materials) for i in overrides):
        raise ValueError('textures keys must be existing integer material-slot indices')
    materials = []
    for i, raw in enumerate(mesh.materials):
        mat = dict(raw)
        mat.setdefault('uv_valid', mesh.uv is not None)
        if i in overrides:
            mat['image'] = overrides[i]
        if mat.get('image') is not None:
            if mesh.uv is None or mat.get('uv_valid') is False:
                raise ValueError('textured mesh has no UVs')
            mat['image'] = image_rgba(mat['image'])
        factor = np.asarray(mat.get('factor', (1., 1., 1., 1.)), float)
        if factor.shape != (4,) or not np.isfinite(factor).all() or np.any((factor < 0) | (factor > 1)):
            raise ValueError('material factor requires linear RGBA in 0..1')
        wrap = tuple(mat.get('wrap', ('repeat', 'repeat')))
        if len(wrap) != 2 or any(w not in ('repeat', 'clamp', 'mirror') for w in wrap):
            raise ValueError('material wrap requires two repeat/clamp/mirror modes')
        mat.update(factor=factor, wrap=wrap)
        materials.append(mat)
    colors = None if mesh.colors is None else np.asarray(mesh.colors, float)
    if colors is not None and (colors.shape != (len(t), 3, 4) or not np.isfinite(colors).all()
                               or np.any((colors < 0) | (colors > 1))):
        raise ValueError('corner colors require linear RGBA [triangles,3,4] in 0..1')
    return MeshData(v, t.astype(np.int64), uv, ids, materials, colors)


def read(source, *, textures=None, up_axis=None):
    if isinstance(source, (MeshData, dict)):
        mesh = source
    else:
        if isinstance(source, (str, PathLike)) and not str(source).startswith(('/Game/', '/Engine/', '/Mineprep/')):
            raise ValueError('import model files into UE first, then pass a mesh asset path or component')
        if up_axis is not None:
            raise ValueError('UE inputs use the existing UE-to-MC axes; do not set up_axis')
        from .mesh_unreal import read_unreal
        mesh = read_unreal(source, textures=textures)
    mesh = validated(mesh, textures)
    if up_axis not in (None, 'y', 'z'):
        raise ValueError('up_axis must be y or z')
    if up_axis == 'z':
        mesh.vertices = mesh.vertices[:, [0, 2, 1]]
    return mesh


# Same face corner convention as VanillaMobLoader, with image-space UV corners.
FACE_CORNERS = {'east': (5, 1, 2, 6), 'west': (0, 4, 7, 3), 'down': (5, 4, 0, 1),
                'up': (2, 3, 7, 6), 'north': (1, 0, 3, 2), 'south': (4, 5, 6, 7)}


def boxes_mesh(source, boxes, texture_size=None):
    image = image_rgba(source)
    ts = np.asarray(texture_size or image.shape[1::-1], float)
    if ts.shape != (2,) or not np.isfinite(ts).all() or np.any(ts <= 0):
        raise ValueError('texture_size requires positive width,height')
    vertices, triangles, uv = [], [], []
    for box in boxes:
        lo, size = np.asarray(box['origin'], float), np.asarray(box['size'], float)
        if lo.shape != (3,) or size.shape != (3,) or not np.isfinite([lo, size]).all() or np.any(size < 0):
            raise ValueError('UV box requires finite origin and nonnegative size')
        inflate = float(box.get('inflate', 0.))
        a, b = lo-inflate, lo+size+inflate
        if not np.isfinite(inflate) or np.any(b < a):
            raise ValueError('invalid box inflate')
        x,y,z = a
        X,Y,Z = b
        points = np.array(((x,y,z),(X,y,z),(X,Y,z),(x,Y,z),(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z)))
        transform = np.asarray(box.get('transform', np.eye(4)), float)
        if transform.shape != (4, 4) or not np.isfinite(transform).all() or not np.allclose(transform[3], (0,0,0,1)):
            raise ValueError('box transform requires a finite affine 4x4 matrix')
        points = points@transform[:3, :3].T+transform[:3, 3]
        for face, spec in box['faces'].items():
            indices = FACE_CORNERS[face]
            rect = spec if not isinstance(spec, dict) else spec['uv']
            u1,v1,u2,v2 = np.asarray(rect, float)
            tex = (np.array(((u2,v1),(u1,v1),(u1,v2),(u2,v2))) if face in ('up','down')
                   else np.array(((u1,v2),(u2,v2),(u2,v1),(u1,v1))))
            if isinstance(spec, dict):
                rotation = spec.get('rotation', 0)
                if rotation not in (0, 90, 180, 270):
                    raise ValueError('UV face rotation requires 0/90/180/270')
                tex = np.roll(tex, -rotation//90, axis=0)
                if spec.get('mirror', False):
                    tex = tex[[1,0,3,2]]
            start = len(vertices)
            vertices.extend(points[list(indices)])
            triangles.extend(((start,start+1,start+2),(start,start+2,start+3)))
            uv.extend((tex[[0,1,2]]/ts, tex[[0,2,3]]/ts))
    return validated(MeshData(vertices, triangles, uv, materials=[dict(image=image, wrap=('clamp','clamp'))]))


def convert(mesh, *, scale, normalize, palette, alpha_cutoff, name, max_cells, stats=None):
    if not np.isfinite(alpha_cutoff) or not 0 <= alpha_cutoff <= 1:
        raise ValueError('alpha_cutoff must be in 0..1')
    require_int('max_cells', max_cells, 1, 2**63-1)
    start = perf_counter()
    names, rgb = palette_colors(palette)
    if stats is not None:
        stats['palette'] = perf_counter()-start
    return structure(mesh, names, rgb, scale=scale, normalize=normalize, alpha_cutoff=alpha_cutoff,
                     name=name, max_cells=max_cells, stats=stats)


def mesh_structure(source, *, resolution=128, palette=None, textures=None, up_axis=None,
                   alpha_cutoff=.5, name='Model', max_cells=4_000_000, _stats=None):
    require_int('resolution', resolution, 1, 2**31-4)
    start = perf_counter()
    mesh = read(source, textures=textures, up_axis=up_axis)
    extent = np.ptp(mesh.vertices, axis=0).max()
    if extent <= 0:
        raise ValueError('mesh has no spatial extent')
    if _stats is not None:
        _stats['read'] = perf_counter()-start
    return convert(mesh, scale=resolution/extent, normalize=True, palette=palette,
                   alpha_cutoff=alpha_cutoff, name=name, max_cells=max_cells, stats=_stats)


def uv_structure(source, boxes, *, scale=1, texture_size=None, palette=None,
                 alpha_cutoff=.5, name='UVModel', max_cells=4_000_000):
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('scale must be finite and positive')
    return convert(boxes_mesh(source, boxes, texture_size), scale=scale, normalize=False,
                   palette=palette, alpha_cutoff=alpha_cutoff, name=name, max_cells=max_cells)
