# Remote Execution & agent testing

How the agent runs Unreal Editor Python. Scope and validation policy: [Testing and essential boundaries](SKILL.md#testing-and-essential-boundaries). Use this for requested editor operations and tests, not automatically for code review or explanation.

Mesh bake / `merge_skm` traps: [pitfalls/mesh.md](pitfalls/mesh.md) — not this file.

## Prefer order

Remote transport does not change which Mineprep API fits the task. For one known
mob, use `spawn_mob` directly; see [placement and recovery](api.md#spawn).

1. **Official Unreal MCP toolsets** (if connected) — Scene / Actor / Object / Material / viewport capture / etc.
2. **`mcptools.PythonTools`** — Mineprep and arbitrary editor Python (`import mineprep` / `unreal`)
3. **Python Remote Execution** — multicast client → editor `remote_execution` listener
4. Neither → **stop testing**; still finish authoring. For `mineprep.ui` / console snippets, give the user the full code to paste into Output Log with the console set to **Python**. Do not add a helper `.py` under `Content/Python/`.

Do not invent browser automation or fake editor state as a substitute. Official `ProgrammaticToolset` is a sandbox for chaining other MCP tools; it is **not** a general `execute_python` and cannot replace `mcptools`.

## Detect availability

**MCP:** inspect available Unreal MCP tools and their connected project before running mutations. Confirm the project (plugin path, current level, or `run` of `unreal.Paths.project_dir()`). If native tools are missing, check the configured endpoint using the HTTP fallback below before trying Remote Execution; do not assume all MCP connections point to this workspace.

`list_toolsets` should include `mcptools.PythonTools` after the Mineprep plugin has started (`init_unreal.py` → `mcptools.register()`). If that toolset is missing: MCP server may be up without the plugin Python having registered — restart the editor, or in Output Log (Python) run `import mcptools; mcptools.register()` then `ModelContextProtocol.RefreshTools`. AllToolsets is a plugin dependency of Mineprep; Unreal MCP still needs Auto Start Server / `ModelContextProtocol.StartServer`.

## Discover and call the bridge

Use the actual exposed tool names (the host may prefix them). This UE server
exposes `list_toolsets`, `describe_toolset`, and `call_tool` as top-level tools;
`run` need not appear as a separate native Codex tool.

1. Call `list_toolsets` and locate `mcptools.PythonTools`.
2. Call `describe_toolset` with `{"toolset_name":"mcptools.PythonTools"}` to
   confirm the live schema.
3. Call `call_tool` with the following arguments for a read-only identity check:

```json
{
  "toolset_name": "mcptools.PythonTools",
  "tool_name": "run",
  "arguments": {
    "code": "{'project': unreal.Paths.project_dir(), 'plugin': mineprep.__file__}",
    "loglevel": 0
  }
}
```

Match these paths to the intended workspace before editing assets or the scene.
For subsequent calls replace `code` with editor Python, ending with the specific
value needed. Prefer counts, selected properties or a small sample over whole
object dumps. `loglevel=0` filters logs, not a large `result`.

## Connect from Codex

For connection setup, inspect the existing project `.codex/config.toml`. Codex
supports project MCP settings in trusted projects; user-level settings can also
live in `~/.codex/config.toml`. Preserve other settings and update an existing
server table instead of adding a duplicate. Typical local configuration:

```toml
[mcp_servers.unreal-mcp]
url = "http://127.0.0.1:8000/mcp"
```

Use the actual configured port (`-ModelContextProtocolPort=N` can override 8000).
In UE's command console, `ModelContextProtocol.StartServer` starts the server.
`ModelContextProtocol.GenerateClientConfig Codex` may refuse to overwrite an
existing TOML file; that message does not mean the server failed. Check the
existing table first. If a changed configuration is not reflected in Codex's
available tools, try restarting Codex and reopening the project. Configuration
alone is not evidence of a successful connection.

Reference: [Codex MCP configuration](https://developers.openai.com/codex/mcp).

### Direct MCP HTTP fallback

Prefer the bundled [scripts/mcp_run.py](scripts/mcp_run.py) (host Python 3.11+)
over rewriting connection code. Replace the angle-bracket paths below:

```text
python <skill>/scripts/mcp_run.py --project <project> --code "unreal.SystemLibrary.get_engine_version()"
python <skill>/scripts/mcp_run.py --project <project> --file <snippet.py> --loglevel 0
```

It reads this project's existing `.codex/config.toml` Unreal MCP URL, or accepts
`--url`. It never edits configuration. Each invocation discovers the bridge and
checks the editor's absolute project path before submitting the supplied code.
Files and HTTP bodies are UTF-8; stdout is ASCII-safe JSON. The host helper adds
`error_kind` and `outcome` to the bridge envelope: `not_submitted`, `uncertain`,
`execution_failed`, or `completed`. The latter means the Python call completed,
not that an async operation or asset import is finished. An exception can follow
partial side effects. Neither Python errors nor transport failures are retried;
after `uncertain`, inspect postconditions before deciding what to do. The default
network timeout is 30 seconds (`--timeout`); it does not cancel editor work.

For another client, follow the session initialization and response decoding in
the helper rather than copying a fixed protocol version. Use an MCP/SSE-capable
client for event-stream responses. Check JSON-RPC `error`, MCP `isError`, and the
inner bridge `ok`; this server wraps the bridge JSON inside `returnValue`.
HTTP success does not imply native tool registration or completed editor work.
After a restart or expired session, reconnect and recheck project identity.

## MCP Python (`mcptools.PythonTools`)

Implementation: `Plugins/Mineprep/Content/Python/mcptools.py`. Not part of `mineprep.reload()` (name is not `mc_*`); restart or `importlib.reload(mcptools); mcptools.register()` after editing the bridge itself. Reloading it resets the shared Python session state.

```
toolset_name = "mcptools.PythonTools"
tool_name    = "run"
arguments    = {"code": "unreal.Paths.project_dir()", "loglevel": 0}
```

- **Session & `loglevel`**: `run(code, loglevel=1)` shares one namespace across the editor process (`unreal` and `mineprep` are updated each call; avoid `reset()` during shared sessions). Pass **`loglevel=0` for routine agent calls** (`0` = Warning/Error/Fatal excluding `LogSlate*` warnings; `1` = adds `LogPython`/`LogTemp`/`LogBlueprintUserMessages` so `print()` appears; `2` = drops Slate/HTTP/MCP noise; `3` = unfiltered). Return needed values via the **last expression** rather than relying on `print()` at level 0.
- **Yielding `@asynctask`**: returns `{"pending": true, "name": "<func>"}` immediately and stores the runner in `_async`. Query `_async` in a later `run` call (`{"pending": false, "name": "...", "result": ...}` or `"error"`); never wait inside `run`. See [parallel.md](parallel.md).
- **Return format & truncation**: returns `{ok, result, logs, error}` (capped at 200,000 chars; sequences/maps keep at most 80 items, with `truncated` and `truncation_details` when trimmed). UObjects serialize as `{"uobject": "<path>", "label": "..."}` and handles as `{"handle": "<class>", "target": ...}`.

For large collections (>80 items), store the list in the session namespace and slice in-editor:

```python
# First call: retain the raw snapshot in the shared bridge namespace.
review_items = list(mineprep.actors().target)
len(review_items)
```

```python
# Subsequent calls: use the count to choose nonoverlapping slices <=80 items.
review_items[0:80]
```

```python
review_items[80:160]
```

Do not count the serialized array or treat its trailing omission string as a
UObject. Use an explicit count to determine the total number of items.

- `ok` + `result` (and task-specific postconditions) are the contract. `logs` are evidence of what the engine reported, not proof the mutation finished. Use status checks before retrying something that can duplicate actors or assets.
- After plugin/mod edits, follow [Reload](api.md#reload). The shared MCP namespace
  retains separately imported names; re-import them after reload.
- Do not block the game thread with `time.sleep` loops. Dialogs (`panic` / `dialog`) freeze the MCP call until dismissed.

```python
# last expression is the return value
unreal.Paths.project_dir()
```

```python
actors = mineprep.spawn_structure(source, loc=(0, 0, 0))
len(actors)
```

**Remote Execution (quick probe):**

```python
# Outside UE. Here UE_ENGINE_DIR means the install root containing Engine/.
import os
import sys
import time
from pathlib import Path

engine_root = os.environ.get('UE_ENGINE_DIR')
if not engine_root:
    raise RuntimeError('Set UE_ENGINE_DIR to the verified engine install root')
re_py = Path(engine_root) / 'Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python'
if not (re_py / 'remote_execution.py').is_file():
    raise RuntimeError(f'Engine remote_execution.py not found: {re_py}')
sys.path.insert(0, str(re_py))
import remote_execution as remote

def discover_nodes(wait_seconds=4.5):
    client = remote.RemoteExecution()
    client.start()
    try:
        # Keep the discovery window open; the first node may be another project.
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            time.sleep(0.3)
        return list(client.remote_nodes)
    finally:
        client.stop()

nodes = discover_nodes()
# Inspect node metadata; discovery alone does not confirm a usable command channel.
```

Resolve `engine_root` from this project's engine association or ask the user. Do not hardcode another machine's drive letter.

Match discovered node metadata to the intended project and host. If metadata is insufficient, use a read-only identity query on the candidate to verify its project directory before sending work. A single discovered node is not proof that it belongs to this project. Keep the verified `node_id` explicit; if the project cannot be identified unambiguously, ask for the target rather than defaulting to the first result. Re-discover and re-verify after an editor restart.

## Enable Remote Execution (tell the user)

In Unreal Editor:

1. **Edit → Editor Preferences → Plugins → Python**
2. Enable **Python Remote Execution**
3. Typical defaults: multicast `239.0.0.1:6766`, bind `127.0.0.1`
4. Restart editor if the preference was just turned on
5. Confirm the project can `import unreal` in the Output Log

Client module (shipped with Engine):

`Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python/remote_execution.py`

## RE client pattern

Use the installed client's default command endpoint unless binding fails. On Windows, `WinError 10013` can indicate an excluded TCP port; inspect `netsh interface ipv4 show excludedportrange protocol=tcp` and select a free, non-excluded loopback port. A bind failure before submission can be retried with another port; an uncertain result after submission needs the status checks below.

```python
# Host Python; use the imports and engine-module setup above.
def ue_run(code: str, *, node_id: str, exec_mode=None, command_port=None):
    if not node_id:
        raise ValueError('An explicitly selected node_id is required')
    config = remote.RemoteExecutionConfig()
    if command_port is not None:
        config.command_endpoint = ('127.0.0.1', command_port)
    re = remote.RemoteExecution(config)
    re.start()
    try:
        for _ in range(15):
            time.sleep(0.3)
            if any(node['node_id'] == node_id for node in re.remote_nodes):
                break
        if not any(node['node_id'] == node_id for node in re.remote_nodes):
            raise RuntimeError('Selected Unreal node is unavailable; re-discover and verify the project')
        re.open_command_connection(node_id)
        return re.run_command(code, exec_mode=exec_mode or remote.MODE_EXEC_FILE)
    finally:
        re.stop()
```

- Prefer `MODE_EXEC_FILE` for multi-line scripts (and for `mineprep.ui("""...""")` blobs)
- Host-side: write a short `_tmp_re_*.py` runner if the shell mangles quotes; **delete after** the probe. Read the editor snippet as **UTF-8 from a file** (`open(path, encoding='utf-8')`). Do not `sys.stdin.read()` through `cmd.exe` (GBK / surrogate `UnicodeEncodeError` on `—` / CJK)
- Keep editor `print` to a few ASCII tokens (`CELLS 2144`, `OK`). `import_block` already logs; huge output plus a GBK host `print` can crash the client **after** a successful spawn
- Check the returned `success`, error information and task-specific postconditions. Spawn logs may precede a failure; `len(spawn_structure(...))` counts actors, not placed blocks or successfully imported model types.
- If output decoding fails or a submitted command times out, mark the outcome **uncertain**. Do not blindly repeat the spawn. Run a read-only check in the same verified project using recorded actor paths, a unique operation name, asset paths or other task-specific evidence. Labels alone may be ambiguous.
- Retry a mutation only after proving it was not applied, or after an explicit reconciliation of partial output within the task's scope. If status cannot be established, report the uncertainty. This does not prohibit harmless status queries.
- After editing plugin Python or a reloadable mod: `mineprep.reload()` inside the remote snippet
- Discovery OK + bind fail → change `command_port`, do not conclude RE is disabled

## mineprep handles under RE

```python
import mineprep
a = mineprep.actor['Steve']          # raw UObject (class subscript → .target)
# mineprep.actor('Steve')            # handle — use handle methods or .target
root = a.root_component              # often Body SkeletalMeshComponent
```

`warn` / `prints` from `mc_utils` show on-screen and in the log when run inside the editor.

## Remote-debug UI panels

Layout joins `WidgetsCache` when `public=True` or `mcvars.DebugMode`. Mods default `_public_=False`.

1. `mcvars.DebugMode = True` **before** the panel draws (`register(True)` / `ui()` / `redraw`). `mineprep.reload()` keeps `mcvars`.
2. Log line `已缓存 mineprep.panel('<path>')`. Pass that **exact** path to `mineprep.panel`. A substring miss only lists candidates (`target` stays `None`). Do not call empty `mineprep.panel()` under RE (whole-cache dump; CJK can crash a GBK host).
3. Drive the handle: SpinBox `get`/`set`; property views `get_object()` then `set_editor_property` + `on_property_changed.broadcast`; hide with `Layout(widget.target).hide(True)` (Collapsed).
4. Save the prior `mcvars.DebugMode` value and restore it in `finally` after inspection. Off does not flush the cache; it only stops new entries.
5. For a **visible panel**, first confirm the tab is open, then use `unreal.mineprep.widget_screenshot`. Current C++ tries a visible Slate capture, then offscreen rendering. A PNG does not prove the tab is open or shows that image on screen. Closed/stale widgets may still fail. Empty path overwrites `Saved/Screenshots/WidgetScreenshot.png`; use a fresh explicit path and inspect it. A successful call saves before returning (unlike async viewport capture). Do not use `mineprep.screenshot` for UI.

```python
import mineprep
import unreal
shot = unreal.Paths.project_saved_dir() + '/Screenshots/panel.png'
w = mineprep.panel['Mineprep'] #插件面板
saved = unreal.mineprep.widget_screenshot(w, shot)
```

`widget_screenshot(w, shot, delay=0.3)` saves immediately, then captures again
after the delay (seconds) and overwrites the same path if the target is still
visible. Read the final image after that interval; `delay=0` captures only once.

## Verification

If the file log is unavailable and the 20,000-entry engine log fallback has lost the call's start marker, `logs` is empty and marked `log_window_limit`; the original count is unknown. Do not interpret this as proof that the call emitted no warnings.

Keep parsing, naming, UV and bind-matrix checks independent of Unreal. Reserve
editor checks for assets, materials, deformation, placement and lifecycle; a
panel reopening check must observe a live instance, not registration logs.
Choose checks for the actual change; [SKILL.md](SKILL.md#testing-and-essential-boundaries)
covers proportional validation. Documentation checks do not prove editor behavior.

## Viewport screenshot (agent can Read the png)

Prefer MCP **`EditorToolset.EditorAppToolset.CaptureViewport`** with `bShowUI=false`
for the current viewport. Inspect the returned image; it is inline, not a saved
file. Discover the current schema first. If the bridge requires optional
arguments, pass the current camera transform and an `annotations` object with
`gridSpacing=0`, `gridExtent=0`, `gridHeight=0`, `maxLabelDistance=0`,
`maxLabels=0`, `classFilter={"refPath":"/Script/Engine.Actor"}`.
This tool is not exposed as `unreal.EditorAppToolset.capture_viewport` in Python.

For a high-resolution image or a Python-only session, use `mineprep.screenshot`:

```python
import os
import mineprep
import unreal

shot_dir = os.path.join(unreal.Paths.project_saved_dir(), 'Screenshots')
os.makedirs(shot_dir, exist_ok=True)
import uuid
path = os.path.join(shot_dir, f'view_{uuid.uuid4().hex}.png')
mineprep.screenshot(
    size=(1920, 1080),   # omit → viewport res; (1080,1080) square; (1080,1920) portrait
    path=path,           # explicit path makes the new image easy to inspect
    delay=0.3,           # seconds before capture; default 0
)
```

The Python capture is async. Verify a fresh, decodable PNG before inspecting it;
delay alone does not guarantee completion in a background viewport. Check Alpha
if an image looks blank. A `.jpg` suffix does not convert PNG output to JPEG.
Small tasks do not need screenshots; further captures should check a changed
result or answer a new visual question. Use widget capture above for panels.

## Blueprint defaults and components

Confirm `unreal.Paths.project_dir()` before writing. If `UnrealEditorSubsystem.get_game_world()` is set, PIE is running; don't reparent or compile. An editor restart clears the bridge namespace. Keep a snapshot you still need in a UTF-8 file and return a count — a large `run` result is truncated.

Class defaults are on the CDO: `unreal.get_default_object(blueprint.generated_class())`. `get_editor_property` takes the variable name, including non-ASCII names. `dir()` on the CDO does not list them, and `new_variables` is not exposed on `Blueprint`. Don't `dir()` a struct or UObject to discover fields; that can freeze the editor. Use `export_text()`, or a field you already know.

Components come from `SubobjectDataSubsystem.k2_gather_subobject_data_for_blueprint` and `k2_find_subobject_data_from_handle`. `get_object()` is often the parent template; writing it changes every child. `get_object_for_blueprint(data, blueprint)` is that blueprint's template — data first. Write only when the outer is this generated class (`Foo_C`) or its CDO (`Default__Foo_C`). The same object can appear twice; skip duplicates by identity. `get_components_by_class` on a child CDO is often empty, and `is_editor_property_overridden` often has no archetype value. Neither means the component is missing.

```python
sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
lib = unreal.SubobjectDataBlueprintFunctionLibrary
cls_name = blueprint.generated_class().get_name()
for handle in sub.k2_gather_subobject_data_for_blueprint(blueprint):
    data = sub.k2_find_subobject_data_from_handle(handle)
    component = lib.get_object_for_blueprint(data, blueprint)
    if component is None:
        continue
    outer = component.get_outer().get_name()
    if outer not in (cls_name, 'Default__' + cls_name):
        continue  # parent template
```

A native mesh or capsule sits on the CDO (`CharacterMesh0`, `CollisionCylinder`). A Blueprint component is `Name_GEN_VARIABLE` on the class. After a reparent, the same role can switch between those; match the role, not the old name. The skeletal mesh property is `skeletal_mesh_asset`. An empty `override_materials` list means the mesh default. A null mesh on a child template usually means inherit — don't clear a mesh because the source template is null.

If the viewport shows a mesh the template doesn't store, the construction script is copying an actor variable onto it. Set that variable on the CDO. If this class has no such variable, set the asset on this blueprint's own component.

Across editors, serialize a struct with `export_text()`, an object as its path, and an enum as `.name` (`int(enum)` fails). Walk maps and arrays the same way. Apply with `import_text`, then `set_editor_property`. Edit an existing map in place: drop extra keys, copy an existing value to insert a missing key, then `import_text` each value and assign it back. Enum keys come from `for member in type(sample)`. Two rotators can be one orientation; compare quaternion dot products before writing, or a later compile will normalize the Euler and look like a mismatch. Set capsule size with `set_capsule_size(radius, half_height)`. Rotator argument order: [pitfalls/common.md](pitfalls/common.md).

`BlueprintEditorLibrary.reparent_blueprint`, `get_blueprint_parent_class`, and `compile_blueprint`. A class path ends in `.Name_C`; the blueprint asset path does not. The hierarchy-changing log is expected. Reparenting drops per-child overrides, so snapshot first and put each blueprint back on its own parent. Don't export every `*_GEN_VARIABLE` on a parent template; that can crash the editor.

Compile can rebuild the CDO and drop a default you just set. Set, compile, read back. If the value is gone, set it again and save without compiling a second time. Take one asset through that check before a folder. Batch with `@mineprep.asynctask` and `yield` between assets. Keep progress in a list the next `run` can read. The runner has `done`, `result`, and `error`, not `is_running`. Save with `EditorAssetLibrary.save_loaded_asset` only after the re-read matches.
