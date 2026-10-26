"""Static portal faces over the physical fountain."""
import numpy as np
from ...core.postprocess import SurfacePatch
from .terrain import altar


def apply(ctx, surfaces):
    p,r = ctx.params,ctx.region
    points,types = [],[]
    if altar(p):
        for dz in range(-2,3):
            for dx in range(-2,3):
                if .8 < np.hypot(dx,dz) < 2.3:
                    points.append((p['end.center_x']+dx,int(round(p['end.height'])),p['end.center_z']+dz))
                    types.append(ctx.block_ids['end_portal_surface'])
    q = np.asarray(points,np.int64).reshape(-1,3)
    t = np.asarray(types,np.uint16)
    inside = ((q[:,0]>=r.x0)&(q[:,0]<r.x0+r.width)&(q[:,2]>=r.z0)&(q[:,2]<r.z0+r.depth)
              &(q[:,1]>=p['world.y_min'])&(q[:,1]+2<p['world.y_max']))
    q,t = q[inside],t[inside]
    if len(q):
        free = ~ctx.query.occupied(q)
        q,t = q[free],t[free]
    return SurfacePatch(q,t,np.zeros(len(q),bool))
