"""用数据表记录烟花粒子形状。

表格沿用 ``/Game/table/示例结构表`` 的行结构。一个表最多四种烟花。
第一行 ``不同种类起始行数`` 的 Coord 四个分量是每种烟花的起始行号，用不到的分量写 0。
后面每一行是一个粒子，Coord 的 xyz 是坐标，Z 轴向上。
"""
import json

import cv2
import numpy as np
import unreal
import mineprep
from mineprep import i18n

ID = 'firework'
ORDER = 3
LABEL = i18n('烟花', 'Firework')

SOURCE = '/Game/table/示例结构表'
META_NAME = '不同种类起始行数'
DEFAULT_PATH = '/Game/Mineprep/MC_Blueprint/Niagara/烟花/🎆烟花结构表'
_KIND = 'ABCD'
_ZERO = {'X': 0, 'Y': 0, 'Z': 0, 'W': 0}

_SPHERE = """\
# 球形
count = 386
radius = 1.0
seed = 0
golden = np.pi * (3 - np.sqrt(5))
i = np.arange(count)
z = 1 - (2 * i + 1) / count
ring = np.sqrt(np.maximum(0, 1 - z * z))
theta = golden * i + seed
x = np.cos(theta) * ring * radius
y = np.sin(theta) * ring * radius
z *= radius
points = [(float(a), float(b), float(c)) for a, b, c in zip(x, y, z)]
rng = np.random.default_rng(seed)
rng.shuffle(points)
"""

_STAR = """\
# 星形
speed = 0.5
spread = 0.34
angle = 0.0
shape = np.array([
    [0.0, 1.0],
    [0.3455, 0.309],
    [0.9511, 0.309],
    [0.3795918367346939, -0.12653061224489795],
    [0.6122448979591837, -0.8040816326530612],
    [0.0, -0.35918367346938773],
])
samples = [(1 - t) * shape[c - 1] + t * shape[c]
           for c in range(1, len(shape)) for t in (0.25, 0.5, 0.75, 1.0)]
samples = np.asarray(samples)
pi = np.float32(np.pi)
angles = np.array([angle + float(np.float32(i) * pi) * spread for i in range(3)])
px = samples[:, 0] * speed
pz = samples[:, 1] * speed
x = px[None, :] * np.cos(angles)[:, None]
y = px[None, :] * np.sin(angles)[:, None]
z = np.broadcast_to(pz, x.shape)
flip = np.array([-1.0, 1.0])
cloud = np.stack((
    x[:, :, None] * flip,
    y[:, :, None] * flip,
    np.broadcast_to(z[:, :, None], x.shape + (2,)),
), axis=-1).reshape(-1, 3)
seed = np.array([[shape[0, 0] * speed, 0.0, shape[0, 1] * speed]])
points = [(float(a), float(b), float(c)) for a, b, c in np.vstack((seed, cloud))]
"""

_CREEPER = """\
# 苦力怕
speed = 0.5
spread = 0.034
angle = 0.0
shape = np.array([
    [0.0, 0.2], [0.2, 0.2], [0.2, 0.6], [0.6, 0.6], [0.6, 0.2], [0.2, 0.2],
    [0.2, 0.0], [0.4, 0.0], [0.4, -0.6], [0.2, -0.6], [0.2, -0.4], [0.0, -0.4],
])
samples = [(1 - t) * shape[c - 1] + t * shape[c]
           for c in range(1, len(shape)) for t in (0.25, 0.5, 0.75, 1.0)]
samples = np.asarray(samples)
pi = np.float32(np.pi)
angles = np.array([angle + float(np.float32(i) * pi) * spread for i in range(3)])
px = samples[:, 0] * speed
pz = samples[:, 1] * speed
x = px[None, :] * np.cos(angles)[:, None]
y = px[None, :] * np.sin(angles)[:, None]
z = np.broadcast_to(pz, x.shape)
flip = np.array([-1.0, 1.0])
cloud = np.stack((
    x[:, :, None] * flip,
    y[:, :, None] * flip,
    np.broadcast_to(z[:, :, None], x.shape + (2,)),
), axis=-1).reshape(-1, 3)
seed = np.array([[shape[0, 0] * speed, 0.0, shape[0, 1] * speed]])
points = [(float(a), float(b), float(c)) for a, b, c in np.vstack((seed, cloud))]
"""

