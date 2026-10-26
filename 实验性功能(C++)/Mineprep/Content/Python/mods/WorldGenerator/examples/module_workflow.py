"""Offline modular authoring demo; --output must be a new directory."""
import argparse
import json
from pathlib import Path
import sys

PYTHON_DIR = Path(__file__).resolve().parents[3]
PROJECT_DIR = Path(__file__).resolve().parents[7]
sys.path[:0] = [str(PYTHON_DIR), str(PROJECT_DIR/'Intermediate/PipInstall/Lib/site-packages')]
from mods.WorldGenerator import api


def module():
    b = api.builder((7,8,5),origin=(-3,0,-2))
    b.box('stone_bricks',(-3,0,-2),(4,1,3))
    b.box('oak_planks',(-3,1,2),(4,4,3))
    b.box('glass_pane',(-1,2,2),(2,4,3))
    for x in (-3,3):
        for z in (-2,2):
            b.box('oak_log',(x,1,z),(x+1,4,z+1),axis='y')
    b.box('oak_log',(-3,3,-2),(4,4,-1),axis='x')
    b.line('oak_fence',(-2,1,-2),(-1,1,-2))
    b.line('oak_fence',(1,1,-2),(2,1,-2))
    b.set('oak_fence_gate',(0,1,-2),facing='north')
    b.set('gold_block',(-2,3,-1))  # Asymmetric marker makes the mirror visible.
    for rise in range(3):
        for x,facing in ((-3+rise,'east'),(3-rise,'west')):
            b.set('brick_stairs',[(x,4+rise,z) for z in range(-2,3)],facing=facing)
    b.box('brick_slab',(0,7,-2),(1,8,3),type='bottom')
    return b.connect().freeze('PorchModule')


EDITOR_SCRIPT = '''"""Run this file in UE Python with runpy.run_path; adds a separately named scene."""
from pathlib import Path
import uuid
from mods.WorldGenerator import api

source = api.Structure.load(Path(__file__).with_name('assembly.json'))
blocks = api.to_blocks(source)
restored = api.from_blocks(blocks)
assert restored.key == source.key
name = 'ModuleInterop_' + uuid.uuid4().hex[:8]

def placed(job):
    if job.state == 'completed':
        print(dict(state=job.state, actors=job.result['actor_paths']))
    else:
        print(dict(state=job.state, error=job.error))

def ready(job):
    if job.state != 'completed':
        print(dict(state=job.state, error=job.error))
        return
    global place_job
    place_job = api.place(job.result, name=name, location=(0,0,0), on_done=placed)

prepare_job = api.prepare(restored, name=name, on_done=ready)
'''


def deliver(output):
    output = Path(output)
    output.mkdir(parents=True,exist_ok=False)
    original = module()
    mirrored = original.edit().mirror('x').freeze('PorchMirrored')
    b = api.builder((29,8,29),origin=(-14,0,-14))
    b.box('dark_oak_planks',(-14,0,-14),(15,1,15))
    for piece,at,rotation in ((original,(-12,0,-12),180), (original,(6,0,-12),270),
                               (mirrored,(5,0,7),0), (mirrored,(-12,0,5),90)):
        b.paste(piece,at,rotation=rotation)
    assembly = b.freeze('ModuleCourtyard')
    reports = {}
    for name,structure in (('module',original),('mirrored',mirrored),('assembly',assembly)):
        structure.save(output/(name+'.json'))
        loaded = api.Structure.load(output/(name+'.json'))
        assert loaded.key == structure.key
        reports[name] = api.check(loaded)
        api.snapshot(loaded,output/(name+'.png'))
    (output/'place_in_editor.py').write_text(EDITOR_SCRIPT,encoding='utf-8')
    (output/'checks.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
    (output/'README.md').write_text(
        '# Module authoring demo\n\n'
        'module / mirrored / assembly JSON are editable frozen Structures. PNG files are\n'
        'cell-colour diagnostics, not UE renders. The roof and panes use native states.\n\n'
        'To place the assembly, run in UE Python (substitute the actual output path):\n\n'
        "```python\nimport mineprep, runpy\nmineprep.reload()  # Load this round's source changes; inspect reload warnings.\n"
        "runpy.run_path(r'PATH_TO_OUTPUT/place_in_editor.py')\n```\n\n"
        'The script verifies the Blocks roundtrip and creates a unique scene name;\n'
        'it does not save the level.\n',encoding='utf-8')
    if not all(report['ok'] for report in reports.values()):
        raise RuntimeError('inspect checks.json')
    return reports


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(deliver(args.output),ensure_ascii=False))
