"""Fixed-target Filmic HDR: configuration previews and a temporary PQ video action.

Requires the rebuilt Mineprep C++ plugin; no HDR monitor or viewport is needed.
EXR defaults to display-referred Rec.2020 PQ; optional scRGB uses 1.0 = 80 nits.
"""
from datetime import datetime
import json
import math
import struct
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


def _gainmap_parameters(peak_nits, paper_white_nits, sdr_quality, hdr_quality):
    if not math.isfinite(peak_nits) or not 203 <= peak_nits <= 10000:
        raise ValueError('Gainmap peak must be between 203 and 10000 nits.')
    if not math.isfinite(paper_white_nits) or not 0 < paper_white_nits <= peak_nits:
        raise ValueError('Paper white must be positive and no greater than the peak.')
    if any(type(q) is not int or not 1 <= q <= 100 for q in (sdr_quality, hdr_quality)):
        raise ValueError('SDR and HDR quality must be integers from 1 to 100.')
    return dict(peak_nits=float(peak_nits), paper_white_nits=float(paper_white_nits),
                sdr_quality=sdr_quality, hdr_quality=hdr_quality)


def _gainmap_image_size(path):
    """Read EXR dataWindow without decoding pixels or requiring an EXR Python package."""
    from . import hdr
    if Path(path).suffix.lower() != '.exr':
        return hdr._image_size(path)
    with Path(path).open('rb') as stream:
        if stream.read(4) != b'\x76\x2f\x31\x01':
            raise ValueError('Invalid EXR input: ' + str(path))
        stream.read(4)  # Version and flags.

        def string():
            value = bytearray()
            while True:
                byte = stream.read(1)
                if not byte:
                    raise ValueError('Truncated EXR header: ' + str(path))
                if byte == b'\0':
                    return bytes(value)
                value.extend(byte)

        while name := string():
            kind = string()
            size = struct.unpack('<I', stream.read(4))[0]
            if name == b'dataWindow' and kind == b'box2i' and size == 16:
                x0, y0, x1, y1 = struct.unpack('<4i', stream.read(size))
                return x1 - x0 + 1, y1 - y0 + 1
            stream.seek(size, 1)
    raise ValueError('EXR has no dataWindow: ' + str(path))


