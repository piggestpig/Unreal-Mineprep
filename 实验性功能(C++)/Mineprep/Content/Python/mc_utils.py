import unreal
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pprint import pformat
from functools import wraps

libs = {
    'np': 'numpy',
    'numpy': 'numpy',
    'cv2': 'cv2',
    'plt': 'matplotlib.pyplot',
}

def lazy_import(func):
    # 在装饰阶段，自动扫描函数内部引用的所有全局名称
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

# 装饰器，使函数内部可以使用 yield 秒数 延迟执行
def asynctask(func):
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


def reload():
    import importlib, types
    import mineprep
    localization_copy = mineprep.LocalizationCache
    widgets_copy = mineprep.WidgetsCache

    for attr in mineprep.__dict__.values():
        if isinstance(attr, types.ModuleType) and 'mc_' in attr.__name__:
            importlib.reload(attr)
            print(f'重新加载 {attr.__name__}')

    importlib.reload(mineprep)
    print("重新加载 mineprep")
    mineprep.LocalizationCache = localization_copy
    mineprep.WidgetsCache = widgets_copy


def enum(input):
    return list(type(input))


def world():
    subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    return subsystem.get_editor_world() or subsystem.get_game_world()


def prints(*args, duration=2.0, color=unreal.LinearColor(0, 0.66, 1, 1)):
    text = '\n'.join(arg if isinstance(arg, str) else pformat(arg, sort_dicts=False) for arg in args)
    unreal.SystemLibrary.print_string(None, text, text_color=color, duration=duration)
    return text

def warn(*warnings, duration=5.0, color=unreal.LinearColor(1, 1, 0, 1)):
    text = '\n'.join(arg if isinstance(arg, str) else pformat(arg, sort_dicts=False) for arg in warnings)
    unreal.SystemLibrary.print_string(None, text, text_color=color, duration=duration)
    return warnings

def throw(*errors, duration=5.0, color=unreal.LinearColor(1, 0, 0, 1)):
    text = '\n'.join(arg if isinstance(arg, str) else pformat(arg, sort_dicts=False) for arg in errors)
    unreal.SystemLibrary.print_string(None, text, text_color=color, duration=duration)
    raise RuntimeError(errors)

def panic(title, message=''):
    if not message:
        message = title
        title = '警告'
    message = str(message) + ' \n\n是否继续运行？'
    title = str(title)
    status = unreal.EditorDialog.show_message(title, message, unreal.AppMsgType.YES_NO)
    if status == unreal.AppReturnType.YES:
        throw(f'{title}: {message}')


def uclass(input):
    """从蓝图路径、引擎内置类或对象中获取自身类"""
    if isinstance(input, (type, unreal.Class)):
        return input
    elif isinstance(input, str):
        asset = unreal.load_asset(input)
        if isinstance(asset, unreal.Blueprint):
            return unreal.EditorAssetLibrary.load_blueprint_class(input)
        return type(asset)
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


def askopenfilename(title="Select File", filetypes=None):
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

    return ""






def set_actor_label(actor, label, unique=True, filter_class=unreal.Actor) -> str:
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
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if append:
        actors = subsystem.get_selected_level_actors() + list(actors)
    else:
        actors = list(actors)
    subsystem.set_selected_level_actors(actors)
    return actors