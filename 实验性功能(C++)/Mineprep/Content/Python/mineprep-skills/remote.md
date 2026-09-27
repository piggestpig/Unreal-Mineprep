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

Native tools remain preferred. For another client or diagnosing the helper,
the underlying protocol is:

If Codex has no native Unreal tools but local HTTP access is available, an agent
can still use MCP at the configured URL. This is a fallback for the same server,
not Python Remote Execution. Use a session-capable MCP client when available;
the following sequence was verified against this UE 5.8 server's JSON responses:

1. POST JSON-RPC `initialize` with `id`, `params.protocolVersion="2024-11-05"`,
   `params.capabilities={}`, and `params.clientInfo={"name":"codex","version":"1.0"}`.
   Send `Content-Type: application/json` and
   `Accept: application/json, text/event-stream`; encode JSON bodies as UTF-8.
2. Save the response's **`Mcp-Session-Id` header**. Send it on subsequent requests,
   together with `MCP-Protocol-Version` set to the negotiated protocol version.
3. POST `notifications/initialized` without an `id`; an empty notification
   response is normal. Then use `tools/list` to inspect top-level schemas.
4. POST `tools/call` with `params.name="describe_toolset"` and the discovery
   arguments above; for execution use `params.name="call_tool"` and the complete
   identity-check argument object above. Include an `id` on requests.
5. Check JSON-RPC `error` and MCP `isError` before unpacking the result. For this
   server, parse the text content block as JSON, then parse its `returnValue`
   string as JSON to obtain `{ok, result, logs, error}`. A transport success or
   outer MCP success does not imply the inner `ok` is true.

Do not report native Codex tool registration merely because this HTTP path works.
If a server returns `text/event-stream`, use an MCP/SSE-capable client rather than
parsing the entire response as one JSON document. After an editor restart or an
expired session, initialize again and recheck the project. After a mutation times
out, query its postconditions before retrying; reconnecting does not prove the
operation failed.

## MCP Python (`mcptools.PythonTools`)

Implementation: `Plugins/Mineprep/Content/Python/mcptools.py`. Not part of `mineprep.reload()` (name is not `mc_*`); restart or `importlib.reload(mcptools); mcptools.register()` after editing the bridge itself. Reloading it resets the shared Python session state.

```
toolset_name = "mcptools.PythonTools"
tool_name    = "run"
arguments    = {"code": "unreal.Paths.project_dir()", "loglevel": 0}
```

- `run(code, loglevel=1)` is the API signature; explicitly pass **`loglevel=0` for routine agent calls**. The namespace persists and `unreal` / `mineprep` are injected every call. Nested `def` can see prior assignments. This namespace is shared by clients in the editor process, not isolated per MCP session; use distinct variable names when coordinating agents. `reset()` clears everyone's snippet state, so avoid it as routine cleanup.
- If the last statement is an **expression**, its value is JSON `result`. Bare assignments return `result: null` — end the snippet with the value you need (`len(actors)`, `path`, `actor`).
- An `@asynctask` that `yield`s returns its runner before later frames run. Do not wait inside `run`: the Slate tick that resumes it happens after this call returns. The result is then `{"pending": true, "name": "<func>"}`, and the runner is stored as `_async`. A later `run` of `_async` returns `{"pending": false, "name": "...", "result": ...}` or `"error"` if the task threw. `runner.result` stays `None` until a normal finish, including a finish that returns `None`; use `pending`. A bare `runner = task()` with no trailing expression is treated the same when it starts exactly one task. See [parallel.md](parallel.md) for `yield` itself.
- Return JSON: `{ok, result, logs, error}`. UObjects become `{"uobject": "<path>", "label": "..."}`. `print()` uses the engine `sys.stdout` wrapper (`LogPython`) so it shares a timeline with `unreal.log` / `log_warning` / C++ `UE_LOG` in `logs` (marker slice after `unreal.log_flush()`, not a game-thread sleep). `mineprep.prints` also logs: its `SystemLibrary.print_string` call uses the current default `print_to_log=True`. `warn` explicitly emits a log warning. Filtering and capture limits still apply.
- `loglevel`: `0` recommended for agents and the HTTP helper default — only Warning/Error/Fatal; `1` API default — also keep LogPython/LogTemp/LogBlueprintUserMessages; `2` — keep engine C++ categories, drop Slate/HTTP/MCP noise; `3` — raw slice. Ordinary `print()` output is hidden at `0`; return needed values as the final expression. Use `1` for Python output, `2` for engine diagnostics, or `3` to investigate filtering; do not repeat a scene mutation just to obtain more verbose logs.
- Levels 0/1/2 preserve Warning/Error/Fatal entries plus continuation lines of retained entries. At level 0, `LogSlate*` warnings and their continuation lines are excluded; Slate errors/fatal entries remain. Levels 1–3 include Slate warnings for UI diagnosis. Filtering is by category/severity, not semantic relevance.
- Log discovery checks the flushed call marker to select the active file (including numbered editor log files), rather than assuming `<project>.log` is current.
- The returned JSON string is limited to 200,000 characters (not bytes or tokens).
  Lists/tuples/sets and dictionaries keep at most 80 items; composite values at
  depth 5 become repr previews (up to 2,000 characters). Logs keep up to 2,000
  lines / 80,000 characters before total-response limiting. Every applied limit
  marks its field in `truncated`; `truncation_details` gives paths (field name +
  JSON Pointer segments), reasons and available counts/units. Details are capped
  at 32 records plus an omitted-count summary; paths at 256 characters are marked
  `path_truncated`. Existing in-result omission messages remain. Count metadata
  excludes those messages. Total-size trimming can replace a result's original
  type with text. Non-finite floats become strings (`"nan"`, `"inf"`, `"-inf"`).
  These flags describe serialization/capture trimming, not whether a query
  covered every actor or whether log filtering retained all engine messages.

