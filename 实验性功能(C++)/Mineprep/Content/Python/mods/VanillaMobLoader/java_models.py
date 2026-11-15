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


def import_source(path, cache, profile=None):
    """Keep the imported GLB version available for reimport and later splitting."""
    from mc_model import cache_model_source, humanoid_edit_glb, quadruped_edit_glb

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
        directory = Path(cache).resolve() / 'resources' / 'generated' / folder
        return cache_model_source(directory, path.name, data)
    except Exception as exc:
        raise ValueError(f'{path}: {exc}') from exc


def split_source(path, cache):
    from mc_model import cache_model_source
    from .gltf import split_head

    parts = split_head(path.read_bytes())
    directory = Path(cache) / 'resources' / 'generated' / 'head_split'
    return {part: cache_model_source(directory, path.stem + '_' + part + '.glb', data)
            for part, data in parts.items()}
