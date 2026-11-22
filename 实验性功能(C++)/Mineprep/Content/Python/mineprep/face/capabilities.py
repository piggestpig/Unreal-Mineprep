from __future__ import annotations

import json

try:
    import unreal
except ModuleNotFoundError:
    unreal = None

from .protocol import (
    DEFAULT_EYE_BOUNDS,
    FACE2D_SLOT,
    FACE3D_CORRECTIVE_MORPHS,
    FACE3D_MATERIAL_DRIVEN_CURVES,
    FACE3D_SLOT,
    FACE_BONES_ADVANCED,
    FACE_BONES_STANDARD,
    FACE_CURVES,
    FACE_META_CURVES,
    FACE_META_DRIVERS,
    FACE_META_EYE_BOUNDS,
    FACE_META_MODE,
    FACE_META_PUPIL_MODE,
    FACE_META_VERSION,
    FACE_SPEC_VERSION,
    infer_eye_head_margins,
    infer_pupil_rest_mode,
    infer_pupil_rest_mode_from_rects,
    load_face_templates,
    normalize_face_mode,
    supported_face_curves,
)
from .solver import (
    ensure_face3d_post_process_abp,
)


def setup_face_skeleton(
    skeleton,
    curves=FACE_CURVES,
    *,
    material_curves=None,
    morph_curves=None,
    mesh=None,
    spec: dict | None = None,
    mode: str | None = None,
    options: dict | None = None,
    preserve_existing: bool | None = None,
) -> dict[str, str]:
    """Register canonical facial curves on `USkeleton` with accurate driver flags and mesh metadata.

    - Only registers public curves actually supported by `(spec, mode, options)` when provided;
      internal corrective morphs (`_mc_*`) are never added to `USkeleton`.
    - Sets `bMaterial` and `bMorphTarget` per curve based on true driver (`material`, `morph`, `morph+material`).
    - When `preserve_existing` is True (default whenever no authoritative `spec`/`mode`/driver sets are passed),
      already-registered skeleton curves keep their existing `bMaterial`/`bMorphTarget` flags untouched.
    - When `mesh` is provided, writes `Mineprep.Face*` asset metadata tags and attaches
      `ABP_MineprepFace3D` to `mesh.post_process_anim_blueprint` for 3D corrective morphs.
    """
    norm_mode = normalize_face_mode(mode) if mode is not None else None
    if preserve_existing is None:
        preserve_existing = (spec is None and norm_mode is None and material_curves is None and morph_curves is None)
    if spec is not None and norm_mode in ('2d', '3d'):
        spec_drivers = supported_face_curves(spec, norm_mode, options)
        if curves is None or curves is FACE_CURVES:
            drivers = spec_drivers
        else:
            drivers = {}
            for cname in curves:
                name = str(cname)
                if name.startswith('_mc_'):
                    continue
                if name in spec_drivers:
                    drivers[name] = spec_drivers[name]
                elif norm_mode == '2d':
                    drivers[name] = 'material'
                else:
                    drivers[name] = 'morph+material' if name in FACE3D_MATERIAL_DRIVEN_CURVES else 'morph'
    else:
        raw_curves = [str(c) for c in (curves or ()) if not str(c).startswith('_mc_')]
        if material_curves is None and morph_curves is None:
            if norm_mode == '3d':
                drivers = {
                    c: ('morph+material' if c in FACE3D_MATERIAL_DRIVEN_CURVES else 'morph')
                    for c in raw_curves
                }
            else:
                drivers = {c: 'material' for c in raw_curves}
        else:
            mat_set = set(material_curves or ())
            morph_set = set(morph_curves or ())
            drivers = {
                c: (
                    'morph+material' if (c in mat_set and c in morph_set)
                    else ('morph' if c in morph_set else 'material')
                )
                for c in raw_curves
            }

    if unreal is None:
        return drivers

    if skeleton is not None and drivers:
        existing = {str(n) for n in skeleton.get_curve_meta_data_names()}
        changed = False
        for cname, driver in drivers.items():
            is_new = cname not in existing
            if not is_new and preserve_existing:
                continue
            want_mat = 'material' in driver
            want_morph = 'morph' in driver
            if is_new:
                skeleton.add_curve_meta_data(cname)
                existing.add(cname)
                changed = True
            if bool(skeleton.get_curve_meta_data_material(cname)) != want_mat:
                skeleton.set_curve_meta_data_material(cname, want_mat)
                changed = True
            if hasattr(skeleton, 'get_curve_meta_data_morph_target') and hasattr(skeleton, 'set_curve_meta_data_morph_target'):
                if bool(skeleton.get_curve_meta_data_morph_target(cname)) != want_morph:
                    skeleton.set_curve_meta_data_morph_target(cname, want_morph)
                    changed = True
        if changed:
            skeleton.modify()

    if mesh is not None:
        lib = unreal.EditorAssetLibrary
        if norm_mode in ('2d', '3d') or drivers:
            if norm_mode is not None:
                lib.set_metadata_tag(mesh, FACE_META_MODE, norm_mode)
            lib.set_metadata_tag(mesh, FACE_META_VERSION, FACE_SPEC_VERSION)
            lib.set_metadata_tag(mesh, FACE_META_CURVES, json.dumps(list(drivers.keys())))
            lib.set_metadata_tag(mesh, FACE_META_DRIVERS, json.dumps(drivers, sort_keys=True))
            if spec is not None:
                lib.set_metadata_tag(mesh, FACE_META_PUPIL_MODE, str(infer_pupil_rest_mode(spec)))
                lib.set_metadata_tag(
                    mesh, FACE_META_EYE_BOUNDS,
                    json.dumps(infer_eye_head_margins(spec), sort_keys=True),
                )
        if norm_mode == '3d':
            morph_names = {str(n) for n in (mesh.get_all_morph_target_names() or ())}
            if any(cm in morph_names for cm in FACE3D_CORRECTIVE_MORPHS):
                abp = ensure_face3d_post_process_abp()
                abp_cls = abp.generated_class()
                if mesh.get_editor_property('post_process_anim_blueprint') != abp_cls:
                    mesh.modify()
                    mesh.set_editor_property('post_process_anim_blueprint', abp_cls)

    return drivers


