"""Three public-API recipes. CLI is offline; --output must name a delivery folder."""
import argparse
import json
from pathlib import Path
import sys

PYTHON_DIR = Path(__file__).resolve().parents[3]
PROJECT_DIR = Path(__file__).resolve().parents[7]
sys.path[:0] = [str(PYTHON_DIR), str(PROJECT_DIR/'Intermediate/PipInstall/Lib/site-packages')]
from mods.WorldGenerator import api


def treehouse():
    b = api.builder((33, 36, 37), origin=(-16, 0, -16))
    for center, radii in [((-5,25,0),(6,5,6)), ((4,28,1),(7,5,7)), ((0,25,-6),(7,5,6))]:
        b.ellipsoid('oak_leaves', center, radii, persistent=True)
    b.cylinder('oak_log', (.5,0,.5), 1.6, 27, axis='y')
    b.box('oak_log', (-2,0,-2), (3,2,3), axis='y')
    b.box('oak_log', (-5,21,-1), (6,23,2), axis='x')
    b.box('oak_log', (-1,20,-7), (2,22,4), axis='z')
    b.box('oak_log', (-6,11,0), (10,12,2), axis='x')
    b.box('oak_planks', (-7,12,-7), (10,13,7))
    b.box('oak_planks', (2,13,-5), (9,20,4), hollow=True)
    b.box('air', (4,14,-5), (6,18,-4))
    b.box('glass', (8,15,-2), (9,18,2))
    b.box('glass', (3,15,3), (6,18,4))
    for y in (13,):
        b.set('oak_fence', [[x,y,z] for x in range(-7,10) for z in (-7,6)], east=True,west=True)
        b.set('oak_fence', [[x,y,z] for x in (-7,9) for z in range(-6,6)], north=True,south=True)
        for x in (-7,9):
            for z in (-7,6):
                b.set('oak_fence', (x,y,z), north=True,south=True,east=True,west=True)
    b.box('air', (-2,13,6), (0,14,7))
    for step in range(13):
        z = 18-step
        b.set('oak_stairs', [(-2,step,z),(-1,step,z)], facing='north',half='bottom',shape='straight')
        if step:
            b.set('oak_log', [(-2,step-1,z),(-1,step-1,z)], axis='x')
    for rise in range(4):
        for x, facing in ((1+rise,'east'),(9-rise,'west')):
            b.set('dark_oak_stairs', [(x,20+rise,z) for z in range(-6,5)],
                  facing=facing,half='bottom',shape='straight')
    b.box('dark_oak_slab', (5,24,-6), (6,25,5), type='bottom')
    return b.freeze('treehouse')


def steve():
    """128 blocks tall: 4 world blocks per pixel of the classic 32-pixel figure."""
    b = api.builder((64,128,32), origin=(-32,0,-16))
    for lo, hi in [((-16,0,-8),(0,48,8)), ((0,0,-8),(16,48,8))]:
        b.box('blue_concrete', lo, hi)
    b.box('gray_concrete', (-16,0,-8), (16,8,8))
    b.box('blue_wool', (-4,8,-8), (4,44,-4))
    b.box('cyan_concrete', (-16,48,-8), (16,96,8))
    for x in (-32,16):
        b.box('white_terracotta', (x,48,-8), (x+16,80,8))
        b.box('cyan_concrete', (x,80,-8), (x+16,96,8))
    b.box('light_blue_wool', (-4,56,-8), (4,84,-4))
    b.box('white_terracotta', (-16,96,-16), (16,128,16))
    b.box('brown_concrete', (-16,124,-16), (16,128,16))
    b.box('brown_concrete', (-16,96,12), (16,128,16))
    for x in (-16,12):
        b.box('brown_concrete', (x,112,-12), (x+4,128,12))
    for x in (-12,4):
        b.box('brown_concrete', (x,112,-16), (x+8,116,-12))
        b.box('white_concrete', (x,108,-16), (x+8,112,-12))
    for x in (-8,4):
        b.box('purple_concrete', (x,108,-16), (x+4,112,-12))
    b.box('brown_terracotta', (-4,104,-16), (4,108,-12))
    b.box('brown_concrete', (-8,96,-16), (8,104,-12))
    b.box('pink_terracotta', (-4,100,-16), (4,104,-12))
    return b.freeze('steve_128')


def deliver(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    reports = {}
    badlands = api.generate(api.spec('vanilla','badlands',seed=42,region=(-64,-64,128,128)))
    reports['badlands'] = api.check(badlands,expect_biomes=('badlands',))
    api.snapshot(badlands,output/'badlands.png')
    (output/'badlands_spec.json').write_text(badlands.spec.to_json(),encoding='utf-8')
    ground = api.generate(api.spec('vanilla','',seed=42,region=(-32,-32,64,64),params={'terrain.flat': True,
        'trees.enabled':False,'vegetation.enabled':True,'caves.enabled':False,'water.generate':False}))
    house = treehouse()
    house.save(output/'treehouse.json')
    api.snapshot(house,output/'treehouse_views.png')
    scene = api.compose(ground,house.at((0,int(ground.heights.max())+1,0)))
    reports['treehouse_scene'] = api.check(scene)
    api.snapshot(scene,output/'treehouse_scene.png')
    (output/'treehouse_ground_spec.json').write_text(ground.spec.to_json(),encoding='utf-8')
    statue = steve()
    statue.save(output/'steve.json')
    reports['steve'] = api.check(statue)
    api.snapshot(statue,output/'steve_views.png')
    # A local material revision never requires writing a new content pack.
    statue.edit().replace('cyan_concrete','cyan_wool').freeze('steve_wool_shirt').save(output/'steve_wool.json')
    (output/'checks.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(r['ok'] for r in reports.values()):
        raise RuntimeError('example checks failed; inspect checks.json')
    return reports


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    results = deliver(args.output)
    print(json.dumps({name:r['ok'] for name,r in results.items()}))
