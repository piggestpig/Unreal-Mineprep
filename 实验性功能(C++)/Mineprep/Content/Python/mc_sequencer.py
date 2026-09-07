"""
Sequencer 关键帧工具 — 等效于细节面板菱形“添加关键帧”按钮。

支持：
  - Transform（默认）：Location / Rotation / Scale 及单轴子通道
  - 常见属性：bool, int, float, Vector, Vector2D, Rotator, LinearColor, str

限制：
  - 首版以 Possessable Actor/Component 为主；Spawnable 绑定可能需手动添加
  - 子序列内使用 local 时间与绑定（与 Sequencer UI 一致）
  - 暂不支持 enum/byte/object 引用等复杂类型
"""

import fnmatch
from collections.abc import Iterable
from types import SimpleNamespace

import unreal
from mc_utils import throw, uclass, world, undo

_TIME_UNIT = unreal.MovieSceneTimeUnit.DISPLAY_RATE

_channel_gather_loc = {}
_key_gather_loc = {}

_TRANSFORM_CHANNELS = (
    'Location.X', 'Location.Y', 'Location.Z',
    'Rotation.X', 'Rotation.Y', 'Rotation.Z',
    'Scale.X', 'Scale.Y', 'Scale.Z',
)

_TRANSFORM_PROP_CHANNELS = {
    '': _TRANSFORM_CHANNELS,
    'Transform': _TRANSFORM_CHANNELS,
    'transform': _TRANSFORM_CHANNELS,
    'Location': ('Location.X', 'Location.Y', 'Location.Z'),
    'RelativeLocation': ('Location.X', 'Location.Y', 'Location.Z'),
    'Rotation': ('Rotation.X', 'Rotation.Y', 'Rotation.Z'),
    'RelativeRotation': ('Rotation.X', 'Rotation.Y', 'Rotation.Z'),
    'Scale': ('Scale.X', 'Scale.Y', 'Scale.Z'),
    'RelativeScale3D': ('Scale.X', 'Scale.Y', 'Scale.Z'),
}

_LOCATION_PROPS = frozenset({'Location', 'RelativeLocation'})
_ROTATION_PROPS = frozenset({'Rotation', 'RelativeRotation'})
_SCALE_PROPS = frozenset({'Scale', 'RelativeScale3D'})


def resolve_sequence(target=None) -> unreal.LevelSequence:
    """解析 Level Sequence：默认取当前聚焦/打开的序列，也可传对象或资产路径"""
    if target is None:
        sequence = unreal.LevelSequenceEditorBlueprintLibrary.get_focused_level_sequence()
        if not sequence:
            sequence = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
        return sequence
    if isinstance(target, unreal.LevelSequence):
        return target
    if isinstance(target, str):
        return unreal.load_asset(target, unreal.LevelSequence)
    return None


def _get_active_sequence() -> unreal.LevelSequence:
    """获取当前序列，不存在则抛错"""
    sequence = resolve_sequence()
    if not sequence:
        throw('未打开 Level Sequence，请先在 Sequencer 中打开或聚焦一个序列')
    return sequence


def sequencer_frame(sequence=None) -> int:
    """获取 Sequencer 播放头所在帧号"""
    sequence = resolve_sequence(sequence)
    if not sequence:
        throw('未打开 Level Sequence，请先在 Sequencer 中打开或聚焦一个序列')
    return _resolve_frame(None, sequence)


def sequencer_time(sequence=None) -> float:
    """获取 Sequencer 播放头所在时间（秒）"""
    sequence = resolve_sequence(sequence)
    if not sequence:
        throw('未打开 Level Sequence，请先在 Sequencer 中打开或聚焦一个序列')
    frame_number = _resolve_frame(None, sequence)
    rate = sequence.get_display_rate()
    return frame_number * rate.denominator / rate.numerator


def _resolve_frame(time, sequence) -> int:
    """将 None/帧/秒 解析为整数帧号；None 取播放头"""
    if time is None:
        playback = unreal.LevelSequenceEditorBlueprintLibrary.get_local_position(time_unit=_TIME_UNIT)
        return playback.frame.frame_number.value

    if isinstance(time, unreal.FrameNumber):
        return time.value

    if isinstance(time, unreal.FrameTime):
        return time.frame_number.value

    if isinstance(time, int):
        return time

    if isinstance(time, float):
        rate = sequence.get_display_rate()
        return int(round(time * rate.numerator / rate.denominator))

    throw(f'不支持的时间类型: {type(time).__name__}')


def _binding_id(binding) -> unreal.MovieSceneObjectBindingID:
    """把 binding 转成 MovieSceneObjectBindingID"""
    binding_id = unreal.MovieSceneObjectBindingID()
    binding_id.set_editor_property('Guid', binding.get_id())
    return binding_id


def _iter_bindings(sequence):
    """递归遍历序列全部绑定（含子 Possessable）"""
    stack = list(sequence.get_bindings())
    while stack:
        binding = stack.pop()
        yield binding
        stack.extend(binding.get_child_possessables())


def _iter_all_tracks(sequence):
    """遍历根轨道与所有绑定下的轨道"""
    if not sequence:
        return
    for track in sequence.get_tracks():
        yield track
    for binding in _iter_bindings(sequence):
        for track in binding.get_tracks():
            yield track


def _find_binding_for_object(sequence, obj):
    """在序列中查找对象对应的绑定"""
    for binding in _iter_bindings(sequence):
        bound_objects = unreal.LevelSequenceEditorBlueprintLibrary.get_bound_objects(_binding_id(binding))
        for bound in bound_objects:
            if bound == obj:
                return binding
    return None


def _is_actor(obj) -> bool:
    """判断是否为 Actor"""
    return isinstance(obj, unreal.Actor)


def _is_scene_component(obj) -> bool:
    """判断是否为 SceneComponent"""
    return isinstance(obj, unreal.SceneComponent)


