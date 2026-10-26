try:
    import unreal
except ModuleNotFoundError:
    from mc_utils import Lazy as unreal
import importlib
import sys
import random
import re
import tomllib
import mcvars
from fnmatch import translate
from pathlib import Path
from mc_config import wclass
from mc_widget import Layout, copy
from mc_utils import uclass, startfile, warn
from mc_localization import bilingual

MODS_DIR = Path(__file__).with_name('mods')
MANIFEST_NAME = 'mod_manifest.toml'
DEFAULT_INFO = {
    'Description': '', 'Version': '-', 'CreatedBy': '',
    'EnabledByDefault': False, 'ReloadWithMineprep': False,
    'Priority': 0, 'Advanced': False,
}

PAUSE_BREAK = unreal.Key()
PAUSE_BREAK.import_text('Pause')


def read_manifest(path):
    """读取可选清单；不存在返回 None，存在但无效则报错。"""
    path = Path(path)
    if not path.exists():
        return None
    with path.open('rb') as stream:
        data = tomllib.load(stream)
    if type(data.get('schema_version')) is not int or data['schema_version'] != 2:
        raise ValueError(f'{path}: schema_version 必须是整数 2')
    for key in ('Name', 'Description'):
        if key not in data:
            continue
        value = data[key]
        valid = isinstance(value, str)
        if isinstance(value, list):
            valid = 1 <= len(value) <= 2 and all(isinstance(v, str) for v in value)
        elif isinstance(value, dict):
            valid = ('chinese' in value and value.keys() <= {'chinese', 'english'}
                     and all(isinstance(v, str) for v in value.values()))
        if not valid:
            raise ValueError(f'{path}: {key} 须为字符串、双语数组或 chinese/english 字典')
    for key, expected in (('Version', str), ('CreatedBy', str), ('Priority', int),
                          ('EnabledByDefault', bool), ('ReloadWithMineprep', bool), ('Advanced', bool)):
        if key in data and type(data[key]) is not expected:
            raise ValueError(f'{path}: {key} 须为 {expected.__name__}')
    build = data.get('build', {})
    if not isinstance(build, dict) or build.keys() - {'paths', 'paths_exclude_pattern'}:
        raise ValueError(f'{path}: build 只支持 paths 或 paths_exclude_pattern')
    if 'paths' in build and 'paths_exclude_pattern' in build:
        raise ValueError(f'{path}: paths 和 paths_exclude_pattern 不能同时声明')
    for key, value in build.items():
        if not isinstance(value, list) or not all(isinstance(p, str) and p for p in value):
            raise ValueError(f'{path}: build.{key} 须为非空字符串组成的数组')
    return data


def manifest_info(data, name):
    """将清单转换为 mod_info；保留额外元数据，不混入构建设置。"""
    info = {'Name': name, **DEFAULT_INFO}
    info.update((key, value) for key, value in data.items() if key not in ('schema_version', 'build'))
    for key in ('Name', 'Description'):
        value = info[key]
        if isinstance(value, (list, dict)):
            info[key] = bilingual(*value) if isinstance(value, list) else bilingual(**value)
    return info


