"""山谷驿站：生成预览和可在 UE 中放置的场景。--output 使用一个新目录。"""
import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from time import perf_counter
from types import MappingProxyType

PYTHON_DIR = Path(__file__).resolve().parents[3]
PROJECT_DIR = Path(__file__).resolve().parents[7]
sys.path[:0] = [str(PYTHON_DIR), str(PROJECT_DIR/'Intermediate/PipInstall/Lib/site-packages')]
os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR', '1')

import cv2
import numpy as np
from mods.WorldGenerator import api
from mods.WorldGenerator.examples.valley_outpost_pack.valley_outpost.layout import heights, sites, support_pads, pad_distance

PACK_SOURCE = Path(__file__).with_name('valley_outpost_pack')/'valley_outpost'


def inn():
    b = api.builder((27, 30, 29), origin=(-13, 0, -14))
    b.box('stone_bricks', (-10, 0, -6), (11, 3, 8))
    b.box('oak_planks', (-9, 3, -5), (10, 12, 7), hollow=True)
    b.box('air', (-8, 4, -4), (9, 11, 6))
    for x in (-10, 0, 10):
        for z in (-6, 7):
            b.box('stripped_spruce_log', (x, 2, z), (x+1, 13, z+1), axis='y')
    for y in (3, 11):
        for z in (-6, 7):
            b.box('spruce_log', (-10, y, z), (11, y+1, z+1), axis='x')
        for x in (-10, 10):
            b.box('spruce_log', (x, y, -6), (x+1, y+1, 8), axis='z')
    for x in (-6, 5):
        b.box('air', (x, 6, -6), (x+3, 9, -4))
        b.box('glass_pane', (x, 6, -5), (x+3, 9, -4))
        b.box('spruce_slab', (x-1, 5, -7), (x+4, 6, -5), type='top')
    for z in (-2, 3):
        b.box('air', (9, 6, z), (11, 9, z+2))
        b.box('glass_pane', (9, 6, z), (10, 9, z+2))
    b.box('air', (-1, 3, -6), (2, 6, -4))
    for half, y in (('lower', 3), ('upper', 4)):
        b.set('spruce_door', (0, y, -5), half=half, facing='north', hinge='left')
    b.box('spruce_log', (-1, 5, -5), (2, 6, -4), axis='x')
    # Two gables carry the roof; individual stair rows retain native UVs.
    for z in (-6, 7):
        b.extrude('oak_planks', [(-11, 0), (12, 0), (.5, 11.5)], (0, 12, z), 1, direction='z')
    for rise in range(13):
        for x, facing in ((-12+rise, 'east'), (12-rise, 'west')):
            b.box('dark_oak_stairs', (x, 12+rise, -8), (x+1, 13+rise, 10), facing=facing)
    b.box('dark_oak_slab', (0, 25, -8), (1, 26, 10), type='bottom')
    b.box('oak_planks', (-10, 2, -11), (11, 3, -6))
    for x in (-9, 9):
        for z in (-10, -7):
            b.box('spruce_log', (x, 0, z), (x+1, 10, z+1), axis='y')
    b.box('air', (-2, 2, -11), (3, 3, -10))
    for z, y in ((-12, 0), (-11, 1), (-10, 2)):
        b.box('spruce_stairs', (-2, y, z), (3, y+1, z+1), facing='south')
    for x in range(-11, 12):
        b.box('dark_oak_slab', (x, 10, -12), (x+1, 11, -6), type='bottom')
    for a, c in ((-9, -2), (3, 10)):
        b.box('spruce_fence', (a, 3, -11), (c, 5, -10))
    b.set('lantern', [(-6, 9, -9), (6, 9, -9)], hanging=True)
    b.box('bricks', (6, 12, 2), (8, 27, 4))
    b.box('stone_brick_slab', (5, 27, 1), (9, 28, 5), type='bottom')
    b.paint([('stone_bricks', 7), ('mossy_stone_bricks', 1)],
            b.select(blocks='stone_bricks'), mode='noise', scale=5, salt='inn/stone')
    return b.connect().freeze('ValleyInn')


