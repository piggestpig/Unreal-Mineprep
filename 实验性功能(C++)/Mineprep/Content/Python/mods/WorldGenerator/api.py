"""Public entry for scripts and agents. preview/prepare/place require UE.

    from mods.WorldGenerator import api
    spec = api.spec("vanilla", "default", seed=7, region=(0, 0, 512, 512))
    spec = spec.with_params({"terrain.mountain_height": 110, "climate.temperature_offset": -0.2})
    world = api.generate(spec)                 # arrays: heights, biome_ids, columns, arrays...
    api.snapshot(world, "out/sheet.png")
    job = api.prepare(spec, backend="pcg")     # UE main thread; returns a Job
    # when job.state == "completed":  api.place(job.result, location=(0, 0, 0))
"""

from .core.data import Region, from_ue, to_ue
from .core.fields import field, region_pass
from .core.pack import list_packs, load_pack, register_pack_root, catalog as _catalog
from .core.spec import WorldSpec
from .core.world import build_world, build_overview, sample_fields, world_key

__all__ = ["spec", "generate", "overview", "snapshot", "fields", "packs", "pack", "describe",
           "prepare", "place", "preview", "edit", "plan_water", "plan_caves", "fluid_surfaces", "section", "projection", "apply_preset", "reset_section", "preset_sections", "presets", "preset_library", "register_pack_root", "WorldSpec", "Region", "world_key"]
__all__.append('catalog')
__all__.extend(('create_pack', 'check', 'locate', 'biome_order'))
__all__.append('write_biome_texture')
__all__.append('with_heightmap')
__all__.extend(('with_vegetation_mask', 'with_clearance_mask'))
__all__.extend(('to_ue', 'from_ue', 'field', 'region_pass'))
from .core.building import Builder, Selection, Structure
from .core.scene import Scene
__all__.extend(('builder', 'compose', 'palette', 'Builder', 'Selection', 'Structure', 'Scene'))
__all__.extend(('to_blocks', 'from_blocks'))
__all__.extend(('ground', 'foundation'))
from .core.scatter import ScatterResult
__all__.extend(('scatter', 'ScatterResult'))
__all__.extend(('mesh_structure', 'uv_structure', 'image_structure'))


def image_structure(source, *, size=128, depth=1, axis='z', palette=None,
                    resample='box', colors=None, smooth=0., alpha_cutoff=0.5,
                    name='Image', max_cells=4_000_000):
    """Image/Texture2D to pixel art or solid relief; depth accepts a map or callable.

    An integer size caps the longest edge without upscaling; None keeps native size.
    colors caps used block types; smooth (0..1) groups similar neighbouring colours.
    A depth tuple gives black/white thicknesses. A callable receives the resized
    uint8 RGBA image and returns a scalar or [height,width] depth map.
    """
    from .adapters.image_input import image_structure as convert
    return convert(source, size=size, depth=depth, axis=axis, palette=palette,
                   resample=resample, colors=colors, smooth=smooth,
                   alpha_cutoff=alpha_cutoff, name=name, max_cells=max_cells)


def mesh_structure(source, *, resolution=128, palette=None, textures=None, up_axis=None,
                   alpha_cutoff=0.5, name='Model', max_cells=4_000_000):
    """Textured arrays or UE mesh/CPU component pose to a sparse block shell.

    Import model files into UE first; textures overrides material-slot base colors.
    """
    from .adapters.mesh_input import mesh_structure as convert
    return convert(source, resolution=resolution, palette=palette, textures=textures,
                   up_axis=up_axis, alpha_cutoff=alpha_cutoff, name=name, max_cells=max_cells)


def uv_structure(source, boxes, *, scale=1, texture_size=None, palette=None,
                 alpha_cutoff=0.5, name='UVModel', max_cells=4_000_000):
    """Image and arbitrary transformed UV boxes to a sparse block shell."""
    from .adapters.mesh_input import uv_structure as convert
    return convert(source, boxes, scale=scale, texture_size=texture_size, palette=palette,
                   alpha_cutoff=alpha_cutoff, name=name, max_cells=max_cells)


def builder(size, *, origin=(0, 0, 0), max_cells=16_777_216):
    """Create a bounded MC XYZ/Y-up authoring grid, without Unreal."""
    return Builder(size, origin=origin, max_cells=max_cells)


