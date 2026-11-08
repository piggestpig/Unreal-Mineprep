"""当前帧 Ultra HDR 增益图 JPG 渲染，以及已有 SDR + PQ/Rec.2020 HDR 图片合成。"""
import math
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

import mineprep
import unreal
from mineprep import i18n

from . import encoding, ops

_GRAPH = '/Game/Mineprep/Render/libultrahdr增益图jpg渲染配置'


def _context(options, render=False):
    options = dict(options or {})
    quality = int(options.get('hdr_quality', options.get('quality', 98)))
    sdr_quality = int(options.get('sdr_quality', 100))
    if not 1 <= quality <= 100 or not 1 <= sdr_quality <= 100:
        raise ValueError(i18n('SDR 和 HDR 质量必须在 1～100 之间'))
    gamma = float(options.get('gamma', 1.175)) if render else None
    if render and (not math.isfinite(gamma) or gamma <= 0):
        raise ValueError(i18n('渲染 HDR 伽马必须是大于 0 的有限数值'))
    prefs = ops._preferences()
    platform = unreal.GameplayStatics.get_platform_name()
    folder = {'Windows': 'Win64', 'Mac': 'Mac', 'Linux': 'Linux'}[platform]
    tools = Path(mineprep.paths.mineprep) / 'Render' / 'ffmpeg' / folder
    suffix = '.exe' if platform == 'Windows' else ''
    project = Path(unreal.Paths.project_dir()).resolve()
    return dict(quality=quality, sdr_quality=sdr_quality, gamma=gamma,
                ffmpeg=str(prefs.get('ffmpeg_path', '')).strip().strip('"') or str(tools / ('ffmpeg' + suffix)),
                ultrahdr=str(tools / ('ultrahdr_app' + suffix)),
                cache_dir=str(project / 'cache' / 'RenderPanelHDR' / uuid4().hex),
                project_dir=str(project),
                open_after=str(prefs.get('open_file_after_render', 'false')).lower() == 'true',
                finish_sound=prefs.get('render_finish_sound', ''))


def read_settings(options=None):
    """读取当前帧 HDR 渲染所需的分辨率、暖场帧、输出名称及时间线帧号。"""
    s = _context(options, render=True)
    values = {}
    for name, kind in (('X_分辨率', float), ('Y_分辨率', float),
                       ('暖场帧滑条', float), ('视频名称文本框', str)):
        public_name = f'{ops._PANEL}.{name}'
        try:
            values[name] = mineprep.panel(public_name).get(kind)
        except Exception as exc:
            raise RuntimeError(i18n('无法读取控件 {public_name}：{exc}').format(public_name=str(public_name), exc=str(exc))) from exc
    s['width'] = int(values['X_分辨率']) // 2 * 2
    s['height'] = int(values['Y_分辨率']) // 2 * 2
    warmup = int(values['暖场帧滑条'])
    if min(s['width'], s['height']) < 2 or warmup < 0:
        raise ValueError(i18n('HDR 图片宽高至少为 2，暖场帧数不能为负数'))
    s['warmup'] = warmup + 20
    folder, stem = encoding.output_name(values['视频名称文本框'])
    s['output_file'] = str(Path(s['project_dir']) / 'Saved' / 'MovieRenders' / folder / (stem + '_Gainmap.jpg'))
    current = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    cuts = current.find_tracks_by_type(unreal.MovieSceneCameraCutTrack) if current else []
    s['sequence_fallback'] = 'missing_camera_cut' if current and not cuts else 'no_sequence' if not current else ''
    s['sequence'] = current.get_path_name() if current and cuts else ops._TEMP_SEQUENCE
    # 临时序列没有时间线播放头，固定渲染第 0 帧
    s['frame'] = int(unreal.LevelSequenceEditorBlueprintLibrary.get_global_position().frame.frame_number.value) if current and cuts else 0
    return s


