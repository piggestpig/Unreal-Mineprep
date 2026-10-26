"""Bounded MC cell authoring. No Unreal, model imports or terrain mutation."""
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np
from mc_blockstates import connect as connect_cells, family, mirror_state, rotate_state

from .data import MAX_COORD, require_int
from .surface import block_name, parse_candidates
from .noise3 import fbm3, hash01
from .templates import rotate

MAX_BUILD_CELLS = 16_777_216
_PAINT_BATCH = 262_144
COLORS = ('white', 'orange', 'magenta', 'light_blue', 'yellow', 'lime', 'pink',
          'gray', 'light_gray', 'cyan', 'purple', 'blue', 'brown', 'green', 'red', 'black')


def integer_vector(value, name):
    a = np.asarray(value)
    if a.shape != (3,) or a.dtype.kind not in 'iu' or np.any(a < -MAX_COORD) or np.any(a > MAX_COORD):
        raise ValueError(f'{name}: needs three bounded MC integer coordinates')
    return a.astype(np.int64)


def _polygon_inside(u, v, profile):
    """Even-odd inclusion, including polygon edges, on broadcast coordinates."""
    shape = np.broadcast_shapes(u.shape, v.shape)
    inside, boundary = np.zeros(shape, bool), np.zeros(shape, bool)
    for (au, av), (bu, bv) in zip(profile, np.roll(profile, -1, axis=0)):
        du, dv = bu-au, bv-av
        cross = (u-au)*dv-(v-av)*du
        boundary |= ((np.abs(cross) <= 1e-9*max(1., math.hypot(du, dv)))
                     & (u >= min(au, bu)) & (u <= max(au, bu))
                     & (v >= min(av, bv)) & (v <= max(av, bv)))
        if dv != 0:
            inside ^= ((av > v) != (bv > v)) & (u < au+(v-av)*du/dv)
    return inside | boundary


def _state(block, states):
    name = block_name(block)
    if not isinstance(states, dict) or any(not isinstance(k, str) or not re.fullmatch(r'(?:[a-z0-9_.-]+:)?[a-z0-9_]+', k)
                                         for k in states):
        raise ValueError('block states: invalid property name')
    pairs = []
    for key, value in sorted(states.items()):
        if not isinstance(value, (str, bool, int)):
            raise ValueError('block states must be strings, integers or booleans')
        pairs.append((key, str(value).lower() if isinstance(value, bool) else str(value)))
    if name == 'air' and pairs:
        raise ValueError('air does not take block states')
    return name, tuple(pairs)


def _readonly(a, dtype):
    # A bytes-backed view cannot be made writable by changing NumPy flags.
    a = np.asarray(a, dtype=dtype)
    return np.frombuffer(a.tobytes(), dtype=a.dtype).reshape(a.shape)


