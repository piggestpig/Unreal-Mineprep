"""Mineprep scene and Sequencer handles."""

import builtins
import math
import operator
from collections.abc import Iterable
from pprint import pformat
from typing import Any

try:
    import unreal
except ModuleNotFoundError:
    from mc_utils import Lazy as unreal

import mc_sequencer as mcseq
import mc_utils
from mc_localization import tooltip
from mc_rig import Rig
from mc_sequencer import keyframe
from mc_utils import List, WrapList, enum, iscollection, prints, throw, undo, world


class helper:
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):
        target = owner if instance is None else instance
        return lambda: self.func(target)


class MineprepAPIHandle:
    """对象包装器，提供语法糖"""
    target: Any = None
    label: str = None
    class_help: str = ''
    inst_help: str = ''
    _collection = False

    @helper
    def help(obj):
        """打印这个类的帮助信息，在实例上调用help有时能得到专属信息"""
        if isinstance(obj, type):
            builtins.help(obj)
            text = obj.class_help or f'{obj!r}\n{tooltip("help")}'
        else:
            builtins.help(obj.__class__)
            text = obj.__class__.inst_help or f'{obj!r}\n{tooltip("help")}'
        return prints(text, color=unreal.LinearColor(0, 1, 0, 1), duration=5)

    def __init__(self, target, label=''):
        """设置包装的对象为target，对象名称为label。可通过.target直接访问对象"""
        if self._collection:
            target = WrapList(target) if iscollection(target) else WrapList()
        self.target = target
        self.label = label

    def __len__(self):
        """返回集合句柄的元素数量；单对象句柄不支持长度。"""
        if not self._collection:
            raise TypeError(f'{type(self).__name__} is not a collection handle')
        return len(self.target)

    def __bool__(self):
        """集合非空或单对象 target 不为 None 时为真。"""
        return len(self.target) > 0 if self._collection else self.target is not None

    def __str__(self):
        return pformat(self.label)
    
    def __repr__(self):
        return f'<mineprep.{self.__class__.__name__} object of ' + pformat(self.label) + '>'

    def __class_getitem__(cls, target):
        """直接使用类下标[...]时，先调用init, 然后返回self.target"""
        return cls(target).target

    @undo
    def __getattr__(self, name):
        """调用不存在的属性或函数时, 自动转发到target, 支持数组，能自动转换整数为枚举"""
        target = self.target
        if isinstance(target, List):
            attr = getattr(target, name)
            if callable(attr) and target:
                doc = getattr(getattr(target[0], name), '__doc__', None)
                def wrapper(*args, **kwargs):
                    args, kwargs = mc_utils.convert_ue_call_args(args, kwargs, doc)
                    return attr(*args, **kwargs)
                return wrapper
            return attr

        attr = getattr(target, name)
        return mc_utils.wrap_ue_method(attr) if callable(attr) else attr

    def __call__(self, fn, *args, **kwargs):
        target = self.target
        if isinstance(target, List):
            return target(fn, *args, **kwargs)
        if target is None:
            return None
        return fn(target, *args, **kwargs)

    def get(self, prop: str=None):
        """获取属性值，支持泛型"""
        pass

    def get_value(self, prop: str=None) -> float:
        """获取属性值，转换为浮点数"""
        return float(self.get(prop))
    
    def get_string(self, prop: str=None) -> str:
        """获取属性值，转换为字符串"""
        return str(self.get(prop))

    @undo
    def set(self, prop: str=None, value: Any=None):
        """设置属性值，支持泛型"""
        pass

    @undo
    def set_string(self, prop: str=None, value: str=None):
        """用字符串设置属性值"""
        return self.set(prop, str(value))

    @undo
    def set_value(self, prop:str=None, value:float=None):
        """用浮点数设置属性值"""
        return self.set(prop, float(value))

######################################################################################


