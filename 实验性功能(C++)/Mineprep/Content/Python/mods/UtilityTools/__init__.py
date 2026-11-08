"""实用工具：多页面壳。导入本包不会打开面板。"""
try:
    import unreal
except ModuleNotFoundError as exc:
    if exc.name != 'unreal':
        raise

    def i18n(zh, en=None, *texts, **kwargs):
        return zh
else:
    from mineprep import i18n

mod_info = {
    'Name': i18n('实用工具', 'Utility Tools'),
    'Description': i18n(
        '把常用操作分成独立页面，也可不打开界面直接调用',
        'Split utilities into pages, and call them without opening the panel',
    ),
    'Version': '1.0',
    'CreatedBy': 'Pig',
    'EnabledByDefault': True,
    'ReloadWithMineprep': True,
}


def register():
    from . import panel
    panel.UtilityTools.register()


def unregister():
    import sys
    from . import panel
    panel.UtilityTools.unregister()
    prefix = f'{__name__}.pages.'
    for name in list(sys.modules):
        if name.startswith(prefix):
            sys.modules.pop(name, None)
    for sub in ('api', 'panel', 'pages'):
        sys.modules.pop(f'{__name__}.{sub}', None)
        globals().pop(sub, None)
