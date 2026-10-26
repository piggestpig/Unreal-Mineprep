# -*- coding: utf-8 -*-
"""EditorShortcuts 业务逻辑与核心操作：以左栏快捷键名称直接作为字典主键。

配置持久化、按键冲突检测、静态语法校验、C++ 子系统事件总线桥接与代码执行。
"""
from __future__ import annotations

import json
import os
import unreal
import mineprep

from . import snippets

_CPP_REQUIRED = mineprep.bilingual(
    '此操作需要启用 Mineprep C++ 实验性功能插件。',
    'This operation requires the Mineprep experimental C++ plugin.',
)

# 默认预设快捷键清单 (name, chord_text, tooltip)
DEFAULT_SHORTCUTS = [
    ('放置空物体', '(Key=Zero,bShift=False,bCtrl=True,bAlt=True,bCmd=False)', '【预设】在场景中放置一个空物体'),
    ('随机弃选一半选中项', '(Key=One,bShift=False,bCtrl=True,bAlt=True,bCmd=False)', '【预设】随机弃选一半的选中项'),
    ('启用/禁用预览摄像机窗口', '(Key=Two,bShift=False,bCtrl=True,bAlt=True,bCmd=False)', '【预设】启用/禁用预览摄像机窗口'),
    ('仅显示工具栏图标', '(Key=Three,bShift=False,bCtrl=True,bAlt=True,bCmd=False)', '【预设】仅显示工具栏图标'),
    ('显示蓝图生成的组件', '(Key=Four,bShift=False,bCtrl=True,bAlt=True,bCmd=False)', '【预设】显示蓝图生成的组件'),
    ('高亮选中项', '(Key=Five,bShift=False,bCtrl=True,bAlt=True,bCmd=False)', '【预设】高亮选中项'),
    ('移动选中项到面前', '(Key=Six,bShift=False,bCtrl=True,bAlt=True,bCmd=False)', '【预设】移动选中项到面前'),
    ('设置可视性关键帧', '(Key=Seven,bShift=False,bCtrl=True,bAlt=True,bCmd=False)', '【预设】设置可视性关键帧'),
    ('刷新选中项，重新编译蓝图', '(Key=Eight,bShift=False,bCtrl=True,bAlt=True,bCmd=False)', '【预设】刷新选中项，重新编译蓝图'),
    ('交换选中对象位置', '(Key=Nine,bShift=False,bCtrl=True,bAlt=True,bCmd=False)', '【预设】交换选中对象的位置'),
    ('进入摄像机视图', '(Key=NumPadZero,bShift=False,bCtrl=False,bAlt=False,bCmd=False)', '进入摄像机视图'),
    ('对齐摄像机至视图', '(Key=NumPadZero,bShift=False,bCtrl=True,bAlt=True,bCmd=False)', '对齐摄像机至视图'),
    ('绑定其他选中项至最后选中项', '(Key=Equals,bShift=False,bCtrl=True,bAlt=True,bCmd=False)', '绑定其他选中项至最后一个视口选中项'),
    ('渲染图片', '(Key=F12,bShift=False,bCtrl=False,bAlt=False,bCmd=False)', '渲染图片'),
    ('渲染视频', '(Key=F12,bShift=False,bCtrl=True,bAlt=False,bCmd=False)', '渲染视频'),
    ('绑定选中项至空物体', '(Key=Zero,bShift=True,bCtrl=True,bAlt=True,bCmd=False)', '【预设】绑定选中项至空物体'),
    ('预览最终画质', '(Key=Tab,bShift=True,bCtrl=False,bAlt=False,bCmd=False)', '【预设】切换到最终渲染画质，持续1秒'),
    ('临时测试', '(Key=T,bShift=True,bCtrl=True,bAlt=True,bCmd=False)', '临时测试按键'),
    ('设置隐藏关键帧', '(Key=Seven,bShift=True,bCtrl=True,bAlt=True,bCmd=False)', '【预设】设置隐藏关键帧'),
    ('显示快捷键信息', '(Key=Slash,bShift=False,bCtrl=True,bAlt=True,bCmd=False)', '显示快捷键信息'),
    ('翻译鼠标下文本', '(Key=Apostrophe,bShift=False,bCtrl=False,bAlt=False,bCmd=False)', '尝试从本地化csv文件翻译鼠标下的文本'),
    ('传送摄像机至前方物体', '(Key=Tilde,bShift=True,bCtrl=False,bAlt=False,bCmd=False)', '将视口摄像机传送到前方物体'),
]

