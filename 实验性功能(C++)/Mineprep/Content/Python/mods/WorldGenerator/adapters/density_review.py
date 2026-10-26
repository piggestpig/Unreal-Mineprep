"""Offline cutaway of actual occupied cells; never modifies world output."""
import numpy as np
from ..core.data import Region
from ..core.geometry import sample
from ..core.fields import Context
from ..core.planning import Resources


def cutaway(spec, center, path, *, side=44):
    import cv2
    from .preview import write_png
    from ..api import pack as load_pack
    p = load_pack(spec.pack); params = p.resolve(spec)
    x0, z0 = int(center[0]) - side // 2, int(center[2]) - side // 2
    region = Region(x0, z0, side, side)
    resources = Resources(p, params, spec.seed)
    ctx = Context.for_region(p.fields, params, spec.seed, region, resources=resources)
    tops = np.ceil(ctx.get(p.height_field)).astype(np.int32) - 1
    xx, zz = region.coordinates()
    lo = max(params['world.y_min'], int(center[1]) - 16)
    hi = min(params['world.y_max'], int(center[1]) + 19)
    ys = np.arange(lo, hi)[None, :, None]
    occupied, _ = sample(p, params, spec.seed, xx[:, None], ys, zz[:, None], tops, resources=resources)
    # Remove the camera-facing quarter only from this diagnostic copy.
    occupied &= ~((xx[:, None] >= center[0]) & (zz[:, None] <= center[2]) & (ys >= center[1] - 7))
    padded = np.pad(occupied, 1)
    faces, colors = [], []
    corners = (((1,0,0),(1,1,0),(1,1,1),(1,0,1)), ((0,0,0),(0,0,1),(0,1,1),(0,1,0)),
               ((0,1,0),(0,1,1),(1,1,1),(1,1,0)), ((0,0,0),(1,0,0),(1,0,1),(0,0,1)),
               ((0,0,1),(1,0,1),(1,1,1),(0,1,1)), ((0,0,0),(0,1,0),(1,1,0),(1,0,0)))
    neighbors = (padded[1:-1,1:-1,2:], padded[1:-1,1:-1,:-2], padded[1:-1,2:,1:-1],
                 padded[1:-1,:-2,1:-1], padded[2:,1:-1,1:-1], padded[:-2,1:-1,1:-1])
    for direction, (neighbor, corner) in enumerate(zip(neighbors, corners)):
        iz, iy, ix = np.nonzero(occupied & ~neighbor)
        origin = np.stack((ix, iz, iy), axis=1)
        # Density array axes are Z,Y,X; plot axes are X,Z,Y.
        c = np.asarray(corner)[:, (0,2,1)]
        faces.extend(origin[:, None, :] + c[None, :, :])
        shade = (.55, .43, .72, .38, .62, .48)[direction]
        colors.extend([(shade, shade * .97, shade * .91, 1)] * len(ix))
    image = np.full((620, 800, 3), 245, np.uint8)
    if faces:
        faces = np.asarray(faces, np.float64)
        right, up, camera = np.array([.707,.707,0]), np.array([-.4,.4,.8]), np.array([.5,-.5,.5])
        screen = np.stack((faces @ right, -(faces @ up)), axis=-1)
        lo_screen, hi_screen = screen.min(axis=(0,1)), screen.max(axis=(0,1))
        scale = min(740 / max(hi_screen[0] - lo_screen[0], 1), 520 / max(hi_screen[1] - lo_screen[1], 1))
        pixels = np.rint((screen - lo_screen) * scale + (30,65)).astype(np.int32)
        depth = faces.mean(axis=1) @ camera
        for i in np.argsort(depth, kind='stable'):
            color = tuple(int(c * 255) for c in colors[i][:3])
            cv2.fillConvexPoly(image, pixels[i], color, lineType=cv2.LINE_AA)
            cv2.polylines(image, [pixels[i]], True, tuple(int(c * .90) for c in color), 1, cv2.LINE_AA)
    cv2.putText(image, 'Actual voxels - diagnostic quarter cutaway', (24,26), cv2.FONT_HERSHEY_SIMPLEX, .65, (30,30,30), 1, cv2.LINE_AA)
    cv2.putText(image, f'MC center {tuple(round(v,1) for v in center)}; vertical Y', (24,50), cv2.FONT_HERSHEY_SIMPLEX, .45, (30,30,30), 1)
    return write_png(path, image)
