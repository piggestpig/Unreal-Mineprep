"""轮播 image/ 中的参考截图。"""
from pathlib import Path

import unreal
import mineprep
from mineprep import i18n

_IMAGE = {'.png', '.jpg', '.jpeg'}
_DIR = Path(__file__).resolve().parent / 'image'


def _key(name):
    key = unreal.Key()
    key.import_text(name)
    return key


_LEFT = _key('Left')
_RIGHT = _key('Right')
_ADD = _key('Add')


def list_images():
    if not _DIR.is_dir():
        return []
    return sorted(
        path for path in _DIR.iterdir()
        if path.is_file() and path.suffix.lower() in _IMAGE
    )


class Showcase(mineprep.Mod):
    _unique_ = True
    _label_ = i18n('内容展示', 'Showcase')

    def _step(self, delta):
        carousel = self._carousel
        if carousel is None:
            return
        carousel.page(carousel.index() + delta)

    def on_key_down(self, key):
        same = unreal.InputLibrary.equal_equal_key_key
        if same(key, _LEFT):
            self._step(-1)
        elif same(key, _RIGHT):
            self._step(1)
        elif not same(key, _ADD):
            super().on_key_down(key)

    def draw(self, context=None):
        self._carousel = None
        frame = self.layout.sizebox(height=700, align=(0, 0))
        root = frame.col(align=(0, 0), fill=1)
        files = list_images()
        if not files:
            root.text(i18n(
                '把截图放进 image/ 后重新打开。',
                'Put screenshots in image/ and reopen.',
            ), padding=8, wrap=True)
            return

        names = [path.name for path in files]
        bar = root.overlay(padding=(4, 4, 4, 2), align=(0, 1), fill=False)
        name = bar.text(names[0], align=(2, 2), padding=(40, 0))
        name.hide(unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE)

        bar.button('◀', size=13, text_padding=(8, 2), align=(1, 2), padding=(4, 0),
                   tooltip=i18n('上一张', 'Previous'), on_clicked=lambda: self._step(-1))
        bar.button('▶', size=13, text_padding=(8, 2), align=(3, 2), padding=(4, 0),
                   tooltip=i18n('下一张', 'Next'), on_clicked=lambda: self._step(1))

        slider = root.custom(unreal.Slider, padding=(8, 2, 8, 4), align=(0, 1))
        slider.target.set_min_value(0.0)
        slider.target.set_max_value(float(len(files) - 1))
        slider.target.set_step_size(1.0)

        self._carousel = root.carousel(fill=1, align=(0, 0))
        carousel = self._carousel
        for path in files:
            page = carousel.col(align=(0, 0), fill=1)
            box = page.scalebox(fill=1, align=(0, 0))
            box.target.set_editor_property('Stretch', unreal.Stretch.SCALE_TO_FIT)
            box.target.set_editor_property('StretchDirection', unreal.StretchDirection.BOTH)
            tex = unreal.RenderingLibrary.import_file_as_texture2d(mineprep.world(), str(path))
            if tex is None:
                continue
            tex.set_editor_property('srgb', True)
            image = box.image(align=(2, 1))
            image.set_brush_from_texture(tex, False)
            image.set_desired_size_override(unreal.Vector2D(
                tex.blueprint_get_size_x(), tex.blueprint_get_size_y()))

        busy = False

        def show(index):
            nonlocal busy
            name.target.set_text(names[index])
            if busy:
                return
            busy = True
            slider.target.set_value(float(index))
            busy = False

        def slide(value):
            nonlocal busy
            if busy:
                return
            busy = True
            carousel.page(int(round(float(value))))
            busy = False

        carousel.on_current_page_index_changed.add_callable(lambda _widget, index: show(int(index)))
        slider.target.on_value_changed.add_callable(slide)
        slider.target.on_mouse_capture_end.add_callable(lambda: slide(slider.target.get_value()))
        show(0)
