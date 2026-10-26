"""Bounded delta plans against old rock; pools precede stepped column clusters.

Only intervals and small pool footprints survive a build. No plan queries the
final density, retains a voxel volume, or depends on output crops.
"""
import hashlib
import numpy as np
from ...core.cache import Memo
from ...core.data import Region, check_cancel
from ...core.fluids import FluidBody
from ...core.planning import Resources
from ...core.store import biomes as biome_ids
from ...core.volume_query import VolumeQuery
from ...core.noise import fbm2


def selected(pack, params, seed, xz, resources):
    """The fifth biome consumes only unclaimed wastes, in pack order."""
    xz = np.asarray(xz, np.int64)
    if not len(xz):
        return np.empty(0, bool)
    x0, z0 = xz.min(0)
    width, depth = xz.max(0) - (x0, z0) + 1
    ids = biome_ids(pack, params, seed, Region(int(x0), int(z0), int(width), int(depth)), resources)
    index = next((i for i,b in enumerate(pack.biomes) if b.id == 'basalt_deltas'), -1)
    return ids[xz[:,1]-z0,xz[:,0]-x0] == index


def sea_level(params):
    level = int(np.floor(params['world.sea_level']))
    return level if (params['nether.lava_enabled'] and params['nether.floor_y'] <= level
                     and level+1 < params['nether.roof_y']) else None


def interval_mask(records, x, y, z, result):
    """Apply unique-XZ intervals on a small rectangle, not a full-volume scan."""
    if not records or not result.size:
        return
    rows = np.asarray(records, np.int64)
    if rows[:,3].max() <= y.min() or rows[:,2].min() > y.max():
        return
    x0, z0 = rows[:, :2].min(0)
    x1, z1 = rows[:, :2].max(0)
    lower = np.zeros((z1-z0+1, x1-x0+1), np.int64)
    upper = lower.copy()
    lower[rows[:, 1]-z0, rows[:, 0]-x0] = rows[:, 2]
    upper[rows[:, 1]-z0, rows[:, 0]-x0] = rows[:, 3]
    regular = (x.ndim == y.ndim == z.ndim == 3 and x.shape[:2] == (1, 1)
               and y.shape[::2] == (1, 1) and z.shape[1:] == (1, 1))
    if regular:
        ix = np.flatnonzero((x[0, 0] >= x0) & (x[0, 0] <= x1) & (x[0,0] == np.floor(x[0,0])))
        iz = np.flatnonzero((z[:, 0, 0] >= z0) & (z[:, 0, 0] <= z1) & (z[:,0,0] == np.floor(z[:,0,0])))
        if not len(ix) or not len(iz):
            return
        xx, zz = x[0, 0, ix].astype(np.intp)-x0, z[iz, 0, 0].astype(np.intp)-z0
        lo, hi = lower[np.ix_(zz, xx)], upper[np.ix_(zz, xx)]
        hit = (y >= lo[:, None, :]) & (y < hi[:, None, :])
        result[np.ix_(iz, np.arange(result.shape[1]), ix)] |= hit
    else:
        xx, yy, zz = np.broadcast_arrays(x, y, z)
        use = ((xx >= x0) & (xx <= x1) & (zz >= z0) & (zz <= z1)
               & (xx == np.floor(xx)) & (zz == np.floor(zz)))
        ax, az = xx[use].astype(np.intp)-x0, zz[use].astype(np.intp)-z0
        result[use] |= (yy[use] >= lower[az, ax]) & (yy[use] < upper[az, ax])


