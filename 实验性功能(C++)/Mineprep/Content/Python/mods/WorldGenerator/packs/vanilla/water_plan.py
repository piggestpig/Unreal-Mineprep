"""Vanilla appearance-first layout: coarse drainage proposals, curves and basins."""
from time import perf_counter
from dataclasses import replace

import numpy as np

from ...core.fields import Context
from ...core.planning import FieldWindows
from ...core.hydrology import WaterBody, WaterPlan, priority_flood, readonly, spatial_bins, signed_distance
from ...core.noise import seed_key
from .terrain import _smooth


def _candidate(seed, x, z):
    key = int(seed_key(seed, 'water/pond')[0])
    value = ((x * 0x9E3779B185EBCA87) ^ (z * 0xC2B2AE3D27D4EB4F) ^ key) & (2**64 - 1)
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & (2**64 - 1)
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & (2**64 - 1)
    return ((value ^ (value >> 31)) >> 11) / 2**53


def _rounded_path(points, widths, mouth):
    """Round degree-two corners inside their grid cells, preserving junctions.

    Straight edges and convex quadratic arcs cannot overshoot the original
    drainage skeleton. Shared endpoint coordinates remain exactly identical.
    """
    samples = [(points[0], widths[0], mouth[0])]
    for i in range(1, len(points) - 1):
        p, c, n = points[i - 1:i + 2]
        v, w = c - p, n - c
        if np.dot(v, w) / (np.linalg.norm(v) * np.linalg.norm(w)) > .98:
            samples.append((c, widths[i], mouth[i]))
            continue
        a, b = c + .3 * (p - c), c + .3 * (n - c)
        wa = widths[i] + .3 * (widths[i - 1] - widths[i])
        wb = widths[i] + .3 * (widths[i + 1] - widths[i])
        samples.append((a, wa, mouth[i] + .3 * (mouth[i - 1] - mouth[i])))
        for t in (.5, 1.):
            pos = (1 - t) ** 2 * a + 2 * t * (1 - t) * c + t * t * b
            samples.append((pos, wa * (1 - t) + wb * t, mouth[i]))
    samples.append((points[-1], widths[-1], mouth[-1]))
    result = []
    for (a, wa, ma), (b, wb, mb) in zip(samples, samples[1:]):
        if np.linalg.norm(a - b) > 1e-8:
            result.append((*a, *b, wa, wb, ma, mb))
    return result


def _lake_candidates(dem, filled, x0, z0, params):
    if not params['lakes.enabled']:
        return []
    import cv2
    depression = (filled - dem >= params['lakes.min_depression']).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStatsWithAlgorithm(
        depression, 4, cv2.CV_32S, cv2.CCL_WU)
    bodies = []
    for label in range(1, count):
        c_left, r_top, width, height, area = (int(v) for v in stats[label])
        if area * 256 < params['lakes.min_area']:
            continue
        box = (slice(r_top, r_top + height), slice(c_left, c_left + width))
        member = labels[box] == label
        rows, cols = np.nonzero(member)
        rows, cols = rows + r_top, cols + c_left
        spill_height = float(np.min(filled[rows, cols]))
        level = max(float(np.floor(spill_height) - 1), float(params['world.sea_level']))
        # Flooded region at this body's fixed level, restricted to its basin.
        basin = member & (dem[box] < level)
        if int(basin.sum()) * 256 < params['lakes.min_area']:
            continue
        rr, cc = np.nonzero(basin)
        r0, r1 = max(0, int(rr.min()) + r_top - 2), min(dem.shape[0], int(rr.max()) + r_top + 3)
        c0, c1 = max(0, int(cc.min()) + c_left - 2), min(dem.shape[1], int(cc.max()) + c_left + 3)
        if r0 == 0 or c0 == 0 or r1 == dem.shape[0] or c1 == dem.shape[1]:
            continue  # complete containment required, never crop a lake at an edge
        mask = (labels[r0:r1, c0:c1] == label) & (dem[r0:r1, c0:c1] < level)
        sdf = signed_distance(mask) * 16
        # Spill location is metadata; high lakes do not draw an elevated outlet.
        k = int(np.argmin(filled[rows, cols]))
        bodies.append(WaterBody(len(bodies) + 1, 3, level, params['lakes.depth'],
                                (x0 + c0 * 16, z0 + r0 * 16, (c1 - c0 - 1) * 16, (r1 - r0 - 1) * 16),
                                distance_grid=readonly(sdf),
                                spill=(x0 + int(cols[k]) * 16, z0 + int(rows[k]) * 16, spill_height)))
    return bodies


