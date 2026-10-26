"""Native compact editors for raw PackDraft data; generation stays in core."""
from copy import deepcopy
import math

import unreal
import mineprep

from .core.blocks import parse_block
from .core.data import from_ue, to_ue
from .core.biomes import vegetation_tint, vegetation_hsv
from .editing import normalize_source
from .ui_model import rule_summary, preview_color_linear, preview_color_hex


def tr(zh, en):
    return mineprep.bilingual(zh, en)


def name_text(name):
    """Use provided translations; plain user names are never translated."""
    if isinstance(name, dict):
        zh = name.get('zh') or name.get('en', '')
        en = name.get('en') or zh
    elif isinstance(name, (list, tuple)):
        zh, en = name[0], name[1] if len(name) > 1 else name[0]
    else:
        return str(name)
    return tr(zh, en) if zh != en else str(zh)


def click(fn):
    """UE delegates count optional Python arguments too: expose exactly zero."""
    def call():
        return fn()
    return call


def commit(fn):
    def call(value, reason):
        return fn(value, reason)
    return call


def textbox(parent, text='', *, hint='', multiline=False, on_text_changed=None, on_text_committed=None, **kwargs):
    """Use the actual native class; Layout.textbox only accepts multiline subclasses."""
    cls = unreal.EditorUtilityMultiLineEditableTextBox if multiline else unreal.EditorUtilityEditableTextBox
    widget = mineprep.add_widget(parent.target, cls, **kwargs)
    style = widget.get_editor_property('widget_style')
    for name, shade in (('background_image_normal', .025), ('background_image_hovered', .045),
                        ('background_image_focused', .035), ('background_image_read_only', .025)):
        brush = getattr(style, name)
        brush.tint_color = unreal.SlateColor(unreal.LinearColor(shade, shade, shade, 1))
        setattr(style, name, brush)
    style.foreground_color = unreal.SlateColor(unreal.LinearColor(.85, .85, .85, 1))
    style.text_style.font.size = 10
    widget.set_editor_property('widget_style', style)
    widget.set_text(text)
    widget.set_hint_text(hint)
    if on_text_changed:
        widget.on_text_changed.add_callable(on_text_changed)
    if on_text_committed:
        widget.on_text_committed.add_callable(on_text_committed)
    return mineprep.Layout(widget)


def bound_text(value):
    return '' if value is None else str(value)


def read_bound(text):
    text = str(text).strip()
    if not text:
        return None
    if text.startswith('$'):
        return text
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(tr('边界必须是有限数字、空白或 $参数名', 'Bounds must be finite numbers, blank or $parameter references.'))
    return value


class BiomeColor(mineprep.PropertyGroup):
    _autosave_ = False
    MapColor: unreal.LinearColor = ((1, 1, 1, 1), {'HideAlphaChannel': True})
    Tint: unreal.LinearColor = ((1, 1, 1, 1), {"HideAlphaChannel": True,
        "ToolTip": "线性RGB乘法倍率，1不变；允许大于1 / Linear RGB multiplier; 1 is neutral, HDR values allowed"})
    H: float = (1., {'ClampMin': .5, 'ClampMax': 1.5,
        'ToolTip': '1不变；0.9为−36°，范围±180° / 1 is neutral; 0.9 shifts −36°, range ±180°'})
    S: float = (1., {'ClampMin': 0, 'ClampMax': 65504, 'UIMax': 2})
    V: float = (1., {'ClampMin': 0, 'ClampMax': 65504, 'UIMax': 2})


BiomeColor.localize('Tint', '植被颜色倍率', 'Vegetation colour multiplier', '植被颜色倍率')
BiomeColor.localize('MapColor', '地图标识色', 'Map colour', '地图标识色')
BiomeColor.localize('BiomeColor', '群系颜色', 'Biome colours', '群系颜色')
for field, zh, en in (('H', '色相', 'Hue'), ('S', '饱和度', 'Saturation'), ('V', '明度', 'Value')):
    BiomeColor.localize(field, zh, en, zh)