register_face_curves = setup_face_skeleton


_ALL_KNOWN_FACE_BONES = frozenset((*FACE_BONES_STANDARD, *FACE_BONES_ADVANCED))
_FACE_CURVE_SET = frozenset(FACE_CURVES)


def _mesh_bone_names(mesh) -> list[str]:
    if unreal is None or mesh is None:
        return []
    try:
        comp = unreal.SkeletalMeshComponent()
        comp.set_skeletal_mesh_asset(mesh)
        return [str(comp.get_bone_name(i)) for i in range(comp.get_num_bones())]
    except Exception:
        return []


def _match_mesh_template(mesh) -> dict | None:
    """Match a SkeletalMesh asset name to its facial template spec when metadata is absent."""
    raw_name = str(mesh.get_name() or '').strip().lower()
    stem = raw_name[4:] if raw_name.startswith('skm_') else raw_name
    for suffix in ('_head', '_body', '_3d', '_2d'):
        while stem.endswith(suffix):
            stem = stem[:-len(suffix)]
    templates = load_face_templates()
    if stem in templates:
        return templates[stem]
    # Match longest template prefix followed by '_' (e.g. 'horse_baby_custom' -> 'horse_baby')
    for tpl_name in sorted(templates, key=len, reverse=True):
        if stem.startswith(tpl_name + '_'):
            return templates[tpl_name]
    return None


