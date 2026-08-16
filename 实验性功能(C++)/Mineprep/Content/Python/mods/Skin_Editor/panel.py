"""Skin & Face Editor panel."""
import mineprep
from mineprep import bilingual
from .props import Mats
from . import ops


class SkinEditor(mineprep.Mod):
    _guid_ = 'skin_editor'
    _label_ = bilingual('皮肤&表情编辑器', 'Skin & Face Editor')

    def __init__(self, context=None):
        self.props = Mats()
        self._log = None
        self._sel_hook = None
        self._syncing = False
        self._main_comp = None
        self._head_comp = None
        super().__init__(context)

    def draw(self, context=None):
        layout = self.layout
        layout.prop(
            self.props,
            align=(0, 1),
            on_property_changed=lambda name: ops.on_changed(self, name),
        )
        self._log = layout.text(
            bilingual('选择视口中的 Actor 以刷新材质', 'Select a viewport actor to refresh materials'),
            size=12,
            align=(1, 3),
            padding=6,
            fill=1,
        )
        ops.bind_selection(self)
        ops.refresh(self)
