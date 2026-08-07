SafeBroadcast = False
DebugMode = False
PythonTooltips = False
RegisteredMods = {}
Props = {}
Languages = ['zh-Hans', 'en', 'zh-Hant']

def help():
    """打印所有cvars"""
    import unreal
    import mcvars
    text = '\n'.join(f'{key} = {value}'
                     for key, value in mcvars.__dict__.items()
                     if not (key.startswith('__') or callable(value)))
    unreal.SystemLibrary.print_string(None, text, duration=5)

def reload():
    """重新加载mcvars"""
    import importlib
    import mcvars
    importlib.reload(mcvars)
