"""植被与留空区域对照：--output 新目录，--size 128 或256。"""
import argparse
import json
import os
from pathlib import Path
import sys
from time import perf_counter

PYTHON_DIR = Path(__file__).resolve().parents[3]
PROJECT_DIR = Path(__file__).resolve().parents[7]
sys.path[:0] = [str(PYTHON_DIR), str(PROJECT_DIR/'Intermediate/PipInstall/Lib/site-packages')]
os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR','1')

import cv2
import numpy as np
from mods.WorldGenerator import api
from mods.WorldGenerator.adapters.preview import write_views
from mods.WorldGenerator.core.masks import blocked


EDITOR = '''from pathlib import Path
from mods.WorldGenerator import api
folder = Path(__file__).resolve().parent
spec = api.WorldSpec.from_json((folder/'terrain_spec.json').read_text(encoding='utf8'))
spec = api.with_vegetation_mask(spec, folder/'vegetation.png', region=spec.vegetation_mask.region)
spec = api.with_clearance_mask(spec, folder/'clearance.png', region=spec.clearance_mask.region)
world = api.generate(spec)
def prepared(job):
    if job.state == 'completed':
        api.place(job.result, name='MaskStudy_'+str(spec.region.width))
api.prepare(world, backend='pcg', on_done=prepared)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--size',type=int,choices=(128,256),default=128)
    parser.add_argument('--seed',type=int,default=42)
    args = parser.parse_args()
    out, size = args.output.resolve(),args.size
    out.mkdir(parents=True,exist_ok=False)
    z,x = np.mgrid[:size,:size]
    # The path bends through an irregular clearing; the meadow fades into forest.
    centre = size*(.48+.14*np.sin(z/size*5.5))
    distance = np.abs(x-centre)
    clearing = ((x-size*.65)/(size*.15))**2+((z-size*.58)/(size*.12))**2
    clearance = ((distance < max(3,size*.025)) | (clearing<1)).astype(np.uint8)*255
    vegetation = np.clip((distance-size*.04)/(size*.15),0,1)
    vegetation *= .65+.35*np.sin((x+z*.6)/size*3)**2
    cv2.imwrite(str(out/'vegetation.png'),np.rint(vegetation*65535).astype(np.uint16))
    cv2.imwrite(str(out/'clearance.png'),clearance)
    base_spec = api.spec(seed=args.seed,region=(-64,-96,size,size))
    spec = api.with_clearance_mask(api.with_vegetation_mask(base_spec,out/'vegetation.png'),out/'clearance.png')
    report = {}
    worlds = {}
    for label,s in (('before',base_spec),('after',spec)):
        started = perf_counter()
        world = api.generate(s)
        seconds = perf_counter()-started
        worlds[label] = world
        write_views(world,out/label,names=('landscape','vegetation','surface','vegetation_mask','clearance_mask'))
        api.snapshot(world,out/(label+'.png'))
        report[label] = dict(seconds=seconds,features=world.stats['feature_categories'])
    after = worlds['after']
    intersections = 0
    for model in after.model_instances:
        xz = model.template.orientations[model.rotation][1]+np.asarray(model.anchor)[[0,2]]
        category = next(f.category for f in after.pack.feature_defs if f.id==model.id[0])
        intersections += int(np.any(blocked(after.pack,category,xz[:,0],xz[:,1])))
    report['models_in_clearance'] = intersections
    report['height_unchanged'] = bool(np.array_equal(worlds['before'].heights,after.heights))
    report['water_unchanged'] = bool(np.array_equal(worlds['before'].water_levels,after.water_levels))
    (out/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    (out/'terrain_spec.json').write_text(spec.to_json(),encoding='utf8')
    (out/'place_in_editor.py').write_text(EDITOR,encoding='utf8')
    (out/'README.md').write_text('植被与留空区域对照\n\n查看before.png、after.png和两个子目录。'
        '\n在UE中运行place_in_editor.py，以PCG放入独立的MaskStudy组；不保存关卡。'
        '\n移动输出目录后脚本会重新绑定图片路径。\n',encoding='utf8')
    print(json.dumps({k:v if not isinstance(v,dict) else {'seconds':v['seconds']} for k,v in report.items()},ensure_ascii=False))


if __name__=='__main__':
    main()
