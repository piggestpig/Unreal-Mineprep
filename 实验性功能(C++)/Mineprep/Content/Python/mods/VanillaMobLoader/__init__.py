"""MC 原版生物加载器：浏览、构建并放置 Blockbench CEM Template Loader 生物模型。

上游模型目录：https://wynem.com/assets/json/cem_template_models.json
参考插件：https://github.com/ewanhowell5195/blockbenchPlugins/tree/main/cem_template_loader
"""
import mineprep

mod_info = {
    'Name': mineprep.bilingual('MC原版生物加载器', 'Vanilla Mob Loader'),
    'Description': mineprep.bilingual('浏览、导入并放置MC生物模型', 'Browse, import and place skeletal MC entities'),
    'Version': '2.0',
    'CreatedBy': 'Pig',
    'Credits': '[CEM Template Loader](https://ewanhowell.com/plugins/cem-template-loader/)',
    'EnabledByDefault': True,
    'ReloadWithMineprep': True,
    'Priority': 1,
}


def register():
    from .panel import VanillaMobLoader
    VanillaMobLoader.register(True)


def unregister():
    from . import panel, api
    api.cancel_all()
    panel.VanillaMobLoader.unregister()