def _ensure_binding(sequence, obj):
    """确保对象已绑定到序列，必要时创建并挂到父绑定"""
    binding = _find_binding_for_object(sequence, obj)
    if binding:
        return binding

    if _is_actor(obj):
        return sequence.add_possessable(obj)

    if _is_scene_component(obj):
        binding = sequence.add_possessable(obj)
        owner = obj.get_owner()
        if owner:
            owner_binding = _find_binding_for_object(sequence, owner)
            if owner_binding:
                binding.set_parent(owner_binding)
        return binding

    throw(f'obj 必须是 Actor 或 SceneComponent，当前类型: {type(obj).__name__}')


def _get_or_create_section(track):
    """取轨道首个 section，没有则新建"""
    sections = track.get_sections()
    if sections:
        return sections[0]

    section = track.add_section()
    section.set_start_frame_bounded(0)
    section.set_end_frame_bounded(0)
    return section


def _channel_name(channel) -> str:
    """读取 ScriptingChannel 的通道名"""
    try:
        return str(channel.get_editor_property('channel_name'))
    except Exception:
        return str(channel.channel_name)


def _text(value) -> str:
    """安全转为字符串，None 得到空串"""
    return str(value) if value is not None else ''


def _join_path(*parts) -> str:
    """用 '.' 拼接层级路径，跳过空段"""
    return '.'.join(str(part) for part in parts if part is not None and str(part))


def _track_short_name(track) -> str:
    """轨道短显示名（display name / 属性名 / 类名）"""
    try:
        label = track.get_display_name()
        if label:
            return _text(label)
    except Exception:
        pass
    if isinstance(track, unreal.MovieScenePropertyTrack):
        try:
            return str(track.get_property_name())
        except Exception:
            pass
    class_name = track.get_class().get_name()
    if class_name.startswith('MovieScene') and class_name.endswith('Track'):
        return class_name[len('MovieScene'):-len('Track')]
    return class_name


def _section_track(section) -> unreal.MovieSceneTrack:
    """通过 get_outer 取 section 所属轨道"""
    outer = section.get_outer()
    return outer if isinstance(outer, unreal.MovieSceneTrack) else None


def _binding_track_map(sequence):
    """构建 id(track)->binding 映射"""
    mapping = {}
    if not sequence:
        return mapping
    for binding in _iter_bindings(sequence):
        for track in binding.get_tracks():
            mapping[id(track)] = binding
    return mapping


def _register_channel_loc(section, channel_index, channel):
    """登记 channel wrapper 的 (section, index) 位置"""
    _channel_gather_loc[id(channel)] = (section, channel_index)


def _register_key_loc(section, channel_index, key_index, key):
    """登记 key wrapper 的 (section, channel_index, key_index)"""
    _key_gather_loc[id(key)] = (section, channel_index, key_index)


def _channels_from_section(section):
    """取出 section 全部通道并登记位置"""
    channels = []
    try:
        raw = section.get_all_channels()
    except Exception:
        return channels
    for channel_index, channel in enumerate(raw):
        _register_channel_loc(section, channel_index, channel)
        channels.append(channel)
    return channels


def _keys_from_channel(channel, section=None, channel_index=-1):
    """取出 channel 全部关键帧并登记位置"""
    if section is None:
        section, channel_index = _channel_gather_loc.get(id(channel), (None, -1))
    keys = []
    try:
        raw = channel.get_keys()
    except Exception:
        return keys
    for key_index, key in enumerate(raw):
        if section is not None and channel_index >= 0:
            _register_key_loc(section, channel_index, key_index, key)
        keys.append(key)
    return keys


def _same_scripting_object(a, b) -> bool:
    """比较两个 Scripting 包装对象是否同一实体"""
    if a is b:
        return True
    try:
        return a == b
    except Exception:
        return False


def _build_label_context(sequence):
    """一次遍历构建 label 用的层级索引上下文"""
    ctx = SimpleNamespace(
        sequence=sequence,
        track_bindings=_binding_track_map(sequence),
        channel_labels={},
        key_labels={},
        _channel_loc_cache={},
        _key_loc_cache={},
    )
    if not sequence:
        return ctx
    for track in _iter_all_tracks(sequence):
        for section in track.get_sections():
            section_label = None
            try:
                channels = section.get_all_channels()
            except Exception:
                continue
            for channel_index, channel in enumerate(channels):
                if section_label is None:
                    section_label = label_section(section, ctx)
                channel_label = _join_path(section_label, _channel_name(channel))
                ctx.channel_labels[(id(section), channel_index)] = channel_label
                try:
                    for key_index, key in enumerate(channel.get_keys()):
                        suffix = _format_key_suffix(key)
                        ctx.key_labels[(id(section), channel_index, key_index)] = (
                            _join_path(channel_label, suffix)
                        )
                except Exception:
                    pass
    return ctx


def _resolve_channel(channel, ctx):
    """解析 channel 所属 section 与下标"""
    cached = ctx._channel_loc_cache.get(id(channel))
    if cached is not None:
        return cached
    gathered = _channel_gather_loc.get(id(channel))
    if gathered is not None:
        ctx._channel_loc_cache[id(channel)] = gathered
        return gathered
    for track in _iter_all_tracks(ctx.sequence):
        for section in track.get_sections():
            try:
                channels = section.get_all_channels()
            except Exception:
                continue
            for channel_index, candidate in enumerate(channels):
                if _same_scripting_object(candidate, channel):
                    loc = (section, channel_index)
                    ctx._channel_loc_cache[id(channel)] = loc
                    return loc
    ctx._channel_loc_cache[id(channel)] = (None, -1)
    return None, -1


def _resolve_key(key, ctx):
    """解析 key 所属 section/channel 下标"""
    cached = ctx._key_loc_cache.get(id(key))
    if cached is not None:
        return cached
    gathered = _key_gather_loc.get(id(key))
    if gathered is not None:
        ctx._key_loc_cache[id(key)] = gathered
        return gathered
    for track in _iter_all_tracks(ctx.sequence):
        for section in track.get_sections():
            try:
                channels = section.get_all_channels()
            except Exception:
                continue
            for channel_index, channel in enumerate(channels):
                try:
                    keys = channel.get_keys()
                except Exception:
                    continue
                for key_index, candidate in enumerate(keys):
                    if _same_scripting_object(candidate, key):
                        loc = (section, channel_index, key_index)
                        ctx._key_loc_cache[id(key)] = loc
                        return loc
    ctx._key_loc_cache[id(key)] = (None, -1, -1)
    return None, -1, -1


