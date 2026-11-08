"""基于主面板渲染参数配置的 MRQ 动画渲染流程。"""
import json
import math
import re
import warnings
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import mineprep
import unreal
from mineprep import i18n

from . import encoding

_PANEL = '渲染输出子面板'
_TEMP_SEQUENCE = '/Game/Mineprep/Render/MC临时序列'
_PRESET = '/Game/Mineprep/Render/Mineprep自定义渲染配置'
_DIRECTOR = '/Game/Mineprep/MC_Blueprint/Core/MC导播台.MC导播台_C'
_DEFAULT_GAME_MODE = '/Script/MovieRenderPipelineCore.MoviePipelineGameMode'
# 独立于面板实例保存活动任务状态，关闭面板不会中断正在运行的渲染
_active = None
_batch_owner = None
_background = {}  # 后台视频任务的纯 Python 状态；渲染占用仍由 _active 单独管理。
MAX_BACKGROUND_ENCODERS = 2

_CONTROLS = {
    'image_formats': ('渲染图片格式选项', int),
    'width': ('X_分辨率', float), 'height': ('Y_分辨率', float),
    'custom_fps': ('🔲自定义帧率', int), 'fps_value': ('➖帧率滑条', float),
    'spatial': ('➖空间采样滑条', float), 'temporal': ('➖时间采样滑条', float),
    'warmup': ('暖场帧滑条', float), 'warmup_type': ('暖场类型选项', int),
    'color': ('色彩管理选项', int), 'hdr': ('🔲HDR渲染', int),
    'vr': ('🔲VR全景渲染', int), 'stereo': ('🔲3D立体渲染', int),
    'stereo_format': ('3D格式选项', int), 'audio': ('🔲渲染音频', int),
    'layers': ('🔲分层渲染', int), 'video': ('🔲视频编码输出', int),
    'delete_source': ('🔲删除原图', int), 'codec': ('视频编码选项', int),
    'container': ('视频封装格式选项', str), 'hardware': ('硬件选项', int),
    'chroma': ('色度抽样选项', str), 'image_transcode': ('图片转码选项', str),
    'quality': ('视频编码质量选项', int), 'name': ('视频名称文本框', str),
    'background_encode': ('🔲后台编码', int),
}


def _world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def _map_path():
    return _world().get_path_name().split('.')[0]


def _runtime_settings():
    prefs = _preferences()
    return dict(platform=unreal.GameplayStatics.get_platform_name(),
                project_dir=str(Path(unreal.Paths.project_dir()).resolve()),
                ffmpeg_path=prefs.get('ffmpeg_path', ''),
                open_after=str(prefs.get('open_file_after_render', 'false')).lower() == 'true',
                finish_sound=prefs.get('render_finish_sound', ''))


def prepare_settings(settings):
    """解析显式参数的当前工程环境与序列帧率，不访问旧控件。"""
    s = deepcopy(settings)
    s.setdefault('background_encode', 0)  # 兼容旧 JSON 配置。
    if s.get('map') and s['map'] != _map_path():
        raise RuntimeError(i18n('配置地图为 {map}，当前地图为 {map_path}；请先打开对应地图').format(map=str(s["map"]), map_path=str(_map_path())))
    rate = _sequence(s['sequence']).get_display_rate()
    s.update(_runtime_settings(), sequence_rate=(rate.numerator, rate.denominator))
    s['fps'] = int(s['fps_value']) if s['custom_fps'] == 1 else rate.numerator / rate.denominator
    s.setdefault('sequence_fallback', '')
    return s


def capture_settings():
    """采集可持久化参数；不保存资产，不包含机器路径与通知偏好。"""
    s = read_settings()
    if not unreal.EditorAssetLibrary.does_asset_exist(s['map']):
        raise RuntimeError(i18n('请先将当前地图保存为资产，再保存渲染配置'))
    keys = tuple(_CONTROLS) + ('game_mode', 'actor_layers', 'data_layers', 'main_pass', 'default_layer',
                               'dlss_mask', 'map', 'sequence', 'sequence_fallback')
    return {key: deepcopy(s[key]) for key in keys}


