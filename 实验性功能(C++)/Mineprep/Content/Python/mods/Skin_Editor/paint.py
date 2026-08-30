"""RT sketchpad: load a Texture2D, paint, save."""
import math
import os
import unreal
import mineprep
from mineprep import bilingual

RT = 64
DISPLAY = 512
VIEW_MIN = 64
VIEW_MAX = 2048
VIEW_STEP = 32
SAVE_SUFFIX = '_2'
BATCH_DIR = '/Game/mc/tex'
WHITE = '/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture'
CLEAR = unreal.LinearColor(0, 0, 0, 0)
MASK = unreal.LinearColor(1, 1, 1, 1)
FRAME = unreal.LinearColor(0.15, 0.15, 0.15, 1)
HINT_WHITE = unreal.LinearColor(1, 1, 1, 1)
NEAREST = unreal.TextureFilter.TF_NEAREST
OPAQUE = unreal.BlendMode.BLEND_OPAQUE
TRANSLUCENT = unreal.BlendMode.BLEND_TRANSLUCENT
FORMAT = unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB


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


def srgb_to_linear(c):
    """read_render_target_pixel returns sRGB FColor; the Color picker stores LinearColor."""
    linear = unreal.LinearColor()
    linear.set_from_srgb(c)
    return linear


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
        self.hover = None
        self._overlay_src = None
        self._overlay_colors = None

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
            hint.target.set_text(f'{y},{x}')
            hint.target.set_color_and_opacity(unreal.SlateColor(HINT_WHITE))
            return
        r, g, b, a = (int(color.r), int(color.g), int(color.b), int(color.a))
        hint.target.set_text(f'{y},{x}  #{r:02X}{g:02X}{b:02X} {a:02X}')
        linear = srgb_to_linear(color)
        hint.target.set_color_and_opacity(unreal.SlateColor(
            unreal.LinearColor(linear.r, linear.g, linear.b, 1.0)))

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

    def bind_hover(self, hover):
        self.hover = hover

    def overlay_colors(self):
        ov = self.tools.Overlay
        if not isinstance(ov, unreal.Texture2D):
            return None
        if ov is self._overlay_src:
            return self._overlay_colors
        colors = mineprep.tex_to_color(ov)
        if not colors:
            return None
        self._overlay_src = ov
        self._overlay_colors = colors
        return colors

    def pick_color(self):
        hover = self.hover
        if hover and getattr(hover, 'target', None):
            try:
                if unreal.SystemLibrary.is_valid(hover.target):
                    uv = hover.get_mouse_uv()
                    if 0.0 <= uv.x <= 1.0 and 0.0 <= uv.y <= 1.0:
                        x, y = self.pixel(hover)
                        self.hint_xy = (x, y)
            except Exception:
                pass
        if not self.hint_xy:
            return
        x, y = self.hint_xy
        c = unreal.RenderingLibrary.read_render_target_pixel(
            self.world, self.rt, x, y)
        self.tools.Color = srgb_to_linear(c)
        if self.sample_color:
            self.show_hint(x, y, c)

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
    elif name == 'Advanced':
        col = getattr(mod, '_batch', None)
        if col:
            col.hide(not mod.paint_tools.Advanced)


def nudge_view(mod, delta):
    if not delta:
        return
    view = float(mod.paint_tools.ViewSize or DISPLAY)
    view = view + (VIEW_STEP if delta > 0 else -VIEW_STEP)
    view = min(VIEW_MAX, max(VIEW_MIN, view))
    if view == float(mod.paint_tools.ViewSize or DISPLAY):
        return
    mod.paint_tools.ViewSize = view
    mod._pad.sync_image()


def restore(mod):
    mod._pad.load(mod.paint_tools.Texture)


def use_snippet(mod, name):
    from . import snippets
    mod.code_tools.Code = snippets.source(name)
    run_code(mod)


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


def _compile_main(mod):
    code = (mod.code_tools.Code or '').strip()
    if not code:
        mineprep.warn(bilingual('请先填写代码', 'Write a script first'))
        return None
    ns = {
        'unreal': unreal, 'mineprep': mineprep, 'ColorList': mineprep.ColorList,
        '__name__': 'skin_code',
    }
    try:
        exec(code, ns)
    except Exception as e:
        mineprep.warn(bilingual(f'编译失败: ', f'Compile failed: '), e)
        return None
    main = ns.get('main')
    if not callable(main):
        mineprep.warn(bilingual(
            '代码需要 def main(tex, overlay)',
            'Script needs def main(tex, overlay)'))
        return None
    return main


def _eval_main(main, tex, overlay):
    result = main(tex, overlay)
    if result is None:
        result = tex
    return mineprep.ColorList(result)


