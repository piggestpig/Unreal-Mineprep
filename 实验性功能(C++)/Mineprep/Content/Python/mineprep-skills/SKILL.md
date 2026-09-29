---
name: mineprep
description: >-
  Use for the Mineprep Unreal Editor plugin: Python scripting, UI panels and
  mods, Minecraft structures, animation, and plugin development. Also use for
  Mineprep API or skill reviews and product introductions. Unreal remote
  execution guidance applies when working on Mineprep editor tasks.
---

# Mineprep

Plugin Python lives in `Plugins/Mineprep/Content/Python/`; entry: `import mineprep`.
Prefer public `mineprep.*` wrappers for supported operations. Use `unreal.*` for
engine operations with no wrapper; experimental `unreal.mineprep` is a separate
C++ library — [cpp.md](cpp.md). Editor Python is the runtime; writing or reviewing
code does not require a live editor connection.

## Scope and evidence

Follow the user's requested outcome. Reviewing this skill means evaluating it,
not editing it; a request to improve it authorizes document changes. Reading
source to verify behavior does not imply permission to change that source.
If there is no task, briefly introduce Mineprep and ask what they want to do.

Choose the smallest suitable delivery: console snippet or `mineprep.ui` for
one-shot work, a single-file Mod for a kept tool, a folder Mod when its complexity
benefits from multiple files. Change plugin internals when the request calls for
it. Use existing context to resolve routine choices; ask only when ambiguity
materially affects the outcome or scope.