def _preset_settings(preset, *, sequence=None, frame=None, name=None, viewport=False, for_editor=False, **overrides):
    """Resolve a preset into one call's settings, without reading legacy controls."""
    kind = preset.get('kind', 'animation')
    if kind == 'animation' and frame is not None:
        raise ValueError(i18n('frame 仅用于静帧，视频使用序列播放范围'))
    fps = overrides.pop('fps', None)
    if fps is not None:
        if 'custom_fps' in overrides or 'fps_value' in overrides:
            raise ValueError(i18n('fps 不能与 custom_fps／fps_value 同时指定'))
        overrides.update(custom_fps=1, fps_value=fps)
    unknown = overrides.keys() - (_CONTROLS.keys() | {'game_mode', 'actor_layers', 'data_layers', 'main_pass', 'default_layer', 'dlss_mask'})
    if unknown:
        raise ValueError(i18n('未知的渲染参数：{fields}').format(fields=', '.join(sorted(unknown))))
    s = deepcopy(preset['settings'])
    s.update(deepcopy(overrides))
    if s['custom_fps'] == 1:
        value = s['fps_value']
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 1 or value != int(value)):
            raise ValueError(i18n('帧率须为正整数'))
        s['fps_value'] = int(value)
    if name is not None:
        s['name'] = name
    current_context = preset.get('context') == 'current'
    current = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    fallback = ''
    if viewport:
        target = _sequence(_TEMP_SEQUENCE)
        fallback = 'viewport'
    elif sequence is not None:
        target = _sequence(sequence if isinstance(sequence, str) else sequence.get_path_name())
        if not target.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
            raise ValueError(i18n('指定序列没有相机切换轨道'))
    elif current_context:
        target = current
        if not target or not target.find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
            if kind == 'animation' and (not for_editor or target is not None):
                if for_editor:
                    return dict(s, map=_map_path(), sequence='', sequence_fallback='')
                raise ValueError(i18n('视频需要有效相机序列，或指定 viewport=True'))
            fallback = 'missing_camera_cut' if target else 'no_sequence'
            target = _sequence(_TEMP_SEQUENCE)
    else:
        target = _sequence(s['sequence'])
        fallback = s.get('sequence_fallback', '')
    if current_context or viewport:
        s['map'] = _map_path()
    s.update(sequence=target.get_path_name(), sequence_fallback=fallback)
    if kind != 'animation':
        if frame is not None and (type(frame) is not int or fallback and frame != 0):
            raise ValueError(i18n('帧号须为整数；临时视角只支持第 0 帧'))
        if fallback:
            s['frame'] = 0
        elif frame is not None:
            s['frame'] = frame
        elif not current_context and sequence is None and 'frame' in s:
            pass  # Scene-bound presets retain their saved frame.
        elif current and current.get_path_name() == target.get_path_name():
            s['frame'] = current_frame(s)
        else:
            s['frame'] = int(target.get_playback_start())
        if kind == 'still':
            s = still_settings(s, s['frame'])
    else:
        s.pop('frame', None)
    return s


def render_preset(preset, *, sequence=None, frame=None, name=None, viewport=False,
                  on_done=None, notify=True, **overrides):
    """Render by filename (with or without .json), ID or name; overrides affect this call only."""
    from . import batch
    record = batch.get_store().find_preset(preset)
    s = _preset_settings(record, sequence=sequence, frame=frame, name=name, viewport=viewport,
                         for_editor=False, **overrides)
    kind = record.get('kind', 'animation')
    if kind == 'hdr':
        from . import hdr
        return hdr._start_pair(s, on_done=on_done, notify=notify)
    return _start_animation(s, record['backend'], kind=kind, on_done=on_done, notify=notify)


def _director():
    cls = unreal.load_class(None, _DIRECTOR)
    return unreal.GameplayStatics.get_actor_of_class(_world(), cls) if cls else None


def _sequence(path):
    sequence = unreal.load_asset(path) if path else None
    if not sequence:
        raise RuntimeError(i18n('无法加载渲染序列：{path}').format(path=str(path)))
    return sequence


def _game_mode(settings):
    path = settings.get('game_mode', _DEFAULT_GAME_MODE)
    if not path:
        return None
    mode = unreal.load_class(None, path)
    if not mode:
        raise RuntimeError(i18n('无法加载渲染游戏模式：{path}', 'Could not load render game mode: {path}').format(path=path))
    return mode


def _preferences():
    path = Path(mineprep.paths.config)
    return json.loads(path.read_text(encoding='utf-8-sig')).get('Settings', {}) if path.exists() else {}


