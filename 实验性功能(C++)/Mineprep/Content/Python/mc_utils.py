import unreal
import os
import re
import subprocess
import sys
import time
import unreal

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


def reload():
    exec("""
import importlib, types
import mineprep

for attr in mineprep.__dict__.values():
    if isinstance(attr, types.ModuleType) and 'mc_' in attr.__name__:
        importlib.reload(attr)
        print(f'重新加载 {attr.__name__}')

importlib.reload(mineprep)
print("重新加载 mineprep")
""")


def uclass(path):
    if isinstance(path, str):
        asset = unreal.load_asset(path)
        if isinstance(asset, unreal.Blueprint):
            return unreal.EditorAssetLibrary.load_blueprint_class(path)
        return asset.get_class()

    elif isinstance(path, type):
        return path
    return None


def cast(obj, cls):
    if isinstance(cls, str):
        loaded_class = uclass(cls)
        if loaded_class and isinstance(obj, loaded_class):
            return obj
    elif isinstance(obj, cls):
        return obj
    return None


def world():
    subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    return subsystem.get_editor_world() or subsystem.get_game_world()


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






def set_actor_label_unique(actor, label, unique=True, uclass=unreal.Actor) -> str:
    if not actor:
        return ''
    
    modified = label
    if unique:
        all_actors = unreal.GameplayStatics.get_all_actors_of_class(actor, uclass)
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