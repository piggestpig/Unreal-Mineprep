"""Finite unit-cell fountain over the main island, independent of terrain detail."""
import numpy as np
from ...core.postprocess import SurfacePatch
from .terrain import altar


def apply(ctx, surfaces):
    p,r = ctx.params,ctx.region
    points,types = [],[]
    height = int(round(p['end.height']))
    if altar(p):
        for dy in range(-3,4):
            for dz in range(-3,4):
                for dx in range(-3,4):
                    radius=np.hypot(dx,dz)
                    if radius<3.5 and (dy<0 or radius<.8 or (dy==0 and radius>2.3)):
                        points.append((p['end.center_x']+dx,height+dy,p['end.center_z']+dz))
                        types.append(ctx.block_ids['bedrock'])
        for dz in range(-2,3):
            for dx in range(-2,3):
                if .8 < np.hypot(dx,dz) < 2.3 and height+2<p['world.y_max']:
                    points.append((p['end.center_x']+dx,height,p['end.center_z']+dz))
                    types.append(ctx.block_ids['end_portal_surface'])
    q = np.asarray(points,np.int64).reshape(-1,3)
    t = np.asarray(types,np.uint16)
    inside = ((q[:,0]>=r.x0)&(q[:,0]<r.x0+r.width)&(q[:,2]>=r.z0)&(q[:,2]<r.z0+r.depth)
              &(q[:,1]>=p['world.y_min'])&(q[:,1]<p['world.y_max']))
    layout=ctx.query.world.pack.layout
    if layout is not None:inside &= layout.terrain(q[:,0],q[:,2])
    q,t = q[inside],t[inside]
    emitted=ctx.query.emitted(q)
    occupied=ctx.query.occupied(q)
    keep=emitted|~occupied
    # Hidden island cells already provide the embedded foundation. Recolour
    # only emitted terrain, and add the exposed rim, stem and portal in air.
    return SurfacePatch(q[keep],t[keep],emitted[keep])
