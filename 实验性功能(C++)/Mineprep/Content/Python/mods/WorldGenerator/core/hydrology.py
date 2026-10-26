"""Immutable water geometry and spatial queries; independent of vanilla shaping.

Coordinates are Minecraft X/Z blocks. Drainage is only a layout proposal.
The output pipeline remains a heightfield and surface-water pipeline.
"""
from dataclasses import dataclass
import heapq
import numpy as np


def readonly(value, dtype=None):
    a = np.asarray(value, dtype=dtype)
    return np.frombuffer(a.tobytes(), dtype=a.dtype).reshape(a.shape)


def signed_distance(mask):
    """Exact raster Euclidean signed distance; negative inside, in grid units."""
    import cv2
    mask = np.asarray(mask, bool)
    outside = cv2.distanceTransform((~mask).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    inside = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    return (outside - inside).astype(np.float64)


def priority_flood(dem, sea):
    """Eight-edge drainage forest, deterministic ties, parents settled before children.

    The first settled neighbour claims a cell, avoiding crossed diagonal links.
    Every sea cell and planning boundary is an outlet.
"""
    rows, cols = dem.shape
    h = dem.ravel()
    filled = h.copy()
    parents = np.full(h.size, -1, np.int32)
    seen = np.zeros(h.size, bool)
    seeds = dem <= sea
    seeds[[0, -1], :] = True
    seeds[:, [0, -1]] = True
    heap = [(float(h[i]), int(i)) for i in np.flatnonzero(seeds)]
    heapq.heapify(heap)
    seen[seeds.ravel()] = True
    order = []
    while heap:
        level, i = heapq.heappop(heap)
        order.append(i)
        r, c = divmod(i, cols)
        neighbors = []
        if r: neighbors.append(i - cols)
        if c: neighbors.append(i - 1)
        if c + 1 < cols: neighbors.append(i + 1)
        if r + 1 < rows: neighbors.append(i + cols)
        if r and c: neighbors.append(i - cols - 1)
        if r and c + 1 < cols: neighbors.append(i - cols + 1)
        if r + 1 < rows and c: neighbors.append(i + cols - 1)
        if r + 1 < rows and c + 1 < cols: neighbors.append(i + cols + 1)
        for j in neighbors:
            if not seen[j]:
                seen[j] = True
                parents[j] = i
                filled[j] = max(level, float(h[j]))
                heapq.heappush(heap, (filled[j], j))
    area = np.full(h.size, 256., np.float64)
    for i in reversed(order):
        if parents[i] >= 0:
            area[parents[i]] += area[i]
    return filled.reshape(dem.shape), parents, area, np.asarray(order, np.int32)


@dataclass(frozen=True)
class WaterBody:
    id: int
    kind: int
    level: float
    depth: float
    bounds: tuple
    center: tuple = ()
    radii: tuple = ()
    distance_grid: object = None
    spill: tuple = ()

    def distance(self, x, z):
        if self.center:
            # A continuous asymmetric outline, not concentric circular steps.
            cx, cz = self.center
            rx, rz = self.radii
            angle = np.arctan2((z - cz) / rz, (x - cx) / rx)
            radius = np.sqrt(((x - cx) / rx) ** 2 + ((z - cz) / rz) ** 2)
            rim = 1 + .10 * np.sin(angle * 3 + self.id) + .06 * np.cos(angle * 5 - self.id)
            return (radius - rim) * min(rx, rz)
        x0, z0, _, _ = self.bounds
        return bilinear(self.distance_grid, (x - x0) / 16, (z - z0) / 16)


def bilinear(a, x, z):
    x = np.clip(x, 0, a.shape[1] - 1.000001)
    z = np.clip(z, 0, a.shape[0] - 1.000001)
    ix, iz = x.astype(np.intp), z.astype(np.intp)
    tx, tz = x - ix, z - iz
    return ((a[iz, ix] * (1 - tx) + a[iz, ix + 1] * tx) * (1 - tz)
            + (a[iz + 1, ix] * (1 - tx) + a[iz + 1, ix + 1] * tx) * tz)


@dataclass(frozen=True)
class WaterPlan:
    seed: int
    bounds: tuple
    dem: object
    filled: object
    parents: object
    catchment: object
    order: object
    edges: object             # node IDs, downstream-directed, acyclic
    node_positions: object    # world X/Z, shared endpoints including junctions
    segments: object          # ax,az,bx,bz,half_a,half_b,mouth_a,mouth_b
    sources: tuple
    junctions: tuple
    outlets: tuple            # (node, 'sea' | 'boundary')
    bodies: tuple
    stats: object
    bins: object
    body_bins: object
    bin_size: int = 64
    mouth_profiles: object = None  # float64[N,3]: distance_a, distance_b, outlet bed

    def __post_init__(self):
        if self.mouth_profiles is not None:
            profiles = np.asarray(self.mouth_profiles, dtype=np.float64)
            if profiles.shape != (len(self.segments), 3) or not np.isfinite(profiles).all():
                raise ValueError('mouth_profiles must be finite with shape (segment count, 3)')
            object.__setattr__(self, 'mouth_profiles', readonly(profiles))

    def validate_region(self, region):
        x0, z0, width, depth = self.bounds
        if not (x0 <= region.x0 and z0 <= region.z0
                and region.x0 + region.width <= x0 + width
                and region.z0 + region.depth <= z0 + depth):
            raise ValueError('生成范围超出固定水系规划；请调整水系规划起点或范围 / '
                             'output crop lies outside the fixed water planning bounds')

    def query(self, x, z, *, wet_mask=None):
        """Nearest continuous river segment, using bounded spatial bins.

        Queries visit only nearby segments and never traverse the entire graph.
        Each vector operation covers at most one 64-block spatial bin.
        """
        shape = (z.shape[0], x.shape[1])
        distance = np.full(shape, 1e6)
        half = np.zeros(shape)
        mouth = np.zeros(shape)
        sid = np.full(shape, -1, np.int32)
        bx = np.floor_divide(x[0].astype(np.int64), self.bin_size)
        bz = np.floor_divide(z[:, 0].astype(np.int64), self.bin_size)
        for iz in np.unique(bz):
            zi = np.flatnonzero(bz == iz)
            for ix in np.unique(bx):
                candidates = self.bins.get((int(ix), int(iz)), ())
                if not candidates:
                    continue
                xi = np.flatnonzero(bx == ix)
                target = np.ix_(zi, xi)
                xx, zz = x[:, xi], z[zi, :]
                best = distance[target].copy()
                wh, wm, wi = half[target].copy(), mouth[target].copy(), sid[target].copy()
                for offset in range(0, len(candidates), 24):
                    ids = np.asarray(candidates[offset:offset + 24])
                    s = self.segments[ids].T[:, :, None, None]
                    ax, az, ex, ez, wa, wb, ma, mb = s
                    dx, dz = ex - ax, ez - az
                    t = np.clip(((xx - ax) * dx + (zz - az) * dz) / np.maximum(dx * dx + dz * dz, 1e-12), 0, 1)
                    d = np.hypot(xx - ax - t * dx, zz - az - t * dz)
                    width = wa + (wb - wa) * t
                    score = d - width
                    if wet_mask is not None:
                        score = np.where((mb < 0) & ~wet_mask[target][None, ...], 1e12, score)
                    nearest = np.argmin(score, axis=0)[None, ...]
                    take = lambda a: np.take_along_axis(a, nearest, axis=0)[0]
                    bd, bw = take(d), take(width)
                    choose = take(score) < best - wh
                    best = np.where(choose, bd, best)
                    wh = np.where(choose, bw, wh)
                    wm = np.where(choose, take(ma + (mb - ma) * t), wm)
                    wi = np.where(choose, ids[nearest[0]], wi)
                distance[target], half[target], mouth[target], sid[target] = best, wh, wm, wi
        return distance, half, mouth, sid

    def nearby_bodies(self, x, z):
        ids = set()
        for iz in np.unique(np.floor_divide(z[:, 0].astype(np.int64), self.bin_size)):
            for ix in np.unique(np.floor_divide(x[0].astype(np.int64), self.bin_size)):
                ids.update(self.body_bins.get((int(ix), int(iz)), ()))
        return tuple(self.bodies[i] for i in sorted(ids))


def spatial_bins(bounds, padding, size=64):
    """Index geometry bounds; lists are frozen before exposing a plan."""
    bins = {}
    for i, (x0, z0, x1, z1) in enumerate(bounds):
        for z in range(int(np.floor((z0 - padding) / size)), int(np.floor((z1 + padding) / size)) + 1):
            for x in range(int(np.floor((x0 - padding) / size)), int(np.floor((x1 + padding) / size)) + 1):
                bins.setdefault((x, z), []).append(i)
    return {k: tuple(v) for k, v in bins.items()}
