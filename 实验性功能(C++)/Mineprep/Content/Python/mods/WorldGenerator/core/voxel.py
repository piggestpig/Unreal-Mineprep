"""Sparse, deterministic surface voxelization of already decoded triangle arrays."""
from dataclasses import dataclass, field
from time import perf_counter

import numpy as np

from .building import Structure

BATCH = 262_144


@dataclass
class MeshData:
    """MC Y-up geometry. UVs are per triangle corner, image-space V points down.

    Materials contain an optional RGBA ``image`` and a linear RGBA ``factor``.
    Corner ``colors`` are linear RGBA. This is a transient input, not a new save format.
    """
    vertices: np.ndarray
    triangles: np.ndarray
    uv: np.ndarray = None
    material_ids: np.ndarray = None
    materials: list = field(default_factory=lambda: [dict(factor=(1., 1., 1., 1.))])
    colors: np.ndarray = None


def linear(rgb):
    return np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)


def srgb(rgb):
    return np.where(rgb <= .0031308, rgb*12.92, 1.055*np.maximum(rgb, 0)**(1/2.4)-.055)


def closest(points, triangle):
    """Closest point and barycentrics, including edges and obtuse triangles."""
    a, b, c = triangle
    ab, ac = b-a, c-a
    d00, d01, d11 = ab@ab, ab@ac, ac@ac
    ap = points-a
    v = ((ap@ab)*d11-(ap@ac)*d01)/(d00*d11-d01*d01)
    w = ((ap@ac)*d00-(ap@ab)*d01)/(d00*d11-d01*d01)
    bary = np.column_stack((1-v-w, v, w))
    projected = bary@triangle
    distance = np.sum((points-projected)**2, axis=1)
    distance[np.any(bary < 0, axis=1)] = np.inf
    for i, j in ((0, 1), (1, 2), (2, 0)):
        edge = triangle[j]-triangle[i]
        t = np.clip((points-triangle[i])@edge/(edge@edge), 0., 1.)
        q = triangle[i]+t[:, None]*edge
        d = np.sum((points-q)**2, axis=1)
        take = d < distance
        bary[take] = 0.
        bary[take, i], bary[take, j] = 1-t[take], t[take]
        distance[take] = d[take]
    return distance, bary


def _patches(triangle):
    pending = [triangle]
    while pending:
        t = pending.pop()
        if np.ptp(t, axis=0).max() <= 12:
            yield t
            continue
        edges = np.roll(t, -1, axis=0)-t
        a = int(np.argmax(np.sum(edges*edges, axis=1)))
        b, c = (a+1) % 3, (a+2) % 3
        mid = (t[a]+t[b])/2
        pending.extend((np.array((t[a], mid, t[c])), np.array((mid, t[b], t[c]))))


def _overlap(triangle, lo, hi):
    q = np.stack(np.meshgrid(*(np.arange(a, b+1) for a, b in zip(lo, hi)),
                             indexing='ij'), axis=-1).reshape(-1, 3)
    edges = np.roll(triangle, -1, axis=0)-triangle
    axes = np.concatenate((np.eye(3), np.cross(edges[0], edges[1])[None],
                           np.cross(edges[:, None], np.eye(3)[None]).reshape(-1, 3)))
    axes = axes[np.linalg.norm(axes, axis=1) > 1e-12]
    p, centers = triangle@axes.T, (q+.5)@axes.T
    radius = .5*np.abs(axes).sum(axis=1)
    hit = ((centers+radius >= p.min(axis=0)-1e-9)
           & (centers-radius <= p.max(axis=0)+1e-9)).all(axis=1)
    return q[hit]


def _alpha_rectangles(mask):
    """Merge painted scanline runs into rectangles, once per material/operation."""
    active, rectangles = {}, []
    for y, row in enumerate(mask):
        edges = np.flatnonzero(np.diff(np.r_[False, row, False]))
        spans = set(zip(edges[::2], edges[1::2]))
        for span in active.keys()-spans:
            rectangles.append((*span, active[span], y))
        active = {span: active.get(span, y) for span in spans}
    rectangles.extend((*span, start, len(mask)) for span, start in active.items())
    # [u0,v0,u1,v1], with stable order independent of set iteration.
    return np.array(sorted((a, c, b, d) for a,b,c,d in rectangles), float).reshape(-1, 4)


