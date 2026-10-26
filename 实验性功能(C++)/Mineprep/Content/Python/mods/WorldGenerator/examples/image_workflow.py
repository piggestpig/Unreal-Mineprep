"""Export pixel art, brightness relief and a custom relief to a new directory.

    python image_workflow.py --output NEW_DIRECTORY [--source IMAGE] [--size 64]
"""
import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

PYTHON_DIR = Path(__file__).resolve().parents[3]
PROJECT_DIR = Path(__file__).resolve().parents[7]
sys.path[:0] = [str(PYTHON_DIR), str(PROJECT_DIR/'Intermediate/PipInstall/Lib/site-packages')]

import numpy as np
from PIL import Image
from mods.WorldGenerator import api
from mods.WorldGenerator.adapters.mesh_input import image_rgba


def waves(rgba):
    """A common backing plus smooth ridges; input is the final uint8 RGBA image."""
    y,x = np.indices(rgba.shape[:2])
    return 5 + 3*np.sin(x/5)*np.cos(y/7)


EDITOR_SCRIPT = '''from pathlib import Path
import uuid
from mods.WorldGenerator import api

root = Path(__file__).parent
models = [api.Structure.load(root/(key+'.json'))
          for key in ('pixel_art','brightness_relief','custom_relief')]
step = max(m.size[0] for m in models)+12
scene = api.compose(None, *(m.at((i*step,0,0)) for i,m in enumerate(models)))
name = 'ImageArt_' + uuid.uuid4().hex[:8]

def ready(job):
    if job.state == 'completed':
        global place_job
        place_job = api.place(job.result,name=name,location=(0,0,0))
    else:
        print(job.status())

prepare_job = api.prepare(scene,name=name,backend='pcg',on_done=ready)
'''


def deliver(output, source=None, *, size=128, resample='box', colors=None, smooth=0.):
    output = Path(output)
    output.mkdir(parents=True,exist_ok=False)
    if source is None:
        # Ordinary RGBA art with a transparent exterior and hole; no UE dependency.
        y,x = np.indices((64,64))
        radius = np.hypot(x-31.5,y-31.5)
        image = np.empty((64,64,4),np.uint8)
        image[...,0] = np.rint(x/63*255)
        image[...,1] = np.rint(y/63*255)
        image[...,2] = np.where((x//8+y//8)%2,220,70)
        image[...,3] = np.where((radius < 30) & (radius > 6),255,0)
    else:
        image = image_rgba(source,size=size,resample=resample)
    Image.fromarray(image).save(output/'source.png')
    report = {}
    for key,depth in (('pixel_art',1),('brightness_relief',(2,14)),('custom_relief',waves)):
        start = perf_counter()
        model = api.image_structure(image,size=size,resample=resample,depth=depth,
                                    colors=colors,smooth=smooth,name=key)
        elapsed = perf_counter()-start
        model.save(output/(key+'.json'))
        assert api.Structure.load(output/(key+'.json')).key == model.key
        check = api.check(model)
        assert check['ok'], check
        api.snapshot(model,output/(key+'.png'))
        if key != 'pixel_art':
            facing = api.compose(None,model.at((0,0,0),180))
            api.snapshot(facing,output/(key+'_relief_side.png'))
        report[key] = dict(seconds=elapsed,cells=model.count,size=model.size,key=model.key,check=check,
                          used_blocks=len(np.unique(model.types)),colors=colors,smooth=smooth)
    (output/'place_in_editor.py').write_text(EDITOR_SCRIPT,encoding='utf-8')
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'README.md').write_text(
        '# Image structures\n\nsource.png is the resized input; other PNGs are offline diagnostics, not UE renders.\n'
        'pixel_art has one layer; brightness_relief maps black/white to depths 2/14;\n'
        'custom_relief uses the vectorized waves(rgba) callback from image_workflow.py.\n'
        'All columns have a flat back and carry their pixel material through the depth.\n\n'
        '*_relief_side.png shows the raised +Z side using a rotated display instance;\n'
        'the frozen model is unchanged. Standard front views look at the flat back (-Z).\n\n'
        'Run place_in_editor.py in UE Python to add an independent group. It does not save the level.\n',
        encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--size',type=int,default=128,help='Longest edge cap; keeps aspect ratio and never upscales')
    parser.add_argument('--resample',choices=('box','nearest'),default='box')
    parser.add_argument('--colors',type=int,help='Maximum used block colours; omitted keeps the full palette')
    parser.add_argument('--smooth',type=float,default=0.,help='Group similar neighbouring colours, 0..1')
    args = parser.parse_args()
    print(json.dumps(deliver(args.output,args.source,size=args.size,resample=args.resample,
                             colors=args.colors,smooth=args.smooth),ensure_ascii=True))
