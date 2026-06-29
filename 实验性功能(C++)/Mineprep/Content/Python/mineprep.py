import unreal
import os
import re
import json
from collections.abc import Iterable
from pprint import pformat
from pathlib import Path

import mc_importer, mc_utils, mc_prep, mc_localization, mc_structure, mc_config
from mc_importer import import_block, import_item, resolve_block_json_path
from mc_utils import (reload, cast, uclass, world, prints, warn, throw, panic,
                      asynctask, askopenfilename, set_actor_label, select_actors,
                      lazy_import, safe)
from mc_prep import prep_texture, load_mcprep_data, colorize_material
from mc_localization import language, get_kernel_language, loctext, nsloctext, loctable_col, LocalizationCache
from mc_structure import parse_structure, structure_to_tex
from mc_config import config, paths


HotkeyObjCache = None
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

def help():
    prints(f'前往https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API查看更多信息')
    return


class helper:
    @staticmethod
    def default_class_help(cls, *args, **kwargs):
        text = f'【{cls.__name__}类】 \n前往https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API查看更多信息'
        return prints(text)

    @staticmethod
    def default_instance_help(instance, *args, **kwargs):
        text = f'【{instance.__class__.__name__}实例】\n前往https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API查看更多信息'
        return prints(text)

    def __init__(self, class_func=None, instance_func=None):
        self.class_func = class_func or self.default_class_help
        self.instance_func = instance_func or self.default_instance_help

    def __get__(self, instance, owner):
        if instance is None:
            # 在类上调用
            return lambda *args, **kwargs: self.class_func(owner, *args, **kwargs)
        else:
            # 在实例上调用
            return lambda *args, **kwargs: self.instance_func(instance, *args, **kwargs)


class MineprepAPIHandle:
    help = helper()

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

    ########################################################################

    def get(self, prop=None):
        cast = prop if isinstance(prop, type) else None
        type_str = cast.__name__ if cast else str(prop)
        value = get_hotkey_object().call_method('GetValue', (self.target, type_str))
        try:
            value = eval(str(value))
        except:
            pass
        return cast(value) if cast else value
    
    def get_value(self, prop=None):
        return float(self.get(prop))
    
    def get_string(self, prop=None):
        return str(self.get(prop))

    #############################################################################################

    def trigger(self, name=''):
        trigger_name = name if name else self.label
        return get_hotkey_object().call_method('Trigger', (self.target, str(trigger_name)))
    
    def click(self, index=-1):
        return get_hotkey_object().call_method('Click', (self.target, int(index)))
    
    def set(self, value=''):
        if isinstance(value, (int, float, bool)):
            return self.set_value(value)
        return self.set_string(str(value))

    def set_string(self, value=''):
        return get_hotkey_object().call_method('SetString', (self.target, str(value)))
    
    def set_value(self, value=0.0):
        return get_hotkey_object().call_method('SetValue', (self.target, float(value)))
    
    def select(self, index=0):
        return get_hotkey_object().call_method('Select', (self.target, int(index)))


class panel(MineprepAPIHandle):
    def __init__(self, name = ''):
        label, target = get_hotkey_object().call_method('Panel', (str(name),))
        super().__init__(target, label)

class toolbar(MineprepAPIHandle):
    def __init__(self, name = ''):
        get_hotkey_object().call_method('Toolbar', (str(name),))
        super().__init__(None, name)

class hotkey(MineprepAPIHandle):
    def __init__(self, name = ''):
        target = get_hotkey_object().call_method(str(name))
        super().__init__(target, name)

###########################################################################

class MineprepWorldHandle(MineprepAPIHandle):
    def __str__(self):
        return pformat(self.label)
    
    def __repr__(self):
        return f'<mineprep.{self.__class__.__name__} object at' + pformat(self.label)
    
    def get(self, prop=''):
        return self.get_editor_property(prop)

    def set(self, prop='', value=''):
        return self.set_editor_property(prop, value)


class component(MineprepWorldHandle):
    def __init__(self, target=None):
        super().__init__(target, target.get_name() if target else '')

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
            name_lower = name.lower()
            target = next((c for c in comps if c.get_name().lower() == name_lower), None)
            if not target:
                target = next((c for c in comps if re.sub(r'[\s\d]+$', '', c.get_name().lower()) == name_lower), None)
            return target
        if callable(name):
            return next((c for c in comps if name(c)), None)
        return None


class components(MineprepWorldHandle):
    def __init__(self, target=None):
        target = target or []
        super().__init__(target, [c.get_name() for c in target])

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
        if isinstance(name, type):
            target = unreal.GameplayStatics.get_actor_of_class(world(), name)
        else:
            actors_list = unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.Actor)
            if isinstance(name, str):
                target = next((a for a in actors_list if a.get_actor_label() == name), None)
                if not target:
                    target = next((a for a in actors_list if re.sub(r'[\s\d]+$', '', a.get_actor_label()) == name), None)
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

        self.component = ComponentHandle
        self.components = ComponentsHandle


class actors(MineprepWorldHandle):
    def __init__(self, name=unreal.Actor):
        target = []
        if isinstance(name, type):
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

        self.component = ComponentHandle
        self.components = ComponentsHandle


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

def spawn_mob(target='', loc=None, rot=None, scale=None, baby=None, id=None):
    if baby is not None and panel("生成器子面板.生物宝宝_可点击").get() != int(baby):
        panel("生成器子面板.生物宝宝_可点击").click()
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


def spawn_structure(filepath='', loc=(0,0,0), rot=(0,0,0), gpu=False):
    map = parse_structure(filepath)
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
    
    if gpu:
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

    select_actors(actors)
    return actors