"""界面参考图库。默认不启用；启用后才打开轮播面板。"""
import mineprep
from mineprep import i18n

mod_info = {
    'Name': i18n(
        '内容展示', 'Showcase', key='mod_info.Name',
    ),
    'Description': i18n(
        '界面参考图库，仅供参考，图片可能尚未更新。做界面前直接查看 image/，不必启用本模组。',
        'A UI reference library. Images may be out of date. Read image/ before building a panel; do not enable this mod.',
        key='mod_info.Description',
    ),
    'Version': '1.0',
    'CreatedBy': 'Pig',
    'Advanced': True,
    'EnabledByDefault': False,
    'ReloadWithMineprep': True,
}


def register():
    from .panel import Showcase
    Showcase.register(True)


def unregister():
    from .panel import Showcase
    Showcase.unregister()
