import unreal
import mineprep
import math
import numpy as np

"""
import automation_test
automation_test.spawner(step=300, offset=(0,0,0))
"""

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


# 转换为 {(0,0,0) : arr[0]} 这样的字典
def coords_dict(arr, step=100, offset=(0,0,0)):
    arr = np.asarray(arr)
    result = {}
    
    for idx, val in np.ndenumerate(arr):
        # 将坐标补齐为3维，并乘以步长
        coord = tuple(idx[i] * step + offset[i] if i < len(idx) else offset[i] for i in range(3))
        result[coord] = val

    return result


@mineprep.asynctask
def spawner(step=200, offset=(0,0,0)):
    options = mineprep.panel('生成器子面板.放置生物选项').get(list)
    options = coords_dict(reshape(options), step=step, offset=offset)
    for pos, name in options.items():
        if name == -1 or name == '-1':
            continue
        print(f'生成 {name} 于 {pos}')
        mineprep.spawn_mob(name, pos)
        yield