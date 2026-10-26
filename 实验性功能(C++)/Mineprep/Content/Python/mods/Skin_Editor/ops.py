"""视口选中角色与材质面板的同步逻辑。"""
import unreal
import mineprep
from . import util


def _alive_layout(lay):
    t = getattr(lay, 'target', None) if lay is not None else None
    if not t:
        return False
    try:
        return bool(unreal.SystemLibrary.is_valid(t))
    except Exception:
        return False


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


def _set_text(lay, msg):
    if lay and _alive_layout(lay):
        lay.target.set_text(msg)


def _set_object(view, obj):
    if not _alive_layout(view):
        return
    view.target.set_object(obj if util._alive(obj) else None)
    view.hide(not util._alive(obj))


def selected_actors():
    return list(
        unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_selected_level_actors() or [])


def actor_skms(actor):
    if not actor:
        return []
    return list(mineprep.components.find(actor, unreal.SkeletalMeshComponent) or [])


def _spin_index(mod):
    spin = getattr(mod, '_actor_spin', None)
    if not _alive_layout(spin):
        return 1
    return max(1, int(round(spin.target.get_value())))


def _sync_spin(mod, count):
    spin = getattr(mod, '_actor_spin', None)
    if not _alive_layout(spin):
        return
    hi = float(max(1, count))
    mod._syncing = True
    try:
        box = spin.target
        box.set_min_value(1.0)
        box.set_max_value(hi)
        box.set_min_slider_value(1.0)
        box.set_max_slider_value(hi)
        box.set_value(1.0)
    finally:
        mod._syncing = False


def apply_columns(mod):
    opts = getattr(mod, 'options', None)
    split = getattr(mod, '_split', None)
    if not opts or not _alive_layout(split):
        return
    body, head = bool(opts.Body), bool(opts.Head)
    split.hide(not (body or head))
    if body and head:
        split.solo(0)
    elif body:
        split.solo(1)
    elif head:
        split.solo(2)


def on_actor_index(mod, _value=None):
    if getattr(mod, '_syncing', False):
        return
    refresh(mod, reset_index=False)


def refresh(mod, _selection_set=None, reset_index=True):
    if not _alive_layout(getattr(mod, '_body_view', None)):
        unbind_selection(mod)
        return

    selected = selected_actors()
    if reset_index:
        _sync_spin(mod, len(selected))

    index = _spin_index(mod)
    actor = selected[index - 1] if selected and 1 <= index <= len(selected) else None
    skms = actor_skms(actor)

    if not selected or not actor or not skms:
        _set_object(mod._body_view, None)
        _set_object(mod._head_view, None)
        if not selected:
            body_msg = mineprep.bilingual('未选中 Actor', 'No actor selected')
        elif not skms:
            body_msg = mineprep.bilingual(
                '选中的 Actor 中未找到骨骼网格体',
                'No skeletal mesh component on the selected actor')
        else:
            body_msg = mineprep.bilingual('未选中 Actor', 'No actor selected')
        _set_text(mod._body_title, body_msg)
        _set_text(mod._head_title, mineprep.bilingual('无头部', 'No Head'))
        return

    main = util.pick_main(skms, actor)
    head = util.pick_head(skms, main)
    _set_object(mod._body_view, main)
    _set_object(mod._head_view, head)
    _set_text(mod._body_title, actor.get_actor_label())
    _set_text(mod._head_title, head.get_name() if head else mineprep.bilingual('无头部', 'No Head'))
