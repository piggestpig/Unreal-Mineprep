"""结构文件的数值化方块容器与邻格查询加速（不依赖 Unreal）。"""
import math
import numpy as np


def decode_varints(raw):
    """将 Sponge schematic 的 VarInt 字节流批量解码为 uint32 调色板索引数组。"""
    b = np.frombuffer(raw, np.uint8)
    high = np.flatnonzero(b >= 128)
    if not len(high):
        return b.astype(np.uint32)
    if high[-1] == len(b)-1:
        raise ValueError('Schematic VarInt is truncated')
    if np.all(b[high+1] < 128):
        values = b[b < 128].astype(np.uint32)
        values[high-np.arange(len(high))] = ((b[high].astype(np.uint32) & 127)
                                           | (b[high+1].astype(np.uint32) << 7))
        return values
    ends = np.flatnonzero(b < 128)
    starts = np.r_[0, ends[:-1]+1]
    lengths = ends-starts+1
    if np.any(lengths > 5) or np.any((lengths == 5) & (b[ends] > 15)):
        raise ValueError('Schematic palette ID exceeds uint32')
    values = np.zeros(len(ends), np.uint32)
    for shift in range(int(lengths.max())):
        active = lengths > shift
        values[active] |= (b[starts[active]+shift].astype(np.uint32) & 127) << (7*shift)
    return values


