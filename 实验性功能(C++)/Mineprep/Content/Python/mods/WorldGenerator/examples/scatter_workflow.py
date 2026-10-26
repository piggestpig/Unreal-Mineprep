"""Independent 128-square scatter demo; --output must be a new directory."""
import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

PYTHON_DIR = Path(__file__).resolve().parents[3]
PROJECT_DIR = Path(__file__).resolve().parents[7]
sys.path[:0] = [str(PYTHON_DIR),str(PROJECT_DIR/'Intermediate/PipInstall/Lib/site-packages')]
import cv2
import numpy as np
from mods.WorldGenerator import api


def models():
    b = api.builder((9,9,9),origin=(-4,0,-4))
    for x in (-3,3):
        for z in (-3,3):
            b.box('oak_log',(x,0,z),(x+1,6,z+1),axis='y')
    b.box('oak_planks',(-3,2,-3),(4,3,4))
    b.box('dark_oak_slab',(-4,6,-4),(5,7,5),type='top')
    shelter = b.freeze('ScatterShelter')
    b = api.builder((7,11,7),origin=(-3,0,-3))
    b.box('stone_bricks',(-2,0,-2),(3,2,3))
    b.extrude('cut_sandstone',[(-1,-1),(1,-1),(1,1),(-1,1)],(0,2,0),7,end_scale=.5)
    b.set('gold_block',(0,9,0))
    monument = b.freeze('ScatterMonument')
    b = api.builder((17,8,7),origin=(-8,0,-3))
    b.box('red_sandstone',(-8,0,-3),(-5,8,4))
    b.box('red_sandstone',(5,0,-3),(8,8,4))
    b.box('red_sandstone',(-5,6,-3),(5,8,4))
    return shelter,monument,b.freeze('ExistingGateway')


EDITOR_SCRIPT = '''"""Run in UE Python; creates a unique scene without saving the level."""
import json
from pathlib import Path
import uuid
from mods.WorldGenerator import api

root = Path(__file__).parent
spec = api.WorldSpec.from_json((root/'terrain_spec.json').read_text(encoding='utf-8'))
world = api.generate(spec)
models = {p.stem:api.Structure.load(p) for p in root.glob('model_*.json')}
records = json.loads((root/'placements.json').read_text(encoding='utf-8'))
parts = [models[row['model']].at(row['position'],row['rotation']) for row in records]
footing = api.Structure.load(root/'foundation.json')
if footing.count:
    parts.append(footing.at((0,0,0)))
source = api.compose(world,*parts)
assert api.check(source)['ok']
name = 'ScatterTools_' + uuid.uuid4().hex[:8]

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
    z,x = np.indices((128,128))
    values = .2+.5*x/127+.08*np.sin(z/18)
    if not cv2.imwrite(str(output/'slope.png'),np.rint(values*65535).astype(np.uint16)):
        raise OSError('could not write slope.png')
    spec = api.spec(region=(-64,-64,128,128),params={
        'world.y_min':32,'world.y_max':96,'trees.enabled':False,'vegetation.enabled':False,
        'aquatic.enabled':False,'decorations.enabled':False,'caves.enabled':False,
        'water.generate':False,'cold.enabled':False})
    spec = api.with_heightmap(spec,output/'slope.png',output_range=(40,64))
    world = api.generate(spec,keep_fields=('slope',))
    shelter,monument,gateway = models()
    existing = api.ground(world,gateway.at((0,0,0)))
    existing_base = api.foundation(world,existing,max_depth=4)
    obstacles = (existing,*([existing_base.at((0,0,0))] if existing_base.count else []))
    # Artist-provided probability map: a protected empty corridor and broad patches.
    density = np.clip(.55+.4*np.sin(x/19)*np.cos(z/23),0,1)
    density[np.abs(x-64)<10] = 0
    started = perf_counter()
    result = api.scatter(world,[(shelter,3),(monument,1)],spacing=14,density=density,
                         where={'slope':{'max':.4}},existing=obstacles,max_depth=4,seed=29)
    seconds = perf_counter()-started
    assert result.placements
    parts = [existing,*result.placements]
    footing = api.foundation(world,*parts,block='stone_bricks',max_depth=4)
    scene = api.compose(world,*parts,*([footing.at((0,0,0))] if footing.count else []))
    check = api.check(scene)
    assert check['ok'],check
    table = {s.key:'model_'+str(i) for i,s in enumerate((shelter,monument,gateway))}
    for s in (shelter,monument,gateway):
        s.save(output/(table[s.key]+'.json'))
    footing.save(output/'foundation.json')
    records = [dict(model=table[p.structure.key],position=p.position,rotation=p.rotation) for p in parts]
    (output/'placements.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    (output/'terrain_spec.json').write_text(spec.to_json(),encoding='utf-8')
    api.snapshot(scene,output/'scene.png',box=512,
                 extra_lines=('Weighted shared templates, density patches, protected corridor and existing gateway.',))
    api.snapshot(api.compose(None,*scene.placements),output/'details.png',box=512,
                 extra_lines=('Terrain hidden for inspection; not proof of UE rendering.',))
    cv2.imwrite(str(output/'density.png'),np.rint(density*255).astype(np.uint8))
    report = dict(scatter=result.stats,scatter_seconds=seconds,
                  footing_cells=footing.count,check=check,templates=scene.world.stats['structure_templates'])
    (output/'checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (output/'place_in_editor.py').write_text(EDITOR_SCRIPT,encoding='utf-8')
    (output/'README.md').write_text(
        '# Shared-template scatter\n\n'
        'A 128-square slope with weighted shelters/monuments, an artist density map, an existing gateway,\n'
        'and one separate foundation. The density map reserves a central corridor.\n'
        'PNG files are cell-colour diagnostics, not UE renders. Keep this directory in place: the Spec\n'
        'references slope.png by absolute path.\n\n'
        'Run in UE Python, substituting this output directory:\n\n'
        '```python\nimport mineprep, runpy\nmineprep.reload()\n'
        "runpy.run_path(r'PATH_TO_OUTPUT/place_in_editor.py')\n```\n\n"
        'Inspect reload warnings first. Placement creates a unique name and does not save the level.\n',encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(deliver(parser.parse_args().output),ensure_ascii=False))
