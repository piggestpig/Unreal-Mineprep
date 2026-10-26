"""Explicit volume placement; reuse multi-block batches, conflicts and output."""
from dataclasses import dataclass
from types import MappingProxyType
import numpy as np
from .data import Region, check_cancel
from .fields import Context
from .reference import biomes_for
from .features import FeatureBatch
from .noise import fbm2
from .surface import bound
from .volume_query import VolumeQuery


@dataclass(frozen=True)
class Anchors:
    positions: np.ndarray   # absolute integer XYZ; no output cropping
    candidates: np.ndarray  # indices into supplied candidate_xz
    materials: np.ndarray   # recipe's physical support material IDs
    slopes: np.ndarray      # recipe's measured local support slope


@dataclass(frozen=True)
class PlacementContext:
    pack: object
    params: object
    seed: int
    feature: object
    block_ids: object
    query: object
    resources: object

    def param(self,key):
        return self.params[key]


def validate_anchors(result, xz, block_ids):
    if not isinstance(result,Anchors):
        raise ValueError('volume placement must return Anchors')
    p,i,m,s = result.positions,result.candidates,result.materials,result.slopes
    if not all(isinstance(a,np.ndarray) for a in (p,i,m,s)) or p.ndim != 2:
        raise ValueError('volume anchors must be arrays with [N,3] positions')
    n = len(p)
    if (p.shape != (n,3)
            or any(a.dtype.kind not in 'iu' for a in (p,i,m)) or i.shape != (n,)
            or m.shape != (n,) or s.shape != (n,) or s.dtype.kind not in 'fiu'
            or not np.isfinite(s).all() or np.any(s < 0)
            or np.any(i < 0) or np.any(i >= len(xz)) or len(np.unique(i)) != n
            or np.any(m < 0) or np.any(m >= len(block_ids))):
        raise ValueError('invalid volume anchors, owners, materials or slopes')
    if not np.array_equal(p[:,(0,2)],xz[i]):
        raise ValueError('volume anchors must retain candidate XZ')
    for a in (p,i,m,s):
        a.setflags(write=False)


