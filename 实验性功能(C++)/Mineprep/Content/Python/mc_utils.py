import unreal
import os
import re
import math
import subprocess
import sys
import traceback
import builtins
import mcvars
from dataclasses import dataclass, asdict
from pprint import pformat
from functools import lru_cache, wraps
from typing import Iterable
import operator

HotkeyObjCache = None

libs = {
    'np': 'numpy',
    'numpy': 'numpy',
    'cv2': 'cv2',
    'plt': 'matplotlib.pyplot',
}

def lazy_import(func):
    """函数装饰器，自动扫描函数内部引用的全局名称，并导入libs中匹配的库"""
    referenced_names = func.__code__.co_names
    # 筛选出匹配我们映射表的库
    detected_dependencies = {name: libs[name] for name in referenced_names if name in libs}

    @wraps(func)
    def wrapper(*args, **kwargs):
        # 3. 在函数被实际调用时，才执行以下逻辑（延迟加载）
        for alias, real_lib_name in detected_dependencies.items():
            # 如果这个库还没有被导入过
            if alias not in func.__globals__:
                # 动态导入库，fromlist=['*'] 是为了兼容 matplotlib.pyplot 这种带点的子模块
                module = __import__(real_lib_name, fromlist=['*'] if '.' in real_lib_name else [])
                # 把导入的模块以别名（如 np）的形式，直接注入到该函数的全局命名空间中！
                func.__globals__[alias] = module
        return func(*args, **kwargs)
    return wrapper


def iscollection(obj):
    """判断对象是否为集合类型（list, tuple, set, dict等），排除字符串"""
    return isinstance(obj, Iterable) and not isinstance(obj, (str, bytes))


