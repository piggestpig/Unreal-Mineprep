from mineprep import i18n

mod_info = {
    'Name': i18n('插件更新与迁移工具', 'Plugin Update & Migration'),
    'Description': i18n(
        '将 Mineprep 同步至安装包仓库或迁移到其他 UE 工程',
        'Sync Mineprep to the installer repo or migrate to another UE project',
    ),
    'Version': '2.0',
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
