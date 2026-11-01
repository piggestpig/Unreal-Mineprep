"""Paint discrete forest/desert regions and erase a corridor on the same hills."""
import argparse
import json
import os
from pathlib import Path
import sys

PYTHON_DIR = Path(__file__).resolve().parents[3]
PROJECT_DIR = Path(__file__).resolve().parents[7]
sys.path[:0] = [str(PYTHON_DIR),str(PROJECT_DIR/'Intermediate/PipInstall/Lib/site-packages')]
os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR','1')
import cv2
import numpy as np
from mods.WorldGenerator import api
from mods.WorldGenerator.biome_paint import BiomeCanvas
from mods.WorldGenerator.painting import Brush


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    folder = args.output.resolve()
    folder.mkdir(parents=True,exist_ok=False)
    region = api.Region(-64,-96,128,128)
    z,x = np.mgrid[:128,:128]
    height = (78+7*np.sin(x/29.)+5*np.cos(z/31.)).astype(np.float32)
    if not cv2.imwrite(str(folder/'height.exr'),height):
        raise OSError('cannot write height image')
    doc = BiomeCanvas(api.pack(),region)
    for ident,a,b,width in (('forest',(-44,-76),(-28,12),48),('desert',(16,-76),(34,12),42)):
        doc.begin(a,Brush(doc.target(ident),width))
        doc.stroke.segment(a,b);doc.finish()
    before_erase = doc.values.copy()
    doc.begin((-44,-43),Brush(0,12))
    doc.stroke.segment((-44,-43),(38,-20));doc.finish()
    painted = doc.values.copy()
    doc.history();np.testing.assert_array_equal(doc.values,before_erase)
    doc.history(True);np.testing.assert_array_equal(doc.values,painted)
    doc.path = str(folder/'painted.png')
    path = doc.save(folder)
    base = api.spec(region=region,params={'water.generate':False,'climate.single_biome':'grassland'})
    base = api.with_heightmap(base,folder/'height.exr')
    natural = api.generate(base)
    spec = api.with_biome_map(base,path,palette=doc.palette,tolerance=0)
    world = api.generate(spec)
    np.testing.assert_array_equal(world.heights,natural.heights)
    np.testing.assert_array_equal(world.biome_ids,np.where(doc.values>0,doc.values-1,natural.biome_ids))
    api.snapshot(natural,folder/'natural.png')
    api.snapshot(world,folder/'painted_world.png')
    overlay = doc.rgba((0,0,128,128))
    if not cv2.imwrite(str(folder/'paint_overlay.png'),overlay[...,[2,1,0,3]]):
        raise OSError('cannot write paint overlay')
    (folder/'world_spec.json').write_text(spec.to_json(),encoding='utf-8')
    (folder/'stats.json').write_text(json.dumps(world.stats,indent=2,default=str),encoding='utf-8')
    report = dict(undo_redo_equal=True,height_unchanged=True,
                  painted_pixels=int(np.count_nonzero(doc.values)),biomes=world.biome_fractions(),
                  models=len(world.model_instances))
    (folder/'painting.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(folder)
    print(json.dumps(report))


if __name__=='__main__':
    main()
