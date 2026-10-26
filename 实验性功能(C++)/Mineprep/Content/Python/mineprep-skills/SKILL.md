---
name: mineprep
description: >-
  Use for the Mineprep Unreal Editor plugin: Python scripting, UI panels and
  mods, Minecraft structures, animation, and plugin development. Also use for
  Mineprep API or skill reviews and product introductions. Unreal remote
  execution guidance applies when working on Mineprep editor tasks.
---

# Mineprep

> **⚠️ DEPENDENCY POLICY:** Use only Python's standard library, Unreal APIs, and Python packages supplied by the engine or enabled engine plugins (e.g. NumPy, cv2, Pillow). **Do not install, vendor, or introduce additional third-party dependencies.** A package installed on the development machine is not guaranteed to exist for users.

Plugin Python lives in `Plugins/Mineprep/Content/Python/`; entry: `import mineprep`.
Prefer public `mineprep.*` wrappers. Use `unreal.*` for engine operations without
a wrapper; experimental `unreal.mineprep` is a separate C++ library.

## Scope and evidence

Use a console snippet or `mineprep.ui` for one-shot work; use a Mod for a persistent tool.
Try the matching public `mineprep.*` API before inspecting internals. Reviewing code or
this skill does not require an editor connection or imply an edit request.

Verify plugin contracts against current source and `unreal.*` against the
installed engine's bindings.

## Route

Read focused sections relevant to the task, then matching source as needed.

| Task | Reference | Key entry / boundary |
|------|-----------|----------------------|
| Overview / installation | [intro.md](intro.md) | Verify current product facts when needed |
| API / console / reload | [api.md](api.md) | Public helpers, defaults and recovery |
| UI / persistence / paint | [ui.md](ui.md), [pitfalls/ui.md](pitfalls/ui.md) | `ui()`, PropertyGroup, per-execution state |
| PropertyGroup metadata / native conditions | [property-metadata.md](property-metadata.md) | Metadata keys and Python declaration limits; callbacks/persistence stay in ui.md |
| NBT / schematic / procedural blocks | [structure.md](structure.md), [pitfalls/structure.md](pitfalls/structure.md) | `Blocks`, `spawn_structure`, coordinates and units |
| Terrain / biomes / buildings composed with terrain | [worldgenerator.md](worldgenerator.md) | WorldGenerator public API, batch building, offline checks and previews |
| Bake reusable block models | [structure.md](structure.md#blocksbake-one-reusable-model) | `Blocks.bake`, culling, compatible tiled UVs, recipe identity |
| Kept tool / callable Mod operations | [mods.md](mods.md) | Start from `mods/minimal.py` or `mods/template.py`; split only as needed |
| Level Sequence / Control Rig / AnimSequence | [api.md](api.md), [pitfalls/anim.md](pitfalls/anim.md) | Control Rig belongs on an SKM component; AnimSequence is a different API |
| Mesh merge / generated mesh import | [api.md](api.md), [pitfalls/mesh.md](pitfalls/mesh.md) | `merge_skm`, materials, UVs and skinning |
| Texture import / black sample / render target | [pitfalls/common.md](pitfalls/common.md#textures--rt) | Compilation, source dimensions, painted-RT preservation |
| VAT | [pitfalls/vat.md](pitfalls/vat.md) | VAT-specific resource and bake contracts |
| Delay / tick / worker threads | [parallel.md](parallel.md) | Game-thread callbacks; avoid busy polling |
| Connect / execute / inspect editor | [remote.md](remote.md) | Verify project; bridge `run(loglevel=0)`; compact postconditions |
| Blueprint defaults / components | [remote.md](remote.md#blueprint-defaults-and-components) | Child template only; construction-script variables; compile can drop a CDO write |
| Experimental C++ | [cpp.md](cpp.md) | Verify installed bindings before use |

## Testing and essential boundaries

- Unreal APIs and widgets run on the game thread. A Slate callback must yield
  before work requiring another engine frame; sleeps and same-frame polling do
  not advance that frame. See [parallel.md](parallel.md) and [remote.md](remote.md).
- Instantiate PropertyGroup before `layout.prop` and before Mod's `super().__init__`
  calls `draw()`. Never call `redraw()` from inside `draw()`; use `Layout.hide` to toggle visibility.
- Each `ui()` run has its own namespace; put imports inside the script string.
  PropertyGroup `_autosave_` is off by default; when enabled, it saves `.json` files
  under `__pycache__` (do not blindly delete `__pycache__` if settings are stored there).
- `mineprep.reload()` reloads supported Python modules in place. If it warns that
  mod panels could not close, ask the user to close those leftover windows manually
  rather than reloading repeatedly. See [mods.md](mods.md).
- Structures preserve grid coordinates by default (`center=False`); block meshes
  use cell-center pivots. Structure axes differ from UE and bone-local axes.
  Always construct `Rotator` with keyword arguments (`pitch=`, `yaw=`, `roll=`); see [structure.md](structure.md).
- Source `Texture2D` build completion and painted RenderTargets have different lifecycles:
  never call `force_update_texture` on a painted RT. See [pitfalls/common.md](pitfalls/common.md#textures--rt).
- A successful transport or log line does not prove a mutation succeeded. Query
  scene/asset postconditions before retrying operations that could duplicate objects.
  If no editor connection is available, provide the script for Output Log's **Python**
  console and state that it was not executed.
- Run checks proportional to the change rather than a full test suite on every task.
- Small tasks do not need a screenshot. Capture only when the user asks, or when
  verifying a complex visual result such as modeling or UI layout. See [remote.md](remote.md).

## Source map

The public facade is `mineprep.py`. Follow its imports to `mc_widget` / `mc_mod`
(UI and lifecycle), `mc_sequencer` (animation), `mc_structure` / `mc_importer`
(blocks and models), `mc_mesh` (baking and merging), `mc_prep` (textures), and
`mc_parallel` (scheduling). `mcptools.py` implements the editor bridge;
`Source/Mineprep/` contains C++ bindings. References identify relevant functions.

## Maintaining this skill

Check changed contracts against source, parse complete Python examples without
Unreal, and check local links. Keep reusable methods here, project state and
test histories in project documentation, and each detailed rule in one reference.
