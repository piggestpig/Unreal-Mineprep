"""FieldGraph: named 2D fields, evaluated once per tile, optionally on a coarse lattice.

A Pack module declares fields with the `@field` decorator:

    @field("height", deps=("base_height",), res=1)
    def height(ctx, base):
        return base + 2 * ctx.noise("custom/detail", 24)

`res=r` evaluates the function on a world-aligned lattice with an r-block step
and interpolates (Catmull-Rom) to the requesting grid. Lattice points sit at
multiples of r in world coordinates, so every tile sees identical node values
and tiles join without seams. Fields are pure functions of world position,
seed and parameters. A res=1 field may declare `halo=n` for a bounded local
operation: its dependencies are sampled n blocks farther out, then cropped.
Pipeline operations such as slope still use their own halo.
"""

from contextlib import contextmanager
import contextvars
from dataclasses import dataclass
import inspect

import numpy as np

from .noise import fbm2, perlin2, ridged2, seed_key, _hash64

RESOLUTIONS = (1, 2, 4, 8, 16, 32)
# Blocks of extra coverage per lattice step. A step-r lattice spans one node
# before and two after its extent, so a step-R lattice brackets every finer
# lattice when E[R] >= E[r] + 2r; E[r] = E[r/2] + r satisfies that.
_EXTENT = {1: 0, 2: 0, 4: 4, 8: 12, 16: 28, 32: 60}
_active_passes = contextvars.ContextVar('worldgen_region_passes', default=None)
_active_region = contextvars.ContextVar('worldgen_active_region', default=None)


def active_region():
    return _active_region.get()


@contextmanager
def active_passes(passes, region=None):
    """Install pass windows; (None, None) means prepared but outside this task."""
    token = _active_passes.set(passes)
    rtoken = _active_region.set(region) if region is not None else None
    try:
        yield passes
    finally:
        if rtoken is not None:
            _active_region.reset(rtoken)
        _active_passes.reset(token)


@dataclass(frozen=True)
class FieldDef:
    name: str
    fn: object
    deps: tuple = ()
    res: int = 1
    doc: str = ""
    halo: int = 0
    resources: tuple = ()
    region_pass: bool = False
    margin: int = 0
    region: object = None
    outside: object = None

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.isidentifier():
            raise ValueError(f"field name must be an identifier: {self.name!r}")
        if self.res not in RESOLUTIONS:
            raise ValueError(f"field {self.name}: res must be one of {RESOLUTIONS}")
        if type(self.halo) is not int or self.halo < 0 or (self.halo and self.res != 1):
            raise ValueError(f"field {self.name}: halo must be a nonnegative integer, with res=1")
        if type(self.margin) is not int or self.margin < 0 or (self.margin and not self.region_pass):
            raise ValueError(f"field {self.name}: margin must be a nonnegative integer on a region_pass")
        if self.region_pass and (self.res != 1 or self.halo):
            raise ValueError(f"field {self.name}: region_pass requires res=1 and uses margin instead of halo")
        if self.region is not None:
            if not self.region_pass:
                raise ValueError(f"field {self.name}: region is only valid on a region_pass")
            from .data import Region
            if not isinstance(self.region, Region):
                if (not isinstance(self.region, (tuple, list)) or len(self.region) != 4
                        or any(type(v) is not int for v in self.region)):
                    raise ValueError(f"field {self.name}: region must be a Region or (x0, z0, width, depth)")
                object.__setattr__(self, 'region', Region(*self.region))
        if self.outside is not None:
            if not self.region_pass:
                raise ValueError(f"field {self.name}: outside is only valid on a region_pass")
            if isinstance(self.outside, str):
                if not self.outside.isidentifier():
                    raise ValueError(f"field {self.name}: outside field must be an identifier")
            elif isinstance(self.outside, bool) or not isinstance(self.outside, (int, float)) or not np.isfinite(self.outside):
                raise ValueError(f"field {self.name}: outside must be a field name or finite number")
        if len(inspect.signature(self.fn).parameters) != 1 + len(self.deps):
            raise ValueError(f"field {self.name}: function takes ctx plus one argument per dep")


def field(name, *, deps=(), res=1, halo=0, resources=()):
    """Decorator; returns a FieldDef that the Pack loader collects from the module."""
    def wrap(fn):
        return FieldDef(name, fn, tuple(deps), res, (fn.__doc__ or "").strip(), halo, tuple(resources))
    return wrap


