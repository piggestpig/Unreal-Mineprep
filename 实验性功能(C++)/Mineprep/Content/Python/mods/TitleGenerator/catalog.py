"""标题字体与贴图资源目录读取及在线刷新缓存（读取过程不依赖 Unreal）。"""
import copy
import io
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import urllib.request
import zipfile

ARCHIVES = ('https://codeload.github.com/ewanhowell5195/MinecraftTitleGenerator/zip/refs/heads/main',
            'https://github.com/ewanhowell5195/MinecraftTitleGenerator/archive/refs/heads/main.zip')
MISSING = '标题素材未缓存，请点击“刷新资源”下载完整素材。'
# 字体图集布局的默认坐标参数
FONT_DEFAULTS = dict(textureWidth=1000, textureHeight=320, height=44, border=266,
                     faces=[[22, 62], [108, 148], [194, 194, 234, 242]],
                     ends=[[0, 22, 62, 84], [86, 108, 148, 170], [172, 194, 242, 264]])
TEN_SHIFTS = {'//': 16, '\\\\': 16, 'tj': 8, 'lt': 8, 'ly': 8, 'yj': 6, 'lv': 4, 'qt': 4,
              'qv': 4, '{{': 4, '}}': 4, '}]': 4, '[{': 4, 'l?': 4, 'q?': 4, 't.': 4,
              't,': 4, 't_': 4, 't-': 4, '-t': 4, 'l-': 8, '/j': 8, 'l\\': 8}


def cache_dir():
    return Path(__file__).resolve().parent / '__pycache__'


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _local(relative, cache):
    target = cache / 'cache' / relative
    if not target.is_file():
        raise FileNotFoundError(f'{MISSING}\n缺少：{relative}')
    return target


def _entries(raw):
    result = {}
    for entry in raw:
        metadata = {**FONT_DEFAULTS, 'shifts': {}, **entry}
        if entry['id'] == 'minecraft-ten':
            metadata = {**metadata, 'terminatorSpace': True, 'shifts': TEN_SHIFTS, 'author': 'Ewan Howell'}
        metadata.setdefault('name', entry['id'].replace('-', ' ').title())
        result[entry['id']] = metadata
        for variant in entry.get('variants', ()):
            item = {**metadata, **variant}
            item['name'] = metadata['name'] + ' — ' + variant.get('name', variant['id'])
            if item.get('shifts') == 'inherit':
                item['shifts'] = metadata.get('shifts', {})
            result[item['id']] = item
    return result


def entries(cache=None):
    cache = Path(cache) if cache is not None else cache_dir()
    path = cache / 'cache/fonts.json'
    if not path.is_file():
        return {}
    return {key: value for key, value in _entries(_read(path)).items()
            if all((cache/'cache/fonts'/key/name).is_file() for name in ('characters.json', 'textures.json', 'textures/flat.png'))}


def font(font_id, cache=None):
    cache = Path(cache) if cache is not None else cache_dir()
    fonts = entries(cache)
    if font_id not in fonts:
        raise ValueError(f'{MISSING}\n字体：{font_id}')
    result = copy.deepcopy(fonts[font_id])
    result.update(_read(_local(f'fonts/{font_id}/textures.json', cache)))
    return result


def resolve(font_id, options, cache=None):
    cache = Path(cache) if cache is not None else cache_dir()
    metadata = font(font_id, cache)
    metadata['characters'] = _read(_local(f'fonts/{font_id}/characters.json', cache))
    if options['source'] == 'file':
        base = Path(options['file'])
        if not base.is_file():
            raise FileNotFoundError(f'请选择有效的本地图集：{base}')
    else:
        texture = options['texture'] if options['source'] == 'premade' else 'flat'
        if texture not in choices(metadata, 'textures'):
            raise ValueError(f'字体 {font_id} 没有贴图 {texture}')
        base = _local(f'fonts/{font_id}/textures/{texture}.png', cache)
    overlay = None
    if options['overlay'] != 'none':
        if options['overlay'] not in choices(metadata, 'overlays'):
            raise ValueError(f'字体 {font_id} 没有叠加层 {options["overlay"]}')
        overlay = _local(f'fonts/{font_id}/overlays/{options["overlay"]}.png', cache)
    return metadata, base, overlay


