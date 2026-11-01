"""World-space numeric brushes and bounded stroke history; no editor dependency."""
from dataclasses import dataclass
import math
import os
from pathlib import Path
import uuid

import numpy as np
from .core.heightmap import MAX_PIXELS

TILE = 64
HISTORY_BYTES = 64 * 1024 ** 2
KINDS = ('heightmap', 'vegetation', 'clearance', 'biome_map')
COLORS = dict(warm=(240,150,45),cold=(45,150,245),vegetation=(45,190,95),clearance=(225,75,175))


def union_box(a, b):
    if a is None:return b
    if b is None:return a
    return min(a[0],b[0]),min(a[1],b[1]),max(a[2],b[2]),max(a[3],b[3])


def canvas_shape(region):
    scale = min(1., 2048 / max(region.width, region.depth))
    return max(1, round(region.depth * scale)), max(1, round(region.width * scale))


def brush_values(values=None):
    result = dict(Diameter=32., Hardness=.5, Strength=1., Visible=True,
                  heightmap=16., vegetation=0., clearance=1., biome_map='forest')
    values = values or {}
    if not isinstance(values, dict) or set(values)-set(result):
        raise ValueError('invalid paint preferences')
    result.update(values)
    for key in result.keys()-{'Visible','biome_map'}:
        v = result[key]
        if isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v):
            raise ValueError(f'{key}: expected a finite brush value')
    if (result['Diameter'] <= 0 or not 0 <= result['Hardness'] <= 1
            or not 0 <= result['Strength'] <= 1 or type(result['Visible']) is not bool
            or not isinstance(result['biome_map'],str)
            or any(not 0 <= result[k] <= 1 for k in ('vegetation','clearance'))):
        raise ValueError('brush size/strength/mask value out of range')
    return result


@dataclass(frozen=True)
class Brush:
    value: float
    diameter: float = 32.
    hardness: float = .5
    strength: float = 1.

    def __post_init__(self):
        if (not all(math.isfinite(v) for v in (self.value,self.diameter,self.hardness,self.strength))
                or abs(self.value)>np.finfo(np.float32).max
                or self.diameter <= 0 or not 0 <= self.hardness <= 1 or not 0 <= self.strength <= 1):
            raise ValueError('invalid brush')


@dataclass(frozen=True)
class PreviewCommand:
    operation: str
    box: tuple
    brush: Brush
    a: tuple = (0.,0.)  # world units relative to the canvas origin
    b: tuple = (0.,0.)


class Canvas:
    categorical = False
    extension = '.exr'

    def __init__(self, kind, region, values=None, *, mode='add'):
        self.kind, self.region, self.mode = kind, region, mode
        if kind not in KINDS:
            raise ValueError('unknown paint layer')
        if values is None:
            values = np.full(canvas_shape(region),1. if kind=='vegetation' else 0.,np.float32)
        self.values = np.array(values,dtype=np.int32 if self.categorical else np.float32,copy=True,order='C')
        if (self.values.ndim != 2 or not self.values.size or self.values.size > MAX_PIXELS
                or not np.isfinite(self.values).all()
                or (not self.categorical and kind!='heightmap' and np.any((self.values<0)|(self.values>1)))):
            raise ValueError('invalid paint image')
        self.undo_stack, self.redo_stack = [],[]
        self.stroke = None
        self.dirty = (0,0,self.values.shape[1],self.values.shape[0])
        self.path = ''
        self.unsaved = False
        self.preview_commands = []
        self.preview_reset = True

    def mark(self, box):
        self.dirty = union_box(self.dirty,box)

    def invalidate_preview(self):
        self.preview_commands.clear()
        self.preview_reset = True

    def preview_state(self):
        """One-time RG upload: frozen base and this stroke's maximum coverage."""
        state = np.zeros((*self.values.shape,2),np.float32)
        state[...,0] = self.values
        if self.stroke is not None:
            for (x,z),(before,cover) in self.stroke.tiles.items():
                h,w = before.shape
                state[z:z+h,x:x+w,0] = before
                state[z:z+h,x:x+w,1] = cover
        return state

    def _preview_end(self, operation):
        if not self.preview_reset and self.stroke.bounds is not None:
            self.preview_commands.append(PreviewCommand(operation,self.stroke.bounds,self.stroke.brush))

    def begin(self, point, brush):
        if not self.categorical and self.kind!='heightmap' and not 0 <= brush.value <= 1:
            raise ValueError('mask brush value must be in [0,1]')
        self.stroke = Stroke(self,brush)
        self.stroke.segment(point,point)

    def cancel(self):
        if self.stroke is not None:
            self._preview_end('cancel')
            for (x,z),(before,_) in self.stroke.tiles.items():
                h,w = before.shape
                self.values[z:z+h,x:x+w] = before
                self.mark((x,z,x+w,z+h))
            self.stroke = None

    def finish(self):
        self._preview_end('commit')
        changes = []
        for (x,z),(before,_) in self.stroke.tiles.items():
            h,w = before.shape
            after = self.values[z:z+h,x:x+w]
            if not np.array_equal(before,after):
                changes.append((x,z,before,after.copy()))
        self.stroke = None
        if not changes:
            return False
        self.undo_stack.append(changes)
        self.redo_stack.clear()
        total = sum(a.nbytes+b.nbytes for entry in self.undo_stack for _,_,a,b in entry)
        while total > HISTORY_BYTES and len(self.undo_stack)>1:
            total -= sum(a.nbytes+b.nbytes for _,_,a,b in self.undo_stack.pop(0))
        self.unsaved = True
        return True

    def history(self, redo=False):
        source,dest = (self.redo_stack,self.undo_stack) if redo else (self.undo_stack,self.redo_stack)
        if not source:
            return False
        changes = source.pop()
        for x,z,before,after in changes:
            a = after if redo else before
            h,w = a.shape
            self.values[z:z+h,x:x+w] = a
            self.mark((x,z,x+w,z+h))
        dest.append(changes)
        self.unsaved = True
        self.invalidate_preview()
        return True

    def value_at(self, point):
        r = self.region
        x,z = point
        if not (r.x0<=x<r.x0+r.width and r.z0<=z<r.z0+r.depth):
            return None
        h,w = self.values.shape
        return float(self.values[min(h-1,int((z-r.z0)*h/r.depth)),min(w-1,int((x-r.x0)*w/r.width))])

    def rgba(self, box):
        x,z,ex,ez = box
        v = self.values[z:ez,x:ex]
        rgba = np.empty((*v.shape,4),np.uint8)
        if self.kind=='heightmap':
            rgba[...,:3] = np.where((v>=0)[...,None],COLORS['warm'],COLORS['cold'])
            alpha = np.abs(v)/(np.abs(v)+16.) if self.mode=='add' else np.full_like(v,.8)
        else:
            rgba[...,:3] = COLORS[self.kind]
            alpha = 1-v if self.kind=='vegetation' else v
        rgba[...,3] = np.round(alpha*150).astype(np.uint8)
        return rgba

    def file_values(self):
        return self.values

    def write(self, path):
        write_image(path,self.file_values())

    def save(self, directory):
        path = Path(self.path) if self.path else Path(directory)/(self.kind+'_'+uuid.uuid4().hex+self.extension)
        self.write(path)
        self.path, self.unsaved = str(path.resolve()),False
        return self.path


