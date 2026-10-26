"""基于 Ewan Howell 的 Minecraft Title Generator 排版规则构建 UE 四边形网格。

参考来源：minecraft_title_generator.js (addText / makeWord / makeCharacter)。
UE 局部坐标系：正面朝 +X，上方为 +Z，单位为厘米；文字从左到右沿 -Y 排列。
"""
import copy
import math
import re

FACES = {
    'north': (0, 1, 2, 3), 'south': (5, 4, 7, 6), 'up': (1, 0, 4, 5),
    'down': (3, 2, 6, 7), 'west': (4, 0, 3, 7), 'east': (1, 5, 6, 2),
}
UVS = {'down': (2, 3, 1, 0)}
# UV 角点顺序：左上、右上、左下、右下。保留 from/to 的正负号以支持反向描边外壳。


def text_lines(text):
    """去除首尾空行，保留原始行号与中间空行的行距位置。"""
    lines = list(enumerate(str(text).replace('\r\n', '\n').replace('\r', '\n').split('\n'), 1))
    while lines and not lines[0][1].strip():
        lines.pop(0)
    while lines and not lines[-1][1].strip():
        lines.pop()
    if not lines:
        raise ValueError('请输入标题文字。')
    for number, value in lines:
        if len(value) > 256:
            raise ValueError(f'输入第 {number} 行：每行最多 256 个字符。')
    return lines


def layout_lines(text, font, options):
    """先校验全部输入行，再逐行生成字形几何数据。"""
    lines = text_lines(text)
    for number, value in lines:
        if value.strip():
            try:
                prepare_text(value, font, options.get('terminators', False))
            except ValueError as exc:
                raise ValueError(f'输入第 {number} 行：{exc}') from exc
    result = []
    for index, (number, value) in enumerate(lines):
        if not value.strip():
            continue
        offset = len(lines)-1-index if options['layout'] == 'top' else index
        row = options['row']+offset
        result.extend(dict(glyph, line=number, row=row) for glyph in layout(value, font, dict(options, row=row)))
    return result, len(lines)


def prepare_text(text, font, terminators=False):
    text = str(text).replace('A', '😳')
    text = re.sub(r"(\s|^)'", r'\1😩', text)
    text = re.sub(r'(\s|^)"', r'\1😩😩', text).replace('"', "''").lower().strip()
    if not text:
        raise ValueError('请输入标题文字。')
    missing = sorted(set(text) - set(font['characters']) - {' '})
    if missing:
        raise ValueError('当前字库不支持：' + ' '.join(missing))
    if terminators or font.get('forcedTerminators'):
        gap = ' ' if font.get('terminatorSpace') else ''
        text = '┫' + gap + text + gap + '┣'
    return text


def _rotate(point, rotation):
    if not rotation or not rotation.get('angle'):
        return point
    origin = rotation.get('origin', (0, 0, 0))
    x, y, z = (point[i] - origin[i] for i in range(3))
    c, s = math.cos(math.radians(rotation['angle'])), math.sin(math.radians(rotation['angle']))
    axis = rotation['axis']
    if axis == 'x':
        y, z = y*c-z*s, y*s+z*c
    elif axis == 'y':
        x, z = x*c+z*s, -x*s+z*c
    else:
        x, y = x*c-y*s, x*s+y*c
    return tuple(v + origin[i] for i, v in enumerate((x, y, z)))


def _cube(cube):
    f, t = cube['from'], cube['to']
    points = ((f[0], t[1], f[2]), (t[0], t[1], f[2]), (t[0], f[1], f[2]), (f[0], f[1], f[2]),
              (f[0], t[1], t[2]), (t[0], t[1], t[2]), (t[0], f[1], t[2]), (f[0], f[1], t[2]))
    points = [_rotate(p, cube.get('rotation')) for p in points]
    inverted = math.prod(t[i]-f[i] for i in range(3)) < 0
    for face, value in cube['faces'].items():
        if value is None:
            continue
        uv = value.get('uv') if isinstance(value, dict) else value
        corners = ((uv[0]/16, uv[1]/16), (uv[2]/16, uv[1]/16),
                   (uv[0]/16, uv[3]/16), (uv[2]/16, uv[3]/16))
        order = UVS.get(face, (1, 0, 2, 3))
        yield [points[i] for i in FACES[face]], [corners[i] for i in order], int(inverted)


