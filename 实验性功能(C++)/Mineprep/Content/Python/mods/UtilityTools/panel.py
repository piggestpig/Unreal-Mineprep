"""实用工具面板：左栏切换页面，右栏是对应内容。"""
from functools import partial
from pathlib import Path

import mineprep
from mineprep import i18n

from . import pages

TAB_DIM = 0.4
NAV_WIDTH = 160


def open_folder():
    mineprep.startfile(str(Path(__file__).resolve().parent))


class UtilityTools(mineprep.Mod):
    _unique_ = True
    _label_ = i18n('实用工具', 'Utility Tools')

    def __init__(self, context=None):
        self._tabs = []
        self._ids = []
        self._switcher = None
        self._current = None
        super().__init__(context)

    def draw(self, context=None):
        self._wheels = {}
        self._frame = self.layout.sizebox(height=700, align=(0, 0))
        root = self._frame.col(align=(0, 0), fill=1)
        header = root.row(padding=(3, 2))
        header.scalebox(align=(1, 2), padding=(5, 3)).text(
            i18n('实用工具', 'Utility Tools'), size=16)
        header.scalebox(align=3, fill=1).button(
            i18n('打开模组', 'Open Mod'),
            on_clicked=open_folder,
            align=3, padding=(4, 2), size=12,
        )

        found = pages.collect()
        if not found:
            root.text(
                i18n('在 pages/ 下新增模块即可。', 'Add a module under pages/.'),
                padding=8, wrap=True,
            )
            return

        body = root.row(fill=1, align=(0, 0))
        nav = body.sizebox(width=NAV_WIDTH, align=(0, 0))
        buttons = nav.scrollbox(align=(0, 0), fill=1)
        self._switcher = body.switcher(align=(0, 0), fill=1)
        self._tabs = []
        self._ids = []
        for page in found:
            self._tabs.append(buttons.button(
                page.label, align=(0, 1), padding=(2, 1), size=12,
                on_clicked=partial(self.show_page, page.id),
            ))
            self._ids.append(page.id)
            page.module.draw(self, self._switcher.col(align=(0, 0), fill=1))
        self.show_page(found[0].id)

    def show_page(self, page_id):
        try:
            index = self._ids.index(page_id)
        except ValueError:
            known = ', '.join(self._ids) or '(none)'
            raise LookupError(f'未知页面 {page_id!r}。可用页面: {known}') from None
        self._switcher.set_active_widget_index(index)
        for i, button in enumerate(self._tabs):
            button.set_render_opacity(1.0 if i == index else TAB_DIM)
        self._current = page_id

    def current_page(self):
        return self._current

    def on_mouse_wheel(self, delta):
        wheel = self._wheels.get(self._current) if self._current else None
        if wheel is not None:
            wheel(delta)
