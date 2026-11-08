"""Fixed-target Filmic HDR: configuration previews and a temporary PQ video action.

Requires the rebuilt Mineprep C++ plugin; no HDR monitor or viewport is needed.
EXR defaults to display-referred Rec.2020 PQ; optional scRGB uses 1.0 = 80 nits.
"""
from datetime import datetime
import json
import math
from pathlib import Path
from uuid import uuid4

import mineprep
import unreal
from mineprep import i18n


def build_test_config(sequence=None, frame=None, resolution=(1920, 1080), *,
                      peak_nits=1000.0, paper_white_nits=203.0, output_pq=True):
    """Return (transient configuration, sequence); no queue, asset or CVar writes.

    With no sequence/frame, use the current timeline and cursor. An explicit
    different sequence defaults to its playback start. Frames use display rate.
    """
    hdr_class = getattr(unreal, 'MoviePipelineFilmicHDRSetting', None)
    if hdr_class is None:
        raise RuntimeError(i18n('请编译 Mineprep C++ 插件并重启编辑器，以加载显示 HDR 设置',
                                'Build the Mineprep C++ plugin and restart the editor to load Display HDR.'))
    if (not isinstance(resolution, (tuple, list)) or len(resolution) != 2
            or any(type(value) is not int or value <= 0 for value in resolution)):
        raise ValueError(i18n('分辨率须为两个正整数', 'Resolution must contain two positive integers.'))
    if (not isinstance(peak_nits, (int, float)) or not math.isfinite(peak_nits)
            or not 100 < peak_nits <= 10000):
        raise ValueError(i18n('HDR 峰值须为大于 100 且不超过 10000 nit 的有限数值',
                              'HDR peak must be finite, above 100 and at most 10000 nits.'))
    if (not isinstance(paper_white_nits, (int, float)) or not math.isfinite(paper_white_nits)
            or not 0 < paper_white_nits <= peak_nits):
        raise ValueError(i18n('HDR 参考白须为正的有限数值，且不超过峰值',
                              'HDR paper white must be finite, positive and no greater than the peak.'))
    current = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    sequence = current if sequence is None else unreal.load_asset(sequence) if isinstance(sequence, str) else sequence
    if not isinstance(sequence, unreal.LevelSequence):
        raise ValueError(i18n('请打开或指定一个关卡序列', 'Open or specify a Level Sequence.'))
    if not sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
        raise ValueError(i18n('显示 HDR 测试需要相机切换轨道', 'Display HDR testing requires a Camera Cuts track.'))
    if frame is None:
        frame = (int(unreal.LevelSequenceEditorBlueprintLibrary.get_global_position().frame.frame_number.value)
                 if current == sequence else int(sequence.get_playback_start()))
    if type(frame) is not int:
        raise ValueError(i18n('帧号须为整数', 'Frame must be an integer.'))

    config = unreal.MoviePipelinePrimaryConfig()
    folder = (Path(unreal.Paths.project_saved_dir()).resolve() / 'MovieRenders' / 'FilmicHDR_Test'
              / (datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid4().hex[:12]))
    for cls, values in (
        (hdr_class, dict(PeakNits=float(peak_nits), PaperWhiteNits=float(paper_white_nits), bOutputPQ=bool(output_pq))),
        (unreal.MoviePipelineOutputSetting, dict(
            OutputResolution=unreal.IntPoint(*resolution), OutputDirectory=unreal.DirectoryPath(folder.as_posix()),
            FileNameFormat='{sequence_name}.{frame_number}', ZeroPadFrameNumbers=4, FrameNumberOffset=0,
            bUseCustomFrameRate=False, bUseCustomPlaybackRange=True,
            CustomStartFrame=frame, CustomEndFrame=frame + 1)),
        (unreal.MoviePipelineDeferredPassBase, {}),
        (unreal.MoviePipelineAntiAliasingSetting, dict(
            SpatialSampleCount=1, TemporalSampleCount=1,
            RenderWarmUpCount=40, EngineWarmUpCount=2, bRenderWarmUpFrames=True)),
        (unreal.MoviePipelineColorSetting, dict(
            bDisableToneCurve=False, OCIOConfiguration=unreal.OpenColorIODisplayConfiguration())),
        (unreal.MoviePipelineImageSequenceOutput_EXR, dict(
            bMultilayer=False, bMultipart=False, Compression=unreal.EXRCompressionFormat.ZIP)),
    ):
        setting = config.find_or_add_setting_by_class(cls)
        setting.set_editor_properties(values)
    return config, sequence


