"""Sequencer 关键帧工具。

支持 Transform 及其单轴通道，以及 bool、int、float、Vector、Vector2D、
Rotator、LinearColor 和 str 属性。子序列使用本地时间和绑定。
主要处理 Possessable Actor/Component；Spawnable 绑定可能需要手动添加。
暂不支持 enum、byte 和对象引用属性。"""

import fnmatch
import math
from collections.abc import Iterable
from types import SimpleNamespace

try:
    import unreal
except ModuleNotFoundError:
    from mc_utils import Lazy as unreal
from mc_utils import throw, unwrap_rotations
from mc_math import _rotation_axes, unwrap_angles

_TIME_UNIT = unreal.MovieSceneTimeUnit.DISPLAY_RATE

class _LocatedItems(list):
    """Query-local provenance. The list keeps each indexed wrapper alive."""
    def __init__(self, items=(), locations=None):
        locations = locations if locations is not None else (items.locations if isinstance(items, _LocatedItems) else {})
        super().__init__(items)
        self.locations = {id(item): locations[id(item)] for item in self if id(item) in locations}

    def extend(self, items):
        if isinstance(items, _LocatedItems):
            self.locations.update(items.locations)
        super().extend(items)

    def select(self, items):
        return _LocatedItems(items, self.locations)

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
    """解析 Level Sequence：默认取当前序列，也可传句柄、对象或资产路径。"""
    if target is None:
        sequence = unreal.LevelSequenceEditorBlueprintLibrary.get_focused_level_sequence()
        if not sequence:
            sequence = unreal.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence()
        return sequence
    target = getattr(target, 'target', target)
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


def bound_actor(binding):
    """已打开序列里，该绑定对应的第一个 Actor。尚未解析时返回 None。"""
    if not is_binding(binding):
        return None
    for obj in unreal.LevelSequenceEditorBlueprintLibrary.get_bound_objects(_binding_id(binding)):
        if _is_actor(obj):
            return obj
    return None


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
        bound_objects = sequence.locate_bound_objects(binding, obj.get_world())
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
        owner = obj.get_owner()
        owner_binding = _ensure_binding(sequence, owner) if owner else None
        binding = sequence.add_possessable(obj)
        if owner_binding:
            binding.set_parent(owner_binding)
        return binding

    throw(f'obj 必须是 Actor 或 SceneComponent，当前类型: {type(obj).__name__}')


def _get_or_create_unbounded_property_section(track):
    """仅供 Transform/属性轨道：取首个 section，没有则新建无界片段。"""
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
            mapping[track.get_path_name()] = binding
    return mapping


def _channels_from_section(section):
    raw = list(section.get_all_channels())
    return _LocatedItems(raw, {id(ch): (section, i) for i, ch in enumerate(raw)})


def _keys_from_channel(channel, section=None, channel_index=-1):
    raw = list(channel.get_keys())
    locations = {id(key): (section, channel_index) for key in raw} if section is not None else {}
    return _LocatedItems(raw, locations)


def _build_label_context(sequence):
    return SimpleNamespace(sequence=sequence, track_bindings=_binding_track_map(sequence), locations={})


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
    binding = ctx.track_bindings.get(track.get_path_name())
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
    section, channel_index = ctx.locations.get(id(channel), (None, -1))
    if section is not None and channel_index >= 0:
        return _join_path(label_section(section, ctx), _channel_name(channel))
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
    """生成关键帧后缀，格式为 '@帧:值'"""
    frame = key.get_time().frame_number.value
    try:
        value = key.get_value()
    except Exception:
        return f'@{frame}:?'
    return f'@{frame}:{_format_key_value(value)}'


def label_key(key, ctx) -> str:
    """生成关键帧的层级显示名，后缀格式为 '@帧:值'"""
    section, channel_index = ctx.locations.get(id(key), (None, -1))
    if section is not None and channel_index >= 0:
        channel = section.get_all_channels()[channel_index]
        return _join_path(label_section(section, ctx), _channel_name(channel), _format_key_suffix(key))
    return _format_key_suffix(key)


