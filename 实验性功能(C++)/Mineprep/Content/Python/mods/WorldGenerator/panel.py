"""Three-column editing workflow. Pure drafts and ops are shared with scripts."""
from copy import deepcopy
import time
import weakref

import mineprep
import unreal

from . import ops
from .adapters.preview import overview_views
from .core.pack import list_packs, load_pack, register_pack_root, catalog, pack_roots
from .core.spec import WorldSpec
from .core.data import Region
from .core.world import world_key
from .core.presets import preset_sections
from .editing import PackDraft, PreviewSchedule, WORKSPACE, fit_water_bounds
from .editor import ContentEditors, click, tr, name_text
from .props import (WorldOutput, WorldRange, WorldCustom, HeightmapTexture, CaveSlice, LandscapeView, overrides, params_group, read_params, write_params,
                    prop_name, operation_values, normalize_group, visible_properties, restore_operations)
from .storage import load_ui, save_ui, load_preferences, save_preferences, load_group, save_group, SAVED_DIR
from .ui_model import group_pages, page_id, SaveSchedule
from .preset_library import PresetLibrary, _digest
from .heightmap_source import HeightmapSource
from .heightmap_panel import HeightmapPanel
from .mask_panel import MaskPanel
from .preset_panel import PresetPanel

# The shared localization table can already contain an untranslated Blocks key.
mineprep.localize('方块', **{'zh-Hans': '方块', 'en': 'Blocks'})
# Replace cached translations as well as source labels during a live reload.
for zh, en in (('恢复默认', 'Reset'), ('保存用户资源包', 'Save Pack'),
               ('另存预设', 'Save Preset'), ('预设库', 'Preset Lib'),
               ('资源包｜', 'Pack | '), ('资源包默认', 'Pack Default')):
    mineprep.localize(zh, **{'zh-Hans': zh, 'en': en})

LIVE_INSTANCES = weakref.WeakSet()
VIEWS = {'landscape': ('景观', 'Landscape'), 'surface': ('地表方块', 'Surface blocks'),
         'vegetation': ('植被分布', 'Vegetation'), 'biomes': ('群系', 'Biomes'),
         'height': ('高度', 'Height'), 'temperature': ('温度', 'Temperature'),
         'humidity': ('湿度', 'Humidity'), 'water_system': ('水系', 'Water systems'),
         'heightmap': ('自定义高度图', 'Custom heightmap'),
         'vegetation_mask': ('植被遮罩', 'Vegetation mask'), 'clearance_mask': ('留空遮罩', 'Clearance mask'),
         'caves': ('洞穴总览', 'Cave overview'), 'cave_sections': ('精确剖面', 'Exact sections'),
         'underground_water': ('地下水', 'Underground Water')}
EXECUTIONS = {'serial': ('单线程', 'Single thread'), 'threads': ('多线程', 'Threads'),
              'processes': ('多进程', 'Processes')}
BACKEND_LABELS = {'ism': ('实例（CPU）', 'Instances (CPU)'), 'pcg': ('PCG（GPU）', 'PCG (GPU)'),
                  'niagara': ('粒子（GPU）', 'Particles (GPU)')}
PAGES = {'world': ('世界与范围', 'World & region'),
         'blocks': ('方块', 'Blocks'), 'custom': ('自定义', 'Custom'),
         'output': ('输出与性能', 'Output & performance')}
NAV_LABELS = {'world': ('世界范围', 'World region'), 'terrain': ('地形', 'Terrain'),
              'output': ('输出', 'Output')}


