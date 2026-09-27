from mineprep import bilingual

mod_info = {
    "Name": bilingual("模组管理器", "Mod Manager"),
    "Description": bilingual("用于启用/禁用模组", "Used for enabling/disabling mods"),
    "Version": "2.0",
    "CreatedBy": "Pig",
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
