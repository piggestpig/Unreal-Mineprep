"""Composable signed fields. Positive is rock; values are not distances.

Lattice nodes sit on world-aligned 32-cell blocks. The tasks of one generation
in one process (strips, tiles, main-process stages) share evaluated blocks
through task_scope(key); a process keeps only its latest generation's blocks,
and no complete voxel world is stored.
Coordinates are cell origins; arrays broadcast to [Z,Y,X], including support Y.
"""
from collections import Counter
from contextlib import contextmanager
import contextvars
from dataclasses import dataclass
import inspect
from time import perf_counter
import numpy as np
from .noise3 import fbm3
from .cache import Memo
from .data import check_cancel

VERSION = 'density3-6'
BLOCK = 32
_task = contextvars.ContextVar('worldgen_density_task', default=None)
_generations = Memo(limit=1)


@contextmanager
def task_scope(key=None):
    """Share lattice blocks and regular samples among the queries of generation `key`."""
    token = _task.set(Memo() if key is None else _generations.get(key, Memo))
    try:
        yield
    finally:
        _task.reset(token)

@dataclass(frozen=True)
class DensityDef:
    name: str
    fn: object
    deps: tuple = ()
    res: object = 1
    resources: tuple = ()
    axes: str = 'xyz'

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.isidentifier():
            raise ValueError('density name must be an identifier')
        steps = (self.res,) * 3 if type(self.res) is int else self.res
        if (not isinstance(steps, tuple) or len(steps) != 3
                or any(type(v) is not int or v not in (1, 2, 4, 8, 16, 32) for v in steps)):
            raise ValueError('density resolution must be an integer or XYZ tuple of 1,2,4,8,16,32')
        if not isinstance(self.axes,str) or self.axes != ''.join(a for a in 'xyz' if a in self.axes):
            raise ValueError('density axes must be an ordered subset of xyz (empty means constant)')
        if len(inspect.signature(self.fn).parameters) != 1 + len(self.deps):
            raise ValueError(f'density {self.name}: function takes ctx plus dependencies')


    @property
    def steps(self):
        return (self.res,) * 3 if type(self.res) is int else self.res


def density(name, *, deps=(), res=1, resources=(), axes='xyz'):
    def decorate(fn):
        return DensityDef(name, fn, tuple(deps), res, tuple(resources), axes)
    return decorate


@dataclass(frozen=True)
class DensityRecipe:
    field: str
    base: str = 'height'
    enabled_param: object = None
    bounds: object = None
    wet_protection: str = 'shell'


def union(a, b):
    return np.maximum(a, b)


def intersect(a, b):
    return np.minimum(a, b)


def smooth_intersect(a, b, width):
    return -smooth_union(-a, -b, width)


def subtract(a, b):
    return np.minimum(a, -b)


def smooth_union(a, b, width):
    width = np.maximum(width, 0)
    h = np.maximum(width - np.abs(a - b), 0) / np.maximum(width, 1e-12)
    return union(a, b) + h * h * width * .25


def gradient(y, lo, hi, a, b):
    if hi <= lo:
        raise ValueError('gradient upper height must exceed lower height')
    return a + (b - a) * np.clip((y - lo) / (hi - lo), 0, 1)


