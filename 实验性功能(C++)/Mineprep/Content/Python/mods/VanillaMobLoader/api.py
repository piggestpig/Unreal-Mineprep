"""UE 主线程中的目录加载与生物资产构建；不依赖面板。"""
from dataclasses import replace
import hashlib
from pathlib import Path
import math
import time

import mineprep

from .assets import AssetStore, CACHE
from . import composition, java_models, names

_jobs = set()
_building = False


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

    @property
    def done(self):
        return self.state in ('completed', 'failed', 'cancelled')

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


def _serialized_build(operation, job):
    global _building
    # Interchange and asset rename can pump Slate. A nested build must wait.
    while _building:
        job.check()
        yield
    _building = True
    try:
        return (yield from operation(job))
    finally:
        _building = False


def _load_catalog_step(job, refresh):
    job.progress('读取生物目录')
    catalog = None if refresh else job.store.cached_catalog()
    if catalog is None:
        future = job.store.submit(job.store.refresh_catalog)
        for event in job.wait({future: None}):
            if event is None:
                yield
            else:
                catalog, _saved = event[1].result()
    return catalog


def load_catalog(*, refresh=False, cache=CACHE, stall_timeout=10,
                 on_progress=None, on_stall=None, on_done=None):
    """优先本地目录缓存；缺失或 refresh=True 时后台下载，不刷新缩略图。"""
    def operation(job):
        catalog = yield from _load_catalog_step(job, refresh)
        return dict(catalog=catalog, warnings=['目录缓存未保存'] if job.store.unsaved else [])
    return _start(operation, cache, stall_timeout, on_progress, on_stall, on_done)


def _resolve_keys(catalog, entities):
    items = [entities] if isinstance(entities, str) else list(entities)
    if not items or any(not isinstance(item, str) or not item for item in items):
        raise ValueError('请选择存在的生物英文 ID 或目录 key')
    keys = []
    for item in items:
        if item in catalog.by_key:
            keys.append(item)
            continue
        folded = item.casefold()
        matches = [entry.key for entry in catalog.entries if entry.id.casefold() == folded]
        if not matches:
            raise ValueError(f'找不到生物 ID: {item}')
        if len(matches) > 1:
            raise ValueError(f'生物 ID 不唯一，请改传完整 key: {item} -> {matches}')
        keys.append(matches[0])
    if len(set(keys)) != len(keys):
        raise ValueError('请选择存在且不重复的生物条目 key')
    return keys


def _prepare_build(catalog, keys, save_path, name, layer_expansion, random_scale,
                   prefer_java, edit_rig, conflict_policy, face='none', face_options=None):
    from mineprep.face import normalize_face_mode, normalize_face_options

    face_mode = normalize_face_mode(face)
    norm_face_opts = normalize_face_options(face_options)
    if not keys or any(k not in catalog.by_key for k in keys) or len(set(keys)) != len(keys):
        raise ValueError('请选择存在且不重复的生物条目 key')
    if conflict_policy not in ('error', 'keep_first'):
        raise ValueError('conflict_policy 须为 error 或 keep_first')
    entries = [catalog.by_key[k] for k in keys]
    explicit_name = bool(name)
    model = java_models.find(entries, mineprep.paths.glb, prefer_java)
    profile = java_models.edit_profile(model[0].name) if model else None
    rig_profile = profile if edit_rig else None
    source = 'java_glb' if model else 'cem'
    face_spec = None
    effective_face = 'none'
    face_warning = None
    if face_mode != 'none':
        if model:
            face_spec = java_models.face_spec_for(model[0])
            if face_spec is None:
                face_warning = f'表情未应用：当前尚未收录 {model[0].stem} 的五官模板'
            elif face_mode == '3d' and not face_spec.get('supports_3d', False):
                raise ValueError(f'{model[0].stem} 当前仅支持 2d 表情模式，请使用 face="2d"')
            else:
                effective_face = face_mode
        else:
            face_warning = '表情未应用：当前仅支持本地 Java GLB'
    auto_name = composition.automatic_name(entries, effective_face)
    folder, resolved_name = composition.destination(save_path, name or auto_name)
    entry = entries[0] if model else composition.aggregate_entry(entries, resolved_name, layer_expansion, random_scale)
    asset_name = resolved_name + '_Raw' if profile and not edit_rig and not explicit_name else resolved_name
    recipe = f'{entry.key}:{rig_profile}' if rig_profile else entry.key
    if effective_face != 'none':
        recipe = f'{recipe}:face_{effective_face}'
    label = ('Java GLB / FK' if rig_profile else 'Java GLB') if model else 'CEM'
    if effective_face != 'none':
        label = f'{label} / {effective_face.upper()}'
    return dict(entries=entries, folder=folder, asset_name=asset_name, model=model,
                rig_profile=rig_profile, source=source, entry=entry, recipe=recipe, label=label, keys=keys,
                face_mode=effective_face, face_spec=face_spec, face_options=norm_face_opts, face_warning=face_warning)