class MineprepWorldHandle(MineprepAPIHandle):
    _element = None

    def __new__(cls, *args, **kwargs):
        """集合句柄用单个 int/float 调用时，返回该下标元素的单个包装器。"""
        if (cls._element is not None and len(args) == 1 and not kwargs
                and isinstance(args[0], (int, float)) and not isinstance(args[0], bool)):
            return cls._element(cls().target[args[0]])
        return super().__new__(cls)

    @classmethod
    def _indexed(cls, key):
        """若传入整数或布尔列表，则作为花式索引从默认集合中取值；否则返回 None。"""
        indices = List._take(key)
        if indices is None:
            return None
        if not indices:
            return []
        source = cls()
        selected = source.target[key]
        return source._items.select(selected) if '_items' in vars(source) else selected

    def __class_getitem__(cls, key):
        """类下标访问：传入索引、切片或掩码时从集合中取值；传入名称、类型等参数时查找并返回底层 UObject。"""
        if isinstance(key, (int, slice)) or (cls._collection and isinstance(key, float)):
            return cls()._raw_index(key)
        if isinstance(key, tuple) and len(key) == 2:
            return cls()._raw_index(key)
        if cls._collection and List._take(key) is not None:
            return cls()._raw_index(key)
        return cls(key).target

    def _raw_index(self, key):
        return self.target[key] if self._collection else self.target

    @staticmethod
    def _selection_items(result):
        return result if isinstance(result, List) else ([] if result is None else [result])

    def _select(self, selected):
        # Scoped query subclasses take filters in their constructor. Rebuild the
        # public collection class with the selected objects instead.
        collection = next(cls for cls in type(self).__mro__ if cls.__dict__.get('_collection'))
        if '_items' in vars(self):
            selected = self._items.select(selected)
        return collection(selected)

    def __getitem__(self, key):
        """实例下标保留句柄；多轴索引返回 List 的原生结果。"""
        if not self._collection:
            return self
        if isinstance(key, tuple):
            if len(key) != 1:
                return self.target[key]
            key = key[0]
        result = self.target[key]
        if self._element is not None and isinstance(key, (int, float)):
            return self._element(result)
        return self._select(self._selection_items(result))

    def __iter__(self):
        return iter(self.target)

    def get(self, prop: str):
        """获取 Actor/组件/材质等对象的编辑器属性"""
        return self.get_editor_property(prop)

    @undo
    def set(self, prop: str, value: Any):
        """设置编辑器属性；传入 int 时自动匹配枚举下标"""
        if isinstance(value, int):
            values = self.get_editor_property(prop)
            values = values if isinstance(values, Iterable) else [values]
            enums = [v for v in values if isinstance(v, unreal.EnumBase)]
            if enums:
                var = enums[0]
                value = enum(var)[value]
        return self.set_editor_property(prop, value)
    
    @undo
    def key(self, prop: str='', value: Any=None, time: int|float=None,
            *, interp='auto', sequence=None, relative=False):
        """在当前时刻对指定属性打关键帧。
        提供value时会先设置值，然后打关键帧。
        如果重载时间time，传入int表示帧数，传入float表示秒数。
        relative=True 时显式值叠加通道默认值，None 仍使用起始快照。
        """
        if isinstance(self.target, List):
            return WrapList(keyframe(t, prop, value, time, interp=interp, sequence=sequence, relative=relative)
                            for t in self.target)
        return keyframe(self.target, prop, value, time, interp=interp, sequence=sequence, relative=relative)

    def keyframes(self, prop, times, values, *, interp='auto', sequence=None, relative=False, unwrap=False):
        """批量写键，共用一次事务和刷新；返回本批关键帧句柄。"""
        return keyframes(self.target, prop, times, values, interp=interp, sequence=sequence, relative=relative, unwrap=unwrap)

    def channels(self, prop='', *, sequence=None):
        """查询 Actor/组件已有的动画通道；空 prop 为 Transform，不创建轨道。"""
        return channels(mcseq.object_channels(self.target, prop, sequence=sequence))

    def lookat_rotation(self, target, *, origin=None, pitch=True, roll=0):
        """计算当前世界目标对应的 Rotation；组件返回父级相对旋转，不修改姿态。"""
        if self._collection:
            return [mc_utils._lookat_rotation(obj, target, origin=origin, pitch=pitch, roll=roll) for obj in self.target]
        return mc_utils._lookat_rotation(self.target, target, origin=origin, pitch=pitch, roll=roll)

    def lookat(self, target, *, pitch=True, roll=0):
        """以 +X 朝向当前世界目标；pitch=False 为水平面，roll 为度，返回自身。"""
        rotations = self.lookat_rotation(target, pitch=pitch, roll=roll)
        objects = self.target if self._collection else [self.target]
        if not objects:
            return self
        if not self._collection:
            rotations = [rotations]
        with unreal.ScopedEditorTransaction('Look at target'):
            for obj, rotation in zip(objects, rotations):
                obj.modify()
                if isinstance(obj, unreal.Actor):
                    if obj.root_component is not None:
                        obj.root_component.modify()
                    obj.set_actor_rotation(rotation, True)
                else:
                    obj.set_relative_rotation(rotation, False, True)
        return self


class actor(MineprepWorldHandle):
    __iter__ = None
    _actor_class = unreal.Actor

    def __init__(self, name=unreal.Actor):
        """按标签/类型/回调查找单个 Actor，支持 .comp/.comps/.mats 链式访问"""
        target = None
        if isinstance(name, unreal.Actor):
            target = name
        elif isinstance(name, type):
            target = unreal.GameplayStatics.get_actor_of_class(world(), name)
        elif name is not None:
            actors_list = unreal.GameplayStatics.get_all_actors_of_class(world(), self._actor_class)
            if isinstance(name, str):
                pattern = f'*{name}*' if '*' not in name else name
                actors = unreal.EditorFilterLibrary.by_actor_label(actors_list, pattern, unreal.EditorScriptingStringMatchType.MATCHES_WILDCARD)
                target = next((a for a in actors if a.get_actor_label() == name), None)
                if not target and actors:
                    target = actors[0]
            elif callable(name):
                target = next((a for a in actors_list if name(a)), None)
        super().__init__(target, target.get_actor_label() if target else '')

        class ComponentHandle(component):
            def __init__(sub_self, name=None):
                comp_target = component.find(self.target, name)
                super().__init__(comp_target)

        class ComponentsHandle(components):
            def __init__(sub_self, name=None):
                comps_target = components.find(self.target, name)
                super().__init__(comps_target)

        class MaterialsHandle(materials):
            def __init__(sub_self, name=None):
                comps = self.target.get_components_by_class(unreal.MeshComponent) if self.target else []
                super().__init__(materials.gather_materials(comps, name))

        self.component = ComponentHandle
        self.components = ComponentsHandle
        self.materials = MaterialsHandle
        self.comp = ComponentHandle
        self.comps = ComponentsHandle
        self.mats = MaterialsHandle

    def rig(self, target=unreal.SkeletalMeshComponent, rig_class=None, *, layered=None):
        """取骨骼网格体上的 Control Rig；layered 仅用于新建轨道。"""
        return self.component(target).rig(rig_class, layered=layered)


def _positive_camera_value(value, name):
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name} 必须为有限正数')


