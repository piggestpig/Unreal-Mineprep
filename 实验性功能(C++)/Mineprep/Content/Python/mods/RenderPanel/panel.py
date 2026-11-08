"""单页任务工作台，布局在 draw 中创建，任务变化仅刷新队列。"""
from copy import deepcopy
from pathlib import Path

import mineprep
import unreal
from mineprep import i18n

from . import batch, hdr, native_hdr, ops
from .presets import STATES, name_text

ACCENT = unreal.LinearColor(1.5, 3.5, 5, 1)
MUTED = unreal.LinearColor(0.65, 0.65, 0.65, 1)
KINDS = {'animation': i18n('动画', 'Animation'), 'still': i18n('静帧', 'Still'),
         'hdr': i18n('HDR JPG', 'HDR JPG')}
# Header and rows share the same fixed widths / remaining-space weights.
QUEUE_COLUMNS = ((38, 0), (None, 1.6), (120, 0), (None, 1.0),
                 (None, 1.6), (90, 0), (242, 0))


class RenderPanelHDRSettings(mineprep.PropertyGroup):
    _autosave_ = True
    SDRQuality: str = '100'
    Quality: str = '98'
    Gamma: float = (1.175, {'ClampMin': 0.001, 'UIMin': 0.1, 'UIMax': 3.0,
                           'ToolTip': '仅用于原双通道流程的风格化调色；新的双次渲染与已有图片合成均不应用。'})


RenderPanelHDRSettings.localize(tooltip='zh')


class RenderTaskSettings(mineprep.PropertyGroup):
    Sequence: unreal.LevelSequence = (None, {'DisplayThumbnail': False})
    Output: str = ''
    Frame: int = 0


