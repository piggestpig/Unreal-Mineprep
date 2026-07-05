import unreal
import os
import re
import json
from collections.abc import Iterable
from pprint import pformat
from pathlib import Path

import mc_importer, mc_utils, mc_prep, mc_localization, mc_structure, mc_config, mc_sequencer
from mc_importer import import_block, import_item, resolve_block_json_path
from mc_utils import (reload, cast, uclass, bpclass, world, prints, warn, throw, panic,
                      enum, asynctask, askopenfilename, set_actor_label, select_actors,
                      lazy_import, safe)
from mc_prep import prep_texture, load_mcprep_data, colorize_material
from mc_localization import (language, KernelLanguage, LocalizationCache,
                             loctext, nsloctext, loctable_col, bilingual)
from mc_structure import parse_structure, structure_to_tex
from mc_config import config, paths, wclass
from mc_sequencer import (keyframe, resolve_sequence, gather_bindings, gather_tracks,
                          gather_sections, gather_channels, gather_keys, labels_for,
                          sequence_label, is_binding)

HotkeyObjCache = None
WidgetsCache = {}
ActorCache = None
SpawnIDCache = None
SpawnNameCache = None

def get_hotkey_object(reload=False):
    global HotkeyObjCache
    if HotkeyObjCache and not reload:
        return HotkeyObjCache

    loaded_class = uclass(paths.hotkey)
    if loaded_class:
        hotkey_object = unreal.new_object(loaded_class)
        HotkeyObjCache = hotkey_object
        return hotkey_object

    return None

####################################################################################

default_help_text = bilingual(
    '前往https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API查看更多信息',
    'Go to https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API for more information'
)

def help():
    return prints(default_help_text)

class helper:
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):
        target = owner if instance is None else instance
        return lambda: self.func(target)


class MineprepAPIHandle:
    class_help = ''
    inst_help = ''

    @helper
    def help(obj):
        if isinstance(obj, type):
            text = obj.class_help or f'{obj} {default_help_text}'
        else:
            text = obj.__class__.inst_help or f'{obj} {default_help_text}'
        return prints(text)

    def __init__(self, target, label=''):
        self.target = target
        self.label = label

    # MineprepAPIHandle[target] 先调用子类init，然后返回 self.target
    def __class_getitem__(cls, target):
        return cls(target).target

    # 调用不存在的属性或函数时，自动转发到target，支持数组
    def __getattr__(self, name):
        if isinstance(self.target, Iterable):
            if not self.target:
                return []
            if callable(getattr(self.target[0], name)):
                def wrapper(*args, **kwargs):
                    return [getattr(t, name)(*args, **kwargs) for t in self.target]
                return wrapper
            else:
                return [getattr(t, name) for t in self.target]

        return getattr(self.target, name)

    def get(self, prop=None):
        pass

    def get_value(self, prop=None):
        return float(self.get(prop))
    
    def get_string(self, prop=None):
        return str(self.get(prop))

    def set(self, prop=None, value=None):
        pass

    def set_string(self, prop=None, value=None):
        return self.set(prop, str(value))

    def set_value(self, prop=None, value=None):
        return self.set(prop, float(value))

######################################################################################

class MineprepAddonHandle(MineprepAPIHandle):
    def get(self, prop=None):
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

    def get_value(self, prop=None):
        return float(self.get(prop))

    def get_string(self, prop=None):
        return str(self.get(prop))

    #############################################################################################

    def trigger(self, name: str = ''):
        trigger_name = name if name else self.label
        return get_hotkey_object().call_method('Trigger', (self.target, str(trigger_name)))

    def click(self, index: int = -1):
        return get_hotkey_object().call_method('Click', (self.target, int(index)))

    def set(self, value = ''):
        if isinstance(value, (int, float, bool)):
            return self.set_value(value)
        return self.set_string(str(value))

    def set_string(self, value: str =''):
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
            print(outer_widget, prop_name, value)
            outer_widget.set_editor_property(prop_name, value)
            self.target.on_property_changed.broadcast(prop_name)
            return True


    def set_value(self, value: float = 0.0):
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


    def select(self, index: int = 0):
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
        label = name
        target = None
        if not name:
            id_cls_map = {k:bpclass(v).get_name() for k,v in WidgetsCache.items()}
            prints(bilingual('【unreal.mineprep.panel() 可用的对象->类别】',
                'Available objects -> classes for unreal.mineprep.panel()'),
                id_cls_map)
            return

        target = WidgetsCache.get(name)
        if not target:
            candidate = [k for k in WidgetsCache.keys() if name.lower() in k.lower()]
            warn(bilingual(f'未找到"{name}", 运行 unreal.mineprep.panel() 在日志中打印所有控件',
                f'No widget found for "{name}", run unreal.mineprep.panel() to print all available widgets'),
                '---------------',
                bilingual('你可能在寻找:', 'You may be looking for:'),
                candidate)
        super().__init__(target, label)