For straightforward editor tasks, try the matching public API with its defaults
before probing implementation details. For example, place a known mob with
`mineprep.spawn_mob('Blaze')`; omit coordinates unless requested. Investigate
prerequisites only after a concrete failure, and check uncertain outcomes before
retrying a mutation. If the ready generator's options lack the requested mob,
use [VanillaMobLoader fallback](api.md#mob-missing-from-the-generator) directly;
do not inspect the whole mod or substitute a similarly named species.
See [placement and recovery](api.md#spawn).

**Evidence order:** current source for plugin contracts; the installed engine's
bindings/docs for `unreal.*`; the product README for installation and releases.
This package targets UE 5.8. Check version-specific notes against the installed
engine. Distinguish source checks from runtime tests and state what remains
unverified.

Distinguish API requirements from project defaults and examples. A workaround
for a particular engine version, model, or host is conditional. If source and
this skill disagree, report the discrepancy and follow verified behavior.

For an important backend API gap, describe the reproduction and impact.
If useful, suggest a [GitHub issue](https://github.com/piggestpig/Unreal-Mineprep/issues);
create one only when the user requests it.

## Route

Start with the references relevant to the task. Follow additional references or
source when needed to resolve uncertainty; the table is a reading guide, not an
allowlist. Read focused sections rather than the entire package by default.

| Task | Start with | Delivery / important boundary |
|------|------------|--------------------------------|
| Overview, install, changelog | [intro.md](intro.md) | Answer the requested topic; fetch current product facts when needed |
| Review this skill / API | Relevant documents and matching source | Findings with evidence; no automatic edits; live probes only when authorized |
| Improve this skill | Affected documents and matching source | Update instructions and cross-references; validate links and examples |
| API Q&A / console snippet | [api.md](api.md) | Answer or script; source checks are welcome, editor execution depends on intent |
| Level Sequence / Control Rig | [api.md](api.md), [pitfalls/anim.md](pitfalls/anim.md) | `actor.rig(...).key`; Control Rig belongs on an SKM component. Copy the 60fps preset; `bindings.actor()` after `until` |
| Scene automation script | [automation.md](automation.md) | One session's example only. Not a rule; do not copy its paths, frames, or coordinates unless requested |
| Temporary UI / persistence / paint | [ui.md](ui.md), relevant [pitfalls/ui.md](pitfalls/ui.md) section | `ui()` + PropertyGroup instance; per-execution state; default cache or explicit settings path |
| NBT / schematic / procedural blocks | [structure.md](structure.md), [api.md](api.md) examples; [pitfalls/structure.md](pitfalls/structure.md) if needed | User file or `Blocks` → `spawn_structure`; choose geometry for the requested design |
| Kept tool / Mod / script-callable operations | [mods.md](mods.md), [ui.md](ui.md), `mods/minimal.py` or `mods/template.py` | Single-file first; expose only necessary operations; keep internals simple; `api.py` only when useful |
| Public API change / bug | Matching `mc_*.py`, facade and affected consumers | Update affected callers and verify changed behavior |
| AnimSequence bone tracks | [pitfalls/anim.md](pitfalls/anim.md) | Engine animation APIs; distinct from Level Sequence |
| Merge SKM / Geometry Script / generated mesh import | [api.md](api.md), [pitfalls/mesh.md](pitfalls/mesh.md) | `mineprep.merge_skm`; UV, skinning and import validation |
| Texture sample / render target | [pitfalls/common.md](pitfalls/common.md); paint details in [ui.md](ui.md) | Source texture refresh and canvas preservation are different operations |
| VAT bake / VAT asset duplication | [pitfalls/vat.md](pitfalls/vat.md), relevant `mods/VAT_Tools` code | VAT-specific paths and reuse policy; don't apply them to unrelated asset copies |
| Delay / tick / background thread | [parallel.md](parallel.md) | Game thread for `unreal.*`; `@thread` is not a pool; do not poll with ticker `delay=0` |
| Reload / stale Props | [api.md](api.md) § Reload, [mods.md](mods.md) | Full reload handles reloadable submodules; registration alone does not reload code |
| Connect Codex to UE / run / test / inspect editor UI | [remote.md](remote.md) | MCP configuration, discovery and HTTP fallback; verify project; use `mcptools.PythonTools.run` with explicit `loglevel=0`; check results before retrying mutations |
| Experimental C++ | [cpp.md](cpp.md), `Source/Mineprep/Public/MineprepBPLibrary.h` | Verify availability; missing bindings do not imply a request to write replacement C++ |
| Unknown engine API / binding failure | Installed engine docs/bindings; `Engine/Source` if available | Confirm signatures; use a focused probe if runtime verification is in scope |

## Testing and essential boundaries

- Reviews and explanations do not connect to the editor by default. If the user
  authorizes necessary live verification, use focused probes; respect explicit
  code-only or no-capture requests. Never infer permission to edit from a review.
- Requested editor work: prefer available Unreal MCP tools, then the Python
  bridge with explicit `loglevel=0`. [remote.md](remote.md) covers project identity,
  the bundled HTTP client, RE fallback, result limits and screenshots. Missing
  native tools alone do not establish that the server is unavailable.
- If no connection works, deliver the complete script and where to run it
  (Output Log, console set to **Python**), and state it was not executed.
- Verify postconditions, not just logs or a successful call. Check state before
  retrying a submitted operation whose outcome is uncertain.
- UI: instantiate PropertyGroup before `layout.prop` and before Mod's
  `super().__init__` calls `draw`. Never redraw from `draw`; prefer `Layout.hide`
  for visibility. Temporary `ui()` scripts have per-execution namespaces; keep imports
  inside the script. Persistence remains in `__pycache__` unless an explicit path is used.
  Full rules and complete examples: [ui.md](ui.md).
- Reload: use `mineprep.reload()` after editing plugin Python/reloadable mods;
  inspect warnings and notify the user to close leftover windows manually. No
  repeated reload to close them, no automatic reopening. [mods.md](mods.md)
  explains the Blueprint close event and cleanup ownership.
- Simple placement uses the matching `spawn_mob` / `spawn_item` / `spawn_block`
  helper. Structures use `spawn_structure` / `spawn_blocks`.
  [api.md](api.md#spawn) covers defaults and recovery after a missing-cache error.
- Rotators use keyword `pitch`/`yaw`/`roll`. A user-supplied triple is roll, pitch, yaw (details panel 横滚 / 俯仰 / 偏转). Structure and bone-local axes differ.
  See [pitfalls/common.md](pitfalls/common.md) and [structure.md](structure.md).
- Texture refresh and canvas preservation are different: never rebuild a painted
  RT to refresh source texture data. [pitfalls/common.md](pitfalls/common.md).
- Worker threads must not call Unreal APIs; use game-thread callbacks. Do not
  busy-poll a Future with ticker delay=0. [parallel.md](parallel.md).
- Public API changes: update only affected facade/Mod consumers, keep useful
  validation and error handling, and verify behavior appropriate to the change.
- Keep verification proportional: run affected regression tests once, then one
  focused editor check for behavior that needs UE. Batch independent checks and
  return compact assertions/counts. Expand or repeat only for new changes,
  failures or unresolved risks; keep detailed logs for diagnosis.

## Source map

| Module | Role |
|--------|------|
| `mineprep.py` | Public facade: handles, plugin chrome, spawn, mesh helpers |
| `mc_widget.py` | `Layout`, `PropertyGroup`, `ui` |
| `mc_mod.py` | Mod registration and lifecycle |
| `mc_utils.py` | Reload, screenshot, logging, transactions, handles' utilities |
| `mc_parallel.py` | `delay`, `tick`, `asynctask`, `thread`, `asyncthread`, `until` |
| `mc_localization.py` | `bilingual`, `localize`, `loctext` |
| `mc_sequencer.py` | Level Sequence, `keyframe`, `Rig` |
| `mc_importer.py` / `mc_structure.py` | JSON mesh import, block cells, NBT, transforms |
| `mc_prep.py` / `mc_material.py` | Texture preparation and color conversion |
| `mc_mesh.py` | `merge_skm` |
| `mc_config.py` / `mcvars.py` | Paths, configuration, shared editor state |
| `mcptools.py` | UE 5.8 MCP Python bridge (`mcptools.PythonTools`); registered from `init_unreal.py` |
| `Source/Mineprep/` | C++ bindings and editor integration |

## Maintaining this skill

After an API-related document change, check exported names, signatures, defaults,
return types and prerequisites against source. Parse complete Python examples
without importing Unreal; syntax success does not prove runtime validity.
Check local Markdown links, and test changed runtime examples in-editor when
available and in scope. Record any unverified behavior explicitly. Keep a rule's
full explanation in one reference and link to it rather than copying it across
multiple checklists.
