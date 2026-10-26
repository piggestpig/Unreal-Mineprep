"""像素标题生成器面板界面。"""
from functools import partial

import mineprep
import unreal

from . import catalog, ops

B = mineprep.bilingual


def _linear(hex_color):
    values = [int(hex_color[i:i+2], 16)/255 for i in (1, 3, 5)]
    return unreal.LinearColor(*(v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in values), 1)


def _hex(value):
    values = [max(0, min(1, v)) for v in (value.r, value.g, value.b)]
    return '#'+''.join(f'{round((v*12.92 if v <= .0031308 else 1.055*v**(1/2.4)-.055)*255):02X}' for v in values)


class Settings(mineprep.PropertyGroup):
    _autosave_ = True
    Text: str = 'Minecraft'
    Name: str = ''
    Font: str = 'minecraft-ten'
    Texture: str = 'flat'
    Overlay: str = 'off'
    Source: str = 'premade'
    Lighting: str = 'unlit'
    OutputMode: str = 'actors'
    Layout: str = 'top'
    SplitRatio: float = .5
    File: unreal.FilePath = (unreal.FilePath(), {'FilePathFilter': 'png,jpg,jpeg'})
    Height: float = (100., {'ClampMin': .1, 'UIMin': 10., 'UIMax': 500.})
    CharacterSpacing: float = (0., {'ClampMin': 0., 'UIMin': 0.})
    RowSpacing: float = (0., {'ClampMin': 0., 'UIMin': 0.})
    TopColor: unreal.LinearColor = _linear('#FFCF76')
    BottomColor: unreal.LinearColor = _linear('#DA371E')
    Tint: unreal.LinearColor = _linear('#FFFFFF')
    OverlayTint: unreal.LinearColor = _linear('#FFFFFF')
    OverlayOpacity: float = (1., {'ClampMin': 0., 'ClampMax': 1.})
    Blend: str = 'overlay'
    AutoRow: bool = True
    Row: int = (0, {'ClampMin': 0, 'EditCondition': '!AutoRow'})
    Thickness: float = (1., {'ClampMin': .01, 'UIMin': .1, 'UIMax': 3.})
    Terminators: bool = False
    DisableShifting: bool = False
    CustomBorder: bool = False
    BorderColor: unreal.LinearColor = (_linear('#000000'), {'EditCondition': 'CustomBorder'})
    EdgeBrightness: float = (35., {'ClampMin': 0., 'ClampMax': 100.})
    Location: unreal.Vector = unreal.Vector(0, 0, 0)


LABELS = {field: (zh, en) for field, zh, en in (
    ('Name', 'Actor标签', 'Actor label'), ('File', '图片文件', 'Image file'),
    ('Height', '字号 · cm', 'Size · cm'), ('CharacterSpacing', '字距', 'Letter spacing'),
    ('RowSpacing', '行距', 'Row spacing'),
    ('TopColor', '顶部颜色', 'Top colour'), ('BottomColor', '底部颜色', 'Bottom colour'),
    ('Tint', '整体染色', 'Tint'), ('OverlayTint', '叠加层染色', 'Overlay tint'),
    ('OverlayOpacity', '不透明度', 'Opacity'), ('AutoRow', '自动递增行号', 'Automatic row'),
    ('Row', '指定行号', 'Row number'), ('Thickness', '厚度倍率', 'Depth multiplier'),
    ('Terminators', '两端装饰', 'Terminators'), ('DisableShifting', '关闭字距微调', 'Disable kerning'),
    ('CustomBorder', '自定义描边颜色', 'Custom outline colour'), ('BorderColor', '描边颜色', 'Outline colour'),
    ('EdgeBrightness', '侧面亮度 · %', 'Edge light · %'), ('Location', '新标题位置', 'New title position'),
)}
MUTED = unreal.LinearColor(.55, .58, .62, 1)
OUTPUT_LABELS = {
    'merged': ('完整模型', 'Merged model'), 'actors': ('多个 Actor', 'Multiple Actors'),
    'ism': ('实例化网格体（CPU）', 'Instanced meshes (CPU)'), 'pcg': ('PCG（GPU）', 'PCG (GPU)'),
    'niagara': ('Niagara（GPU）', 'Niagara (GPU)'),
}
OUTPUT_HELP = {
    'merged': ('每行一个完整网格；追加只生成新行。', 'One mesh per row; appending keeps existing rows.'),
    'actors': ('每字一个 Actor，适合独立调整与逐字动画。', 'One Actor per letter for individual editing and animation.'),
    'ism': ('相同字形共用实例化网格体，减少场景中的 Actor 数量。', 'Repeated letters share instanced static meshes to reduce Actor count.'),
    'pcg': ('通过 PCG 生成实例，适合批量展示；不提供逐字 Actor。', 'PCG instances for batch display; no per-letter Actors.'),
    'niagara': ('通过 Niagara 生成实例，适合批量展示；不提供逐字 Actor。', 'Niagara instances for batch display; no per-letter Actors.'),
}