_BURST = """\
# 喷发
seed = 0
count = 70
rocket = np.array([0.0, 0.0, 0.0])
rng = np.random.default_rng(seed)
off_x = float(rng.normal() * 0.05)
off_y = float(rng.normal() * 0.05)
x = rocket[0] * 0.5 + rng.normal(size=count) * 0.15 + off_x
y = rocket[1] * 0.5 + rng.normal(size=count) * 0.15 + off_y
z = rocket[2] * 0.5 + rng.random(count) * 0.5
points = [(float(a), float(b), float(c)) for a, b, c in zip(x, y, z)]
"""

_COLORS = ((80, 170, 255), (90, 210, 120), (255, 170, 70), (200, 120, 255))


class FireworkProps(mineprep.PropertyGroup):
    _autosave_ = True
    Path: str = (DEFAULT_PATH, {'DisplayName': '表格路径', 'Category': '烟花'})
    A: str = (_SPHERE, {'DisplayName': 'A', 'Category': '烟花', 'MultiLine': True})
    B: str = (_STAR, {'DisplayName': 'B', 'Category': '烟花', 'MultiLine': True})
    C: str = (_CREEPER, {'DisplayName': 'C', 'Category': '烟花', 'MultiLine': True})
    D: str = (_BURST, {'DisplayName': 'D', 'Category': '烟花', 'MultiLine': True})


def render_preview(groups, size=512):
    """四宫格示意图。X 向右，Z 向上，点的亮度表示 Y。"""
    slots = [list(group) for group in list(groups)[:4]]
    while len(slots) < 4:
        slots.append([])
    if not any(slots):
        return None
    cell = size // 2
    image = np.full((size, size, 3), 22, np.uint8)
    for index, group in enumerate(slots):
        col, row = index % 2, index // 2
        tile = _kind_tile(group, _COLORS[index], _KIND[index], cell)
        y0, x0 = row * cell, col * cell
        image[y0:y0 + cell, x0:x0 + cell] = tile
    image[:, cell - 1:cell + 1] = (48, 48, 48)
    image[cell - 1:cell + 1, :] = (48, 48, 48)
    return image


def _kind_tile(group, color, label, cell):
    tile = np.full((cell, cell, 3), 28, np.uint8)
    array = np.asarray(list(group), np.float64).reshape(-1, 3)
    if len(array):
        flat = array[:, [0, 2]]
        center = (flat.min(axis=0) + flat.max(axis=0)) / 2
        span = float(max(np.max(flat.max(axis=0) - flat.min(axis=0)), 1e-6))
        scale = (cell * 0.72) / span
        depth = array[:, 1]
        spread = float(depth.max()) - float(depth.min())
        if spread < 1e-6:
            nearness = np.ones(len(depth))
        else:
            nearness = (depth - float(depth.min())) / spread
        base = np.asarray(color, np.float64)
        for i in np.argsort(nearness):
            shade = 0.22 + 0.78 * float(nearness[i])
            paint = tuple(int(v) for v in np.clip(base * shade, 0, 255))
            x = int(round((flat[i, 0] - center[0]) * scale + cell / 2))
            y = int(round(cell / 2 - (flat[i, 1] - center[1]) * scale))
            cv2.circle(tile, (x, y), 3, paint, -1, cv2.LINE_AA)
    tone = (200, 200, 200) if len(array) else (78, 78, 78)
    origin = (14, 32)
    cv2.putText(tile, label, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (16, 16, 16), 3, cv2.LINE_AA)
    cv2.putText(tile, label, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.7, tone, 1, cv2.LINE_AA)
    return tile


def _preview_texture(picture):
    ok, encoded = cv2.imencode('.png', picture)
    if not ok:
        return None
    tex = unreal.RenderingLibrary.import_buffer_as_texture2d(mineprep.world(), encoded.tobytes())
    if tex is None:
        return None
    tex.set_editor_properties({
        'srgb': True,
        'filter': unreal.TextureFilter.TF_BILINEAR,
    })
    unreal.LandmassBlueprintFunctionLibrary.force_update_texture(tex)
    return tex


