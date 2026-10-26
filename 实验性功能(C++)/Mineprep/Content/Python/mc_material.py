"""材质、纹理和渲染目标工具。"""
import struct
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

try:
    import unreal
except ModuleNotFoundError:
    from mc_utils import Lazy as unreal
from mc_utils import world, warn, List, iscollection

CLEAR = unreal.LinearColor(0, 0, 0, 0)
MASK = unreal.LinearColor(1, 1, 1, 1)
OPAQUE = unreal.BlendMode.BLEND_OPAQUE
FORMAT = unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB
NEAREST = unreal.TextureFilter.TF_NEAREST
CLAMP = unreal.TextureAddress.TA_CLAMP
BIOME_TEX_COLLECTION = '/Game/Mineprep/材质/Core/生物群系纹理集合'
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
    """二维 [y][x] 或一维像素列表。赋值为数字或 RGB 元组时存成 LinearColor。
    浮点下标是 UV（0~1），由 List 处理：grid[:0.5, :] 为上半，grid[:, 0.5:] 为右半。"""

    def __init__(self, *args):
        if len(args) == 1:
            arg = args[0]
            items = (arg,) if _is_color_like(arg) or not iscollection(arg) else arg
        else:
            items = args
        super().__init__(self._item(v) for v in items)

    @classmethod
    def from_rows(cls, rows):
        """按行创建二维颜色表，每个元素作为像素转换，保留各行长度。"""
        if not iscollection(rows):
            raise TypeError('rows must be an iterable of pixel rows')
        result = cls()
        for row in rows:
            if not iscollection(row):
                raise TypeError('each row must be an iterable of pixels')
            result.append(cls(to_linear(pixel) for pixel in row))
        return result

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
        warn('read_render_target_raw 失败')
        return ColorList()
    n = len(raw)
    if n != w * h:
        warn(f'tex_to_color 尺寸不符: {n} != {w}x{h}')
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
    rt.set_editor_properties(dict(
        clear_color=CLEAR,
        filter=NEAREST,
        address_x=CLAMP,
        address_y=CLAMP,
        render_target_format=FORMAT,
        srgb=True,
    ))
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
    """将 Texture2D 或 TextureRenderTarget2D 读取为二维 [y][x] 的 LinearColor (0~1) 颜色表。"""
    if isinstance(tex, unreal.TextureRenderTarget2D):
        return _rt_to_grid(tex)
    if isinstance(tex, unreal.Texture2D):
        w, h = get_tex_size(tex)
        rt = _blit_texture(tex, w, h)
        try:
            return _rt_to_grid(rt)
        finally:
            unreal.RenderingLibrary.release_render_target2d(rt)
    warn(f'tex_to_color 需要 Texture2D 或 TextureRenderTarget2D，实际是 {type(tex)!r}')
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
                warn(f'color_to_tex 长度 {n} 不是宽度 {width} 的整数倍')
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
            warn('color_to_tex 每一行长度必须相同')
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


def _same_biome_tex(slot, source) -> bool:
    if not slot or not source:
        return False
    return slot == source or slot.get_path_name() == source.get_path_name()


def _biome_collection(action):
    collection = unreal.load_asset(BIOME_TEX_COLLECTION)
    if not isinstance(collection, unreal.TextureCollection):
        warn(f'{action}找不到纹理集合: {BIOME_TEX_COLLECTION}')
        return None
    return collection


def _store_biome_slots(collection, slots, action):
    collection.set_editor_property('textures', slots)
    if not unreal.EditorAssetLibrary.save_loaded_asset(collection):
        warn(f'{action}保存失败: {BIOME_TEX_COLLECTION}')


def _biome_slot_keys(slots):
    return tuple(tex.get_path_name() if tex else None for tex in slots)


