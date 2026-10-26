"""Pure file dependency snapshots for JSON imports and preview colours (no Unreal)."""
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
from mc_math import MODEL_FRAME

RESOURCE_VERSION = 'block-sources-2:' + MODEL_FRAME
SPECIAL_PARENTS = ('builtin/generated', 'item/generated', 'builtin/entity')


class ResourceChangedError(RuntimeError):
    def __init__(self):
        super().__init__('方块资源已变化，请重新准备资源')


def assets_root(path):
    for parent in path.parents:
        if parent.name == 'assets':
            return parent
    raise ValueError(f'JSON references need an assets/<namespace> hierarchy: {path}')


def reference(path, ref, category, suffix, fallback=None):
    if ref.startswith('.'):
        result = path.parent / ref
    else:
        namespace, sep, value = ref.partition(':')
        namespace, value = (namespace, value) if sep else ('minecraft', namespace)
        try:
            local = assets_root(path)
        except ValueError:
            if fallback is None:
                raise
            local = fallback
        result = local / namespace / category / value
        candidate = result if result.suffix else result.with_suffix(suffix)
        if not candidate.is_file() and fallback is not None:
            result = fallback / namespace / category / value
    return (result if result.suffix else result.with_suffix(suffix)).resolve()


def model_data(path, dependencies=None, stack=(), fallback=None):
    """Mirror Mineprep parent/texture references, preserving inherited relative texture semantics."""
    path = Path(path).resolve()
    if path in stack:
        raise ValueError(f'model parent cycle: {path}')
    raw_bytes = path.read_bytes()
    if dependencies is not None:
        dependencies[path] = raw_bytes
    raw = json.loads(raw_bytes.decode('utf-8-sig'))
    textures, elements = {}, None
    parent = raw.get('parent')
    if parent and parent not in SPECIAL_PARENTS:
        textures, elements = model_data(reference(path, parent, 'models', '.json', fallback),
                                        dependencies, (*stack, path), fallback)
    textures = {**textures, **raw.get('textures', {})}
    return textures, raw.get('elements', elements)


def texture_ref(textures, key):
    ref = textures[key]
    seen = set()
    while True:
        ref = ref.get('sprite') if isinstance(ref, dict) else ref
        if not isinstance(ref, str):
            raise ValueError(f'invalid texture reference {key}')
        if not ref.startswith('#'):
            return ref
        key = ref[1:]
        if key in seen:
            raise ValueError(f'texture reference cycle: {key}')
        seen.add(key)
        ref = textures[key]


def _full_cube(elements):
    return any(e.get('from') == [0, 0, 0] and e.get('to') == [16, 16, 16]
               and not e.get('rotation') and {'up', 'down', 'north', 'south', 'east', 'west'} <= e.get('faces', {}).keys()
               for e in (elements or ()))


def connection_full_cube(models_dir=None):
    """Per-operation geometry facts for shared rules; no texture reads or UE imports."""
    directory = Path(models_dir or default_models_dir())
    fallback = next((p for p in directory.parents if p.name == 'assets'), None)
    models = {}

    def full(name, properties):
        if name == 'snow':
            if int(properties.get('layers', 1)) < 8:
                return False
            name = 'snow_block'
        if name not in models:
            path = directory / (name + '.json')
            models[name] = _full_cube(model_data(path, fallback=fallback)[1]) if path.is_file() else False
        return models[name]
    return full


def lava_textures(path, textures, fallback):
    """Match import_block's level-zero lava: particle still, default flow, sibling fallback."""
    try:
        ref = texture_ref(textures, 'particle')
        relative = ref.startswith('.')
        # Mirror the public fluid importer's texture-path normalization, without
        # importing its Unreal module or changing ordinary model dependencies.
        ref = ref.replace('\\', '/').replace('/./', '/')
        if ref.startswith('./'):
            ref = ref[2:]
        if ref.lower().endswith('.png'):
            ref = ref[:-4]
        ref = '/'.join(part for part in ref.split('/') if part and part != '..')
        if ref.startswith('textures/'):
            ref = ref[9:]
        still = reference(path, './'+ref if relative else ref, 'textures', '.png', fallback)
    except (ValueError, KeyError, TypeError):
        still = reference(path, 'block/lava_still', 'textures', '.png', fallback)
    if not still.is_file():
        raise ValueError(f'missing lava still texture: {still}')
    flow = reference(path, 'block/lava_flow', 'textures', '.png', fallback)
    if not flow.is_file():
        sibling = still.with_name(still.stem.replace('_still', '_flow') + still.suffix)
        flow = sibling if sibling.is_file() else still
    return (('still', still), ('flow', flow))


@dataclass(frozen=True)
class Resource:
    block: object
    path: str
    fingerprint: str
    textures: tuple = ()  # (texture key, absolute PNG)
    full_cube: bool = False