def to_blocks(structure):
    """Convert native cells to Mineprep Blocks in UE; preserve coordinates and states."""
    from .adapters.building import to_blocks as convert
    return convert(structure)


def from_blocks(source, *, name=None, repair_trapdoors=False):
    """Import Blocks or a structure file (file parsing requires Mineprep/UE)."""
    from .adapters.building import from_blocks as convert
    return convert(source, name=name, repair_trapdoors=repair_trapdoors)


def compose(world, *placements, **budgets):
    """Add Structure.at(...) instances to a World, or None for a standalone scene."""
    from .core.scene import compose as combine
    return combine(world, *placements, **budgets)


def ground(world, placement):
    """Move a Placement vertically onto surface terrain, keeping X/Z and rotation."""
    from .core.grounding import ground as place_on_ground
    return place_on_ground(world, placement)


def foundation(world, *placements, block='stone', max_depth=16, max_cells=4_000_000, **states):
    """Return sparse world-coordinate footings, shared separately from model bodies."""
    from .core.grounding import foundation as build_foundation
    return build_foundation(world, *placements, block=block, max_depth=max_depth, max_cells=max_cells, **states)


def scatter(world, structures, *, region=None, spacing=16, density=1., biomes=None, where=None,
            avoid_water=True, rotations=(0,90,180,270), max_depth=0, existing=(),
            seed=None, salt='scatter', max_candidates=65_536, max_cells=4_000_000):
    """Return shared surface Placements and filtering stats, without changing the World."""
    from .core.scatter import scatter as distribute
    return distribute(world, structures, region=region, spacing=spacing, density=density,
                      biomes=biomes, where=where, avoid_water=avoid_water, rotations=rotations,
                      max_depth=max_depth, existing=existing, seed=seed, salt=salt,
                      max_candidates=max_candidates, max_cells=max_cells)


def palette(family='concrete'):
    """Native coloured block names and diagnostic sRGB; never changes materials."""
    from .core.building import COLORS
    from .adapters.block_colors import color_table
    if family not in ('concrete', 'wool', 'terracotta'):
        raise ValueError('palette family must be concrete, wool or terracotta')
    names = tuple(c+'_'+family for c in COLORS)
    return {n: '#'+''.join(f'{int(v):02X}' for v in rgb) for n, rgb in zip(names, color_table(names))}


def _with_mask(spec, path, region, kind):
    from .core.spec import MaskInput
    if not isinstance(spec, WorldSpec):
        raise TypeError('mask input requires a WorldSpec')
    region = spec.region if region is None else region if isinstance(region, Region) else Region(*region)
    return spec.replace(**{kind+'_mask': None if path is None else MaskInput(path, region)})


def with_vegetation_mask(spec, path, *, region=None):
    """White keeps existing density, black removes plants; None clears input."""
    return _with_mask(spec, path, region, 'vegetation')


def with_clearance_mask(spec, path, *, region=None):
    """White reserves complete vertical columns from generated scenery."""
    return _with_mask(spec, path, region, 'clearance')


def with_heightmap(spec, path, *, mode='faithful', region=None,
                   input_range=(0., 1.), output_range=None):
    """Attach fixed file mapping without reading pixels; None removes the input."""
    from .core.spec import HeightmapInput
    if not isinstance(spec, WorldSpec):
        raise TypeError('with_heightmap requires a WorldSpec')
    if path is None:
        return spec.replace(heightmap=None)
    region = spec.region if region is None else region if isinstance(region, Region) else Region(*region)
    return spec.replace(heightmap=HeightmapInput(path, region, mode, input_range, output_range))


def write_biome_texture(source, path, *, cell_size=4, vegetation_tints=None,
                       biome_color_mode='rgb', vegetation_hsv=None, biome_color_power=1.):
    """Export RGB multipliers or negative HSV adjustments as FP16 EXR."""
    from .adapters.biome_texture import write
    return write(source, path, cell_size=cell_size, vegetation_tints=vegetation_tints,
                 biome_color_mode=biome_color_mode, vegetation_hsv=vegetation_hsv,
                 biome_color_power=biome_color_power)


