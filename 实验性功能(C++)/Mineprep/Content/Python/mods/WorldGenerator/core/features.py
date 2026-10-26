"""Deterministic surface scatter, keyed by seed, feature ID and world coordinates."""
from dataclasses import dataclass, field, replace
import math
import numpy as np
from .noise import seed_key
from .surface import block_name, parse_bound, bound


@dataclass(frozen=True)
class Feature:
    id: str
    block: str
    biomes: tuple = ()
    surface: tuple = ()
    density: object = 0
    patch_scale: object = 1
    max_slope: object = 0
    enabled_param: object = None
    category: str = 'features'
    enabled_when: tuple = ()
    habitat: str = 'dry'
    soft: bool = False
    allow_overlap_categories: tuple = ()
    placement: object = None  # None = legacy reference surface; volume_floor = all true floors

    @property
    def type(self):
        return 'surface_scatter'

    @property
    def blocks(self):
        return (self.block,)


@dataclass(frozen=True)
class MultiBlockFeature:
    id: str
    generator: str
    blocks: tuple
    bounds: tuple
    max_blocks: int
    cell_size: object
    enabled_param: object = None
    biomes: tuple = ()
    surface: tuple = ()
    density: object = 0
    patch_scale: object = 1
    max_slope: object = 0
    priority: int = 0
    support: str = 'anchor'
    habitat: str = 'dry'
    owner: str = ''
    fn: object = field(default=None, repr=False, compare=False)
    category: str = 'features'
    enabled_when: tuple = ()
    placement: object = None
    placement_fn: object = field(default=None, repr=False, compare=False)
    collision: str = 'bounds'  # explicit volume recipes may opt into exact cells
    overlap_blocks: tuple = ()  # small canopy overlaps; all other contacts remain hard

    @property
    def type(self):
        return 'multi_block'


@dataclass(frozen=True)
class FeatureBatch:
    """Integer local XYZ offsets, pack block IDs, and indices into input anchors."""
    offsets: np.ndarray
    types: np.ndarray
    owners: np.ndarray
    rotations: object = None  # integer [N] codes 0..23; None means identity


@dataclass(frozen=True)
class ColumnFeature:
    id: str
    generator: str
    blocks: tuple
    radius: int
    max_height: int
    habitat: str = 'water_surface'
    category: str = 'features'
    enabled_param: object = None
    biomes: tuple = ()
    surface: tuple = ()
    density: object = 0
    patch_scale: object = 1
    max_slope: object = 0
    owner: str = ''
    fn: object = field(default=None, repr=False, compare=False)
    enabled_when: tuple = ()

    @property
    def type(self): return 'column_field'


@dataclass(frozen=True)
class ColumnBatch:
    """Absolute XZ columns and half-open Y intervals; adjacent materials allowed."""
    xz: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    types: np.ndarray
    diagnostics: dict = field(default_factory=dict)


def describe_feature(f):
    """Source declaration only: callable namespaces are private and not JSON data."""
    raw = {k: v for k, v in f.__dict__.items() if k not in
           ('id', 'owner', 'fn', 'placement_fn', 'biomes', 'surface', 'density', 'patch_scale', 'max_slope', 'enabled_param')}
    raw['enabled_when']=dict(f.enabled_when)
    if f.type == 'surface_scatter' and f.placement is None:
        raw.pop('placement', None)
    return dict(id=f.id, type=f.type, **raw)


def enabled(feature, params):
    return ((feature.enabled_param is None or params[feature.enabled_param]) and
            all(params[key] == value for key, value in feature.enabled_when))


def parse_feature(name, raw):
    if not isinstance(raw, dict): return _parse_feature(name, raw)
    raw = dict(raw)
    when = raw.pop('enabled_when', {})
    if not isinstance(when, dict) or any(not isinstance(k,str) or type(v) is not bool for k,v in when.items()):
        raise ValueError(f'feature {name}: enabled_when must map boolean parameters to booleans')
    return replace(_parse_feature(name,raw),enabled_when=tuple(sorted(when.items())))


