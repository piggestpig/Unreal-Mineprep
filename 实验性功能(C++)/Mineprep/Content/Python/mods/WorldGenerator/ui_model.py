"""Display metadata, page migration and debounced saves; no Unreal dependency."""
import json
import math
from .core.ui_metadata import section_id, group_pages


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
