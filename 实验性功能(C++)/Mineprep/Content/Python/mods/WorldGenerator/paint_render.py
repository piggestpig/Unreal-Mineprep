"""Two persistent numeric RTs and a display material; Unreal is loaded on demand."""
import hashlib
import os
import time
from .painting import Brush, COLORS, union_box
from .ui_model import preview_color_linear

STATE_CODE = r'''
int2 pixel = min(int2(UV * Size.xy), int2(Size.xy) - 1);
float2 s = Source.Load(int3(pixel, 0)).rg;
if (Operation < 0.5) return float3(s.r, Coverage.Load(int3(pixel, 0)).r, 0);
if (Operation < 1.5) {
    float2 p = (float2(pixel) + 0.5) * Size.zw;
    float2 d = Segment.zw - Segment.xy;
    float l = dot(d, d);
    float t = l > 0 ? saturate(dot(p - Segment.xy, d) / l) : 0;
    float distance = length(p - Segment.xy - t * d);
    float w = Brush.y >= 1 ? (distance <= Brush.x ? 1 : 0)
                           : saturate((Brush.x - distance) / (Brush.x * (1 - Brush.y)));
    return float3(s.r, max(s.g, w), 0);
}
if (Operation < 2.5) {
    if (Categorical > 0.5) return float3(s.g > 0.5 ? Brush.z : s.r, 0, 0);
    float a = s.g * Brush.w;
    precise float value = s.r * (1 - a) + Brush.z * a;
    return float3(value, 0, 0);
}
return Operation < 3.5 ? float3(s.r, 0, 0) : float3(s, 0);
'''

OVERLAY_CODE = r'''
int2 pixel = min(int2(UV * Size.xy), int2(Size.xy) - 1);
float2 s = Source.Load(int3(pixel, 0)).rg;
if (Layer > 3.5) {
    int id = (int)round(s.g > 0.5 ? Brush.z : s.r);
    return Palette.Load(int3(id % 256, id / 256, 0));
}
float a = s.g * Brush.w;
precise float value = s.r * (1 - a) + Brush.z * a;
float3 color = Layer < 1.5 && value < 0 ? Cold.rgb : Tint.rgb;
float opacity = Layer < 0.5 ? abs(value) / (abs(value) + 16)
              : Layer < 1.5 ? 0.8 : Layer < 2.5 ? 1 - value : value;
return float4(color, round(saturate(opacity) * 150) / 255);
'''


def _pixels(box):
    return (box[2]-box[0])*(box[3]-box[1])


def _material(overlay):
    import unreal as ue
    code = OVERLAY_CODE if overlay else STATE_CODE
    key = hashlib.sha256(('paint-rg32-v2'+code).encode()).hexdigest()[:12]
    folder = '/Game/mc/WorldGenerator/_PaintPreview/v2'
    name = ('M_Overlay_' if overlay else 'M_State_')+key
    path = folder+'/'+name
    if ue.EditorAssetLibrary.does_asset_exist(path):
        material = ue.load_asset(path)
        if not isinstance(material,ue.Material):
            raise TypeError(f'Paint material path is occupied: {path}')
        return material
    material = ue.AssetToolsHelpers.get_asset_tools().create_asset(name,folder,ue.Material,ue.MaterialFactoryNew())
    if material is None:raise RuntimeError(f'Cannot create paint material: {path}')
    try:
        material.set_editor_properties(dict(
            material_domain=ue.MaterialDomain.MD_UI if overlay else ue.MaterialDomain.MD_SURFACE,
            blend_mode=ue.BlendMode.BLEND_TRANSLUCENT if overlay else ue.BlendMode.BLEND_OPAQUE,
            shading_model=ue.MaterialShadingModel.MSM_UNLIT,
            float_precision_mode=ue.MaterialFloatPrecisionMode.MFPM_FULL,
            allow_negative_emissive_color=not overlay))
        edit = ue.MaterialEditingLibrary
        node = edit.create_material_expression(material,ue.MaterialExpressionCustom)
        pins = ('Source','Palette','UV','Size','Brush','Layer','Tint','Cold') if overlay else ('Source','Coverage','UV','Size','Brush','Operation','Segment','Categorical')
        inputs = []
        for name in pins:
            item = ue.CustomInput()
            item.set_editor_property('input_name',name)
            inputs.append(item)
        node.set_editor_properties(dict(code=code,inputs=inputs,
            output_type=ue.CustomMaterialOutputType.CMOT_FLOAT4 if overlay else ue.CustomMaterialOutputType.CMOT_FLOAT3))
        for name in pins:
            output = ''
            if name in ('Source','Coverage','Palette'):
                source = edit.create_material_expression(material,ue.MaterialExpressionTextureObjectParameter)
                source.set_editor_properties(dict(parameter_name=name,texture=ue.load_asset('/Engine/EngineResources/WhiteSquareTexture')))
            elif name=='UV':
                source = edit.create_material_expression(material,ue.MaterialExpressionTextureCoordinate)
            else:
                scalar = name in ('Operation','Layer','Categorical')
                cls = ue.MaterialExpressionScalarParameter if scalar else ue.MaterialExpressionVectorParameter
                source = edit.create_material_expression(material,cls)
                source.set_editor_property('parameter_name',name)
                if not scalar:output = 'RGBA'
            if not edit.connect_material_expressions(source,output,node,name):
                raise RuntimeError(f'Cannot connect paint input: {name}')
        color = node
        if overlay:
            color = edit.create_material_expression(material,ue.MaterialExpressionComponentMask)
            color.set_editor_properties(dict(r=True,g=True,b=True,a=False))
            alpha = edit.create_material_expression(material,ue.MaterialExpressionComponentMask)
            alpha.set_editor_properties(dict(r=False,g=False,b=False,a=True))
            if (not edit.connect_material_expressions(node,'',color,'')
                    or not edit.connect_material_expressions(node,'',alpha,'')
                    or not edit.connect_material_property(alpha,'',ue.MaterialProperty.MP_OPACITY)):
                raise RuntimeError('Cannot connect paint opacity')
        if not edit.connect_material_property(color,'',ue.MaterialProperty.MP_EMISSIVE_COLOR):
            raise RuntimeError('Cannot connect paint color')
        errors = edit.recompile_material(material)
        if errors:raise RuntimeError('\n'.join(map(str,errors)))
        if not ue.EditorAssetLibrary.save_loaded_asset(material):
            raise OSError(f'Cannot save paint material: {path}')
        return material
    except Exception:
        # Only this failed new cache asset belongs to the builder.
        ue.EditorAssetLibrary.delete_asset(path)
        raise


