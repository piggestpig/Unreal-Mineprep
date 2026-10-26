"""World-anchored, locally queried dry cave systems. No output-crop input.

The immutable geometry lives in a process-local planning resource; each
anchor's system is built once and memoized on the plan.
"""
from collections import Counter
from dataclasses import dataclass
import hashlib
import math
from time import perf_counter

import numpy as np

from ...core.planning import Resources, SurfaceTiles
from ...core.cache import Memo

HEIGHT_TILE = 64
VERSION = 'entrance-guides-2'


@dataclass(frozen=True)
class Primitive:
    kind: str
    a: tuple
    b: tuple  # tube end, or ellipsoid radii
    radius: tuple  # tube radii at its two ends
    bounds: tuple  # xmin,ymin,zmin,xmax,ymax,zmax (cell-centre coordinates)


def tube(a, b, ra, rb):
    r = max(ra, rb) + 1  # bounded wall detail, included in all extraction bounds
    bounds = tuple(min(a[i], b[i]) - r for i in range(3)) + tuple(max(a[i], b[i]) + r for i in range(3))
    return Primitive('tube', tuple(a), tuple(b), (float(ra), float(rb)), bounds)


@dataclass(frozen=True)
class EntranceGuide:
    id: tuple
    center: tuple
    primitives: tuple
    entrances: tuple
    bounds: tuple


@dataclass(frozen=True)
class Ravine:
    id: tuple
    center: tuple
    primitives: tuple
    bounds: tuple


def intersects(a, b):
    return all(a[i] <= b[i + 3] and a[i + 3] >= b[i] for i in range(3))


