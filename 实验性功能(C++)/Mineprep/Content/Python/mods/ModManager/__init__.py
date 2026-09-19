from mineprep import bilingual

mod_info = {
    "Name": bilingual("模组管理器", "Mod Manager"),
    "Description": bilingual("用于启用/禁用模组", "Used for enabling/disabling mods"),
    "Version": "1.0",
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
    sys.modules.pop(f'{__name__}.mod_manager', None)
    globals().pop('mod_manager', None)