def _infer_mesh_pupil_rest_mode(mesh, lib) -> int:
    """Resolve horizontal `Pupil_Rest_Mode` (-1 inner, 0 center/full, +1 outer) for any SkeletalMesh."""
    raw_tag = str(lib.get_metadata_tag(mesh, FACE_META_PUPIL_MODE) or '').strip()
    if raw_tag in ('-1', '0', '1', '+1'):
        return int(raw_tag)

    # Fallback 1: read exact 2D shader socket/pupil rects directly from the mesh's Face2D MIC
    mel = unreal.MaterialEditingLibrary
    for slot in (mesh.materials or ()):
        mi = slot.material_interface
        if mi is None or not isinstance(mi, unreal.MaterialInstanceConstant):
            continue
        if str(slot.material_slot_name) != FACE2D_SLOT and 'Face2D' not in str(mi.get_name()):
            continue
        try:
            def _vec4(pname: str):
                c = mel.get_material_instance_vector_parameter_value(mi, pname)
                return (float(c.r), float(c.g), float(c.b), float(c.a))

            el, pl = _vec4('Rect_Eye_L'), _vec4('Rect_Pupil_L')
            er, pr = _vec4('Rect_Eye_R'), _vec4('Rect_Pupil_R')
            if (el[2] > el[0] and pl[2] > pl[0]) or (er[2] > er[0] and pr[2] > pr[0]):
                return infer_pupil_rest_mode_from_rects(el, pl, er, pr)
        except Exception:
            pass

    # Fallback 2: infer template from SkeletalMesh asset name (handles already-imported 3D meshes)
    tpl = _match_mesh_template(mesh)
    if tpl is not None:
        return infer_pupil_rest_mode(tpl)
    return -1


def _infer_mesh_eye_bounds(mesh, lib, pupil_mode: int) -> dict[str, float]:
    """Resolve per-direction head-surface pupil clearances & scale-shift ratio for any SkeletalMesh."""
    raw_tag = str(lib.get_metadata_tag(mesh, FACE_META_EYE_BOUNDS) or '').strip()
    if raw_tag:
        try:
            parsed = json.loads(raw_tag)
            if isinstance(parsed, dict) and {'margin_in', 'margin_out', 'scale_shift'} <= set(parsed):
                return {
                    'margin_in': max(0.0, min(10.0, float(parsed['margin_in']))),
                    'margin_out': max(0.0, min(10.0, float(parsed['margin_out']))),
                    'scale_shift': max(0.0, min(3.0, float(parsed['scale_shift']))),
                }
        except Exception:
            pass
    tpl = _match_mesh_template(mesh)
    if tpl is not None:
        return infer_eye_head_margins(tpl)
    return {
        'margin_in': DEFAULT_EYE_BOUNDS['margin_in'],
        'margin_out': 0.0 if pupil_mode > 0 else DEFAULT_EYE_BOUNDS['margin_out'],
        'scale_shift': DEFAULT_EYE_BOUNDS['scale_shift'],
    }