class List(list):
    """改进版list：
    1. 支持 List(1, 2, 3) 变长参数构造，也支持 List([1, 2, 3]) 迭代器构造
    2. 调用不存在的属性或函数时, 尝试转发到内部元素，返回结果数组
    3. 下标模仿 numpy：a[i, j]、切片、a[[1, 2]]、a[[True, False]]、a[a > 2]（与标量比较得 mask）；两个 List 比较仍是 True/False
    4. float 下标当 0~1 比例（UV）：floor((u % 1) * n)；[:0.5] 前半，[0.5:] 后半。
       int -1 仍是末项，-1.0 会 wrap 到 0
    5. a(fn, *args) 对每个元素调用 fn(item, *args)，嵌套 List 再进一层
    """

    def __new__(cls, *args):
        return super().__new__(cls)

    def __init__(self, *args):
        if len(args) == 1:
            super().__init__(args[0] if iscollection(args[0]) else [args[0]])
        else:
            super().__init__(args)

    @staticmethod
    def _key(tail):
        return tail[0] if len(tail) == 1 else tail

    @staticmethod
    def _take(index):
        if not isinstance(index, list):
            return None
        if not index:
            return []
        if isinstance(index[0], bool):
            return [i for i, m in enumerate(index) if m]
        if isinstance(index[0], int):
            return list(index)
        return None

    @staticmethod
    def _uv_index(u, n):
        if n <= 0:
            return 0
        return int(math.floor((u % 1.0) * n))

    def _resolve(self, index):
        n = len(self)
        if isinstance(index, float):
            return self._uv_index(index, n)
        if isinstance(index, slice):
            start, stop, step = index.start, index.stop, index.step
            if isinstance(step, float):
                raise TypeError('slice step must be an integer')
            if isinstance(start, float):
                start = self._uv_index(start, n)
            if isinstance(stop, float):
                stop = self._uv_index(stop, n)
            if start is index.start and stop is index.stop:
                return index
            return slice(start, stop, step)
        if isinstance(index, tuple) and index:
            head = self._resolve(index[0])
            if head is index[0]:
                return index
            return (head,) + index[1:]
        return index

    def __getitem__(self, index):
        index = self._resolve(index)
        idxs = self._take(index)
        if idxs is not None:
            return type(self)(self[i] for i in idxs)
        if isinstance(index, tuple):
            if not index:
                return self
            head, tail = index[0], index[1:]
            rows = self._take(head)
            if rows is not None:
                taken = type(self)(self[i] for i in rows)
                return taken if not tail else type(self)(
                    row[self._key(tail)] for row in taken)
            item = super().__getitem__(head)
            if not tail:
                return type(self)(item) if isinstance(head, slice) else item
            key = self._key(tail)
            if isinstance(head, slice):
                return type(self)(row[key] for row in item)
            return item[key]
        res = super().__getitem__(index)
        return type(self)(res) if isinstance(index, slice) else res

    def __setitem__(self, index, value):
        index = self._resolve(index)
        idxs = self._take(index)
        if idxs is not None:
            if not iscollection(value):
                for i in idxs:
                    self[i] = value
            else:
                for i, v in zip(idxs, value):
                    self[i] = v
            return
        if isinstance(index, tuple):
            if not index:
                raise TypeError('empty index')
            head, tail = index[0], index[1:]
            if not tail:
                self[head] = value
                return
            key = self._key(tail)
            scalar = not iscollection(value)
            rows = self._take(head)
            if rows is not None:
                for n, i in enumerate(rows):
                    self[i][key] = value if scalar else value[n]
                return
            if isinstance(head, slice):
                for i, row in enumerate(super().__getitem__(head)):
                    row[key] = value if scalar else value[i]
                return
            super().__getitem__(head)[key] = value
            return
        if isinstance(index, slice) and not iscollection(value):
            start, stop, step = index.indices(len(self))
            super().__setitem__(index, [value] * len(range(start, stop, step)))
            return
        super().__setitem__(index, value)

    _LIST_CMP = {
        operator.eq: list.__eq__,
        operator.ne: list.__ne__,
        operator.gt: list.__gt__,
        operator.ge: list.__ge__,
        operator.lt: list.__lt__,
        operator.le: list.__le__,
    }

    def _cmp(self, other, op):
        if iscollection(other):
            return self._LIST_CMP[op](self, other)
        return List(self._cmp_elem(a, other, op) for a in self)


    @staticmethod
    def _cmp_elem(a, b, op):
        if isinstance(a, List):
            return a._cmp(b, op)
        return op(a, b)

    def __gt__(self, other):
        return self._cmp(other, operator.gt)

    def __ge__(self, other):
        return self._cmp(other, operator.ge)

    def __lt__(self, other):
        return self._cmp(other, operator.lt)

    def __le__(self, other):
        return self._cmp(other, operator.le)

    def __eq__(self, other):
        return self._cmp(other, operator.eq)

    def __ne__(self, other):
        return self._cmp(other, operator.ne)

    def __getattr__(self, name):
        if not self:
            return self
        cls = type(self)
        try:
            first_attr = getattr(self[0], name)
        except AttributeError as e:
            raise AttributeError(f"'{cls.__name__}' 及其元素均无属性 '{name}'") from e
        if callable(first_attr):
            return lambda *a, **k: cls(getattr(item, name)(*a, **k) for item in self)
        return cls(getattr(item, name) for item in self)

    def __call__(self, fn, *args, **kwargs):
        return List(
            item(fn, *args, **kwargs) if isinstance(item, List)
            else fn(item, *args, **kwargs)
            for item in self
        )


class SafeList(List):
    """安全版List：越界不报错（默认返回None），属性不存在不报错"""

    # SafeList 无需重写 __new__ 和 __init__，它们会完美继承父类 List 的新构造函数

    def __getitem__(self, index):
        try:
            return super().__getitem__(index)
        except IndexError:
            return None

    def __getattr__(self, name):
        if not self:
            return self

        cls = type(self)
        first_has_attr = next((item for item in self if hasattr(item, name)), None)

        if first_has_attr is not None and callable(getattr(first_has_attr, name)):
            def safe_method_wrapper(*args, **kwargs):
                res = []
                for item in self:
                    if hasattr(item, name):
                        val = getattr(item, name)
                        if callable(val):
                            res.append(val(*args, **kwargs))
                            continue
                    res.append(None)
                return cls(res)
            return safe_method_wrapper

        return cls(getattr(item, name) if hasattr(item, name) else None for item in self)


