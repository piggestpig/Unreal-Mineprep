"""Sparse world-anchored ceiling pillars, planned against unmodified rock only."""
import hashlib
import numpy as np
from ...core.cache import Memo
from ...core.data import Region, check_cancel
from ...core.volume_query import VolumeQuery
from ...core.fields import Context
from ...core.planning import Resources


class Pillars:
    radius = 2

    def __init__(self, pack, params, seed):
        self.pack, self.params, self.seed = pack, params, seed
        self.resources = Resources(pack, params, seed)
        self.query = VolumeQuery(pack,params,seed,self.resources,field='nether_base')
        self.spacing = params['soul.pillar_spacing']
        self.cells = Memo()

    def profiles(self, positions):
        """Narrow columns, never a square volume or the final pillar density."""
        lo, hi = self.params['nether.floor_y'], self.params['nether.roof_y']
        return self.query.profiles(np.asarray(positions,np.int64),lo,hi)

    air_runs = staticmethod(VolumeQuery.air_runs)

    def build(self, cell, cancel_event=None):
        p = self.params
        raw = f'soul-pillars-1/{self.seed}/{cell[0]}/{cell[1]}'.encode()
        rng = np.random.default_rng(int.from_bytes(hashlib.sha256(raw).digest()[:8], 'little'))
        if rng.random() >= p['soul.pillar_density']:
            return ()
        center = np.floor((np.array(cell) + .5 + rng.uniform(-.28,.28,2)) * self.spacing).astype(int)
        x, z = map(int, center)
        ref = Context.for_region(self.pack.fields, p, self.seed, Region(x,z,1,1), resources=self.resources)
        if ref.get('soul_region')[0,0] < p['soul.biome_threshold']:
            return ()
        check_cancel(cancel_event)
        positions = [(x,z), (x-1,z), (x+1,z), (x,z-1), (x,z+1)]
        rock = self.profiles(positions)
        floor, roof = p['nether.floor_y'], p['nether.roof_y']
        lava = int(np.floor(p['world.sea_level']))
        cutoff = lava + 1 if p['nether.lava_enabled'] and floor <= lava and lava+1 < roof else floor
        runs = [(a+floor,b+floor) for a,b in self.air_runs(rock[:,0])
                if a > 0 and b < len(rock) and b+floor-max(a+floor,cutoff) >= 12]
        if not runs:
            return ()
        bottom, top = runs[int(rng.integers(len(runs)))]
        lower = max(bottom, cutoff)
        # Lava selects a visible cavern, not a physical support plane.
        result = [(x,z,bottom,top)]
        for index, (sx,sz) in enumerate(positions[1:], 1):
            # Short, connected side rods; some extend nearly to the central foot.
            length = min(top-lower, int(rng.geometric(.12)))
            desired = top-length
            for a,b in self.air_runs(rock[:,index]):
                a, b = a+floor, b+floor
                start, end = max(a,desired,lower), min(b,top+1)
                if lower > bottom and start == lower and a > floor:
                    start = a  # rods previously truncated by lava reach their own floor
                if end > start and start < top and end > lower:
                    result.append((sx,sz,start,end))
        if lower == bottom:
            # Only a grounded foot gets rubble; never put a platform over lava.
            offsets = [(dx,dz) for dz in range(-2,3) for dx in range(-2,3)
                       if 1 < abs(dx)+abs(dz) <= 2 and rng.random() < .35]
            if offsets:
                rubble = self.profiles([(x+dx,z+dz) for dx,dz in offsets])
                for i,(dx,dz) in enumerate(offsets):
                    for a,b in self.air_runs(rubble[:,i]):
                        a,b = a+floor,b+floor
                        if abs(a-bottom) <= 1 and a > floor and a < b:
                            result.append((x+dx,z+dz,a,min(b,a+int(rng.integers(1,3)))))
        return tuple(tuple(map(int,segment)) for segment in result)

    def get(self, cell, resources=None):
        cancel = getattr(resources, 'cancel_event', None)
        check_cancel(cancel)
        return self.cells.get(cell, lambda: self.build(cell, cancel))

    def mask(self, x, y, z, *, resources=None):
        check_cancel(getattr(resources, 'cancel_event', None))
        x,y,z = (np.asarray(v) for v in (x,y,z))
        result = np.zeros(np.broadcast_shapes(x.shape,y.shape,z.shape), bool)
        if not result.size:
            return result
        min_y, max_y = y.min(), y.max()
        vertical_grid = (x.ndim == y.ndim == z.ndim == 3 and x.shape[1] == z.shape[1] == 1
                         and y.shape[0] == y.shape[2] == 1)
        lo = np.floor((np.array([x.min(),z.min()])-self.radius)/self.spacing).astype(int)
        hi = np.floor((np.array([x.max(),z.max()])+self.radius)/self.spacing).astype(int)
        for cz in range(lo[1],hi[1]+1):
            for cx in range(lo[0],hi[0]+1):
                for sx,sz,a,b in self.get((cx,cz), resources):
                    if b <= min_y or a > max_y:
                        continue
                    horizontal = (x == sx) & (z == sz)
                    if vertical_grid:
                        zz,_,xx = np.nonzero(horizontal)
                        yy = np.flatnonzero((y[0,:,0] >= a) & (y[0,:,0] < b))
                        result[zz[:,None],yy[None,:],xx[:,None]] = True
                    else:
                        result |= horizontal & (y >= a) & (y < b)
        return result


def plan(pack, params, seed):
    return Pillars(pack, params, seed)