def read_settings():
    """从主面板读取当前渲染输出设置，返回纯数据字典。"""
    panel = mineprep.panel(_PANEL).target
    if panel is None:
        raise RuntimeError(i18n('请先打开旧面板：{PANEL}').format(PANEL=str(_PANEL)))
    settings = {}
    for key, (name, kind) in _CONTROLS.items():
        try:
            settings[key] = mineprep.panel(f'{_PANEL}.{name}').get(kind)
        except Exception as exc:
            raise RuntimeError(i18n('无法读取控件 {PANEL}.{name}：{exc}').format(PANEL=str(_PANEL), name=str(name), exc=str(exc))) from exc
    mode = panel.get_editor_property('渲染游戏模式')
    settings['game_mode'] = mode.get_path_name() if mode else ''
    settings['actor_layers'] = [str(item.name) for item in panel.get_editor_property('Actor层')]
    settings['data_layers'] = [item.to_dict()['path_string'] for item in panel.get_editor_property('开放世界数据层')]
    settings['main_pass'] = panel.get_editor_property('单独渲染原图')
    settings['default_layer'] = panel.get_editor_property('单独渲染其他Actor')
    # 注释表记录了与语言无关的 ffmpeg 参数标识，返回 (参数标识, 本地化文本)
    for key, row in (('chroma', 3), ('image_transcode', 9)):
        settings[key] = str(mineprep.EditorBPLib('读取某格注释', 5, row, settings[key])[0])
    director = _director()  # 仅查询现有导播台，预览配置时不自动生成 Actor
    settings['dlss_mask'] = int(director.get_editor_property('DLSS/FSR')) if director else 1
    current = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    cuts = current.find_tracks_by_type(unreal.MovieSceneCameraCutTrack) if current else []
    settings['sequence_fallback'] = 'missing_camera_cut' if current and not cuts else 'no_sequence' if not current else ''
    settings['sequence'] = current.get_path_name() if current and cuts else _TEMP_SEQUENCE
    # 按实际提交给 MRQ 的序列读取帧率
    rate = _sequence(settings['sequence']).get_display_rate()
    settings['sequence_rate'] = (rate.numerator, rate.denominator)
    settings['fps'] = int(settings['fps_value']) if settings['custom_fps'] == 1 else rate.numerator / rate.denominator
    settings['map'] = _map_path()
    settings.update(_runtime_settings())
    return settings


def _validate(s):
    for key in ('width', 'height', 'spatial', 'temporal', 'fps'):
        if not math.isfinite(s[key]) or int(s[key]) < 1:
            raise ValueError(i18n('渲染参数 {key} 必须大于等于 1：{value}').format(key=str(key), value=str(s[key])))
    if not math.isfinite(s['warmup']) or int(s['warmup']) < 0:
        raise ValueError(i18n('暖场帧数不能为负数'))
    for key in ('codec', 'quality', 'hardware', 'color', 'stereo_format', 'warmup_type'):
        if s[key] < 0:
            raise ValueError(i18n('请先选择：{value}').format(value=str(_CONTROLS[key][0])))


def reset_output_name():
    """按聚焦序列和旧面板参数生成名称，保留相对子目录；不保存或渲染。"""
    values = {}
    for key in ('width', 'height', 'custom_fps', 'fps_value', 'color', 'vr', 'stereo', 'stereo_format', 'name'):
        name, kind = _CONTROLS[key]
        control = mineprep.panel(f'{_PANEL}.{name}')
        if control.target is None:
            raise RuntimeError(f'缺少控件：{_PANEL}.{name}')
        values[key] = control.get(kind)
    sequence = unreal.LevelSequenceEditorBlueprintLibrary.get_focused_level_sequence()
    title = sequence.get_name() if sequence else _map_path().rsplit('/', 1)[-1]
    rate = (sequence or _sequence(_TEMP_SEQUENCE)).get_display_rate()
    fps = values['fps_value'] if values['custom_fps'] == 1 else rate.numerator / rate.denominator
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError('帧率必须是大于 0 的有限数值')
    suffix = ('', '_HDR', '_ACES')[values['color']]
    if values['vr'] == 1:
        suffix += '_VR'
    if values['stereo'] == 1:
        suffix += ('_3D', '_3D(FSBS)', '_3D(FTB)', '_3D(Anaglyph)')[values['stereo_format']]
    stem = f"{title}_{int(values['width'])}x{int(values['height'])}_{fps:.6g}fps{suffix}"
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f{}]', '_', stem).rstrip(' .')
    folder = str(values['name']).replace('\\', '/').strip().rpartition('/')[0]
    result = f'{folder}/{stem}' if folder else stem
    encoding.output_name(result)  # 写回前检查相对目录，避免生成逃逸工程的路径。
    mineprep.panel(f'{_PANEL}.视频名称文本框').target.set_text(result)
    return result


def _set(obj, **values):
    for key, value in values.items():
        obj.set_editor_property(key, value)
    return obj


def _enum(cls, value):
    return next(item for item in cls if item.value == value)


def _setting(config, cls, enabled=True, **values):
    # WAV 的预览校验会查询 World；实际提交后设置才绑定渲染上下文。
    # 保留校验结果，仅抑制无 World 的临时配置产生的这条 Python 警告。
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message='MoviePipelinePrimaryConfig: No world was found.*', category=RuntimeWarning)
        setting = config.find_or_add_setting_by_class(cls, True, True)
    setting.set_is_enabled(enabled)
    return _set(setting, **values)


def _optional(config, path, enabled, **values):
    cls = unreal.load_class(None, path)
    if cls:
        return _setting(config, cls, enabled, **values)
    if enabled:
        raise RuntimeError(i18n('所选渲染功能需要未安装的 UE 类：{path}').format(path=str(path)))
    return None