def _camera_fov_ratio(degrees):
    if not 0 < degrees < 180:
        raise ValueError('水平 FOV 必须大于 0° 且小于 180°')
    return math.tan(math.radians(degrees) / 2)


def _set_camera_fov(lens, ratio):
    focal_length = lens.current_focal_length
    current_ratio = _camera_fov_ratio(lens.get_horizontal_field_of_view())
    lens.set_editor_property('current_focal_length', focal_length * current_ratio / ratio)


class camera(actor):
    """CineCameraActor 句柄，支持镜头和对焦操作。"""

    _actor_class = unreal.CineCameraActor

    def __init__(self, target):
        super().__init__(target.target if isinstance(target, actor) else target)
        if not isinstance(self.target, unreal.CineCameraActor):
            raise TypeError('camera 需要 CineCameraActor')

    def fov(self, degrees=None):
        """读取或设置水平 FOV（度），设置时返回自身。"""
        lens = self.target.get_cine_camera_component()
        if degrees is None:
            return lens.get_horizontal_field_of_view()
        ratio = _camera_fov_ratio(degrees)
        with unreal.ScopedEditorTransaction('Set camera FOV'):
            lens.modify()
            _set_camera_fov(lens, ratio)
        return self

    def aperture(self, f_stop=None):
        """读取或设置光圈，设置时返回自身。"""
        lens = self.target.get_cine_camera_component()
        if f_stop is None:
            return lens.current_aperture
        _positive_camera_value(f_stop, '光圈')
        return self._set_camera_property('current_aperture', f_stop)

    def focus(self, target):
        """按厘米手动对焦、追踪 Actor，或以 None 关闭景深。"""
        lens = self.target.get_cine_camera_component()
        settings = lens.focus_settings
        if target is None:
            settings.focus_method = unreal.CameraFocusMethod.DISABLE
        elif isinstance(target, (int, float)):
            _positive_camera_value(target, '对焦距离')
            settings.focus_method = unreal.CameraFocusMethod.MANUAL
            settings.manual_focus_distance = target
        else:
            if isinstance(target, str):
                target = actor(target)
            target = target.target if isinstance(target, actor) else target
            if not isinstance(target, unreal.Actor) or not unreal.SystemLibrary.is_valid(target):
                raise TypeError('对焦目标需要有效的 Actor')
            settings.focus_method = unreal.CameraFocusMethod.TRACKING
            settings.tracking_focus_settings = unreal.CameraTrackingFocusSettings(actor_to_track=target)
        return self._set_camera_property('focus_settings', settings)

    def _set_camera_property(self, prop, value):
        lens = self.target.get_cine_camera_component()
        with unreal.ScopedEditorTransaction('Edit camera lens'):
            lens.modify()
            lens.set_editor_property(prop, value)
        return self


def spawn_camera(name='CineCamera', *, location=None, rotation=None, fov=70.0,
                 aperture=22.0, focus_distance=1000.0):
    """按当前视口或指定姿态创建电影相机，返回 camera 句柄。"""
    ratio = _camera_fov_ratio(fov)
    _positive_camera_value(aperture, '光圈')
    _positive_camera_value(focus_distance, '对焦距离')
    if location is None or rotation is None:
        viewport = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_level_viewport_camera_info()
        if viewport is None:
            raise RuntimeError('找不到关卡视口，请指定 location 和 rotation')
        if location is None:
            location = viewport[0]
        if rotation is None:
            rotation = viewport[1]
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    with unreal.ScopedEditorTransaction('Spawn Cine Camera'):
        obj = subsystem.spawn_actor_from_class(unreal.CineCameraActor, location, rotation)
        if obj is None:
            raise RuntimeError('无法在当前关卡创建电影相机')
        obj.set_actor_label(name)
        obj.set_editor_property('tags', [*obj.tags, 'camera'])
        lens = obj.get_cine_camera_component()
        lens.modify()
        lens.set_editor_property('filmback', unreal.CameraFilmbackSettings(
            sensor_width=36.0, sensor_height=20.25))
        limits = lens.lens_settings
        limits.min_f_stop, limits.max_f_stop = 0.01, 22.0
        lens.set_editor_property('lens_settings', limits)
        lens.set_editor_property('current_aperture', aperture)
        settings = lens.focus_settings
        settings.focus_method = unreal.CameraFocusMethod.MANUAL
        settings.manual_focus_distance = focus_distance
        lens.set_editor_property('focus_settings', settings)
        _set_camera_fov(lens, ratio)
    return camera(obj)


class actors(MineprepWorldHandle):
    _collection = True
    _element = actor

    def __init__(self, name=unreal.Actor):
        """按标签/类型/回调查找多个 Actor，支持批量组件与材质操作"""
        target = type(self)._indexed(name)
        if target is None:
            target = []
            if isinstance(name, unreal.Actor):
                target = [name]
            elif isinstance(name, Iterable) and not isinstance(name, (str, bytes, type)):
                target = list(name)
            elif isinstance(name, type):
                target = unreal.GameplayStatics.get_all_actors_of_class(world(), name)
            elif name is not None:
                actors_list = unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.Actor)
                if isinstance(name, str):
                    name = f'*{name}*' if '*' not in name else name
                    target = unreal.EditorFilterLibrary.by_actor_label(actors_list, name, unreal.EditorScriptingStringMatchType.MATCHES_WILDCARD)
                elif callable(name):
                    target = [a for a in actors_list if name(a)]
        super().__init__(target, [a.get_actor_label() for a in target])

        class ComponentHandle(components):  # 多个 Actor 各取一个组件, 返回的仍是组件数组
            def __init__(sub_self, name=None):
                results = [comp for a in self.target if (comp := component.find(a, name))]
                super().__init__(results)

        class ComponentsHandle(components): # 多个 Actor 各取多个组件, 返回组件数组
            def __init__(sub_self, name=None):
                results = []
                for a in self.target:
                    results.extend(components.find(a, name))
                super().__init__(results)

        class MaterialsHandle(materials):
            def __init__(sub_self, name=None):
                comps = [c for a in self.target for c in a.get_components_by_class(unreal.MeshComponent)]
                super().__init__(materials.gather_materials(comps, name))

        self.component = ComponentHandle
        self.components = ComponentsHandle
        self.materials = MaterialsHandle
        self.comp = ComponentHandle
        self.comps = ComponentsHandle
        self.mats = MaterialsHandle


