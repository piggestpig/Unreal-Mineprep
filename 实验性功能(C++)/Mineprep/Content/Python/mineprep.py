import unreal
import os
import re
import json
import builtins
from collections.abc import Iterable
from pprint import pformat
from pathlib import Path
from typing import Any

import mc_importer, mc_utils, mc_prep, mc_localization, mc_structure, mc_config
import mc_sequencer, mc_widget, mc_mod, mc_mesh, mc_material, mc_parallel
import mc_sequencer as mcseq
from mc_importer import import_block, import_item, resolve_block_json_path, get_all_blocks
from mc_utils import (reload, cast, uclass, bpclass, world, prints, warn, throw, panic,
                      enum, askopenfilename, send2trash, set_actor_label, select_actors,
                      lazy_import, undo, get_hotkey_object, construct, uasset, copy,
                      List, SafeList, WrapList, iscollection, debug, resolve_soft, dialog,
                      askdirectory, asksaveasfilename, startfile, screenshot)
from mc_parallel import (
    delay, tick, asynctask, thread, asyncthread,
    DelayRunner, TickRunner, AsyncTaskRunner, ThreadRunner,
)
from mc_prep import prep_texture, load_mcprep_data, colorize_material
from mc_material import tex_to_color, color_to_tex, ColorList
from mc_localization import (localize, loctext, nsloctext, loctable_col, bilingual, tooltip)
from mc_structure import (
    parse_structure, structure_to_tex, structure_parts, Blocks,
    convert_to_unreal_transforms, convert_to_packed_arrays,
)
import mcvars
from mc_config import config, paths, wclass
from mc_sequencer import keyframe, Rig
from mc_widget import Layout, PropertyGroup, add_widget, ui, make_combo_text
from mc_mod import mods, Mod
from mc_mesh import merge_skm


####################################################################################

def help():
    """打印Mineprep Python API的默认提示"""
    return prints(tooltip('help'), duration=5)

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