def sequence_label(sequence) -> str:
    """获取序列名称"""
    return sequence.get_name() if sequence else ''


def is_binding(obj) -> bool:
    """判断对象是否为 Sequencer 绑定包装器"""
    return isinstance(obj, unreal.MovieSceneBindingProxy)


def labels_for(objects, sequence=None) -> list[str]:
    """批量为 bindings/tracks/sections/channels/keys 生成层级显示名"""
    if not objects:
        return []
    ctx = _build_label_context(sequence or resolve_sequence())
    sample = objects[0]
    if isinstance(sample, (unreal.MovieSceneScriptingChannel, unreal.MovieSceneScriptingKey)):
        locations = objects.locations if isinstance(objects, _LocatedItems) else {}
        contexts, labels = {}, []
        for obj in objects:
            section, _ = locations.get(id(obj), (None, -1))
            owner = section.get_typed_outer(unreal.LevelSequence) if section is not None else None
            if owner is not None:
                path = owner.get_path_name()
                if path not in contexts:
                    contexts[path] = _build_label_context(owner)
                context = contexts[path]
            else:
                context = ctx
            context.locations = locations
            labels.append(label_channel(obj, context) if isinstance(obj, unreal.MovieSceneScriptingChannel)
                          else label_key(obj, context))
        return labels
    if is_binding(sample):
        return [binding_label(obj) for obj in objects]
    if isinstance(sample, unreal.MovieSceneTrack):
        return [label_track(obj, ctx) for obj in objects]
    if isinstance(sample, unreal.MovieSceneSection):
        return [label_section(obj, ctx) for obj in objects]
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
    channels = _LocatedItems(channels)
    if not name:
        return channels
    if isinstance(name, type):
        return channels.select(c for c in channels if isinstance(c, name))
    if isinstance(name, str):
        pattern = name if '*' in name else f'*{name}*'
        return channels.select(
            c for c, label in zip(channels, labels_for(channels))
            if fnmatch.fnmatch(_channel_name(c), pattern)
            or fnmatch.fnmatch(label, pattern))
    if callable(name):
        return channels.select(c for c in channels if name(c))
    return []


def _filter_keys(keys, name=None, ctx=None):
    """按帧号、完整路径或后缀通配过滤关键帧"""
    keys = _LocatedItems(keys)
    if not name:
        return keys
    if isinstance(name, int):
        return keys.select(k for k in keys if k.get_time().frame_number.value == name)
    if isinstance(name, type):
        return keys.select(k for k in keys if isinstance(k, name))
    if isinstance(name, str):
        pattern = name if '*' in name else f'*{name}*'
        return keys.select(k for k, label in zip(keys, labels_for(keys))
                           if fnmatch.fnmatch(label, pattern)
                           or fnmatch.fnmatch(_format_key_suffix(k), pattern))
    if callable(name):
        return keys.select(k for k in keys if name(k))
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
    if isinstance(source, _LocatedItems):
        return _filter_channels(source, name)
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
            channels = _LocatedItems()
            for section in items:
                channels.extend(_channels_from_section(section))
            return _filter_channels(channels, name)
    return []


def gather_keys(source, name=None):
    """从通道收集关键帧，可按帧号或显示名过滤"""
    if source is None:
        return []
    if isinstance(source, _LocatedItems):
        if source and isinstance(source[0], unreal.MovieSceneScriptingChannel):
            result = _LocatedItems()
            for channel in source:
                result.extend(_keys_from_channel(channel, *source.locations.get(id(channel), (None, -1))))
            return _filter_keys(result, name)
        return _filter_keys(source, name)
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
            keys = _LocatedItems()
            for channel in items:
                keys.extend(_keys_from_channel(channel))
            return _filter_keys(keys, name)
    return []


def _is_transform_prop(prop) -> bool:
    """判断属性名是否属于 Transform 相关通道"""
    if prop in _TRANSFORM_PROP_CHANNELS:
        return True
    return prop in _TRANSFORM_CHANNELS


