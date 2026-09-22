import threading
import unreal
from concurrent.futures import Future
from functools import wraps
from mc_utils import warn

_active_delays = set()
_active_async = set()
_active_threads = set()
_active_ticks = set()


def _submit_thread(fn, args, kwargs):
    """在 daemon 线程中运行 fn，立刻返回 Future。子线程禁止 unreal.*。"""
    future = Future()

    def worker():
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as e:
            future.set_exception(e)

    threading.Thread(
        target=worker, daemon=True,
        name=f'mineprep.thread.{fn.__name__}').start()
    return future


class DelayRunner:
    """延迟任务句柄；destroy() 可在触发前取消。"""

    __slots__ = ('callback_handle', 'fired')

    def __init__(self):
        self.callback_handle = None
        self.fired = False

    def destroy(self):
        if self.callback_handle is not None:
            unreal.unregister_ticker_callback(self.callback_handle)
            self.callback_handle = None
        _active_delays.discard(self)


class AsyncTaskRunner:
    """asynctask 句柄；destroy() 可取消尚未跑完的协程。

    用 Slate post-tick（每帧一次）推进 generator。
    不可用 register_ticker_callback(delay=0)：同一 Tick 里会反复注册并立刻触发，
    占住 GIL，子线程 Future 无法 set_result，yield from asyncthread 会卡死。
    """

    __slots__ = (
        'gen', 'func_name', 'on_done', 'result', 'callback_handle',
        'target_wait_time', 'elapsed_time', 'advancing',
    )

    def __init__(self, gen, func_name, on_done=None):
        self.gen = gen
        self.func_name = func_name
        self.on_done = on_done
        self.result = None
        self.callback_handle = None
        self.target_wait_time = 0.0
        self.elapsed_time = 0.0
        self.advancing = False

    def start(self):
        _active_async.add(self)
        self.callback_handle = unreal.register_slate_post_tick_callback(self._tick)
        self._advance()

    def _tick(self, delta_time):
        if self.advancing:
            return
        if self.target_wait_time > 0.0:
            self.elapsed_time += delta_time
            if self.elapsed_time < self.target_wait_time:
                return
            self.elapsed_time = 0.0
            self.target_wait_time = 0.0
        self._advance()

    def _advance(self):
        if self.advancing or self.gen is None:
            return
        self.advancing = True
        try:
            yielded = next(self.gen)
            wait = float(yielded) if isinstance(yielded, (int, float)) else 0.0
            self.target_wait_time = max(0.0, wait)
            self.elapsed_time = 0.0
        except StopIteration as stop:
            self._finish(stop.value)
        except Exception as e:
            warn(f"异步任务【{self.func_name}】运行时崩溃", e)
            self.destroy()
        finally:
            self.advancing = False

    def _finish(self, result):
        self.result = result
        cb = self.on_done
        self.destroy()
        if not cb:
            return
        try:
            cb(result)
        except Exception as e:
            warn(f"异步任务【{self.func_name}】callback 崩溃", e)

    def destroy(self):
        if self.callback_handle is not None:
            unreal.unregister_slate_post_tick_callback(self.callback_handle)
            self.callback_handle = None
        gen = self.gen
        self.gen = None
        if gen is not None:
            try:
                gen.close()
            except Exception:
                pass
        _active_async.discard(self)


def delay(seconds=0.0):
    """函数装饰器，到期后执行原函数。

    @delay / @delay()：下一帧（FTSTicker delay=0）。
    @delay(0.5)：0.5 秒后。
    调用包装函数立即返回 DelayRunner，不返回原函数的结果。
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            wait = max(0.0, float(seconds))
            runner = DelayRunner()

            def tick(_delta_time):
                if runner.fired:
                    return False
                runner.fired = True
                runner.callback_handle = None
                _active_delays.discard(runner)
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    warn(f"延迟任务【{func.__name__}】运行时崩溃", e)
                return False

            _active_delays.add(runner)
            runner.callback_handle = unreal.register_ticker_callback(tick, wait)
            return runner

        return wrapper

    if callable(seconds):
        func = seconds
        seconds = 0.0
        return decorator(func)

    return decorator


class TickRunner:
    """tick 句柄；不会自动结束，destroy() 取消注册。"""

    __slots__ = ('fn', 'fn_name', 'args', 'kwargs', 'interval', 'elapsed',
                 'callback_handle', 'ticking')

    def __init__(self, fn, args, kwargs, interval):
        self.fn = fn
        self.fn_name = fn.__name__
        self.args = args
        self.kwargs = kwargs
        self.interval = max(0.0, float(interval))
        self.elapsed = 0.0
        self.callback_handle = None
        self.ticking = False

    def start(self):
        _active_ticks.add(self)
        self.callback_handle = unreal.register_slate_post_tick_callback(self._tick)

    def _tick(self, delta_time):
        if self.ticking:
            return
        if self.interval > 0.0:
            self.elapsed += delta_time
            if self.elapsed < self.interval:
                return
            self.elapsed -= self.interval
        self.ticking = True
        try:
            self.fn(*self.args, **self.kwargs)
        except Exception as e:
            warn(f"tick 任务【{self.fn_name}】运行时崩溃", e)
        finally:
            self.ticking = False

    def destroy(self):
        if self.callback_handle is not None:
            unreal.unregister_slate_post_tick_callback(self.callback_handle)
            self.callback_handle = None
        _active_ticks.discard(self)


def tick(seconds=0.0):
    """函数装饰器，在 Slate post-tick 上反复执行，不会自动停止。

    @tick / @tick()：每帧一次。
    @tick(0.5)：每隔约 0.5 秒一次。
    调用立刻返回 TickRunner；runner.destroy() 取消。
    用 Slate 每帧回调，不用 ticker delay=0（会在同一帧里空转）。
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            runner = TickRunner(func, args, kwargs, seconds)
            runner.start()
            return runner

        return wrapper

    if callable(seconds):
        func = seconds
        seconds = 0.0
        return decorator(func)

    return decorator