def _clip_uv(uv, bounds):
    """Clip in barycentric space so positions, UV seams and corner colors agree."""
    polygon = np.eye(3)
    for axis, bound, sign in ((0,bounds[0],1),(1,bounds[1],1),
                              (0,bounds[2],-1),(1,bounds[3],-1)):
        if not len(polygon):
            break
        distance = (polygon@uv[:, axis]-bound)*sign
        result = []
        for i in range(len(polygon)):
            a, b = polygon[i-1], polygon[i]
            da, db = distance[i-1], distance[i]
            if (da >= 0) != (db >= 0):
                result.append(a+(b-a)*da/(da-db))
            if db >= 0:
                result.append(b)
        polygon = np.asarray(result).reshape(-1, 3)
    return polygon


def _painted_triangles(uv, alpha, wrap):
    """Trim transparent geometry before voxelization, rather than reject its center."""
    if alpha is None:
        yield None, None
        return
    mask, rectangles = alpha
    if not len(rectangles):
        return
    low, high = uv.min(axis=0), uv.max(axis=0)
    h, w = mask.shape
    # Most atlas faces lie entirely in one painted region: retain their fast path.
    if np.all(low >= 0) and np.all(high <= 1):
        a = np.clip(np.floor(low*[w,h]).astype(int), 0, [w-1,h-1])
        b = np.clip(np.maximum(a+1, np.ceil(high*[w,h]).astype(int)), 1, [w,h])
        if mask[a[1]:b[1], a[0]:b[0]].all():
            yield None, None
            return
    base = rectangles/[w,h,w,h]
    tiles = [range(int(np.floor(low[i])), max(int(np.floor(low[i])), int(np.ceil(high[i]))-1)+1)
             if mode != 'clamp' else (0,) for i,mode in enumerate(wrap)]
    for x in tiles[0]:
        for y in tiles[1]:
            mapped = base.copy()
            for axis, (tile, mode) in enumerate(zip((x,y),wrap)):
                i,j = axis,axis+2
                if mode == 'clamp':
                    mapped[mapped[:,i] == 0,i] = min(low[axis],0.)
                    mapped[mapped[:,j] == 1,j] = max(high[axis],1.)
                elif mode == 'mirror' and tile % 2:
                    mapped[:,[i,j]] = tile+1-mapped[:,[j,i]]
                else:
                    mapped[:,[i,j]] += tile
            hit = ((mapped[:,:2] <= high) & (mapped[:,2:] >= low)).all(axis=1)
            for rect in mapped[hit]:
                polygon = _clip_uv(uv,rect)
                for i in range(1,len(polygon)-1):
                    yield polygon[[0,i,i+1]], rect


def _sample(mesh, tid, bary, bounds=None):
    material = mesh.materials[int(mesh.material_ids[tid])]
    factor = np.asarray(material.get('factor', (1., 1., 1., 1.)), float)
    rgba = np.broadcast_to(factor, (len(bary), 4)).copy()
    image = material.get('image')
    if image is not None:
        uv = bary@mesh.uv[tid]
        lo, hi = mesh.uv[tid].min(axis=0), mesh.uv[tid].max(axis=0)
        if bounds is not None:
            lo, hi = np.maximum(lo,bounds[:2]), np.minimum(hi,bounds[2:])
        # Edge projections belong to this UV region, never the adjacent atlas part.
        inset = np.minimum((hi-lo)/2, 1e-9/np.array(image.shape[1::-1]))
        uv = np.clip(uv, lo+inset, hi-inset)
        for axis, mode in enumerate(material.get('wrap', ('repeat', 'repeat'))):
            if mode == 'repeat':
                uv[:, axis] %= 1.
            elif mode == 'mirror':
                uv[:, axis] = 1-np.abs(uv[:, axis] % 2-1)
        h, w = image.shape[:2]
        xy = np.clip(np.floor(uv*[w, h]).astype(np.int64), (0, 0), (w-1, h-1))
        tex = image[xy[:, 1], xy[:, 0]].astype(float)/255.
        rgba[:, :3] *= linear(tex[:, :3])
        rgba[:, 3] *= tex[:, 3]
    if mesh.colors is not None:
        rgba *= bary@mesh.colors[tid]
    rgb = np.rint(np.clip(srgb(rgba[:, :3]), 0, 1)*255).astype(np.uint8)
    return rgb, rgba[:, 3]


def _winners(xyz, rgb, distance, tids):
    # Stable source-triangle priority on exact ties, independent of batching.
    order = np.lexsort((tids, distance, xyz[:, 2], xyz[:, 1], xyz[:, 0]))
    p = xyz[order]
    keep = np.r_[True, np.any(p[1:] != p[:-1], axis=1)]
    at = order[keep]
    return xyz[at], rgb[at], distance[at], tids[at]


