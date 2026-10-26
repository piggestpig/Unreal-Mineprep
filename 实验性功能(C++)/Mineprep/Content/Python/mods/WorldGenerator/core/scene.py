"""Read-only additions to a generated World; no excavation or actor access."""
from dataclasses import dataclass, replace
import hashlib
import json
from types import MappingProxyType

import numpy as np

from .blocks import BlockDef
from .building import Placement, _readonly
from .data import Region, check_cancel, require_int
from .pack import Params, load_pack
from .shell import WorldArrays
from .spec import WorldSpec
from .templates import TemplateDefinition, TemplateInstance, ModelIndex
from .world import World, _GenerationInput, MAX_CELLS, MAX_INSTANCES


def _keys(points):
    return np.ascontiguousarray(points, dtype=np.int64).view(np.dtype((np.void, 24))).ravel()


def _members(points, sorted_keys):
    result = np.zeros(len(points), bool)
    if len(sorted_keys):
        q = _keys(points)
        at = np.searchsorted(sorted_keys, q)
        use = at < len(sorted_keys)
        result[use] = sorted_keys[at[use]] == q[use]
    return result


def _world_points(data):
    p = data.xyz.astype(np.int64).copy()
    p[:, 0] += data.region.x0
    p[:, 2] += data.region.z0
    return p


class _WorldQuery:
    """One operation's terrain and scenery queries, shared with grounding."""
    def __init__(self, world, cancel_event=None):
        from .planning import Resources
        self.world = world
        self.resources = Resources(world.pack, world.params, world.spec.seed)
        self.resources.cancel_event = cancel_event
        self.hard = None
        self.fluid_keys = (np.empty(0, dtype=np.dtype((np.void, 24))) if world.fluid_layers is None
                           else np.unique(_keys(world.fluid_layers.xyz)))

    def terrain(self, points):
        from .multi_features import _occupied
        w = self.world
        x, z = points[:, 0]-w.region.x0, points[:, 2]-w.region.z0
        # The shell uses y < height, including at an exact integer height.
        tops = np.ceil(w.heights[z, x]).astype(np.int64)-1
        solid = _occupied(w.pack, w.params, w.spec.seed, points, tops, self.resources)
        if w.pack.density is not None and w.pack.density.base == 'height' and w.pack.density.wet_protection == 'shell':
            solid |= (w.wet_mask[z, x] & (points[:, 1] <= tops)
                      & (points[:, 1] >= w.params['world.y_min'])
                      & (points[:, 1] < w.params['world.y_max']))
        return solid

    def features(self, points):
        w = self.world
        if self.hard is None:
            p = _world_points(w.arrays)
            if w.soft_mask is not None:
                p = p[~w.soft_mask]
            if w.feature_cells is not None:
                p = np.r_[p, _world_points(w.feature_cells)]
            self.hard = np.unique(_keys(p))
        found = _members(points, self.hard)
        if w.column_index is not None:
            found |= w.column_index.lookup(points)[0]
        return found

    def models(self, points):
        index = self.world.model_index
        return np.zeros(len(points), bool) if index is None else index.occupied(points)

    def obstacles(self, points):
        w = self.world
        x, z = points[:, 0]-w.region.x0, points[:, 2]-w.region.z0
        wet = w.water_mask[z, x] & (points[:, 1] == np.floor(w.water_levels[z, x]))
        wet |= _members(points, self.fluid_keys)
        return dict(features=self.features(points), models=self.models(points), water=wet)


@dataclass(frozen=True, eq=False)
class Scene:
    terrain: object
    placements: tuple
    world: World
    source: _GenerationInput
    removed_soft_cells: int = 0

    @property
    def key(self):
        return self.world.key

    @property
    def region(self):
        return self.world.region


def _empty_world(region, lo, hi, source):
    pack = source.pack
    spec = source.spec.replace(region=region)
    params = Params({**pack.resolve(source.spec).to_dict(), 'world.y_min': lo, 'world.y_max': hi})
    shape = region.shape
    arrays = WorldArrays(region, _readonly(np.empty((0, 3)), np.int32),
                         _readonly([], np.uint32), (), 0)
    return World(spec, '', pack, params, _readonly(np.full(shape, lo-1), np.float32),
        _readonly(np.zeros(shape), np.uint16), _readonly(np.zeros((*shape, 3)), np.uint16),
        {}, arrays, {}, _readonly(np.zeros(shape), bool), _readonly(np.zeros(shape), np.uint16),
        _readonly(np.zeros(shape), np.float64), _readonly(np.zeros(shape), bool))