def WrapList(*args):
    """按 SafeBroadcast 构造 List 或 SafeList"""
    return (SafeList if mcvars.SafeBroadcast else List)(*args)


def undo(arg: str=None):
    """函数装饰器，添加编辑器撤销功能，相当于with unreal.ScopedEditorTransaction()"""
    def decorator(func):
        if isinstance(arg, str):
            tx_name = arg
        else:
            tx_name = func.__name__
            
        @wraps(func)
        def wrapper(*args, **kwargs):
            with unreal.ScopedEditorTransaction(tx_name):
                return func(*args, **kwargs)
        return wrapper

    # 如果不带括号使用 @undo，此时arg就是被装饰的函数本身
    if callable(arg):
        return decorator(arg)

    return decorator


def _adopt_module(dst, src):
    """把 src 的命名空间拷进 dst，保持 dst 对象身份。

    控制台里的 `mineprep` 仍是旧模块对象；只换 sys.modules 条目的话，
    `mineprep.reload()` 之后 `mineprep.screenshot` 仍会找不到。
    """
    dst_dict = dst.__dict__
    src_dict = src.__dict__
    keep = ('__name__', '__doc__', '__package__', '__loader__', '__spec__')
    for key in list(dst_dict):
        if key not in src_dict and key not in keep:
            del dst_dict[key]
    dst_dict.update(src_dict)


def _rebind_mineprep(from_mod, to_mod) -> int:
    """把各命名空间里的 mineprep 从 from_mod 改到 to_mod（含控制台栈帧）。"""
    rebound = 0
    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        try:
            d = getattr(mod, '__dict__', None)
            if d is not None and d.get('mineprep') is from_mod:
                d['mineprep'] = to_mod
                rebound += 1
        except Exception:
            pass
    try:
        import inspect
        for info in inspect.stack():
            g = info.frame.f_globals
            if g.get('mineprep') is from_mod:
                g['mineprep'] = to_mod
                rebound += 1
    except Exception:
        pass
    return rebound


