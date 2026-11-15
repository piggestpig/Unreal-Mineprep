"""MC动画转换器面板。"""
import mineprep
from mineprep import i18n

from . import library, ops, util
from .props import Props


class MCAnimConverter(mineprep.Mod):
    _label_ = i18n('MC动画转换器', 'Minecraft Animation Converter')
    _unique_ = True

    def __init__(self, context=None):
        self._runner = None
        self.props = Props()
        super().__init__(context)

    def draw(self, context=None):
        layout = self.layout
        layout.prop(self.props, properties=['Actor', 'JsonPath', 'CreateNewSequence', 'LevelSequenceName',
                                            'StartAtPlayhead', 'AnimSequenceName', 'TimeScale'],
                    on_property_changed=self.on_props, pass_rootname=True)
        self.clip_view = layout.col()
        self.update_clips()
        layout.button(
            i18n('写入 Sequencer', 'Key to Sequencer', key='将动画写入 Sequencer'),
            on_clicked=self.apply,
        )
        layout.button(
            i18n('烘焙动画序列', 'Bake Anim Sequence'),
            on_clicked=self.bake,
        )

    def update_clips(self):
        self.clip_view.clear_children()
        self.clips = {}
        self.clip_id = None
        path = util.json_file(self.props)
        try:
            entries = ([(path, clip, clip) for clip in library.clips(path)] if path else
                       [(item['path'], item['clip'], f"{item['source']} · {item['file']} · {item['clip']}")
                        for item in library.catalog()])
        except (OSError, ValueError, KeyError) as exc:
            self.clip_view.text(str(exc))
            return
        if not entries:
            self.clip_view.text(i18n('请选择动画 JSON', 'Choose an animation JSON'))
            return
        self.clips = {str(i): (file, clip) for i, (file, clip, _) in enumerate(entries)}
        labels = {str(i): label
                  for i, (_, _, label) in enumerate(entries)}
        self.clip_id = '0'
        self.clip_view.text(i18n('动画片段', 'Clip'))
        self.clip_view.combo(labels, selected=self.clip_id, on_selection_changed=self.select_clip)
        if not self.props.LevelSequenceName or not self.props.AnimSequenceName:
            util.sync_asset_names(self.props, self.selected_clip()[1])

    def select_clip(self, key, _reason):
        self.clip_id = key
        util.sync_asset_names(self.props, self.selected_clip()[1])

    def selected_clip(self):
        if self.clip_id is None:
            raise ValueError('请选择动画片段')
        return self.clips[self.clip_id]

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
        if name in ('JsonPath', 'FilePath'):
            self.update_clips()
        if name in ('Actor', 'JsonPath', 'FilePath') and self.clip_id is not None:
            util.sync_asset_names(self.props, self.selected_clip()[1])