def _inspect_mesh_face_capabilities(mesh) -> dict:
    """Inspect a single `USkeletalMesh` via Mineprep metadata first, falling back to asset scanning."""
    empty = {
        'face_mode': 'none',
        'spec_version': '',
        'source': 'none',
        'curves': [],
        'drivers': {},
        'bones': [],
        'face_bones': [],
        'corrective_morphs': [],
        'has_post_process_solver': False,
        'pupil_rest_mode': -1,
        'eye_bounds': dict(DEFAULT_EYE_BOUNDS),
    }
    if unreal is None or mesh is None:
        return empty

    lib = unreal.EditorAssetLibrary
    bones = _mesh_bone_names(mesh)
    face_bones = [b for b in bones if b in _ALL_KNOWN_FACE_BONES]
    all_morphs = [str(n) for n in (mesh.get_all_morph_target_names() or ())]
    corrective = [n for n in all_morphs if n in FACE3D_CORRECTIVE_MORPHS]
    pp_abp = None
    try:
        pp_abp = mesh.get_editor_property('post_process_anim_blueprint')
    except Exception:
        pp_abp = None
    has_solver = pp_abp is not None and 'ABP_MineprepFace3D' in str(pp_abp.get_name())

    meta_mode = str(lib.get_metadata_tag(mesh, FACE_META_MODE) or '').strip().lower()
    meta_ver = str(lib.get_metadata_tag(mesh, FACE_META_VERSION) or '').strip()
    raw_curves = str(lib.get_metadata_tag(mesh, FACE_META_CURVES) or '').strip()
    raw_drivers = str(lib.get_metadata_tag(mesh, FACE_META_DRIVERS) or '').strip()
    pupil_mode = _infer_mesh_pupil_rest_mode(mesh, lib)
    eye_bounds = _infer_mesh_eye_bounds(mesh, lib, pupil_mode)

    if meta_mode in ('2d', '3d') or raw_curves:
        curves_list: list[str] = []
        drivers_map: dict[str, str] = {}
        try:
            parsed_c = json.loads(raw_curves) if raw_curves else []
            if isinstance(parsed_c, list):
                curves_list = [str(c) for c in parsed_c if not str(c).startswith('_mc_')]
        except Exception:
            curves_list = []
        try:
            parsed_d = json.loads(raw_drivers) if raw_drivers else {}
            if isinstance(parsed_d, dict):
                drivers_map = {str(k): str(v) for k, v in parsed_d.items() if not str(k).startswith('_mc_')}
        except Exception:
            drivers_map = {}
        if not curves_list and drivers_map:
            curves_list = list(drivers_map.keys())
        for c in curves_list:
            drivers_map.setdefault(c, 'material' if meta_mode == '2d' else 'morph')
        return {
            'face_mode': meta_mode if meta_mode in ('2d', '3d') else ('custom' if curves_list else 'none'),
            'spec_version': meta_ver,
            'source': 'metadata',
            'curves': curves_list,
            'drivers': drivers_map,
            'bones': bones,
            'face_bones': face_bones,
            'corrective_morphs': corrective,
            'has_post_process_solver': has_solver,
            'pupil_rest_mode': pupil_mode,
            'eye_bounds': dict(eye_bounds),
        }

    # Fallback scan for external / Blender / legacy meshes without Mineprep.Face* metadata
    public_morphs = [n for n in all_morphs if not n.startswith('_mc_')]
    public_morph_set = set(public_morphs)
    slot_names = set()
    mat_params = set()
    mel = unreal.MaterialEditingLibrary
    for slot in (mesh.materials or ()):
        slot_names.add(str(slot.material_slot_name))
        mi = slot.material_interface
        if mi is None:
            continue
        try:
            base = mi.get_base_material() if hasattr(mi, 'get_base_material') else mi
            if base is not None:
                mat_params.update(str(p) for p in (mel.get_scalar_parameter_names(base) or ()))
        except Exception:
            pass

    skel_curves: list[str] = []
    skel_mat_flags: dict[str, bool] = {}
    skel = getattr(mesh, 'skeleton', None)
    if skel is not None:
        for cname in (skel.get_curve_meta_data_names() or ()):
            s = str(cname)
            if not s.startswith('_mc_'):
                skel_curves.append(s)
                skel_mat_flags[s] = bool(skel.get_curve_meta_data_material(s))

    drivers_map = {}
    ordered_candidates = list(dict.fromkeys([
        *FACE_CURVES,
        *public_morphs,
        *(p for p in sorted(mat_params) if p.startswith('face_')),
        *skel_curves,
    ]))
    for cname in ordered_candidates:
        in_morph = cname in public_morph_set
        in_mat = (cname in mat_params) and (cname in _FACE_CURVE_SET or cname.startswith('face_'))
        in_skel = cname in skel_mat_flags
        if in_morph and in_mat:
            drivers_map[cname] = 'morph+material'
        elif in_morph:
            drivers_map[cname] = 'morph'
        elif in_mat:
            drivers_map[cname] = 'material'
        elif in_skel:
            drivers_map[cname] = 'material' if skel_mat_flags[cname] else 'curve'

    if FACE3D_SLOT in slot_names:
        inferred_mode = '3d'
    elif FACE2D_SLOT in slot_names:
        inferred_mode = '2d'
    elif drivers_map:
        inferred_mode = 'custom'
    else:
        inferred_mode = 'none'

    return {
        'face_mode': inferred_mode,
        'spec_version': '',
        'source': 'fallback' if drivers_map else 'none',
        'curves': list(drivers_map.keys()),
        'drivers': drivers_map,
        'bones': bones,
        'face_bones': face_bones,
        'corrective_morphs': corrective,
        'has_post_process_solver': has_solver,
        'pupil_rest_mode': pupil_mode,
        'eye_bounds': dict(eye_bounds),
    }