class BlockOptions(mineprep.PropertyGroup):
    _autosave_ = False
    IsBuiltin: bool = (True, {'EditCondition':'false','EditConditionHides':True})
    IsJSON: bool = (False, {'EditCondition':'false','EditConditionHides':True})
    IsMesh: bool = (False, {'EditCondition':'false','EditConditionHides':True})
    Builtin: str = ('', {'EditCondition':'IsBuiltin','EditConditionHides':True,'HideEditConditionToggle':True})
    JSON: unreal.FilePath = (unreal.FilePath(), {'EditCondition':'IsJSON','EditConditionHides':True,
                                              'HideEditConditionToggle':True,'FilePathFilter':'json'})
    Mesh: unreal.StaticMesh = (None, {'EditCondition':'IsMesh','EditConditionHides':True,'HideEditConditionToggle':True})
    OverrideEmission: bool = (False, {'InlineEditConditionToggle':True})
    Emission: float = (0.1, {'EditCondition':'OverrideEmission','ClampMin':0,'UIMax':1})
    OverrideLighting: bool = (False, {'InlineEditConditionToggle':True})
    Lighting: float = (1., {'EditCondition':'OverrideLighting','ClampMin':0,'UIMax':2})
    OverrideColor: bool = (False, {'InlineEditConditionToggle':True})
    Color: unreal.LinearColor = ((1,1,1,1), {'EditCondition':'OverrideColor','HideAlphaChannel':True})
    Offset: unreal.Vector = (unreal.Vector(0,0,0), {'EditCondition':'!Occludes','HideEditConditionToggle':True,
                                                 'ToolTip':'UE XYZ，Z为高度；单位格 / UE XYZ, Z up, blocks'})
    Scale: unreal.Vector = (unreal.Vector(1,1,1), {'EditCondition':'!Occludes','HideEditConditionToggle':True,
                                                'ToolTip':'UE XYZ，Z为高度 / UE XYZ, Z up'})
    ShowGeometry: bool = False
    Occludes: bool = (True, {'EditCondition':'ShowGeometry','EditConditionHides':True,'HideEditConditionToggle':True})


BlockOptions.localize('BlockOptions','方块设置','Block options','方塊設定')

for _name, _zh, _en in (
    ('Builtin','内置模型','Builtin model'),('JSON','模型JSON文件','Model JSON file'),('Mesh','来源网格','Source mesh'),
    ('Emission','发光亮度','Emission'),
    ('Lighting','照明强度','Lighting'),
    ('Color','预览颜色','Preview colour'),
    ('Offset','偏移（格）','Offset (blocks)'),
    ('Scale','缩放','Scale'),('ShowGeometry','高级几何设置','Advanced geometry'),
    ('Occludes','完整不透明立方体','Complete opaque cube')):
    BlockOptions.localize(_name,_zh,_en,_zh)


