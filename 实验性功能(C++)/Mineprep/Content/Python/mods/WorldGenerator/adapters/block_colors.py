"""Top-face preview colours from the MC resource pack; no Unreal dependency.

Read the resource-pack root from Settings.default_resource_pack, with the legacy
installer location used when that setting is absent. WG_MC_ASSETS overrides
the assets/minecraft folder. Missing assets fall back to a fixed table.
"""

from functools import lru_cache
import json
import os
from pathlib import Path

import numpy as np

PROJECT_DIR = Path(__file__).resolve().parents[7]
TINTS = {"grass_block": (145, 189, 89), "oak_leaves": (119, 171, 47), "birch_leaves": (128, 167, 85),
         "spruce_leaves": (97, 153, 97), "jungle_leaves": (48, 187, 11), "vine": (119, 171, 47),
         "short_grass": (145, 189, 89), "fern": (145, 189, 89), "water": (63, 118, 228)}
FALLBACK = {"grass_block": (91, 145, 67), "dirt": (134, 96, 67), "stone": (125, 125, 125),
            "sand": (219, 207, 163), "sandstone": (216, 203, 155), "snow_block": (249, 254, 254),
            "gravel": (131, 127, 126), "andesite": (136, 136, 137), "water": (63, 118, 228)}


def assets_dir():
    override = os.environ.get("WG_MC_ASSETS")
    if override:
        return Path(override) if Path(override).is_dir() else None
    config = PROJECT_DIR / "Content" / "Mineprep" / "Mineprep_config.txt"
    try:
        settings = json.loads(config.read_text(encoding="utf-8"))["Settings"]
        pack = settings.get("default_resource_pack") or str(Path(settings["installer_dir"]) / "Blender扩展资源" / "mc_default")
    except (OSError, ValueError, KeyError, TypeError):
        return None
    path = Path(pack) / "assets" / "minecraft"
    return path if path.is_dir() else None


def _texture_color(path):
    import cv2
    pixels = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_UNCHANGED)
    if pixels is None:
        return None
    pixels = pixels[:16] if pixels.shape[0] > pixels.shape[1] else pixels  # animated strips
    if pixels.ndim == 2:
        pixels = np.repeat(pixels[..., None], 3, axis=2)
    rgb = pixels[..., :3][..., ::-1].reshape(-1, 3).astype(np.float64)
    if pixels.shape[-1] == 4:
        alpha = pixels[..., 3].reshape(-1) > 0
        rgb = rgb[alpha] if alpha.any() else rgb
    return rgb.mean(axis=0)


def block_color(name, definition=None):
    """(r, g, b) uint8 average of the block's top texture, tinted like the game."""
    from ..core.blocks import BlockDef
    from .resources import resolve_resource, default_models_dir
    block = definition or BlockDef(name, 'builtin', name)
    if block.color is not None:
        return block.color
    if block.source == 'mesh':
        return FALLBACK.get(name, (200, 0, 200))
    try:
        resource = resolve_resource(block, default_models_dir())
    except ValueError:
        if block.source == 'json':
            raise
        return FALLBACK.get(name, (200, 0, 200))
    return _resource_color(block.id, block.value, resource.fingerprint, resource.textures)


@lru_cache(maxsize=512)
def _resource_color(name, source, fingerprint, textures):
    refs = dict(textures)
    path = next((refs[k] for k in ('top', 'up', 'end', 'all', 'particle', 'cross') if k in refs), None)
    color = _texture_color(path) if path else None
    if color is None:
        return FALLBACK.get(name, (200, 0, 200))
    tint_name = source if source in TINTS else name
    if tint_name in TINTS:
        color = color * np.array(TINTS[tint_name]) / 255.0
    return tuple(int(round(c)) for c in np.clip(color, 0, 255))


def color_table(names, definitions=None):
    return np.array([block_color(n, definitions.get(n) if definitions else None) for n in names], np.uint8).reshape(-1, 3)
