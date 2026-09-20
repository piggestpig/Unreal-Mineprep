from mineprep import bilingual

mod_info = {
    'Name': bilingual('插件更新与迁移工具', 'Plugin Update & Migration'),
    'Description': bilingual(
        '迁移Mineprep插件至其他工程文件或安装包仓库',
        'Migrate Mineprep plugins to other projects or the installer',
    ),
    'Version': '1.0',
    'CreatedBy': 'Pig',
    'EnabledByDefault': False,
    'ReloadWithMineprep': True,
    'Advanced': True,
    'Priority': 99,
}


def register():
    from . import panel
    panel.VersionControl.register(True)


def unregister():
    import sys
    from . import panel
    panel.VersionControl.unregister()
    for sub in ('panel', 'ops', 'props'):
        sys.modules.pop(f'{__name__}.{sub}', None)
        globals().pop(sub, None)
