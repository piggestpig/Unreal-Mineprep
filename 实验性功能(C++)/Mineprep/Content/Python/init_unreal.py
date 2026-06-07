import unreal

# 如果有mineprep模块，备份原有的 C++ 蓝图库
if not hasattr(unreal, 'MineprepKernel'):
    if hasattr(unreal, 'mineprep'):
        unreal.MineprepKernel = unreal.mineprep
    else:
        unreal.MineprepKernel = None


@unreal.uclass()
class MineprepAPIHandle(unreal.Object):
    name = unreal.uproperty(str)
    target = unreal.uproperty(unreal.Object)

    def __init__(self, name='', target=None):
        super().__init__()
        self.name = name
        self.target = target

    def get(self, prop=None):
        cast = prop if isinstance(prop, type) else None
        type_str = cast.__name__ if cast else str(prop)
        value = MC.get_hotkey_object().call_method('GetValue', (self.target, type_str))
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
        trigger_name = name if name else self.name
        return MC.get_hotkey_object().call_method('Trigger', (self.target, str(trigger_name)))
    
    def click(self, index=-1):
        return MC.get_hotkey_object().call_method('Click', (self.target, int(index)))
    
    def set_string(self, value=''):
        return MC.get_hotkey_object().call_method('SetString', (self.target, str(value)))
    
    def set_value(self, value=0.0):
        return MC.get_hotkey_object().call_method('SetValue', (self.target, float(value)))
    
    def select(self, index=0):
        return MC.get_hotkey_object().call_method('Select', (self.target, int(index)))
    
    @staticmethod
    def help(name=''):
        helper = {}
        text = '前往https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API查看更多信息'
        if name in helper:
            text = helper[name]
        unreal.SystemLibrary.print_string(None, text)
        return text



# mineprep包装器
@unreal.uclass() 
class MC(unreal.Object):

    HotkeyObjCache = None
    CacheStr = ''

    ################################################################################

    @staticmethod   #检查unreal.mineprep有没有这个属性且不为空
    def check(prop):
        return hasattr(unreal.mineprep, prop) and getattr(unreal.mineprep, prop)
    
    @staticmethod  #检查对象是否是某个类，可以是unreal.C++类 或 蓝图类的路径字符串
    def cast(obj, cls):
        if isinstance(cls, str):
            loaded_class = unreal.load_class(None, cls)
            if loaded_class and isinstance(obj, loaded_class):
                return obj
        elif isinstance(obj, cls):
            return obj
        return None

    @unreal.ufunction(static=True, ret=unreal.Object, params=[bool])
    def get_hotkey_object(reload=False):
        if MC.HotkeyObjCache and MC.check('cache') and not reload:
            return MC.HotkeyObjCache

        blueprint_path = '/Mineprep/Mineprep自定义快捷键.Mineprep自定义快捷键_C'
        loaded_class = unreal.load_class(None, blueprint_path)
        
        if loaded_class:
            hotkey_object = unreal.new_object(loaded_class)
            MC.HotkeyObjCache = hotkey_object
            return hotkey_object

        return None

    ###########################################################################

    @staticmethod
    def panel(name=''):
        id, obj = MC.get_hotkey_object().call_method('Panel', (str(name),))
        return MineprepAPIHandle(name, obj)
    
    @staticmethod
    def toolbar(name=''):
        id, obj = MC.get_hotkey_object().call_method('Toolbar', (str(name),))
        return MineprepAPIHandle(name, obj)
    
    @staticmethod
    def config(name=''):
        id, obj = MC.get_hotkey_object().call_method('Config', (str(name),))
        return MineprepAPIHandle(name, obj)
    
    @staticmethod
    def hotkey(name=''):
        return MC.get_hotkey_object().call_method(str(name))

    @staticmethod
    def help(name=''):
        helper = {}
        text = '前往https://github.com/piggestpig/Unreal-Mineprep/wiki/Mineprep-Python-API查看更多信息'
        if name in helper:
            text = helper[name]
        unreal.SystemLibrary.print_string(None, text)
        return text
    
    #################################################################################

    @staticmethod
    def spawn_helper(button='', target='', loc=None, rot=None, scale=None):
        unreal.mineprep.panel(f'生成器子面板.{button}选项').set_string(target)
        unreal.mineprep.panel(f'生成器子面板.{button}_可右键').click(1)
        actors = list(unreal.VRScoutingInteractor.get_selected_actors())
        if not actors:
            unreal.SystemLibrary.print_string(None, f'{button}: {target} 失败')
            return None
        for actor in actors:
            if loc:
                actor.set_actor_location(loc, False, True)
            if rot:
                actor.set_actor_rotation(rot, True)
            if scale:
                actor.set_actor_scale3d(scale)
        return actors

    @staticmethod
    def spawn_block(target='', loc=None, rot=None, scale=None):
        return MC.spawn_helper('放置方块', target, loc, rot, scale)
    
    @staticmethod
    def spawn_item(target='', loc=None, rot=None, scale=None):
        return MC.spawn_helper('放置物品', target, loc, rot, scale)

    @staticmethod
    def spawn_mob(target='', loc=None, rot=None, scale=None, baby=None):
        print(unreal.mineprep.panel("生成器子面板.生物宝宝_可点击").get(),int(baby))
        if baby is not None and unreal.mineprep.panel("生成器子面板.生物宝宝_可点击").get() != int(baby):
            print('切换生物宝宝状态')
            unreal.mineprep.panel("生成器子面板.生物宝宝_可点击").click()
        return MC.spawn_helper('放置生物', target, loc, rot, scale)
    
    @staticmethod
    def spawn_preset(target='', loc=None, rot=None, scale=None):
        return MC.spawn_helper('预设素材', target, loc, rot, scale)
    
    @staticmethod
    def attach(target='', loc=None, rot=None, scale=None):
        return MC.spawn_helper('附加组件', target, loc, rot, scale)

    # 魔法方法：如果代理类里找不到，就去原 C++ 类里找
    def __getattr__(self, name):
        return getattr(unreal.MineprepKernel, name)


# 替换模块
unreal.mineprep = MC()
unreal.mineprep.cache = True
unreal.mineprep.actors = []