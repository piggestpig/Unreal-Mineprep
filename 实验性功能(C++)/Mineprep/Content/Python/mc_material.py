"""Material / Texture / RT helpers."""
import struct
import unreal
from mc_utils import world, warn, List, iscollection

CLEAR = unreal.LinearColor(0, 0, 0, 0)
MASK = unreal.LinearColor(1, 1, 1, 1)
OPAQUE = unreal.BlendMode.BLEND_OPAQUE
FORMAT = unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB
NEAREST = unreal.TextureFilter.TF_NEAREST
CLAMP = unreal.TextureAddress.TA_CLAMP
_U8 = (
    unreal.TextureRenderTargetFormat.RTF_R8,
    unreal.TextureRenderTargetFormat.RTF_RG8,
    unreal.TextureRenderTargetFormat.RTF_RGBA8,
    unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB,
)


def to_linear(c):
    if isinstance(c, unreal.LinearColor):
        return c
    if isinstance(c, unreal.Color):
        return unreal.LinearColor(
            c.r / 255.0, c.g / 255.0, c.b / 255.0, c.a / 255.0)
    c = (c, c, c, 1) if isinstance(c, (int, float)) else c
    c = (c[0], c[1], c[2], 1) if len(c) == 3 else c
    return unreal.LinearColor(*c)


def _is_color_like(c):
    if isinstance(c, (unreal.LinearColor, unreal.Color, int, float)):
        return True
    if isinstance(c, (list, tuple)) and 3 <= len(c) <= 4:
        return all(isinstance(x, (int, float)) for x in c)
    return False


class ColorList(List):
    """2D [y][x] or 1D pixel list. Assigning a number / RGB tuple stores LinearColor.
    Float indices are UV (0~1) via List: grid[:0.5, :] top half, grid[:, 0.5:] right half."""

    def __init__(self, *args):
        if len(args) == 1:
            arg = args[0]
            items = (arg,) if _is_color_like(arg) or not iscollection(arg) else arg
        else:
            items = args
        super().__init__(self._item(v) for v in items)

    @staticmethod
    def _item(v):
        if isinstance(v, ColorList):
            return v
        if _is_color_like(v):
            return to_linear(v)
        if iscollection(v):
            return ColorList(v)
        return to_linear(v)

    def __setitem__(self, index, value):
        super().__setitem__(index, self._item(value))

    def append(self, value):
        super().append(self._item(value))

    def insert(self, i, value):
        super().insert(i, self._item(value))

    def extend(self, values):
        super().extend(self._item(v) for v in values)


def get_tex_size(tex):
    if isinstance(tex, unreal.TextureRenderTarget2D):
        return max(int(tex.size_x), 1), max(int(tex.size_y), 1)
    return max(int(tex.blueprint_get_size_x()), 1), max(int(tex.blueprint_get_size_y()), 1)


def _force_update(tex):
    unreal.LandmassBlueprintFunctionLibrary.force_update_texture(tex)


def _unit(c, u8):
    if not u8:
        return unreal.LinearColor(c.r, c.g, c.b, c.a)
    return unreal.LinearColor(c.r / 255.0, c.g / 255.0, c.b / 255.0, c.a / 255.0)


def _rt_to_grid(rt):
    w, h = get_tex_size(rt)
    raw = unreal.RenderingLibrary.read_render_target_raw(world(), rt)
    if not raw:
        warn('read_render_target_raw failed')
        return ColorList()
    n = len(raw)
    if n != w * h:
        warn(f'tex_to_color size mismatch: {n} != {w}x{h}')
        return ColorList()
    u8 = rt.get_editor_property('render_target_format') in _U8
    return ColorList(
        ColorList(_unit(raw[y * w + x], u8) for x in range(w))
        for y in range(h)
    )


