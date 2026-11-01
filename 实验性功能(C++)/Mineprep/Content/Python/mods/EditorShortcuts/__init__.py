"""Mineprep 自定义快捷键模组。"""
import mineprep
from mineprep import i18n

mod_info = {
    "Name": i18n("自定义快捷键", "Editor Shortcuts"),
    "Description": i18n('管理与自定义 Mineprep 编辑器快捷键', "Manage and customize Mineprep editor shortcuts"),
    "Version": "2.0",
    "CreatedBy": "Pig",
    "EnabledByDefault": True,
    "ReloadWithMineprep": True,
    "Advanced": True,
    "Priority": 10,
}


def register():
    from .panel import EditorShortcuts
    from . import ops
    EditorShortcuts.register(True)
    ops.register_all_hotkeys()


def unregister():
    from .panel import EditorShortcuts
    from . import ops
    ops.unregister_all_hotkeys()
    ops.unbind_hotkey_delegate()
    EditorShortcuts.unregister()
