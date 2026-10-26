"""128-square slope, shared pavilions and separate footings; --output must be new."""
import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

PYTHON_DIR = Path(__file__).resolve().parents[3]
PROJECT_DIR = Path(__file__).resolve().parents[7]
sys.path[:0] = [str(PYTHON_DIR), str(PROJECT_DIR/'Intermediate/PipInstall/Lib/site-packages')]
import cv2
import numpy as np
from mods.WorldGenerator import api


def pavilion():
    b = api.builder((15,16,13),origin=(-7,-2,-6))
    for x in (-5,5):
        for z in (-3,3):
            b.box('oak_log',(x,2,z),(x+1,10,z+1),axis='y')
    b.box('oak_planks',(-5,5,-3),(6,6,4))
    for x in (-5,5):
        b.box('oak_fence',(x,6,-2),(x+1,8,3))
    for rise in range(4):
        for x,facing in ((-6+rise,'east'),(6-rise,'west')):
            b.set('brick_stairs',[(x,10+rise,z) for z in range(-4,5)],facing=facing)
    b.box('bricks',(-2,13,-4),(3,14,5))
    return b.connect().freeze('SlopePavilion')


EDITOR_SCRIPT = '''"""Run in UE Python; adds a unique scene without saving the level."""
import json
from pathlib import Path
import uuid
from mods.WorldGenerator import api

root = Path(__file__).parent
world = api.generate(api.WorldSpec.from_json((root/'terrain_spec.json').read_text(encoding='utf-8')))
model = api.Structure.load(root/'pavilion.json')
records = json.loads((root/'placements.json').read_text(encoding='utf-8'))
parts = [model.at(row['position'],row['rotation']) for row in records]
footing = api.Structure.load(root/'foundation.json')
if footing.count:
    parts.append(footing.at((0,0,0)))
source = api.compose(world,*parts)
assert api.check(source)['ok']
name = 'GroundingTools_' + uuid.uuid4().hex[:8]

def ready(job):
    if job.state != 'completed':
        print(job.status())
        return
    global place_job
    place_job = api.place(job.result,name=name,on_done=lambda done: print(done.status()))

prepare_job = api.prepare(source,name=name,on_done=ready)
'''


def deliver(output):
    output = Path(output)
    output.mkdir(parents=True,exist_ok=False)
    x,z = np.meshgrid(np.arange(128),np.arange(128))
    values = .15+.65*x/127+.05*np.sin(z/14)
    if not cv2.imwrite(str(output/'slope.png'),np.rint(values*65535).astype(np.uint16)):
        raise OSError('could not write slope.png')
    spec = api.spec(region=(-64,-64,128,128),params={
        'world.y_min':32, 'world.y_max':96, 'trees.enabled':False, 'vegetation.enabled':False,
        'aquatic.enabled':False, 'decorations.enabled':False, 'caves.enabled':False,
        'water.generate':False, 'cold.enabled':False})
    spec = api.with_heightmap(spec,output/'slope.png',output_range=(40,68))
    start = perf_counter()
    world = api.generate(spec)
    timings = {'generate':perf_counter()-start}
    model = pavilion()
    start = perf_counter()
    placements = [api.ground(world,model.at((x,0,z),rotation))
                  for x,z,rotation in ((-24,-14,0),(0,0,90),(24,14,180))]
    timings['ground_three'] = perf_counter()-start
    start = perf_counter()
    footing = api.foundation(world,*placements,block='polished_blackstone_bricks',max_depth=8)
    timings['foundation'] = perf_counter()-start
    parts = [*placements, *([footing.at((0,0,0))] if footing.count else [])]
    before,after = api.compose(world,*placements),api.compose(world,*parts)
    checks = {'before':api.check(before),'after':api.check(after)}
    model.save(output/'pavilion.json')
    footing.save(output/'foundation.json')
    assert api.Structure.load(output/'foundation.json').key == footing.key
    assert after.world.stats['structure_templates'] == 2
    records = [dict(position=p.position,rotation=p.rotation) for p in placements]
    (output/'placements.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    (output/'terrain_spec.json').write_text(spec.to_json(),encoding='utf-8')
    api.snapshot(before,output/'before.png',box=512,extra_lines=('Grounded bodies only; uneven terrain leaves gaps under some legs.',))
    api.snapshot(after,output/'after.png',box=512,extra_lines=('Shared bodies plus one separate foundation recipe.',))
    api.snapshot(api.compose(None,*parts),output/'details.png',box=384,
                 extra_lines=('Terrain hidden for inspection; this view does not prove ground contact.',))
    report = dict(checks=checks,seconds=timings,foundation_cells=footing.count,
                  body_instances=len(placements),templates=after.world.stats['structure_templates'])
    (output/'checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (output/'place_in_editor.py').write_text(EDITOR_SCRIPT,encoding='utf-8')
    (output/'README.md').write_text(
        '# Surface grounding and foundations\n\n'
        'Three rotations share pavilion.json. The lowest actual layer contains four posts;\n'
        'foundation.json fills only beneath those posts, leaving the entrance and raised deck open.\n'
        'Before/after show the generated 128-square slope. Details hides the terrain.\n'
        'PNG files are cell-colour diagnostics; UE textures and lighting need user acceptance.\n\n'
        'Keep this directory in place: terrain_spec.json references slope.png by absolute path.\n'
        'Run in UE Python, substituting the output directory:\n\n'
        '```python\nimport mineprep, runpy\nmineprep.reload()\n'
        "runpy.run_path(r'PATH_TO_OUTPUT/place_in_editor.py')\n```\n\n"
        'Inspect reload warnings first. The script adds a unique scene without saving the level.\n',encoding='utf-8')
    if not all(r['ok'] for r in checks.values()):
        raise RuntimeError('inspect checks.json')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(deliver(parser.parse_args().output),ensure_ascii=False))
