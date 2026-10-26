"""将打包后的结构实例数据编码并写出为 BPT/BRT EXR 贴图与映射表（不依赖 Unreal）。"""
from pathlib import Path
import json
import numpy as np
from mc_math import validate_packed

ENCODING_VERSION = 'bpt-brt-f32-3'


def encode_arrays(payloads, max_side=16384):
    """将各模型的 pos/rot/scale 实例数组编码为正方形 BPT（位置与类型 ID）和 BRT（缩放与旋转）像素矩阵。"""
    # 先校验所有模型数据，通过后再分配纹理内存
    payloads = {name: validate_packed(p) for name, p in payloads.items()}
    if len(payloads) > 2**24:
        raise ValueError('mesh type IDs exceed float32 texture integer precision')
    count = sum(len(p['pos']) for p in payloads.values())
    if count <= 0:
        raise ValueError('structure contains no instances')
    side = int(np.ceil(np.sqrt(count)))
    if side > max_side:
        raise ValueError(f'texture {side}×{side} exceeds max_side={max_side}')
    bpt = np.zeros((side*side, 4), np.float32)
    bpt[:, 3] = -1
    brt = np.ones((side*side, 4), np.float32)
    brt[:, 3] = 0
    cursor = 0
    for type_id, payload in enumerate(payloads.values()):
        pos, rot, scale = payload['pos'], payload['rot'], payload['scale']
        n = len(pos)
        dest = slice(cursor, cursor+n)
        bpt[dest, :3], bpt[dest, 3] = pos[:, ::-1]/100, type_id
        brt[dest, :3], brt[dest, 3] = scale[:, ::-1], rot
        cursor += n
    return bpt.reshape(side, side, 4), brt.reshape(side, side, 4)


def write_structure_textures(payloads, directory, name='structure', fp32=True,
                             max_side=16384):
    """将实例数据写成 {name}_BPT.exr、{name}_BRT.exr 和 {name}_names.json。"""
    import cv2
    if not name or Path(name).name != name or '/' in name or '\\' in name:
        raise ValueError('name must be a filename stem')
    bpt, brt = encode_arrays(payloads, max_side)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    options = [cv2.IMWRITE_EXR_TYPE,
               cv2.IMWRITE_EXR_TYPE_FLOAT if fp32 else cv2.IMWRITE_EXR_TYPE_HALF]
    paths = {'side': int(bpt.shape[0])}
    for suffix, pixels in (('BPT', bpt), ('BRT', brt)):
        ok, encoded = cv2.imencode('.exr', pixels, options)
        if not ok:
            raise RuntimeError(f'{suffix} EXR encoding failed')
        path = directory / f'{name}_{suffix}.exr'
        path.write_bytes(encoded.tobytes())
        paths[suffix] = str(path)
    paths['mapping'] = {i: n for i, n in enumerate(payloads)}
    (directory / f'{name}_names.json').write_text(
        json.dumps(paths['mapping'], ensure_ascii=False, indent=2), encoding='utf-8')
    return paths
