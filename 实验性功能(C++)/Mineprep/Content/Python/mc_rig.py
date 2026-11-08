"""Control Rig editing on Level Sequence tracks."""

import math
from collections.abc import Mapping

try:
    import unreal
except ModuleNotFoundError:
    from mc_utils import Lazy as unreal

from mc_sequencer import (
    _TIME_UNIT, _binding_id, _ensure_binding, _get_active_sequence,
    _resolve_frame, _unwrap_target,
)
import mc_sequencer as mcseq
from mc_utils import throw, uclass, undo, world


# Sequencer channel identifiers for scalar, vector and transform controls.
_CONTROL_GROUPS = ('.location', '.rotation', '.scale')
_ROTATION_ALIASES = {
    '.rotation.roll': '.rotation.x',
    '.rotation.pitch': '.rotation.y',
    '.rotation.yaw': '.rotation.z',
}
_CONTROL_SUFFIXES = frozenset(
    ['', *_ROTATION_ALIASES]
    + ['.' + axis for axis in 'xyzw']
    + [f'{group}.{axis}' for group in _CONTROL_GROUPS for axis in 'xyz']
)
_CONTROL_PARTS = tuple(suffix for suffix in _CONTROL_SUFFIXES if suffix.count('.') == 2) + _CONTROL_GROUPS


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
    """查找绑定在指定骨骼网格体轨道上的 Control Rig 实例（同一 Actor 可有多个骨骼网格体，因此按组件绑定匹配）。"""
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


def _rig_batch_io(ctype):
    lib = unreal.ControlRigSequencerLibrary
    T = unreal.RigControlType
    table = {
        T.BOOL: (lib.set_local_control_rig_bools, bool),
        T.FLOAT: (lib.set_local_control_rig_floats, float),
        T.SCALE_FLOAT: (lib.set_local_control_rig_floats, float),
        T.INTEGER: (lib.set_local_control_rig_ints, int),
        T.VECTOR2D: (lib.set_local_control_rig_vector2_ds, unreal.Vector2D),
        T.POSITION: (lib.set_local_control_rig_positions, unreal.Vector),
        T.SCALE: (lib.set_local_control_rig_scales, unreal.Vector),
        T.ROTATOR: (lib.set_local_control_rig_rotators, unreal.Rotator),
        T.EULER_TRANSFORM: (lib.set_local_control_rig_euler_transforms, unreal.EulerTransform),
    }
    if ctype not in table:
        throw(f'不支持的控件类型: {ctype}')
    return table[ctype]