def region_pass(name, *, deps=(), margin=0, region=None, outside=None, resources=()):
    """Declare a whole-region 2D pass in the field graph."""
    def wrap(fn):
        return FieldDef(name, fn, tuple(deps), 1, (fn.__doc__ or "").strip(), 0, tuple(resources),
                        region_pass=True, margin=margin, region=region, outside=outside)
    return wrap


def _deps(f):
    out = getattr(f, "outside", None)
    return (*f.deps, *((out,) if isinstance(out, str) else ()))


def check_graph(fields):
    """Reject unknown dependencies and cycles when a Pack is loaded."""
    state = {}

    def visit(name, path):
        if name not in fields:
            raise ValueError(f"field {path[-1] if path else '?'} depends on unknown field {name!r}")
        if state.get(name) == 1:
            raise ValueError("field cycle: " + " -> ".join(path + (name,)))
        if state.get(name) == 2:
            return
        state[name] = 1
        for dep in _deps(fields[name]):
            visit(dep, path + (name,))
        state[name] = 2

    for name in fields:
        visit(name, ())


def pass_order(fields):
    """Topological order of @region_pass fields, downstream pads, and resource flags."""
    order, seen = [], set()
    def visit(name):
        if name in seen or name not in fields:
            return
        seen.add(name)
        for dep in _deps(fields[name]):
            visit(dep)
        order.append(name)
    for name in fields:
        visit(name)
    pads = {name: 0 for name in order}
    for name in reversed(order):
        f = fields[name]
        need = pads[name] + f.halo + f.margin
        # Match _coarse: its aligned lattice extends beyond the requesting grid.
        if f.res > 1:
            need += _EXTENT[f.res] + 2 * f.res
        for dep in _deps(f):
            if dep in pads and need > pads[dep]:
                pads[dep] = need
    uses_res = {}
    for name in order:
        f = fields[name]
        uses_res[name] = bool(f.resources) or any(uses_res.get(d, False) for d in _deps(f))
    passes = tuple(name for name in order if fields[name].region_pass)
    return passes, {n: pads[n] for n in passes}, {n: uses_res[n] for n in passes}


def _catmull_rom(t):
    t2, t3 = t * t, t * t * t
    return (-0.5 * t3 + t2 - 0.5 * t, 1.5 * t3 - 2.5 * t2 + 1.0,
            -1.5 * t3 + 2.0 * t2 + 0.5 * t, 0.5 * t3 - 0.5 * t2)


def _interp_axis(values, coords, start, step, axis):
    """Interpolate `values` (lattice index start.. along axis) at world coords."""
    u = coords / step - start
    i = np.floor(u).astype(np.intp)
    weights = _catmull_rom(u - i)
    result = 0.0
    for k, w in enumerate(weights):
        taken = np.take(values, i + (k - 1), axis=axis)
        result = result + (taken * (w[None, :] if axis == 1 else w[:, None]))
    return result


