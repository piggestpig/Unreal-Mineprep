"""在 sRGB 空间合成标题 RGBA 图集（渐变、染色、叠加层与描边色，不依赖 Unreal）。"""
from pathlib import Path

import cv2
import numpy as np


def color(value):
    value = value.removeprefix('#')
    if len(value) != 6:
        raise ValueError('颜色使用 #RRGGBB 格式。')
    return np.array([int(value[i:i+2], 16)/255 for i in (0, 2, 4)], np.float32)


def read(path):
    image = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None or image.dtype != np.uint8:
        raise ValueError(f'无法读取 8-bit 图片：{path}')
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
    elif image.shape[2] == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
    return cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)


def compose(image, font, options, overlay=None):
    h, w = image.shape[:2]
    if w*font['textureHeight'] != h*font['textureWidth']:
        raise ValueError('图集宽高比必须与所选字库相同；请使用该字库的图集模板。')
    rgba = image.astype(np.float32)/255
    rgb = rgba[..., :3]
    scale = h/font['textureHeight']
    if options['source'] == 'gradient':
        top, bottom = color(options['gradient_top']), color(options['gradient_bottom'])
        for i, face in enumerate(font['faces']):
            ends = font['ends'][i]
            y = np.arange(h, dtype=np.float32)
            a, b = (face if len(face) == 2 else face[1:3])
            t = np.clip((y/scale-a)/max(b-a, 1), 0, 1)
            rows = (y >= ends[0]*scale) & (y < ends[3]*scale)
            rgb[rows] = (top[None, :]*(1-t[rows, None])+bottom[None, :]*t[rows, None])[:, None, :]
        for a, b, c, d in font['ends']:
            for low, high in ((a, b), (c, d)):
                rgb[round(low*scale):round(high*scale)] *= options['edge_brightness']/100
    rgb *= color(options['tint'])
    if overlay is not None:
        over = cv2.resize(overlay, (w, h), interpolation=cv2.INTER_NEAREST).astype(np.float32)/255
        over[..., :3] *= color(options['overlay_tint'])
        other = over[..., :3]
        mode = options['overlay_blend']
        if mode == 'normal':
            blend = other
        elif mode == 'multiply':
            blend = rgb*other
        elif mode == 'screen':
            blend = 1-(1-rgb)*(1-other)
        elif mode == 'overlay':
            blend = np.where(rgb <= .5, 2*rgb*other, 1-2*(1-rgb)*(1-other))
        else:
            raise ValueError(f'未知叠加模式：{mode}')
        alpha = over[..., 3:4]*options['overlay_opacity']
        rgb[:] = rgb*(1-alpha)+blend*alpha
    if options['border_color']:
        rgb[round(font['border']*scale):] = color(options['border_color'])
    # 叠加层只改变已有像素的 RGB 颜色，不填充原本透明的镂空区域
    return np.rint(np.clip(rgba, 0, 1)*255).astype(np.uint8)


def write(path, rgba):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, data = cv2.imencode('.png', cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))
    if not ok:
        raise OSError(f'无法编码图集：{path}')
    data.tofile(path)
    return path
