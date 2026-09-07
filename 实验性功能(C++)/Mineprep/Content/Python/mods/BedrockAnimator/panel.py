"""基岩版动画转换器面板。"""
import mineprep
from mineprep import bilingual

from . import ops, util
from .props import Props


class BedrockAnimator(mineprep.Mod):
    _label_ = bilingual('基岩版动画转换器', 'Bedrock Animator')
    _unique_ = True

    def __init__(self, context=None):
        self.props = Props()
        if not (self.props.SequenceName or '').strip():
            util.sync_seq_name(self.props)
        super().__init__(context)

    def draw(self, context=None):
        layout = self.layout
        layout.prop(
            self.props, align=(0, 1),
            on_property_changed=self.on_props,
        )
        layout.button(
            bilingual('生成动画至Sequencer', 'Key to Sequencer'),
            on_clicked=lambda: ops.apply(self),
        )
        layout.button(
            bilingual('烘焙动画序列', 'Bake Anim Sequence'),
            on_clicked=lambda: ops.bake(self),
        )

    def on_props(self, name):
        if name in ('Actor', 'JsonPath', 'FilePath'):
            util.sync_seq_name(self.props)