class MineprepAddonHandle(MineprepAPIHandle):
    def get(self, prop: type=None):
        """获取属性值，自动转换为prop类型；如果target是数组，则返回数组"""
        value = None
        cast_type = prop if isinstance(prop, type) else None
        type_str = cast_type.__name__ if cast_type else str(prop)

        if cast(self.target, wclass.checkbox):
            state = self.target.get_checked_state()
            if state == unreal.CheckBoxState.CHECKED:
                value = 1
            elif state == unreal.CheckBoxState.UNCHECKED:
                value = 0
            else:
                value = -1

        elif cast(self.target, wclass.MCimage):
            value = self.target.get_editor_property('当前状态')

        elif cast(self.target, wclass.slider):
            value = self.target.get_value()

        elif cast(self.target, wclass.option):
            if cast_type in (int, float):
                value = self.target.get_selected_index()
            elif issubclass(cast_type, Iterable) and not issubclass(cast_type, (str, bytes)):
                value = [self.target.get_option_at_index(i) for i in range(self.target.get_option_count())]
            else:
                value = self.target.get_selected_option()

        elif cast(self.target, wclass.textbox):
            value = self.target.get_text()

        elif cast(self.target, wclass.prop):
            prop_name = self.target.get_property_name()
            outer_widget = unreal.UserWidgetFunctionLibrary.get_outer_user_widget(self.target)
            value = outer_widget.get_editor_property(prop_name)

        else:
            value = self.target.get_editor_property(type_str)

        try:
            value = eval(str(value))
        except:
            pass
        return cast_type(value) if cast_type else value

    def get_value(self, prop: type=None) -> float:
        """获取属性值并转为浮点数"""
        return float(self.get(prop))

    def get_string(self, prop: type=None) -> str:
        """获取属性值并转为字符串"""
        return str(self.get(prop))

    #############################################################################################

    def trigger(self, name: str = ''):
        """触发按钮"""
        trigger_name = name if name else self.label
        return get_hotkey_object().call_method('Trigger', (self.target, str(trigger_name)))

    def click(self, index: int = -1):
        """模拟点击按钮, -1左键, 0中键, 1右键, 2双击"""
        return get_hotkey_object().call_method('Click', (self.target, int(index)))

    def set(self, value = ''):
        """按值类型自动调用 set_value 或 set_string"""
        if isinstance(value, (int, float, bool)):
            return self.set_value(value)
        return self.set_string(str(value))

    def set_string(self, value: str = ''):
        """用字符串设置控件值（选项/文本框/复选框等）"""
        value = str(value)
        if cast(self.target, wclass.checkbox):
            if value.lower() in ('true', '1'):
                return self.select(1)
            elif value.lower() in ('false', '0'):
                return self.select(0)
            else:
                return self.select(int(value))

        elif cast(self.target, wclass.slider):
            return self.set_value(float(value))

        elif cast(self.target, wclass.option):
            self.target.set_selected_option(value)
            self.target.on_selection_changed.broadcast(value, unreal.SelectInfo.ON_MOUSE_CLICK)
            return True

        elif cast(self.target, wclass.textbox):
            self.target.set_text(value)
            self.target.on_text_changed.broadcast(value)
            self.target.on_text_committed.broadcast(value, unreal.TextCommit.ON_ENTER)
            return True

        elif cast(self.target, wclass.prop):
            prop_name = self.target.get_property_name()
            outer_widget = unreal.UserWidgetFunctionLibrary.get_outer_user_widget(self.target)
            value = eval(value)
            unreal.log(f"设置属性 {prop_name} 的值为 {value}")
            outer_widget.set_editor_property(prop_name, value)
            self.target.on_property_changed.broadcast(prop_name)
            return True

    def set_value(self, value: float = 0.0):
        """用数值设置控件值（滑块/复选框/选项等）"""
        if cast(self.target, wclass.checkbox):
            return self.select(int(value))

        elif cast(self.target, wclass.slider):
            self.target.set_value(float(value))
            self.target.on_value_changed.broadcast(float(value))
            return True

        elif cast(self.target, wclass.option):
            return self.select(int(value))

        elif cast(self.target, wclass.textbox):
            return self.set_string(str(value))

    def select(self, index: int = 0) -> bool:
        """用整数设置选项"""
        if cast(self.target, wclass.checkbox):
            state = unreal.CheckBoxState.UNDETERMINED
            if index > 0:
                state = unreal.CheckBoxState.CHECKED
            elif index == 0:
                state = unreal.CheckBoxState.UNCHECKED
            self.target.set_checked_state(state)
            self.target.on_check_state_changed.broadcast(index > 0)
            return True

        elif cast(self.target, wclass.slider):
            return self.set_value(float(index))

        elif cast(self.target, wclass.option):
            option_count = self.target.get_option_count()
            if index < 0:
                index = option_count() + index
            index = max(0, min(index, option_count - 1))
            self.target.set_selected_index(index)
            string = self.target.get_option_at_index(index)
            self.target.on_selection_changed.broadcast(string, unreal.SelectInfo.ON_MOUSE_CLICK)
            return True

        elif cast(self.target, wclass.MCimage):
            state = self.target.get_editor_property('当前状态')
            if index == state:
                return True
            if index > 0:
                self.click() #左键点击
            elif index < 0:
                self.click(1) #右键点击
            elif state > 0:
                self.click() #左键点击还原为0
            else:
                self.click(1) #右键点击还原为0
            return True

        return False



class panel(MineprepAddonHandle):
    def __init__(self, name = ''):
        """按名称获取插件面板控件；空名称时打印所有可用面板"""
        label = name
        target = None
        if not name:
            id_cls_map = {k:bpclass(v).get_name() for k,v in mc_widget.WidgetsCache.items() if v}
            prints(tooltip('所有插件面板'), id_cls_map)
            return

        target = mc_widget.WidgetsCache.get(name)
        if not target:
            candidate = [k for k in mc_widget.WidgetsCache.keys() if name.lower() in k.lower()]
            warn(tooltip('未找到面板', name), '---------------', tooltip('你可能在寻找'), candidate)
        super().__init__(target, label)

