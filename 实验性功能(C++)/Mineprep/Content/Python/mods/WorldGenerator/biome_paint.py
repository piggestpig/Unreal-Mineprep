"""Categorical strokes reuse Canvas history; files retain stable biome IDs."""
from itertools import chain, product
from pathlib import Path
import numpy as np

from .core.biome_map import MARKERS, WATER_BIOMES, palette as default_palette, capture, bind
from .painting import Canvas, Brush
from .storage import write_json


class BiomeCanvas(Canvas):
    categorical = True
    extension = '.png'

    def __init__(self, pack, region, values=None, *, palette=None):
        self.biomes = tuple(b.id for b in pack.biomes)
        self.land = {b.id for b in pack.biomes if b.id not in WATER_BIOMES}
        self.colors = np.array([(0,0,0,0), *((*b.color,150) for b in pack.biomes)],np.uint8)
        self.palette = dict(default_palette(pack) if palette is None else palette)
        if set(self.palette.values())-self.land:
            raise ValueError('biome paint palette requires this pack\'s land biome IDs')
        if values is not None:
            values = np.asarray(values)
            if values.dtype.kind not in 'iu' or np.any(values < 0) or np.any(values > len(self.biomes)):
                raise ValueError('biome canvas requires integer class IDs in its biome table')
        super().__init__('biome_map',region,values)

    def target(self, ident):
        if not ident:
            return 0  # transparent input: use natural/preset selection
        if ident not in self.land:
            raise ValueError(f'biome brush requires a land biome: {ident}')
        if ident not in self.palette.values():
            candidates = chain(MARKERS,
                ('#'+''.join(f'{c:02x}' for c in rgb) for rgb in product((0,85,170,255),repeat=3)),
                (f'#{n:06x}' for n in range(1,0xffffff)))
            color = next(c for c in candidates if c not in self.palette and c not in ('#000000','#ffffff'))
            self.palette[color] = ident
        return self.biomes.index(ident)+1

    def begin(self, point, brush):
        value = int(brush.value)
        if value != brush.value or not 0 <= value <= len(self.biomes):
            raise ValueError('biome brush requires a class from its biome table')
        if value:
            self.target(self.biomes[value-1])
        # Categories have hard coverage; numeric brush softness/strength stay intact.
        super().begin(point,Brush(value,brush.diameter,1.,1.))

    def rgba(self, box):
        x,z,ex,ez = box
        return self.colors[self.values[z:ez,x:ex]]

    def file_values(self):
        colors = np.zeros((len(self.biomes)+1,4),np.uint8)
        indices = {ident:i+1 for i,ident in enumerate(self.biomes)}
        for color,ident in reversed(tuple(self.palette.items())):
            index = indices[ident]
            colors[index] = [*(int(color[i:i+2],16) for i in (5,3,1)),255]  # cv2 BGRA
        return colors[self.values]

    def write(self, path):
        super().write(path)
        write_json(Path(path).with_suffix('.palette.json'),self.palette)


def load_biome_canvas(pack, config):
    source = capture(config)
    image = bind(pack,config,source).biome_map
    source.checked()
    # Classification runs once on import; subsequent strokes edit integer labels.
    return BiomeCanvas(pack,config.region,image.values+1,palette=dict(config.palette))
