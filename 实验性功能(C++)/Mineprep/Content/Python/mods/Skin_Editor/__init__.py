try:
    import unreal
except ModuleNotFoundError as exc:
    if exc.name != 'unreal':
        raise
    # 普通 Python 允许导入图片 API，不加载 UE 插件或面板。
    def i18n(zh, en):
        return zh
else:
    from mineprep import i18n

mod_info = {
    'Name': i18n('皮肤&表情编辑器', 'Skin & Face Editor'),
    'Description': i18n(
        '编辑选中角色的皮肤纹理与头部材质',
        'Edit skin textures and head materials on selected characters',
    ),
    'Version': '2.0',
    'CreatedBy': 'Pig',
    'Credits': '[MC Skin Converter](https://util.gflash.eu/mcskinconverter/)',
    'EnabledByDefault': True,
    'ReloadWithMineprep': True,
    'Priority': 1,
}


def register():
    from . import panel
    panel.SkinEditor.register(True)


def unregister():
    import sys
    from . import panel
    panel.SkinEditor.unregister()
    for sub in ('api', 'panel', 'ops', 'paint', 'props', 'util', 'snippets'):
        sys.modules.pop(f'{__name__}.{sub}', None)
        globals().pop(sub, None)
