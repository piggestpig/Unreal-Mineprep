"""横向拼接纹理并保存为 Sprite 资产。"""
import os
import tempfile

import unreal
import mineprep
from mineprep import i18n

ID = 'sprite'
ORDER = 0
LABEL = 'Sprite'

_IMAGE_TYPES = [('Image', '*.png *.jpg *.jpeg *.tga *.bmp *.exr')]
_BLANK = unreal.LinearColor(0, 0, 0, 0)


class SpriteProps(mineprep.PropertyGroup):
    Textures: list[unreal.Texture2D] = ([], {'DisplayName': '纹理', 'Category': 'Sprite'})
    Reverse: bool = (False, {'DisplayName': '倒序', 'Category': 'Sprite'})
    Vertical: bool = (False, {'DisplayName': '竖向排列', 'Category': 'Sprite'})
    Directory: str = ('/Game/mc/tex/Sprites', {'DisplayName': '保存路径', 'Category': 'Sprite'})
    FileName: str = ('Sprite', {'DisplayName': '文件名', 'Category': 'Sprite'})


def import_files(paths):
    """把图片文件导入为临时纹理。"""
    world = mineprep.world()
    textures = []
    for path in paths:
        tex = unreal.RenderingLibrary.import_file_as_texture2d(world, str(path))
        if tex is None:
            mineprep.warn(i18n('导入失败: {path}', 'Import failed: {path}').format(path=str(path)))
            continue
        tex.set_editor_properties({
            'srgb': True,
            'filter': unreal.TextureFilter.TF_NEAREST,
        })
        textures.append(tex)
    return textures


def _rows(textures, reverse=False, vertical=False):
    sources = [tex for tex in textures or () if isinstance(tex, unreal.Texture2D)]
    if reverse:
        sources.reverse()
    grids = []
    for tex in sources:
        grid = mineprep.tex_to_color(tex)
        if not grid or not grid[0]:
            continue
        grids.append(grid)
    if not grids:
        return None
    if vertical:
        width = max(len(grid[0]) for grid in grids)
        rows = []
        for grid in grids:
            pad = [_BLANK] * (width - len(grid[0]))
            rows.extend([*line, *pad] for line in grid)
        return mineprep.ColorList.from_rows(rows)
    height = max(len(grid) for grid in grids)
    rows = []
    for y in range(height):
        row = []
        for grid in grids:
            width = len(grid[0])
            row.extend(grid[y] if y < len(grid) else [_BLANK] * width)
        rows.append(row)
    return mineprep.ColorList.from_rows(rows)


def compose(textures, reverse=False, vertical=False):
    """拼接纹理。vertical 为真时竖向排列，reverse 为真时从数组末尾往前排。没有可用纹理时返回 None。"""
    rows = _rows(textures, reverse, vertical)
    if not rows:
        return None
    return mineprep.color_to_tex(rows)


def _png(rows):
    from PIL import Image
    image = Image.new('RGBA', (len(rows[0]), len(rows)))
    image.putdata([
        (_byte(pixel, 'r'), _byte(pixel, 'g'), _byte(pixel, 'b'), _byte(pixel, 'a'))
        for row in rows for pixel in row
    ])
    return image


def export_png(textures, path, reverse=False, vertical=False):
    """把拼接结果写成本地 PNG。取消或失败时返回空字符串。"""
    rows = _rows(textures, reverse, vertical)
    if not rows:
        mineprep.warn(i18n('没有可保存的纹理', 'No textures to save'))
        return ''
    image = _png(rows)
    image.save(str(path))
    return str(path)


def _byte(pixel, channel):
    value = float(getattr(pixel, channel))
    if value > 1.0:
        value = value / 255.0
    return max(0, min(255, int(round(value * 255.0))))


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


