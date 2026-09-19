"""Skin & Face Editor panel."""
import unreal
import mineprep
from functools import partial
from mineprep import bilingual
from . import ops, paint, util
from .props import SkinEditorOptions, SkinPaintTools, SkinCodeTools, SkinBatchTools
from .util import MATERIAL_DETAILS

PAGES = (
    bilingual('编辑材质', 'Edit Materials'),
    bilingual('绘制皮肤', 'Paint Skin'),
)
TAB_DIM = 0.4


class SkinEditor(mineprep.Mod):
    _label_ = bilingual('皮肤&表情编辑器', 'Skin & Face Editor')

    def __init__(self, context=None):
        self.options = SkinEditorOptions()
        self.paint_tools = SkinPaintTools()
        self.code_tools = SkinCodeTools()
        self.batch_tools = SkinBatchTools()
        self._sel_hook = None
        self._syncing = False
        self._tabs = []
        self._pages = None
        self._left = None
        self._right = None
        self._body_title = None
        self._head_title = None
        self._body_view = None
        self._head_view = None
        self._actor_spin = None
        self._pad = None
        self._batch = None
        super().__init__(context)

    def draw(self, context=None):
        layout = self.layout
        header = layout.row(padding=(3, 2))
        tabs = header.row(align=(1, 2))
        self._tabs = []
        self._pages = layout.switcher(align=(0, 0), fill=1)
        builders = (self._draw_materials, self._draw_paint)
        for i, (label, build) in enumerate(zip(PAGES, builders)):
            btn = tabs.button(
                label, align=1, padding=(4, 2), size=12,
                on_clicked=partial(self.show_page, i),
            )
            self._tabs.append(btn)
            build(self._pages.col(align=(0, 0)))
        header.button(
            bilingual('打开模组', 'Open Mod'),
            on_clicked=util.open_mod_script,
            align=3, padding=(4, 2), size=12, fill=1
        )
        self.show_page(0)

    def show_page(self, index):
        self._pages.set_active_widget_index(index)
        for i, btn in enumerate(self._tabs):
            btn.set_render_opacity(1.0 if i == index else TAB_DIM)

    def _draw_materials(self, layout):
        actors = ops.selected_actors()
        actor = actors[0] if actors else None
        skms = ops.actor_skms(actor)
        main = util.pick_main(skms, actor) if actor and skms else None
        head = util.pick_head(skms, main) if actor and skms else None

        row = layout.row()
        self._left = row.col(fill=1, padding=3)
        self._right = row.col(fill=1, padding=3)

        self._body_title = self._left.text('', size=12, padding=(3, 4), clip=True)
        self._body_view = _material_prop(self._left, main)
        self._head_title = self._right.text('', size=12, padding=(3, 4))
        self._head_view = _material_prop(self._right, head)

        footer = layout.row(align=(1, 3), padding=(3, 1), fill=1)
        footer.text('Actor', size=10, padding=(3, 1), align=(1, 2))
        self._actor_spin = footer.spinbox(
            1, min=1, max=1, step=1, digits=0, width=32,
            padding=(3, 1, 18, 1), align=(1, 2),
            on_value_changed=lambda v: ops.on_actor_index(self, v),
        )
        footer.prop(
            self.options, 'Body',
            bilingual('身体', 'Body'),
            align=(1, 2),
            on_property_changed=lambda _: ops.apply_columns(self),
        )
        footer.prop(
            self.options, 'Head',
            bilingual('头部', 'Head'),
            align=(1, 2),
            padding=(-2, 1),
            on_property_changed=lambda _: ops.apply_columns(self),
        )

        ops.bind_selection(self)
        ops.refresh(self)
        ops.apply_columns(self)

    def _draw_paint(self, layout: mineprep.Layout):
        self._pad = paint.Pad(self.paint_tools)

        row = layout.row(align=(0, 0), fill=1)
        left = row.col(align=(0, 0), fill=1, padding=3)
        mid = row.col(padding=3, align=(0, 0))
        right = row.col(padding=3, align=(0, 0))

        box = left.scalebox(align=(2, 2), fill=1)
        box.target.set_editor_property('Stretch', unreal.Stretch.SCALE_TO_FIT)
        box.target.set_editor_property(
            'StretchDirection', unreal.StretchDirection.DOWN_ONLY)
        border = box.border(
            color=paint.FRAME,
            padding=2,
            align=(2, 2),
            on_mouse_button_down=self._pad.down,
            on_mouse_button_up=self._pad.up,
            on_mouse_move=self._pad.move,
        )
        img = border.image(
            self._pad.rt,
            size=paint.display_size(paint.RT, paint.RT, self.paint_tools.ViewSize),
            padding=0,
            align=(2, 2),
        )
        img.hide(unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE)
        self._pad.bind_image(img)
        self._pad.bind_hover(border)
        if self.paint_tools.Texture:
            paint.on_tools_changed(self, 'Texture')
        else:
            self.paint_tools.ExportPath = paint.png_path_from_tex(None)

        footer = left.row(align=(1, 3), padding=3)
        footer.checkbox(
            '', size=10, align=(1, 3),
            tooltip=bilingual('读取鼠标下的像素颜色（性能低）', 'Read color under mouse (low performance)'),
            on_check_state_changed=self._pad.set_sample_color,
        )
        hint = footer.text(
            '', size=10, align=(1, 3), clip=True,
            color=paint.HINT_WHITE)
        self._pad.bind_hint(hint)

        mid.prop(
            self.paint_tools,
            on_property_changed=lambda n: paint.on_tools_changed(self, n),
        )
        actions = mid.row(padding=(0, 3))
        actions.button(
            bilingual('还原', 'Restore'),
            on_clicked=lambda: paint.restore(self),
            padding=(3,3,3,0), size=12, fill=1
        )
        actions.button(
            bilingual('宽手臂', 'Wide Arm'),
            on_clicked=lambda: paint.use_snippet(self, 'wide_arms'),
            padding=(3,3,3,0), size=12, fill=1
        )
        actions.button(
            bilingual('细手臂', 'Slim Arm'),
            on_clicked=lambda: paint.use_snippet(self, 'slim_arms'),
            padding=(3,3,3,0), size=12, fill=1
        )
        layers = mid.row(padding=(0, 3))
        layers.button(
            bilingual('内层', 'Inner'),
            on_clicked=lambda: paint.use_snippet(self, 'keep_inner'),
            padding=(3,0,3,3), size=12, fill=1
        )
        layers.button(
            bilingual('外层', 'Outer'),
            on_clicked=lambda: paint.use_snippet(self, 'keep_outer'),
            padding=(3,0,3,3), size=12, fill=1
        )
        layers.button(
            bilingual('叠加', 'Overlay'),
            on_clicked=lambda: paint.use_snippet(self, 'apply_overlay'),
            padding=(3,0,3,3), size=12, fill=1
        )
        mid.button(
            bilingual('保存皮肤纹理', 'Save Skin Texture'),
            on_clicked=lambda: paint.save(self),
            padding=(3,0,3,3), size=12
        )
        mid.button(
            bilingual('导出.png', 'Export .png'),
            on_clicked=lambda: paint.export_png(self),
            padding=3, size=12
        )


        right.prop(self.code_tools, padding = (0, 3))
        right.button(
            bilingual('运行Python代码', 'Run Python Script'),
            on_clicked=lambda: paint.run_code(self),
            padding=3, size=12,
        )
        right.button(
            bilingual('批量处理', 'Batch Process'),
            on_clicked=lambda: paint.run_batch(self),
            padding=3, size=12,
        )
        right.button(
            bilingual('保存所有新纹理', 'Save All New Textures'),
            on_clicked=lambda: paint.save_batch(self),
            padding=3, size=12,
        )
        right.spacer()
        right.prop(self.batch_tools)
        self._batch = right
        right.hide(not self.paint_tools.Advanced)

    def _is_key(self, bound, key):
        return bool(bound) and unreal.InputLibrary.equal_equal_key_key(key, bound)

    def destruct(self):
        ops.unbind_selection(self)

    def on_key_down(self, key):
        super().on_key_down(key)
        if not self._pad:
            return
        if self._is_key(self.paint_tools.PickKey, key):
            self._pad.pick_color()
        if self._is_key(self.paint_tools.PeekKey, key):
            self._pad.show_source(True)

    def on_key_up(self, key):
        if self._pad and self._is_key(self.paint_tools.PeekKey, key):
            self._pad.show_source(False)

    def on_mouse_wheel(self, delta):
        if not self._pad or not self._pages:
            return
        if int(self._pages.get_active_widget_index()) != 1:
            return
        state = unreal.InputLibrary.get_modifier_keys_state()
        if not unreal.InputLibrary.modifier_keys_state_is_control_down(state):
            self.layout.set_consume_mouse_wheel(unreal.ConsumeMouseWheel.WHEN_SCROLLING_POSSIBLE)
            return
        self.layout.set_consume_mouse_wheel(unreal.ConsumeMouseWheel.NEVER)
        hover = self._pad.hover
        if not hover or not getattr(hover, 'target', None):
            return
        try:
            if not unreal.SystemLibrary.is_valid(hover.target):
                return
            uv = hover.get_mouse_uv()
        except Exception:
            return
        if uv.x < 0.0 or uv.x > 1.0 or uv.y < 0.0 or uv.y > 1.0:
            return
        paint.nudge_view(self, delta)


def _material_prop(layout, obj):
    kwargs = dict(subclass=MATERIAL_DETAILS, fill=1)
    if obj:
        return layout.prop(obj, **kwargs)
    return layout.custom(unreal.DetailsView, **kwargs)
