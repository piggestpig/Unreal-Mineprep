"""Pack-authored navigation and parameter groups; independent of Unreal."""
from dataclasses import dataclass
from .biomes import _label


@dataclass(frozen=True)
class UIGroup:
    id: str
    label: tuple
    pages: tuple
    fold: bool = True
    default_open: bool = False


@dataclass(frozen=True)
class UISection:
    id: str
    label: tuple
    pages: tuple
    groups: tuple = ()
    controls: tuple = ()
    shared_group: bool = False
    editor: object = None


def section_id(value, sections):
    return next((s.id for s in sections if value in s.pages), value)


def group_pages(pack, page):
    return next((s.pages for s in pack.ui_sections if s.shared_group and page in s.pages), (page,))


def parse_sections(raw, pages, params, inherited=()):
    if not isinstance(raw, dict):
        raise ValueError('ui_sections must be an ordered mapping')
    result = {s.id: s for s in inherited}
    for ident, item in raw.items():
        if not isinstance(item, dict) or set(item) - {'label','pages','groups','controls','shared_group','editor'}:
            raise ValueError(f'ui section {ident}: invalid keys')
        owned = tuple(item.get('pages', (ident,)))
        if not owned or len(set(owned)) != len(owned) or any(p not in pages for p in owned):
            raise ValueError(f'ui section {ident}: unknown or duplicate pages')
        controls = tuple(item.get('controls', ()))
        if any(k not in params or params[k].page not in owned for k in controls):
            raise ValueError(f'ui section {ident}: unknown controls')
        groups, seen = [], set()
        for g in item.get('groups', ()):
            if not isinstance(g, dict) or set(g) - {'id','label','pages','fold','default_open'}:
                raise ValueError(f'ui section {ident}: invalid group')
            gp = tuple(g.get('pages', ()))
            if not gp or any(p not in owned or p in seen for p in gp):
                raise ValueError(f'ui section {ident}: invalid group pages')
            seen.update(gp)
            groups.append(UIGroup(g['id'], _label(g.get('label'), g['id']), gp,
                                  bool(g.get('fold', True)), bool(g.get('default_open', False))))
        editor = item.get('editor')
        if editor not in (None, 'biomes', 'surface', 'features', 'water'):
            raise ValueError(f'ui section {ident}: unknown editor')
        result[ident] = UISection(ident, _label(item.get('label'), ident), owned, tuple(groups),
                                 controls, bool(item.get('shared_group', False)), editor)
    assigned = [p for s in result.values() for p in s.pages]
    if len(set(assigned)) != len(assigned):
        raise ValueError('ui_sections assign a page more than once')
    for page, label in pages.items():
        if page not in assigned:
            result[page] = UISection(page, label, (page,))
    return tuple(result.values())
