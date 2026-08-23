"""RT sketchpad: load a Texture2D, paint, save."""
import math
import os
import unreal
import mineprep
from mineprep import bilingual

RT = 64
DISPLAY = 512
SAVE_SUFFIX = '_2'
WHITE = '/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture'
CLEAR = unreal.LinearColor(0, 0, 0, 0)
MASK = unreal.LinearColor(1, 1, 1, 1)
FRAME = unreal.LinearColor(0.15, 0.15, 0.15, 1)
HINT_WHITE = unreal.LinearColor(1, 1, 1, 1)
NEAREST = unreal.TextureFilter.TF_NEAREST
OPAQUE = unreal.BlendMode.BLEND_OPAQUE
TRANSLUCENT = unreal.BlendMode.BLEND_TRANSLUCENT
FORMAT = unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB

# 64x64 Steve/Alex arm UV. Squeeze/stretch matches 811Alex/MCSkinConverter.
ARM_SHIFT = (
    (55, 16, 1, 32),
    (51, 16, 1, 4),
    (51, 32, 1, 4),
    (47, 16, 8, 32),
    (63, 48, 1, 16),
    (59, 48, 1, 4),
    (55, 48, 8, 16),
    (47, 48, 1, 16),
    (43, 48, 1, 4),
    (39, 48, 8, 16),
)
ARM_EDGE = (
    (40, 20, 16, 12),
    (40, 36, 16, 12),
    (32, 52, 16, 12),
    (48, 52, 16, 12),
    (44, 16, 8, 4),
    (44, 32, 8, 4),
    (36, 48, 8, 4),
    (52, 48, 8, 4),
)
# 1.8+ 64x64: inner (head/body/limbs) vs outer (hat/jacket/sleeves/pants).
INNER_BOXES = (
    (0, 0, 32, 16),
    (0, 16, 16, 16),
    (16, 16, 24, 16),
    (40, 16, 16, 16),
    (16, 48, 16, 16),
    (32, 48, 16, 16),
)
OUTER_BOXES = (
    (32, 0, 32, 16),
    (0, 32, 16, 16),
    (16, 32, 24, 16),
    (40, 32, 16, 16),
    (0, 48, 16, 16),
    (48, 48, 16, 16),
)


def tex_size(tex):
    return max(int(tex.blueprint_get_size_x()), 1), max(int(tex.blueprint_get_size_y()), 1)


def display_size(w, h, view=None):
    m = max(int(w), int(h), 1)
    view = max(float(view if view is not None else DISPLAY), 1.0)
    scale = view / m
    return unreal.Vector2D(max(1.0, w * scale), max(1.0, h * scale))


def package_path(obj):
    path = obj.get_path_name()
    if '.' in path:
        path = path.rsplit('.', 1)[0]
    return path


def save_path_from_tex(tex):
    if not isinstance(tex, unreal.Texture2D):
        return ''
    return package_path(tex) + SAVE_SUFFIX


def png_path_from_tex(tex):
    name = tex.get_name() if isinstance(tex, unreal.Texture2D) else 'skin'
    return os.path.normpath(os.path.join(
        unreal.Paths.project_saved_dir(), f'{name}.png'))


def split_png_path(path):
    path = (path or '').strip().strip('"').replace('\\', '/')
    if not path:
        raise ValueError(path)
    if not path.lower().endswith('.png'):
        path += '.png'
    directory, name = os.path.split(path)
    if not name:
        raise ValueError(path)
    if not directory:
        directory = os.path.normpath(unreal.Paths.project_saved_dir())
    return os.path.normpath(directory), name


def split_content_path(path):
    path = (path or '').strip().replace('\\', '/')
    if path.endswith('/'):
        path = path.rstrip('/')
    leaf = path.rsplit('/', 1)[-1]
    if '.' in leaf:
        path = path.rsplit('.', 1)[0]
    if '/' not in path:
        raise ValueError(path)
    directory, name = path.rsplit('/', 1)
    if not directory.startswith('/Game') or not name:
        raise ValueError(path)
    return directory, name


def force_update(tex):
    unreal.LandmassBlueprintFunctionLibrary.force_update_texture(tex)