def reload(*args):
    """重新加载 mineprep 及其子模块；传入特定模块时，只重新加载这些模块。

    全量重载流程：
      1. 注销 ReloadWithMineprep 的 mod
      2. 从 sys.modules 卸载 mineprep / mc_*（保留 mcvars）/ 相关 mods
      3. 全新 import mineprep（避免 importlib.reload 造成 Layout/PropertyGroup 多份类对象）
      4. 把新模块的命名空间写回旧模块对象（控制台无需 mineprep = mineprep.reload()）
      5. 再 import 并 register 先前启用的 mod

    返回同一个 mineprep 模块对象（原地更新）。控制台直接 `mineprep.reload()` 即可。
    """
    import importlib
    import sys

    if args:
        for mod in args:
            importlib.reload(mod)
            unreal.log(f'重新加载 {mod.__name__}')
        return mod if len(args) == 1 else args

    import mc_mod
    import mcvars
    mcvars.ModsInitialized = False
    reloadable = list(mc_mod.reloadable_mods())
    # 模组对象即将失效，先记下名字与启用状态
    enabled_names = {
        mod.__name__
        for mod in reloadable
        if (getattr(mod, 'mod_info', None) or {}).get('EnabledByDefault')
    }
    reloadable_names = [mod.__name__ for mod in reloadable]

    for mod in reversed(reloadable):
        mc_mod.unregister_mod(mod)

    import mineprep as old_mineprep
    import mc_widget
    widgets_copy = mc_widget.WidgetsCache

    drop = set()
    for name in list(sys.modules):
        if name == 'mineprep':
            drop.add(name)
        elif name.startswith('mc_') and name != 'mcvars':
            # mcvars 保留全局状态；其余 mc_* 全部卸掉以便全新绑定
            drop.add(name)
        elif name == 'mods':
            drop.add(name)
        else:
            for mod_name in reloadable_names:
                if name == mod_name or name.startswith(mod_name + '.'):
                    drop.add(name)
                    break

    for name in sorted(drop, key=lambda n: n.count('.'), reverse=True):
        sys.modules.pop(name, None)
        unreal.log(f'已卸载 {name}')

    mcvars.Props.clear()

    import mineprep as new_mineprep
    unreal.log('重新加载 mineprep')

    import mc_widget
    mc_widget.WidgetsCache = widgets_copy

    # 原地更新：控制台持有的仍是 old_mineprep 这个对象
    _adopt_module(old_mineprep, new_mineprep)
    sys.modules['mineprep'] = old_mineprep
    rebound = _rebind_mineprep(new_mineprep, old_mineprep)
    if rebound:
        unreal.log(f'已刷新 {rebound} 处 mineprep 引用')

    import mc_mod
    for mod_name in reloadable_names:
        try:
            mod = importlib.import_module(mod_name)
            if mod_name in enabled_names:
                info = getattr(mod, 'mod_info', None)
                if info is None:
                    mod.mod_info = info = {}
                info['EnabledByDefault'] = True
            mc_mod.register_mod(mod)
            unreal.log(f'重新加载 {mod_name}')
        except Exception as e:
            warn(f'重新加载 {mod_name} 时出错: {e}')

    mcvars.ModsInitialized = True
    return old_mineprep


def enum(input: type | unreal.EnumBase):
    """用下标获取UE枚举类型的对应值，如enum(var)[0]"""
    if isinstance(input, type):
        return list(input)
    else:
        return list(type(input))


def world() -> unreal.World:
    """获取当前编辑器或游戏世界"""
    subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    return subsystem.get_editor_world() or subsystem.get_game_world()


def prints(*args, duration=2.0, color=unreal.LinearColor(0, 0.66, 1, 1)) -> str:
    """在屏幕上打印多行文本"""
    text = '\n'.join(str(arg) if isinstance(arg, (str, unreal.Text)) else pformat(arg, sort_dicts=False) for arg in args)
    unreal.SystemLibrary.print_string(None, text, text_color=color, duration=duration)
    return text


def _format_warn_arg(arg) -> str:
    """格式化 warn 参数；Exception 展开为完整 traceback"""
    if isinstance(arg, BaseException):
        return "".join(traceback.format_exception(type(arg), arg, arg.__traceback__)).rstrip()
    if isinstance(arg, (str, unreal.Text)):
        return str(arg)
    return pformat(arg, sort_dicts=False)


def warn(*warnings, duration=5.0, color=unreal.LinearColor(1, 1, 0, 1)):
    """在屏幕上打印多行警告文本，传入Exception将自动进行traceback"""
    text = "\n".join(_format_warn_arg(arg) for arg in warnings)
    unreal.SystemLibrary.print_string(None, text, text_color=color, duration=duration, print_to_log=False)
    unreal.log_warning(text)
    return warnings


def throw(*errors, duration=5.0, color=unreal.LinearColor(1, 0, 0, 1)):
    """在屏幕上打印多行错误文本并抛出异常"""
    text = "\n".join(_format_warn_arg(arg) for arg in errors)
    unreal.SystemLibrary.print_string(None, text, text_color=color, duration=duration, print_to_log=False)
    raise RuntimeError(errors)


