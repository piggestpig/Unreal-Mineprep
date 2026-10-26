"""Polyline/profile geometry and blend-width demo; --output must be new."""
import argparse
import json
from pathlib import Path
import sys

PYTHON_DIR = Path(__file__).resolve().parents[3]
PROJECT_DIR = Path(__file__).resolve().parents[7]
sys.path[:0] = [str(PYTHON_DIR), str(PROJECT_DIR/'Intermediate/PipInstall/Lib/site-packages')]
from mods.WorldGenerator import api


def samples():
    tube = api.builder((44,28,20),origin=(-22,0,-10))
    tube.tube('oxidized_copper',[(-18,3,-5),(-8,11,1),(2,18,-3),(18,1.5,4)],
              [3,2.6,2.2,2])
    tube.tube('oxidized_copper',[(-8,11,1),(-14,18,3),(-19,23,4)],[2.4,1.5,0])

    profiles = api.builder((48,28,20),origin=(-24,0,-10))
    arch = [(-8,0),(-8,20),(8,20),(8,0),(4,0),(4,12),(-4,12),(-4,0)]
    profiles.extrude('sandstone',arch,(-10,0,-6),6,direction='z')
    profiles.extrude('red_terracotta',[(-8,0),(8,0),(0,11)],(12,0,-6),12,direction='z')

    column = api.builder((16,32,16),origin=(-8,0,-8))
    column.extrude('stone',[(-6,-6),(6,-6),(6,6),(-6,6)],(0,0,0),28,end_scale=.35)
    column.box('stone',(-7,0,-7),(7,2,7))
    source = column.freeze('ColumnSource')
    result = {'tube':tube.freeze('RoundTube'), 'profiles':profiles.freeze('ProfileExtrusions')}
    for name,blend in (('blend_0',0),('blend_035',.35),('blend_1',1)):
        painted = source.edit().paint([(2,'blackstone'),(26,'calcite')],mode='height',blend=blend)
        result[name] = painted.freeze(name)
    return result


EDITOR_SCRIPT = '''"""Run with runpy.run_path in UE Python; adds a uniquely named scene."""
from pathlib import Path
import uuid
from mods.WorldGenerator import api

source = api.Structure.load(Path(__file__).with_name('assembly.json'))
name = 'GeometryTools_' + uuid.uuid4().hex[:8]

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
    assembly = api.builder((112,44,72),origin=(-56,0,-36))
    assembly.box('smooth_stone',(-56,0,-36),(56,1,36))
    for x,name in ((-48,'blend_0'),(-16,'blend_035'),(16,'blend_1')):
        assembly.paste(structures[name],(x,1,12))
    assembly.paste(structures['tube'],(-52,1,-28))
    assembly.paste(structures['profiles'],(0,1,-28))
    structures['assembly'] = assembly.freeze('GeometryGallery')
    reports = {}
    for name,structure in structures.items():
        structure.save(output/(name+'.json'))
        loaded = api.Structure.load(output/(name+'.json'))
        assert loaded.key == structure.key
        reports[name] = api.check(loaded)
        lines = ('Back row left to right: blend 0 / 0.35 / 1',
                 'Front: tapered round tubes / concave and triangular profiles') if name=='assembly' else ()
        api.snapshot(loaded,output/(name+'.png'),extra_lines=lines)
    for name in ('blend_035','blend_1'):
        assert (structures[name].xyz == structures['blend_0'].xyz).all()
    (output/'checks.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
    (output/'place_in_editor.py').write_text(EDITOR_SCRIPT,encoding='utf-8')
    (output/'README.md').write_text(
        '# Geometry and blend-width gallery\n\n'
        'Back row, left to right: blend 0, 0.35 and 1. The three columns share identical geometry.\n'
        'Front: a varying-radius tube with a tapered offshoot, a concave extrusion, and a triangular extrusion.\n'
        'All JSON files are editable frozen structures. PNG files are cell-colour diagnostics, not UE renders.\n\n'
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