class Pad:
    def __init__(self, tools):
        self.tools = tools
        self.world = mineprep.world()
        self.width = RT
        self.height = RT
        self.rt = self.make_rt(RT, RT)
        self.base = self.make_rt(RT, RT)
        self.cover = self.make_rt(RT, RT)
        self.white = unreal.load_object(None, WHITE)
        self.img = None
        self.drawing = False
        self.last = None
        self.ink = None
        self.nib = 8.0
        self.round = False
        self.replace = False
        self.peek = False
        self.hint = None
        self.sample_color = False
        self.hint_xy = None

    def make_rt(self, w, h):
        rt = unreal.RenderingLibrary.create_render_target2d(
            self.world, w, h, FORMAT, CLEAR)
        self.apply_sampling(rt, update=True)
        unreal.RenderingLibrary.clear_render_target2d(self.world, rt, CLEAR)
        return rt

    def apply_sampling(self, rt, update=False):
        rt.set_editor_property('clear_color', CLEAR)
        rt.set_editor_property('filter', NEAREST)
        rt.set_editor_property('address_x', unreal.TextureAddress.TA_CLAMP)
        rt.set_editor_property('address_y', unreal.TextureAddress.TA_CLAMP)
        rt.set_editor_property('render_target_format', FORMAT)
        rt.set_editor_property('srgb', True)
        if update:
            force_update(rt)

    def canvas_on(self, rt):
        canvas, size, ctx = unreal.RenderingLibrary.begin_draw_canvas_to_render_target(
            self.world, rt)
        if size.x < 1 or size.y < 1:
            size = unreal.Vector2D(self.width, self.height)
        return canvas, size, ctx

    def copy_rt(self, src, dest, color=MASK, blend=OPAQUE):
        canvas, size, ctx = self.canvas_on(dest)
        canvas.draw_texture(
            src, unreal.Vector2D(0, 0), size,
            unreal.Vector2D(0, 0), unreal.Vector2D(1, 1), color, blend)
        unreal.RenderingLibrary.end_draw_canvas_to_render_target(self.world, ctx)

    def pos(self, w):
        uv = w.get_mouse_uv()
        return unreal.Vector2D(uv.x * self.width, uv.y * self.height)

    def brush(self):
        return max(1.0, float(self.tools.BrushSize or 8))

    def color(self):
        return self.tools.Color or unreal.LinearColor(0, 0, 0, 1)

    def stamp(self, canvas, p, color, blend):
        size = self.nib
        r = size * 0.5
        if self.round:
            canvas.draw_polygon(
                self.white, p, unreal.Vector2D(r, r), 32, color)
            return
        canvas.draw_texture(
            self.white, unreal.Vector2D(p.x - r, p.y - r),
            unreal.Vector2D(size, size),
            unreal.Vector2D(0, 0), unreal.Vector2D(1, 1), color, blend)

    def stamp_segment(self, a, b):
        dx = b.x - a.x
        dy = b.y - a.y
        dist = math.hypot(dx, dy)
        n = max(1, int(math.ceil(dist)))
        target = self.rt if self.replace else self.cover
        color = self.ink if self.replace else MASK
        blend = OPAQUE if self.replace else TRANSLUCENT
        canvas, _, ctx = self.canvas_on(target)
        for i in range(n + 1):
            t = i / n
            self.stamp(
                canvas, unreal.Vector2D(a.x + dx * t, a.y + dy * t),
                color, blend)
        unreal.RenderingLibrary.end_draw_canvas_to_render_target(self.world, ctx)

    def composite(self):
        self.copy_rt(self.base, self.rt)
        canvas, size, ctx = self.canvas_on(self.rt)
        canvas.draw_texture(
            self.cover, unreal.Vector2D(0, 0), size,
            unreal.Vector2D(0, 0), unreal.Vector2D(1, 1),
            self.ink, TRANSLUCENT)
        unreal.RenderingLibrary.end_draw_canvas_to_render_target(self.world, ctx)

    def begin_stroke(self, p):
        self.drawing = True
        self.last = p
        self.ink = self.color()
        self.nib = self.brush()
        self.round = bool(self.tools.Round)
        self.replace = bool(self.tools.WriteAlpha)
        if self.replace:
            self.stamp_segment(p, p)
            return
        self.copy_rt(self.rt, self.base)
        unreal.RenderingLibrary.clear_render_target2d(self.world, self.cover, CLEAR)
        self.stamp_segment(p, p)
        self.composite()

    def pixel(self, w):
        uv = w.get_mouse_uv()
        x = min(self.width - 1, max(0, int(uv.x * self.width)))
        y = min(self.height - 1, max(0, int(uv.y * self.height)))
        return x, y

    def bind_hint(self, hint):
        self.hint = hint
        if hint and getattr(hint, 'target', None):
            hint.target.set_text('')
            hint.target.set_color_and_opacity(unreal.SlateColor(HINT_WHITE))

    def set_sample_color(self, on):
        self.sample_color = bool(on)
        if self.hint_xy:
            self.show_hint(*self.hint_xy)

    def show_hint(self, x, y, color=None):
        hint = self.hint
        if not hint or not getattr(hint, 'target', None):
            return
        try:
            if not unreal.SystemLibrary.is_valid(hint.target):
                return
        except Exception:
            return
        if color is None:
            hint.target.set_text(f'{x},{y}')
            hint.target.set_color_and_opacity(unreal.SlateColor(HINT_WHITE))
            return
        r, g, b, a = (int(color.r), int(color.g), int(color.b), int(color.a))
        hint.target.set_text(f'{x},{y}  #{r:02X}{g:02X}{b:02X} {a:02X}')
        hint.target.set_color_and_opacity(unreal.SlateColor(
            unreal.LinearColor(r / 255.0, g / 255.0, b / 255.0, 1.0)))

    def update_hint(self, w):
        x, y = self.pixel(w)
        self.hint_xy = (x, y)
        if not self.sample_color:
            self.show_hint(x, y)
            return
        self.show_hint(
            x, y,
            unreal.RenderingLibrary.read_render_target_pixel(
                self.world, self.rt, x, y))

    def down(self, w):
        self.begin_stroke(self.pos(w))
        self.update_hint(w)
        return True

    def move(self, w):
        if self.drawing:
            p = self.pos(w)
            self.stamp_segment(self.last, p)
            self.last = p
            if not self.replace:
                self.composite()
            self.update_hint(w)
            return True
        self.update_hint(w)
        return False

    def up(self, w):
        self.drawing = False
        return True

    def bind_image(self, img):
        self.img = img
        self.sync_image()

    def sync_image(self):
        img = self.img
        if not img or not getattr(img, 'target', None):
            return
        if not unreal.SystemLibrary.is_valid(img.target):
            return
        size = display_size(self.width, self.height, self.tools.ViewSize)
        resource = self.rt
        if self.peek and isinstance(self.tools.Texture, unreal.Texture2D):
            resource = self.tools.Texture
        if resource is self.rt:
            img.target.set_brush_resource_object(None)
        img.target.set_brush_resource_object(resource)
        img.target.set_desired_size_override(size)

    def show_source(self, on):
        self.peek = bool(on)
        self.sync_image()

    def resize(self, w, h):
        w, h = max(int(w), 1), max(int(h), 1)
        if (w, h) != (self.width, self.height):
            self.drawing = False
            for rt in (self.rt, self.base, self.cover):
                unreal.RenderingLibrary.resize_render_target2d(rt, w, h)
                self.apply_sampling(rt, update=True)
        self.width = max(int(self.rt.size_x), 1)
        self.height = max(int(self.rt.size_y), 1)

    def clear(self):
        self.drawing = False
        unreal.RenderingLibrary.clear_render_target2d(self.world, self.rt, CLEAR)
        unreal.RenderingLibrary.clear_render_target2d(self.world, self.cover, CLEAR)

    def blit(self, tex):
        canvas, size, ctx = self.canvas_on(self.rt)
        canvas.draw_texture(
            tex,
            unreal.Vector2D(0, 0),
            size,
            unreal.Vector2D(0, 0),
            unreal.Vector2D(1, 1),
            MASK,
            OPAQUE,
        )
        unreal.RenderingLibrary.end_draw_canvas_to_render_target(self.world, ctx)

    def load(self, tex):
        self.drawing = False
        if isinstance(tex, unreal.Texture2D):
            force_update(tex)
            w, h = tex_size(tex)
            self.resize(w, h)
            self.clear()
            self.blit(tex)
        else:
            self.resize(RT, RT)
            self.clear()
        self.sync_image()


