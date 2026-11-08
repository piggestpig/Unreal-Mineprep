"""生成固定尺寸、固定颜色的纹理。"""
import os
import tempfile

import numpy as np
import unreal
import mineprep
from mineprep import i18n

ID = 'solid'
ORDER = 2
LABEL = i18n('纯色图片', 'Solid Color')


class SolidProps(mineprep.PropertyGroup):
    Size: unreal.IntPoint = (unreal.IntPoint(1, 1), {
        'DisplayName': '尺寸', 'ClampMin': 1, 'ClampMax': 8192, 'Category': '纯色图片'})
    Color: unreal.LinearColor = (unreal.LinearColor(1, 1, 1, 1), {
        'DisplayName': '颜色', 'Category': '纯色图片'})
    SRGB: bool = (True, {'DisplayName': 'sRGB', 'Category': '纯色图片'})
    Directory: str = ('/Game/mc/tex/Colors', {'DisplayName': '保存路径', 'Category': '纯色图片'})
    FileName: str = ('Color', {'DisplayName': '文件名', 'Category': '纯色图片'})


def _channel(value):
    value = float(value)
    if value > 1.0:
        value = value / 255.0
    return max(0.0, min(1.0, value))


def _srgb_byte(value):
    value = _channel(value)
    if value <= 0.0031308:
        encoded = value * 12.92
    else:
        encoded = 1.055 * (value ** (1.0 / 2.4)) - 0.055
    return max(0, min(255, int(round(encoded * 255.0))))


def _size(size):
    width = int(getattr(size, 'x', 0))
    height = int(getattr(size, 'y', 0))
    if width < 1 or height < 1:
        mineprep.warn(i18n('尺寸至少为 1', 'Size must be at least 1'))
        return None
    return width, height


def _byte(value):
    return max(0, min(255, int(round(_channel(value) * 255.0))))


def _image(size, color, srgb=True):
    place = _size(size)
    if place is None:
        return None
    width, height = place
    image = np.empty((height, width, 4), np.uint8)
    image[:, :] = (
        _srgb_byte(color.r) if srgb else _byte(color.r),
        _srgb_byte(color.g) if srgb else _byte(color.g),
        _srgb_byte(color.b) if srgb else _byte(color.b),
        _byte(color.a),
    )
    return image


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


def export_png(size, color, path, srgb=True):
    """把纯色图写成本地 PNG。失败时返回空字符串。"""
    image = _image(size, color, srgb)
    if image is None:
        return ''
    from PIL import Image
    Image.fromarray(image, 'RGBA').save(str(path))
    return str(path)


def save_solid(size, color, directory, name, srgb=True):
    """把纯色图保存为纹理资产。失败时返回 None。"""
    place = _destination(directory, name)
    if place is None:
        return None
    image = _image(size, color, srgb)
    if image is None:
        return None
    directory, name = place
    from PIL import Image
    picture = Image.fromarray(image, 'RGBA')
    handle, filename = tempfile.mkstemp(suffix='.png')
    os.close(handle)
    try:
        picture.save(filename)
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
        mineprep.warn(i18n('无法保存纯色图片: {path}', 'Cannot save solid color: {path}').format(
            path=f'{directory}/{name}'))
        return None
    asset.set_editor_properties({
        'srgb': bool(srgb),
        'filter': unreal.TextureFilter.TF_NEAREST,
        'mip_gen_settings': unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS,
    })
    unreal.EditorAssetLibrary.save_loaded_asset(asset)
    return asset


def draw(mod, layout):
    SolidProps.localize(i18n)
    props = SolidProps()

    def show(_name=''):
        preview.set_brush_color(props.Color)

    def do_save():
        asset = save_solid(props.Size, props.Color, props.Directory, props.FileName, props.SRGB)
        if asset:
            mineprep.prints(asset.get_path_name())

    def do_export():
        path = mineprep.asksaveasfilename(
            title=str(i18n('导出图片', 'Export Image')),
            defaultextension='.png',
            initialfile=props.FileName or 'Color',
            filetypes=[('PNG', '*.png')],
        )
        if not path:
            return
        saved = export_png(props.Size, props.Color, path, props.SRGB)
        if saved:
            mineprep.prints(saved)

    split = layout.splitter(ratio=0.62, fill=1, limits=(0.3, 0.85))
    preview = split.first.border(fill=1, align=(0, 0))
    show()

    side = split.second.col(fill=1, align=(0, 0), padding=4)
    side.button(i18n('生成图片', 'Generate Image'), on_clicked=do_save, padding=3)
    side.prop(props, on_property_changed=show)
    side.button(i18n('导出图片', 'Export Image'), on_clicked=do_export, padding=3)