# 以下路径匹配算法摘自 Blender scripts/addons_core/bl_pkg/cli/blender_ext.py。
# SPDX-FileCopyrightText: 2023 Blender Foundation
# SPDX-License-Identifier: GPL-2.0-or-later
class PathPatternMatch:
    """Blender 风格匹配；! 例外优先，目录剪枝由调用方负责。"""

    def __init__(self, patterns):
        self.rules = []
        for pattern in patterns:
            negate = pattern.startswith('!')
            pattern = pattern.lstrip('!') if negate else pattern
            if pattern:
                self.rules.append((negate, re.compile(self._regex(pattern), re.MULTILINE)))

    def test_path(self, path):
        """相对路径使用 /；目录以 / 结尾。True 表示应排除。"""
        path_test = path.rstrip('/').replace('/', '\n')
        if path.endswith('/'):
            path_test += '/'
        result = False
        for negate, regex in self.rules:
            if regex.match(path_test):
                if negate:
                    return False
                result = True
        return result

    @staticmethod
    def _regex(pattern):
        if pattern.startswith('\\!'):
            pattern = pattern[1:]
        while '//' in pattern:
            pattern = pattern.replace('//', '/')
        if pattern.strip('/') == '**':
            return '(?s:.*)/\\Z' if pattern.endswith('/') else '(?s:.*)'
        while pattern.endswith(('/**/', '/**')):
            pattern = pattern[:-3] if pattern.endswith('/**/') else pattern[:-2]
        while pattern.startswith(('/**/', '**/')):
            pattern = pattern[4:] if pattern.startswith('/**/') else pattern[3:]
        while '/**/**/' in pattern:
            pattern = pattern.replace('/**/**/', '/**/')

        any_prefix = not pattern.startswith('/')
        only_directory = pattern.endswith('/')
        parts = pattern.strip('/').split('/')
        double_stars = []
        anchor = '\\z' if sys.version_info >= (3, 14) else '\\Z'
        for i, part in enumerate(parts):
            if part == '**':
                double_stars.append(i)
                continue
            regex = translate(part).removesuffix(anchor)
            if regex.startswith('(?s:'):
                regex = '(?:' + regex[4:]
            parts[i] = regex
        for i in reversed(double_stars):
            before, _, after = parts[i-1:i+2]
            del parts[i-1:i+1]
            parts[i-1] = before + '(?:\n|\n(?s:.*)\n)?' + after

        regex = '\\n'.join(parts)
        regex = ('(?s:.*)^' if any_prefix else '\\A') + regex
        return regex + ('[\\n/]' if only_directory else '/?\\Z')


def _iter_mod_names():
    """扫描 mods/ 目录，产出模块名（如 mods.template）"""
    mods_dir = MODS_DIR
    if not mods_dir.is_dir():
        return
    for entry in sorted(mods_dir.iterdir()):
        if entry.name.startswith('_'):
            continue
        if entry.is_file() and entry.suffix == '.py':
            yield f'mods.{entry.stem}'
        elif entry.is_dir() and (entry / '__init__.py').is_file():
            yield f'mods.{entry.name}'


def _mod_priority(info):
    """mod_info.Priority，缺省或非法时为 0。越大越先加载。"""
    try:
        return int(info.get('Priority', 0) or 0)
    except (TypeError, ValueError):
        return 0


def _module_info(mod):
    info = getattr(mod, 'mod_info', None)
    if not isinstance(info, dict):
        raise ValueError(f'{mod.__name__} 必须声明字典 mod_info')
    return info


def _sync_mod_info(mod):
    info = _module_info(mod)
    source = Path(mod.__file__)
    data = read_manifest(source.with_name(MANIFEST_NAME)) if source.name == '__init__.py' else None
    if data is not None:
        effective = manifest_info(data, mod.__name__.removeprefix('mods.'))
        changes = [f'{key}: {info[key]!s} → {value!s}' for key, value in effective.items()
                   if key in info and (str(info[key]) != str(value) if key in ('Name', 'Description')
                                       else info[key] != value)]
        if changes:
            import mineprep
            mineprep.debug(f'{mod.__name__}: 清单与 mod_info 不一致，使用清单中的值',
                           *changes, autolog=True, warning=True)
        info.update(effective)
    return info


def iter_mod_infos(*, loaded_only=False, reverse=False):
    """按优先级返回 (模块名, 信息)；有清单的模组不因扫描而导入。"""
    entries = []
    for name in _iter_mod_names():
        if loaded_only and name not in sys.modules:
            continue
        try:
            data = read_manifest(MODS_DIR / name.removeprefix('mods.') / MANIFEST_NAME)
            info = (manifest_info(data, name.removeprefix('mods.')) if data is not None
                    else _module_info(importlib.import_module(name)))
            entries.append((name, info))
        except Exception as e:
            unreal.log_warning(f'读取模组信息失败: {name}: {e}')
    entries.sort(key=lambda item: (-_mod_priority(item[1]), item[0]), reverse=reverse)
    yield from entries


def iter_mod_modules(*, loaded_only=False, reverse=False):
    """显式获取模块对象；界面与启动扫描应使用 iter_mod_infos。"""
    for name, _info in iter_mod_infos(loaded_only=loaded_only, reverse=reverse):
        try:
            mod = importlib.import_module(name)
            _module_info(mod)
            yield name, mod
        except Exception as e:
            unreal.log_warning(f'导入模组失败: {name}: {e}')


