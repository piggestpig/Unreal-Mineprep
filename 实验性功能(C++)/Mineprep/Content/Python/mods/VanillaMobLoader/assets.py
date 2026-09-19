"""Optional image decoding and cancellable, standard-library network workers.

Catalog and renders originate from Ewan Howell's CEM Template Loader / wynem.
No Blender modules or bundled third-party code are required.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote
import io
import json
import os
import threading
import uuid
import zlib

from .catalog import Catalog

ROOTS = ('https://wynem.com/assets',
         'https://raw.githubusercontent.com/ewanhowell5195/wynem/main/src/assets',
         'https://cdn.jsdelivr.net/gh/ewanhowell5195/wynem/src/assets')
CACHE = Path(__file__).parent / '__pycache__'


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_bytes(data)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


class AssetStore:
    def __init__(self, cache=CACHE):
        self.cache = Path(cache)
        self.pool = ThreadPoolExecutor(max_workers=16, thread_name_prefix='VanillaMobLoader')
        self.closed = threading.Event()
        self.lock = threading.Lock()
        self.image_lock = threading.Lock()
        self.preferred = ROOTS[0]
        self.unsaved = False
        self._checked = False
        self._image = None
        self.futures = set()

    def submit(self, fn, *args):
        future = self.pool.submit(fn, *args)
        self.futures.add(future)
        return future

    def close(self):
        with self.lock:
            self.closed.set()
        for future in self.futures:
            future.cancel()
        self.futures.clear()
        self.pool.shutdown(wait=False, cancel_futures=True)

    def cached_catalog(self):
        try:
            return Catalog(json.loads((self.cache / 'resources/catalog.json').read_text(encoding='utf-8')))
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return None

    def _fetch(self, relative):
        errors = []
        for root in [self.preferred] + [r for r in ROOTS if r != self.preferred]:
            if self.closed.is_set():
                raise RuntimeError('Cancelled')
            try:
                request = Request(root + '/' + relative, headers={'User-Agent': 'Mineprep-VanillaMobLoader/0.1'})
                with urlopen(request, timeout=10) as response:
                    raw = response.read(16 * 1024 * 1024 + 1)
                    if 'text/html' in response.headers.get('Content-Type', '') or not raw or len(raw) > 16 * 1024 * 1024:
                        raise ValueError('Invalid resource response')
                self.preferred = root
                return raw
            except Exception as exc:
                errors.append(type(exc).__name__)
        raise RuntimeError(' / '.join(errors))

    def refresh_catalog(self):
        raw = self._fetch('json/cem_template_models.json')
        catalog = Catalog(json.loads(raw.decode('utf-8')))
        saved = True
        with self.lock:
            if self.closed.is_set():
                raise RuntimeError('Cancelled')
            try:
                atomic_write(self.cache / 'resources/catalog.json', raw)
            except OSError:
                self.unsaved = True
                saved = False
        return catalog, saved

    def png_path(self, ident):
        # Quote the entire upstream identifier, never use it as an unchecked path.
        return self.cache / 'resources/thumbnails' / (quote(ident, safe='') + '.png')

    def cached_png(self, ident):
        try:
            raw = self.png_path(ident).read_bytes()
            return raw if raw.startswith(b'\x89PNG\r\n\x1a\n') else None
        except OSError:
            return None

    def decoder(self):
        with self.image_lock:
            if not self._checked:
                self._checked = True
                try:
                    from PIL import Image, features
                    if features.check('webp'):
                        self._image = Image
                except Exception:
                    self._image = None
            return self._image

    def thumbnail(self, ident):
        # Cache hits need neither network access nor the optional WebP decoder.
        if self.closed.is_set():
            return None
        cached = self.cached_png(ident)
        if cached is not None:
            return cached

        image = self.decoder()
        if image is None or self.closed.is_set():
            return None
        raw = self._fetch('images/minecraft/renders/' + quote(ident, safe='') + '.webp')
        with image.open(io.BytesIO(raw)) as source:
            output = io.BytesIO()
            source.convert('RGBA').save(output, format='PNG')
            png = output.getvalue()

        with self.lock:
            if self.closed.is_set():
                return None
            try:
                atomic_write(self.png_path(ident), png)
            except OSError:
                self.unsaved = True
        return png

    def skin_path(self, ident):
        return self.cache / 'resources/skins' / (quote(ident, safe='') + '.png')

    def skin(self, ident):
        """Read/download the selected entity's primary skin, never its render."""
        path = self.skin_path(ident)
        from .skin import alpha_reader
        try:
            raw = path.read_bytes()
            alpha_reader(raw)
            return raw
        except (OSError, ValueError, zlib.error):
            pass

        raw = self._fetch('images/minecraft/entities/' + quote(ident, safe='') + '.png')
        alpha_reader(raw)
        with self.lock:
            if self.closed.is_set():
                raise RuntimeError('Cancelled')
            try:
                atomic_write(path, raw)
            except OSError:
                self.unsaved = True
        return raw


def load_settings(cache=CACHE):
    try:
        value = json.loads((Path(cache) / 'settings.json').read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(category, selected, cache=CACHE, **options):
    try:
        atomic_write(Path(cache) / 'settings.json', json.dumps(
            dict(category=category, selected=selected, **options), ensure_ascii=True).encode('utf-8'))
        return True
    except OSError:
        return False