def current_frame(settings):
    """时间线以序列显示帧率计数；临时序列使用第 0 帧。"""
    if settings.get('sequence_fallback'):
        return 0
    current = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
    if current and current.get_path_name() == settings['sequence']:
        return int(unreal.LevelSequenceEditorBlueprintLibrary.get_global_position().frame.frame_number.value)
    return int(settings.get('frame', 0))


def still_settings(settings, frame):
    """静帧沿用序列帧率，保留图片转码选项，关闭视频与音频。"""
    result = dict(deepcopy(settings), frame=0 if settings.get('sequence_fallback') else int(frame),
                  custom_fps=0, video=0, audio=0)
    if 'sequence_rate' in result:
        numerator, denominator = result['sequence_rate']
        result['fps'] = numerator / denominator
    return result


def build_config(settings):
    """根据渲染设置字典构建临时的 MoviePipelinePrimaryConfig 与输出目录路径（不修改现有资产或队列）。"""
    return _build_config(settings)


def _build_config(settings, base=None):
    s = dict(settings)
    if s.get('background_encode') == 1 and s['video'] == 1 and not s['image_formats'] & 15:
        s['image_formats'] = 4 if s['hdr'] == 1 else 1
    numerator, denominator = s['sequence_rate']
    s['fps'] = int(s['fps_value']) if s['custom_fps'] == 1 else numerator / denominator
    _validate(s)
    route = encoding.routing(s)
    if not route['native'] and not s['image_formats'] & 15:
        raise ValueError(i18n('请至少选择一种图片序列格式'))
    folder, stem = encoding.output_name(s['name'])
    output_dir = str(Path(s['project_dir']) / 'Saved' / 'MovieRenders' / folder).replace('\\', '/')
    stereo = s['stereo'] == 1
    flat_stereo = stereo and s['vr'] == 0 and s['platform'] in ('Windows', 'Linux')
    panoramic = s['vr'] == 1 or stereo and (s['vr'] == -1 or s['platform'] == 'Mac')
    panoramic_separate = stereo and (s['vr'] in (-1, 1) or s['platform'] == 'Mac') and s['stereo_format'] == 0
    suffix = '_{render_pass}_{camera_name}' if flat_stereo else '_{render_pass}' if panoramic_separate else ''
    config = unreal.MoviePipelinePrimaryConfig()
    if base is not None:
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='MoviePipelinePrimaryConfig: No world was found.*', category=RuntimeWarning)
            config.copy_from(base)
    _setting(config, unreal.MoviePipelineOutputSetting,
             OutputResolution=unreal.IntPoint(int(s['width']), int(s['height'])),
             OutputDirectory=unreal.DirectoryPath(output_dir),
             FileNameFormat=stem + '.{frame_number_rel}' + suffix,
             bUseCustomFrameRate=s['custom_fps'] == 1,
             OutputFrameRate=unreal.FrameRate(int(s['fps_value']), 1) if s['custom_fps'] == 1 else unreal.FrameRate(numerator, denominator),
             bUseCustomPlaybackRange=False, ZeroPadFrameNumbers=4, FrameNumberOffset=0)
    if s.get('single_frame'):
        output = config.find_setting_by_class(unreal.MoviePipelineOutputSetting)
        _set(output, bUseCustomPlaybackRange=True, CustomStartFrame=int(s['frame']),
             CustomEndFrame=int(s['frame']) + 1, FrameNumberOffset=0,
             FileNameFormat=stem + '.{frame_number}' + suffix)
    _setting(config, unreal.MoviePipelineAntiAliasingSetting,
             SpatialSampleCount=int(s['spatial']), TemporalSampleCount=int(s['temporal']),
             RenderWarmUpCount=int(s['warmup']) if s['warmup_type'] >= 1 else 0,
             bRenderWarmUpFrames=s['warmup_type'] == 1,
             EngineWarmUpCount=2 if s['warmup_type'] == 1 else int(s['warmup']))
    layer_values = dict(
        bAccumulatorIncludesAlpha=s['spatial'] + s['temporal'] >= 3,
        bRenderMainPass=s['main_pass'] or s['layers'] != 1,
        bAddDefaultLayer=s['default_layer'],
        ActorLayers=[unreal.ActorLayer(name=name) for name in s['actor_layers']] if s['layers'] == 1 else [],
        DataLayers=[unreal.SoftObjectPath(path) for path in s['data_layers']] if s['layers'] == 1 else [])
    _setting(config, unreal.MoviePipelineDeferredPassBase,
             s['vr'] != 1 and not stereo, **layer_values)
    _optional(config, '/Script/MoviePipelineMaskRenderPass.MoviePipelinePanoramicPass', panoramic,
              bStereo=stereo, bDisablePanoramic=s['vr'] == -1 or s['vr'] == 0 and stereo and s['platform'] == 'Mac',
              StereoOutputFormat=_enum(unreal.StereoOutputFormat, s['stereo_format']), NumHorizontalSteps=5 if stereo else 4,
              HorzFieldOfView=120., bAllocateHistoryPerPane=True, bFollowCameraOrientation=True)
    _optional(config, '/Script/DisplayClusterMoviePipeline.DisplayClusterMoviePipelineViewportPassBase',
              stereo and s['vr'] == 0, **layer_values)
    _optional(config, '/Script/DisplayClusterMoviePipeline.DisplayClusterMoviePipelineSettings',
              stereo and s['vr'] == 0)
    formats = s['image_formats']
    _setting(config, unreal.MoviePipelineImageSequenceOutput_PNG, bool(formats & 1) and not route['native'])
    _setting(config, unreal.MoviePipelineImageSequenceOutput_JPG, bool(formats & 2) and not route['native'])
    _setting(config, unreal.MoviePipelineImageSequenceOutput_EXR, bool(formats & 12) and not route['native'],
             bMultilayer=bool(formats & 8), Compression=unreal.EXRCompressionFormat.DWAA if formats & 8 else unreal.EXRCompressionFormat.NONE)
    _setting(config, unreal.MoviePipelineWaveOutput, s['audio'] == 1)
    _optional(config, '/Script/MovieRenderPipelineMP4Encoder.MoviePipelineMP4EncoderOutput',
              route['native'] and s['codec'] == 0,
              ConstantRateFactor=(28, 23, 19, 16)[s['quality']], bIncludeAudio=s['audio'] == 1)
    _optional(config, '/Script/AppleProResMedia.MoviePipelineAppleProResOutput',
              route['native'] and s['codec'] == 3,
              Codec=_enum(unreal.AppleProResEncoderCodec, s['quality'] + 1), bIncludeAudio=s['audio'] == 1)
    _setting(config, unreal.MoviePipelineCommandLineEncoder,
             route['ffmpeg'] and not s.get('single_frame') and not encoding.uses_background(s),
             Quality=_enum(unreal.MoviePipelineEncodeQuality, s['quality']),
             AdditionalCommandLineArgs='' if s.get('single_frame') else encoding.build_command(s, s['project_dir']),
             bDeleteSourceFiles=s['delete_source'] == 1,
             bSkipEncodeOnRenderCanceled=False, bWriteEachFrameDuration=False)
    ocio = unreal.OpenColorIODisplayConfiguration()
    if s['color'] in (1, 2):
        conversion = unreal.OpenColorIOColorConversionSettings(
            configuration_source=unreal.load_asset('/Game/Mineprep/Render/ACES_OCIO'),
            source_color_space=unreal.OpenColorIOColorSpace(color_space_name='Working Color Space', family_name='UE'))
        if s['color'] == 1:
            conversion.destination_display_view = unreal.OpenColorIODisplayView(
                display='Rec.2100-PQ - Display', view='ACES 2.0 - HDR 1000 nits (Rec.2020)')
        else:
            conversion.destination_color_space = unreal.OpenColorIOColorSpace(color_space_name='ACEScg', family_name='ACES')
        ocio.is_enabled = True
        ocio.color_configuration = conversion
    _setting(config, unreal.MoviePipelineColorSetting, s['color'] != 0,
             OCIOConfiguration=ocio, bDisableToneCurve=s['color'] != 0)
    _setting(config, unreal.MoviePipelineGameOverrideSetting,
             bCinematicQualitySettings=False, SoftGameModeOverride=_game_mode(s))
    # 读取最低有效位对应的档位序号 (1~5)；未安装 DLSS 时回退到 FSR3
    for existing in config.get_user_settings():
        if existing.get_class().get_path_name() in (
                '/Script/DLSSMoviePipelineSupport.MoviePipelineDLSSSetting',
                '/Script/FSR3MovieRenderPipeline.FSR3MoviePipelineSettings'):
            existing.set_is_enabled(False)
    mask = s['dlss_mask']
    bit = (mask & -mask).bit_length() if mask > 0 else 0
    if 1 <= bit <= 5:
        dlss = unreal.load_class(None, '/Script/DLSSMoviePipelineSupport.MoviePipelineDLSSSetting')
        if dlss:
            _setting(config, dlss, DLSSQuality=_enum(unreal.MoviePipelineDLSSQuality, 0 if bit == 1 else bit))
        else:
            fsr = unreal.load_class(None, '/Script/FSR3MovieRenderPipeline.FSR3MoviePipelineSettings')
            if fsr:
                quality_type = type(unreal.get_default_object(fsr).get_editor_property('FSR3Quality'))
                _setting(config, fsr, FSR3Quality=_enum(quality_type, bit))
    config.initialize_transient_settings()
    return config, output_dir