def _gainmap_graph(s, *, graph=None, expose=False):
    """Shared builder for the saved example and transient single-frame jobs."""
    from . import mrg, ops
    cls = getattr(unreal, 'MovieGraphFilmicHDRRenderPassNode', None)
    if cls is None:
        raise RuntimeError('Build the Mineprep C++ plugin and restart the editor to load the Filmic HDR graph node.')
    graph = graph if graph is not None else unreal.MovieGraphConfig()
    if not any(str(member.get_member_name()) == 'DefaultLayer' for member in graph.get_inputs()):
        graph.add_input('DefaultLayer')
    resolution = unreal.MovieGraphNamedResolution(profile_name='Custom',
        resolution=unreal.IntPoint(s['width'], s['height']))
    bound = unreal.MovieGraphSequencePlaybackRangeBound
    start = bound(type=unreal.MovieGraphSequenceRangeType.CUSTOM, value=s['frame'])
    end = bound(type=unreal.MovieGraphSequenceRangeType.CUSTOM, value=s['frame'] + 1)
    output = mrg._node(graph, unreal.MovieGraphGlobalOutputSettingNode,
        OutputResolution=resolution, OutputDirectory=unreal.DirectoryPath(s['output_dir']),
        bOverwriteExistingOutput=True, ZeroPadFrameNumbers=4,
        CustomPlaybackRangeStart=start, CustomPlaybackRangeEnd=end)
    warmup = mrg._node(graph, unreal.MovieGraphWarmUpSettingNode,
        NumWarmUpFrames=int(s['warmup']), bEmulateMotionBlur=True)
    globals_ = [warmup,
        mrg._node(graph, unreal.MovieGraphGlobalGameOverridesNode, SoftGameModeOverride=ops._game_mode(s)),
        output,
        mrg._node(graph, unreal.MovieGraphSamplingMethodNode, TemporalSampleCount=int(s['temporal'])),
        mrg._node(graph, unreal.MovieGraphSetCVarValueNode, Name='r.LUT.TonemappingMethod', Value=0.0)]
    mrg._connect(graph, globals_, 'Globals')
    graph.add_labeled_edge(graph.get_input_node(), 'Globals', globals_[0], '')
    filename = s['stem'] + '.{layer_name}.{frame_number}'
    file_nodes = []
    hdr_renderer = None
    for index, (branch, renderer_cls, file_cls) in enumerate((
            ('SDR', unreal.MovieGraphDeferredRenderPassNode, unreal.MovieGraphImageSequenceOutputNode_PNG),
            ('HDR', cls, unreal.MovieGraphImageSequenceOutputNode_EXR))):
        graph.add_output(branch)
        renderer = mrg._node(graph, renderer_cls, SpatialSampleCount=int(s['spatial']),
            bDisableToneCurve=False, bAllowOCIO=False)
        file_node = mrg._node(graph, file_cls, FileNameFormat=filename,
            OCIOConfiguration=unreal.OpenColorIODisplayConfiguration())
        if branch == 'HDR':
            hdr_renderer = renderer
            ops._set(renderer, bOverride_bOutputPQ=True, bOutputPQ=True,
                     bOverride_PeakNits=True, PeakNits=s['peak_nits'],
                     bOverride_PaperWhiteNits=True, PaperWhiteNits=s['paper_white_nits'])
            ops._set(file_node, bOverride_Compression=True, Compression=unreal.EXRCompressionFormat.ZIP)
        file_nodes.append(file_node)
        nodes = [renderer, file_node, mrg._node(graph, unreal.MovieGraphRenderLayerNode, LayerName=branch)]
        mrg._connect(graph, nodes, branch)
        graph.add_labeled_edge(graph.get_input_node(), 'DefaultLayer', renderer, '')
        if expose:
            for column, node in enumerate(nodes):
                cls.set_graph_node_position(node, column * 380, 360 + index * 360)
    if expose:
        for column, node in enumerate(globals_):
            cls.set_graph_node_position(node, column * 280, 0)
        cls.set_graph_node_position(graph.get_output_node(), 1550, 0)
        cls.set_graph_node_position(graph.get_input_node(), -380, 0)
        bindings = [
            ('分辨率', unreal.MovieGraphValueType.STRUCT, unreal.MovieGraphNamedResolution.static_struct(), resolution.export_text(), [(output, 'OutputResolution')]),
            ('起始帧', unreal.MovieGraphValueType.STRUCT, bound.static_struct(), start.export_text(), [(output, 'CustomPlaybackRangeStart')]),
            ('结束帧', unreal.MovieGraphValueType.STRUCT, bound.static_struct(), end.export_text(), [(output, 'CustomPlaybackRangeEnd')]),
            ('暖场帧', unreal.MovieGraphValueType.INT32, None, str(s['warmup']), [(warmup, 'NumWarmUpFrames')]),
            ('文件名', unreal.MovieGraphValueType.STRING, None, filename, [(node, 'FileNameFormat') for node in file_nodes]),
            ('HDR峰值', unreal.MovieGraphValueType.FLOAT, None, str(s['peak_nits']), [(hdr_renderer, 'PeakNits')]),
            ('参考白', unreal.MovieGraphValueType.FLOAT, None, str(s['paper_white_nits']), [(hdr_renderer, 'PaperWhiteNits')]),
        ]
        for index, (name, value_type, type_object, value, targets) in enumerate(bindings):
            variable = graph.add_variable(name)
            variable.set_value_type(value_type, type_object)
            if not variable.set_value_serialized_string(value):
                raise RuntimeError('Cannot initialize graph variable: ' + name)
            getter = graph.create_node_by_class(unreal.MovieGraphVariableNode)
            getter.set_variable(variable)
            cls.set_graph_node_position(getter, -380, 180 + index * 150)
            for target, prop in targets:
                target.promote_property_to_pin(prop)
                graph.add_labeled_edge(getter, name, target, prop)
    return graph