def run_code(mod):
    pad = getattr(mod, '_pad', None)
    if not pad or not pad.rt:
        mineprep.warn(bilingual('画布未就绪', 'Canvas is not ready'))
        return
    tex = mineprep.tex_to_color(pad.rt)
    if not tex:
        return
    overlay = pad.overlay_colors()
    main = _compile_main(mod)
    if not main:
        return
    try:
        result = _eval_main(main, tex, overlay)
    except Exception as e:
        mineprep.warn(bilingual(f'运行失败: ', f'Script failed: '), e)
        return
    out = mineprep.color_to_tex(result)
    if not out:
        return
    pad.load(out)


def run_batch(mod):
    sources = list(mod.batch_tools.Textures or [])
    if not any(isinstance(t, unreal.Texture2D) for t in sources):
        mineprep.warn(bilingual(
            '请先在批量处理中指定纹理',
            'Set textures in Batch Process first'))
        return
    main = _compile_main(mod)
    if not main:
        return
    pad = getattr(mod, '_pad', None)
    overlay = pad.overlay_colors() if pad else None
    outs = []
    ok = 0
    for i, src in enumerate(sources):
        if not isinstance(src, unreal.Texture2D):
            outs.append(None)
            continue
        tex = mineprep.tex_to_color(src)
        if not tex:
            mineprep.warn(bilingual(
                f'第 {i + 1} 张读取失败',
                f'Texture {i + 1} failed to read'))
            outs.append(None)
            continue
        try:
            result = _eval_main(main, tex, overlay)
        except Exception as e:
            mineprep.warn(bilingual(
                f'第 {i + 1} 张运行失败: ',
                f'Texture {i + 1} failed: '), e)
            outs.append(None)
            continue
        out = mineprep.color_to_tex(result)
        if not out:
            outs.append(None)
            continue
        outs.append(out)
        ok += 1
    mod.batch_tools.NewTextures = outs
    mineprep.prints(bilingual(
        f'已处理 {ok}/{len(sources)} 张',
        f'Processed {ok}/{len(sources)}'))


def _copy_tex_to_asset(src, directory, name, template=None):
    if not unreal.EditorAssetLibrary.does_directory_exist(directory):
        unreal.EditorAssetLibrary.make_directory(directory)
    full = f'{directory}/{name}'
    dest = None
    if unreal.EditorAssetLibrary.does_asset_exist(full):
        dest = unreal.load_asset(full)
    else:
        seed = template if isinstance(template, unreal.Texture2D) else src
        dest = unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset(
            name, directory, seed)
    if not isinstance(dest, unreal.Texture2D):
        return None
    ctx = mineprep.world()
    w, h = tex_size(src)
    rt = unreal.RenderingLibrary.create_render_target2d(ctx, w, h, FORMAT, CLEAR)
    canvas, size, draw = unreal.RenderingLibrary.begin_draw_canvas_to_render_target(
        ctx, rt)
    if size.x < 1 or size.y < 1:
        size = unreal.Vector2D(float(w), float(h))
    canvas.draw_texture(
        src, unreal.Vector2D(0, 0), size,
        unreal.Vector2D(0, 0), unreal.Vector2D(1, 1), MASK, OPAQUE)
    unreal.RenderingLibrary.end_draw_canvas_to_render_target(ctx, draw)
    unreal.RenderingLibrary.convert_render_target_to_texture2d_editor_only(
        ctx, rt, dest)
    unreal.RenderingLibrary.release_render_target2d(rt)
    mineprep.prep_texture(dest)
    unreal.EditorAssetLibrary.save_loaded_asset(dest)
    return dest


def save_batch(mod):
    originals = list(mod.batch_tools.Textures or [])
    news = list(mod.batch_tools.NewTextures or [])
    if not news:
        mineprep.warn(bilingual('没有可保存的新纹理', 'No new textures to save'))
        return
    beside = bool(mod.batch_tools.BesideOriginal)
    saved = []
    ok = 0
    for i, out in enumerate(news):
        if not isinstance(out, unreal.Texture2D):
            saved.append(None)
            continue
        src = originals[i] if i < len(originals) else None
        if isinstance(src, unreal.Texture2D):
            path = package_path(src)
            orig_dir, base = path.rsplit('/', 1) if '/' in path else (BATCH_DIR, src.get_name())
            directory = orig_dir if beside else BATCH_DIR
        else:
            directory, base = BATCH_DIR, 'skin'
        name = f'{base}_{i + 1}'
        dest = _copy_tex_to_asset(
            out, directory, name,
            src if isinstance(src, unreal.Texture2D) else out)
        if not dest:
            mineprep.warn(bilingual(
                f'第 {i + 1} 张保存失败',
                f'Texture {i + 1} failed to save'))
            saved.append(None)
            continue
        saved.append(dest)
        ok += 1
        mineprep.prints(bilingual(
            f'已保存 {directory}/{name}',
            f'Saved {directory}/{name}'))
    mod.batch_tools.NewTextures = saved
    mineprep.prints(bilingual(
        f'已保存 {ok}/{len(news)} 张',
        f'Saved {ok}/{len(news)}'))