def panic(title, message=''):
    """弹出提示框，由用户决定是否继续运行"""
    if not message:
        message = title
        title = '警告'
    message = str(message) + ' \n\n是否继续运行？'
    title = str(title)
    status = unreal.EditorDialog.show_message(title, message, unreal.AppMsgType.YES_NO)
    if status == unreal.AppReturnType.NO:
        throw(f'{title}: {message} NO.\n')


def dialog(title, message=''):
    """弹出对话框"""
    if not message:
        message = title
        title = '提示'
    message = str(message)
    title = str(title)
    result = unreal.EditorDialog.show_message(title, message, unreal.AppMsgType.YES_NO,
                                     message_category=unreal.AppMsgCategory.INFO)
    return result == unreal.AppReturnType.YES


def debug(*args):
    """启用DebugMode时在日志中打印信息"""
    if mcvars.DebugMode:
        text = '\n'.join(str(arg) if isinstance(arg, (str, unreal.Text)) else pformat(arg, sort_dicts=False) for arg in args)
        unreal.log(text)


def screenshot(size: tuple[int, int]=None, path: str='', pos: unreal.Vector=None, lookat: unreal.Vector=None):
    """在编辑器中截取高分辨率截图，size默认是视口分辨率，
    path默认在项目/Saved/Screenshots下，会自动生成后缀名；指定path则覆写图片
    使用pos和lookat调整摄像机坐标与朝向
    """
    size = 0 if size is None else size
    size = (size, size) if isinstance(size, (int, float)) else size

    if pos or lookat:
        subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        current_pos, current_rot = subsystem.get_level_viewport_camera_info()
        pos = pos or current_pos
        rot = unreal.MathLibrary.find_look_at_rotation(pos, lookat) if lookat else current_rot
        subsystem.set_level_viewport_camera_info(pos, rot)

    unreal.AutomationLibrary.take_high_res_screenshot(size[0], size[1], path)


def uasset(input):
    """从蓝图路径或对象中获取资产"""
    if isinstance(input, str):
        return unreal.load_asset(input)
    elif isinstance(input, unreal.Class):
        return unreal.BlueprintEditorLibrary.get_blueprint_for_class(input)[0]
    elif isinstance(input, unreal.Object):
        return input
    return None


def uclass(input):
    """从蓝图路径、引擎内置类或对象中获取自身类"""
    if isinstance(input, (type, unreal.Class)):
        return input
    elif isinstance(input, str):
        asset = unreal.load_asset(input)
        if isinstance(asset, unreal.Blueprint):
            return unreal.EditorAssetLibrary.load_blueprint_class(input)
        return type(asset)
    elif isinstance(input, unreal.Blueprint):
        return unreal.EditorAssetLibrary.load_blueprint_class(input.get_path_name())
    elif isinstance(input, unreal.Object):
        return type(input)
    return None


def bpclass(input):
    """从蓝图路径、引擎内置类或对象中获取资产类"""
    if isinstance(input, (type, unreal.Class)):
        return input
    elif isinstance(input, str):
        asset = unreal.load_asset(input)
        if isinstance(asset, unreal.Blueprint):
            return unreal.EditorAssetLibrary.load_blueprint_class(input)
        return type(asset)
    elif isinstance(input, unreal.Object):
        return input.get_class()
    return None


def cast(input, target):
    """判断输入对象是否为指定类（支持蓝图类和对象类），或输入类是否为子类"""
    target_cls = uclass(target)
    if target_cls is None:
        return None

    input_cls = input.get_class() if isinstance(input, unreal.Object) else uclass(input)
    if input_cls is None:
        return None

    if isinstance(input_cls, unreal.Class) and isinstance(target_cls, unreal.Class):
        return input if unreal.MathLibrary.class_is_child_of(input_cls, target_cls) else None

    if isinstance(target_cls, type):
        if isinstance(input, unreal.Object):
            return input if isinstance(input, target_cls) else None
        if isinstance(input_cls, type):
            return input if issubclass(input_cls, target_cls) else None

    return None