def _build_entity_step(job, catalog, spec, *, layer_expansion, random_scale,
                       reload, try_split_head, use_physics, rebuild_physics,
                       conflict_policy, on_conflict):
    import unreal
    from mineprep.face import FACE_META_VERSION, FACE_SPEC_VERSION, supported_face_curves
    from . import importer, java_import, physics as physics_mod

    names.register(catalog)
    entry = spec['entry']
    keys = spec['keys']
    source = spec['source']
    model = spec['model']
    folder = spec['folder']
    asset_name = spec['asset_name']
    recipe = spec['recipe']
    face_mode = spec['face_mode']
    face_spec = spec['face_spec']
    face_options = spec.get('face_options')
    face_curves = tuple(supported_face_curves(face_spec, face_mode, face_options)) if face_mode != 'none' else ()
    display_name = str(names.text(entry.name))
    pa_snapshot = None
    if use_physics and not rebuild_physics:
        pa_snapshot = physics_mod.snapshot_existing_physics_assets(folder, asset_name)
    job.progress(str(mineprep.i18n('准备 {name} · {source}', 'Preparing {name} · {source}').format(
        name=display_name, source=spec['label'])))
    target = importer.composition_target(recipe, folder, asset_name, source, keys, reload)
    mesh = target[2]
    warnings = [spec['face_warning']] if spec.get('face_warning') else []
    raw_model_path = model[0] if model else None
    source_current = False
    if model:
        path, version = model
        path = java_models.import_source(path, job.store.cache, spec['rig_profile'],
                                         face_mode=face_mode, face_spec=face_spec, face_options=face_options)
        if mesh is not None and not reload:
            lib = unreal.EditorAssetLibrary
            face_meta_ok = (face_mode == 'none') or (lib.get_metadata_tag(mesh, FACE_META_VERSION) == FACE_SPEC_VERSION)
            source_current = (
                lib.get_metadata_tag(mesh, java_import.SOURCE_HASH) == hashlib.sha256(path.read_bytes()).hexdigest()
                and face_meta_ok
            )
    reused = (mesh is not None and not reload and (source_current if model else True))
    if reused and model and face_mode != 'none':
        from mineprep.model_assets import RECIPE as ASSET_RECIPE, SOURCE as ASSET_SOURCE, sync_face_material_slot
        if sync_face_material_slot(
            mesh, folder, asset_name,
            owner={ASSET_SOURCE: 'java_glb', ASSET_RECIPE: recipe},
            face_mode=face_mode, face_spec=face_spec, face_options=face_options,
        ) is None:
            reused = False
    if not reused:
        if model:
            job.progress(str(mineprep.i18n('导入 {name} · {source}', 'Importing {name} · {source}').format(
                name=display_name, source=spec['label'])))
            mesh = java_import.build(entry, keys, target, path, version, recipe=recipe,
                                     face_spec=face_spec, register_curves=face_curves,
                                     face_options=face_options)
        else:
            mesh, cem_warnings = yield from _build_cem(job, catalog, spec['entries'], keys, entry, target,
                                                       layer_expansion, random_scale, conflict_policy, on_conflict)
            warnings.extend(cem_warnings)
    if mesh is None:
        raise RuntimeError('未生成生物网格体')
    full_mesh = mesh
    head_mesh = None
    if try_split_head is None:
        try_split_head = bool(face_mode != 'none' and spec['rig_profile'] == 'biped')
    if try_split_head:
        if model:
            try:
                base_split_path = java_models.import_source(raw_model_path, job.store.cache, spec['rig_profile'])
                parts = java_models.split_source(base_split_path, job.store.cache,
                                                 face_mode=face_mode, face_spec=face_spec, face_options=face_options)
            except (OSError, ValueError) as exc:
                warnings.append('头身分离未应用：' + str(exc))
            else:
                lib = unreal.EditorAssetLibrary
                surfaces = {str(slot.material_slot_name): slot.material_interface for slot in full_mesh.materials}
                outputs = {}
                for part, part_path in parts.items():
                    job.check()
                    part_recipe = recipe + ':' + part
                    part_target = importer.composition_target(part_recipe, folder, asset_name + '_' + part,
                                                              source, keys, reload)
                    output = part_target[2]
                    source_hash = hashlib.sha256(part_path.read_bytes()).hexdigest()
                    part_face_ok = (
                        part != 'head' or face_mode == 'none'
                        or lib.get_metadata_tag(output, FACE_META_VERSION) == FACE_SPEC_VERSION
                    ) if output is not None else False
                    geo_current = (
                        output is not None
                        and lib.get_metadata_tag(output, java_import.SOURCE_HASH) == source_hash
                        and part_face_ok
                    )
                    mat_slots_match = (
                        output is not None
                        and all(slot.material_interface == surfaces.get(str(slot.material_slot_name))
                                for slot in output.materials)
                    )
                    if (geo_current and not reload and not mat_slots_match
                            and {str(s.material_slot_name) for s in output.materials} <= surfaces.keys()):
                        part_slots = list(output.materials)
                        for s in part_slots:
                            s.material_interface = surfaces[str(s.material_slot_name)]
                        output.set_editor_property('materials', part_slots)
                        if not lib.save_loaded_asset(output):
                            raise RuntimeError('Failed to save ' + output.get_path_name())
                        mat_slots_match = True
                    current = geo_current and mat_slots_match
                    reused = reused and current and not reload
                    if not current or reload:
                        job.progress(str(mineprep.i18n('导入 {name} · {source}', 'Importing {name} · {source}').format(
                            name=display_name, source=part)))
                        output = java_import.build(
                            entry, keys, part_target, part_path, version,
                            recipe=part_recipe, shared_materials=surfaces,
                            face_spec=face_spec if part == 'head' else None,
                            register_curves=face_curves if part == 'head' else (),
                            face_options=face_options if part == 'head' else None,
                        )
                    outputs[part] = output
                mesh, head_mesh = outputs['body'], outputs['head']
        else:
            warnings.append('头身分离未应用：当前仅支持本地 Java GLB')
    rig_profile = spec['rig_profile']
    phys_info = physics_mod.ensure_entity_physics(
        full_mesh,
        body_mesh=mesh if mesh != full_mesh else None,
        head_mesh=head_mesh,
        asset_name=asset_name,
        folder=folder,
        rig_profile=rig_profile,
        physics=use_physics,
        rebuild_physics=rebuild_physics,
        save=True,
        pre_reload_snapshot=pa_snapshot,
    )
    warnings.extend(phys_info['warnings'])
    return dict(mesh=mesh, warnings=warnings, path=mesh.get_path_name(), name=display_name,
                full_mesh=full_mesh, head_mesh=head_mesh,
                physics_asset=phys_info['physics_asset'],
                head_physics_asset=phys_info['head_physics_asset'],
                reused=reused, source=source, rig_profile=rig_profile, face_mode=face_mode)