def _log_skip(message, *, warning=False):
    """记录 keyframe 跳过原因日志"""
    (unreal.log_warning if warning else unreal.log)(f'[mc_keyframe] {message}')


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
        pose = obj.get_relative_transform()
        return pose.translation, pose.rotation.rotator(), pose.scale3d
    throw(f'无法读取 Transform，obj 类型: {type(obj).__name__}')


def _key_value(prop, value):
    if (prop in _LOCATION_PROPS or prop in _SCALE_PROPS) and isinstance(value, tuple) and len(value) == 3:
        return unreal.Vector(*value)
    return value


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
            rot = unreal.Rotator(pitch=rot.pitch, yaw=rot.yaw, roll=value)
        elif prop.endswith('.Y'):
            rot = unreal.Rotator(pitch=value, yaw=rot.yaw, roll=rot.roll)
        else:
            rot = unreal.Rotator(pitch=rot.pitch, yaw=value, roll=rot.roll)
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


def _get_or_create_transform_section(binding, pose=None):
    """获取或创建 3DTransform 轨道的 section"""
    tracks = binding.find_tracks_by_exact_type(unreal.MovieScene3DTransformTrack)
    if tracks:
        track = tracks[0]
    else:
        track = binding.add_track(unreal.MovieScene3DTransformTrack)
    existing = track.get_sections()
    if existing:
        return existing[0]
    section = _get_or_create_unbounded_property_section(track)
    if pose is not None:
        for channel in section.get_all_channels():
            name = _channel_name(channel)
            if name in _TRANSFORM_CHANNELS:
                channel.set_default(_transform_scalar(name, *pose))
    return section


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


def _track_class_for_kind(kind, prop=''):
    """按 kind 返回对应 MovieScene*Track 类"""
    if prop and prop.lower() in ('bhidden', 'visibility'):
        return unreal.MovieSceneVisibilityTrack
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
    if isinstance(track, (unreal.MovieSceneBoolTrack, unreal.MovieSceneVisibilityTrack)):
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

    if prop.lower() == 'visibility' and not _property_exists(obj, prop):
        prop = 'bHidden'

    try:
        stored = _read_property(obj, prop)
    except Exception:
        _log_skip(f'找不到属性 {prop!r}')
        return None
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

    return stored, kind


def _is_property_track(track) -> bool:
    """判断是否为属性轨道"""
    return isinstance(track, unreal.MovieScenePropertyTrack)


def _find_property_track(binding, prop):
    """在绑定中查找匹配属性路径的轨道"""
    prop_name, prop_path = _prop_name_and_path(prop)
    if prop_name.lower() in ('bhidden', 'visibility'):
        vis_tracks = binding.find_tracks_by_exact_type(unreal.MovieSceneVisibilityTrack)
        if vis_tracks:
            return vis_tracks[0]
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


def _get_or_create_property_section(binding, prop, kind, current):
    """获取或创建属性轨道及其 section"""
    track = _find_property_track(binding, prop)
    if not track:
        track_class = _track_class_for_kind(kind, prop)
        if not track_class:
            _log_skip(f'无法为属性种类 {kind!r} 创建轨道')
            return None
        track = binding.add_track(track_class)
        prop_name, prop_path = _prop_name_and_path(prop)
        track.set_property_name_and_path(prop_name, prop_path)
        if kind == 'vector2':
            track.set_num_channels_used(2)
    sections = track.get_sections()
    if sections:
        return sections[0]
    section = _get_or_create_unbounded_property_section(track)
    values = _channel_values_for_property(current, kind)
    for channel in section.get_all_channels():
        if isinstance(channel, (unreal.MovieSceneScriptingFloatChannel, unreal.MovieSceneScriptingDoubleChannel)):
            name = None if None in values else _channel_name(channel)
            if name in values:
                channel.set_default(values[name])
    return section


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


def _relative_value(value, values, prop):
    """把最终通道值重组为单次设置姿态/属性所需的原生值。"""
    if None in values:
        return values[None]
    if prop in _TRANSFORM_CHANNELS:
        return values[prop]
    if isinstance(value, unreal.Rotator):
        return unreal.Rotator(roll=values['Rotation.X'], pitch=values['Rotation.Y'], yaw=values['Rotation.Z'])
    return type(value)(**{name.rsplit('.', 1)[-1].lower(): number for name, number in values.items()})