class selected(actors):
    """按标签/类型/回调查选中的Actors。整数或小数索引返回对应的 actor。"""

    def __new__(cls, name=unreal.Actor):
        if isinstance(name, (int, float)) and not isinstance(name, bool):
            return super().__new__(cls, name)
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        picked = list(subsystem.get_selected_level_actors())
        if isinstance(name, type):
            if name is not unreal.Actor:
                picked = [a for a in picked if isinstance(a, name)]
        elif isinstance(name, str):
            pattern = name if '*' in name else f'*{name}*'
            picked = list(unreal.EditorFilterLibrary.by_actor_label(
                picked, pattern, unreal.EditorScriptingStringMatchType.MATCHES_WILDCARD))
        elif callable(name):
            picked = [a for a in picked if name(a)]
        return actors(picked)


class component(MineprepWorldHandle):
    __iter__ = None

    def __init__(self, target=None):
        super().__init__(target, target.get_name() if target else '')

        class MaterialsHandle(materials):
            def __init__(sub_self, name=None):
                comps = [self.target] if isinstance(self.target, unreal.MeshComponent) else []
                super().__init__(materials.gather_materials(comps, name))

        self.materials = MaterialsHandle
        self.mats = MaterialsHandle

    @staticmethod
    def find(actor_obj, name):
        """静态方法：从单个 Actor 中提取符合条件的单个组件"""
        if not actor_obj:
            return None
        if not name:
            return actor_obj.root_component
        if isinstance(name, type):
            return actor_obj.get_component_by_class(name)
        
        comps = actor_obj.get_components_by_class(unreal.ActorComponent)
        if isinstance(name, str):
            pattern = f'*{name}*' if '*' not in name else name
            filtered_comps = unreal.EditorFilterLibrary.by_id_name(comps, pattern, unreal.EditorScriptingStringMatchType.MATCHES_WILDCARD)
            comp = next((c for c in filtered_comps if c.get_name() == name), None)
            if not comp and filtered_comps:
                comp = filtered_comps[0]
            return comp
        if callable(name):
            return next((c for c in comps if name(c)), None)
        return None

    def rig(self, rig_class=None, *, layered=None):
        """当前组件必须是 SkeletalMeshComponent，返回 Rig"""
        if not isinstance(self.target, unreal.SkeletalMeshComponent):
            kind = type(self.target).__name__ if self.target else 'None'
            throw(f'rig() 需要 SkeletalMeshComponent，当前: {kind}')
        return Rig(self.target, rig_class, layered=layered)


class components(MineprepWorldHandle):
    _collection = True
    _element = component

    def __init__(self, target=None):
        indexed = type(self)._indexed(target)
        if indexed is not None:
            target = indexed
        elif isinstance(target, unreal.ActorComponent):
            target = [target]
        elif isinstance(target, Iterable) and not isinstance(target, (str, bytes)):
            target = list(target)
        else:
            target = []
        super().__init__(target, [c.get_name() for c in target])

        class MaterialsHandle(materials):
            def __init__(sub_self, name=None):
                super().__init__(materials.gather_materials(self.target, name))

        self.materials = MaterialsHandle
        self.mats = MaterialsHandle

    @staticmethod
    def find(actor_obj, name):
        """静态方法：从单个 Actor 中提取符合条件的所有组件列表"""
        if not actor_obj:
            return []
        if not name:
            return actor_obj.get_components_by_class(unreal.ActorComponent)
        if isinstance(name, type):
            return actor_obj.get_components_by_class(name)
        
        comps = actor_obj.get_components_by_class(unreal.ActorComponent)
        if isinstance(name, str):
            name = f'*{name}*' if '*' not in name else name
            return unreal.EditorFilterLibrary.by_id_name(comps, name, unreal.EditorScriptingStringMatchType.MATCHES_WILDCARD)
        if callable(name):
            return [c for c in comps if name(c)]
        return []





