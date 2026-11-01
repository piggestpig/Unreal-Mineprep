"""Display metadata, page migration and debounced saves; no Unreal dependency."""
import json
import math
from dataclasses import dataclass
from .core.ui_metadata import section_id, group_pages
from .core.coarse import capabilities

MAP_VIEWS = frozenset(('landscape','surface','vegetation','biomes','height',
                       'temperature','humidity','water_system','lod'))


def detail_options(pack, cell_step, core=None, core_empty=False):
    """Effective request options; inactive saved core coordinates stay untouched."""
    caps = capabilities(pack)
    core = core if caps['fixed_regions'] else None
    return dict(cell_step=cell_step if cell_step in caps['horizontal_steps'] else 1,
                core=core,core_empty=bool(core is not None and core_empty))


def preview_color_linear(value):
    """Stored preview colours are sRGB bytes; the native picker edits linear RGB."""
    rgb = [int(value[i:i+2],16)/255 for i in (1,3,5)]
    return tuple(c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in rgb)


def preview_color_hex(rgb):
    values = tuple(float(c) for c in rgb)
    if len(values) != 3 or any(not math.isfinite(c) or not 0 <= c <= 1 for c in values):
        raise ValueError('preview colour requires three finite linear values in [0,1]')
    srgb = (12.92*c if c <= .0031308 else 1.055*c**(1/2.4)-.055 for c in values)
    return '#' + ''.join(f'{round(c*255):02X}' for c in srgb)


def page_id(value, pack=None):
    if pack is None:
        return value
    value = section_id(value,pack.ui_sections)
    return value if value in ('world','blocks','custom','output') or any(s.id==value for s in pack.ui_sections) else 'world'


def rule_summary(rule):
    """Compact display facts and complete tooltip, without changing raw rules."""
    top = rule.get('top')
    material, extra = None, 0
    if isinstance(top, str):
        material = top
    elif top:
        material, extra = top[0][0], len(top) - 1
    return material, extra, len(rule.get('when', {})), json.dumps(rule, ensure_ascii=False, indent=2)


@dataclass(frozen=True)
class PreviewMap:
    """One image-to-world transform, including letterbox, zoom and pan."""
    region: object
    image_size: tuple
    viewport: tuple
    zoom: float
    pan: tuple

    @property
    def size(self):
        scale = min(v / n for v,n in zip(self.viewport,self.image_size))
        return tuple(n * scale for n in self.image_size)

    def world(self, point, *, clip=False):
        """Continuous MC X/Z, also used by world-size brushes."""
        uv = tuple((p-v/2-t)/(n*self.zoom)+.5
                   for p,v,t,n in zip(point,self.viewport,self.pan,self.size))
        if not clip and not all(0 <= q < 1 for q in uv):
            return None
        r = self.region
        if clip: uv = tuple(min(1.,max(0.,q)) for q in uv)
        return tuple(o+q*n for o,n,q in zip((r.x0,r.z0),(r.width,r.depth),uv))

    def cell(self, point, *, clip=False):
        world = self.world(point,clip=clip)
        if world is None:
            return None
        r = self.region
        return tuple(min(o+n-1,max(o,math.floor(p)))
                     for o,n,p in zip((r.x0,r.z0),(r.width,r.depth),world))

    def local(self, point):
        r = self.region
        return tuple(v/2+t+((p-o)/n-.5)*s*self.zoom for p,o,n,s,v,t in zip(
            point,(r.x0,r.z0),(r.width,r.depth),self.size,self.viewport,self.pan))

    def box(self, corners):
        """Visible intersection: unscaled size and translation from viewport centre."""
        r = self.region
        a,b = corners
        lo = max(r.x0,min(a[0],b[0])),max(r.z0,min(a[1],b[1]))
        hi = min(r.x0+r.width,max(a[0],b[0])+1),min(r.z0+r.depth,max(a[1],b[1])+1)
        if any(end <= start for start,end in zip(lo,hi)):
            return None
        size = tuple((end-start)*s/n for start,end,s,n in zip(lo,hi,self.size,(r.width,r.depth)))
        offset = tuple(t+((start+end)/2-o-n/2)*s/n*self.zoom
                       for start,end,o,n,s,t in zip(lo,hi,(r.x0,r.z0),(r.width,r.depth),self.size,self.pan))
        return size,offset


class SaveSchedule:
    """Preferences debounce; bounded draft checkpoint latency during continuous edits."""
    def __init__(self):
        self.preferences_due = self.draft_due = None

    def changed(self, now, *, draft=True):
        self.preferences_due = now + 1
        if draft and self.draft_due is None:
            self.draft_due = now + 5

    def ready(self, now):
        prefs = self.preferences_due is not None and now >= self.preferences_due
        draft = self.draft_due is not None and now >= self.draft_due
        if prefs:
            self.preferences_due = None
        if draft:
            self.draft_due = None
        return prefs, draft
