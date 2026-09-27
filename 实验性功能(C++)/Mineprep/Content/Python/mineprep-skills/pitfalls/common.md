# Pitfalls (common)

Failures that show up across tasks. Prefer these fixes before inventing new plumbing.

Module-specific references (read the relevant topic):

| File | When |
|------|------|
| [ui.md](ui.md) | Layout, PropertyGroup, UMG Geometry, paint RT |
| [structure.md](structure.md) | spawn helpers, stairs/fence/roof, MC↔UE axes |
| [anim.md](anim.md) | Control Rig, AnimSequence bone tracks |
| [mesh.md](mesh.md) | `merge_skm`, Geometry Script |
| [vat.md](vat.md) | VAT Tools bake / DA copy |
| [../remote.md](../remote.md) | RE Unicode, screenshots, panel DebugMode |
| [../parallel.md](../parallel.md) | `delay` / `tick` / `asynctask` / `thread` / `asyncthread` / `until` |

## Reload / class identity

| Symptom | Cause | Fix |
|---------|--------|-----|
| `KeyError` / wrong Layout after edit | `importlib.reload` duplicated `Layout`/`PropertyGroup` | `mineprep.reload()` (in-place; do not `importlib.reload`) |
| A separately imported function stays old after reload | `from mineprep import screenshot` keeps its own binding | Re-import `screenshot`, or use `mineprep.screenshot`; assigning the module return value does not refresh the function binding |
| MCP `run` still calls old `mc_structure` after `reload()` | Shared snippet namespace kept the pre-reload module; another agent in this editor sees it too | `import mc_structure` again in that snippet, or call `mineprep.*`. [../remote.md](../remote.md) |
| Panel shows old fields / ops use old names | Registration alone does not reload code; open panels retain objects | Full `mineprep.reload()` clears reloadable Mod submodules; reopen the panel. Other lifecycles: [../mods.md](../mods.md) |
| Props attrs empty in ops | Read class attrs or passed class not instance | Instantiate `Props()` in the UI; pass its values to core operations. [Callable operations](../mods.md#callable-operations) |
| Re-import JSON but mesh unchanged | `import_block` skips existing asset | `reload=True` when the source changed; no asset deletion is needed |
| `unreal.mineprep.panel` missing | C++ BFL ≠ Python module | `import mineprep` then `mineprep.panel`; experimental C++: [../cpp.md](../cpp.md) |
| `spawn_mob` logs `不存在` after `reload()`; actor still appears; `loc=` ignored | Blueprint wrote `mineprep.ActorCache`; handshake is `mcvars.ActorCache` | Assign `mcvars.ActorCache` (and spawn name/id caches). Restart also works until the next reload. [../api.md](../api.md) § Spawn |

## Instantiation / redraw

| Symptom | Cause | Fix |
|---------|--------|-----|
| Details empty / errors | `layout.prop(MyProps)` class | `layout.prop(MyProps())` |
| `super().__init__` then create props | `draw()` already ran | Instantiate PGs **before** `super().__init__` |
| Infinite panel rebuild | `redraw()` inside `draw()` | Never; use `Layout.hide` / partial updates |

SoftObjectPath, named `prop` arrays, fill, hide-column, `save`/`load` (`/Game` strings vs assets): [ui.md](ui.md) / [../ui.md](../ui.md).

## Rotator

A user-supplied triple is **roll, pitch, yaw**, the same order as the details panel (横滚, 俯仰, 偏转) and as `Rotator` positional arguments. Write keywords: `(0, -11, -30)` → `Rotator(roll=0, pitch=-11, yaw=-30)`.

`unreal.Rotator(0, 90, 0)` is therefore Pitch 90 (fence rails stand vertical), not Yaw 90.

Level Sequence transform channels store the same order: `Rotation.X` roll, `Rotation.Y` pitch, `Rotation.Z` yaw.

MC structure facing / uvlock / roofs: [structure.md](structure.md). Character Control Rig axes: [anim.md](anim.md).

## Generator panel errors

For missing widget caches, unknown mob names or uncertain spawn outcomes, follow
[placement recovery](../api.md#recover-a-failed-placement). Use `spawn_structure`
for supplied structure files or composed cells; see [structure.md](../structure.md).

## Textures / RT

| Symptom | Cause | Fix |
|---------|--------|-----|
| First sample / bake **all black**; second run OK | CPU/Source updated; GPU Resource not ready | `unreal.LandmassBlueprintFunctionLibrary.force_update_texture(tex)` on the **source Texture2D** before `set_texture_parameter_value` / `draw_material_to_render_target` |
| Canvas RT goes **white / empty** after load, save, or `force_update` | `force_update_texture(rt)` → `UpdateResource()` rebuilds GPU from **clear color** | Never `force_update` a **painted** canvas RT. Only after **create / resize**, and **before** blit or paint |
| Exported PNG / saved skin **much darker** than the paint view | `RTF_RGBA8` is linear; PNG writer dumps U8 bytes | `RTF_RGBA8_SRGB`. Do **not** also set `target_gamma=2.2` on an sRGB RT |

`mc_prep.prep_texture` already force-updates. Paint coverage / `draw_line`: [../ui.md](../ui.md) § Sketch RT + [ui.md](ui.md). VAT bake DA: [vat.md](vat.md).

## warn

```python
mineprep.warn(f'导入方块失败: {source}', exc)  # Exception → full traceback
```

Pass the exception object, not only `str(exc)`.

## Threads / tickers

Full decorator rules: [../parallel.md](../parallel.md).

| Symptom | Cause | Fix |
|---------|--------|-----|
| Editor hang / `@thread` callback never runs | `register_ticker_callback(delay=0)` busy-loop holds the GIL so the worker cannot `set_result` | Use the provided `@thread` (Slate poll) or `@asynctask`; never ticker `delay=0` returning `True` to wait on a `Future` |
| `accessed from a thread that is not the game thread` | `unreal.*` / `prints` inside `@thread` / `@asyncthread` | Stdlib / numpy only in the worker; UE work in `callback` or `@asynctask` |
| `@asyncthread` function never runs | Wrapper is a generator; `work()` alone does not start the thread | `yield from work()` inside `@asynctask`, or use `@thread` for fire-and-forget |
| `ValueError: generator already executing` from `@asynctask` | UE work inside a step re-entered Slate post-tick → nested `next()` | Current runners skip nested ticks. Do not roll a custom ticker that `next()`s the same gen. [../parallel.md](../parallel.md) § Re-entrancy |

## Shipping a public API change

Find affected callers in `mods/`, templates and facade re-exports; update only
those consumers. Verify direct calls and relevant UI/reload paths using
[Mod testing](../mods.md#testing) and the [live-test policy](../SKILL.md#testing-and-essential-boundaries).
Report untested paths; connection availability alone does not authorize mutations.
