# Pitfalls — VAT Tools

Only for `mods/VAT_Tools/` (bake, AnimSeq slots, copy DA). Do not apply these asset-path / DA conventions to unrelated mods.

Layout / PropertyGroup / hide: [../ui.md](../ui.md) + [ui.md](ui.md). `force_update` on **source** tex: [common.md](common.md). `merge_skm` dest-exists behavior is different — [mesh.md](mesh.md).

## Bake flow

1. Temp cache DA: **one** AnimSequence per bake (do not stuff multi-clip into cache DA).
2. Premul materials sample the generated AnimToTexture cache textures; the bake
   implementation refreshes their GPU resource first.
3. Optional: delete `.../cache` after success when “auto clean cache” is on.

| Symptom | Cause | Fix |
|---------|--------|-----|
| First bake → premul / RT sample **all black**; second run OK | Generated cache Source updated but GPU resource not ready | Check the refresh before sampling in `bake_anim_ops._premul_to_directory`; source Texture2D only |
| Imported texture or painted RT is black | Different resource lifecycle | Follow [Textures / RT](common.md#textures--rt); do not apply the bake-cache refresh indiscriminately |

Paint / sketch RTs: [ui.md](ui.md) — not this bake path.

## Anim / data asset sync

| Symptom | Cause | Fix |
|---------|--------|-----|
| Panel AnimSeq stale after switching DA | No change handler | On `DataAsset` change, read `anim_sequences` → pad to ≥3 → assign list |
| Empty AnimSeq index still has VAT textures | Bake only wrote non-empty slots | On bake, clear TextureCollection group (`index*3 .. index*3+2`) when slot empty |
| Index vs list confusion | Separate Index field | Prefer `list[AnimSequence]`; use enumerate index as group id |
| TargetPath / NewName not refreshed after `assign_soft_prop` | Soft write may skip Details callback | Call sync helpers; TargetPath = `/Game/mc/VAT/{strippedName}` |

## Asset duplication (copy DA)

This is `mods/VAT_Tools/copy_ops.py` (`_duplicate_or_use`). **Not** `merge_skm` (that one skips when dest exists and `overwrite=False`).

| Rule | Detail |
|------|--------|
| Dest exists | Load + reuse, then continue rewire — **do not abort** |
| Path | Auto: `/Game/mc/VAT/{name}` (name = strip `DA_VAT_`); must stay under `/Game` |
| Name prefix | Strip `DA_VAT_` only when present; use `asset.get_name()` not display name |
| CopyDeps False | `duplicate_asset` DA only; keep SM / mats / TC / AnimSeq refs |
| CopyDeps True | Copy textures **from the anim texture collection only** (`动画纹理集合`, not MIC texture params) → TCs (rewire slots) → materials (rewire TC params; keep original mat textures) → SM → DA. Keep SKM + AnimSequences shared |
| TC on MC_VAT | `TextureCollectionParameterValue` with `parameter_info.name` + `parameter_value` |
| Remap keys | Dict keyed by **original** UObject identity (`tex in remap`) |

```python
existing = load_or_none(directory, name)
if existing:
    return existing  # reuse
return asset_tools().duplicate_asset(name, directory, original)
```