def biome_order(pack_id='vanilla', *, insert=(), before=None, after=None):
    """Return an explicit priority list; insert new IDs beside one existing anchor."""
    from .authoring import biome_order as order
    return order(pack_id, insert=insert, before=before, after=after)


def create_pack(pack_id, *, extends='vanilla', root=None, name=None):
    """Create and register an inherited pack; never overwrite an existing pack."""
    from .authoring import create_pack as create
    return create(pack_id, extends=extends, root=root, name=name)


def check(source, *, full=False, expect_biomes=(), expect_features=(), **options):
    """JSON-friendly regional diagnostics; reference-only unless full is requested."""
    if isinstance(source, (Structure, Scene)):
        from .core.scene import check_scene
        if expect_biomes or expect_features or full:
            raise ValueError('check the terrain World separately for biome/feature expectations')
        if isinstance(source, Structure):
            if not source.count:
                return dict(ok=True, scope='structure', cells=0, materials=0, errors=[])
            budgets = {k: options.pop(k) for k in ('max_cells', 'max_instances') if k in options}
            source = compose(None, source.at((0, 0, 0)), **budgets)
        return check_scene(source, **options)
    from .authoring import check as inspect
    return inspect(source, full=full, expect_biomes=expect_biomes,
                   expect_features=expect_features, **options)


def locate(source, *, biome=None, where=None, origin=None, **options):
    """Nearest matching reference column in source.region, or None in this region."""
    from .authoring import locate as find
    return find(source, biome=biome, where=where, origin=origin, **options)


def _field_names(names):
    return (names,) if isinstance(names, str) else names


def apply_preset(spec, preset_id, section=None):
    if ':' in preset_id:
        return preset_library(spec.pack).apply(spec,preset_id,section)
    from .core.presets import apply_preset as apply
    return apply(load_pack(spec.pack), spec, preset_id, section)


def preset_library(pack_id='vanilla'):
    from .preset_library import PresetLibrary
    return PresetLibrary(pack_id=pack_id)


def presets(pack_id='vanilla', section=None):
    return preset_library(pack_id).entries(section=section)


def reset_section(spec, section):
    from .core.presets import reset_section as reset
    return reset(load_pack(spec.pack), spec, section)


def preset_sections(pack_id='vanilla'):
    from .core.presets import preset_sections as sections
    return sections(load_pack(pack_id))


def projection(world, axis="y"):
    """Read-only actual carved-space projection; depth is distance from the near face.

    Observers look along +X/+Z or downward -Y. Maps have at most 512 pixels
    per axis; steps describe world-cell bin sizes. Overlap does not imply connectivity.
    Volume recipes project solid geometry instead of height-relative cavities.
    """
    from .core.projection import section as projected
    return projected(world, axis)


def plan_caves(spec):
    """Crop-independent dry layout; guides(region)/ravines(region) are immutable."""
    from .core.planning import Resources
    from .core.world import _GenerationInput
    request = _GenerationInput.capture(spec)
    pack = request.pack
    params = pack.resolve(spec)
    if not params.get('caves.enabled', False) or 'caves' not in (pack.planners or {}):
        return None
    resources = Resources(pack, params, spec.seed)
    resources.validate_region(spec.region)
    plan = resources.get('caves')
    return plan


def section(spec, axis="z", at=None, *, field="solid"):
    """Read-only solid/density slice in MC axes; continuous density needs a recipe."""
    from .core.geometry import section as sample_section
    return sample_section(spec, axis, at, field=field)


def fluid_surfaces(world):
    """Read-only world XYZ water surfaces and body indices; no sampling or UE calls.

    Pools have independent levels; connected bodies inherit their source level.
    Bodies carry stable IDs, optional source metadata and sparse half-open
    X,Z,Y0,Y1 wet runs, not water cube instances.
    """
    from .core.world import World
    from .core.fluids import empty
    if not isinstance(world,World):raise ValueError('fluid_surfaces requires a generated World')
    data=world.fluid_layers if world.fluid_layers is not None else empty()
    return dict(xyz=data.xyz,levels=data.levels,body_indices=data.body_indices,
                bodies=tuple(dict(id=b.id,level=b.level,runs=b.runs,
                    source=None if b.source is None else dict(kind=b.source.kind,id=b.source.id,level=b.source.level))
                    for b in data.bodies))