def draw(mod, layout):
    FireworkProps.localize(i18n)
    props = FireworkProps()

    split = layout.splitter(ratio=0.62, fill=1, limits=(0.3, 0.85))
    box = split.first.scalebox(fill=1, align=(0, 0))
    box.target.set_editor_property('Stretch', unreal.Stretch.SCALE_TO_FIT)
    box.target.set_editor_property('StretchDirection', unreal.StretchDirection.BOTH)
    image = box.image(align=(2, 1))
    image.hide(True)

    side = split.second.col(fill=1, align=(0, 0), padding=4)

    def show(groups):
        picture = render_preview(groups)
        if picture is None:
            image.hide(True)
            return
        tex = _preview_texture(picture)
        if tex is None:
            image.hide(True)
            return
        image.set_brush_from_texture(tex, False)
        image.set_desired_size_override(unreal.Vector2D(tex.blueprint_get_size_x(), tex.blueprint_get_size_y()))
        image.hide(False)

    def collect():
        groups = []
        for index, name in enumerate(_KIND):
            source = str(getattr(props, name)).strip()
            if not source:
                groups.append([])
                continue
            try:
                groups.append(run_script(source))
            except Exception as exc:
                mineprep.warn(i18n(
                    '{kind} 执行失败',
                    '{kind} failed',
                ).format(kind=_KIND[index]), exc)
                return None
        return groups

    def preview():
        groups = collect()
        if groups is not None:
            show(groups)

    def generate():
        groups = collect()
        if groups is None:
            return
        show(groups)
        table = write_table(str(props.Path).strip(), groups)
        if table:
            mineprep.prints(table.get_path_name())

    side.button(i18n('预览图', 'Preview'), on_clicked=preview, padding=3)
    side.button(i18n('生成表格', 'Generate Table'), on_clicked=generate, padding=3)
    side.prop(props, 'Path', padding=3)
    for name in _KIND:
        side.prop(props, name, fill=1, align=(0, 0), padding=3)


def run_script(source):
    """执行一段生成代码。代码需要给 ``points`` 赋值，元素是 xyz。"""
    namespace = {'np': np, 'sphere': sphere}
    exec(source, namespace)
    if 'points' not in namespace:
        raise ValueError(str(i18n('代码需要给 points 赋值', 'The script must assign points')))
    return [(float(x), float(y), float(z)) for x, y, z in namespace['points']]


def sphere(count, radius=1.0, seed=None):
    """用斐波那契格点在球面上均匀取点，返回 ``[(x, y, z), ...]``。极点在 Z 轴，seed 只旋转整组点。"""
    count = int(count)
    if count < 1:
        raise ValueError('点数至少为 1')
    golden = np.pi * (3.0 - np.sqrt(5.0))
    index = np.arange(count, dtype=np.float64)
    z = 1.0 - (2.0 * index + 1.0) / count
    ring = np.sqrt(np.maximum(0.0, 1.0 - z * z))
    theta = golden * index + (0.0 if seed is None else float(seed))
    radius = float(radius)
    points = np.stack((np.cos(theta) * ring, np.sin(theta) * ring, z), axis=1) * radius
    return [(float(x), float(y), float(z)) for x, y, z in points]


def build_rows(groups):
    """把最多四组坐标收成数据表的 JSON 行。空组会被跳过。"""
    points = []
    for group in groups:
        rows = [(float(x), float(y), float(z)) for x, y, z in group]
        if rows:
            points.append(rows)
    if not points:
        raise ValueError('至少要有一种烟花')
    if len(points) > 4:
        raise ValueError('一个表格最多四种烟花')
    starts = []
    cursor = 1
    for group in points:
        starts.append(cursor)
        cursor += len(group)
    starts.extend([0] * (4 - len(starts)))
    rows = [{
        'Name': META_NAME,
        'Coord': {'X': starts[0], 'Y': starts[1], 'Z': starts[2], 'W': starts[3]},
        'Type': dict(_ZERO),
    }]
    for kind, group in enumerate(points):
        for index, (x, y, z) in enumerate(group):
            rows.append({
                'Name': f'{_KIND[kind]}{index}',
                'Coord': {'X': x, 'Y': y, 'Z': z, 'W': 0},
                'Type': dict(_ZERO),
            })
    return rows


def write_table(path, groups, source=SOURCE):
    """把粒子写入数据表。路径已存在就覆盖行，否则从示例表复制行结构。失败时返回 None。"""
    path = (path or '').strip().replace('\\', '/')
    if path.endswith('/'):
        path = path.rstrip('/')
    try:
        rows = build_rows(groups)
    except ValueError as exc:
        mineprep.warn(str(exc))
        return None
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        table = unreal.load_asset(path)
    else:
        table = mineprep.copy(source, path)
    if not isinstance(table, unreal.DataTable):
        mineprep.warn(i18n('无法创建烟花表: {path}', 'Cannot create firework table: {path}').format(path=path))
        return None
    text = json.dumps(rows, ensure_ascii=False)
    if not table.fill_from_json_string(text, table.get_row_struct()):
        mineprep.warn(i18n('无法写入烟花表: {path}', 'Cannot write firework table: {path}').format(path=path))
        return None
    unreal.EditorAssetLibrary.save_loaded_asset(table)
    return table