def binding_label(binding) -> str:
    """获取绑定的显示名称"""
    try:
        label = binding.get_display_name()
        if label:
            return _text(label)
    except Exception:
        pass
    try:
        return binding.get_name()
    except Exception:
        return str(binding)


def label_track(track, ctx) -> str:
    """生成轨道的层级显示名，如 'Alex.变换'"""
    short = _track_short_name(track)
    binding = ctx.track_bindings.get(id(track))
    if binding:
        return _join_path(binding_label(binding), short)
    return short


def label_section(section, ctx) -> str:
    """生成片段的层级显示名；同轨多片段时追加 [index]"""
    track = _section_track(section)
    if not track:
        class_name = section.get_class().get_name()
        if class_name.startswith('MovieScene') and class_name.endswith('Section'):
            return class_name[len('MovieScene'):-len('Section')]
        return class_name
    base = label_track(track, ctx)
    sections = track.get_sections()
    if len(sections) > 1:
        try:
            return f'{base}[{sections.index(section)}]'
        except ValueError:
            pass
    return base


def label_channel(channel, ctx) -> str:
    """生成通道的层级显示名，如 'Alex.变换.Location.X'"""
    section, channel_index = _resolve_channel(channel, ctx)
    if section is not None and channel_index >= 0:
        label = ctx.channel_labels.get((id(section), channel_index))
        if label:
            return label
    return _channel_name(channel)


def _format_key_value(value) -> str:
    """把关键帧值格式化为简短可读字符串"""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return str(round(value, 4))
    if isinstance(value, str):
        return value
    type_name = value.get_class().get_name() if hasattr(value, 'get_class') else type(value).__name__
    if type_name.startswith('MovieScene'):
        type_name = type_name[len('MovieScene'):]
    return type_name


def _format_key_suffix(key) -> str:
    """关帧后缀，格式 '@帧:值'"""
    frame = key.get_time().frame_number.value
    try:
        value = key.get_value()
    except Exception:
        return f'@{frame}:?'
    return f'@{frame}:{_format_key_value(value)}'


def label_key(key, ctx) -> str:
    """生成关键帧的层级显示名，后缀格式为 '@帧:值'"""
    section, channel_index, key_index = _resolve_key(key, ctx)
    if section is not None and channel_index >= 0 and key_index >= 0:
        label = ctx.key_labels.get((id(section), channel_index, key_index))
        if label:
            return label
    return _format_key_suffix(key)


def sequence_label(sequence) -> str:
    """获取序列名称"""
    return sequence.get_name() if sequence else ''


def is_binding(obj) -> bool:
    """判断对象是否为 Sequencer 绑定包装器"""
    return hasattr(obj, 'get_tracks') and hasattr(obj, 'get_display_name') and hasattr(obj, 'get_id')


def labels_for(objects, sequence=None) -> list[str]:
    """批量为 bindings/tracks/sections/channels/keys 生成层级显示名"""
    if not objects:
        return []
    ctx = _build_label_context(sequence or resolve_sequence())
    sample = objects[0]
    if is_binding(sample):
        return [binding_label(obj) for obj in objects]
    if isinstance(sample, unreal.MovieSceneTrack):
        return [label_track(obj, ctx) for obj in objects]
    if isinstance(sample, unreal.MovieSceneSection):
        return [label_section(obj, ctx) for obj in objects]
    if isinstance(sample, unreal.MovieSceneScriptingChannel):
        return [label_channel(obj, ctx) for obj in objects]
    if isinstance(sample, unreal.MovieSceneScriptingKey):
        return [label_key(obj, ctx) for obj in objects]
    if isinstance(sample, unreal.LevelSequence):
        return [sequence_label(obj) for obj in objects]
    return [obj.get_name() for obj in objects]


def _filter_tracks(tracks, name=None, ctx=None):
    """按显示名/短名/内部名通配过滤轨道"""
    tracks = list(tracks)
    if not name:
        return tracks
    if isinstance(name, type):
        return [track for track in tracks if isinstance(track, name)]
    if isinstance(name, str):
        pattern = name if '*' in name else f'*{name}*'
        if ctx is None:
            ctx = _build_label_context(resolve_sequence())
        result = []
        for track in tracks:
            label = label_track(track, ctx)
            short = _track_short_name(track)
            internal = ''
            try:
                internal = track.get_name()
            except Exception:
                pass
            if (fnmatch.fnmatch(label, pattern)
                    or fnmatch.fnmatch(short, pattern)
                    or (internal and fnmatch.fnmatch(internal, pattern))):
                result.append(track)
        return result
    if callable(name):
        return [track for track in tracks if name(track)]
    return []


def _filter_sections(sections, name=None, ctx=None):
    """按层级显示名通配过滤片段"""
    sections = list(sections)
    if not name:
        return sections
    if isinstance(name, type):
        return [section for section in sections if isinstance(section, name)]
    if isinstance(name, str):
        pattern = name if '*' in name else f'*{name}*'
        if ctx is None:
            ctx = _build_label_context(resolve_sequence())
        return [
            section for section in sections
            if fnmatch.fnmatch(label_section(section, ctx), pattern)
        ]
    if callable(name):
        return [section for section in sections if name(section)]
    return []


def filter_items(items, name=None):
    """通用过滤：轨道/片段按显示名，其它对象回退到内部名通配"""
    items = list(items)
    if not items or not name:
        return items
    sample = items[0]
    if isinstance(sample, unreal.MovieSceneTrack):
        return _filter_tracks(items, name)
    if isinstance(sample, unreal.MovieSceneSection):
        return _filter_sections(items, name)
    if isinstance(name, type):
        return [item for item in items if isinstance(item, name)]
    if isinstance(name, str):
        pattern = name if '*' in name else f'*{name}*'
        return unreal.EditorFilterLibrary.by_id_name(
            items, pattern, unreal.EditorScriptingStringMatchType.MATCHES_WILDCARD,
        )
    if callable(name):
        return [item for item in items if name(item)]
    return []