def prepare_test_job(sequence=None, frame=None, resolution=(1920, 1080), *,
                     peak_nits=1000.0, paper_white_nits=203.0, output_pq=True):
    """Add one test job to an empty editor MRQ queue. User submits it in MRQ.

    This does not save assets, create output directories, clear jobs or start PIE.
    """
    from . import ops
    subsystem = ops._idle_subsystem()
    queue = subsystem.get_queue()
    if queue.get_jobs():
        raise RuntimeError(i18n('请先切换到空 MRQ 测试队列；现有任务已保留',
                                'Switch to an empty MRQ test queue first; existing jobs were preserved.'))
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    map_path = world.get_path_name().split('.')[0]
    if not unreal.EditorAssetLibrary.does_asset_exist(map_path):
        raise RuntimeError(i18n('请先保存当前地图，再准备 HDR 测试任务',
                                'Save the current map before preparing an HDR test job.'))
    config, sequence = build_test_config(sequence, frame, resolution,
                                         peak_nits=peak_nits, paper_white_nits=paper_white_nits, output_pq=output_pq)
    job = unreal.MoviePipelineEditorLibrary.create_job_from_sequence(queue, sequence)
    try:
        job.map = unreal.SoftObjectPath(map_path)
        job.set_configuration(config)
        job.job_name = 'Filmic HDR - ' + sequence.get_name()
    except Exception:
        queue.delete_job(job)
        raise
    return job


def build_video_config(settings):
    """Build a temporary animation config from RenderPanel settings; no submission."""
    from . import ops
    s = ops.prepare_settings(settings)
    if any(s.get(key) == 1 for key in ('vr', 'stereo', 'layers')):
        raise ValueError(i18n('Filmic HDR 临时入口仅支持普通动画，请关闭全景、立体和分层',
                              'Temporary Filmic HDR supports ordinary animation only. Disable panorama, stereo and layers.'))
    if any(int(s[key]) <= 0 or int(s[key]) % 2 for key in ('width', 'height')):
        raise ValueError(i18n('Filmic HDR 视频的宽高须为正偶数',
                              'Filmic HDR video dimensions must be positive even numbers.'))
    hdr_class = getattr(unreal, 'MoviePipelineFilmicHDRSetting', None)
    if hdr_class is None:
        raise RuntimeError(i18n('请编译 Mineprep C++ 插件并重启编辑器，以加载显示 HDR 设置'))
    config, _ = ops.build_config(dict(s, video=0, audio=0, image_transcode='No',
                                     delete_source=0, image_formats=4, color=0, hdr=0, default_layer=False))
    folder, stem = ops.encoding.output_name(s['name'])
    target = (Path(s['project_dir']) / 'Saved' / 'MovieRenders' / folder / (stem + '_FilmicHDR')
              / (datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid4().hex[:8]))
    for cls, values in (
        (hdr_class, dict(PeakNits=1000.0, PaperWhiteNits=203.0, bOutputPQ=True)),
        (unreal.MoviePipelineOutputSetting, dict(OutputDirectory=unreal.DirectoryPath(target.as_posix()),
            FileNameFormat='frame.{frame_number_rel}', ZeroPadFrameNumbers=4, FrameNumberOffset=0,
            bUseCustomPlaybackRange=False)),
        (unreal.MoviePipelineImageSequenceOutput_EXR, dict(bMultilayer=False, bMultipart=False,
                                                        Compression=unreal.EXRCompressionFormat.ZIP)),
        (unreal.MoviePipelineColorSetting, dict(bDisableToneCurve=False,
                                               OCIOConfiguration=unreal.OpenColorIODisplayConfiguration())),
    ):
        setting = config.find_or_add_setting_by_class(cls, True, True)
        setting.set_is_enabled(True)
        setting.set_editor_properties(values)
    if s.get('background_encode') != 1:
        args = _video_args('', target, target / (stem + '_FilmicHDR.mp4'), s['fps'], 0, None,
                           hardware=s.get('hardware', 0), quality=s.get('quality', 3))
        cli = config.find_or_add_setting_by_class(unreal.MoviePipelineCommandLineEncoder, True, True)
        cli.set_is_enabled(True)
        ops._set(cli, AdditionalCommandLineArgs=' '.join(ops.encoding.quote(arg) for arg in args[1:]),
                 bDeleteSourceFiles=False, bSkipEncodeOnRenderCanceled=False, bWriteEachFrameDuration=False)
    return config, str(target)


