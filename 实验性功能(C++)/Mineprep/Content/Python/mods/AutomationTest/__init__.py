from mineprep import bilingual

mod_info = {
    'Name': bilingual('自动化测试', 'Automation Test'),
    'Description': bilingual('运行编辑器自动化测试项目', 'Run editor automation tests'),
    'Version': '2.0',
    'CreatedBy': 'Pig',
    'EnabledByDefault': False,
    'ReloadWithMineprep': True,
    'Advanced': True,
}


def register():
    from . import panel
    panel.AutomationTest.register(True)


def unregister():
    import sys
    from . import panel, ops
    ops.cancel_all()
    panel.AutomationTest.unregister()
    for sub in ('panel', 'tests', 'ops'):
        sys.modules.pop(f'{__name__}.{sub}', None)
        globals().pop(sub, None)
