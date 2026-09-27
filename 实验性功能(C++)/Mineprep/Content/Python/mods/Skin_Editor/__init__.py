try:
    import unreal
except ModuleNotFoundError as exc:
    if exc.name != 'unreal':
        raise
    # 普通 Python 允许导入图片 API，不加载 UE 插件或面板。
    def bilingual(zh, en):
        return zh
else:
    from mineprep import bilingual

mod_info = {
    'Name': bilingual('皮肤&表情编辑器', 'Skin & Face Editor'),
    'Description': bilingual(
        '编辑视口选中的骨骼网格体皮肤与头部材质',
        'Edit skin and head materials from the selected skeletal mesh',
    ),
    'Version': '2.0',
    'CreatedBy': 'Pig',
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
