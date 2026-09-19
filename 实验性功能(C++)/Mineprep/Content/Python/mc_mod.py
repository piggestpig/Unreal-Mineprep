import unreal
import importlib
import sys
import random
import mcvars
from pathlib import Path
from mc_config import wclass
from mc_widget import Layout, copy
from mc_utils import uclass, startfile

PAUSE_BREAK = unreal.Key()
PAUSE_BREAK.import_text('Pause')

def _iter_mod_names():
    """扫描 mods/ 目录，产出模块名（如 mods.template）"""
    mods_dir = Path(__file__).with_name('mods')
    if not mods_dir.is_dir():
        return
    for entry in sorted(mods_dir.iterdir()):
        if entry.name.startswith('_'):
            continue
        if entry.is_file() and entry.suffix == '.py':
            yield f'mods.{entry.stem}'
        elif entry.is_dir() and (entry / '__init__.py').is_file():
            yield f'mods.{entry.name}'


def _mod_priority(mod):
    """mod_info.Priority，缺省或非法时为 0。越大越先加载。"""
    info = getattr(mod, 'mod_info', None) or {}
    try:
        return int(info.get('Priority', 0) or 0)
    except (TypeError, ValueError):
        return 0


def iter_mod_modules(*, loaded_only=False, reverse=False):
    """迭代 mod 模块。默认按 Priority 降序（越大越先）。reverse=True 为加载的相反顺序。
    loaded_only=True 时只返回已在 sys.modules 中的。"""
    modules = []
    for name in _iter_mod_names():
        if loaded_only and name not in sys.modules:
            continue
        try:
            modules.append((name, importlib.import_module(name)))
        except Exception as e:
            unreal.log_warning(f'导入 mod 失败: {name}: {e}')
    modules.sort(key=lambda item: (-_mod_priority(item[1]), item[0]), reverse=reverse)
    yield from modules


def register_mod(mod, *, force=False):
    """注册单个 mod；默认需 EnabledByDefault 为真，成功后设置 EnabledByDefault=True"""
    info = getattr(mod, 'mod_info', None)
    if info is None:
        mod.mod_info = info = {}
    if not force and not info.get('EnabledByDefault'):
        return False
    register = getattr(mod, 'register', None)
    if not callable(register):
        return False
    register()
    info['EnabledByDefault'] = True
    unreal.log(f'已注册 mod: {getattr(mod, "__name__", mod)}')
    return True


def unregister_mod(mod):
    """注销单个 mod：清理 RegisteredMods/菜单，再调用模组 unregister，并设置 EnabledByDefault=False"""
    name = getattr(mod, '__name__', str(mod))
    try:
        for path, cls in list(mcvars.RegisteredMods.items()):
            if path == name or path.startswith(name + '.'):
                cls.unregister()
        unregister = getattr(mod, 'unregister', None)
        if callable(unregister):
            unregister()
        info = getattr(mod, 'mod_info', None)
        if info is None:
            mod.mod_info = info = {}
        info['EnabledByDefault'] = False
        unreal.log(f'已注销 mod: {name}')
        return True
    except Exception as e:
        unreal.log_warning(f'注销 mod 失败: {name}: {e}')
        return False


def register_all():
    """扫描 mods/，按 Priority 降序注册 EnabledByDefault 的 mod（越大越先）"""
    for _name, mod in iter_mod_modules():
        register_mod(mod)
    mcvars.ModsInitialized = True


def unregister_all(*, loaded_only=True):
    """注销 mod；顺序与加载相反（Priority 小的先卸）。默认只处理已加载的模块"""
    for _name, mod in iter_mod_modules(loaded_only=loaded_only, reverse=True):
        unregister_mod(mod)
    mcvars.ModsInitialized = False


def reloadable_mods():
    """已加载且 mod_info.ReloadWithMineprep 为真的 mod 列表"""
    result = []
    for _name, mod in iter_mod_modules(loaded_only=True):
        info = getattr(mod, 'mod_info', None) or {}
        if info.get('ReloadWithMineprep'):
            result.append(mod)
    return result


class mods():
    @staticmethod
    def register(mod):
        """注册单个 mod"""
        register_mod(mod, force=True)

    @staticmethod
    def unregister(mod):
        """注销单个 mod"""
        unregister_mod(mod)

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
    _public_ = False
    _unique_ = False  # True → 固定一个 tab，id = 类名；False → 每次随机 id
    _label_ = None
    _root_ = 'Root'
    _template_ = None

    def __new__(cls, context=None):
        """初始化layout, 默认由蓝图调用Mod(widget)"""
        cls._template_ = cls._template_ or wclass.mod_panel
        instance = super().__new__(cls)
        public = cls._public_ or mcvars.DebugMode
        root = context.find_child_widget_by_name(cls._root_) if context else None
        instance.layout = Layout(root, public=public)
        mcvars.WidgetModMap[instance.layout.outer] = instance
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
        toolbar.add_menu_entry('mods', mod_entry)

    @classmethod
    def unregister(cls):
        """从 RegisteredMods 和工具栏菜单中移除本模组"""
        mod_path = f'{cls.__module__}.{cls.__name__}'
        mcvars.RegisteredMods.pop(mod_path, None)
        menus = unreal.ToolMenus.get()
        menus.remove_entry("LevelEditor.MainMenu.mineprep", "mods", mod_path)