def register_biome_tex(source: unreal.Texture=None) -> int:
    """返回 source 在生物群系纹理集合中的索引；没有则优先写入空槽，否则追加到末尾。失败返回 -1。"""
    if not isinstance(source, unreal.Texture):
        return -1
    collection = _biome_collection('register_biome_tex ')
    if collection is None:
        return -1
    slots = list(collection.get_editor_property('textures') or [])
    for index, tex in enumerate(slots):
        if _same_biome_tex(tex, source):
            return index
    for index, tex in enumerate(slots):
        if not tex:
            slots[index] = source
            _store_biome_slots(collection, slots, 'register_biome_tex ')
            return index
    slots.append(source)
    _store_biome_slots(collection, slots, 'register_biome_tex ')
    return len(slots) - 1


def clear_biome_tex(target=None) -> bool:
    """整理生物群系纹理集合。默认去掉空槽和重复纹理。
    传入整数把该槽设为 None；传入纹理把匹配项设为 None；
    传入 True 只保留前两张，其余删除。有变更时保存并返回 True。"""
    collection = _biome_collection('clear_biome_tex ')
    if collection is None:
        return False
    slots = list(collection.get_editor_property('textures') or [])
    updated = _cleared_biome_slots(slots, target)
    if updated is None or _biome_slot_keys(updated) == _biome_slot_keys(slots):
        return False
    _store_biome_slots(collection, updated, 'clear_biome_tex ')
    return True


def _cleared_biome_slots(slots, target):
    if target is None:
        seen = set()
        updated = []
        for tex in slots:
            if not tex:
                continue
            path = tex.get_path_name()
            if path in seen:
                continue
            seen.add(path)
            updated.append(tex)
        return updated
    if target is True:
        return list(slots[:2])
    if isinstance(target, bool):
        warn(f'clear_biome_tex 不能把 {target!r} 当作槽位')
        return None
    if isinstance(target, int):
        index = target + len(slots) if target < 0 else target
        if index < 0 or index >= len(slots):
            warn(f'clear_biome_tex 槽位越界: {target}')
            return None
        updated = list(slots)
        updated[index] = None
        return updated
    if isinstance(target, unreal.Texture):
        updated = list(slots)
        for index, tex in enumerate(updated):
            if _same_biome_tex(tex, target):
                updated[index] = None
        return updated
    warn(f'clear_biome_tex 需要 None、整数、Texture 或 True，实际是 {type(target)!r}')
    return None


def color_to_tex(colors, width: int = 0) -> unreal.Texture2D | None:
    """用一维或二维 LinearColor/Color 数组生成临时 Texture2D。"""
    colors = colors if isinstance(colors, ColorList) else ColorList(colors)
    flat, w, h = _flatten_colors(colors, width)
    if not flat:
        warn('color_to_tex 需要非空的颜色数组')
        return None
    bmp = _colors_to_bmp32(flat, w, h)
    tex = unreal.RenderingLibrary.import_buffer_as_texture2d(world(), bmp)
    if not tex:
        warn('import_buffer_as_texture2d 失败')
        return None
    tex.set_editor_property('filter', NEAREST)
    tex.set_editor_property('srgb', True)
    _force_update(tex)
    return tex


def tex_source_files(texture: unreal.Texture2D) -> tuple[Path, ...]:
    """获取 Texture2D 导入时记录的源文件绝对路径列表（需在主线程调用）。"""
    if not isinstance(texture, unreal.Texture2D):
        raise TypeError('tex_source_files 需要 Texture2D')

    data = texture.get_editor_property('asset_import_data')
    if data is None:
        return ()

    return tuple(dict.fromkeys(
        Path(name).expanduser().resolve()
        for name in data.extract_filenames() if name
    ))


