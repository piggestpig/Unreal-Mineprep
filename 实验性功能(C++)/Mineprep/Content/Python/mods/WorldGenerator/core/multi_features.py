"""Bounded multi-block placement, independent of output crops and tiles.

Generators produce geometry only. This module owns suitability, local priority,
actual occupancy checks, budgets and cropping.
"""
from dataclasses import dataclass, replace
from types import MappingProxyType

import numpy as np

from .data import Region, MAX_COORD, check_cancel, require_int
from .features import FeatureBatch, enabled
from .fields import Context
from .noise import seed_key, fbm2
from .surface import bound, apply_surface
from .biomes import select_biomes
from .water import sample_water, generated as water_generated, displayed as water_displayed
from . import geometry

BATCH = 128


@dataclass(frozen=True)
class FeatureInstance:
    id: tuple                 # feature ID, seed, candidate cell X/Z
    anchor: tuple             # absolute MC XYZ
    bounds: tuple             # absolute half-open XYZ min/max
    block_count: int           # emitted cells inside this output region


@dataclass(frozen=True)
class BuildContext:
    seed: int
    params: object
    feature: object
    block_ids: object
    water_depths: object = None  # read-only [anchors], submerged cells available above terrain
    reference: object = None   # shared read-only reference arrays for template selection
    block_defs: object = None
    query: object = None       # bounded physical occupancy, explicit volume generators only

    def param(self, key):
        return self.params[key]


@dataclass(frozen=True)
class FeatureReference:
    """Read-only views; field evaluation still uses the current reference context."""
    _source: object

    def get(self,name):
        value=self._source.ctx.get(name).view();value.setflags(write=False)
        return value

    def __getattr__(self,name):
        if name in ('x','z'):value=getattr(self._source.ctx,name)
        elif name in ('height','levels','wet','biomes','columns'):value=getattr(self._source,name)
        else:raise AttributeError(name)
        value=value.view();value.setflags(write=False)
        return value


@dataclass(frozen=True)
class FeatureTile:
    xyz: np.ndarray           # absolute int64 XYZ
    types: np.ndarray          # uint16 pack IDs
    owners: np.ndarray         # indices into instances
    instances: tuple
    candidates: np.ndarray    # absolute XZ, before surface/space filtering
    rotations: object = None  # optional uint8[N], aligned with xyz
    block_counts: tuple = ()  # (feature ID, pack block ID, count) after output crop
    models: tuple = ()        # complete models, owned by anchor rather than cell crop

    @property
    def array_bytes(self):
        return (sum(a.nbytes for a in (self.xyz, self.types, self.owners, self.candidates))
                + (0 if self.rotations is None else self.rotations.nbytes) + 1024 * len(self.instances)
                + sum(t.array_bytes for t in {id(m.template):m.template for m in self.models}.values()))


def _empty():
    return FeatureTile(np.empty((0, 3), np.int64), np.empty(0, np.uint16),
                       np.empty(0, np.int32), (), np.empty((0, 2), np.int64))


def _compact_rotations(parts):
    rotations = np.concatenate(parts).astype(np.uint8, copy=False)
    return rotations if np.any(rotations) else None