def rasterize(mesh, *, scale, normalize, alpha_cutoff, max_cells, stats=None):
    started = perf_counter()
    vertices = mesh.vertices.astype(np.float64)*scale
    if normalize:
        vertices -= vertices.min(axis=0)
    origin = np.floor(vertices.min(axis=0)).astype(np.int64)
    size = np.maximum(1, np.ceil(vertices.max(axis=0)).astype(np.int64)-origin)
    end = origin+size-1
    retained = (np.empty((0, 3), np.int64), np.empty((0, 3), np.uint8),
                np.empty(0), np.empty(0, np.int64))
    pending, count = [], 0
    timing = dict(geometry=0., sampling=0., reduction=0.)
    masks = []
    for material in mesh.materials:
        image = material.get('image')
        if image is None:
            masks.append(None)
            continue
        factor = material.get('factor',(1,1,1,1))[3]
        mask = ((image[:,:,3] >= alpha_cutoff*255/factor) & (image[:,:,3] > 0)
                if factor > 0 else np.zeros(image.shape[:2],bool))
        masks.append(None if mask.all() else (mask,_alpha_rectangles(mask)))

    def flush():
        nonlocal retained, pending, count
        start = perf_counter()
        columns = tuple(np.concatenate([r[i] for r in pending]) for i in range(4))
        retained = _winners(*(np.concatenate((a, b)) for a, b in zip(retained, columns)))
        if len(retained[0]) > max_cells:
            raise ValueError('voxelized surface exceeds max_cells')
        pending, count = [], 0
        timing['reduction'] += perf_counter()-start

    for tid, indices in enumerate(mesh.triangles):
        triangle = vertices[indices]
        if np.linalg.norm(np.cross(triangle[1]-triangle[0], triangle[2]-triangle[0])) < 1e-12:
            continue
        material_id = int(mesh.material_ids[tid])
        wrap = mesh.materials[material_id].get('wrap',('repeat','repeat'))
        for weights, bounds in _painted_triangles(mesh.uv[tid],masks[material_id],wrap):
            painted = triangle if weights is None else weights@triangle
            if np.linalg.norm(np.cross(painted[1]-painted[0],painted[2]-painted[0])) < 1e-12:
                continue
            # Nonzero extents are half-open; a flat face still owns one cell layer.
            for patch in _patches(painted):
                start = perf_counter()
                low, high = patch.min(axis=0), patch.max(axis=0)
                a = np.floor(low).astype(np.int64)
                b = np.maximum(a,np.ceil(high).astype(np.int64)-1)
                xyz = _overlap(patch,np.clip(a,origin,end),np.clip(b,origin,end))
                timing['geometry'] += perf_counter()-start
                if not len(xyz):
                    continue
                start = perf_counter()
                distance, bary = closest(xyz+.5, painted)
                rgb, alpha = _sample(mesh,tid,bary if weights is None else bary@weights,bounds)
                visible = (alpha >= alpha_cutoff) & (alpha > 0)
                n = int(visible.sum())
                timing['sampling'] += perf_counter()-start
                if n:
                    if pending and count+n > BATCH:
                        flush()
                    pending.append((xyz[visible],rgb[visible],distance[visible],np.full(n,tid)))
                    count += n
    if pending:
        flush()
    if stats is not None:
        timing['geometry'] = perf_counter()-started-timing['sampling']-timing['reduction']
        stats.update(timing)
    return retained[0], retained[1], origin, size


def match_colors(rgb, palette_rgb):
    """Match unique sRGB colours in Lab, shared by mesh shells and image columns."""
    import cv2
    unique, inverse = np.unique(rgb, axis=0, return_inverse=True)
    lab = cv2.cvtColor(unique.astype(np.float32).reshape(1, -1, 3)/255., cv2.COLOR_RGB2LAB)[0] if len(unique) else np.empty((0, 3))
    target = cv2.cvtColor(palette_rgb.astype(np.float32)[None]/255., cv2.COLOR_RGB2LAB)[0]
    ids = np.empty(len(lab), np.uint16)
    for offset in range(0, len(lab), 4096):
        diff = lab[offset:offset+4096, None]-target
        ids[offset:offset+4096] = np.argmin(np.sum(diff*diff, axis=2), axis=1)
    return ids[inverse]


def structure(mesh, names, palette_rgb, *, scale, normalize, alpha_cutoff, name,
              max_cells, stats=None):
    xyz, rgb, origin, size = rasterize(mesh, scale=scale, normalize=normalize,
                                      alpha_cutoff=alpha_cutoff, max_cells=max_cells, stats=stats)
    start = perf_counter()
    types = match_colors(rgb, palette_rgb)
    if stats is not None:
        stats['matching'] = perf_counter()-start
    start = perf_counter()
    result = Structure(name, tuple(origin), tuple(size), tuple((n, ()) for n in names), xyz, types)
    if stats is not None:
        stats['structure'] = perf_counter()-start
    return result
