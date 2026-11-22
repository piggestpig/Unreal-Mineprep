from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from io import BytesIO


# ---------------------------------------------------------------------------
# Canonical Facial Protocol (Shared by 2D, 3D, Custom Multi-Bone Heads, and MCAnimConverter)
# ---------------------------------------------------------------------------

FACE_CURVES = (
    'face_blink_l',
    'face_blink_r',
    'face_eye_wide',
    'face_pupil_scale',
    'face_look_x_l',
    'face_look_x_r',
    'face_look_y',
    'face_brow_y_l',
    'face_brow_y_r',
    'face_brow_rot_l',
    'face_brow_rot_r',
    'face_mouth_open',
    'face_mouth_wide',
    'face_mouth_smile',
    'face_mouth_x',
)

# Internal 3D corrective morph targets driven automatically by ABP_MineprepFace3D -> CR_MineprepFace3DSolver.
# Interchange marks them bMorphTarget=True (bMaterial=False) on USkeleton so FAnimInstanceProxy applies them;
# they are excluded from Mineprep.FaceCurves metadata and capability queries so user-facing tooling stays clean.
FACE3D_CORRECTIVE_MORPHS = (
    '_mc_eye_wide_pos',
    '_mc_mouth_neg_cancel',
    '_mc_blink_wide_l',
    '_mc_blink_wide_r',
    '_mc_brow_rot_sq_l',
    '_mc_brow_rot_sq_r',
)

FACE3D_MATERIAL_DRIVEN_CURVES = frozenset((
    'face_eye_wide',
    'face_mouth_open',
    'face_mouth_wide',
    'face_mouth_smile',
    'face_mouth_x',
))

FACE_BONES_STANDARD = (
    'face_root', 'eye_l', 'eye_r', 'pupil_l', 'pupil_r',
    'brow_l', 'brow_r', 'mouth', 'nose', 'ear_l', 'ear_r', 'jaw',
)

FACE_BONES_ADVANCED = (
    'lip_upper_l', 'lip_upper_c', 'lip_upper_r',
    'lip_lower_l', 'lip_lower_c', 'lip_lower_r',
    'lip_corner_l', 'lip_corner_r',
    'eyelid_upper_l', 'eyelid_upper_r', 'eyelid_lower_l', 'eyelid_lower_r',
    'brow_in_l', 'brow_mid_l', 'brow_out_l',
    'brow_in_r', 'brow_mid_r', 'brow_out_r',
    'tongue', 'teeth_upper', 'teeth_lower',
)

FACE_MODES = ('none', '2d', '3d')

FACE_BONE_ALIASES = {
    'face': 'face_root',
    'left_ear': 'ear_l',
    'right_ear': 'ear_r',
    'leftear': 'ear_l',
    'rightear': 'ear_r',
    'l_eye_pupil': 'pupil_l',
    'r_eye_pupil': 'pupil_r',
    'left_pupil': 'pupil_l',
    'right_pupil': 'pupil_r',
    'left_eye': 'eye_l',
    'right_eye': 'eye_r',
    'left_eyelid': 'eye_l',
    'right_eyelid': 'eye_r',
    'left_brow': 'brow_l',
    'right_brow': 'brow_r',
    'eyebrow_l': 'brow_l',
    'eyebrow_r': 'brow_r',
    'lower_beak': 'jaw',
}

FACE2D_CORE_MATERIAL = '/Game/Mineprep/材质/Core/M_Face2D'
FACE3D_CORE_MATERIAL = '/Game/Mineprep/材质/Core/M_Face3D'
FACE3D_SOLVER_CR_PATH = '/Game/Mineprep/生物模型rigs/Core/CR_MineprepFace3DSolver'
FACE3D_POST_ABP_PATH = '/Game/Mineprep/生物模型rigs/Core/ABP_MineprepFace3D'
FACE_RIG_CR_PATH = '/Game/Mineprep/生物模型rigs/Rig/CR_MC_Face'
FACE2D_SLOT = 'Face2D'
FACE3D_SLOT = 'Face3D'

