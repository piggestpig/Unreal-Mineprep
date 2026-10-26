"""Editor jobs: preview / prepare / place a WorldSpec. Import is safe offline; jobs need UE.

Pure work runs on one background thread (which may fan tiles out to the chosen
executor); every UE call and every callback runs on the editor main thread.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
import hashlib
import math
import threading
from queue import SimpleQueue
from time import perf_counter
import numpy as np

from .core.data import GenerationCancelled, check_cancel, require_int
from .core.merge import MERGE_TILE, MERGE_VERSION, MODES, merge_arrays
from .core.spec import WorldSpec
from .core.pack import load_pack
from .core.tiles import MODES as EXECUTIONS, shutdown_executors
from .core.world import MAX_CELLS, MAX_INSTANCES, Overview, _GenerationInput, build_world, build_overview, check_budgets
from .storage import SAVED_DIR
from .naming import validate_output_name

BACKENDS = ('ism', 'pcg', 'niagara')
from mc_structure_tex import ENCODING_VERSION
from mc_math import TYPE_GROUP_VERSION
RESOURCE_VERSION = 'wg-resource-11-tree-scale'
PREVIEW_VERSION = 'r36-volume-floor-decor-1'
OVERVIEW_VERSION = 'reference-overview-2'


def _complete_textures(job, output, meshes, textures):
    pending=output.unready_textures(meshes,textures)
    if pending:
        job.progress('完成纹理构建 / Completing textures')
        native=output.native_texture_finish()
        if native is None:
            frame=_editor().SystemLibrary.get_frame_count()
            while _editor().SystemLibrary.get_frame_count()==frame:
                check_cancel(job.event)
                yield
        for texture in pending:
            check_cancel(job.event)
            output.finish_texture(texture,native)
    remaining=output.unready_textures(meshes,textures)
    for texture in remaining:
        job.warnings.append('纹理仍未就绪 / texture still not ready: '+texture.get_path_name())
    return remaining


_jobs = set()
_executor = None
_world_cache = {}     # world key -> World (most recent two)
_prepared_cache = {}  # (resource key, backend, type group count, BCT key), most recent two
_pumping = False      # UE calls may re-enter Slate; never interleave two jobs' steps.
PHASE_TEXT = {
    'heightmap': '读取自定义高度图 / Reading custom heightmap',
    'planning': '规划与初始化 / Planning and initialization',
    'reference': '计算参考地形 / Reference terrain',
    'reference_publish': '绘制参考预览 / Drawing reference preview',
    'entities': '生成实体 / Generating entities',
    'assembly': '组装结果与模型索引 / Assembling results and model index',
    'column_features': '生成列景观 / Column features',
    'surface_processing': '处理积雪与表面 / Surface processing',
    'finalize': '检查生成结果 / Checking results',
}


def _editor():
    import unreal
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError('WorldGenerator operations must start on the editor main thread')
    return unreal


def _submit(fn, *args, **kwargs):
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='worldgen')
    return _executor.submit(fn, *args, **kwargs)


def _remember(cache, key, value, limit=2):
    cache.pop(key, None)
    cache[key] = value
    while len(cache) > limit:
        del cache[next(iter(cache))]


class Job:
    """Main-thread callbacks, terminal state exactly once, no UI ownership."""
    def __init__(self, operation, on_progress=None, on_done=None, *, on_stage=None, _schedule=True, pack=None):
        self.state, self.result, self.error = 'running', None, None
        self._pack = pack  # main-process lease; never part of worker requests
        self.stage, self.warnings = 'queued', []
        self.event = threading.Event()
        self._advancing = self._committing = False
        self._handle = None
        self._report = None  # written by the worker thread, forwarded on the main thread
        self._source_check = None  # editor-only lease, installed by the panel before the first step
        self._started = False
        self._on_progress, self._on_done = on_progress, on_done
        self._on_stage, self._stages = on_stage, SimpleQueue()
        self._operation = operation(self)
        _jobs.add(self)
        if _schedule:
            self._handle = _editor().register_slate_post_tick_callback(self._advance)

    def status(self):
        return dict(state=self.state, stage=self.stage, result=self.result,
                    error=self.error, warnings=list(self.warnings))

    def progress(self, text):
        self.stage = text
        if self._on_progress:
            try:
                self._on_progress(text)
            except Exception as exc:
                self.warnings.append(f'progress callback: {exc}')
        check_cancel(self.event)

    def report(self, text):
        """Thread-safe progress from worker code; shown on the next editor tick."""
        self._report = text

    def check_source(self):
        if self._source_check is not None:
            self._source_check()
        if getattr(self, '_mask_pack', None) is not None:
            from .core.masks import check_sources
            check_sources(self._mask_pack)

    def publish_stage(self, name, result):
        self._stages.put((name, result))

    def _drain_stages(self):
        while not self._stages.empty():
            name, result = self._stages.get()
            if self._on_stage and not self.event.is_set():
                self.check_source()
                try:
                    self._on_stage(name, result)
                except Exception as exc:
                    self.warnings.append(f'stage callback: {exc}')

    def wait(self, future):
        try:
            while not future.done():
                check_cancel(self.event)
                self._drain_stages()
                report, self._report = self._report, None
                if report:
                    self.progress(report)
                yield
            check_cancel(self.event)
            self.check_source()
            self._drain_stages()
            report, self._report = self._report, None
            if report:
                self.progress(report)
            return future.result()
        finally:
            if self.event.is_set():
                future.cancel()

    def cancel(self):
        if self.state not in ('running', 'cancelling') or self._committing:
            return False
        self.state = 'cancelling'
        self.event.set()
        if not self._advancing:
            self._advance(0)
        return True

    def _advance(self, _delta):
        global _pumping
        if _pumping or self._advancing or self.state not in ('running', 'cancelling'):
            return
        _pumping = True
        self._advancing = True
        try:
            check_cancel(self.event)
            if not self._started:
                self.check_source()
                self._started = True
            next(self._operation)
        except StopIteration as stop:
            try:
                self.check_source()
                self.result, self.state = stop.value, 'completed'
            except Exception as exc:
                self.state, self.error = 'failed', f'{type(exc).__name__}: {exc}'
                self.event.set()
        except GenerationCancelled:
            self.state = 'cancelled'
        except Exception as exc:
            self.state, self.error = 'failed', f'{type(exc).__name__}: {exc}'
            self.event.set()
            self.result = getattr(exc, 'result', None)
        finally:
            self._advancing = False
            if self.state in ('completed', 'failed', 'cancelled'):
                try:
                    self._operation.close()
                except Exception as exc:
                    self.warnings.append(f'job cleanup: {exc}')
                if self._handle is not None:
                    try:
                        _editor().unregister_slate_post_tick_callback(self._handle)
                    except Exception as exc:
                        self.warnings.append(f'callback cleanup: {exc}')
                    self._handle = None
                _jobs.discard(self)
                self._pack = None
                if self._on_done:
                    try:
                        self._on_done(self)
                    except Exception as exc:
                        self.warnings.append(f'completion callback: {exc}')
                self._source_check = None
            _pumping = False


@dataclass(frozen=True)
class PreparedGroup:
    type_ids: tuple       # indices into the shared model table, in original order
    instance_count: int
    key: str
    textures: tuple       # this group's matching BPT/BRT pair


@dataclass(frozen=True)
class PreparedWorld:
    key: str
    backend: str
    world: object          # core.world.World (maps, pack, params, stats)
    data: object           # WorldArrays after merging
    meshes: tuple
    textures: tuple
    actor_class: object
    seconds: float
    reused: bool = False
    merge: str = 'none'
    merge_seconds: float = 0.0
    mesh_keys: tuple = ()  # Full imported source identities, aligned with meshes; None for UE sources.
    biome_texture: object = None  # BCT, independent of the BPT/BRT pair
    biome_key: str = ''
    biome_enabled: bool = True
    biome_cell_size: int = 4
    biome_seconds: float = 0.0
    biome_import_seconds: float = 0.0
    vegetation_tints: tuple = ()  # frozen (biome ID, linear RGB) pairs
    chunk_count: int = 1
    base_reused: bool = False
    type_group_count: int = 1
    type_groups: tuple = ()  # PreparedGroup; textures is their flattened resource list
    block_materials: tuple = ()  # effective (logical block ID, scalar overrides)
    biome_color_mode: str = 'rgb'
    vegetation_hsv: tuple = ()  # frozen positive HSV adjustments; 1/1/1 is neutral
    biome_color_power: float = 1.

    @property
    def all_textures(self):
        return self.textures + ((self.biome_texture,) if self.biome_texture is not None else ())

    @property
    def spec(self):
        return self.world.spec

    @property
    def visible_count(self):
        return self.data.visible_count if self.data.visible_count is not None else self.data.count

    @property
    def instance_count(self):
        return self.data.count


@dataclass(frozen=True)
class PreviewResult:
    key: str
    world: object
    images: dict           # view name -> PNG path (RGB)
    seconds: float
    stats: dict = field(default_factory=dict)
    sections: tuple = None  # (MC Z, MC Y, optional MC X planes)


@dataclass(frozen=True)
class OverviewResult:
    key: str
    overview: object
    images: dict
    seconds: float
    stats: dict


def resource_key(world_key_, merge, fingerprint=''):
    return hashlib.sha256(f'{world_key_}:{ENCODING_VERSION}:{MERGE_VERSION}:{MERGE_TILE}:{merge}:{RESOURCE_VERSION}:{fingerprint}'
                          .encode()).hexdigest()


def _check_request(spec, execution, workers, max_cells, max_instances):
    from .core.scene import Scene, SceneInput
    if isinstance(spec, Scene):
        if execution not in EXECUTIONS:
            raise ValueError(f'execution must be one of {EXECUTIONS}')
        require_int('workers', workers, 1, 64)
        check_budgets(spec.world.spec, max_cells, max_instances)
        return SceneInput(spec)
    if not isinstance(spec, WorldSpec):
        raise ValueError('spec must be a WorldSpec (see api.spec)')
    if execution not in EXECUTIONS:
        raise ValueError(f'execution must be one of {EXECUTIONS}')
    require_int('workers', workers, 1, 64)
    check_budgets(spec, max_cells, max_instances)
    return _GenerationInput.capture(spec, defer_heightmap=True)


def _check_preprocessing(request, limit):
    if limit is None:
        return
    require_int('max_preprocess_cells', limit, 1, 2**40)
    from .core.scene import SceneInput
    params = (request.scene.world.params if isinstance(request, SceneInput) else
              request.pack.resolve(request.spec))
    height = params['world.y_max'] - params['world.y_min']
    region = request.spec.region
    count = region.cells * height
    if count > limit:
        raise ValueError(f'preprocessing {region.width}×{region.depth}×{height}={count:,} '
                         f'exceeds max_preprocess_cells={limit:,}')


def _resolve_input(job, request):
    if not request.key:
        request = yield from job.wait(_submit(request.resolved, job.event))
    job._mask_pack = request.pack
    return request


def _world(job, request, execution, workers, max_cells, max_instances, on_stage=None):
    """Generator: cached World or one built on the worker thread."""
    from .core.scene import SceneInput
    if isinstance(request, SceneInput):
        job.progress('检查场景组合 / Checking scene composition')
        return (yield from job.wait(_submit(request.validate, max_cells, max_instances, job.event)))
    cached = _world_cache.get(request.key)
    if cached is None:
        cached = next((p.world for p in reversed(tuple(_prepared_cache.values()))
                       if p.world.key == request.key), None)
    if cached is not None:
        count=cached.arrays.count+len(cached.model_instances)
        if count > max_instances:
            raise ValueError(f'output records {count:,} exceed max_instances={max_instances:,}')
        pack = request.pack
        job.progress('复用已有结果 / Reusing world result')
        if (cached.spec == request.spec and cached.pack.fingerprint == pack.fingerprint
                and (request.heightmap_source is None or
                     cached.pack.heightmap.source.stamp == request.heightmap_source.stamp)
                and all(cached.pack.masks[k].source.stamp == v.source.stamp
                        for k,v in (pack.masks or {}).items())):
            return cached
        return replace(cached,spec=request.spec,pack=pack,params=pack.resolve(request.spec))
    def report_phase(name):
        job.report(PHASE_TEXT[name])

    job.progress(PHASE_TEXT['planning'])
    world = yield from job.wait(_submit(
        build_world, request.spec, _input=request, execution=execution, workers=workers, cancel_event=job.event,
        max_cells=max_cells, max_instances=max_instances,
        on_stage=on_stage, on_phase=report_phase,
        progress=lambda done, total: job.report(f'{PHASE_TEXT["entities"]} / Tiles {done}/{total}')))
    return world


def preview_overview(spec, *, execution='serial', workers=4, max_cells=MAX_CELLS,
                     on_progress=None, on_done=None, views=('landscape',), overview=None):
    """Editor image job backed only by exact references; holds no complete World cache."""
    _editor()
    if overview is not None and not isinstance(overview,Overview):
        raise ValueError('overview must be an Overview, not a complete World')
    request = _check_request(spec, execution, workers, max_cells, MAX_INSTANCES)
    from .adapters.preview import overview_views, write_overview_views
    names = (views,) if isinstance(views,str) else tuple(views)
    pack = request.pack
    if any(n not in overview_views(pack) for n in names):
        raise ValueError('this view requires a full preview or an available reference field')
    folder = SAVED_DIR / 'preview' / request.key[:24] / OVERVIEW_VERSION
    def operation(job):
        nonlocal request, folder
        started = perf_counter()
        request = yield from _resolve_input(job, request)
        folder = SAVED_DIR / 'preview' / request.key[:24] / OVERVIEW_VERSION
        data = overview
        keep = tuple(n for n in overview_views(pack) if n in ('temperature','humidity'))
        if (data is None or data.key != request.key or data.pack.fingerprint != request.fingerprint
                or any(n not in data.fields for n in keep)):
            job.progress('参考概览 / Reference overview')
            data = yield from job.wait(_submit(build_overview, spec, _input=request,
                execution=execution, workers=workers, max_cells=max_cells, keep_fields=keep,
                cancel_event=job.event,
                progress=lambda done,total: job.report(f'参考概览 / Tiles {done}/{total}')))
        def draw():
            draw_started = perf_counter()
            images = write_overview_views(data, folder, names)
            return images, perf_counter()-draw_started
        images, seconds = yield from job.wait(_submit(draw))
        return OverviewResult(request.key,data,images,seconds,
                              dict(total_wait_seconds=perf_counter()-started, draw_seconds=seconds))
    return Job(operation,on_progress,on_done,pack=pack)


def preview_world(spec, *, execution='serial', workers=4, max_cells=MAX_CELLS,
                  max_instances=MAX_INSTANCES, on_progress=None, on_done=None, views=None, on_stage=None,
                  max_preprocess_cells=None):
    """Generate (or reuse) a World and write RGB preview PNGs; touches no scene data."""
    _editor()
    request = _check_request(spec, execution, workers, max_cells, max_instances)
    _check_preprocessing(request, max_preprocess_cells)
    key = request.key
    folder = SAVED_DIR / 'preview' / key[:24] / PREVIEW_VERSION
    from .adapters.preview import VIEWS
    names = tuple(n for n in VIEWS if n not in ('heightmap','vegetation_mask','clearance_mask')
                  or getattr(spec,n) is not None) if views is None else (views,) if isinstance(views, str) else tuple(views)
    if any(n not in VIEWS for n in names):
        raise ValueError('unknown preview view')

    def operation(job):
        nonlocal request, key, folder
        started = perf_counter()
        request = yield from _resolve_input(job, request)
        key = request.key
        folder = SAVED_DIR / 'preview' / key[:24] / PREVIEW_VERSION
        metrics = {}
        def stage(name, reference):
            from .adapters.preview import write_views
            draw = perf_counter()
            images = write_views(reference,folder/'reference',names=('landscape',))
            seconds = perf_counter()-draw
            metrics.update(first_image_seconds=perf_counter()-started, reference_draw_seconds=seconds)
            job.publish_stage(name,PreviewResult(key,reference,images,seconds,dict(metrics)))
        world = yield from _world(job, request, execution, workers, max_cells, max_instances,
                                  stage if on_stage is not None else None)
        job.progress('写入预览图 / Writing preview images')
        from .adapters.preview import write_views, cave_positions3
        def write():
            draw = perf_counter()
            positions = cave_positions3(world) if 'cave_sections' in names and world.pack.density is not None else None
            existing = {n:str(folder/f'{n}.png') for n in names if (folder/f'{n}.png').is_file()}
            images = {**existing,**write_views(world, folder, names=tuple(n for n in names if n not in existing), cave_positions_=positions)}
            return images, positions, perf_counter()-draw
        images, positions, seconds = yield from job.wait(_submit(write))
        job.check_source()
        _remember(_world_cache, key, world)
        metrics.update(total_wait_seconds=perf_counter()-started, draw_seconds=seconds)
        return PreviewResult(key, world, images, seconds, {**world.stats,**metrics}, positions)
    return Job(operation, on_progress, on_done, on_stage=on_stage, pack=request.pack)


@dataclass(frozen=True)
class HeightmapPreview:
    spec: WorldSpec
    key: str
    data: object
    images: dict
    info: dict
    seconds: float


def preview_heightmap(spec, *, snapshot=None, max_cells=MAX_CELLS,
                      on_progress=None, on_done=None):
    """Read/map/draw input only. No terrain fields, planners or entity generation."""
    _editor()
    request = _check_request(spec, 'serial', 1, max_cells, MAX_INSTANCES)
    if spec.heightmap is None:
        raise ValueError('enable a heightmap before previewing it')
    pack = request.pack
    def operation(job):
        nonlocal request
        started = perf_counter()
        from .core.heightmap import snapshot as input_snapshot
        from .adapters.preview import heightmap_rgb
        def draw():
            nonlocal request
            reused = snapshot is not None and snapshot.spec.heightmap == spec.heightmap
            if reused:
                from .core.world import world_key
                data = snapshot.data
                key = world_key(spec, pack, _source=data.source)
            else:
                job.report(PHASE_TEXT['heightmap'])
                request = request.resolved(job.event)
                data = input_snapshot(spec.heightmap, request.heightmap_source)
                key = request.key
            params = pack.resolve(spec)
            rgb = heightmap_rgb(data, spec.region, params)
            check_cancel(job.event)
            folder = SAVED_DIR / 'preview' / key[:24] / 'heightmap'
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / 'heightmap.png'
            import cv2
            if not cv2.imwrite(str(path), rgb[..., ::-1]):
                raise ValueError('cannot write heightmap preview')
            return HeightmapPreview(spec, key, data, {'heightmap': str(path)},
                                    data.info(params), perf_counter() - started)
        return (yield from job.wait(_submit(draw)))
    return Job(operation, on_progress, on_done, pack=pack)


def preview_mask(spec, kind, *, on_progress=None, on_done=None):
    """Decode and draw one mapped input without generating terrain or scenery."""
    _editor()
    from .core import masks
    from .core.heightmap import capture, decoded, input_key
    if kind not in masks.KINDS or getattr(spec, kind+'_mask') is None:
        raise ValueError('select and enable a mask')
    config = getattr(spec, kind+'_mask')
    def operation(job):
        def draw():
            started = perf_counter()
            source = capture(config, cancel_event=job.event)
            image = decoded(source)
            if np.any((image.values < 0) | (image.values > 1)):
                raise ValueError('mask pixels must be in [0,1]')
            data = masks.Mask(config, source, image.values, kind)
            from .adapters.preview import mask_rgb
            rgb = mask_rgb(data, spec.region)
            key = input_key(config, source)
            folder = SAVED_DIR / 'preview' / key[:24] / (kind+'_mask')
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / 'input.png'
            import cv2
            if not cv2.imwrite(str(path), rgb[..., ::-1]):
                raise ValueError('cannot write mask preview')
            source.checked()
            return HeightmapPreview(spec, key, data, {kind+'_mask': str(path)}, {}, perf_counter()-started)
        return (yield from job.wait(_submit(draw)))
    return Job(operation, on_progress, on_done, pack=load_pack(spec.pack))


def preview_landscape(world, *, max_y, on_progress=None, on_done=None):
    """Image-only request: never generates, prepares or changes the World key."""
    _editor()
    request = _GenerationInput.capture(world.spec, defer_heightmap=True)
    require_int('preview height', max_y, world.params['world.y_min'], world.params['world.y_max'] - 1)
    folder = SAVED_DIR / 'preview' / world.key[:24] / PREVIEW_VERSION / f'landscape_{max_y}'
    def operation(job):
        nonlocal request
        request = yield from _resolve_input(job, request)
        if request.key != world.key:
            raise ValueError('world is outdated; regenerate its preview')
        from .adapters.preview import volume_landscape, write_png
        started = perf_counter()
        def draw():
            return {'landscape': write_png(folder / 'landscape.png', volume_landscape(world, max_y))}
        images = yield from job.wait(_submit(draw))
        job.check_source()
        return PreviewResult(world.key, world, images, perf_counter() - started, dict(world.stats))
    return Job(operation, on_progress, on_done, pack=world.pack)


def preview_sections(world, *, at_z, at_y, at_x=None, on_progress=None, on_done=None):
    """Reuse a generated World. Slice coordinates do not affect resource caches."""
    _editor()
    request = _GenerationInput.capture(world.spec, defer_heightmap=True)
    if world.spec.heightmap is None and request.key != world.key:
        raise ValueError('world is outdated; regenerate its preview')
    r, p = world.region, world.params
    require_int('at_z', at_z, r.z0, r.z0 + r.depth - 1)
    require_int('at_y', at_y, p['world.y_min'], p['world.y_max'] - 1)
    at_x = r.x0 + r.width // 2 if at_x is None else at_x
    require_int('at_x', at_x, r.x0, r.x0 + r.width - 1)
    positions = (at_z, at_y, at_x)
    folder = SAVED_DIR / 'preview' / world.key[:24] / PREVIEW_VERSION / f'sections_{at_z}_{at_y}_{at_x}'
    def operation(job):
        nonlocal request
        started = perf_counter()
        request = yield from _resolve_input(job, request)
        if request.key != world.key:
            raise ValueError('world is outdated; regenerate its preview')
        from .adapters.preview import write_views
        job.progress('更新洞穴剖面 / Updating cave sections')
        images = yield from job.wait(_submit(write_views, world, folder, names=('cave_sections',), cave_positions_=positions))
        return PreviewResult(world.key, world, images, perf_counter() - started, dict(world.stats), positions)
    return Job(operation, on_progress, on_done, pack=world.pack)


def prepare_world(spec, *, backend='pcg', merge='cuboids', execution='serial', workers=4,
                  max_cells=MAX_CELLS, max_instances=MAX_INSTANCES, on_progress=None, on_done=None,
                  refresh_resources=False, name='World', biome_texture=True, biome_cell_size=4,
                  chunk_count=1, type_group_count=1, vegetation_tints=None, block_materials=None,
                  biome_color_mode='rgb', vegetation_hsv=None, biome_color_power=1.,
                  max_preprocess_cells=None, max_output_instances=None):
    """Prepare reusable data/assets for a spec; creates no Actor. backend: ism/pcg/niagara."""
    _editor()
    if backend not in BACKENDS:
        raise ValueError(f'backend must be one of {BACKENDS}')
    name = validate_output_name(name)
    if merge not in MODES:
        raise ValueError(f'merge must be one of {MODES}')
    if type(biome_texture) is not bool:
        raise ValueError('biome_texture must be true/false')
    require_int('biome_cell_size', biome_cell_size, 1, 16)
    request = _check_request(spec, execution, workers, max_cells, max_instances)
    _check_preprocessing(request, max_preprocess_cells)
    if max_output_instances is not None:
        require_int('max_output_instances', max_output_instances, 1, 2**40)
    require_int('chunk_count', chunk_count, 1, request.spec.region.cells)
    require_int('type_group_count', type_group_count, 1, 2**31 - 1)
    chunk_count = chunk_count if backend == 'ism' else 1
    type_group_count = type_group_count if backend != 'ism' else 1
    biome_texture = biome_texture and (backend != 'ism' or chunk_count == 1)
    from .adapters import biome_texture as bct
    biome_color_power = bct.colour_power(biome_color_power)
    pack = request.pack
    tints = bct.palette(pack, vegetation_tints)
    hsv = bct.palette(pack, vegetation_hsv, biome_color_mode='hsv')
    if biome_color_mode not in ('rgb', 'hsv'):
        raise ValueError("biome_color_mode must be 'rgb' or 'hsv'")
    colours = tints if biome_color_mode == 'rgb' else hsv
    if biome_texture:
        bct.dimensions(request.spec.region, biome_cell_size)
    key = request.key
    from .adapters import mineprep_output as output
    from .adapters.resources import ResourceSnapshot
    from .core.scene import SceneInput
    # Freeze external dependencies at entrance, before any worker or import starts.
    resource_options = dict(block_materials=block_materials)
    if isinstance(request, SceneInput):
        # Logical stairs/fences are expanded by the shared template resolver;
        # they need not have a same-named model JSON of their own.
        resource_options['used_blocks'] = request.scene.world.arrays.names
    resources = ResourceSnapshot.capture(
        request.pack, output.model_directory(), **resource_options)

    def operation(job):
        nonlocal request, key
        from .adapters import mineprep_output as output
        started = perf_counter()
        request = yield from _resolve_input(job, request)
        key = request.key
        actor_class = output.prepare_class(backend)
        world = yield from _world(job, request, execution, workers, max_cells, max_instances)
        template_sources = {}
        if world.model_instances:
            material_options = {name:dict(values) for name, values in resources.materials}
            template_sources = output.template_resources(world.model_instances,resources.models_dir,
                **(dict(block_names=world.pack.blocks,block_materials=material_options) if material_options else {}))
        used_key=':'.join(r.fingerprint for _,r in sorted(template_sources.items()))
        actual_key=resource_key(key,merge,resources.fingerprint+used_key)
        started_key = perf_counter()
        biome_key = (bct.texture_key(world, biome_cell_size, biome_color_mode=biome_color_mode,
                                   biome_color_power=biome_color_power, _palette=colours)
                     if biome_texture and (world.arrays.count or world.model_instances) else '')
        key_seconds = perf_counter() - started_key
        cache_key = (actual_key, backend, type_group_count, biome_key)
        if type_group_count > 1:
            cache_key += (TYPE_GROUP_VERSION,)
        cached = _prepared_cache.get(cache_key)
        if (cached and not refresh_resources and output.valid_prepared(cached)
                and not output.unready_textures(cached.meshes,cached.all_textures)):
            output.validate_backend(cached.data, backend, cached.type_groups)
            if cached.visible_count > max_instances:
                raise ValueError(f'visible cells {cached.visible_count:,} exceed max_instances={max_instances:,}')
            if max_output_instances is not None and cached.instance_count > max_output_instances:
                raise ValueError(f'merged instances {cached.instance_count:,} exceed max_output_instances={max_output_instances:,}')
            resources.checked()
            for source in template_sources.values():source.checked()
            pack = request.pack
            from .core.scene import SceneInput
            world = (request.scene.world if isinstance(request, SceneInput) else
                     replace(cached.world,spec=request.spec,pack=pack,params=pack.resolve(request.spec)))
            return replace(cached, world=world, actor_class=actor_class, reused=True, seconds=perf_counter() - started,
                           merge_seconds=0.0, biome_enabled=biome_texture,
                           biome_cell_size=biome_cell_size, biome_seconds=0.0, biome_import_seconds=0.0,
                           vegetation_tints=tints, vegetation_hsv=hsv, biome_color_mode=biome_color_mode,
                           biome_color_power=biome_color_power,
                           chunk_count=chunk_count, base_reused=True)
        base = None
        if not refresh_resources:
            for candidate in reversed(tuple(_prepared_cache.values())):
                if candidate.key != actual_key or candidate.backend != backend:
                    continue
                # Geometry survives a partition change or a deleted BPT/BRT/BCT.
                if (output.valid_base(candidate)
                        and not output.unready_textures(candidate.meshes, ())):
                    base = candidate
                    break
        # Keep the last completed record as a model base if a repair is cancelled.
        # Full cache hits always revalidate its complete current resource set.
        if base is not None:
            job.progress('复用准备基底 / Reusing prepared geometry')
            data, meshes, mesh_keys = base.data, base.meshes, base.mesh_keys
            merge_seconds = 0.0
        else:
            job.progress('合并可见方块 / Merging visible cells')

            def merge_data():
                merge_started = perf_counter()
                return merge_arrays(world.arrays, merge, job.event), perf_counter() - merge_started
            data, merge_seconds = yield from job.wait(_submit(merge_data))
            meshes = []
            for block_name in data.names:
                job.progress('准备模型 / Model: ' + block_name)
                check_cancel(job.event)
                meshes.append(output.prepare_mesh(resources.get(block_name),refresh=refresh_resources))
                yield
            mesh_keys=tuple(None if resources.get(b).block.source=='mesh' and not resources.get(b).block.material else
                            (resources.get(b).fingerprint,b) for b in data.names)
            if template_sources:
                import uuid
                from .core.blocks import BlockDef
                from .core.templates import append_output
                definitions={}
                pool_revision=uuid.uuid4().hex[:12] if refresh_resources else None
                for template_id,source in sorted(template_sources.items()):
                    job.progress('准备整树模型 / Template: '+template_id)
                    check_cancel(job.event)
                    mesh=output.prepare_template(source,refresh=refresh_resources,pool_revision=pool_revision)
                    meshes.append(mesh)
                    definitions[template_id]=BlockDef('template_'+template_id,'mesh',mesh.get_path_name(),
                                                       shape='decor',occludes=False,merge='none')
                    mesh_keys+=((source.fingerprint,'template_'+template_id),)
                    yield
                data=append_output(data,world.model_instances,definitions)
        if max_output_instances is not None and data.count > max_output_instances:
            raise ValueError(f'merged instances {data.count:,} exceed max_output_instances={max_output_instances:,}')
        groups = ()
        textures = ()
        texture_target = None
        if backend != 'ism' and data.count:
            def partition():
                check_cancel(job.event)
                layouts = data.type_groups(type_group_count)
                return tuple(PreparedGroup(ids, count,
                    actual_key if type_group_count == 1 else hashlib.sha256(
                        f'{actual_key}:{TYPE_GROUP_VERSION}:{ids}'.encode()).hexdigest(), ())
                    for ids, count in layouts)
            groups = yield from job.wait(_submit(partition))
            # Validate each future Actor before allocating or importing its textures.
            output.validate_backend(data, backend, groups)
            texture_target = output.texture_folder(actual_key, groups, name=name)
            folder,world_key = texture_target
            indices = None
            ready_groups = []
            previous_groups = {g.key: g for g in base.type_groups} if base is not None else {}
            for index,group in enumerate(groups,1):
                job.progress('准备结构纹理 / Structure textures')
                check_cancel(job.event)
                previous = previous_groups.get(group.key)
                if previous is not None and output.valid_group(previous,folder=folder,index=index):
                    ready_groups.append(previous)
                    continue
                pair = output.cached_textures(group.key,folder=folder,index=index)
                if not pair:
                    if indices is None:
                        indices = yield from job.wait(_submit(data.type_indices))
                    directory = SAVED_DIR / 'cache' / group.key

                    def encode():
                        from mc_structure_tex import write_structure_textures
                        check_cancel(job.event)
                        payloads = {data.names[i]: data.payload(indices[i]) for i in group.type_ids}
                        return write_structure_textures(payloads, directory)
                    files = yield from job.wait(_submit(encode))
                    job.progress('导入结构纹理 / Import textures')
                    check_cancel(job.event)
                    pair = (output.cached_textures(group.key,folder=folder,index=index)
                            or output.import_textures(files, group.key,folder=folder,index=index,world_key=world_key))
                ready_groups.append(replace(group, textures=tuple(pair)))
            groups = tuple(ready_groups)
            textures = (base.textures if base is not None and groups == base.type_groups
                        else tuple(t for group in groups for t in group.textures))
            del indices
        colour_texture = None
        colour_seconds = import_seconds = 0.0
        if biome_key:
            job.progress('准备群系颜色纹理 / Biome colour texture')
            if texture_target is None:
                texture_target = output.texture_folder(actual_key, groups, name=name)
            folder,world_key = texture_target
            colour_texture = output.cached_biome_texture(biome_key,folder=folder)
            if colour_texture is None:
                job.progress('生成群系颜色 / Generating biome colours')
                files = yield from job.wait(_submit(bct.write, world,
                    SAVED_DIR / 'cache' / biome_key / 'structure_BCT.exr',
                    cell_size=biome_cell_size, biome_color_mode=biome_color_mode,
                    biome_color_power=biome_color_power,
                    cancel=job.event, _palette=colours, _key=biome_key))
                colour_seconds = files['seconds'] + key_seconds
                job.progress('导入群系纹理 / Importing biome texture')
                started_import = perf_counter()
                colour_texture = (output.cached_biome_texture(biome_key,folder=folder)
                                  or output.import_biome_texture(files,folder=folder,world_key=world_key))
                import_seconds = perf_counter() - started_import
        check_cancel(job.event)
        all_textures = tuple(textures or ()) + ((colour_texture,) if colour_texture is not None else ())
        unready=yield from _complete_textures(job,output,tuple(meshes),all_textures)
        check_cancel(job.event)
        resources.checked()
        for source in template_sources.values():source.checked()
        if (data.visible_count if data.visible_count is not None else data.count) > max_instances:
            raise ValueError(f'visible cells exceed max_instances={max_instances:,}')
        result = PreparedWorld(actual_key, backend, world, data, tuple(meshes), tuple(textures or ()),
                               actor_class, perf_counter() - started, merge=merge,
                               merge_seconds=merge_seconds,
                               mesh_keys=mesh_keys, biome_texture=colour_texture, biome_key=biome_key,
                               biome_enabled=biome_texture, biome_cell_size=biome_cell_size,
                               biome_seconds=colour_seconds, biome_import_seconds=import_seconds,
                               vegetation_tints=tints, vegetation_hsv=hsv, biome_color_mode=biome_color_mode,
                               biome_color_power=biome_color_power,
                               chunk_count=chunk_count, base_reused=base is not None,
                               type_group_count=type_group_count, type_groups=groups,
                               block_materials=resources.materials)
        if not output.valid_prepared(result):
            raise RuntimeError('prepared resource references are invalid')
        job.check_source()
        _remember(_world_cache, key, world)
        if not unready:_remember(_prepared_cache,cache_key,result)
        return result
    return Job(operation, on_progress, on_done, pack=request.pack)


def place_world(prepared, *, location=(0, 0, 0), chunk_count=None,
                name='World', on_progress=None, on_done=None):
    """Add Actors in one undo transaction; final commit is synchronous."""
    _editor()
    if not isinstance(prepared, PreparedWorld):
        raise ValueError('prepared must be a completed prepare_world result')
    location = tuple(float(v) for v in location)
    if len(location) != 3 or any(not math.isfinite(v) for v in location):
        raise ValueError('location must contain three finite cm coordinates')
    chunk_count = prepared.chunk_count if chunk_count is None else chunk_count
    require_int('chunk_count', chunk_count, 1, prepared.world.region.cells)
    if chunk_count != prepared.chunk_count:
        raise ValueError('chunk_count differs from preparation; prepare with the desired count first')
    from .adapters import mineprep_output as output
    name = output.validate_output_name(name)
    level = output.level_path()

    def operation(job):
        job.progress('准备放置 / Preparing placement')
        from .core.masks import check_sources
        yield from job.wait(_submit(check_sources, prepared.world.pack, full=True))
        if prepared.world.pack.heightmap is not None:
            yield from job.wait(_submit(prepared.world.pack.heightmap.source.checked, full=True))
        # Spatial grouping is pure work; never open a transaction across frames.
        if prepared.backend == 'ism':
            groups = yield from job.wait(_submit(lambda: list(prepared.data.spatial_groups(chunk_count))))
        else:
            groups = []
        if output.level_path() != level:
            raise RuntimeError('active level changed before placement')
        if not output.valid_prepared(prepared):
            raise ValueError('prepared resources are no longer valid; prepare again')
        output.validate_backend(prepared.data, prepared.backend, prepared.type_groups)
        job.progress('放置中（一次提交）/ Committing Actors')
        check_sources(prepared.world.pack)
        if prepared.world.pack.heightmap is not None:
            prepared.world.pack.heightmap.source.checked()
        job.check_source()
        job._committing = True
        try:
            return output.place(prepared, location, groups, name)
        finally:
            job._committing = False
    return Job(operation, on_progress, on_done, pack=prepared.world.pack)


def cancel_all():
    """Called on mod unload; closing a panel cancels only its own job."""
    global _executor
    for job in tuple(_jobs):
        job.cancel()
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=True)
        _executor = None
    shutdown_executors()
    from .core.planning import clear_cache
    clear_cache()
    _world_cache.clear()
    _prepared_cache.clear()