def resolve_soft(path: str | unreal.SoftObjectPath):
    """解析软引用路径，返回对象或None"""
    if isinstance(path, unreal.SoftObjectPath):
        path = path.export_text() if path else ''
    if not path:
        return None
    return unreal.find_object(None, path) or unreal.load_object(None, path)


def get_hotkey_object(reload=False):
    """获取自定义快捷键对象"""
    global HotkeyObjCache
    if HotkeyObjCache and not reload:
        return HotkeyObjCache

    loaded_class = uclass('/Mineprep/Mineprep自定义快捷键.Mineprep自定义快捷键')
    if loaded_class:
        hotkey_object = unreal.new_object(loaded_class)
        HotkeyObjCache = hotkey_object
        return hotkey_object

    return None


def construct(cls, outer=None):
    """构造对象实例（调用蓝图的Construct方法，垃圾回收更安全）"""
    return get_hotkey_object().call_method('Construct', (bpclass(cls), outer))


def get_tex_size(tex: unreal.Texture2D) -> tuple[int, int]:
    """读取贴图像素宽高"""
    width = tex.blueprint_get_size_x()
    height = tex.blueprint_get_size_y()
    return max(int(width), 1), max(int(height), 1)


##############################################################################


def askopenfilename(title="Select File", filetypes=None) -> str:
    """跨平台文件选择对话框，返回选中的文件路径"""
    # 1. tkinter (Windows)
    try:
        import tkinter as tk
        from tkinter import filedialog as fd
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        result = fd.askopenfilename(title=title, filetypes=filetypes or [])
        root.destroy()
        return result
    except Exception:
        pass

    # 2. zenity（常见于 Linux 桌面环境）
    if sys.platform.startswith("linux"):
        try:
            cmd = ["zenity", "--file-selection", f"--title={title}"]
            if filetypes:
                for desc, pattern in filetypes:
                    cmd += [f"--file-filter={desc} | {pattern}"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

    # 3. osascript（macOS 原生）
    if sys.platform == "darwin":
        try:
            exts = []
            if filetypes:
                for desc, pattern in filetypes:
                    for pat in pattern.split():
                        ext = pat.lstrip("*.")
                        if ext and ext != "*":
                            exts.append(ext)
            if exts:
                ext_list = ", ".join(f'"{e}"' for e in exts)
                script = f'POSIX path of (choose file with prompt "{title}" of type {{{ext_list}}})'
            else:
                script = f'POSIX path of (choose file with prompt "{title}")'
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

    return ''


def askdirectory(title="Select Directory") -> str:
    """跨平台文件夹选择对话框，返回选中的文件夹路径"""
    # 1. tkinter（Windows）
    try:
        import tkinter as tk
        from tkinter import filedialog as fd
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        result = fd.askdirectory(title=title)
        root.destroy()
        return result
    except Exception:
        pass

    # 2. zenity（常见于 Linux 桌面环境）
    if sys.platform.startswith("linux"):
        try:
            result = subprocess.run(
                ["zenity", "--file-selection", "--directory", f"--title={title}"],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

    # 3. osascript（macOS 原生）
    if sys.platform == "darwin":
        try:
            script = f'POSIX path of (choose folder with prompt "{title}")'
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

    return ''


def asksaveasfilename(title="Save File", defaultextension="", initialfile="", filetypes=None):
    """跨平台文件保存对话框，返回要保存的文件路径"""
    # 1. tkinter
    try:
        import tkinter as tk
        from tkinter import filedialog as fd
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        result = fd.asksaveasfilename(
            title=title,
            defaultextension=defaultextension,
            initialfile=initialfile,
            filetypes=filetypes or []
        )
        root.destroy()
        return result
    except Exception:
        pass

    # 2. zenity（Linux）
    if sys.platform.startswith("linux"):
        try:
            cmd = ["zenity", "--file-selection", "--save", "--confirm-overwrite", f"--title={title}"]
            if initialfile:
                cmd += [f"--filename={initialfile}"]
            if filetypes:
                for desc, pattern in filetypes:
                    cmd += [f"--file-filter={desc} | {pattern}"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                path = result.stdout.strip()
                if defaultextension and not os.path.splitext(path)[1]:
                    path += defaultextension
                return path
        except Exception:
            pass

    # 3. osascript（macOS）
    if sys.platform == "darwin":
        try:
            init = initialfile or "untitled"
            script = f'POSIX path of (choose file name with prompt "{title}" default name "{init}")'
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                path = result.stdout.strip()
                if defaultextension and not os.path.splitext(path)[1]:
                    path += defaultextension
                return path
        except Exception:
            pass

    return ""


def startfile(folder_path):
    """跨平台打开文件夹"""
    if sys.platform == 'win32':
        os.startfile(folder_path)
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', folder_path])
    else:
        subprocess.Popen(['xdg-open', folder_path])
    return True


def send2trash(path, delete=False) -> str:
    """将文件或文件夹移至回收站；delete=True 或回收站失败时则彻底删除"""
    import shutil
    path = os.path.abspath(str(path))
    if not os.path.exists(path):
        return path

    def _purge():
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)

    if delete:
        _purge()
        return path

    try:
        if sys.platform == 'win32':
            import ctypes
            from ctypes import wintypes

            class SHFILEOPSTRUCTW(ctypes.Structure):
                _fields_ = [
                    ('hwnd', wintypes.HWND),
                    ('wFunc', wintypes.UINT),
                    ('pFrom', wintypes.LPCWSTR),
                    ('pTo', wintypes.LPCWSTR),
                    ('fFlags', wintypes.WORD),
                    ('fAnyOperationsAborted', wintypes.BOOL),
                    ('hNameMappings', wintypes.LPVOID),
                    ('lpszProgressTitle', wintypes.LPCWSTR),
                ]

            op = SHFILEOPSTRUCTW()
            op.wFunc = 3  # FO_DELETE
            op.pFrom = path + '\0\0'
            op.fFlags = 0x40 | 0x10 | 0x04  # ALLOWUNDO | NOCONFIRMATION | SILENT
            if ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)):
                raise OSError(f'无法移至回收站: {path}')
        elif sys.platform == 'darwin':
            script = f'tell application "Finder" to delete POSIX file {path!r}'
            subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
        else:
            for cmd in (['gio', 'trash', path], ['trash-put', path]):
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                    break
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue
            else:
                raise OSError(f'无法移至回收站（需要 gio 或 trash-cli）: {path}')
    except Exception:
        _purge()
    return path


