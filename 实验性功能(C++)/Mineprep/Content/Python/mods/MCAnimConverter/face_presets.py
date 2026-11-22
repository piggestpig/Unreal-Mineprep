"""Cross-species facial expression presets and procedural auto-blink generator."""
from __future__ import annotations

from collections.abc import Mapping
import copy
import json
import math
from pathlib import Path
import random

from mineprep.face import FACE_CURVES
from .library import parse_localized_text

PRESETS_PATH = Path(__file__).with_name('Anim') / 'custom' / 'Face' / 'presets.json'
CATEGORIES = ('emotion', 'gaze', 'blink')
GAZE_CURVES = ('face_look_x_l', 'face_look_x_r', 'face_look_y')
BLINK_CURVES = ('face_blink_l', 'face_blink_r')
EMOTION_CURVES = tuple(c for c in FACE_CURVES if c not in GAZE_CURVES and c not in BLINK_CURVES)
RESET_SCOPES = ('none', 'emotion', 'all')
_BLINK_CURVES = frozenset(BLINK_CURVES)
_CACHE: list[dict] | None = None


def _normalize_reset_scope(value, *, default: str = 'none') -> str:
    if value is None:
        return default
    if value is True:
        return 'all'
    if value is False:
        return 'none'
    text = str(value).strip().lower()
    if text not in RESET_SCOPES:
        raise ValueError(f"reset_scope 须为 'none'、'emotion' 或 'all'，当前: {value!r}")
    return text


def _reset_pool(scope: str) -> tuple[str, ...]:
    if scope == 'all':
        return FACE_CURVES
    if scope == 'emotion':
        return EMOTION_CURVES
    return ()


def load_presets(*, reload: bool = False) -> list[dict]:
    """Load and validate the facial preset catalog from `Anim/custom/Face/presets.json`."""
    global _CACHE
    if _CACHE is None or reload:
        raw = json.loads(PRESETS_PATH.read_text(encoding='utf-8-sig'))
        items = raw.get('presets') if isinstance(raw, dict) else None
        if not isinstance(items, list) or not items:
            raise ValueError(f'表情预设清单无效: {PRESETS_PATH}')
        valid_curves = set(FACE_CURVES)
        seen = set()
        parsed = []
        for entry in items:
            pid = str(entry.get('id', '')).strip()
            if not pid or pid in seen:
                raise ValueError(f'表情预设 ID 为空或重复: {pid!r}')
            seen.add(pid)
            cat = str(entry.get('category', 'emotion'))
            if cat not in CATEGORIES:
                raise ValueError(f'表情预设分类无效: {pid} -> {cat!r}')
            curves = entry.get('curves')
            if not isinstance(curves, dict):
                raise ValueError(f'表情预设 curves 须为对象: {pid}')
            unknown = sorted(set(curves) - valid_curves)
            if unknown:
                raise ValueError(f'表情预设包含未知曲线: {pid} -> {unknown}')
            name_rec = parse_localized_text(entry.get('name'))
            if name_rec is None:
                fallback_zh = str(entry.get('zh') or pid)
                fallback_en = str(entry.get('en') or fallback_zh)
                name_rec = {'_native': 'zh', 'zh': fallback_zh, 'en': fallback_en}
            if 'reset_scope' in entry:
                reset_scope = _normalize_reset_scope(entry['reset_scope'])
            elif 'reset_others' in entry:
                reset_scope = _normalize_reset_scope(entry['reset_others'])
            else:
                reset_scope = 'all' if (cat == 'emotion' and not curves) else ('emotion' if cat == 'emotion' else 'none')
            parsed.append({
                'id': pid,
                'category': cat,
                'name': name_rec,
                'zh': name_rec.get('zh', pid),
                'en': name_rec.get('en', name_rec.get('zh', pid)),
                'reset_scope': reset_scope,
                'reset_others': reset_scope != 'none',
                'animation_length': entry.get('animation_length'),
                'curves': copy.deepcopy(curves),
            })
        _CACHE = parsed
    return [copy.deepcopy(item) for item in _CACHE]


def list_presets(*, category: str | None = None, reload: bool = False) -> list[dict]:
    items = load_presets(reload=reload)
    if category is not None:
        return [item for item in items if item['category'] == category]
    return items