def choices(metadata, key):
    """展开贴图或叠加层及其子变体，生成 {id: 显示名} 字典。"""
    result = {}
    for item_id, entry in metadata.get(key, {}).items():
        name = entry.get('name', item_id.replace('_', ' ').title())
        result[item_id] = name
        for variant_id, variant in entry.get('variants', {}).items():
            result[variant_id] = name + ' — ' + variant.get('name', variant_id)
    return result


def thumbnail(font_id, texture_id='flat', cache=None):
    cache = Path(cache) if cache is not None else cache_dir()
    metadata = font(font_id, cache)
    if texture_id != 'none' and texture_id not in {**choices(metadata, 'textures'), **choices(metadata, 'overlays')}:
        raise ValueError(f'字体 {font_id} 没有示例 {texture_id}')
    return _local(f'fonts/{font_id}/thumbnails/{texture_id}.png', cache)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
        file.write(content)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def refresh_all(cache=None, *, progress=None, cancel=None):
    """后台线程：下载上游资源包并解压缓存字体 JSON、贴图 PNG 与许可证文件。"""
    cache = Path(cache) if cache is not None else cache_dir()
    progress = progress if progress is not None else {}

    def check_cancel():
        if cancel is not None and cancel.is_set():
            raise RuntimeError('资源刷新已取消。')

    errors = []
    for url in ARCHIVES:
        check_cancel()
        try:
            archive = io.BytesIO()
            progress.update(stage='download', downloaded=0)
            request = urllib.request.Request(url, headers={'User-Agent': 'Mineprep-TitleGenerator/1.0'})
            with urllib.request.urlopen(request, timeout=20) as response:
                while chunk := response.read(256*1024):
                    check_cancel()
                    archive.write(chunk)
                    progress['downloaded'] = archive.tell()
            archive.seek(0)
            package = zipfile.ZipFile(archive)
            break
        except (OSError, zipfile.BadZipFile) as exc:
            errors.append(f'{url}: {exc}')
    else:
        raise OSError('下载资源包失败；已有缓存保留。\n'+'\n'.join(errors))
    with package:
        files = {}
        for item in package.infolist():
            # 仅提取受信任的字体 JSON、PNG 与说明文件
            relative = item.filename.partition('/')[2]
            parts = PurePosixPath(relative).parts
            if item.is_dir() or '..' in parts or relative.startswith('/'):
                continue
            if relative in ('fonts.json', 'LICENSE.md', 'README.md') or (
                len(parts) == 3 and parts[0] == 'fonts' and parts[2] in ('characters.json', 'textures.json')
            ) or (len(parts) == 4 and parts[0] == 'fonts' and parts[2] in ('textures', 'overlays', 'thumbnails') and relative.endswith('.png')):
                files[relative] = item
        raw = package.read(files['fonts.json'])
        fonts = _entries(json.loads(raw))
        required = set()
        for key in fonts:
            prefix = f'fonts/{key}/'
            required.update(prefix+name for name in ('characters.json', 'textures.json'))
            metadata = json.loads(package.read(files[prefix+'textures.json']))
            for kind in ('textures', 'overlays'):
                for name in choices(metadata, kind):
                    required.add(prefix+f'{kind}/{name}.png')
                    if kind == 'textures':
                        required.add(prefix+f'thumbnails/{name}.png')
        missing = sorted(required-files.keys())
        if missing:
            raise ValueError('上游资源包缺少文件：\n'+'\n'.join(missing[:10]))
        progress.update(stage='cache', done=0, total=len(files))
        for number, (relative, item) in enumerate(files.items(), 1):
            check_cancel()
            if relative != 'fonts.json':
                content = package.read(item)
                if relative.endswith('.json'):
                    json.loads(content)
                _write(cache/'cache'/relative, content)
            progress['done'] = number
        check_cancel()
        _write(cache/'cache/fonts.json', raw)  # 全部资源写入完成后再更新 fonts.json 索引
    return dict(font_count=len(fonts), file_count=len(files), download_bytes=archive.getbuffer().nbytes)
