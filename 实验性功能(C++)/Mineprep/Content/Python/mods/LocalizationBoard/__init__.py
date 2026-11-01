from mineprep import i18n

mod_info = {
    'Name': i18n('本地化控制板', 'Localization Board'),
    'Description': i18n(
        '扫描资产并提取变量显示名至 CSV',
        'Scan assets and export variable display names to CSV',
    ),
    'Version': '2.0',
    'CreatedBy': 'Pig',
    'EnabledByDefault': False,
    'ReloadWithMineprep': True,
    'Advanced': True,
    'Priority': 1,
}


def register():
    from . import panel
    panel.LocalizationBoard.register(True)


def unregister():
    import sys
    from . import panel, ops
    ops.cancel_all()
    panel.LocalizationBoard.unregister()
    for sub in ('panel', 'ops', 'props'):
        sys.modules.pop(f'{__name__}.{sub}', None)
        globals().pop(sub, None)