def _save_render_config(s, preserve_extra=True):
    preset = unreal.load_asset(_PRESET) if unreal.EditorAssetLibrary.does_asset_exist(_PRESET) else None
    config, folder = _build_config(s, preset if preserve_extra else None)
    if preset:
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='MoviePipelinePrimaryConfig: No world was found.*', category=RuntimeWarning)
            preset.copy_from(config)
        if not unreal.EditorAssetLibrary.save_loaded_asset(preset, False):
            raise RuntimeError(i18n('保存渲染预设失败，未提交任务'))
    _apply_render_settings(s)
    return config, folder


def _apply_render_settings(s):
    _apply_encoder_settings(s)
    director = _director() or mineprep.BPLib('导播台')
    if director:
        director.set_editor_property('HDR渲染', unreal.CheckBoxState.CHECKED if s['hdr'] == 1 else unreal.CheckBoxState.UNCHECKED)


def update_render_config(settings=None, *, preserve_extra=True):
    """更新会话设置，并在旧 MRQ 预设仍存在时保存它。"""
    _idle_subsystem()
    s = read_settings() if settings is None else prepare_settings(settings)
    return _save_render_config(s, preserve_extra)


def _transcode_still(s, state):
    """只处理本次 UE 回调中的静帧；成功校验后再替换输出和删除原图。"""
    from . import hdr
    files = {Path(path) for path in state.get('output_files', [])}
    priority = {'.exr': 0, '.png': 1, '.jpeg': 2, '.jpg': 2}
    sources = {}
    for path in sorted(files, key=lambda p: (priority.get(p.suffix.lower(), 9), str(p))):
        if path.suffix.lower() in priority and path.is_file():
            sources.setdefault(path.with_suffix(''), path)
    if not sources:
        if state['success']:
            raise RuntimeError('静帧转码没有收到本次渲染的图片文件')
        return
    background = bool(state.get('background_still'))
    cache = Path(state['cache_dir']) if background else Path(s['project_dir']) / 'cache' / 'RenderPanelStill' / uuid4().hex
    cache.mkdir(parents=True, exist_ok=True)
    prefs = hdr._context(None)  # 复用工具路径、进程等待和可取消提示。
    notice = hdr._ProcessingNotice('静帧图片转码')
    outputs = []
    done = False
    try:
        if background:
            from . import video
            yield from video.acquire(state, notice)
        for stem, source in sources.items():
            inputs = [source]
            flat_merge = s['stereo'] == 1 and s['vr'] == 0 and s['platform'] in ('Windows', 'Linux') and s['stereo_format'] != 0
            if flat_merge:
                if '_nDisplayLit_R' in stem.name:
                    continue
                if '_nDisplayLit_L' in stem.name:
                    right = sources.get(stem.with_name(stem.name.replace('_nDisplayLit_L', '_nDisplayLit_R')))
                    if right is None:
                        if state['success']:
                            raise RuntimeError(f'缺少右眼图片：{source}')
                        continue
                    inputs.append(right)
                    stem = stem.with_name(stem.name.replace('_nDisplayLit_L', ''))
            output = stem.with_name(stem.name + '.' + s['image_transcode'].lower())
            if background:
                output = Path(state['output_dir']) / output.relative_to(cache)
            output.parent.mkdir(parents=True, exist_ok=True)
            temp = cache / f'{len(outputs)}.{s["image_transcode"].lower()}'
            args = [prefs['ffmpeg'], *encoding.still_args(s, inputs, temp)]
            yield from hdr._run_process(args, cache / f'{len(outputs)}.log', '静帧图片转码', notice=notice)
            if not temp.is_file() or not temp.stat().st_size:
                raise RuntimeError(f'静帧转码未生成有效图片：{temp}')
            temp.replace(output)
            outputs.append(output)
        if not outputs and state['success']:
            raise RuntimeError('静帧转码未生成有效图片')
        if state['success'] and s['delete_source'] == 1:
            for source in files.difference(outputs):
                if source.suffix.lower() in priority:
                    source.unlink(missing_ok=True)
        state['converted_files'] = [str(path) for path in outputs]
        done = state['success'] and bool(outputs)
        if background and done:
            video.publish_sources(state)
    except hdr._ProcessingCancelled:
        state.update(success=False, cancelled=True)
    finally:
        if background:
            state['encoding_started'] = False
        notice.finish(done)
        if done:
            import shutil
            shutil.rmtree(cache)