For large results, count and slice **inside** the editor. Context fragments:

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

Use the installed client's default command endpoint unless binding fails. On Windows, `WinError 10013` can indicate an excluded TCP port; inspect `netsh interface ipv4 show excludedportrange protocol=tcp` and select a free, non-excluded loopback port. A historical failure on port 6776 does not make port 18811 universally available. A bind failure before command submission can be retried with another port; an uncertain result after submission needs the status checks below.

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

## Iterative test loop

If the file log is unavailable and the 20,000-entry engine log fallback has lost the call's start marker, `logs` is empty and marked `log_window_limit`; the original count is unknown. Do not interpret this as proof that the call emitted no warnings.

[Documentation tests](../../../Tests/test_skill_examples.py) check links, Python
syntax and repeated UI execution with substitutes; they do not render panels.
The adjacent MCP tests cover serialization, project checks and timeout handling.
These checks do not establish current editor connectivity or mod E2E coverage;
record live evidence for the actual task.

1. Probe one concern (path, children, signature, materials) via MCP `run` (or RE) — a tiny snippet, not the whole tool
2. Assert with JSON `result` / `logs` (MCP) or returned `output` lines (RE). Do not treat logs alone as success
3. Fold confirmed calls into the shipped code. Remove exploratory API guessing; retain necessary validation, cleanup and known-error handling
4. E2E once; remove `_tmp_*` scripts and leftover probe assets

For importers, keep parsing, naming, UV and bind-matrix tests independent of
`unreal`; reserve RE/MCP checks for asset import, material slots, deformation,
placement and lifecycle. A panel reopening test must observe a new live instance,
not just successful registration logs ([mods.md](mods.md) § Panel lifecycle).
When a preview export is darker than the viewport, check the render-target color
format before changing model materials ([pitfalls/ui.md](pitfalls/ui.md) § Paint / sketch RT).

## Viewport screenshot (agent can Read the png)

Use **`mineprep.screenshot`** for the viewport. Capture when visual evidence helps validate requested editor work, an explicit test, or a reported visual error. Respect no-capture and code-only requests. Additional captures should answer a new question or verify a changed result; avoid repeated identical shots. Choose camera positions for the current scene rather than copying the example coordinates.

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
    path=path,           # always set — default auto-name is hard to find
    pos=unreal.Vector(2100, -4400, 1600),      # optional camera location
    lookat=unreal.Vector(100, -1600, 900),     # optional look-at; with pos sets yaw/pitch
)
```

| Arg | Default | Notes |
|-----|---------|--------|
| `size` | viewport | `(w,h)` sets aspect. Landscape `(1920,1080)`, square `(1080,1080)`, portrait `(1080,1920)`. A single int → square |
| `path` | `Saved/Screenshots/` + auto suffix | **Pass an explicit `.png` path** so you can Read it. Reusing the path overwrites |
| `pos` / `lookat` | current viewport | `lookat` uses `find_look_at_rotation(pos, lookat)` |

The capture is async and may stall on **shader compile**. Use a new filename, or check that a reused file changed since the request. On the host, poll briefly until the new file is nonempty and can be decoded, then inspect it. If it is not ready, report that rather than treating an old PNG or RE `success` as a new screenshot.

PNG only (not EXR). `{Project}/Saved/Screenshots/` may be gitignored — use `unreal.Paths.project_saved_dir()` (there is **no** `project_saved_directory`), do not hardcode a drive letter. `os.makedirs` the folder first.
