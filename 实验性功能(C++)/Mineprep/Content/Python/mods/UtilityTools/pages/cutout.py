"""按采样色去掉连到边缘的背景，并保存带透明通道的纹理。"""
import os
import shutil
import tempfile

import cv2
import numpy as np
import unreal
import mineprep
from mineprep import i18n

ID = 'cutout'
ORDER = 1
LABEL = i18n('抠图', 'Cutout')

_IMAGE_TYPES = [('Image', '*.png *.jpg *.jpeg *.tga *.bmp *.exr')]
_BLACK = (unreal.LinearColor(0, 0, 0, 1), 28)
_WHITE = (unreal.LinearColor(1, 1, 1, 1), 28)
_GREEN = (unreal.LinearColor(0, 1, 0, 1), 48)


class CutoutProps(mineprep.PropertyGroup):
    Source: unreal.Texture2D = (None, {'DisplayName': '源纹理', 'Category': '抠图'})
    KeyColor: unreal.LinearColor = (
        unreal.LinearColor(0, 0, 0, 1), {'DisplayName': '采样色', 'Category': '抠图'})
    Tolerance: int = (28, {'DisplayName': '容差', 'ClampMin': 0, 'ClampMax': 255, 'Category': '抠图'})
    Contract: int = (0, {'DisplayName': '收缩', 'ClampMin': 0, 'ClampMax': 16, 'Category': '抠图'})
    Feather: int = (0, {'DisplayName': '羽化', 'ClampMin': 0, 'ClampMax': 16, 'Category': '抠图'})
    EdgeOnly: bool = (True, {'DisplayName': '只连边缘', 'Category': '抠图'})
    Directory: str = ('/Game/mc/tex/Cutouts', {'DisplayName': '保存路径', 'Category': '抠图'})
    FileName: str = ('Cutout', {'DisplayName': '文件名', 'Category': '抠图'})


def import_file(path):
    """把一张图片导入为临时纹理。失败时返回 None。"""
    tex = unreal.RenderingLibrary.import_file_as_texture2d(mineprep.world(), str(path))
    if tex is None:
        mineprep.warn(i18n('导入失败: {path}', 'Import failed: {path}').format(path=str(path)))
        return None
    tex.set_editor_properties({
        'srgb': True,
        'filter': unreal.TextureFilter.TF_NEAREST,
    })
    return tex


def _byte(pixel, channel):
    value = float(getattr(pixel, channel))
    if value > 1.0:
        value = value / 255.0
    return max(0, min(255, int(round(value * 255.0))))


def _split_image(image):
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR), np.full(image.shape, 255, np.uint8)
    if image.shape[2] == 4:
        return image[:, :, :3].copy(), image[:, :, 3].copy()
    return image[:, :, :3].copy(), np.full(image.shape[:2], 255, np.uint8)


def _read_texture(texture):
    if not isinstance(texture, unreal.Texture2D):
        return None
    width = max(int(texture.blueprint_get_size_x()), 1)
    height = max(int(texture.blueprint_get_size_y()), 1)
    world = mineprep.world()
    clear = unreal.LinearColor(0, 0, 0, 0)
    rt = unreal.RenderingLibrary.create_render_target2d(
        world, width, height, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB, clear)
    if rt is None:
        return None
    folder = tempfile.mkdtemp()
    image = None
    try:
        rt.set_editor_properties({
            'clear_color': clear,
            'filter': unreal.TextureFilter.TF_NEAREST,
            'address_x': unreal.TextureAddress.TA_CLAMP,
            'address_y': unreal.TextureAddress.TA_CLAMP,
            'render_target_format': unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB,
            'srgb': True,
        })
        unreal.LandmassBlueprintFunctionLibrary.force_update_texture(rt)
        unreal.LandmassBlueprintFunctionLibrary.force_update_texture(texture)
        canvas, size, ctx = unreal.RenderingLibrary.begin_draw_canvas_to_render_target(world, rt)
        if size.x < 1 or size.y < 1:
            size = unreal.Vector2D(width, height)
        canvas.draw_texture(
            texture, unreal.Vector2D(0, 0), size,
            unreal.Vector2D(0, 0), unreal.Vector2D(1, 1),
            unreal.LinearColor(1, 1, 1, 1), unreal.BlendMode.BLEND_OPAQUE)
        unreal.RenderingLibrary.end_draw_canvas_to_render_target(world, ctx)
        unreal.RenderingLibrary.export_render_target(world, rt, folder, 'pixels.png')
        image = cv2.imread(os.path.join(folder, 'pixels.png'), cv2.IMREAD_UNCHANGED)
    finally:
        unreal.RenderingLibrary.release_render_target2d(rt)
        shutil.rmtree(folder, ignore_errors=True)
    if image is None or image.size == 0:
        return None
    return _split_image(image)