def _resolve_interp(value):
    """公共数字别名与 UE 枚举的数值不同，先识别枚举再查别名。"""
    mode = unreal.MovieSceneKeyInterpolation
    if isinstance(value, mode):
        return value
    if isinstance(value, unreal.RichCurveInterpMode):
        return {unreal.RichCurveInterpMode.RCIM_CONSTANT: mode.CONSTANT,
                unreal.RichCurveInterpMode.RCIM_LINEAR: mode.LINEAR}.get(value, mode.AUTO)
    names = ('constant', 'linear', 'auto', 'smart_auto', 'user', 'break')
    modes = (mode.CONSTANT, mode.LINEAR, mode.AUTO, mode.SMART_AUTO, mode.USER, mode.BREAK)
    mapping = dict(enumerate(modes)) | dict(zip(names, modes))
    if isinstance(value, str):
        value = value.strip().casefold()
    return mapping.get(value, mode.AUTO) if isinstance(value, (int, str)) else mode.AUTO


def _key_sequence(sequence, times):
    active = resolve_sequence()
    target = resolve_sequence(sequence) if sequence is not None else active
    if target is None:
        throw('找不到 Level Sequence，请打开序列或传入 sequence')
    if target != active and any(time is None for time in times):
        raise ValueError('非当前聚焦序列必须显式指定关键帧时间')
    return target


def _prepare_keyframe(obj, prop, value, sequence, *, relative=False):
    """一次定位绑定、片段和目标通道，供单次或批量写入共用。"""
    obj = _unwrap_target(obj)
    if relative and isinstance(value, unreal.Transform):
        _log_skip('relative 不支持完整 Transform 值，请分别写 Location/Rotation/Scale', warning=True)
        return None
    pose = _read_transform_values(obj) if _is_transform_prop(prop) else None
    binding = _ensure_binding(sequence, obj)
    if _is_transform_prop(prop):
        if value is not None and not _validate_transform_value(prop, value):
            return None
        kind = 'transform'
        section = _get_or_create_transform_section(binding, pose)
        names = _transform_channels_for_prop(prop)
    else:
        if prop.lower() == 'visibility' and not _property_exists(obj, prop):
            prop = 'bHidden'
        validated = _validate_property_keyframe(obj, binding, prop, value)
        if not validated:
            return None
        current, kind = validated
        section = _get_or_create_property_section(binding, prop, kind, current)
        if section is None:
            return None
        names = _channel_values_for_property(current, kind)
    all_channels = _channels_from_section(section)
    channels = ({None: all_channels[0]} if None in names and all_channels else
                {_channel_name(ch): ch for ch in all_channels if _channel_name(ch) in names})
    if not channels:
        _log_skip(f'未找到属性 {prop!r} 的可写通道')
        return None
    defaults = {}
    if relative:
        for name, channel in channels.items():
            if not isinstance(channel, (unreal.MovieSceneScriptingFloatChannel, unreal.MovieSceneScriptingDoubleChannel)):
                _log_skip(f'属性 {prop!r} 的 relative 写键只支持 Float/Double 通道', warning=True)
                return None
            if not channel.has_default():
                _log_skip(f'属性 {prop!r} 的通道 {_channel_name(channel)!r} 缺少默认值，无法相对写键', warning=True)
                return None
            defaults[name] = channel.get_default()
    section.modify()
    snapshot = ({name: _transform_scalar(name, *pose) for name in channels} if pose is not None
                else _channel_values_for_property(current, kind))
    return SimpleNamespace(obj=obj, prop=prop, kind=kind, channels=channels,
                           snapshot=snapshot, defaults=defaults, locations=all_channels.locations)