def save_sprite(textures, directory, name, reverse=False, vertical=False):
    """把拼接结果保存为纹理资产。失败时返回 None。"""
    place = _destination(directory, name)
    if place is None:
        return None
    rows = _rows(textures, reverse, vertical)
    if not rows:
        mineprep.warn(i18n('没有可保存的纹理', 'No textures to save'))
        return None
    directory, name = place
    image = _png(rows)
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
        mineprep.warn(i18n('无法保存 Sprite: {path}', 'Cannot save Sprite: {path}').format(
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
    SpriteProps.localize(i18n)
    props = SpriteProps()
    shown = {}

    view = {'zoom': 1.0, 'pan': [0.0, 0.0], 'drag': None}

    def apply_view():
        image.set_render_transform_pivot(unreal.Vector2D(0.5, 0.5))
        image.set_render_scale(unreal.Vector2D(view['zoom'], view['zoom']))
        image.set_render_translation(unreal.Vector2D(*view['pan']))

    def show(tex):
        shown['tex'] = tex
        view['zoom'] = 1.0
        view['pan'] = [0.0, 0.0]
        view['drag'] = None
        if tex is None:
            image.hide(True)
            return
        image.set_brush_from_texture(tex, False)
        image.set_desired_size_override(unreal.Vector2D(
            tex.blueprint_get_size_x(), tex.blueprint_get_size_y()))
        image.hide(unreal.SlateVisibility.HIT_TEST_INVISIBLE)
        apply_view()

    def refresh(_name=''):
        show(compose(props.Textures, props.Reverse, props.Vertical))

    def do_import():
        paths = mineprep.askopenfilenames(
            title=str(i18n('导入图片', 'Import Images')),
            filetypes=_IMAGE_TYPES,
        )
        if not paths:
            return
        added = import_files(paths)
        if not added:
            return
        props.Textures = [*props.Textures, *added]
        refresh()

    def do_save():
        asset = save_sprite(
            props.Textures, props.Directory, props.FileName, props.Reverse, props.Vertical)
        if asset:
            mineprep.prints(asset.get_path_name())

    def do_export():
        path = mineprep.asksaveasfilename(
            title=str(i18n('导出图片', 'Export Image')),
            defaultextension='.png',
            initialfile=props.FileName or 'Sprite',
            filetypes=[('PNG', '*.png')],
        )
        if not path:
            return
        saved = export_png(props.Textures, path, props.Reverse, props.Vertical)
        if saved:
            mineprep.prints(saved)

    def over_preview():
        size = border.get_local_size()
        point = border.get_mouse_local()
        return size.x > 1 and size.y > 1 and 0 <= point.x < size.x and 0 <= point.y < size.y

    def wheel(delta):
        if not delta or shown.get('tex') is None or not over_preview():
            mod.layout.set_consume_mouse_wheel(unreal.ConsumeMouseWheel.WHEN_SCROLLING_POSSIBLE)
            return
        mod.layout.set_consume_mouse_wheel(unreal.ConsumeMouseWheel.NEVER)
        old = view['zoom']
        zoom = min(8.0, max(0.25, old * (1.25 ** delta)))
        if zoom == old:
            return
        point = border.get_mouse_local()
        size = border.get_local_size()
        anchor = (point.x - size.x / 2, point.y - size.y / 2)
        view['pan'] = [q - zoom / old * (q - p) for q, p in zip(anchor, view['pan'])]
        view['zoom'] = zoom
        apply_view()

    def down(border):
        if shown.get('tex') is None or mineprep.middle_mouse_down() is not True:
            return False
        point = border.get_mouse_local()
        view['drag'] = (point.x, point.y)
        return unreal.WidgetLibrary.capture_mouse(unreal.WidgetLibrary.handled(), border.target)

    def move(border):
        if view['drag'] is None:
            return False
        if not border.target.has_mouse_capture() or mineprep.middle_mouse_down() is not True:
            view['drag'] = None
            return False
        point = border.get_mouse_local()
        view['pan'][0] += point.x - view['drag'][0]
        view['pan'][1] += point.y - view['drag'][1]
        view['drag'] = (point.x, point.y)
        apply_view()
        return True

    def up(border):
        if view['drag'] is None and not border.target.has_mouse_capture():
            return False
        view['drag'] = None
        return unreal.WidgetLibrary.release_mouse_capture(unreal.WidgetLibrary.handled())

    split = layout.splitter(ratio=0.62, fill=1, limits=(0.3, 0.85))
    box = split.first.scalebox(fill=1, align=(0, 0))
    box.target.set_editor_property('Stretch', unreal.Stretch.SCALE_TO_FIT)
    box.target.set_editor_property('StretchDirection', unreal.StretchDirection.BOTH)
    border = box.border(
        fill=1, align=(0, 0), clip=True,
        on_mouse_button_down=down, on_mouse_move=move, on_mouse_button_up=up)
    image = border.overlay().image(size=unreal.Vector2D(1, 1), padding=0, align=(2, 2))
    image.set_render_transform_pivot(unreal.Vector2D(0.5, 0.5))
    image.hide(True)
    mod._wheels[ID] = wheel

    side = split.second.col(fill=1, align=(0, 0), padding=4)
    side.button(i18n('导入图片', 'Import Images'), on_clicked=do_import, padding=3)
    side.button(i18n('生成 Sprite', 'Generate Sprite'), on_clicked=do_save, padding=3)
    side.prop(props, on_property_changed=refresh)
    side.button(i18n('导出图片', 'Export Image'), on_clicked=do_export, padding=3)
