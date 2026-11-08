"""渲染输出面板模组入口。"""
import mineprep
from mineprep import i18n

mod_info = {
    'Name': i18n('渲染输出面板', 'Render Output Panel'),
    'Description': i18n('MRQ／MRG 配置库与批量渲染、HDR 增益图 JPG',
                                     'MRQ/MRG presets, sequential rendering and Ultra HDR JPEG'),
    'Version': '0.8.1',
    'CreatedBy': 'Pig',
    'EnabledByDefault': True,
    'ReloadWithMineprep': True,
}


def register():
    from .panel import RenderPanel
    RenderPanel.register(True)


def unregister():
    from .panel import RenderPanel
    RenderPanel.unregister()