class materials(MineprepWorldHandle):
    _collection = True

    def __init__(self, target=None):
        indexed = type(self)._indexed(target)
        if indexed is not None:
            target = indexed
        elif isinstance(target, unreal.MaterialInterface):
            target = [target]
        elif isinstance(target, unreal.MeshComponent):
            target = self.find(target)
        elif isinstance(target, Iterable) and not isinstance(target, (str, bytes, type)):
            items = list(target)
            if items and isinstance(items[0], unreal.MaterialInterface):
                target = items
            else:
                target = self.gather_materials(items)
        else:
            target = []
        super().__init__(target, [m.get_name() for m in target])

    @staticmethod
    def find(mesh_comp, name=None):
        """从网格组件中按名称/类型筛选材质列表"""
        if not mesh_comp or not isinstance(mesh_comp, unreal.MeshComponent):
            return []
        mats = [m for m in mesh_comp.get_materials() if m]
        if not name:
            return mats
        if isinstance(name, unreal.MaterialInterface):
            return [m for m in mats if m == name]
        if isinstance(name, type):
            return [m for m in mats if isinstance(m, name)]
        if isinstance(name, str):
            name = f'*{name}*' if '*' not in name else name
            return unreal.EditorFilterLibrary.by_id_name(mats, name, unreal.EditorScriptingStringMatchType.MATCHES_WILDCARD)
        if callable(name):
            return [m for m in mats if name(m)]
        return []

    @staticmethod
    def gather_materials(mesh_comps, name=None):
        """从多个网格组件汇总材质，可选名称过滤"""
        return [m for c in mesh_comps if isinstance(c, unreal.MeshComponent) for m in materials.find(c, name)]

    @staticmethod
    def get_material_param(mat, name):
        """读取材质标量/向量/贴图参数值"""
        if not mat or not name:
            return None
        for getter in ('get_scalar_parameter_value', 'get_vector_parameter_value', 'get_texture_parameter_value'):
            fn = getattr(mat, getter, None)
            if callable(fn):
                try:
                    return fn(name)
                except Exception:
                    pass
        return None

    @staticmethod
    def set_material_param(mat, name, value):
        """设置材质标量/向量/贴图参数值"""
        if not mat or not name:
            return
        if isinstance(value, unreal.Texture):
            setter, args = 'set_texture_parameter_value', (name, value)
        elif isinstance(value, (int, float, bool)):
            setter, args = 'set_scalar_parameter_value', (name, float(value))
        else:
            setter, args = 'set_vector_parameter_value', (name, value)
        fn = getattr(mat, setter, None)
        if callable(fn):
            fn(*args)
            return
        lib = getattr(unreal, 'MaterialEditingLibrary', None)
        if lib and isinstance(mat, unreal.MaterialInstance):
            if isinstance(value, unreal.Texture):
                lib.set_material_instance_texture_parameter_value(mat, name, value)
            elif isinstance(value, (int, float, bool)):
                lib.set_material_instance_scalar_parameter_value(mat, name, float(value))
            else:
                lib.set_material_instance_vector_parameter_value(mat, name, value)


    def get(self, param=''):
        """获取当前材质集合的参数值；单个材质时返回标量结果"""
        results = [self.get_material_param(m, param) for m in self.target]
        return results[0] if len(self.target) == 1 else results

    @undo
    def set(self, param: str, value: Any):
        """批量设置当前材质集合的参数值"""
        for m in self.target:
            self.set_material_param(m, param, value)
        return self

###########################################################################

class MineprepSequencerHandle(MineprepWorldHandle):
    @staticmethod
    def frame() -> int:
        """获取当前播放头所在帧数"""
        return mcseq.sequencer_frame()

    @staticmethod
    def time() -> float:
        """获取当前播放头所在时间"""
        return mcseq.sequencer_time()


class sequencer(MineprepSequencerHandle):
    __iter__ = None

    def __init__(self, target=None):
        """获取当前或指定 Level Sequence，可链式访问 .bindings/.tracks"""
        target = mcseq.resolve_sequence(target)
        super().__init__(target, mcseq.sequence_label(target))

        class BindingsHandle(bindings):
            def __init__(sub_self, name=None):
                super().__init__(mcseq.gather_bindings(self.target, name))

        class TracksHandle(tracks):
            def __init__(sub_self, name=None):
                super().__init__(mcseq.gather_tracks(self.target, name))

        self.bindings = BindingsHandle
        self.tracks = TracksHandle

    def set_range(self, start, end, *, fps=None):
        """设置 [start,end) 播放范围；int 帧/float 秒，不移动 section。"""
        mcseq.set_sequence_range(self.target, start, end, fps=fps)
        return self

    def set_frame(self, frame):
        """定位并求值当前聚焦的目标序列；int 帧/float 秒。"""
        mcseq.set_sequence_frame(self.target, frame)
        return self

    def play(self):
        mcseq.require_focused_sequence(self.target)
        unreal.LevelSequenceEditorBlueprintLibrary.play()
        return self

    def pause(self):
        mcseq.require_focused_sequence(self.target)
        unreal.LevelSequenceEditorBlueprintLibrary.pause()
        return self

    def camera_cut(self, camera, *, start=None, end=None, lock_viewport=False):
        """设置有限 [start,end) 相机片段；缺省当前帧至结尾，同范围复用。"""
        mcseq.set_camera_cut(self.target, camera, start=start, end=end, lock_viewport=lock_viewport)
        return self


def new_sequence(name='Sequence', *, fps=60, duration=5.0, open=False):
    """创建独立的 Level Sequence，短名称默认放在 /Game/Cinematics。"""
    return sequencer(mcseq.create_sequence(name, fps=fps, duration=duration, open_editor=open))


class bindings(MineprepSequencerHandle):
    _collection = True

    def __init__(self, target=None):
        indexed = type(self)._indexed(target)
        if indexed is not None:
            target = indexed
        elif mcseq.is_binding(target):
            target = [target]
        elif isinstance(target, unreal.LevelSequence):
            target = mcseq.gather_bindings(target)
        elif isinstance(target, Iterable) and not isinstance(target, (str, bytes, type)):
            items = list(target)
            if items and mcseq.is_binding(items[0]):
                target = items
            elif items and isinstance(items[0], unreal.LevelSequence):
                target = [b for seq in items for b in mcseq.gather_bindings(seq)]
            else:
                target = []
        elif target is None:
            target = mcseq.gather_bindings(mcseq.resolve_sequence())
        elif isinstance(target, str):
            target = mcseq.gather_bindings(mcseq.resolve_sequence(), target)
        else:
            target = []
        super().__init__(target, mcseq.labels_for(target))

        class TracksHandle(tracks):
            def __init__(sub_self, name=None):
                super().__init__(mcseq.gather_tracks(self.target, name))

        self.tracks = TracksHandle

    @staticmethod
    def find(parent, name=None):
        """从序列中收集绑定，可按显示名过滤"""
        return mcseq.gather_bindings(parent, name)

    def actor(self):
        """唯一绑定时返回它在关卡里的 Actor。没有、多个或尚未解析时返回 None。序列需已打开。"""
        items = [b for b in self.target if mcseq.is_binding(b)]
        if len(items) != 1:
            return None
        return mcseq.bound_actor(items[0])