def woodshed():
    b = api.builder((15, 12, 17), origin=(-7, 0, -8))
    b.box('cobblestone', (-6, 0, -5), (7, 1, 6))
    b.box('oak_planks', (-6, 1, 4), (7, 7, 6))
    for x in (-6, 6):
        for z in (-5, 5):
            b.box('spruce_log', (x, 1, z), (x+1, 8, z+1), axis='y')
    for z in range(-6, 7):
        y = 8-(z+6)//5
        b.box('spruce_slab', (-7, y, z), (8, y+1, z+1), type='top')
    for y in range(1, 4):
        for x in range(-4, 4, 2):
            b.box('oak_log', (x, y, 0), (x+1, y+1, 4), axis='z')
    b.set('barrel', [(4, 1, 1), (4, 1, 3)], facing='north')
    return b.connect().freeze('ValleyWoodshed')


def rest_deck():
    b = api.builder((19, 13, 17), origin=(-9, 0, -8))
    for x in (-7, 7):
        for z in (-5, 5):
            b.box('spruce_log', (x, 0, z), (x+1, 3, z+1), axis='y')
    b.box('spruce_planks', (-8, 2, -6), (9, 3, 7))
    b.box('spruce_stairs', (-2, 0, -8), (3, 1, -7), facing='south')
    b.box('spruce_stairs', (-2, 1, -7), (3, 2, -6), facing='south')
    b.box('spruce_stairs', (-2, 2, -6), (3, 3, -5), facing='south')
    for z in (-4, 3):
        b.box('oak_stairs', (2, 3, z), (7, 4, z+1), facing='north' if z > 0 else 'south')
    b.box('oak_fence', (-1, 3, -1), (0, 5, 0))
    b.box('oak_pressure_plate', (-2, 5, -2), (1, 6, 1))
    b.box('spruce_fence', (-8, 3, 6), (9, 5, 7))
    b.box('spruce_log', (-7, 3, 5), (-6, 11, 6), axis='y')
    b.box('spruce_log', (-7, 10, 3), (-6, 11, 6), axis='z')
    b.set('lantern', (-7, 9, 3), hanging=True)
    return b.connect().freeze('ValleyRestDeck')


def bridge():
    b = api.builder((43, 11, 11), origin=(-21, 0, -5))
    profile = [(-20, 6), (21, 6)]
    profile += [(x, 3*(1-((x-.5)/20.5)**2)) for x in range(21, -21, -1)]
    b.extrude('stone_bricks', profile, (0, 0, -3), 7, direction='z')
    b.box('andesite', (-20, 5, -3), (21, 6, 4))
    for z in (-4, 4):
        b.box('stone_brick_wall', (-20, 6, z), (21, 7, z+1))
        for x in (-20, -10, 0, 10, 20):
            b.box('stone_bricks', (x, 6, z), (x+1, 7, z+1))
            b.set('stone_brick_slab', (x, 7, z), type='bottom')
    b.paint([('stone_bricks', 6), ('mossy_stone_bricks', 1)],
            b.select(blocks='stone_bricks'), mode='noise', scale=6, salt='bridge/stone')
    return b.connect().freeze('ValleyBridge')


def cargo():
    b = api.builder((5, 5, 5), origin=(-2, 0, -2))
    b.box('spruce_planks', (-2, 0, -2), (3, 3, 3))
    for x in (-2, 2):
        b.box('stripped_spruce_log', (x, 0, -2), (x+1, 3, 3), axis='z')
    top = b.select((-2, 0, -2), (3, 3, 3), surface='top')
    caps = top.shift(dy=1) & b.select(blocks='air')
    b.set('spruce_slab', caps, type='bottom')
    b.set('barrel', (-1, 0, -2), facing='north')
    return b.freeze('ValleyCargo')


LOADER = '''"""Load the outpost from this directory; no editor operations on import."""
import json
from pathlib import Path
from mods.WorldGenerator import api

def load_scene(root=None):
    root = Path(root) if root is not None else Path(__file__).parent
    api.register_pack_root(root/'packs')
    spec = api.WorldSpec.from_json((root/'terrain_spec.json').read_text(encoding='utf-8'))
    spec = api.with_heightmap(spec, root/'heightmap.png', output_range=(0, 128))
    world = api.generate(spec)
    models = {p.stem: api.Structure.load(p) for p in (root/'models').glob('*.json')}
    rows = json.loads((root/'placements.json').read_text(encoding='utf-8'))
    parts = [models[r['model']].at(r['position'], r['rotation']) for r in rows]
    return api.compose(world, *parts)
'''

