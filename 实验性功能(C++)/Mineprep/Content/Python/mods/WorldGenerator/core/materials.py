"""Sparse shell-only materials. Geometry and UE resources remain separate."""
from dataclasses import dataclass
from types import MappingProxyType
from time import perf_counter
import numpy as np
from .data import check_cancel


@dataclass(frozen=True)
class ShellMaterials:
    sampler: object
    blocks: tuple
    enabled_param: object = None
    surface_depth: int = 0
    surface_depth_enabled_param: object = None


@dataclass(frozen=True)
class TerrainMaterials:
    sampler: object
    inputs: tuple
    blocks: tuple
    fields: tuple = ()
    enabled_param: object = None


@dataclass(frozen=True)
class TerrainMaterialContext:
    """Sparse terrain cells and read-only, flattened reference columns.

    `fields[name][column_index]` gives a cell's reference value without
    evaluating noise per voxel. Coordinates are absolute world coordinates.
    """
    pack: object
    params: object
    seed: int
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    materials: np.ndarray
    biomes: np.ndarray
    column_index: np.ndarray
    fields: object
    block_index: object


def readonly(value):
    result = np.asarray(value).view()
    result.setflags(write=False)
    return result


def validate_result(pack, recipe, original, result, label):
    """Shared validation for cave and ordinary terrain material samplers."""
    result = np.asarray(result)
    if result.shape != original.shape or result.dtype.kind not in 'iu':
        raise ValueError(f'{label} sampler must return an equal-length integer array')
    if np.any(result < 0) or np.any(result >= len(pack.blocks)):
        raise ValueError(f'{label} sampler returned an invalid block ID')
    solid = np.array([pack.block_defs[n].occludes and pack.block_defs[n].shape == 'cube'
                      for n in pack.blocks], bool)
    allowed = np.array([n in recipe.blocks for n in pack.blocks], bool)
    if np.any(~solid[result]) or np.any((result != original) & ~allowed[result]):
        raise ValueError(f'{label} may only return original or declared opaque cube types')
    return result


def apply_terrain(pack, params, seed, xyz, types, reference, biomes, *, origin=(0, 0)):
    """Recolour an emitted shell, or just its overview tops; never emit cells."""
    recipe = pack.terrain_materials
    if recipe is None or (recipe.enabled_param is not None and not params[recipe.enabled_param]):
        return types
    selected = np.array([n in recipe.inputs for n in pack.blocks], bool)
    chosen = np.flatnonzero(selected[types])
    if not len(chosen):
        return types
    resources = reference.resources
    check_cancel(getattr(resources, 'cancel_event', None))
    started = perf_counter()
    coords = xyz[chosen].astype(np.int64)
    coords[:, 0] += origin[0]
    coords[:, 2] += origin[1]
    ix = coords[:, 0] - int(reference.x[0, 0])
    iz = coords[:, 2] - int(reference.z[0, 0])
    if np.any((ix < 0) | (ix >= reference.shape[1]) | (iz < 0) | (iz >= reference.shape[0])):
        raise ValueError('terrain_materials coordinates outside reference columns')
    index = iz * reference.shape[1] + ix
    fields = {}
    for name in recipe.fields:
        value = np.asarray(reference.get(name))
        if value.shape != reference.shape or not np.isfinite(value).all():
            raise ValueError(f'terrain_materials field {name}: expected finite reference columns')
        fields[name] = readonly(value.reshape(-1))
    ctx = TerrainMaterialContext(pack, params, seed, *(readonly(coords[:,i]) for i in range(3)),
                                 readonly(types[chosen]), readonly(biomes.reshape(-1)[index]),
                                 readonly(index), MappingProxyType(fields),
                                 MappingProxyType({n:i for i,n in enumerate(pack.blocks)}))
    result = validate_result(pack, recipe, ctx.materials, recipe.sampler(ctx), 'terrain_materials')
    check_cancel(getattr(resources, 'cancel_event', None))
    changed = int(np.count_nonzero(result != ctx.materials))
    if resources is not None:
        resources.report.add('terrain_material_candidates', len(chosen))
        resources.report.add('terrain_material_changed', changed)
        resources.report.add('terrain_material_seconds', perf_counter()-started)
        resources.report.peak('terrain_material_work_bytes', coords.nbytes+index.nbytes+
                              chosen.nbytes+result.nbytes+sum(v.nbytes for v in fields.values()))
    if not changed:
        return types
    output = types.copy()
    output[chosen] = result
    return output