def _hash(x, z, seed, salt):
    with np.errstate(over='ignore'):
        h = (x.astype(np.uint64) * np.uint64(0x9E3779B185EBCA87)
             ^ z.astype(np.uint64) * np.uint64(0xC2B2AE3D27D4EB4F) ^ seed_key(seed, salt)[0])
        h = (h ^ (h >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        h = (h ^ (h >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        return h ^ (h >> np.uint64(31))


def validate_batch(batch, f, count, block_ids):
    """Validate once; return owner/X/Z columns with their exact Y extrema."""
    prefix = f'feature {f.id}: '
    if not isinstance(batch, FeatureBatch):
        raise ValueError(prefix + 'generator must return FeatureBatch')
    p, t, o = batch.offsets, batch.types, batch.owners
    if (not all(isinstance(a, np.ndarray) and a.dtype.kind in 'iu' for a in (p, t, o))
            or p.ndim != 2 or p.shape[1] != 3 or t.shape != (len(p),) or o.shape != (len(p),)):
        raise ValueError(prefix + 'offsets [N,3], types [N], owners [N] must be integer arrays')
    if batch.rotations is not None:
        r = batch.rotations
        if (not isinstance(r, np.ndarray) or r.dtype.kind not in 'iu' or r.shape != (len(p),)
                or np.any(r < 0) or np.any(r > 23)):
            raise ValueError(prefix + 'rotations must be integer [N] codes 0..23')
    if len(p) > count * f.max_blocks:
        raise ValueError(prefix + 'generator exceeds max_blocks')
    if not len(p):
        return
    if np.any(o >= count) or np.any(o < 0):
        raise ValueError(prefix + 'invalid owner index')
    if np.any(p < f.bounds[0]) or np.any(p >= f.bounds[1]):
        raise ValueError(prefix + 'generator exceeds declared bounds')
    if not np.isin(t, [block_ids[n] for n in f.blocks]).all():
        raise ValueError(prefix + 'generator returned an undeclared block')
    if np.bincount(o.astype(np.intp), minlength=count).max() > f.max_blocks:
        raise ValueError(prefix + 'generator exceeds max_blocks for one owner')
    order = np.lexsort((p[:, 1], p[:, 2], p[:, 0], o))
    sorted_p, sorted_o = p[order], o[order]
    same_column = ((sorted_o[1:] == sorted_o[:-1])
                   & np.all(sorted_p[1:, (0, 2)] == sorted_p[:-1, (0, 2)], axis=1))
    if np.any(same_column & (sorted_p[1:, 1] == sorted_p[:-1, 1])):
        raise ValueError(prefix + 'generator returned duplicate cells')
    starts = np.r_[0, np.flatnonzero(~same_column)+1]
    ends = np.r_[starts[1:]-1, len(p)-1]
    return sorted_o[starts].astype(np.intp), sorted_p[starts], sorted_p[ends, 1]


def _affected(points, boxes):
    if boxes is None:
        return np.ones(len(points), bool)
    mask = np.zeros(len(points), bool)
    for box in boxes:
        mask |= np.all((points >= box[:3]) & (points < box[3:]), axis=1)
    return mask


def _occupied(pack, params, seed, points, tops, resources):
    values, _ = geometry.sample(pack, params, seed, points[:, 0, None, None],
                                points[:, 1, None, None], points[:, 2, None, None],
                                tops[:, None], resources=resources)
    return values[:, 0, 0]


def _thin(boxes, priorities, levels=None, *, overlap=None):
    """Local minima only: no greedy dependency chain across a query boundary."""
    count = len(boxes)
    keep = np.ones(count, bool)
    if not count:
        return keep
    width = max(1, int(np.max(boxes[:, 3:][:, (0, 2)] - boxes[:, :3][:, (0, 2)])))
    bins = np.floor_divide(boxes[:, (0, 2)], width)
    buckets = {}
    for i, cell in enumerate(bins):
        buckets.setdefault(tuple(cell), []).append(i)
    rank = np.empty(count, np.intp)
    order = np.argsort(priorities, kind='stable') if levels is None else np.lexsort((priorities, levels))
    rank[order] = np.arange(count)
    for cell, ids in buckets.items():
        for dx, dz in ((0, 0), (0, 1), (1, -1), (1, 0), (1, 1)):
            other = buckets.get((cell[0] + dx, cell[1] + dz))
            if other is None:
                continue
            a, b = np.meshgrid(ids, other, indexing='ij')
            a, b = a.ravel(), b.ravel()
            if dx == dz == 0:
                use = a < b
                a, b = a[use], b[use]
            intersects = np.all((boxes[a, :3] < boxes[b, 3:]) & (boxes[b, :3] < boxes[a, 3:]), axis=1)
            a, b = a[intersects], b[intersects]
            if overlap is not None and len(a):
                exact = overlap(a,b)
                a,b = a[exact],b[exact]
            keep[np.where(rank[a] < rank[b], b, a)] = False
    return keep


def _proposals(params, seed, region, features):
    radius = max(max(abs(v) for v in (f.bounds[0][0], f.bounds[0][2], f.bounds[1][0]-1, f.bounds[1][2]-1)) for f in features)
    # Emitting anchors extend by radius; their competitors extend by another 2r.
    query = region.expanded(3 * radius)
    proposals = []
    for f in features:
        size = f.cell_size
        nx = (query.x0+query.width-1)//size - query.x0//size + 1
        nz = (query.z0+query.depth-1)//size - query.z0//size + 1
        if nx*nz > 65536:
            raise ValueError(f'feature {f.id}: local query exceeds 65,536 candidates; reduce bounds or increase cell_size')
        xx, zz = np.meshgrid(np.arange(query.x0 // size, (query.x0 + query.width - 1) // size + 1),
                             np.arange(query.z0 // size, (query.z0 + query.depth - 1) // size + 1))
        cx, cz = xx.ravel(), zz.ravel()
        keys = _hash(cx, cz, seed, f'features/{f.id}/shape')
        px = cx * size + (_hash(cx, cz, seed, f'features/{f.id}/x') % size).astype(np.int64)
        pz = cz * size + (_hash(cx, cz, seed, f'features/{f.id}/z') % size).astype(np.int64)
        # Cells intersecting query can jitter outside it, especially with large
        # cell_size. They cannot influence emitted geometry: query already
        # includes the direct competitors, and _thin has no greedy chain.
        inside = ((px >= query.x0) & (px < query.x0+query.width)
                  & (pz >= query.z0) & (pz < query.z0+query.depth))
        if inside.any():
            proposals.append((f, cx[inside], cz[inside], px[inside], pz[inside], keys[inside]))
    return radius,proposals


def _build(pack, params, seed, region, features, resources):
    radius,proposals = _proposals(params,seed,region,features)
    if not proposals:
        return _empty()
    if not geometry.height_mode(pack):
        from .volume_features import build
        return build(pack,params,seed,region,proposals,resources)
    px = np.concatenate([p[3] for p in proposals]); pz = np.concatenate([p[4] for p in proposals])
    surface_region = Region(int(px.min())-radius-1, int(pz.min())-radius-1,
                            int(px.max()-px.min())+2*radius+3, int(pz.max()-pz.min())+2*radius+3)
    if surface_region.cells > 1_048_576:
        raise ValueError('feature surface query exceeds 1,048,576 cells; reduce feature bounds')
    # The same deterministic 2D pipeline as terrain, without allocating a shell.
    from .store import reference as reference_for
    reference = reference_for(pack, params, seed, surface_region, resources)
    feature_reference=FeatureReference(reference)
    ctx, raw, height = reference.ctx, reference.raw, reference.height
    water_levels, wet, biomes, columns = reference.levels, reference.wet, reference.biomes, reference.columns
    water_ys=displayed=None
    if any(f.habitat=='water_surface' for f in features):
        water_ys=np.floor(water_levels).astype(np.int64)
        displayed=wet & water_displayed(pack,params) & (water_ys>=params['world.y_min']) & (water_ys<params['world.y_max'])
    block_ids = {n: i for i, n in enumerate(pack.blocks)}
    tops = np.ceil(raw).astype(np.int64)-1
    boxes = geometry.plan_bounds(pack, params, seed, surface_region, resources) if geometry.enabled(pack, params) else ()
    all_p, all_t, all_o, instances, priorities, levels, envelopes, candidates = [], [], [], [], [], [], [], []
    all_r = []
    model_proposals = []
    validated_templates = set()
    for f, cx, cz, px, pz, keys in proposals:
        density, scale, slope = (bound(ctx, v) for v in (f.density, f.patch_scale, f.max_slope))
        if not 0 <= density <= 1 or scale <= 0 or slope < 0:
            raise ValueError(f'feature {f.id}: density [0,1], patch_scale >0 and max_slope >=0 required')
        iz, ix = pz-surface_region.z0, px-surface_region.x0
        # Only candidate points consume this noise. Paired coordinates preserve
        # its exact world-position values without allocating a dense image.
        patch = fbm2(px.astype(np.float64)/scale, pz.astype(np.float64)/scale,
                     seed=seed, salt=f'features/{f.id}/patch', octaves=2)
        probability = density * np.clip(1 + 2*patch, 0, 2)
        from .masks import weight, rejected
        probability = np.minimum(probability, 1.) * weight(pack, f.category, px, pz)
        uniform = (_hash(cx, cz, seed, f'features/{f.id}/candidate') >> np.uint64(11)).astype(np.float64) / 2**53
        proposed = uniform < probability
        owned = ((px >= region.x0) & (px < region.x0+region.width) & (pz >= region.z0) & (pz < region.z0+region.depth))
        candidates.append(np.column_stack((px[proposed & owned], pz[proposed & owned])))
        underwater = f.habitat == 'underwater'
        floating = f.habitat == 'water_surface'
        habitat = displayed[iz, ix] if floating else (wet[iz, ix] if underwater else ~wet[iz, ix])
        material = (np.full(len(px),block_ids[pack.water['block']],np.uint16) if floating
                    else columns[iz, ix, 0])
        # Connected displayed water is planar (validated by the reference sampler).
        candidate_slope = 0 if floating else ctx.get('slope')[iz, ix]
        anchor_y = water_ys[iz,ix] if floating else tops[iz, ix]+1
        usable = (proposed & habitat & (candidate_slope <= slope)
                  & np.isin(biomes[iz, ix], [i for i, b in enumerate(pack.biomes) if b.id in f.biomes])
                  & np.isin(material, [block_ids[n] for n in f.surface])
                  & (anchor_y >= params['world.y_min']) & (anchor_y < params['world.y_max'])
                  & (True if floating else tops[iz,ix] >= params['world.y_min']))
        chosen = np.flatnonzero(usable)
        for start in range(0, len(chosen), BATCH):
            check_cancel(getattr(resources, 'cancel_event', None))
            ids = chosen[start:start+BATCH]
            roots = np.column_stack((px[ids], anchor_y[ids], pz[ids]))
            support = roots.copy(); support[:, 1] -= 1
            affected = _affected(support, boxes) if not floating else np.zeros(len(ids),bool)
            good = np.ones(len(ids), bool)
            if affected.any():
                good[affected] = _occupied(pack, params, seed, support[affected], support[affected, 1], resources)
            ids, roots = ids[good], roots[good]
            if not len(ids):
                continue
            roots.setflags(write=False)
            shape_keys = keys[ids].copy(); shape_keys.setflags(write=False)
            depths = None
            if underwater or floating:
                depths = (np.floor(water_levels[iz[ids], ix[ids]]).astype(np.int64) -
                          (tops[iz[ids], ix[ids]]+1 if floating else roots[:, 1]))
                depths.setflags(write=False)
            batch = f.fn(BuildContext(seed, params, f, MappingProxyType(block_ids), depths,
                                     feature_reference,pack.block_defs), roots, shape_keys)
            from .templates import TemplateBatch, TemplateInstance, validate as validate_templates, clearance
            model = isinstance(batch, TemplateBatch)
            if model:
                validate_templates(batch, f, len(ids), block_ids, validated_templates)
                if not len(batch.owners): continue
                low, high_y, owners = clearance(batch, roots)
                summary = owners, low-roots[owners], high_y-roots[owners,1]
                points = low
            else:
                summary = validate_batch(batch, f, len(ids), block_ids)
                if not len(batch.offsets): continue
                owners = batch.owners.astype(np.intp)
                points = roots[owners] + batch.offsets
            column_owners, column_offsets, column_high = summary
            low = roots[column_owners] + column_offsets
            high_y = roots[column_owners, 1] + column_high
            # Monotone height/water tests need only column extrema. Carved
            # terrain still queries every affected emitted cell below.
            test_points = points if not model and (boxes is None or len(boxes)) else low
            test_owners = owners if test_points is points else column_owners
            highest = test_points[:, 1] if test_points is points else high_y
            zz, xx = test_points[:, 2]-surface_region.z0, test_points[:, 0]-surface_region.x0
            space = (displayed[zz,xx] if floating else
                     ((wet[zz,xx] & (highest < np.floor(water_levels[zz,xx]))) if underwater else
                      (~wet[zz,xx] | (test_points[:,1] > np.floor(water_levels[zz,xx])))))
            clear = ((test_points[:,1] > tops[zz,xx]) & (test_points[:,1] >= params['world.y_min'])
                     & (highest < params['world.y_max']) & space)
            if floating:
                # All projected columns, including overhangs, need the same water plane.
                clear &= displayed[zz,xx] & (water_levels[zz,xx] == water_levels[iz[ids],ix[ids]][test_owners])
            affected = _affected(test_points, boxes) & clear
            if model and affected.any():
                # Only cave-affected models need exact cells, never all trees.
                bad=np.unique(test_owners[affected])
                for row in np.flatnonzero(np.isin(batch.owners,bad)):
                    owner=int(batch.owners[row]); template=batch.templates[int(batch.template_ids[row])]
                    p=template.orientations[int(batch.rotations[row])][0]+roots[owner]
                    z,x=p[:,2]-surface_region.z0,p[:,0]-surface_region.x0
                    if _occupied(pack,params,seed,p,tops[z,x],resources).any():
                        clear[test_owners==owner]=False
            elif affected.any():
                clear[affected] &= ~_occupied(pack, params, seed, test_points[affected], tops[zz[affected], xx[affected]], resources)
            invalid = np.union1d(np.unique(test_owners[~clear]), rejected(pack, f.category, batch, roots))
            if f.support == 'footprint' and not floating:
                if model:
                    base_p,base_o=[],[]
                    for row,owner in enumerate(batch.owners):
                        offsets=batch.templates[int(batch.template_ids[row])].orientations[int(batch.rotations[row])][0]
                        footprint=offsets[offsets[:,1]==0]
                        base_p.append(footprint+roots[owner]);base_o.append(np.full(len(footprint),owner,np.intp))
                    ground=np.concatenate(base_p);base_owners=np.concatenate(base_o)
                else:
                    base = batch.offsets[:, 1] == 0
                    base_owners = owners[base]
                    ground = points[base].copy()
                ground[:, 1] -= 1
                gz, gx = ground[:, 2]-surface_region.z0, ground[:, 0]-surface_region.x0
                supported = ((ground[:, 1] == tops[gz, gx]) & (ground[:, 1] >= params['world.y_min'])
                             & (wet[gz, gx] if underwater else ~wet[gz, gx])
                             & np.isin(columns[gz, gx, 0], [block_ids[n] for n in f.surface]))
                affected = _affected(ground, boxes) & supported
                if affected.any():
                    supported[affected] &= _occupied(pack, params, seed, ground[affected], tops[gz[affected], gx[affected]], resources)
                missing = np.flatnonzero(np.bincount(base_owners, minlength=len(ids)) == 0)
                invalid = np.union1d(invalid, np.r_[base_owners[~supported], missing])
            counts = np.bincount(owners, minlength=len(ids))
            valid = counts > 0; valid[invalid] = False
            lower = np.full((len(ids), 3), np.iinfo(np.int64).max, np.int64)
            upper = np.full((len(ids), 3), np.iinfo(np.int64).min, np.int64)
            high = low.copy(); high[:, 1] = high_y
            np.minimum.at(lower, column_owners, low); np.maximum.at(upper, column_owners, high+1)
            remap = np.full(len(ids), -1, np.int32)
            for local in np.flatnonzero(valid):
                index = len(instances); remap[local] = index
                cell = ids[local]
                instances.append(FeatureInstance((f.id, seed, int(cx[cell]), int(cz[cell])), tuple(map(int, roots[local])),
                                                 (tuple(map(int, lower[local])), tuple(map(int, upper[local]))), 0))
                priorities.append(keys[cell]); levels.append(f.priority)
                envelopes.append(np.r_[lower[local], upper[local]])
            if model:
                for row,local in enumerate(batch.owners):
                    if not valid[local]: continue
                    template=batch.templates[int(batch.template_ids[row])]
                    item=instances[remap[local]]
                    model_proposals.append((int(remap[local]),TemplateInstance(item.id,item.anchor,item.bounds,
                        len(template.offsets),template,int(batch.rotations[row]))))
                continue
            use = valid[owners]
            all_p.append(points[use]); all_t.append(batch.types[use].astype(np.uint16)); all_o.append(remap[owners[use]])
            all_r.append(np.zeros(int(use.sum()), np.uint8) if batch.rotations is None else batch.rotations[use])
    if not instances:
        empty = _empty()
        return FeatureTile(empty.xyz, empty.types, empty.owners, (), np.concatenate(candidates))
    keep = _thin(np.asarray(envelopes), np.asarray(priorities, np.uint64), np.asarray(levels))
    empty=_empty()
    points, types, owners = (np.concatenate(a) if a else b for a,b in
                            ((all_p,empty.xyz),(all_t,empty.types),(all_o,empty.owners)))
    rotations = _compact_rotations(all_r) if all_r else None
    use = (keep[owners] & (points[:, 0] >= region.x0) & (points[:, 0] < region.x0+region.width)
           & (points[:, 2] >= region.z0) & (points[:, 2] < region.z0+region.depth))
    selected_models=[(i,m) for i,m in model_proposals if keep[i] and
        region.x0<=m.anchor[0]<region.x0+region.width and region.z0<=m.anchor[2]<region.z0+region.depth]
    models=tuple(m for _,m in selected_models)
    used = np.union1d(np.unique(owners[use]),[i for i,_ in selected_models]).astype(np.intp)
    remap = np.zeros(len(instances), np.int32); remap[used] = np.arange(len(used))
    selected_rotations = None if rotations is None else rotations[use]
    if selected_rotations is not None and not np.any(selected_rotations):
        selected_rotations = None
    return FeatureTile(points[use], types[use], remap[owners[use]], tuple(instances[i] for i in used),
                       np.concatenate(candidates), selected_rotations, models=models)


def generate(pack, params, seed, tile, world_region, resources, max_instances):
    features = tuple(sorted((f for f in pack.features if f.type == 'multi_block'
                            and enabled(f,params) and bound(BuildContext(seed, params, f, {}), f.density)
                            and (f.habitat not in ('underwater','water_surface') or water_generated(pack, params))
                            and (f.habitat != 'water_surface' or water_displayed(pack,params))), key=lambda f: f.id))
    if not features:
        return _empty(), 0, ()
    features = tuple(replace(f,cell_size=params[f.cell_size[1:]]) if isinstance(f.cell_size,str) else f
                     for f in features)
    for f in features:
        require_int(f'feature {f.id}.cell_size',f.cell_size,1,1024)
    unsupported = ()
    if not geometry.height_mode(pack):
        unsupported = tuple(f.id for f in features if f.placement_fn is None)
        features = tuple(f for f in features if f.placement_fn is not None)
        if not features:
            return _empty(),0,unsupported
    # Do not manufacture a world beyond the supported coordinate interval.
    radius = max(max(abs(v) for row in f.bounds for v in (row[0], row[2])) for f in features)
    if min(tile.x0, tile.z0) < -MAX_COORD+4*radius or max(tile.x0+tile.width, tile.z0+tile.depth) > MAX_COORD-4*radius:
        raise ValueError('multi-block feature query exceeds supported world coordinates')
    check_cancel(getattr(resources, 'cancel_event', None))
    # Competition is local (_thin has no greedy chain), so the tile itself is the query window.
    data = _build(pack, params, seed, tile, features, resources)
    p = data.xyz
    use = ((p[:, 0] >= tile.x0) & (p[:, 0] < tile.x0+tile.width) & (p[:, 2] >= tile.z0) & (p[:, 2] < tile.z0+tile.depth))
    if not geometry.height_mode(pack):
        use &= (p[:,1] >= params['world.y_min']) & (p[:,1] < params['world.y_max'])
    n = int(use.sum())
    if n > max_instances:
        raise ValueError(f'feature visible cells exceed max_instances={max_instances:,} before sparse concatenation')
    selected = p[use].copy(); selected[:, 0] -= world_region.x0; selected[:, 2] -= world_region.z0
    instances, block_counts, models = {}, {}, {}
    # Count by feature ownership, not material name (trees and logs share oak_log).
    names, labels = np.unique([i.id[0] for i in data.instances], return_inverse=True)
    labels = labels[data.owners[use]]
    for label, feature in enumerate(names):
        counts = np.bincount(data.types[use][labels == label].astype(np.intp))
        for block in np.flatnonzero(counts):
            block_counts[str(feature), int(block)] = int(counts[block])
    for owner, count in zip(*np.unique(data.owners[use], return_counts=True)):
        item = data.instances[owner]
        instances[item.id] = FeatureInstance(item.id, item.anchor, item.bounds, int(count))
    for item in data.models:
        models[item.id] = item
        instances[item.id] = FeatureInstance(item.id, item.anchor, item.bounds, item.block_count)
    if n + len(models) > max_instances:
        raise ValueError('template instances exceed max_instances')
    c = data.candidates
    checked = int(((c[:, 0] >= tile.x0) & (c[:, 0] < tile.x0+tile.width) & (c[:, 1] >= tile.z0) & (c[:, 1] < tile.z0+tile.depth)).sum())
    for template_id in sorted({(m.id[0],m.template.id) for m in models.values()}):
        group=[m for m in models.values() if (m.id[0],m.template.id)==template_id]
        for block,count in zip(*np.unique(group[0].template.types,return_counts=True)):
            key=template_id[0],int(block)
            block_counts[key]=block_counts.get(key,0)+int(count)*len(group)
    ordered = tuple(instances[k] for k in sorted(instances))
    owner_index = {item.id:i for i,item in enumerate(ordered)}
    point_owners = np.array([owner_index.get(item.id, -1) for item in data.instances], np.int32)[data.owners[use]]
    rotations = None if data.rotations is None else data.rotations[use]
    result = FeatureTile(selected.astype(np.int32), data.types[use], point_owners, ordered, np.empty((0, 2), np.int64),
                         rotations if rotations is not None and np.any(rotations) else None,
                         tuple((f, b, c) for (f, b), c in sorted(block_counts.items())),
                         tuple(models[k] for k in sorted(models)))
    return result, checked, unsupported