# 运行时配置缓存
SHORTCUTS_CACHE = {}

# 自动注入的基础前置代码
AUTO_IMPORT_HEADER = "import unreal\nimport mineprep\n"

# 保留委托包装对象，让 UE 的 GC 能追踪到 Python 回调代理。
_hotkey_delegate = None


def get_subsystem() -> unreal.MineprepSubsystem | None:
    """获取快捷键子系统；未安装 C++ 插件时返回 None。"""
    cls = getattr(unreal, 'MineprepSubsystem', None)
    if cls is None:
        return None
    try:
        if hasattr(unreal, 'get_editor_subsystem'):
            return unreal.get_editor_subsystem(cls)
        return unreal.EditorSubsystemBlueprintLibrary.get_editor_subsystem(cls)
    except Exception:
        return None


def _cpp_function(name):
    fn = getattr(getattr(unreal, 'mineprep', None), name, None)
    if fn is None:
        raise RuntimeError(f'{_CPP_REQUIRED} ({name})')
    return fn


def get_config_path() -> str:
    """获取 Content/Mineprep/Editor_Shortcuts.txt 的绝对规范化路径。"""
    content_dir = unreal.Paths.project_content_dir()
    return os.path.normpath(os.path.join(content_dir, "Mineprep", "Editor_Shortcuts.txt"))


