# Delay / tick / asynctask / thread

Implementation: `Plugins/Mineprep/Content/Python/mc_parallel.py`  
Public names: `mineprep.delay`, `tick`, `asynctask`, `thread`, `asyncthread`, `until` (and the runner classes). After editing `mc_*.py`, `mineprep.reload()` is enough.

Worker threads must not call `unreal.*` or `mineprep.prints`. `callback` runs on the game thread and may touch UE. Runner exceptions are reported through `mineprep.warn` (on-screen + traceback).

There is no thread pool: each `@thread` / `@asyncthread` start creates a new daemon thread. `concurrent.futures.Future` is only a result box, not a `ThreadPoolExecutor`.

## Which decorator

| Need | Decorator |
|------|-----------|
| Run once after a delay | `@delay` / `@delay(0.5)` |
| Repeat every frame or every N seconds; caller stops it | `@tick` / `@tick(0.5)` |
| Game-thread stepping / waiting, may `yield` | `@asynctask` |
| Start in the background immediately; `callback` gets the result | `@thread` |
| Wait for a background result inside `@asynctask` | `@asyncthread` + `yield from` |
| Wait until a game-thread lookup returns an object | `until` + `yield from` inside `@asynctask` |

## `@delay`

Runs once on a later ticker dispatch. `@delay` / `@delay()` / `@delay(0)` use zero delay;
that is not proof another engine frame has completed. For frame-by-frame stepping,
use `@asynctask` with `yield`.

```python
@mineprep.delay
def next_frame():
    mineprep.prints('next frame')

@mineprep.delay(0.5)
def later():
    mineprep.prints('0.5s')

next_frame()
runner = later()       # DelayRunner; runner.destroy() cancels before it fires
```

The call returns the handle immediately, **not** the wrapped function's return value.

## `@tick`

Repeats on Slate post-tick and **does not stop by itself**. Call `runner.destroy()`.

```python
@mineprep.tick              # every frame
def every_frame():
    pass

@mineprep.tick(0.5)         # about every 0.5s
def heartbeat():
    mineprep.prints('tick')

runner = heartbeat()
# runner.destroy()
```

Exceptions `warn` and the tick continues. Do not use ticker `delay=0` as a loop (same-tick busy-wait holds the GIL).

## `@asynctask`

With `yield`, the call creates `AsyncTaskRunner` and advances immediately to the
first yield (or completion/error) before returning it. Subsequent steps run on
Slate frames. Keep the first step short too; do not poll with ticker `delay=0`.

- `yield`: continue next frame
- `yield 0.5`: continue after about 0.5s
- no `yield`: ordinary function; returns the original result
- `@asynctask(callback=fn)`: on a normal finish, `fn(return_value)`; `destroy()` or a crash does not call it
- `return (yield from work())`: the parentheses are required; do not write `return yield from ...`

```python
def on_done(value):
    mineprep.prints(f'callback: {value!r}')

@mineprep.asynctask(callback=on_done)
def task():
    mineprep.prints('start')
    yield 0.5
    mineprep.prints('after 0.5s')
    return 'hello'

runner = task()   # returns immediately; callback ~0.5s later
# runner.destroy() cancels a coroutine that has not finished
```

`def task(callback=on_done)` is only a function parameter. Put the finish callback on `@asynctask(callback=...)`.

Read `runner.done`, `runner.result` and `runner.error` for completion/failure.
Currently `destroy()` closes the generator and stops polling but does not set
`done` or a cancelled status. Jobs exposing cancellation must track that state
explicitly; a pending flag alone cannot distinguish cancellation from running.

MCP `run` does not wait for later frames. A yielding task comes back as `pending`, stored on `_async`; read that on a later call. See [remote.md](remote.md).

## `until`

Generator for `yield from` inside `@asynctask`. It waits `delay` seconds (default 0.1) before the first `find()`. After a miss it waits `step` seconds (default 0.1) and tries again. `timeout` (default 5s) is that polling time and does not include `delay`. `delay=0` checks on the current tick. Any truthy result ends the wait and becomes the `yield from` result, including `True`. An invalid `unreal.Object` keeps polling. Falsy values (`None`, `False`, `0`, `''`) keep polling. Timeout calls `throw`. Pass `label` so the message is not a lambda's `<lambda>`.

```python
cam = yield from mineprep.until(
    lambda: mineprep.sequencer(seq).bindings('MC摄像机').actor(),
    label='MC摄像机',
)
```

Blueprint-created objects and newly opened sequence bindings may need another
editor frame. Use `until` when readiness is asynchronous; an already available
object needs no wait. Keep `step > 0` when relying on `until`'s timeout: its
internal counter adds `step` after each miss, so `step=0` never advances it.

## Re-entrancy (same thread)

Some UE calls re-enter Slate/ticker callbacks on the same thread. A nested
`next()` on an active generator raises `ValueError: generator already executing`.
Mineprep's runners guard against this; custom runners must avoid advancing the
same generator recursively. A `yield` separates steps, not callbacks inside one UE call.

## `@thread`

**Calling it** starts a daemon thread and returns `ThreadRunner` without `join`. The game thread watches `Future.done()` on Slate post-tick, then runs `callback`.

```python
import time

def on_done(value):
    mineprep.prints(f'callback: {value!r}')

@mineprep.thread(callback=on_done)
def demo():
    time.sleep(0.5)
    return 'from thread'

runner = demo()
# runner.destroy() cancels polling/callback only; the worker still runs to completion
```

## `@asyncthread`

The wrapper contains `yield`, so `work()` **only returns a generator; the thread has not started**. A bare `work()` does nothing. The first `next` / `yield from` / `for` calls `_submit_thread`. While waiting, it polls `Future.done()` every `step` seconds. The default `step=0` is one editor frame. `@asyncthread(step=1)` polls about once a second.

```python
import time

@mineprep.asyncthread
def work():
    time.sleep(0.5)
    return 'from thread'

@mineprep.asynctask(callback=mineprep.prints)
def task():
    mineprep.prints('task start')
    yield 1
    mineprep.prints('task after 1s')
    result = yield from work()
    return result

task()
```

Or `return (yield from work())`.

## Do not

- Call `unreal.*` or `prints` on a worker (UE 5.6+ errors if not on the game thread)
- `join()` / `Future.result()` (before `done`) / `queue.get()` / `time.sleep` in a generator on the game thread
- Use `@asyncthread` as fire-and-forget (use `@thread`)
- Put `callback=` on `def task(callback=fn)` instead of the decorator
- Spawn unbounded threads: there is no pool cap
- Poll a `Future` with `register_ticker_callback(..., 0.0)` returning `True` — same-tick busy-wait holds the GIL so the worker cannot `set_result`
- Assume a UE call inside an `@asynctask` step cannot re-enter the same runner (see **Re-entrancy** above)
