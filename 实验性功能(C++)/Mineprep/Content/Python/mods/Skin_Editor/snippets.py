"""Preset main(tex, overlay) scripts. Buttons copy these into the Code field."""
import inspect
from mineprep import ColorList


def source(name):
    fn = globals()[name]
    text = inspect.getsource(fn)
    return text.replace(f'def {name}(', 'def main(', 1)


def slim_arms(tex, overlay):
    s = len(tex) // 64
    if not s or len(tex) != len(tex[0]):
        return tex
    boxes = (
        (55, 16, 1, 32),
        (51, 16, 1, 4),
        (51, 32, 1, 4),
        (47, 16, 8, 32),
        (63, 48, 1, 16),
        (59, 48, 1, 4),
        (55, 48, 8, 16),
        (47, 48, 1, 16),
        (43, 48, 1, 4),
        (39, 48, 8, 16),
    )
    clear = (0, 0, 0, 0)
    for x, y, w, h in boxes:
        x, y, w, h = x * s, y * s, w * s, h * s
        patch = [row[x:x + w] for row in tex[y:y + h]]
        tex[y:y + h, x:x + w] = clear
        for i, row in enumerate(tex[y:y + h]):
            row[x - s:x - s + w] = patch[i]
    return tex


def wide_arms(tex, overlay):
    s = len(tex) // 64
    if not s or len(tex) != len(tex[0]):
        return tex
    boxes = (
        (55, 16, 1, 32),
        (51, 16, 1, 4),
        (51, 32, 1, 4),
        (47, 16, 8, 32),
        (63, 48, 1, 16),
        (59, 48, 1, 4),
        (55, 48, 8, 16),
        (47, 48, 1, 16),
        (43, 48, 1, 4),
        (39, 48, 8, 16),
    )
    for x, y, w, h in reversed(boxes):
        x, y, w, h = x * s, y * s, w * s, h * s
        x0, w0 = x - 2 * s, w + s
        patch = [row[x0:x0 + w0] for row in tex[y:y + h]]
        for i, row in enumerate(tex[y:y + h]):
            row[x0 + s:x0 + s + w0] = patch[i]
    return tex


def keep_inner(tex, overlay):
    out = tex.multiply_float(0)
    out[:0.25, :0.5] = tex[:0.25, :0.5]
    out[0.25:0.5, :0.25] = tex[0.25:0.5, :0.25]
    out[0.25:0.5, 0.25:0.625] = tex[0.25:0.5, 0.25:0.625]
    out[0.25:0.5, 0.625:0.875] = tex[0.25:0.5, 0.625:0.875]
    out[0.75:, 0.25:0.5] = tex[0.75:, 0.25:0.5]
    out[0.75:, 0.5:0.75] = tex[0.75:, 0.5:0.75]
    return out


def keep_outer(tex, overlay):
    out = tex.multiply_float(0)
    out[:0.25, 0.5:] = tex[:0.25, 0.5:]
    out[0.5:0.75, :0.25] = tex[0.5:0.75, :0.25]
    out[0.5:0.75, 0.25:0.625] = tex[0.5:0.75, 0.25:0.625]
    out[0.5:0.75, 0.625:0.875] = tex[0.5:0.75, 0.625:0.875]
    out[0.75:, :0.25] = tex[0.75:, :0.25]
    out[0.75:, 0.75:] = tex[0.75:, 0.75:]
    return out


def apply_overlay(tex, overlay):
    if overlay is None:
        return tex
    h = float(len(tex))
    for y, row in enumerate(tex):
        v = (y + 0.5) / h
        w = float(len(row))
        for x, d in enumerate(row):
            s = overlay[v, (x + 0.5) / w]
            a = s.a
            row[x] = (
                s.r * a + d.r * (1 - a),
                s.g * a + d.g * (1 - a),
                s.b * a + d.b * (1 - a),
                a + d.a * (1 - a),
            )
    return tex
