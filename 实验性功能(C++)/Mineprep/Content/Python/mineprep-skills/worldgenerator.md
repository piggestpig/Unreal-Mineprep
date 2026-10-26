# Terrain and composed block scenes

Use WorldGenerator for terrain, biomes, vegetation, scripted buildings and
composing block models with generated terrain:

```python
from mods.WorldGenerator import api
```

Read its [agent guide](../mods/WorldGenerator/docs/AGENT_GUIDE.md) for builder
methods, `ground` / `foundation` / `scatter` parameters, collision checks and
complete recipes.

## Core workflow

1. **Discover**: `api.catalog()` for packs; `api.describe()` for parameters and presets.
2. **Terrain**: `api.spec(...)` → `api.generate(spec)` → `api.check(world)` / `api.snapshot(world)`.
3. **Buildings / sculptures**: `api.builder(size)` → batch shapes and native blockstates → `.freeze(name)`.
4. **Compose & ground**: `api.compose(world, structure.at(position, rotation=90))` (pass `None` for a standalone scene). Use `api.ground`, `api.foundation`, and `api.scatter` to place and support structures on terrain; see the agent guide for options.
5. **Place in UE** (when requested): `api.prepare(scene, on_done=...)` → wait for the Job to complete (via callback or separate status queries, never busy-wait) → `api.place(job.result)`.

## Key boundaries

- **Coordinates**: all generation data, packs and builders use MC blocks (Y up); the UE scene and panel use UE axes (Z up, cm). Horizontal axes map MC `(X, Z)` ↔ UE `(X, Y)` via `api.to_ue` / `api.from_ue`.
- **Previews**: offline snapshots are cell-color diagnostics, not UE renders.
- **Standalone NBT / `Blocks`**: existing `.nbt` / `.schem` imports and `mineprep.Blocks` continue to use the [structure workflow](structure.md).
