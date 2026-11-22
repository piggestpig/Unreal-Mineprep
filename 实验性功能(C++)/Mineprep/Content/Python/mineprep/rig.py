"""Control Rig editing on Level Sequence tracks."""

import math
from collections.abc import Mapping

try:
    import unreal
except ModuleNotFoundError:
    from mineprep.utils import Lazy as unreal

from mineprep.sequencer_tools import (
    _TIME_UNIT, _binding_id, _ensure_binding, _get_active_sequence,
    _resolve_frame, _unwrap_target,
)
from mineprep import sequencer_tools as mcseq
from mineprep.utils import throw, uclass, undo, world


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
_CONTROL_PARTS = tuple(sorted((s for s in _CONTROL_SUFFIXES if s), key=len, reverse=True)) + _CONTROL_GROUPS


def _key_tick_time(key, tick_unit):
    ft = key.get_time(tick_unit)
    return ft.frame_number.value + ft.sub_frame


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


def describe_skeleton(component):
    """Read the mesh reference pose without evaluating or changing the live pose."""
    bones = {}
    axes = [unreal.Vector(x, y, z) for x, y, z in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    for index in range(component.get_num_bones()):
        name = component.get_bone_name(index)
        parent = str(component.get_parent_bone(name))
        parent = None if parent.casefold() == 'none' else parent
        local = component.get_ref_pose_transform(index)
        reference = local if parent is None else local.multiply(bones[parent]['reference'])
        bones[str(name)] = dict(parent=parent, local=local, reference=reference,
                                pivot=reference.translation,
                                axes=dict(zip('xyz', (reference.rotation.rotate_vector(axis) for axis in axes))))
    return bones


class Rig:
    """Sequencer 上的 Control Rig 句柄。默认 FK；已有轨保持 layered，新建为 layered。"""

    def __init__(self, target, rig_class=None, *, layered=None, section=None):
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
        self.binding = skm_binding
        self.track = track
        self.target = control_rig
        self.section = section

    @classmethod
    def bake_from_anim(cls, target, rig_class, *, reduce_keys=False, tolerance=0.01,
                       reset_controls=True, export_options=None):
        """将当前序列中目标骨骼网格体的现有动画烘焙到指定 Control Rig（依赖向后解析）。"""
        sequence = _get_active_sequence()
        skm = _resolve_skm(target)
        rig_uclass = _resolve_rig_class(rig_class)
        owner = skm.get_owner()
        if owner:
            _ensure_binding(sequence, owner)
        skm_binding = _ensure_binding(sequence, skm)
        opts = export_options if export_options is not None else unreal.AnimSeqExportOption()
        ok = unreal.ControlRigSequencerLibrary.bake_to_control_rig(
            world(), sequence, rig_uclass, opts, bool(reduce_keys), float(tolerance),
            skm_binding, reset_controls=bool(reset_controls),
        )
        mcseq._refresh_sequencer()
        if not ok:
            throw(f'烘焙动画到 Control Rig 失败: {rig_class}')
        return cls(skm, rig_uclass)

    @property
    def priority(self) -> int:
        """多条 Control Rig 轨道的执行优先级（UE 5.8 中数值越小越后求值、覆盖优先级越高，默认基线 100）。"""
        return int(unreal.ControlRigSequencerLibrary.get_control_rig_priority_order(self.track))

    @priority.setter
    def priority(self, value: int) -> None:
        self.track.modify()
        unreal.ControlRigSequencerLibrary.set_control_rig_priority_order(self.track, int(value))
        mcseq._refresh_sequencer()

    def sections(self) -> list:
        """返回当前 Control Rig 轨道上的全部 section（基础层及叠加动画层）。"""
        return list(self.track.get_sections())

    def _target_section(self):
        all_sections = self.sections()
        if not all_sections:
            throw('Control Rig 轨道没有可用 section')
        section = getattr(self, 'section', None)
        if section is None:
            if len(all_sections) != 1:
                raise ValueError('Rig 写键需要单个 section，多动画层轨道请在构造时指定 section= 索引或对象')
            return all_sections[0]
        if isinstance(section, int) and not isinstance(section, bool):
            try:
                return all_sections[section]
            except IndexError as exc:
                raise ValueError(f'section 索引越界: {section}（共 {len(all_sections)} 个）') from exc
        if section in all_sections:
            return section
        raise ValueError('指定的 section 不属于当前 Control Rig 轨道')

    def names(self, *, include_visual_cues: bool = False) -> list[str]:
        """列出控件全名（含模块前缀与子动画通道，默认跳过仅视觉提示的 VISUAL_CUE）。"""
        hier = self.target.get_hierarchy()
        cue_type = getattr(unreal.RigControlAnimationType, 'VISUAL_CUE', None)
        result = []
        for key in hier.get_controls(True):
            if not include_visual_cues and cue_type is not None:
                if hier.get_control_settings(key).animation_type == cue_type:
                    continue
            result.append(str(key.name))
        return result

    def describe(self):
        """Return parent, local and component reference poses, pivot and axes for each bone."""
        return describe_skeleton(self.skm)

    def _control_aliases(self, controls):
        hier = self.target.get_hierarchy()
        ch_type = getattr(unreal.RigControlAnimationType, 'ANIMATION_CHANNEL', None)
        aliases = {}
        channel_aliases = {}
        for full in controls:
            short = full.rsplit('/', 1)[-1]
            keys = {full, short}
            if short.endswith('_CURVE_CONTROL'):
                keys.add(short[:-len('_CURVE_CONTROL')])
            elif short.endswith('_CONTROL'):
                keys.add(short[:-len('_CONTROL')])
            if ch_type is not None:
                elem_key = unreal.RigElementKey(type=unreal.RigElementType.CONTROL, name=full)
                if hier.contains(elem_key):
                    settings = hier.get_control_settings(elem_key)
                    if settings.animation_type == ch_type:
                        disp = str(getattr(settings, 'display_name', '') or '')
                        if disp.casefold() in ('', 'none'):
                            disp = ''
                        parents = hier.get_parents(elem_key)
                        for p in parents:
                            p_full = str(p.name)
                            p_short = p_full.rsplit('/', 1)[-1]
                            for p_alias in (p_full, p_short):
                                for ch_alias in (short, disp) if disp else (short,):
                                    dotted = f'{p_alias}.{ch_alias}'
                                    keys.add(dotted)
                                    channel_aliases.setdefault(dotted, []).append(full)
                        if disp and disp != short:
                            keys.add(disp)
            for key in keys:
                aliases.setdefault(key, []).append(full)
        return aliases, channel_aliases

    def _resolve_name(self, name: str, *, controls=None) -> str:
        """匹配全名、短名、父控件.子通道名（ctrl.Channel）、FK 骨骼名；撞名则报错"""
        name = str(name)
        controls = self.names() if controls is None else controls
        aliases, _ = self._control_aliases(controls)

        matches = aliases.get(name)
        if matches is None:
            folded = name.casefold()
            matches = next((v for k, v in aliases.items() if k.casefold() == folded), None)
            if matches is None:
                from mineprep.face import FACE_BONE_ALIASES
                mapped = FACE_BONE_ALIASES.get(folded)
                if mapped is not None:
                    matches = next((v for k, v in aliases.items() if k.casefold() == mapped), None)
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

    def _read(self, full_name, frame, time_unit=_TIME_UNIT):
        getter, _ = _rig_io(self._type(full_name))
        return getter(self.sequence, self.target, full_name, frame, time_unit)

    def _coerce(self, full_name, ctype, value, frame, time_unit=_TIME_UNIT):
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
            if isinstance(value, unreal.TransformNoScale):
                return unreal.EulerTransform(
                    location=value.location,
                    rotation=value.rotation.rotator(),
                    scale=unreal.Vector(1.0, 1.0, 1.0),
                )
            if isinstance(value, (unreal.Rotator, unreal.Vector)):
                cur = self._read(full_name, frame, time_unit)
                if isinstance(value, unreal.Rotator):
                    return unreal.EulerTransform(location=cur.location, rotation=value, scale=cur.scale)
                return unreal.EulerTransform(location=value, rotation=cur.rotation, scale=cur.scale)
        if ctype == T.ROTATOR and isinstance(value, (unreal.EulerTransform, unreal.Transform)):
            return value.rotation if isinstance(value, unreal.EulerTransform) else value.rotation.rotator()
        if ctype == T.POSITION and isinstance(value, (unreal.EulerTransform, unreal.Transform)):
            return value.location if isinstance(value, unreal.EulerTransform) else value.translation
        if ctype in (T.FLOAT, T.SCALE_FLOAT) and isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if ctype == T.VECTOR2D and isinstance(value, (tuple, list)) and len(value) == 2:
            return unreal.Vector2D(float(value[0]), float(value[1]))
        if ctype in (T.POSITION, T.SCALE) and isinstance(value, (tuple, list)) and len(value) == 3:
            return unreal.Vector(float(value[0]), float(value[1]), float(value[2]))
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
        return self._key_batches({name: ([self._time_tick(time)], [value])}, interp,
                                 time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)

    def keyframes(self, name, times, values, *, interp=None):
        """写整控件、分组或单轴；返回本次写入的 keys，按样本排列。"""
        times, values = list(times), list(values)
        if len(times) != len(values):
            raise ValueError('times 和 values 长度必须一致')
        times = [self._time_tick(time) for time in times]
        return self._key_batches({name: (times, values)}, interp,
                                 time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)

    def _time_tick(self, time):
        if isinstance(time, float):
            if not math.isfinite(time):
                raise ValueError('关键帧时间须为有限数值')
            rate = self.sequence.get_tick_resolution()
            return math.floor(time * rate.numerator / rate.denominator + 0.5)
        if time is not None and (isinstance(time, bool) or not isinstance(time, int)):
            raise TypeError('关键帧时间须为整数显示帧或浮点秒')
        return self._key_tick(self._frame(time))

    def poses(self, poses, *, interp=None):
        """按时刻批量写姿势；未列出的控件不写键。"""
        batches = {}
        for time, controls in poses.items() if isinstance(poses, Mapping) else poses:
            for name, value in controls.items():
                times, values = batches.setdefault(name, ([], []))
                times.append(self._time_tick(time))
                values.append(value)
        self._key_batches(batches, interp, time_unit=unreal.MovieSceneTimeUnit.TICK_RESOLUTION)
        return self

    def _key_batches(self, batches, interp, *, replace_span=False, playback_end=None,
                     time_unit=_TIME_UNIT, hold_ticks=()):
        from mineprep.handles import keys
        if not batches:
            return keys([], sequence=self.sequence)
        modes = {
            'constant': unreal.RichCurveInterpMode.RCIM_CONSTANT,
            'linear': unreal.RichCurveInterpMode.RCIM_LINEAR,
            'auto': unreal.RichCurveInterpMode.RCIM_CUBIC,
        }
        if interp is not None and interp not in modes:
            raise ValueError("Rig interp 必须为 None、'constant'、'linear' 或 'auto'")
        for name, (times, values) in batches.items():
            if len(times) != len(values):
                raise ValueError('times 和 values 长度必须一致')
        if not any(times for times, _ in batches.values()):
            return keys([], sequence=self.sequence)
        mcseq.require_focused_sequence(self.sequence)
        all_sections = self.sections()
        target_section = self._target_section()
        use_native_batch = (len(all_sections) == 1)
        sections = [target_section]
        tick_unit = unreal.MovieSceneTimeUnit.TICK_RESOLUTION
        key_tick = (lambda frame: frame.value) if time_unit == tick_unit else self._key_tick
        channels = mcseq.gather_channels(sections)
        prepared = []
        selected = []
        occupied = set()
        for name, (times, values) in batches.items():
            if not times:
                continue
            full, part = self._control_selection(name)
            chosen = self._control_channels(channels, full, part)
            if part:
                frames = ([self._frame(t) for t in times] if time_unit == _TIME_UNIT
                          else [unreal.FrameNumber(t) for t in times])
                encoded = [self._part_values(full, part, value, frame, time_unit)
                           for frame, value in zip(frames, values)]
                expected = len(encoded[0])
                if len(chosen) != expected:
                    raise ValueError(f'{name}: 找不到完整的目标通道')
                item = (full, frames, encoded, None, None)
            elif use_native_batch:
                item = self._prepare_keys(full, times, values, time_unit)
            else:
                frames = ([self._frame(t) for t in times] if time_unit == _TIME_UNIT
                          else [unreal.FrameNumber(t) for t in times])
                ctype = self._type(full)
                getter, _ = _rig_io(ctype)
                encoded = [
                    self._encode_scalars(
                        ctype,
                        getter(self.sequence, self.target, full, frame, time_unit)
                        if value is None else self._coerce(full, ctype, value, frame, time_unit),
                    )
                    for frame, value in zip(frames, values)
                ]
                if len(chosen) != len(encoded[0]):
                    raise ValueError(f'{name}: 找不到完整的目标通道')
                item = (full, frames, encoded, None, None)
            for frame in item[1]:
                for channel in chosen:
                    identity = (chosen.locations[id(channel)], key_tick(frame))
                    if identity in occupied:
                        raise ValueError(f'{name}: 同一时刻重复写入同一通道')
                    occupied.add(identity)
            prepared.append(item)
            selected.append(chosen)
        if not prepared:
            return keys([], sequence=self.sequence)
        if replace_span:
            first, end_tick = self._replace_bounds(replace_span, prepared, time_unit, tick_unit)
            unique_channels = {chosen.locations[id(channel)]: channel
                               for chosen in selected for channel in chosen}
            removals = (
                [
                    (channel, key)
                    for channel in unique_channels.values()
                    for key in channel.get_keys()
                    if first <= _key_tick_time(key, tick_unit) < end_tick
                ]
                if end_tick > first else []
            )
        try:
            with unreal.ScopedEditorTransaction('Batch Control Rig keys'):
                self.track.modify()
                for section in sections:
                    section.modify()
                if replace_span:
                    for channel, key in removals:
                        channel.remove_key(key)
                written = mcseq._LocatedItems()
                for (full, frames, values, single, batch), chosen in zip(prepared, selected):
                    if batch is not None:
                        single(self.sequence, self.target, full, frames[0], values[0], time_unit, False)
                        batch(self.sequence, self.target, full, frames, values, time_unit)
                    else:
                        for frame, row in zip(frames, values):
                            for channel, value in zip(chosen, row):
                                key = channel.add_key(frame, value, time_unit=time_unit)
                                written.append(key)
                                written.locations[id(key)] = chosen.locations[id(channel)]
                        continue
                    # Native batches return no keys. Query each channel once, then order by sample.
                    if batch is not None and not chosen:
                        chosen = self._control_channels(mcseq.gather_channels(sections), full)
                    lookup = [{_key_tick_time(k, tick_unit): k for k in channel.get_keys()} for channel in chosen]
                    for frame in frames:
                        for channel, table in zip(chosen, lookup):
                            key = table[key_tick(frame)]
                            written.append(key)
                            written.locations[id(key)] = chosen.locations[id(channel)]
                if interp is not None:
                    for key in written:
                        mode = unreal.RichCurveInterpMode.RCIM_CONSTANT if _key_tick_time(key, tick_unit) in hold_ticks else modes[interp]
                        if isinstance(key, (unreal.MovieSceneScriptingFloatKey, unreal.MovieSceneScriptingDoubleKey)):
                            key.set_interpolation_mode(mode)
                            if mode == unreal.RichCurveInterpMode.RCIM_CUBIC:
                                key.set_tangent_mode(unreal.RichCurveTangentMode.RCTM_AUTO)
                if playback_end is not None and playback_end > self.sequence.get_playback_end():
                    self.sequence.modify()
                    self.sequence.set_playback_end(playback_end)
        finally:
            mcseq._refresh_sequencer()
        return keys(written, sequence=self.sequence)

    @staticmethod
    def _encode_scalars(ctype, value):
        T = unreal.RigControlType
        if ctype == T.BOOL:
            return (bool(value),)
        if ctype in (T.FLOAT, T.SCALE_FLOAT):
            return (float(value),)
        if ctype == T.INTEGER:
            return (int(value),)
        if ctype == T.VECTOR2D:
            return (float(value.x), float(value.y))
        if ctype in (T.POSITION, T.SCALE):
            return (float(value.x), float(value.y), float(value.z))
        if ctype == T.ROTATOR:
            return (float(value.roll), float(value.pitch), float(value.yaw))
        if ctype == T.EULER_TRANSFORM:
            return (float(value.location.x), float(value.location.y), float(value.location.z),
                    float(value.rotation.roll), float(value.rotation.pitch), float(value.rotation.yaw),
                    float(value.scale.x), float(value.scale.y), float(value.scale.z))
        throw(f'不支持的控件类型: {ctype}')

    def _prepare_keys(self, full, times, values, time_unit):
        if any(not isinstance(time, (int, float)) or not math.isfinite(time) for time in times):
            raise ValueError('批量时间必须为有限的整数帧或浮点秒')
        ctype = self._type(full)
        getter, single = _rig_io(ctype)
        batch, value_type = _rig_batch_io(ctype)
        frames = ([self._frame(time) for time in times] if time_unit == _TIME_UNIT
                  else [unreal.FrameNumber(time) for time in times])
        encoded = []
        for frame, value in zip(frames, values):
            if value is None:
                value = getter(self.sequence, self.target, full, frame, time_unit)
            else:
                value = self._coerce(full, ctype, value, frame, time_unit)
            encoded.append(value)
        # Validate native value conversion before the warm-up changes the rig.
        return full, frames, unreal.Array.cast(value_type, encoded), single, batch

    def _control_channels(self, channels, full, part=''):
        part = _ROTATION_ALIASES.get(part, part)
        bases = {full.casefold()}
        hier = self.target.get_hierarchy()
        ch_type = getattr(unreal.RigControlAnimationType, 'ANIMATION_CHANNEL', None)
        if ch_type is not None and not part:
            elem_key = unreal.RigElementKey(type=unreal.RigElementType.CONTROL, name=full)
            if hier.contains(elem_key):
                settings = hier.get_control_settings(elem_key)
                if settings.animation_type == ch_type:
                    short = full.rsplit('/', 1)[-1]
                    disp = str(getattr(settings, 'display_name', '') or '')
                    if disp.casefold() in ('', 'none'):
                        disp = ''
                    for p in hier.get_parents(elem_key):
                        p_name = str(p.name).casefold()
                        bases.add(f'{p_name}.{short.casefold()}')
                        if disp:
                            bases.add(f'{p_name}.{disp.casefold()}')
        names = {base + suffix for base in bases for suffix in _CONTROL_SUFFIXES
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
        if '.' in name:
            _, channel_aliases = self._control_aliases(controls)
            ch_match = channel_aliases.get(name)
            if ch_match is None:
                ch_match = next((v for k, v in channel_aliases.items() if k.casefold() == folded), None)
            if ch_match:
                unique = list(dict.fromkeys(ch_match))
                if len(unique) > 1:
                    throw(f'控件名 {name} 不唯一: {unique}')
                return unique[0], ''
        for part in _CONTROL_PARTS:
            if folded.endswith(part):
                full = self._resolve_name(name[:-len(part)], controls=controls)
                part = _ROTATION_ALIASES.get(part, part)
                T = unreal.RigControlType
                ctype = self._type(full)
                allowed = ({g for g in _CONTROL_GROUPS} |
                           {f'{g}.{axis}' for g in _CONTROL_GROUPS for axis in 'xyz'}
                           if ctype == T.EULER_TRANSFORM else
                           {'.x', '.y'} if ctype == T.VECTOR2D else
                           {'.x', '.y', '.z'} if ctype in (T.POSITION, T.SCALE, T.ROTATOR) else set())
                if part not in allowed:
                    raise ValueError(f'{name}: 控件类型不支持该分量')
                return full, part
        return self._resolve_name(name, controls=controls), ''

    def _part_values(self, full, part, value, frame, time_unit):
        """Encode one selected group/axis, taking None from the pre-write pose."""
        ctype = self._type(full)
        group, _, axis = part.lstrip('.').partition('.')
        scalar = bool(axis) or group in 'xyz'
        if value is None:
            value = self._read(full, frame, time_unit)
            if ctype == unreal.RigControlType.EULER_TRANSFORM:
                value = getattr(value, {'location': 'location', 'rotation': 'rotation', 'scale': 'scale'}[group])
            if scalar:
                axis = axis or group
                value = getattr(value, dict(x='roll', y='pitch', z='yaw')[axis]
                                if isinstance(value, unreal.Rotator) else axis)
        if scalar:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('单轴关键帧须为有限数值或 None')
            return (value,)
        if group == 'rotation':
            if not isinstance(value, unreal.Rotator):
                raise TypeError('Rotation 组需要 unreal.Rotator')
            row = (value.roll, value.pitch, value.yaw)
        else:
            if isinstance(value, unreal.Vector):
                row = (value.x, value.y, value.z)
            elif isinstance(value, (tuple, list)) and len(value) == 3:
                row = tuple(value)
            else:
                raise TypeError('Location / Scale 组需要 Vector 或 XYZ 三元组')
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in row):
            raise ValueError('分组关键帧须为有限数值')
        return row

    def _key_tick(self, frame):
        converted = unreal.TimeManagementLibrary.transform_time(
            unreal.FrameTime(frame), self.sequence.get_display_rate(), self.sequence.get_tick_resolution())
        # Match the native Rig writer's RoundToFrame.
        return converted.frame_number.value + int(converted.sub_frame >= 0.5)

    def _replace_bounds(self, replace_span, prepared, time_unit, tick_unit):
        """Return half-open [start_tick, end_tick) bounds for replace_span."""
        if isinstance(replace_span, slice):
            if (time_unit != tick_unit or replace_span.step not in (None, 1)
                    or any(isinstance(t, bool) or not isinstance(t, int)
                           for t in (replace_span.start, replace_span.stop))
                    or replace_span.stop < replace_span.start):
                raise ValueError('tick 区间须为有限整数 slice(start, end)')
            return replace_span.start, replace_span.stop
        if replace_span is True:
            if time_unit == tick_unit:
                rate = self.sequence.get_display_rate()
                res = self.sequence.get_tick_resolution()
                ticks = [frame.value for _, frames, _, _, _ in prepared for frame in frames]
                last_tick = unreal.TimeManagementLibrary.transform_time(
                    unreal.FrameTime(unreal.FrameNumber(max(ticks))), res, rate)
                return min(ticks), self._key_tick(unreal.FrameNumber(last_tick.frame_number.value + 1))
            frames = [frame.value for _, frames, _, _, _ in prepared for frame in frames]
            return self._key_tick(unreal.FrameNumber(min(frames))), self._key_tick(unreal.FrameNumber(max(frames) + 1))
        if isinstance(replace_span, range):
            if replace_span.step != 1:
                raise ValueError('Rig replace_span range 步长必须为 1')
            span_start, span_end = replace_span.start, replace_span.stop
        elif isinstance(replace_span, (tuple, list)) and len(replace_span) == 2:
            span_start, span_end = replace_span
        else:
            raise ValueError('Rig replace_span 必须为 bool、range 或 (start_frame, end_frame)')
        if (isinstance(span_start, bool) or not isinstance(span_start, int)
                or isinstance(span_end, bool) or not isinstance(span_end, int)):
            raise ValueError('Rig replace_span 区间端点必须为整数显示帧')
        if span_end < span_start:
            raise ValueError('Rig replace_span 结束帧不能小于起始帧')
        return self._key_tick(unreal.FrameNumber(span_start)), self._key_tick(unreal.FrameNumber(span_end))

    def _resolve_space_key(self, space) -> unreal.RigElementKey:
        lib = unreal.ControlRigSequencerLibrary
        if space is None or (isinstance(space, str) and space.strip().casefold() == 'world'):
            return lib.get_world_space_reference_key()
        if isinstance(space, unreal.RigElementKey):
            return space
        hier = self.target.get_hierarchy()
        name = str(space)
        for etype in (unreal.RigElementType.CONTROL, unreal.RigElementType.BONE, unreal.RigElementType.NULL):
            key = unreal.RigElementKey(type=etype, name=name)
            if hier.contains(key):
                return key
        try:
            full = self._resolve_name(name)
            return unreal.RigElementKey(type=unreal.RigElementType.CONTROL, name=full)
        except Exception:
            throw(f'找不到空间参考元素: {space}')

    def set_space(self, name, space=None, time=None) -> bool:
        """在指定时刻切换控件的参考空间（space=None/'world' 表示世界空间，或传骨骼/控件名）。"""
        full = self._resolve_name(name)
        space_key = self._resolve_space_key(space)
        ok = unreal.ControlRigSequencerLibrary.set_control_rig_space(
            self.sequence, self.target, full, space_key, self._frame(time), _TIME_UNIT,
        )
        mcseq._refresh_sequencer()
        return bool(ok)

    def bake_space(self, names, space=None, *, start=None, end=None, reduce_keys=False, tolerance=0.001) -> bool:
        """将指定控件区间内的运动烘焙到目标参考空间。"""
        if isinstance(names, str):
            names = [names]
        full_names = [self._resolve_name(n) for n in names]
        space_key = self._resolve_space_key(space)
        settings = unreal.RigSpacePickerBakeSettings()
        settings.set_editor_property('target_space', space_key)
        settings.set_editor_property('reduce_keys', bool(reduce_keys))
        settings.set_editor_property('tolerance', float(tolerance))
        if start is not None:
            settings.set_editor_property('start_frame', self._frame(start))
        if end is not None:
            settings.set_editor_property('end_frame', self._frame(end))
        ok = unreal.ControlRigSequencerLibrary.bake_control_rig_space(
            self.sequence, self.target, full_names, settings, _TIME_UNIT,
        )
        mcseq._refresh_sequencer()
        return bool(ok)

    def constrain_to(self, name, parent, *, bone='', maintain_offset=True, constraint_type=None):
        """将控件约束到另一个 Actor/Component/Socket 或 (Rig, 控件名)。"""
        full = self._resolve_name(name)
        clib = unreal.ConstraintsScriptingLibrary
        w = world()
        child_handle = clib.create_transformable_handle(w, self.target, full)
        if isinstance(parent, tuple) and len(parent) == 2 and isinstance(parent[0], Rig):
            p_rig, p_ctrl = parent
            parent_handle = clib.create_transformable_handle(w, p_rig.target, p_rig._resolve_name(p_ctrl))
        else:
            parent_obj = _unwrap_target(parent)
            if isinstance(parent_obj, unreal.Actor) and not bone:
                parent_obj = parent_obj.root_component or parent_obj
            parent_handle = clib.create_transformable_handle(w, parent_obj, str(bone) if bone else 'None')
        ctype = constraint_type if constraint_type is not None else unreal.TransformConstraintType.PARENT
        constraint = unreal.ControlRigSequencerLibrary.add_constraint(
            w, ctype, child_handle, parent_handle, bool(maintain_offset),
        )
        mcseq._refresh_sequencer()
        return constraint

    def bake_constraint(self, constraint, frames) -> bool:
        """将约束烘焙为指定帧序列上的关键帧。"""
        frame_nums = [self._frame(f) for f in frames]
        ok = unreal.ControlRigSequencerLibrary.bake_constraint(
            world(), constraint, frame_nums, _TIME_UNIT,
        )
        mcseq._refresh_sequencer()
        return bool(ok)

    def channels(self, name=''):
        """查询整轨、控件、分组或单轴通道。"""
        from mineprep.handles import channels

        secs = [self._target_section()] if getattr(self, 'section', None) is not None else mcseq.gather_sections(self.track)
        found = mcseq.gather_channels(secs)
        if name:
            found = self._control_channels(found, *self._control_selection(name))
        return channels(found)

    def keys(self, name=''):
        """查询所选通道的键。"""
        return self.channels(name).keys()

    def clear(self, name='', *, all_sections=False):
        """清除所选通道的键，保留 section 和通道默认值；多动画层轨道须指定 section= 或传 all_sections=True。"""
        if all_sections:
            self.channels(name).clear()
            return self
        from mineprep.handles import channels
        found = mcseq.gather_channels([self._target_section()])
        if name:
            found = self._control_channels(found, *self._control_selection(name))
        channels(found).clear()
        return self