def build_entity(catalog, entry_keys, *, save_path=composition.DEFAULT_SAVE_PATH, name='',
                 layer_expansion=0.01, random_scale=0.001, reload=False,
                 prefer_java=True, edit_rig=True, try_split_head=None, face='none', face_options=None,
                 physics=True, rebuild_physics=False,
                 conflict_policy='error', cache=CACHE, stall_timeout=10,
                 on_progress=None, on_conflict=None, on_stall=None, on_done=None):
    """构建/复用资产，不放置 Actor。未显式传 try_split_head 时，人形启用表情默认头身分离，四足/其他默认一体模型。"""
    from mineprep.face import normalize_face_mode

    face_mode = normalize_face_mode(face)
    split_head_flag = None if try_split_head is None else bool(try_split_head)
    keys = [entry_keys] if isinstance(entry_keys, str) else list(entry_keys)
    spec = _prepare_build(catalog, keys, save_path, name, layer_expansion, random_scale,
                          prefer_java, edit_rig, conflict_policy, face=face_mode, face_options=face_options)

    def operation(job):
        return (yield from _build_entity_step(
            job, catalog, spec,
            layer_expansion=layer_expansion, random_scale=random_scale,
            reload=reload, try_split_head=split_head_flag,
            use_physics=physics, rebuild_physics=rebuild_physics,
            conflict_policy=conflict_policy, on_conflict=on_conflict,
        ))
    return _start(lambda job: _serialized_build(operation, job), cache, stall_timeout, on_progress, on_stall, on_done)