def _filter_channels(channels, name=None, ctx=None):
    """按通道名或完整路径通配过滤通道"""
    channels = list(channels)
    if not name:
        return channels
    if isinstance(name, type):
        return [c for c in channels if isinstance(c, name)]
    if isinstance(name, str):
        pattern = name if '*' in name else f'*{name}*'
        if ctx is None:
            ctx = _build_label_context(resolve_sequence())
        return [
            c for c in channels
            if fnmatch.fnmatch(_channel_name(c), pattern)
            or fnmatch.fnmatch(label_channel(c, ctx), pattern)
        ]
    if callable(name):
        return [c for c in channels if name(c)]
    return []


def _filter_keys(keys, name=None, ctx=None):
    """按完整路径或后缀通配过滤关帧"""
    keys = list(keys)
    if not name:
        return keys
    if isinstance(name, int):
        return [k for k in keys if k.get_time().frame_number.value == name]
    if isinstance(name, type):
        return [k for k in keys if isinstance(k, name)]
    if isinstance(name, str):
        pattern = name if '*' in name else f'*{name}*'
        if ctx is None:
            ctx = _build_label_context(resolve_sequence())
        return [
            k for k in keys
            if fnmatch.fnmatch(label_key(k, ctx), pattern)
            or fnmatch.fnmatch(_format_key_suffix(k), pattern)
        ]
    if callable(name):
        return [k for k in keys if name(k)]
    return []


def _filter_bindings(bindings, name=None):
    """按显示名/内部名通配过滤绑定"""
    bindings = list(bindings)
    if not name:
        return bindings
    if callable(name):
        return [b for b in bindings if name(b)]
    if isinstance(name, str):
        pattern = name if '*' in name else f'*{name}*'
        result = []
        for binding in bindings:
            display = binding_label(binding)
            internal = ''
            try:
                internal = binding.get_name()
            except Exception:
                pass
            if fnmatch.fnmatch(display, pattern) or (internal and fnmatch.fnmatch(internal, pattern)):
                result.append(binding)
        return result
    return []


def gather_bindings(source, name=None):
    """从序列收集绑定，可按显示名过滤"""
    if source is None:
        return []
    if is_binding(source):
        return _filter_bindings([source], name)
    if isinstance(source, unreal.LevelSequence):
        return _filter_bindings(_iter_bindings(source), name)
    if isinstance(source, Iterable) and not isinstance(source, (str, bytes)):
        items = list(source)
        if not items:
            return []
        if is_binding(items[0]):
            return _filter_bindings(items, name)
        if isinstance(items[0], unreal.LevelSequence):
            bindings = []
            for seq in items:
                bindings.extend(gather_bindings(seq))
            return _filter_bindings(bindings, name)
    return []


def _tracks_from_bindings(bindings):
    """汇总多个绑定下的全部轨道"""
    tracks = []
    for binding in bindings:
        tracks.extend(binding.get_tracks())
    return tracks


def gather_tracks(source, name=None):
    """从序列/绑定收集轨道，可按显示名过滤"""
    if source is None:
        return []
    if isinstance(source, unreal.MovieSceneTrack):
        return _filter_tracks([source], name)
    if is_binding(source):
        return _filter_tracks(_tracks_from_bindings([source]), name)
    if isinstance(source, unreal.LevelSequence):
        return _filter_tracks(list(_iter_all_tracks(source)), name)
    if isinstance(source, Iterable) and not isinstance(source, (str, bytes)):
        items = list(source)
        if not items:
            return []
        if isinstance(items[0], unreal.MovieSceneTrack):
            return _filter_tracks(items, name)
        if is_binding(items[0]):
            return _filter_tracks(_tracks_from_bindings(items), name)
        if isinstance(items[0], unreal.LevelSequence):
            tracks = []
            for seq in items:
                tracks.extend(gather_tracks(seq))
            return _filter_tracks(tracks, name)
    return []


def gather_sections(source, name=None):
    """从轨道收集片段，可按显示名过滤"""
    if source is None:
        return []
    if isinstance(source, unreal.MovieSceneSection):
        return _filter_sections([source], name)
    if isinstance(source, unreal.MovieSceneTrack):
        return _filter_sections(source.get_sections(), name)
    if isinstance(source, Iterable) and not isinstance(source, (str, bytes)):
        items = list(source)
        if not items:
            return []
        if isinstance(items[0], unreal.MovieSceneSection):
            return _filter_sections(items, name)
        if isinstance(items[0], unreal.MovieSceneTrack):
            sections = []
            for track in items:
                sections.extend(track.get_sections())
            return _filter_sections(sections, name)
    return []


def gather_channels(source, name=None):
    """从片段收集通道，可按显示名过滤"""
    if source is None:
        return []
    if isinstance(source, unreal.MovieSceneScriptingChannel):
        return _filter_channels([source], name)
    if isinstance(source, unreal.MovieSceneSection):
        return _filter_channels(_channels_from_section(source), name)
    if isinstance(source, Iterable) and not isinstance(source, (str, bytes)):
        items = list(source)
        if not items:
            return []
        if isinstance(items[0], unreal.MovieSceneScriptingChannel):
            return _filter_channels(items, name)
        if isinstance(items[0], unreal.MovieSceneSection):
            channels = []
            for section in items:
                channels.extend(_channels_from_section(section))
            return _filter_channels(channels, name)
    return []


def gather_keys(source, name=None):
    """从通道收集关键帧，可按帧号或显示名过滤"""
    if source is None:
        return []
    if isinstance(source, unreal.MovieSceneScriptingKey):
        return _filter_keys([source], name)
    if isinstance(source, unreal.MovieSceneScriptingChannel):
        return _filter_keys(_keys_from_channel(source), name)
    if isinstance(source, Iterable) and not isinstance(source, (str, bytes)):
        items = list(source)
        if not items:
            return []
        if isinstance(items[0], unreal.MovieSceneScriptingKey):
            return _filter_keys(items, name)
        if isinstance(items[0], unreal.MovieSceneScriptingChannel):
            keys = []
            for channel in items:
                keys.extend(_keys_from_channel(channel))
            return _filter_keys(keys, name)
    return []


