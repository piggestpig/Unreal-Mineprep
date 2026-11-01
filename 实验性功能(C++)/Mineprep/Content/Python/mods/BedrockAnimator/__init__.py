from mineprep import i18n

mod_info = {
    'Name': i18n('基岩版动画转换器', 'Bedrock Animation Converter'),
    'Description': i18n(
        '将基岩版 animation.json 导入 Sequencer 或烘焙为动画序列',
        'Import Bedrock animation.json into Sequencer or bake to an Animation Sequence',
    ),
    'Version': '2.0',
    'CreatedBy': 'Pig',
    'EnabledByDefault': True,
    'ReloadWithMineprep': True,
    'Priority': 1,
}


def register():
    from . import panel
    panel.BedrockAnimator.register(True)


def unregister():
    import sys
    from . import panel
    panel.BedrockAnimator.unregister()
    for sub in ('panel', 'ops', 'props', 'util'):
        sys.modules.pop(f'{__name__}.{sub}', None)
        globals().pop(sub, None)