def _alpha_mask(bgr, color, tolerance, contract, feather, edge_only):
    tolerance = max(0, min(255, int(tolerance)))
    contract = max(0, min(16, int(contract)))
    feather = max(0, min(16, int(feather)))
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2Lab).astype(np.float32)
    key = np.array([[[_byte(color, 'b'), _byte(color, 'g'), _byte(color, 'r')]]], np.uint8)
    key_lab = cv2.cvtColor(key, cv2.COLOR_BGR2Lab).astype(np.float32)[0, 0]
    background = np.sqrt(np.sum((lab - key_lab) ** 2, axis=2)) <= tolerance
    if edge_only:
        labels = cv2.connectedComponents(background.astype(np.uint8), connectivity=4)[1]
        edge = np.unique(np.concatenate([
            labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1],
        ]))
        keep = edge[edge != 0]
        background = np.isin(labels, keep) if keep.size else np.zeros(background.shape, bool)
    if contract:
        size = contract * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
        background = cv2.dilate(background.astype(np.uint8), kernel).astype(bool)
    alpha = np.where(background, 0, 255).astype(np.uint8)
    if feather:
        alpha = cv2.GaussianBlur(alpha, (feather * 2 + 1, feather * 2 + 1), 0)
    return alpha


def _apply(bgr, source_alpha, color, tolerance, contract, feather, edge_only):
    alpha = _alpha_mask(bgr, color, tolerance, contract, feather, edge_only)
    alpha = (alpha.astype(np.uint16) * source_alpha.astype(np.uint16) // 255).astype(np.uint8)
    return np.dstack([bgr[:, :, 2], bgr[:, :, 1], bgr[:, :, 0], alpha])


def _rgba(texture, color, tolerance=28, contract=0, feather=0, edge_only=True):
    arrays = _read_texture(texture)
    if arrays is None:
        return None
    bgr, source_alpha = arrays
    return _apply(bgr, source_alpha, color, tolerance, contract, feather, edge_only), bgr


def _checker(rgba):
    height, width = rgba.shape[:2]
    yy, xx = np.indices((height, width))
    shade = np.where(((xx // 8 + yy // 8) & 1) == 0, 32, 56).astype(np.float32)
    coverage = rgba[:, :, 3:4].astype(np.float32) / 255.0
    rgb = rgba[:, :, :3].astype(np.float32) * coverage + shade[..., None] * (1.0 - coverage)
    image = np.empty_like(rgba)
    image[:, :, :3] = np.clip(rgb, 0, 255)
    image[:, :, 3] = 255
    return image


def _texture_from_rgba(rgba):
    bgra = np.dstack([rgba[:, :, 2], rgba[:, :, 1], rgba[:, :, 0], rgba[:, :, 3]])
    ok, encoded = cv2.imencode('.png', bgra)
    if not ok:
        return None
    tex = unreal.RenderingLibrary.import_buffer_as_texture2d(mineprep.world(), encoded.tobytes())
    if tex is None:
        return None
    tex.set_editor_properties({
        'srgb': True,
        'filter': unreal.TextureFilter.TF_NEAREST,
    })
    unreal.LandmassBlueprintFunctionLibrary.force_update_texture(tex)
    return tex


def cutout(texture, color, tolerance=28, contract=0, feather=0, edge_only=True):
    """按采样色抠图，返回带透明通道的临时纹理。失败时返回 None。"""
    evaluated = _rgba(texture, color, tolerance, contract, feather, edge_only)
    if evaluated is None:
        mineprep.warn(i18n('没有可抠的纹理', 'No texture to cut out'))
        return None
    return _texture_from_rgba(evaluated[0])


def _destination(directory, name):
    directory = (directory or '').strip().replace('\\', '/').rstrip('/')
    name = (name or '').strip()
    if not directory.startswith('/Game/'):
        mineprep.warn(i18n('请选择 /Game 下的目录', 'Choose a directory under /Game'))
        return None
    if not name or '/' in name or '\\' in name:
        mineprep.warn(i18n('文件名不能为空或包含斜杠', 'File name must not be empty or contain a slash'))
        return None
    return directory, name


def export_png(texture, color, path, tolerance=28, contract=0, feather=0, edge_only=True, rgba=None):
    """把抠图结果写成本地 PNG。rgba 可传入已算好的数组，避免再读一遍纹理。"""
    if rgba is None:
        evaluated = _rgba(texture, color, tolerance, contract, feather, edge_only)
        if evaluated is None:
            mineprep.warn(i18n('没有可抠的纹理', 'No texture to cut out'))
            return ''
        rgba = evaluated[0]
    from PIL import Image
    Image.fromarray(rgba, 'RGBA').save(str(path))
    return str(path)


def save_cutout(texture, color, directory, name, tolerance=28, contract=0, feather=0, edge_only=True):
    """把抠图结果保存为纹理资产。失败时返回 None。"""
    place = _destination(directory, name)
    if place is None:
        return None
    evaluated = _rgba(texture, color, tolerance, contract, feather, edge_only)
    if evaluated is None:
        mineprep.warn(i18n('没有可抠的纹理', 'No texture to cut out'))
        return None
    directory, name = place
    from PIL import Image
    image = Image.fromarray(evaluated[0], 'RGBA')
    handle, filename = tempfile.mkstemp(suffix='.png')
    os.close(handle)
    try:
        image.save(filename)
        task = unreal.AssetImportTask()
        task.set_editor_property('filename', filename)
        task.set_editor_property('destination_path', directory)
        task.set_editor_property('destination_name', name)
        task.set_editor_property('automated', True)
        task.set_editor_property('save', True)
        task.set_editor_property('replace_existing', True)
        task.set_editor_property('replace_existing_settings', True)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    finally:
        os.remove(filename)
    asset = unreal.load_asset(f'{directory}/{name}')
    if not isinstance(asset, unreal.Texture2D):
        mineprep.warn(i18n('无法保存抠图: {path}', 'Cannot save cutout: {path}').format(
            path=f'{directory}/{name}'))
        return None
    asset.set_editor_properties({
        'srgb': True,
        'filter': unreal.TextureFilter.TF_NEAREST,
        'mip_gen_settings': unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS,
    })
    unreal.EditorAssetLibrary.save_loaded_asset(asset)
    return asset


def draw(mod, layout):
    CutoutProps.localize(i18n)
    props = CutoutProps()
    shown = {}

    def source_pixels():
        tex = props.Source
        if not isinstance(tex, unreal.Texture2D):
            shown['tex'] = shown['bgr'] = shown['alpha'] = None
            return None
        if shown.get('tex') is tex and shown.get('bgr') is not None:
            return shown['bgr'], shown['alpha']
        arrays = _read_texture(tex)
        if arrays is None:
            shown['tex'] = shown['bgr'] = shown['alpha'] = None
            return None
        shown['tex'] = tex
        shown['bgr'], shown['alpha'] = arrays
        return arrays

    def show():
        arrays = source_pixels()
        if arrays is None:
            image.hide(True)
            return
        bgr, source_alpha = arrays
        rgba = _apply(
            bgr, source_alpha, props.KeyColor, props.Tolerance,
            props.Contract, props.Feather, props.EdgeOnly)
        preview = _texture_from_rgba(_checker(rgba))
        if preview is None:
            image.hide(True)
            return
        image.set_brush_from_texture(preview, False)
        image.set_desired_size_override(unreal.Vector2D(
            preview.blueprint_get_size_x(), preview.blueprint_get_size_y()))
        image.hide(unreal.SlateVisibility.HIT_TEST_INVISIBLE)

    def refresh(_name=''):
        show()

    def use(color, tolerance):
        props.KeyColor = color
        props.Tolerance = tolerance
        refresh()

    def do_import():
        path = mineprep.askopenfilename(
            title=str(i18n('导入图片', 'Import Images')),
            filetypes=_IMAGE_TYPES,
        )
        if not path:
            return
        tex = import_file(path)
        if tex is None:
            return
        props.Source = tex
        refresh()

    def do_save():
        asset = save_cutout(
            props.Source, props.KeyColor, props.Directory, props.FileName,
            props.Tolerance, props.Contract, props.Feather, props.EdgeOnly)
        if asset:
            mineprep.prints(asset.get_path_name())

    def do_export():
        path = mineprep.asksaveasfilename(
            title=str(i18n('导出图片', 'Export Image')),
            defaultextension='.png',
            initialfile=props.FileName or 'Cutout',
            filetypes=[('PNG', '*.png')],
        )
        if not path:
            return
        rgba = None
        if shown.get('bgr') is not None and shown.get('tex') is props.Source:
            rgba = _apply(
                shown['bgr'], shown['alpha'], props.KeyColor, props.Tolerance,
                props.Contract, props.Feather, props.EdgeOnly)
        saved = export_png(
            props.Source, props.KeyColor, path, props.Tolerance,
            props.Contract, props.Feather, props.EdgeOnly, rgba)
        if saved:
            mineprep.prints(saved)

    def pick(border):
        bgr = shown.get('bgr')
        if bgr is None or mineprep.left_mouse_down() is not True:
            return False
        uv = border.get_mouse_uv()
        if uv.x < 0.0 or uv.y < 0.0 or uv.x > 1.0 or uv.y > 1.0:
            return False
        height, width = bgr.shape[:2]
        x = min(width - 1, int(uv.x * width))
        y = min(height - 1, int(uv.y * height))
        blue, green, red = (int(channel) for channel in bgr[y, x])
        props.KeyColor = unreal.LinearColor(red / 255.0, green / 255.0, blue / 255.0, 1)
        refresh()
        return True

    split = layout.splitter(ratio=0.62, fill=1, limits=(0.3, 0.85))
    box = split.first.scalebox(fill=1, align=(0, 0))
    box.target.set_editor_property('Stretch', unreal.Stretch.SCALE_TO_FIT)
    box.target.set_editor_property('StretchDirection', unreal.StretchDirection.BOTH)
    border = box.border(fill=1, align=(0, 0), clip=True, on_mouse_button_down=pick)
    image = border.overlay().image(size=unreal.Vector2D(1, 1), padding=0, align=(2, 2))
    image.hide(True)

    side = split.second.col(fill=1, align=(0, 0), padding=4)
    side.button(i18n('导入图片', 'Import Images'), on_clicked=do_import, padding=3)
    presets = side.row(padding=3)
    presets.button(i18n('黑底', 'Black'), on_clicked=lambda: use(*_BLACK), fill=1, padding=(0, 0, 2, 0))
    presets.button(i18n('白底', 'White'), on_clicked=lambda: use(*_WHITE), fill=1, padding=(0, 0, 2, 0))
    presets.button(i18n('绿幕', 'Green Screen'), on_clicked=lambda: use(*_GREEN), fill=1)
    side.button(i18n('保存抠图', 'Save Cutout'), on_clicked=do_save, padding=3)
    side.prop(props, on_property_changed=refresh)
    side.button(i18n('导出图片', 'Export Image'), on_clicked=do_export, padding=3)