def _add_scalar_key(channel, frame, value):
    """向标量通道添加一帧关键帧"""
    channel.add_key(unreal.FrameNumber(frame), value, 0.0, _TIME_UNIT)


def _is_transform_prop(prop) -> bool:
    """判断属性名是否属于 Transform 相关通道"""
    if prop in _TRANSFORM_PROP_CHANNELS:
        return True
    return prop in _TRANSFORM_CHANNELS


def _log_skip(message):
    """记录 keyframe 跳过原因日志"""
    unreal.log(f'[mc_keyframe] {message}')


def _transform_channels_for_prop(prop):
    """按属性名返回要写入的 Transform 通道列表"""
    if prop in _TRANSFORM_PROP_CHANNELS:
        return _TRANSFORM_PROP_CHANNELS[prop]
    if prop in _TRANSFORM_CHANNELS:
        return (prop,)
    return None


def _read_transform_values(obj):
    """读取对象当前 Location/Rotation/Scale"""
    if _is_actor(obj):
        return obj.get_actor_location(), obj.get_actor_rotation(), obj.get_actor_scale3d()
    if _is_scene_component(obj):
        return obj.get_relative_location(), obj.get_relative_rotation(), obj.get_relative_scale3d()
    throw(f'无法读取 Transform，obj 类型: {type(obj).__name__}')


def _validate_transform_value(prop, value) -> bool:
    """校验 Transform 写入值类型是否匹配属性"""
    if isinstance(value, unreal.Transform):
        return True

    if prop in _LOCATION_PROPS or prop.startswith('Location.'):
        if isinstance(value, unreal.Vector):
            return True
        if prop.startswith('Location.') and isinstance(value, (int, float)):
            return True
        _log_skip(f'Transform 属性 {prop!r} 需要 Vector 或单轴数值，收到: {type(value).__name__}')
        return False

    if prop in _ROTATION_PROPS or prop.startswith('Rotation.'):
        if isinstance(value, unreal.Rotator):
            return True
        if prop.startswith('Rotation.') and isinstance(value, (int, float)):
            return True
        _log_skip(f'Transform 属性 {prop!r} 需要 Rotator 或单轴数值，收到: {type(value).__name__}')
        return False

    if prop in _SCALE_PROPS or prop.startswith('Scale.'):
        if isinstance(value, unreal.Vector):
            return True
        if prop.startswith('Scale.') and isinstance(value, (int, float)):
            return True
        _log_skip(f'Transform 属性 {prop!r} 需要 Vector 或单轴数值，收到: {type(value).__name__}')
        return False

    if not prop or prop in ('Transform', 'transform'):
        _log_skip(f'完整 Transform 需要 unreal.Transform，收到: {type(value).__name__}')
        return False

    _log_skip(f'无法将 value 应用到 Transform 属性 {prop!r}')
    return False


def _apply_transform_value(obj, prop, value):
    """把 Transform 相关值写回对象属性"""
    if isinstance(value, unreal.Transform):
        if _is_actor(obj):
            obj.set_actor_transform(value, False, True)
        elif _is_scene_component(obj):
            obj.set_relative_transform(value, False, True)
        return

    loc, rot, scale = _read_transform_values(obj)

    if prop in _LOCATION_PROPS or prop.startswith('Location.'):
        if isinstance(value, unreal.Vector):
            loc = value
        elif prop.endswith('.X'):
            loc = unreal.Vector(value, loc.y, loc.z)
        elif prop.endswith('.Y'):
            loc = unreal.Vector(loc.x, value, loc.z)
        else:
            loc = unreal.Vector(loc.x, loc.y, value)
        if _is_actor(obj):
            obj.set_actor_location(loc, False, True)
        else:
            obj.set_relative_location(loc, False, True)
        return

    if prop in _ROTATION_PROPS or prop.startswith('Rotation.'):
        if isinstance(value, unreal.Rotator):
            rot = value
        elif prop.endswith('.X'):
            rot = unreal.Rotator(rot.pitch, rot.yaw, value)
        elif prop.endswith('.Y'):
            rot = unreal.Rotator(value, rot.yaw, rot.roll)
        else:
            rot = unreal.Rotator(rot.pitch, value, rot.roll)
        if _is_actor(obj):
            obj.set_actor_rotation(rot, True)
        else:
            obj.set_relative_rotation(rot, False, True)
        return

    if prop in _SCALE_PROPS or prop.startswith('Scale.'):
        if isinstance(value, unreal.Vector):
            scale = value
        elif prop.endswith('.X'):
            scale = unreal.Vector(value, scale.y, scale.z)
        elif prop.endswith('.Y'):
            scale = unreal.Vector(scale.x, value, scale.z)
        else:
            scale = unreal.Vector(scale.x, scale.y, value)
        if _is_actor(obj):
            obj.set_actor_scale3d(scale)
        else:
            obj.set_relative_scale3d(scale)
        return

    if not prop or prop in ('Transform', 'transform'):
        if _is_actor(obj):
            obj.set_actor_transform(value, False, True)
        else:
            obj.set_relative_transform(value, False, True)


def _transform_scalar(channel_name, loc, rot, scale) -> float:
    """从 loc/rot/scale 取出指定通道的标量"""
    mapping = {
        'Location.X': loc.x,
        'Location.Y': loc.y,
        'Location.Z': loc.z,
        'Rotation.X': rot.roll,
        'Rotation.Y': rot.pitch,
        'Rotation.Z': rot.yaw,
        'Scale.X': scale.x,
        'Scale.Y': scale.y,
        'Scale.Z': scale.z,
    }
    return mapping[channel_name]


def _get_or_create_transform_section(binding):
    """获取或创建 3DTransform 轨道的 section"""
    tracks = binding.find_tracks_by_exact_type(unreal.MovieScene3DTransformTrack)
    if tracks:
        track = tracks[0]
    else:
        track = binding.add_track(unreal.MovieScene3DTransformTrack)
    return _get_or_create_section(track)