class WorldGenerator(MaskPanel, HeightmapPanel, PresetPanel, ContentEditors, mineprep.Mod):
    _unique_ = True
    _label_ = tr('MC世界生成器', 'MC World Generator')

    def __init__(self, context=None):
        self.range_options, self.output_options = WorldRange(), WorldOutput()
        self.custom_options, self._heightmap_result = WorldCustom(), None
        self._heightmap_texture, self._heightmap_source = HeightmapTexture(), HeightmapSource()
        self._init_masks()
        self.slice_options, self._preview_world = CaveSlice(), None
        self.landscape_options = LandscapeView()
        self._landscape_due = self._landscape_key = None
        self._overview, self._overview_textures = None, {}
        self._last_native = {id(g): operation_values(g) for g in (self.range_options, self.output_options, self.custom_options)}
        self.backend, self.merge, self.execution = 'pcg', 'cuboids', 'processes'
        self.view, self.page = 'landscape', 'world'
        self._view_revision = 0
        self._geometry_revision, self._display_versions = 0, {}
        self._reference_texture = None
        self._view_failures = set()
        self._job_kind = self._job = self._prepared = None
        self._action = self._preview_key = None
        self._textures, self._errors, self._scrolls = {}, {}, {}
        self._input_text, self._page_inputs, self._active_inputs, self._views = {}, {}, set(), {}
        self._closed = self._suspend = self._curves_pending = False
        self._schedule = PreviewSchedule()
        self._zoom, self._pan, self._drag = 1., [0., 0.], None
        self._image_shape = None
        self._ui_state, self._ui_due = load_ui(), None
        self._preferences, self._saving = load_preferences(), SaveSchedule()
        self._custom_image_type = self._preferences['custom_image_type']
        self._advanced = dict(self._preferences['advanced'])
        self._folds = dict(self._preferences['folds'])
        self._preview_hidden, self._preview_old = self._ui_state['preview_hidden'], False
        self._biome_id, self._rules_id, self._block_id = '', 'common', ''
        self._biome_search, self._expanded = '', set()
        self._block_shape, self._block_advanced = 'cube', False
        self._batches, self._new_source = {}, ''
        self._pending_switch = None
        self._recovery = False
        from .migration import upgrade_workspace
        self._upgrade_report = upgrade_workspace(WORKSPACE, roots=pack_roots())
        for error in self._upgrade_report['errors']:
            unreal.log_warning(f"WorldGenerator migration preserved {error['path']}: {error['error']}")
        if (WORKSPACE / 'packs').is_dir():
            register_pack_root(WORKSPACE / 'packs')
        pack_id = self._preferences['pack']
        if pack_id not in self._packs():
            pack_id = 'vanilla'
        try:
            self._select_pack(pack_id, self._preferences['preset'])
        except Exception as exc:
            unreal.log_warning(f'WorldGenerator remembered pack could not be loaded: {exc}')
            healthy = next((item['id'] for item in catalog() if item['status'] == 'ready'), None)
            if healthy is None:
                raise ValueError('No usable WorldGenerator packs') from exc
            self._select_pack(healthy)
        self._restore_preferences()
        self._restore_heightmap_source()
        self._restore_masks()
        self._recovery = self.draft.needs_recovery(self._session_state())
        super().__init__(context)
        LIVE_INSTANCES.add(self)
        self._tick_handle = unreal.register_slate_post_tick_callback(self._tick)
        self._heightmap_source.listen(self._heightmap_event, self._heightmap_refresh)
        self._listen_masks()
        self._update_buttons()

    def _packs(self):
        return [p for p in list_packs() if not p.startswith('wg_draft_')]

    def _page_label(self, page):
        section = next((s for s in self.pack.ui_sections if s.id == page), None)
        return name_text(section.label if section else PAGES.get(page, (page, page)))

    def _nav_label(self, page):
        return tr(*NAV_LABELS[page]) if page in NAV_LABELS else self._page_label(page)

    def _select_pack(self, pack_id, preset=None, draft=None):
        self.draft = draft or PackDraft(pack_id)
        self.pack = self.draft.pack
        self.page = page_id(self.page,self.pack)
        if self.view in ('temperature', 'humidity') and self.view not in self.pack.fields:
            self.view = 'landscape'
        self._library = PresetLibrary(pack_id=self.pack.id)
        self._library_stamp, self._preset_poll_at = self._library.stamp(), 0.
        if self.view in ('caves', 'cave_sections') and self.pack.density is None:
            self.view = 'landscape'
        if self.view == 'underground_water' and self.pack.fluids is None:
            self.view = 'landscape'
        self.preset = preset if preset in self.pack.presets and self.pack.presets[preset].section is None else self.pack.default_preset
        self.groups = {}
        schemas = {}
        for p in self.pack.pages:
            key = group_pages(self.pack, p)
            if key not in schemas:
                schemas[key] = params_group(self.pack, p)()
            self.groups[p] = schemas[key]
        for page, group in self.groups.items():
            group.ShowAdvanced = self._advanced.get(f'{self.pack.id}/{page_id(page, self.pack)}', False)
        self._apply_preset()
        self._saved_params = deepcopy(self._values())
        self._biome_id = self.draft.data['biomes'][0]['id']
        self._block_id = next(iter(self.draft.data['blocks']), '')
        self._expanded, self._errors, self._scrolls = set(), {}, {}
        self._input_text, self._page_inputs, self._views = {}, {}, {}
        self._batches, self._new_source = {}, ''

    def _baseline(self):
        return self.pack.resolve(WorldSpec(self.pack.id, self.preset)).to_dict()

    def _apply_preset(self):
        self._suspend = True
        try:
            values = self._baseline()
            for group in self.groups.values():
                write_params(group, self.pack, values)
            self._curves = {k: v for k, v in values.items() if self.pack.params[k].type == 'curve'}
            self._curves_pending = False
            for group in self.groups.values():
                self._last_native[id(group)] = read_params(group, self.pack, curves=False)
            self._global_values = deepcopy(values)
            record = self._library.get('pack:'+self.preset) if self.preset else None
            self._global_mark = dict(id='pack:'+self.preset if self.preset else '',
                                     name=record['name'] if record else '',
                                     digest=_digest(record) if record else '', values=deepcopy(values))
            sections = preset_sections(self.pack)
            self._section_marks = {page_id(d.page, self.pack): dict(id=self.preset if page_id(d.page, self.pack) in sections.get(self.preset, ()) else '',
                values={k: v for k, v in values.items() if page_id(self.pack.params[k].page, self.pack) == page_id(d.page, self.pack)})
                for d in self.pack.params.values() if page_id(d.page, self.pack) not in ('blocks', 'output')}
        finally:
            self._suspend = False

    def _values(self, pending=False):
        values = self._baseline()
        for group in self.groups.values():
            values.update(read_params(group, self.pack, curves=pending))
        if not pending:
            values.update(self._curves)
        baseline = self._baseline()
        return {**baseline, **overrides(values, baseline, self.pack)}

    def _dirty(self):
        return self.draft.dirty or self._curves_pending or bool(overrides(self._values(),self._saved_params,self.pack)) or bool(self._errors)

    def spec(self):
        if self._errors:
            raise ValueError(next(iter(self._errors.values())))
        r = self.range_options
        region = Region(int(r.Origin.x), int(r.Origin.y), int(r.Size.x), int(r.Size.y))
        values = self._values()
        fitted = fit_water_bounds(self.pack, values, region)
        if fitted:
            values.update(fitted)
            self._set_parameter_values(values, fitted)
            self._remember()
        spec = self.draft._geometry_spec(self.preset, seed=int(r.Seed),
            region=region, params=overrides(values, self._baseline(), self.pack))
        return self._custom_spec(spec)


    def apply_curves(self):
        self._schedule.curves_due = None
        try:
            values = self._values(pending=True)
            self.pack.resolve(WorldSpec(self.pack.id, self.preset, params=values))
            self._suspend = True
            for group in self.groups.values():
                write_params(group, self.pack, values)
            changed = self._curves_pending
            self._curves = {k: v for k, v in values.items() if self.pack.params[k].type == 'curve'}
            self._curves_pending = False
            self._errors.pop('curves', None)
            if changed:
                self._suspend = False
                self._changed()
            self._set_status(tr('曲线已应用；切线与插值已按生成样条重建', 'Curves applied; tangents and interpolation match the generating spline.'))
            return True
        except Exception as exc:
            self._errors['curves'] = str(exc)
            self._set_status(str(exc))
            return False
        finally:
            self._suspend = False
            self._update_buttons()

    # -- layout ------------------------------------------------------------
    def draw(self, context=None):
        self._library_form = self._library_state = None
        self._frame_height = None
        self._frame = self.layout.sizebox(height=700, align=(0, 0))
        root = self._frame.col(padding=6, align=(0, 0))
        head = root.row(padding=(0, 3))
        from . import mod_info
        head.text('v' + mod_info['Version'], size=13)
        self._pack_combo = head.combo({item['id']: unreal.Text('{name}{error}').format(
                                      name=name_text(item['name']), error=(' ⚠ ' + item['error'] if item['error'] else ''))
                                      for item in catalog() if item['id'] in self._packs()},
                   selected=self.pack.id, on_selection_changed=self._on_pack, fill=1,
                   tooltip=tr('选择生成资源包：算法、参数、群系与方块规则。',
                              'Choose a generation pack: algorithms, parameters, biomes and block rules.'))
        self._preset_slot = head.col(fill=1)
        self._render_global_preset()
        head.button(tr('恢复默认', 'Reset'), text_scaling=True, size=11, on_clicked=click(self._reset_params),
                    tooltip=tr('恢复当前资源包的全部生成参数默认值；保留种子、生成范围、输出设置及规则草稿。',
                               'Reset all pack generation defaults; keep seed, region, output settings and rule drafts.'))
        head.button(tr('保存资源包', 'Save Pack'), text_scaling=True, size=11, on_clicked=click(self._save_form),
                    tooltip=tr('保存群系、地表、方块、植被及当前参数；内置/外部资源包另存为继承资源包。',
                               'Save biomes, surfaces, blocks, vegetation and parameters. Built-in/external packs are saved as derived user packs.'))
        head.button(tr('另存预设', 'Save Preset'), text_scaling=True, size=11, on_clicked=click(lambda: self._save_form(True)),
                    tooltip=tr('直接保存生成参数到独立预设库；规则草稿保留。',
                               'Save generation parameters to the independent library; retain content drafts.'))
        head.button(tr('预设库', 'Preset Lib'), text_scaling=True, size=11, on_clicked=click(self._library_manager),
                    tooltip=tr('打开预设库：加载、管理、导入或导出参数预设。',
                               'Open the preset library to load, manage, import or export parameter presets.'))
        self._dirty_text = head.text('', size=10)
        self._notice = root.col()
        if self._recovery:
            row = self._notice.row()
            row.text(tr('找到上次会话草稿', 'Previous session draft found'), size=11, fill=1)
            row.button(tr('恢复', 'Restore'), text_scaling=True, size=11, on_clicked=click(self._restore))
            row.button(tr('放弃', 'Discard'), text_scaling=True, size=11, on_clicked=click(self._discard_session))
        columns = root.row(fill=1, align=(0, 0))
        nav = columns.sizebox(width=128, padding=(0, 2), align=(0, 0)).scrollbox(align=(0, 0), clip=True).col()
        pages = {'world': self._nav_label('world')}
        pages.update({s.id: name_text(s.label) for s in self.pack.ui_sections})
        pages.update({p: self._nav_label(p) for p in ('blocks', 'custom', 'output')})
        self._nav_buttons = {}
        for page, label in pages.items():
            self._nav_buttons[page] = nav.button(unreal.Text('{selected}{label}').format(
                       selected='● ' if page == self.page else '', label=label), text_scaling=True, size=11, padding=(1, 3),
                       tooltip=self._page_label(page), on_clicked=click(lambda p=page: self._page(p)))
        nav.spacer(12)
        self._preview_toggle = nav.button(tr('展开预览', 'Show preview') if self._preview_hidden else tr('收起预览', 'Hide preview'), text_scaling=True, size=10,
                   on_clicked=click(self._toggle_preview))
        self._splitter = columns.splitter(ratio=self._ui_state['ratio'], fill=1,
                                         padding=0, on_changed=self._on_split_changed)
        self._preview_column = self._splitter.first
        self._splitter.solo(2 if self._preview_hidden else 0)
        preview = self._preview_column.col(fill=1, padding=6, align=(0, 0))
        self._view_combo = preview.combo({k: tr(*v) for k, v in VIEWS.items()
            if (k not in ('caves', 'cave_sections') or self.pack.density is not None)
            and (k!='underground_water' or self.pack.fluids is not None)}, selected=self.view,
                      on_selection_changed=self._on_view)
        self._slice_controls = preview.col()
        self._slice_controls.prop(self.slice_options, searching=False,
                                  on_property_changed=self._on_slice_changed)
        self._slice_controls.button(tr('更新剖面', 'Update sections'), text_scaling=True, size=11,
                                    on_clicked=click(self.update_sections))
        self._slice_controls.text(tr('仅更新图像；不重新生成或准备资源',
                                     'Updates images only; keeps generated world and prepared resources.'), size=9, wrap=True)
        self._old_text = preview.text('', size=10)
        self._preview_border = preview.border(color=unreal.LinearColor(.025, .025, .025, 1), clip=True,
            fill=1, align=(0, 0), on_mouse_button_down=self._pan_start, on_mouse_button_up=self._pan_stop,
            on_mouse_move=self._pan_move)
        overlay = self._preview_border.overlay()
        self._image = overlay.image(size=unreal.Vector2D(1, 1), align=(2, 2))
        self._image.set_render_transform_pivot(unreal.Vector2D(.5, .5))
        self._image.hide(unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE)
        self._placeholder = overlay.text(tr('尚无预览\n点击“生成预览”查看当前草稿', 'No preview yet\nClick Generate preview to view this draft'), size=13, align=(2, 2))
        self._legend_text = preview.text('', size=10, wrap=True)
        self._stats_text = preview.text('', size=10, wrap=True)
        controls = preview.row()
        controls.button('-', text_scaling=True, size=12, on_clicked=click(lambda: self._zoom_by(1 / 1.25)))
        controls.button('+', text_scaling=True, size=12, on_clicked=click(lambda: self._zoom_by(1.25)))
        controls.button(tr('适应范围', 'Fit view'), text_scaling=True, size=11, on_clicked=click(self._fit))
        controls.text(tr('拖动平移', 'Drag to pan; wheel to zoom'), size=10, align=(1,2))
        self._landscape_controls = controls.col(fill=1, align=(3,2))
        self._landscape_controls.prop(self.landscape_options, 'MaxY',
                                      on_property_changed=self._on_landscape_changed)
        editor_pane = self._splitter.second.col(fill=1, padding=4, align=(0, 0))
        self._editor_header = editor_pane.col()
        self._editor_scroll = editor_pane.scrollbox(fill=1, align=(0, 0), clip=True)
        self._editor = self._editor_scroll.col()
        self._render_editor()
        actions = root.row(padding=(0, 5))
        auto = actions.checkbox(tr('自动概览', 'Auto overview'), size=11, on_check_state_changed=self._auto)
        auto.set_is_checked(self._schedule.enabled)
        actions.button(tr('生成预览', 'Generate preview'), text_scaling=True, size=12, on_clicked=click(self.preview), fill=1)
        actions.button(tr('准备资源', 'Prepare resources'), text_scaling=True, size=12, on_clicked=click(self.prepare), fill=1)
        self._place_button = actions.button(tr('放置到场景', 'Place in level'), text_scaling=True, size=12, on_clicked=click(self.place), fill=1)
        actions.button(tr('取消', 'Cancel'), text_scaling=True, size=11, on_clicked=click(self.cancel_job))
        self._status_text = root.text(tr('就绪', 'Ready'), size=10, wrap=True)
        self._on_view(self.view)
        self._update_buttons()

    def _render_editor(self):
        self._content_regions = {}
        self._rule_widgets = {}
        self._section_folds = {}
        self._bct_controls = None
        self._section_choice = None
        self._heightmap_info = self._heightmap_mode_combo = None
        self._heightmap_auto_check = self._heightmap_output = None
        self._mask_file_labels.clear()
        self._editor.clear_children()
        self._editor_header.clear_children()
        previous = self._page_inputs.get(self.page, set())
        self._active_inputs = set()
        self._suspend = True
        try:
            parent = self._editor
            self._editor_header.text(self._page_label(self.page), size=13)
            self._section_slot = self._editor_header.col()
            self._render_section_preset()
            if self.page == 'world':
                self._properties(parent, 'range', self.range_options, self._on_range)
                parent.text(tr('水平 X/Y，高度 Z；1 格 = 100 厘米', 'Horizontal X/Y, height Z; 1 block = 100 cm'), size=9)
            section = next((s for s in self.pack.ui_sections if s.id == self.page), None)
            if section:
                self._section_editor(parent, section)
            if any(d.type == 'curve' and page_id(d.page, self.pack) == self.page for d in self.pack.params.values()):
                parent.text(tr('曲线修改后自动应用，切线随生成样条重建。', 'Curve edits apply automatically; tangents follow the generating spline.'), size=10, wrap=True)
            if section and section.editor == 'biomes':
                self._biome_editor(parent)
            elif section and section.editor == 'surface':
                self._rules_editor(parent)
            elif self.page == 'blocks':
                self._blocks_editor(parent)
            elif self.page == 'custom':
                self._custom_editor(parent)
            elif self.page == 'output':
                row = parent.row()
                row.combo({n: tr(*BACKEND_LABELS[n]) for n in ops.BACKENDS}, selected=self.backend, fill=1,
                          on_selection_changed=self._on_backend)
                self._merge_combo = row.combo({'none': tr('不合并', 'No merge'), 'runs': tr('条带', 'Runs'), 'rectangles': tr('矩形', 'Rectangles'), 'cuboids': tr('长方体', 'Cuboids')}, selected=self.merge, fill=1,
                          on_selection_changed=self._on_merge)
                parent.combo({k: tr(*v) for k, v in EXECUTIONS.items()}, selected=self.execution,
                             on_selection_changed=self._on_execution)
                self._properties(parent, 'output', self.output_options, self._on_output_changed,
                                 exclude=('BCTEnabled', 'BCTCellSize', 'BCTColorMode', 'BCTPower'))
                self._bct_controls = parent.col()
                self._bct_mode_editor(self._bct_controls)
                self._properties(self._bct_controls, 'output', self.output_options, self._on_output_changed,
                                 exclude=('OutputName', 'Offset', 'ISMChunkCount', 'GPUTypeGroupCount', 'Workers', 'Budgets', 'BCTColorMode'),
                                 key='output_bct')
                self._output_info = parent.text('', size=11)
                self._refresh_output_editor()
            self._advanced_footer(parent)
            self._editor_scroll.set_scroll_offset(self._scrolls.get(self.page, 0.))
        finally:
            for key in previous - self._active_inputs:
                self._errors.pop(key, None)
                self._input_text.pop(key, None)
            self._page_inputs[self.page] = self._active_inputs.copy()
            self._suspend = False

    def _section_editor(self, parent, section):
        if section.controls:
            for page in section.pages:
                self._properties(parent, '__controls:' + section.id, self.groups[page], self._on_changed)
                if section.shared_group:
                    break
        grouped = {p for g in section.groups for p in g.pages}
        for page in section.pages:
            if page not in grouped:
                self._properties(parent, page, self.groups[page], self._on_changed, exclude=section.controls)
        for group in section.groups:
            opened = self._folds.get(group.id, group.default_open)
            if group.fold:
                button = parent.button(unreal.Text('{state} {label}').format(
                    state='▼' if opened else '▶', label=name_text(group.label)),
                    text_scaling=True, size=11, on_clicked=click(lambda g=group: self._toggle_section(g)))
            else:
                parent.text(name_text(group.label), size=12)
            body = parent.col()
            for page in group.pages:
                self._properties(body, page, self.groups[page], self._on_changed, exclude=section.controls)
            if group.fold:
                self._section_folds[group.id] = (button, body)
                body.hide(not opened)
        if section.editor == 'features':
            for name, feature in self.draft.data['features'].items():
                if feature.get('type') == 'surface_scatter':
                    self._block_reference(parent, feature, name, 'decor')
        if section.editor == 'water' and self.draft.data['water']:
            self._block_reference(parent, self.draft.data['water'], name_text(('水面方块', 'Water block')), 'surface')

    def _toggle_section(self, group):
        self._folds[group.id] = not self._folds.get(group.id, group.default_open)
        self._remember(draft=False)
        button, body = self._section_folds[group.id]
        opened = self._folds[group.id]
        button.get_content().get_content().set_text(unreal.Text('{state} {label}').format(
            state='▼' if opened else '▶', label=name_text(group.label)))
        body.hide(not opened)

    def _properties(self, parent, page, group, callback, *, exclude=(), key=None):
        # Whitelists partition pages only. Native EditCondition attributes handle
        # interaction: changing PropertiesToShow does not rebuild Slate rows.
        key = key or page
        allowed = visible_properties(group, self.pack, page, exclude=exclude, advanced=True,
                                     show_advanced=False)
        properties = [unreal.Name(n) for n in sorted(allowed)]
        if key not in self._views:
            self._views[key] = parent.prop(group, categories=[], properties=properties, searching=False,
                                          on_property_changed=lambda name:
                                          self._native_changed(page, group, callback, name))
        else:
            view = self._views[key]
            view.remove_from_parent()
            mineprep.add_widget(parent.target, view.target)
            if getattr(view, '_wg_object', None) is not group.uobject:
                view.set_object(group.uobject)
        self._views[key]._wg_object = group.uobject
        self._views[key].hide(not allowed)

    def _refresh_output_editor(self):
        is_ism = self.backend == 'ism'
        previous, self._suspend = self._suspend, True
        try:
            for field, value in (('UIIsISM', is_ism), ('UIUsesWorkers', self.execution != 'serial')):
                if getattr(self.output_options, field) != value:
                    setattr(self.output_options, field, value)
        finally:
            self._suspend = previous
        if self.page != 'output':
            return
        split = is_ism and self._chunk_count() > 1
        self._bct_controls.hide(split)
        text = ''
        if split:
            text = tr('ISM分区时不启用群系颜色纹理', 'Biome colour texture is disabled for split ISM output')
        elif self._bct_enabled():
            size, cell = self.range_options.Size, int(self.output_options.BCTCellSize)
            text = tr('群系纹理：{width} × {height} 像素', 'Biome texture: {width} × {height} pixels').format(
                width=(int(size.x)+cell-1)//cell, height=(int(size.y)+cell-1)//cell)
        self._output_info.set_text(text)
        self._output_info.hide(not text)

    def _advanced_footer(self, parent):
        if self.page != 'output' and any(d.advanced and page_id(d.page, self.pack) == self.page for d in self.pack.params.values()):
            control = parent.checkbox(tr('显示高级参数', 'Show advanced parameters'), size=11,
                                      on_check_state_changed=self._show_advanced)
            control.set_is_checked(self._advanced.get(f'{self.pack.id}/{self.page}', False))

    def _native_changed(self, page, group, callback, name=None):
        if self._suspend:
            return
        if hasattr(group, 'ShowAdvanced') and (str(name) == 'ShowAdvanced' or
                bool(group.ShowAdvanced) != self._advanced.get(f'{self.pack.id}/{self.page}', False)):
            self._show_advanced(bool(group.ShowAdvanced))
            return
        operations = page in ('range', 'output', 'custom')
        previous = self._last_native[id(group)]
        self._suspend = True
        try:
            values = normalize_group(group, None if operations else self.pack)
            if operations:
                if page == 'custom' and values['OutputRange'] != previous['OutputRange']:
                    group.AutoOutput = False  # compound delegates may name only X/Y
                    values['AutoOutput'] = False
                self._validate_operations(group)
            else:
                self.pack.resolve(WorldSpec(self.pack.id, self.preset, params=self._values()))
            self._last_native[id(group)] = values
            self._errors.pop('native', None)
        except (ValueError, TypeError, OverflowError) as exc:
            if operations:
                for key, value in previous.items():
                    setattr(group, key, value)
            else:
                write_params(group, self.pack, previous)
            self._errors['native'] = str(exc)
            self._set_status(str(exc))
            return
        finally:
            self._suspend = False
            self._update_buttons()
        callback(name)

    def _show_advanced(self, checked):
        if self._suspend:
            return
        self._advanced[f'{self.pack.id}/{self.page}'] = bool(checked)
        self._suspend = True
        try:
            for page, group in self.groups.items():
                if page_id(page, self.pack) == self.page:
                    group.ShowAdvanced = bool(checked)
        finally:
            self._suspend = False
        self._remember(draft=False)


    def _page(self, page):
        page = page_id(page, self.pack)
        if page == self.page:
            return
        self._scrolls[self.page] = self._editor_scroll.get_scroll_offset()
        self.page = page_id(page, self.pack)
        for key, button in self._nav_buttons.items():
            label = self._nav_label(key)
            button.get_content().get_content().set_text(unreal.Text('{selected}{label}').format(
                selected='● ' if key == page else '', label=label))
        self._render_editor()
        self._remember(draft=False)

    def _toggle_preview(self):
        self._preview_hidden = not self._preview_hidden
        self._splitter.solo(2 if self._preview_hidden else 0)
        self._ui_state['preview_hidden'] = self._preview_hidden
        self._ui_due = time.monotonic() + .3
        self._preview_toggle.get_content().get_content().set_text(tr('展开预览', 'Show preview') if self._preview_hidden else tr('收起预览', 'Hide preview'))

    def _on_split_changed(self, ratio):
        self._ui_state['ratio'] = ratio
        self._ui_due = time.monotonic() + .3

    def _save_ui(self):
        self._ui_due = None
        try:
            save_ui(self._ui_state)
        except (OSError, ValueError) as exc:
            unreal.log_warning(f'WorldGenerator UI preferences were not saved: {exc}')

    def _set_status(self, text):
        if not self._closed and hasattr(self, '_status_text'):
            self._status_text.set_text(text)

    def _busy(self):
        return self._job is not None and self._job.state in ('running', 'cancelling')

    def _place_valid(self):
        if self._prepared is None or self._curves_pending or self._errors:
            return False
        p, o = self._prepared, self.output_options
        return (p.world.spec.region.cells * (p.world.params['world.y_max']-p.world.params['world.y_min']) <= int(o.Budgets.x)
                and p.instance_count <= int(o.Budgets.y)
                and self._current(p.world) and p.backend == self.backend and p.merge == self.merge
                and p.chunk_count == self._chunk_count()
                and p.type_group_count == self._type_group_count()
                and p.biome_enabled == self._bct_enabled()
                and (not self._bct_enabled() or p.biome_cell_size == int(o.BCTCellSize))
                and self._colour_current(p))

    def _update_buttons(self):
        if not self._closed and hasattr(self, '_place_button'):
            self._place_button.set_is_enabled(not self._busy() and not self._errors)
            self._dirty_text.set_text(tr('未保存 ●', 'Unsaved ●') if self._dirty() else tr('已保存', 'Saved'))
            self._old_text.set_text(tr('参考概览 · 不含树木、冰体、覆雪和洞穴', 'Reference overview · excludes trees, ice bodies, covers and caves') if self._displaying_overview() else
                tr('旧概览 · 配置已变化', 'Old overview · configuration changed') if self.view not in self._textures and self.view in self._overview_textures else
                tr('参考地表 · 完整生成中', 'Reference surface · Full generation in progress') if self.view == 'landscape' and self._reference_texture is not None and self._busy() else
                tr('旧预览 · 配置已变化', 'Old preview · configuration changed') if self._preview_old and self._textures else '')

    # -- state and auto preview -------------------------------------------
    def _vegetation_tints(self):
        return {b['id']: b.get('vegetation_tint', [1, 1, 1]) for b in self.draft.data['biomes']}

    def _vegetation_hsv(self):
        return {b['id']: b.get('vegetation_hsv', [1, 1, 1]) for b in self.draft.data['biomes']}

    def _block_materials(self):
        result = {}
        for name in dict.fromkeys((*self.pack.blocks,*self.draft.data['blocks'])):
            old = dict(self.pack.block_defs[name].material) if name in self.pack.block_defs else {}
            current = self.draft.block(name).get('material',{})
            values = {key:current.get(key) for key in old.keys() | current.keys() if old.get(key) != current.get(key)}
            if values:result[name] = values
        return result

    def _material_changed(self):
        if self._suspend or self._closed:
            return
        self._remember()
        self._refresh_preset_labels()
        self._action = None
        self._prepared = None
        if self._busy() and self._job_kind == 'prepare':
            self._job.cancel()
        self._set_status(tr('材质覆盖已更新；请重新准备资源','Material overrides updated; prepare resources again'))
        self._update_buttons()

    def _chunk_count(self):
        return int(self.output_options.ISMChunkCount) if self.backend == 'ism' else 1

    def _type_group_count(self):
        return int(self.output_options.GPUTypeGroupCount) if self.backend != 'ism' else 1

    def _bct_enabled(self):
        return bool(self.output_options.BCTEnabled) and self._chunk_count() == 1

    def _colour_current(self, prepared):
        materials = getattr(prepared,'block_materials',None)
        if materials is not None:
            current = {name:tuple(sorted(self.draft.block(name).get('material',{}).items()))
                       for name in dict.fromkeys((*self.pack.blocks,*self.draft.data['blocks']))}
            if dict(materials) != {name:values for name,values in current.items() if values}:
                return False
        if not self._bct_enabled():
            return True
        from .adapters.biome_texture import palette
        mode = self.output_options.BCTColorMode
        if prepared.biome_color_mode != mode:
            return False
        if prepared.biome_color_power != float(self.output_options.BCTPower):
            return False
        if mode == 'hsv':
            return prepared.vegetation_hsv == palette(prepared.world.pack, self._vegetation_hsv(), biome_color_mode=mode)
        return prepared.vegetation_tints == palette(prepared.world.pack, self._vegetation_tints())

    def _palette_changed(self):
        if self._suspend or self._closed:
            return
        self._remember()
        self._action = None
        self._set_status(tr('颜色已更新；下次准备仅更新群系纹理', 'Colours updated; preparation will update the biome texture'))
        self._update_buttons()

    def _changed(self):
        if self._suspend or self._closed:
            return
        self._geometry_revision += 1
        self._remember()
        self._refresh_preset_labels()
        self._schedule.changed(time.monotonic(), curves_pending=self._curves_pending)
        self._preview_old = True
        self._textures.pop('heightmap', None)
        for kind in self.mask_options:
            self._textures.pop(kind+'_mask', None)
            self._overview_textures.pop(kind+'_mask', None)
        self._reference_texture = None
        self._action = None
        self._prepared = None
        if self._busy() and self._job_kind in ('prepare', 'preview', 'view', 'sections', 'landscape', 'overview', 'heightmap', 'mask'):
            self._job.cancel()
        self._set_status(tr('曲线待自动应用', 'Curve edits will apply shortly') if self._curves_pending else tr('配置已变化', 'Configuration changed'))
        self._update_buttons()

    def _on_changed(self, name=None):
        if str(name) == 'ShowAdvanced' or self._suspend:
            return
        try:
            pending = self._values(pending=True)
            self._curves_pending = any(pending[k] != self._curves[k] for k in self._curves) or any(
                getattr(group, key.replace('.', '__')).export_text() != group._curve_text[key]
                for group in self.groups.values() for key in getattr(group, '_curve_text', {}))
        except ValueError:
            self._curves_pending = True
        self._changed()

    def _on_range(self, name=None):
        if str(name) != 'Seed':
            self._fit()
        self._changed()

    def _on_output_changed(self, name=None):
        if self._suspend:
            return
        self._action = None
        if str(name) in ('BCTEnabled', 'BCTCellSize', 'BCTColorMode', 'BCTPower', 'ISMChunkCount', 'GPUTypeGroupCount'):
            self._prepared = None
            self._schedule.revision += 1  # reject jobs started with old output settings
            if self._busy() and self._job_kind == 'prepare':
                self._job.cancel()
            self._refresh_output_editor()
        self._remember()
        self._update_buttons()
        if str(name) in ('Budgets',):
            self._set_status(tr('数量上限已变化；每次生成和放置都会重新检查', 'Limits changed; generation and placement check them each time.'))

    def _on_bct_mode(self, mode, _reason=None):
        if self._suspend or mode == self.output_options.BCTColorMode:
            return
        self.output_options.BCTColorMode = mode
        self._on_output_changed('BCTColorMode')
        if 'biome_details' in self._content_regions:
            self._refresh_content('biome_details')

    def _bct_mode_editor(self, parent):
        row = parent.row()
        row.text(tr('群系颜色模式', 'Biome colour mode'), size=11)
        row.combo({'rgb': tr('RGB倍率', 'RGB multipliers'), 'hsv': tr('HSV调整', 'HSV adjustments')},
                  selected=self.output_options.BCTColorMode, fill=1,
                  on_selection_changed=self._on_bct_mode)

    def _auto(self, checked):
        self._schedule.enabled = checked
        self._schedule.due = time.monotonic() + .3 if checked and not self._curves_pending else None

    def _tick(self, delta):
        if self._closed:
            return
        if self._schedule.curves_due is not None and time.monotonic() >= self._schedule.curves_due:
            self._schedule.curves_due = None
            if self._curves_pending:
                self.apply_curves()
        if time.monotonic() >= self._preset_poll_at:
            self._preset_poll_at = time.monotonic() + 1.
            stamp = self._library.stamp()
            if stamp != self._library_stamp:
                self._library_stamp = stamp
                self._refresh_preset_labels()
        if self._ui_due is not None and time.monotonic() >= self._ui_due:
            self._save_ui()
        prefs, draft = self._saving.ready(time.monotonic())
        if prefs:
            self._save_preferences()
        if draft and not self._recovery:
            try:
                self._checkpoint()
            except Exception as exc:
                unreal.log_warning(f'WorldGenerator session draft was not saved: {exc}')
        size = self.layout.get_local_size()
        if size.y > 250 and size.y != getattr(self, '_frame_height', None):
            self._frame_height = size.y
            self._frame.set_height_override(size.y)
        self._transform()
        cells = int(self.range_options.Size.x) * int(self.range_options.Size.y)
        if self._schedule.due is not None and cells > 512 ** 2:
            self._schedule.cancel()
            self._set_status(tr('范围超过 512²；本次请手动生成预览', 'Region exceeds 512²; generate this preview manually.'))
        if self._schedule.ready(time.monotonic(), busy=self._busy(), cells=cells):
            self._schedule.cancel()
            self.overview()
        if not self._busy() and self._action is None:
            self._ensure_view()

    # -- pack switch and storage ------------------------------------------
    def _remember(self, *, draft=True):
        if not self._suspend and not self._closed:
            self._saving.changed(time.monotonic(), draft=draft)

    def _restore_preferences(self):
        self._suspend = True
        try:
            state = self._preferences
            for label, group in (('range', self.range_options), ('output', self.output_options), ('custom', self.custom_options)):
                size = (self.range_options.Size.x, self.range_options.Size.y)
                restore_operations(group, state.get(label, {}), self._validate_operations, size=size)
                load_group(group, SAVED_DIR / f'{label}.json', self._validate_operations, size=size)
                self._last_native[id(group)] = operation_values(group)
            self.backend, self.merge, self.execution = (state[k] for k in ('backend', 'merge', 'execution'))
            page = page_id(state['page'], self.pack)
            self.page = page if page in PAGES or page in {s.id for s in self.pack.ui_sections} else 'world'
            self.view = state['view'] if state['view'] in VIEWS else 'landscape'
            selection = state.get('selection', {})
            if selection:
                try:
                    values = self.pack.resolve(WorldSpec(self.pack.id,self.preset,params=selection['params'])).to_dict()
                    self._set_parameter_values(values, values)
                    self._global_mark = selection.get('global_mark', self._global_mark)
                    self._global_values = self._global_mark.get('values',values)
                    self._section_marks = selection.get('section_marks', self._section_marks)
                    self._saved_params = deepcopy(values)
                except (KeyError,ValueError,TypeError) as exc:
                    unreal.log_warning(f'WorldGenerator remembered parameters were not restored: {exc}')
        finally:
            self._suspend = False

    def _save_preferences(self):
        # Invalid edits leave the last valid operation preferences intact.
        if self._errors:
            return
        try:
            for label, group in (('range', self.range_options), ('output', self.output_options), ('custom', self.custom_options)):
                save_group(group, SAVED_DIR / f'{label}.json', self._validate_operations)
            state = dict(pack=self.pack.id, preset=self.preset, page=self.page, view=self.view,
                         custom_image_type=self._custom_image_type,
                         range=operation_values(self.range_options), output=operation_values(self.output_options),
                         custom=operation_values(self.custom_options),
                         masks=self._mask_state(),
                         backend=self.backend, merge=self.merge, execution=self.execution,
                         advanced=self._advanced, folds=self._folds,
                         selection=dict(params=self._values(),global_mark=self._global_mark,section_marks=self._section_marks))
            save_preferences(state)
        except (OSError, ValueError) as exc:
            unreal.log_warning(f'WorldGenerator operation preferences were not saved: {exc}')

    def _validate_operations(self, group):
        from .storage import preferences
        label = 'range' if isinstance(group, WorldRange) else 'custom' if isinstance(group, WorldCustom) else 'output'
        values = {label: operation_values(group)}
        if label == 'output':
            values['range'] = operation_values(self.range_options)
        preferences(values)

    def _guard_switch(self, action):
        if not self._dirty():
            action()
            return
        self._pending_switch = action
        self._library_state = None
        self._notice.clear_children()
        row = self._notice.row()
        row.text(tr('当前草稿未保存', 'This draft has unsaved changes'), size=11, fill=1)
        row.button(tr('保存', 'Save'), text_scaling=True, size=11, on_clicked=click(self._save_form))
        row.button(tr('放弃', 'Discard'), text_scaling=True, size=11, on_clicked=click(self._accept_switch))
        row.button(tr('取消', 'Cancel'), text_scaling=True, size=11, on_clicked=click(self._cancel_switch))

    def _accept_switch(self):
        action, self._pending_switch = self._pending_switch, None
        self._notice.clear_children()
        if action:
            action()

    def _cancel_switch(self):
        self._pending_switch = None
        self._library_state = None
        self._notice.clear_children()
        self._suspend = True
        self._pack_combo.set_selected_option(unreal.Name(self.pack.id))
        self._preset_combo.set_selected_option(unreal.Name(self._global_mark['id'] or 'defaults:all'))
        self._suspend = False

    def _on_pack(self, pack_id, _reason=None):
        if not self._suspend and pack_id != self.pack.id and pack_id in self._packs():
            self._guard_switch(lambda: self._switch_pack(pack_id))

    def _switch_pack(self, pack_id):
        self.cancel_job()
        try:
            self._select_pack(pack_id)
        except Exception as exc:
            self._set_status(str(exc))
            self._suspend = True
            self._pack_combo.set_selected_option(unreal.Name(self.pack.id))
            self._suspend = False
            return
        self._changed()
        self.redraw()


    def _session_state(self):
        pending_curves = {k: getattr(group, k.replace('.', '__')).export_text()
                          for group in self.groups.values() for k in getattr(group, '_curve_text', {})}
        return dict(preset=self.preset, params=self._values(), page=self.page,
            custom_image_type=self._custom_image_type,
            section_marks=self._section_marks, global_values=self._global_values,global_mark=self._global_mark,
            pending_curves=pending_curves, curves_pending=self._curves_pending,
            input_errors=[str(error) for error in self._errors.values()],
            view=self.view, range=operation_values(self.range_options),
            output=operation_values(self.output_options),
            custom=operation_values(self.custom_options),
            masks=self._mask_state(),
            backend=self.backend, merge=self.merge, execution=self.execution)

    def _checkpoint(self):
        self.draft.checkpoint(self._session_state())

    def _restore(self):
        try:
            draft, state = PackDraft.restore()
            self._select_pack(draft.pack.id, state['preset'], draft=draft)
            for group in self.groups.values():
                write_params(group, self.pack, state['params'])
            self._curves = {k: v for k, v in state['params'].items() if self.pack.params[k].type == 'curve'}
            self._section_marks = state.get('section_marks', self._section_marks)
            self._global_values = state.get('global_values', self._global_values)
            self._global_mark = state.get('global_mark',{**self._global_mark,'values':deepcopy(self._global_values)})
            for group in self.groups.values():
                self._last_native[id(group)] = read_params(group,self.pack,curves=False)
            if state.get('curves_pending'):
                for group in self.groups.values():
                    for key in getattr(group, '_curve_text', {}):
                        curve = unreal.RuntimeFloatCurve()
                        curve.import_text(state['pending_curves'][key])
                        setattr(group, key.replace('.', '__'), curve)
                self._curves_pending = True
            for label, group in (('range', self.range_options), ('output', self.output_options), ('custom', self.custom_options)):
                from .storage import custom_values
                values = state.get(label, custom_values({}) if label == 'custom' else {})
                restore_operations(group, values, self._validate_operations,
                                   size=(self.range_options.Size.x, self.range_options.Size.y))
                self._last_native[id(group)] = operation_values(group)
            self.page, self.view = page_id(state.get('page', 'world'), self.pack), state.get('view', 'landscape')
            self.backend, self.merge, self.execution = (state.get(k, v) for k, v in
                (('backend', 'pcg'), ('merge', 'cuboids'), ('execution', 'processes')))
            self._recovery = False
            self._restore_heightmap_source()
            self._restore_masks(state.get('masks', {}))
            self._custom_image_type = state.get('custom_image_type', self._custom_image_type)
            self._changed()
            self.redraw()
            self._set_status(tr('已恢复上次会话草稿{warning}', 'Previous session draft restored{warning}').format(
                warning=tr('；上次有未完成输入，请重新检查', '; unfinished input was found; please review.') if state.get('input_errors') else ''))
        except Exception as exc:
            self._set_status(str(exc))

    def _discard_session(self):
        (WORKSPACE / 'session.json').unlink(missing_ok=True)
        self._recovery = False
        self._notice.clear_children()
        self._remember()

    # -- preview navigation -----------------------------------------------
    def _fit(self):
        self._zoom, self._pan = 1., [0., 0.]
        self._transform()

    def _zoom_by(self, factor, anchor=None):
        old = self._zoom
        zoom = min(8., max(.25, old * factor))
        if zoom == old:
            return
        if anchor is not None:
            ratio = zoom / old
            self._pan = [q - ratio * (q - p) for q, p in zip(anchor, self._pan)]
        self._zoom = zoom
        self._transform()

    def on_mouse_wheel(self, delta):
        self.layout.set_consume_mouse_wheel(unreal.ConsumeMouseWheel.WHEN_SCROLLING_POSSIBLE)
        if not delta or self._preview_hidden or not self._textures.get(self.view):
            return
        size = self._preview_border.get_local_size()
        if min(size.x, size.y) <= 0:
            return
        point = self._preview_border.get_mouse_local()
        if not (0 <= point.x < size.x and 0 <= point.y < size.y):
            return
        self.layout.set_consume_mouse_wheel(unreal.ConsumeMouseWheel.NEVER)
        self._zoom_by(1.25 ** delta, (point.x - size.x / 2, point.y - size.y / 2))

    def _transform(self):
        if not hasattr(self, '_image'):
            return
        size = self._preview_border.get_local_size()
        if min(size.x, size.y) < 1:
            return
        width, depth = self._image_shape or (int(self.range_options.Size.x), int(self.range_options.Size.y))
        state = (id(self._image), size.x, size.y, width, depth, self._zoom, *self._pan)
        if state == getattr(self, '_image_transform', None):
            return
        self._image_transform = state
        scale = min(size.x / width, size.y / depth)
        self._image.set_desired_size_override(unreal.Vector2D(width * scale, depth * scale))
        self._image.set_render_scale(unreal.Vector2D(self._zoom, self._zoom))
        self._image.set_render_translation(unreal.Vector2D(*self._pan))

    def _pan_start(self, border):
        point = border.get_mouse_local()
        self._drag = (point.x, point.y)
        return unreal.WidgetLibrary.capture_mouse(unreal.WidgetLibrary.handled(), border.target)

    def _pan_stop(self, border):
        self._drag = None
        return unreal.WidgetLibrary.release_mouse_capture(unreal.WidgetLibrary.handled())

    def _pan_move(self, border):
        if self._drag is None:
            return False
        point = border.get_mouse_local()
        self._pan[0] += point.x - self._drag[0]
        self._pan[1] += point.y - self._drag[1]
        self._drag = (point.x, point.y)
        self._transform()
        return True

    def _on_view(self, name, _reason=None):
        if getattr(self, '_sync_view', False):
            return
        if name in VIEWS:
            combo = getattr(self, '_view_combo', None)
            if combo is not None and str(combo.get_selected_option()) != name:
                self._sync_view = True
                try:
                    combo.set_selected_option(unreal.Name(name))
                finally:
                    self._sync_view = False
            changed = name != self.view
            if changed:
                self._view_revision += 1
                self._view_failures.discard((self._preview_key,name))
            self.view = name
            self._slice_controls.hide(name != 'cave_sections')
            if hasattr(self, '_landscape_controls'):
                density = self.pack.density
                self._landscape_controls.hide(name != 'landscape' or density is None or density.base != 'volume')
            self._remember(draft=False)
            texture = self._textures.get(name)
            if self._displaying_overview():
                texture = self._overview_textures[name]
            elif texture is None:
                texture = self._overview_textures.get(name)
            if name == 'landscape' and self._busy() and self._reference_texture is not None:
                texture = self._reference_texture
                if self._first_shown_seconds is None:
                    self._first_shown_seconds = time.perf_counter()-self._image_request_started
            if texture is not None:
                texture.set_editor_property('filter', unreal.TextureFilter.TF_NEAREST)
                self._image_shape = (int(texture.blueprint_get_size_x()), int(texture.blueprint_get_size_y()))
            self._image.set_brush_resource_object(texture)
            self._image.hide(unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE if texture else
                             unreal.SlateVisibility.COLLAPSED)
            self._placeholder.hide(texture is not None)
            self._transform()
            self._update_buttons()
            # A first selection must request its missing image immediately.
            # Internal redisplay (completion/reference) must not start a job
            # while the current completion handler is still publishing state.
            if not self._suspend and (changed or _reason is not None):
                self._ensure_view()

    def _ensure_view(self):
        if self.view in ('vegetation_mask','clearance_mask'):
            kind = self.view.removesuffix('_mask')
            if (not self._closed and not self._busy() and self._action is None and not self._errors
                    and self.mask_options[kind].Enabled and self.view not in self._textures
                    and (self.view,self.spec().key) not in self._view_failures):
                self._preview_mask(kind)
            return
        if self.view == 'landscape' and getattr(self, '_landscape_due', None) is not None:
            if time.monotonic() >= self._landscape_due:
                self.update_landscape()
            return
        if self.view == 'heightmap':
            if (not self._closed and not self._busy() and self._action is None and not self._errors
                    and self.custom_options.Enabled and 'heightmap' not in self._textures
                    and ('heightmap', self.spec().key) not in self._view_failures):
                self.preview_heightmap()
            return
        if (not self._closed and not self._busy() and self._action is None
                and self._overview_valid() and not self._preview_valid()):
            if (self.view not in self._overview_textures and
                    ('overview',self._overview.key,self.view) not in self._view_failures):
                self.overview()
            return
        if (self._closed or self._busy() or self._action is not None or self.view in self._textures
                or self._preview_world is None or (self._preview_key,self.view) in self._view_failures or not self._preview_valid()):
            return
        view_revision = self._view_revision
        if self.view == 'cave_sections' and getattr(self, '_sections_initialized', False):
            self.update_sections()
        elif self.view == 'landscape' and self._preview_world.pack.density is not None and self._preview_world.pack.density.base == 'volume':
            self.update_landscape()
        else:
            self._launch('view', lambda rev: ops.preview_world(self.spec(), views=self.view, **self._job_args(),
                on_done=lambda j: self._done('view', j, rev, view_revision)))

    def _on_slice_changed(self, _name=None):
        if self._suspend:
            return
        self._sections_initialized = True
        self._view_revision += 1
        self._textures.pop('cave_sections',None)
        self._view_failures.discard((self._preview_key,'cave_sections'))

    def _on_landscape_changed(self, _name=None):
        if self._suspend or self._closed or self._preview_world is None:
            return
        world = self._preview_world
        value = max(world.params['world.y_min'], min(int(self.landscape_options.MaxY), world.params['world.y_max'] - 1))
        if value != self.landscape_options.MaxY:
            self._suspend = True
            try:
                self.landscape_options.MaxY = value
            finally:
                self._suspend = False
        self._view_revision += 1
        self._view_failures.discard((self._preview_key, 'landscape'))
        self._landscape_due = time.monotonic() + .15

    def update_landscape(self):
        if self._closed or self._busy() or self._action is not None:
            return
        self._landscape_due = None
        world = self._preview_world
        if world is None or not self._preview_valid() or not self._sync_heightmap_source() or not self._current(world):
            return
        revision = self._view_revision
        self._launch('landscape', lambda rev: ops.preview_landscape(world,
                     max_y=int(self.landscape_options.MaxY),
                     on_done=lambda job: self._done('landscape', job, rev, revision)))

    def _sync_landscape_options(self, world):
        if hasattr(self, 'landscape_options') and self._landscape_key != world.key:
            self._suspend = True
            try:
                self.landscape_options.MaxY = world.params['world.y_max'] - 1
            finally:
                self._suspend = False
            self._landscape_key, self._landscape_due = world.key, None

    def _reference_done(self, stage, result, revision):
        if self._closed or not self._schedule.current(revision) or not self._current(result.world):
            return
        self._set_status(tr('载入参考预览', 'Loading reference preview'))
        started = time.perf_counter()
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        texture = unreal.RenderingLibrary.import_file_as_texture2d(world, result.images['landscape'])
        if texture is None:
            raise RuntimeError('reference preview import failed')
        self._reference_texture = texture
        self._reference_import_seconds = time.perf_counter()-started
        self._show_world(result.world)
        self._on_view(self.view)

    # -- tasks ------------------------------------------------------------
    def _on_backend(self, name, _reason=None):
        if name != self.backend:
            self._action = None
            self.backend, self._prepared = name, None
            self._remember()
            self._refresh_output_editor()
            self._update_buttons()

    def _on_merge(self, name, _reason=None):
        if name != self.merge:
            self._action = None
            self.merge, self._prepared = name, None
            self._remember()
            self._update_buttons()

    def _on_execution(self, name, _reason=None):
        if name in EXECUTIONS and name != self.execution:
            self.execution = name
            self._refresh_output_editor()
            self._remember()

    def _job_args(self):
        o = self.output_options
        revision = self._schedule.revision
        def progress(text):
            if self._schedule.current(revision):
                self._set_status(text)
        return dict(execution=self.execution, workers=int(o.Workers), max_cells=int(o.Budgets.x),
                    max_instances=int(o.Budgets.x), max_preprocess_cells=int(o.Budgets.x), on_progress=progress)

    def _launch(self, kind, start):
        if self._closed or self._busy():
            self._set_status(tr('请等待或取消当前任务', 'Wait for or cancel the current task.'))
            return
        try:
            self._schedule.cancel()
            self._job_kind = kind
            if kind in ('preview','view','sections','landscape','overview'):
                self._image_request_started = time.perf_counter()
                self._first_shown_seconds = None
                self._reference_import_seconds = 0.
            revision = self._schedule.revision
            source = getattr(self, '_heightmap_source', None)
            guards = [source.guard()] if source is not None and (self.custom_options.Enabled or kind == 'heightmap') else []
            guards += [s.guard() for k,s in self._mask_sources.items() if self.mask_options[k].Enabled]
            guards = [g for g in guards if g is not None]
            def check_inputs():
                for check in guards:
                    check()
            guard = check_inputs if guards else None
            if guard is not None:
                guard()
            self._job = start(revision)
            self._job._source_check = guard
        except Exception as exc:
            self._action = None
            self._set_status(f'{type(exc).__name__}: {exc}')
        self._update_buttons()

    def _landscape_for_action(self):
        if self.view in ('heightmap','vegetation_mask','clearance_mask'):
            suspended, self._suspend = self._suspend, True
            try:
                self._on_view('landscape')
            finally:
                self._suspend = suspended

    def preview(self):
        if self._closed or not self._sync_heightmap_source() or self._busy():
            return
        self._action = None
        self._landscape_for_action()
        if self.apply_curves():
            self._reference_texture = None
            self._view_failures.clear()
            self._launch('preview', lambda rev: ops.preview_world(self.spec(), **self._job_args(),
                         views=self.view, on_stage=lambda stage,result:self._reference_done(stage,result,rev),
                         on_done=lambda j: self._done('preview', j, rev)))

    def _overview_valid(self):
        return self._overview is not None and self._known_current(self._overview)

    def _displaying_overview(self):
        return (self._overview_valid() and self.view in self._overview_textures
                and not (self.view == 'landscape' and self._reference_texture is not None and self._busy())
                and not (self._preview_valid() and self.view in self._textures))

    def overview(self):
        if not self._sync_heightmap_source():
            return
        if (self._closed or self._busy() or self._action is not None or self._errors
                or self._curves_pending):
            return
        spec = self.spec()
        if self.view in ('vegetation_mask','clearance_mask'):
            self._preview_mask(self.view.removesuffix('_mask'))
            return
        if self.view == 'heightmap':
            self.preview_heightmap()
            return
        failed = ('overview',spec.key,self.view)
        if self.view not in overview_views(load_pack(spec.pack)):
            if failed not in self._view_failures:
                self._view_failures.add(failed)
                self._set_status(tr('此视图需要手动生成完整预览', 'Generate a full preview manually for this view.'))
            return
        if self._preview_valid() and self.view in self._textures and self._current(self._preview_world):
            self._on_view(self.view)
            return
        args = self._job_args()
        args.pop('max_instances')
        args.pop('max_preprocess_cells')  # Reference overview samples columns, not the volume.
        view = self.view
        self._launch('overview', lambda rev: ops.preview_overview(spec, views=self.view,
            overview=self._overview if self._overview_valid() else None, **args,
            on_done=lambda j: self._done('overview',j,rev,view)))

    def prepare(self):
        self._start_action('prepare')

    def place(self):
        self._start_action('place')

    def _preview_valid(self):
        try:
            return self._preview_world is not None and not self._preview_old and self._known_current(self._preview_world)
        except Exception:
            return False

    def _start_action(self, goal):
        if not self._sync_heightmap_source():
            return
        if self._closed or self._busy():
            self._set_status(tr('请等待或取消当前任务', 'Wait for or cancel the current task.'))
            return
        self._landscape_for_action()
        if self.apply_curves():
            self._action = (goal, self._schedule.revision, self.backend, self.merge)
            self._continue_action()

    def _continue_action(self, completed=None):
        action = self._action
        if action is None:
            return
        goal, revision, backend, merge = action
        if (self._closed or not self._schedule.current(revision) or self._errors or self._curves_pending
                or backend != self.backend or merge != self.merge):
            self._action = None
            return
        if completed == 'prepare':
            self._action = None
            if goal == 'place':
                self._place_prepared()
        else:
            # Always check resource dependencies; prepare_world reuses valid assets.
            self._launch('prepare', lambda rev: ops.prepare_world(self.spec(), backend=backend, merge=merge,
                         name=str(self.output_options.OutputName),
                         biome_texture=bool(self.output_options.BCTEnabled),
                         biome_cell_size=int(self.output_options.BCTCellSize),
                         biome_color_power=float(self.output_options.BCTPower),
                         max_output_instances=int(self.output_options.Budgets.y),
                         biome_color_mode=self.output_options.BCTColorMode,
                         vegetation_hsv=self._vegetation_hsv(),
                         chunk_count=self._chunk_count(), type_group_count=self._type_group_count(),
                         vegetation_tints=self._vegetation_tints(),
                         block_materials=self._block_materials(),
                         **self._job_args(), on_done=lambda j: self._done('prepare', j, rev)))

    def update_sections(self):
        if not self._sync_heightmap_source():
            return
        if self._closed or self._busy():
            return
        if self._preview_world is None or not self._preview_valid() or not self._current(self._preview_world):
            self._set_status(tr('请先生成当前世界的预览', 'Generate a preview of the current world first.'))
            return
        self._view_revision += 1
        view_revision = self._view_revision
        self._launch('sections', lambda rev: ops.preview_sections(self._preview_world,
                     at_z=self.slice_options.VerticalY, at_y=self.slice_options.HorizontalZ,
                     at_x=self.slice_options.VerticalX,
                     on_done=lambda j: self._done('sections', j, rev, view_revision)))

    def _place_prepared(self):
        if not self._sync_heightmap_source():
            return
        if not self._place_valid():
            self._set_status(tr('准备结果已过期、超出数量上限或尚未准备；请重新准备资源', 'Resources are missing, outdated or over the limit; prepare again.'))
            return
        o = self.output_options
        self._launch('place', lambda rev: ops.place_world(self._prepared,
            location=(o.Offset.x, o.Offset.y, o.Offset.z), chunk_count=self._chunk_count(), name=str(o.OutputName),
            on_progress=self._set_status, on_done=lambda j: self._done('place', j, rev)))

    def _known_current(self, world):
        """Display validity only. Request and publication boundaries still use _current."""
        return self._display_versions.get(world.key) == self._geometry_revision

    def _accept_display(self, world):
        keys = {world.key} | {w.key for w in (self._overview, self._preview_world) if w is not None}
        self._display_versions = {k: v for k, v in self._display_versions.items() if k in keys}
        self._display_versions[world.key] = self._geometry_revision

    def _current(self, world):
        try:
            spec = self.spec()
            if spec.vegetation_mask is not None or spec.clearance_mask is not None:
                if world.spec != spec:
                    return False
                from .core.masks import check_sources
                check_sources(world.pack)
                if world.pack.heightmap is not None:
                    world.pack.heightmap.source.checked()
                return world.pack.fingerprint == load_pack(spec.pack).fingerprint
            if getattr(spec, 'heightmap', None) is not None:
                data = world.pack.heightmap
                if data is None or world.spec != spec:
                    return False
                data.source.checked()  # metadata only; hashing remains on workers
                return world.pack.fingerprint == load_pack(spec.pack).fingerprint
            return world.key == world_key(spec)
        except Exception:
            return False

    def _show_world(self, world):
        labels = unreal.Text('')
        fractions = world.biome_fractions()
        for index, biome in enumerate(world.pack.biomes):
            labels = unreal.Text('{previous}{separator}{name} {fraction}').format(
                previous=labels, separator=' / ' if index else '', name=name_text(biome.name),
                fraction=f'{fractions[biome.id]:.0%}')
        s = world.stats
        self._legend_text.set_text(tr('{labels}\n高度 {low}–{high}', '{labels}\nHeight {low}–{high}').format(
            labels=labels, low=f"{s['height_min']:.1f}", high=f"{s['height_max']:.1f}"))

    def _import_images(self, images):
        self._set_status(tr('载入预览图片', 'Loading preview images'))
        started = time.perf_counter()
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        textures = {name:unreal.RenderingLibrary.import_file_as_texture2d(world,path)
                    for name,path in images.items()}
        if any(t is None for t in textures.values()):
            raise RuntimeError(tr('预览图片载入失败', 'Failed to load preview images.'))
        return textures, time.perf_counter()-started

    def _done(self, kind, job, revision, view_revision=None):
        if self._closed:
            return
        succeeded = False
        try:
            if not self._schedule.current(revision):
                return
            job.check_source()
            if job.state != 'completed':
                self._reference_texture = None
                if kind in ('view','sections','landscape'):
                    self._view_failures.add((self._preview_key,self.view))
                self._on_view(self.view)
                self._set_status(job.error or tr('已取消', 'Cancelled'))
                return
            result = job.result
            if kind == 'overview':
                if not self._current(result.overview):
                    return
                textures, import_seconds = self._import_images(result.images)
                if self._overview is None or self._overview.key != result.key:
                    self._overview_textures = {}
                self._overview, self._reference_texture = result.overview, None
                self._accept_display(result.overview)
                self._overview_textures.update(textures)
                self._show_world(result.overview)
                generation = f"{result.overview.stats['seconds']:.3f}"
                draw = f'{result.seconds:.3f}'
                import_time = f'{import_seconds:.3f}'
                total = f'{time.perf_counter()-self._image_request_started:.3f}'
                self._stats_text.set_text(tr('参考计算 {generation} 秒 · 总等待 {total} 秒（悬停查看详细统计）',
                                            'Reference {generation} s · wait {total} s (hover for details)').format(
                    generation=generation, total=total))
                self._stats_text.set_tool_tip_text(tr('详细统计\n参考计算：{generation} 秒；绘图：{draw} 秒；导入：{import_time} 秒\n本次等待：{total} 秒',
                                                      'Detailed stats\nReference: {generation} s; image: {draw} s; import: {import_time} s\nRequest wait: {total} s').format(
                    generation=generation, draw=draw, import_time=import_time, total=total))
                self._on_view(self.view)
            elif kind in ('preview', 'sections', 'view', 'landscape'):
                if not self._current(result.world):
                    return
                if kind in ('sections', 'landscape') and view_revision != self._view_revision:
                    return
                self._sync_landscape_options(result.world)
                if (kind in ('preview', 'view') and hasattr(self, 'landscape_options')
                      and self.landscape_options.MaxY != result.world.params['world.y_max'] - 1
                      and 'landscape' in result.images):
                    self._landscape_due = time.monotonic()
                textures, import_seconds = self._import_images(result.images)
                if self._preview_key != result.world.key:
                    self._textures = {}
                    self._sections_initialized = False
                self._textures.update(textures)
                if not textures:
                    self._view_failures.add((result.world.key,self.view))
                self._reference_texture = None
                self._preview_old = False
                self._preview_world = result.world
                self._preview_key = result.world.key
                self._accept_display(result.world)
                if getattr(result, 'sections', None) is not None:
                    self.slice_options.VerticalY, self.slice_options.HorizontalZ = result.sections[:2]
                    self.slice_options.VerticalX = result.sections[2] if len(result.sections) > 2 else result.world.region.x0 + result.world.region.width // 2
                    self._sections_initialized = True
                self._image_shape = (result.world.region.width, result.world.region.depth)
                self._on_view(self.view)
                if kind in ('preview', 'view'):
                    self._show_world(result.world)
                    visible = f"{result.world.stats.get('output_instances',result.world.stats['visible']):,}"
                    models = f"{result.world.stats.get('model_instances',0):,}"
                    templates = str(result.world.stats.get('model_templates',0))
                    generation = f"{result.world.stats.get('build_wall_seconds',result.world.stats['seconds']):.3f}"
                    preview = f'{result.seconds:.3f}'
                    import_time = f'{import_seconds:.3f}'
                    surface = f"{result.world.stats.get('phase_seconds',{}).get('surface_processing',result.world.stats.get('stages',{}).get('surface_processing',0.)):.3f}"
                    reference_draw = f"{result.stats.get('reference_draw_seconds',0.):.3f}"
                    reference_import = f"{getattr(self,'_reference_import_seconds',0.):.3f}"
                    first = f'{self._first_shown_seconds:.3f}' if self._first_shown_seconds is not None else '—'
                    total = f'{time.perf_counter()-self._image_request_started:.3f}'
                    self._stats_text.set_text(tr('合并前实例 {visible} · 模型 {models}（{templates} 种） · 生成 {generation} 秒 · 总等待 {total} 秒（悬停查看详细统计）',
                                                'Pre-merge instances {visible} · models {models} ({templates} types) · build {generation} s · wait {total} s (hover for details)').format(
                        visible=visible, models=models, templates=templates, generation=generation, total=total))
                    self._stats_text.set_tool_tip_text(tr('详细统计\n合并前实例：{visible}；模型：{models}；种类：{templates}\n生成流程：{generation} 秒；单图：{preview} 秒；导入：{import_time} 秒\n表面处理：{surface} 秒；参考绘图：{reference_draw} 秒；参考导入：{reference_import} 秒\n首图：{first} 秒；本次等待：{total} 秒',
                                                          'Detailed stats\nPre-merge instances: {visible}; models: {models}; types: {templates}\nGeneration flow: {generation} s; image: {preview} s; import: {import_time} s\nSurface processing: {surface} s; reference image: {reference_draw} s; reference import: {reference_import} s\nFirst image: {first} s; request wait: {total} s').format(
                        visible=visible, models=models, templates=templates, generation=generation, preview=preview,
                        import_time=import_time, surface=surface, reference_draw=reference_draw,
                        reference_import=reference_import, first=first, total=total))
            elif kind == 'prepare':
                if (not self._current(result.world) or result.backend != self.backend or result.merge != self.merge
                        or result.chunk_count != self._chunk_count()
                        or result.type_group_count != self._type_group_count()
                        or result.biome_enabled != self._bct_enabled()
                        or (result.biome_enabled and result.biome_cell_size != int(self.output_options.BCTCellSize))):
                    return
                if not self._colour_current(result):
                    self._set_status(tr('准备基底已缓存；颜色已变化，请重新准备', 'Geometry cached; colours changed, prepare again'))
                    return
                self._sync_landscape_options(result.world)
                self._prepared = result
                if self._preview_key != result.world.key:
                    self._textures = {}
                    self._sections_initialized = False
                self._preview_world, self._preview_key, self._preview_old = result.world, result.world.key, False
                self._accept_display(result.world)
                self._show_world(result.world)
                cache_state = (tr('复用完整缓存', 'full cache') if result.reused else
                               tr('复用几何基底', 'reused geometry') if result.base_reused else
                               tr('新建资源', 'fresh build'))
                visible = f'{result.visible_count:,}'
                instances = f'{result.instance_count:,}'
                seconds = f'{result.seconds:.3f}'
                merge_s = f'{result.merge_seconds:.3f}'
                self._stats_text.set_text(tr('合并前实例 {visible} → 合并后实例 {instances} · 准备 {seconds} 秒（{cache}，悬停查看详细统计）',
                                            'Pre-merge instances {visible} → merged instances {instances} · prepared in {seconds} s ({cache}, hover for details)').format(
                    visible=visible, instances=instances, seconds=seconds, cache=cache_state))
                details = tr('详细统计\n合并前实例：{visible}；合并后实例：{instances}\n准备：{seconds} 秒（合并 {merge} 秒）；状态：{cache}',
                             'Detailed stats\nPre-merge instances: {visible}; merged instances: {instances}\nPreparation: {seconds} s (merge {merge} s); state: {cache}').format(
                    visible=visible, instances=instances, seconds=seconds, merge=merge_s, cache=cache_state)
                if result.biome_enabled:
                    from .adapters.biome_texture import dimensions
                    w, h = dimensions(result.world.region, result.biome_cell_size)
                    details = unreal.Text('{text}\nBCT {width}×{height} · {build}s / {import_time}s').format(
                        text=details, width=w, height=h,
                        build=f'{result.biome_seconds:.3f}', import_time=f'{result.biome_import_seconds:.3f}')
                self._stats_text.set_tool_tip_text(details)
            else:
                self._stats_text.set_text(tr('新增 Actor {actors}；放置 {seconds} 秒',
                                            'New actors {actors}; placement {seconds} s').format(
                    actors=len(result['actors']), seconds=f"{result['seconds']:.3f}"))
                self._stats_text.set_tool_tip_text('')
            self._set_status(tr('完成', 'Completed'))
            succeeded = True
        except Exception as exc:
            self._set_status(str(exc))
        finally:
            if not succeeded:
                self._action = None
                if kind == 'overview' and self._schedule.current(revision):
                    spec = self.spec()
                    self._view_failures.add(('overview',spec.key,view_revision or self.view))
            self._update_buttons()
        if succeeded and kind in ('preview', 'prepare'):
            self._continue_action(kind)

    def cancel_job(self):
        self._landscape_due = None
        self._action = None
        self._schedule.cancel()
        self._schedule.revision += 1
        if self._busy():
            self._job.cancel()

    def destruct(self):
        if self._closed:
            return
        self._save_ui()
        self._save_preferences()
        try:
            if not self._recovery:
                self._checkpoint()
        except Exception as exc:
            unreal.log_warning(f'WorldGenerator session draft was not saved: {exc}')
        self.cancel_job()
        for source in self._mask_sources.values():
            source.close()
        self._mask_textures.clear()
        source = getattr(self, '_heightmap_source', None)
        if source is not None:
            source.close()
            self._set_heightmap_texture(None)
        handle = getattr(self, '_tick_handle', None)
        if handle:
            unreal.unregister_slate_post_tick_callback(handle)
        self._closed = True
        self._prepared, self._textures, self._preview_world = None, {}, None
        self._overview, self._overview_textures = None, {}
        LIVE_INSTANCES.discard(self)
        self._views, self._content_regions = {}, {}
        self._rule_widgets = {}
        self._bct_controls = None
        self._global_choice = self._section_choice = self._library_form = self._library_state = None