def spawn(entity, *, catalog=None, refresh=False, scale=1.0, target=None, label=None,
          save_path=composition.DEFAULT_SAVE_PATH, name='',
          layer_expansion=0.01, random_scale=0.001, reload=False,
          prefer_java=True, edit_rig=True, try_split_head=None, face='none', face_options=None,
          physics=True, rebuild_physics=False,
          conflict_policy='error', cache=CACHE, stall_timeout=10,
          on_progress=None, on_conflict=None, on_stall=None, on_done=None):
    """按英文 ID（或目录 key / 组合列表）在内部完成目录查找、构建并放置 Actor，返回任务句柄。"""
    import unreal
    from mineprep.face import normalize_face_mode, normalize_face_options
    from . import importer

    face_mode = normalize_face_mode(face)
    norm_face_opts = normalize_face_options(face_options)
    split_head_flag = None if try_split_head is None else bool(try_split_head)
    scale = float(scale)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('Scale must be positive')
    if conflict_policy not in ('error', 'keep_first'):
        raise ValueError('conflict_policy 须为 error 或 keep_first')
    if isinstance(target, unreal.Vector):
        target = (target, False)
    resolved_spec = None
    if catalog is not None:
        resolved_keys = _resolve_keys(catalog, entity)
        resolved_spec = _prepare_build(catalog, resolved_keys, save_path, name,
                                       layer_expansion, random_scale, prefer_java, edit_rig, conflict_policy,
                                       face=face_mode, face_options=norm_face_opts)
    else:
        items = [entity] if isinstance(entity, str) else list(entity)
        if not items or any(not isinstance(item, str) or not item for item in items):
            raise ValueError('请选择存在的生物英文 ID 或目录 key')

    def operation(job):
        active_catalog = catalog if catalog is not None else (yield from _load_catalog_step(job, refresh))
        spec = resolved_spec or _prepare_build(
            active_catalog, _resolve_keys(active_catalog, entity),
            save_path, name, layer_expansion, random_scale, prefer_java, edit_rig, conflict_policy,
            face=face_mode, face_options=norm_face_opts,
        )
        result = yield from _build_entity_step(
            job, active_catalog, spec,
            layer_expansion=layer_expansion, random_scale=random_scale,
            reload=reload, try_split_head=split_head_flag,
            use_physics=physics, rebuild_physics=rebuild_physics,
            conflict_policy=conflict_policy, on_conflict=on_conflict,
        )
        job.progress(str(mineprep.i18n('放置 {name}', 'Placing {name}').format(name=result['name'])))
        actor = importer.place(result['mesh'], scale=scale, target=target, head_mesh=result['head_mesh'])
        if label is not None:
            actor.set_actor_label(str(label))
        return dict(result, actor=actor)

    return _start(lambda job: _serialized_build(operation, job), cache, stall_timeout, on_progress, on_stall, on_done)


def _build_cem(job, catalog, entries, keys, entry, target, expansion, random_scale, conflict_policy, on_conflict):
    from . import importer, skeletal

    skeletal.prerequisites()
    warnings = []
    models = [catalog.model_data(e) for e in entries]
    skins = [None] * len(entries)
    futures = {job.store.submit(job.store.skin, e.id): i for i, e in enumerate(entries) if not e.textureless}
    for event in job.wait(futures):
        if event is None:
            yield
            continue
        i, future = event
        try:
            skins[i] = future.result()
        except Exception as exc:
            warnings.append(str(names.text(entries[i].name)) + ': 皮肤不可用 ' + str(exc))
    future = job.store.submit(composition.combine, entries, models, skins, expansion, random_scale)
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
        material_name = importer.skin_name(owner, target[0], composition.clean_name(e.id) + '_CEM', reserved)
        reserved.add(material_name.casefold())
        path = job.store.skin_path(e.id) if not e.textureless else None
        sources.append((owner, material_name, path))
    job.progress(str(mineprep.i18n('导入 {name} · {source}', 'Importing {name} · {source}').format(
        name=names.text(entry.name), source='CEM')))
    mesh, build_warnings = skeletal.create_assets(entry, catalog.version, target, geo,
                                                  keys=keys, material_sources=sources)
    warnings.extend(build_warnings)
    if any(catalog.texture_count(e) > 1 for e in entries):
        warnings.append('每个模板仅使用主皮肤')
    if job.store.unsaved:
        warnings.append('部分缓存未保存')
    return mesh, warnings


def cancel_all():
    for job in tuple(_jobs):
        job.cancel()