class toolbar(MineprepAddonHandle):
    def __init__(self, name = ''):
        get_hotkey_object().call_method('Toolbar', (str(name),))
        super().__init__(None, name)

class hotkey(MineprepAddonHandle):
    def __init__(self, name = ''):
        target = get_hotkey_object().call_method(str(name))
        super().__init__(target, name)

###########################################################################

class MineprepWorldHandle(MineprepAPIHandle):
    _collection = False

    @staticmethod
    def _pick(target, key, collection):
        if not collection:
            return target
        if isinstance(key, tuple):
            return [target[i] for i in key]
        return target[key]

    @classmethod
    def __class_getitem__(cls, key):
        if isinstance(key, (int, slice)) or (isinstance(key, tuple) and (not key or isinstance(key[0], int))):
            return cls._pick(cls().target, key, cls._collection)
        return cls(key).target

    def __getitem__(self, key):
        return self._pick(self.target, key, self._collection)

    def __str__(self):
        return pformat(self.label)
    
    def __repr__(self):
        return f'<mineprep.{self.__class__.__name__} object of ' + pformat(self.label) + '>'
    
    def get(self, prop=''):
        return self.get_editor_property(prop)

    def set(self, prop='', value=''):
        return self.set_editor_property(prop, value)


class materials(MineprepWorldHandle):
    _collection = True

    def __init__(self, target=None):
        if isinstance(target, unreal.MaterialInterface):
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
        return [m for c in mesh_comps if isinstance(c, unreal.MeshComponent) for m in materials.find(c, name)]

    @staticmethod
    def get_material_param(mat, name):
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
        results = [self.get_material_param(m, param) for m in self.target]
        return results[0] if len(self.target) == 1 else results

    def set(self, param='', value=''):
        for m in self.target:
            self.set_material_param(m, param, value)
        return self


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


class components(MineprepWorldHandle):
    _collection = True

    def __init__(self, target=None):
        if isinstance(target, unreal.ActorComponent):
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


class actor(MineprepWorldHandle):
    def __init__(self, name=unreal.Actor):
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


class actors(MineprepWorldHandle):
    _collection = True

    def __init__(self, name=unreal.Actor):
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

        class ComponentHandle(components):  # 多个 Actor 各取一个组件，返回的仍是组件数组
            def __init__(sub_self, name=None):
                results = [comp for a in self.target if (comp := component.find(a, name))]
                super().__init__(results)

        class ComponentsHandle(components): # 多个 Actor 各取多个组件，返回组件数组
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

###########################################################################

class MineprepSequencerHandle(MineprepWorldHandle):
    pass


class sequencer(MineprepSequencerHandle):
    def __init__(self, target=None):
        target = resolve_sequence(target)
        super().__init__(target, sequence_label(target))

        class BindingsHandle(bindings):
            def __init__(sub_self, name=None):
                super().__init__(gather_bindings(self.target, name))

        class TracksHandle(tracks):
            def __init__(sub_self, name=None):
                super().__init__(gather_tracks(self.target, name))

        self.bindings = BindingsHandle
        self.tracks = TracksHandle


class bindings(MineprepSequencerHandle):
    _collection = True

    def __init__(self, target=None):
        if is_binding(target):
            target = [target]
        elif isinstance(target, unreal.LevelSequence):
            target = gather_bindings(target)
        elif isinstance(target, Iterable) and not isinstance(target, (str, bytes, type)):
            items = list(target)
            if items and is_binding(items[0]):
                target = items
            elif items and isinstance(items[0], unreal.LevelSequence):
                target = [b for seq in items for b in gather_bindings(seq)]
            else:
                target = []
        elif target is None:
            target = gather_bindings(resolve_sequence())
        elif isinstance(target, str):
            target = gather_bindings(resolve_sequence(), target)
        else:
            target = []
        super().__init__(target, labels_for(target))

        class TracksHandle(tracks):
            def __init__(sub_self, name=None):
                super().__init__(gather_tracks(self.target, name))

        self.tracks = TracksHandle

    @staticmethod
    def find(parent, name=None):
        return gather_bindings(parent, name)


