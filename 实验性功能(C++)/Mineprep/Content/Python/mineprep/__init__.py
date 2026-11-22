"""Public Mineprep Python API."""
from importlib import import_module

import mcvars


_EXPORTS = {
    "blueprint_libs": (
        "BPLibCaller", "BPLib", "EditorBPLib",
    ),
    "handles": (
        "MineprepAPIHandle", "actor", "actors", "camera", "selected", "component", "components",
        "materials", "sequencer", "bindings", "tracks", "sections", "channels", "keys",
        "spawn_camera", "new_sequence", "keyframes",
    ),
    "importer": (
        "import_block", "import_item", "resolve_block_json_path", "get_all_blocks",
    ),
    "utils": (
        "cast", "uclass", "bpclass", "world", "prints", "warn", "throw", "panic", "enum",
        "askopenfilename", "askopenfilenames", "send2trash", "set_actor_label", "select_actors",
        "undo", "open_main_panel", "get_hotkey_object", "construct", "uasset", "copy", "List",
        "SafeList", "WrapList", "iscollection", "debug", "resolve_soft", "dialog", "askdirectory",
        "asksaveasfilename", "startfile", "screenshot", "Lazy", "left_mouse_down",
        "middle_mouse_down", "right_mouse_down", "show_editor_task", "unwrap_rotations",
    ),
    "parallel": (
        "delay", "tick", "asynctask", "thread", "asyncthread", "until", "DelayRunner",
        "TickRunner", "AsyncTaskRunner", "ThreadRunner",
    ),
    "prep": (
        "prep_texture", "load_mcprep_data", "colorize_material", "apply_mc_material_defaults",
        "identify_mc_texture", "resolve_mc_texture", "prepare_materials", "replace_materials",
        "prepare_scene", "prepare_assets",
    ),
    "material_tools": (
        "tex_to_color", "color_to_tex", "ColorList", "register_biome_tex", "clear_biome_tex",
        "tex_source_files", "export_tex_cache", "import_data_tex",
    ),
    "localization": (
        "localize", "loctext", "nsloctext", "loctable_col", "bilingual", "tooltip",
        "Internationalization", "i18n", "I18N", "collect_i18n", "check_i18n",
        "copy_engine_culture", "editor_has_culture",
    ),
    "structure": (
        "parse_structure", "structure_to_tex", "structure_parts", "Blocks",
        "convert_to_unreal_transforms", "convert_to_packed_arrays", "add_packed_instances",
        "spawn_structure",
    ),
    "math_tools": (
        "boxes_to_packed", "encode_rotation", "decode_rotation", "wave", "unwrap_angles",
    ),
    "blockstates": (
        "rotate_state", "mirror_state",
    ),
    "settings": (
        "config", "paths", "wclass",
    ),
    "rig": (
        "Rig",
    ),
    "sequencer_tools": (
        "keyframe", "orbit", "spline",
    ),
    "widgets": (
        "Layout", "PropertyGroup", "add_widget", "ui", "make_combo_text",
    ),
    "modding": (
        "mods", "Mod",
    ),
    "mesh": (
        "merge_skm",
    ),
    "model": (
        "LowPolyModel", "SkeletalModel",
    ),
    "face.protocol": (
        "FACE_CURVES", "FACE3D_CORRECTIVE_MORPHS", "FACE_BONES_STANDARD", "FACE_BONES_ADVANCED",
        "supported_face_curves",
    ),
    "editor_tools": (
        "MineprepAddonHandle", "attach", "help", "hotkey", "panel", "prep_from_browser",
        "prep_from_panel", "spawn_block", "spawn_blocks", "spawn_helper", "spawn_item",
        "spawn_mob", "spawn_preset", "toolbar",
    ),
    "reloading": (
        "reload",
    ),
    "face": (
        "add_face_rig", "bake_face_to_rig", "describe_actor_capabilities", "setup_face_skeleton",
        "ensure_face2d_material", "ensure_face3d_material", "ensure_face3d_post_process_abp",
        "ensure_face3d_solver_rig", "ensure_face_control_rig", "create_face2d_material",
        "create_face3d_material",
    ),
}

_PUBLIC_MODULE = {name: module for module, names in _EXPORTS.items() for name in names}
__all__ = [*_PUBLIC_MODULE, "mcvars", "unreal"]


def __getattr__(name):
    if name in _EXPORTS or name in ("inventory", "model_assets", "structure_data"):
        return import_module("." + name, __name__)
    if name == "unreal":
        from .utils import unreal
        return unreal
    if name in _PUBLIC_MODULE:
        value = getattr(import_module("." + _PUBLIC_MODULE[name], __name__), name)
        globals()[name] = value
        return value
    raise AttributeError(name)


def __dir__():
    return sorted(set(globals()) | set(__all__))