class toolbar(MineprepAddonHandle):
    def __init__(self, name = ''):
        """触发工具栏按钮"""
        get_hotkey_object().call_method('Toolbar', (str(name),))
        super().__init__(None, name)

class hotkey(MineprepAddonHandle):
    def __init__(self, name = ''):
        """调用自定义快捷键蓝图中的同名函数"""
        target = get_hotkey_object().call_method(str(name))
        super().__init__(target, name)

###########################################################################

class MineprepWorldHandle(MineprepAPIHandle):
    @classmethod
    def _indexed(cls, key):
        """int/bool 列表视为对 cls() 的花式下标；否则 None。"""
        if List._take(key) is None:
            return None
        return list(cls()[key])

    @undo
    def __class_getitem__(cls, key):
        """类下标：int/slice/numpy 多轴/花式下标取集合元素；其它参数走构造查找"""
        if isinstance(key, (int, slice)):
            return cls()[key]
        if isinstance(key, tuple) and len(key) == 2:
            return cls()[key]
        if cls._collection and List._take(key) is not None:
            return cls()[key]
        return cls(key).target

    def __getitem__(self, key):
        """实例下标：集合支持 int/slice/numpy 多轴；非集合返回自身 target"""
        if not self._collection:
            return self.target
        return self.target[key]

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
    def key(self, prop: str='', value: Any=None, time: int|float=None):
        """在当前时刻对指定属性打关键帧。
        提供value时会先设置值，然后打关键帧。
        如果重载时间time，传入int表示帧数，传入float表示秒数。
        """
        if isinstance(self.target, List):
            return WrapList(keyframe(t, prop, value, time) for t in self.target)
        return keyframe(self.target, prop, value, time)


class actor(MineprepWorldHandle):
    def __init__(self, name=unreal.Actor):
        """按标签/类型/回调查找单个 Actor，支持 .comp/.comps/.mats 链式访问"""
        target = None
        if isinstance(name, unreal.Actor):
            target = name
        elif isinstance(name, type):
            target = unreal.GameplayStatics.get_actor_of_class(world(), name)
        else:
            actors_list = unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.Actor)
            if isinstance(name, str):
                name = f'*{name}*' if '*' not in name else name
                actors = unreal.EditorFilterLibrary.by_actor_label(actors_list, name, unreal.EditorScriptingStringMatchType.MATCHES_WILDCARD)
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

    def rig(self, target=unreal.SkeletalMeshComponent, rig_class=None):
        """取骨骼网格体上的 Control Rig；先 component(target) 再 .rig(rig_class)"""
        return self.component(target).rig(rig_class)


class actors(MineprepWorldHandle):
    _collection = True

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
            else:
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


class component(MineprepWorldHandle):
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
            name = f'*{name}*' if '*' not in name else name
            filtered_comps = unreal.EditorFilterLibrary.by_id_name(comps, name, unreal.EditorScriptingStringMatchType.MATCHES_WILDCARD)
            comp = next((c for c in filtered_comps if c.get_name() == name), None)
            if not comp and filtered_comps:
                comp = filtered_comps[0]
            return comp
        if callable(name):
            return next((c for c in comps if name(c)), None)
        return None

    def rig(self, rig_class=None):
        """当前组件必须是 SkeletalMeshComponent，返回 Rig"""
        if not isinstance(self.target, unreal.SkeletalMeshComponent):
            kind = type(self.target).__name__ if self.target else 'None'
            throw(f'rig() 需要 SkeletalMeshComponent，当前: {kind}')
        return Rig(self.target, rig_class)


class components(MineprepWorldHandle):
    _collection = True

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
    def key():
        """⚠暂不支持"""
        return None

    @staticmethod
    def frame() -> int:
        """获取当前播放头所在帧数"""
        return mcseq.sequencer_frame()

    @staticmethod
    def time() -> float:
        """获取当前播放头所在时间"""
        return mcseq.sequencer_time()