class CellPlans:
    def __init__(self, pack, params, seed):
        self.pack, self.params, self.seed = pack, params, seed
        self.spacing = params['basalt.'+self.kind+'_spacing']
        self.cells = Memo()

    def context(self, cancel, report=None):
        resources = Resources(self.pack, self.params, self.seed)
        resources.cancel_event = cancel
        if report is not None:
            resources.report = report
        return resources, VolumeQuery(self.pack, self.params, self.seed, resources, field='nether_pillared')

    def profiles(self, query, xz, lower, upper):
        return query.profiles(xz, lower, upper)

    def random(self, cell):
        key = f'basalt-{self.kind}-1/{self.seed}/{cell[0]}/{cell[1]}'.encode()
        return np.random.default_rng(int.from_bytes(hashlib.sha256(key).digest()[:8], 'little'))

    def get(self, cell, resources=None):
        cancel = getattr(resources, 'cancel_event', None)
        check_cancel(cancel)
        return self.cells.get(cell, lambda: self.build(cell, cancel, getattr(resources, 'report', None)))

    def intersecting(self, x0, z0, x1, z1, resources=None):
        lo = np.floor((np.array((x0, z0))-self.radius)/self.spacing).astype(int)
        hi = np.floor((np.array((x1, z1))+self.radius)/self.spacing).astype(int)
        for cz in range(lo[1], hi[1]+1):
            for cx in range(lo[0], hi[0]+1):
                cell = (cx, cz)
                result = self.get(cell, resources)
                if result:
                    yield cell, result

    def mask(self, x, y, z, *, resources=None, rim=False):
        check_cancel(getattr(resources,'cancel_event',None))
        x, y, z = (np.asarray(v) for v in (x, y, z))
        result = np.zeros(np.broadcast_shapes(x.shape, y.shape, z.shape), bool)
        if not result.size:
            return result
        # Shell coordinates repeat the same X/Z axes as a meshgrid. Keep views
        # of those axes so interval_mask indexes only each cluster's rectangle.
        cartesian = (x.ndim == z.ndim == 3 and x.shape[1] == z.shape[1] == 1
                and x.shape[2] == result.shape[2] and z.shape[0] == result.shape[0]
                and np.all(x == x[:1,:,:]) and np.all(z == z[:,:,:1]))
        if cartesian and y.ndim == 3 and y.shape[::2] == (1,1):
            x, z = x[:1,:,:], z[:,:,:1]
        # Both builders restrict every output column to this biome. Reject
        # unmodified XZ first, before empty candidates can churn the cell LRU.
        xx,zz = np.broadcast_arrays(x,z)
        positions = np.column_stack((xx.ravel(),zz.ravel()))
        allowed = selected(self.pack,self.params,self.seed,positions,resources)
        check_cancel(getattr(resources,'cancel_event',None))
        if not allowed.any():
            return result
        positions = positions[allowed]
        x0,z0 = positions.min(0);x1,z1 = positions.max(0)
        for _, record in self.intersecting(x0,z0,x1,z1,resources):
            interval_mask(self.intervals(record, rim), x, y, z, result)
        return result