def _write_keyframe(context, frame, value, interp, *, apply=False, relative=False):
    obj, prop, kind = context.obj, context.prop, context.kind
    if relative and isinstance(value, unreal.Transform):
        _log_skip('relative 不支持完整 Transform 值，请分别写 Location/Rotation/Scale', warning=True)
        return []
    if kind == 'transform':
        if value is not None:
            if not _validate_transform_value(prop, value):
                return []
        values = context.snapshot.copy()
        if isinstance(value, unreal.Transform):
            values.update((name, _transform_scalar(name, value.translation,
                          value.rotation.rotator(), value.scale3d)) for name in values)
        elif value is not None:
            if isinstance(value, (int, float)):
                values[prop] = value
            elif isinstance(value, unreal.Rotator):
                angles = _channel_values_for_property(value, 'rotator')
                values.update((name, angles[name]) for name in values)
            else:
                values.update((name, getattr(value, name[-1].lower())) for name in values)
    else:
        if value is not None:
            if _resolve_value_kind(value) != kind:
                _log_skip(f'属性 {prop!r} 的批量 value 类型不匹配: {type(value).__name__}')
                return []
        values = context.snapshot if value is None else _channel_values_for_property(value, kind)
    if value is not None:
        if relative:
            values = {name: context.defaults[name] + number for name, number in values.items()}
        if apply:
            resolved = _relative_value(value, values, prop) if relative else value
            obj.modify()
            if kind == 'transform':
                _apply_transform_value(obj, prop, resolved)
            elif not _try_write_property(obj, prop, resolved):
                return []
    written = _LocatedItems()
    for name, channel in context.channels.items():
        options = {'interpolation': interp} if isinstance(channel, (
            unreal.MovieSceneScriptingFloatChannel, unreal.MovieSceneScriptingDoubleChannel)) else {}
        key = channel.add_key(unreal.FrameNumber(frame), values[name], 0.0, _TIME_UNIT, **options)
        written.append(key)
        written.locations[id(key)] = context.locations[id(channel)]
    return written


def _refresh_sequencer():
    """强制刷新当前 Level Sequence 编辑器"""
    unreal.LevelSequenceEditorBlueprintLibrary.force_update()
    unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()


def object_channels(obj, prop='', *, sequence=None):
    """只读查询已有轨道，包含所有 section，支持 Actor/组件集合。"""
    sequence = resolve_sequence(sequence)
    if sequence is None:
        return []
    obj = _unwrap_target(obj)
    if obj is None:
        return []
    targets = list(obj) if isinstance(obj, Iterable) else [obj]
    result = _LocatedItems()
    seen = set()
    for target in targets:
        binding = _find_binding_for_object(sequence, target)
        if binding is None:
            continue
        if _is_transform_prop(prop):
            tracks = binding.find_tracks_by_exact_type(unreal.MovieScene3DTransformTrack)
            names = _transform_channels_for_prop(prop)
        else:
            track = _find_property_track(binding, prop)
            tracks = [track] if track is not None else []
            names = None
        for track in tracks:
            for section in track.get_sections():
                located = _channels_from_section(section)
                for index, channel in enumerate(located):
                    identity = (section.get_path_name(), index)
                    if identity not in seen and (names is None or _channel_name(channel) in names):
                        seen.add(identity)
                        result.append(channel)
                        result.locations[id(channel)] = located.locations[id(channel)]
    return result


def _unique_channel_sources(sources):
    """包装器可重复创建；实际通道以 section 和通道下标去重。"""
    unique = {}
    for channel, section, index in sources:
        if section is None or index < 0:
            raise ValueError('通道缺少所有者信息，请通过 Actor.channels 或 section 查询通道')
        unique.setdefault((section.get_path_name(), index), (channel, section))
    return list(unique.values())


def _resolve_loop(mode):
    enum = unreal.RichCurveExtrapolation
    if isinstance(mode, enum):
        return mode
    modes = {'cycle': enum.RCCE_CYCLE, 'cycle_with_offset': enum.RCCE_CYCLE_WITH_OFFSET,
             'oscillate': enum.RCCE_OSCILLATE, 'linear': enum.RCCE_LINEAR,
             'constant': enum.RCCE_CONSTANT, 'none': enum.RCCE_NONE,
             'offset': enum.RCCE_CYCLE_WITH_OFFSET, 'pingpong': enum.RCCE_OSCILLATE}
    if isinstance(mode, str) and mode.strip().casefold() in modes:
        return modes[mode.strip().casefold()]
    raise ValueError(f'未知循环模式: {mode!r}')


