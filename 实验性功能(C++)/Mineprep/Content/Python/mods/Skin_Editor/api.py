"""MC 皮肤 UV 规则及 Pillow 转换；不依赖 unreal、面板或 ColorList。"""
from pathlib import Path

# 坐标以 64×64 皮肤左上角为原点；高分辨率按整数倍缩放。
ARM_UV = {
    'right': {'inner': (40, 16), 'outer': (40, 32)},
    'left': {'inner': (32, 48), 'outer': (48, 48)},
}
# 相对每块 16×16 手臂区域的 (x, y, width, height)，按原预设顺序移位。
ARM_SHIFTS = ((15, 0, 1, 16), (11, 0, 1, 4), (7, 0, 8, 16))
LAYER_UV = {
    'inner': ((0, 0, 32, 16), (0, 16, 16, 16), (16, 16, 24, 16),
              (40, 16, 16, 16), (16, 48, 16, 16), (32, 48, 16, 16)),
    'outer': ((32, 0, 32, 16), (0, 32, 16, 16), (16, 32, 24, 16),
              (40, 32, 16, 16), (0, 48, 16, 16), (48, 48, 16, 16)),
}


def arm_boxes(*, arm='both', layer='both'):
    """返回所选手臂/层的移位矩形，坐标单位为基础皮肤像素。"""
    if arm not in ('both', 'left', 'right') or layer not in ('both', 'inner', 'outer'):
        raise ValueError('arm 须为 both/left/right，layer 须为 both/inner/outer')
    return tuple((ox + x, oy + y, w, h)
                 for side, layers in ARM_UV.items() if arm in ('both', side)
                 for name, (ox, oy) in layers.items() if layer in ('both', name)
                 for x, y, w, h in ARM_SHIFTS)


def _image(source):
    from PIL import Image
    if isinstance(source, Image.Image):
        image = source.convert('RGBA').copy()
    else:
        with Image.open(source) as original:
            image = original.convert('RGBA')
    w, h = image.size
    if w != h or w < 64 or w % 64:
        raise ValueError('需要 64×64 或其整数倍的方形皮肤；不支持旧版 64×32 布局')
    return image, w // 64


def _finish(image, output):
    if output is not None:
        path = Path(output)
        if path.suffix.lower() != '.png':
            raise ValueError('output 必须是 PNG 路径')
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, format='PNG')
    return image


def _arms(source, wide, output, arm, layer):
    boxes = arm_boxes(arm=arm, layer=layer)
    image, scale = _image(source)
    for x, y, w, h in reversed(boxes) if wide else boxes:
        x, y, w, h = (v * scale for v in (x, y, w, h))
        if wide:
            # 沿用原预设的补列策略，复制相邻像素；并非细化的逆运算。
            x, w = x - 2 * scale, w + scale
            image.paste(image.crop((x, y, x + w, y + h)), (x + scale, y))
        else:
            patch = image.crop((x, y, x + w, y + h))
            image.paste((0, 0, 0, 0), (x, y, x + w, y + h))
            image.paste(patch, (x - scale, y))
    return _finish(image, output)


def slim_arms(source, output=None, *, arm='both', layer='both'):
    """宽臂布局转细臂；返回新的 RGBA Pillow Image，可同时写入 PNG。"""
    return _arms(source, False, output, arm, layer)


def wide_arms(source, output=None, *, arm='both', layer='both'):
    """细臂布局转宽臂；复制邻列补宽，不恢复细化时丢失的像素。"""
    return _arms(source, True, output, arm, layer)


def keep_layer(source, layer, output=None):
    """保留 inner/outer 的原 UV 位置，其他区域清为透明；不合并或搬移层。"""
    from PIL import Image
    if layer not in LAYER_UV:
        raise ValueError('layer 须为 inner 或 outer')
    image, scale = _image(source)
    out = Image.new('RGBA', image.size)
    for x, y, w, h in LAYER_UV[layer]:
        x, y, w, h = (v * scale for v in (x, y, w, h))
        out.paste(image.crop((x, y, x + w, y + h)), (x, y))
    return _finish(out, output)