def _parse_feature(name, raw):
    if isinstance(raw, dict) and raw.get('type') == 'column_field':
        from .data import require_int
        keys = {'type','generator','blocks','radius','max_height'}
        if not keys <= raw.keys() or set(raw)-keys-{'habitat','category'} or not name.isidentifier():
            raise ValueError(f'feature {name}: invalid column_field declaration')
        target = raw['generator']
        if not isinstance(target,str) or len(target.split(':')) != 2 or not all(p.isidentifier() for p in target.split(':')):
            raise ValueError(f'feature {name}: generator must be module:function')
        blocks = raw['blocks']
        if not isinstance(blocks,list) or not blocks or any(not isinstance(b,str) for b in blocks) or len(set(blocks)) != len(blocks):
            raise ValueError(f'feature {name}: blocks must be unique names')
        habitat, category = raw.get('habitat','water_surface'), raw.get('category','features')
        if habitat not in ('dry','underwater','water_surface') or not isinstance(category,str) or not category.isidentifier():
            raise ValueError(f'feature {name}: invalid habitat/category')
        require_int(f'feature {name}.radius',raw['radius'],0,128)
        require_int(f'feature {name}.max_height',raw['max_height'],1,4096)
        return ColumnFeature(name,target,tuple(block_name(b) for b in blocks),raw['radius'],raw['max_height'],habitat,category)
    common = {'type'}
    multi = isinstance(raw, dict) and raw.get('type') == 'multi_block'
    keys = common | ({'generator', 'blocks', 'bounds', 'max_blocks', 'cell_size'}
                     if multi else {'block'})
    optional = {'category'} | ({'priority', 'support', 'habitat', 'placement', 'collision', 'overlap_blocks'} if multi else
                              {'habitat', 'soft', 'allow_overlap_categories', 'placement'})
    if (not isinstance(raw, dict) or not keys <= set(raw) or set(raw) - keys - optional or not name.isidentifier()
            or raw['type'] not in ('surface_scatter', 'multi_block')):
        raise ValueError(f'feature {name}: needs {sorted(keys)}; supported types: surface_scatter, multi_block')
    category = raw.get('category', 'features')
    if not isinstance(category, str) or not category.isidentifier():
        raise ValueError(f'feature {name}: category must be an identifier')
    if multi:
        from .data import require_int
        target = raw['generator']
        if not isinstance(target, str) or len(target.split(':')) != 2 or not all(p.isidentifier() for p in target.split(':')):
            raise ValueError(f'feature {name}: generator must be module:function')
        blocks = raw['blocks']
        if (not isinstance(blocks, list) or not blocks or any(not isinstance(b, str) for b in blocks)
                or len(set(blocks)) != len(blocks)):
            raise ValueError(f'feature {name}: blocks must be unique block names')
        blocks = tuple(block_name(b) for b in blocks)
        bounds = raw['bounds']
        if (not isinstance(bounds, list) or len(bounds) != 2 or any(not isinstance(v, list) or len(v) != 3 for v in bounds)
                or any(type(v) is not int for row in bounds for v in row)
                or any(a >= b for a, b in zip(*bounds))):
            raise ValueError(f'feature {name}: bounds need integer half-open XYZ min/max')
        require_int(f'feature {name}.max_blocks', raw['max_blocks'], 1, 2**31-1)
        if isinstance(raw['cell_size'],str):
            parse_bound(raw['cell_size'],f'feature {name}.cell_size')
        else:
            require_int(f'feature {name}.cell_size', raw['cell_size'], 1, 1024)
        require_int(f'feature {name}.priority', raw.get('priority', 0), -(2**31), 2**31-1)
        if raw.get('support', 'anchor') not in ('anchor', 'footprint', 'ceiling'):
            raise ValueError(f'feature {name}.support: anchor, footprint or ceiling required')
        if raw.get('habitat', 'dry') not in ('dry', 'underwater', 'water_surface'):
            raise ValueError(f'feature {name}.habitat: dry, underwater or water_surface required')
        placement = raw.get('placement')
        if placement is not None and (not isinstance(placement,str) or len(placement.split(':')) != 2
                                      or not all(p.isidentifier() for p in placement.split(':'))):
            raise ValueError(f'feature {name}.placement must be module:function')
        collision = raw.get('collision','bounds')
        if collision not in ('bounds','cells') or (collision == 'cells' and placement is None):
            raise ValueError(f'feature {name}.collision: bounds or cells with explicit volume placement required')
        overlaps = raw.get('overlap_blocks',[])
        if (not isinstance(overlaps,list) or any(not isinstance(b,str) or b not in blocks for b in overlaps)
                or len(set(overlaps)) != len(overlaps) or (overlaps and collision != 'cells')):
            raise ValueError(f'feature {name}.overlap_blocks: declared blocks with cell collision required')
        return MultiBlockFeature(name, target, blocks, tuple(tuple(v) for v in bounds),
                                 raw['max_blocks'], raw['cell_size'],
                                 priority=raw.get('priority', 0), support=raw.get('support', 'anchor'),
                                 habitat=raw.get('habitat', 'dry'), category=category, placement=placement,
                                 collision=collision,overlap_blocks=tuple(overlaps))
    habitat, soft = raw.get('habitat', 'dry'), raw.get('soft', False)
    placement = raw.get('placement')
    if placement not in (None, 'volume_floor') or (placement == 'volume_floor' and habitat != 'dry'):
        raise ValueError(f'feature {name}: volume_floor requires dry scatter')
    overlap = raw.get('allow_overlap_categories', [])
    if (habitat not in ('dry', 'underwater') or type(soft) is not bool
            or not isinstance(overlap, list)
            or any(not isinstance(v, str) or not v.isidentifier() for v in overlap)):
        raise ValueError(f'feature {name}: invalid scatter habitat/soft/overlap categories')
    return Feature(name, block_name(raw['block']), category=category, habitat=habitat,
                   soft=soft, allow_overlap_categories=tuple(overlap), placement=placement)