class sequencer(MineprepSequencerHandle):
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
        indexed = type(self)._indexed(target)
        if indexed is not None:
            target = indexed
        elif isinstance(target, unreal.MovieSceneScriptingChannel):
            target = [target]
        elif isinstance(target, unreal.MovieSceneSection):
            target = mcseq.gather_channels(target)
        elif isinstance(target, Iterable) and not isinstance(target, (str, bytes, type)):
            items = list(target)
            if items and isinstance(items[0], unreal.MovieSceneScriptingChannel):
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
        super().__init__(target, mcseq.labels_for(target))

        class KeysHandle(keys):
            def __init__(sub_self, name=None):
                super().__init__(mcseq.gather_keys(self.target, name))

        self.keys = KeysHandle

    @staticmethod
    def find(parent, name=None):
        """从片段中收集通道，可按显示名过滤"""
        return mcseq.gather_channels(parent, name)


class keys(MineprepSequencerHandle):
    _collection = True

    def __init__(self, target=None):
        indexed = type(self)._indexed(target)
        if indexed is not None:
            target = indexed
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
        super().__init__(target, mcseq.labels_for(target))

    @staticmethod
    def find(parent, name=None):
        """从通道中收集关键帧，可按帧号或显示名过滤"""
        return mcseq.gather_keys(parent, name)

##########################################################################

def spawn_helper(button='', target='', loc=None, rot=None, scale=None, id=None) -> unreal.Actor:
    """通过生成器面板放置 Actor，可指定位置/旋转/缩放"""
    mcvars.SpawnIDCache = id if id else target if isinstance(target, int) else None
    mcvars.SpawnNameCache = target if isinstance(target, str) else None
    mcvars.ActorCache = None

    panel(f'生成器子面板.{button}选项').set_string(target)
    panel(f'生成器子面板.{button}_可右键').click(0)
    mcvars.SpawnIDCache = None
    mcvars.SpawnNameCache = None
    actor = mcvars.ActorCache

    if not actor:
        warn(f'{button}: {target} 不存在')
        return None
    if loc:
        actor.set_actor_location(loc, False, True)
    if rot:
        actor.set_actor_rotation(rot, True)
    if scale:
        actor.set_actor_scale3d(scale)
    return actor


def spawn_block(target='', loc=None, rot=None, scale=None, id: int=None) -> unreal.Actor:
    """放置单个方块, 指定id时忽略target名称"""
    return spawn_helper('放置方块', target, loc, rot, scale, id)

def spawn_item(target='', loc=None, rot=None, scale=None, id: int=None) -> unreal.Actor:
    """放置物品, 指定id时忽略target名称"""
    return spawn_helper('放置物品', target, loc, rot, scale, id)

def spawn_mob(target='', loc=None, rot=None, scale=None, baby=False, id: int=None) -> unreal.Actor:
    """放置生物, 指定id时忽略target名称"""
    panel("生成器子面板.生物宝宝_可点击").select(int(baby))
    return spawn_helper('放置生物', target, loc, rot, scale, id)

def spawn_preset(target='', loc=None, rot=None, scale=None, id: int=None) -> unreal.Actor:
    """放置预设素材, 指定id时忽略target名称"""
    return spawn_helper('预设素材', target, loc, rot, scale, id)

def attach(target='', loc=None, rot=None, scale=None, id: int=None) -> unreal.Actor:
    """附加组件至选中项, 指定id时忽略target名称"""
    return spawn_helper('附加组件', target, loc, rot, scale, id)


def spawn_blocks(mesh=None, transforms=[unreal.Transform()], loc=(0,0,0), rot=(0,0,0)) -> unreal.Actor:
    """放置多个方块为实例化方块"""
    loaded_class = uclass('/Game/Mineprep/MC_Blueprint/Core/实例化方块.实例化方块')
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(loaded_class, loc, rot)
    ism = actor.root_component

    if isinstance(mesh, str):
        asset = unreal.load_asset(mesh)
        if isinstance(asset, unreal.StaticMesh):
            mesh = asset
        else:
            mesh = import_block(mesh)

    ism.set_editor_property('StaticMesh', mesh)
    ism.clear_instances()
    ism.add_instances(transforms, False, False, True)
    return actor