def _conflict(body, others, segments, sea):
    # Conservative dry separation for different levels. Equal-level contact
    # belongs to one water surface; classification may retain local body IDs.
    x0, z0, w, d = body.bounds
    for other in others:
        if body.level == other.level:
            continue
        ox, oz, ow, od = other.bounds
        if x0 < ox + ow + 4 and ox < x0 + w + 4 and z0 < oz + od + 4 and oz < z0 + d + 4:
            return True
    if body.level != sea and len(segments):
        # Width plus valley: elevated bodies must not touch a sea-level river.
        padding = np.maximum(segments[:, 4], segments[:, 5]) + 68
        contact = ((np.minimum(segments[:, 0], segments[:, 2]) - padding < x0 + w)
                   & (np.maximum(segments[:, 0], segments[:, 2]) + padding > x0)
                   & (np.minimum(segments[:, 1], segments[:, 3]) - padding < z0 + d)
                   & (np.maximum(segments[:, 1], segments[:, 3]) + padding > z0))
        if contact.any():
            return True
    return False


def _lake_window(body):
    x0, z0, w, d = body.bounds
    return x0, z0, x0 + w, z0 + d


def _contain_lake(body, params, fine):
    """Verify the fine shoreline before accepting an independent elevated lake."""
    if body.level <= params['world.sea_level']:
        return body
    x0, z0, w, d = body.bounds
    x = np.arange(x0, x0 + w + 1, dtype=np.float64)[None, :]
    z = np.arange(z0, z0 + d + 1, dtype=np.float64)[:, None]
    distance = body.distance(x, z)
    ring = (distance >= 0) & (distance <= 2)
    if not ring.any():
        return None
    height = fine.get(_lake_window(body))
    ring_height = np.where(ring, height, np.inf)
    iz, ix = np.unravel_index(np.argmin(ring_height), height.shape)
    spill = min(body.spill[2], float(height[iz, ix]))
    level = float(np.floor(spill) - 1)
    if level <= params['world.sea_level']:
        return None  # do not invent a sea-level connection for an elevated basin
    return replace(body, level=level, spill=(float(x[0, ix]), float(z[iz, 0]), spill))


def _merge_body_id(body, others):
    """Touching equal-level geometry fragments share one stable waterbody ID."""
    ids = {body.id}
    for other in others:
        if other.level != body.level:
            continue
        ax, az, aw, ad = body.bounds
        bx, bz, bw, bd = other.bounds
        x0, z0 = max(ax, bx) - 1, max(az, bz) - 1
        x1, z1 = min(ax + aw, bx + bw) + 1, min(az + ad, bz + bd) + 1
        if x0 > x1 or z0 > z1:
            continue
        x, z = np.arange(x0, x1 + 1)[None, :], np.arange(z0, z1 + 1)[:, None]
        if ((body.distance(x, z) <= 1) & (other.distance(x, z) <= 1)).any():
            ids.add(other.id)
    canonical = min(ids)
    if len(ids) > 1:
        others[:] = [replace(b, id=canonical) if b.id in ids else b for b in others]
    return replace(body, id=canonical)


def _outlet_window(position, bounds, radius):
    x0, z0, size = bounds
    cx, cz = np.rint(position).astype(int)
    return max(x0, cx - radius), max(z0, cz - radius), min(x0 + size, cx + radius), min(z0 + size, cz + radius)


def _wet_outlet(position, bounds, params, fine):
    """Anchor a coarse marine outlet in actual fine-grid water, not dry detail."""
    for radius in (16, 32, 64, 96):
        window = _outlet_window(position, bounds, radius)
        x = np.arange(window[0], window[2] + 1, dtype=np.float64)[None, :]
        z = np.arange(window[1], window[3] + 1, dtype=np.float64)[:, None]
        height = fine.get(window)
        wet = np.ceil(height) <= params['world.sea_level']
        if wet.any():
            distance = np.where(wet, (x - position[0]) ** 2 + (z - position[1]) ** 2, np.inf)
            iz, ix = np.unravel_index(np.argmin(distance), distance.shape)
            return np.array((x[0, ix], z[iz, 0])), float(height[iz, ix])
    return None