def on_tools_changed(mod, name):
    name = str(name)
    if name == 'Texture':
        tex = mod.paint_tools.Texture
        mod.paint_tools.SavePath = save_path_from_tex(tex)
        mod.paint_tools.ExportPath = png_path_from_tex(tex)
        mod._pad.load(tex)
    elif name == 'ViewSize':
        mod._pad.sync_image()


def restore(mod):
    mod._pad.load(mod.paint_tools.Texture)


def _skin_scale(pad):
    w, h = pad.width, pad.height
    if w != h or w < RT or w % RT:
        return 0
    return w // RT


def _scaled(boxes, ratio):
    return tuple(tuple(int(v) * ratio for v in box) for box in boxes)


def _shift_rect(pad, x, y, w, h, dx, copy=False):
    pad.copy_rt(pad.rt, pad.base)
    tw = float(pad.width)
    th = float(pad.height)
    canvas, _, ctx = pad.canvas_on(pad.rt)
    if not copy:
        canvas.draw_texture(
            pad.white, unreal.Vector2D(x, y), unreal.Vector2D(w, h),
            unreal.Vector2D(0, 0), unreal.Vector2D(1, 1), CLEAR, OPAQUE)
    canvas.draw_texture(
        pad.base,
        unreal.Vector2D(x + dx, y), unreal.Vector2D(w, h),
        unreal.Vector2D(x / tw, y / th),
        unreal.Vector2D(w / tw, h / th),
        MASK, OPAQUE)
    unreal.RenderingLibrary.end_draw_canvas_to_render_target(pad.world, ctx)


