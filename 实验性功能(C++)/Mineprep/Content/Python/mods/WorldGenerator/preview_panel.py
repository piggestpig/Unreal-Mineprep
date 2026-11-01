"""Preview navigation and a single fixed core rectangle; no generation on Move."""
import mineprep
from mineprep import i18n
import unreal
from .core.data import Region
from .props import operation_values
from .ui_model import PreviewMap, MAP_VIEWS


class PreviewPanel:
    def _init_core_overlay(self, overlay):
        self._core_overlay = overlay.image(size=unreal.Vector2D(1,1),padding=0,align=(2,2),hidden=True)
        self._core_overlay.set_render_transform_pivot(unreal.Vector2D(.5,.5))
        self._core_overlay_state = self._core_brush_state = None

    def _preview_map(self):
        size = self._preview_border.get_local_size()
        if min(size.x,size.y) < 1:
            return None
        r = self.range_options
        region = (Region(int(r.Origin.x),int(r.Origin.y),int(r.Size.x),int(r.Size.y)) if self._paint_active()
                  else self._image_region or Region(int(r.Origin.x),int(r.Origin.y),int(r.Size.x),int(r.Size.y)))
        shape = (region.width,region.depth) if self._paint_active() else self._image_shape or (region.width,region.depth)
        return PreviewMap(region,shape,
                          (size.x,size.y),self._zoom,tuple(self._pan))

    def _selection_map(self, mapping=None):
        r = self.range_options
        if self._image_region is None or self.view not in MAP_VIEWS or not self._supports_lod():
            return None
        if self._image_region.to_list() != [int(r.Origin.x),int(r.Origin.y),int(r.Size.x),int(r.Size.y)]:
            return None
        return mapping or self._preview_map()

    def _fit(self):
        self._cancel_drag()
        self._zoom, self._pan = 1., [0., 0.]
        self._transform()

    def _zoom_by(self, factor, anchor=None):
        if self._drag is not None and self._drag['mode'] != 'pan':
            return
        old = self._zoom
        zoom = min(8.,max(.25,old*factor))
        if zoom == old:
            return
        if anchor is not None:
            self._pan = [q-zoom/old*(q-p) for q,p in zip(anchor,self._pan)]
        self._zoom = zoom
        self._transform()

    def on_mouse_wheel(self, delta):
        self.layout.set_consume_mouse_wheel(unreal.ConsumeMouseWheel.WHEN_SCROLLING_POSSIBLE)
        if not delta or self._preview_hidden or (self._image_region is None and not self._paint_active()):
            return
        size = self._preview_border.get_local_size()
        point = self._preview_border.get_mouse_local()
        if not (0 <= point.x < size.x and 0 <= point.y < size.y):
            return
        self.layout.set_consume_mouse_wheel(unreal.ConsumeMouseWheel.NEVER)
        self._zoom_by(1.25**delta,(point.x-size.x/2,point.y-size.y/2))

    def _transform(self):
        if not hasattr(self,'_image'):
            return
        mapping = self._preview_map()
        if mapping is None:
            return
        state = (id(self._image),mapping.size,self._zoom,tuple(self._pan))
        if state != getattr(self,'_image_transform',None):
            self._image_transform = state
            self._image.set_desired_size_override(unreal.Vector2D(*mapping.size))
            self._image.set_render_scale(unreal.Vector2D(self._zoom,self._zoom))
            self._image.set_render_translation(unreal.Vector2D(*self._pan))
        self._update_core_overlay(mapping)
        self._paint_display(mapping)

    def _update_core_overlay(self, mapping):
        r = self.range_options
        drag = self._drag if self._drag is not None and self._drag['mode'] in ('fine','empty') else None
        detail = self._supports_lod()
        corners = (drag['start'],drag['end']) if drag else (
            ((int(r.CoreA.x),int(r.CoreA.y)),(int(r.CoreB.x),int(r.CoreB.y))) if detail and r.CoreEnabled else None)
        empty = drag['mode'] == 'empty' if drag else r.CoreEmpty
        usable = self._selection_map(mapping) is not None
        state = (mapping,corners,empty,usable,detail,self.page)
        if state == self._core_overlay_state:
            return
        self._core_overlay_state = state
        self._clear_core_button.set_is_enabled(corners is not None)
        if self._paint_active():
            controls = (i18n('左键绘图 · 中键平移 · 右键LOD · 滚轮缩放','Left: paint · Middle: pan · Right: LOD · Wheel: zoom')
                        if detail and self.view in MAP_VIEWS else i18n(
                            '左键绘图 · 中键平移 · 滚轮缩放','Left: paint · Middle: pan · Wheel: zoom'))
        elif detail and self.view in MAP_VIEWS:
            controls = i18n('左键留空 · 中键平移 · 右键LOD','Left: empty LOD · Middle: pan · Right: LOD')
        else:
            controls = i18n('中键平移 · 滚轮缩放','Middle: pan · Wheel: zoom')
        selection = warning = ''
        if corners is not None:
            a,b = corners
            lo = min(a[0],b[0]),min(a[1],b[1])
            hi = max(a[0],b[0]),max(a[1],b[1])
            selection = i18n('\n{mode} ({x0}, {z0}) → ({x1}, {z1}) · {width} × {depth}',
                           '\n{mode} ({x0}, {z0}) → ({x1}, {z1}) · {width} × {depth}').format(
                mode=i18n('LOD留空','Empty LOD') if empty else 'LOD',
                x0=lo[0],z0=lo[1],x1=hi[0],z1=hi[1],width=hi[0]-lo[0]+1,depth=hi[1]-lo[1]+1)
        if not self._paint_active() and self._image_region is not None and self.view in MAP_VIEWS and mapping.region.to_list() != [
                int(r.Origin.x),int(r.Origin.y),int(r.Size.x),int(r.Size.y)]:
            warning = i18n('\n预览范围已变化，请刷新后框选','\nBounds changed: refresh the preview before selecting')
        self._core_hint.set_text(unreal.Text('{controls}{selection}{warning}').format(
            controls=controls,selection=selection,warning=warning))
        box = mapping.box(corners) if corners is not None and usable else None
        if box is None:
            self._core_overlay.hide()
            return
        size,offset = box
        brush_state = (empty,self._zoom)
        if brush_state != self._core_brush_state:
            self._core_brush_state = brush_state
            fill = unreal.LinearColor(1,1,1,1) if empty else unreal.LinearColor(.65,.08,.85,.25)
            line = unreal.LinearColor(.3,.3,.3,1) if empty else unreal.LinearColor(.65,.08,.85,1)
            self._core_overlay.set_brush(unreal.SlateBrush(
                tint_color=unreal.SlateColor(specified_color=fill),draw_as=unreal.SlateBrushDrawType.ROUNDED_BOX,
                outline_settings=unreal.SlateBrushOutlineSettings(
                    corner_radii=unreal.Vector4(0,0,0,0),color=unreal.SlateColor(specified_color=line),
                    width=2/self._zoom,rounding_type=unreal.SlateBrushRoundingType.FIXED_RADIUS)))
        self._core_overlay.set_desired_size_override(unreal.Vector2D(*size))
        self._core_overlay.set_render_scale(unreal.Vector2D(self._zoom,self._zoom))
        self._core_overlay.set_render_translation(unreal.Vector2D(*offset))
        self._core_overlay.hide(unreal.SlateVisibility.HIT_TEST_INVISIBLE)

    def _cancel_drag(self):
        if self._drag is not None and self._drag['mode']=='paint':
            self._drag['doc'].cancel()
        self._drag = None
        self._transform()

    def _write_core(self, corners=None, *, empty=False):
        self._suspend = True
        try:
            r = self.range_options
            if corners is None:
                r.CoreEnabled = False
            else:
                a,b = corners
                if r.CellStep == 1 and (not empty or not r.CoreInitialized):
                    r.CellStep = 2
                r.CoreA = unreal.IntPoint(min(a[0],b[0]),min(a[1],b[1]))
                r.CoreB = unreal.IntPoint(max(a[0],b[0]),max(a[1],b[1]))
                r.CoreEnabled, r.CoreEmpty, r.CoreInitialized = True,empty,True
            self._last_native[id(r)] = operation_values(r)
            combo = getattr(self,'_cell_step_combo',None)
            if combo is not None:
                combo.set_selected_option(unreal.Name(str(r.CellStep)))
        finally:
            self._suspend = False
        self._on_range('CoreEnabled')

    def _clear_core(self):
        self._cancel_drag()
        if self.range_options.CoreEnabled:
            self._write_core()

    def _pan_start(self, border):
        if self._drag is not None:
            return True
        buttons = ((mineprep.left_mouse_down,'paint' if self.page=='custom' else 'empty'),
                   (mineprep.middle_mouse_down,'pan'),(mineprep.right_mouse_down,'fine'))
        pressed = [(fn,mode) for fn,mode in buttons if fn() is True]
        if len(pressed) != 1:
            return False
        button,mode = pressed[0]
        point = border.get_mouse_local()
        if mode == 'pan':
            self._drag = dict(mode=mode,button=button,last=(point.x,point.y))
        elif mode == 'paint':
            mapping = self._preview_map() if self._paint_active() else None
            position = mapping.world((point.x,point.y)) if mapping is not None else None
            doc = self._paint_begin(position) if position is not None else False
            if doc is False:
                return False
            self._paint_hover = position
            self._drag = dict(mode=mode,button=button,last=position,doc=doc)
            self._transform()
        else:
            mapping = self._selection_map()
            if mapping is None:
                self._set_status(i18n('请在与当前范围一致的俯视预览中框选',
                                    'Select on a map preview matching the current bounds'))
                return False
            cell = mapping.cell((point.x,point.y))
            if cell is None:
                return False
            self._drag = dict(mode=mode,button=button,start=cell,end=cell)
            self._transform()
        return unreal.WidgetLibrary.capture_mouse(unreal.WidgetLibrary.handled(),border.target)

    def _pan_move(self, border):
        point = border.get_mouse_local()
        if self._paint_active():
            mapping = self._preview_map()
            self._paint_hover = (mapping.world((point.x,point.y)) if mapping is not None
                                 and 0<=point.x<mapping.viewport[0] and 0<=point.y<mapping.viewport[1] else None)
            if self._paint_supported() and self._paint_hover is not None:
                try:
                    self._paint_document()
                except (OSError,ValueError,RuntimeError) as exc:
                    self._set_status(str(exc))
        if self._drag is None:
            self._transform()
            return False
        if not border.target.has_mouse_capture():
            self._cancel_drag()
            return False
        drag = self._drag
        if drag['mode'] == 'pan':
            self._pan[0] += point.x-drag['last'][0]
            self._pan[1] += point.y-drag['last'][1]
            drag['last'] = point.x,point.y
        elif drag['mode']=='paint':
            if not self._paint_active() or self._paint_documents[self._custom_image_type][1] is not drag['doc']:
                self._cancel_drag()
                return False
            position = self._paint_hover
            if position is not None:
                drag['doc'].stroke.segment(drag['last'] or position,position)
            drag['last'] = position
        else:
            mapping = self._selection_map()
            if mapping is None:
                self._cancel_drag()
                return False
            drag['end'] = mapping.cell((point.x,point.y),clip=True)
        self._transform()
        return True

    def _pan_stop(self, border):
        drag = self._drag
        if drag is not None:
            down = drag['button']()
            if down is True:
                return True
            self._drag = None
            if drag['mode']=='paint':
                doc = drag['doc']
                if down is False:
                    mapping = self._preview_map()
                    point = border.get_mouse_local()
                    position = (mapping.world((point.x,point.y)) if mapping is not None
                                and 0<=point.x<mapping.viewport[0] and 0<=point.y<mapping.viewport[1] else None)
                    if position is not None:
                        doc.stroke.segment(drag['last'] or position,position)
                    if doc.finish():self._paint_publish(doc)
                else:
                    doc.cancel()
            mapping = self._selection_map() if drag['mode'] in ('fine','empty') else None
            if down is False and mapping is not None:
                point = border.get_mouse_local()
                self._write_core((drag['start'],mapping.cell((point.x,point.y),clip=True)),empty=drag['mode']=='empty')
            self._transform()
        if drag is not None or border.target.has_mouse_capture():
            return unreal.WidgetLibrary.release_mouse_capture(unreal.WidgetLibrary.handled())
        return False