def resolve_resource(block, models_dir):
    if block.material:
        base = resolve_resource(replace(block, material=()), models_dir)
        digest = hashlib.sha256(('block-material-1:' + base.fingerprint + ':' +
                                 json.dumps(dict(block.material), sort_keys=True)).encode()).hexdigest()
        return replace(base, block=block, fingerprint=digest)
    if block.source == 'mesh':
        digest = hashlib.sha256((RESOURCE_VERSION + block.value).encode()).hexdigest()
        return Resource(block, block.value, digest)
    path = (Path(block.value) if block.source == 'json' else Path(models_dir) / (block.value + '.json')).resolve()
    try:
        deps = {}
        fallback = next((p for p in (Path(models_dir), *Path(models_dir).parents) if p.name == 'assets'), None)
        textures, elements = model_data(path, deps, fallback=fallback)
        # Only this builtin ID is imported as a full dynamic fluid cube. An
        # alias asset_name takes the public importer's ordinary model path.
        fluid = block.source == 'builtin' and block.id == block.value == 'lava' and not elements
        selected = (lava_textures(path, textures, fallback) if fluid else
                    ((key, reference(path, texture_ref(textures, key), 'textures', '.png', fallback))
                     for key in textures))
        files = []
        for key, file in selected:
            deps[file] = file.read_bytes()
            meta = file.with_suffix('.png.mcmeta')
            if meta.is_file():
                deps[meta] = meta.read_bytes()
            files.append((key, str(file)))
        full = fluid or _full_cube(elements)
        if block.occludes and (not full or any(s in block.value for s in ('glass', 'leaves')) or block.value in ('ice', 'water', 'air')):
            raise ValueError('height-shell output requires an opaque full cube')
        digest = hashlib.sha256(RESOURCE_VERSION.encode())
        if fluid:
            digest.update(b'\0lava-fluid-level-0-1\0')
        for file, content in sorted(deps.items()):
            digest.update(str(file).encode() + b'\0' + content + b'\0')
        return Resource(block, str(path), digest.hexdigest(), tuple(files), full)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f'block {block.id} source {block.source}:{path}: {exc}') from exc


def default_models_dir():
    from .block_colors import assets_dir
    root = assets_dir()
    return root / 'models/block' if root else Path('__missing_mc_models__')


@dataclass(frozen=True)
class ResourceSnapshot:
    resources: tuple
    models_dir: str
    fingerprint: str
    materials: tuple = ()

    @classmethod
    def capture(cls, pack, models_dir=None, *, block_materials=None, used_blocks=None):
        from ..core.blocks import material_values
        if block_materials is not None and (not isinstance(block_materials, dict)
                or set(block_materials) - set(pack.blocks)):
            raise ValueError('block_materials: unknown block IDs or invalid mapping')
        definitions = dict(pack.block_defs)
        for name, raw in (block_materials or {}).items():
            values = dict(definitions[name].material)
            for key, value in material_values(raw, allow_none=True).items():
                if value is None:
                    values.pop(key, None)
                else:
                    values[key] = value
            definitions[name] = replace(definitions[name], material=tuple(sorted(values.items())))
        directory = str(Path(models_dir or default_models_dir()).resolve())
        names = pack.blocks if used_blocks is None else tuple(used_blocks)
        if set(names)-set(pack.blocks):
            raise ValueError('resource snapshot: unknown used block IDs')
        resources = tuple(resolve_resource(definitions[n], directory) for n in names)
        raw = ':'.join(f'{r.block.id}:{r.fingerprint}' for r in resources)
        materials = tuple((n, definitions[n].material) for n in pack.blocks if definitions[n].material)
        return cls(resources, directory, hashlib.sha256(raw.encode()).hexdigest(), materials)

    def checked(self):
        try:
            for old in self.resources:
                if resolve_resource(old.block, self.models_dir).fingerprint != old.fingerprint:
                    raise ResourceChangedError()
        except (OSError, ValueError) as exc:
            raise ResourceChangedError() from exc

    def get(self, name):
        return next(r for r in self.resources if r.block.id == name)


@dataclass(frozen=True)
class TemplateResource:
    template: object
    fingerprint: str
    sources: tuple
    models_dir: str
    dependencies: tuple
    materials: tuple = ()  # per logical template cell, empty preserves old bake identity

    def checked(self):
        try:
            if any(hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h for p,h in self.dependencies):
                raise ResourceChangedError()
            for old in self.sources:
                if resolve_resource(old.block,self.models_dir).fingerprint!=old.fingerprint:
                    raise ResourceChangedError()
        except (OSError, ValueError) as exc:
            raise ResourceChangedError() from exc


def template_texture_key(path):
    """Shared import identity excludes tree geometry, but includes import policy and animation."""
    path = Path(path).resolve()
    digest = hashlib.sha256(b'wg-template-texture-1\0' + str(path).encode())
    digest.update(path.read_bytes())
    meta = path.with_suffix('.png.mcmeta')
    if meta.is_file():
        digest.update(b'\0mcmeta\0' + meta.read_bytes())
    return digest.hexdigest()


def capture_templates(instances, models_dir, parts, bake_version, *, block_names=(), block_materials=None):
    """Freeze only used recipes; block-state expansion is supplied by the editor adapter."""
    from ..core.blocks import BlockDef
    from ..core.templates import definitions
    templates=definitions(instances);result={}
    for name,t in sorted(templates.items()):
        models=set();dependencies={}
        for _,_,_,block,props in t.bake_cells:
            models.update(model for model,*_ in parts(block,dict(props)))
            states=Path(models_dir).parent.parent/'blockstates'/(block+'.json')
            if states.is_file():dependencies[str(states)]=hashlib.sha256(states.read_bytes()).hexdigest()
        sources=tuple(resolve_resource(BlockDef('template_source_'+str(i),'builtin',model,
                            shape='decor',occludes=False,merge='none'),models_dir)
                      for i,model in enumerate(sorted(models)))
        recipe=(bake_version,'same',True,t.id,t.bake_cells,t.types.tolist(),t.boxes.tolist(),
                [(r.path,r.fingerprint) for r in sources],sorted(dependencies.items()))
        if not t.two_sided:
            recipe += (('two-sided-1',False),)
        materials = tuple(tuple(sorted((block_materials or {}).get(block_names[int(i)], {}).items()))
                          for i in t.types) if block_names else ()
        if any(materials):
            recipe += (('block-material-1',materials),)
        else:
            materials = ()
        fingerprint=hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest()
        result[name]=TemplateResource(t,fingerprint,sources,str(models_dir),tuple(sorted(dependencies.items())),materials)
    return result
