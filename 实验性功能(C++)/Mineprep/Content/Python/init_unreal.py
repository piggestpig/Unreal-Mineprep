import unreal
import mineprep
import mcvars
import mods

import os
os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"

menus = unreal.ToolMenus.get()
toolbar = menus.find_menu("LevelEditor.MainMenu")
mc_menu = toolbar.add_sub_menu("LevelEditor.MainMenu", "mineprep", "mineprep", "MC")
mc_menu.add_section('render', mineprep.bilingual('渲染', 'Render'))
mc_menu.add_section('debug', mineprep.bilingual('调试与开发', 'Debug & Dev'))
mc_menu.add_section('mods', mineprep.bilingual('模组', 'Mods'))

mineprep.mods.register_all()