class Pools(CellPlans):
    kind = 'pools'
    radius = 5

    @staticmethod
    def intervals(record, rim=False):
        level, upper, wet, edge = record
        return (tuple((x, z, y, y+1) for x, z, y in edge if y is not None) if rim
                else tuple((x, z, level, upper) for x, z in wet))

    def build(self, cell, cancel=None, report=None):
        p, rng = self.params, self.random(cell)
        if rng.random() >= p['basalt.pools_density']:
            return ()
        center = np.floor((np.asarray(cell)+.5+rng.uniform(-.1, .1, 2))*self.spacing).astype(int)
        resources, query = self.context(cancel, report)
        if not selected(self.pack, p, self.seed, [center], resources)[0]:
            return ()
        floor, roof = p['nether.floor_y'], p['nether.roof_y']
        profile = self.profiles(query, center[None, :], floor, roof)[:, 0]
        sea = sea_level(p)
        runs = [(int(a)+floor, int(b)+floor) for a, b in query.air_runs(profile)
                if a >= 4 and b < roof-floor and (sea is None or a+floor-2 > sea)]
        if not runs:
            return ()
        radius = int(rng.integers(2, 5))
        footprint = {(int(center[0]+dx), int(center[1]+dz))
               for dz in range(-radius, radius+1) for dx in range(-radius, radius+1)
               if abs(dx)+abs(dz) < radius or (abs(dx)+abs(dz) == radius and rng.random() < .65)}
        directions = ((1,0),(-1,0),(0,1),(0,-1))
        halo = {(x+dx,z+dz) for x,z in footprint for dx,dz in directions}
        positions = np.asarray(sorted(footprint | halo),np.int64)
        lookup = {tuple(point):i for i,point in enumerate(positions)}
        xz = np.asarray(sorted(footprint),np.int64)
        ids = np.asarray([lookup[tuple(point)] for point in xz],np.intp)
        neighbors = np.asarray([[lookup[(x+dx,z+dz)] for dx,dz in directions] for x,z in xz])
        air,_ = runs[int(rng.integers(len(runs)))]
        level = air-2
        # One short batch for the footprint and its neighbors. Reject unsafe
        # cells individually so a ledge or natural rock island does not veto all.
        rock = self.profiles(query,positions,level-2,air+1)
        valid = rock[:3,ids].all(0) & ~rock[4,ids] & rock[2,neighbors].all(1)
        valid &= selected(self.pack,p,self.seed,xz,resources)
        valid &= fbm2(xz[:,0]/3,xz[:,1]/3,seed=self.seed,
                      salt='nether/basalt-pool-shape',octaves=1) > -.1
        wet = {tuple(map(int,point)) for point in xz[valid]}
        if not wet:
            return ()
        edge = {(x+dx,z+dz) for x,z in wet for dx,dz in directions}-wet
        tops = []
        edge_points = np.asarray(sorted(edge),np.int64)
        inside = selected(self.pack,p,self.seed,edge_points,resources)
        for (x,z),allowed in zip(edge_points,inside):
            i = lookup[(x,z)]
            top = air-1 if rock[3,i] and not rock[4,i] else (level if not rock[3,i] else None)
            if not allowed or rng.random() >= .3:
                top = None
            tops.append((int(x),int(z),top))
        return int(level),int(air),tuple(sorted(wet)),tuple(tops)

    def reserved(self, xz, resources):
        result = np.zeros(len(xz), bool)
        for _, record in self.intersecting(*xz.min(0), *xz.max(0), resources):
            _, _, wet, edge = record
            reserved = set(wet) | {(x, z) for x, z, _ in edge}
            result |= np.fromiter((tuple(v) in reserved for v in xz), bool, len(xz))
        return result