def capture_settings(options=None, *, settings=None, frame=None):
    """采集双次渲染的普通字典；不切换控件，也不保存或提交渲染。"""
    quality = _context(options)  # 新路径不读取、校验或应用旧伽马。
    s = dict(settings) if settings is not None else ops.capture_settings()
    s.update(width=int(s['width']) // 2 * 2, height=int(s['height']) // 2 * 2,
             warmup=int(s['warmup']) + 20,
             sdr_quality=quality['sdr_quality'], hdr_quality=quality['quality'])
    if min(s['width'], s['height']) < 2 or s['warmup'] < 20:
        raise ValueError(i18n('HDR 图片宽高至少为 2，暖场帧数不能为负数'))
    s['frame'] = ops.current_frame(s) if frame is None else int(frame)
    return s


def build_still_config(settings, stage, cache_dir):
    """预览单次 MRQ 图片配置；不触发旧面板事件，不生成配置资产。"""
    if stage not in ('SDR', 'HDR'):
        raise ValueError(i18n('请选择 SDR 或 HDR 阶段'))
    is_hdr = stage == 'HDR'
    s = dict(settings, hdr=int(is_hdr), color=int(is_hdr), image_formats=4 if is_hdr else 1,
             video=0, audio=0, delete_source=0, image_transcode='No',
             vr=0, stereo=0, layers=0, custom_fps=0)
    config, _ = ops.build_config(s)
    folder = str(Path(cache_dir) / stage)
    output = config.find_setting_by_class(unreal.MoviePipelineOutputSetting)
    ops._set(output, OutputDirectory=unreal.DirectoryPath(folder),
             FileNameFormat=stage + '.{frame_number}', ZeroPadFrameNumbers=4, FrameNumberOffset=0,
             bUseCustomPlaybackRange=True, CustomStartFrame=s['frame'], CustomEndFrame=s['frame'] + 1)
    return config, folder


def _sdr_qscale(s):
    # FFmpeg MJPEG 的 qscale 越小画质越高：1 为最高质量，31 为最低质量
    return str(round(1 + (100 - s['sdr_quality']) * 30 / 99))


def _render_args(s):
    """生成注入到 HDR 渲染图命令行编码器节点的 FFmpeg 参数列表。"""
    cache = Path(s['cache_dir']).as_posix()
    return ['-start_number', str(s['frame']), '-i', cache + '/frame.SDR.%04d.png',
            '-start_number', str(s['frame']), '-i', cache + '/frame.HDR.%04d.exr',
            '-map', '0:v:0', '-frames:v', '1', '-qscale:v', _sdr_qscale(s), '-qmin', '1',
            '-pix_fmt', 'yuvj420p', cache + '/SDR_input.jpg',
            '-map', '1:v:0', '-frames:v', '1', '-vf', f"eq=gamma={s['gamma']},format=p010le",
            '-pix_fmt', 'p010le', '-f', 'rawvideo', cache + '/HDR_input.yuv']


def build_config(settings):
    """创建临时渲染队列并通过任务变量覆盖 HDR 渲染图参数（不修改原渲染图资产）。"""
    s = settings
    graph = unreal.load_asset(_GRAPH)
    if not graph:
        raise RuntimeError(i18n('无法加载 HDR 渲染配置：{GRAPH}').format(GRAPH=str(_GRAPH)))
    queue = unreal.MoviePipelineQueue(outer=ops._world())
    job = unreal.MoviePipelineEditorLibrary.create_job_from_sequence(queue, ops._sequence(s['sequence']))
    job.set_graph_preset(graph)
    assignments = job.get_or_create_variable_overrides(graph)
    # 模板固定输出在 {project_dir}/cache 下，每次任务使用独立的子目录
    prefix = Path(s['cache_dir']).relative_to(Path(s['project_dir']) / 'cache').as_posix()
    values = {
        '分辨率': ('set_value_serialized_string', f'(ProfileName="Custom",Resolution=(X={s["width"]},Y={s["height"]}),Description="")'),
        '起始帧': ('set_value_serialized_string', f'(Type=Custom,Value={s["frame"]})'),
        '结束帧': ('set_value_serialized_string', f'(Type=Custom,Value={s["frame"] + 1})'),
        '暖场帧': ('set_value_int32', s['warmup']),
        '文件名': ('set_value_string', prefix + '/frame.{layer_name}.{frame_number}'),
        'ffmpeg编码': ('set_value_string', ' '.join(encoding.quote(arg) for arg in _render_args(s))),
    }
    variables = {str(v.get_member_name()): v for v in graph.get_variables(False)}
    for name, (method, value) in values.items():
        if name not in variables:
            raise RuntimeError(i18n('HDR 渲染配置缺少变量：{name}').format(name=str(name)))
        variable = variables[name]
        if not getattr(assignments, method)(variable, value) or not assignments.set_variable_assignment_enable_state(variable, True):
            raise RuntimeError(i18n('无法覆盖 HDR 任务变量：{name}').format(name=str(name)))
    return queue, job


