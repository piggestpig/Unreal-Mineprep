"""Heightmap editor controls and source-owned preview flow."""
from pathlib import Path
import mineprep
import unreal
from . import ops
from .core.data import Region
from .editor import click, tr
from .props import operation_values


class HeightmapPanel:
    def _custom_spec(self, spec, *, force=False):
        from .api import with_heightmap
        if hasattr(self, 'mask_options'):
            spec = self._mask_spec(spec)
        c = self.custom_options
        if not (c.Enabled or force):
            return spec
        return with_heightmap(spec, str(c.Path), mode=str(c.Mode),
            region=Region(int(c.Origin.x), int(c.Origin.y), int(c.Size.x), int(c.Size.y)),
            input_range=(c.InputRange.x, c.InputRange.y),
            output_range=None if c.AutoOutput else (c.OutputRange.x, c.OutputRange.y))

    def _heightmap_editor(self, parent):
        from .core.heightmap import supported
        if not supported(self.pack):
            parent.text(tr('当前资源包未保留vanilla高度链，不能接入高度图。',
                           'This pack does not retain the vanilla height chain.'), size=11, wrap=True)
            return
        c = self.custom_options
        def changed(name):
            self._native_changed('custom', c, self._on_custom_changed, name)
        parent.prop(c, 'Enabled', on_property_changed=changed)
        row = parent.row()
        row.button(tr('选择高度图', 'Choose heightmap'), size=11,
                   on_clicked=click(self._heightmap_pick))
        row.button(tr('清除', 'Clear'), size=11, on_clicked=click(self._heightmap_clear))
        parent.prop(self._heightmap_texture, 'Texture', on_property_changed=self._heightmap_texture_changed,
            tooltip=tr('彩色输入取R通道。PNG按位深归一化，EXR保留格数。',
                       'Colour inputs use red. PNG normalizes by bit depth; EXR keeps block values.'))
        self._heightmap_mode_combo = parent.combo({'faithful': tr('直接使用高度图', 'Use heightmap directly'),
                      'add': tr('叠加到主地形', 'Add to terrain')}, selected=self.custom_options.Mode,
                     on_selection_changed=self._heightmap_mode)
        for name in ('Origin', 'Size'):
            parent.prop(c, name, on_property_changed=changed,
                tooltip=tr('图片覆盖范围固定，改变世界范围不会拉伸图片。',
                           'Image mapping stays fixed when the world region changes.'))
        row = parent.row()
        row.button(tr('使用当前世界范围', 'Use current world region'), size=11,
                   on_clicked=click(self._heightmap_rebind))
        row.button(tr('查看图像', 'Preview image'), size=11,
                   on_clicked=click(lambda: self._on_view('heightmap', 'selected')))
        opened = self._folds.get('custom_mapping', False)
        parent.button(('▼ ' if opened else '▶ ') + str(tr('数值映射', 'Value mapping')), size=11,
                      on_clicked=click(self._toggle_custom_mapping))
        if opened:
            mapping = parent.col()
            mapping.prop(c, 'InputRange', on_property_changed=changed,
                tooltip=tr('PNG归一化到0～1；EXR保留原值。按输入／输出范围线性映射，范围外线性外推。',
                           'PNG normalizes to 0–1; EXR keeps raw values. Mapping is linear and extrapolates.'))
            self._heightmap_auto_check = mapping.checkbox(tr('自动输出范围', 'Automatic output range'), size=11,
                on_check_state_changed=self._heightmap_auto_output,
                tooltip=tr('归一化输入使用世界高度范围；浮点EXR保留原高度。关闭后手动指定输出范围。',
                           'Normalized input uses world height bounds; floating EXR preserves heights. Disable to set output bounds.'))
            self._heightmap_output = mapping.prop(c, 'OutputRange', text=tr('输出范围（格）', 'Output range (blocks)'),
                on_property_changed=changed, tooltip=tr('叠加模式下，负值降低地形。', 'Negative additions lower terrain.'))
        self._heightmap_info = parent.text('', size=10, wrap=True)
        self._refresh_heightmap_editor()
        parent.text(tr('「直接使用高度图」按图中高度生成地形；「叠加到主地形」在原地形上增减高度。',
                       '“Use heightmap directly” applies image heights; “Add to terrain” offsets the base terrain.'), size=10, wrap=True)

    def _heightmap_auto_output(self, checked):
        if not self._suspend:
            self.custom_options.AutoOutput = checked
            self._native_changed('custom', self.custom_options, self._on_custom_changed, 'AutoOutput')

    def _refresh_heightmap_editor(self, *, result=None):
        info_text = getattr(self, '_heightmap_info', None)
        if info_text is None:
            return
        previous = self._suspend
        self._suspend = True
        try:
            self._heightmap_mode_combo.set_selected_option(self.custom_options.Mode)
            if self._heightmap_auto_check is not None:
                self._heightmap_auto_check.set_is_checked(self.custom_options.AutoOutput)
                self._heightmap_output.set_is_enabled(not self.custom_options.AutoOutput)
        finally:
            self._suspend = previous
        result = result or self._heightmap_result
        info_text.hide(result is None)
        if result is not None:
            from dataclasses import replace
            data = replace(result.data, config=self._custom_spec(self.spec(), force=True).heightmap)
            info = data.info(self.pack.resolve(self.spec()))
            if self.custom_options.AutoOutput:
                self._suspend = True
                try:
                    self.custom_options.OutputRange = unreal.Vector2D(*info['output_range'])
                    self._last_native[id(self.custom_options)] = operation_values(self.custom_options)
                finally:
                    self._suspend = previous
            info_text.set_text(tr('文件 {width}×{depth}，{dtype}；读入 {low}～{high}\n映射 {mapped_low}～{mapped_high} 格{clip}',
                           'File {width}×{depth}, {dtype}; input {low}–{high}\nMapped {mapped_low}–{mapped_high} blocks{clip}').format(
                width=info['width'], depth=info['depth'], dtype=info['dtype'],
                low=f"{info['input_min']:.3f}", high=f"{info['input_max']:.3f}",
                mapped_low=f"{info['mapped_min']:.3f}", mapped_high=f"{info['mapped_max']:.3f}",
                clip=tr('；超出世界高度将裁切', '; world height bounds will clip') if info['clipped'] else ''))

    def _heightmap_rebind(self):
        c, r = self.custom_options, self.range_options
        c.Origin = unreal.IntPoint(r.Origin.x, r.Origin.y)
        c.Size = unreal.IntPoint(r.Size.x, r.Size.y)
        self._on_custom_changed()

    def _heightmap_pick(self):
        path = mineprep.askopenfilename(title='高度图 / Heightmap',
                                       filetypes=[('Heightmap', '*.png *.exr')])
        if not path:
            return
        self._heightmap_source.clear()
        self._set_heightmap_texture(None)
        self.custom_options.SourceKind, self.custom_options.AssetPath = 'file', ''
        self.custom_options.Path = str(Path(path).resolve())
        self.custom_options.Enabled = True
        self._heightmap_rebind()
        self._on_view('heightmap')
        self.preview_heightmap(force=True)

    def _set_heightmap_texture(self, texture):
        previous = self._suspend
        self._suspend = True
        try:
            self._heightmap_texture.Texture = texture
        finally:
            self._suspend = previous

    def _restore_heightmap_source(self):
        self._heightmap_source.clear()
        c = self.custom_options
        texture = unreal.load_asset(c.AssetPath) if c.SourceKind == 'asset' else None
        self._heightmap_source.asset_path = c.AssetPath if c.SourceKind == 'asset' else ''
        self._set_heightmap_texture(texture)
        if c.SourceKind == 'asset' and texture is None:
            if c.Enabled:
                self._errors['heightmap'] = str(tr('高度图资产缺失；请重新选择', 'Heightmap asset missing; select it again'))

    def _heightmap_texture_changed(self, _name=None):
        if self._suspend or self._closed:
            return
        texture = self._heightmap_texture.Texture
        if texture == self._heightmap_source.texture and self.custom_options.SourceKind == 'file':
            return  # The file's own transient object is never passed to an exporter.
        if texture is None:
            self._heightmap_clear()
            return
        self._heightmap_source.clear()
        c = self.custom_options
        c.SourceKind, c.AssetPath, c.Path, c.Enabled = 'asset', texture.get_path_name(), '', True
        self._heightmap_source.texture = texture
        self._heightmap_rebind()
        if not self._sync_heightmap_source():
            return
        self._on_view('heightmap')
        self.preview_heightmap(force=True)

    def _sync_heightmap_source(self, *, force=False):
        if hasattr(self, 'mask_options') and not self._sync_masks():
            return False
        c = self.custom_options
        source = getattr(self, '_heightmap_source', None)
        if source is None or c.SourceKind != 'asset' or not (c.Enabled or force):
            return True
        try:
            previous = source.identity
            path = source.resolve(c.AssetPath)
            if path != c.Path or (previous is not None and previous != source.identity):
                c.Path = path
                self._on_custom_changed()
            self._set_heightmap_texture(source.texture)
            self._errors.pop('heightmap', None)
            return True
        except Exception as exc:
            self._on_custom_changed()
            self._errors['heightmap'] = str(exc)
            self._set_status(str(exc))
            self._on_view('heightmap')
            return False

    def _heightmap_event(self):
        if self._closed or not self.custom_options.Enabled:
            return False
        self._on_custom_changed()
        self._schedule.cancel()  # Import notifications never schedule a world overview.
        self._errors['heightmap'] = str(tr('高度图来源已变化，正在刷新', 'Heightmap source changed; refreshing'))
        self._on_view('heightmap')
        return True

    def _heightmap_refresh(self):
        if not self._closed and self._sync_heightmap_source():
            self._schedule.cancel()
            self.preview_heightmap()

    def _heightmap_clear(self):
        source = getattr(self, '_heightmap_source', None)
        if source is not None:
            source.clear()
            self._set_heightmap_texture(None)
        self.custom_options.Path = ''
        self.custom_options.AssetPath, self.custom_options.SourceKind = '', 'file'
        self.custom_options.Enabled = False
        self._on_custom_changed()
        if hasattr(self, '_on_view'):
            self._on_view('landscape')

    def _heightmap_mode(self, name, _reason=None):
        if not self._suspend and name != self.custom_options.Mode:
            self.custom_options.Mode = name
            self._on_custom_changed('Mode')

    def _on_custom_changed(self, name=None):
        if self._suspend:
            return
        self._errors.pop('heightmap', None)
        # Mapping edits can display the current automatic range from the frozen
        # input immediately. Source selection/refresh (no name) discards it.
        result = self._heightmap_result if name is not None else None
        self._heightmap_result = None
        self._textures.pop('heightmap', None)
        self._overview_textures.pop('heightmap', None)
        self._view_failures.clear()
        self._last_native[id(self.custom_options)] = operation_values(self.custom_options)
        self._changed()
        self._refresh_heightmap_editor(result=result)

    def preview_heightmap(self, *, force=False):
        if self._closed or not self._sync_heightmap_source(force=force) or self._busy():
            return
        if not self.custom_options.Path or not (self.custom_options.Enabled or force):
            self._set_status(tr('请选择并启用高度图', 'Choose and enable a heightmap'))
            return
        self._errors.pop('heightmap', None)
        spec = self._custom_spec(self.spec(), force=force)
        snapshot = self._heightmap_result
        if snapshot is not None:
            try:
                snapshot.data.source.checked()
            except Exception:
                snapshot = None
        if snapshot is None:
            from types import SimpleNamespace
            for world in (self._preview_world, self._overview):
                if world is not None and self._current(world) and world.pack.heightmap is not None:
                    snapshot = SimpleNamespace(spec=world.spec, key=world.key, data=world.pack.heightmap)
                    break
        self._launch('heightmap', lambda rev: ops.preview_heightmap(spec, snapshot=snapshot,
            max_cells=int(self.output_options.Budgets.x), on_progress=self._set_status,
            on_done=lambda job: self._heightmap_done(job, rev, force)))

    def _heightmap_done(self, job, revision, select_input=False):
        try:
            if self._closed or not self._schedule.current(revision):
                return
            if job.state != 'completed':
                self._view_failures.add(('heightmap', self.spec().key))
                self._errors['heightmap'] = str(job.error or tr('已取消', 'Cancelled'))
                self._set_status(job.error or tr('已取消', 'Cancelled'))
                self._on_view('heightmap')
                return
            result = job.result
            if result.spec != self._custom_spec(self.spec(), force=True):
                return
            job.check_source()
            if self.custom_options.SourceKind == 'file':
                texture = self._heightmap_source.import_file(self.custom_options.Path, result.data.source)
                self._set_heightmap_texture(texture)
            textures, imported = self._import_images(result.images)
            job.check_source()
            self._heightmap_result = result
            self._textures.update(textures)
            self._legend_text.set_text(tr('高度图输入：{low}～{high} 格（{mode}）',
                                         'Heightmap input: {low}–{high} blocks ({mode})').format(
                low=f"{result.info['mapped_min']:.3f}", high=f"{result.info['mapped_max']:.3f}",
                mode=tr('绝对高度', 'absolute') if result.spec.heightmap.mode == 'faithful' else tr('增量', 'delta')))
            self._stats_text.set_text(tr('读取／映射／绘图 {seconds} 秒；导入 {imported} 秒',
                                        'Read / map / image {seconds} s; import {imported} s').format(
                seconds=f'{result.seconds:.3f}', imported=f'{imported:.3f}'))
            self._refresh_heightmap_editor()
            self._on_view('heightmap' if select_input else self.view)
            self._schedule.cancel()
            self._set_status(tr('高度图就绪', 'Heightmap ready'))
        except Exception as exc:
            self._textures.pop('heightmap', None)
            self._heightmap_result = None
            self._errors['heightmap'] = str(exc)
            self._set_status(f'{type(exc).__name__}: {exc}')
        finally:
            if self._job is job:
                self._job = None
            self._update_buttons()
