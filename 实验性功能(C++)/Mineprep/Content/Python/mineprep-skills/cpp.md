# Experimental C++ (`unreal.mineprep`)

Experimental editor helpers from plugin C++. Prefer `import mineprep` / `mineprep.*` where a wrapper exists. Read this reference for C++ binding use, review or development.

C++ class: `Umineprep` in `Source/Mineprep/Public/MineprepBPLibrary.h` (category `Mineprep|实验性功能(C++)`). UE Python exposes it as **`unreal.mineprep`** — that name is intentional.

These bindings can **break after an Engine upgrade** until the plugin is rebuilt. They are experimental, not a second public API.

## Policy

1. Search `mineprep.*` and engine `unreal.*` first.
2. Call `unreal.mineprep` only for a **necessary** gap (notification toast, UI scale, widget-under-mouse loc, viewport→RT, project-setting helpers, Scriptable Tool, …).
3. Verify against the header and installed bindings; probe when runtime testing is in scope. If the type is missing, report that experimental C++ is unavailable (possibly not built or not loaded). Use a verified Python alternative where one exists; otherwise explain the limitation. Write or restore C++ only when the development request calls for it.
4. Do not wrap these into `mineprep.py` unless they asked for a stable Python API.
5. Do not confuse this type with the Python module:

```python
import mineprep          # Python facade — panel / spawn / ui
unreal.mineprep          # C++ Blueprint Function Library (a class)
# unreal.mineprep.panel  # DOES NOT EXIST — use mineprep.panel(...)
```

`TempBPLibrary` is commented out. Ignore it.

## Detect

```python
import unreal

ok = hasattr(unreal, 'mineprep') and hasattr(unreal.mineprep, 'show_editor_notification')
if not ok:
    # tell the user; continue with mineprep.*
    pass
```

Unsure of a signature? `print(unreal.mineprep.set_editor_ui_scale.__doc__)` (or `dir(unreal.mineprep)`), then one RE probe. Trust `MineprepBPLibrary.h` over this file if they disagree.

## Call shape

Static methods on the **class**. Out-params become a return tuple.

```python
unreal.mineprep.show_editor_notification(
    'done', '', unreal.EditorNotificationState.SUCCESS, 3.0, False)

scale = unreal.mineprep.set_editor_ui_scale(-1.0)  # <0 → current scale, no change
text, tip = unreal.mineprep.get_widget_text_under_mouse()
```

Enums recorded for the UE 5.7-targeted bindings; recheck the installed build when using them:

- `unreal.EditorNotificationState`: `NONE`, `PENDING`, `SUCCESS`, `FAIL`
- `unreal.MineprepPostProcessStage`: `SCENE_COLOR_BEFORE_DOF`, `SCENE_COLOR_AFTER_DOF`, `TRANSLUCENCY_AFTER_DOF`, `SSR_INPUT`, `SCENE_COLOR_BEFORE_BLOOM`, `REPLACING_TONEMAPPER`, `SCENE_COLOR_AFTER_TONEMAPPING`

## Functions

Do not recommend `inject_display_name` / `set_property_tooltip` (`DeprecatedFunction`).

| Python | Use when |
|--------|----------|
| `show_editor_notification(message, sub_text, state=NONE, duration=3.0, use_throbber=False)` | Editor toast. Prefer `mineprep.prints` / `warn` for ordinary script feedback |
| `set_editor_ui_scale(scale) -> float` | Slate UI scale. `scale < 0` returns current without changing |
| `get_widget_text_under_mouse() -> (str, str)` | Widget text + tooltip under the cursor |
| `loc_widget_text_under_mouse(new_text="") -> int` | Empty `new_text` → look up loc table; else set text |
| `draw_viewport_to_render_target(rt, auto_resize=True, block_until_ready=False) -> bool` | Blit viewport into an RT. Visual checks for the **agent**: `mineprep.screenshot` — [remote.md](remote.md) |
| `draw_post_process_stage_to_render_target(rt, stage, auto_resize=True, block_until_ready=False) -> bool` | Same, at a post-process stage |
| `widget_screenshot(widget=None, path="") -> str` | PNG of a UMG widget. Empty widget → active top-level window. Empty path → `Saved/Screenshots/WidgetScreenshot.png`. Success = saved `.png` path; failure = `WidgetScreenshot: ...` error. Visible capture is attempted first, then offscreen rendering. A PNG does not establish live-tab visibility. Panel shots: [remote.md](remote.md) |
| `get_project_setting(name) -> str` / `set_project_setting(name, value) -> bool` | Project setting by name |
| `open_project_setting(container, category, section)` | Open that Project Settings page |
| `switch_editor_mode(mode_id="EM_ScriptableToolsEditorMode")` | Editor mode |
| `is_editor_mode_active(mode_id="EM_Default") -> bool` | Query mode |
| `activate_scriptable_tool(tool_blueprint) -> bool` | Enter Scriptable Tools mode and start that tool BP |
| `call_delegate(object, delegate_name, params) -> bool` | Fire a multicast delegate by name; `params` is `str` array |
| `set_global_gravity(vector)` | Chaos gravity |
| `set_tick_run_on_any_thread(object, bool)` | Tick on any thread |
| `get_material_info(track)` / `clean_material(material) -> bool` | Sequencer material track / strip unused material nodes |
| `expose_struct_variables(user_defined_struct) -> bool` | Keyframe buttons on struct vars |
| `gather_property_names(obj, set_enum_key=False) -> (types, keys, source_strings)` | Public BP vars/functions, user-enum values, material/Niagara params. `set_enum_key=True` writes user-enum DisplayName identity (ns `UObjectDisplayNames`, key `{AssetName}.{DisplayNameWithoutSpaces}`) only when namespace/key differ — no `MarkPackageDirty` if already matching |
| `bind_niagara_param(parameter_track, niagara_variable, default_value_data)` | Bind a Niagara parameter track |

## Other plugin C++ (not this BFL)

Not console APIs. Do not invent Python wrappers. Mention only if the user is in that UI or asked to change plugin C++.

| Code | What it is |
|------|------------|
| `UMineprepSubsystem` | Hotkey register/load. Python: `mineprep.hotkey(...)` |
| `AddKeyframes` | Details row keyframes for Niagara / color grading |
| `CustomDetailsPanel` | Details customization for `Pawn` (Mover) and `SkeletalMeshActor` |
| `Mineprep.TickInterval` | Console variable for the editor ticker (hotkey BP `Run`) |

Engine binding crashes still use this machine's Engine install (`Engine/Source` **only if it exists**) — not these plugin files.

## Rebuild

**Mineprep C++:** build the game Editor target. That is the normal path.

Do **not** drop an Engine plugin (e.g. `PythonScriptPlugin`) into Mineprep `Plugins/` to patch it. Installed-engine modules such as `NiagaraEditor` / `ControlRigEditor` then depend on a **Project** plugin, and UBT rejects the hierarchy (`Project → … → Engine Plugins`).

Last resort only — patched Engine plugin on a **launcher** Engine: compile it in a **blank** C++ project with `"DisableEnginePluginsByDefault": true`, enable that plugin plus `EnhancedInput` if the game module needs it, then copy `Plugins/<Name>/Binaries` back. `ModelingToolsEditorMode` pulls Niagara (via GeometryCache) and re-breaks the hierarchy — leave it off. Do not use this circus for Mineprep itself.
