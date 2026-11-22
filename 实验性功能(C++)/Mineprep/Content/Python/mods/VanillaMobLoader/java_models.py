"""Match installed Java models to exact CEM catalog entries."""

import json
from pathlib import Path


HUMANOIDS = frozenset({
    'bogged.glb', 'copper_golem.glb', 'drowned.glb', 'drowned_baby.glb', 'enderman.glb',
    'evoker.glb', 'husk.glb', 'husk_baby.glb', 'illusioner.glb', 'iron_golem.glb',
    'parched.glb', 'piglin.glb', 'piglin_baby.glb', 'piglin_brute.glb',
    'pillager.glb', 'player.glb', 'player_slim.glb', 'skeleton.glb', 'stray.glb',
    'villager.glb', 'villager_baby.glb', 'vindicator.glb', 'wandering_trader.glb',
    'witch.glb', 'wither_skeleton.glb', 'zombie.glb', 'zombie_baby.glb',
    'zombie_villager.glb', 'zombie_villager_baby.glb',
    'zombified_piglin.glb', 'zombified_piglin_baby.glb',
})

QUADRUPEDS = frozenset({
    'armadillo.glb', 'armadillo_baby.glb', 'camel.glb', 'camel_baby.glb',
    'cat.glb', 'cat_baby.glb', 'cow.glb', 'cow_baby.glb',
    'fox.glb', 'fox_baby.glb', 'goat.glb', 'goat_baby.glb',
    'hoglin.glb', 'hoglin_baby.glb', 'horse.glb', 'horse_baby.glb',
    'llama.glb', 'llama_baby.glb', 'mooshroom.glb', 'mooshroom_baby.glb',
    'ocelot.glb', 'ocelot_baby.glb', 'panda.glb', 'panda_baby.glb',
    'pig.glb', 'pig_baby.glb', 'polar_bear.glb', 'polar_bear_baby.glb',
    'ravager.glb', 'sheep.glb', 'sheep_baby.glb',
    'turtle.glb', 'turtle_baby.glb', 'wolf.glb', 'wolf_baby.glb',
    'zoglin.glb', 'zoglin_baby.glb',
})


def edit_profile(filename):
    """Return the editing rig profile name for a Java GLB filename, or None."""
    if filename in HUMANOIDS:
        return 'biped'
    if filename in QUADRUPEDS:
        return 'quadruped_edit'
    return None


def find(entries, root, prefer_java):
    if not prefer_java or not root or len(entries) != 1:
        return None
    manifest = json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf-8'))
    filename = manifest['models'].get(entries[0].key)
    if filename is None:
        return None
    path = Path(root) / filename
    try:
        if path.is_absolute() and path.is_file():
            return path, manifest['version']
    except OSError:
        return None


def face_spec_for(path: Path):
    """Return the configured facial template (refined against embedded PNG) for a Java GLB, or None."""
    from mineprep.face import get_face_spec
    from mineprep.model import embedded_base_color_surfaces

    raw = path.read_bytes()
    surfs = embedded_base_color_surfaces(raw)
    primary_png = bytes(next(iter(surfs.values()))[0]) if surfs else None
    return get_face_spec(path.stem, primary_png)


def import_source(path, cache, profile=None, *, face_mode='none', face_spec=None, face_options=None):
    """Keep the imported GLB version available for reimport and later splitting."""
    from mineprep.face import normalize_face_mode, upgrade_face_glb
    from mineprep.model import cache_model_source, humanoid_edit_glb, quadruped_edit_glb

    face_mode = normalize_face_mode(face_mode)
    builders = {
        'biped': ('humanoid_edit', humanoid_edit_glb),
        'quadruped_edit': ('quadruped_edit', quadruped_edit_glb),
    }
    try:
        data = path.read_bytes()
        folder = 'java'
        if profile is not None:
            if profile not in builders:
                raise ValueError(f'Unknown edit rig profile: {profile}')
            folder, build = builders[profile]
            data = build(data)
        if face_mode != 'none' and face_spec is not None:
            data = upgrade_face_glb(data, face_spec, mode=face_mode, options=face_options)
            folder = f'{folder}_face_{face_mode}'
        directory = Path(cache).resolve() / 'resources' / 'generated' / folder
        return cache_model_source(directory, path.name, data)
    except Exception as exc:
        raise ValueError(f'{path}: {exc}') from exc


def split_source(path, cache, *, face_mode='none', face_spec=None, face_options=None):
    from mineprep.face import normalize_face_mode, upgrade_face_glb
    from mineprep.model import cache_model_source
    from .gltf import split_head

    face_mode = normalize_face_mode(face_mode)
    parts = split_head(path.read_bytes())
    folder = 'head_split'
    if face_mode != 'none' and face_spec is not None:
        parts['head'] = upgrade_face_glb(parts['head'], face_spec, mode=face_mode, options=face_options)
        folder = f'head_split_face_{face_mode}'
    directory = Path(cache) / 'resources' / 'generated' / folder
    return {part: cache_model_source(directory, path.stem + '_' + part + '.glb', data)
            for part, data in parts.items()}