def _image_size(path):
    from PIL import Image
    with Image.open(path) as image:
        return image.size


def _conversion_args(s, *, pq=False):
    cache = Path(s['cache_dir'])
    crop = f'crop={s["width"]}:{s["height"]}'
    # 新路径的 EXR 已是 PQ RGB：仅转换为 BT.2020 窄范围 YUV，不能再做传递函数或伽马变换。
    hdr_filter = crop + (',scale=in_range=full:out_range=tv:out_color_matrix=bt2020:flags=accurate_rnd' if pq else '') + ',format=p010le'
    common = [s['ffmpeg'], '-hide_banner', '-y', '-loglevel', 'error']
    return [common + ['-i', s['sdr_path'], '-frames:v', '1', '-vf', crop,
                      '-qscale:v', _sdr_qscale(s), '-qmin', '1', '-pix_fmt', 'yuvj420p', str(cache / 'SDR_input.jpg')],
            common + ['-i', s['hdr_path'], '-frames:v', '1', '-vf', hdr_filter,
                      '-pix_fmt', 'p010le', '-f', 'rawvideo', str(cache / 'HDR_input.yuv')]]


def _ultrahdr_args(s):
    cache = Path(s['cache_dir'])
    return [s['ultrahdr'], '-m', '0', '-p', str(cache / 'HDR_input.yuv'),
            '-i', str(cache / 'SDR_input.jpg'), '-w', str(s['width']), '-h', str(s['height']),
            '-a', '0', '-t', '2', '-L', '1000', '-C', '2',
            '-Q', str(s['quality']), '-q', str(s['sdr_quality']), '-z', str(cache / 'result.jpg')]


class _ProcessingCancelled(Exception):
    pass


class _ProcessingNotice:
    """One notification shared by an operation's external processing stages."""
    def __init__(self, title):
        self.started = self.finished = self.cancelled = False
        self.result = self.process = None
        self.text = str(title)
        self.task = mineprep.show_editor_task(title, begin=self._begin, cancel=self._cancel)

    def _begin(self, task):
        self.task = task
        self.started = True
        if self.result is not None:
            self.finish(self.result)
        else:
            task.set_task_notification_text(self.text)

    def _cancel(self, task):
        self.cancelled = self.finished = True
        if self.process is not None and self.process.poll() is None:
            self.process.kill()

    def stage(self, label):
        if self.cancelled:
            raise _ProcessingCancelled()
        self.text = str(label)
        if self.started and not self.finished:
            self.task.set_task_notification_text(self.text)

    def finish(self, success):
        self.result = bool(success)
        if self.started and not self.finished:
            self.finished = True
            self.task.finish_executing_task(self.result)


def _run_process(args, log_path, label, *, notice=None):
    """将子进程输出重定向到日志文件并按帧轮询等待退出，避免管道缓冲区死锁。"""
    kwargs = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}
    if notice:
        notice.stage(label)
    with Path(log_path).open('wb') as log:
        process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, **kwargs)
        if notice:
            notice.process = process
        try:
            while process.poll() is None:
                yield 0.1
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            if notice:
                notice.process = None
    if notice and notice.cancelled:
        raise _ProcessingCancelled()
    if process.returncode:
        detail = Path(log_path).read_bytes().decode('utf-8', errors='replace')[-3000:]
        raise RuntimeError(i18n('{label}失败（退出码 {returncode}）：{detail}\n日志：{log_path}').format(label=str(label), returncode=str(process.returncode), detail=str(detail), log_path=str(log_path)))


