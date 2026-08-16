"""Selection sync and write-back for Skin Editor."""
import unreal
import mineprep
from . import util


def _alive_layout(lay):
    t = getattr(lay, 'target', None)
    return bool(t) and unreal.SystemLibrary.is_valid(t)


def unbind_selection(mod):
    hook = getattr(mod, '_sel_hook', None)
    if not hook:
        return
    sel, cb = hook
    try:
        sel.on_selection_change.remove_callable(cb)
    except Exception:
        pass
    mod._sel_hook = None


def bind_selection(mod):
    unbind_selection(mod)
    sel = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).get_selection_set()

    def cb(_selection_set=None):
        refresh(mod)

    sel.on_selection_change.add_callable(cb)
    mod._sel_hook = (sel, cb)


def _set_log(mod, msg):
    log = getattr(mod, '_log', None)
    if log and _alive_layout(log):
        log.target.set_text(str(msg))


@mineprep.undo('Skin Editor materials')
def apply_map(comp, mapping):
    if not util._alive(comp) or not mapping:
        return
    n = int(comp.get_num_materials() or 0)
    for key, mat in mapping.items():
        index = util.parse_slot_key(key)
        if index is None or index < 0 or index >= n:
            continue
        if comp.get_material(index) != mat:
            comp.set_material(index, mat)


def on_changed(mod, name=None):
    if getattr(mod, '_syncing', False):
        return
    if name in (None, 'Skin'):
        apply_map(getattr(mod, '_main_comp', None), mod.props.Skin)
    if name in (None, 'Head'):
        apply_map(getattr(mod, '_head_comp', None), mod.props.Head)


def refresh(mod, _selection_set=None):
    if not _alive_layout(getattr(mod, '_log', None)):
        unbind_selection(mod)
        return

    selected = list(
        unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_selected_level_actors() or [])
    notes = []

    actor, skms = None, []
    for candidate in selected:
        found = list(mineprep.components.find(candidate, unreal.SkeletalMeshComponent) or [])
        if found:
            actor, skms = candidate, found
            break

    mod._syncing = True
    try:
        if not selected or not actor:
            mod._main_comp = mod._head_comp = None
            mod.props.Skin = {}
            mod.props.Head = {}
            _set_log(mod, mineprep.bilingual(
                '未选中 Actor' if not selected else '选中的 Actor 中未找到骨骼网格体',
                'No actor selected' if not selected else 'No skeletal mesh component on the selected actor(s)'))
            return

        if len(selected) > 1:
            notes.append(mineprep.bilingual(
                f'选中了 {len(selected)} 个 Actor，仅显示「{actor.get_actor_label()}」',
                f'{len(selected)} actors selected; showing "{actor.get_actor_label()}"'))

        main = util.pick_main(skms, actor)
        head_comp = util.pick_head(skms, main)
        mod._main_comp, mod._head_comp = main, head_comp
        mod.props.Skin = util.read_slot_map(main)
        mod.props.Head = util.read_slot_map(head_comp) if head_comp else {}

        if head_comp:
            notes.append(mineprep.bilingual(
                f'头部：{head_comp.get_name()}', f'Head: {head_comp.get_name()}'))
        elif len(skms) == 1:
            notes.append(mineprep.bilingual(
                '仅一个骨骼网格体，无头部材质', 'Only one skeletal mesh; no head materials'))
        else:
            notes.append(mineprep.bilingual(
                f'未找到 Head（共 {len(skms)} 个骨骼网格体）',
                f'No Head component ({len(skms)} skeletal meshes)'))

        _set_log(mod, '  |  '.join(str(n) for n in notes))
    finally:
        mod._syncing = False
