import math
import numpy as np
import mineprep
from mineprep import bilingual


def reshape(arr, dim=2):
    # 计算尽可能接近的各轴长度
    l, shape = len(arr), []
    for i in range(dim, 0, -1):
        side = math.ceil(l ** (1 / i))
        shape.append(side)
        l = math.ceil(l / side)

    # 用-1填充末尾并重塑形状
    padded = np.pad(arr, (0, np.prod(shape) - len(arr)), constant_values=-1)
    return padded.reshape(shape)


def coords_dict(arr, step=100, offset=(0, 0, 0)):
    arr = np.asarray(arr)
    result = {}

    for idx, val in np.ndenumerate(arr):
        # 将坐标补齐为3维，并乘以步长
        coord = tuple(idx[i] * step + offset[i] if i < len(idx) else offset[i] for i in range(3))
        result[coord] = val

    return result


def placeholder(*args, **kwargs):
    pass


def spawn_oak(status=placeholder, loc=(0, 0, 0), step=800):
    h = 5
    b = mineprep.Blocks(name='oak')
    for y in range(h):
        b.add('oak_log', 0, y, 0, axis='y')
    for y, r in ((h - 2, 2), (h - 1, 2), (h, 1), (h + 1, 1)):
        for x in range(-r, r + 1):
            for z in range(-r, r + 1):
                if x == 0 and z == 0 and y < h:
                    continue
                if abs(x) == r and abs(z) == r:
                    continue
                b.add('oak_leaves', x, y, z)

    modes = (
        (0, '实例化网格体', 'ISM'),
        (1, 'PCG', 'PCG'),
        (2, '粒子', 'Niagara'),
    )
    for i, (gpu, zh, en) in enumerate(modes):
        status(bilingual(f'正在生成{zh}橡树', f'Spawning {en} oak'))
        pos = (loc[0] + i * step, loc[1], loc[2])
        out = mineprep.spawn_structure(b, loc=pos, gpu=gpu, name=f'oak_{en.lower()}')
        if not out:
            raise RuntimeError(str(bilingual(f'{zh}橡树生成失败', f'{en} oak spawn failed')))
        yield 0.5


def mob_spawner(status=placeholder, step=250, offset=(0, 0, 1000)):
    options = mineprep.panel('生成器子面板.放置生物选项').get(list)
    options = coords_dict(reshape(options), step=step, offset=offset)
    for pos, name in options.items():
        if name == -1 or name == '-1':
            continue
        status(bilingual(f'正在生成 {name}', f'Spawning {name}'))
        mineprep.spawn_mob(name, pos)
        yield


TESTS = [
    {
        'label': mineprep.bilingual('生成橡树', 'Spawn oak'),
        'fn': spawn_oak,
    },
    {
        'label': mineprep.bilingual('生成生物', 'Spawn mobs'),
        'fn': mob_spawner,
    },
]
