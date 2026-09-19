import unreal
import json
from dataclasses import dataclass, asdict

from mc_utils import prints, uclass


class _LazyUClass:
    def __init__(self, path):
        self.path = path
        self._value = None

    def __get__(self, obj, owner=None):
        if self._value is None:
            self._value = uclass(self.path)
        return self._value

@dataclass
class MCpath:
    """各种路径"""
    def __str__(self):
        return str(asdict(self))

    project: str = unreal.Paths.project_dir()
    game: str = unreal.Paths.project_content_dir()
    content: str = game
    plugin: str = unreal.Paths.project_plugins_dir()
    mineprep: str = game + 'Mineprep/'
    config: str = mineprep + 'Mineprep_config.txt'
    installer: str = ''
    blocks: str = ''
    blockstates: str = ''
    cache: str = project + 'cache/'
    mcprep_data: str = mineprep + 'mcprep_data.json'


class wclass:
    """各种控件类"""
    button = unreal.Button
    checkbox = unreal.CheckBox
    slider = unreal.SpinBox
    option = unreal.ComboBoxString
    textbox = unreal.EditableTextBox
    prop = unreal.SinglePropertyView
    MCbutton = _LazyUClass('/Game/Mineprep/插件贴图/小控件/可右键按钮.可右键按钮')
    MCtext = _LazyUClass('/Game/Mineprep/插件贴图/小控件/可双击文本.可双击文本')
    MCimage = _LazyUClass('/Game/Mineprep/插件贴图/小控件/可点击图片.可点击图片')
    MCsection = _LazyUClass('/Game/Mineprep/插件贴图/小控件/折叠框.折叠框')
    mod_panel = _LazyUClass('/Game/Mineprep/插件贴图/小控件/MOD自定义面板.MOD自定义面板')


class ConfigNode:
    """代理类：用于处理嵌套字典的读取和自动保存（保持不变）"""
    def __init__(self, data, save_callback):
        self._data = data
        self._save_callback = save_callback

    def __getitem__(self, key):
        value = self._data[key]
        if isinstance(value, dict):
            return ConfigNode(value, self._save_callback)
        return value

    def __setitem__(self, key, value):
        self._data[key] = value
        self._save_callback()  # 触发元类的 save 方法

    def __repr__(self):
        return repr(self._data)


class ConfigMeta(type):
    """元类：让类本身具备字典的 [] 读写能力"""
    
    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)
        cls.config_dict = {}
        cls.load()  # 类定义加载时，自动读取文件

    def load(cls):
        """从 Mineprep_config.txt 读取配置字典"""
        try:
            with open(MCpath.config, 'r', encoding='utf-8') as file:
                cls.config_dict = json.load(file)
        except FileNotFoundError:
            cls.config_dict = {}

    def save(cls):
        """将配置字典写回 Mineprep_config.txt"""
        with open(MCpath.config, 'w', encoding='utf-8') as file:
            json.dump(cls.config_dict, file, indent=4, ensure_ascii=False)

    def __getitem__(cls, key):
        value = cls.config_dict[key]
        if isinstance(value, dict):
            return ConfigNode(value, cls.save)
        return value

    def __setitem__(cls, key, value):
        cls.config_dict[key] = value
        cls.save()


class config(metaclass=ConfigMeta):
    """读取和保存Mineprep_config.txt的工具类"""
    def __init__(self):
        prints(self.__class__.config_dict)
        self.help()

    @classmethod
    def help(cls):
        """打印帮助信息"""
        help_text = """
        直接使用mineprep.config()会打印所有配置项
        - 读取配置：value = mineprep.config['Settings']['key']
        - 写入配置：mineprep.config['Settings']['key'] = value
        """.strip()
        prints(help_text)


paths = MCpath()
paths.installer = config['Settings']['installer_dir']
_mc_assets = paths.installer + '/Blender扩展资源/mc_default/assets/minecraft'
paths.blocks = _mc_assets + '/models/block'
paths.blockstates = _mc_assets + '/blockstates'