def _inputs_ready(s):
    cache = Path(s['cache_dir'])
    raw = cache / 'HDR_input.yuv'
    try:
        return (raw.stat().st_size == s['width'] * s['height'] * 3
                and _image_size(cache / 'SDR_input.jpg') == (s['width'], s['height']))
    except (OSError, ValueError):
        return False


def _render_inputs(s, state, subsystem):
    queue, job = build_config(s)
    director = None
    executor = None
    previous_hdr = None
    finished_cb = error_cb = None
    try:
        if subsystem.is_rendering():
            raise RuntimeError(i18n('另一个 MRQ 任务已启动，本次提交已停止'))
        if s['sequence_fallback'] == 'missing_camera_cut':
            mineprep.warn(i18n('当前时间线没有相机切换轨道，将使用临时摄像机渲染第 0 帧'))
        if not unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True):
            raise RuntimeError(i18n('保存地图／资源失败，未提交任务'))
        if subsystem.is_rendering():
            raise RuntimeError(i18n('另一个 MRQ 任务已启动，本次提交已停止'))
        director = ops._director() or mineprep.BPLib('导播台')
        if director:
            previous_hdr = director.get_editor_property('HDR渲染')
            director.set_editor_property('HDR渲染', unreal.CheckBoxState.UNDETERMINED)
        # 渲染图已自带命令行格式，只需在全局设置中指定 ffmpeg 可执行文件路径
        cdo = unreal.get_default_object(unreal.MoviePipelineCommandLineEncoderSettings.static_class())
        cdo.set_editor_property('ExecutablePath', str(s['ffmpeg']).replace('\\', '/'))
        executor = unreal.MoviePipelinePIEExecutor()
        finished_cb = lambda ex, ok: ops._on_finished(state, ex, ok)
        error_cb = lambda ex, pipeline, fatal, text: ops._on_error(state, ex, pipeline, fatal, text)
        executor.on_executor_finished_delegate.add_callable(finished_cb)
        executor.on_executor_errored_delegate.add_callable(error_cb)
        if not subsystem.get_queue().copy_from(queue):
            raise RuntimeError(i18n('无法提交 HDR 渲染队列'))
        subsystem.render_queue_with_executor_instance(executor)
        while not state['finished']:
            yield 0.1
    finally:
        if executor:
            executor.on_executor_finished_delegate.remove_callable(finished_cb)
            executor.on_executor_errored_delegate.remove_callable(error_cb)
        if director and previous_hdr is not None:
            try:
                director.set_editor_property('HDR渲染', previous_hdr)
                director.call_method('刷新状态', ())
            except Exception as exc:
                mineprep.warn(i18n('HDR 渲染结束后刷新导播台失败：{exc}').format(exc=str(exc)))


def _start(s, subsystem=None, *, pair=False, notify=True, on_done=None):
    for key in ('ffmpeg', 'ultrahdr'):
        if not Path(s[key]).is_file():
            raise RuntimeError(i18n('找不到 {key}：{value}').format(key=str(key), value=str(s[key])))
    state = {'finished': False, 'success': subsystem is None or pair, 'fatal': False, 'errors': [], 'notify': notify}
    ops._active = state
    try:
        task = _task(s, state, subsystem, pair=pair)
        if on_done:
            task.on_done = on_done
        return task
    except Exception:
        ops._active = None
        raise


def render_current_frame(options=None):
    """渲染当前帧并合成为 Ultra HDR 增益图 JPG，返回异步任务句柄。"""
    subsystem = ops._idle_subsystem()
    return _start(read_settings(options), subsystem)


def render_current_frame_twice(options=None, *, on_done=None, notify=True):
    """按 SDR → HDR → 合成渲染当前帧；返回 done/result/error 句柄，不使用伽马。"""
    ops._idle_subsystem()
    return _start_pair(capture_settings(options), on_done=on_done, notify=notify)


def _start_pair(settings, *, on_done=None, notify=True, owner=None):
    subsystem = ops._idle_subsystem(owner)
    render_settings = ops.prepare_settings(settings)
    s = _context(settings)
    folder, stem = encoding.output_name(settings['name'])
    s.update(render_settings=render_settings, width=int(settings['width']), height=int(settings['height']),
             output_file=str(Path(s['project_dir']) / 'Saved/MovieRenders' / folder / (stem + '_Gainmap.jpg')))
    return _start(s, subsystem, pair=True, notify=notify, on_done=on_done)