class TitleGenerator(mineprep.Mod):
    _label_ = B('像素标题生成器', 'Pixel Title Generator')
    _unique_ = True

    def __init__(self, context=None):
        self.props = Settings()
        self._runner, self._action = None, ''
        self._preview_request, self._preview_texture = None, None
        self._preview_textures = {}
        self._refresh_progress = {}
        self._split_ratio = self.props.SplitRatio
        if self.props.OutputMode not in OUTPUT_LABELS:
            self.props.OutputMode = 'actors'
        self._data = ops.catalog(self.props.Font)
        self.props.Font = self._data['font']
        super().__init__(context)
        self._ticker = mineprep.tick(.15)(self._watch)()

    def _change(self, field, value, reason=None):
        setattr(self.props, field, value)
        if field == 'Font':
            self._data = ops.catalog(value)
            self.redraw()
            return
        self._visibility()
        if field in ('Texture', 'Source'):
            self._request_preview()

    def draw(self, context=None):
        p = self.props
        if hasattr(self, '_splitter'):
            self._split_ratio = self._splitter.get_ratio()
        self._frame_height = None
        self._frame = self.layout.sizebox(height=700, align=(0, 0))
        layout = self._frame.col(align=(0, 0))
        header = layout.row()
        self._refresh_button = header.button(B('刷新资源', 'Refresh resources'), size=10, on_clicked=self._refresh)
        self._status = header.text(B('就绪', 'Ready'), size=10, color=MUTED, wrap=True, fill=1, align=(0, 2))
        body = self._body = layout.col(fill=1, align=(0, 0))
        self._splitter = body.splitter(ratio=self._split_ratio, fill=1)
        left = self._splitter.first.scrollbox(fill=1).col()
        right = self._splitter.second.scrollbox(fill=1).col()
        self._text = left.textbox(
            p.Text, hint=B('输入标题，Enter 换行', 'Enter title text; Enter adds a row'),
            on_text_changed=lambda value: setattr(p, 'Text', str(value)))
        self._text.set_tool_tip_text(B('支持多行输入，中间空行保留行距。大写 A 为苦力怕字形，小写 a 为普通字母 A。',
                                      'Supports multiple rows; inner blank lines keep row spacing. Uppercase A uses the Creeper glyph; lowercase a is regular.'))
        for field, label, choices in (
            ('Font', B('字体／变体', 'Font / variant'), self._data['fonts']),
            ('Layout', B('文字布局', 'Layout'), {'top': B('主标题', 'Top'), 'bottom': B('底部', 'Bottom'), 'small': B('小字', 'Small')}),
        ):
            row = left.row()
            row.sizebox(100, align=(1, 2)).text(label, size=10, color=MUTED)
            callbacks = {}
            if field == 'Font':
                build = partial(self._choice_widget, field, choices)
                callbacks = dict(on_generate_content_widget=build, on_generate_item_widget=build)
            combo = row.combo(choices, selected=getattr(p, field), on_selection_changed=partial(self._change, field), fill=1, **callbacks)
            if field == 'Font':
                self._font_combo = combo
        for field in ('Height', 'CharacterSpacing', 'RowSpacing', 'Thickness', 'AutoRow', 'Row',
                      'Terminators', 'DisableShifting', 'Location'):
            node = left.prop(p, field, text=B(*LABELS[field]))
            if field in ('CharacterSpacing', 'RowSpacing'):
                node.set_tool_tip_text(B('按字库模型单位计算，随字号一起缩放。', 'In font model units; scales with title size.'))
            elif field == 'Location':
                node.set_tool_tip_text(B('仅用于新建标题；追加文字跟随原根物体。', 'Applies to new titles; appended text follows its root.'))

        preview = right.overlay()
        self._preview_image = preview.image(size=unreal.Vector2D(96, 44), align=2)
        self._preview_hint = preview.text('', size=10, color=MUTED, align=(2, 2), wrap=True)
        right.spacer(5)
        row = right.row()
        row.sizebox(100, align=(1, 2)).text(B('颜色来源', 'Colour source'), size=10, color=MUTED)
        row.combo({'premade': B('预制', 'Preset'), 'gradient': B('渐变', 'Gradient'), 'file': B('本地', 'Local')},
                  selected=p.Source, on_selection_changed=partial(self._change, 'Source'), fill=1)
        self._premade = right.col()
        if self._data['textures'] and p.Texture not in self._data['textures']:
            p.Texture = next(iter(self._data['textures']))
        row = self._premade.row()
        row.sizebox(100, align=(1, 2)).text(B('贴图／变体', 'Texture / variant'), size=10, color=MUTED)
        build = partial(self._choice_widget, 'Texture', self._data['textures'])
        self._texture_combo = row.combo(self._data['textures'], selected=p.Texture,
            on_selection_changed=partial(self._change, 'Texture'), on_generate_content_widget=build,
            on_generate_item_widget=build, fill=1)
        self._file = right.col()
        self._file.prop(p, 'File', text=B(*LABELS['File']))
        self._gradient = right.col()
        for field in ('TopColor', 'BottomColor', 'EdgeBrightness'):
            self._gradient.prop(p, field, text=B(*LABELS[field]))
        overlays = {'off': B('无', 'None'), **self._data['overlays']}
        if p.Overlay not in overlays:
            p.Overlay = 'off'
        for field, label, choices in (
            ('Lighting', B('光照模式', 'Lighting'), {'unlit': B('无光照', 'Unlit'), 'lit': B('场景受光', 'Lit')}),
            ('Overlay', B('叠加层', 'Overlay'), overlays),
        ):
            row = right.row()
            row.sizebox(100, align=(1, 2)).text(label, size=10, color=MUTED)
            callbacks = {}
            if field == 'Overlay':
                build = partial(self._choice_widget, field, choices)
                callbacks = dict(on_generate_content_widget=build, on_generate_item_widget=build)
            row.combo(choices, selected=getattr(p, field), on_selection_changed=partial(self._change, field), fill=1, **callbacks)
        right.prop(p, 'Tint', text=B(*LABELS['Tint']))
        self._overlay = right.col()
        row = self._overlay.row()
        row.sizebox(100, align=(1, 2)).text(B('混合方式', 'Blend'), size=10, color=MUTED)
        row.combo({'normal': B('正常', 'Normal'), 'multiply': B('正片叠底', 'Multiply'),
                   'screen': B('滤色', 'Screen'), 'overlay': B('叠加', 'Overlay')},
                  selected=p.Blend, on_selection_changed=partial(self._change, 'Blend'), fill=1)
        for field in ('OverlayOpacity', 'OverlayTint'):
            self._overlay.prop(p, field, text=B(*LABELS[field]))
        for field in ('CustomBorder', 'BorderColor'):
            right.prop(p, field, text=B(*LABELS[field]))

        footer = body.col()
        output = footer.row()
        mode = output.row(fill=1)
        mode.sizebox(100, align=(1, 2)).text(B('输出模式', 'Output mode'), size=10, color=MUTED)
        self._mode_combo = mode.combo({k: B(*v) for k, v in OUTPUT_LABELS.items()}, selected=p.OutputMode,
                                      on_selection_changed=partial(self._change, 'OutputMode'), fill=1)
        label = output.prop(p, 'Name', text=B(*LABELS['Name']), fill=1)
        label.set_tool_tip_text(B('留空时取文本首个非空行的前16个字符；本次生成的Actor使用此标签，重名自动添加数字后缀。',
                                 'Leave blank to use the first 16 characters of the first nonempty row. Applies to Actors created in this batch; duplicates gain a numeric suffix.'))
        actions = footer.row()
        self._new_button = actions.button(B('新建标题', 'New title'), on_clicked=self._new, fill=1)
        self._append_button = actions.button(B('追加文字', 'Append text'), on_clicked=self._append, fill=1)
        self._new_button.set_is_enabled(bool(self._data['fonts']))
        self._append_button.set_is_enabled(bool(self._data['fonts']))
        actions.set_tool_tip_text(B('追加：选中已有标题的根物体或任意输出对象。', 'Append: select a title root or output object.'))
        if not self._data['fonts']:
            self._status.set_text(B('请先点击“刷新资源”下载素材。', 'Click Refresh resources to download the assets first.'))
        self._visibility()
        self._preview_request = None
        self._request_preview()

    def _thumbnail(self, font, style):
        key = font, style
        if key not in self._preview_textures:
            try:
                raw = catalog.thumbnail(font, style).read_bytes()
                world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
                image = unreal.RenderingLibrary.import_buffer_as_texture2d(world, raw)
                if image is None:
                    raise ValueError('无法读取示例图片。')
                image.set_editor_property('srgb', True)
                image.set_editor_property('filter', unreal.TextureFilter.TF_NEAREST)
                self._preview_textures[key] = image, image.blueprint_get_size_x(), image.blueprint_get_size_y()
            except (OSError, ValueError, RuntimeError):
                self._preview_textures[key] = None  # 缓存缺失时记为 None，待手动刷新资源后再重试
        return self._preview_textures[key]

    def _choice_widget(self, field, choices, key):
        row = mineprep.Layout(mineprep.construct(unreal.HorizontalBox, self.layout.target))
        label = choices.get(key, '')
        if key not in choices:  # 空选中项（含 NAME_None）
            row.text('', size=10)
            return row.target
        font, style = (key, 'flat') if field == 'Font' else (self.props.Font, key)
        if field == 'Overlay' and key == 'off':
            style = 'none'
        thumbnail = self._thumbnail(font, style)
        slot = row.sizebox(48, 24, align=(1, 2))
        if thumbnail is not None:
            image, width, height = thumbnail
            icon = slot.scalebox(align=(0, 0)).image(size=unreal.Vector2D(width, height), align=2)
            # 通过 set_brush_from_texture(match_size=True) 写入画刷尺寸，构建 Slate 时保持缩略图比例
            icon.set_brush_from_texture(image, match_size=True)
        row.text(label, size=10, fill=1, align=(0, 2))
        hint = str(label)
        if thumbnail is None:
            hint += '\n'+str(B('示例缺失，请刷新资源。', 'Example missing; refresh resources.'))
        row.set_tool_tip_text(hint)
        return row.target  # ComboBoxKey 委托需要返回原生 UWidget

    def _visibility(self):
        for node, source in ((self._premade, 'premade'), (self._file, 'file'), (self._gradient, 'gradient')):
            node.hide(self.props.Source != source)
        self._overlay.hide(self.props.Overlay == 'off')
        self._mode_combo.set_tool_tip_text(B(*OUTPUT_HELP[self.props.OutputMode]))

    def _request_preview(self):
        p = self.props
        key = (p.Font, p.Texture if p.Source == 'premade' else 'flat', p.Source)
        if key == self._preview_request:
            return
        self._preview_request = key
        self._preview_texture = None
        self._preview_image.set_brush_resource_object(None)
        self._preview_image.set_color_and_opacity(unreal.LinearColor(1, 1, 1, 0))
        self._preview_image.set_tool_tip_text(B('字体示例', 'Font example') if p.Source == 'premade' else B('基础字形预览', 'Base glyph preview'))
        if not self._data['fonts']:
            self._preview_hint.set_text(B('点击“刷新资源”下载素材', 'Click Refresh resources to download assets'))
            return
        thumbnail = self._thumbnail(*key[:2])
        if thumbnail is None:
            self._preview_hint.set_text(B('示例暂不可用 · 可继续生成', 'Example unavailable · generation is available'))
            self._preview_hint.set_tool_tip_text(B('请点击“刷新资源”补齐示例图片。', 'Click Refresh resources to restore the example image.'))
        else:
            self._show_preview(*thumbnail)

    def _show_preview(self, image, width, height):
        self._preview_texture = image
        self._preview_image.set_brush_resource_object(image)
        self._preview_image.set_desired_size_override(unreal.Vector2D(width, height))
        self._preview_image.set_color_and_opacity(unreal.LinearColor(1, 1, 1, 1))
        self._preview_hint.set_text('')
        self._preview_hint.set_tool_tip_text('')

    def _options(self):
        p = self.props
        return dict(font=p.Font, layout=p.Layout, source=p.Source, texture=p.Texture,
                    overlay='none' if p.Overlay == 'off' else p.Overlay, file=p.File.file_path,
                    gradient_top=_hex(p.TopColor), gradient_bottom=_hex(p.BottomColor), tint=_hex(p.Tint),
                    overlay_tint=_hex(p.OverlayTint), overlay_opacity=p.OverlayOpacity, overlay_blend=p.Blend,
                    edge_brightness=p.EdgeBrightness, border_color=_hex(p.BorderColor) if p.CustomBorder else '',
                    height_cm=p.Height, thickness=p.Thickness, character_spacing=p.CharacterSpacing,
                    row_spacing=p.RowSpacing, row=None if p.AutoRow else p.Row, terminators=p.Terminators,
                    disable_shifting=p.DisableShifting, lighting=p.Lighting, output_mode=p.OutputMode, name=p.Name,
                    location=(p.Location.x, p.Location.y, p.Location.z))

    def _begin(self, runner, action):
        self._runner, self._action = runner, action
        self._body.set_is_enabled(False)
        self._refresh_button.set_is_enabled(False)
        self._status.set_text(B('正在处理…', 'Working…'))

    def _new(self):
        self._generate()

    def _generate(self, parent=None):
        try:
            self._begin(ops.generate(self.props.Text, parent=parent, options=self._options()), 'generate')
        except ValueError as exc:
            self._status.set_text(str(exc))

    def _append(self):
        selected = list(mineprep.selected().target)
        if len(selected) != 1:
            self._status.set_text(B('请选中一个标题空物体或字形，再追加文字。', 'Select one title root or letter to append text.'))
            return
        self._generate(selected[0])

    def _refresh(self):
        self._refresh_progress = {}
        self._begin(ops.refresh_catalog(font=self.props.Font, progress=self._refresh_progress), 'catalog')

    def _watch(self):
        size = self.layout.get_local_size()
        if size.y > 250 and size.y != self._frame_height:
            self._frame_height = size.y
            self._frame.set_height_override(size.y)
        runner = self._runner
        if runner is None or not runner.done:
            if runner is not None and self._action == 'catalog':
                p = self._refresh_progress
                if p.get('stage') == 'download':
                    self._status.set_text(str(B('正在下载资源包 · {mb:.1f} MB', 'Downloading resources · {mb:.1f} MB')).format(mb=p.get('downloaded', 0)/1024**2))
                elif p.get('stage') == 'cache':
                    self._status.set_text(B('正在缓存资源 · {done}/{total}', 'Caching resources · {done}/{total}').format(done=p['done'], total=p['total']))
            return
        self._runner = None
        self._body.set_is_enabled(True)
        self._refresh_button.set_is_enabled(True)
        if runner.error:
            self._status.set_text(runner.error)
        elif self._action == 'catalog':
            self._data = runner.result
            self.props.Font = self._data['font']
            self._preview_textures.clear()
            self.redraw()
            summary = runner.result['resources']
            self._status.set_text(B('资源已缓存 · {fonts} 种字体／变体 · {files} 个文件', 'Resources cached · {fonts} fonts/variants · {files} files').format(fonts=summary['font_count'], files=summary['file_count']))
        else:
            result = runner.result
            text = B('已提交 {lines} 行（{count} 字），等待 GPU 生成', 'Submitted {lines} rows ({count} letters); waiting for GPU generation') if result['render_state'] == 'pending' else B(
                '已生成 {lines} 行（{count} 字，共 {actors} 个 Actor）', 'Generated {lines} rows ({count} letters, {actors} Actors)')
            self._status.set_text(text.format(lines=result['line_count'], count=result['character_count'], actors=len(result['actors'])))
            self._status.set_tool_tip_text(result['line_path'])

    def destruct(self):
        self._ticker.destroy()
        if self._runner is not None:
            self._runner.destroy()
        self._preview_image.set_brush_resource_object(None)
        self._preview_texture = None
        self._preview_textures.clear()
        self.props.SplitRatio = self._splitter.get_ratio()