EDITOR = '''"""在 UE 的 Python 控制台用 runpy.run_path 运行此文件。"""
from pathlib import Path
import runpy
import uuid
from mods.WorldGenerator import api

root = Path(__file__).parent
scene = runpy.run_path(str(root/'load_scene.py'))['load_scene'](root)
name = 'ValleyOutpost_' + uuid.uuid4().hex[:8]

def ready(job):
    if job.state != 'completed':
        print(job.status())
        return
    global place_job
    place_job = api.place(job.result, name=name, on_done=lambda done: print(done.status()))

prepare_job = api.prepare(scene, name=name, backend='pcg', on_done=ready)
'''


def signature(scene):
    """Compare generated cells and recipes without embedding filesystem paths."""
    w = scene.terrain
    h = hashlib.sha256()
    for a in (w.heights, w.biome_ids, w.water_mask, w.arrays.xyz, w.arrays.types):
        h.update(np.ascontiguousarray(a).tobytes())
    records = (w.arrays.names, [(m.template.id, m.anchor, m.rotation) for m in w.model_instances],
               [(p.structure.key, p.position, p.rotation) for p in scene.placements])
    h.update(json.dumps(records, sort_keys=True).encode())
    return h.hexdigest()


def preview_colors(scene):
    """Door/wall model stems have no top-texture average; colours are preview-only."""
    colors = {'stone_brick_wall': (133, 135, 120), 'spruce_door': (112, 83, 51)}
    definitions = MappingProxyType({n: replace(d, color=colors[n]) if n in colors else d
                                    for n, d in scene.world.pack.block_defs.items()})
    return replace(scene, world=replace(scene.world, pack=replace(scene.world.pack, block_defs=definitions)))


def site_preview(scene, path, x, z):
    """A temporary display crop; keep the placed scene and terrain untouched."""
    world = scene.world
    points = world.arrays.xyz
    inside = ((np.abs(points[:, 0]+world.arrays.region.x0-x) <= 30) &
              (np.abs(points[:, 2]+world.arrays.region.z0-z) <= 30))
    arrays = replace(world.arrays, xyz=points[inside], types=world.arrays.types[inside])
    models = tuple(m for m in world.model_instances
                   if abs(m.anchor[0]-x) <= 30 and abs(m.anchor[2]-z) <= 30)
    view = replace(scene, world=replace(world, arrays=arrays, model_instances=models))
    api.snapshot(preview_colors(view), path, box=800, views=('isometric', 'front'))