class tracks(MineprepSequencerHandle):
    _collection = True

    def __init__(self, target=None):
        indexed = type(self)._indexed(target)
        if indexed is not None:
            target = indexed
        elif isinstance(target, unreal.MovieSceneTrack):
            target = [target]
        elif isinstance(target, unreal.LevelSequence):
            target = mcseq.gather_tracks(target)
        elif isinstance(target, Iterable) and not isinstance(target, (str, bytes, type)):
            items = list(target)
            if items and isinstance(items[0], unreal.MovieSceneTrack):
                target = items
            elif items and mcseq.is_binding(items[0]):
                target = mcseq.gather_tracks(items)
            elif items and isinstance(items[0], unreal.LevelSequence):
                target = [t for seq in items for t in mcseq.gather_tracks(seq)]
            else:
                target = []
        elif target is None:
            target = mcseq.gather_tracks(mcseq.resolve_sequence())
        elif isinstance(target, str):
            target = mcseq.gather_tracks(mcseq.resolve_sequence(), target)
        else:
            target = []
        super().__init__(target, mcseq.labels_for(target))

        class SectionsHandle(sections):
            def __init__(sub_self, name=None):
                super().__init__(mcseq.gather_sections(self.target, name))

        self.sections = SectionsHandle

    @staticmethod
    def find(parent, name=None):
        """从序列/绑定中收集轨道，可按显示名过滤"""
        return mcseq.gather_tracks(parent, name)


class sections(MineprepSequencerHandle):
    _collection = True

    def __init__(self, target=None):
        indexed = type(self)._indexed(target)
        if indexed is not None:
            target = indexed
        elif isinstance(target, unreal.MovieSceneSection):
            target = [target]
        elif isinstance(target, unreal.MovieSceneTrack):
            target = mcseq.gather_sections(target)
        elif isinstance(target, Iterable) and not isinstance(target, (str, bytes, type)):
            items = list(target)
            if items and isinstance(items[0], unreal.MovieSceneSection):
                target = items
            elif items and isinstance(items[0], unreal.MovieSceneTrack):
                target = mcseq.gather_sections(items)
            else:
                target = []
        elif target is None:
            target = mcseq.gather_sections(mcseq.gather_tracks(mcseq.resolve_sequence()))
        elif isinstance(target, str):
            target = mcseq.gather_sections(mcseq.gather_tracks(mcseq.resolve_sequence()), target)
        else:
            target = []
        super().__init__(target, mcseq.labels_for(target))

        class ChannelsHandle(channels):
            def __init__(sub_self, name=None):
                super().__init__(mcseq.gather_channels(self.target, name))

        self.channels = ChannelsHandle

    @staticmethod
    def find(parent, name=None):
        """从轨道中收集片段，可按显示名过滤"""
        return mcseq.gather_sections(parent, name)


class channels(MineprepSequencerHandle):
    _collection = True

    def __init__(self, target=None):
        if isinstance(target, channels):
            target = target._items
        indexed = type(self)._indexed(target)
        if indexed is not None:
            target = indexed
        elif isinstance(target, mcseq._LocatedItems):
            pass
        elif isinstance(target, unreal.MovieSceneScriptingChannel):
            target = [target]
        elif isinstance(target, unreal.MovieSceneSection):
            target = mcseq.gather_channels(target)
        elif isinstance(target, Iterable) and not isinstance(target, (str, bytes, type)):
            items = list(target)
            if items and isinstance(items[0], channels):
                target = mcseq._LocatedItems()
                seen = set()
                for handle in items:
                    for ch, section, index in handle._sources:
                        identity = (section.get_path_name(), index) if section is not None else id(ch)
                        if identity not in seen:
                            seen.add(identity)
                            target.extend(handle._items.select([ch]))
            elif items and isinstance(items[0], unreal.MovieSceneScriptingChannel):
                target = items
            elif items and isinstance(items[0], unreal.MovieSceneSection):
                target = mcseq.gather_channels(items)
            else:
                target = []
        elif target is None:
            target = mcseq.gather_channels(mcseq.gather_sections(mcseq.gather_tracks(mcseq.resolve_sequence())))
        elif isinstance(target, str):
            target = mcseq.gather_channels(
                mcseq.gather_sections(mcseq.gather_tracks(mcseq.resolve_sequence())), target,
            )
        else:
            target = []
        self._items = mcseq._LocatedItems(target)
        self._sources = [(ch, *self._items.locations.get(id(ch), (None, -1))) for ch in self._items]
        super().__init__(self._items, mcseq.labels_for(self._items))

        class KeysHandle(keys):
            def __init__(sub_self, name=None):
                super().__init__(mcseq.gather_keys(self._items, name))

        self.keys = KeysHandle

    def loop(self, mode='cycle', *, before=False, after=True):
        """设置整条 Float/Double 通道的外推；不复制关键帧或修改播放范围。"""
        mcseq.loop_channels(self._sources, mode, before=before, after=after)
        return self

    def retime(self, offset=0, scale=1.0, pivot=0):
        """整条通道重定时：pivot + (time-pivot)*scale + offset；int 帧/float 秒。"""
        mcseq.retime_channels(self._sources, offset=offset, scale=scale, pivot=pivot)
        return self

    def clear(self):
        """删除整条通道的键，保留默认值、外推和 section。"""
        mcseq.clear_channels(self._sources)
        return self

    @staticmethod
    def find(parent, name=None):
        """从片段中收集通道，可按显示名过滤"""
        return mcseq.gather_channels(parent, name)


