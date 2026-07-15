from numpy import isin

import unreal
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pprint import pformat
from functools import lru_cache, wraps

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


_active_async_runners = set()


def asynctask(func):
    """函数装饰器，可在内部使用 yield（秒数）延迟执行"""
    def wrapper(*args, **kwargs):
        # 1. 执行原函数，获取生成器对象 (Generator)
        gen = func(*args, **kwargs)
        
        # 容错处理：如果函数内部没有 yield 关键字，它就是一个普通函数，直接返回结果即可
        if not hasattr(gen, '__next__'):
            return gen

        # 2. 内部定义高精度的帧驱动类
        class SlateCoroutineRunner:
            def __init__(self, generator_instance):
                self.gen = generator_instance
                self.target_wait_time = 0.0
                self.elapsed_time = 0.0
                self.callback_handle = None

            def start(self):
                # 注册到虚幻主循环
                self.callback_handle = unreal.register_slate_post_tick_callback(self._tick)
                # 放入全局集合，确保在异步等待期间，这个对象绝对不会别销毁
                _active_async_runners.add(self)
                # 立即驱动第一步
                self._advance()

            def _tick(self, delta_time):
                # 时间轮询检查
                if self.target_wait_time > 0.0:
                    self.elapsed_time += delta_time
                    if self.elapsed_time < self.target_wait_time:
                        return  # 时间没到，继续把控制权还给虚幻

                # 时间到了，重置计时器，迈出下一步
                self.elapsed_time = 0.0
                self.target_wait_time = 0.0
                self._advance()

            def _advance(self):
                try:
                    # 关键点：接收 yield 后面的返回值
                    result = next(self.gen)
                    
                    # 识别 yield 出来的数字（支持整型和浮点型）
                    if isinstance(result, (int, float)):
                        self.target_wait_time = float(result)
                    else:
                        self.target_wait_time = 0.0  # 纯 yield 则代表只等待一帧
                        
                except StopIteration:
                    # 逻辑全部走完，安全退出
                    self.destroy()
                except Exception as e:
                    unreal.log_error(f"异步任务【{func.__name__}】运行时崩溃: {e}")
                    self.destroy()

            def destroy(self):
                # 注销 Tick，斩断 C++ 的引用
                if self.callback_handle:
                    unreal.unregister_slate_post_tick_callback(self.callback_handle)
                    self.callback_handle = None
                # 从全局集合移出，彻底释放内存
                if self in _active_async_runners:
                    _active_async_runners.remove(self)

        # 3. 实例化驱动器并立刻启动
        runner = SlateCoroutineRunner(gen)
        runner.start()
        
        # 返回 runner 实例（如果外部想手动取消任务可以留存，不留存也会在全局集合里活得很好）
        return runner

    return wrapper


class safe:
    """数组包装器 safe(iterable, default=None)[id]，当索引超出范围时，返回输入的默认值或首个元素类型的默认值"""
    def __init__(self, iterable, default=None):
        self._data = iterable
        self._default = default

    def __getitem__(self, index):
        try:
            # 尝试正常获取索引值
            return self._data[index]
        except IndexError:
            # 1. 如果数组为空，直接返回默认值/None
            if not self._data:
                return self._default
            
            # 2. 获取首个元素的类型，尝试获取默认值
            first_element_type = type(self._data[0])
            try:
                return self._default or first_element_type()
            except:
                return self._default


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


def reload(*args):
    """重新加载mineprep及其所有子模块；传入特定模块时，只重新加载这些模块"""
    import importlib, types
    if args:
        for mod in args:
            importlib.reload(mod)
            unreal.log(f'重新加载 {mod.__name__}')
        return

    import mineprep
    localization_copy = mineprep.LocalizationCache
    widgets_copy = mineprep.WidgetsCache

    for attr in mineprep.__dict__.values():
        if isinstance(attr, types.ModuleType) and 'mc_' in attr.__name__:
            importlib.reload(attr)
            unreal.log(f'重新加载 {attr.__name__}')

    importlib.reload(mineprep)
    unreal.log("重新加载 mineprep")
    mineprep.LocalizationCache = localization_copy
    mineprep.WidgetsCache = widgets_copy

    import mods
    for attr in mods.__dict__.values():
        if isinstance(attr, types.ModuleType):
            info = getattr(attr, 'mod_info', None)
            if info and info.get('ReloadWithMineprep'):
                importlib.reload(attr)
                unreal.log(f'重新加载 {attr.__name__}')


def enum(input: type | unreal.EnumBase):
    """用下标获取UE枚举类型的对应值，如enum(var)[0]"""
    if isinstance(input, type):
        return list(input)
    else:
        return list(type(input))


def world():
    """获取当前编辑器或游戏世界"""
    subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    return subsystem.get_editor_world() or subsystem.get_game_world()


def prints(*args, duration=2.0, color=unreal.LinearColor(0, 0.66, 1, 1)):
    """在屏幕上打印多行文本"""
    text = '\n'.join(arg if isinstance(arg, str) else pformat(arg, sort_dicts=False) for arg in args)
    unreal.SystemLibrary.print_string(None, text, text_color=color, duration=duration)
    return text

def warn(*warnings, duration=5.0, color=unreal.LinearColor(1, 1, 0, 1)):
    """在屏幕上打印多行警告文本"""
    text = '\n'.join(arg if isinstance(arg, str) else pformat(arg, sort_dicts=False) for arg in warnings)
    unreal.SystemLibrary.print_string(None, text, text_color=color, duration=duration, print_to_log=False)
    unreal.log_warning(text)
    return warnings

def throw(*errors, duration=5.0, color=unreal.LinearColor(1, 0, 0, 1)):
    """在屏幕上打印多行错误文本并抛出异常"""
    text = '\n'.join(arg if isinstance(arg, str) else pformat(arg, sort_dicts=False) for arg in errors)
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
    if status == unreal.AppReturnType.YES:
        throw(f'{title}: {message}')


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
    return get_hotkey_object().call_method('Construct', (bpclass(cls), outer))


def askopenfilename(title="Select File", filetypes=None):
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







def set_actor_label(actor, label, unique=True, filter_class=unreal.Actor):
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


def select_actors(actors=[], append=False):
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
    type_str = type_str.strip().rstrip(':')
    if type_str.startswith('type(') and type_str.endswith(')'):
        return _resolve_ue_type(type_str[5:-1])
    if type_str in _BUILTIN_TYPES:
        return _BUILTIN_TYPES[type_str]
    return getattr(unreal, type_str, None)


def _is_ue_enum(cls):
    try:
        return isinstance(cls, type) and issubclass(cls, unreal.EnumBase)
    except TypeError:
        return False


def _to_ue_enum(value, enum_type):
    try:
        return enum_type.cast(value)
    except Exception:
        return list(enum_type)[value]


def _has_int_arg(args, kwargs):
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