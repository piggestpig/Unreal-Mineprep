import unreal
import mineprep
import mcvars
import mods

import os
os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"

menus = unreal.ToolMenus.get()
toolbar = menus.find_menu("LevelEditor.MainMenu")
mc_menu = toolbar.add_sub_menu("LevelEditor.MainMenu", "mineprep", "mineprep", "MC")
mc_menu.add_section('render', mineprep.i18n.menu.render('渲染', 'Render'))
mc_menu.add_section('debug', mineprep.i18n.menu.debug('调试与开发', 'Debug & Dev'))
mc_menu.add_section('modules', mineprep.i18n.menu.modules('核心模块', 'Core Modules'))
mc_menu.add_section('mods', mineprep.i18n.menu.mods('模组', 'Mods'))

try:
    mineprep.mods.register_all()
except Exception as exc:
    import traceback
    unreal.log_error(f'[Mineprep] 模组注册阶段抛出异常: {exc}\n{traceback.format_exc()}')

try:
    import mcptools
    mcptools.register()
except Exception as exc:
    unreal.log_warning(f'[Mineprep] MCP Python tools not registered: {exc}')