def set_actor_label(actor, label, unique=True, filter_class=unreal.Actor) -> str:
    """设置Actor的标签，支持唯一后缀"""
    if not actor:
        return ''
    
    modified = label
    if unique:
        all_actors = unreal.GameplayStatics.get_all_actors_of_class(actor, filter_class)
        existing_labels = {a.get_actor_label() for a in all_actors}

        if modified in existing_labels:
            prefix = label
            idx = 0

            m = re.match(r"^(.*?)(\d+)$", label)
            if m:
                prefix = m.group(1)
                idx = int(m.group(2))
            else:
                idx = 1

            while modified in existing_labels:
                idx += 1
                modified = f"{prefix}{idx}"

    actor.set_actor_label(modified, mark_dirty=True)
    return modified


def select_actors(actors=[], append=False) -> list[unreal.Actor]:
    """选择Actor，支持追加选择"""
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if append:
        actors = subsystem.get_selected_level_actors() + list(actors)
    else:
        actors = list(actors)
    subsystem.set_selected_level_actors(actors)
    return actors

def copy(source, target=None):
    """复制Actor或资产, 名称冲突时自动添加后缀, target为坐标或路径"""
    if isinstance(source, unreal.Actor):
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        offset = unreal.Vector(*target) - source.get_actor_location()
        return subsystem.duplicate_actor(source, None, offset)

    asset = uasset(source) if not isinstance(source, str) else None
    source_path = asset.get_path_name() if asset else source
    if not unreal.EditorAssetLibrary.does_asset_exist(source_path):
        return None

    base_path = target if target else source_path
    if '.' in base_path.rsplit('/', 1)[-1]:
        base_path = base_path.rsplit('.', 1)[0]
    dest_path = base_path
    counter = 2
    while unreal.EditorAssetLibrary.does_asset_exist(dest_path):
        dest_path = f"{base_path}_{counter}"
        counter += 1
    return unreal.EditorAssetLibrary.duplicate_asset(source_path, dest_path)