def _render_pair(s, state, subsystem):
    """两份单帧 MRQ 任务共用一次占用；状态切换必须广播旧蓝图事件。"""
    from . import batch
    controls = {}
    for name in ('🔲HDR渲染', '色彩管理选项', '渲染图片格式选项'):
        path = f'{ops._PANEL}.{name}'
        control = mineprep.panel(path)
        if control.target is None:
            raise RuntimeError(i18n('缺少控件：{path}；双次渲染期间请保持旧面板打开').format(path=str(path)))
        controls[name] = control
    previous = {name: control.get(int) for name, control in controls.items()}
    director = ops._director() or mineprep.BPLib('导播台')
    previous_hdr = director.get_editor_property('HDR渲染') if director else None
    # 先保存用户场景，再临时切换；不把 SDR/HDR 中间状态保存回地图或旧预设。
    if not unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True):
        raise RuntimeError(i18n('保存地图／资源失败，未提交任务'))
    settings = s['render_settings']
    sequence = ops._sequence(settings['sequence'])
    state['legacy_switching'] = True
    try:
        for stage, mode, mask, extension in (('SDR', 0, 1, 'png'), ('HDR', 1, 4, 'exr')):
            state['phase'] = str(i18n('{stage} 图片渲染').format(stage=stage))
            batch._changed()
            controls['🔲HDR渲染'].select(mode)
            controls['色彩管理选项'].select(mode)
            controls['渲染图片格式选项'].set_string(str(mask))
            if director:
                # 旧按钮也会将复选框状态传给导播台，PIE 中的后期蓝图读取此变量。
                director.set_editor_property('HDR渲染', unreal.CheckBoxState.CHECKED if mode else unreal.CheckBoxState.UNCHECKED)
            yield 0  # 给蓝图事件、后期体积和编辑器状态一个引擎帧。
            config, folder = build_still_config(settings, stage, s['cache_dir'])
            part = dict(finished=False, success=False, fatal=False, errors=[])
            yield from ops._render_config(part, subsystem, config, sequence)
            state['success'] = state['success'] and part['success']
            state['errors'].extend(part['errors'])
            images = list(Path(folder).glob('*.' + extension))
            if len(images) != 1 or images[0].stat().st_size == 0:
                if part['success']:
                    raise RuntimeError(i18n('{stage} 未生成唯一有效图片：{folder}').format(stage=str(stage), folder=str(folder)))
                return False
            s[stage.lower() + '_path'] = str(images[0])
            if stage == 'SDR' and not part['success']:
                return False  # 用户取消后不再提交第二次渲染。
            yield 0  # 前一个执行器和委托已清理，下一帧才处理下一阶段。
        state['phase'] = str(i18n('HDR JPG 合成'))
        batch._changed()
        return True
    finally:
        try:
            controls['🔲HDR渲染'].select(previous['🔲HDR渲染'])
            controls['色彩管理选项'].select(previous['色彩管理选项'])
            controls['渲染图片格式选项'].set_string(str(previous['渲染图片格式选项']))
            if director:
                director.set_editor_property('HDR渲染', previous_hdr)
                director.call_method('刷新状态', ())
        except Exception as exc:
            state['success'] = False
            state['errors'].append(str(i18n('恢复旧面板状态失败：{error}').format(error=str(exc))))
            mineprep.warn(state['errors'][-1])
        finally:
            state['legacy_switching'] = False
            batch._changed()


