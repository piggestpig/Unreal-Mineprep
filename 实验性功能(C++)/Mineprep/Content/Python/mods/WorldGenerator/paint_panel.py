"""Numeric image editing on the existing map; RTs are display-only."""
from pathlib import Path
import json
import time

import numpy as np
import mineprep
from mineprep import i18n
import unreal

from .core.data import Region
from .core.heightmap import supported
from .core.spec import HeightmapInput, MaskInput, BiomeMapInput
from .core.biome_map import WATER_BIOMES, supported as biome_supported
from .biome_paint import BiomeCanvas, load_biome_canvas
from .editor import click
from .painting import Canvas, Brush, brush_values, load_canvas, write_image, KINDS
from .props import MapPaintTools, operation_values
from .storage import SAVED_DIR
from .ui_model import MAP_VIEWS
from .ui_choices import choice

PAINT_VIEWS = MAP_VIEWS | {'heightmap','vegetation_mask','clearance_mask'}
PAINT_DIR = SAVED_DIR/'paint'
AUTO_BIOME = '__automatic__'  # a nonempty native FName key; preferences still store ''


class PaintPanel:
    def _init_paint(self):
        self._paint_settings = brush_values(self._preferences.get('paint'))
        self.paint_tools = MapPaintTools()
        self._paint_documents = {}
        self._paint_renderer = None
        self._paint_due = 0.
        self._paint_hover = None
        self._paint_new_hint = None
        self._paint_biome_choice = None
        self._paint_failed = False
        self._load_paint_tools()

    def _load_paint_tools(self):
        previous,self._suspend = self._suspend,True
        try:
            for name in ('Diameter','Hardness','Strength','Visible'):
                setattr(self.paint_tools,name,self._paint_settings[name])
            if self._custom_image_type != 'biome_map':
                self.paint_tools.Value = self._paint_settings[self._custom_image_type]
        finally:
            self._suspend = previous

    def _paint_active(self):
        return self.page=='custom' and self._custom_image_type in KINDS and self.view in PAINT_VIEWS

    def _paint_supported(self):
        if self._custom_image_type == 'biome_map':
            return biome_supported(self.pack)
        return self._custom_image_type in KINDS and (self._custom_image_type!='heightmap' or supported(self.pack))

    def _paint_options(self):
        if self._custom_image_type == 'biome_map':
            return self.biome_map_options
        return self.custom_options if self._custom_image_type=='heightmap' else self.mask_options[self._custom_image_type]

    def _paint_source(self):
        if self._custom_image_type == 'biome_map':
            return None
        return self._heightmap_source if self._custom_image_type=='heightmap' else self._mask_sources[self._custom_image_type]

    def _paint_identity(self):
        c = self._paint_options()
        state = operation_values(c)
        state.pop('Enabled')
        if self._custom_image_type == 'biome_map':
            state['pack'] = self.pack.fingerprint
        if self._custom_image_type != 'biome_map' and c.SourceKind=='asset':
            texture = self._heightmap_texture.Texture if self._custom_image_type=='heightmap' else self._mask_textures[self._custom_image_type].Texture
            state['source'] = (texture.blueprint_get_texture_source_id_string()
                               if texture is not None and unreal.SystemLibrary.is_valid(texture) else None)
        elif c.Path:
            try:
                stat = Path(c.Path).stat()
                state['stamp'] = (stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
            except OSError:
                state['stamp'] = None
        if not c.Path and (self._custom_image_type == 'biome_map' or not c.AssetPath):
            r = self.range_options
            state['Origin'],state['Size'] = [int(r.Origin.x),int(r.Origin.y)],[int(r.Size.x),int(r.Size.y)]
        return state

    def _paint_document(self):
        kind = self._custom_image_type
        identity = self._paint_identity()
        current = self._paint_documents.get(kind)
        if current is not None and (current[0]==identity or current[1].unsaved):
            return current[1]
        c = self._paint_options()
        source = self._paint_source()
        path = source.resolve(c.AssetPath) if source is not None and c.SourceKind=='asset' and c.AssetPath else c.Path
        if path:
            region = Region(int(c.Origin.x),int(c.Origin.y),int(c.Size.x),int(c.Size.y))
            if kind=='biome_map':
                config = BiomeMapInput(path,region,self._biome_map_palette(),int(c.Tolerance))
                doc = load_biome_canvas(self.pack,config)
            elif kind=='heightmap':
                config = HeightmapInput(path,region,c.Mode,(c.InputRange.x,c.InputRange.y),
                                       None if c.AutoOutput else (c.OutputRange.x,c.OutputRange.y))
                doc = load_canvas(kind,config,self._values())
            else:
                config = MaskInput(path,region)
                doc = load_canvas(kind,config,self._values())
            # An owned working file can be resumed; external inputs are never overwritten.
            if Path(path).resolve().parent==PAINT_DIR.resolve():
                doc.path = str(Path(path).resolve())
        else:
            r = self.range_options
            region = Region(int(r.Origin.x),int(r.Origin.y),int(r.Size.x),int(r.Size.y))
            doc = (BiomeCanvas(self.pack,region,palette=self._biome_map_palette()) if kind=='biome_map'
                   else Canvas(kind,region))
        self._paint_documents[kind] = self._paint_identity(),doc
        self._paint_failed = False
        return doc

    def _discard_paint(self, kind):
        self._cancel_drag()
        self._paint_documents.pop(kind,None)
        self._errors.pop('paint_'+kind,None)

    def _paint_editor(self, parent):
        if not self._paint_supported():
            return
        parent.text(i18n('地图绘图','Map painting'),size=12)
        if self._custom_image_type == 'biome_map':
            self._paint_biome_choice = choice(parent,self._paint_biome_choices(),self._paint_biome_selection(),
                                             self._paint_biome_changed)
            if not self.biome_map_options.Path:
                self._paint_new_hint = parent.text(i18n('首笔新建透明群系图；未绘制区域沿用自动选择。',
                    'The first stroke creates a transparent biome map. Unpainted areas keep automatic selection.'),size=10,wrap=True)
        if self._custom_image_type=='heightmap' and not self.custom_options.Path and not self.custom_options.AssetPath:
            self._paint_new_hint = parent.text(i18n('首笔新建零增量图，保留原地形。','The first stroke creates a zero-delta image over the original terrain.'),size=10,wrap=True)
        for name in (('Diameter','Visible') if self._custom_image_type=='biome_map' else ('Value','Diameter','Hardness','Strength','Visible')):
            label = (i18n('目标高度／增量（格）','Target height / delta (blocks)') if self._custom_image_type=='heightmap'
                     else i18n('目标数值（0～1）','Target value (0–1)')) if name=='Value' else None
            parent.prop(self.paint_tools,name,text=label,on_property_changed=self._paint_tools_changed)
        row = parent.row()
        row.button(i18n('撤销','Undo'),size=11,on_clicked=click(lambda:self._paint_history(False)))
        row.button(i18n('重做','Redo'),size=11,on_clicked=click(lambda:self._paint_history(True)))
        row.button(i18n('保存绘图','Save painting'),size=11,on_clicked=click(self._paint_save))
        row.button(i18n('导出图像','Export image'),size=11,on_clicked=click(self._paint_export))
        if self._custom_image_type == 'biome_map':
            parent.text(i18n('左键绘制所选群系；选择“自动群系”可擦除。笔画结束后保存PNG副本，不改写导入的原图。',
                'Left paints the selected biome. Choose Automatic biome to erase. Completed strokes save a PNG copy and leave imported originals intact.'),size=10,wrap=True)
        else:
            parent.text(i18n('左键绘制当前图层。笔画结束后自动保存副本；不改写原图。留空遮罩只清理植物和景物。',
                           'Left paints this layer. Completed strokes save a copy; original images stay intact. Clearance removes scenery only.'),size=10,wrap=True)

    def _paint_biome_choices(self):
        return {AUTO_BIOME:i18n('自动群系（擦除）','Automatic biome (erase)'),
                **{b.id:self._biome_name(b.id) for b in self.pack.biomes if b.id not in WATER_BIOMES}}

    def _paint_biome_selection(self):
        choices = self._paint_biome_choices()
        selected = self._paint_settings['biome_map'] or AUTO_BIOME
        return selected if selected in choices else next((k for k in choices if k != AUTO_BIOME),AUTO_BIOME)

    def _paint_biome_changed(self, ident, _reason=None):
        if self._suspend:
            return
        self._cancel_drag()
        self._paint_settings['biome_map'] = '' if ident == AUTO_BIOME else ident
        self._paint_biome_choice['selected'] = ident
        self._remember(draft=False)
        self._transform()

    def _paint_tools_changed(self, _name):
        if self._suspend:
            return
        self._cancel_drag()
        values = operation_values(self.paint_tools)
        target = float(values.pop('Value'))
        if self._custom_image_type not in ('heightmap','biome_map'):
            target = min(1.,max(0.,target))
            self._suspend = True
            try:
                self.paint_tools.Value = target
            finally:
                self._suspend = False
        if self._custom_image_type != 'biome_map':
            values[self._custom_image_type] = target
        self._paint_settings = brush_values({**self._paint_settings,**values})
        self._paint_failed = False
        self._remember(draft=False)
        self._transform()

    def _paint_begin(self, point):
        if not self._paint_supported():
            self._set_status(i18n('当前资源包不支持此绘图项','This pack does not support this paint input'))
            return False
        try:
            doc = self._paint_document()
            if doc.value_at(point) is None:
                return False
            t = self.paint_tools
            if doc.categorical:
                ident = self._paint_biome_selection()
                target = doc.target('' if ident == AUTO_BIOME else ident)
            else:
                target = float(t.Value)
            doc.begin(point,Brush(target,float(t.Diameter),float(t.Hardness),float(t.Strength)))
            return doc
        except (OSError,ValueError,RuntimeError) as exc:
            self._set_status(str(exc))
            return False

    def _paint_publish(self, doc):
        try:
            path = doc.save(PAINT_DIR)
        except (OSError,ValueError,RuntimeError) as exc:
            self._errors['paint_'+doc.kind] = str(exc)
            self._set_status(i18n('绘图未保存：{error}','Painting not saved: {error}').format(error=str(exc)))
            return False
        self._errors.pop('paint_'+doc.kind,None)
        self._paint_failed = False
        c,source = self._paint_options(),self._paint_source()
        palette_changed = doc.categorical and self._biome_map_palette() != doc.palette
        if source is not None:
            source.clear()
        previous,self._suspend = self._suspend,True
        try:
            c.Path,c.Enabled = path,True
            if doc.categorical:
                c.Palette,c.Tolerance = json.dumps(doc.palette),0
            else:
                c.SourceKind,c.AssetPath = 'file',''
            r = doc.region
            c.Origin,c.Size = unreal.IntPoint(r.x0,r.z0),unreal.IntPoint(r.width,r.depth)
            if doc.kind=='heightmap':
                c.Mode,c.AutoOutput = doc.mode,True
                c.InputRange = unreal.Vector2D(0.,1.)
                self._set_heightmap_texture(None)
            elif not doc.categorical:
                self._set_mask_texture(doc.kind,None)
        finally:
            self._suspend = previous
        self._paint_documents[doc.kind] = self._paint_identity(),doc
        if doc.categorical:
            self._biome_map_changed()
            if palette_changed and self.page=='custom' and self._custom_image_type=='biome_map':
                self._biome_map_mapping_editor()
        elif doc.kind=='heightmap':
            self._on_custom_changed()
        else:
            self._mask_changed(doc.kind)
        self._set_status(i18n('笔画已保存','Stroke saved'))
        if self._paint_new_hint is not None:
            self._paint_new_hint.hide(True)
        return True

    def _paint_history(self, redo):
        self._cancel_drag()
        try:
            doc = self._paint_document()
            if doc.history(redo):
                self._paint_publish(doc)
        except (OSError,ValueError,RuntimeError) as exc:
            self._set_status(str(exc))

    def _paint_save(self):
        self._cancel_drag()
        try:
            self._paint_publish(self._paint_document())
        except (OSError,ValueError,RuntimeError) as exc:
            self._set_status(str(exc))

    def _paint_export(self):
        self._cancel_drag()
        try:
            doc = self._paint_document()
            extensions = ('.png',) if doc.categorical else ('.exr',) if doc.kind=='heightmap' else ('.exr','.png')
            path = mineprep.asksaveasfilename(title=str(i18n('导出绘图','Export painting')),
                filetypes=[(suffix[1:].upper(),'*'+suffix) for suffix in extensions])
            if path:
                path = Path(path)
                if not path.suffix:path = path.with_suffix(doc.extension)
                if path.suffix.lower() not in extensions:
                    raise ValueError('Biomes: PNG; height: EXR; masks: EXR or PNG')
                if doc.categorical:
                    doc.write(path)
                else:
                    values = np.round(doc.values*65535).astype(np.uint16) if path.suffix.lower()=='.png' else doc.values
                    write_image(path,values)
                self._set_status(i18n('图像已导出','Image exported'))
        except (OSError,ValueError,RuntimeError) as exc:
            self._set_status(str(exc))

    def _init_paint_overlay(self, overlay):
        self._release_paint_rt()
        self._paint_background = overlay.image(size=unreal.Vector2D(1,1),padding=0,align=(2,2),hidden=True)
        self._paint_background.set_render_transform_pivot(unreal.Vector2D(.5,.5))
        self._paint_background.set_brush(unreal.SlateBrush(
            tint_color=unreal.SlateColor(specified_color=unreal.LinearColor(.07,.07,.07,1)),
            draw_as=unreal.SlateBrushDrawType.ROUNDED_BOX,
            outline_settings=unreal.SlateBrushOutlineSettings(corner_radii=unreal.Vector4(0,0,0,0),
                width=0,rounding_type=unreal.SlateBrushRoundingType.FIXED_RADIUS)))
        self._paint_image = overlay.image(size=unreal.Vector2D(1,1),padding=0,align=(2,2),hidden=True)
        self._paint_image.set_render_transform_pivot(unreal.Vector2D(.5,.5))
        self._paint_cursor = overlay.image(size=unreal.Vector2D(1,1),padding=0,align=(2,2),hidden=True)
        self._paint_cursor.set_render_transform_pivot(unreal.Vector2D(.5,.5))
        self._paint_cursor_size = None
        self._paint_cursor.set_brush(unreal.SlateBrush(
            tint_color=unreal.SlateColor(specified_color=unreal.LinearColor(0,0,0,0)),
            draw_as=unreal.SlateBrushDrawType.ROUNDED_BOX,
            outline_settings=unreal.SlateBrushOutlineSettings(color=unreal.SlateColor(specified_color=unreal.LinearColor(1,1,1,1)),
                width=1.5,rounding_type=unreal.SlateBrushRoundingType.HALF_HEIGHT_RADIUS)))

    def _paint_display(self, mapping):
        active = self._paint_active() and self._paint_supported()
        self._paint_cursor.hide()
        self._paint_image.hide()
        self._paint_background.hide()
        r = self.range_options
        region = Region(int(r.Origin.x),int(r.Origin.y),int(r.Size.x),int(r.Size.y))
        if self._paint_active():
            matching = self._image_region==region
            self._image.hide(unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE if matching else unreal.SlateVisibility.COLLAPSED)
            self._placeholder.hide()
        if not active:
            self._paint_hint.set_text('')
            return
        if self._image_region!=region:
            self._paint_background.set_render_scale(unreal.Vector2D(mapping.size[0]*mapping.zoom,mapping.size[1]*mapping.zoom))
            self._paint_background.set_render_translation(unreal.Vector2D(*mapping.pan))
            self._paint_background.hide(unreal.SlateVisibility.HIT_TEST_INVISIBLE)
        current = self._paint_documents.get(self._custom_image_type)
        # Decode once on first interaction rather than importing large files on every tick.
        if current is None or (current[0]!=self._paint_identity() and not current[1].unsaved):
            return
        doc = current[1]
        if not self.paint_tools.Visible:
            doc.invalidate_preview()
        if self.paint_tools.Visible and not self._paint_failed and not self._preview_hidden:
            try:
                self._paint_flush(doc)
            except Exception as exc:
                self._paint_failed = True
                self._set_status(i18n('绘图显示失败：{error}','Paint display failed: {error}').format(error=str(exc)))
                return
            a = doc.region
            box = mapping.box(((a.x0,a.z0),(a.x0+a.width-1,a.z0+a.depth-1)))
            if box is not None:
                # Preserve the full texture mapping; clipping belongs to the border.
                size = (a.width*mapping.size[0]/region.width,a.depth*mapping.size[1]/region.depth)
                center = mapping.local((a.x0+a.width/2,a.z0+a.depth/2))
                self._paint_image.set_desired_size_override(unreal.Vector2D(1,1))
                self._paint_image.set_render_scale(unreal.Vector2D(size[0]*mapping.zoom,size[1]*mapping.zoom))
                self._paint_image.set_render_translation(unreal.Vector2D(center[0]-mapping.viewport[0]/2,center[1]-mapping.viewport[1]/2))
                self._paint_image.hide(unreal.SlateVisibility.HIT_TEST_INVISIBLE)
        point = self._preview_border.get_mouse_local()
        self._paint_hover = (mapping.world((point.x,point.y)) if 0<=point.x<mapping.viewport[0]
                             and 0<=point.y<mapping.viewport[1] else None)
        if self._paint_hover is not None and doc.value_at(self._paint_hover) is not None:
            center = mapping.local(self._paint_hover)
            size = tuple(max(2.,float(self.paint_tools.Diameter)*s/n*mapping.zoom) for s,n in zip(mapping.size,(region.width,region.depth)))
            if size!=self._paint_cursor_size:
                self._paint_cursor_size = size
                brush = self._paint_cursor.get_editor_property('brush')
                brush.outline_settings.width = 1.5/max(size)
                self._paint_cursor.set_brush(brush)
            self._paint_cursor.set_render_scale(unreal.Vector2D(*size))
            self._paint_cursor.set_render_translation(unreal.Vector2D(center[0]-mapping.viewport[0]/2,center[1]-mapping.viewport[1]/2))
            self._paint_cursor.hide(unreal.SlateVisibility.HIT_TEST_INVISIBLE)
            x,z = self._paint_hover
            value = doc.value_at((x,z))
            if doc.categorical:
                name = self._biome_name(doc.biomes[int(value)-1]) if value else i18n('自动群系','Automatic biome')
                self._paint_hint.set_text(i18n('位置 ({x}, {z}) · 群系 {name}',
                    'Position ({x}, {z}) · biome {name}').format(x=f'{x:.1f}',z=f'{z:.1f}',name=name))
            else:
                self._paint_hint.set_text(i18n('位置 ({x}, {z}) · 数值 {value}',
                                             'Position ({x}, {z}) · value {value}').format(
                                                 x=f'{x:.1f}', z=f'{z:.1f}', value=f'{value:.3f}'))
        else:
            self._paint_hint.set_text('')

    def _paint_flush(self, doc):
        renderer = self._paint_renderer
        if renderer is not None and renderer.document is doc and not doc.preview_reset:
            if not doc.preview_commands or time.monotonic()<self._paint_due:
                return
        if renderer is None:
            from .paint_render import PaintRender
            renderer = self._paint_renderer = PaintRender(mineprep.world())
            self._paint_image.set_brush_from_material(renderer.overlay)
        renderer.flush(doc)
        self._paint_due = time.monotonic()+1/30

    def _release_paint_rt(self):
        if self._paint_renderer is not None:
            self._paint_renderer.close()
        self._paint_renderer = None