def loop_channels(sources, mode='cycle', *, before=False, after=True):
    if not sources or not (before or after):
        return
    mode = _resolve_loop(mode)
    targets = _unique_channel_sources(sources)
    if any(not isinstance(ch, (unreal.MovieSceneScriptingFloatChannel,
                              unreal.MovieSceneScriptingDoubleChannel)) for ch, _ in targets):
        raise TypeError('循环只支持 Float/Double 通道')
    with unreal.ScopedEditorTransaction('Loop animation channels'):
        for channel, section in targets:
            section.modify()
            if before:
                channel.set_pre_infinity_extrapolation(mode)
            if after:
                channel.set_post_infinity_extrapolation(mode)
    _refresh_sequencer()


def clear_channels(sources):
    targets = [(ch, section, list(ch.get_keys()))
               for ch, section in _unique_channel_sources(sources)]
    targets = [(ch, section, keys) for ch, section, keys in targets if keys]
    if not targets:
        return
    with unreal.ScopedEditorTransaction('Clear animation keys'):
        for channel, section, keys in targets:
            section.modify()
            for key in keys:
                channel.remove_key(key)
    _refresh_sequencer()


def require_focused_sequence(sequence):
    if sequence is None or sequence != resolve_sequence():
        raise ValueError('播放控制的目标必须是当前聚焦的 LevelSequence')


def set_camera_cut(sequence, camera, *, start=None, end=None, lock_viewport=False):
    """目标序列内的有限 Camera Cut；同范围更新，其余部分重叠拒绝。"""
    if sequence is None:
        raise ValueError('找不到 LevelSequence')
    camera = _unwrap_target(camera)
    if (not isinstance(camera, unreal.Actor) or not unreal.SystemLibrary.is_valid(camera)
            or camera.get_component_by_class(unreal.CameraComponent) is None):
        raise TypeError('camera 必须为带有 CameraComponent 的有效 Actor')
    if start is None or lock_viewport:
        require_focused_sequence(sequence)
    first = _resolve_frame(start, sequence)
    last = sequence.get_playback_end() if end is None else _resolve_frame(end, sequence)
    if last <= first:
        raise ValueError('Camera Cut 必须满足 end > start，范围为 [start,end)')
    tracks = list(sequence.find_tracks_by_type(unreal.MovieSceneCameraCutTrack))
    if len(tracks) > 1:
        raise ValueError('目标序列存在多个 Camera Cut 轨道，无法确定修改目标')
    track = tracks[0] if tracks else None
    matched = None
    for section in track.get_sections() if track is not None else ():
        if not section.has_start_frame() or not section.has_end_frame():
            raise ValueError('已有 Camera Cut 缺少有限边界，请先设置其范围')
        lower, upper = section.get_start_frame(), section.get_end_frame()
        if (lower, upper) == (first, last) and matched is None:
            matched = section
        elif first < upper and lower < last:
            raise ValueError('Camera Cut 与已有片段部分重叠，不会自动裁剪')
    with unreal.ScopedEditorTransaction('Set camera cut'):
        sequence.modify()
        sequence.get_movie_scene().modify()
        binding = _ensure_binding(sequence, camera)
        track = track if track is not None else sequence.add_track(unreal.MovieSceneCameraCutTrack)
        track.modify()
        section = matched if matched is not None else track.add_section()
        section.modify()
        # Bound before yielding/refreshing: thumbnail caches require finite ranges.
        section.set_range(first, last)
        section.set_camera_binding_id(sequence.get_binding_id(binding))
    _refresh_sequencer()
    if lock_viewport:
        unreal.LevelSequenceEditorBlueprintLibrary.set_lock_camera_cut_to_viewport(True)