@dataclass(frozen=True, eq=False)
class Structure:
    """Version-one recipe: bounds include air; xyz contains only occupied cells."""
    name: str
    origin: tuple
    size: tuple
    palette: tuple                   # ((native block name, ((state, value), ...)), ...)
    xyz: np.ndarray                 # local MC XYZ, not UE coordinates
    types: np.ndarray               # palette indices; air is omitted
    key: str = field(init=False)

    def __post_init__(self):
        origin = integer_vector(self.origin, 'origin')
        size = integer_vector(self.size, 'size')
        if np.any(size < 1) or np.any(origin < -(2**31-4)) or np.any(origin + size > 2**31-4):
            raise ValueError('structure bounds exceed local int32 coordinates')
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError('structure name must be nonempty')
        palette = tuple(_state(n, dict(p)) for n, p in self.palette)
        if len(palette) > 65535 or len(set(palette)) != len(palette) or any(n == 'air' for n, _ in palette):
            raise ValueError('structure palette must contain unique non-air states')
        p, t = np.asarray(self.xyz), np.asarray(self.types)
        if (p.ndim != 2 or p.shape[1:] != (3,) or p.dtype.kind not in 'iu'
                or t.shape != (len(p),) or t.dtype.kind not in 'iu'
                or np.any(p < origin) or np.any(p >= origin+size)
                or np.any(t < 0) or np.any(t >= len(palette))):
            raise ValueError('structure cells exceed bounds or palette')
        order = np.lexsort((p[:, 1], p[:, 2], p[:, 0]))
        p = p[order]
        if np.any(np.all(p[1:] == p[:-1], axis=1)):
            raise ValueError('structure contains duplicate cells')
        object.__setattr__(self, 'origin', tuple(map(int, origin)))
        object.__setattr__(self, 'size', tuple(map(int, size)))
        object.__setattr__(self, 'palette', palette)
        object.__setattr__(self, 'xyz', _readonly(p, np.int32))
        object.__setattr__(self, 'types', _readonly(t[order], np.uint16))
        h = hashlib.sha256(json.dumps((1, self.origin, self.size, self.palette), separators=(',', ':')).encode())
        h.update(self.xyz.tobytes())
        h.update(self.types.tobytes())
        object.__setattr__(self, 'key', h.hexdigest())

    @property
    def count(self):
        return len(self.xyz)

    def at(self, position, rotation=0):
        return Placement(self, position, rotation)

    def edit(self, *, max_cells=MAX_BUILD_CELLS):
        result = Builder(self.size, origin=self.origin, max_cells=max_cells)
        return result.paste(self, self.origin)

    def to_dict(self):
        return dict(version=1, name=self.name, origin=list(self.origin), size=list(self.size),
                    palette=[dict(block=n, states=dict(s)) for n, s in self.palette],
                    xyz=self.xyz.tolist(), types=self.types.tolist())

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
        return path

    @classmethod
    def load(cls, path, *, max_cells=MAX_BUILD_CELLS):
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
        keys = {'version', 'name', 'origin', 'size', 'palette', 'xyz', 'types'}
        if not isinstance(raw, dict) or set(raw) != keys or raw['version'] != 1:
            raise ValueError('unsupported structure recipe')
        size = integer_vector(raw['size'], 'size')
        require_int('max_cells', max_cells, 1, 2**63-1)
        if math.prod(map(int, size)) > max_cells:
            raise ValueError('structure exceeds max_cells')
        palette = tuple((p['block'], tuple(p['states'].items())) for p in raw['palette'])
        p = np.asarray(raw['xyz'])
        if not p.size:
            p = np.empty((0, 3), np.int32)
        t = np.asarray(raw['types']) if raw['types'] else np.empty(0, np.uint16)
        return cls(raw['name'], tuple(raw['origin']), tuple(size), palette, p, t)