class RenderPanel(mineprep.Mod):
    _unique_ = True
    _label_ = i18n('渲染输出面板', 'Render Output Panel')
    _menu_ = 'modules'

    def __init__(self, context=None):
        self.hdr_settings = RenderPanelHDRSettings()
        self.queue_settings = batch.RenderPanelQueueSettings()
        self.task_settings = RenderTaskSettings()
        self._source, self._source_kind = 'current', 'animation'
        self._snapshot, self._message = None, ''
        try:
            self.store = batch.get_store()
        except Exception as exc:
            self.store, self._message = None, str(exc)
        super().__init__(context)
        batch._panels.add(self)
        if self.store is not None:
            try:
                self._load_source()
            except Exception as exc:
                self._message = str(exc)
        self.refresh_queue()

    def destruct(self):
        batch._panels.discard(self)

    @classmethod
    def unregister(cls):
        if ops._batch_owner is not None or ops._active is not None or ops._background:
            raise RuntimeError(i18n('RenderPanel 任务正在运行，请先结束批次再重载；当前任务仍会继续'))
        super().unregister()

    def draw(self, context=None):
        layout = self.layout.col(padding=8)
        layout.text(i18n('当前任务', 'Current task'), size=13, padding=(3, 5))
        row = layout.row()
        row.text(i18n('任务', 'Task'), size=11, align=(1, 2))
        self._kind = row.sizebox(width=110).combo(KINDS, selected='animation', on_selection_changed=self._kind_changed)
        self._backend = row.sizebox(width=85).combo(['MRQ', 'MRG'], selected='MRQ',
            tooltip=i18n('MRQ：立体与分层；MRG：普通动画与单目全景。HDR JPG 固定使用 MRQ。',
                         'MRQ: stereo and layers. MRG: animation and mono panorama. HDR JPG uses MRQ.'))
        row.text(i18n('来源', 'Source'), size=11, align=(1, 2))
        self._sources = row.col(fill=1)
        self._refresh_button = row.button(i18n('采集', 'Capture'), size=11, on_clicked=self._click(self._load_source),
            tooltip=i18n('刷新参数和光标帧', 'Refresh settings and cursor frame'))
        row.button(i18n('预设', 'Presets'), size=11,
                   on_clicked=lambda: self._manage.hide(self._manage.is_visible()))
        self._manage = layout.col(hidden=True)
        row = self._manage.row()
        self._preset_name = row.textbox(hint=i18n('预设名称', 'Preset name'), fill=1)
                                        #EditorUtilityEditableTextBox不是MultiLineEditableTextBox的子类
        row.button(i18n('新建', 'New'), size=10, on_clicked=self._click(self._save_preset))
        self._preset_actions = row.row()
        self._preset_actions.button(i18n('更新', 'Update'), size=10, on_clicked=self._click(self._save_preset, True),
            tooltip=i18n('保存编辑区参数，队列副本不变。', 'Save editor settings; queued copies stay unchanged.'))
        self._preset_actions.button(i18n('改名', 'Rename'), size=10, on_clicked=self._click(self._rename_preset))
        self._preset_actions.button(i18n('删除', 'Delete'), size=10, on_clicked=self._click(self._delete_preset))
        split = layout.splitter(ratio=0.55, padding=(0, 6))
        split.first.prop(self.task_settings, 'Sequence', text=i18n('序列', 'Sequence'), on_property_changed=self._edited)
        right = split.second.col()
        right.prop(self.task_settings, 'Output', text=i18n('输出名', 'Output'), on_property_changed=self._edited)
        self._frame_row = right.row(hidden=True)
        self._frame_row.prop(self.task_settings, 'Frame', text=i18n('帧', 'Frame'), fill=1,
                             on_property_changed=self._edited)
        self._frame_row.button(i18n('光标', 'Cursor'), size=11, on_clicked=self._click(self._cursor),
                               tooltip=i18n('使用时间线光标帧', 'Use the timeline cursor frame'))
        self._summary = layout.text('', size=10, color=MUTED, wrap=True, padding=(3, 4))
        self._hdr_row = layout.row(hidden=True)
        self._quality_boxes = {'SDRQuality': [], 'Quality': []}
        self._draw_quality(self._hdr_row)
        self._hdr_row.text(i18n('双次渲染并合成', 'Two passes + compose'), size=10, color=MUTED,
            tooltip=i18n('自动切换 SDR / HDR；渲染期间保持旧面板打开。',
                         'Switches SDR/HDR automatically. Keep the legacy panel open.'))
        row = layout.row(padding=(0, 4))
        row.spacer(fill=1)
        self._render_button = row.button(i18n('立即渲染', 'Render now'), size=11,
                   on_clicked=self._click(self._render_now),
                   tooltip=i18n('直接执行，不入队、不改名；已有文件沿用覆盖规则。',
                                'Run directly without queuing or renaming; existing overwrite rules apply.'))
        self._add_button = row.button(i18n('+ 加入队列', '+ Queue'), size=11, on_clicked=self._click(self._enqueue))

        layout.border(color=unreal.LinearColor(0.15, 0.15, 0.15, 1), padding=(0, 6)).sizebox(height=1)
        row = layout.row(padding=(0, 5))
        self._queue_heading = row.text(i18n('渲染队列', 'Render queue'), size=13, fill=1, align=(1, 2))
        row.prop(self.queue_settings, 'RemoveCompleted', text=i18n('成功后移除', 'Remove on success'),
            tooltip=i18n('完整成功后移除队列项，失败或取消保留；在开始批次时固定此选项。',
                         'Remove successful queue jobs; keep failed or canceled jobs. Applied when a batch starts.'))
        self._clear_button = row.button(i18n('清除已结束', 'Clear ended'), size=11,
                                       on_clicked=self._click(batch.edit_queue, 'clear_finished'))
        self._queue_header = layout.row(padding=0)
        header = self._queue_header.row(fill=1, padding=0)
        for cell, label in zip(self._queue_cells(header),
                (i18n('启用', 'On'), i18n('输出名', 'Output'), i18n('类型 / 后端', 'Type / backend'),
                 i18n('序列', 'Sequence'), i18n('规格', 'Format'), i18n('状态', 'Status'), i18n('操作', 'Actions'))):
            cell.text(label, size=10, color=MUTED, clip=True, padding=(0, 4))
        self._queue_header.spacer(size=(8, 1), padding=0)
        self._queue_box = layout.sizebox(padding=0)
        self._queue_box.set_max_desired_height(360)
        self._queue_scroll = self._queue_box.custom(unreal.EditorUtilityScrollBox, props={
            'always_show_scrollbar': True, 'scrollbar_thickness': unreal.Vector2D(8, 8),
            'scrollbar_padding': unreal.Margin(0), 'allow_overscroll': False,
        }, align=(0, 0), padding=0, clip=True)
        self._queue_area = self._queue_scroll.col(padding=0)
        self._empty_queue = layout.text(i18n('队列为空，调整上方任务后直接入队。', 'Queue empty. Add a job above.'),
                                        size=11, color=MUTED, padding=(3, 8))
        row = layout.row(padding=(0, 6))
        self._progress = row.text('', size=10, color=MUTED, fill=1, align=(1, 2), wrap=True)
        self._stop_button = row.button(i18n('本项后停止', 'Stop after job'), size=11,
            on_clicked=self._click(batch.stop_after_current),
            tooltip=i18n('立即取消请使用 UE 渲染窗口；取消后仍会等待部分视频编码结束。'))
        self._start_button = row.button(i18n('开始队列', 'Run queue'), size=11, on_clicked=self._click(batch.run_queue))
        self._start_button.set_background_color(ACCENT)
        self._notice = layout.text('', size=10, wrap=True, color=unreal.LinearColor(1, 0.6, 0.4, 1))

        layout.border(color=unreal.LinearColor(0.15, 0.15, 0.15, 1), padding=(0, 6)).sizebox(height=1)
        self._tools_button = layout.button(i18n('+ 特殊工具', '+ Special tools'), size=11,
                                           align=(1, 2), on_clicked=self._toggle_tools)
        self._tools = layout.col(hidden=True, padding=(8, 3))
        self._tools.text(i18n('Filmic HDR 视频', 'Filmic HDR video'), size=12)
        self._filmic_button = self._tools.button(i18n('渲染 Filmic HDR 视频', 'Render Filmic HDR video'), size=11,
            align=(1, 2), on_clicked=self._click(self._render_filmic),
            tooltip=i18n('单次动画：沿用当前序列、输出名、分辨率、帧率、采样和暖场；固定 MRQ、1000/203 nit、H.265 10-bit PQ，无音频。独立目录保留 EXR，不改旧 HDR 控件。',
                         'One animation: current sequence, name, resolution, FPS, samples and warm-up. Fixed MRQ, 1000/203 nits, HEVC 10-bit PQ, no audio. Separate output keeps EXRs; legacy HDR controls stay unchanged.'))
        self._tools.text(i18n('图片工具', 'Image tools'), size=12, padding=(3, 6))
        self._draw_quality(self._tools.row())
        self._tools.button(i18n('合成已有图片'), size=11, on_clicked=self._click(self._compose_images),
                           align=(1, 2), tooltip=i18n('HDR 输入：PQ / Rec.2020，1000 nit。'))
        self._tools.button(i18n('原 HDR 流程', 'Legacy HDR'), size=11, align=(1, 2),
                           on_clicked=lambda: legacy.hide(legacy.is_visible()))
        legacy = self._tools.col(hidden=True)
        legacy.prop(self.hdr_settings, 'Gamma')
        legacy.button(i18n('渲染 HDR JPG（原流程）', key='渲染当前帧为 HDR JPG（原流程）'), size=11,
                      align=(1, 0), on_clicked=self._click(self._render_legacy))
        self._refresh_sources()
        self.refresh_queue()

    def _draw_quality(self, row):
        for label, field in (('SDR', 'SDRQuality'), ('HDR', 'Quality')):
            row.text(label, size=11, align=(1, 2))
            box = row.sizebox(width=100).spinbox(value=float(getattr(self.hdr_settings, field)),
                min=1, max=100, step=1, digits=0, on_value_changed=self._quality_callback(field))
            self._quality_boxes[field].append(box)

    def _queue_cells(self, row):
        cells = []
        for width, weight in QUEUE_COLUMNS:
            parent = row.sizebox(width=width, align=(0, 0), padding=0) if width else row
            cells.append(parent.col(fill=weight, align=(0, 2), padding=(3, 0), clip=True))
        return cells

    def _click(self, fn, *args, **kwargs):
        def clicked():
            try:
                fn(*args, **kwargs)
                self._message = ''
                self._edited(None)
            except Exception as exc:
                self._message = str(exc)
                mineprep.warn(self._message)
                self.refresh_queue()
        return clicked

    def _refresh_sources(self):
        self._sources.clear_children()
        choices = {'current': i18n('当前设置', 'Current settings')}
        if self.store:
            choices.update({p['id']: name_text(p) for p in self.store.presets})
        if self._source not in choices:
            self._source = 'current'
        self._sources.combo(choices, selected=self._source, on_selection_changed=self._source_changed)
        self._preset_actions.hide(self._source == 'current')

    def _source_changed(self, key, reason):
        self._source = key
        self._preset_actions.hide(key == 'current')
        self._click(self._load_source)()

    def _load_source(self):
        self._snapshot = None
        self._summary.set_text('')
        if self._source == 'current':
            self._check_current()
            s = ops.capture_settings()
            self._source_kind = 'animation'
            s['frame'] = ops.current_frame(s)
        else:
            preset = self.store.preset(self._source)
            s = ops._preset_settings(preset, for_editor=True) if preset.get('context') == 'current' else deepcopy(preset['settings'])
            self._source_kind = preset.get('kind', 'animation')
            self._kind.set_selected_option(self._source_kind)
            self._backend.set_selected_option(preset['backend'])
            self._preset_name.set_text(name_text(preset))
            self.hdr_settings.SDRQuality = str(s.get('sdr_quality', 100))
            self.hdr_settings.Quality = str(s.get('hdr_quality', 98))
            for field in self._quality_boxes:
                self._quality_callback(field)(float(getattr(self.hdr_settings, field)))
            if 'frame' not in s:
                s['frame'] = ops.current_frame(s)
        self._snapshot = s
        self.task_settings.Sequence = ops._sequence(s['sequence']) if s['sequence'] else None
        self.task_settings.Output = s['name']
        self.task_settings.Frame = s['frame']
        self._kind_changed(str(self._kind.get_selected_option()), None)

    def _kind_changed(self, key, reason):
        self._frame_row.hide(key == 'animation')
        self._hdr_row.hide(key != 'hdr')
        self._backend.set_is_enabled(key != 'hdr')
        if key == 'hdr':
            self._backend.set_selected_option('MRQ')
        self._edited(None)

    def _check_current(self):
        if (ops._active or {}).get('legacy_switching'):
            raise RuntimeError(i18n('HDR 切换中，请使用预设或等待当前项结束',
                                    'HDR switching: use a preset or wait for this job.'))

    def _toggle_tools(self):
        visible = self._tools.is_visible()
        self._tools.hide(visible)
        self._tools_button.children[0].set_text(i18n('+ 特殊工具', '+ Special tools') if visible
                                               else i18n('- 特殊工具', '- Special tools'))

    def _cursor(self):
        if self.task_settings.Sequence:
            self.task_settings.Frame = ops.current_frame(dict(sequence=self.task_settings.Sequence.get_path_name()))

    def _edited(self, field):
        s, sequence = self._snapshot, self.task_settings.Sequence
        if not s or not sequence:
            self._summary.set_text('')
            self.refresh_queue()
            return
        rate = sequence.get_display_rate()
        fps = int(s['fps_value']) if s['custom_fps'] == 1 else rate.numerator / rate.denominator
        kind = str(self._kind.get_selected_option())
        if kind == 'still':
            fps = rate.numerator / rate.denominator
        formats = '/'.join(label for bit, label in ((1, 'PNG'), (2, 'JPG'), (12, 'EXR')) if s['image_formats'] & bit)
        if kind == 'animation' and s['video'] == 1:
            formats = ops.encoding.CODECS[s['codec']] + ' ' + s['container'].upper()
        elif kind == 'hdr':
            formats = 'SDR + HDR → JPG'
        value = (f"{int(s['width'])} × {int(s['height'])} · {fps:g} fps · "
                 f"{int(s['spatial'])} × {int(s['temporal'])} · {formats}")
        self._summary.set_text(i18n('最近采集：{summary}', 'Last capture: {summary}').format(summary=value))
        self._summary.set_tool_tip_text(i18n('地图：{map}\n序列：{sequence}\n采样：{spatial}×{temporal}').format(
            map=s['map'], sequence=sequence.get_path_name(), spatial=int(s['spatial']), temporal=int(s['temporal'])))
        self.refresh_queue()

    def _task_data(self):
        current = self._source == 'current'
        if current:
            self._check_current()
        s = ops.capture_settings() if current else deepcopy(self._snapshot)
        if not s:
            raise ValueError(i18n('请先刷新参数或选择预设', 'Refresh settings or select a preset.'))
        sequence = self.task_settings.Sequence
        if not sequence:
            raise ValueError(i18n('请选择序列', 'Select a sequence.'))
        path = sequence.get_path_name()
        base = self._snapshot or {}
        s.update(sequence=path, name=self.task_settings.Output,
                 sequence_fallback=base.get('sequence_fallback', '') if path == base.get('sequence') else '')
        if not ops._sequence(s['sequence']).find_tracks_by_type(unreal.MovieSceneCameraCutTrack):
            if (not current and self.store.preset(self._source).get('context') == 'current'
                    and str(self._kind.get_selected_option()) == 'animation'):
                raise ValueError(i18n('指定序列没有相机切换轨道'))
            s.update(sequence=ops._TEMP_SEQUENCE, sequence_fallback='missing_camera_cut')
        frame = self.task_settings.Frame
        if s.get('sequence_fallback'):
            frame = 0
            self.task_settings.Sequence = ops._sequence(s['sequence'])
            self.task_settings.Frame = 0
        if not current and self._source_kind == 'hdr':
            s['warmup'] -= 20  # HDR 预设已含额外暖场，转换前还原。
        kind = str(self._kind.get_selected_option())
        if kind == 'hdr':
            s = hdr.capture_settings(self._hdr_options(), settings=s, frame=frame)
        elif kind == 'still':
            s = ops.still_settings(s, frame)
        ops.encoding.output_name(s['name'])
        if current:
            self._snapshot = deepcopy(s)
        return kind, 'MRQ' if kind == 'hdr' else str(self._backend.get_selected_option()), s

    def _enqueue(self):
        kind, backend, s = self._task_data()
        label = str(name_text(self.store.preset(self._source))) if self._source != 'current' else ops.encoding.output_name(s['name'])[1]
        return batch.edit_queue('enqueue_settings', label, backend, s, kind=kind,
                                preset_id=None if self._source == 'current' else self._source)

    def _render_now(self):
        ops._idle_subsystem()
        kind, backend, settings = self._task_data()
        if kind == 'hdr':
            return hdr._start_pair(settings)
        return ops._start_animation(settings, backend, kind=kind)

    def _render_filmic(self):
        ops._idle_subsystem()
        kind, _, settings = self._task_data()
        if kind != 'animation':
            raise ValueError(i18n('Filmic HDR 临时入口仅用于动画', 'Temporary Filmic HDR is for animation only.'))
        return native_hdr.render_video(settings)

    def _save_preset(self, overwrite=False):
        kind, backend, s = self._task_data()
        self._source = self.store.save_preset(str(self._preset_name.get_text()), backend, s,
            self._source if overwrite and self._source != 'current' else None, kind=kind)
        self._refresh_sources()
        self._load_source()
        self._manage.hide(True)

    def _rename_preset(self):
        self.store.rename_preset(self._source, str(self._preset_name.get_text()))
        self._refresh_sources()

    def _delete_preset(self):
        self.store.delete_preset(self._source)
        self._source = 'current'
        self._refresh_sources()
        self._snapshot = None
        self._manage.hide(True)
        self._load_source()

    def _toggle_item(self, item_id):
        def changed(value):
            self._click(batch.edit_queue, 'update_item', item_id, enabled=bool(value))()
        return changed

    def refresh_queue(self):
        if self.store is None:
            self._notice.set_text(self._message)
            for button in (self._add_button, self._render_button, self._filmic_button, self._start_button):
                button.set_is_enabled(False)
            return
        state = batch.get_state()
        busy = state['running'] or ops._active is not None
        pending = sum(item['enabled'] and item['state'] == 'pending' for item in self.store.queue)
        self._queue_heading.set_text(i18n('队列 · {count}', 'Queue · {count}').format(count=len(self.store.queue)))
        self._queue_header.hide(not self.store.queue)
        self._queue_box.hide(not self.store.queue)
        self._empty_queue.hide(bool(self.store.queue))
        offset = self._queue_scroll.get_scroll_offset()
        self._queue_area.clear_children()
        rates = {}
        for index, item in enumerate(self.store.queue):
            active = item['id'] in state['active_ids']
            s, kind = item['settings'], item.get('kind', 'animation')
            row = self._queue_area.sizebox(height=36, padding=0).row(align=(0, 0), padding=0)
            enabled, name, type_, sequence_cell, spec, status, actions_cell = self._queue_cells(row)
            check = enabled.checkbox(padding=0)
            check.set_is_checked(item['enabled'])
            check.set_is_enabled(not active)
            check.on_check_state_changed.add_callable(self._toggle_item(item['id']))
            output_name = item.get('output_name', s['name'])
            name.text(f"{index + 1}. {output_name}", size=11, clip=True,
                      tooltip=f"{output_name}\n{item['label']}", padding=0)
            type_.text(f"{KINDS[kind]} / {item['backend']}", size=10, clip=True, padding=0)
            sequence = s['sequence'].rsplit('/', 1)[-1].split('.')[0]
            sequence_cell.text(sequence, size=11, clip=True, tooltip=s['sequence'], padding=0)
            if kind == 'animation':
                if s['sequence'] not in rates:
                    asset = unreal.load_asset(s['sequence'])
                    rate = asset.get_display_rate() if asset else None
                    rates[s['sequence']] = rate.numerator / rate.denominator if rate else None
                fps = int(s['fps_value']) if s['custom_fps'] == 1 else rates[s['sequence']]
                detail = f'{fps:g} fps' if fps is not None else '—'
                tip = detail
            else:
                detail = f"F{int(s['frame'])}"
                tip = str(i18n('第 {frame} 帧', 'Frame {frame}').format(frame=s['frame']))
            specification = f"{int(s['width'])}×{int(s['height'])} · {detail}"
            spec.text(specification, size=10, clip=True,
                      tooltip=f"{int(s['width'])}×{int(s['height'])} · {tip}", padding=0)
            encoding_now = any(job.get('queue_id') == item['id'] and job.get('render_released')
                               for job in ops._background.values())
            status_text = i18n('编码中', 'Encoding') if encoding_now else STATES[item['state']]
            status.text(status_text, size=10, clip=True, tooltip=status_text, padding=0)
            actions = actions_cell.row(padding=0)
            retry = actions.sizebox(width=28, padding=(2, 0)).button('↻', size=10, padding=0, tooltip=i18n('重试', 'Retry'),
                on_clicked=self._click(batch.edit_queue, 'requeue', item['id']))
            retry.set_visibility(unreal.SlateVisibility.HIDDEN if item['state'] in ('pending', 'running', 'completed')
                                 else unreal.SlateVisibility.VISIBLE)
            for label, tip, action, args, allowed, width in (
                (i18n('复制', 'Copy'), i18n('复制任务', 'Duplicate'), 'copy_item', (), True, 60),
                ('↑', i18n('上移'), 'move_item', (-1,), not active and index > 0, 28),
                ('↓', i18n('下移'), 'move_item', (1,), not active and index < len(self.store.queue) - 1, 28),
                ('×', i18n('移除'), 'remove_item', (), not active, 28)):
                actions.sizebox(width=width, padding=(2, 0)).button(label, size=10, padding=0, tooltip=tip,
                    on_clicked=self._click(batch.edit_queue, action, item['id'], *args)).set_is_enabled(allowed)
            actions.sizebox(width=32, padding=(2, 0)).button('📁', size=10, padding=0, tooltip=i18n('打开输出目录'),
                on_clicked=self._click(self._open_output, item['id']))
            if item.get('error'):
                error = item['error']
                self._queue_area.text(error.splitlines()[0][:180], size=9, wrap=True, tooltip=error,
                                      color=unreal.LinearColor(1, 0.6, 0.4, 1))
        self._queue_scroll.set_scroll_offset(offset)
        blocked = self._source == 'current' and (ops._active or {}).get('legacy_switching', False)
        missing_sequence = bool(self._snapshot) and self.task_settings.Sequence is None
        self._add_button.set_is_enabled(not blocked and not missing_sequence)
        self._refresh_button.set_is_enabled(not blocked)
        self._render_button.set_is_enabled(not busy and ops._batch_owner is None and not blocked and not missing_sequence)
        self._filmic_button.set_is_enabled(str(self._kind.get_selected_option()) == 'animation'
            and not busy and ops._batch_owner is None and not blocked and not missing_sequence)
        self._start_button.set_is_enabled(pending > 0 and not busy and ops._batch_owner is None)
        self._stop_button.hide(not state['running'])
        self._stop_button.set_is_enabled(not state['stopping'])
        self._clear_button.set_is_enabled(any(item['state'] not in ('pending', 'running') for item in self.store.queue))
        if state['running']:
            progress = str(i18n('第 {index} / {total} 项 · {current}').format(
                index=state['index'], total=state['total'], current=state['current']))
            progress += ' · ' + state['phase'] if state['phase'] else ''
            progress += ' · ' + str(i18n('本项后停止', 'Stop after job')) if state['stopping'] else ''
        elif ops._active is not None:
            progress = state['phase'] or i18n('正在渲染…')
        else:
            progress = i18n('待渲染 {count} 项', '{count} pending').format(count=pending)
        if state['background_count']:
            progress = str(progress) + ' · ' + str(i18n('后台编码 {count}', '{count} background encodes').format(count=state['background_count']))
        self._progress.set_text(progress)
        self._notice.set_text(self._message or state['error'] or
                              (i18n('请选择带相机切换轨道的序列') if missing_sequence else ''))

    def _open_output(self, item_id):
        item = self.store.item(item_id)
        folder = (item.get('result') or {}).get('output_dir')
        if not folder:
            parent, _ = ops.encoding.output_name(item['settings']['name'])
            folder = str(Path(unreal.Paths.project_dir()).resolve() / 'Saved/MovieRenders' / parent)
        if not Path(folder).is_dir():
            raise ValueError(i18n('输出目录尚不存在：{folder}').format(folder=str(folder)))
        mineprep.startfile(folder)

    def _hdr_options(self):
        return dict(sdr_quality=int(self.hdr_settings.SDRQuality), hdr_quality=int(self.hdr_settings.Quality))

    def _quality_callback(self, field):
        def changed(value):
            quality = round(value)
            setattr(self.hdr_settings, field, str(quality))
            for box in self._quality_boxes[field]:
                if box.get_value() != quality:
                    box.set_value(quality)
        return changed

    def _render_legacy(self):
        return hdr.render_current_frame(dict(self._hdr_options(), gamma=self.hdr_settings.Gamma))

    def _compose_images(self):
        try:
            ops._idle_subsystem()
            options = self._hdr_options()
            sdr = mineprep.askopenfilename(title=str(i18n('选择 SDR 图片')),
                                           filetypes=[(str(i18n('SDR 图片')), '*.jpg *.jpeg *.png')])
            if not sdr:
                return
            hdr_path = mineprep.askopenfilename(title=str(i18n('选择已校色的 HDR 图片（PQ / Rec.2020，1000 nit）')),
                                               filetypes=[(str(i18n('HDR 图片')), '*.exr *.png *.avif *.jxl *.hdr')])
            if not hdr_path:
                return
            output = mineprep.asksaveasfilename(title=str(i18n('保存 HDR 增益图 JPG')), defaultextension='.jpg',
                initialfile=Path(sdr).stem + '_HDR.jpg', filetypes=[(str(i18n('JPEG 图片')), '*.jpg *.jpeg')])
            if output:
                hdr.compose_images(sdr, hdr_path, output, options)
        except Exception as exc:
            mineprep.warn(str(exc))
