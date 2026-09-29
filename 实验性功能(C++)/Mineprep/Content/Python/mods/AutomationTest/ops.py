"""显式选择用例的编辑器队列，不打开面板或默认运行演示。"""
import inspect
import time

import mineprep
from mc_parallel import AsyncTaskRunner

from . import tests

_jobs = set()


class _Cancelled(Exception):
    pass


class RunJob:
    def __init__(self, cases, on_progress, on_done):
        self.state, self.error = 'running', None
        self.result = [dict(id=c['id'], state='pending', result=None, error=None, seconds=0.) for c in cases]
        self._current = None
        self._on_progress = on_progress
        self._runner = None
        _jobs.add(self)
        self._runner = self._run(cases, on_done)

    def status(self):
        return dict(state=self.state, result=[dict(r) for r in self.result], error=self.error)

    def cancel(self):
        if self.state != 'running':
            return
        self.state = 'cancelling'
        if self._runner and not self._runner.advancing:
            self._runner.destroy()

    def _check(self):
        if self.state == 'cancelling':
            raise _Cancelled()

    def _notify(self, row, text=None, color=None):
        if self._on_progress:
            self._on_progress(dict(row), text, color)

    def _resolve(self, value):
        self._current = value
        if inspect.isgenerator(value):
            try:
                while True:
                    self._check()
                    try:
                        delay = next(value)
                    except StopIteration as done:
                        return (yield from self._resolve(done.value))
                    yield delay
            finally:
                value.close()
        elif isinstance(value, AsyncTaskRunner):
            while not value.done:
                self._check()
                if value.gen is None:
                    raise _Cancelled()
                yield
            if value.error:
                raise RuntimeError(value.error)
            return (yield from self._resolve(value.result))
        elif callable(getattr(value, 'status', None)) and callable(getattr(value, 'cancel', None)):
            while True:
                self._check()
                status = value.status()
                state = status.get('state')
                if state == 'cancelled':
                    raise _Cancelled()
                if state == 'failed':
                    raise RuntimeError(status.get('error') or '子任务失败')
                if state == 'completed':
                    return (yield from self._resolve(status.get('result')))
                if state not in ('running', 'cancelling', 'pending'):
                    raise TypeError(f'不支持的任务状态: {state}')
                yield
        elif any(hasattr(value, attr) for attr in ('done', 'pending', '__await__', 'status', 'cancel')):
            raise TypeError(f'不支持的异步返回类型: {type(value).__name__}')
        elif value is False or isinstance(value, dict) and (value.get('ok') is False or value.get('pending') is True):
            raise RuntimeError(str(value))
        return value

    @mineprep.asynctask
    def _run(self, cases, on_done):
        try:
            yield  # 让调用方先拿到句柄，回调才开始执行。
            for spec, row in zip(cases, self.result):
                self._check()
                row['state'] = 'running'
                started = time.perf_counter()
                try:
                    self._notify(row)
                    self._check()
                    fn = spec['fn']
                    params = inspect.signature(fn).parameters
                    report = lambda text, color=None: self._notify(row, text, color)
                    value = fn(status=report) if 'status' in params or any(p.kind == p.VAR_KEYWORD for p in params.values()) else fn()
                    row['result'] = yield from self._resolve(value)
                    self._check()
                    row['state'] = 'passed'
                except _Cancelled:
                    raise
                except Exception as exc:
                    row.update(state='failed', error=f'{type(exc).__name__}: {exc}')
                finally:
                    row['seconds'] = time.perf_counter() - started
                self._current = None
                self._notify(row)
                yield
            self.state = 'failed' if any(r['state'] == 'failed' for r in self.result) else 'completed'
        except (GeneratorExit, _Cancelled):
            self.state = 'cancelled'
        except Exception as exc:
            self.state, self.error = 'failed', f'{type(exc).__name__}: {exc}'
        finally:
            if self.state in ('cancelled', 'failed') and self._current is not None:
                cancel = getattr(self._current, 'cancel', None) or getattr(self._current, 'destroy', None)
                if callable(cancel):
                    try:
                        cancel()
                    except Exception as exc:
                        self.error = f'取消子任务失败: {exc}'
            for row in self.result:
                if row['state'] in ('pending', 'running'):
                    row['state'] = 'cancelled' if self.state == 'cancelled' else 'failed'
            _jobs.discard(self)
            if on_done:
                on_done(self)


def run_cases(case_ids, *, on_progress=None, on_done=None):
    """按稳定 ID 运行，返回 RunJob；回调在 UE 主线程执行。"""
    by_id = {case['id']: case for case in tests.TESTS}
    ids = [case_ids] if isinstance(case_ids, str) else list(case_ids)
    if not ids or len(set(ids)) != len(ids) or any(key not in by_id for key in ids):
        raise ValueError('请指定非空、不重复且存在的用例 ID')
    return RunJob([by_id[key] for key in ids], on_progress, on_done)


def cancel_all():
    for job in tuple(_jobs):
        job.cancel()