def plan_water(spec):
    """Read-only, crop-independent water plan; None when disabled or unsupported."""
    from .core.planning import Resources
    from .core.world import _GenerationInput
    request = _GenerationInput.capture(spec)
    p = request.pack
    if 'water' not in (p.planners or {}):
        return None
    plan = Resources(p, p.resolve(spec), spec.seed, region=spec.region).get('water')
    if plan is not None and hasattr(plan, 'validate_region'):
        plan.validate_region(spec.region)
    return plan


def edit(pack="vanilla", *, workspace=None):
    """Editable pure-data PackDraft; temporary previews and staged user-pack saves."""
    from .editing import PackDraft
    return PackDraft(pack, workspace=workspace)


def spec(pack="vanilla", preset="", *, seed=42, region=(0, 0, 256, 256), params=None):
    """Build and validate a WorldSpec against its pack (raises on unknown parameters)."""
    region = region if isinstance(region, Region) else Region(*region)
    result = WorldSpec(pack, preset, seed, region, tuple((params or {}).items()))
    load_pack(pack).resolve(result)
    return result


def generate(spec, *, execution="serial", workers=4, tile_size=256, keep_fields=None,
             cancel_event=None, progress=None, on_stage=None, on_phase=None, **budgets):
    """Pure generation; on_phase(name) and tile progress run in the calling thread."""
    return build_world(spec, execution=execution, workers=workers, tile_size=tile_size,
                       keep_fields=_field_names(keep_fields), cancel_event=cancel_event, progress=progress,
                       on_stage=on_stage, on_phase=on_phase, **budgets)


def overview(spec, **kwargs):
    """Offline exact reference maps; excludes features, caves, covers and output cells.

    Options: execution, workers, keep_fields, cancel_event, progress,
    max_cells. The returned Overview cannot be prepared or placed.
    """
    if 'keep_fields' in kwargs:
        kwargs['keep_fields'] = _field_names(kwargs['keep_fields'])
    return build_overview(spec, **kwargs)


def snapshot(world, path, **kwargs):
    """Write the contact sheet PNG (maps, section, stats); returns the path."""
    if isinstance(world, (Structure, Scene)):
        from .adapters.build_preview import snapshot as write
        return write(world, path, **kwargs)
    from .adapters.preview import contact_sheet
    return contact_sheet(world, path, **kwargs)


def fields(spec, names, region=None):
    """Evaluate named fields without surface or shell (debugging custom terrain)."""
    if region is not None and not isinstance(region, Region):
        if not isinstance(region, (list, tuple)) or len(region) != 4:
            raise TypeError('region must be a Region or (x0, z0, width, depth)')
        region = Region(*region)
    return sample_fields(spec, tuple(_field_names(names)), region)


def packs():
    return list_packs()


def catalog():
    return _catalog()


def pack(pack_id="vanilla"):
    return load_pack(pack_id)