def render_gainmap(settings=None, *, peak_nits=1000, paper_white_nits=203,
                   sdr_quality=100, hdr_quality=98, on_done=None, notify=True):
    """Render one SDR/HDR MRG frame pair, then compose an Ultra HDR JPEG."""
    from . import hdr, ops
    subsystem = ops._idle_subsystem()
    params = _gainmap_parameters(peak_nits, paper_white_nits, sdr_quality, hdr_quality)
    s = ops.prepare_settings(ops.capture_settings() if settings is None else settings)
    ops._validate(s)
    if any(s.get(key) == 1 for key in ('vr', 'stereo', 'layers')):
        raise ValueError('Filmic gainmap rendering supports ordinary Deferred images. Disable panorama, stereo and layers.')
    dimensions = (s['width'], s['height'])
    if any(not math.isfinite(v) or v < 2 or v != int(v) or int(v) % 2 for v in dimensions):
        raise ValueError('Gainmap dimensions must be positive even integers.')
    folder, stem = ops.encoding.output_name(s['name'])
    output = (Path(s['project_dir']) / 'Saved/MovieRenders' / folder / (stem + '_FilmicGainmap')
              / (datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid4().hex[:8]))
    context = hdr._context(params)
    frame = s['frame'] if 'frame' in s and not s.get('sequence_fallback') else ops.current_frame(s)
    if type(frame) is not int:
        raise ValueError('Frame must be an integer.')
    s.update(params, width=int(s['width']), height=int(s['height']), frame=frame,
             output_dir=str(output), stem=stem, name=s['name'])
    graph = _gainmap_graph(s)
    return _start_gainmap(s, context, subsystem=subsystem, graph=graph, on_done=on_done, notify=notify)


def compose_gainmap(sdr_path, hdr_path, output_file, *, peak_nits=1000,
                    sdr_quality=100, hdr_quality=98, on_done=None, notify=True):
    """Compose matching sRGB SDR and Rec.2020 PQ HDR inputs; preserve all inputs."""
    from . import hdr, ops
    ops._idle_subsystem()
    params = _gainmap_parameters(peak_nits, 203, sdr_quality, hdr_quality)
    paths = [Path(path).resolve() for path in (sdr_path, hdr_path)]
    if any(not path.is_file() for path in paths):
        raise ValueError('Both SDR and HDR image files must exist.')
    width, height = hdr._image_size(paths[0])
    if _gainmap_image_size(paths[1]) != (width, height) or min(width, height) < 2 or width % 2 or height % 2:
        raise ValueError('SDR and HDR inputs must have identical, positive even dimensions.')
    context = hdr._context(params)
    output_file = Path(output_file).resolve()
    if output_file in paths:
        raise ValueError('The output JPEG must have a different path from the inputs.')
    cache = Path(context['cache_dir'])
    s = dict(params, width=width, height=height, sdr_path=str(paths[0]), hdr_path=str(paths[1]),
             output_file=str(output_file), output_dir=str(cache))
    return _start_gainmap(s, context, on_done=on_done, notify=notify)


def _start_gainmap(s, context, *, subsystem=None, graph=None, on_done=None, notify=True):
    from . import ops
    for key in ('ffmpeg', 'ultrahdr'):
        if not Path(context[key]).is_file():
            raise ValueError('Missing executable: ' + context[key])
    state = dict(finished=False, success=True, fatal=False, errors=[], settings=s,
                 phase='Filmic gainmap', notify=notify)
    ops._active = state
    try:
        task = _gainmap_task(s, context, state, subsystem, graph)
        state['task'] = task
        if on_done:
            task.on_done = on_done
        return task
    except Exception:
        ops._release_task(state)
        raise