def _blit_texture(tex, w, h):
    ctx_world = world()
    rt = unreal.RenderingLibrary.create_render_target2d(
        ctx_world, w, h, FORMAT, CLEAR)
    rt.set_editor_property('clear_color', CLEAR)
    rt.set_editor_property('filter', NEAREST)
    rt.set_editor_property('address_x', CLAMP)
    rt.set_editor_property('address_y', CLAMP)
    rt.set_editor_property('render_target_format', FORMAT)
    rt.set_editor_property('srgb', True)
    _force_update(rt)
    _force_update(tex)
    canvas, size, ctx = unreal.RenderingLibrary.begin_draw_canvas_to_render_target(
        ctx_world, rt)
    if size.x < 1 or size.y < 1:
        size = unreal.Vector2D(w, h)
    canvas.draw_texture(
        tex, unreal.Vector2D(0, 0), size,
        unreal.Vector2D(0, 0), unreal.Vector2D(1, 1), MASK, OPAQUE)
    unreal.RenderingLibrary.end_draw_canvas_to_render_target(ctx_world, ctx)
    return rt


def tex_to_color(tex: unreal.Texture2D | unreal.TextureRenderTarget2D) -> ColorList:
    """Read a Texture2D or TextureRenderTarget2D as [y][x] LinearColor (0–1)."""
    if isinstance(tex, unreal.TextureRenderTarget2D):
        return _rt_to_grid(tex)
    if isinstance(tex, unreal.Texture2D):
        w, h = get_tex_size(tex)
        rt = _blit_texture(tex, w, h)
        try:
            return _rt_to_grid(rt)
        finally:
            unreal.RenderingLibrary.release_render_target2d(rt)
    warn(f'tex_to_color expected Texture2D or TextureRenderTarget2D, got {type(tex)!r}')
    return ColorList()


###########################################################################


def _is_color(c):
    return isinstance(c, (unreal.LinearColor, unreal.Color))


def _to_u8(value):
    return max(0, min(255, int(round(float(value) * 255.0))))


def _bgra(c):
    if isinstance(c, unreal.Color):
        return int(c.b), int(c.g), int(c.r), int(c.a)
    r, g, b, a = float(c.r), float(c.g), float(c.b), float(c.a)
    if max(r, g, b, a) > 1.0:
        return (
            max(0, min(255, int(round(b)))),
            max(0, min(255, int(round(g)))),
            max(0, min(255, int(round(r)))),
            max(0, min(255, int(round(a)))),
        )
    return _to_u8(b), _to_u8(g), _to_u8(r), _to_u8(a)


def _flatten_colors(colors, width=0):
    if not colors:
        return None, 0, 0
    first = colors[0]
    if _is_color(first):
        flat = list(colors)
        n = len(flat)
        if width > 0:
            if n % width:
                warn(f'color_to_tex length {n} is not a multiple of width {width}')
                return None, 0, 0
            return flat, width, n // width
        side = int(n ** 0.5)
        if side * side == n:
            return flat, side, side
        return flat, n, 1
    h = len(colors)
    w = len(first)
    flat = []
    for row in colors:
        if len(row) != w:
            warn('color_to_tex rows must be the same length')
            return None, 0, 0
        flat.extend(row)
    return flat, w, h


def _colors_to_bmp32(flat, width, height):
    stride = width * 4
    raw = bytearray(stride * height)
    for y in range(height):
        src_y = height - 1 - y
        offset = y * stride
        row = src_y * width
        for x in range(width):
            b, g, r, a = _bgra(flat[row + x])
            i = offset + x * 4
            raw[i] = b
            raw[i + 1] = g
            raw[i + 2] = r
            raw[i + 3] = a
    pixel_off = 54
    header = b'BM' + struct.pack('<IHHI', pixel_off + len(raw), 0, 0, pixel_off)
    header += struct.pack(
        '<IiiHHIIiiII', 40, width, height, 1, 32, 0, len(raw), 0, 0, 0, 0)
    return header + bytes(raw)


def color_to_tex(colors, width: int = 0) -> unreal.Texture2D | None:
    """Build a transient Texture2D from a 1D or 2D LinearColor/Color array."""
    colors = colors if isinstance(colors, ColorList) else ColorList(colors)
    flat, w, h = _flatten_colors(colors, width)
    if not flat:
        warn('color_to_tex needs a non-empty color array')
        return None
    bmp = _colors_to_bmp32(flat, w, h)
    tex = unreal.RenderingLibrary.import_buffer_as_texture2d(world(), bmp)
    if not tex:
        warn('import_buffer_as_texture2d failed')
        return None
    tex.set_editor_property('filter', NEAREST)
    tex.set_editor_property('srgb', True)
    _force_update(tex)
    return tex