def _video_args(ffmpeg, folder, output_file, fps, start, count, *, hardware=0, quality=3):
    # UE already outputs Rec.2020 PQ. Convert RGB to limited-range YUV only.
    filters = ('format=gbrpf32le,zscale=matrixin=gbr:transferin=smpte2084:primariesin=bt2020:'
               'rangein=full:primaries=bt2020:transfer=smpte2084:matrix=bt2020nc:'
               'range=limited:dither=error_diffusion')
    mastering = 'G(8500,39850)B(6550,2300)R(35400,14600)WP(15635,16450)L(10000000,0)'
    qp = str((28, 23, 19, 16)[quality])
    encoder, options, pixel = (
        ('libx265', ['-preset', 'medium', '-crf', qp], 'yuv420p10le'),
        ('hevc_nvenc', ['-preset', 'p5', '-rc', 'vbr', '-cq', qp, '-b:v', '0'], 'p010le'),
        ('hevc_qsv', ['-preset', 'medium', '-global_quality', qp], 'p010le'),
        ('hevc_amf', ['-quality', 'quality', '-rc', 'cqp', '-qp_i', qp, '-qp_p', qp], 'p010le'),
        ('hevc_videotoolbox', ['-allow_sw', '0', '-q:v', str((35, 50, 65, 75)[quality])], 'p010le'),
        ('hevc_vulkan', ['-qp', qp], 'p010le'),
    )[hardware]
    filters += ',format=' + pixel
    init = []
    if hardware == 5:
        init = ['-init_hw_device', 'vulkan=vk:0', '-filter_hw_device', 'vk']
        filters += ',hwupload'
    metadata = (['-x265-params', 'hdr10=1:hdr10-opt=1:repeat-headers=1:pools=8:master-display=' + mastering]
                if hardware == 0 else ['-bsf:v', 'hevc_metadata=colour_primaries=9:transfer_characteristics=16:matrix_coefficients=9',
                                       '-metadata:s:v', 'master-display=' + mastering])
    return [str(ffmpeg), '-hide_banner', '-n', *init, '-framerate', str(fps), '-start_number', str(start),
            '-i', str(Path(folder) / 'frame.%04d.exr'),
            *(['-frames:v', str(count)] if count is not None else []), '-vf', filters,
            '-an', '-c:v', encoder, *options, '-pix_fmt', pixel,
            '-profile:v', 'main10', '-tag:v', 'hvc1', '-color_primaries', 'bt2020',
            '-color_trc', 'smpte2084', '-colorspace', 'bt2020nc', '-color_range', 'tv',
            *metadata,
            '-movflags', '+faststart', str(output_file)]


def render_video(settings=None, *, on_done=None, notify=True):
    """Temporary MRQ animation → PQ EXR → HEVC/PQ action; returns an async handle."""
    from . import ops
    subsystem = ops._idle_subsystem()
    s = ops.prepare_settings(ops.capture_settings() if settings is None else settings)
    ffmpeg = (str(s['ffmpeg_path']).strip().strip('"') or
              str(Path(mineprep.paths.mineprep) / 'Render' / 'ffmpeg' / 'Win64' / 'ffmpeg.exe'))
    if not Path(ffmpeg).is_file():
        raise RuntimeError(i18n('找不到 ffmpeg：{executable}').format(executable=ffmpeg))
    config, output_dir = build_video_config(s)
    state = dict(finished=False, success=False, fatal=False, errors=[], settings=s,
                 phase=str(i18n('Filmic HDR 渲染中', 'Rendering Filmic HDR')), filmic=True)
    ops._active = state
    try:
        task = _video_task(state, subsystem, config, output_dir, ffmpeg, notify)
        state['task'] = task
        if on_done:
            task.on_done = on_done
        return task
    except Exception:
        ops._active = None
        raise