def _apply_encoder_settings(s):
    """设置当前编辑器会话的 MRQ 命令行编码器默认参数（不写入工程 ini）。"""
    if s.get('single_frame') or not encoding.routing(s)['ffmpeg']:
        return
    platform = {'Windows': 'Win64', 'Mac': 'Mac', 'Linux': 'Linux'}[s['platform']]
    filename = 'ffmpeg.exe' if s['platform'] == 'Windows' else 'ffmpeg'
    executable = str(s['ffmpeg_path']).strip().strip('"') or str(Path(mineprep.paths.mineprep) / 'Render' / 'ffmpeg' / platform / filename)
    if not Path(executable).is_file():
        raise RuntimeError(i18n('找不到 ffmpeg：{executable}').format(executable=str(executable)))
    executable = executable.replace('\\', '/')
    if not encoding.uses_background(s):
        cdo = unreal.get_default_object(unreal.MoviePipelineCommandLineEncoderSettings.static_class())
        _set(cdo, ExecutablePath=executable,
             CommandLineFormat='-hide_banner -y -loglevel error {AdditionalLocalArgs}',
             VideoCodec='libx265', AudioCodec='aac',
             OutputFileExtension=s['container'] if s['video'] == 1 else s['image_transcode'].lower())
    command_settings = s
    if s.get('background_encode') == 1 and s['video'] == 1 and not s['image_formats'] & 15:
        command_settings = dict(s, image_formats=4 if s['hdr'] == 1 else 1)
    command = encoding.build_command(command_settings, s['project_dir'])
    unreal.log(f'{encoding.quote(executable)} -hide_banner -y -loglevel error {command}')


