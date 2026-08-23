"""Skeletal-mesh component helpers for Skin Editor."""
import pathlib
import unreal
import mineprep


MATERIAL_DETAILS = (
    '/Mineprep/Python/mods/Skin_Editor/MaterialDetailsView.MaterialDetailsView')


def _alive(obj):
    return bool(obj) and unreal.SystemLibrary.is_valid(obj)


def is_head_comp(comp):
    return 'head' in (comp.get_name() or '').lower()


def is_mc_comp(comp):
    return 'MC' in (comp.get_name() or '')


def pick_main(skms, actor):
    if len(skms) >= 3:
        for comp in skms:
            if is_mc_comp(comp):
                return comp
    root = actor.root_component
    if isinstance(root, unreal.SkeletalMeshComponent) and root in skms:
        return root
    try:
        mesh = actor.get_editor_property('mesh')
        if isinstance(mesh, unreal.SkeletalMeshComponent) and mesh in skms:
            return mesh
    except Exception:
        pass
    body = [c for c in skms if not is_head_comp(c)]
    return (body or skms)[0]


def pick_head(skms, main):
    if len(skms) < 2:
        return None
    for comp in skms:
        if comp is not main and is_head_comp(comp):
            return comp
    for comp in skms:
        if is_head_comp(comp):
            return comp
    return None


def open_mod_script():
    mineprep.startfile(str(pathlib.Path(__file__).resolve().parent))