# Simple version tags (warn on mismatch without overwriting user-edited core assets unless rebuild=True)
FACE2D_MATERIAL_VERSION = '8'
FACE3D_MATERIAL_VERSION = '9'
FACE3D_SOLVER_VERSION = '3'
FACE_RIG_VERSION = '5'
FACE_SPEC_VERSION = '1.0'
FACE_MAT_VERSION_TAG = 'Mineprep.FaceMaterialVersion'
FACE_SOLVER_VERSION_TAG = 'Mineprep.FaceSolverVersion'
FACE_RIG_VERSION_TAG = 'Mineprep.FaceRigVersion'
FACE_META_MODE = 'Mineprep.FaceMode'
FACE_META_VERSION = 'Mineprep.FaceSpecVersion'
FACE_META_CURVES = 'Mineprep.FaceCurves'
FACE_META_DRIVERS = 'Mineprep.FaceCurveDrivers'
FACE_META_PUPIL_MODE = 'Mineprep.FacePupilMode'
FACE_META_EYE_BOUNDS = 'Mineprep.FaceEyeBounds'

DEFAULT_EYE_BOUNDS: dict[str, float] = {
    'margin_in': 2.0,
    'margin_out': 2.0,
    'scale_shift': 0.175,
}

# Shared analytic mouth-ring pixel displacements (keep Python & FACE3D_VS_HLSL in exact lockstep)
_MOUTH_OPEN_UP = 0.38
_MOUTH_OPEN_DN = 0.38
_MOUTH_PUCKER_X = 0.28
_MOUTH_PUCKER_V = 0.008
_MOUTH_WIDE_X = 0.65
_MOUTH_SMILE_Y = 0.30
_MOUTH_SMILE_X = 0.20
_MOUTH_SHIFT_X = 0.65
_BROW_BLINK_FULL_DIP = 0.90

DEFAULT_FACE_OPTIONS = {
    'eye_depth': 0.12,
    'mouth_depth': 0.22,
    'brow_thickness': 0.08,
    'brow_height': 0.50,
    'use_teeth': False,
    'mouth_cavity_color': '#0d0b0d',
    'brow_blink_follow': False,
}

_TEMPLATES_CACHE = None


def normalize_face_mode(mode) -> str:
    if mode is None or mode is False or mode == '':
        return 'none'
    if mode is True:
        return '2d'
    text = str(mode).strip().lower()
    if text == 'off':
        return 'none'
    if text not in FACE_MODES:
        raise ValueError(f"face 模式须为 'none'、'2d' 或 '3d'，当前: {mode!r}")
    return text


def _linear_to_srgb_channel(c: float) -> float:
    c = max(0.0, min(1.0, float(c)))
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055


def linear_rgba_to_hex(rgba) -> str:
    if hasattr(rgba, 'r') and hasattr(rgba, 'g') and hasattr(rgba, 'b'):
        r, g, b = float(rgba.r), float(rgba.g), float(rgba.b)
    else:
        r, g, b = (float(rgba[0]), float(rgba[1]), float(rgba[2]))
    sr = int(round(_linear_to_srgb_channel(r) * 255.0))
    sg = int(round(_linear_to_srgb_channel(g) * 255.0))
    sb = int(round(_linear_to_srgb_channel(b) * 255.0))
    return f'#{sr:02x}{sg:02x}{sb:02x}'