def build_plan(pack, params, seed):
    started = perf_counter()
    if not params['water.generate'] or not params['hydrology.enabled'] or params['terrain.flat']:
        return None
    x0, z0, size = (params[k] for k in ('hydrology.origin_x', 'hydrology.origin_z', 'hydrology.size'))
    if x0 % 16 or z0 % 16 or size % 16:
        raise ValueError('水系规划起点和范围须为16的倍数 / water planning bounds must align to 16 blocks')
    x = np.arange(x0, x0 + size + 1, 16, dtype=np.float64)[None, :]
    z = np.arange(z0, z0 + size + 1, 16, dtype=np.float64)[:, None]
    ctx = Context(pack.fields, params, seed, x, z, step=16, lattice=(x0 // 16, z0 // 16))
    base, mountain = ctx.get('base_height'), ctx.get('mountain_weight')
    sea = params['world.sea_level']
    q = np.maximum(base - sea, 0)
    weight = 1 - _smooth((mountain - .15) / .5)
    h = params['terrain.lowland_height']
    dem = base - params['terrain.lowland_strength'] * weight * (q - h * q / (q + h))
    # The same dry shaping precedes both planning and final water output.
    # height_custom, islands and badlands consume this coarse lowland input.
    # Desert dunes and author extensions use the same chain before planning.
    ctx.put('height_lowlands', dem)
    dem = ctx.get('height_badlands')
    sampled = perf_counter()
    filled, parent, area, order = priority_flood(dem, sea)
    flooded = perf_counter()
    rows, cols = dem.shape
    # Bound interpolation/detail around every prospective node. Propagating
    # eligibility downstream removes whole upstream branches, never wet pixels.
    import cv2
    upper = cv2.dilate(dem, np.ones((7, 7), np.uint8), borderType=cv2.BORDER_REPLICATE).ravel()
    budget = params['river.max_cut'] + params['river.pass_cut_extra']
    # Bed appearance must not prune upstream branches or move lake candidates.
    # Keep the accepted 0.13 reference clearance, independent of bed depth.
    margin = 4.0 + params['terrain.detail_strength'] * 2 + 3
    allowed = upper <= np.floor(sea) + budget - margin
    valid = np.zeros(parent.size, bool)
    for i in order:
        valid[i] = bool(allowed[i] and (parent[i] < 0 or valid[parent[i]]))
    land = dem.ravel() > sea
    selected = valid & land & (area >= params['river.min_catchment_area']) & (parent >= 0)
    if not params['river.enabled'] or params['river.max_cut'] <= 0:
        selected[:] = False
    edges = np.column_stack((np.flatnonzero(selected), parent[selected])).astype(np.int32)
    incoming = np.zeros(parent.size, np.int32)
    np.add.at(incoming, edges[:, 1], 1)
    sources = tuple(int(i) for i in edges[:, 0] if incoming[i] == 0)
    junctions = tuple(int(i) for i in np.flatnonzero(incoming >= 2))
    outlets = tuple((int(i), 'sea' if dem.ravel()[i] <= sea else 'boundary')
                    for i in np.unique(edges[:, 1]) if not selected[i])
    xx, zz = np.broadcast_arrays(x, z)
    positions = np.column_stack((xx.ravel(), zz.ravel()))
    # A small world-continuous displacement preserves the grid topology.
    warp = min(params['river.warp_strength'], params['river.scale'] * .15)
    for axis in range(2):
        positions[:, axis] += ctx.noise(f'water/layout/{axis}', params['river.scale'], octaves=2).ravel() * warp
    # Open planning exits sit on the actual domain boundary, even after warp.
    positions[xx.ravel() == x0, 0] = x0
    positions[xx.ravel() == x0 + size, 0] = x0 + size
    positions[zz.ravel() == z0, 1] = z0
    positions[zz.ravel() == z0 + size, 1] = z0 + size
    rejected = set()
    adjusted = 0
    outlet_beds = {}
    fine = FieldWindows(pack, params, seed, 'height_before_rivers')
    fine.prefetch([_outlet_window(positions[node], (x0, z0, size), 16) for node, kind in outlets if kind == 'sea'])
    for node, kind in outlets:
        if kind != 'sea':
            continue
        anchor = _wet_outlet(positions[node], (x0, z0, size), params, fine)
        if anchor is None:
            rejected.add(node)
        else:
            position, bed = anchor
            adjusted += int(np.linalg.norm(position - positions[node]) > 1)
            positions[node] = position
            outlet_beds[node] = np.clip(bed, min(params['world.y_min'] + 1, np.floor(sea)), np.floor(sea))
    if rejected:
        # A false coarse sea outlet invalidates its complete upstream tree.
        # Never leave a disconnected wet fragment by masking individual cells.
        reachable = np.ones(parent.size, bool)
        for node in order:
            reachable[node] = node not in rejected and (parent[node] < 0 or reachable[parent[node]])
        selected &= reachable
        valid &= reachable
        edges = np.column_stack((np.flatnonzero(selected), parent[selected])).astype(np.int32)
        incoming[:] = 0
        np.add.at(incoming, edges[:, 1], 1)
        sources = tuple(int(i) for i in edges[:, 0] if incoming[i] == 0)
        junctions = tuple(int(i) for i in np.flatnonzero(incoming >= 2))
        outlets = tuple((int(i), 'sea' if dem.ravel()[i] <= sea else 'boundary')
                        for i in np.unique(edges[:, 1]) if not selected[i])
    widths = np.minimum(params['river.max_width'], params['river.width'] * np.maximum(1, area / params['river.min_catchment_area']) ** .18) * .5
    # Downstream-first order shares one marine target at every junction.
    outlet_distances = np.full(parent.size, 97., np.float64)
    reference_beds = np.zeros(parent.size, np.float64)
    marine = np.zeros(parent.size, bool)
    for node, bed in outlet_beds.items():
        marine[node], outlet_distances[node], reference_beds[node] = True, 0., bed
    for node in order:
        dest = parent[node]
        if selected[node] and dest >= 0 and marine[dest]:
            marine[node] = True
            outlet_distances[node] = outlet_distances[dest] + np.linalg.norm(positions[node] - positions[dest])
            reference_beds[node] = reference_beds[dest]
    segments = []
    profiles = []
    starts = [int(i) for i in edges[:, 0] if incoming[i] != 1]
    for start in starts:
        nodes = [start]
        i = start
        while selected[i]:
            i = int(parent[i])
            nodes.append(i)
            if incoming[i] != 1 or not selected[i]:
                break
        points = positions[nodes]
        widths_here = widths[nodes].copy()
        if incoming[start] == 0:
            lengths = np.r_[0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
            initial = np.clip(widths_here[0] * .5, 1, 3)
            taper = _smooth(lengths / 24)
            widths_here = initial * (1 - taper) + widths_here * taper
        mouths = np.zeros(len(nodes))
        terminal = not selected[nodes[-1]]
        if terminal and dem.ravel()[nodes[-1]] <= sea:
            mouths[-1] = 1
        reach = _rounded_path(points, widths_here, mouths)
        segments.extend(reach)
        if reach and marine[start]:
            r = np.asarray(reach)
            arc = np.r_[0., np.cumsum(np.linalg.norm(r[:, 2:4] - r[:, :2], axis=1))]
            # Match shared node distances exactly even where corner rounding
            # shortens a reach; interpolate by its actual polyline length.
            d = outlet_distances[start] + arc / arc[-1] * (outlet_distances[nodes[-1]] - outlet_distances[start])
            profiles.extend(zip(d[:-1], d[1:], np.full(len(reach), reference_beds[start])))
        else:
            profiles.extend([(97., 97., 0.)] * len(reach))
        if mouths[-1] and len(points) > 1:
            direction = points[-1] - points[-2]
            direction /= np.linalg.norm(direction)
            end = points[-1] + direction * 96
            # Extension sculpts only pre-existing wet floor, never new dry land.
            segments.append((*points[-1], *end, widths_here[-1], widths_here[-1], 1., -1.))
            profiles.append((0., -96., reference_beds[start]))
    segments = np.asarray(segments, np.float64).reshape(-1, 8)
    lakes = []
    for body in _lake_candidates(dem, filled, x0, z0, params):
        # A natural lowland basin touching a planned river can share sea level.
        # Its candidate shoreline remains derived from the original depression;
        # only the local lake floor changes, within the river passage budget.
        if len(segments):
            bx, bz, bw, bd = body.bounds
            centers = (segments[:, :2] + segments[:, 2:4]) * .5
            nearby = ((centers[:, 0] > bx) & (centers[:, 0] < bx + bw)
                     & (centers[:, 1] > bz) & (centers[:, 1] < bz + bd))
            close = np.zeros(len(segments), bool)
            for t in (0., .5, 1.):
                points = segments[:, :2] * (1 - t) + segments[:, 2:4] * t
                width = segments[:, 4] * (1 - t) + segments[:, 5] * t
                distance = body.distance(points[:, 0][None, :], points[:, 1][None, :]).ravel()
                close |= nearby & (distance < width * .83)
            r0, c0 = (int(bz - z0) // 16, int(bx - x0) // 16)
            patch = dem[r0:r0 + int(bd // 16) + 1, c0:c0 + int(bw // 16) + 1]
            if close.any() and patch.max() + margin <= sea + budget and params['river.max_cut'] > 0:
                body = replace(body, level=sea)
        lakes.append(body)
    ponds = []
    if params['ponds.enabled']:
        radius = params['ponds.radius']
        extent = int(np.ceil(radius * 1.5 + 4))
        for cz in range(((z0 + 127) // 128) * 128, z0 + size, 128):
            for cx in range(((x0 + 127) // 128) * 128, x0 + size, 128):
                if _candidate(seed, cx // 128, cz // 128) >= params['ponds.probability']:
                    continue
                ix, iz = (cx - x0) // 16, (cz - z0) // 16
                if ix < 2 or iz < 2 or ix + 2 >= cols or iz + 2 >= rows:
                    continue
                patch = dem[iz - 1:iz + 2, ix - 1:ix + 2]
                if patch.min() <= sea + 2 or np.ptp(patch) > 3 or mountain[iz, ix] > .3:
                    continue
                ponds.append((cx, cz, ix, iz))
    fine.prefetch([_lake_window(b) for b in lakes if b.level > sea]
                  + [(cx - extent, cz - extent, cx + extent, cz + extent) for cx, cz, _, _ in ponds])
    bodies = []
    for body in lakes:
        if not _conflict(body, bodies, segments, sea):
            body = _contain_lake(body, params, fine)
            if body is not None and not _conflict(body, bodies, segments, sea):
                bodies.append(_merge_body_id(body, bodies))
    for cx, cz, ix, iz in ponds:
        # Verify the complete ring with the same fine terrain fields,
        # not just coarse corners. This happens once per cached plan.
        px = np.arange(cx - extent, cx + extent + 1, dtype=np.float64)[None, :]
        pz = np.arange(cz - extent, cz + extent + 1, dtype=np.float64)[:, None]
        height = fine.get((cx - extent, cz - extent, cx + extent, cz + extent))
        ring = (np.maximum(np.abs(px - cx), np.abs(pz - cz)) >= radius * 1.5 + 1)
        if height[ring].max() - height[ring].min() > 3:
            continue
        level = float(np.floor(height[ring].min()) - 1)
        if level <= sea:
            continue
        body = WaterBody(100000 + (iz * cols + ix), 4, level, params['ponds.depth'],
                         (cx - radius * 1.5, cz - radius * 1.5, radius * 3, radius * 3),
                         center=(cx, cz), radii=(radius, radius * .8))
        if not _conflict(body, bodies, segments, sea):
            bodies.append(_merge_body_id(body, bodies))
    bounds = [(min(s[0], s[2]), min(s[1], s[3]), max(s[0], s[2]), max(s[1], s[3])) for s in segments]
    bins = spatial_bins(bounds, params['river.max_width'] * .585 + params['river.near_bank'] * 1.2 + 65)
    body_bins = spatial_bins([(b.bounds[0], b.bounds[1], b.bounds[0] + b.bounds[2], b.bounds[1] + b.bounds[3]) for b in bodies], 8)
    stats = (dict(seconds=perf_counter() - started, sampling_seconds=sampled - started,
                                  flood_seconds=flooded - sampled, nodes=parent.size, edges=len(edges),
                                  segments=len(segments), sources=len(sources), junctions=len(junctions),
                                  sea_outlets=sum(k == 'sea' for _, k in outlets),
                                  adjusted_sea_outlets=adjusted, rejected_sea_outlets=len(rejected),
                                  boundary_outlets=sum(k == 'boundary' for _, k in outlets),
                                  lakes=sum(b.kind == 3 for b in bodies), ponds=sum(b.kind == 4 for b in bodies),
                                  shortened_nodes=int(np.count_nonzero(land & (area >= params['river.min_catchment_area']) & ~valid))))
    return WaterPlan(seed, (x0, z0, size, size), readonly(dem), readonly(filled), readonly(parent),
                     readonly(area), readonly(order), readonly(edges), readonly(positions), readonly(segments), sources, junctions,
                     outlets, tuple(bodies), stats, bins, body_bins,
                     mouth_profiles=np.asarray(profiles, np.float64).reshape(-1, 3))