def describe_actor_capabilities(target) -> dict:
    """Inspect an Actor, SkeletalMeshComponent, or SkeletalMesh and report facial & skeletal capabilities.

    Reads `Mineprep.Face*` UE asset metadata first; falls back to scanning MorphTargets,
    material scalar parameters, and Skeleton curves for external / custom rigs.
    """
    if unreal is None or target is None:
        return {
            'face_mode': 'none',
            'spec_version': '',
            'source': 'none',
            'has_face_component': False,
            'face_component': '',
            'curves': [],
            'drivers': {},
            'bones': [],
            'face_bones': [],
            'corrective_morphs': [],
            'has_post_process_solver': False,
            'pupil_rest_mode': -1,
            'eye_bounds': dict(DEFAULT_EYE_BOUNDS),
        }

    comp_meshes: dict[str, object] = {}
    if isinstance(target, unreal.SkeletalMesh):
        comp_meshes['body'] = target
    elif isinstance(target, unreal.SkeletalMeshComponent):
        mesh = target.get_skeletal_mesh_asset()
        if mesh is not None:
            comp_meshes['body'] = mesh
    elif isinstance(target, unreal.Actor):
        body = (
            target.skeletal_mesh_component
            if isinstance(target, unreal.SkeletalMeshActor)
            else target.get_component_by_class(unreal.SkeletalMeshComponent)
        )
        if body is not None and body.get_skeletal_mesh_asset() is not None:
            comp_meshes['body'] = body.get_skeletal_mesh_asset()
        for comp in (target.get_components_by_class(unreal.SkeletalMeshComponent) or ()):
            mesh = comp.get_skeletal_mesh_asset()
            if comp == body or mesh is None:
                continue
            if (comp.get_name() == 'Head'
                    and comp.get_attach_parent() == body
                    and str(comp.get_attach_socket_name()) == 'head'):
                comp_meshes['head'] = mesh
            else:
                comp_meshes.setdefault(comp.get_name(), mesh)
    else:
        raise ValueError('target 须为 Actor、SkeletalMeshComponent 或 SkeletalMesh')

    inspected = {k: _inspect_mesh_face_capabilities(m) for k, m in comp_meshes.items()}
    face_key = ''
    for pref in ('head', 'body', *inspected.keys()):
        info = inspected.get(pref)
        if info and (info['curves'] or info['face_mode'] != 'none'):
            face_key = pref
            break

    chosen = inspected.get(face_key) or {
        'face_mode': 'none',
        'spec_version': '',
        'source': 'none',
        'curves': [],
        'drivers': {},
        'bones': [],
        'face_bones': [],
        'corrective_morphs': [],
        'has_post_process_solver': False,
        'pupil_rest_mode': -1,
        'eye_bounds': dict(DEFAULT_EYE_BOUNDS),
    }

    all_bones = list(dict.fromkeys(b for info in inspected.values() for b in info['bones']))
    all_face_bones = list(dict.fromkeys(b for info in inspected.values() for b in info['face_bones']))
    return {
        'face_mode': chosen['face_mode'],
        'spec_version': chosen['spec_version'],
        'source': chosen['source'],
        'has_face_component': bool(face_key),
        'face_component': face_key,
        'curves': list(chosen['curves']),
        'drivers': dict(chosen['drivers']),
        'bones': all_bones,
        'face_bones': all_face_bones,
        'corrective_morphs': list(chosen['corrective_morphs']),
        'has_post_process_solver': bool(chosen['has_post_process_solver']),
        'pupil_rest_mode': int(chosen.get('pupil_rest_mode', -1)),
        'eye_bounds': dict(chosen.get('eye_bounds') or DEFAULT_EYE_BOUNDS),
    }