class CellData:
    """用稀疏坐标数组与调色板索引存储非空气方块，加速邻格查询与内部剔除。

    palette[0] 固定为空气，有效方块的调色板索引从 1 开始。
    包围盒在 2 GiB 限制内时构建三维网格索引，超大跨度结构则回退为排序二分查找。
    """
    def __init__(self, xyz=(), types=(), palette=(), source_size=None):
        self.palette = [{'name':'air', 'properties':{}}, *palette]
        self.source_size = source_size
        p = np.asarray(xyz, np.int64).reshape(-1, 3)
        t = np.asarray(types, np.int64)
        valid = (t >= 0) & (t < len(palette))
        keep = np.zeros(len(t), bool)
        nonair = np.array([c['name'] != 'air' for c in palette], bool)
        keep[valid] = nonair[t[valid]]
        self.xyz, self.types = p[keep], (t[keep]+1).astype(np.uint32)
        self._ids = None
        self._index = None

    @classmethod
    def linear(cls, values, size, palette, *, order='yzx', source_size=None):
        """从一维数组按尺寸展开非空气方块的坐标（默认按 schematic 的 YZX 顺序）。"""
        values = np.asarray(values).reshape(-1)[:math.prod(size)]
        if not len(values):
            return cls(palette=palette, source_size=source_size)
        valid = (values >= 0) & (values < len(palette))
        nonair = np.array([c['name'] != 'air' for c in palette], bool)
        keep = np.zeros(len(values), bool)
        keep[valid] = nonair[values[valid]]
        linear = np.flatnonzero(keep)
        if not len(linear):
            return cls(palette=palette, source_size=source_size)
        xsize, ysize, zsize = size
        if order == 'yzx':
            y, rem = np.divmod(linear, xsize*zsize)
            z, x = np.divmod(rem, xsize)
        else:
            x, rem = np.divmod(linear, ysize*zsize)
            y, z = np.divmod(rem, zsize)
        return cls(np.column_stack((x,y,z)), values[linear], palette, source_size)

    @classmethod
    def from_cells(cls, cells):
        palette, ids, types = [], {}, []
        for cell in cells.values():
            key = cell['name'], frozenset((cell.get('properties') or {}).items())
            if key not in ids:
                ids[key] = len(palette)
                palette.append(cell)
            types.append(ids[key])
        return cls(list(cells), types, palette)

    def __len__(self):
        return len(self.xyz)

    def __iter__(self):
        return (tuple(map(int, p)) for p in self.xyz)

    def items(self):
        # 分批转为 Python 元组，避免一次性分配超大列表
        for start in range(0,len(self),65536):
            points = self.xyz[start:start+65536].tolist()
            for p,t in zip(points,self.types[start:start+65536]):
                yield tuple(p), self.palette[t]

    def to_cells(self):
        return {p:{'name':c['name'], 'properties':dict(c.get('properties') or {})}
                for p,c in self.items()}

    def bounds(self):
        if not len(self):
            return None
        return self.xyz.min(axis=0), self.xyz.max(axis=0)+1

    def positions(self, predicate):
        flags = np.array([predicate(c) for c in self.palette], bool)
        return map(tuple, self.xyz[flags[self.types]])

    def _lookup(self, points):
        """查询坐标对应的行号（从 1 开始），未找到返回 0。"""
        points = np.asarray(points, np.int64).reshape(-1,3)
        result = np.zeros(len(points), np.uint32)
        if not len(self):
            return result
        if self._index is None:
            lo, hi = self.bounds()
            shape = hi-lo+2
            if math.prod(map(int,shape)) <= 536_870_912:  # 2 GiB of uint32 rows
                grid = np.zeros(tuple(shape), np.uint32)
                q = self.xyz-lo+1
                grid[tuple(q.T)] = np.arange(1,len(self)+1,dtype=np.uint32)
                self._index = grid, lo-1
            else:
                order = np.lexsort(self.xyz[:,::-1].T)
                keys = self.xyz[order].view([('x',np.int64),('y',np.int64),('z',np.int64)]).ravel()
                self._index = keys, order
        index, offset = self._index
        if index.ndim == 3:
            q = points-offset
            inside = np.all((q >= 0) & (q < index.shape),axis=1)
            result[inside] = index[tuple(q[inside].T)]
        else:
            keys = np.ascontiguousarray(points).view(index.dtype).ravel()
            at = np.minimum(np.searchsorted(index,keys),len(index)-1)
            found = index[at] == keys
            result[found] = offset[at[found]]+1
        return result

    def get(self, point):
        row = int(self._lookup([point])[0])
        return self.palette[self.types[row-1]] if row else None

    __getitem__ = get

    def __setitem__(self, point, cell):
        if self._ids is None:
            self._ids = {(c['name'],frozenset((c.get('properties') or {}).items())):i
                         for i,c in enumerate(self.palette)}
        key = cell['name'], frozenset((cell.get('properties') or {}).items())
        if key not in self._ids:
            self._ids[key] = len(self.palette)
            self.palette.append(cell)
        row = int(self._lookup([point])[0])-1
        self.types[row] = self._ids[key]

    def cull(self, mode, facts):
        if not len(self) or mode not in (1,2,3):
            return self
        full, opaque = np.zeros(len(self.palette),bool), np.zeros(len(self.palette),bool)
        water = np.array([c['name'] in ('water','flowing_water') for c in self.palette],bool)
        names = {}
        name_ids = []
        for i,c in enumerate(self.palette):
            name = c['name']
            name_ids.append(names.setdefault(name,len(names)))
            if name != 'air' and not water[i]:
                full[i] = facts.full(name,c.get('properties') or {})
                if mode != 1 and full[i]:
                    opaque[i] = facts.opaque(name,c.get('properties') or {})
        name_ids = np.asarray(name_ids,np.uint32)
        t = self.types
        transparent = full & ~opaque
        hidden = (full | water)[t]
        center_names = name_ids[t]
        center_water, center_opaque, center_transparent = water[t], opaque[t], transparent[t]
        if self._index is None:
            self._lookup(self.xyz[:1])
        index, origin = self._index
        local = (self.xyz-origin).T if index.ndim == 3 else None
        for offset in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
            if local is None:
                rows = self._lookup(self.xyz+offset)
            else:
                # 网格四周留有 1 格边距，六个方向的邻格查询均在数组范围内
                key = [local[i]+d if d else local[i] for i,d in enumerate(offset)]
                rows = index[tuple(key)]
            other = np.zeros(len(self),np.uint32)
            found = rows != 0
            other[found] = t[rows[found]-1]
            same = center_names == name_ids[other]
            if mode == 1:
                hidden &= (full | water)[other] & same
            else:
                hidden &= ((center_water & water[other]) | (center_opaque & opaque[other])
                           | (center_transparent & (opaque[other] | (transparent[other] & same))))
        keep = ~hidden
        if mode == 3 and np.any(keep):
            p = self.xyz[keep]
            lo, hi = p.min(axis=0), p.max(axis=0)
            keep &= ((self.xyz[:,1] != lo[1]) & (self.xyz[:,0] != lo[0]) & (self.xyz[:,0] != hi[0])
                     & (self.xyz[:,2] != lo[2]) & (self.xyz[:,2] != hi[2]))
        self.xyz, self.types = self.xyz[keep], t[keep]
        self._index = None
        return self
