"""页面注册表。

在本目录新增一个非下划线模块即可出现在左栏，不必改面板。模块约定：

- ``ID``：稳定字符串，供 API 切换和调用，不随排序改变。
- ``ORDER``：左栏顺序，缺省为 0；相同则按 ``ID``。
- ``LABEL``：导航标题，可以是 ``i18n(...)``。
- ``draw(mod, layout)``：往这一页的格子里构建界面。``mod`` 是面板实例，滚轮等事件直接写在页面上，再由面板转发。
- 其他公开函数是不依赖面板的操作。下划线开头的名称不会通过 API 调用。
"""
from collections import namedtuple
import importlib
import pkgutil

Page = namedtuple('Page', ('id', 'label', 'order', 'module'))


def bind(module):
    """把页面模块收成一条记录。缺字段或重复约定时直接报错。"""
    page_id = getattr(module, 'ID', None)
    if not isinstance(page_id, str) or not page_id or page_id.startswith('_'):
        raise ValueError(f'{module.__name__} 需要非空且非下划线开头的字符串 ID')
    label = getattr(module, 'LABEL', None)
    if label is None or label == '':
        raise ValueError(f'{module.__name__} 需要 LABEL')
    order = getattr(module, 'ORDER', 0)
    if isinstance(order, bool) or not isinstance(order, (int, float)):
        raise ValueError(f'{module.__name__} 的 ORDER 需要数字')
    draw = getattr(module, 'draw', None)
    if not callable(draw):
        raise ValueError(f'{module.__name__} 需要 draw(mod, layout)')
    return Page(page_id, label, order, module)


def from_modules(modules):
    """按 ORDER、ID 排序，并拒绝重复 ID。"""
    pages = [bind(module) for module in modules]
    pages.sort(key=lambda page: (page.order, page.id))
    seen = {}
    for page in pages:
        previous = seen.get(page.id)
        if previous is not None:
            raise ValueError(
                f'页面 ID {page.id!r} 重复: {previous} 与 {page.module.__name__}')
        seen[page.id] = page.module.__name__
    return tuple(pages)


def collect():
    """载入本目录下的页面模块。下划线开头的文件不会导入。"""
    modules = []
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith('_'):
            continue
        modules.append(importlib.import_module(f'{__name__}.{info.name}'))
    return from_modules(modules)


def operations(module):
    """页面模块上可直接调用的公开函数名。"""
    return tuple(sorted(
        name for name, value in vars(module).items()
        if not name.startswith('_') and callable(value) and not isinstance(value, type)
    ))
