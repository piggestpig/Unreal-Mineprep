"""Selection and paint demo; --output must be a new directory. Runs without UE."""
import argparse
import json
from pathlib import Path
import sys

PYTHON_DIR = Path(__file__).resolve().parents[3]
PROJECT_DIR = Path(__file__).resolve().parents[7]
sys.path[:0] = [str(PYTHON_DIR), str(PROJECT_DIR/'Intermediate/PipInstall/Lib/site-packages')]
from mods.WorldGenerator import api


def samples():
    wall = api.builder((36,24,8),origin=(-18,0,-4))
    wall.box('stone_bricks',(-18,0,-2),(18,18,3))
    wall.box('air',(-4,0,-2),(4,10,3))
    wall.box('air',(-3,10,-2),(3,12,3))
    wall.box('air',(-1,12,-2),(1,13,3))
    for x in (-17,-9,8,16):
        wall.box('stone_bricks',(x,0,-3),(x+1,20,4))
    for x in range(-18,18,4):
        wall.box('stone_bricks',(x,18,-2),(x+2,21,3))
    before_wall = wall.freeze('WallBefore')
    exposed = wall.select(blocks='stone_bricks',surface='exposed')
    protected = wall.select((-5,0,-4),(5,15,4))
    wall.paint([('stone_bricks',3),('mossy_stone_bricks',1),('cracked_stone_bricks',1)],
               exposed-protected,mode='noise',scale=5,seed=42,salt='wall/weather')
    wall.paint('chiseled_stone_bricks',exposed & protected)

    monument = api.builder((24,36,24),origin=(-12,0,-12))
    for y in range(34):
        radius = 11 if y<3 else max(1,9-(y-3)//4)
        monument.box('stone',(-radius,y,-radius),(radius,y+1,radius))
    before_monument = monument.freeze('MonumentBefore')
    monument.paint([(0,'blackstone'),(12,'deepslate'),(24,'tuff'),(34,'calcite')],
                   mode='height',seed=42,salt='monument/height')
    return {'wall_before':before_wall, 'wall_after':wall.freeze('WeatheredWall'),
            'monument_before':before_monument, 'monument_after':monument.freeze('HeightMonument')}


EDITOR_SCRIPT = '''"""Run with runpy.run_path in UE Python; adds a uniquely named scene."""
from pathlib import Path
import uuid
from mods.WorldGenerator import api

source = api.Structure.load(Path(__file__).with_name('assembly.json'))
name = 'MaterialPaint_' + uuid.uuid4().hex[:8]

def ready(job):
    if job.state != 'completed':
        print(job.status())
        return
    global place_job
    place_job = api.place(job.result, name=name, on_done=lambda done: print(done.status()))

prepare_job = api.prepare(source, name=name, on_done=ready)
'''


def deliver(output):
    output = Path(output)
    output.mkdir(parents=True,exist_ok=False)
    structures = samples()
    assembly = api.builder((72,40,32),origin=(-36,0,-16))
    assembly.box('smooth_stone',(-36,0,-16),(36,1,16))
    assembly.paste(structures['wall_after'],(-34,1,-4))
    assembly.paste(structures['monument_after'],(8,1,-12))
    structures['assembly'] = assembly.freeze('PaintGallery')
    reports = {}
    for name,structure in structures.items():
        structure.save(output/(name+'.json'))
        loaded = api.Structure.load(output/(name+'.json'))
        assert loaded.key == structure.key
        reports[name] = api.check(loaded)
        api.snapshot(loaded,output/(name+'.png'))
    for before,after in (('wall_before','wall_after'),('monument_before','monument_after')):
        assert structures[before].count == structures[after].count
        assert (structures[before].xyz == structures[after].xyz).all()
    (output/'checks.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
    (output/'place_in_editor.py').write_text(EDITOR_SCRIPT,encoding='utf-8')
    (output/'README.md').write_text(
        '# Selection and paint gallery\n\n'
        'Wall: smooth noise patches outside a protected gate frame; fixed material inside.\n'
        'Monument: seeded height blends between blackstone, deepslate, tuff and calcite.\n'
        'Before/after pairs preserve every occupied coordinate. JSON recipes remain editable.\n'
        'PNG files are cell-colour diagnostics, not UE renders.\n\n'
        'Run in UE Python, substituting this output directory:\n\n'
        '```python\nimport mineprep, runpy\nmineprep.reload()\n'
        "runpy.run_path(r'PATH_TO_OUTPUT/place_in_editor.py')\n```\n\n"
        'Inspect reload warnings first. The script adds a uniquely named scene and does not save the level.\n',
        encoding='utf-8')
    if not all(report['ok'] for report in reports.values()):
        raise RuntimeError('inspect checks.json')
    return reports


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(deliver(parser.parse_args().output),ensure_ascii=False))