def asynctask(func=None, *, callback=None):
    """函数装饰器，可在内部使用 yield（秒数）延迟执行。

    yield：下一帧再继续；yield 0.5：0.5 秒后再继续。
    无 yield 时当普通函数立刻跑完并返回原结果。
    @asynctask(callback=fn)：正常结束时调用 fn(返回值)。
    提前 destroy() 或运行中崩溃不会调用 callback。
    可 yield from @asyncthread 函数：result = yield from work()。
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            gen = fn(*args, **kwargs)
            if not hasattr(gen, '__next__'):
                if callback:
                    try:
                        callback(gen)
                    except Exception as e:
                        warn(f"异步任务【{fn.__name__}】callback 崩溃", e)
                return gen
            runner = AsyncTaskRunner(gen, fn.__name__, on_done=callback)
            runner.start()
            return runner

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


class ThreadRunner:
    """thread 句柄；destroy() 只取消 callback / 轮询，子线程仍会跑完。

    用 Slate post-tick 轮询 Future.done()。不可用 register_ticker_callback(delay=0)：
    同一 Tick 里会空转占 GIL，子线程无法 set_result。
    """

    __slots__ = ('future', 'func_name', 'on_done', 'result', 'cancelled', 'callback_handle')

    def __init__(self, future, func_name, on_done=None):
        self.future = future
        self.func_name = func_name
        self.on_done = on_done
        self.result = None
        self.cancelled = False
        self.callback_handle = None

    def start(self):
        _active_threads.add(self)
        if self.future.done():
            self._collect()
            return
        self.callback_handle = unreal.register_slate_post_tick_callback(self._tick)

    def _tick(self, _delta_time):
        if self.cancelled or not self.future.done():
            return
        self._collect()

    def _collect(self):
        if self.cancelled:
            self.destroy()
            return
        self.cancelled = True
        try:
            result = self.future.result()
        except Exception as e:
            warn(f"线程任务【{self.func_name}】运行时崩溃", e)
            self.destroy()
            return
        self._finish(result)

    def _finish(self, result):
        self.result = result
        cb = self.on_done
        self.destroy()
        if not cb:
            return
        try:
            cb(result)
        except Exception as e:
            warn(f"线程任务【{self.func_name}】callback 崩溃", e)

    def destroy(self):
        self.cancelled = True
        if self.callback_handle is not None:
            unreal.unregister_slate_post_tick_callback(self.callback_handle)
            self.callback_handle = None
        _active_threads.discard(self)


def thread(func=None, *, callback=None):
    """函数装饰器，在子线程中运行原函数。

    子线程禁止调用 unreal.*（仅标准库 / numpy 等）。
    调用立刻启动线程并返回 ThreadRunner，不 join。
    需要「调用即跑、callback 收结果」时用本装饰器，不要用 @asyncthread。
    @thread(callback=fn)：任务在主线程正常结束时调用 fn(返回值)。
    提前 destroy() 或运行中崩溃不会调用 callback。
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            future = _submit_thread(fn, args, kwargs)
            runner = ThreadRunner(future, fn.__name__, on_done=callback)
            runner.start()
            return runner

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def asyncthread(func=None):
    """将函数放到后台线程执行，配合 asynctask 使用。
    
    调用后返回生成器，首次迭代才启动线程。用 yield from 等待结果，
    等待期间每帧让出执行；线程中的异常会传给调用方。
    
    @asynctask
    def task():
        result = yield from work()
    
    后台函数不能调用 unreal API。"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            future = _submit_thread(fn, args, kwargs)
            while not future.done():
                yield
            return future.result()

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