#############################################################################


_UE_ARGS_SECTION = re.compile(r'Args:\s*\n(.*?)(?:\nReturns:|\Z)', re.DOTALL)
_UE_ARG_LINE = re.compile(r'^\s*(\w+)\s*\(([^)]+)\)', re.MULTILINE)
_BUILTIN_TYPES = {'bool': bool, 'int': int, 'float': float, 'str': str}


def _resolve_ue_type(type_str):
    """将 UE 文档中的类型字符串解析为 Python/unreal 类型"""
    type_str = type_str.strip().rstrip(':')
    if type_str.startswith('type(') and type_str.endswith(')'):
        return _resolve_ue_type(type_str[5:-1])
    if type_str in _BUILTIN_TYPES:
        return _BUILTIN_TYPES[type_str]
    return getattr(unreal, type_str, None)


def _is_ue_enum(cls) -> bool:
    """判断类型是否为 unreal.EnumBase 子类"""
    try:
        return isinstance(cls, type) and issubclass(cls, unreal.EnumBase)
    except TypeError:
        return False


def _to_ue_enum(value, enum_type):
    """把整数或值转换为指定 UE 枚举"""
    try:
        return enum_type.cast(value)
    except Exception:
        return list(enum_type)[value]


def _has_int_arg(args, kwargs) -> bool:
    """检查位置/关键字参数中是否含非 bool 的 int"""
    return any(isinstance(v, int) and not isinstance(v, bool) for v in args) or \
           any(isinstance(v, int) and not isinstance(v, bool) for v in kwargs.values())


@lru_cache(maxsize=256)
def parse_ue_method_args(doc):
    """解析UE函数的参数类型"""
    if not doc:
        return ()
    match = _UE_ARGS_SECTION.search(doc)
    if not match:
        return ()
    return tuple((name, _resolve_ue_type(type_str)) for name, type_str in _UE_ARG_LINE.findall(match.group(1)))


def convert_ue_call_args(args, kwargs, doc):
    """将int类型参数转换为对应的UE枚举值"""
    if not _has_int_arg(args, kwargs):
        return args, kwargs
    specs = parse_ue_method_args(doc or '')
    if not specs:
        return args, kwargs
    names = [name for name, _ in specs]
    types = [typ for _, typ in specs]
    args = list(args)
    for i, value in enumerate(args):
        if i < len(types) and isinstance(value, int) and not isinstance(value, bool) and _is_ue_enum(types[i]):
            args[i] = _to_ue_enum(value, types[i])
    kwargs = dict(kwargs)
    for key, value in kwargs.items():
        if key in names and isinstance(value, int) and not isinstance(value, bool):
            typ = types[names.index(key)]
            if _is_ue_enum(typ):
                kwargs[key] = _to_ue_enum(value, typ)
    return tuple(args), kwargs


def wrap_ue_method(method):
    """包装UE函数，将int类型参数转换为对应的UE枚举值"""
    doc = getattr(method, '__doc__', None)
    def wrapper(*args, **kwargs):
        args, kwargs = convert_ue_call_args(args, kwargs, doc)
        return method(*args, **kwargs)
    return wrapper