def _on_finished(state, executor, success):
    state['success'] = bool(success) and not state['fatal'] and state.get('job_success', True)
    state['finished'] = True


def _on_output(state, data):
    # 委托参数含 Pipeline/Job 等 UObject 引用。必须在回调内取出纯数据，
    # 不把整个 UE 结构体或嵌套的 Array/Map 包装器留到 PIE 清理后的下一帧。
    paths = []
    for shot in data.shot_data:
        for output in shot.render_pass_data.values():
            paths.extend(str(path) for path in output.file_paths)
    for shot in data.graph_data:
        for output in shot.render_layer_data.values():
            paths.extend(str(path) for path in output.file_paths)
    state.update(output_files=paths, job_success=bool(data.success))


def _on_error(state, executor, pipeline, fatal, text):
    if text:
        state['errors'].append(str(text))
    state['fatal'] = state['fatal'] or bool(fatal)


def _finish(s, output_dir, success, label=None, refresh=True):
    label = i18n('动画渲染完成') if label is None else label
    try:
        director = _director() if refresh else None
        if director:
            director.call_method('刷新状态', ())
        if not success:
            return
        if s['finish_sound']:
            sound = unreal.load_asset(s['finish_sound'])
            if sound:
                unreal.GameplayStatics.play_sound2d(_world(), sound)
        mineprep.prints(i18n('{label}：{path}').format(label=label, path=output_dir))
    finally:
        # 即使取消渲染或提示音异常，只要启用了“渲染后打开文件夹”且目录存在就打开输出目录
        if s['open_after'] and Path(output_dir).is_dir():
            mineprep.startfile(output_dir)


def _idle_subsystem(owner=None):
    """检查当前是否有正在运行的渲染或合成任务，空闲时返回 MoviePipelineQueueSubsystem。"""
    subsystem = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
    if _active is not None or subsystem.is_rendering() or (_batch_owner is not None and owner is not _batch_owner):
        raise RuntimeError(i18n('已有渲染或合成任务正在运行，请等待完成或在 UE 渲染窗口取消'))
    return subsystem


def _release_render(state):
    global _active
    state['render_released'] = True
    if _active is state:
        _active = None
    from . import batch
    batch._changed()


def _release_task(state):
    _background.pop(id(state), None)
    _release_render(state)


def _check_background_output(s):
    if not _background:
        return
    target = tuple(part.casefold() for part in encoding.output_name(s['name']))
    for state in _background.values():
        if state.get('output_key') == target:
            previous = state.get('settings', {})
            if s.get('single_frame') and previous.get('single_frame') and s['frame'] != previous['frame']:
                continue
            raise RuntimeError('此输出名称仍在后台处理中，请更改输出名称或等待编码结束')


def render_animation(settings=None, *, on_done=None, notify=True):
    """启动 MRQ 动画；显式参数不读取控件，回调在正常返回后收到结果。"""
    return _start_animation(settings, 'MRQ', on_done=on_done, notify=notify)


def render_still(settings=None, *, backend='MRQ', on_done=None, notify=True):
    """渲染光标所在静帧或显式 frame，不输出视频或音频。"""
    return _start_animation(settings, backend, kind='still', on_done=on_done, notify=notify)


