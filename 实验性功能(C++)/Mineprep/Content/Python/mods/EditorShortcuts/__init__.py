"""Mineprep 自定义快捷键模组。"""
import mineprep

mod_info = {
    "Name": mineprep.bilingual("自定义快捷键", "Editor Shortcuts"),
    "Description": mineprep.bilingual("Mineprep自定义快捷键编辑面板", "Manage and customize Mineprep editor shortcuts"),
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