class CavePlan:
    def __init__(self, pack, params, seed):
        self._pack, self._params, self._seed = pack, params, seed
        self._resources = Resources(pack, params, seed)
        self._anchors, self._ravine_anchors = Memo(), Memo()
        self._terrain = SurfaceTiles(self._resources)
        self._rejections = Counter()
        self._timings = Counter()
        self._reach = 32 + params['caves.entrance_length'] + params['caves.tunnel_radius'] * 6
        self._ravine_reach = 32 + params['ravines.length'] * .85 + params['ravines.width']

    def _land(self, xs, zs):
        """Paired integer samples; cached world-aligned tiles retain exact R3 height."""
        started = perf_counter()
        xs, zs = np.broadcast_arrays(np.asarray(xs), np.asarray(zs))
        ix, iz = np.floor(xs).astype(np.int64).ravel(), np.floor(zs).astype(np.int64).ravel()
        heights, wets = np.empty(len(ix)), np.empty(len(ix), bool)
        txs, tzs = ix // HEIGHT_TILE, iz // HEIGHT_TILE
        minx, minz = int(txs.min()), int(tzs.min())
        nz = int(tzs.max()) - minz + 1
        keys = (txs - minx) * nz + tzs - minz
        values = np.unique(keys)
        tiles = self._terrain.get_many((int(v)//nz+minx,int(v)%nz+minz) for v in values)
        for value in values:
            tx, tz = int(value) // nz + minx, int(value) % nz + minz
            key = (int(tx), int(tz))
            h, wet = tiles[key]
            selected = keys == value
            xx, zz = ix[selected] % HEIGHT_TILE, iz[selected] % HEIGHT_TILE
            heights[selected], wets[selected] = h[zz, xx], wet[zz, xx]
        self._timings['surface_queries'] += perf_counter() - started
        return heights.reshape(xs.shape), wets.reshape(xs.shape)

    def surface_region(self, region):
        """Bound terrain reads for every anchor visited by _query in this region."""
        from ...core.data import Region
        p = self._params
        radius = p['caves.tunnel_radius'] * (1.35 if p['caves.style'] == 1 else 1)
        # Path bend, one lateral repair and the dry-route radius surround an anchor.
        guide = 1.1 * p['caves.entrance_length'] + 4.8 * radius + 6
        queries = [(p['caves.entrance_spacing'], self._reach, guide)]
        if p['ravines.enabled']:
            # 1.2 is the length variation; Catmull-Rom bends can overshoot by 25%.
            ravine = 1.2 * p['ravines.length'] * (.5 + .225 * p['ravines.curvature']) + .55 * p['ravines.width'] + 2
            queries.append((p['ravines.spacing'], self._ravine_reach, ravine))
        x0, z0 = region.x0, region.z0
        x1, z1 = x0 + region.width, z0 + region.depth
        for step, reach, extent in queries:
            for axis, lo, hi in ((0, region.x0, region.x0 + region.width),
                                 (1, region.z0, region.z0 + region.depth)):
                low = math.floor((math.floor((lo - reach) / step) + .5) * step - 32 - extent)
                high = math.ceil((math.floor((hi + reach) / step) + .5) * step + 32 + extent) + 1
                if axis == 0:
                    x0, x1 = min(x0, low), max(x1, high)
                else:
                    z0, z1 = min(z0, low), max(z1, high)
        return Region(x0, z0, x1 - x0, z1 - z0)

    def _natural(self, points):
        started=perf_counter()
        from ...core.density import DensityContext
        points=np.asarray(points)
        h,_=self._land(points[:,0],points[:,2])
        ctx=DensityContext(self._pack,self._params,self._seed,
                           points[:,0][None,None,:],points[:,1][None,None,:],
                           points[:,2][None,None,:],tops=(np.ceil(h)-1)[None,:],
                           resources=self._resources)
        result=ctx.get('cave_background').ravel()
        self._timings['natural_target_sampling']+=perf_counter()-started
        return result

    def _system(self, ix, iz):
        p=self._params
        raw=hashlib.sha256(f'{VERSION}:{self._seed}:{ix}:{iz}'.encode()).digest()
        rng=np.random.default_rng(int.from_bytes(raw[:8],'little'))
        if rng.random() >= p['caves.entrance_probability']:
            self._rejections['guides.probability']+=1
            return None
        for attempt in range(4):
            x,z=(ix+.5)*p['caves.entrance_spacing']+rng.uniform(-32,32),(iz+.5)*p['caves.entrance_spacing']+rng.uniform(-32,32)
            h,wet=self._land(x,z)
            if wet or h < p['world.y_min']+24: continue
            angles=np.arange(16)*np.pi/8+rng.uniform(0,np.pi/8)
            length=p['caves.entrance_length']
            ex,ez=x+np.cos(angles)*length,z+np.sin(angles)*length
            eh,ew=self._land(ex,ez)
            eligible=np.flatnonzero((~ew)&(eh<h-8)&(eh>p['world.y_min']+12))
            for index in eligible[np.argsort(eh[eligible],kind='stable')][:4]:
                radius=p['caves.tunnel_radius']*(1.35 if p['caves.style']==1 else 1)
                # Choose an existing natural target with a full 4x4x4 air core.
                low=p['world.y_min']+radius+4; high=float(h)-radius-8
                if high<low: continue
                levels=np.arange(int(low),int(high)+1,4)
                centers=np.stack((np.full(len(levels),x),levels,np.full(len(levels),z)),axis=1)
                offsets=np.array([(a,b,c) for a in range(-2,2) for b in range(-2,2) for c in range(-2,2)])
                clearance=self._natural((np.floor(centers)[:,None,:]+offsets).reshape(-1,3)).reshape(-1,64).min(axis=1)
                accepted=np.flatnonzero(clearance>1.)
                if not len(accepted): continue
                choice=accepted[np.argmin(abs(levels[accepted]-(float(h)-p['caves.depth'])))]
                center=centers[choice]
                endpoint=np.array((ex[index],float(eh[index])-radius*.3,ez[index]))
                t=np.linspace(0,1,13); delta=endpoint-center
                bend=rng.uniform(-.1,.1)*length*np.sin(np.pi*t)
                angle=angles[index]
                points=center[None,:]+t[:,None]*delta
                points[:,0]-=np.sin(angle)*bend; points[:,2]+=np.cos(angle)*bend
                radii=np.full(13,radius)
                repaired=self._repair_path(points,radii,True)
                if repaired is None: continue
                points,radii=repaired
                # Repair must retain the original natural endpoint.
                if np.linalg.norm(points[0]-center)>1e-6: continue
                if not self._walkable(points):
                    self._rejections['guides.insufficient_walkable_core']+=1
                    continue
                primitives=tuple(tube(a,b,ra,rb) for a,b,ra,rb in zip(points[:-1],points[1:],radii[:-1],radii[1:]))
                bounds=tuple(min(o.bounds[i] for o in primitives) for i in range(3))+tuple(max(o.bounds[i] for o in primitives) for i in range(3,6))
                return EntranceGuide((ix,iz),tuple(center),primitives,(tuple(endpoint),),bounds)
        self._rejections['guides.no_accessible_target']+=1
        return None

    def _walkable(self, points):
        """Check every four-cell core along accepted geometry, not just endpoints."""
        p=self._params
        offsets=np.array([(a,b,c) for a in range(-2,2) for b in range(-2,2) for c in range(-2,2)])
        for index,(a,b) in enumerate(zip(points[:-1],points[1:])):
            t=np.linspace(0,1,max(2,int(np.linalg.norm(b-a)*2)+1))
            cells=(np.floor(a[None,:]+t[:,None]*(b-a))[:,None,:]+offsets).reshape(-1,3)
            h,wet=self._land(cells[:,0],cells[:,2])
            if wet.any() or np.any(cells[:,1]+.5<p['world.y_min']+4): return False
            if index<len(points)-3 and np.any(cells[:,1]+.5>h-8): return False
        return True

    def _repair_path(self, proposed, radii, opening):
        """Bounded local geometry repair. Never fill terrain or restore a wet cut."""
        started = perf_counter()
        points,radii = proposed.copy(),radii.copy()
        p = self._params
        h,wet = self._land(points[:,0],points[:,2])
        ordinary = np.arange(len(points)) < (len(points)-2 if opening else len(points))
        ordinary[0] = False
        available = np.maximum((h-p['world.y_min']-10)*.5,0)
        radii[ordinary] = np.minimum(radii[ordinary],available[ordinary])
        if np.any(radii < 3):
            self._timings['repairs'] += perf_counter()-started
            return None
        points[ordinary,1] = np.clip(points[ordinary,1],p['world.y_min']+radii[ordinary]+4,h[ordinary]-radii[ordinary]-8)
        radii[0] = min(radii[0],h[0]-points[0,1]-8,points[0,1]-p['world.y_min']-4)
        if radii[0]<3:
            self._timings['repairs'] += perf_counter()-started
            return None
        if self._path_dry(points,float(radii.max())*1.6):
            self._timings['repairs'] += perf_counter()-started
            return points,radii
        for i in range(1,len(points)):
            reach = max(radii[i-1:i+1])*1.6
            if self._path_dry(points[i-1:i+1],reach): continue
            if i == len(points)-1 and opening:
                self._timings['repairs'] += perf_counter()-started
                return None
            delta = points[i,[0,2]]-points[i-1,[0,2]]
            normal = np.array([-delta[1],delta[0]]) / max(np.linalg.norm(delta),1e-6)
            fixed = False
            for sign in (-1,1):
                candidate = points.copy()
                candidate[i,[0,2]] += sign*normal*(reach*2+2)
                heights,wets = self._land(candidate[i,0],candidate[i,2])
                if wets or heights <= p['world.y_min']+2*radii[i]+10: continue
                candidate[i,1] = np.clip(candidate[i,1],p['world.y_min']+radii[i]+4,float(heights)-radii[i]-6)
                lo,hi = max(i-1,0),min(i+2,len(points))
                if self._path_dry(candidate[lo:hi],max(radii[lo:hi])*1.6):
                    points=candidate; fixed=True; break
            if not fixed:
                smaller = max(3.,min(radii[i-1:i+1])*.75)
                if self._path_dry(points[i-1:i+1],smaller*1.6):
                    radii[i-1:i+1] = smaller
                else:
                    self._timings['repairs'] += perf_counter()-started
                    return None
        self._timings['repairs'] += perf_counter()-started
        return points,radii

    def _path_land(self, points, radius):
        xs, zs = np.meshgrid(np.arange(math.floor(points[:, 0].min() - radius), math.ceil(points[:, 0].max() + radius) + 1),
                             np.arange(math.floor(points[:, 2].min() - radius), math.ceil(points[:, 2].max() + radius) + 1))
        mask = np.zeros(xs.shape, bool)
        for a, b in zip(points[:-1], points[1:]):
            dx, dz = b[0] - a[0], b[2] - a[2]
            t = np.clip(((xs + .5 - a[0]) * dx + (zs + .5 - a[2]) * dz) / max(dx * dx + dz * dz, 1e-12), 0, 1)
            mask |= (xs + .5 - a[0] - t * dx) ** 2 + (zs + .5 - a[2] - t * dz) ** 2 <= radius ** 2
        return self._land(xs[mask], zs[mask])

    def _path_dry(self, points, radius):
        started = perf_counter()
        _,_,wet_count = self._terrain.rectangle(math.floor(points[:,0].min()-radius),math.floor(points[:,2].min()-radius),
                                                math.ceil(points[:,0].max()+radius)+1,math.ceil(points[:,2].max()+radius)+1)
        self._timings['surface_queries'] += perf_counter()-started
        if not wet_count:
            return True
        _, wet = self._path_land(points, radius)
        return not wet.any()

    def _ravine(self, ix, iz):
        raw = hashlib.sha256(f'dry-ravines-1:{self._seed}:{ix}:{iz}'.encode()).digest()
        rng = np.random.default_rng(int.from_bytes(raw[:8], 'little'))
        p = self._params
        if rng.random() >= p['ravines.density']:
            self._rejections['ravines.density'] += 1
            return None
        for attempt in range(4):
            x, z = (ix + .5) * p['ravines.spacing'] + rng.uniform(-32, 32), (iz + .5) * p['ravines.spacing'] + rng.uniform(-32, 32)
            angle, length = rng.uniform(0, 2 * np.pi), p['ravines.length'] * rng.uniform(.8, 1.2)
            t = np.linspace(0,1,33)
            knots = rng.uniform(-.18,.18,5)*length*p['ravines.curvature']
            knots[0]=knots[-1]=0
            u=t*4; segment=np.minimum(u.astype(int),3); f=u-segment
            extended=np.pad(knots,(1,1),mode='edge')
            a,b,c,d=(extended[segment+i] for i in range(4))
            bend=.5*((2*b)+(-a+c)*f+(2*a-5*b+4*c-d)*f*f+(-a+3*b-3*c+d)*f*f*f)
            along = (t - .5) * length
            xs = x + np.cos(angle) * along - np.sin(angle) * bend
            zs = z + np.sin(angle) * along + np.cos(angle) * bend
            heights, wet = self._land(xs, zs)
            arc = np.concatenate(([0],np.cumsum(np.hypot(np.diff(xs),np.diff(zs)))))
            arc /= arc[-1]
            widths = p['ravines.width']*.5*np.sin(np.pi*arc)**1.2*(.85+.15*np.sin(arc*2*np.pi+rng.uniform(0,2*np.pi)))
            widths[0]=widths[-1]=0
            points = np.stack((xs, heights, zs), axis=1)
            if wet.any() or not self._path_dry(points,float(widths.max())*1.1):
                self._rejections['ravines.wet_route'] += 1
                continue
            # Width tapers only at whole-path ends, never at segment/crop seams.
            if heights.min() <= p['world.y_min'] + 8:
                self._rejections['ravines.thin_floor'] += 1
                continue
            depth = p['ravines.depth'] * (.85 + .15 * np.sin(t * np.pi))
            ceiling=p['world.sea_level']+p['ravines.ceiling_above_sea']
            floors = np.maximum(p['world.y_min'] + 4., np.minimum(heights,ceiling)-depth
                                + np.sin(arc*3*np.pi)*p['ravines.depth']*.06)
            if ceiling <= p['world.y_min']+5: continue
            points[:, 1] = floors
            primitives = []
            for i, (a, b) in enumerate(zip(points[:-1], points[1:])):
                width = max(widths[i:i + 2])
                bounds = (min(a[0], b[0]) - width, max(p['world.y_min']+4,min(a[1],b[1])-width*.3), min(a[2], b[2]) - width,
                          max(a[0], b[0]) + width, ceiling, max(a[2], b[2]) + width)
                primitives.append(Primitive('ravine', tuple(a), tuple(b), tuple(widths[i:i + 2]), bounds))
            bounds = tuple(min(o.bounds[i] for o in primitives) for i in range(3)) + tuple(max(o.bounds[i] for o in primitives) for i in range(3, 6))
            return Ravine((ix, iz), tuple(points[16]), tuple(primitives), bounds)
        return None

    def _query(self, bounds, cache, step, reach, builder):
        result = []
        for iz in range(math.floor((bounds[2] - reach) / step), math.floor((bounds[5] + reach) / step) + 1):
            for ix in range(math.floor((bounds[0] - reach) / step), math.floor((bounds[3] + reach) / step) + 1):
                system = cache.get((ix, iz), lambda: builder(ix, iz))
                if system is not None and intersects(system.bounds, bounds):
                    result.append(system)
        return tuple(result)

    def query(self, bounds):
        caves = self._query(bounds, self._anchors, self._params['caves.entrance_spacing'], self._reach, self._system)
        if not self._params['ravines.enabled']:
            return caves
        return caves + self._query(bounds, self._ravine_anchors, self._params['ravines.spacing'], self._ravine_reach, self._ravine)

    def guides(self, region):
        bounds = (region.x0, self._params['world.y_min'], region.z0,
                  region.x0 + region.width, self._params['world.y_max'], region.z0 + region.depth)
        return self._query(bounds, self._anchors, self._params['caves.entrance_spacing'], self._reach, self._system)

    def ravines(self, region):
        if not self._params['ravines.enabled']:
            return ()
        bounds = (region.x0, self._params['world.y_min'], region.z0,
                  region.x0 + region.width, self._params['world.y_max'], region.z0 + region.depth)
        return self._query(bounds, self._ravine_anchors, self._params['ravines.spacing'], self._ravine_reach, self._ravine)

    def summary(self, region):
        systems = self.guides(region)
        ravines = self.ravines(region)
        return dict(guides=len(systems), entrances=sum(len(s.entrances) for s in systems),
                    primitives=sum(len(s.primitives) for s in (*systems, *ravines)), ravines=len(ravines),
                    rejections=dict(self._rejections), anchors_built=len(self._anchors)+len(self._ravine_anchors),
                    timings=dict(self._timings))


def build_plan(pack, params, seed):
    return CavePlan(pack, params, seed)

def affected_bounds(pack,params,seed,region,resources):
    """Conservative continuous-network volume, plus sparse entrance/ravine boxes."""
    if not params['caves.enabled']: return ()
    terrain=SurfaceTiles(resources)
    boxes=[]
    if params['caves.density']>0:
        for az in range(region.z0//32,(region.z0+region.depth-1)//32+1):
            for ax in range(region.x0//32,(region.x0+region.width-1)//32+1):
                x0,z0=max(region.x0,ax*32),max(region.z0,az*32)
                x1,z1=min(region.x0+region.width,(ax+1)*32),min(region.z0+region.depth,(az+1)*32)
                _,maximum,wet=terrain.rectangle(x0,z0,x1,z1)
                high=min(params['world.y_max'],math.ceil(maximum)-8)
                if high>params['world.y_min']+4 and wet<(x1-x0)*(z1-z0):
                    boxes.append((x0,params['world.y_min']+4,z0,x1,high,z1))
    bounds=(region.x0,params['world.y_min'],region.z0,region.x0+region.width,params['world.y_max'],region.z0+region.depth)
    for obj in resources.get('caves').query(bounds):
        boxes.append(tuple(math.floor(v) for v in obj.bounds[:3])+tuple(math.ceil(v) for v in obj.bounds[3:]))
    from .water_connections import query
    boxes.extend(entry.bounds for entry in query(pack,params,seed,region,resources))
    return tuple(boxes)