def register_mod(mod):
    """明确启用模块对象或完整模块名，不改变默认启用声明。"""
    name = mod if isinstance(mod, str) else mod.__name__
    if name in mcvars.EnabledMods:
        return True
    try:
        mod = importlib.import_module(name) if isinstance(mod, str) else mod
        _sync_mod_info(mod)
        register = getattr(mod, 'register', None)
        if not callable(register):
            raise ValueError('模组没有 register()')
        register()
        mcvars.EnabledMods.add(name)
        unreal.log(f'已注册 mod: {name}')
        return True
    except Exception as e:
        import traceback
        unreal.log_error(f'注册 mod 失败 [{name}]: {e}\n{traceback.format_exc()}')
        return False


def unregister_mod(mod):
    """注销已启用模组，不因注销而导入程序，不改变默认声明。"""
    name = mod if isinstance(mod, str) else mod.__name__
    if name not in mcvars.EnabledMods:
        return True
    try:
        mod = sys.modules[name] if isinstance(mod, str) else mod
        for path, cls in list(mcvars.RegisteredMods.items()):
            if path == name or path.startswith(name + '.'):
                cls.unregister()
        unregister = getattr(mod, 'unregister', None)
        if callable(unregister):
            unregister()
        mcvars.EnabledMods.remove(name)
        unreal.log(f'已注销 mod: {name}')
        return True
    except Exception as e:
        unreal.log_warning(f'注销 mod 失败: {name}: {e}')
        return False


def register_all():
    """扫描 mods/，按 Priority 降序注册 EnabledByDefault 的 mod（越大越先）"""
    for name, info in iter_mod_infos():
        if info.get('EnabledByDefault'):
            register_mod(name)
    mcvars.ModsInitialized = True


def unregister_all():
    """注销 mod；顺序与加载相反（Priority 小的先卸）。默认只处理已加载的模块"""
    for name, _info in iter_mod_infos(loaded_only=True, reverse=True):
        unregister_mod(name)
    mcvars.ModsInitialized = False


def reloadable_mods():
    """已加载且 mod_info.ReloadWithMineprep 为真的 mod 列表"""
    result = []
    for name, info in iter_mod_infos(loaded_only=True):
        if info.get('ReloadWithMineprep'):
            result.append(sys.modules[name])
    return result


class mods():
    @staticmethod
    def register(mod):
        """注册单个 mod"""
        return register_mod(mod)

    @staticmethod
    def unregister(mod):
        """注销单个 mod"""
        return unregister_mod(mod)

    @staticmethod
    def register_all():
        """扫描 mods/ 目录，按 Priority 降序注册 EnabledByDefault 的 mod"""
        register_all()

    @staticmethod
    def unregister_all():
        """按加载的相反顺序注销已加载的 mod"""
        unregister_all()