class tracks(MineprepSequencerHandle):
    _collection = True

    def __init__(self, target=None):
        if isinstance(target, unreal.MovieSceneTrack):
            target = [target]
        elif isinstance(target, unreal.LevelSequence):
            target = gather_tracks(target)
        elif isinstance(target, Iterable) and not isinstance(target, (str, bytes, type)):
            items = list(target)
            if items and isinstance(items[0], unreal.MovieSceneTrack):
                target = items
            elif items and is_binding(items[0]):
                target = gather_tracks(items)
            elif items and isinstance(items[0], unreal.LevelSequence):
                target = [t for seq in items for t in gather_tracks(seq)]
            else:
                target = []
        elif target is None:
            target = gather_tracks(resolve_sequence())
        elif isinstance(target, str):
            target = gather_tracks(resolve_sequence(), target)
        else:
            target = []
        super().__init__(target, labels_for(target))

        class SectionsHandle(sections):
            def __init__(sub_self, name=None):
                super().__init__(gather_sections(self.target, name))

        self.sections = SectionsHandle

    @staticmethod
    def find(parent, name=None):
        return gather_tracks(parent, name)


class sections(MineprepSequencerHandle):
    _collection = True

    def __init__(self, target=None):
        if isinstance(target, unreal.MovieSceneSection):
            target = [target]
        elif isinstance(target, unreal.MovieSceneTrack):
            target = gather_sections(target)
        elif isinstance(target, Iterable) and not isinstance(target, (str, bytes, type)):
            items = list(target)
            if items and isinstance(items[0], unreal.MovieSceneSection):
                target = items
            elif items and isinstance(items[0], unreal.MovieSceneTrack):
                target = gather_sections(items)
            else:
                target = []
        elif target is None:
            target = gather_sections(gather_tracks(resolve_sequence()))
        elif isinstance(target, str):
            target = gather_sections(gather_tracks(resolve_sequence()), target)
        else:
            target = []
        super().__init__(target, labels_for(target))

        class ChannelsHandle(channels):
            def __init__(sub_self, name=None):
                super().__init__(gather_channels(self.target, name))

        self.channels = ChannelsHandle

    @staticmethod
    def find(parent, name=None):
        return gather_sections(parent, name)


class channels(MineprepSequencerHandle):
    _collection = True

    def __init__(self, target=None):
        if isinstance(target, unreal.MovieSceneScriptingChannel):
            target = [target]
        elif isinstance(target, unreal.MovieSceneSection):
            target = gather_channels(target)
        elif isinstance(target, Iterable) and not isinstance(target, (str, bytes, type)):
            items = list(target)
            if items and isinstance(items[0], unreal.MovieSceneScriptingChannel):
                target = items
            elif items and isinstance(items[0], unreal.MovieSceneSection):
                target = gather_channels(items)
            else:
                target = []
        elif target is None:
            target = gather_channels(gather_sections(gather_tracks(resolve_sequence())))
        elif isinstance(target, str):
            target = gather_channels(
                gather_sections(gather_tracks(resolve_sequence())), target,
            )
        else:
            target = []
        super().__init__(target, labels_for(target))

        class KeysHandle(keys):
            def __init__(sub_self, name=None):
                super().__init__(gather_keys(self.target, name))

        self.keys = KeysHandle

    @staticmethod
    def find(parent, name=None):
        return gather_channels(parent, name)


class keys(MineprepSequencerHandle):
    _collection = True

    def __init__(self, target=None):
        if isinstance(target, unreal.MovieSceneScriptingKey):
            target = [target]
        elif isinstance(target, unreal.MovieSceneScriptingChannel):
            target = gather_keys(target)
        elif isinstance(target, Iterable) and not isinstance(target, (str, bytes, type)):
            items = list(target)
            if items and isinstance(items[0], unreal.MovieSceneScriptingKey):
                target = items
            elif items and isinstance(items[0], unreal.MovieSceneScriptingChannel):
                target = gather_keys(items)
            else:
                target = []
        elif target is None:
            target = gather_keys(
                gather_channels(gather_sections(gather_tracks(resolve_sequence()))),
            )
        elif isinstance(target, int):
            target = gather_keys(
                gather_channels(gather_sections(gather_tracks(resolve_sequence()))),
                target,
            )
        elif isinstance(target, str) or callable(target):
            target = gather_keys(
                gather_channels(gather_sections(gather_tracks(resolve_sequence()))),
                target,
            )
        else:
            target = []
        super().__init__(target, labels_for(target))

    @staticmethod
    def find(parent, name=None):
        return gather_keys(parent, name)