def parse_placements(raw, where):
    if not isinstance(raw, dict):
        raise ValueError(f'{where}.features must map feature IDs to placement objects')
    result = {}
    required = {'surface', 'density'}
    for name, item in raw.items():
        at = f'{where}.features.{name}'
        if (not isinstance(name, str) or not name.isidentifier() or not isinstance(item, dict)
                or not required <= item.keys() or set(item) - required - {'enabled_param', 'patch_scale', 'max_slope'}):
            raise ValueError(f'{at}: needs surface/density/patch_scale/max_slope and optional enabled_param')
        surface = item['surface']
        if not isinstance(surface, list) or not surface or any(not isinstance(n, str) for n in surface):
            raise ValueError(f'{at}.surface must be non-empty block names')
        values = [parse_bound(item[k], at+'.'+k) if k in item else None
                  for k in ('density', 'patch_scale', 'max_slope')]
        if values[0] is None or any(isinstance(v, float) and not math.isfinite(v) for v in values):
            raise ValueError(f'{at}: placement values must be finite')
        gate = item.get('enabled_param')
        if gate is not None and not isinstance(gate, str):
            raise ValueError(f'{at}.enabled_param must name a boolean parameter')
        result[name] = dict(surface=tuple(block_name(n) for n in surface), density=values[0],
                            patch_scale=values[1], max_slope=values[2], enabled_param=gate)
    return result


def compile_placements(definitions, biomes, params):
    """Merge identical biome bindings; preserve the old candidate grid and feature order."""
    grouped = {}
    for definition in definitions.values():
        for key, _ in definition.enabled_when:
            if key not in params or params[key].type != 'bool':
                raise ValueError(f'feature {definition.id}: enabled_when requires boolean parameters')
    for biome in biomes:
        for name, placement in biome.features.items():
            if name not in definitions:
                raise ValueError(f'biome {biome.id}: unknown feature {name!r}')
            volume = (definitions[name].type == 'surface_scatter'
                      and definitions[name].placement == 'volume_floor')
            extra = (placement['patch_scale'], placement['max_slope'])
            if (volume and any(v is not None for v in extra)) or (not volume and any(v is None for v in extra)):
                raise ValueError(f'biome {biome.id}: {name} ' + ('volume_floor uses only surface/density'
                                 if volume else 'needs patch_scale/max_slope'))
            gate = placement['enabled_param']
            if gate is not None and (gate not in params or params[gate].type != 'bool'):
                raise ValueError(f'biome {biome.id}: enabled_param must name a boolean parameter')
            for key in ('density', 'patch_scale', 'max_slope'):
                v = placement[key]
                if v is None:
                    continue
                if isinstance(v, str) and (v[1:] not in params or params[v[1:]].type not in ('float', 'int')):
                    raise ValueError(f'biome {biome.id}: unknown/non-numeric parameter {v}')
                value = params[v[1:]].default if isinstance(v, str) else v
                if key == 'density' and not 0 <= value <= 1 or key == 'patch_scale' and value <= 0 or key == 'max_slope' and value < 0:
                    raise ValueError(f'biome {biome.id}: invalid {key}')
            signature = (name, tuple(placement.items()))
            grouped.setdefault(signature, []).append(biome.id)
    return tuple(replace(definition, biomes=tuple(ids), **dict(signature[1]))
                 for name, definition in definitions.items()
                 for signature, ids in grouped.items() if signature[0] == name)