def layout(text, font, options):
    text = prepare_text(text, font, options.get('terminators', False))
    spacing = options['character_spacing']
    spacer = '\u200b' in font['characters'] and spacing != 0
    if spacer:
        text = '\u200b'.join(text)
    kind, row, gap, height = options['layout'], options['row'], options['row_spacing'], font['height']
    factor = {'top': 1., 'bottom': .75, 'small': .35}[kind]
    offset, last, glyphs = 0., None, []
    for word in ([text] if ' ' in font['characters'] else text.split(' ')):
        word_glyphs = []
        for char in word:
            if last and not options.get('disable_shifting', False):
                offset -= font.get('shifts', {}).get(last+char, 0)
            cubes = copy.deepcopy(font['characters'][char])
            for cube in cubes:
                f, t = cube['from'], cube['to']
                if char == '\u200b':
                    (t if t[0] > f[0] else f)[0] += spacing-1
                if kind == 'small':
                    (t if t[2] > f[2] else f)[2] -= 6
            xs = [c[k][0] for c in cubes for k in ('from', 'to')]
            zs = [c[k][2] for c in cubes for k in ('from', 'to')]
            x_max, z_min, depth = max(xs), min(zs), max(zs)-min(zs)
            quads = []
            for cube in cubes:
                if kind == 'bottom' and not font.get('flat'):
                    f, t = cube['from'], cube['to']
                    (t if t[2] > f[2] else f)[2] += 32  # 乘以 0.75 缩放后为 24
                for points, uv, slot in _cube(cube):
                    placed = []
                    for x, y, z in points:
                        x, z = x-offset-x_max, z-z_min
                        if kind == 'bottom':
                            x, y, z = x*.75, (y*2-row*(height*2+4)-gap*row-height*2-18)*.75, z*.75-8
                        elif kind == 'small':
                            x, y, z = x*.35, y*.35-row*(height*.35)-gap*row-height*.35, (z-depth)*.35
                        else:
                            y, z = y+row*(height+4)+gap*row, z-depth/2
                        placed.append((x, y, z*options['thickness']))
                    quads.append((placed, uv, slot))
            word_glyphs.append({'char': char, 'quads': quads})
            offset += max(xs)-min(xs) + (0 if spacer else spacing)
            last = char
        if font.get('autoBorder') and word_glyphs:
            points = [p for g in word_glyphs for q, _, _ in g['quads'] for p in q]
            low = [min(p[i] for p in points)-2*factor for i in range(3)]
            high = [max(p[i] for p in points)+2*factor for i in range(3)]
            # 外框 UV 从像素坐标换算到 0~16 的模型 UV 空间
            border = font['border'] * 16 / font['textureHeight']
            uv = [0, border, 16/font['textureWidth'], border+16/font['textureHeight']]
            word_glyphs.append({'char': '', 'quads': list(_cube({'from': high, 'to': low,
                                      'faces': {f: uv for f in FACES}}))})
            offset += 4
        glyphs.extend(word_glyphs)
        offset += font.get('spaceWidth', 8)+(0 if spacer else spacing)
    all_points = [p for g in glyphs for q, _, _ in g['quads'] for p in q]
    center = (min(p[0] for p in all_points)+max(p[0] for p in all_points))/2
    unit = options['height_cm']/height
    result = []
    for glyph in glyphs:
        quads = []
        for points, uv, slot in glyph['quads']:
            transformed = []
            for x, y, z in points:
                if kind == 'bottom':
                    y, z = z, -y  # 对应原版绕 MC X 轴旋转 -90 度
                transformed.append((-z*unit, (x-center)*unit, y*unit))
            # 交换 MC Y/Z 轴后顶点绕序已自然变为 UE 顺时针正面
            quads.append((transformed, uv, slot))
        points = [p for q, _, _ in quads for p in q]
        pivot = tuple((min(p[i] for p in points)+max(p[i] for p in points))/2 if i < 2
                      else min(p[i] for p in points) for i in range(3))
        local = [([tuple(p[i]-pivot[i] for i in range(3)) for p in q], uv, slot) for q, uv, slot in quads]
        result.append({'char': glyph['char'], 'pivot': pivot, 'quads': local})
    return result