@mineprep.asynctask
def _gainmap_task(s, context, state, subsystem, graph):
    from . import batch, hdr, ops
    output = Path(s['output_dir'])
    notice = None
    success = False
    result = dict(success=False, sdr_path=s.get('sdr_path'), hdr_path=s.get('hdr_path'),
                  output_file=None, output_dir=str(output), errors=state['errors'])
    try:
        yield 0
        output.mkdir(parents=True, exist_ok=True)
        if graph is not None:
            if not unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True):
                raise RuntimeError('Could not save the current map and assets.')
            state.update(success=False, phase='Filmic SDR/HDR rendering')
            batch._changed()
            # A private queue keeps existing editor MRQ jobs available.
            queue = unreal.MoviePipelineQueue()
            job = unreal.MoviePipelineEditorLibrary.create_job_from_sequence(queue, ops._sequence(s['sequence']))
            job.set_graph_preset(graph)
            job.map = unreal.SoftObjectPath(s['map'])
            executor = unreal.MoviePipelinePIEExecutor()
            finished = lambda ex, ok: ops._on_finished(state, ex, ok)
            errored = lambda ex, pipeline, fatal, text: ops._on_error(state, ex, pipeline, fatal, text)
            executor.on_executor_finished_delegate.add_callable(finished)
            executor.on_executor_errored_delegate.add_callable(errored)
            try:
                subsystem.render_queue_instance_with_executor_instance(queue, executor)
                while not state['finished']:
                    yield 0.1
            finally:
                executor.on_executor_finished_delegate.remove_callable(finished)
                executor.on_executor_errored_delegate.remove_callable(errored)
            if not state['success']:
                return result
            yield 0
            for branch, extension in (('SDR', 'png'), ('HDR', 'exr')):
                paths = list(output.glob(s['stem'] + '.' + branch + '.*.' + extension))
                if len(paths) != 1 or not paths[0].stat().st_size:
                    raise RuntimeError('Expected exactly one completed ' + branch + ' image.')
                s[branch.lower() + '_path'] = str(paths[0])
            s['output_file'] = str(output / (s['stem'] + '_Gainmap.jpg'))
        result.update(sdr_path=s['sdr_path'], hdr_path=s['hdr_path'])
        if _gainmap_image_size(s['sdr_path']) != (s['width'], s['height']) or _gainmap_image_size(s['hdr_path']) != (s['width'], s['height']):
            raise RuntimeError('Rendered SDR/HDR dimensions do not match the requested dimensions.')
        processing = {**context, **s, 'cache_dir': str(output), 'quality': s['hdr_quality']}
        state['phase'] = 'Filmic gainmap composition'
        batch._changed()
        notice = hdr._ProcessingNotice('Filmic HDR gainmap')
        # The EXR pixels are PQ already. zscale performs only gamut-matrix/range conversion.
        commands = hdr._conversion_args(processing, pq=True)
        hdr_filter = ('format=gbrpf32le,zscale=matrixin=gbr:transferin=smpte2084:primariesin=bt2020:'
                      'rangein=full:primaries=bt2020:transfer=smpte2084:matrix=bt2020nc:'
                      'range=limited:dither=error_diffusion,format=p010le')
        commands[1][commands[1].index('-vf') + 1] = hdr_filter
        ultra = hdr._ultrahdr_args(processing)
        ultra[ultra.index('-L') + 1] = str(s['peak_nits'])
        ultra.extend(['-c', '0', '-R', '0'])
        (output / 'commands.json').write_text(json.dumps([*commands, ultra], ensure_ascii=False, indent=2), encoding='utf-8')
        for command, label in zip([*commands, ultra], ('SDR', 'HDR', 'UltraHDR')):
            yield from hdr._run_process(command, output / (label + '.log'), label, notice=notice)
        final = Path(s['output_file'])
        temporary = output / 'result.jpg'
        if hdr._image_size(temporary) != (s['width'], s['height']):
            raise RuntimeError('The Ultra HDR output dimensions are incorrect.')
        final.parent.mkdir(parents=True, exist_ok=True)
        temporary.replace(final)
        success = True
        result.update(success=True, output_file=str(final))
        if state['notify']:
            try:
                ops._finish(context, str(final.parent), True, label='Filmic gainmap complete', refresh=False)
            except Exception as exc:
                mineprep.warn(str(exc))
        return result
    except hdr._ProcessingCancelled:
        result['cancelled'] = True
        return result
    except Exception as exc:
        state['errors'].append(str(exc))
        raise
    finally:
        if notice:
            notice.finish(success)
        ops._release_task(state)
