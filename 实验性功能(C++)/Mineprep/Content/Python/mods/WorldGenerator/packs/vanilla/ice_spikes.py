"""Grounded, solid tapered packed-ice shapes; placement belongs to the core."""
import numpy as np
from ...core.features import FeatureBatch


def _shape(height, radius, key):
    points=[]
    for x in range(-radius,radius+1):
        for z in range(-radius,radius+1):
            distance=np.hypot(x,z)
            if distance>radius:
                continue
            # Every column starts at y=0. Edge variation never makes cavities
            # or detached cells, and the central column keeps a unique tip.
            jitter=((key>>((x+3+7*(z+3))%32))%3)-1
            top=height if x==z==0 else max(1,min(height-1,int(height*(1-(distance/(radius+.5))**1.3))+jitter))
            points.extend((x,y,z) for y in range(top))
    return np.asarray(points,np.int32)


def build(ctx, anchors, keys):
    parts,owners=[],[]
    base=int(ctx.params['ice_spikes.height'])
    chance=ctx.params['ice_spikes.tall_chance']
    for i,value in enumerate(keys):
        key=int(value)
        tall=((key>>32)/2**32)<chance
        height=3*base+((key>>6)%9)-4 if tall else base+((key>>1)%5)-2
        shape=_shape(height,2+((key>>12)&1),key)
        parts.append(shape);owners.append(np.full(len(shape),i,np.int32))
    xyz=np.concatenate(parts) if parts else np.empty((0,3),np.int32)
    owner=np.concatenate(owners) if owners else np.empty(0,np.int32)
    return FeatureBatch(xyz,np.full(len(xyz),ctx.block_ids['packed_ice'],np.uint16),owner)