def _cell_overlap(parts, exact, soft_parts=None):
    """AABB broad phase, then actual occupied cells; no all-pairs voxel scan."""
    lower = np.min([p.min(0) for p in parts],axis=0)
    upper = np.max([p.max(0) for p in parts],axis=0)+1
    span = upper-lower
    keys,soft = [],[]
    for i,points in enumerate(parts):
        p = points-lower
        code = (p[:,0]*span[2]+p[:,2])*span[1]+p[:,1]
        order = np.argsort(code)
        keys.append(code[order])
        soft.append(np.zeros(len(points),bool) if soft_parts is None else soft_parts[i][order])

    def overlap(a,b):
        result = np.ones(len(a),bool)
        for i in np.flatnonzero(exact[a] | exact[b]):
            x,y = a[i],b[i]
            if len(keys[x]) > len(keys[y]):
                x,y = y,x
            small,large = keys[x],keys[y]
            at = np.searchsorted(large,small)
            valid = np.flatnonzero(at < len(large))
            hit = valid[large[at[valid]] == small[valid]]
            # At most one eighth of the smaller canopy may interleave. A
            # single stem, vine or other hard contact still rejects the pair.
            limit = max(1,min(np.count_nonzero(soft[x]),np.count_nonzero(soft[y]))//8)
            result[i] = len(hit)>limit or np.any(~(soft[x][hit] & soft[y][at[hit]]))
        return result
    return overlap


def build(pack,params,seed,region,proposals,resources):
    from .multi_features import (_hash,_empty,_thin,FeatureInstance,FeatureTile,
                                 BuildContext,validate_batch,_compact_rotations)
    from .templates import TemplateBatch,TemplateInstance,validate as validate_templates
    query = VolumeQuery(pack,params,seed,resources)
    block_ids = MappingProxyType({n:i for i,n in enumerate(pack.blocks)})
    parts,types,owners,rotations = [],[],[],[]
    instances,boxes,ranks,priorities,candidates = [],[],[],[],[]
    model_proposals = []
    collision_cells = []
    exact_collisions = []
    soft_collisions = []
    voxel_overlap = False
    validated_templates = set()
    for f,cx,cz,px,pz,keys in proposals:
        check_cancel(getattr(resources,'cancel_event',None))
        r = Region(int(px.min()),int(pz.min()),int(px.max()-px.min())+1,int(pz.max()-pz.min())+1)
        if r.cells > 1_048_576:
            raise ValueError('volume feature reference exceeds 1,048,576 cells; reduce bounds')
        ctx = Context.for_region(pack.fields,params,seed,r,resources=resources)
        density,scale,slope = (bound(ctx,v) for v in (f.density,f.patch_scale,f.max_slope))
        if not 0 <= density <= 1 or scale <= 0 or slope < 0:
            raise ValueError(f'feature {f.id}: invalid density, scale or slope')
        patch = fbm2(px/scale,pz/scale,seed=seed,salt=f'features/{f.id}/patch',octaves=2)
        uniform = (_hash(cx,cz,seed,f'features/{f.id}/candidate') >> np.uint64(11)).astype(float)/2**53
        from .masks import weight, rejected
        probability = np.minimum(density*np.clip(1+2*patch,0,2), 1.)
        mask = uniform < probability * weight(pack, f.category, px, pz)
        biome = biomes_for(ctx,pack)[pz-r.z0,px-r.x0]
        mask &= np.isin(biome,[i for i,b in enumerate(pack.biomes) if b.id in f.biomes])
        ids = np.flatnonzero(mask)
        xz = np.column_stack((px[ids],pz[ids]))
        owned = ((px[ids] >= region.x0) & (px[ids] < region.x0+region.width)
                 & (pz[ids] >= region.z0) & (pz[ids] < region.z0+region.depth))
        candidates.append(xz[owned])
        if not len(ids):
            continue
        placement = PlacementContext(pack,params,seed,f,block_ids,query,resources)
        xz.setflags(write=False)
        shape_keys = keys[ids].copy(); shape_keys.setflags(write=False)
        anchors = f.placement_fn(placement,xz,shape_keys)
        validate_anchors(anchors,xz,block_ids)
        allowed = np.isin(anchors.materials,[block_ids[n] for n in f.surface]) & (anchors.slopes <= slope)
        roots = anchors.positions[allowed]
        ids = ids[anchors.candidates[allowed]]
        if not len(roots):
            continue
        roots.setflags(write=False)
        shape_keys = keys[ids].copy(); shape_keys.setflags(write=False)
        batch = f.fn(BuildContext(seed,params,f,block_ids,block_defs=pack.block_defs,query=query),roots,shape_keys)
        model = isinstance(batch,TemplateBatch)
        if model:
            validate_templates(batch,f,len(roots),block_ids,validated_templates)
            if not len(batch.owners):
                continue
            offsets,model_types,model_owners = [],[],[]
            for row,owner in enumerate(batch.owners):
                t = batch.templates[int(batch.template_ids[row])]
                offsets.append(t.orientations[int(batch.rotations[row])][0])
                model_types.append(t.types)
                model_owners.append(np.full(len(t.offsets),owner,np.int32))
            voxel_batch = FeatureBatch(np.concatenate(offsets),np.concatenate(model_types),np.concatenate(model_owners))
        else:
            validate_batch(batch,f,len(roots),block_ids)
            voxel_batch = batch
        cells = voxel_batch
        if not len(cells.offsets):
            continue
        o = cells.owners.astype(np.intp)
        points = roots[o]+cells.offsets
        # Physical support and exact cell clearance never use crop boundaries.
        support = roots.copy(); support[:,1] += 1 if f.support == 'ceiling' else -1
        if f.support in ('anchor','ceiling'):
            good = query.occupied(support).copy()
        else:
            base = cells.offsets[:,1] == 0
            supported = query.occupied(points[base]-[0,1,0])
            if model:
                totals = np.bincount(o[base],minlength=len(roots))
                good = (totals > 0) & (np.bincount(o[base][supported],minlength=len(roots)) == totals)
            else:
                good = np.bincount(o[base][supported],minlength=len(roots)) > 0
        good &= ~query.occupied(roots)
        good[rejected(pack, f.category, batch, roots)] = False
        blocked = query.occupied(points)
        bad = np.unique(o[blocked]); good[bad] = False
        resources.report.add('volume_space_rejected',len(bad))
        for owner in np.flatnonzero(good):
            take = o == owner
            p = points[take]
            lower,upper = p.min(0),p.max(0)+1
            if model and (lower[1] < params['world.y_min'] or upper[1] > params['world.y_max']):
                continue
            index = len(instances)
            cell = ids[owner]
            instances.append(FeatureInstance((f.id,seed,int(cx[cell]),int(cz[cell])),tuple(map(int,roots[owner])),
                                             (tuple(map(int,lower)),tuple(map(int,upper))),0))
            boxes.append(np.r_[lower,upper]); ranks.append(keys[cell]); priorities.append(f.priority)
            collision_cells.append(p)
            exact_collisions.append(f.collision == 'cells')
            soft_collisions.append(np.isin(cells.types[take],[block_ids[n] for n in f.overlap_blocks]))
            voxel_overlap |= bool(f.overlap_blocks) and not model
            if model:
                row = int(np.flatnonzero(batch.owners == owner)[0])
                t = batch.templates[int(batch.template_ids[row])]
                item = instances[index]
                model_proposals.append((index,TemplateInstance(item.id,item.anchor,item.bounds,
                                                               len(t.offsets),t,int(batch.rotations[row]))))
            else:
                parts.append(p); types.append(cells.types[take]); owners.append(np.full(len(p),index,np.int32))
                rotations.append(np.zeros(len(p),np.uint8) if cells.rotations is None else cells.rotations[take])
    if not instances:
        empty = _empty()
        return FeatureTile(empty.xyz,empty.types,empty.owners,(),np.concatenate(candidates) if candidates else empty.candidates)
    # Height recipes keep their existing conservative boxes. Volume recipes
    # already queried these cells for full clearance, so reuse them here.
    overlap = _cell_overlap(collision_cells,np.asarray(exact_collisions),soft_collisions) if any(exact_collisions) else None
    keep = _thin(np.asarray(boxes),np.asarray(ranks,np.uint64),np.asarray(priorities),overlap=overlap)
    empty = _empty()
    p,t,o = (np.concatenate(a) if a else b for a,b in
             ((parts,empty.xyz),(types,empty.types),(owners,empty.owners)))
    use = keep[o] & (p[:,0] >= region.x0) & (p[:,0] < region.x0+region.width) & (p[:,2] >= region.z0) & (p[:,2] < region.z0+region.depth)
    if voxel_overlap and np.any(use):
        # Shared crown cells have one deterministic voxel output. Rank order
        # matches competition and is independent of tile assembly/order.
        selected = np.flatnonzero(use)
        q,owner = p[selected],o[selected]
        order = np.lexsort((np.asarray(ranks,np.uint64)[owner],np.asarray(priorities)[owner],q[:,2],q[:,1],q[:,0]))
        sorted_points = q[order]
        first = np.r_[True,np.any(sorted_points[1:] != sorted_points[:-1],axis=1)]
        use[selected[order[~first]]] = False
    models = tuple(m for i,m in model_proposals if keep[i] and region.x0 <= m.anchor[0] < region.x0+region.width
                   and region.z0 <= m.anchor[2] < region.z0+region.depth)
    model_ids = {m.id for m in models}
    selected = np.union1d(np.unique(o[use]),[i for i,item in enumerate(instances) if item.id in model_ids]).astype(np.intp)
    remap = np.full(len(instances),-1,np.int32); remap[selected] = np.arange(len(selected))
    rot = _compact_rotations(rotations) if rotations else None
    return FeatureTile(p[use],t[use],remap[o[use]],tuple(instances[i] for i in selected),
                       np.concatenate(candidates),None if rot is None else rot[use],models=models)


def _feature_tops(pack, params, region, xyz, types, models):
    """Solid feature cells and model top faces, region-local, with pack block IDs."""
    solid = np.asarray([pack.block_defs[n].occludes for n in pack.blocks])[types]
    faces, materials = [xyz[solid].astype(np.int64)], [np.asarray(types,np.int64)[solid]]
    for model in models:
        points,ids = model.template.surface_tops[model.rotation]
        points = points+model.anchor
        inside = ((points[:,0] >= region.x0) & (points[:,0] < region.x0+region.width)
                  & (points[:,2] >= region.z0) & (points[:,2] < region.z0+region.depth)
                  & (points[:,1] >= params['world.y_min']) & (points[:,1] < params['world.y_max']))
        faces.append(points[inside]-[region.x0,0,region.z0]);materials.append(ids[inside])
    return np.concatenate(faces), np.concatenate(materials)


def _containment(params, region, p, model_index):
    def keys(points):
        return ((points[:,1]-params['world.y_min'])*region.depth+points[:,2])*region.width+points[:,0]
    occupied = np.unique(keys(p))
    def contains(points):
        values = keys(points)
        at = np.searchsorted(occupied,values)
        found = (at < len(occupied)) & (occupied[np.minimum(at,len(occupied)-1)] == values)
        if model_index is not None:
            found |= model_index.occupied(points+[region.x0,0,region.z0])
        return found
    return contains


def _terrain_filled(pack, params, seed, absolute, resources):
    query = VolumeQuery(pack,params,seed,resources)
    # Nearby faces share planner cells. Keep the query batch size and restore
    # original face order after sampling; do not span distant trees per batch.
    from .density import BLOCK
    order = np.lexsort((absolute[:,1],absolute[:,2]//BLOCK,absolute[:,0]//BLOCK))
    blocked = np.empty(len(absolute),bool)
    blocked[order] = query.occupied(absolute[order])
    return blocked


def blocked_tops(pack, params, seed, region, xyz, types, models, resources):
    """Terrain-filled cells above one tile's feature tops, sampled with the tile's warm caches.

    Other tiles can only hide more tops, so add_surfaces needs no further density queries.
    """
    p, _ = _feature_tops(pack, params, region, xyz, types, models)
    if not len(p):
        return np.empty((0,3),np.int64)
    from .templates import ModelIndex
    contains = _containment(params, region, p, ModelIndex(models,params['world.y_min'],params['world.y_max']) if models else None)
    above = p+[0,1,0]
    absolute = above[~contains(above) & (above[:,1] < params['world.y_max'])]+[region.x0,0,region.z0]
    return absolute[_terrain_filled(pack, params, seed, absolute, resources)]


def add_surfaces(pack,params,seed,region,surfaces,features,model_index=None,*,resources=None,blocked=None):
    """Overlay sparse feature faces and remove terrain faces they now occlude.

    `blocked` holds absolute terrain-filled cells from blocked_tops for every tile.
    """
    from .planning import Resources
    if (features is None or not features.count) and model_index is None:
        return surfaces
    types = np.asarray([pack.blocks.index(n) for n in features.names],np.int64)[features.types]
    p, types = _feature_tops(pack, params, region, features.xyz, types, model_index.instances if model_index is not None else ())
    if not len(p):
        return surfaces
    contains = _containment(params, region, p, model_index)
    surfaces = surfaces[~contains(surfaces[:,:3]+[0,1,0])]
    above = p+[0,1,0]
    visible = ~contains(above) & (above[:,1] < params['world.y_max'])
    ids = np.flatnonzero(visible)
    absolute = above[ids]+[region.x0,0,region.z0]
    if blocked is None:
        filled = _terrain_filled(pack, params, seed, absolute, resources if resources is not None else Resources(pack,params,seed))
    else:
        from .postprocess import _PointIndex
        filled = _PointIndex(blocked).lookup(absolute)[0]
    visible[ids] &= ~filled
    extra = np.column_stack((p[visible],types[visible])).astype(surfaces.dtype,copy=False)
    return np.concatenate((surfaces,extra))
