"""UE 主线程中的目录加载与生物资产构建；不依赖面板。"""
from dataclasses import replace
from types import SimpleNamespace
import math
import time

import mineprep

from .assets import AssetStore, CACHE
from . import composition

_jobs = set()


class _Cancelled(Exception):
    pass


class _Job:
    def __init__(self, operation, cache, stall_timeout, on_progress, on_stall, on_done):
        self.state, self.result, self.error = 'running', None, None
        self.store = AssetStore(cache)
        self.timeout = float(stall_timeout)
        self.on_progress, self.on_stall = on_progress, on_stall
        self._runner = None
        _jobs.add(self)
        self._runner = self._run(operation, on_done)

    def status(self):
        return dict(state=self.state, result=self.result, error=self.error)

    def cancel(self):
        if self.state != 'running':
            return
        self.state = 'cancelling'
        self.store.close()
        if self._runner and not self._runner.advancing:
            self._runner.destroy()

    def check(self):
        if self.state == 'cancelling':
            raise _Cancelled()

    def progress(self, text):
        if self.on_progress:
            self.on_progress(text)
        self.check()

    def wait(self, futures):
        pending = dict(futures)
        last = time.monotonic()
        while pending:
            self.check()
            done = [f for f in pending if f.done()]
            if done:
                last = time.monotonic()
                for future in done:
                    self.store.futures.discard(future)
                    yield pending.pop(future), future
            elif time.monotonic() - last >= self.timeout:
                if not self.on_stall or not self.on_stall():
                    raise TimeoutError(f'{self.timeout:g} 秒内没有资源处理完成')
                self.check()
                last = time.monotonic()
            else:
                yield None  # 调用方逐帧让出主线程。

    @mineprep.asynctask
    def _run(self, operation, on_done):
        try:
            yield
            self.check()
            self.result = yield from operation(self)
            self.check()
            self.state = 'completed'
        except (GeneratorExit, _Cancelled):
            self.state = 'cancelled'
        except Exception as exc:
            self.state, self.error = 'failed', f'{type(exc).__name__}: {exc}'
        finally:
            self.store.close()
            _jobs.discard(self)
            if on_done:
                on_done(self)


def _start(operation, cache, stall_timeout, on_progress, on_stall, on_done):
    if not math.isfinite(float(stall_timeout)) or float(stall_timeout) <= 0:
        raise ValueError('stall_timeout 必须为正有限数')
    return _Job(operation, cache, stall_timeout, on_progress, on_stall, on_done)


def load_catalog(*, refresh=False, cache=CACHE, stall_timeout=10,
                 on_progress=None, on_stall=None, on_done=None):
    """优先本地目录缓存；缺失或 refresh=True 时后台下载，不刷新缩略图。"""
    def operation(job):
        job.progress('读取生物目录')
        catalog = None if refresh else job.store.cached_catalog()
        if catalog is None:
            future = job.store.submit(job.store.refresh_catalog)
            for event in job.wait({future: None}):
                if event is None:
                    yield
                else:
                    catalog, _saved = event[1].result()
        return dict(catalog=catalog, warnings=['目录缓存未保存'] if job.store.unsaved else [])
    return _start(operation, cache, stall_timeout, on_progress, on_stall, on_done)


def build_entity(catalog, entry_keys, *, save_path='/Game/mc/mob/', name='',
                 layer_expansion=0.01, random_scale=0.001, reload=False,
                 conflict_policy='error', cache=CACHE, stall_timeout=10,
                 on_progress=None, on_conflict=None, on_stall=None, on_done=None):
    """构建/复用资产，不放置 Actor。冲突默认失败；keep_first 显式保留主模型骨骼。"""
    from . import importer, skeletal
    keys = [entry_keys] if isinstance(entry_keys, str) else list(entry_keys)
    if not keys or any(k not in catalog.by_key for k in keys) or len(set(keys)) != len(keys):
        raise ValueError('请选择存在且不重复的生物条目 key')
    if conflict_policy not in ('error', 'keep_first'):
        raise ValueError('conflict_policy 须为 error 或 keep_first')
    entries = [catalog.by_key[k] for k in keys]
    folder, name = composition.destination(save_path, name or composition.automatic_name(entries))
    entry = composition.aggregate_entry(entries, name, layer_expansion, random_scale)

    def operation(job):
        job.progress('准备 ' + entry.name)
        target = importer.composition_target(entry, folder, name, reload)
        mesh = target[2]
        warnings = []
        reused = mesh is not None and not reload
        if not reused:
            skeletal.prerequisites()
            models = [catalog.model_data(e) for e in entries]
            skins = [None] * len(entries)
            futures = {job.store.submit(job.store.skin, e.id): i for i,e in enumerate(entries) if not e.textureless}
            for event in job.wait(futures):
                if event is None:
                    yield
                    continue
                i, future = event
                try:
                    skins[i] = future.result()
                except Exception as exc:
                    warnings.append(f'{entries[i].name}: 皮肤不可用 {exc}')
            future = job.store.submit(composition.combine, entries, models, skins, layer_expansion, random_scale)
            for event in job.wait({future: None}):
                if event is None:
                    yield
            geo, conflicts = future.result()
            if conflicts and conflict_policy != 'keep_first':
                if not on_conflict or not on_conflict(conflicts):
                    raise ValueError('组合骨骼冲突: ' + '; '.join(conflicts))
            job.check()
            warnings.extend(conflicts)
            sources, reserved = [], set()
            for slot in geo.materials:
                e = entries[slot['source']]
                owner = e if len(entries) == 1 else replace(e, key='skin:' + slot['digest'])
                material_name = importer.skin_name(owner, target[0], composition.clean_name(e.id), reserved)
                reserved.add(material_name.casefold())
                path = job.store.skin_path(e.id) if not e.textureless else None
                sources.append((owner, material_name, path, SimpleNamespace(single_sided=slot['single_sided'])))
            job.progress('导入 ' + entry.name)
            mesh, build_warnings = skeletal.create_assets(entry, catalog.version, target, geo,
                                                          reload=reload, material_sources=sources)
            warnings += build_warnings
            if any(catalog.texture_count(e) > 1 for e in entries):
                warnings.append('每个模板仅使用主皮肤')
            if job.store.unsaved:
                warnings.append('部分缓存未保存')
        if mesh is None:
            raise RuntimeError('未生成生物网格体')
        return dict(mesh=mesh, warnings=warnings, path=mesh.get_path_name(), name=entry.name, reused=reused)
    return _start(operation, cache, stall_timeout, on_progress, on_stall, on_done)


def cancel_all():
    for job in tuple(_jobs):
        job.cancel()