class Rig:
    """Sequencer 上的 Control Rig 句柄。默认 FK；已有轨保持 layered，新建为 layered。"""

    def __init__(self, target, rig_class=None, *, layered=None):
        sequence = _get_active_sequence()
        skm = _resolve_skm(target)
        cls = _resolve_rig_class(rig_class)
        owner = skm.get_owner()
        if owner:
            _ensure_binding(sequence, owner)
        skm_binding = _ensure_binding(sequence, skm)

        lib = unreal.ControlRigSequencerLibrary
        track = lib.find_or_create_control_rig_track(
            world(), sequence, cls, skm_binding, layered if layered is not None else True)
        if not track:
            throw('无法创建或找到 Control Rig 轨道')
        mcseq._refresh_sequencer()

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

    def _resolve_name(self, name: str, *, controls=None) -> str:
        """匹配全名、短名、FK 骨骼名（head → head_CONTROL）；撞名则报错"""
        name = str(name)
        aliases = {}
        for full in self.names() if controls is None else controls:
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
        if not hier.contains(key):
            throw(f'找不到控件: {full_name}')
        return hier.get_control_settings(key).control_type

    def _read(self, full_name, frame):
        getter, _ = _rig_io(self._type(full_name))
        return getter(self.sequence, self.target, full_name, frame, _TIME_UNIT)

    def _coerce(self, full_name, ctype, value, frame):
        T = unreal.RigControlType
        if ctype == T.EULER_TRANSFORM:
            if isinstance(value, unreal.EulerTransform):
                return value
            if isinstance(value, unreal.Transform):
                return unreal.EulerTransform(
                    location=value.translation,
                    rotation=value.rotation.rotator(),
                    scale=value.scale3d,
                )
            if isinstance(value, (unreal.Rotator, unreal.Vector)):
                cur = self._read(full_name, frame)
                if isinstance(value, unreal.Rotator):
                    return unreal.EulerTransform(location=cur.location, rotation=value, scale=cur.scale)
                return unreal.EulerTransform(location=value, rotation=cur.rotation, scale=cur.scale)
        if ctype == T.ROTATOR and isinstance(value, unreal.EulerTransform):
            return value.rotation
        if ctype == T.POSITION and isinstance(value, unreal.EulerTransform):
            return value.location
        if ctype in (T.POSITION, T.SCALE) and isinstance(value, tuple) and len(value) == 3:
            return unreal.Vector(*value)
        return value

    def _write(self, full_name, value, frame, set_key: bool):
        ctype = self._type(full_name)
        value = self._coerce(full_name, ctype, value, frame)
        _, setter = _rig_io(ctype)
        setter(self.sequence, self.target, full_name, frame, value, _TIME_UNIT, set_key)
        return value

    def get(self, name, time=None):
        """读取控件值；time=None 为播放头（int 帧 / float 秒），不修改姿态或关键帧。"""
        full = self._resolve_name(name)
        return self._read(full, self._frame(time))

    @undo
    def set(self, name, value, time=None):
        """写入控件值但不打帧"""
        full = self._resolve_name(name)
        self._write(full, value, self._frame(time), False)
        mcseq._refresh_sequencer()
        return self

    def key(self, name, value=None, time=None, *, interp=None):
        """打关键帧；value=None 则对目标帧原值打帧。"""
        frame = _resolve_frame(time, self.sequence)
        return self.keyframes(name, [frame], [value], interp=interp)

    def keyframes(self, name, times, values, *, interp=None):
        """批量写控件键；部分姿态和 None 使用写入前各目标帧的值。"""
        times, values = list(times), list(values)
        if len(times) != len(values):
            raise ValueError('times 和 values 长度必须一致')
        if not times:
            return self
        return self._key_batches({self._resolve_name(name): (times, values)}, interp)

    def poses(self, poses, *, interp=None):
        """按时刻批量写姿势；未列出的控件不写键。"""
        batches = {}
        names = {}
        for time, controls in poses.items() if isinstance(poses, Mapping) else poses:
            for name, value in controls.items():
                if name not in names:
                    names[name] = self._resolve_name(name)
                times, values = batches.setdefault(names[name], ([], []))
                times.append(time)
                values.append(value)
        return self._key_batches(batches, interp)

    def _key_batches(self, batches, interp):
        if not batches:
            return self
        mcseq.require_focused_sequence(self.sequence)
        sections = self.track.get_sections()
        if interp is not None:
            modes = {
                'constant': unreal.RichCurveInterpMode.RCIM_CONSTANT,
                'linear': unreal.RichCurveInterpMode.RCIM_LINEAR,
                'auto': unreal.RichCurveInterpMode.RCIM_CUBIC,
            }
            if interp not in modes:
                raise ValueError("Rig interp 必须为 None、'constant'、'linear' 或 'auto'")
            if len(sections) != 1:
                raise ValueError('Rig 显式插值只支持单个 section，请使用 rig.keys() 选择要编辑的键')
        prepared = [self._prepare_keys(full, times, values)
                    for full, (times, values) in batches.items()]
        try:
            with unreal.ScopedEditorTransaction('Batch Control Rig keys'):
                self.track.modify()
                for section in sections:
                    section.modify()
                for full, frames, values, single, batch in prepared:
                    single(self.sequence, self.target, full, frames[0], values[0], _TIME_UNIT, False)
                    batch(self.sequence, self.target, full, frames, values, _TIME_UNIT)
                if interp is not None:
                    self._apply_interp(sections[0], prepared, modes[interp])
        finally:
            mcseq._refresh_sequencer()
        return self

    def _prepare_keys(self, full, times, values):
        if any(not isinstance(time, (int, float)) or not math.isfinite(time) for time in times):
            raise ValueError('批量时间必须为有限的整数帧或浮点秒')
        ctype = self._type(full)
        getter, single = _rig_io(ctype)
        batch, value_type = _rig_batch_io(ctype)
        frames = [self._frame(time) for time in times]
        encoded = []
        for frame, value in zip(frames, values):
            if value is None:
                value = getter(self.sequence, self.target, full, frame, _TIME_UNIT)
            else:
                value = self._coerce(full, ctype, value, frame)
            encoded.append(value)
        # Validate native value conversion before the warm-up changes the rig.
        return full, frames, unreal.Array.cast(value_type, encoded), single, batch

    @staticmethod
    def _control_channels(channels, full, part=''):
        part = _ROTATION_ALIASES.get(part, part)
        names = {full.casefold() + suffix for suffix in _CONTROL_SUFFIXES
                 if not part or _ROTATION_ALIASES.get(suffix, suffix) == part
                 or suffix.startswith(part + '.')}
        return channels.select(ch for ch in channels if mcseq._channel_name(ch).casefold() in names)

    def _control_selection(self, name):
        name = str(name)
        folded = name.casefold()
        controls = self.names()
        for full in controls:
            if full.casefold() == folded:
                return full, ''
        for part in _CONTROL_PARTS:
            if folded.endswith(part):
                return self._resolve_name(name[:-len(part)], controls=controls), part
        return self._resolve_name(name, controls=controls), ''

    def _apply_interp(self, section, prepared, mode):
        channels = mcseq.gather_channels(section)
        continuous = (unreal.MovieSceneScriptingFloatChannel, unreal.MovieSceneScriptingDoubleChannel)
        tick_unit = unreal.MovieSceneTimeUnit.TICK_RESOLUTION
        display_rate = self.sequence.get_display_rate()
        tick_rate = self.sequence.get_tick_resolution()
        for full, frames, _, _, _ in prepared:
            ticks = set()
            for frame in frames:
                converted = unreal.TimeManagementLibrary.transform_time(
                    unreal.FrameTime(frame), display_rate, tick_rate)
                # Match the native Rig writer's RoundToFrame.
                ticks.add(converted.frame_number.value + int(converted.sub_frame >= 0.5))
            for channel in self._control_channels(channels, full):
                if isinstance(channel, continuous):
                    for key in channel.get_keys():
                        if key.get_time(tick_unit).frame_number.value in ticks:
                            key.set_interpolation_mode(mode)
                            if mode == unreal.RichCurveInterpMode.RCIM_CUBIC:
                                key.set_tangent_mode(unreal.RichCurveTangentMode.RCTM_AUTO)

    def channels(self, name=''):
        """查询整轨、控件、分组或单轴通道。"""
        from mc_handle import channels

        found = mcseq.gather_channels(mcseq.gather_sections(self.track))
        if name:
            found = self._control_channels(found, *self._control_selection(name))
        return channels(found)

    def keys(self, name=''):
        """查询所选通道的键。"""
        return self.channels(name).keys()

    def clear(self, name=''):
        """清除所选通道的键，保留 section 和通道默认值。"""
        self.channels(name).clear()
        return self