def _shift_arms(pad, dx, dw, move, copy=False, reverse=False):
    boxes = _scaled(ARM_SHIFT, pad.width // RT)
    seq = reversed(boxes) if reverse else boxes
    for x, y, w, h in seq:
        _shift_rect(pad, x + dx, y, w + dw, h, move, copy)


def is_wide(pad):
    ratio = _skin_scale(pad)
    if not ratio:
        return False
    samples = unreal.RenderingLibrary.read_render_target(pad.world, pad.rt)
    if not samples:
        return False
    width = pad.width
    for x, y, w, h in _scaled(ARM_EDGE, ratio):
        left = x + w - ratio
        for yy in range(y, y + h):
            row = yy * width
            for xx in range(left, x + w):
                if int(samples[row + xx].a) > 0:
                    return True
    return False


def convert_arms(mod, slim):
    pad = mod._pad
    pad.drawing = False
    ratio = _skin_scale(pad)
    if not ratio:
        mineprep.warn(bilingual(
            '手臂转换需要正方形皮肤（64 的倍数）',
            'Arm convert needs a square skin (multiple of 64)'))
        return
    wide = is_wide(pad)
    if slim and not wide:
        mineprep.warn(bilingual('已经是细手臂', 'Already slim arms'))
        return
    if not slim and wide:
        mineprep.warn(bilingual('已经是宽手臂', 'Already wide arms'))
        return
    if slim:
        _shift_arms(pad, 0, 0, -ratio)
    else:
        _shift_arms(pad, -2 * ratio, ratio, ratio, copy=True, reverse=True)
    pad.sync_image()
    mineprep.prints(bilingual(
        '已转为细手臂' if slim else '已转为宽手臂',
        'Converted to slim arms' if slim else 'Converted to wide arms'))


def wide_arms(mod):
    convert_arms(mod, False)


def slim_arms(mod):
    convert_arms(mod, True)


def _tex_scale(tex):
    w, h = tex_size(tex)
    if w != h or w < RT or w % RT:
        return 0
    return w // RT


def keep_layer(mod, outer=False):
    tex = mod.paint_tools.Texture
    if not isinstance(tex, unreal.Texture2D):
        mineprep.warn(bilingual('请先指定皮肤纹理', 'Set a skin texture first'))
        return
    ratio = _tex_scale(tex)
    if not ratio:
        mineprep.warn(bilingual(
            '分层需要正方形皮肤（64 的倍数）',
            'Layers need a square skin (multiple of 64)'))
        return
    pad = mod._pad
    pad.drawing = False
    force_update(tex)
    w, h = tex_size(tex)
    pad.resize(w, h)
    pad.clear()
    tw = float(w)
    th = float(h)
    boxes = OUTER_BOXES if outer else INNER_BOXES
    canvas, _, ctx = pad.canvas_on(pad.rt)
    for x, y, bw, bh in _scaled(boxes, ratio):
        canvas.draw_texture(
            tex,
            unreal.Vector2D(x, y), unreal.Vector2D(bw, bh),
            unreal.Vector2D(x / tw, y / th),
            unreal.Vector2D(bw / tw, bh / th),
            MASK, OPAQUE)
    unreal.RenderingLibrary.end_draw_canvas_to_render_target(pad.world, ctx)
    pad.sync_image()
    mineprep.prints(bilingual(
        '已保留外层' if outer else '已保留内层',
        'Kept outer layer' if outer else 'Kept inner layer'))


def keep_inner(mod):
    keep_layer(mod, False)


def keep_outer(mod):
    keep_layer(mod, True)


def apply_overlay(mod):
    ov = mod.paint_tools.Overlay
    if not isinstance(ov, unreal.Texture2D):
        mineprep.warn(bilingual('请先指定叠加纹理', 'Set an overlay texture first'))
        return
    pad = mod._pad
    pad.drawing = False
    force_update(ov)
    canvas, size, ctx = pad.canvas_on(pad.rt)
    canvas.draw_texture(
        ov, unreal.Vector2D(0, 0), size,
        unreal.Vector2D(0, 0), unreal.Vector2D(1, 1),
        MASK, TRANSLUCENT)
    unreal.RenderingLibrary.end_draw_canvas_to_render_target(pad.world, ctx)
    pad.sync_image()
    mineprep.prints(bilingual('已叠加纹理', 'Overlay applied'))


def export_png(mod):
    pad = mod._pad
    path = (mod.paint_tools.ExportPath or '').strip()
    if not path:
        mineprep.warn(bilingual('请先指定导出PNG路径', 'Set an export PNG path first'))
        return
    try:
        directory, name = split_png_path(path)
    except ValueError:
        mineprep.warn(bilingual(f'无效导出路径: {path}', f'Invalid export path: {path}'))
        return
    os.makedirs(directory, exist_ok=True)
    unreal.RenderingLibrary.export_render_target(
        pad.world, pad.rt, directory, name)
    full = os.path.join(directory, name)
    mineprep.prints(bilingual(f'已导出 {full}', f'Exported {full}'))


def save(mod):
    pad = mod._pad
    path = (mod.paint_tools.SavePath or '').strip()
    if not path:
        mineprep.warn(bilingual('请先指定保存路径', 'Set a save path first'))
        return
    try:
        directory, name = split_content_path(path)
    except ValueError:
        mineprep.warn(bilingual(f'无效保存路径: {path}', f'Invalid save path: {path}'))
        return
    if not unreal.EditorAssetLibrary.does_directory_exist(directory):
        unreal.EditorAssetLibrary.make_directory(directory)
    full = f'{directory}/{name}'
    source = mod.paint_tools.Texture
    out = None
    if unreal.EditorAssetLibrary.does_asset_exist(full):
        out = unreal.load_asset(full)
    elif isinstance(source, unreal.Texture2D):
        out = unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset(
            name, directory, source)
    else:
        out = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, directory, unreal.Texture2D, unreal.Texture2DFactoryNew())
    if not isinstance(out, unreal.Texture2D):
        mineprep.warn(bilingual(f'无法写入纹理: {full}', f'Cannot write texture: {full}'))
        return
    unreal.RenderingLibrary.convert_render_target_to_texture2d_editor_only(
        pad.world, pad.rt, out)
    mineprep.prep_texture(out)
    unreal.EditorAssetLibrary.save_loaded_asset(out)
    mineprep.prints(bilingual(f'已保存 {full}', f'Saved {full}'))
