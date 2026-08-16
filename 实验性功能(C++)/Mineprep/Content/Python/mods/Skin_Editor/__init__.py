from mineprep import bilingual

mod_info = {
    'Name': bilingual('皮肤&表情编辑器', 'Skin & Face Editor'),
    'Description': bilingual(
        '编辑视口选中的骨骼网格体皮肤与头部材质',
        'Edit skin and head materials from the selected skeletal mesh',
    ),
    'Version': '0.6-pre1',
    'CreatedBy': '',
    'EnabledByDefault': True,
    'ReloadWithMineprep': True,
}


def register():
    from . import panel
    panel.SkinEditor.register()


def unregister():
    import sys
    from . import panel
    panel.SkinEditor.unregister()
    for sub in ('panel', 'ops', 'props', 'util'):
        sys.modules.pop(f'{__name__}.{sub}', None)
        globals().pop(sub, None)
