"""Biome colour-map control on the same hills. Output must be a new directory."""
import argparse
import json
import os
from pathlib import Path
import sys

PYTHON_DIR = Path(__file__).resolve().parents[3]
PROJECT_DIR = Path(__file__).resolve().parents[7]
sys.path[:0] = [str(PYTHON_DIR), str(PROJECT_DIR/'Intermediate/PipInstall/Lib/site-packages')]
os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR', '1')

import cv2
import numpy as np
from mods.WorldGenerator import api

EDITOR = '''from pathlib import Path
from mods.WorldGenerator import api
folder = Path(__file__).resolve().parent
spec = api.WorldSpec.from_json((folder/'terrain_spec.json').read_text(encoding='utf-8'))
spec = api.with_heightmap(spec,folder/'height.exr',region=spec.heightmap.region)
spec = api.with_biome_map(spec,folder/'biomes.png',palette=dict(spec.biome_map.palette),region=spec.biome_map.region,tolerance=spec.biome_map.tolerance)
def ready(job):
    if job.state == 'completed':
        api.place(job.result,name='BiomeMapStudy')
job = api.prepare(spec,backend='pcg',on_done=ready,name='BiomeMapStudy')
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, choices=(128,256), default=128)
    args = parser.parse_args()
    folder = args.output.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    n = args.size
    z, x = np.mgrid[:n,:n]
    height = (78 + 7*np.sin(x/29.) + 5*np.cos(z/31.)).astype(np.float32)
    if not cv2.imwrite(str(folder/'height.exr'),height):
        raise OSError('cannot write height image')
    image = np.zeros((n,n,4),np.uint8)
    left = (x > 8) & (x < n*.48 + 8*np.sin(z/20.)) & (z > 8) & (z < n-8)
    right = (x > n*.52 + 8*np.sin(z/20.)) & (x < n-8) & (z > 8) & (z < n-8)
    palette = api.describe()['biome_map']['palette']
    palette = {color: ident for color,ident in palette.items() if ident in ('forest','desert')}
    for mask, ident in ((left,'forest'),(right,'desert')):
        color = next(c for c,b in palette.items() if b == ident)
        rgb = [int(color[i:i+2],16) for i in (1,3,5)]
        image[mask] = [*rgb[::-1],255]  # cv2 writes BGRA.
    if not cv2.imwrite(str(folder/'biomes.png'),image):
        raise OSError('cannot write biome image')
    noisy = image.copy()
    noise = np.random.default_rng(42).integers(-16,17,image[...,:3].shape,dtype=np.int16)
    noisy[...,:3] = np.clip(image[...,:3].astype(np.int16)+noise,0,255).astype(np.uint8)
    if not cv2.imwrite(str(folder/'biomes_noisy.png'),noisy):
        raise OSError('cannot write noisy biome image')
    spec = api.spec(region=(-64,-96,n,n),params={
        'water.generate':False, 'climate.single_biome':'grassland'})
    spec = api.with_heightmap(spec,folder/'height.exr')
    natural = api.generate(spec)
    spec = api.with_biome_map(spec,folder/'biomes.png',palette=palette)
    world = api.generate(spec)
    noisy_spec = api.with_biome_map(spec,folder/'biomes_noisy.png',palette=palette)
    tolerant = api.generate(noisy_spec)
    np.testing.assert_array_equal(world.biome_ids,tolerant.biome_ids)
    np.testing.assert_array_equal(world.columns,tolerant.columns)
    strict = api.generate(api.with_biome_map(noisy_spec,folder/'biomes_noisy.png',palette=palette,tolerance=0))
    api.snapshot(natural,folder/'natural.png')
    api.snapshot(world,folder/'mapped.png')
    api.snapshot(tolerant,folder/'tolerant.png')
    api.snapshot(strict,folder/'strict.png')
    (folder/'palette.json').write_text(json.dumps(palette,indent=2)+'\n',encoding='utf-8')
    (folder/'terrain_spec.json').write_text(spec.to_json(),encoding='utf-8')
    (folder/'noisy_spec.json').write_text(noisy_spec.to_json(),encoding='utf-8')
    (folder/'place_in_editor.py').write_text(EDITOR,encoding='utf-8')
    (folder/'stats.json').write_text(json.dumps(world.stats,indent=2,default=str),encoding='utf-8')
    recognition = {name: value.stats['biome_map'] for name,value in
                   (('exact_source',world),('noisy_tolerance32',tolerant),('noisy_tolerance0',strict))}
    (folder/'recognition.json').write_text(json.dumps(recognition,indent=2),encoding='utf-8')
    print(folder)
    print(json.dumps(world.stats['biome_map']))


if __name__ == '__main__':
    main()
