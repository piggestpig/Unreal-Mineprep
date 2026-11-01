"""File-based biome distribution controls; preview uses the existing biome view."""
import json
from pathlib import Path
import mineprep
from mineprep import i18n
import unreal
from . import api
from .core.biome_map import MARKERS, WATER_BIOMES, palette, supported
from .core.spec import BiomeMapInput
from .editor import click
from .props import BiomeMapOptions, BiomeMapColor, operation_values, normalize_group, restore_operations
from .storage import biome_map_values
from .ui_model import preview_color_linear, preview_color_hex
from .ui_choices import choice, refresh_choice


class BiomeMapPanel:
    def _init_biome_map(self):
        self.biome_map_options = BiomeMapOptions()
        self._biome_map_stats_label = None
        self._biome_map_rows = []

    def _restore_biome_map(self, values=None):
        values = self._preferences.get('biome_map', {}) if values is None else values
        restore_operations(self.biome_map_options, biome_map_values(values),
                           lambda g: biome_map_values(operation_values(g)))
        c = self.biome_map_options
        if c.Enabled and not c.Palette.strip() and supported(self.pack):
            c.Palette = json.dumps(palette(self.pack))

    def _biome_map_spec(self, spec):
        c = self.biome_map_options
        if not c.Enabled:
            return spec
        return api.with_biome_map(spec, c.Path,
            palette=self._biome_map_palette(), tolerance=int(c.Tolerance),
            region=(int(c.Origin.x), int(c.Origin.y), int(c.Size.x), int(c.Size.y)))

    def _biome_map_palette(self):
        text = self.biome_map_options.Palette
        if not text.strip():
            return palette(self.pack)
        entries = dict(json.loads(text))
        BiomeMapInput('palette.png', api.Region(0,0,1,1), entries)
        return {color.lower(): ident for color,ident in entries.items()}

    def _biome_map_editor(self, parent):
        c = self.biome_map_options
        parent.prop(c, 'Enabled', on_property_changed=self._biome_map_changed)
        if not supported(self.pack):
            parent.text(i18n('群系图支持主世界及其派生资源包。',
                             'Biome maps support the Overworld and derived packs.'), size=10, wrap=True)
            return
        row = parent.row()
        row.button(i18n('选择群系图', 'Choose biome map'), size=11, on_clicked=click(self._biome_map_pick))
        row.button(i18n('清除', 'Clear'), size=11, on_clicked=click(self._biome_map_clear))
        for name in ('Path', 'Origin', 'Size', 'Tolerance'):
            parent.prop(c, name, on_property_changed=self._biome_map_changed)
        row = parent.row()
        row.button(i18n('使用当前世界范围', 'Use current world region'), size=11,
                   on_clicked=click(self._biome_map_rebind))
        row.button(i18n('查看群系', 'Preview biomes'), size=11, on_clicked=click(self._preview_biome_map))
        parent.text(i18n('PNG标记色通过下表指定群系；容差按每个RGB通道计算，0为精确匹配。透明、未匹配及图外区域沿用原群系。',
                         'Assign PNG marker colours below. Tolerance applies to each RGB channel; 0 matches exactly. Transparent, unmatched and outside pixels keep the original biome.'), size=10, wrap=True)
        parent.text(i18n('标记色独立于地图显示色。容差只修复小色差，不还原混色；高度和水系保持原规则。',
                         'Marker colours are independent of map display colours. Tolerance handles small colour differences, not blended categories. Height and water retain their rules.'), size=10, wrap=True)
        self._biome_map_stats_label = parent.text('', size=10, wrap=True)
        self._biome_map_stats(getattr(self, '_legend_world', None))
        parent.button(i18n('恢复默认色板', 'Reset marker palette'), size=11,
                      on_clicked=click(self._biome_map_reset_palette))
        self._biome_map_palette_box = parent.col()
        self._biome_map_mapping_editor()

    def _biome_map_mapping_editor(self):
        parent = self._biome_map_palette_box
        parent.clear_children()
        self._biome_map_rows = []
        try:
            entries = self._biome_map_palette()
        except (ValueError, TypeError) as exc:
            parent.text(str(exc), size=10, wrap=True)
            return
        choices = {b.id: self._biome_name(b.id) for b in self.pack.biomes if b.id not in WATER_BIOMES}
        for color, ident in entries.items():
            self._biome_map_mapping_row(parent, color, ident, choices)
        if choices:
            color = next((c for c in MARKERS if c not in entries), '#ffffff')
            self._biome_map_mapping_row(parent, color, next(iter(choices)), choices, new=True)

    def _biome_map_mapping_row(self, parent, color, ident, choices, *, new=False):
        item = dict(color=color, biome=ident, props=BiomeMapColor(), new=new)
        item['props'].Color = unreal.LinearColor(*preview_color_linear(color), 1)
        self._biome_map_rows.append(item)  # retain native property groups for the widgets
        row = parent.row()
        row.sizebox(140).prop(item['props'], 'Color', on_property_changed=lambda _: self._biome_map_color_changed(item))
        item['label'] = row.text(color, size=9, align=(1,2))
        item['choice'] = choice(row, {**choices, **({ident: ident} if ident not in choices else {})}, ident,
                               lambda value, _: self._biome_map_target_changed(item, value), fill=1)
        row.button(i18n('添加', 'Add') if new else i18n('删除', 'Delete'), size=10,
                   on_clicked=click(lambda: self._biome_map_mapping_action(item)))

    def _biome_map_store_palette(self, entries, *, rebuild=False):
        self.biome_map_options.Palette = json.dumps(entries, ensure_ascii=False)
        self._biome_map_changed()
        if rebuild:
            self._biome_map_mapping_editor()

    def _biome_map_color_changed(self, item):
        if self._suspend:
            return
        c = item['props'].Color
        color = preview_color_hex((c.r, c.g, c.b)).lower()
        entries = self._biome_map_palette()
        if not item['new'] and color != item['color'] and color in entries:
            self._set_status(i18n('这个标记色已存在，请选择其他颜色。', 'This marker colour already exists. Choose another colour.'))
            item['props'].Color = unreal.LinearColor(*preview_color_linear(item['color']), 1)
            return
        if not item['new']:
            self._biome_map_store_palette({color if k == item['color'] else k: v for k,v in entries.items()})
        item['color'] = color
        item['label'].set_text(color)

    def _biome_map_target_changed(self, item, ident):
        if self._suspend:
            return
        item['biome'] = ident
        item['choice']['selected'] = ident
        if not item['new']:
            entries = self._biome_map_palette()
            entries[item['color']] = ident
            self._biome_map_store_palette(entries)

    def _biome_map_mapping_action(self, item):
        entries = self._biome_map_palette()
        if item['new']:
            if item['color'] in entries:
                self._set_status(i18n('这个标记色已存在，请选择其他颜色。', 'This marker colour already exists. Choose another colour.'))
                return
            entries[item['color']] = item['biome']
        else:
            del entries[item['color']]
        self._biome_map_store_palette(entries, rebuild=True)

    def _biome_map_reset_palette(self):
        self._biome_map_store_palette(palette(self.pack), rebuild=True)

    def _refresh_biome_map_names(self):
        choices = {b.id: self._biome_name(b.id) for b in self.pack.biomes if b.id not in WATER_BIOMES}
        for item in self._biome_map_rows:
            ident = item['biome']
            refresh_choice(item['choice'], {**choices, **({ident: ident} if ident not in choices else {})}, ident)
        if self._paint_biome_choice is not None:
            refresh_choice(self._paint_biome_choice,self._paint_biome_choices(),self._paint_biome_selection())

    def _biome_map_stats(self, world):
        label = self._biome_map_stats_label
        if label is None:
            return
        data = world.stats.get('biome_map') if world is not None and self._current(world) else None
        label.hide(data is None)
        if data is not None:
            label.set_text(i18n('输入像素：已匹配 {matched}，未匹配 {unmatched}，透明 {transparent}',
                                'Input pixels: matched {matched}, unmatched {unmatched}, transparent {transparent}').format(
                matched=data['matched_pixels'], unmatched=data['unmatched_pixels'], transparent=data['transparent_pixels']))

    def _biome_map_changed(self, _name=None):
        if self._suspend:
            return
        self._errors.pop('biome_map', None)
        try:
            biome_map_values(normalize_group(self.biome_map_options))
        except (ValueError, TypeError) as exc:
            self._errors['biome_map'] = str(exc)
            self._set_status(str(exc))
            return
        self._view_failures.clear()
        c = self.biome_map_options
        if c.Enabled and not c.Palette.strip() and supported(self.pack):
            c.Palette = json.dumps(palette(self.pack))
        if self._biome_map_stats_label is not None:
            self._biome_map_stats_label.hide(True)
        self._changed()

    def _biome_map_rebind(self):
        c, r = self.biome_map_options, self.range_options
        c.Origin = unreal.IntPoint(r.Origin.x, r.Origin.y)
        c.Size = unreal.IntPoint(r.Size.x, r.Size.y)
        self._biome_map_changed()

    def _biome_map_pick(self):
        path = mineprep.askopenfilename(title=str(i18n('选择群系图', 'Choose biome map')),
                                       filetypes=[('PNG', '*.png')])
        if path:
            companion = Path(path).with_suffix('.palette.json')
            if companion.exists():
                try:
                    entries = json.loads(companion.read_text(encoding='utf-8-sig'))
                    checked = api.with_biome_map(api.spec(self.pack.id),path,palette=entries,tolerance=0)
                except (OSError,ValueError,TypeError) as exc:
                    self._set_status(str(exc))
                    return
                self.biome_map_options.Palette = json.dumps(dict(checked.biome_map.palette))
                self.biome_map_options.Tolerance = 0
                self._biome_map_mapping_editor()
            self.biome_map_options.Path = str(Path(path).resolve())
            self.biome_map_options.Enabled = True
            self._biome_map_rebind()
            self._preview_biome_map()

    def _biome_map_clear(self):
        self.biome_map_options.Path, self.biome_map_options.Enabled = '', False
        self._biome_map_changed()

    def _preview_biome_map(self):
        self._on_view('biomes')
        self.overview()
