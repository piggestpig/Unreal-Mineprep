import unreal
import json
from dataclasses import dataclass, asdict

from mc_utils import prints

@dataclass
class MCpath:
    def __str__(self):
        return str(asdict(self))
    
    project: str = unreal.Paths.project_dir()
    game: str = unreal.Paths.project_content_dir()
    content: str = game
    plugin: str = unreal.Paths.project_plugins_dir()
    mineprep: str = game + 'Mineprep/'
    config: str = mineprep + 'Mineprep_config.txt'
    hotkey: str = '/Mineprep/Mineprep自定义快捷键.Mineprep自定义快捷键'
    installer: str = ''
    blocks: str = ''
    cache: str = project + 'cache/'
    mcprep_data: str = mineprep + 'mcprep_data.json'




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
        try:
            with open(MCpath.config, 'r', encoding='utf-8') as file:
                cls.config_dict = json.load(file)
        except FileNotFoundError:
            cls.config_dict = {}

    def save(cls):
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
    def __init__(self):
        prints(self.__class__.config_dict)


paths = MCpath()
paths.installer = config['Settings']['installer_dir']
paths.blocks= paths.installer + '/Blender扩展资源/mc_default/assets/minecraft/models/block'