class ContentEditors:
    """Mixin: selections and folds are model state, independent of page widgets."""
    def _text(self, row, text, setter, *, hint='', key=None, multiline=False, fill=1):
        def identity(value):
            return value if isinstance(value, (str, int, float, bool, type(None))) else id(value)
        closure = tuple(identity(c.cell_contents) for c in (setter.__closure__ or ()))
        defaults = tuple(identity(v) for v in (setter.__defaults__ or ()))
        error_key = (self.page, key or (setter.__code__.co_firstlineno, closure, defaults))
        self._active_inputs.add(error_key)
        def changed(value):
            self._input_text[error_key] = str(value)
            self._edit(lambda: setter(str(value)), error_key=error_key)
            if error_key not in self._errors:
                self._input_text.pop(error_key, None)
        return textbox(row, self._input_text.get(error_key, str(text)), hint=hint, multiline=multiline,
                       on_text_changed=changed, fill=fill)

    def _edit(self, action, *, redraw=False, error_key=None, appearance=False):
        if self._suspend:
            return
        try:
            action()
            self._errors.pop(error_key, None)
            (self._palette_changed if appearance else self._changed)()
            if redraw:
                self._refresh_content(*((redraw,) if isinstance(redraw, str) else ()))
            elif 'rules' in getattr(self, '_content_regions', {}):
                self._refresh_rule_titles()
        except Exception as exc:
            self._errors[error_key] = str(exc)
            (self._palette_changed if appearance else self._changed)()
            self._set_status(str(exc))

    def _content_region(self, parent, name, build):
        slot = parent.col()
        before = self._active_inputs.copy()
        build(slot)
        self._content_regions[name] = (slot, build, self._active_inputs - before)

    def _refresh_content(self, *names, prune=True):
        suspended, self._suspend = self._suspend, True
        try:
            for name in names or tuple(self._content_regions):
                slot, build, previous = self._content_regions[name]
                slot.clear_children()
                self._active_inputs = set()
                build(slot)
                current = self._active_inputs.copy()
                if prune:
                    for key in previous - current:
                        self._errors.pop(key, None)
                        self._input_text.pop(key, None)
                self._page_inputs[self.page].difference_update(previous)
                self._page_inputs[self.page].update(current)
                self._content_regions[name] = (slot, build, current)
        finally:
            self._suspend = suspended

    def _move(self, items, index, delta):
        other = index + delta
        if 0 <= other < len(items):
            items[index], items[other] = items[other], items[index]

    def _order_buttons(self, row, items, index, delete=None):
        region = (True if items is self.draft.data['biomes'] else
                  'biome_details' if any(items is b['climate'] for b in self.draft.data['biomes']) else 'rules')
        for label, delta in (('↑', -1), ('↓', 1)):
            row.button(label, text_scaling=True, size=10, on_clicked=click(lambda d=delta: self._edit(
                lambda: self._move(items, index, d), redraw=region)))
        row.button(tr('删除', 'Delete'), text_scaling=True, size=10, on_clicked=click(lambda: self._edit(
            delete or (lambda: items.pop(index)), redraw=region)))

    def _bounds(self, row, values, *, mapping=False):
        for index, label in enumerate((tr('下界', 'Lower'), tr('上界', 'Upper'))):
            name = ('min', 'max')[index] if mapping else index
            row.text(label, size=9)
            value = values.get(name) if mapping else values[index]
            self._text(row, bound_text(value), lambda text, n=name: values.__setitem__(n, read_bound(text)))

    def _field_row(self, parent, conditions, field, *, climate=False):
        row = parent.row(padding=(0, 2))
        fields = self.pack.biome_parameters if climate else self.pack.fields
        row.combo({f: f for f in fields}, selected=field, fill=.8,
                  on_selection_changed=lambda name, _: self._rename_field(conditions, field, name, climate=climate))
        if climate:
            self._bounds(row, conditions[field])
        else:
            raw = conditions[field]
            for name, index, label in (('min', 0, tr('下界', 'Lower')), ('max', 1, tr('上界', 'Upper'))):
                row.text(label, size=9)
                value = raw.get(name) if isinstance(raw, dict) else raw[index]
                self._text(row, bound_text(value), lambda text, n=name: self._condition(conditions, field, n, text))
        if not climate:
            row.text(tr('扰动', 'Jitter'), size=9)
            self._text(row, bound_text(raw.get('jitter', 0) if isinstance(raw, dict) else 0),
                       lambda text: self._condition(conditions, field, 'jitter', text), fill=.6)
        row.button('×', text_scaling=True, size=10, on_clicked=click(lambda: self._edit(
            lambda: conditions.pop(field), redraw='biome_details' if climate else 'rules')))

    def _rename_field(self, conditions, old, new, *, climate=False):
        def change():
            if new in conditions and new != old:
                raise ValueError(tr('同一个盒/规则中的字段不能重复', 'A field cannot occur twice in one box or rule.'))
            conditions[new] = conditions.pop(old)
        self._edit(change, redraw='biome_details' if climate else 'rules')

    def _add_field(self, conditions, *, climate=False):
        def add():
            fields = self.pack.biome_parameters if climate else self.pack.fields
            field = next((f for f in fields if f not in conditions), None)
            if field is None:
                raise ValueError(tr('所有字段已在当前条件中', 'All available fields are already used.'))
            conditions[field] = [None, None] if climate else {'min': None, 'max': None}
        self._edit(add, redraw='biome_details' if climate else 'rules')

    def _biome_editor(self, parent):
        parent.text(tr('群系列表：顺序决定重叠/等距优先级', 'Biome order resolves overlaps and equal distances.'), size=11, wrap=True)
        search = textbox(parent, self._biome_search, hint=tr('搜索名称或 ID', 'Search name or ID'),
                               on_text_committed=lambda value, _: self._search_biomes(str(value)))
        self._biome_search_box = search
        self._content_region(parent, 'biome_list', self._biome_list)
        parent.button(tr('复制当前群系并新增', 'Duplicate selected biome'), text_scaling=True, size=11, on_clicked=click(self._clone_biome))
        self._content_region(parent, 'biome_details', self._biome_details)

    def _biome_list(self, parent):
        biomes = self.draft.data['biomes']
        self._biome_buttons = {}
        for index, biome in enumerate(biomes):
            if self._biome_search.lower() not in (biome['id'] + str(biome['name'])).lower():
                continue
            row = parent.row(padding=(0, 2))
            color = biome.get('color', '#808080')
            try:
                rgb = preview_color_linear(color)
                row.border(color=unreal.LinearColor(*rgb, 1)).spacer(12)
            except (ValueError, TypeError):
                row.text('?', size=10)
            name = name_text(biome['name'])
            label = unreal.Text('{selected}{name} · {id}{fallback}').format(
                selected='● ' if biome['id'] == self._biome_id else '', name=name, id=biome['id'],
                fallback=tr(' [兜底]', ' [fallback]') if biome.get('fallback') else '')
            button = row.button(label, text_scaling=True, size=11, fill=1,
                       on_clicked=click(lambda b=biome: self._select_biome(b['id'])))
            self._biome_buttons[biome['id']] = (button, biome)
            self._order_buttons(row, biomes, index)

    def _biome_details(self, parent):
        biomes = self.draft.data['biomes']
        biome = next((b for b in biomes if b['id'] == self._biome_id), None)
        if not biome:
            parent.text(tr('请选择群系', 'Select a biome'), size=11)
            return
        parent.text(tr('ID {id}（已有 ID 保持稳定）', 'ID {id} (existing IDs remain stable)').format(id=biome['id']), size=10)
        if isinstance(biome['name'], str):
            # Preserve the original shape until the name is actually edited.
            def name_set(text):
                biome['name'] = {'zh': text, 'en': text}
            self._text(parent.row(), biome['name'], name_set)
        else:
            for language, label in (('zh', tr('中文名称', 'Chinese name')), ('en', tr('英文名称', 'English name'))):
                row = parent.row()
                row.text(label, size=10)
                self._text(row, biome['name'].get(language, ''),
                           lambda text, lang=language: biome['name'].__setitem__(lang, text))
        self._biome_colors = BiomeColor()
        self._biome_colors.MapColor = unreal.LinearColor(*preview_color_linear(biome.get('color', '#808080')), 1)
        parent.prop(self._biome_colors, 'MapColor', searching=False,
                    on_property_changed=lambda _: self._map_color_changed(biome))
        self._bct_mode_editor(parent)
        if self.output_options.BCTColorMode == 'hsv':
            self._biome_colors.H, self._biome_colors.S, self._biome_colors.V = biome.get('vegetation_hsv', [1, 1, 1])
            parent.prop(self._biome_colors, properties=['H', 'S', 'V'], categories=[], searching=False,
                        on_property_changed=lambda _: self._hsv_changed(biome))
        else:
            self._biome_colors.Tint = unreal.LinearColor(*biome.get('vegetation_tint', [1, 1, 1]), 1)
            parent.prop(self._biome_colors, properties=['Tint'], categories=[], searching=False,
                        on_property_changed=lambda _: self._tint_changed(biome))
        box = parent.checkbox(tr('兜底群系（不参与普通气候盒竞争）', 'Fallback biome (excluded from normal climate candidates)'), size=11,
                              on_check_state_changed=lambda checked: self._fallback(biome, checked))
        box.set_is_checked(bool(biome.get('fallback')))
        parent.text(tr('盒内条件为“且”；盒间为“或”；区间包含两端。空白为无界，支持 $参数名。', 'AND within a box; OR between boxes. Bounds are inclusive. Blank is unbounded; $parameter references are supported.'), size=10, wrap=True)
        if biome.get('fallback'):
            return
        for index, climate in enumerate(biome['climate']):
            card = parent.col(padding=4)
            row = card.row()
            row.text(tr('气候盒 {index} · 且{or}', 'Climate box {index} · AND{or}').format(
                index=index + 1, **{'or': tr('（或）', ' (OR)') if index else ''}), size=11, fill=1)
            self._order_buttons(row, biome['climate'], index)
            for field in list(climate):
                self._field_row(card, climate, field, climate=True)
            card.button(tr('＋条件', '+ Condition'), text_scaling=True, size=10, on_clicked=click(lambda c=climate: self._add_field(c, climate=True)))
        parent.button(tr('＋气候盒（或）', '+ Climate box (OR)'), text_scaling=True, size=11, on_clicked=click(lambda: self._edit(
            lambda: biome['climate'].append({'temperature': [None, None]}), redraw='biome_details')))

    def _map_color_changed(self, biome):
        if self._suspend:
            return
        def change():
            colour = self._biome_colors.MapColor
            value = preview_color_hex((colour.r, colour.g, colour.b))
            self._suspend = True
            try:
                self._biome_colors.MapColor = unreal.LinearColor(*preview_color_linear(value), 1)
            finally:
                self._suspend = False
            biome['color'] = value
        self._edit(change, redraw='biome_list', error_key=('color', biome['id']))

    def _tint_changed(self, biome):
        if self._suspend:
            return
        value = self._biome_colors.Tint
        def change():
            rgb = vegetation_tint([value.r, value.g, value.b])
            self._suspend = True
            try:
                self._biome_colors.Tint = unreal.LinearColor(*rgb, 1)
            finally:
                self._suspend = False
            biome['vegetation_tint'] = list(rgb)
        self._edit(change, error_key=('vegetation_tint', biome['id']), appearance=True)

    def _hsv_changed(self, biome):
        if self._suspend:
            return
        def change():
            colour = self._biome_colors
            biome['vegetation_hsv'] = list(vegetation_hsv([colour.H, colour.S, colour.V]))
        self._edit(change, error_key=('vegetation_hsv', biome['id']), appearance=True)

    def _search_biomes(self, text):
        self._biome_search = text
        self._refresh_content('biome_list')

    def _select_biome(self, name):
        if name == self._biome_id or self._suspend:
            return
        self._biome_id = name
        for key, (button, biome) in self._biome_buttons.items():
            button.get_content().get_content().set_text(unreal.Text('{selected}{name} · {id}{fallback}').format(
                selected='● ' if key == name else '', name=name_text(biome['name']), id=key,
                fallback=tr(' [兜底]', ' [fallback]') if biome.get('fallback') else ''))
        self._refresh_content('biome_details', prune=False)

    def _clone_biome(self):
        def add():
            biomes = self.draft.data['biomes']
            original = next((b for b in biomes if b['id'] == self._biome_id), biomes[-1] if biomes else None)
            if original is None:
                raise ValueError(tr('没有可复制的群系，请恢复预设或重新载入资源包', 'No biome to duplicate; reset or reload the pack.'))
            clone = deepcopy(original)
            used = {b['id'] for b in biomes}
            index = 1
            while f'custom_biome_{index}' in used:
                index += 1
            clone['id'] = f'custom_biome_{index}'
            if clone.get('fallback'):
                clone['fallback'], clone['climate'] = False, [{'temperature': [None, None]}]
            biomes.append(clone)
            self._biome_id = clone['id']
        self._edit(add, redraw=True)

    def _fallback(self, biome, checked):
        def change():
            biome['fallback'] = checked
            biome['climate'] = [] if checked else [{'temperature': [None, None]}]
        self._edit(change, redraw=True)

    def _candidate_editor(self, parent, rule, role):
        raw = rule.get(role, '')
        candidates = [[raw, 1]] if isinstance(raw, str) else raw
        parent.text({'top': tr('顶层', 'Top'), 'under': tr('覆盖层', 'Under'), 'deep': tr('深层', 'Deep')}[role], size=10)
        for index, (name, weight) in enumerate(candidates):
            row = parent.row(padding=(0, 1))
            def set_name(text, i=index):
                block = self.draft.input_block(text)
                updated = deepcopy(candidates)
                updated[i][0] = block
                rule[role] = updated
                candidates[i][0] = block
            self._text(row, name, set_name, hint=tr('方块名 / JSON 路径 / StaticMesh 引用', 'Block name / JSON path / StaticMesh reference'), key=(id(rule), role, index))
            row.spinbox(weight, min=0.000001, digits=3, width=52,
                        on_value_committed=commit(lambda value, _, i=index: self._edit(
                            lambda: self._weight(rule, role, candidates, i, value))))
            row.button('×', text_scaling=True, size=10, on_clicked=click(lambda i=index: self._edit(
                lambda: rule.__setitem__(role, [c for j, c in enumerate(candidates) if j != i]), redraw='rules')))
        row = parent.row()
        row.button(tr('＋候选', '+ Candidate'), text_scaling=True, size=10, on_clicked=click(lambda: self._edit(
            lambda: rule.__setitem__(role, deepcopy(candidates) + [['stone', 1]]), redraw='rules')))
        batch_key = (id(rule), role)
        batch = textbox(parent, self._batches.get(batch_key, ''),
                        hint=tr('批量粘贴：每行一个方块名或路径，初始等权', 'Paste one block name or path per line; initial weights are equal.'), multiline=True,
                        on_text_changed=lambda value: self._batches.__setitem__(batch_key, str(value)))
        row.button(tr('替换为批量输入', 'Replace with batch input'), text_scaling=True, size=10, on_clicked=click(lambda: self._edit(
            lambda: rule.__setitem__(role, [[self.draft.input_block(line), 1]
                                          for line in str(batch.get_text()).splitlines() if line.strip()]), redraw='rules')))

    @staticmethod
    def _weight(rule, role, candidates, index, value):
        candidates[index][1] = value
        rule[role] = deepcopy(candidates)

    def _rules_editor(self, parent):
        options = {'common': tr('公共覆盖（优先于群系规则）', 'Common overrides (before biome rules)')}
        options.update({b['id']: b['id'] for b in self.draft.data['biomes']})
        if self._rules_id not in options:
            self._rules_id = 'common'
        parent.combo(options, selected=self._rules_id, on_selection_changed=self._select_rules)
        self._content_region(parent, 'rules', self._rule_details)

    def _rule_details(self, parent):
        self._rule_widgets = {}
        rules = self.draft.data['surface_overrides'] if self._rules_id == 'common' else next(
            b['surface'] for b in self.draft.data['biomes'] if b['id'] == self._rules_id)
        parent.text(tr('按顺序匹配；区间为 [下界, 上界)', 'Match in order; bounds are [lower, upper)'),
                    size=10, wrap=True, tooltip=tr(
                        '公共覆盖优先。各层取首条匹配；群系末条须无条件且含完整三层。',
                        'Common overrides take priority. Each layer uses its first match; the last biome rule must be unconditional and cover all three layers.'))
        for index, rule in enumerate(rules):
            row = parent.row(padding=(0, 4))
            expanded = id(rule) in self._expanded
            button = row.button(' ', size=10, fill=1,
                       on_clicked=click(lambda r=rule: self._toggle_rule(r)))
            caption = button.get_content()
            caption.set_text_overflow_policy(unreal.TextOverflowPolicy.ELLIPSIS)
            caption.set_editor_property('justification', unreal.TextJustify.LEFT)
            self._order_buttons(row, rules, index)
            card = parent.col(padding=4)
            self._rule_widgets[id(rule)] = dict(button=button, caption=caption, card=card,
                rule=rule, index=index + 1, text=None, tooltip=None)
            card.hide(not expanded)
            conditions = rule.get('when', {})
            for field in list(conditions):
                self._field_row(card, conditions, field)
            card.button(tr('＋条件', '+ Condition'), text_scaling=True, size=10, on_clicked=click(lambda r=rule: self._add_rule_field(r)))
            for role in ('top', 'under', 'deep'):
                self._candidate_editor(card, rule, role)
        parent.button(tr('＋规则', '+ Rule'), text_scaling=True, size=11, on_clicked=click(lambda: self._edit(
            lambda: rules.append({'top': 'stone', 'under': 'stone', 'deep': 'stone'}), redraw='rules')))
        self._refresh_rule_titles()

    def _refresh_rule_titles(self):
        for key, state in self._rule_widgets.items():
            material, extra, count, details = rule_summary(state['rule'])
            material = material or tr('沿用后续规则', 'Use later rule')
            if extra:
                material += f' +{extra}'
            conditions = (tr('{count} 条条件', 'Conditions: {count}').format(count=count)
                          if count else tr('无条件', 'Unconditional'))
            text = unreal.Text('{arrow}{index} · {material} · {conditions}').format(
                arrow='▼ ' if key in self._expanded else '▶ ', index=state['index'],
                material=material, conditions=conditions)
            if str(text) != state['text']:
                state['caption'].set_text(text)
                state['text'] = str(text)
            if details != state['tooltip']:
                state['button'].set_tool_tip_text(details)
                state['tooltip'] = details

    def _add_rule_field(self, rule):
        self._add_field(rule.setdefault('when', {}))

    def _select_rules(self, name, _reason=None):
        if self._suspend or name == self._rules_id:
            return
        self._rules_id = name
        self._refresh_content('rules', prune=False)

    def _toggle_rule(self, rule):
        key = id(rule)
        self._expanded.discard(key) if key in self._expanded else self._expanded.add(key)
        self._rule_widgets[key]['card'].hide(key not in self._expanded)
        self._refresh_rule_titles()

    def _block_reference(self, parent, target, label, shape):
        row = parent.row()
        row.text(label, size=10)
        def change(text):
            # Preserve attributes of the referenced water/plant when replacing its source.
            old = self.draft.block(target['block'])
            target['block'] = self.draft.input_block(text, shape=shape, definition=old)
        self._text(row, target['block'], change)

    def _blocks_editor(self, parent):
        parent.text(tr('共享方块定义；输入不导入资源。材质覆盖在下次准备、放置时生效。', 'Shared block definitions; typing does not import. Material overrides apply on preparation and placement.'), size=11, wrap=True)
        row = parent.row()
        source = textbox(row, self._new_source, hint=tr('名称 / JSON 文件路径 / UE 复制引用', 'Name / JSON file path / UE copied reference'), fill=1,
                         on_text_changed=lambda value: setattr(self, '_new_source', str(value)))
        template = {'cube': tr('实体地形', 'Solid terrain'), 'surface': tr('水面', 'Water surface'), 'decor': tr('植物', 'Plant')}
        usage = row.combo(template, selected=self._block_shape,
                          on_selection_changed=lambda name, _: setattr(self, '_block_shape', name))
        row.button(tr('新增', 'Add'), text_scaling=True, size=10, on_clicked=click(lambda: self._new_block(str(source.get_text()))))
        textbox(parent, getattr(self,'_block_search',''),hint=tr('搜索方块ID', 'Search block IDs'),
                on_text_changed=self._search_blocks)
        from .ui_choices import choice
        options = self._block_choices()
        if self._block_id not in options:
            self._block_id = next(iter(options),'')
        self._block_choice = choice(parent, options, self._block_id, self._select_block)
        self._content_region(parent, 'block_details', self._selected_block_editor)

    def _selected_block_editor(self, parent):
        template = {'cube': tr('实体地形', 'Solid terrain'), 'surface': tr('水面', 'Water surface'), 'decor': tr('植物', 'Plant')}
        if not self._block_id:
            return
        self._block_title = parent.text('ID ' + self._block_id,size=11)
        self._block_source = parent.combo({'builtin':tr('内置模型','Builtin'), 'json':tr('JSON模型','JSON model'),
                                          'mesh':tr('UE网格','UE mesh')},
                                         on_selection_changed=self._block_source_kind)
        row = parent.row()
        row.text(tr('用途', 'Usage'), size=10)
        self._block_usage = row.combo(template,fill=1,
            on_selection_changed=lambda name, _: self._block_template(None,name))
        if not hasattr(self,'_block_options'):
            self._block_options = BlockOptions()
        parent.prop(self._block_options,categories=[],searching=False,pass_rootname=True,
                    on_property_changed=self._block_options_changed)
        parent.text(tr('未勾选时跟随来源材质；覆盖作用于全部材质槽。预览颜色仅影响离线图片。',
                       'Unchecked values follow source materials; overrides affect all slots. Preview colour affects offline images only.'),size=10,wrap=True)
        parent.button(tr('重置材质覆盖','Reset material overrides'),on_clicked=click(self._reset_block_material))
        self._block_extra = parent.col()
        row = self._block_extra.row()
        row.text(tr('合并方式','Merge'),size=10)
        self._block_merge = row.combo({'none':tr('不合并','No merge'),'xz':tr('水平面合并','Horizontal merge'),
                                      'xyz':tr('长方体合并','Cuboid merge')},fill=1,
                                     on_selection_changed=lambda value,_:self._set_block_value('merge',value))
        self._block_extra.text(tr('实体必须是完整、无偏移的单位立方体；植物不能合并。',
                                 'Occluding cells require an unshifted unit cube; plants cannot merge.'),size=10,wrap=True)
        self._fill_block_options()

    def _block_choices(self):
        names = dict.fromkeys((*self.pack.blocks,*self.draft.data['blocks']))
        query = getattr(self,'_block_search','').strip().lower()
        return {name:name for name in names if query in name.lower() or name == self._block_id}

    def _search_blocks(self, text):
        self._block_search = str(text)
        if hasattr(self,'_block_choice'):
            from .ui_choices import refresh_choice
            suspended, self._suspend = self._suspend, True
            try:
                refresh_choice(self._block_choice,self._block_choices(),self._block_id)
            finally:
                self._suspend = suspended

    def _fill_block_options(self):
        suspended, self._suspend = self._suspend, True
        try:
            item = self.draft.block(self._block_id)
            options = self._block_options
            kind,value = next(iter(item['source'].items()))
            self._block_title.set_text('ID '+self._block_id)
            self._block_source.set_selected_option(kind)
            self._block_usage.set_selected_option(item['shape'])
            self._block_merge.set_selected_option(item['merge'])
            options.IsBuiltin,options.IsJSON,options.IsMesh = kind=='builtin',kind=='json',kind=='mesh'
            options.Builtin = value if kind=='builtin' else ''
            options.JSON = unreal.FilePath(file_path=value if kind=='json' else '')
            options.Mesh = unreal.load_asset(value) if kind=='mesh' else None
            material = item.get('material',{})
            options.OverrideEmission,options.Emission = 'emission' in material,material.get('emission',.1)
            options.OverrideLighting,options.Lighting = 'lighting' in material,material.get('lighting',1.)
            options.OverrideColor = bool(item.get('color'))
            options.Color = unreal.LinearColor(*preview_color_linear(item.get('color') or '#FFFFFF'),1)
            # Panel fields use UE axes in blocks; pack files keep MC axes.
            options.Offset = unreal.Vector(*to_ue(item.get('offset',(0,0,0)),1).tolist())
            options.Scale = unreal.Vector(*to_ue(item.get('scale',(1,1,1)),1).tolist())
            options.Occludes = item['occludes']
            options.ShowGeometry = self._block_advanced
            self._block_extra.hide(not self._block_advanced)
        finally:
            self._suspend = suspended

    def _block_source_kind(self, kind, _reason=None):
        if self._suspend:
            return
        options = self._block_options
        self._suspend = True
        try:
            options.IsBuiltin,options.IsJSON,options.IsMesh = kind=='builtin',kind=='json',kind=='mesh'
        finally:
            self._suspend = False
        self._block_options_changed({'builtin':'Builtin','json':'JSON','mesh':'Mesh'}[kind])

    def _set_block_value(self, name, value):
        def change():
            item = deepcopy(self.draft.block(self._block_id))
            if value is None:
                item.pop(name,None)
            else:
                item[name] = value
            parse_block(self._block_id,item,self.pack.root)
            self.draft.data['blocks'][self._block_id] = item
        self._edit(change,error_key=('block',self._block_id,name))

    def _block_options_changed(self, name):
        if self._suspend:
            return
        name = str(name)
        options = self._block_options
        if name == 'ShowGeometry':
            self._block_details(options.ShowGeometry)
            return
        if name not in ('OverrideEmission','Emission','OverrideLighting','Lighting','Color','OverrideColor',
                        'Offset','Scale','Occludes','Builtin','JSON','Mesh'):
            return
        def change():
            item = deepcopy(self.draft.block(self._block_id))
            if name in ('OverrideEmission','Emission','OverrideLighting','Lighting'):
                values = dict(item.get('material',{}))
                for key, enabled, value in (('emission',options.OverrideEmission,options.Emission),
                                            ('lighting',options.OverrideLighting,options.Lighting)):
                    if enabled:
                        values[key] = float(value)
                    else:
                        values.pop(key,None)
                if values:item['material'] = values
                else:item.pop('material',None)
            elif name in ('Color','OverrideColor'):
                if options.OverrideColor:
                    item['color'] = preview_color_hex((options.Color.r,options.Color.g,options.Color.b))
                else:item.pop('color',None)
            elif name in ('Offset','Scale'):
                value = getattr(options,name)
                item[name.lower()] = from_ue((value.x,value.y,value.z),1).tolist()
            elif name == 'Occludes':
                item['occludes'] = bool(options.Occludes)
                if not item['occludes'] and item['merge']=='xyz':
                    item['merge'] = 'none'
            elif name in ('Builtin','JSON','Mesh'):
                value = (options.Builtin if name=='Builtin' else options.JSON.file_path if name=='JSON'
                         else options.Mesh.get_path_name() if options.Mesh else '')
                if not value:
                    raise ValueError(tr('请选择有效的方块来源','Choose a valid block source'))
                source = normalize_source(value,self.pack.root)
                expected = {'Builtin':'builtin','JSON':'json','Mesh':'mesh'}[name]
                if next(iter(source)) != expected:
                    raise ValueError(tr('来源类型不匹配','Source type does not match'))
                item['source'] = source
            else:return
            parse_block(self._block_id,item,self.pack.root)
            self.draft.data['blocks'][self._block_id] = item
            if name == 'Occludes':
                suspended, self._suspend = self._suspend, True
                try:
                    self._block_merge.set_selected_option(item['merge'])
                finally:
                    self._suspend = suspended
        material = name in ('OverrideEmission','Emission','OverrideLighting','Lighting')
        if material:
            try:
                change()
                self._errors.pop(('block_material',self._block_id),None)
                self._material_changed()
            except Exception as exc:
                self._errors[('block_material',self._block_id)] = str(exc)
                self._material_changed()
                self._set_status(str(exc))
        else:
            field = 'source' if name in ('Builtin','JSON','Mesh') else name
            self._edit(change,error_key=('block',self._block_id,field))

    def _reset_block_material(self):
        if self._suspend:return
        item = deepcopy(self.draft.block(self._block_id))
        item.pop('material',None)
        self.draft.data['blocks'][self._block_id] = item
        self._errors.pop(('block_material',self._block_id),None)
        self._fill_block_options()
        self._material_changed()

    def _new_block(self, text):
        def add():
            self._block_id = self.draft.input_block(text, shape=self._block_shape,
                definition={'shape': self._block_shape, 'occludes': self._block_shape == 'cube', 'merge': 'none'})
        self._edit(add)
        from .ui_choices import refresh_choice
        suspended, self._suspend = self._suspend, True
        try:
            refresh_choice(self._block_choice, self._block_choices(), self._block_id)
            self._fill_block_options()
        finally:
            self._suspend = suspended

    def _select_block(self, name, _reason=None):
        if self._suspend or name == self._block_id:
            return
        # Invalid native input was never committed to the draft. Changing the
        # selection discards it together with its no-longer-visible error.
        for key in tuple(self._errors):
            if isinstance(key,tuple) and len(key)>1 and key[0] in ('block','block_material') and key[1]==self._block_id:
                self._errors.pop(key)
        self._block_id = name
        self._block_choice['selected'] = name
        self._fill_block_options()

    def _block_details(self, checked):
        self._block_advanced = checked
        self._block_extra.hide(not checked)

    def _block_template(self, item, name):
        def change():
            value = deepcopy(self.draft.block(self._block_id))
            value.update(shape=name,occludes=name=='cube',merge='none')
            parse_block(self._block_id,value,self.pack.root)
            self.draft.data['blocks'][self._block_id] = value
        self._edit(change)
        self._fill_block_options()

    @staticmethod
    def _condition(conditions, field, key, text):
        raw = conditions[field]
        value = deepcopy(raw) if isinstance(raw, dict) else dict(min=raw[0], max=raw[1])
        value[key] = read_bound(text)
        if key == 'jitter':
            value[key] = value[key] or 0
        conditions[field] = value