def _key_transform(section, frame, loc, rot, scale, prop) -> bool:
    """对 Transform section 指定通道打关键帧"""
    channels = _transform_channels_for_prop(prop)
    if not channels:
        _log_skip(f'未知的 Transform 属性: {prop!r}')
        return False

    target_channels = set(channels)
    keyed = 0
    for channel in section.get_all_channels():
        name = _channel_name(channel)
        if name not in target_channels:
            continue
        _add_scalar_key(channel, frame, _transform_scalar(name, loc, rot, scale))
        keyed += 1
    if keyed == 0:
        _log_skip(f'未在 Transform 轨道中找到通道: {sorted(target_channels)}')
        return False
    return True


def _prop_name_and_path(prop):
    """拆分属性路径，返回末段名与完整路径"""
    return prop.split('.')[-1], prop


def _property_exists(obj, prop) -> bool:
    """检查对象是否暴露该编辑器属性"""
    try:
        obj.get_editor_property(prop)
        return True
    except Exception:
        return False


def _read_property(obj, prop):
    """读取对象编辑器属性"""
    return obj.get_editor_property(prop)


def _try_write_property(obj, prop, value) -> bool:
    """尝试写入属性，失败则打日志并返回 False"""
    try:
        obj.set_editor_property(prop, value)
        return True
    except Exception as exc:
        _log_skip(f'无法设置属性 {prop!r}: {exc}')
        return False


def _resolve_value_kind(value):
    """推断值的 keyframe 类型标签（bool/float/vector3 等）"""
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, int) and not isinstance(value, bool):
        return 'int'
    if isinstance(value, float):
        return 'float'
    if isinstance(value, unreal.Vector):
        return 'vector3'
    if isinstance(value, unreal.Vector2D):
        return 'vector2'
    if isinstance(value, unreal.Rotator):
        return 'rotator'
    if isinstance(value, unreal.LinearColor):
        return 'color'
    if isinstance(value, str):
        return 'string'
    return None


def _track_class_for_kind(kind):
    """按 kind 返回对应 MovieScene*Track 类"""
    mapping = {
        'bool': unreal.MovieSceneBoolTrack,
        'int': unreal.MovieSceneIntegerTrack,
        'float': unreal.MovieSceneFloatTrack,
        'vector3': unreal.MovieSceneDoubleVectorTrack if hasattr(unreal, 'MovieSceneDoubleVectorTrack') else unreal.MovieSceneFloatVectorTrack,
        'vector2': unreal.MovieSceneDoubleVectorTrack if hasattr(unreal, 'MovieSceneDoubleVectorTrack') else unreal.MovieSceneFloatVectorTrack,
        'rotator': unreal.MovieSceneRotatorTrack,
        'color': unreal.MovieSceneColorTrack,
        'string': unreal.MovieSceneStringTrack,
    }
    return mapping.get(kind)


def _track_kind(track):
    """从属性轨道推断其值类型 kind"""
    if isinstance(track, unreal.MovieSceneBoolTrack):
        return 'bool'
    if isinstance(track, unreal.MovieSceneIntegerTrack):
        return 'int'
    if isinstance(track, unreal.MovieSceneFloatTrack):
        return 'float'
    if isinstance(track, unreal.MovieSceneDoubleTrack):
        return 'float'
    track_name = track.get_class().get_name()
    if track_name.endswith('VectorTrack'):
        channels = 3
        try:
            channels = track.get_num_channels_used()
        except Exception:
            pass
        return 'vector2' if channels == 2 else 'vector3'
    if isinstance(track, unreal.MovieSceneRotatorTrack):
        return 'rotator'
    if isinstance(track, unreal.MovieSceneColorTrack):
        return 'color'
    if isinstance(track, unreal.MovieSceneStringTrack):
        return 'string'
    return None


def _validate_property_keyframe(obj, binding, prop, value):
    """校验属性名与值类型。通过则返回 (current_value, kind)，否则返回 None 并写日志。"""
    if not prop:
        _log_skip('非 Transform 关键帧必须指定 prop')
        return None

    if not _property_exists(obj, prop):
        _log_skip(f'找不到属性 {prop!r}')
        return None

    stored = _read_property(obj, prop)
    stored_kind = _resolve_value_kind(stored)
    if stored_kind is None:
        _log_skip(
            f'不支持的属性类型 {type(stored).__name__} ({prop!r})，'
            '须在蓝图中勾选 Expose to Cinematics'
        )
        return None

    if value is not None:
        value_kind = _resolve_value_kind(value)
        if value_kind is None:
            _log_skip(
                f'不支持的 value 类型 {type(value).__name__} ({prop!r})，'
                '支持: bool, int, float, Vector, Vector2D, Rotator, LinearColor, str'
            )
            return None
        if value_kind != stored_kind:
            _log_skip(
                f'属性 {prop!r} 的 value 类型 ({value_kind}) 与属性实际类型 ({stored_kind}) 不匹配'
            )
            return None
        current = value
        kind = value_kind
    else:
        current = stored
        kind = stored_kind

    existing = _find_property_track(binding, prop)
    if existing:
        track_kind = _track_kind(existing)
        if track_kind and track_kind != kind:
            _log_skip(
                f'属性 {prop!r} 的值类型 ({kind}) 与已有轨道类型 ({track_kind}) 不匹配'
            )
            return None

    return current, kind


def _is_property_track(track) -> bool:
    """判断是否为属性轨道"""
    return isinstance(track, unreal.MovieScenePropertyTrack)


def _find_property_track(binding, prop):
    """在绑定中查找匹配属性路径的轨道"""
    prop_name, prop_path = _prop_name_and_path(prop)
    for track in binding.get_tracks():
        if not _is_property_track(track):
            continue
        try:
            track_name = str(track.get_property_name())
            track_path = track.get_property_path()
        except Exception:
            track_name = str(unreal.MovieScenePropertyTrackExtensions.get_property_name(track))
            track_path = unreal.MovieScenePropertyTrackExtensions.get_property_path(track)
        if track_path == prop_path or track_name == prop_name:
            return track
    return None


def _get_or_create_property_section(binding, prop, kind):
    """获取或创建属性轨道及其 section"""
    track = _find_property_track(binding, prop)
    if not track:
        track_class = _track_class_for_kind(kind)
        if not track_class:
            _log_skip(f'无法为属性种类 {kind!r} 创建轨道')
            return None
        track = binding.add_track(track_class)
        prop_name, prop_path = _prop_name_and_path(prop)
        track.set_property_name_and_path(prop_name, prop_path)
        if kind == 'vector2':
            track.set_num_channels_used(2)
    return _get_or_create_section(track)