##########################################################################

def spawn_helper(button='', target='', loc=None, rot=None, scale=None, id=None):
    global SpawnIDCache, SpawnNameCache, ActorCache
    SpawnIDCache = id if id else target if isinstance(target, int) else None
    SpawnNameCache = target if isinstance(target, str) else None
    ActorCache = None

    panel(f'生成器子面板.{button}选项').set_string(target)
    panel(f'生成器子面板.{button}_可右键').click(0)
    SpawnIDCache = None
    SpawnNameCache = None
    actor = ActorCache

    if not ActorCache:
        warn(f'{button}: {target} 不存在')
        return None
    if loc:
        actor.set_actor_location(loc, False, True)
    if rot:
        actor.set_actor_rotation(rot, True)
    if scale:
        actor.set_actor_scale3d(scale)
    return actor


def spawn_block(target='', loc=None, rot=None, scale=None, id=None):
    return spawn_helper('放置方块', target, loc, rot, scale, id)

def spawn_item(target='', loc=None, rot=None, scale=None, id=None):
    return spawn_helper('放置物品', target, loc, rot, scale, id)

def spawn_mob(target='', loc=None, rot=None, scale=None, baby=False, id=None):
    panel("生成器子面板.生物宝宝_可点击").select(int(baby))
    return spawn_helper('放置生物', target, loc, rot, scale, id)

def spawn_preset(target='', loc=None, rot=None, scale=None, id=None):
    return spawn_helper('预设素材', target, loc, rot, scale, id)

def attach(target='', loc=None, rot=None, scale=None, id=None):
    return spawn_helper('附加组件', target, loc, rot, scale, id)


def spawn_blocks(mesh=None, transforms=[unreal.Transform()], loc=(0,0,0), rot=(0,0,0)):
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


def spawn_structure(filepath='', loc=(0,0,0), rot=(0,0,0), gpu=0, cull=0):
    map = parse_structure(filepath, cull=cull)
    filename = Path(filepath).stem
    inventory = loctable_col(6,2)

    actors = []
    meshes = []
    for name, transforms in map.items():
        path = resolve_block_json_path(name)
        mesh = None
        if path is not None:
            mesh = import_block(path, asset_name=name)
        else:
            candidate = next((n for n in inventory if n.startswith(name)), None)
            path = resolve_block_json_path(candidate) if candidate else None
            if path is not None:
                mesh = import_block(path, asset_name=name)
            else:
                warn(f'未找到{name}模型')

        if mesh is None:
            continue

        meshes.append(mesh)
        if not gpu:
            actor = spawn_blocks(mesh, transforms, loc, rot)
            actor.set_folder_path(filename)
            actors.append(actor)
            set_actor_label(actor, f'{filename}_{name}')

    if gpu == 1:
        BPT_Tex, BRT_Tex, mapping_data = structure_to_tex(map, filename)
        loaded_class = uclass('/Game/Mineprep/MC_Blueprint/PCG/PCG实例化方块.PCG实例化方块')
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(loaded_class, loc, rot)
        actor.set_folder_path('Structures')
        actors.append(actor)
        set_actor_label(actor, f'{filename}')

        # meshes转换为软对象路径数组
        mesh_paths = [unreal.SystemLibrary.get_soft_object_path(mesh) for mesh in meshes]
        actor.set_editor_property('Blocks', mesh_paths)
        actor.set_editor_property('PosTex', BPT_Tex)
        actor.set_editor_property('RotTex', BRT_Tex)

    elif gpu == 2:
        BPT_Tex, BRT_Tex, mapping_data = structure_to_tex(map, filename)
        loaded_class = uclass('/Game/Mineprep/MC_Blueprint/Niagara/动态地形粒子/动态结构粒子.动态结构粒子')
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(loaded_class, loc, rot)
        actor.set_folder_path('Structures')
        actors.append(actor)
        set_actor_label(actor, f'{filename}')

        #重启后方块丢失？
        #unreal.NiagaraDataInterfaceArrayMesh.set_niagara_array_mesh_sm(actor.root_component, '方块', meshes)
        actor.set_editor_property('方块', meshes)
        actor.root_component.set_variable_texture('方块位置纹理', BPT_Tex)
        actor.root_component.set_variable_texture('方块旋转纹理', BRT_Tex)

    select_actors(actors)
    return actors