@dataclass(frozen=True)
class Placement:
    structure: Structure
    position: tuple
    rotation: int = 0

    def __post_init__(self):
        if not isinstance(self.structure, Structure):
            raise TypeError('placement requires a Structure')
        object.__setattr__(self, 'position', tuple(map(int, integer_vector(self.position, 'position'))))
        if type(self.rotation) is not int or self.rotation not in (0, 90, 180, 270):
            raise ValueError('rotation must be 0, 90, 180 or 270 degrees')

    @property
    def points(self):
        return rotate(self.structure.xyz, self.rotation//90).astype(np.int64) + self.position


@dataclass(frozen=True, eq=False)
class Selection:
    """Snapshot of selected positions in one Builder; masks use local [Z,Y,X]."""
    _builder: object
    _lo: np.ndarray
    _mask: np.ndarray

    def __post_init__(self):
        object.__setattr__(self, '_lo', np.array(self._lo, dtype=np.int64, copy=True))
        self._lo.setflags(write=False)
        self._mask.setflags(write=False)

    @property
    def count(self):
        return int(np.count_nonzero(self._mask))

    @property
    def _hi(self):
        return self._lo + self._mask.shape[::-1]

    def _slices(self, lo, hi):
        a, b = lo-self._lo, hi-self._lo
        return tuple(slice(int(a[i]), int(b[i])) for i in (2, 1, 0))

    def shift(self, dx=0, dy=0, dz=0):
        """Translate this position snapshot in MC XYZ, clipping to its Builder."""
        offset = integer_vector((dx, dy, dz), 'selection shift')
        b = self._builder
        lo = np.clip(self._lo+offset, b.origin, b.origin+b.size)
        hi = np.clip(self._hi+offset, b.origin, b.origin+b.size)
        mask = (self._mask[self._slices(lo-offset, hi-offset)].copy()
                if np.all(lo < hi) else np.zeros((0, 0, 0), bool))
        return Selection(b, lo, mask)

    def _combine(self, other, operation):
        if not isinstance(other, Selection) or other._builder is not self._builder:
            raise ValueError('selections must belong to the same builder')
        if operation == 'union':
            lo, hi = np.minimum(self._lo, other._lo), np.maximum(self._hi, other._hi)
            mask = np.zeros(tuple((hi-lo)[::-1]), bool)
            for part in (self, other):
                a, b = part._lo-lo, part._hi-lo
                slices = tuple(slice(int(a[i]), int(b[i])) for i in (2, 1, 0))
                mask[slices] |= part._mask
        else:
            lo, hi = np.maximum(self._lo, other._lo), np.minimum(self._hi, other._hi)
            if operation == 'difference':
                mask = self._mask.copy()
                if np.all(lo < hi):
                    mask[self._slices(lo, hi)] &= ~other._mask[other._slices(lo, hi)]
                lo = self._lo
            elif np.all(lo < hi):
                mask = self._mask[self._slices(lo, hi)] & other._mask[other._slices(lo, hi)]
            else:
                mask = np.zeros((0, 0, 0), bool)
        return Selection(self._builder, lo, mask)

    def __and__(self, other):
        return self._combine(other, 'intersection')

    def __or__(self, other):
        return self._combine(other, 'union')

    def __sub__(self, other):
        return self._combine(other, 'difference')


class _BuilderCells:
    """Sparse rule access over a dense grid; only selected rule writes allocate states."""
    def __init__(self, builder):
        self.builder = builder

    def get(self, point):
        b = self.builder
        x, y, z = (point[i] - b.origin[i] for i in range(3))
        if not (0 <= x < b.size[0] and 0 <= y < b.size[1] and 0 <= z < b.size[2]):
            return None
        value = int(b._grid[z, y, x])
        if value:
            name, states = b._palette[value]
            return {'name': name, 'properties': dict(states)}
        return None

    __getitem__ = get

    def __setitem__(self, point, cell):
        b = self.builder
        x, y, z = (point[i] - b.origin[i] for i in range(3))
        b._grid[z, y, x] = b._id(cell['name'], cell['properties'])


class Builder:
    """Mutable uint16 grid [Z,Y,X]; MC XYZ inputs and chainable editing methods."""
    def __init__(self, size, *, origin=(0, 0, 0), max_cells=MAX_BUILD_CELLS):
        self.size = integer_vector(size, 'size')
        self.origin = integer_vector(origin, 'origin')
        require_int('max_cells', max_cells, 1, 2**63-1)
        if (np.any(self.size <= 0) or math.prod(map(int, self.size)) > max_cells
                or np.any(self.origin < -(2**31-4)) or np.any(self.origin+self.size > 2**31-4)):
            raise ValueError('builder exceeds max_cells or local coordinate bounds')
        self.size.setflags(write=False)
        self.origin.setflags(write=False)
        self.max_cells = max_cells
        self._grid = np.zeros(tuple(self.size[[2, 1, 0]]), np.uint16)
        self._palette = [('air', ())]
        self._ids = {self._palette[0]: 0}

    def _id(self, block, states):
        state = _state(block, states)
        if state not in self._ids:
            if len(self._palette) >= 65536:
                raise ValueError('builder exceeds 65535 non-air states')
            self._ids[state] = len(self._palette)
            self._palette.append(state)
        return self._ids[state]

    def _bounds(self, lo=None, hi=None):
        lo = self.origin if lo is None else integer_vector(lo, 'lower bound')
        hi = self.origin+self.size if hi is None else integer_vector(hi, 'upper bound')
        if np.any(lo < self.origin) or np.any(hi > self.origin+self.size) or np.any(lo >= hi):
            raise ValueError('region must be nonempty and inside builder bounds')
        a, b = lo-self.origin, hi-self.origin
        slices = tuple(slice(int(a[i]), int(b[i])) for i in (2, 1, 0))
        return lo, hi, self._grid[slices]

    def _palette_ids(self, palette):
        if len(self._palette) + len(set(palette) - self._ids.keys()) > 65536:
            raise ValueError('builder exceeds 65535 non-air states')
        return np.array([self._id(n, dict(s)) for n, s in palette], np.uint16)

    def select(self, lo=None, hi=None, *, blocks=None, surface=None):
        """Capture positions by bounds, block names and air-exposed faces."""
        lo, hi, grid = self._bounds(lo, hi)
        mask = np.ones(grid.shape, bool)
        if blocks is not None:
            names = {block_name(n) for n in ((blocks,) if isinstance(blocks, str) else blocks)}
            matching = np.array([n in names for n, _ in self._palette], bool)
            mask &= matching[grid]
        if surface is not None:
            directions = {'top': ((1, 1),), 'bottom': ((1, -1),),
                          'sides': ((0, -1), (0, 1), (2, -1), (2, 1))}
            directions['exposed'] = directions['top'] + directions['bottom'] + directions['sides']
            if surface not in directions:
                raise ValueError('surface must be exposed, top, bottom or sides')
            a, b = lo-self.origin, hi-self.origin
            halo_lo, halo_hi = np.maximum(a-1, 0), np.minimum(b+1, self.size)
            slices = tuple(slice(int(halo_lo[i]), int(halo_hi[i])) for i in (2, 1, 0))
            padding = tuple((int(a[i] == 0), int(b[i] == self.size[i])) for i in (2, 1, 0))
            occupied = np.pad(self._grid[slices] != 0, padding)
            exposed = np.zeros(grid.shape, bool)
            for axis, step in directions[surface]:
                neighbour = [slice(1, -1)] * 3
                neighbour[axis] = slice(2, None) if step > 0 else slice(None, -2)
                exposed |= ~occupied[tuple(neighbour)]
            mask &= (grid != 0) & exposed
        return Selection(self, lo, mask)

    def paint(self, material, selection=None, *, mode='solid', scale=8.0,
              seed=42, salt='paint', blend=1.0, **states):
        """Recolour existing cells with a solid block, smooth patches or height blend.

        Noise accepts names or (name, weight) pairs. Height accepts increasing
        (height, name) stops and uses seeded cell choices between adjacent stops.
        Height blend=0 makes hard bands; blend=1 preserves the full transition.
        New states replace old states. Explicit air deletes; air is never filled.
        """
        selection = self.select() if selection is None else selection
        if not isinstance(selection, Selection) or selection._builder is not self:
            raise ValueError('selection must belong to this builder')
        if mode == 'solid':
            names = (material,)
        elif mode == 'noise':
            if isinstance(scale, bool) or not math.isfinite(scale) or scale <= 0:
                raise ValueError('noise scale must be positive and finite')
            candidates = parse_candidates(material, 'paint')
            names = candidates.names
        elif mode == 'height':
            if isinstance(blend, bool) or not math.isfinite(blend) or not 0 <= blend <= 1:
                raise ValueError('height blend must be finite and between 0 and 1')
            stops = tuple(material)
            if len(stops) < 2 or any(len(stop) != 2 for stop in stops):
                raise ValueError('height paint needs at least two (height, block) stops')
            heights = np.asarray([stop[0] for stop in stops], dtype=float)
            if heights.shape != (len(stops),) or not np.isfinite(heights).all() or np.any(np.diff(heights) <= 0):
                raise ValueError('height stops must be finite and strictly increasing')
            names = tuple(stop[1] for stop in stops)
        else:
            raise ValueError('paint mode must be solid, noise or height')
        if mode != 'solid' and (type(seed) is not int or not isinstance(salt, str)):
            raise ValueError('paint seed must be an integer and salt a string')
        palette = tuple(_state(name, states) for name in names)
        if not selection._mask.size:
            return self
        lo, _, grid = self._bounds(selection._lo, selection._hi)
        mask = selection._mask & (grid != 0)
        if not mask.any():
            return self
        ids = self._palette_ids(palette)
        if mode == 'solid' or len(ids) == 1:
            grid[mask] = ids[0]
            return self
        flat = mask.ravel()
        for start in range(0, flat.size, _PAINT_BATCH):
            selected = np.flatnonzero(flat[start:start+_PAINT_BATCH]) + start
            if not len(selected):
                continue
            z, remainder = np.divmod(selected, grid.shape[1]*grid.shape[2])
            y, x = np.divmod(remainder, grid.shape[2])
            wx, wy, wz = x+lo[0], y+lo[1], z+lo[2]
            if mode == 'noise':
                values = fbm3((wx+.5)/scale, (wy+.5)/scale, (wz+.5)/scale,
                              seed=seed, salt=salt, octaves=2)
                chosen = np.searchsorted(candidates.cuts, values)
            else:
                interval = np.clip(np.searchsorted(heights, wy+.5, side='right')-1, 0, len(heights)-2)
                ratio = np.clip((wy+.5-heights[interval]) / (heights[interval+1]-heights[interval]), 0, 1)
                if blend == 0:
                    chosen = interval + (ratio >= .5)
                else:
                    if blend != 1:
                        ratio = np.clip((ratio-.5)/blend+.5, 0, 1)
                    chosen = interval + (hash01(wx, wy, wz, seed, salt+'/height') < ratio)
            grid[z, y, x] = ids[chosen]
        return self

    def connect(self, lo=None, hi=None, *, families=None):
        """Recompute selected links/corners, reading neighbours from the whole builder."""
        from ..adapters.resources import connection_full_cube
        lo, _, grid = self._bounds(lo, hi)
        families = None if families is None else tuple(families)
        selected = np.array([bool(family(n)) and (families is None or family(n) in families)
                             for n, _ in self._palette], bool)
        z, y, x = np.nonzero(selected[grid])
        connect_cells(_BuilderCells(self), is_full_cube=connection_full_cube(), families=families,
                      positions=zip(x + lo[0], y + lo[1], z + lo[2]))
        return self

    def set(self, block, xyz, **states):
        """Write coordinates or a same-Builder Selection, including air cells."""
        if isinstance(xyz, Selection):
            if xyz._builder is not self:
                raise ValueError('selection must belong to this builder')
            if xyz._mask.any():
                _, _, grid = self._bounds(xyz._lo, xyz._hi)
                grid[xyz._mask] = self._id(block, states)
            return self
        p = np.asarray(xyz)
        if p.shape == (3,):
            p = p[None]
        if p.ndim != 2 or p.shape[1:] != (3,) or p.dtype.kind not in 'iu':
            raise ValueError('set needs integer XYZ or [N,3] coordinates')
        if np.any(p < self.origin) or np.any(p >= self.origin+self.size):
            raise ValueError('set exceeds builder bounds')
        q = p-self.origin
        self._grid[q[:, 2], q[:, 1], q[:, 0]] = self._id(block, states)
        return self

    def box(self, block, lo=None, hi=None, *, hollow=False, **states):
        if type(hollow) is not bool:
            raise ValueError('hollow must be bool')
        _, _, a = self._bounds(lo, hi)
        value = self._id(block, states)
        if hollow:
            a[[0, -1], :, :] = value
            a[:, [0, -1], :] = value
            a[:, :, [0, -1]] = value
        else:
            a[:] = value
        return self

    def _shape(self, block, lo, hi, predicate, states):
        lo = np.maximum(np.floor(lo), self.origin).astype(np.int64)
        hi = np.minimum(np.ceil(hi), self.origin+self.size).astype(np.int64)
        if np.any(lo >= hi):
            return self
        _, _, a = self._bounds(lo, hi)
        x, y, z = (np.arange(lo[i], hi[i], dtype=np.float64)+.5 for i in range(3))
        mask = predicate(x[None, None, :], y[None, :, None], z[:, None, None])
        a[np.broadcast_to(mask, a.shape)] = self._id(block, states)
        return self

    def ellipsoid(self, block, center, radii, **states):
        center, radii = np.asarray(center, float), np.asarray(radii, float)
        if radii.shape == ():
            radii = np.repeat(radii, 3)
        if center.shape != (3,) or radii.shape != (3,) or not np.isfinite([center, radii]).all() or np.any(radii <= 0):
            raise ValueError('ellipsoid needs finite center and positive radii')
        return self._shape(block, center-radii, center+radii,
            lambda x, y, z: sum(((p-c)/r)**2 for p, c, r in zip((x, y, z), center, radii)) <= 1, states)

    def cylinder(self, block, base, radius, height, *, direction='y', **states):
        base = np.asarray(base, float)
        if (base.shape != (3,) or not np.isfinite(base).all() or direction not in ('x', 'y', 'z')
                or isinstance(radius, bool) or isinstance(height, bool)
                or not math.isfinite(radius) or not math.isfinite(height) or radius <= 0 or height <= 0):
            raise ValueError('cylinder needs finite base, positive radius/height and x/y/z direction')
        axis = 'xyz'.index(direction)
        lo, hi = base-radius, base+radius
        lo[axis], hi[axis] = base[axis], base[axis]+height
        def inside(x, y, z):
            v = (x, y, z)
            return ((v[axis] >= base[axis]) & (v[axis] < base[axis]+height)
                    & (sum((v[i]-base[i])**2 for i in range(3) if i != axis) <= radius**2))
        return self._shape(block, lo, hi, inside, states)

    def line(self, block, start, end, **states):
        a, b = integer_vector(start, 'start'), integer_vector(end, 'end')
        steps = int(np.abs(b-a).max())
        if steps >= int(self.size.max()) or np.any(np.minimum(a, b) < self.origin) or np.any(np.maximum(a, b) >= self.origin+self.size):
            raise ValueError('line exceeds builder bounds')
        t = np.linspace(0, 1, steps+1)[:, None]
        return self.set(block, np.floor(a+(b-a)*t+.5).astype(np.int64), **states)

    def tube(self, block, points, radii=1.0, **states):
        """Union of round-ended polyline segments with linearly varying radii."""
        points, radii = np.asarray(points, float), np.asarray(radii, float)
        if points.ndim != 2 or points.shape[1:] != (3,) or len(points) < 2 or not np.isfinite(points).all():
            raise ValueError('tube points must be at least two finite XYZ positions')
        if radii.shape == ():
            radii = np.full(len(points), radii)
        if (radii.shape != (len(points),) or not np.isfinite(radii).all()
                or np.any(radii < 0) or not np.any(radii > 0)
                or np.any(np.all(np.diff(points, axis=0) == 0, axis=1))):
            raise ValueError('tube needs nonnegative radii, one positive radius and distinct adjacent points')
        for a, b, ra, rb in zip(points[:-1], points[1:], radii[:-1], radii[1:]):
            delta = b-a
            length2 = float(delta @ delta)
            def inside(x, y, z):
                offset = (x-a[0], y-a[1], z-a[2])
                t = np.clip(sum(p*d for p,d in zip(offset, delta))/length2, 0, 1)
                distance2 = sum((p-t*d)**2 for p,d in zip(offset, delta))
                return distance2 <= (ra+t*(rb-ra))**2
            radius = max(ra, rb)
            self._shape(block, np.minimum(a, b)-radius, np.maximum(a, b)+radius, inside, states)
        return self

    def extrude(self, block, profile, base, height, *, direction='y', end_scale=1.0, **states):
        """Extrude a simple polygon along +X/+Y/+Z, scaling about base to end_scale.

        Profile UV maps to YZ/XZ/XY respectively. Polygon edges are included;
        the axial upper bound is excluded. Concave profiles are supported.
        """
        profile, base = np.asarray(profile, float), np.asarray(base, float)
        if (profile.ndim != 2 or profile.shape[1:] != (2,) or len(profile) < 3
                or not np.isfinite(profile).all() or base.shape != (3,) or not np.isfinite(base).all()):
            raise ValueError('extrude needs a finite polygon [N,2] and XYZ base')
        if (direction not in ('x', 'y', 'z') or isinstance(height, bool) or not math.isfinite(height)
                or height <= 0 or isinstance(end_scale, bool) or not math.isfinite(end_scale) or end_scale < 0):
            raise ValueError('extrude needs x/y/z direction, positive height and nonnegative end_scale')
        following = np.roll(profile, -1, axis=0)
        if np.sum(profile[:,0]*following[:,1]-following[:,0]*profile[:,1]) == 0:
            raise ValueError('extrude profile must have nonzero area')
        axis = 'xyz'.index(direction)
        u, v = (i for i in range(3) if i != axis)
        ends = np.concatenate((profile, profile*end_scale))
        lo, hi = base.copy(), base.copy()
        lo[[u,v]], hi[[u,v]] = base[[u,v]]+ends.min(axis=0), base[[u,v]]+ends.max(axis=0)
        hi[axis] += height
        def inside(x, y, z):
            coords = (x, y, z)
            along = coords[axis]-base[axis]
            first, second = coords[u]-base[u], coords[v]-base[v]
            active = (along >= 0) & (along < height)
            if end_scale != 1:
                scale = 1 + np.clip(along/height, 0, 1)*(end_scale-1)
                active = active & (scale > 0)
                divisor = np.where(scale > 0, scale, 1.)
                first, second = first/divisor, second/divisor
            return active & _polygon_inside(first, second, profile)
        return self._shape(block, lo, hi, inside, states)

    def replace(self, old, new, lo=None, hi=None, **states):
        old = block_name(old)
        _, _, a = self._bounds(lo, hi)
        matching = np.array([n == old for n, _ in self._palette], bool)
        mask = matching[a]
        a[mask] = self._id(new, states)
        return self

    def copy(self, lo=None, hi=None, *, name='copy'):
        lo, hi, a = self._bounds(lo, hi)
        result = Builder(hi-lo, max_cells=self.max_cells)
        result._grid[:] = a
        result._palette = list(self._palette)
        result._ids = dict(self._ids)
        return result.freeze(name)

    def paste(self, structure, at, *, mode='replace', rotation=0):
        if not isinstance(structure, Structure) or mode not in ('replace', 'keep'):
            raise ValueError('paste requires a Structure and replace/keep mode')
        if type(rotation) is not int or rotation not in (0, 90, 180, 270):
            raise ValueError('rotation must be 0, 90, 180 or 270 degrees')
        at = integer_vector(at, 'paste position')
        turns = rotation // 90
        corners = rotate(np.array([[0, 0, 0], np.asarray(structure.size)-1]), turns)
        minimum = corners.min(axis=0)
        size = corners.max(axis=0)-minimum+1
        _, _, target = self._bounds(at, at+size)
        palette = tuple((n, tuple(sorted(rotate_state(n, dict(s), turns).items())))
                        for n, s in structure.palette) if turns else structure.palette
        ids = self._palette_ids(palette)
        q = structure.xyz.astype(np.int64)-structure.origin
        if turns:
            q = rotate(q, turns)-minimum
        values = ids[structure.types]
        if mode == 'replace':
            target[:] = 0
        else:
            keep = target[q[:, 2], q[:, 1], q[:, 0]] == 0
            q, values = q[keep], values[keep]
        target[q[:, 2], q[:, 1], q[:, 0]] = values
        return self

    def mirror(self, axis='x', *, lo=None, hi=None):
        """Replace a region with its X/Z reflection about that region's centre, including air."""
        if axis not in ('x', 'z'):
            raise ValueError("mirror axis must be 'x' or 'z'")
        _, _, grid = self._bounds(lo, hi)
        used = np.unique(grid)
        palette = tuple((n, tuple(sorted(mirror_state(n, dict(s), axis).items())))
                        for n, s in (self._palette[i] for i in used))
        ids = self._palette_ids(palette)
        remap = np.zeros(len(self._palette), np.uint16)
        remap[used] = ids
        grid[:] = remap[np.flip(grid, axis=2 if axis == 'x' else 0)]
        return self

    def freeze(self, name='structure'):
        z, y, x = np.nonzero(self._grid)
        values = self._grid[z, y, x]
        used = sorted(np.unique(values).tolist(), key=lambda i: self._palette[i])
        remap = np.zeros(len(self._palette), np.uint16)
        remap[used] = np.arange(len(used), dtype=np.uint16)
        xyz = np.column_stack((x, y, z))+self.origin
        return Structure(name, tuple(self.origin), tuple(self.size), tuple(self._palette[i] for i in used),
                         xyz, remap[values])