def normalize_face_options(options: dict | None = None) -> dict:
    out = dict(DEFAULT_FACE_OPTIONS)
    if options:
        src = dict(options)
        if 'mouth_depth' not in src and 'mouth_thickness' in src:
            src['mouth_depth'] = src['mouth_thickness']
        for key, lo, hi in (
            ('eye_depth', 0.01, 1.0),
            ('mouth_depth', 0.02, 1.0),
            ('brow_thickness', 0.0, 1.0),
            ('brow_height', 0.1, 2.0),
        ):
            if key in src and src[key] is not None:
                val = float(src[key])
                if not math.isfinite(val):
                    raise ValueError(f'{key} 必须为有限数值')
                out[key] = max(lo, min(hi, val))
        if 'use_teeth' in src and src['use_teeth'] is not None:
            out['use_teeth'] = bool(src['use_teeth'])
        if 'brow_blink_follow' in src and src['brow_blink_follow'] is not None:
            out['brow_blink_follow'] = bool(src['brow_blink_follow'])
        if 'mouth_cavity_color' in src and src['mouth_cavity_color'] is not None:
            raw_col = src['mouth_cavity_color']
            if isinstance(raw_col, str):
                hex_to_linear_rgba(raw_col)  # validate
                cleaned = raw_col.strip().lstrip('#')[:6].lower()
                out['mouth_cavity_color'] = '#' + cleaned
            else:
                out['mouth_cavity_color'] = linear_rgba_to_hex(raw_col)
    return out