def cluster_shape(rng, height, large):
    """Offset shelves and narrow spires, without a shared conical height ramp."""
    reach = 5 if large else 2
    count = int(rng.integers(4, 8) if large else rng.integers(2, 5))
    # A wandering ridge keeps lobes related while breaking radial symmetry.
    steps = rng.integers(-2, 3, (count, 2))
    centers = np.clip(np.cumsum(steps, axis=0), -reach, reach)
    tops = rng.integers(max(2, height//3), height+1, count)
    tops[int(rng.integers(count))] = height
    result = {}
    for (cx, cz), top in zip(centers, tops):
        radius = int(rng.integers(1, 4)) if large else 1
        for dz in range(-radius, radius+1):
            for dx in range(-radius, radius+1):
                edge = max(abs(dx), abs(dz)) == radius
                corner = abs(dx) == abs(dz) == radius
                if (corner and rng.random() < .7) or (edge and rng.random() < .15):
                    continue
                point = (int(cx+dx), int(cz+dz))
                result[point] = max(result.get(point, 0), int(top))
    # Outlying rods leave dry gaps instead of completing concentric skirts.
    for _ in range(6 if large else 3):
        x, z = map(int, rng.integers(-reach-3, reach+4, 2))
        result[(x, z)] = max(result.get((x, z), 0), int(rng.integers(1, height+1)))
    # Apply broken tops after joining lobes so overlaps do not erase the gaps.
    variation = rng.choice((-5, -2, 0, 1), len(result), p=(.10, .25, .45, .20))
    return {point:int(np.clip(top+delta,1,height))
            for (point,top),delta in zip(result.items(),variation)}


class Columns(CellPlans):
    kind = 'columns'
    radius = 11

    @staticmethod
    def intervals(record, rim=False):
        return record

    def build(self, cell, cancel=None, report=None):
        p, rng = self.params, self.random(cell)
        if rng.random() >= p['basalt.columns_density']:
            return ()
        center = np.floor((np.asarray(cell)+.5+rng.uniform(-.1, .1, 2))*self.spacing).astype(int)
        resources, query = self.context(cancel, report)
        if not selected(self.pack, p, self.seed, [center], resources)[0]:
            return ()
        floor, roof = p['nether.floor_y'], p['nether.roof_y']
        profile = self.profiles(query, center[None, :], floor, roof)[:, 0]
        sea = sea_level(p)
        large = rng.random() < 1/3
        height = int(rng.integers(7, 16) if large else rng.integers(2, 8))
        runs = [(int(a)+floor, int(b)+floor) for a, b in query.air_runs(profile)
                if a > 0 and b < roof-floor and b-a >= 2
                and (sea is None or a+floor > sea or sea-a-floor < height-1)]
        if not runs:
            return ()
        foot, _ = runs[int(rng.integers(len(runs)))]
        targets = {(int(center[0]+dx), int(center[1]+dz)):length
                   for (dx,dz),length in cluster_shape(rng,height,large).items()}
        xz = np.asarray(sorted(targets), np.int64)
        allowed = selected(self.pack, p, self.seed, xz, resources)
        if p['basalt.pools_enabled'] and p['basalt.pools_density'] > 0:
            allowed &= ~resources.get('basalt_pools').reserved(xz, resources)
        xz = xz[allowed]
        if not len(xz):
            return ()
        # Only a short neighborhood around the selected floor, batched for all feet.
        lower, upper = max(floor, foot-4), min(roof, foot+height+4)
        rock = self.profiles(query, xz, lower, upper)
        result = []
        for i, (x, z) in enumerate(xz):
            choices = [(a+lower, b+lower) for a, b in query.air_runs(rock[:, i])
                       if a > 0 and abs(a+lower-foot) <= 3]
            if not choices:
                continue
            a, b = min(choices, key=lambda pair: abs(pair[0]-foot))
            end = min(b, a+targets[(x, z)])
            if end <= a or (sea is not None and a <= sea and end <= sea+1):
                continue
            result.append((int(x), int(z), int(a), int(end)))
        if len(result) > 529 or sum(b-a for _, _, a, b in result) > 8192:
            raise ValueError('basalt column cluster exceeds its declared budget')
        return tuple(result)


def pools(pack, params, seed):
    return Pools(pack, params, seed)


def columns(pack, params, seed):
    return Columns(pack, params, seed)


def pool_components(wet):
    """Small deterministic 2D components, independent of output tile crops."""
    remaining = set(wet)
    while remaining:
        root = min(remaining)
        remaining.remove(root)
        todo, component = [root], []
        while todo:
            x,z = todo.pop()
            component.append((x,z))
            for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                point = (x+dx,z+dz)
                if point in remaining:
                    remaining.remove(point)
                    todo.append(point)
        yield tuple(sorted(component))


def fluids(pack, params, seed, region, resources):
    plan = resources.get('basalt_pools')
    if plan is None or params['basalt.pools_density'] <= 0:
        return ()
    result = []
    for cell, record in plan.intersecting(region.x0, region.z0, region.x0+region.width-1,
                                         region.z0+region.depth-1, resources):
        level, _, wet, _ = record
        for component in pool_components(wet):
            xyz = np.asarray([(x, level, z) for x, z in component], np.int32)
            runs = np.asarray([(x, z, level, level+1) for x, z in component], np.int32)
            for a in (xyz, runs):
                a.setflags(write=False)
            root = component[0]
            ident = f'basalt/{seed}/{cell[0]}/{cell[1]}/{root[0]}/{root[1]}'
            result.append(FluidBody(ident, float(level), xyz, runs))
    return tuple(result)