class Mod():
    """模组基类，继承 mineprep.Mod 可创建自定义UI面板，self.layout默认是scrollbox"""
    layout: Layout = None
    context = None
    tab_id = None
    _public_ = False
    _unique_ = False  # True → 固定一个 tab，id = 类名；False → 每次随机 id
    _label_ = None
    _root_ = 'Root'
    _menu_ = 'mods'
    _template_ = None

    def __new__(cls, context=None):
        """初始化layout, 默认由蓝图调用Mod(widget)"""
        cls._template_ = cls._template_ or wclass.mod_panel
        instance = super().__new__(cls)
        public = cls._public_ or mcvars.DebugMode
        root = context.find_child_widget_by_name(cls._root_) if context else None
        instance.layout = Layout(root, public=public)
        widget = instance.layout.outer
        mcvars.WidgetModMap[widget] = instance

        # 尝试保存自身的tab_id
        bp, has_bp = unreal.BlueprintEditorLibrary.get_blueprint_for_class(widget.get_class())
        if has_bp:
            subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
            instance.tab_id = str(subsystem.get_tab_id_from_blueprint(bp))
        else:
            unreal.log_warning(f'无法获取{cls._label_ or cls.__name__}的 tab_id')
        return instance

    def __init__(self, context=None):
        """保存 context 并调用 draw 构建界面"""
        self.context = context or self.layout.outer
        self.draw(self.context)

    def draw(self, context=None):
        """重载此方法以创建自定义UI"""
        pass

    def redraw(self):
        """清空面板并重绘UI。不应被重载。绝不能在draw()中调用此方法，否则会陷入死循环"""
        if self.layout:
            self.layout.clear_children()
        self.draw(self.context)

    def close(self):
        if self.tab_id:
            unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem).unregister_tab_by_id(self.tab_id)

    def destruct(self):
        """由蓝图模板传递的析构函数，关闭面板时调用"""
        pass

    def on_key_down(self, key: unreal.Key):
        """由蓝图模板传递的按键事件，按下键盘时调用。默认示例：按PauseBreak打开模组文件夹"""
        if unreal.InputLibrary.equal_equal_key_key(key, PAUSE_BREAK):
            path = getattr(sys.modules.get(type(self).__module__), '__file__', None)
            if path:
                startfile(str(Path(path).resolve().parent))

    def on_key_up(self, key: unreal.Key):
        """由蓝图模板传递的按键事件，松开键盘时调用"""
        pass

    def on_mouse_wheel(self, delta: float):
        """由蓝图模板传递的鼠标滚轮事件，滚动时调用"""
        pass


    ######################################################################


    @classmethod
    def bp_script(cls):
        mod_path = f'{cls.__module__}.{cls.__name__}'
        return f"""
mod_class = mcvars.RegisteredMods.get('{mod_path}')
if mod_class:
    mod_class(context)
else:
    mineprep.warn(mineprep.bilingual('[未注册模组] {mod_path}', '[Unregistered Mod] {mod_path}'))
"""

    @classmethod
    def _tab_id(cls):
        """立即打开面板用的 tab id。_unique_ 时为类名，否则每次随机。"""
        return cls.__name__ if cls._unique_ else str(random.randint(0, 999999999))

    @classmethod
    def toolbar_script(cls):
        id = repr(cls.__name__) if cls._unique_ else 'str(random.randint(0, 999999999))'
        return f"""
import unreal
import random
widget_bp = unreal.load_object(None, f"/Game/mc/mods/{cls.__name__}")
subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
subsystem.spawn_and_register_tab_with_id(widget_bp, {id})
"""

    @classmethod
    def register(cls, open=False):
        """注册mod并创建/更新控件蓝图；在模组初始化后注册时，open=True立即打开面板"""
        mod_path = f'{cls.__module__}.{cls.__name__}'
        mcvars.RegisteredMods[mod_path] = cls
        open = open and (mcvars.ModsInitialized or int(open) >= 2)

        widget_path = f"/Game/mc/mods/{cls.__name__}"
        if not unreal.EditorAssetLibrary.does_asset_exist(widget_path):
            copy(cls._template_ or wclass.mod_panel, widget_path)
            unreal.log(f"已创建自定义控件蓝图: {widget_path}")
        else:
            unreal.log(f"自定义控件蓝图已存在, 更新 {widget_path}")

        widget_bp = unreal.load_object(None, widget_path)
        default_widget = unreal.get_default_object(uclass(widget_path))
        default_widget.set_editor_property("Script", cls.bp_script())
        default_widget.set_editor_property("TabDisplayName", cls._label_ or cls.__name__)

        if open:
            subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
            subsystem.spawn_and_register_tab_with_id(widget_bp, cls._tab_id())

        # 在顶部工具栏添加菜单项
        mod_entry = unreal.ToolMenuEntry(
            name= f'{cls.__module__}.{cls.__name__}',
            type=unreal.MultiBlockType.MENU_ENTRY,
        )
        mod_entry.set_label(cls._label_ or cls.__name__)
        mod_entry.set_string_command(type=unreal.ToolMenuStringCommandType.PYTHON,
                                    custom_type='',
                                    string=cls.toolbar_script()
        )
        toolbar = unreal.ToolMenus.get().find_menu("LevelEditor.MainMenu.mineprep")
        toolbar.add_menu_entry(f'{cls._menu_}', mod_entry)


    @classmethod
    def unregister(cls):
        """关闭本模组面板，并从 RegisteredMods / 工具栏移除"""
        for widget, instance in list(mcvars.WidgetModMap.items()):
            if not isinstance(instance, cls):
                continue
            instance.close()
            if mcvars.WidgetModMap.get(widget) is instance:
                mcvars.WidgetModMap.pop(widget, None)
                try:
                    warn(bilingual(f'未能关闭所有的{cls.__name__}模组面板：{instance}',
                        f'Failed to close all {cls.__name__} mod panels: {instance}'))
                    instance.layout.clear_children()
                except:
                    pass

        mod_path = f'{cls.__module__}.{cls.__name__}'
        mcvars.RegisteredMods.pop(mod_path, None)
        menus = unreal.ToolMenus.get()
        menus.remove_entry("LevelEditor.MainMenu.mineprep", cls._menu_, mod_path)
