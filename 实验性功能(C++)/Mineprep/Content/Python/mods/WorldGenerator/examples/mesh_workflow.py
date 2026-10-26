"""Capture actual editor input once, then reproduce the two demos offline.

UE: capture_in_editor(new_input_directory)
Offline: python mesh_workflow.py --inputs INPUT --output NEW_OUTPUT
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
from time import perf_counter
import tracemalloc

PYTHON_DIR = Path(__file__).resolve().parents[3]
PROJECT_DIR = Path(__file__).resolve().parents[7]
sys.path[:0] = [str(PYTHON_DIR), str(PROJECT_DIR/'Intermediate/PipInstall/Lib/site-packages')]

import numpy as np
from mods.WorldGenerator import api
from mods.WorldGenerator.adapters import mesh_input
from mods.WorldGenerator.core.voxel import MeshData


def capture_in_editor(output):
    """Read assets/templates, export derived inputs. Never place or save actors."""
    import unreal
    import mineprep
    from mods.VanillaMobLoader import geometry
    from mods.VanillaMobLoader.assets import CACHE
    from mods.WorldGenerator.adapters.mesh_unreal import read_unreal
    from mods.WorldGenerator.adapters.block_colors import assets_dir

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    bee = read_unreal('/Game/mc/mob/bee/SKM_bee')
    np.savez_compressed(output/'bee.npz', vertices=bee.vertices, triangles=bee.triangles,
                        uv=bee.uv, material_ids=bee.material_ids, colors=bee.colors,
                        image=bee.materials[0]['image'])
    texture = unreal.load_asset('/Game/Mineprep/材质/皮肤/tex/steve_bare_bones')
    shutil.copyfile(mineprep.export_tex_cache(texture, str(output)), output/'steve.png')
    shutil.copyfile(assets_dir()/'textures/entity/minecart/minecart.png', output/'minecart.png')
    catalog = json.loads((CACHE/'resources/catalog.json').read_text(encoding='utf-8'))

    def boxes(key, seated=False):
        model = json.loads(catalog['models'][key]['model'])
        result = []
        for part in model['models']:
            # These two upstream recipes have root-level rigid parts. Reuse their
            # face UV helper and matrix convention, not another CEM parser.
            assert not part.get('submodels')
            pivot = -np.asarray(part.get('translate',(0,0,0)),float)
            angles = list(part.get('rotate',(0,0,0)))
            name = part['part']
            if seated:
                if 'leg' in name or 'pants' in name:
                    angles[0] = 90
                elif 'arm' in name or 'sleeve' in name:
                    angles[0] = 65
                elif name in ('head','headwear'):
                    angles[1] = -10
            matrix = np.array(geometry.local_matrix(pivot, angles))
            matrix[:3,3] -= matrix[:3,:3]@pivot
            if seated:
                matrix[:3,3] += (0,-5,4)
            for box in part.get('boxes',[]):
                coords = box['coordinates']
                result.append(dict(origin=coords[:3],size=coords[3:],
                    faces=geometry.uv_rects(box,coords[3:],'u' in part.get('mirrorTexture','')),
                    inflate=box.get('sizeAdd',0),transform=matrix.tolist()))
        return dict(boxes=result,texture_size=model['textureSize'])

    recipes = dict(steve=boxes('player',True), cart=boxes('minecart'))
    (output/'boxes.json').write_text(json.dumps(recipes,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'sources.json').write_text(json.dumps(dict(
        bee='/Game/mc/mob/bee/SKM_bee',skin=texture.get_path_name(),
        catalog_version=catalog.get('version'),pose='example-authored rigid joint matrices',
        evidence='asset/source capture only; no level rendering'),ensure_ascii=False,indent=2),encoding='utf-8')
    return str(output)


def combine(first, second):
    assert first.palette == second.palette
    xyz = np.r_[first.xyz,second.xyz]
    ids = np.r_[first.types,second.types]
    _, at = np.unique(xyz,axis=0,return_index=True)
    p = xyz[at]
    lo = p.min(axis=0)
    return api.Structure('SteveInMinecart',tuple(lo),tuple(p.max(axis=0)-lo+1),
                         first.palette,p,ids[at])


EDITOR_SCRIPT = '''from pathlib import Path
import uuid
from mods.WorldGenerator import api

root = Path(__file__).parent
bee = api.Structure.load(root/'bee.json')
statue = api.Structure.load(root/'steve_in_minecart.json')
scene = api.compose(None,statue.at((0,0,0)),bee.at((140,0,0)))
name = 'MeshStatues_' + uuid.uuid4().hex[:8]

def ready(job):
    if job.state == 'completed':
        global place_job
        place_job = api.place(job.result,name=name,location=(0,0,0))
    else:
        print(job.status())

prepare_job = api.prepare(scene,name=name,on_done=ready)
'''


def deliver(inputs, output):
    inputs,output = Path(inputs),Path(output)
    output.mkdir(parents=True,exist_ok=False)
    with np.load(inputs/'bee.npz',allow_pickle=False) as data:
        bee = MeshData(data['vertices'],data['triangles'],data['uv'],data['material_ids'],
                       [dict(image=data['image'])],data['colors'])
    report = {}
    tracemalloc.start()
    start=perf_counter()
    statue = mesh_input.mesh_structure(bee,resolution=128,name='Bee',_stats=report)
    report['total']=perf_counter()-start
    report['peak_traced_bytes']=tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    recipes = json.loads((inputs/'boxes.json').read_text(encoding='utf-8'))
    steve = api.uv_structure(inputs/'steve.png',**recipes['steve'],scale=4,name='SeatedSteve')
    cart = api.uv_structure(inputs/'minecart.png',**recipes['cart'],scale=4,name='Minecart')
    assembly = combine(steve,cart)
    checks = {}
    for key, model in (('bee',statue),('steve',steve),('minecart',cart),('steve_in_minecart',assembly)):
        model.save(output/f'{key}.json')
        assert api.Structure.load(output/f'{key}.json').key == model.key
        checks[key] = api.check(model)
        api.snapshot(model,output/f'{key}.png')
    # Same existing diagnostic renderer for source sampled colours and block colours.
    from mods.WorldGenerator.core.voxel import rasterize
    from mods.WorldGenerator.adapters.build_preview import orthographic
    from mods.WorldGenerator.adapters.preview import write_png
    from mods.WorldGenerator.adapters.block_colors import color_table
    xyz,rgb,_,_=rasterize(mesh_input.validated(bee),scale=128/np.ptp(bee.vertices,axis=0).max(),
                          normalize=True,alpha_cutoff=.5,max_cells=4_000_000)
    mapped=color_table([n for n,_ in statue.palette])[statue.types]
    source_view=orthographic(xyz,rgb,'front',320)
    block_view=orthographic(statue.xyz,mapped,'front',320)
    write_png(output/'source_vs_blocks.png',np.concatenate((source_view,block_view),axis=1))
    (output/'place_in_editor.py').write_text(EDITOR_SCRIPT,encoding='utf-8')
    report.update(checks=checks,cells=statue.count,used_blocks=len(np.unique(statue.types)),
                  size=statue.size,evidence='offline diagnostics, not UE renders')
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'README.md').write_text(
        '# Textured mesh statues\n\nAll PNGs are offline diagnostics, not UE renders.\n'
        'Frozen JSONs can be loaded and edited with the existing API.\n'
        'Source inputs come from the actual bee asset and Steve TextureSource;\n'
        'boxes.json records example-authored joint matrices and the upstream minecart.\n\n'
        'Run place_in_editor.py in UE Python to add a uniquely named scene. It does not save the level.\n'
        'Front comparison: source sampled RGB on the left, chosen Minecraft blocks on the right.\n',encoding='utf-8')
    assert all(c['ok'] for c in checks.values())
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(deliver(args.inputs,args.output),ensure_ascii=True))
