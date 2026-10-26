"""Tile scheduling behind one interface: serial (default), threads or processes.

Generation code never knows which executor runs it. Tasks must follow the
"parallel contract" (DEVELOPMENT_GUIDE §4.1): module-level functions whose
arguments are a WorldSpec, Regions and plain values, returning NumPy arrays
or plain dataclasses. All three executors give identical results.
"""

from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, ThreadPoolExecutor, wait
import multiprocessing
import os
from pathlib import Path
import sys
import threading

from .data import check_cancel, require_int

MODES = ("serial", "threads", "processes")


class SerialExecutor:
    """Runs each task in the calling thread at submit time; no pool, no overhead."""
    mode, workers = "serial", 1

    def submit(self, fn, *args, **kwargs):
        future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:  # delivered like a pool would
            future.set_exception(exc)
        return future

    def shutdown(self):
        pass


class ThreadExecutor:
    mode = "threads"

    def __init__(self, workers):
        self.workers = workers
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="worldgen")

    def submit(self, fn, *args, **kwargs):
        return self._pool.submit(fn, *args, **kwargs)

    def shutdown(self):
        self._pool.shutdown(wait=False, cancel_futures=True)


def python_executable():
    """Interpreter for worker processes: never UnrealEditor.exe; no console on Windows."""
    candidates = []
    current = Path(sys.executable)
    if current.stem.lower().startswith("python"):
        candidates.append(current.parent)
    candidates += [Path(sys.base_prefix), Path(sys.prefix)]
    names = ("pythonw.exe", "python.exe") if os.name == "nt" else ("bin/python3", "python3")
    for directory in candidates:
        for name in names:
            if (directory / name).is_file():
                return str((directory / name).resolve())  # UE reports base_prefix relative to its cwd
    raise RuntimeError("no Python interpreter found for worker processes")


def _warm():
    import numpy  # noqa: F401 - import cost is paid once per worker
    return os.getpid()


class ProcessExecutor:
    """Spawned worker processes; keep one alive and reuse it across generations.

    Workers import this package by module path, so they must be rebuilt after a
    code reload (`shutdown`). Pack edits need no rebuild: packs reload by stamp.
    """
    mode = "processes"

    def __init__(self, workers):
        self.workers = workers
        context = multiprocessing.get_context("spawn")
        context.set_executable(python_executable())
        self._pool = ProcessPoolExecutor(max_workers=workers, mp_context=context)

    def warm(self):
        return [f.result() for f in [self._pool.submit(_warm) for _ in range(self.workers)]]

    def submit(self, fn, *args, **kwargs):
        return self._pool.submit(fn, *args, **kwargs)

    def shutdown(self):
        self._pool.shutdown(wait=False, cancel_futures=True)


_shared = {}
_shared_lock = threading.Lock()


def get_executor(mode="serial", workers=4):
    """Shared executor per (mode, workers); serial is stateless."""
    if mode not in MODES:
        raise ValueError(f"execution must be one of {MODES}")
    require_int("workers", workers, 1, 64)
    if mode == "serial":
        return SerialExecutor()
    with _shared_lock:
        executor = _shared.get((mode, workers))
        if executor is None:
            for key in [k for k in _shared if k[0] == mode]:
                _shared.pop(key).shutdown()
            executor = (ThreadExecutor if mode == "threads" else ProcessExecutor)(workers)
            _shared[(mode, workers)] = executor
        return executor


def shutdown_executors():
    """Stop pooled workers (mod unload / reload); running tasks finish on their own."""
    with _shared_lock:
        for executor in _shared.values():
            executor.shutdown()
        _shared.clear()


def run_tiles(executor, fn, tasks, *, on_result, cancel_event=None):
    """Submit fn(*task) with at most 2*workers in flight; on_result(task, value) in completion order."""
    tasks = iter(tasks)
    pending = {}
    exhausted = False
    try:
        while pending or not exhausted:
            while not exhausted and len(pending) < 2 * executor.workers:
                check_cancel(cancel_event)
                task = next(tasks, None)
                if task is None:
                    exhausted = True
                    break
                pending[executor.submit(fn, *task)] = task
            if not pending:
                break
            done, _ = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)
            check_cancel(cancel_event)
            for future in done:
                on_result(pending.pop(future), future.result())
    finally:
        for future in pending:
            future.cancel()