def compose(terrain, *placements, max_cells=MAX_CELLS, max_instances=MAX_INSTANCES):
    if terrain is not None and not isinstance(terrain, World):
        raise TypeError('compose terrain must be a generated World or None')
    if not placements or any(not isinstance(p, Placement) or not p.structure.count for p in placements):
        raise ValueError('compose needs nonempty Structure.at(...) placements')
    require_int('max_cells', max_cells, 1, 2**63-1)
    require_int('max_instances', max_instances, 1, 2**63-1)
    if sum(p.structure.count for p in placements) > max_instances:
        raise ValueError('structure logical cells exceed max_instances')
    if terrain is None:
        source = _GenerationInput.capture(WorldSpec())
        bounds = np.array([(p.points.min(axis=0), p.points.max(axis=0)+1) for p in placements])
        lo, hi = bounds[:, 0].min(axis=0), bounds[:, 1].max(axis=0)
        if lo[1] <= -(2**31) or hi[1] >= 2**31:
            raise ValueError('scene height exceeds output int32 coordinates')
        region = Region(int(lo[0]), int(lo[2]), int(hi[0]-lo[0]), int(hi[2]-lo[2]))
        if region.cells > max_cells:
            raise ValueError('scene reference area exceeds max_cells')
        base = _empty_world(region, int(lo[1]), int(hi[1]), source)
        names, defs = [], {}
    else:
        source = _GenerationInput.capture(terrain.spec)
        base = terrain
        names, defs = list(base.pack.blocks), dict(base.pack.block_defs)
    if base.region.cells > max_cells:
        raise ValueError('scene reference area exceeds max_cells')
    if base.arrays.count + sum(m.block_count for m in base.model_instances) + sum(p.structure.count for p in placements) > max_instances:
        raise ValueError('scene cells exceed max_instances')
    region = base.region
    minimum = np.array([region.x0, base.params['world.y_min'], region.z0])
    maximum = np.array([region.x0+region.width, base.params['world.y_max'], region.z0+region.depth])
    material_ids = {}
    for placement in placements:
        points = placement.points
        if np.any(points < minimum) or np.any(points >= maximum):
            raise ValueError('structure exceeds generated region or output height; expand the World first')
        for name, _ in placement.structure.palette:
            if name in material_ids:
                continue
            alias = name
            old = defs.get(name)
            if old is not None and (old.source != 'builtin' or old.value != name
                    or old.offset != (0., 0., 0.) or old.scale != (1., 1., 1.)):
                alias = 'build_'+name
                while alias in defs:
                    alias = 'build_'+alias
            if alias not in defs:
                # A recipe is baked from real model faces. Do not assert that
                # stairs, fences or other native models are full opaque cubes.
                defs[alias] = BlockDef(alias, 'builtin', name, shape='decor', occludes=False, merge='none')
                names.append(alias)
            material_ids[name] = names.index(alias)
    if len(names) > 65536:
        raise ValueError('scene exceeds uint16 material palette')
    recipes, models = {}, list(base.model_instances)
    for i, placement in enumerate(placements):
        s = placement.structure
        template = recipes.get(s.key)
        if template is None:
            types = np.array([material_ids[s.palette[t][0]] for t in s.types], np.uint16)
            cells = tuple((*map(int, p), *s.palette[t]) for p, t in zip(s.xyz, s.types))
            # Symmetric bounds cover all four orientations; occupancy remains
            # exact cells, so empty space inside a house is not filled.
            radius = int(np.abs(s.xyz[:, [0, 2]]).max())+1
            box = np.array([[[-radius, int(s.xyz[:, 1].min()), -radius],
                             [radius+1, int(s.xyz[:, 1].max())+1, radius+1]]], np.int32)
            template = TemplateDefinition('build_'+s.key[:32], s.xyz, types, box, cells, two_sided=False)
            recipes[s.key] = template
        points = placement.points
        bounds = tuple(map(int, np.r_[points.min(axis=0), points.max(axis=0)+1]))
        models.append(TemplateInstance(('structure', i), placement.position, bounds, s.count, template, placement.rotation//90))
    raw = (1, None if terrain is None else terrain.key,
           [(p.structure.key, p.position, p.rotation) for p in placements])
    key = hashlib.sha256(json.dumps(raw, separators=(',', ':')).encode()).hexdigest()
    model_index = ModelIndex(tuple(models), base.params['world.y_min'], base.params['world.y_max'])
    data = base.arrays
    removed = np.zeros(data.count, bool)
    if base.soft_mask is not None and base.soft_mask.any():
        at = np.flatnonzero(base.soft_mask)
        added_index = ModelIndex(tuple(models[len(base.model_instances):]), base.params['world.y_min'], base.params['world.y_max'])
        removed[at] = added_index.occupied(_world_points(data)[at])
    if removed.any():
        data = replace(data, xyz=_readonly(data.xyz[~removed], np.int32), types=_readonly(data.types[~removed], np.uint32),
            rotations=None if data.rotations is None else _readonly(data.rotations[~removed], np.uint8),
            instance_y_offsets=None if data.instance_y_offsets is None else _readonly(data.instance_y_offsets[~removed], np.float64),
            visible_count=int((~removed).sum()))
    runtime_pack = replace(base.pack, blocks=tuple(names), block_defs=MappingProxyType(defs))
    stats = {**base.stats, 'structure_instances': len(placements), 'structure_templates': len(recipes),
             'structure_cells': sum(p.structure.count for p in placements), 'scene_removed_soft_cells': int(removed.sum()),
             'output_instances': data.count+len(models), 'model_instances': len(models),
             'model_templates': len({m.template.id for m in models}),
             'model_logical_cells': sum(m.block_count for m in models),
             'model_array_bytes': model_index.array_bytes,
             'soft_plants': 0 if base.soft_mask is None else int(base.soft_mask[~removed].sum()),
             'output_model_types': len(np.unique(data.types))+len({m.template.id for m in models})}
    view = replace(base, key=key, pack=runtime_pack, arrays=data, stats=stats, model_instances=tuple(models),
        model_index=model_index, soft_mask=None if base.soft_mask is None else _readonly(base.soft_mask[~removed], bool))
    return Scene(terrain, tuple(placements), view, source, int(removed.sum()))


def check_scene(scene, *, cancel_event=None):
    base = scene.terrain
    query = None if base is None else _WorldQuery(base, cancel_event)
    previous = np.empty(0, dtype=np.dtype((np.void, 24)))
    result = dict(ok=True, scope='scene', key=scene.key, structures=[], errors=[],
                  removed_soft_cells=scene.removed_soft_cells, collisions=0)
    for placement in scene.placements:
        points = placement.points
        own_keys = np.unique(_keys(points))
        collisions = dict(terrain=0, features=0, models=0, water=0, structures=0)
        examples, contacts = [], 0
        for start in range(0, len(points), 2048):
            check_cancel(cancel_event)
            p = points[start:start+2048]
            overlap = _members(p, previous)
            collisions['structures'] += int(overlap.sum())
            blocked = overlap.copy()
            if base is not None:
                rock = query.terrain(p)
                obstacles = query.obstacles(p)
                obstacles['features'] &= ~rock
                for name, mask in [('terrain', rock), *obstacles.items()]:
                    collisions[name] += int(mask.sum())
                    blocked |= mask
                below = p.copy()
                below[:, 1] -= 1
                bottoms = np.flatnonzero(~_members(below, own_keys))
                if len(bottoms):
                    q = below[bottoms]
                    supported = query.terrain(q) | query.features(q) | query.models(q)
                    contacts += int(supported.sum())
            result['collisions'] += int(blocked.sum())
            examples.extend(p[blocked][:max(0, 12-len(examples))].tolist())
        previous = np.unique(np.r_[previous, _keys(points)])
        result['structures'].append(dict(name=placement.structure.name, cells=len(points),
            position=list(placement.position), rotation=placement.rotation,
            collisions=collisions, samples=examples, ground_contacts=contacts))
    if result['collisions']:
        result['ok'] = False
        result['errors'].append(f"{result['collisions']} structure cells collide with terrain, scenery, water or earlier structures")
    return result


@dataclass(frozen=True)
class SceneInput:
    """The existing prepare pipeline can consume an already composed snapshot."""
    scene: Scene

    @property
    def spec(self):
        return self.scene.world.spec

    @property
    def key(self):
        return self.scene.key

    @property
    def heightmap_source(self):
        return self.scene.source.heightmap_source

    @property
    def pack(self):
        return self.scene.world.pack

    def resolved(self, cancel_event=None):
        return self

    def validate(self, max_cells, max_instances, cancel_event=None):
        world = self.scene.world
        if world.region.cells > max_cells or (world.arrays.count+sum(m.block_count for m in world.model_instances)) > max_instances:
            raise ValueError('scene exceeds max_cells or max_instances')
        report = check_scene(self.scene, cancel_event=cancel_event)
        if not report['ok']:
            raise ValueError('; '.join(report['errors']))
        return world