def scatter(ctx, pack, biomes, columns, height, *, wet_mask=None, water_levels=None, owners=None):
    """uint16[Z,X], zero = empty, otherwise pack block ID + 1."""
    result = np.zeros(ctx.shape, np.uint16)
    index = {n: i for i, n in enumerate(pack.blocks)}
    top_boundary = np.ceil(height)
    for f in pack.features:
        if f.type != 'surface_scatter' or f.placement is not None:
            continue
        if not enabled(f,ctx.params):
            continue
        if f.habitat == 'underwater':
            from .water import generated as water_generated
            if not water_generated(pack, ctx.params):
                continue
        density, scale, slope = (bound(ctx, v) for v in (f.density, f.patch_scale, f.max_slope))
        if not 0 <= density <= 1 or scale <= 0 or slope < 0:
            raise ValueError(f'feature {f.id}: density [0,1], patch_scale >0 and max_slope >=0 required')
        if not density:
            continue
        dry = height >= ctx.param('world.sea_level') if wet_mask is None else ~wet_mask
        habitat = dry
        if f.habitat == 'underwater':
            if water_levels is None:
                continue
            habitat = ~dry & (top_boundary < np.floor(water_levels))
        mask = ((result == 0) & habitat
                & ((top_boundary > ctx.param('world.y_min')) if f.soft else True)
                & (top_boundary < ctx.param('world.y_max')) & (ctx.get('slope') <= slope)
                & np.isin(biomes, [i for i, b in enumerate(pack.biomes) if b.id in f.biomes])
                & np.isin(columns[..., 0], [index[n] for n in f.surface]))
        if not mask.any():
            continue
        patch = ctx.noise(f'features/{f.id}/patch', scale, octaves=2)
        probability = np.clip(density * np.clip(1 + 2 * patch, 0, 2), 0, 1)
        from .masks import weight
        probability = probability * weight(pack, f.category, ctx.x, ctx.z)
        x = ctx.x.astype(np.int64).astype(np.uint64)
        z = ctx.z.astype(np.int64).astype(np.uint64)
        with np.errstate(over='ignore'):
            hashed = (x * np.uint64(0x9E3779B185EBCA87) ^ z * np.uint64(0xC2B2AE3D27D4EB4F)
                      ^ seed_key(ctx.seed, f'features/{f.id}/candidate')[0])
            hashed = (hashed ^ (hashed >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
            hashed = (hashed ^ (hashed >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
            hashed ^= hashed >> np.uint64(31)
        uniform = (hashed >> np.uint64(11)).astype(np.float64) * (1.0 / 2**53)
        selected = mask & (uniform < probability)
        result[selected] = index[f.block] + 1
        if owners is not None:
            owners[selected] = next(i+1 for i, d in enumerate(pack.feature_defs) if d.id == f.id)
    return result


def remove_soft_plants(world, points):
    """Keep scatter previews and ownership counts aligned after column clipping."""
    if not len(points):
        return world
    from .feature_stats import aggregate
    x, z = points[:, 0]-world.region.x0, points[:, 2]-world.region.z0
    plants, owners = world.plant_ids.copy(), world.plant_owners.copy()
    by_id = {k:dict(v, blocks=dict(v['blocks'])) for k,v in world.stats['feature_counts'].items()}
    for owner in np.unique(owners[z, x]):
        use = owners[z, x] == owner
        item = by_id[world.pack.feature_defs[int(owner)-1].id]
        item['instances'] -= int(use.sum())
        item['cells'] -= int(use.sum())
        for block, count in zip(*np.unique(plants[z[use], x[use]], return_counts=True)):
            name = world.pack.blocks[int(block)-1]
            item['blocks'][name] -= int(count)
            if not item['blocks'][name]: del item['blocks'][name]
    plants[z, x] = owners[z, x] = 0
    plants.setflags(write=False)
    owners.setflags(write=False)
    return replace(world, plant_ids=plants, plant_owners=owners,
                   stats=dict(world.stats, vegetation=int(np.count_nonzero(plants)),
                              **aggregate(world.pack, by_id)))