class Stroke:
    def __init__(self, canvas, brush):
        self.canvas, self.brush = canvas, brush
        self.tiles = {}
        self.bounds = None

    def segment(self, a, b):
        c,p = self.canvas,self.brush
        r,h,w = c.region,*c.values.shape
        a,b = (np.asarray(point,np.float64)-(r.x0,r.z0) for point in (a,b))
        scale = np.array((r.width/w,r.depth/h))
        if p.diameter<=max(r.width/w,r.depth/h):
            # Sub-pixel brushes still paint the pixel under the pointer.
            a = (np.floor(a/scale)+.5)*scale
            b = (np.floor(b/scale)+.5)*scale
        radius = p.diameter/2
        lo = np.floor((np.minimum(a,b)-radius)/scale).astype(np.int64)
        hi = np.ceil((np.maximum(a,b)+radius)/scale).astype(np.int64)
        x0,z0 = np.maximum(lo,0)
        x1,z1 = np.minimum(hi,(w,h))
        if x0>=x1 or z0>=z1:return
        box = tuple(map(int,(x0,z0,x1,z1)))
        self.bounds = union_box(self.bounds,box)
        if not c.preview_reset:
            c.preview_commands.append(PreviewCommand('segment',box,p,tuple(a),tuple(b)))
        delta = np.subtract(b,a)
        length = float(delta@delta)
        for z in range(int(z0)//TILE*TILE,int(z1),TILE):
            for x in range(int(x0)//TILE*TILE,int(x1),TILE):
                view = c.values[z:z+TILE,x:x+TILE]
                if (x,z) not in self.tiles:
                    self.tiles[x,z] = view.copy(),np.zeros(view.shape,np.float32)
                before,cover = self.tiles[x,z]
                yy,xx = np.ogrid[z:z+view.shape[0],x:x+view.shape[1]]
                xx = (xx+.5)*scale[0]
                yy = (yy+.5)*scale[1]
                t = np.clip(((xx-a[0])*delta[0]+(yy-a[1])*delta[1])/length,0,1) if length else 0.
                distance = np.hypot(xx-(a[0]+t*delta[0]),yy-(a[1]+t*delta[1]))
                weight = ((distance<=radius).astype(np.float32) if p.hardness==1 else
                          np.clip((radius-distance)/(radius*(1-p.hardness)),0,1).astype(np.float32))
                np.maximum(cover,weight,out=cover)
                if c.categorical:
                    view[:] = np.where(cover > .5,int(p.value),before)
                else:
                    alpha = cover*p.strength
                    view[:] = before*(1-alpha)+p.value*alpha
                c.mark((x,z,x+view.shape[1],z+view.shape[0]))


def load_canvas(kind, config, params=None):
    from .core.heightmap import capture,decoded,snapshot
    source = capture(config)
    if kind=='heightmap':
        image = snapshot(config,source)
        low,high = image.output_range(params)
        a,b = config.input_range
        values = low+(image.values.astype(np.float64)-a)*((high-low)/(b-a))
    else:
        values = decoded(source).values
    source.checked()
    return Canvas(kind,config.region,values,mode=config.mode if kind=='heightmap' else 'add')


def write_image(path, values):
    """Atomic numeric image publication, leaving the previous file intact on failure."""
    os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR','1')
    import cv2
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary = path.with_name(path.stem+'.'+uuid.uuid4().hex+'.tmp'+path.suffix)
    try:
        if not cv2.imwrite(str(temporary),values):
            raise OSError(f'Could not write {path}')
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)
