from mineprep import bilingual

mod_info = {
    'Name': bilingual('本地化翻译控制板', 'Localization Board'),
    'Description': bilingual(
        '扫描资产并整理变量显示名 CSV',
        'Scan assets and refresh variable display-name CSVs',
    ),
    'Version': '1.0',
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
    from . import panel
    panel.LocalizationBoard.unregister()
    for sub in ('panel', 'ops', 'props'):
        sys.modules.pop(f'{__name__}.{sub}', None)
        globals().pop(sub, None)
