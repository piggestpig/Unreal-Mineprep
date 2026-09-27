"""基岩版动画转换器面板。"""
import mineprep
from mineprep import bilingual

from . import ops, util
from .props import Props


class BedrockAnimator(mineprep.Mod):
    _label_ = bilingual('基岩版动画转换器', 'Bedrock Animator')
    _unique_ = True

    def __init__(self, context=None):
        self._runner = None
        self.props = Props()
        if not (self.props.LevelSequenceName or '').strip() or not (self.props.AnimSequenceName or '').strip():
            util.sync_asset_names(self.props)
        super().__init__(context)

    def draw(self, context=None):
        layout = self.layout
        layout.prop(self.props, on_property_changed=self.on_props)
        layout.button(
            bilingual('生成动画至Sequencer', 'Key to Sequencer'),
            on_clicked=self.apply,
        )
        layout.button(
            bilingual('烘焙动画序列', 'Bake Anim Sequence'),
            on_clicked=self.bake,
        )

    def apply(self):
        if self._runner is None or self._runner.done:
            self._runner = ops.apply(self)

    def bake(self):
        if self._runner is None or self._runner.done:
            return ops.bake(self)

    def destruct(self):
        if self._runner is not None:
            self._runner.destroy()
            self._runner = None

    def on_props(self, name):
        if name in ('Actor', 'JsonPath', 'FilePath'):
            util.sync_asset_names(self.props)