def _srgb_to_linear_channel(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_linear_rgba(text: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    raw = str(text or '#ffffff').strip().lstrip('#')
    if len(raw) == 8:
        r, g, b, a = (int(raw[i:i + 2], 16) / 255.0 for i in (0, 2, 4, 6))
    elif len(raw) == 6:
        r, g, b = (int(raw[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        a = float(alpha)
    else:
        raise ValueError(f'Invalid hex color: {text!r}')
    return (_srgb_to_linear_channel(r), _srgb_to_linear_channel(g), _srgb_to_linear_channel(b), a)


# ---------------------------------------------------------------------------
# Template Loading (with `extends` Inheritance) & Skin Refinement
# ---------------------------------------------------------------------------

def _templates_path() -> Path:
    return Path(__file__).with_name('facial_templates.json')


def load_face_templates(*, reload: bool = False) -> dict:
    """Load facial templates and resolve optional `extends` inheritance cleanly."""
    global _TEMPLATES_CACHE
    if _TEMPLATES_CACHE is None or reload:
        raw_templates = json.loads(_templates_path().read_text(encoding='utf-8'))['templates']
        resolved = {}

        def resolve_one(name: str, stack: set[str]) -> dict:
            if name in resolved:
                return resolved[name]
            if name in stack:
                raise ValueError(f'facial_templates.json 存在循环继承: {name}')
            if name not in raw_templates:
                raise ValueError(f'facial_templates.json 继承了不存在的模板: {name}')
            entry = raw_templates[name]
            parent_name = entry.get('extends')
            if parent_name:
                merged = copy.deepcopy(resolve_one(parent_name, stack | {name}))
                for k, v in entry.items():
                    if k != 'extends':
                        merged[k] = copy.deepcopy(v)
            else:
                merged = copy.deepcopy(entry)
            resolved[name] = merged
            return merged

        for key in raw_templates:
            resolve_one(key, set())
        _TEMPLATES_CACHE = resolved
    return _TEMPLATES_CACHE


def _refine_player_skin_spec(spec: dict, png_bytes: bytes | None) -> dict:
    if not png_bytes or not spec.get('auto_player_skin'):
        return spec
    from PIL import Image

    with Image.open(BytesIO(png_bytes)) as image:
        rgba = image.convert('RGBA')
        if rgba.size != (64, 64):
            return spec
        px = rgba.load()

    def dist(a, b):
        return sum((int(a[i]) - int(b[i])) ** 2 for i in range(3))

    cheek_l, cheek_r, hair_top = px[15, 13], px[8, 13], px[11, 8]
    ref_skin = cheek_r if cheek_r[3] > 200 else cheek_l
    candidates = [tuple(spec['skin_uv']), (11, 11), (12, 11), (10, 13), (13, 13), (11, 13), (12, 13)]
    best_uv, best_score = tuple(spec['skin_uv']), float('inf')
    for u, v in candidates:
        c = px[u, v]
        if c[3] < 200:
            continue
        score = dist(c, ref_skin) - 0.35 * dist(c, hair_top)
        if score < best_score:
            best_score, best_uv = score, (u, v)

    out = copy.deepcopy(spec)
    out['skin_uv'] = [best_uv[0], best_uv[1]]
    skin_px = px[best_uv[0], best_uv[1]]
    brow_r_px, brow_l_px = px[9, 11], px[14, 11]
    forehead_r, forehead_l = px[9, 10], px[14, 10]
    if (brow_r_px[3] > 200 and brow_l_px[3] > 200
            and dist(brow_r_px, skin_px) > 1800 and dist(brow_l_px, skin_px) > 1800
            and dist(brow_r_px, forehead_r) > 900 and dist(brow_l_px, forehead_l) > 900):
        out['use_brows'] = True
    return out


def _extract_skin_mouth_hex(spec: dict, png_bytes: bytes | None) -> dict:
    if not png_bytes or not spec.get('mouth'):
        return spec
    from PIL import Image

    with Image.open(BytesIO(png_bytes)) as image:
        rgba = image.convert('RGBA')
        tw, th = rgba.size
        px = rgba.load()
    mx0, my0, mx1, my1 = (int(round(x)) for x in spec['mouth'])
    samples = [
        px[u, v]
        for u in range(max(0, mx0), min(tw, mx1))
        for v in range(max(0, my0), min(th, my1))
        if px[u, v][3] > 128
    ]
    if not samples:
        return spec
    out = copy.deepcopy(spec)
    r = int(round(sum(c[0] for c in samples) / len(samples)))
    g = int(round(sum(c[1] for c in samples) / len(samples)))
    b = int(round(sum(c[2] for c in samples) / len(samples)))
    out['mouth_hex'] = f'#{r:02x}{g:02x}{b:02x}'
    return out


def get_face_spec(model_name: str, png_bytes: bytes | None = None) -> dict | None:
    stem = Path(str(model_name)).stem
    for suffix in ('_head', '_body'):
        if stem.endswith(suffix):
            stem = stem[:-len(suffix)]
    spec = load_face_templates().get(stem)
    if spec is None:
        return None
    out = copy.deepcopy(spec)
    if png_bytes is not None:
        out = _refine_player_skin_spec(out, png_bytes)
        out = _extract_skin_mouth_hex(out, png_bytes)
    return out


def _rect_nonempty(rect) -> bool:
    return (
        isinstance(rect, (list, tuple))
        and len(rect) == 4
        and float(rect[2]) > float(rect[0])
        and float(rect[3]) > float(rect[1])
    )


def infer_pupil_rest_mode_from_rects(eye_l, pupil_l, eye_r, pupil_r) -> int:
    """Infer horizontal pupil rest position within sockets: -1 (inner), 0 (center/full), +1 (outer).

    - `-1` (Inner, e.g. Steve/Villager/Horse/Wolf/Cat/Camel):
      `eye_l` travels `[0, +1]` in-socket; `eye_r` travels `[-1, 0]` in-socket.
    - `+1` (Outer, e.g. Pig/Cow/Sheep/Fox):
      `eye_l` travels `[-1, 0]` in-socket; `eye_r` travels `[0, +1]` in-socket.
    - `0` (Center/Full, e.g. Zombie/Bee/Ghast/Chicken/Rabbit/Goat/Hoglin):
      pupil fills socket horizontally; in-socket travel is `[0, 0]`.
    """
    votes: list[int] = []
    if _rect_nonempty(eye_l) and _rect_nonempty(pupil_l):
        sw = float(eye_l[2]) - float(eye_l[0])
        pw = float(pupil_l[2]) - float(pupil_l[0])
        if sw - pw > 0.05:
            left_gap = float(pupil_l[0]) - float(eye_l[0])
            right_gap = float(eye_l[2]) - float(pupil_l[2])
            if right_gap - left_gap > 0.05:
                votes.append(-1)
            elif left_gap - right_gap > 0.05:
                votes.append(1)
    if _rect_nonempty(eye_r) and _rect_nonempty(pupil_r):
        sw = float(eye_r[2]) - float(eye_r[0])
        pw = float(pupil_r[2]) - float(pupil_r[0])
        if sw - pw > 0.05:
            left_gap = float(pupil_r[0]) - float(eye_r[0])
            right_gap = float(eye_r[2]) - float(pupil_r[2])
            if left_gap - right_gap > 0.05:
                votes.append(-1)
            elif right_gap - left_gap > 0.05:
                votes.append(1)
    if not votes:
        return 0
    total = sum(votes)
    return -1 if total < 0 else (1 if total > 0 else 0)


def infer_pupil_rest_mode(spec: dict | None) -> int:
    """Infer `Pupil_Rest_Mode` (`-1`, `0`, or `+1`) from a facial template spec."""
    if not spec:
        return -1
    return infer_pupil_rest_mode_from_rects(
        spec.get('eye_l'), spec.get('pupil_l'),
        spec.get('eye_r'), spec.get('pupil_r'),
    )


def infer_eye_head_margins(spec: dict | None) -> dict[str, float]:
    """Compute per-direction head-surface pupil clearances & pupil-scale expansion ratio in `face_look_x` units.

    Returns `{'margin_in': float, 'margin_out': float, 'scale_shift': float}`:
    - `margin_in`: safe inward travel (toward nose / `-U` on left eye, `+U` on right eye) before exiting the head surface.
    - `margin_out`: safe outward travel (`+U` on left eye, `-U` on right eye) before exiting the head surface.
    - `scale_shift`: `0.175 * pupil_w / look_x_range` — inward shift per `+1.0` of `face_pupil_scale` needed to keep an
      enlarged 3D pupil flush inside the head boundary (e.g. `0.175` on Pig/Steve, `0.35` on Chicken/Rabbit, `0.70` on Bee).
    """
    if not spec:
        return dict(DEFAULT_EYE_BOUNDS)
    in_vals: list[float] = []
    out_vals: list[float] = []
    shift_vals: list[float] = []
    for sdef in _normalize_surfaces(spec):
        u0, _, u1, _ = (float(x) for x in sdef['uv'])
        for side in sdef['eyes']:
            er = spec.get(f'eye_{side}')
            pr = spec.get(f'pupil_{side}')
            if not (_rect_nonempty(er) and _rect_nonempty(pr)):
                continue
            ew = float(er[2]) - float(er[0])
            pw = float(pr[2]) - float(pr[0])
            lx = min(0.999, max(0.5, ew - pw))
            if side == 'l':
                in_vals.append((float(pr[0]) - u0) / lx)
                out_vals.append((u1 - float(pr[2])) / lx)
            else:
                out_vals.append((float(pr[0]) - u0) / lx)
                in_vals.append((u1 - float(pr[2])) / lx)
            shift_vals.append(0.175 * pw / lx)
    if not in_vals:
        return dict(DEFAULT_EYE_BOUNDS)
    return {
        'margin_in': round(min(10.0, max(0.0, min(in_vals))), 4),
        'margin_out': round(min(10.0, max(0.0, min(out_vals))), 4),
        'scale_shift': round(min(3.0, max(0.0, max(shift_vals))), 4),
    }


# ---------------------------------------------------------------------------
# Pure-Python GLB Rig & Local-Basis FaceSurface Helpers
# ---------------------------------------------------------------------------

def _normalize_surfaces(spec: dict) -> list[dict]:
    """Expand a template into one or more per-quad surface descriptors."""
    if spec.get('surfaces'):
        out = []
        for raw in spec['surfaces']:
            item = {
                'bone': raw.get('bone', spec.get('head_bone', 'head')),
                'uv': raw['uv'],
                'normal': raw.get('normal'),
                'skin_uv': raw.get('skin_uv', spec['skin_uv']),
                'eyes': tuple(raw.get('eyes', ())),
                'use_brows': bool(raw.get('use_brows', False)),
                'use_mouth': bool(raw.get('use_mouth', False)),
                'erase_rects': list(raw.get('erase_rects', ())),
            }
            out.append(item)
        return out
    eyes = tuple(side for side in ('l', 'r') if spec.get(f'eye_{side}'))
    return [{
        'bone': spec.get('head_bone', 'head'),
        'uv': spec['front_uv'],
        'normal': spec.get('front_normal', '+x'),
        'skin_uv': spec['skin_uv'],
        'eyes': eyes,
        'use_brows': bool(spec.get('brow_l') and spec.get('brow_r')),
        'use_mouth': bool(spec.get('use_mouth') and spec.get('mouth')),
        'erase_rects': [],
    }]


def supported_face_curves(
    spec: dict | None,
    mode: str,
    options: dict | None = None,
) -> dict[str, str]:
    """Return ordered `{curve_name: driver}` for curves genuinely supported by `(spec, mode, options)`.

    `driver` is `'material'` (2D shader), `'morph'` (3D geometry morph), or
    `'morph+material'` (3D morph paired with `M_Face3D` vertex UV-slide parameter).
    """
    norm_mode = normalize_face_mode(mode)
    if norm_mode == 'none' or not spec:
        return {}
    surfaces = _normalize_surfaces(spec)
    has_eye_l = _rect_nonempty(spec.get('eye_l')) and any('l' in s['eyes'] for s in surfaces)
    has_eye_r = _rect_nonempty(spec.get('eye_r')) and any('r' in s['eyes'] for s in surfaces)
    has_pupil_l = has_eye_l and _rect_nonempty(spec.get('pupil_l'))
    has_pupil_r = has_eye_r and _rect_nonempty(spec.get('pupil_r'))

    if norm_mode == '2d':
        has_brow_l = bool(spec.get('use_brows')) and _rect_nonempty(spec.get('brow_l'))
        has_brow_r = bool(spec.get('use_brows')) and _rect_nonempty(spec.get('brow_r'))
        has_mouth = bool(spec.get('use_mouth')) and _rect_nonempty(spec.get('mouth'))
    else:
        opts = normalize_face_options(options)
        brows_3d = (
            _rect_nonempty(spec.get('brow_l'))
            and _rect_nonempty(spec.get('brow_r'))
            and float(opts['brow_thickness']) > 1e-5
            and any(s['use_brows'] for s in surfaces)
        )
        has_brow_l = brows_3d
        has_brow_r = brows_3d
        has_mouth = False
        if _rect_nonempty(spec.get('mouth')):
            my0 = float(spec['mouth'][1])
            for s in surfaces:
                if not s['use_mouth']:
                    continue
                eye_holes = [spec[f'eye_{side}'] for side in s['eyes'] if _rect_nonempty(spec.get(f'eye_{side}'))]
                eye_bot = max((float(h[3]) for h in eye_holes), default=float(s['uv'][1]))
                if my0 > eye_bot + 0.25:
                    has_mouth = True
                    break

    enabled = {
        'face_blink_l': has_eye_l,
        'face_blink_r': has_eye_r,
        'face_eye_wide': has_eye_l or has_eye_r,
        'face_pupil_scale': has_pupil_l or has_pupil_r,
        'face_look_x_l': has_pupil_l,
        'face_look_x_r': has_pupil_r,
        'face_look_y': has_pupil_l or has_pupil_r,
        'face_brow_y_l': has_brow_l,
        'face_brow_y_r': has_brow_r,
        'face_brow_rot_l': has_brow_l,
        'face_brow_rot_r': has_brow_r,
        'face_mouth_open': has_mouth,
        'face_mouth_wide': has_mouth,
        'face_mouth_smile': has_mouth,
        'face_mouth_x': has_mouth,
    }

    out: dict[str, str] = {}
    for cname in FACE_CURVES:
        if not enabled.get(cname):
            continue
        if norm_mode == '2d':
            out[cname] = 'material'
        else:
            out[cname] = 'morph+material' if cname in FACE3D_MATERIAL_DRIVEN_CURVES else 'morph'
    return out
