"""基于 Movie Render Graph (MRG) 的动态渲染图构建与动画渲染流程。"""
from pathlib import Path

import unreal
from mineprep import i18n

from . import encoding, ops


def _node(graph, cls, **values):
    """在渲染图中创建设置节点，并自动勾选所传属性的 bOverride_ 开关。"""
    node = graph.create_node_by_class(cls)
    for key, value in values.items():
        node.set_editor_property('bOverride_' + key, True)
        node.set_editor_property(key, value)
    return node


def _connect(graph, nodes, branch):
    # add_labeled_edge 的返回值表示“是否断开了旧连接”，新建有效连接时返回 False 属正常现象
    for source, target in zip(nodes, nodes[1:]):
        graph.add_labeled_edge(source, '', target, '')
    graph.add_labeled_edge(nodes[-1], '', graph.get_output_node(), branch)


def _ocio(color):
    config = unreal.OpenColorIODisplayConfiguration()
    if color in (1, 2):
        conversion = unreal.OpenColorIOColorConversionSettings(
            configuration_source=unreal.load_asset('/Game/Mineprep/Render/ACES_OCIO'),
            source_color_space=unreal.OpenColorIOColorSpace(color_space_name='Working Color Space', family_name='UE'))
        if color == 1:
            conversion.destination_display_view = unreal.OpenColorIODisplayView(
                display='Rec.2100-PQ - Display', view='ACES 2.0 - HDR 1000 nits (Rec.2020)')
        else:
            conversion.destination_color_space = unreal.OpenColorIOColorSpace(color_space_name='ACEScg', family_name='ACES')
        config.is_enabled = True
        config.color_configuration = conversion
    return config