class Context:
    """One tile sampled at one lattice step. Fields are memoized per context.

    `x` is float64[1,X] and `z` float64[Z,1] world block coordinates.
    """

    def __init__(self, fields, params, seed, x, z, step=1, *, lattice=None, root=None, resources=None):
        self.fields, self.params, self.seed = fields, params, seed
        self.x, self.z, self.step = x, z, step
        self.shape = (z.shape[0], x.shape[1])
        self.lattice = lattice  # (ix0, iz0) lattice index of [0, 0], or None at step 1
        self._root = root or self
        self.resources = root.resources if root is not None else resources
        self._cache = {}
        self._halos = {}
        self._grid_samples = {}
        if root is None:
            self._contexts = {step: self}
            self._passes = {}
            self.stats = {"evaluated": {}}

    @classmethod
    def for_region(cls, fields, params, seed, region, *, resources=None):
        x, z = region.coordinates()
        return cls(fields, params, seed, x.astype(np.float64), z.astype(np.float64), resources=resources)

    def resource(self, name):
        """Request a declared, crop-independent planning resource lazily."""
        if self.resources is None:
            raise ValueError(f'field requires planning resource {name!r}')
        return self.resources.get(name)

    # -- inputs for field functions -------------------------------------
    def param(self, key):
        return self.params[key]

    def curve(self, key):
        """Spline object for a 'curve' parameter (points are validated by the Pack)."""
        return self.params.curve(key)

    def noise(self, salt, scale, *, octaves=1, lacunarity=2.0, persistence=0.5, kind="fbm"):
        """Seeded noise at this grid, `scale` blocks per lattice cell; memoized by args."""
        key = ("noise", salt, float(scale), octaves, lacunarity, persistence, kind)
        cached = self._cache.get(key)
        if cached is None:
            x, z = self.x / scale, self.z / scale
            if kind == "perlin":
                cached = perlin2(x, z, seed=self.seed, salt=salt)
            else:
                function = ridged2 if kind == "ridged" else fbm2
                cached = function(x, z, seed=self.seed, salt=salt, octaves=octaves,
                                  lacunarity=lacunarity, persistence=persistence)
            self._cache[key] = cached
        return cached

    def grid_sample(self, name, *, step=4, strength=1.8, salt='climate/cells'):
        """Sample a field through shared jittered 2D cells, without smoothing labels.

        Zero strength preserves the ordinary field path exactly. The temporary
        source grid and selection are shared by consumers in this context only.
        """
        if not strength:
            return self.get(name)
        if step not in RESOLUTIONS or not 0 <= strength <= step / 2:
            raise ValueError('grid_sample needs a supported step and strength in [0, step/2]')
        key = ('grid_sample', step, float(strength), salt)
        mapping = self._grid_samples.get(key)
        if mapping is None:
            cx = np.floor(self.x / step).astype(np.int64)
            cz = np.floor(self.z / step).astype(np.int64)
            x0, z0 = int(cx.min()), int(cz.min())
            gx = np.arange(x0, int(cx.max()) + 2)[None, :]
            gz = np.arange(z0, int(cz.max()) + 2)[:, None]
            source = Context(self.fields, self.params, self.seed, gx * float(step), gz * float(step),
                             step, lattice=(x0,z0), root=self._root)
            hx = _hash64(gx, gz, seed_key(self.seed, salt+'/x')[0])
            hz = _hash64(gx, gz, seed_key(self.seed, salt+'/z')[0])
            jx = ((hx >> np.uint64(11)).astype(np.float64) / 2**53 - .5) * 2 * strength
            jz = ((hz >> np.uint64(11)).astype(np.float64) / 2**53 - .5) * 2 * strength
            best = np.full(self.shape, np.inf)
            ix = np.zeros(self.shape, np.intp); iz = np.zeros(self.shape, np.intp)
            for dz, dx in ((0,0),(0,1),(1,0),(1,1)):
                xx, zz = cx-x0+dx, cz-z0+dz
                distance = (self.x-(cx+dx)*step-jx[zz,xx])**2 + (self.z-(cz+dz)*step-jz[zz,xx])**2
                use = distance < best
                best[use] = distance[use]
                ix[use] = np.broadcast_to(xx,self.shape)[use]
                iz[use] = np.broadcast_to(zz,self.shape)[use]
            mapping = source, iz, ix
            self._grid_samples[key] = mapping
        source, iz, ix = mapping
        return source.get(name)[iz,ix]

    # -- evaluation ------------------------------------------------------
    def put(self, name, value):
        """Inject a pipeline-computed field (e.g. slope) so rules can reference it."""
        self._cache[name] = value

    def has(self, name):
        return name in self._cache or name in self.fields

    def get(self, name):
        cached = self._cache.get(name)
        if cached is not None:
            return cached
        definition = self.fields.get(name)
        if definition is None:
            raise KeyError(f"unknown field {name!r}")
        if definition.region_pass:
            value = self._sample_pass(definition)
        elif definition.halo:
            expanded = self._expanded(definition.halo)
            full = expanded._evaluate(definition)
            h = definition.halo
            # A coarse consumer still needs unit-block neighbourhood samples.
            value = full[h:-h:self.step, h:-h:self.step].copy()
        elif definition.res > self.step:
            coarse = self._root._coarse(definition.res)
            value = self._upsample(coarse, coarse.get(name))
        else:
            value = self._evaluate(definition)
        self._cache[name] = value
        return value

    def _sample_pass(self, d):
        from .data import Region
        active = _active_passes.get()
        entry = active.get(d.name) if active else None
        if entry is None:
            rx0, rx1 = int(np.floor(self.x[0, 0])), int(np.ceil(self.x[0, -1]))
            rz0, rz1 = int(np.floor(self.z[0, 0])), int(np.ceil(self.z[-1, 0]))
            needed = d.region or Region(rx0, rz0, rx1 - rx0 + 1, rz1 - rz0 + 1)
            cached = self._root._passes.get(d.name)
            if cached and (d.region or (cached[0].x0 <= needed.x0 and cached[0].z0 <= needed.z0
                    and needed.x0 + needed.width <= cached[0].x0 + cached[0].width
                    and needed.z0 + needed.depth <= cached[0].z0 + cached[0].depth)):
                entry = cached
            else:
                m = d.margin
                ctx = Context.for_region(self.fields, self.params, self.seed, needed.expanded(m), resources=self.resources)
                ctx.stats, ctx._passes = self._root.stats, self._root._passes
                full = ctx._evaluate(d)
                if not np.isfinite(full).all():
                    raise ValueError(f"field {d.name}: region_pass must return finite values")
                arr = full[m:full.shape[0] - m, m:full.shape[1] - m].copy()
                arr.setflags(write=False)
                entry = self._root._passes[d.name] = (needed, arr)
        region, values = entry
        if region is None:
            return self._pass_outside(d)
        ix = np.rint(self.x).astype(np.intp) - region.x0
        iz = np.rint(self.z).astype(np.intp) - region.z0
        if self.step == 1 and 0 <= ix[0, 0] and ix[0, -1] < region.width and 0 <= iz[0, 0] and iz[-1, 0] < region.depth:
            return values[iz[0, 0]:iz[-1, 0] + 1, ix[0, 0]:ix[0, -1] + 1]
        in_x, in_z = (ix >= 0) & (ix < region.width), (iz >= 0) & (iz < region.depth)
        if in_x.all() and in_z.all():
            return values[iz, ix].copy()
        res = self._pass_outside(d)
        if in_x.any() and in_z.any():
            inside = in_z & in_x
            zz, xx = np.broadcast_arrays(iz, ix)
            res[inside] = values[zz[inside], xx[inside]]
        return res

    def _pass_outside(self, definition):
        out = definition.outside
        if out is None:
            out = definition.deps[0] if definition.deps else 0.0
        value = self.get(out) if isinstance(out, str) else out
        return np.broadcast_to(np.asarray(value, dtype=np.float64), self.shape).copy()

    def _evaluate(self, definition):
        value = np.asarray(definition.fn(self, *(self.get(d) for d in definition.deps)),
                           dtype=np.float64)
        if value.shape != self.shape:
            value = np.broadcast_to(value, self.shape).copy()
        counts = self._root.stats["evaluated"]
        key = (definition.name, self.step)
        counts[key] = counts.get(key, 0) + 1
        return value

    def _expanded(self, halo):
        context = self._halos.get(halo)
        if context is None:
            x = np.arange(self.x[0, 0] - halo, self.x[0, -1] + halo + 1)[None, :]
            z = np.arange(self.z[0, 0] - halo, self.z[-1, 0] + halo + 1)[:, None]
            context = Context(self.fields, self.params, self.seed, x, z, resources=self.resources)
            context.stats = self._root.stats
            context._passes = self._root._passes
            self._halos[halo] = context
        return context

    def _coarse(self, step):
        context = self._contexts.get(step)
        if context is None:
            pad = _EXTENT[step]
            x0, x1 = self.x[0, 0] - pad, self.x[0, -1] + pad
            z0, z1 = self.z[0, 0] - pad, self.z[-1, 0] + pad
            ix0, iz0 = int(np.floor(x0 / step)) - 1, int(np.floor(z0 / step)) - 1
            ix1, iz1 = int(np.floor(x1 / step)) + 2, int(np.floor(z1 / step)) + 2
            x = (np.arange(ix0, ix1 + 1, dtype=np.float64) * step)[None, :]
            z = (np.arange(iz0, iz1 + 1, dtype=np.float64) * step)[:, None]
            context = Context(self.fields, self.params, self.seed, x, z, step,
                              lattice=(ix0, iz0), root=self)
            self._contexts[step] = context
        return context

    def _upsample(self, coarse, values):
        ix0, iz0 = coarse.lattice
        rows = _interp_axis(values, self.x[0], ix0, coarse.step, axis=1)
        return _interp_axis(rows, self.z[:, 0], iz0, coarse.step, axis=0)