def spawn_structure(source='', loc=(0,0,0), rot=(0,0,0), gpu=0, cull=0, merge=0,
                    reload=False, name='', center=None) -> list[unreal.Actor]:
    """生成MC结构。source 是文件路径或 Blocks；gpu=1 是 PCG，gpu=2 是粒子；
    cull=1按类型剔除内部实心, cull=2全体实心统一剔除内部, cull=3=2+剔除AABB侧面与底面；
    merge=0关, 1长条, 2平面, 3长方体（仅完整正方体；cull 优先于 merge）
    """
    if isinstance(source, Blocks):
        filename = name or source.name or 'structure'
        use_center = False if center is None else bool(center)
        cells = source.copy_cells()
    else:
        if not source:
            warn('spawn_structure 需要文件路径或 Blocks')
            return []
        loaded = Blocks.from_file(source)
        if not loaded:
            return []
        filename = name or loaded.name or Path(str(source)).stem
        use_center = True if center is None else bool(center)
        cells = loaded.copy_cells()

    cells = mc_structure._apply_cull(cells, cull)
    packed = bool(gpu)
    if packed:
        payload_map = convert_to_packed_arrays(cells, center=use_center, merge=merge)
    else:
        payload_map = convert_to_unreal_transforms(cells, center=use_center, merge=merge)

    inventory = loctable_col(6,2)
    actors = []
    meshes = []
    spawn_jobs = []

    for model_name, payload in payload_map.items():
        path = resolve_block_json_path(model_name)
        mesh = None
        if path is not None:
            mesh = import_block(path, asset_name=model_name, reload=reload)
        else:
            candidate = next((n for n in inventory if n.startswith(model_name)), None)
            path = resolve_block_json_path(candidate) if candidate else None
            if path is not None:
                mesh = import_block(path, asset_name=model_name, reload=reload)
            else:
                warn(f'未找到{model_name}模型')

        meshes.append(mesh)
        if mesh is not None and not gpu:
            spawn_jobs.append((model_name, mesh, payload))

    if not gpu:
        for model_name, mesh, transforms in spawn_jobs:
            actor = spawn_blocks(mesh, transforms, loc, rot)
            actor.set_folder_path(filename)
            actors.append(actor)
            set_actor_label(actor, f'{filename}_{model_name}')

    if gpu == 1:
        BPT_Tex, BRT_Tex, mapping_data = structure_to_tex(payload_map, filename)
        loaded_class = uclass('/Game/Mineprep/MC_Blueprint/PCG/PCG实例化方块.PCG实例化方块')
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(loaded_class, loc, rot)
        actor.set_folder_path('Structures')
        actors.append(actor)
        set_actor_label(actor, f'{filename}')
        mesh_paths = [unreal.SystemLibrary.get_soft_object_path(mesh) for mesh in meshes]
        actor.set_editor_property('Blocks', mesh_paths)
        actor.set_editor_property('PosTex', BPT_Tex)
        actor.set_editor_property('RotTex', BRT_Tex)

    elif gpu == 2:
        BPT_Tex, BRT_Tex, mapping_data = structure_to_tex(payload_map, filename)
        loaded_class = uclass('/Game/Mineprep/MC_Blueprint/Niagara/动态地形粒子/动态结构粒子.动态结构粒子')
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(loaded_class, loc, rot)
        actor.set_folder_path('Structures')
        actors.append(actor)
        set_actor_label(actor, f'{filename}')
        actor.set_editor_property('方块', meshes)
        actor.root_component.set_variable_texture('方块位置纹理', BPT_Tex)
        actor.root_component.set_variable_texture('方块旋转纹理', BRT_Tex)

    select_actors(actors)
    return actors