import unreal
import re
import mc_importer, mc_utils
from mc_importer import import_block, import_item
from mc_utils import asynctask, reload, cast, uclass, world, askopenfilename, set_actor_label_unique
from mc_prep import prep_texture

cache = True
HotkeyObjCache = None

ActorCache = None


def get_hotkey_object(reload=False):
    global HotkeyObjCache
    global cache
    if HotkeyObjCache and cache and not reload:
        return HotkeyObjCache

    blueprint_path = '/Mineprep/Mineprep自定义快捷键.Mineprep自定义快捷键_C'
    loaded_class = unreal.load_class(None, blueprint_path)
    
    if loaded_class:
        hotkey_object = unreal.new_object(loaded_class)
        HotkeyObjCache = hotkey_object
        return hotkey_object

    return None

####################################################################################

def help():
    text = f'前往https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API查看更多信息'
    unreal.SystemLibrary.print_string(None, text)
    return


class helper:
    @staticmethod
    def default_class_help(cls, *args, **kwargs):
        text = f'【{cls.__name__}类】 \n前往https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API查看更多信息'
        unreal.SystemLibrary.print_string(None, text)
        return text

    @staticmethod
    def default_instance_help(instance, *args, **kwargs):
        text = f'【{instance.__class__.__name__}实例】\n前往https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API查看更多信息'
        unreal.SystemLibrary.print_string(None, text)
        return text

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

    # 调用不存在的函数时，自动转发到 target
    def __getattr__(self, name):
        return getattr(self.target, name)

    #############################################################################################

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

class config(MineprepAPIHandle):
    def __init__(self, name = ''):
        label, target = get_hotkey_object().call_method('Config', (str(name),))
        super().__init__(target, label)

class hotkey(MineprepAPIHandle):
    def __init__(self, name = ''):
        target = get_hotkey_object().call_method(str(name))
        super().__init__(target, name)


class actor(MineprepAPIHandle):
    def __init__(self, name = unreal.Actor):
        target = None
        if isinstance(name, type):
            target = unreal.GameplayStatics.get_actor_of_class(world(), name)
        elif isinstance(name, str):
            actors = unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.Actor)
            target = next((a for a in actors if a.get_actor_label() == name), None)
            if not target:
                target = next((a for a in actors if re.sub(r'[\s\d]+$', '', a.get_actor_label()) == name), None)
        label = target.get_actor_label() if target else ''
        super().__init__(target, label)


class actors(MineprepAPIHandle):
    def __init__(self, name = unreal.Actor):
        target = []
        if isinstance(name, type):
            target = unreal.GameplayStatics.get_all_actors_of_class(world(), name)
        elif isinstance(name, str):
            actors = unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.Actor)
            target = [a for a in actors if name.lower() in a.get_actor_label().lower()]
        label = [a.get_actor_label() for a in target] if target else []
        super().__init__(target, label)

##########################################################################

def spawn_helper(button='', target='', loc=None, rot=None, scale=None):
    panel(f'生成器子面板.{button}选项').set_string(target)
    panel(f'生成器子面板.{button}_可右键').click(0)
    actor = ActorCache
    if not ActorCache:
        unreal.SystemLibrary.print_string(None, f'{button}: {target} 失败')
        return None
    if loc:
        actor.set_actor_location(loc, False, True)
    if rot:
        actor.set_actor_rotation(rot, True)
    if scale:
        actor.set_actor_scale3d(scale)
    return actor

def spawn_block(target='', loc=None, rot=None, scale=None):
    return spawn_helper('放置方块', target, loc, rot, scale)

def spawn_item(target='', loc=None, rot=None, scale=None):
    return spawn_helper('放置物品', target, loc, rot, scale)

def spawn_mob(target='', loc=None, rot=None, scale=None, baby=None):
    if baby is not None and panel("生成器子面板.生物宝宝_可点击").get() != int(baby):
        panel("生成器子面板.生物宝宝_可点击").click()
    return spawn_helper('放置生物', target, loc, rot, scale)

def spawn_preset(target='', loc=None, rot=None, scale=None):
    return spawn_helper('预设素材', target, loc, rot, scale)

def attach(target='', loc=None, rot=None, scale=None):
    return spawn_helper('附加组件', target, loc, rot, scale)


def spawn_blocks(mesh=None, transforms=[unreal.Transform()], pivot=(0,0,0)):
    blueprint_path = '/Game/Mineprep/MC_Blueprint/Core/实例化方块.实例化方块_C'
    loaded_class = unreal.load_class(None, blueprint_path)
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(loaded_class, pivot)
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

