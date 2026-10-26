"""Mutable captions and option sets for native ComboBoxKey widgets."""


def choice(parent, options, selected, callback, **kwargs):
    state = dict(options=dict(options), rows={}, caption=None, selected=selected)

    def text(key, *, content=False):
        import mineprep
        widget = mineprep.make_combo_text(key, texts=state['options'], outer=parent.target)
        if content:
            state['caption'] = widget
        else:
            state['rows'][str(key)] = widget
        return widget

    state['widget'] = parent.combo(options, selected=selected, on_selection_changed=callback,
        on_generate_content_widget=lambda key: text(key, content=True),
        on_generate_item_widget=lambda key: text(key), **kwargs)
    return state


def refresh_choice(state, options, selected):
    old = state['options']
    changed = {key for key in options if str(old.get(key, '')) != str(options[key])}
    widget = state['widget']
    for key in old.keys() - options.keys():
        widget.remove_option(key)
        state['rows'].pop(key, None)
    for key in options:
        if key not in old:
            widget.add_option(key)
    old.clear()
    old.update(options)
    for key in changed:
        if key in state['rows']:
            state['rows'][key].set_text(options[key])
    selection_changed = state['selected'] != selected
    if selection_changed:
        state['selected'] = selected
        widget.set_selected_option(selected)
    # A user selection has already changed the native key before its delegate.
    # Setting that same key is a no-op in UE; publish its caption explicitly.
    if (selection_changed or selected in changed) and state['caption'] is not None:
        state['caption'].set_text(options.get(selected, ''))