def deliver(output, size=256, seed=42):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = perf_counter()
    pack_id = 'valley_outpost_' + hashlib.sha256(str(output).encode()).hexdigest()[:8]
    pack = output/'packs'/pack_id
    shutil.copytree(PACK_SOURCE, pack, ignore=shutil.ignore_patterns('__pycache__'))
    data = json.loads((pack/'pack.json').read_text(encoding='utf-8'))
    data['id'] = pack_id
    (pack/'pack.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    api.register_pack_root(output/'packs')
    pixels = np.rint(heights(size, seed)/128*65535).astype(np.uint16)
    if not cv2.imwrite(str(output/'heightmap.png'), pixels):
        raise OSError('无法保存高度图')
    spec = api.spec(pack_id, seed=seed, region=(-size//2, -size//2, size, size), params={
        'outpost.size': size, 'world.y_min': 16, 'world.y_max': 144, 'world.sea_level': 32.,
        'hydrology.enabled': False, 'caves.enabled': False, 'cold.enabled': False,
        'aquatic.enabled': False, 'decorations.enabled': False,
        'climate.temperature_offset': .2, 'climate.humidity_offset': .35,
    })
    spec = api.with_heightmap(spec, output/'heightmap.png', output_range=(0, 128))
    t = perf_counter()
    world = api.generate(spec)
    seconds = dict(generate=perf_counter()-t)
    t = perf_counter()
    models = dict(inn=inn(), shed=woodshed(), rest=rest_deck(), bridge=bridge(), cargo=cargo())
    layout = sites(size)
    placements = []
    for name in ('inn', 'shed', 'rest'):
        x, z, _, _, _ = layout[name]
        placements.append(api.ground(world, models[name].at((x, 0, z))))
    crossing = api.ground(world, models['bridge'].at((0, 0, 0)))
    placements.append(crossing)
    ix, iz, _, _, _ = layout['inn']
    for x, z, rotation in ((ix+11, iz+11, 0), (ix+5, iz+11, 90),
                            (layout['shed'][0]+3, layout['shed'][1]-8, 180)):
        placements.append(api.ground(world, models['cargo'].at((x, 0, z), rotation)))
    # Only the arch's end supports reach its lowest layer, so its opening stays clear.
    footing = api.foundation(world, *placements, block='cobblestone', max_depth=8)
    if footing.count:
        models['foundation'] = footing
        placements.append(footing.at((0, 0, 0)))
    scene = api.compose(world, *placements)
    seconds['build_and_compose'] = perf_counter()-t
    t = perf_counter()
    check = api.check(scene)
    seconds['check'] = perf_counter()-t
    z, x = np.indices(world.heights.shape)
    x, z = x+spec.region.x0, z+spec.region.z0
    aprons, surroundings = {}, {}
    for name, (cx, cz, rx, rz, level) in zip(
            ('inn', 'cargo_inn_1', 'cargo_inn_2', 'shed', 'cargo_shed', 'rest'), support_pads(size)):
        edge = pad_distance(x, z, cx, cz, rx, rz)
        ring = (edge > 0) & (edge <= 4)
        aprons[name] = float(world.heights[ring].max()-level)
        if name in ('inn', 'shed'):
            ring = (edge > 0) & (edge <= 12)
            surroundings[name] = float(world.heights[ring].max()-level)
    by_key = {s.key: name for name, s in models.items()}
    (output/'models').mkdir()
    for name, model in models.items():
        model.save(output/'models'/f'{name}.json')
        assert api.Structure.load(output/'models'/f'{name}.json').key == model.key
    rows = [dict(model=by_key[p.structure.key], position=p.position, rotation=p.rotation) for p in placements]
    (output/'placements.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    (output/'terrain_spec.json').write_text(spec.to_json(), encoding='utf-8')
    (output/'load_scene.py').write_text(LOADER, encoding='utf-8')
    (output/'place_in_editor.py').write_text(EDITOR, encoding='utf-8')
    api.snapshot(preview_colors(scene), output/'scene.png', box=900, views=('isometric', 'top', 'front'))
    details = preview_colors(api.compose(None, *[p for p in placements if p.structure.key != footing.key]))
    api.snapshot(details, output/'buildings.png', box=800, views=('isometric', 'front'))
    api.snapshot(preview_colors(api.compose(None, models['inn'].at((0, 0, 0)))), output/'inn.png', box=640)
    api.snapshot(preview_colors(api.compose(None, models['bridge'].at((0, 0, 0)))), output/'bridge.png', box=640)
    for name in ('inn', 'shed'):
        site_preview(scene, output/f'{name}_site.png', *layout[name][:2])
    seconds['total'] = perf_counter()-started
    report = dict(size=size, seed=seed, signature=signature(scene), seconds=seconds,
                  check=check, terrain_cells=world.arrays.count, trees=len(world.model_instances),
                  structure_instances=len(placements), structure_templates=scene.world.stats['structure_templates'],
                  foundation_cells=footing.count, bridge_y=crossing.position[1],
                  apron_max_rise=aprons,
                  surroundings_max_rise=surroundings,
                  water_levels=np.unique(world.water_levels[world.water_mask]).tolist())
    (output/'checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (output/'README.md').write_text(
        '# 山谷驿站\n\n林间小路、石拱桥和桥头的歇脚地。模型、地形和摆放位置都可以继续修改。\n\n'
        '先看 scene.png；buildings.png 隐去地形，inn.png 和 bridge.png 查看建筑细节。'
        'inn_site.png 和 shed_site.png 查看房屋与周围地面的衔接。'
        '这些图片是离线配色预览，实际贴图与光照请在 UE 中查看。\n\n'
        '在 UE 输出日志中切换到 Python，运行（换成这个文件夹的位置）：\n\n'
        '```python\nimport runpy\n'
        "runpy.run_path(r'输出目录/place_in_editor.py')\n```\n\n"
        '脚本会添加独立的 ValleyOutpost 场景组，不保存关卡。'
        '整个文件夹可以一起移动，加载时会重新绑定内容包和高度图路径。\n\n'
        'models 保存可编辑模型，placements.json 保存摆放位置，packs 保存此例的地表规则。'
        '地形采用 16 位高度图，水面高度为 32 格；没有额外安装 Python 库。\n', encoding='utf-8')
    if not check['ok']:
        raise RuntimeError(f'场景存在碰撞，请查看 {output / "checks.json"}')
    if max(aprons.values()) > 2:
        raise RuntimeError(f'院子周围地形过高，请查看 {output / "checks.json"}')
    if max(surroundings.values()) > 3.5:
        raise RuntimeError(f'屋舍周围坡面过高，请查看 {output / "checks.json"}')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, choices=(128, 256), default=256)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(deliver(args.output, args.size, args.seed), ensure_ascii=False))