class DensityContext:
    def __init__(self, pack, params, seed, x, y, z, *, tops=None, resources=None, key=None):
        self.pack, self.params, self.seed = pack, params, seed
        self.x, self.y, self.z = (np.asarray(v) for v in (x, y, z))
        for coordinate in (self.x, self.y, self.z):
            coordinate.setflags(write=False)
        self.shape = np.broadcast_shapes(self.x.shape, self.y.shape, self.z.shape)
        self.tops, self.resources = tops, resources
        self.key = key or (resources.key('density/' + VERSION) if resources else
                           (pack.fingerprint, seed, repr(params.to_dict()), VERSION))
        self._memo = {}
        self.evaluated = 0
        self.work_bytes = 0
        self.timings = Counter()
        self.counters = Counter()
        self.interpolations = 0
        self._weights = {}
        task = _task.get()
        self._blocks = Memo() if task is None else task

    def param(self, key):
        return self.params[key]

    def resource(self, name):
        if self.resources is None:
            raise ValueError(f'density requires planning resource {name!r}')
        return self.resources.get(name)

    @property
    def base_density(self):
        if self.tops is None:
            from .planning import Resources, SurfaceTiles
            resources = self.resources or Resources(self.pack, self.params, self.seed)
            h, _ = SurfaceTiles(resources).values(self.x[:, 0, :], self.z[:, 0, :])
            self.tops = np.ceil(h).astype(np.int32) - 1
        return self.tops[:, None, :] + .5 - self.y

    def noise(self, salt, scale, *, octaves=2, coords=None):
        xyz = (self.x + .5, self.y + .5, self.z + .5) if coords is None else coords
        scales = (scale,) * 3 if np.isscalar(scale) else scale
        started = perf_counter()
        result = fbm3(*(v / s for v, s in zip(xyz, scales)), seed=self.seed,
                      salt=salt, octaves=octaves).astype(np.float32)
        self.timings['noise'] += perf_counter()-started
        return result

    def warp(self, salt, amplitude, scale=48):
        return tuple(v + .5 + amplitude * self.noise(salt + '/' + axis, scale, octaves=1)
                     for axis, v in zip('xyz', (self.x, self.y, self.z)))

    def _evaluate(self, definition):
        result = definition.fn(self, *(self.get(n) for n in definition.deps))
        if not isinstance(result, np.ndarray) or result.dtype.kind != 'f' or result.shape != self.shape:
            raise ValueError(f'density {definition.name} must return a float ndarray matching {self.shape}')
        result = result.astype(np.float32, copy=False)
        result.setflags(write=False)
        self.evaluated += result.size
        self.work_bytes = max(self.work_bytes, result.nbytes + sum(a.nbytes for a in self._memo.values()))
        return result

    def get(self, name):
        if name not in self._memo:
            definition = self.pack.densities[name]
            if definition.axes == 'xyz':
                value = self._evaluate(definition) if definition.steps == (1,1,1) else self._lattice(definition)
            else:
                # Axis metadata is a promise from the author. Evaluate a plane,
                # line or scalar, then broadcast without allocating a volume.
                coords = [v if a in definition.axes else np.zeros((1,1,1), dtype=np.int64)
                          for a,v in zip('xyz',(self.x,self.y,self.z))]
                sub = DensityContext(self.pack,self.params,self.seed,*coords,resources=self.resources,key=self.key)
                value = sub._evaluate(definition) if definition.steps == (1,1,1) else sub._lattice(definition)
                self.evaluated += sub.evaluated
                self.timings.update(sub.timings); self.counters.update(sub.counters)
                self.interpolations += sub.interpolations
                self.work_bytes = max(self.work_bytes,sub.work_bytes)
                value = np.broadcast_to(value,self.shape)
            self._memo[name] = value
        return self._memo[name]

    def _lattice(self, definition):
        started = perf_counter()
        noise_before = self.timings['noise']
        regular = (self.x.ndim == self.y.ndim == self.z.ndim == 3
                   and self.x.shape[:2] == (1,1) and self.y.shape[::2] == (1,1) and self.z.shape[1:] == (1,1))
        if regular:
            # Repeated XZ planes and identical windows interpolate once per task.
            key = ('sample',self.key,definition.name,definition.steps,definition.axes,
                   tuple((v.dtype.str,v.shape,v.tobytes()) for v in (self.x,self.y,self.z)))
            result = self._blocks.get(key, lambda: self._interpolate(definition))
        else:
            result = self._interpolate(definition)
        self.timings['interpolation'] += perf_counter()-started-(self.timings['noise']-noise_before)
        self.interpolations += 1
        return result

    def _interpolate(self, definition):
        if (self.x.ndim == self.y.ndim == self.z.ndim == 3
                and self.x.shape[:2] == (1, 1) and self.y.shape[::2] == (1, 1)
                and self.z.shape[1:] == (1, 1)):
            return self._regular_lattice(definition)
        coords = np.broadcast_arrays(self.x, self.y, self.z)
        flat = [a.ravel() for a in coords]
        blocks = np.stack([np.floor(a / BLOCK).astype(np.int64) for a in flat], axis=1)
        # Stable block order, then contiguous slices instead of one N-wide mask
        # per block. This leaves each group's node bounds and arithmetic intact.
        order = np.lexsort((blocks[:,2], blocks[:,1], blocks[:,0]))
        sorted_blocks = blocks[order]
        breaks = np.flatnonzero(np.any(sorted_blocks[1:] != sorted_blocks[:-1], axis=1)) + 1
        cuts = np.r_[0, breaks, len(order)] if len(order) else np.array([0])
        result = np.empty(int(np.prod(self.shape)), np.float32)
        steps = definition.steps
        for lo, hi in zip(cuts[:-1], cuts[1:]):
            mask = order[lo:hi]
            selected = [a[mask] for a in flat]
            nodes, starts = self._node_grid(definition, selected)
            local = [a / step - start for a, start,step in zip(selected, starts,steps)]
            ix, iy, iz = [np.floor(v).astype(np.intp) for v in local]
            tx, ty, tz = [v - i for v, i in zip(local, (ix, iy, iz))]
            planes = []
            for dz in (0, 1):
                rows = []
                for dy in (0,1):
                    a = nodes[iz+dz,iy+dy,ix].astype(np.float64)
                    b = nodes[iz+dz,iy+dy,ix+1].astype(np.float64)
                    rows.append(a+(b-a)*tx)
                planes.append(rows[0]+(rows[1]-rows[0])*ty)
            result[mask] = planes[0]+(planes[1]-planes[0])*tz
        result = result.reshape(self.shape)
        result.setflags(write=False)
        self.work_bytes = max(self.work_bytes, result.nbytes + blocks.nbytes + sorted_blocks.nbytes
                              + order.nbytes + breaks.nbytes + cuts.nbytes)
        return result

    def _block_nodes(self, definition, block):
        block = tuple(int(v) if a in definition.axes else 0 for a,v in zip('xyz',block))
        key = (self.key, definition.name, definition.steps, definition.axes, *block)
        def build():
            # Border nodes belong to the next canonical block.
            axes = [np.arange(v * BLOCK, (v + 1) * BLOCK, step, dtype=np.int64)
                    if a in definition.axes else np.array([0])
                    for a,v,step in zip('xyz',block,definition.steps)]
            sub = DensityContext(self.pack, self.params, self.seed, axes[0][None, None, :],
                                 axes[1][None, :, None], axes[2][:, None, None],
                                 resources=self.resources, key=self.key)
            nodes = sub._evaluate(definition)
            check_cancel(getattr(self.resources,'cancel_event',None))
            self._absorb(sub)
            return nodes
        return np.broadcast_to(self._blocks.get(key, build), tuple(BLOCK//s for s in definition.steps)[::-1])

    def _absorb(self, sub):
        self.evaluated += sub.evaluated
        self.timings.update(sub.timings)
        self.counters.update(sub.counters)
        self.interpolations += sub.interpolations
        self.work_bytes = max(self.work_bytes, sub.work_bytes)

    def _node_grid(self, definition, axes, *, padding=2):
        steps = definition.steps
        starts = [int(np.floor(a.min() / step)) for a,step in zip(axes,steps)]
        ends = [int(np.floor(a.max() / step)) + padding for a,step in zip(axes,steps)]
        counts = [b - a for a, b in zip(starts, ends)]
        grid = np.empty((counts[2], counts[1], counts[0]), np.float32)
        ranges = [range(a * step // BLOCK, ((b - 1) * step) // BLOCK + 1) for a,b,step in zip(starts,ends,steps)]
        self._prime_nodes(definition,ranges)
        for bz in ranges[2]:
            for by in ranges[1]:
                for bx in ranges[0]:
                    block = (bx, by, bz)
                    nodes = self._block_nodes(definition, block)
                    low = [max(a, v * BLOCK // step) for a,v,step in zip(starts,block,steps)]
                    high = [min(b, (v + 1) * BLOCK // step) for b,v,step in zip(ends,block,steps)]
                    target = tuple(slice(l - a, h - a) for l, h, a in zip(low, high, starts))[::-1]
                    source = tuple(slice(l-v*BLOCK//step,h-v*BLOCK//step) for l,h,v,step in zip(low,high,block,steps))[::-1]
                    grid[target] = nodes[source]
        self.work_bytes = max(self.work_bytes, grid.nbytes)
        return grid, starts

    def _prime_nodes(self, definition, ranges):
        """Evaluate neighbouring missing blocks together, then split them into canonical blocks.

        Do not expand a sparse request to an expensive enclosing volume:
        at most 25% redundant nodes are allowed in a batch.
        """
        from itertools import product
        candidates=tuple(product(*(r if a in definition.axes else (0,) for a,r in zip('xyz',ranges))))
        prefix=(self.key,definition.name,definition.steps,definition.axes)
        missing=[b for b in candidates if prefix+b not in self._blocks]
        if len(missing)<2: return
        low=tuple(min(b[i] for b in missing) for i in range(3))
        high=tuple(max(b[i] for b in missing)+1 for i in range(3))
        if np.prod(np.subtract(high,low))>len(missing)*1.25: return
        axes=[np.arange(lo*BLOCK,hi*BLOCK,step,dtype=np.int64) if a in definition.axes else np.array([0])
              for a,lo,hi,step in zip('xyz',low,high,definition.steps)]
        sub=DensityContext(self.pack,self.params,self.seed,axes[0][None,None,:],axes[1][None,:,None],
                           axes[2][:,None,None],resources=self.resources,key=self.key)
        values=sub._evaluate(definition)
        check_cancel(getattr(self.resources,'cancel_event',None))
        self._absorb(sub)
        self.work_bytes=max(self.work_bytes,sub.work_bytes+values.nbytes)
        for block in missing:
            slices=tuple(slice((v-lo)*BLOCK//step,(v-lo+1)*BLOCK//step) if a in definition.axes else slice(0,1)
                         for a,v,lo,step in zip('xyz',block,low,definition.steps))[::-1]
            nodes=values[slices].copy(); nodes.setflags(write=False)
            self._blocks.put(prefix+block,nodes)

    def _regular_lattice(self, definition):
        """Separable interpolation; no per-voxel sorting or eight full gathers."""
        steps = definition.steps
        axes = [a.ravel() for a in (self.x, self.y, self.z)]
        # Dependencies often request their own exact lattice nodes. Their
        # interpolation weights are all zero: take the stored nodes directly,
        # without evaluating an unused border or allocating float64 volumes.
        aligned = [a / step for a,step in zip(axes,steps)]
        if all(np.array_equal(a,np.floor(a)) for a in aligned):
            grid,starts = self._node_grid(definition,axes,padding=1)
            indices = [(a-start).astype(np.intp) for a,start in zip(aligned,starts)]
            result = grid[np.ix_(*indices[::-1])]
            result.setflags(write=False)
            self.counters['aligned_samples'] += 1
            return result
        grid, starts = self._node_grid(definition, axes)
        weight_key = (tuple(starts),steps,tuple(a.shape for a in axes))
        weights = self._weights.get(weight_key)
        if weights is None:
            positions = [a / step - start for a,start,step in zip(axes,starts,steps)]
            indices = [np.floor(a).astype(np.intp) for a in positions]
            weights = self._weights[weight_key] = (indices,[a-i for a,i in zip(positions,indices)])
        else:
            self.counters['weight_reuses'] += 1
        (ix,iy,iz),(tx,ty,tz) = weights
        grid = grid.astype(np.float64)
        a, b = grid[:,:,ix], grid[:,:,ix+1]
        along_x = b-a
        along_x *= tx[None,None,:]
        along_x += a
        a, b = along_x[:,iy,:], along_x[:,iy+1,:]
        along_y = b-a
        along_y *= ty[None,:,None]
        along_y += a
        a, b = along_y[iz], along_y[iz+1]
        interpolated = b-a
        interpolated *= tz[:,None,None]
        interpolated += a
        result = interpolated.astype(np.float32)
        result.setflags(write=False)
        self.work_bytes = max(self.work_bytes, grid.nbytes + along_x.nbytes + along_y.nbytes + result.nbytes * 5)
        return result


class WindowFields:
    """Share scalar interpolation across intersecting primitive windows.

    A union is admitted only while its volume is <=1.25 times the input
    volumes. Diagonal corridors therefore do not become a full core cube.
    """
    def __init__(self, ctx, windows):
        self.ctx, self.windows, self.groups = ctx, windows, {}
        self.arrays = []

    def get(self, name, target):
        if name not in self.groups:
            groups = [[w] for w in dict.fromkeys(self.windows[name])]
            changed = True
            while changed:
                changed = False
                for i in range(len(groups)):
                    a = self._bounds(groups[i])
                    for j in range(i+1,len(groups)):
                        b = self._bounds(groups[j])
                        combined = self._bounds(groups[i]+groups[j])
                        volume = lambda w: np.prod([hi-lo for lo,hi in w])
                        if all(al<=bh and bl<=ah for (al,ah),(bl,bh) in zip(a,b)) and volume(combined)<=1.25*(volume(a)+volume(b)):
                            groups[i] += groups.pop(j); changed=True; break
                    if changed: break
            sampled = []
            self.ctx.counters['window_reuses'] += len(self.windows[name]) - len(groups)
            for members in groups:
                bound = self._bounds(members)
                slices = tuple(slice(a,b) for a,b in bound)
                ctx = self.ctx
                # Coordinates may be axes, column-wise Y or paired sparse points.
                # Slice every varying dimension, retaining broadcast dimensions.
                def window(coordinate):
                    return coordinate[tuple(s if n != 1 else slice(None) for n, s in zip(coordinate.shape, slices))]
                sub = DensityContext(ctx.pack,ctx.params,ctx.seed,window(ctx.x),window(ctx.y),window(ctx.z),
                                     resources=ctx.resources,key=ctx.key)
                array = sub.get(name)
                ctx.evaluated += sub.evaluated
                ctx.timings.update(sub.timings)
                ctx.counters.update(sub.counters)
                ctx.interpolations += sub.interpolations
                ctx.work_bytes = max(ctx.work_bytes,sub.work_bytes)
                sampled.append((members,bound,array)); self.arrays.append(array)
            self.groups[name] = sampled
        for members,bound,array in self.groups[name]:
            if target in members:
                return array[tuple(slice(a-lo,b-lo) for (a,b),(lo,hi) in zip(target,bound))]
        raise KeyError((name,target))

    @staticmethod
    def _bounds(members):
        return tuple((min(w[i][0] for w in members),max(w[i][1] for w in members)) for i in range(3))