def _channel_values_for_property(value, kind):
    """把属性值拆成各通道名->标量映射"""
    if kind == 'bool':
        return {None: value}
    if kind == 'int':
        return {None: value}
    if kind == 'float':
        return {None: value}
    if kind == 'string':
        return {None: value}
    if kind == 'vector3':
        return {
            'Vector.X': value.x,
            'Vector.Y': value.y,
            'Vector.Z': value.z,
        }
    if kind == 'vector2':
        return {
            'Vector.X': value.x,
            'Vector.Y': value.y,
        }
    if kind == 'rotator':
        return {
            'Rotation.X': value.roll,
            'Rotation.Y': value.pitch,
            'Rotation.Z': value.yaw,
        }
    if kind == 'color':
        return {
            'Color.R': value.r,
            'Color.G': value.g,
            'Color.B': value.b,
            'Color.A': value.a,
        }
    return {}


def _key_property_channels(section, frame, value, kind) -> bool:
    """对属性 section 各通道打关帧"""
    values = _channel_values_for_property(value, kind)
    if not values:
        _log_skip(f'内部错误: 未知属性种类 {kind!r}')
        return False

    if kind in ('bool', 'int', 'float', 'string'):
        channels = section.get_all_channels()
        if not channels:
            _log_skip('属性轨道没有可用通道')
            return False
        channels[0].add_key(unreal.FrameNumber(frame), value, 0.0, _TIME_UNIT)
        return True

    keyed = 0
    for channel in section.get_all_channels():
        name = _channel_name(channel)
        if name not in values:
            continue
        _add_scalar_key(channel, frame, values[name])
        keyed += 1

    if keyed == 0:
        _log_skip(f'未在属性轨道中找到可写入的通道，属性值类型: {type(value).__name__}')
        return False
    return True


def _refresh_sequencer():
    """强制刷新当前 Level Sequence 编辑器"""
    unreal.LevelSequenceEditorBlueprintLibrary.force_update()
    unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()


def keyframe(obj, prop='', value=None, time=None) -> bool:
    """
    为 obj 在 Sequencer 中打关键帧。

    Args:
        obj: Actor 或 SceneComponent
        prop: 属性名；空字符串表示 Transform（位置/旋转/缩放）
        value: 新值；None 表示不打值，直接对当前值打帧
        time: 帧号（Display Rate）或秒数；None 表示当前播放头

    Returns:
        成功返回 True，属性名/类型校验失败返回 False
    """
    sequence = _get_active_sequence()
    binding = _ensure_binding(sequence, obj)
    frame = _resolve_frame(time, sequence)

    if _is_transform_prop(prop):
        if value is not None and not _validate_transform_value(prop, value):
            return False
        if value is not None:
            _apply_transform_value(obj, prop, value)
        loc, rot, scale = _read_transform_values(obj)
        section = _get_or_create_transform_section(binding)
        if not _key_transform(section, frame, loc, rot, scale, prop):
            return False
    else:
        validated = _validate_property_keyframe(obj, binding, prop, value)
        if not validated:
            return False
        current, kind = validated
        if value is not None and not _try_write_property(obj, prop, value):
            return False
        section = _get_or_create_property_section(binding, prop, kind)
        if not section:
            return False
        if not _key_property_channels(section, frame, current, kind):
            return False

    _refresh_sequencer()
    return True


def _unwrap_target(obj):
    """解开 mineprep 句柄，得到 Actor / SkeletalMeshComponent"""
    if hasattr(obj, 'target') and not isinstance(obj, (unreal.Actor, unreal.SkeletalMeshComponent)):
        obj = obj.target
    return obj


def _resolve_skm(target) -> unreal.SkeletalMeshComponent:
    """从 Actor 或 SkeletalMeshComponent 得到骨骼网格体"""
    target = _unwrap_target(target)
    if isinstance(target, unreal.SkeletalMeshComponent):
        return target
    if isinstance(target, unreal.Actor):
        skm = target.get_component_by_class(unreal.SkeletalMeshComponent)
        if skm:
            return skm
        throw(f'{target.get_actor_label()} 没有 SkeletalMeshComponent')
    throw(f'target 必须是 Actor 或 SkeletalMeshComponent，当前: {type(target).__name__}')


def _resolve_rig_class(rig_class):
    """None → FKControlRig；路径/蓝图 → Generated Class；类型 → UClass"""
    if rig_class is None:
        return unreal.FKControlRig.static_class()
    if isinstance(rig_class, str) or isinstance(rig_class, unreal.Blueprint):
        cls = uclass(rig_class)
        if cls is None:
            throw(f'无法解析 Control Rig 类: {rig_class}')
        rig_class = cls
    if isinstance(rig_class, type) and hasattr(rig_class, 'static_class'):
        return rig_class.static_class()
    if isinstance(rig_class, unreal.Class):
        return rig_class
    if isinstance(rig_class, unreal.ControlRig):
        return rig_class.get_class()
    throw(f'不支持的 rig_class: {type(rig_class).__name__}')


def _rig_io(ctype):
    """按控件类型取 ControlRigSequencerLibrary 的 get/set"""
    lib = unreal.ControlRigSequencerLibrary
    T = unreal.RigControlType
    table = {
        T.BOOL: (lib.get_local_control_rig_bool, lib.set_local_control_rig_bool),
        T.FLOAT: (lib.get_local_control_rig_float, lib.set_local_control_rig_float),
        T.SCALE_FLOAT: (lib.get_local_control_rig_float, lib.set_local_control_rig_float),
        T.INTEGER: (lib.get_local_control_rig_int, lib.set_local_control_rig_int),
        T.VECTOR2D: (lib.get_local_control_rig_vector2d, lib.set_local_control_rig_vector2d),
        T.POSITION: (lib.get_local_control_rig_position, lib.set_local_control_rig_position),
        T.SCALE: (lib.get_local_control_rig_scale, lib.set_local_control_rig_scale),
        T.ROTATOR: (lib.get_local_control_rig_rotator, lib.set_local_control_rig_rotator),
        T.EULER_TRANSFORM: (lib.get_local_control_rig_euler_transform, lib.set_local_control_rig_euler_transform),
    }
    pair = table.get(ctype)
    if not pair:
        throw(f'不支持的控件类型: {ctype}')
    return pair


