"""Vanilla Mob Loader: browse Ewan Howell's CEM template catalog in Mineprep.

Upstream data: https://wynem.com/assets/json/cem_template_models.json
Reference UI: https://github.com/ewanhowell5195/blockbenchPlugins/tree/main/cem_template_loader
Creates skeletal entity meshes; retains static mesh construction; does not execute CEM animation expressions.
"""
import mineprep

mod_info = {
    'Name': mineprep.bilingual('MC原版生物加载器', 'Vanilla Mob Loader'),
    'Description': mineprep.bilingual('浏览、导入并放置MC生物模型', 'Browse, import and place skeletal MC entities'),
    'Version': '1.0',
    'CreatedBy': 'Pig',
    'EnabledByDefault': True,
    'ReloadWithMineprep': True,
    'Priority': 1,
}


def register():
    from .panel import VanillaMobLoader
    VanillaMobLoader.register(True)


def unregister():
    import unreal
    from . import panel
    panel.close_all()
    # UE prefixes the requested unique ID with the widget blueprint object path.
    tab_id = '/Game/mc/mods/VanillaMobLoader.VanillaMobLoaderVanillaMobLoader'
    unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem).unregister_tab_by_id(tab_id)
    panel.VanillaMobLoader.unregister()