def compose_images(sdr_path, hdr_path, output_file, options=None):
    """将已有的 SDR 图片与 PQ/Rec.2020 HDR 图片合成为 Ultra HDR 增益图 JPG（无需打开旧渲染面板）。"""
    ops._idle_subsystem()
    s = _context(options)
    s.update(sdr_path=str(Path(sdr_path).resolve()), hdr_path=str(Path(hdr_path).resolve()),
             output_file=str(Path(output_file).resolve()))
    for key in ('sdr_path', 'hdr_path'):
        if not Path(s[key]).is_file():
            raise ValueError(i18n('找不到输入图片：{value}').format(value=str(s[key])))
    w, h = _image_size(s['sdr_path'])
    s.update(width=w // 2 * 2, height=h // 2 * 2)
    if min(s['width'], s['height']) < 2:
        raise ValueError(i18n('SDR 图片宽高至少为 2'))
    return _start(s)


@mineprep.asynctask
def _task(s, state, subsystem, *, pair=False):
    cache = Path(s['cache_dir'])
    output = Path(s['output_file'])
    notice = None
    processing_success = False
    try:
        yield 0  # 先退出按钮回调，下一帧再开始执行渲染或外部转换进程
        if subsystem and subsystem.is_rendering():
            raise RuntimeError(i18n('另一个 MRQ 任务已启动，本次提交已停止'))
        cache.mkdir(parents=True)
        if pair:
            ready = yield from _render_pair(s, state, subsystem)
            if not ready:
                mineprep.prints(i18n('HDR 双次渲染未完成；本次缓存：{cache}').format(cache=str(cache)))
                return dict(success=False, output_file=None, output_dir=str(output.parent),
                            errors=state['errors'], cache_dir=str(cache))
        elif subsystem:
            yield from _render_inputs(s, state, subsystem)
        if pair or subsystem is None:
            notice = _ProcessingNotice('HDR 图片处理')
            try:
                for args, name in zip(_conversion_args(s, pq=pair), ('SDR', 'HDR')):
                    label = i18n('{name} 图片转换（裁剪尺寸 {width}×{height}，输入尺寸不可更小）').format(
                        name=name, width=s['width'], height=s['height'])
                    yield from _run_process(args, cache / (name + '.log'), label, notice=notice)
            except RuntimeError as exc:
                if state['success']:
                    raise
                state['errors'].append(str(exc))  # 取消后的不完整图片按未完成结算。
        if not _inputs_ready(s):
            if state['success']:
                raise RuntimeError(i18n('未生成完整的 SDR/HDR 输入，请检查 MRQ 编码日志及缓存：{cache}').format(cache=str(cache)))
            mineprep.prints(i18n('HDR 渲染未完整完成，未生成 JPG；本次缓存：{cache}').format(cache=str(cache)))
            return dict(success=False, output_file=None, output_dir=str(output.parent),
                        errors=state['errors'], cache_dir=str(cache))
        if notice is None:
            notice = _ProcessingNotice('HDR 增益图合成')
        yield from _run_process(_ultrahdr_args(s), cache / 'ultrahdr.log', i18n('HDR 增益图合成'), notice=notice)
        result = cache / 'result.jpg'
        if _image_size(result) != (s['width'], s['height']):
            raise RuntimeError(i18n('HDR JPG 输出尺寸不符：{result}').format(result=str(result)))
        output.parent.mkdir(parents=True, exist_ok=True)
        result.replace(output)  # 合成完毕后再替换目标文件，避免中途失败损坏已有输出
        processing_success = state['success']
        notice.finish(processing_success)
        if not state['success']:
            mineprep.prints(i18n('已生成 HDR JPG，但渲染未完整完成：{output}').format(output=str(output)))
        try:
            if state['notify']:
                ops._finish(s, str(output.parent), state['success'], label=i18n('HDR JPG 合成完成'), refresh=False)
        except Exception as exc:
            mineprep.warn(i18n('HDR JPG 已生成，但结束处理失败：{exc}').format(exc=str(exc)))
        if state['success']:
            try:
                shutil.rmtree(cache)
            except OSError as exc:
                mineprep.warn(i18n('HDR JPG 已生成，但缓存清理失败：{exc}').format(exc=str(exc)))
        return dict(success=state['success'], output_file=str(output), errors=state['errors'],
                    output_dir=str(output.parent),
                    cache_dir=str(cache) if cache.exists() else None)
    except _ProcessingCancelled:
        state['success'] = False
        return dict(success=False, cancelled=True, output_file=None, output_dir=str(output.parent),
                    errors=state['errors'], cache_dir=str(cache))
    finally:
        try:
            if notice:
                notice.finish(processing_success)
        finally:
            ops._active = None
            from . import batch
            batch._changed()