def colour_tops(ctx, pack, biomes, height, columns):
    """Reference tops share the shell sampler, without allocating shell cells."""
    recipe = pack.terrain_materials
    if recipe is None or (recipe.enabled_param is not None and not ctx.params[recipe.enabled_param]):
        return columns
    eligible = np.array([n in recipe.inputs for n in pack.blocks], bool)[columns[...,0]]
    zz, xx = np.nonzero(eligible)
    if not len(xx):
        return columns
    xyz = np.column_stack((ctx.x[0,xx], np.ceil(height[zz,xx])-1, ctx.z[zz,0])).astype(np.int64)
    types = columns[zz,xx,0]
    coloured = apply_terrain(pack, ctx.params, ctx.seed, xyz, types, ctx, biomes)
    output = columns.copy()
    output[zz,xx,0] = coloured
    return output


@dataclass(frozen=True)
class MaterialContext:
    """Read-only 1D world samples. Faces: -X,+X,-Y,+Y,-Z,+Z bits 0..5.

    `depth` uses the uncut reference surface. `carved_faces` excludes natural
    outside air and artificial output cuts. Volume recipes treat real air as
    carved. Resources are the existing planning lookup, not a voxel cache.
    """
    pack: object
    params: object
    seed: int
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    materials: np.ndarray
    depth: np.ndarray
    exposed_faces: np.ndarray
    carved_faces: np.ndarray
    biomes: np.ndarray
    resources: object
    block_index: object
    floor_depth: object = None  # 0 = adjacent air above; cap = no nearby air
    ceiling_depth: object = None

    def record(self, name, value):
        if self.resources is not None:
            key = 'material_' + name
            self.resources.report.add(key, value)


def active(pack, params):
    recipe = pack.shell_materials
    return recipe is not None and (recipe.enabled_param is None or params[recipe.enabled_param])


def surface_depth(pack, params):
    recipe = pack.shell_materials
    if not active(pack, params):
        return 0
    gate = recipe.surface_depth_enabled_param
    return recipe.surface_depth if gate is None or params[gate] else 0


def depths(occupied, indices, cap):
    """Nearest natural air in each vertical direction; indices include the halo."""
    iz, iy, ix = indices
    floor = np.full(len(ix), cap, np.uint8)
    ceiling = floor.copy()
    for distance in range(1, cap + 1):
        floor[(floor == cap) & ~occupied[iz, iy + distance, ix]] = distance - 1
        ceiling[(ceiling == cap) & ~occupied[iz, iy - distance, ix]] = distance - 1
    return floor, ceiling


def faces(occupied, tops, y, indices, params, *, height_mode):
    """Classify only sparse visible cells from the uncut existing halo buffer."""
    iz, iy, ix = (a + 1 for a in indices)
    exposed, carved = np.zeros(len(ix), np.uint8), np.zeros(len(ix), np.uint8)
    for bit, (dz, dy, dx) in enumerate(((0,0,-1),(0,0,1),(0,-1,0),(0,1,0),(-1,0,0),(1,0,0))):
        nz, ny, nx = iz + dz, iy + dy, ix + dx
        heights = y[0,ny,0]
        air = ~occupied[nz,ny,nx]
        air &= (heights >= params['world.y_min']) & (heights < params['world.y_max'])
        exposed |= air.astype(np.uint8) << bit
        if height_mode:
            air &= heights <= tops[nz,nx]
        carved |= air.astype(np.uint8) << bit
    return exposed, carved


def apply(pack, params, seed, xyz, types, depth, exposed, carved, biomes, resources, *, natural_depths=None):
    """Change opaque exposed cells only; output validation is core-owned."""
    if not active(pack, params):
        return types
    solid = np.array([pack.block_defs[n].occludes and pack.block_defs[n].shape == 'cube'
                      for n in pack.blocks], bool)
    chosen = np.flatnonzero((carved != 0) & solid[types])
    if not len(chosen):
        return types
    check_cancel(getattr(resources, 'cancel_event', None))
    start = perf_counter()
    coords = xyz[chosen]
    ctx = MaterialContext(pack, params, seed, *(readonly(coords[:,i]) for i in range(3)),
                          readonly(types[chosen]), readonly(depth[chosen]), readonly(exposed[chosen]),
                          readonly(carved[chosen]), readonly(biomes[chosen]), resources,
                          MappingProxyType({n:i for i,n in enumerate(pack.blocks)}),
                          *(tuple(readonly(d[chosen]) for d in natural_depths) if natural_depths is not None
                            else (None, None)))
    result = validate_result(pack, pack.shell_materials, ctx.materials,
                             pack.shell_materials.sampler(ctx), 'shell_materials')
    check_cancel(getattr(resources, 'cancel_event', None))
    output = types.copy()
    output[chosen] = result
    ctx.record('candidates', len(chosen))
    ctx.record('changed', int(np.count_nonzero(result != ctx.materials)))
    ctx.record('seconds', perf_counter() - start)
    return output