@mineprep.asynctask
def _video_task(state, subsystem, config, output_dir, ffmpeg, notify):
    from . import batch, hdr, ops
    s = state['settings']
    folder = Path(output_dir)
    output_file = None
    background = s.get('background_encode') == 1
    try:
        if background:
            state.update(cache_dir=output_dir, output_dir=output_dir)
            ops._background[id(state)] = state
        yield 0  # Leave the Slate button callback before starting PIE.
        if subsystem.is_rendering():
            raise RuntimeError(i18n('另一个 MRQ 任务已启动，本次提交已停止'))
        # Use a fresh job and SetConfiguration: a duplicated preset origin would reload old OCIO at startup.
        queue = unreal.MoviePipelineQueue()
        job = unreal.MoviePipelineEditorLibrary.create_job_from_sequence(queue, ops._sequence(s['sequence']))
        job.set_configuration(config)
        job.map = unreal.SoftObjectPath(s['map'])
        job.job_name = ops.encoding.output_name(s['name'])[1] + ' - Filmic HDR'
        executor = unreal.MoviePipelinePIEExecutor()
        finished = lambda ex, ok: ops._on_finished(state, ex, ok)
        errored = lambda ex, pipeline, fatal, text: ops._on_error(state, ex, pipeline, fatal, text)
        executor.on_executor_finished_delegate.add_callable(finished)
        executor.on_executor_errored_delegate.add_callable(errored)
        try:
            if not background:
                cdo = unreal.get_default_object(unreal.MoviePipelineCommandLineEncoderSettings.static_class())
                ops._set(cdo, ExecutablePath=ffmpeg.replace('\\', '/'), CommandLineFormat='{AdditionalLocalArgs}',
                         VideoCodec='libx265', AudioCodec='aac', OutputFileExtension='mp4')
                cli = config.find_setting_by_class(unreal.MoviePipelineCommandLineEncoder)
                unreal.log(ops.encoding.quote(ffmpeg) + ' ' + str(cli.get_editor_property('AdditionalCommandLineArgs')))
            subsystem.render_queue_instance_with_executor_instance(queue, executor)
            batch._changed()
            while not state['finished']:
                yield 0.1
        finally:
            executor.on_executor_finished_delegate.remove_callable(finished)
            executor.on_executor_errored_delegate.remove_callable(errored)
        yield 0  # Allow native rendering/PIE teardown to finish before encoding.
        if background:
            ops._release_render(state)
        frames = sorted(int(path.stem.rsplit('.', 1)[1]) for path in folder.glob('frame.*.exr'))
        if frames:
            if frames != list(range(frames[0], frames[-1] + 1)):
                raise RuntimeError(i18n('EXR 帧不连续，已保留输出以便检查',
                                        'EXR frames are not consecutive; output was kept for inspection.'))
            output_file = folder / (ops.encoding.output_name(s['name'])[1] + '_FilmicHDR.mp4')
            fps = str(int(s['fps_value'])) if s['custom_fps'] == 1 else f"{s['sequence_rate'][0]}/{s['sequence_rate'][1]}"
            args = _video_args(ffmpeg, folder, output_file, fps, frames[0], len(frames),
                               hardware=s.get('hardware', 0), quality=s.get('quality', 3))
            folder.joinpath('encode_command.json').write_text(
                json.dumps(args, ensure_ascii=False, indent=2), encoding='utf-8')
            if background:
                from . import video
                if not (yield from video.run(state, [(args, output_file)])):
                    return dict(success=False, cancelled=True, output_file=None, output_dir=output_dir,
                                frames=len(frames), errors=state['errors'])
            if not output_file.is_file() or not output_file.stat().st_size:
                raise RuntimeError(i18n('编码未生成视频，请检查 encode.log',
                                        'Encoding produced no video. Check encode.log.'))
        else:
            state['success'] = False
            message = str(i18n('渲染未完成，未生成可编码的 EXR',
                               'Rendering was incomplete; no EXR frames are available to encode.'))
            state['errors'].append(message)
            mineprep.warn(message)
        if notify:
            try:
                ops._finish(s, output_dir, state['success'], refresh=False,
                            label=i18n('Filmic HDR 视频完成', 'Filmic HDR video complete'))
            except Exception as exc:
                mineprep.warn(i18n('渲染已结束，但结束处理失败：{exc}').format(exc=str(exc)))
        return dict(success=state['success'], output_dir=output_dir,
                    output_file=str(output_file) if output_file else None,
                    frames=len(frames), errors=state['errors'])
    except hdr._ProcessingCancelled:
        state['success'] = False
        return dict(success=False, cancelled=True, output_file=None, output_dir=output_dir,
                    frames=len(frames), errors=state['errors'])
    finally:
        ops._release_task(state)