def load_shortcuts() -> dict:
    """从 Editor_Shortcuts.txt 加载配置。若不存在则初始化默认配置。"""
    global SHORTCUTS_CACHE
    path = get_config_path()

    if os.path.isfile(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and data:
                SHORTCUTS_CACHE = data
                return SHORTCUTS_CACHE
        except Exception as e:
            mineprep.warn("读取 Editor_Shortcuts.txt 失败，将重新初始化", e)

    # 初次加载或文件缺失：以默认预设写入
    data = {}
    for name, chord_text, tooltip in DEFAULT_SHORTCUTS:
        data[name] = {
            'chord_text': chord_text,
            'tooltip': tooltip,
            'code': snippets.get_snippet(name),
        }

    SHORTCUTS_CACHE = data
    save_shortcuts()
    return SHORTCUTS_CACHE


def save_shortcuts() -> None:
    """持久化保存至 Content/Mineprep/Editor_Shortcuts.txt。"""
    global SHORTCUTS_CACHE
    path = get_config_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(SHORTCUTS_CACHE, f, ensure_ascii=False, indent=2)
    except Exception as e:
        unreal.log_error(f"保存快捷键配置到 {path} 失败: {e}")


def get_shortcuts() -> dict:
    """获取当前所有快捷键数据映射。"""
    global SHORTCUTS_CACHE
    if not SHORTCUTS_CACHE:
        load_shortcuts()
    return SHORTCUTS_CACHE


def get_item(name: str) -> dict:
    return get_shortcuts().get(name, {})


def rename_shortcut(old_name: str, new_name: str) -> bool:
    """重命名快捷键主键，严格保持原有显示顺序。"""
    global SHORTCUTS_CACHE
    data = get_shortcuts()
    if old_name not in data or not new_name or new_name in data:
        return False
    unregister_hotkey(old_name)

    # 保持原有在字典中的顺序重构映射
    new_data = {}
    for k, v in data.items():
        if k == old_name:
            new_data[new_name] = v
        else:
            new_data[k] = v

    SHORTCUTS_CACHE = new_data
    save_shortcuts()
    reregister_hotkey(new_name)
    return True


def update_chord_text(name: str, new_chord: str) -> None:
    data = get_shortcuts()
    if name in data:
        data[name]['chord_text'] = new_chord
        save_shortcuts()
        reregister_hotkey(name)


def update_tooltip(name: str, new_tooltip: str) -> None:
    data = get_shortcuts()
    if name in data:
        data[name]['tooltip'] = new_tooltip
        save_shortcuts()
        reregister_hotkey(name)


def update_code(name: str, new_code: str) -> None:
    data = get_shortcuts()
    if name in data:
        data[name]['code'] = new_code
        save_shortcuts()


def delete_shortcut(name: str) -> None:
    data = get_shortcuts()
    if name in data:
        del data[name]
        save_shortcuts()
        unregister_hotkey(name)


def add_shortcut(name: str = "") -> str:
    """添加一行新快捷键并保存至配置。返回生成的新快捷键名称。"""
    data = get_shortcuts()
    if not name:
        base = "新建快捷键"
        if base not in data:
            name = base
        else:
            idx = 1
            while f"{base}_{idx}" in data:
                idx += 1
            name = f"{base}_{idx}"
    elif name in data:
        return name

    data[name] = {
        'chord_text': '',
        'tooltip': '新建自定义快捷键',
        'code': '',
    }
    save_shortcuts()
    return name


def check_name_conflict(current_name: str, new_name: str) -> bool:
    """检查新名称是否与已有快捷键冲突。"""
    return new_name in get_shortcuts() and new_name != current_name


def check_chord_conflict(current_name: str, chord_text: str) -> tuple[bool, str]:
    """检查快捷键绑定是否已被其他项目占用。返回 (has_conflict, conflict_name)。"""
    for name, info in get_shortcuts().items():
        if name != current_name and info.get('chord_text') == chord_text:
            return True, name
    return False, ''


def validate_code(code: str, name: str = '') -> tuple[bool, str]:
    """静态编译校验 Python 代码。自动拼接 import unreal / import mineprep。
    
    返回 (is_valid, error_message)。
    """
    stripped = code.strip()
    if not stripped:
        return True, ""

    full_code = AUTO_IMPORT_HEADER + stripped
    try:
        compile(full_code, f"<shortcut_{name or 'custom'}>", "exec")
        return True, ""
    except SyntaxError as e:
        line_no = max(1, e.lineno - 2) if e.lineno else 1
        return False, f"第 {line_no} 行语法错误: {e.msg}"
    except Exception as e:
        return False, f"语法校验失败: {e}"


def execute_shortcut(name: str) -> None:
    """执行快捷键：
    - 若配置了 Python 代码，动态编译并执行（成功输出 unreal.log）；
    - 若代码留空，则在蓝图 (/Mineprep/Mineprep自定义快捷键) 中直接触发同名函数 name。
    """
    info = get_item(name)
    code = info.get('code', '').strip()

    if code:
        full_code = AUTO_IMPORT_HEADER + code
        try:
            compiled = compile(full_code, f"<shortcut_{name}>", "exec")
            exec(compiled, globals())
            unreal.log(f"[Mineprep] 执行快捷键: [{name}]")
        except Exception as e:
            if (isinstance(e, AttributeError) and getattr(e, 'obj', None) is unreal
                    and e.name in ('mineprep', 'MineprepSubsystem', 'EditorNotificationState', 'MineprepPostProcessStage')):
                mineprep.warn(_CPP_REQUIRED)
                return
            mineprep.warn(
                mineprep.bilingual(f"快捷键 [{name}] 报错", f"Shortcut [{name}] error"),
                e,
            )
    else:
        # 代码留空：在蓝图中直接调用名称对应的函数
        subsystem = get_subsystem()
        hotkey_obj = subsystem.get_hotkey_object() if subsystem else mineprep.get_hotkey_object()
        if not hotkey_obj:
            mineprep.warn(
                mineprep.bilingual("无法获取自定义快捷键蓝图对象", "Failed to get hotkey blueprint object")
            )
            return

        try:
            hotkey_obj.call_method(str(name))
            unreal.log(f"[Mineprep] 触发蓝图快捷键函数: [{name}]")
        except Exception as e:
            mineprep.warn(
                mineprep.bilingual(f"蓝图快捷键 [{name}] 执行报错", f"BP Shortcut [{name}] error"),
                e,
            )


def reset_to_defaults() -> None:
    """重置所有快捷键至初始预设状态。"""
    global SHORTCUTS_CACHE
    unregister_all_hotkeys()

    data = {}
    for name, chord_text, tooltip in DEFAULT_SHORTCUTS:
        data[name] = {
            'chord_text': chord_text,
            'tooltip': tooltip,
            'code': snippets.get_snippet(name),
        }

    SHORTCUTS_CACHE = data
    save_shortcuts()
    register_all_hotkeys()
    unreal.log("[Mineprep] 已将所有快捷键重置为初始预设状态")


def open_blueprint() -> bool:
    """在资产编辑器中打开自定义快捷键蓝图 (/Mineprep/Mineprep自定义快捷键)。"""
    bp_path = "/Mineprep/Mineprep自定义快捷键"
    try:
        asset = unreal.load_asset(bp_path)
        if not asset and hasattr(unreal, 'EditorAssetLibrary'):
            asset = unreal.EditorAssetLibrary.load_asset(bp_path)
        if asset:
            subsystem = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
            if subsystem:
                subsystem.open_editor_for_assets([asset])
                unreal.log(f"[Mineprep] 已打开蓝图资产: {bp_path}")
                return True
    except Exception as e:
        mineprep.warn("打开蓝图失败", e)
    return False


# ==============================================================================
# C++ UMineprepSubsystem 事件总线桥接
# ==============================================================================

def on_subsystem_hotkey_pressed(command_name: str) -> None:
    """由 C++ UMineprepSubsystem.OnHotkeyPressed 动态多播委托触发的回调。"""
    execute_shortcut(command_name)


def bind_hotkey_delegate() -> None:
    """绑定 C++ OnHotkeyPressed 委托。"""
    global _hotkey_delegate
    if _hotkey_delegate is not None:
        return
    subsystem = get_subsystem()
    if subsystem and hasattr(subsystem, 'on_hotkey_pressed'):
        try:
            delegate = subsystem.on_hotkey_pressed
            delegate.add_callable_unique(on_subsystem_hotkey_pressed)
            _hotkey_delegate = delegate
        except Exception as e:
            mineprep.warn("绑定 UMineprepSubsystem 快捷键委托失败", e)


def unbind_hotkey_delegate() -> None:
    """解绑 C++ OnHotkeyPressed 委托。"""
    global _hotkey_delegate
    if _hotkey_delegate is None:
        return
    try:
        _hotkey_delegate.remove_callable(on_subsystem_hotkey_pressed)
    except Exception as e:
        mineprep.warn("解绑 UMineprepSubsystem 快捷键委托失败", e)
    finally:
        _hotkey_delegate = None


def is_valid_chord(chord: unreal.InputChord) -> bool:
    """检查 unreal.InputChord 是否绑定了有效按键。"""
    if chord is None:
        return False
    key = getattr(chord, 'key', None)
    if key is None:
        return False
    try:
        txt = key.export_text().strip()
        if txt and txt != 'None':
            return True
    except Exception:
        pass
    try:
        name = str(getattr(key, 'key_name', '')).strip()
        if name and name != 'None':
            return True
    except Exception:
        pass
    return False


def register_all_hotkeys() -> None:
    """将所有快捷键注册到 C++ UMineprepSubsystem。"""
    subsystem = get_subsystem()
    if not subsystem:
        unreal.log_warning(str(mineprep.bilingual(
            '未启用 Mineprep C++ 插件，无法绑定全局快捷键；仍可编辑并手动执行 Python 代码。',
            'Global hotkeys require the Mineprep C++ plugin; editing and manually running Python code remain available.',
        )))
        return

    bind_hotkey_delegate()
    data = get_shortcuts()
    for name, info in data.items():
        chord_text = info.get('chord_text', '')
        if not chord_text:
            continue
        try:
            chord = unreal.InputChord()
            chord.import_text(chord_text)
            if is_valid_chord(chord):
                tip = info.get('tooltip', '')
                subsystem.register_hotkey(name, name, tip, chord)
        except Exception as e:
            mineprep.warn(f"注册快捷键 [{name}] 失败", e)


def unregister_all_hotkeys() -> None:
    """从 C++ UMineprepSubsystem 注销所有快捷键。"""
    subsystem = get_subsystem()
    if not subsystem:
        return
    data = get_shortcuts()
    for name in data.keys():
        try:
            subsystem.unregister_hotkey(name)
        except Exception:
            pass


def unregister_hotkey(name: str) -> None:
    """注销指定快捷键。"""
    subsystem = get_subsystem()
    if subsystem:
        try:
            subsystem.unregister_hotkey(name)
        except Exception:
            pass


def reregister_hotkey(name: str) -> None:
    """重新注册指定快捷键。"""
    subsystem = get_subsystem()
    if not subsystem:
        return
    try:
        subsystem.unregister_hotkey(name)
    except Exception:
        pass
    info = get_item(name)
    chord_text = info.get('chord_text', '')
    if chord_text:
        try:
            chord = unreal.InputChord()
            chord.import_text(chord_text)
            if is_valid_chord(chord):
                tip = info.get('tooltip', '')
                subsystem.register_hotkey(name, name, tip, chord)
        except Exception as e:
            mineprep.warn(f"重新注册快捷键 [{name}] 失败", e)