def set_sequence_frame(sequence, frame):
    require_focused_sequence(sequence)
    if frame is None:
        raise ValueError('必须指定播放头位置')
    number = _resolve_frame(frame, sequence)
    params = unreal.MovieSceneSequencePlaybackParams(
        frame=unreal.FrameTime(frame_number=unreal.FrameNumber(number)),
        position_type=unreal.MovieScenePositionType.FRAME,
        update_method=unreal.UpdatePositionMethod.JUMP)
    unreal.LevelSequenceEditorBlueprintLibrary.set_local_position(params, _TIME_UNIT)


def _sequence_rate(fps):
    rate = unreal.FrameRate(numerator=fps, denominator=1) if isinstance(fps, int) else fps
    if not isinstance(rate, unreal.FrameRate) or rate.numerator <= 0 or rate.denominator <= 0:
        raise ValueError('fps 必须为正整数或有效的 FrameRate')
    return rate


def _sequence_range_frames(start, end, rate):
    def frame(value):
        if isinstance(value, int):
            return value
        if isinstance(value, float) and math.isfinite(value):
            return int(round(value * rate.numerator / rate.denominator))
        raise ValueError('范围端点必须为整数帧或有限秒数')
    first, last = frame(start), frame(end)
    if last <= first:
        raise ValueError('end 必须大于 start，范围为 [start,end)')
    return first, last


def create_sequence(name, *, fps, duration, open_editor):
    rate = _sequence_rate(fps)
    first, last = _sequence_range_frames(0, duration, rate)
    base = name if '/' in name else f'/Game/Cinematics/{name}'
    if (not base.startswith('/Game/') or not base.rsplit('/', 1)[1]
            or '//' in base or unreal.PackageTools.sanitize_package_name(base) != base):
        raise ValueError('序列名称必须为短名称或完整 /Game/... 包路径')
    path = base
    counter = 2
    while unreal.EditorAssetLibrary.does_asset_exist(path):
        path = f'{base}_{counter}'
        counter += 1
    folder, asset_name = path.rsplit('/', 1)
    sequence = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name, folder, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    if sequence is None:
        raise RuntimeError(f'无法创建序列 {path}')
    set_sequence_range(sequence, first, last, fps=rate)
    if open_editor:
        unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)
    return sequence


def set_sequence_range(sequence, start, end, *, fps=None):
    if sequence is None:
        raise ValueError('找不到 LevelSequence')
    rate = sequence.get_display_rate() if fps is None else _sequence_rate(fps)
    first, last = _sequence_range_frames(start, end, rate)
    with unreal.ScopedEditorTransaction('Set sequence range'):
        sequence.modify()
        sequence.get_movie_scene().modify()
        if fps is not None:
            sequence.set_display_rate(rate)
        # Avoid an inverted intermediate range when moving both bounds forward.
        if first >= sequence.get_playback_end():
            sequence.set_playback_end(last)
            sequence.set_playback_start(first)
        else:
            sequence.set_playback_start(first)
            sequence.set_playback_end(last)
    _refresh_sequencer()


def retime_channels(sources, offset=0, scale=1.0, pivot=0):
    if not sources:
        return
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('scale 必须为有限正数')
    if offset is None or pivot is None:
        raise ValueError('offset 和 pivot 必须显式指定帧数或秒数')
    # Resolve all rates/times before writing, using each section's sequence.
    targets = []
    for channel, section in _unique_channel_sources(sources):
        sequence = section.get_typed_outer(unreal.LevelSequence)
        if sequence is None:
            raise ValueError('重定时通道必须属于 LevelSequence')
        targets.append((channel, section, _resolve_frame(offset, sequence),
                        _resolve_frame(pivot, sequence)))
    with unreal.ScopedEditorTransaction('Retime animation channels'):
        for channel, section, offset_frame, pivot_frame in targets:
            section.modify()
            channel.transform(unreal.FrameNumber(offset_frame), scale, unreal.FrameNumber(pivot_frame),
                              unreal.SequencerScriptingRange(), _TIME_UNIT)
    _refresh_sequencer()


