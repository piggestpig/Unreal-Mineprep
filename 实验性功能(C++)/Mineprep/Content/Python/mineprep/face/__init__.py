"""Shared Minecraft face protocol, geometry and editor asset helpers."""
from importlib import import_module

from .protocol import (
    DEFAULT_EYE_BOUNDS,
    DEFAULT_FACE_OPTIONS,
    FACE2D_CORE_MATERIAL,
    FACE2D_MATERIAL_VERSION,
    FACE2D_SLOT,
    FACE3D_CORE_MATERIAL,
    FACE3D_CORRECTIVE_MORPHS,
    FACE3D_MATERIAL_DRIVEN_CURVES,
    FACE3D_MATERIAL_VERSION,
    FACE3D_POST_ABP_PATH,
    FACE3D_SLOT,
    FACE3D_SOLVER_CR_PATH,
    FACE3D_SOLVER_VERSION,
    FACE_BONES_ADVANCED,
    FACE_BONES_STANDARD,
    FACE_BONE_ALIASES,
    FACE_CURVES,
    FACE_MAT_VERSION_TAG,
    FACE_META_CURVES,
    FACE_META_DRIVERS,
    FACE_META_EYE_BOUNDS,
    FACE_META_MODE,
    FACE_META_PUPIL_MODE,
    FACE_META_VERSION,
    FACE_MODES,
    FACE_RIG_CR_PATH,
    FACE_RIG_VERSION,
    FACE_RIG_VERSION_TAG,
    FACE_SOLVER_VERSION_TAG,
    FACE_SPEC_VERSION,
    get_face_spec,
    hex_to_linear_rgba,
    infer_eye_head_margins,
    infer_pupil_rest_mode,
    infer_pupil_rest_mode_from_rects,
    linear_rgba_to_hex,
    load_face_templates,
    normalize_face_mode,
    normalize_face_options,
    supported_face_curves,
)

_EDITOR_AND_GEOMETRY = {
    "add_face_rig": "face_rig",
    "bake_face_to_rig": "face_rig",
    "create_face2d_material": "materials",
    "create_face3d_material": "materials",
    "curves_to_face_rig_controls": "face_rig",
    "describe_actor_capabilities": "capabilities",
    "ensure_face2d_material": "materials",
    "ensure_face3d_material": "materials",
    "ensure_face3d_post_process_abp": "solver",
    "ensure_face3d_solver_rig": "solver",
    "ensure_face_control_rig": "face_rig",
    "face2d_material_instance": "materials",
    "face3d_material_instance": "materials",
    "find_mounted_face_rig": "face_rig",
    "read_mounted_face_look_x": "face_rig",
    "register_face_curves": "capabilities",
    "setup_face_skeleton": "capabilities",
    "sparse_curves_to_face_rig_batches": "face_rig",
    "upgrade_face_glb": "geometry",
}


def __getattr__(name):
    if name not in _EDITOR_AND_GEOMETRY:
        raise AttributeError(name)
    return getattr(import_module("." + _EDITOR_AND_GEOMETRY[name], __name__), name)
