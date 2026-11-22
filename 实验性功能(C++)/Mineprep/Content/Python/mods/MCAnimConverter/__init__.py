from mineprep import i18n

mod_info = {
    'Name': i18n('MC动画转换器', 'Minecraft Animation Converter'),
    'Description': i18n(
        '将 Java、基岩版与 Blockbench 动画导入 Sequencer 或烘焙为动画序列',
        'Import Java, Bedrock and Blockbench animations into Sequencer or bake to an Animation Sequence',
    ),
    'Version': '5.0',
    'CreatedBy': 'Pig',
    'EnabledByDefault': True,
    'ReloadWithMineprep': True,
    'Priority': 1,
}


def register():
    from . import panel
    panel.MCAnimConverter.register(True)


def unregister():
    import sys
    from . import panel
    panel.MCAnimConverter.unregister()
    for sub in ('panel', 'ops', 'props', 'util', 'rig_rules', 'biped', 'java_clip', 'sampling', 'retarget', 'library', 'curves', 'bbmodel', 'contact', 'face_presets'):
        sys.modules.pop(f'{__name__}.{sub}', None)
        globals().pop(sub, None)