class PaintRender:
    def __init__(self, world):
        import unreal as ue
        self.ue,self.world = ue,world
        self.update = ue.MaterialLibrary.create_dynamic_material_instance(world,_material(False))
        self.overlay = ue.MaterialLibrary.create_dynamic_material_instance(world,_material(True))
        self.targets,self.shape,self.document = [],None,None
        self.current,self.difference = 0,None
        self.upload = None
        self.brush = Brush(0,strength=0)
        self.uploads,self.passes,self.submitted_pixels,self.submit_seconds = 0,0,0,0.

    @property
    def texture(self):
        return self.targets[self.current]

    def _size(self, doc):
        h,w = doc.values.shape
        return self.ue.LinearColor(w,h,doc.region.width/w,doc.region.depth/h)

    def _brush(self, material, brush):
        material.set_vector_parameter_value('Brush',self.ue.LinearColor(
            brush.diameter/2,brush.hardness,brush.value,brush.strength))

    def _draw(self, source, target, box, operation, brush, a=(0,0), b=(0,0)):
        ue = self.ue
        h,w = self.shape
        x,z,ex,ez = box
        self.update.set_texture_parameter_value('Source',source)
        self.update.set_scalar_parameter_value('Operation',operation)
        self._brush(self.update,brush)
        self.update.set_vector_parameter_value('Segment',ue.LinearColor(*a,*b))
        canvas,_,context = ue.RenderingLibrary.begin_draw_canvas_to_render_target(self.world,target)
        try:
            canvas.draw_material(self.update,ue.Vector2D(x,z),ue.Vector2D(ex-x,ez-z),
                                 ue.Vector2D(x/w,z/h),ue.Vector2D((ex-x)/w,(ez-z)/h))
        finally:
            ue.RenderingLibrary.end_draw_canvas_to_render_target(self.world,context)
        self.passes += 1
        self.submitted_pixels += _pixels(box)

    def _initialize(self, doc):
        os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR','1')
        import cv2
        ue = self.ue
        if self.document is not None:self.document.invalidate_preview()
        if self.shape!=doc.values.shape:
            self.close()
            h,w = doc.values.shape
            self.shape = doc.values.shape
            try:
                for _ in range(2):
                    target = ue.RenderingLibrary.create_render_target2d(self.world,w,h,
                        ue.TextureRenderTargetFormat.RTF_RG32F,ue.LinearColor(0,0,0,0))
                    if target is None:raise RuntimeError('Cannot create RG32F paint target')
                    self.targets.append(target)
                    target.set_editor_properties(dict(srgb=False,filter=ue.TextureFilter.TF_NEAREST,
                        address_x=ue.TextureAddress.TA_CLAMP,address_y=ue.TextureAddress.TA_CLAMP))
            except Exception:
                self.close()
                raise
        h,w = self.shape
        state = doc.preview_state()
        # UE maps RGB float imports to RGBA16F; single-channel EXR stays R32F.
        inputs = []
        for channel in range(2):
            ok,encoded = cv2.imencode('.exr',state[...,channel])
            if not ok:raise OSError('Cannot encode numeric paint state')
            texture = ue.RenderingLibrary.import_buffer_as_texture2d(self.world,encoded.tobytes())
            if texture is None:raise RuntimeError('Cannot initialize numeric paint state')
            texture.set_editor_property('srgb',False)
            inputs.append(texture)
        if doc.categorical:
            # Only colours use RGBA16F. Category IDs remain in the R32F uploads.
            import numpy as np
            colors = doc.colors.astype(np.float32)/255
            rgb = colors[:,:3]
            colors[:,:3] = np.where(rgb <= .04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
            atlas = np.zeros(((len(colors)+255)//256,256,4),np.float32)
            atlas.reshape(-1,4)[:len(colors)] = colors
            ok,encoded = cv2.imencode('.exr',atlas[...,[2,1,0,3]])
            if not ok:raise OSError('Cannot encode biome preview colours')
            texture = ue.RenderingLibrary.import_buffer_as_texture2d(self.world,encoded.tobytes())
            if texture is None:raise RuntimeError('Cannot initialize biome preview colours')
            texture.set_editor_properties(dict(srgb=False,filter=ue.TextureFilter.TF_NEAREST))
            inputs.append(texture)
            self.overlay.set_texture_parameter_value('Palette',texture)
        else:
            self.overlay.set_texture_parameter_value('Palette',None)
        self.upload = tuple(inputs)
        self.update.set_texture_parameter_value('Coverage',inputs[1])
        self.update.set_scalar_parameter_value('Categorical',int(doc.categorical))
        size = self._size(doc)
        for material in (self.update,self.overlay):material.set_vector_parameter_value('Size',size)
        self.current = 0
        for target in self.targets:
            self._draw(inputs[0],target,(0,0,w,h),0,Brush(0,strength=0))
        self.difference = None
        self.brush = doc.stroke.brush if doc.stroke is not None else Brush(0,strength=0)
        self.document = doc
        doc.preview_commands.clear()
        doc.preview_reset = False
        self.uploads += len(inputs)

    def flush(self, doc):
        started = time.perf_counter()
        try:
            if self.document is not doc or doc.preview_reset:self._initialize(doc)
            commands,doc.preview_commands = doc.preview_commands,[]
            for command in commands:
                other = 1-self.current
                # Outside the last difference, both targets already agree.
                box = union_box(self.difference,command.box)
                if self.difference is not None and _pixels(box)>_pixels(self.difference)+_pixels(command.box):
                    self._draw(self.texture,self.targets[other],self.difference,4,command.brush)
                    box = command.box
                operation = {'segment':1,'commit':2,'cancel':3}[command.operation]
                self._draw(self.texture,self.targets[other],box,operation,command.brush,command.a,command.b)
                self.current,self.difference = other,command.box
                self.brush = command.brush
            self.overlay.set_texture_parameter_value('Source',self.texture)
            self._brush(self.overlay,self.brush)
            if doc.categorical:
                layer = 4
            elif doc.kind=='heightmap':
                layer = 0 if doc.mode=='add' else 1
            else:
                layer = 2 if doc.kind=='vegetation' else 3
            self.overlay.set_scalar_parameter_value('Layer',layer)
            if not doc.categorical:
                for name,color in (('Tint',COLORS['warm' if doc.kind=='heightmap' else doc.kind]),('Cold',COLORS['cold'])):
                    rgb = preview_color_linear('#'+''.join(f'{v:02X}' for v in color))
                    self.overlay.set_vector_parameter_value(name,self.ue.LinearColor(*rgb,1))
            doc.dirty = None
        except Exception:
            doc.invalidate_preview()
            self.document = None
            raise
        finally:
            self.submit_seconds += time.perf_counter()-started

    def close(self):
        if self.document is not None:self.document.invalidate_preview()
        for target in self.targets:
            self.ue.RenderingLibrary.release_render_target2d(target)
        for material,name in ((self.update,'Source'),(self.update,'Coverage'),(self.overlay,'Source'),(self.overlay,'Palette')):
            material.set_texture_parameter_value(name,None)
        self.targets,self.shape,self.document = [],None,None
        self.upload = None