def _find_sequencer_control_rig(sequence, track, cls, skm, skm_binding):
    """按 SKM 轨道取 Control Rig。同一 Actor 可有多套 FK，不能用 hosting actor。"""
    lib = unreal.ControlRigSequencerLibrary
    skm_id = skm_binding.get_id() if skm_binding else None
    bound_match = None
    for proxy in lib.get_control_rigs(sequence):
        rig = proxy.control_rig
        if not rig or rig.get_class() != cls:
            continue
        if proxy.track == track:
            return rig
        binding = proxy.proxy
        if binding and skm_id is not None and binding.get_id() == skm_id:
            return rig
        if bound_match is None and binding:
            for bound in unreal.LevelSequenceEditorBlueprintLibrary.get_bound_objects(_binding_id(binding)):
                if bound == skm:
                    bound_match = rig
                    break
    return bound_match


class Rig:
    """Sequencer 上的 Control Rig 句柄。默认 FK；已有轨保持 layered，新建为 layered。"""

    def __init__(self, target, rig_class=None):
        sequence = _get_active_sequence()
        skm = _resolve_skm(target)
        cls = _resolve_rig_class(rig_class)
        owner = skm.get_owner()
        if owner:
            _ensure_binding(sequence, owner)
        skm_binding = _ensure_binding(sequence, skm)

        lib = unreal.ControlRigSequencerLibrary
        track = lib.find_or_create_control_rig_track(world(), sequence, cls, skm_binding, True)
        if not track:
            throw('无法创建或找到 Control Rig 轨道')
        _refresh_sequencer()

        control_rig = _find_sequencer_control_rig(sequence, track, cls, skm, skm_binding)
        if control_rig is None:
            throw('找不到 Control Rig 实例')

        self.sequence = sequence
        self.skm = skm
        self.track = track
        self.target = control_rig

    def names(self) -> list[str]:
        """列出控件全名（含模块前缀，如 Spine/body_ctrl）"""
        hier = self.target.get_hierarchy()
        return [str(key.name) for key in hier.get_controls(True)]

    def _resolve_name(self, name: str) -> str:
        """匹配全名、短名、FK 骨骼名（head → head_CONTROL）；撞名则报错"""
        name = str(name)
        aliases = {}
        for full in self.names():
            keys = {full, full.rsplit('/', 1)[-1]}
            short = full.rsplit('/', 1)[-1]
            if short.endswith('_CURVE_CONTROL'):
                keys.add(short[:-len('_CURVE_CONTROL')])
            elif short.endswith('_CONTROL'):
                keys.add(short[:-len('_CONTROL')])
            for key in keys:
                aliases.setdefault(key, []).append(full)

        matches = aliases.get(name)
        if matches is None:
            folded = name.casefold()
            matches = next((v for k, v in aliases.items() if k.casefold() == folded), None)
        if not matches:
            throw(f'找不到控件: {name}')
        unique = list(dict.fromkeys(matches))
        if len(unique) > 1:
            throw(f'控件名 {name} 不唯一: {unique}')
        return unique[0]

    def _frame(self, time) -> unreal.FrameNumber:
        return unreal.FrameNumber(_resolve_frame(time, self.sequence))

    def _type(self, full_name):
        hier = self.target.get_hierarchy()
        key = unreal.RigElementKey(type=unreal.RigElementType.CONTROL, name=full_name)
        element = hier.find_control(key)
        if element is None:
            throw(f'找不到控件: {full_name}')
        settings = element.get_control_settings() if hasattr(element, 'get_control_settings') else element.settings
        return settings.control_type

    def _read(self, full_name, frame):
        getter, _ = _rig_io(self._type(full_name))
        return getter(self.sequence, self.target, full_name, frame, _TIME_UNIT)

    def _coerce(self, full_name, ctype, value, frame):
        T = unreal.RigControlType
        if ctype == T.EULER_TRANSFORM:
            if isinstance(value, unreal.EulerTransform):
                return value
            cur = self._read(full_name, frame)
            if isinstance(value, unreal.Rotator):
                return unreal.EulerTransform(location=cur.location, rotation=value, scale=cur.scale)
            if isinstance(value, unreal.Vector):
                return unreal.EulerTransform(location=value, rotation=cur.rotation, scale=cur.scale)
            if isinstance(value, unreal.Transform):
                return unreal.EulerTransform(
                    location=value.translation,
                    rotation=value.rotation.rotator(),
                    scale=value.scale3d,
                )
        if ctype == T.ROTATOR and isinstance(value, unreal.EulerTransform):
            return value.rotation
        if ctype == T.POSITION and isinstance(value, unreal.EulerTransform):
            return value.location
        return value

    def _write(self, full_name, value, frame, set_key: bool):
        ctype = self._type(full_name)
        value = self._coerce(full_name, ctype, value, frame)
        _, setter = _rig_io(ctype)
        setter(self.sequence, self.target, full_name, frame, value, _TIME_UNIT, set_key)
        return value

        """读取控件值；time=None 为播放头（int 帧 / float 秒）"""
        full = self._resolve_name(name)
        return self._read(full, self._frame(time))

    @undo
    def set(self, name, value, time=None):
        """写入控件值但不打帧"""
        full = self._resolve_name(name)
        self._write(full, value, self._frame(time), False)
        _refresh_sequencer()
        return self

    @undo
    def key(self, name, value=None, time=None):
        """打关键帧；value=None 则对当前值打帧"""
        full = self._resolve_name(name)
        frame = self._frame(time)
        if value is None:
            value = self._read(full, frame)
        # 刚创建的轨第一次 set_key 只写 Rig 值，先 set 再 key 才会进 Sequencer
        self._write(full, value, frame, False)
        self._write(full, value, frame, True)
        _refresh_sequencer()
        return self
