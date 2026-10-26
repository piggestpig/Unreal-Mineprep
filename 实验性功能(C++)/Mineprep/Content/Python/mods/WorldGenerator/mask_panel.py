"""Two compact input editors sharing heightmap texture ownership and jobs."""
from pathlib import Path
import mineprep
import unreal
from . import api, ops
from .editor import click, tr
from .props import MaskOptions, HeightmapTexture, operation_values, normalize_group, restore_operations
from .heightmap_source import HeightmapSource
from .storage import mask_values

LABELS = {'vegetation': ('植被分布', 'Vegetation distribution'), 'clearance': ('留空区域', 'Clear areas')}
CUSTOM_IMAGES = {'heightmap': ('高度图', 'Heightmap'), **LABELS}


class MaskPanel:
    def _init_masks(self):
        self.mask_options = {k: MaskOptions() for k in LABELS}
        self._mask_textures = {k: HeightmapTexture() for k in LABELS}
        self._mask_sources = {k: HeightmapSource('/'.join(LABELS[k])) for k in LABELS}
        self._mask_file_labels = {}

    def _listen_masks(self):
        for kind, source in self._mask_sources.items():
            def callbacks(kind):
                def invalidate():
                    if self._closed or not self.mask_options[kind].Enabled:
                        return False
                    self._mask_changed(kind)
                    self._schedule.cancel()
                    return True
                def refresh():
                    if not self._closed and self._sync_masks():
                        self._schedule.cancel()
                        self._preview_mask(kind)
                return invalidate, refresh
            source.listen(*callbacks(kind))

    def _mask_spec(self, spec):
        for kind, c in self.mask_options.items():
            if c.Enabled:
                spec = getattr(api, 'with_'+kind+'_mask')(spec, str(c.Path),
                    region=(int(c.Origin.x), int(c.Origin.y), int(c.Size.x), int(c.Size.y)))
        return spec

    def _custom_editor(self, parent):
        row = parent.row()
        for kind, label in CUSTOM_IMAGES.items():
            button = row.button(tr(*label), size=11, fill=1, text_scaling=True,
                on_clicked=click(lambda k=kind: self._select_custom_image(k)),
                tooltip=tr('切换编辑项，不改变启用状态。', 'Switch editors without changing enabled inputs.'))
            if kind == self._custom_image_type:
                style = button.get_editor_property('widget_style')
                style.normal.tint_color.specified_color = unreal.LinearColor(.08, .20, .30, 1)
                style.hovered.tint_color.specified_color = unreal.LinearColor(.10, .26, .36, 1)
                button.set_style(style)
        if self._custom_image_type == 'heightmap':
            self._heightmap_editor(parent)
        else:
            self._mask_editor(parent, self._custom_image_type)

    def _select_custom_image(self, kind):
        if kind == self._custom_image_type:
            return
        self._custom_image_type = kind
        self._scrolls['custom'] = 0.
        self._render_editor()
        self._remember(draft=False)

    def _toggle_custom_mapping(self):
        self._folds['custom_mapping'] = not self._folds.get('custom_mapping', False)
        self._scrolls['custom'] = self._editor_scroll.get_scroll_offset()
        self._render_editor()
        self._remember(draft=False)

    def _mask_editor(self, parent, kind):
        c = self.mask_options[kind]
        parent.prop(c, 'Enabled', on_property_changed=lambda name: self._mask_changed(kind))
        row = parent.row()
        row.button(tr('选择遮罩', 'Choose mask'), size=11, on_clicked=click(lambda: self._mask_pick(kind)))
        row.button(tr('清除', 'Clear'), size=11, on_clicked=click(lambda: self._mask_clear(kind)))
        parent.prop(self._mask_textures[kind], 'Texture', on_property_changed=lambda name: self._mask_texture_changed(kind),
            tooltip=tr('PNG按位深归一化，EXR使用0～1原值；彩色输入取R通道。',
                       'PNG normalizes by bit depth; EXR uses values from 0 to 1. Colour inputs use red.'))
        self._mask_file_labels[kind] = parent.text(str(c.Path), size=10, wrap=True)
        self._mask_file_labels[kind].hide(not bool(c.Path))
        for name in ('Origin', 'Size'):
            parent.prop(c, name, on_property_changed=lambda name: self._mask_changed(kind),
                tooltip=tr('图片覆盖范围固定，改变世界范围不会拉伸图片。',
                           'Image mapping stays fixed when the world region changes.'))
        row = parent.row()
        row.button(tr('使用当前世界范围', 'Use current world region'), size=11,
                   on_clicked=click(lambda: self._mask_rebind(kind)))
        row.button(tr('查看图像', 'Preview image'), size=11, on_clicked=click(lambda: self._preview_mask(kind)))
        parent.text(tr('白色保持原有密度，黑色不生成，灰色减少植物。',
                       'White keeps existing density; black removes plants; grey reduces density.') if kind=='vegetation'
                    else tr('白色区域不生成植物和零散景物，树冠也会避让。',
                            'White areas exclude plants and small scenery, including overhanging crowns.'), size=10, wrap=True)

    def _mask_state(self):
        return {k: operation_values(v) for k,v in self.mask_options.items()}

    def _restore_masks(self, values=None):
        values = self._preferences.get('masks', {}) if values is None else values
        for kind, c in self.mask_options.items():
            restore_operations(c, mask_values(values.get(kind, {})), lambda g: mask_values(operation_values(g)))
            source = self._mask_sources[kind]
            source.clear()
            texture = unreal.load_asset(c.AssetPath) if c.SourceKind=='asset' else None
            source.asset_path = c.AssetPath if c.SourceKind=='asset' else ''
            self._set_mask_texture(kind, texture)

    def _set_mask_texture(self, kind, texture):
        previous, self._suspend = self._suspend, True
        try:
            self._mask_textures[kind].Texture = texture
        finally:
            self._suspend = previous

    def _mask_rebind(self, kind):
        c, r = self.mask_options[kind], self.range_options
        c.Origin, c.Size = unreal.IntPoint(r.Origin.x,r.Origin.y), unreal.IntPoint(r.Size.x,r.Size.y)
        self._mask_changed(kind)

    def _mask_pick(self, kind):
        path = mineprep.askopenfilename(title=str(tr(*LABELS[kind])), filetypes=[('Mask', '*.png *.exr')])
        if not path:
            return
        self._mask_sources[kind].clear()
        self._set_mask_texture(kind, None)
        c = self.mask_options[kind]
        c.Path, c.SourceKind, c.AssetPath, c.Enabled = str(Path(path).resolve()), 'file', '', True
        self._mask_rebind(kind)
        self._preview_mask(kind)

    def _mask_clear(self, kind):
        self._mask_sources[kind].clear()
        self._set_mask_texture(kind, None)
        c = self.mask_options[kind]
        c.Path, c.SourceKind, c.AssetPath, c.Enabled = '', 'file', '', False
        self._mask_changed(kind)
        self._on_view('landscape')

    def _mask_texture_changed(self, kind):
        if self._suspend or self._closed:
            return
        c, source = self.mask_options[kind], self._mask_sources[kind]
        texture = self._mask_textures[kind].Texture
        if c.SourceKind=='file' and texture == source.texture:
            return
        if texture is None:
            self._mask_clear(kind)
            return
        source.clear()
        source.texture = texture
        c.Path, c.SourceKind, c.AssetPath, c.Enabled = '', 'asset', texture.get_path_name(), True
        self._mask_rebind(kind)
        if self._sync_masks():
            self._preview_mask(kind)

    def _mask_changed(self, kind):
        if self._suspend:
            return
        self._errors.pop(kind+'_mask', None)
        try:
            mask_values(normalize_group(self.mask_options[kind]))
        except (ValueError, TypeError) as exc:
            self._errors[kind+'_mask'] = str(exc)
            self._set_status(str(exc))
            return
        self._textures.pop(kind+'_mask', None)
        self._overview_textures.pop(kind+'_mask', None)
        label = self._mask_file_labels.get(kind)
        if label is not None:
            label.set_text(str(self.mask_options[kind].Path))
            label.hide(not bool(self.mask_options[kind].Path))
        self._view_failures.clear()
        self._changed()

    def _sync_masks(self):
        for kind, c in self.mask_options.items():
            if not c.Enabled or c.SourceKind != 'asset':
                continue
            try:
                source = self._mask_sources[kind]
                previous = source.identity
                path = source.resolve(c.AssetPath)
                if path != c.Path or previous != source.identity:
                    c.Path = path
                    self._mask_changed(kind)
                self._set_mask_texture(kind, source.texture)
                self._errors.pop(kind+'_mask', None)
            except Exception as exc:
                self._errors[kind+'_mask'] = str(exc)
                self._set_status(str(exc))
                return False
        return True

    def _preview_mask(self, kind):
        if self._closed or self._busy() or not self._sync_masks():
            return
        try:
            spec = self.spec()
        except ValueError as exc:
            self._set_status(str(exc))
            return
        self._launch('mask', lambda rev: ops.preview_mask(spec, kind, on_progress=self._set_status,
            on_done=lambda job: self._mask_done(kind, job, rev)))

    def _mask_done(self, kind, job, revision):
        try:
            if self._closed or not self._schedule.current(revision):
                return
            if job.state != 'completed':
                self._view_failures.add((kind+'_mask', self.spec().key))
                self._set_status(job.error or tr('已取消','Cancelled'))
                return
            result = job.result
            if getattr(self.spec(),kind+'_mask') != result.data.config:
                return
            result.data.source.checked()
            job.check_source()
            if self.mask_options[kind].SourceKind=='file':
                self._set_mask_texture(kind, self._mask_sources[kind].import_file(result.data.config.path,result.data.source))
            textures, _ = self._import_images(result.images)
            result.data.source.checked()
            self._textures.update(textures)
            self._legend_text.set_text(tr(*LABELS[kind]))
            self._stats_text.set_text(tr('遮罩预览 {seconds:.3f} 秒','Mask preview {seconds:.3f} s').format(seconds=result.seconds))
            self._on_view(kind+'_mask')
            self._schedule.cancel()
            self._set_status(tr('遮罩就绪','Mask ready'))
        except Exception as exc:
            self._set_status(str(exc))
        finally:
            if self._job is job:
                self._job = None
            self._update_buttons()
