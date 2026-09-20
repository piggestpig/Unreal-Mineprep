from mineprep import bilingual

mod_info = {
    'Name': bilingual('VAT顶点动画工具', 'VAT Tools'),
    'Description': bilingual(
        '烘焙顶点动画纹理，用于大型群体粒子',
        'Bake VAT textures for large crowd particles',
    ),
    'Version': '1.0',
    'CreatedBy': 'Pig',
    'EnabledByDefault': True,
    'ReloadWithMineprep': True,
    'Priority': 1,
}


def register():
    from . import panel
    panel.VATTools.register(True)


def unregister():
    import sys
    from . import panel
    panel.VATTools.unregister()
    for sub in ('panel', 'bake_anim_ops', 'copy_ops', 'init_ops', 'props', 'util'):
        sys.modules.pop(f'{__name__}.{sub}', None)
        globals().pop(sub, None)