class keys(MineprepSequencerHandle):
    _collection = True

    def __init__(self, target=None, *, sequence=None):
        if isinstance(target, keys):
            if sequence is None:
                sequence = target._sequence
            target = target._items
        indexed = type(self)._indexed(target)
        if indexed is not None:
            target = indexed
        elif isinstance(target, mcseq._LocatedItems):
            pass
        elif isinstance(target, unreal.MovieSceneScriptingKey):
            target = [target]
        elif isinstance(target, unreal.MovieSceneScriptingChannel):
            target = mcseq.gather_keys(target)
        elif isinstance(target, Iterable) and not isinstance(target, (str, bytes, type)):
            items = list(target)
            if items and isinstance(items[0], unreal.MovieSceneScriptingKey):
                target = items
            elif items and isinstance(items[0], unreal.MovieSceneScriptingChannel):
                target = mcseq.gather_keys(items)
            else:
                target = []
        elif target is None:
            target = mcseq.gather_keys(
                mcseq.gather_channels(mcseq.gather_sections(mcseq.gather_tracks(mcseq.resolve_sequence()))),
            )
        elif isinstance(target, int):
            target = mcseq.gather_keys(
                mcseq.gather_channels(mcseq.gather_sections(mcseq.gather_tracks(mcseq.resolve_sequence()))),
                target,
            )
        elif isinstance(target, str) or callable(target):
            target = mcseq.gather_keys(
                mcseq.gather_channels(mcseq.gather_sections(mcseq.gather_tracks(mcseq.resolve_sequence()))),
                target,
            )
        else:
            target = []
        self._items = mcseq._LocatedItems(target)
        self._sequence = mcseq.resolve_sequence(sequence) if sequence is not None else None
        super().__init__(self._items, mcseq.labels_for(self._items, sequence=self._sequence))

    def _select(self, selected):
        return keys(self._items.select(selected), sequence=self._sequence)

    def _owner_sequence(self, key):
        location = self._items.locations.get(id(key))
        sequence = location[0].get_typed_outer(unreal.LevelSequence) if location else self._sequence
        if sequence is None:
            raise ValueError('关键帧缺少所属序列，请从通道查询或传入 keys(..., sequence=...)')
        return sequence

    @property
    def frame(self):
        """按选择顺序返回整数显示帧。"""
        return List(key.get_time().frame_number.value for key in self.target)

    @property
    def time(self):
        """按各键所属序列的 tick rate 返回秒数。"""
        def seconds(key):
            rate = self._owner_sequence(key).get_tick_resolution()
            tick = key.get_time(unreal.MovieSceneTimeUnit.TICK_RESOLUTION).frame_number.value
            return tick * rate.denominator / rate.numerator
        return List(seconds(key) for key in self.target)

    @property
    def value(self):
        """按选择顺序返回原生键值。"""
        return List(key.get_value() for key in self.target)

    def __setitem__(self, index, value):
        """设置选中键的标量值，或接收增强赋值写回。"""
        selected = self[index]
        if isinstance(value, keys):
            if (len(selected) != len(value)
                    or any(left is not right for left, right in zip(selected, value))):
                raise TypeError('只能对相同关键帧选择执行运算写回')
            return
        if iscollection(value):
            raise TypeError('关键帧下标赋值只接受标量')
        self._edit('Set animation key values',
                   [(key.set_value, (value,)) for key in selected._unique_keys()])

    def _tangent_rate(self, key):
        if not isinstance(key, (unreal.MovieSceneScriptingFloatKey, unreal.MovieSceneScriptingDoubleKey)):
            raise TypeError('关键帧切线仅支持 Float／Double 键')
        rate = self._owner_sequence(key).get_tick_resolution()
        return rate.numerator / rate.denominator

    @property
    def arrive_tangent(self):
        """按选择顺序返回入切线斜率，单位为通道值每秒。"""
        return List(self._tangent_rate(key) * key.get_arrive_tangent() for key in self.target)

    @property
    def leave_tangent(self):
        """按选择顺序返回出切线斜率，单位为通道值每秒。"""
        return List(self._tangent_rate(key) * key.get_leave_tangent() for key in self.target)

    def _vector_tangent_values(self, samples):
        kind = type(samples[0])
        if len(self) != 3 * len(samples) or any(type(sample) is not kind for sample in samples):
            raise ValueError('每个切线样本需要同类型数据和对应的三个轴键')
        group, axes = ('Location', ('x', 'y', 'z')) if kind is unreal.Vector else (
            'Rotation', ('roll', 'pitch', 'yaw'))
        locations = [self._items.locations.get(id(key), (None, None)) for key in self.target]
        section = locations[0][0]
        if not isinstance(section, unreal.MovieScene3DTransformSection):
            raise ValueError('向量切线需要 Transform 通道来源')
        names = [mcseq._channel_name(channel) for channel in section.get_all_channels()]
        expected = [f'{group}.{axis}' for axis in 'XYZ']
        unit = unreal.MovieSceneTimeUnit.TICK_RESOLUTION
        seen = set()
        for start in range(0, len(self), 3):
            sources = locations[start:start + 3]
            if any(owner != section for owner, _ in sources) or [names[i] for _, i in sources] != expected:
                raise ValueError(f'向量切线需要按样本排列的完整 {group}.XYZ 键组')
            first, second, third = (key.get_time(unit).frame_number.value
                                    for key in self.target[start:start + 3])
            if first != second or first != third or first in seen:
                raise ValueError('三轴键组须共享同一时刻，且各组时刻不可重复')
            seen.add(first)
        return [getattr(sample, axis) for sample in samples for axis in axes]

    def tangents(self, slopes=None, *, arrive=None, leave=None):
        """为选中键设置每秒斜率，返回当前句柄。"""
        if not self or slopes is arrive is leave is None:
            return self
        mode = unreal.RichCurveTangentMode.RCTM_BREAK
        if slopes is not None:
            if arrive is not None or leave is not None:
                raise TypeError('slopes 与 arrive、leave 互斥')
            mode = unreal.RichCurveTangentMode.RCTM_USER

        def expand(values):
            if values is None:
                return [None] * len(self)
            values = list(values) if iscollection(values) else [values] * len(self)
            if any(isinstance(value, (unreal.Vector, unreal.Rotator)) for value in values):
                if not isinstance(values[0], (unreal.Vector, unreal.Rotator)):
                    raise ValueError('切线样本不能混合标量和向量')
                values = self._vector_tangent_values(values)
            if len(values) != len(self):
                raise ValueError('切线斜率数组长度须与关键帧选择相同')
            if not all(math.isfinite(value) for value in values):
                raise ValueError('切线斜率须为有限数值')
            return values

        if slopes is not None:
            incoming = outgoing = expand(slopes)
        else:
            incoming, outgoing = expand(arrive), expand(leave)
        edits = []
        for key, in_slope, out_slope in zip(self.target, incoming, outgoing):
            rate = self._tangent_rate(key)
            edits.extend(((key.set_interpolation_mode, (unreal.RichCurveInterpMode.RCIM_CUBIC,)),
                          (key.set_tangent_mode, (mode,))))
            if in_slope is not None:
                edits.append((key.set_arrive_tangent, (in_slope / rate,)))
            if out_slope is not None:
                edits.append((key.set_leave_tangent, (out_slope / rate,)))
        self._edit('Edit animation key tangents', edits)
        return self

    def _unique_keys(self):
        return {id(key): key for key in self.target}.values()

    @staticmethod
    def _edit(title, edits):
        if not edits:
            return
        try:
            with unreal.ScopedEditorTransaction(title):
                for setter, args in edits:
                    setter(*args)
        finally:
            mcseq._refresh_sequencer()

    def _arithmetic(self, op, operand):
        edits = [(key.set_value, (op(key.get_value(), operand),)) for key in self._unique_keys()]
        self._edit('Edit animation key values', edits)
        return self

    def __iadd__(self, operand):
        return self._arithmetic(operator.add, operand)

    def __isub__(self, operand):
        return self._arithmetic(operator.sub, operand)

    def __imul__(self, operand):
        return self._arithmetic(operator.mul, operand)

    def __itruediv__(self, operand):
        return self._arithmetic(operator.truediv, operand)

    def _shift(self, offset, direction):
        if not self or offset == 0:
            return self
        if not isinstance(offset, (int, float)):
            raise TypeError('移键偏移须为整数帧或浮点秒')
        unit = unreal.MovieSceneTimeUnit.TICK_RESOLUTION
        edits = []
        for key in self._unique_keys():
            sequence = self._owner_sequence(key)
            rate = sequence.get_tick_resolution()
            seconds = offset
            if isinstance(offset, int):
                display = sequence.get_display_rate()
                seconds = offset * display.denominator / display.numerator
            delta = round(seconds * rate.numerator / rate.denominator)
            if delta:
                tick = key.get_time(unit).frame_number.value + direction * delta
                edits.append((key.set_time, (unreal.FrameNumber(tick), 0.0, unit)))
        self._edit('Shift animation keys', edits)
        return self

    def __rshift__(self, offset):
        return self._shift(offset, 1)

    def __lshift__(self, offset):
        return self._shift(offset, -1)

    def remove(self):
        """删除选中的原生键，清空当前选择。"""
        channels_by_location = {}
        edits = []
        for key in self._unique_keys():
            location = self._items.locations.get(id(key))
            if location is None:
                raise ValueError('删除关键帧需要来源通道，请从 channels.keys() 查询')
            if location not in channels_by_location:
                section, index = location
                channels_by_location[location] = section.get_all_channels()[index]
            edits.append((channels_by_location[location].remove_key, (key,)))
        if edits:
            self._edit('Remove animation keys', edits)
            keys.__init__(self, [], sequence=self._sequence)
        return self

    @staticmethod
    def find(parent, name=None):
        """从通道中收集关键帧，可按帧号或显示名过滤"""
        return mcseq.gather_keys(parent, name)

##########################################################################

def keyframes(obj, prop, times, values, *, interp='auto', sequence=None, relative=False, unwrap=False):
    """为 Actor/SceneComponent（或其集合）批量写键；int 为帧，float 为秒。"""
    written = mcseq.keyframes(obj, prop, times, values, interp=interp, sequence=sequence, relative=relative, unwrap=unwrap)
    return keys(written, sequence=mcseq.resolve_sequence(sequence))