def describe(pack_id="vanilla"):
    """Compact, JSON-friendly description of a pack for agents and UIs."""
    p = load_pack(pack_id)
    from .core.features import describe_feature
    from .core.heightmap import supported
    return {"id": p.id, "name": p.name, "chain": list(p.chain), "fingerprint": p.fingerprint[:8],
            "presets": {k: v.name for k, v in p.presets.items()}, "default_preset": p.default_preset,
            "preset_sections": preset_sections(pack_id),
            "local_presets": {k: v.section for k, v in p.presets.items() if v.section is not None},
            "biomes": [{"id": b.id, "name": b.name, "fallback": b.fallback,
                        "vegetation_tint": list(b.vegetation_tint),
                        "vegetation_hsv": list(b.vegetation_hsv),
                        "climate": [{n: [lo, hi] for n, lo, hi in box} for box in b.climate],
                        "features": b.features}
                       for b in p.biomes],
            "fields": {k: {"deps": f.deps, "res": f.res, "halo": f.halo, "resources": f.resources, "doc": f.doc,
                           **({"region_pass": True, "margin": f.margin,
                               "region": f.region.to_list() if f.region is not None else None,
                               "outside": f.outside} if f.region_pass else {})}
                       for k, f in p.fields.items()},
            "height_field": p.height_field,
            "heightmap": {"formats": ['png', 'exr'], "modes": ['faithful', 'add'],
                          "supported": supported(p)},
            "mask_categories": dict(p.mask_categories or {}),
            "inactive_biomes": list(p.inactive_biomes),
            "planners": list(p.planners or {}),
            "planner_gates": dict(p.planner_gates or {}),
            "ui_sections": [dict(id=s.id,label=s.label,pages=s.pages,controls=s.controls,
                                 shared_group=s.shared_group,editor=s.editor,
                                 groups=[g.__dict__ for g in s.groups]) for s in p.ui_sections],
            "surface_processors": [dict(id=s.id,function=s.function,blocks=s.blocks,radius=s.radius,
                                        enabled_param=s.enabled_param,sky_only=s.sky_only,category=s.category,volume=s.volume) for s in p.surface_processors],
            "soil_depth_field": p.soil_depth_field,
            "reference_mask_field": p.reference_mask_field,
            "terrain_materials": (dict(inputs=p.terrain_materials.inputs,blocks=p.terrain_materials.blocks,
                                       fields=p.terrain_materials.fields,enabled_param=p.terrain_materials.enabled_param)
                                  if p.terrain_materials is not None else None),
            "capabilities": dict(reference=True,overview=True,biome_selector=True,per_column_soil_depth=True,terrain_materials=True,
                                 upward_entities=p.density is None or p.density.base == 'height',
                                 water_surfaces=True,water_surface_features=p.density is None or p.density.base=='height',
                                 column_features=p.density is None or p.density.base=='height',
                                 template_models=True,
                                 template_surface_edits=False,
                                 volume_decoration=p.density is not None and p.density.base=='volume',
                                 structure_authoring=True,scene_composition=True,
                                 image_import=True),
            "planning_params": {name: list(keys) for name, keys in (p.planning_params or {}).items()},
            "density": (dict(field=p.density.field, base=p.density.base, enabled_param=p.density.enabled_param,
                             bounds=p.density.bounds is not None,wet_protection=p.density.wet_protection)
                        if p.density is not None else None),
            "shell_materials": (dict(blocks=list(p.shell_materials.blocks),enabled_param=p.shell_materials.enabled_param)
                                if p.shell_materials is not None else None),
            "fluids": (dict(block=p.fluids.block,enabled_param=p.fluids.enabled_param,requires=p.fluids.requires)
                       if p.fluids is not None else None),
            "densities": {k: dict(deps=f.deps, res=f.res, axes=f.axes, resources=f.resources) for k, f in (p.densities or {}).items()},
            "ui_rows": [{"label": r.label, "keys": r.keys, "components": r.components} for r in p.ui_rows],
            "params": {k: {"type": d.type, "default": d.default, "min": d.min, "max": d.max,
                           "label": d.label, "tooltip": d.tooltip, "advanced": d.advanced,
                           "page": d.page, "enabled_param": d.enabled_param} for k, d in p.params.items()},
            "blocks": list(p.blocks), "block_defs": {k: b.describe() for k, b in p.block_defs.items()},
            "water": p.water, "features": [describe_feature(f) for f in p.feature_defs]}


def prepare(spec, *, name='World', type_group_count=1, block_materials=None,
            biome_color_mode='rgb', vegetation_hsv=None, biome_color_power=1., **kwargs):
    """Prepare output; material overlays are independent of BCT colour power.

    Optional max_preprocess_cells bounds width*depth*output height at entrance;
    max_output_instances bounds final merged instances before texture writes.
    Existing max_cells/max_instances still bound columns/raw generation output.
    """
    if isinstance(spec, Structure):
        budgets = {k: kwargs[k] for k in ('max_cells', 'max_instances') if k in kwargs}
        spec = compose(None, spec.at((0, 0, 0)), **budgets)
    if isinstance(spec, Scene) and spec.terrain is None:
        kwargs.setdefault('biome_texture', False)
    from . import ops
    return ops.prepare_world(spec, name=name, type_group_count=type_group_count,
                             block_materials=block_materials, biome_color_mode=biome_color_mode,
                             vegetation_hsv=vegetation_hsv, biome_color_power=biome_color_power, **kwargs)


def place(prepared, **kwargs):
    from . import ops
    return ops.place_world(prepared, **kwargs)


def preview(spec, **kwargs):
    from . import ops
    return ops.preview_world(spec, **kwargs)