def get_preset(preset_id: str, *, reload: bool = False) -> dict:
    key = str(preset_id or '').strip()
    for item in load_presets(reload=reload):
        if item['id'] == key:
            return item
    raise ValueError(f'找不到表情预设: {preset_id!r}')


def is_animated_preset(preset: Mapping) -> bool:
    curves = preset.get('curves') or {}
    return any(isinstance(v, dict) for v in curves.values())


def _scale_value(cname: str, val: float, strength: float) -> float:
    scaled = float(val) * strength
    if cname in _BLINK_CURVES:
        return max(0.0, min(1.0, scaled))
    return max(-2.0, min(2.0, scaled))


def _fmt_t(t: float) -> str:
    text = f'{round(float(t), 5):.5f}'.rstrip('0').rstrip('.')
    return text if '.' in text else text + '.0'


def build_pose_clip(
    preset_or_curves,
    *,
    strength: float = 1.0,
    blend_in: float = 0.0,
    hold: float = 0.0,
    blend_out: float = 0.0,
    reset_others: bool | str | None = None,
) -> tuple[str, dict]:
    """Compile a preset id/dict or custom curve mapping into a pure-curves Bedrock-style clip dict."""
    for label, val in (
        ('strength', strength),
        ('blend_in', blend_in),
        ('hold', hold),
        ('blend_out', blend_out),
    ):
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or val < 0:
            raise ValueError(f'{label} 须为非负有限数值')
    strength = float(strength)
    blend_in = float(blend_in)
    hold = float(hold)
    blend_out = float(blend_out)

    if isinstance(preset_or_curves, str):
        preset = get_preset(preset_or_curves)
        clip_name = f"face_preset_{preset['id']}"
        raw_curves = preset['curves']
        default_scope = preset['reset_scope']
        anim_len = preset.get('animation_length')
    elif isinstance(preset_or_curves, Mapping) and 'curves' in preset_or_curves and isinstance(preset_or_curves['curves'], Mapping):
        pid = str(preset_or_curves.get('id') or 'custom').strip() or 'custom'
        clip_name = f'face_preset_{pid}'
        raw_curves = preset_or_curves['curves']
        if 'reset_scope' in preset_or_curves:
            default_scope = _normalize_reset_scope(preset_or_curves['reset_scope'])
        else:
            default_scope = _normalize_reset_scope(preset_or_curves.get('reset_others', False))
        anim_len = preset_or_curves.get('animation_length')
    elif isinstance(preset_or_curves, Mapping):
        clip_name = 'face_preset_custom'
        raw_curves = preset_or_curves
        default_scope = 'none'
        anim_len = None
    else:
        raise ValueError('preset 须为预设 ID、预设字典或曲线值字典')

    unknown = sorted(set(raw_curves) - set(FACE_CURVES))
    if unknown:
        raise ValueError(f'包含未知表情曲线: {unknown}')

    scope = _normalize_reset_scope(reset_others, default=default_scope)
    reset_pool = _reset_pool(scope)

    # Timed / animated curve presets (e.g. `blink`, `double_blink`)
    if any(isinstance(v, Mapping) for v in raw_curves.values()):
        out_curves = {}
        max_t = float(anim_len) if anim_len is not None else 0.0
        for cname, ch in raw_curves.items():
            if isinstance(ch, Mapping):
                timed = {}
                for tk, tv in ch.items():
                    t_val = float(tk)
                    max_t = max(max_t, t_val)
                    timed[_fmt_t(t_val)] = round(_scale_value(cname, float(tv), strength), 5)
                out_curves[cname] = timed
            else:
                out_curves[cname] = round(_scale_value(cname, float(ch), strength), 5)
        for cname in reset_pool:
            out_curves.setdefault(cname, 0.0)
        return clip_name, {'animation_length': round(max_t, 5), 'curves': out_curves}

    # Static pose preset -> 1-frame pose stamp (blend_in=hold=blend_out=0) or sparse envelope
    targets = {cname: round(_scale_value(cname, float(val), strength), 5) for cname, val in raw_curves.items()}
    for cname in reset_pool:
        targets.setdefault(cname, 0.0)
    if not targets:
        targets = {cname: 0.0 for cname in FACE_CURVES}

    total = blend_in + hold + blend_out
    if total <= 1e-6:
        return clip_name, {'animation_length': 0.0, 'curves': targets}

    out_curves = {}
    for cname, tgt in targets.items():
        keys = {}
        if blend_in > 1e-6:
            keys[_fmt_t(0.0)] = 0.0
            keys[_fmt_t(blend_in)] = tgt
        else:
            keys[_fmt_t(0.0)] = tgt
        if hold > 1e-6:
            keys[_fmt_t(blend_in + hold)] = tgt
        if blend_out > 1e-6:
            keys[_fmt_t(total)] = 0.0
        out_curves[cname] = keys
    return clip_name, {'animation_length': round(total, 5), 'curves': out_curves}


