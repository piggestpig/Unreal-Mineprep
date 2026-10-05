# -*- coding: utf-8 -*-
"""EditorShortcuts 面板属性与设置。"""
import mineprep


class Settings(mineprep.PropertyGroup):
    """面板缩放与显示设置。"""
    _autosave_ = True
    scale: float = (1.0, {'UIMin': 0.5, 'UIMax': 2.0, 'ClampMin': 0.2, 'ClampMax': 3.0})


Settings.localize('Settings', '快捷键设置', 'Shortcut Settings')
Settings.localize('scale', '缩放', 'Scale')