def keyframe(obj, prop='', value=None, time=None, *, interp='auto', sequence=None, relative=False) -> bool:
    """
    为 obj 在 Sequencer 中打关键帧。

    Args:
        obj: Actor 或 SceneComponent
        prop: 属性名；空字符串表示 Transform（位置/旋转/缩放）
        value: 新值；None 表示不打值，直接对当前值打帧
        time: 帧号（Display Rate）或秒数；None 表示当前播放头
        interp: 0 constant / 1 linear / 2 auto / 3 smart_auto / 4 user / 5 break，或字符串/UE枚举
        sequence: LevelSequence 或资产路径；省略时使用当前聚焦序列
        relative: 显式值逐分量叠加通道默认值；None 仍使用起始快照

    Returns:
        成功返回 True，属性名/类型校验失败返回 False
    """
    value = _key_value(prop, value)
    sequence = _key_sequence(sequence, [time])
    frame = _resolve_frame(time, sequence)
    context = _prepare_keyframe(obj, prop, value, sequence, relative=relative)
    if context is None or not _write_keyframe(context, frame, value, _resolve_interp(interp), apply=True, relative=relative):
        return False
    _refresh_sequencer()
    return True


def _unwrap_keyframe_values(context, values, axes):
    single = {'Rotation.X': ('r', 'roll'), 'Rotation.Y': ('p', 'pitch'), 'Rotation.Z': ('y', 'yaw')}
    if context.kind == 'transform' and context.prop in single:
        letter, attribute = single[context.prop]
        if axes != letter:
            raise ValueError(f'{context.prop} 只支持 unwrap={letter!r}')
        def convert(segment):
            return unwrap_angles(getattr(value, attribute) if isinstance(value, unreal.Rotator)
                                 else value for value in segment)
    elif context.kind == 'rotator' or (context.kind == 'transform' and context.prop in _ROTATION_PROPS):
        def convert(segment):
            return unwrap_rotations(segment, axes=axes)
    else:
        raise ValueError('unwrap 只支持 Rotation 组、旋转单轴或 Rotator 属性')
    result, segment = [], []
    for value in values:
        if value is None:
            result.extend(convert(segment))
            result.append(None)
            segment = []
        else:
            segment.append(value)
    result.extend(convert(segment))
    return result


def keyframes(obj, prop, times, values, *, interp='auto', sequence=None, relative=False, unwrap=False):
    """批量写键，返回原生 keys；不循环调用 keyframe，不逐键刷新。"""
    times, values = list(times), [_key_value(prop, value) for value in values]
    if len(times) != len(values):
        raise ValueError('times 和 values 长度必须一致')
    if not times:
        return []
    obj = _unwrap_target(obj)
    targets = list(obj) if isinstance(obj, Iterable) else [obj]
    if not targets:
        return []
    sequence = _key_sequence(sequence, times)
    frames = [_resolve_frame(time, sequence) for time in times]
    axes = None if unwrap is False else _rotation_axes('y' if unwrap is True else unwrap)
    if axes is not None and any(second <= first for first, second in zip(frames, frames[1:])):
        raise ValueError('unwrap 要求换算后的显示帧严格递增')
    interp = _resolve_interp(interp)
    written = _LocatedItems()
    with unreal.ScopedEditorTransaction('Batch keyframes'):
        try:
            for target in targets:
                context = _prepare_keyframe(target, prop, values[0], sequence, relative=relative)
                if context is None:
                    raise ValueError(f'无法为属性 {prop!r} 创建关键帧')
                samples = _unwrap_keyframe_values(context, values, axes) if axes is not None else values
                for frame, value in zip(frames, samples):
                    result = _write_keyframe(context, frame, value, interp, relative=relative)
                    if not result:
                        raise ValueError(f'写入属性 {prop!r} 第 {frame} 帧失败')
                    written.extend(result)
        finally:
            _refresh_sequencer()
    return written


def _unwrap_target(obj):
    """解开 mineprep 句柄，得到 Actor / SkeletalMeshComponent"""
    if not isinstance(obj, (unreal.Actor, unreal.SceneComponent, Iterable)) and hasattr(obj, 'target'):
        obj = obj.target
    return obj
