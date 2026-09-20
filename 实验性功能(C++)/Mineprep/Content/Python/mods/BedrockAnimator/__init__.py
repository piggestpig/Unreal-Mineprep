from mineprep import bilingual

mod_info = {
    'Name': bilingual('基岩版动画转换器', 'Bedrock Animation Converter'),
    'Description': bilingual(
        '把基岩版 animation.json 转换为动画序列',
        'Convert Bedrock animation.json to an anim sequence',
    ),
    'Version': '1.0',
    'CreatedBy': '',
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