def build_auto_blink_clip(
    duration: float = 5.0,
    *,
    min_interval: float = 2.4,
    max_interval: float = 4.4,
    blink_duration: float = 0.21,
    hold_closed: float = 0.08,
    double_blink_chance: float = 0.15,
    phase_offset: float = 0.0,
    seed: int | None = None,
) -> tuple[str, dict]:
    """Generate a sparse, synchronized procedural blink clip (`face_blink_l` & `face_blink_r`)."""
    for label, val in (
        ('duration', duration),
        ('min_interval', min_interval),
        ('max_interval', max_interval),
        ('blink_duration', blink_duration),
        ('hold_closed', hold_closed),
        ('double_blink_chance', double_blink_chance),
        ('phase_offset', phase_offset),
    ):
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
            raise ValueError(f'{label} 须为有限数值')
    duration = float(duration)
    min_interval = float(min_interval)
    max_interval = float(max_interval)
    blink_duration = float(blink_duration)
    hold_closed = max(0.0, float(hold_closed))
    double_blink_chance = max(0.0, min(1.0, float(double_blink_chance)))
    phase_offset = max(0.0, min(0.06, float(phase_offset)))

    if duration <= 0.0:
        raise ValueError('duration 必须大于 0')
    if min_interval <= 0.0 or max_interval < min_interval:
        raise ValueError('眨眼间隔需满足 0 < min_interval <= max_interval')
    if blink_duration < 0.05:
        raise ValueError('blink_duration 须 >= 0.05 秒')

    # Ensure hold_closed fits cleanly inside total blink duration while keeping crisp close & open ramps
    if hold_closed > blink_duration - 0.04:
        blink_duration = hold_closed + 0.08
    rem = max(0.04, blink_duration - hold_closed)
    close_dt = rem * 0.40
    open_dt = rem - close_dt

    rng = random.Random(seed) if seed is not None else random.Random()
    events: list[float] = []
    margin_end = blink_duration + phase_offset + 0.02
    if duration > margin_end:
        first_max = min(max_interval * 0.75, duration - margin_end)
        first_min = min(min_interval * 0.35, first_max)
        t = rng.uniform(max(0.1, first_min), max(0.1, first_max))
        while t + margin_end <= duration:
            events.append(t)
            if double_blink_chance > 0.0 and rng.random() < double_blink_chance:
                t2 = t + blink_duration + rng.uniform(0.08, 0.14)
                if t2 + margin_end <= duration:
                    events.append(t2)
                    t = t2
            t += rng.uniform(min_interval, max_interval)
        if not events and duration >= blink_duration + 0.04:
            events.append(max(0.02, 0.5 * (duration - blink_duration)))

    def _build_eye_track(offset_s: float) -> dict[str, float]:
        # Sparse keys ONLY at the blink transition moments (4 keys per blink, zero filler keys!)
        pts: dict[float, float] = {}
        for ev in events:
            t0 = max(0.0, ev + offset_s)
            t1 = t0 + close_dt
            t2 = t1 + hold_closed
            t3 = t2 + open_dt
            if t3 > duration:
                continue
            pts[round(t0, 5)] = 0.0
            pts[round(t1, 5)] = 1.0
            if hold_closed > 1e-4:
                pts[round(t2, 5)] = 1.0
            pts[round(t3, 5)] = 0.0
        if not pts:
            pts[0.0] = 0.0
        return {_fmt_t(k): pts[k] for k in sorted(pts)}

    curves = {
        'face_blink_l': _build_eye_track(0.0),
        'face_blink_r': _build_eye_track(phase_offset),
    }
    return 'face_auto_blink', {'animation_length': round(duration, 5), 'curves': curves}