def build_config(settings):
    """在内存中构建 MovieGraphConfig 渲染图与输出目录路径（不落盘保存预设资产）。"""
    s = dict(settings)
    if s.get('background_encode') == 1 and s['video'] == 1 and not s['image_formats'] & 15:
        s['image_formats'] = 4 if s['hdr'] == 1 else 1
    numerator, denominator = s['sequence_rate']
    s['fps'] = int(s['fps_value']) if s['custom_fps'] == 1 else numerator / denominator
    ops._validate(s)
    if s['stereo'] == 1 or s['layers'] == 1:
        raise ValueError(i18n('MRG 暂不支持旧面板的 3D 立体／分层渲染，请使用原“一键渲染动画”按钮（MRQ）'))
    mask = s['dlss_mask']
    bit = (mask & -mask).bit_length() if mask > 0 else 0
    dlss = 2 <= bit <= 5
    if dlss and s['vr'] == 1:
        raise ValueError(i18n('MRG 全景与 DLSS 不能共用同一个渲染器，请关闭 DLSS 或使用 MRQ'))
    if dlss and not hasattr(unreal, 'MovieGraphDLSSRenderPassNode'):
        raise ValueError(i18n('当前引擎没有 MRG DLSS 渲染器，请关闭 DLSS 或使用 MRQ；MRG 入口不回退到 FSR'))
    # 当前 DLSS 插件的 MRG 节点未暴露 bOverride_DLSSQuality，求值时固定使用默认的“平衡”档
    if dlss and bit != 3:
        raise ValueError(i18n('当前 DLSS 插件的 MRG 节点只生效“平衡”档，请选择平衡、关闭 DLSS 或使用 MRQ'))
    route = encoding.routing(s)
    if not route['native'] and not s['image_formats'] & 15:
        raise ValueError(i18n('请至少选择一种图片序列格式'))
    folder, stem = encoding.output_name(s['name'])
    output_dir = (Path(s['project_dir']) / 'Saved' / 'MovieRenders' / folder).as_posix()
    graph = unreal.MovieGraphConfig()
    output = _node(graph, unreal.MovieGraphGlobalOutputSettingNode,
                   OutputResolution=unreal.MovieGraphNamedResolution(
                       profile_name='Custom', resolution=unreal.IntPoint(int(s['width']), int(s['height']))),
                   OutputDirectory=unreal.DirectoryPath(output_dir), ZeroPadFrameNumbers=4,
                   bOverwriteExistingOutput=True)
    if s.get('single_frame'):
        bound = unreal.MovieGraphSequencePlaybackRangeBound
        range_type = unreal.MovieGraphSequenceRangeType.CUSTOM
        ops._set(output, bOverride_CustomPlaybackRangeStart=True, bOverride_CustomPlaybackRangeEnd=True,
                 CustomPlaybackRangeStart=bound(type=range_type, value=int(s['frame'])),
                 CustomPlaybackRangeEnd=bound(type=range_type, value=int(s['frame']) + 1))
    if s['custom_fps'] == 1:
        ops._set(output, bOverride_OutputFrameRate=True, OutputFrameRate=unreal.FrameRate(int(s['fps_value']), 1))
    globals_ = [output,
                _node(graph, unreal.MovieGraphSamplingMethodNode, TemporalSampleCount=int(s['temporal'])),
                _node(graph, unreal.MovieGraphWarmUpSettingNode, NumWarmUpFrames=int(s['warmup']),
                      bEmulateMotionBlur=s['warmup_type'] == 1),
                _node(graph, unreal.MovieGraphGlobalGameOverridesNode,
                      SoftGameModeOverride=ops._game_mode(s))]
    if s['audio'] == 1:
        globals_.append(_node(graph, unreal.MovieGraphAudioOutputNode, FileNameFormat=stem))
    if route['ffmpeg'] and not s.get('single_frame') and not encoding.uses_background(s):
        # 用 {Quality} 一次性注入完整编码命令，避免路径或滤镜中的花括号被 MRG 当成格式占位符解析
        globals_.append(_node(graph, unreal.MovieGraphCommandLineEncoderNode,
                             FileNameFormat=stem, CommandLineFormat='{Quality}',
                             EncodeSettings=encoding.build_command(s, s['project_dir']),
                             VideoCodec='libx265', AudioCodec='aac',
                             OutputFileExtension=s['container'] if s['video'] == 1 else s['image_transcode'].lower(),
                             bDeleteSourceFiles=s['delete_source'] == 1, bSkipEncodeOnRenderCanceled=False))
    graph.add_output('Beauty')
    layer = _node(graph, unreal.MovieGraphRenderLayerNode, LayerName='Beauty')
    renderer_cls = (unreal.MovieGraphDeferredPanoramicNode if s['vr'] == 1 else
                    unreal.MovieGraphDLSSRenderPassNode if dlss else unreal.MovieGraphDeferredRenderPassNode)
    renderer = _node(graph, renderer_cls, SpatialSampleCount=int(s['spatial']),
                     bDisableToneCurve=s['color'] != 0, bAllowOCIO=True)
    if s['vr'] == 1:
        ops._set(renderer, bOverride_NumHorizontalSteps=True, NumHorizontalSteps=4,
                 bOverride_bAllocateHistoryPerPane=True, bAllocateHistoryPerPane=True,
                 bOverride_bFollowCameraOrientation=True, bFollowCameraOrientation=True)
    beauty = [layer, renderer]
    ocio = _ocio(s['color'])
    if route['native']:
        if s['codec'] == 0:
            video = _node(graph, unreal.MovieGraphMP4EncoderNode,
                          EncodingRateControl=unreal.MoviePipelineMP4EncodeRateControlMode.QUALITY,
                          ConstantRateFactor=(28, 23, 19, 16)[s['quality']], bIncludeAudio=s['audio'] == 1,
                          FileNameFormat=stem, OCIOConfiguration=ocio)
        else:
            video = _node(graph, unreal.MovieGraphAppleProResNode,
                          Quality=ops._enum(unreal.AppleProResEncoderCodec, s['quality'] + 1),
                          bIncludeAudio=s['audio'] == 1, FileNameFormat=stem, OCIOConfiguration=ocio)
        beauty.append(video)
    else:
        formats = s['image_formats']
        for flag, cls in ((1, unreal.MovieGraphImageSequenceOutputNode_PNG),
                          (2, unreal.MovieGraphImageSequenceOutputNode_JPG),
                          (12, unreal.MovieGraphImageSequenceOutputNode_MultiLayerEXR if formats & 8
                           else unreal.MovieGraphImageSequenceOutputNode_EXR)):
            if not formats & flag:
                continue
            node = _node(graph, cls, FileNameFormat=stem + ('.{frame_number}' if s.get('single_frame')
                                                          else '.{frame_number_rel}'), OCIOConfiguration=ocio)
            if flag == 12:
                ops._set(node, bOverride_Compression=True,
                         Compression=unreal.EXRCompressionFormat.DWAA if formats & 8 else unreal.EXRCompressionFormat.NONE)
            # 多层 EXR 属于 Globals 全局输出节点，其余图片格式连接到 Beauty 分支
            (globals_ if flag == 12 and formats & 8 else beauty).append(node)
    _connect(graph, globals_, 'Globals')
    _connect(graph, beauty, 'Beauty')
    return graph, output_dir


def render_animation(settings=None, *, on_done=None, notify=True):
    """使用独立内存图启动动画；参数、回调和任务生命周期与 MRQ 入口一致。"""
    return ops._start_animation(settings, 'MRG', on_done=on_done, notify=notify)