def export_tex_cache(texture: unreal.Texture2D, path='') -> Path:
    """将 Texture2D 的源数据导出到缓存目录（.png 或 .exr），同名且源数据未变时直接复用缓存文件。"""
    if not isinstance(texture, unreal.Texture2D):
        raise TypeError('export_tex_cache 需要 Texture2D')

    source_id = texture.blueprint_get_texture_source_id_string()
    if not source_id:
        raise ValueError('纹理没有有效TextureSource，不能使用资产导出器')
    if texture.get_editor_property('virtual_texture_streaming'):
        raise ValueError('export_tex_cache 暂不支持虚拟纹理')

    # 直接读取纹理的真实源数据格式 (SourceFormat)
    data = unreal.AssetRegistryHelpers.create_asset_data(texture)
    source_format = data.get_tag_value('SourceFormat') or ''
    source_format = source_format.replace(' ', '').replace('_', '').upper()

    formats = {
        'TSFG8': '.png',
        'TSFG16': '.png',
        'TSFBGRA8': '.png',
        'TSFRGBA16': '.png',
        'TSFBGRE8': '.exr',
        'TSFR16F': '.exr',
        'TSFR32F': '.exr',
        'TSFRGBA16F': '.exr',
        'TSFRGBA32F': '.exr',
    }
    extension = formats.get(source_format)
    if extension is None:
        raise ValueError(f'无法识别纹理源格式：{source_format!r}')

    project = Path(unreal.Paths.project_dir())
    directory = Path(path).expanduser() if path != '' else project / 'cache'
    if not directory.is_absolute():
        directory = project / directory
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)

    identity = (
        f'export_tex_cache:v1|{texture.get_path_name()}|'
        f'{source_id}|{extension}'
    )
    key = sha256(identity.encode('utf-8')).hexdigest()
    for length in range(8, len(key) + 1, 4):
        output = directory / f'{texture.get_name()[:32]}_{key[:length]}{extension}'
        record = output.with_suffix(extension + '.key')
        try:
            owner = record.read_text(encoding='ascii').strip()
        except (OSError, UnicodeError):
            owner = None
        if owner == key:
            if output.is_file() and output.stat().st_size > 0:
                if texture.blueprint_get_texture_source_id_string() != source_id:
                    raise RuntimeError('查询期间纹理源数据发生变化')
                return output
            if not output.exists() or output.is_file():
                break  # 若 .key 匹配但图片缺失或为空，则原地重新导出
        elif not output.exists() and not record.exists():
            break
    else:
        raise FileExistsError('纹理缓存短名已被其他内容占用')

    temporary = output.with_name(
        f'{output.stem}_{uuid4().hex[:8]}{output.suffix}'
    )
    temporary_record = temporary.with_suffix(extension + '.key')
    try:
        task = unreal.AssetExportTask()
        task.set_editor_properties(dict(
            object=texture,
            filename=str(temporary),
            automated=True,
            prompt=False,
            replace_identical=True,
            write_empty_files=False,
        ))

        # 由引擎根据目标后缀自动选择对应的导出器
        if not unreal.Exporter.run_asset_export_task(task):
            errors = '; '.join(task.get_editor_property('errors'))
            raise RuntimeError(errors or '纹理源数据导出失败')

        if texture.blueprint_get_texture_source_id_string() != source_id:
            raise RuntimeError('导出期间纹理源数据发生变化')
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise RuntimeError('导出未产生有效文件')

        temporary_record.write_text(key, encoding='ascii')
        temporary.replace(output)
        temporary_record.replace(record)  # 最后替换 .key 文件，确保缓存命中时图片已完整写入
        return output
    finally:
        temporary.unlink(missing_ok=True)
        temporary_record.unlink(missing_ok=True)


def import_data_tex(path) -> unreal.Texture2D:
    """从 PNG 或 EXR 文件导入线性色彩、最近邻采样的临时数据纹理 (Texture2D)。"""
    source = Path(path).expanduser().resolve()
    if source.suffix.lower() not in ('.png', '.exr'):
        raise ValueError('数据纹理输入须为PNG或EXR')
    if not source.is_file():
        raise FileNotFoundError(source)

    texture = unreal.RenderingLibrary.import_file_as_texture2d(
        world(), str(source)
    )
    if texture is None:
        raise RuntimeError(f'数据纹理导入失败：{source}')

    texture.set_editor_properties(dict(
        srgb=False,
        filter=NEAREST,
        address_x=CLAMP,
        address_y=CLAMP,
    ))
    _force_update(texture)
    return texture