def _start_animation(settings, backend, *, on_done=None, notify=True, owner=None, kind='animation'):
    global _active
    subsystem = _idle_subsystem(owner)
    state = {'finished': False, 'success': False, 'fatal': False, 'errors': [],
             'settings': read_settings() if settings is None else prepare_settings(settings),
             'backend': backend, 'notify': notify}
    if kind == 'still':
        s = state['settings']
        frame = s['frame'] if 'frame' in s else current_frame(s)
        state['settings'] = dict(still_settings(s, frame), single_frame=True)
    _check_background_output(state['settings'])
    _active = state
    try:
        task = _render_task(state, subsystem)
        state['task'] = task
        if on_done:
            task.on_done = on_done
        return task
    except Exception:
        _active = None
        raise


@mineprep.asynctask
def _render_task(state, subsystem):
    global _active
    try:
        s = state['settings']
        backend = state['backend']
        if backend == 'MRG':
            from . import mrg
            config, output_dir = mrg.build_config(s)
        else:
            config, output_dir = build_config(s)
        background = encoding.uses_background(s)
        if background:
            from . import video
            video.prepare(state, config, backend, output_dir)
        sequence = _sequence(s['sequence'])
        yield 0  # 先退出按钮回调，下一帧再执行资产保存与队列提交
        if subsystem.is_rendering():
            raise RuntimeError(i18n('另一个 MRQ 任务已启动，本次提交已停止'))
        if s['sequence_fallback'] == 'missing_camera_cut':
            mineprep.warn(i18n('当前时间线没有相机切换轨道，将使用默认设置和临时摄像机渲染'))
        _apply_render_settings(s)
        if not unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True):
            raise RuntimeError(i18n('保存地图／资源失败，未提交任务'))
        yield from _render_config(state, subsystem, config, sequence, backend)
        if background:
            # 场景恢复在交接前执行；后台结束时不能刷新下一项正在使用的导播台。
            director = _director()
            if director:
                director.call_method('刷新状态', ())
            yield 0
            _release_render(state)
            if not s.get('single_frame'):
                yield from video.encode(state)
        if s.get('single_frame') and s['image_transcode'] != 'No':
            yield from _transcode_still(s, state)
        # 正常完成或中途取消均通过回调收尾，不将用户在 UE 窗口取消渲染视为异常
        try:
            if state['notify']:
                _finish(s, output_dir, state['success'], refresh=not background,
                        label=i18n('静帧渲染完成') if s.get('single_frame') else
                        i18n('MRG 动画渲染完成') if backend == 'MRG' else i18n('动画渲染完成'))
            else:
                _finish(dict(s, open_after=False, finish_sound=''), output_dir, False, refresh=not background)
        except Exception as exc:
            mineprep.warn(i18n('渲染已结束，但结束处理失败：{exc}').format(exc=str(exc)))
        result = {'success': state['success'], 'output_dir': output_dir, 'errors': state['errors']}
        if s.get('single_frame'):
            result.update(converted_files=state.get('converted_files', []), cancelled=state.get('cancelled', False))
        if background and not s.get('single_frame'):
            result.update(output_files=state.get('encoded_files', []), cancelled=state.get('cancelled', False))
        return result
    finally:
        _release_task(state)


def _render_config(state, subsystem, config, sequence, backend='MRQ'):
    """提交一份临时配置并等候本执行器结束；调用者负责保存与整个任务的占用。"""
    if subsystem.is_rendering():
        raise RuntimeError(i18n('另一个 MRQ 任务已启动，本次提交已停止'))
    executor = unreal.MoviePipelinePIEExecutor()
    finished_cb = lambda ex, ok: _on_finished(state, ex, ok)
    error_cb = lambda ex, pipeline, fatal, text: _on_error(state, ex, pipeline, fatal, text)
    settings = state.get('settings', {})
    capture_output = bool(settings.get('single_frame') and settings.get('image_transcode', 'No') != 'No'
                          or encoding.uses_background(settings))
    output_cb = lambda data: _on_output(state, data)
    executor.on_executor_finished_delegate.add_callable(finished_cb)
    executor.on_executor_errored_delegate.add_callable(error_cb)
    if capture_output:
        executor.on_individual_job_work_finished_delegate.add_callable(output_cb)
    try:
        queue = subsystem.get_queue()
        queue.delete_all_jobs()
        job = unreal.MoviePipelineEditorLibrary.create_job_from_sequence(queue, sequence)
        if backend == 'MRG':
            job.set_graph_preset(config)
        else:
            job.set_configuration(config)
        subsystem.render_queue_with_executor_instance(executor)
        while not state['finished']:
            yield 0.1
    finally:
        executor.on_executor_finished_delegate.remove_callable(finished_cb)
        executor.on_executor_errored_delegate.remove_callable(error_cb)
        if capture_output:
            executor.on_individual_job_work_finished_delegate.remove_callable(output_cb)
