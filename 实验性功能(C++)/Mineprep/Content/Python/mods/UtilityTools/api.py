"""实用工具的稳定入口。导入本模块不会打开面板。"""
from . import pages as registry


def pages():
    """返回 ``(id, label)``。标签保持页面里的原文，不在这里翻译。"""
    return tuple((page.id, page.label) for page in registry.collect())


def _require(page_id):
    found = registry.collect()
    for page in found:
        if page.id == page_id:
            return page
    known = ', '.join(page.id for page in found) or '(none)'
    raise LookupError(f'未知页面 {page_id!r}。可用页面: {known}')


def _instance():
    import mcvars
    from .panel import UtilityTools
    matches = [item for item in mcvars.WidgetModMap.values() if isinstance(item, UtilityTools)]
    return matches[-1] if matches else None


def show(page_id):
    """打开唯一面板并切到 ``page_id``。须在游戏线程调用。

    面板若未打开，用与工具栏相同的方式创建标签。创建后同一帧仍找不到实例就报错，不空转等待。
    """
    page = _require(page_id)
    import unreal
    from .panel import UtilityTools
    host = _instance()
    if host is None:
        widget = unreal.load_object(None, '/Game/mc/mods/UtilityTools')
        if not widget:
            raise RuntimeError('UtilityTools 尚未注册，无法打开面板')
        subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
        subsystem.spawn_and_register_tab_with_id(widget, UtilityTools.__name__)
        host = _instance()
    if host is None:
        raise RuntimeError('UtilityTools 面板未在当前帧创建')
    host.show_page(page.id)
    return page.id


def current():
    """当前页面 id。面板没开时返回 None。"""
    host = _instance()
    if host is None:
        return None
    return host.current_page()


def call(page_id, name, *args, **kwargs):
    """调用页面上的公开函数，不创建控件，也不要求面板已打开。"""
    page = _require(page_id)
    if not isinstance(name, str) or name not in registry.operations(page.module):
        known = ', '.join(registry.operations(page.module)) or '(none)'
        raise LookupError(f'页面 {page_id!r} 没有公开函数 {name!r}。可用函数: {known}')
    return getattr(page.module, name)(*args, **kwargs)
