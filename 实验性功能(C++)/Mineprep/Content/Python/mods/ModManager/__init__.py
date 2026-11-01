from mineprep import i18n

mod_info = {
    "Name": i18n("模组管理器", "Mod Manager"),
    "Description": i18n('启用、禁用、安装与打包 mod', 'Enable, disable, install, and package mods'),
    "Version": "2.0",
    "CreatedBy": "Pig",
    "Credits": "Blender",
    "EnabledByDefault": True,
    "ReloadWithMineprep": True,
    "Priority": 100,
}

def register():
    from . import mod_manager
    mod_manager.ModManager.register(True)

def unregister():
    from . import mod_manager
    mod_manager.ModManager.unregister()
    import sys
    for sub in ('mod_manager', 'ops'):
        sys.modules.pop(f'{__name__}.{sub}', None)
        globals().pop(sub, None)
