"""Reload the public package in place and restore enabled mod registrations."""

import importlib
import sys

import mcvars


def reload(*modules):
    if modules:
        for module in modules:
            importlib.reload(module)
        return modules[0] if len(modules) == 1 else modules

    import mineprep
    from mineprep import modding
    from mineprep import widgets

    mods = [mod.__name__ for mod in modding.reloadable_mods()]
    enabled = mcvars.EnabledMods.intersection(mods)
    widget_cache = widgets.WidgetsCache
    mcvars.ModsInitialized = False
    try:
        for name in reversed(mods):
            if not modding.unregister_mod(name):
                raise RuntimeError(f'注销失败，停止重载: {name}')

        roots = ('mineprep.', *(name + '.' for name in mods))
        names = [name for name in sys.modules if name.startswith(roots) or name in mods]
        for name in sorted(names, key=lambda item: item.count('.'), reverse=True):
            module = sys.modules.pop(name)
            parent, _, leaf = name.rpartition('.')
            namespace = sys.modules.get(parent)
            if namespace and vars(namespace).get(leaf) is module:
                delattr(namespace, leaf)
        mcvars.Props.clear()
        importlib.invalidate_caches()
        for name in tuple(vars(mineprep)):
            if not name.startswith('__'):
                delattr(mineprep, name)
        importlib.reload(mineprep)
        from mineprep import widgets
        from mineprep import modding
        widgets.WidgetsCache = widget_cache
        for name in mods:
            mod = importlib.import_module(name)
            if name in enabled and not modding.register_mod(mod):
                raise RuntimeError(f'重新注册失败: {name}')
    finally:
        mcvars.ModsInitialized = True
    return mineprep
