"""Skeletal-mesh material slot helpers."""
import unreal


def _alive(obj):
    return bool(obj) and unreal.SystemLibrary.is_valid(obj)


def is_head_comp(comp):
    return 'head' in (comp.get_name() or '').lower()


def slot_names(comp):
    """Material slot names on a mesh component, aligned with get_num_materials()."""
    n = int(comp.get_num_materials() or 0)
    names = []
    try:
        names = [str(x) for x in (comp.get_material_slot_names() or [])]
    except Exception:
        names = []
    if len(names) < n:
        mesh = None
        try:
            mesh = comp.get_skeletal_mesh_asset()
        except Exception:
            mesh = None
        if mesh:
            try:
                skm_mats = list(mesh.get_editor_property('materials') or [])
                extra = []
                for entry in skm_mats:
                    slot = (
                        entry.get_editor_property('material_slot_name')
                        or entry.get_editor_property('slot_name')
                        or ''
                    )
                    extra.append(str(slot))
                if extra:
                    names = extra
            except Exception:
                pass
    if len(names) < n:
        names = names + [''] * (n - len(names))
    return names[:n]


def slot_key(index, name):
    return f'{index}:{name}'


def parse_slot_key(key):
    text = str(key)
    if ':' not in text:
        return None
    idx, _name = text.split(':', 1)
    try:
        return int(idx)
    except ValueError:
        return None


def read_slot_map(comp):
    """{ 'index:slotName': MaterialInterface } for a skeletal mesh component."""
    mapping = {}
    if not _alive(comp):
        return mapping
    names = slot_names(comp)
    for i, name in enumerate(names):
        mapping[slot_key(i, name)] = comp.get_material(i)
    return mapping


def pick_main(skms, actor):
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
