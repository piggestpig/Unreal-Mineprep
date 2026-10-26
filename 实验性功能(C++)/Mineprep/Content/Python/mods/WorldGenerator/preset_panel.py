"""Parameter presets, library forms and user-pack publication UI."""
from copy import deepcopy
from pathlib import Path
import mineprep
import unreal
from .core.spec import WorldSpec
from .core.presets import reset_section, section_keys
from .editor import click, tr, name_text, textbox
from .props import read_params, write_params
from .preset_library import preset_ref, _digest
from .naming import safe_name
from .ui_model import page_id
from .ui_choices import choice, refresh_choice

LIBRARY_COLORS = {'edit': (.035, .085, .16), 'file': (.035, .13, .075),
                  'delete': (.20, .035, .035), 'cancel': (.10, .05, .05)}


class PresetPanel:
    def _on_preset(self, preset, _reason=None):
        if not self._suspend and preset not in (None, '', 'None'):
            if preset == 'defaults:all':
                self._reset_params()
            else:
                self._load_parameter_preset(preset)

    def _reset_params(self):
        previous = self._values()
        values = dict(previous)
        values.update({key: definition.default for key, definition in self.pack.params.items()
                       if page_id(definition.page, self.pack) not in ('blocks', 'output')})
        self._set_parameter_values(values, values)
        self._section_marks = {page_id(d.page, self.pack): {} for d in self.pack.params.values()
                               if page_id(d.page, self.pack) not in ('blocks', 'output')}
        self._mark_preset('', self._values())
        self._parameters_published(previous)

    def _preset_label(self, preset_id, section=None, *, values=None):
        mark = self._global_mark if section is None else self._section_marks.get(section,{})
        status = ''
        if preset_id:
            try:
                record = self._library.get(preset_id, pack=self.pack)
                source,ident = preset_ref(preset_id).split(':',1)
                label = name_text(self.pack.presets[ident].name) if source == 'pack' else record['name']
                if mark.get('digest') and mark['digest'] != _digest(record):
                    status = tr(' · 来源已更新',' · Source updated')
            except (OSError,ValueError,TypeError):
                label = mark.get('name',preset_id)
                status = tr(' · 来源已删除或不可用',' · Source deleted or unavailable')
            prefix = tr('用户｜','User | ') if preset_id.startswith('library:') else tr('资源包｜','Pack | ')
            label = unreal.Text('{prefix}{name}').format(prefix=prefix,name=label)
        else:
            label = tr('资源包默认','Pack Default')
        current = self._values() if values is None else values
        saved = self._global_values if section is None else self._section_marks.get(section, {}).get('values', {})
        adjusted = any(k not in current or self.pack.params[k].coerce(current[k]) != self.pack.params[k].coerce(v)
                       for k,v in saved.items())
        adjusted |= self._curves_pending and (section is None or any(self.pack.params[k].type == 'curve' for k in saved))
        return unreal.Text('{name}{suffix}{status}').format(name=label, suffix=tr(' · 已调整', ' · Adjusted') if adjusted else '',status=status)

    def _render_global_preset(self):
        self._global_choice = None
        self._sync_global_preset()

    def _sync_global_preset(self, values=None):
        selected = preset_ref(self._global_mark['id']) if self._global_mark['id'] else 'defaults:all'
        options = {'defaults:all': tr('资源包默认', 'Pack Default')}
        options.update(self._preset_options())
        options[selected] = self._preset_label('' if selected == 'defaults:all' else selected, values=values)
        if self._global_choice is None:
            self._global_choice = choice(self._preset_slot, options, selected, self._on_preset)
            self._preset_combo = self._global_choice['widget']
        else:
            refresh_choice(self._global_choice, options, selected)

    def _entry_label(self, entry):
        name = name_text(self.pack.presets[entry['id']].name) if entry['source'] == 'pack' else entry['name']
        return unreal.Text('{prefix}{name}').format(name=name,prefix=tr('资源包｜','Pack | ') if entry['source']=='pack' else tr('用户｜','User | '))

    def _preset_options(self, section=None):
        identity = (id(self.pack), getattr(self, '_library_stamp', None))
        if identity != getattr(self, '_preset_options_identity', None):
            self._preset_options_identity, self._preset_option_sets = identity, {}
        if section not in self._preset_option_sets:
            entries = self._library.entries(self.pack, section)
            if section is None and self.pack.preset_menu is not None:
                by_id = {e['id']:e for e in entries if e['source'] == 'pack'}
                entries = ([by_id[k] for k in self.pack.preset_menu if k in by_id]
                           + [e for e in entries if e['source'] != 'pack'])
            self._preset_option_sets[section] = {e['ref']:self._entry_label(e)
                for e in entries}
        return self._preset_option_sets[section]

    def _render_section_preset(self):
        if self.page in ('blocks', 'output') or not any(page_id(d.page, self.pack) == self.page for d in self.pack.params.values()):
            return
        self._section_choice = None
        section = self.page
        row = self._section_slot.row()
        self._section_choice_parent = row
        self._sync_section_preset()
        row.button(tr('恢复', 'Reset'), size=10, text_scaling=True,
                   tooltip=tr('恢复本板块默认值', 'Reset section defaults'),
                   on_clicked=click(lambda: self._on_section_preset(section, '')))
        row.button(tr('另存', 'Save as'), size=10, text_scaling=True,
                   tooltip=tr('另存本板块预设', 'Save section preset as'),
                   on_clicked=click(lambda: self._save_form(True, section)))

    def _sync_section_preset(self, values=None):
        section = self.page
        selected = self._section_marks.get(section, {}).get('id', '')
        selected = preset_ref(selected) if selected else 'defaults:section'
        options = {'defaults:section': tr('资源包默认', 'Pack Default')}
        options.update(self._preset_options(section))
        options[selected] = self._preset_label('' if selected == 'defaults:section' else selected, section, values=values)
        if self._section_choice is None:
            self._section_choice = choice(self._section_choice_parent, options, selected,
                lambda value, reason: self._on_section_preset(section, value, reason), fill=1)
            self._section_combo = self._section_choice['widget']
        else:
            refresh_choice(self._section_choice, options, selected)

    def _refresh_preset_labels(self):
        if not hasattr(self, '_preset_slot'):
            return
        suspended = self._suspend
        self._suspend = True
        try:
            values = self._values()
            self._sync_global_preset(values)
            if self._section_choice is not None:
                self._sync_section_preset(values)
        finally:
            self._suspend = suspended

    def _on_section_preset(self, section, preset_id, _reason=None):
        if self._suspend:
            return
        # Keep the UI sentinel out of presets, Spec and persisted selection marks.
        preset_id = '' if preset_id in (None, 'None', 'defaults:section') else preset_id
        self._load_parameter_preset(preset_id,section)

    def _set_parameter_values(self, values, keys):
        """Write only committed keys; untouched native curves/inputs stay intact."""
        self.pack.resolve(WorldSpec(self.pack.id,self.preset,params=values))
        patch = {k:values[k] for k in keys}
        suspended, self._suspend = self._suspend, True
        try:
            for group in dict.fromkeys(self.groups.values()):
                write_params(group,self.pack,patch)
                self._last_native[id(group)] = read_params(group,self.pack,curves=False)
            self._curves.update({k:v for k,v in patch.items() if self.pack.params[k].type=='curve'})
            self._curves_pending = any(getattr(g,k.replace('.','__')).export_text()!=text
                for g in dict.fromkeys(self.groups.values()) for k,text in getattr(g,'_curve_text',{}).items())
            if not self._curves_pending:
                self._errors.pop('curves',None)
        finally:
            self._suspend = suspended

    def _parameter_snapshot(self, section=None):
        values = self._values()
        keys = section_keys(self.pack,section) if section else tuple(k for k,d in self.pack.params.items()
                                                                   if page_id(d.page, self.pack) not in ('blocks','output'))
        # A group may cover multiple subpages, but never unrelated top-level boards.
        for group in dict.fromkeys(self.groups.values()):
            if any(k in keys for k in getattr(group,'_curve_text',{})):
                pending = read_params(group,self.pack,curves=True)
                values.update({k:v for k,v in pending.items() if k in keys})
        self.pack.resolve(WorldSpec(self.pack.id,self.preset,params=values))
        return values,keys

    def _mark_preset(self, ref, values, section=None):
        values = self._values()
        record = self._library.get(ref) if ref else None
        keys = section_keys(self.pack,section) if section else tuple(values)
        mark = dict(id=preset_ref(ref) if ref else '',name=record['name'] if record else '',
                    digest=_digest(record) if record else '',values={k:deepcopy(values[k]) for k in keys})
        if section:
            self._section_marks[section] = mark
        else:
            self._global_mark, self._global_values = mark,deepcopy(values)
            sections = set(d['page'] for d in record['definitions'].values()) if record else set()
            for page in self._section_marks:
                self._mark_preset(ref if page in sections else '',values,page)

    def _parameters_published(self, previous):
        if previous != self._values():
            self._changed()
        else:
            self._remember()
            self._refresh_preset_labels()

    def _load_parameter_preset(self, ref, section=None):
        try:
            previous = self._values()
            current = WorldSpec(self.pack.id,self.preset,params=previous)
            result = self._library.apply(current,ref,section,pack=self.pack) if ref else reset_section(self.pack,current,section)
            values = self.pack.resolve(result).to_dict()
            keys = (tuple(values) if section is None else tuple(self._library.patch(self._library.get(ref),self.pack,section))
                    if ref else section_keys(self.pack,section))
            self._set_parameter_values(values,keys)
            self.preset = result.preset
            self._mark_preset(ref,values,section)
            self._parameters_published(previous)
        except Exception as exc:
            self._set_status(str(exc))
            self._refresh_preset_labels()

    def _save_library_preset(self, name, section=None):
        try:
            previous = self._values()
            values,keys = self._parameter_snapshot(section)
            ref = self._library.save(WorldSpec(self.pack.id,self.preset,params=values),name,section)
            # Only publish native curves and saved-state after the atomic write succeeds.
            self._set_parameter_values(values,keys)
            committed = self._values()
            self._saved_params.update({k:deepcopy(committed[k]) for k in keys})
            self._mark_preset(ref,values,section)
            self._library_stamp = self._library.stamp()
            self._notice.clear_children()
            self._parameters_published(previous)
            self._set_status(tr('参数预设已保存；规则草稿保留。','Parameter preset saved; content drafts retained.'))
            return ref
        except Exception as exc:
            self._set_status(str(exc))

    def _preset_save_reason(self):
        # Retained for callers of the previous private UI helper.
        return ''

    def _library_name_form(self, action, initial='', *, return_to_library=False):
        if getattr(self,'_library_state',None) is not None:
            self._library_state = dict(self._library_state)
        self._notice.clear_children()
        self._notice.text(tr('预设名称','Preset name'),size=11)
        row = self._notice.row()
        box = textbox(row,initial,fill=1)
        row.button(tr('保存','Save'),size=11,text_scaling=True,on_clicked=click(lambda: action(str(box.get_text()))))
        row.button(tr('取消','Cancel'),size=11,text_scaling=True,
                   on_clicked=click(self._library_return if return_to_library else self._cancel_switch))

    def _library_button(self, row, zh, en, action, *, color=None, enabled=True, tooltip=''):
        button = row.button(tr(zh,en),size=10,text_scaling=True,on_clicked=click(action),tooltip=tooltip)
        button.set_is_enabled(enabled)
        if color:
            rgb = LIBRARY_COLORS[color]
            style = button.target.get_editor_property('widget_style')
            for name, factor, alpha in (('normal',1.,.9),('hovered',1.5,1.),('pressed',.7,1.)):
                brush = getattr(style,name)
                brush.tint_color = unreal.SlateColor(unreal.LinearColor(
                    *(min(1.,v*factor) for v in rgb),alpha))
                setattr(style,name,brush)
            button.target.set_style(style)
        return button

    def _library_refresh(self, state, **changes):
        # Ignore delegates from widgets removed by a search or selection redraw.
        if self._suspend or getattr(self,'_library_state',None) is not state:
            return
        updated = dict(state,**changes)
        if updated != state:
            self._library_manager(**updated)

    def _library_return(self, selected=None):
        state = dict(getattr(self,'_library_state',None) or {})
        if selected is not None:
            state['selected'] = selected
        self._library_manager(**state)

    def _library_manager(self, search='', scope='*', include_all=False, selected=''):
        scopes = {'*':tr('全部范围','All scopes'),'whole':tr('整套','Whole')}
        scopes.update({k:self._page_label(k) for k in self._section_marks})
        scope = scope if scope in scopes else '*'
        entries = [e for e in self._library.entries(self.pack,None if scope=='whole' else scope,include_all=include_all)
                   if search.casefold() in e['name'].casefold()]
        by_ref = {e['ref']:e for e in entries}
        selected = selected if selected in by_ref else next(iter(by_ref),'')
        form = getattr(self, '_library_form', None)
        if form is None or form['state'] is not getattr(self, '_library_state', None):
            self._notice.clear_children()
            state = self._library_state = {}
            form = self._library_form = dict(state=state)
            row = self._notice.row()
            row.text(tr('搜索预设','Search presets'),size=10, align=(1,2))
            form['search'] = textbox(row,search,fill=1,on_text_committed=lambda value,reason:
                self._library_refresh(state,search=str(value)))
            def change(**changes):
                self._library_refresh(state,search=str(form['search'].get_text()),**changes)
            form['scope'] = choice(row,scopes,scope,lambda value,reason:
                change(scope=str(value)) if str(value) in scopes else None)
            self._library_button(row,'取消','Cancel',self._cancel_switch,color='cancel')
            row = self._notice.row()
            form['entries'] = choice(row,{},'',lambda value,reason:
                change(selected=str(value)) if str(value) in form['by_ref'] else None,fill=1)
            form['buttons'] = {}
            def button(parent, key, zh, en, fn, **kwargs):
                form['buttons'][key] = self._library_button(parent,zh,en,fn,**kwargs)
            def current():
                return state['selected']
            button(row,'load','加载','Load',lambda:self._load_parameter_preset(
                current(),form['by_ref'][current()]['section'] if state['scope'] in ('*','whole') else state['scope']))
            form['advanced'] = row.checkbox(tr('高级功能','Advanced functions'),size=10,
                tooltip=tr('显示全部条目（含不兼容）及管理操作',
                           'Show all entries (including incompatible) and management actions'))
            form['advanced'].on_check_state_changed.add_callable(lambda checked:change(include_all=checked))
            actions = form['actions'] = self._notice.row()
            edit = actions.row()
            button(edit,'update','更新','Update',lambda:self._library_confirm('update',current()),color='edit')
            def name_form(action):
                ref = current()
                self._library_name_form(lambda name:self._library_action(action,ref,name),
                    form['by_ref'][ref]['name'],return_to_library=True)
            button(edit,'rename','重命名','Rename',lambda:name_form('rename'),color='edit')
            button(edit,'copy','另存','Save as',lambda:name_form('copy'),color='edit')
            actions.text('｜',size=10)
            files = actions.row()
            self._library_button(files,'导入JSON','Import JSON',self._library_pick_file,color='file')
            button(files,'export','导出JSON','Export JSON',lambda:self._library_pick_file(current()),color='file')
            actions.text('｜',size=10)
            button(actions,'delete','删除','Delete',lambda:self._library_confirm('delete',current()),color='delete')
            form['details'] = self._notice.text('',size=9,wrap=True)
        suspended, self._suspend = self._suspend, True
        try:
            form['state'].update(search=search,scope=scope,include_all=include_all,selected=selected)
            form['by_ref'] = by_ref
            if str(form['search'].get_text()) != search:
                form['search'].set_text(search)
            refresh_choice(form['scope'],scopes,scope)
            refresh_choice(form['entries'],{e['ref']:unreal.Text('{name}{error}').format(
                name=self._entry_label(e),error='' if e['compatible'] else tr(' · 不兼容',' · Incompatible'))
                for e in entries},selected)
            form['entries']['widget'].set_is_enabled(bool(entries))
            form['advanced'].set_is_checked(include_all)
            form['actions'].hide(not include_all)
            entry = by_ref.get(selected,{})
            compatible,valid,user = bool(entry.get('compatible')),bool(entry.get('valid')),entry.get('source')=='library'
            enabled = dict(load=compatible,update=user and compatible,rename=user and valid,
                           copy=valid,export=valid,delete=user)
            for key, button in form['buttons'].items():
                button.set_is_enabled(enabled[key])
                reason = (entry.get('error') or tr('资源包预设只读','Resource pack presets are read-only')
                          if key in ('update','rename','delete') else entry.get('error') or
                          tr('没有有效预设','No valid preset'))
                button.set_tool_tip_text('' if enabled[key] else reason)
            form['details'].set_text(
                f"{entry['pack']} / {entry['section'] or 'whole'} / {entry['ref']}\n{entry.get('path') or ''}\n{entry['error']}"
                if entry else tr('没有匹配的预设','No matching presets'))
        finally:
            self._suspend = suspended

    def _library_pick_file(self, ref=None):
        try:
            if ref:
                filename = safe_name(self._library.get(ref)['name'])
                filename = filename if filename.lower().endswith('.json') else filename+'.json'
                path = mineprep.asksaveasfilename(title=str(tr('导出预设','Export preset')),
                    defaultextension='.json',initialfile=filename,filetypes=[('JSON','*.json')])
                if path:
                    if not Path(path).suffix:
                        path = str(path)+'.json'
                    # The native Save dialog already confirms replacing its chosen target.
                    self._library_action('overwrite',ref,path)
            else:
                path = mineprep.askopenfilename(title=str(tr('导入预设','Import preset')),filetypes=[('JSON','*.json')])
                if path:
                    self._library_action('import',None,path)
        except Exception as exc:
            self._set_status(str(exc))

    def _library_confirm(self, action, ref, path=None):
        if getattr(self,'_library_state',None) is not None:
            self._library_state = dict(self._library_state)
        self._notice.clear_children()
        label = {'update':tr('更新预设','Update preset'),'delete':tr('删除预设','Delete preset'),
                 'overwrite':tr('覆盖文件','Overwrite file')}.get(action,action)
        self._notice.text(unreal.Text('{question} {action}: {target}').format(
            question=tr('确认此操作？','Confirm this operation?'),action=label,target=path or ref),size=11,wrap=True)
        row = self._notice.row()
        row.button(tr('确认','Confirm'),size=11,text_scaling=True,on_clicked=click(lambda:self._library_action(action,ref,path)))
        row.button(tr('取消','Cancel'),size=11,text_scaling=True,on_clicked=click(self._library_return))

    def _library_action(self, action, ref, value=None):
        try:
            if action=='update':
                record = self._library.get(ref)
                values,keys = self._parameter_snapshot(record['section'])
                self._library.update(ref,WorldSpec(self.pack.id,self.preset,params=values))
                keys = tuple(self._library.get(ref)['params'])
                previous = self._values()
                self._set_parameter_values(values,keys)
                committed = self._values()
                self._saved_params.update({k:deepcopy(committed[k]) for k in keys})
                self._parameters_published(previous)
            elif action=='delete':
                self._library.delete(ref)
            elif action=='rename':
                self._library.rename(ref,value)
            elif action=='copy':
                ref = self._library.copy(ref,value)
            elif action=='import':
                ref = self._library.import_json(value)
            elif action in ('export','overwrite'):
                try:
                    self._library.export_json(ref,value,overwrite=action=='overwrite')
                except FileExistsError:
                    self._library_confirm('overwrite',ref,value)
                    return
            self._library_stamp = self._library.stamp()
            self._refresh_preset_labels()
            self._remember()
            self._library_return(selected=ref or '')
        except Exception as exc:
            self._set_status(str(exc))

    def _save_form(self, preset_only=False, section=None):
        if preset_only:
            self._library_name_form(lambda name:self._save_library_preset(name,section))
            return
        self._library_state = None
        self._notice.clear_children()
        managed = self.pack.root.parent == self.draft.user_root
        self._notice.text(tr('保存资源包', 'Save Pack'), size=11)
        def field(row, zh, en, value):
            row.sizebox(width=92).text(tr(zh, en), size=10)
            return textbox(row, value, fill=1)
        row = self._notice.row()
        pack_box = field(row, '资源包 ID', 'Pack ID', self.pack.id if managed else 'my_world')
        name_box = field(row, '资源包名称', 'Pack Name', name_text(self.pack.name) if managed else tr('我的世界', 'My world'))
        row = self._notice.row()
        preset_box = field(row, '预设 ID', 'Preset ID', self.preset if managed else 'user_default')
        preset_name_box = field(row, '预设显示名', 'Preset name',
                                name_text(self.pack.presets[self.preset].name) if self.preset else tr('用户默认', 'User default'))
        target = self._notice.text('', size=9, wrap=True)
        def show_target():
            pack_id = str(pack_box.get_text()).strip()
            directory = self.draft.user_root / pack_id
            action = tr('更新现有用户资源包：{path}', 'Update user pack: {path}') if managed and pack_id == self.pack.id else \
                     tr('新建继承资源包：{path}', 'Create derived pack: {path}')
            target.set_text(action.format(path=str(directory)))
        pack_box.on_text_changed.add_callable(lambda _: show_target())
        preset_box.on_text_changed.add_callable(lambda _: show_target())
        show_target()
        self._notice.text(tr('保存规则差异和当前参数；群系、地表、方块、植被由所有预设共享。原资源包不被覆盖，同 ID 用户资源包与预设会更新。',
                             'Save content differences and parameters. All presets share biomes, surfaces, blocks and vegetation. The source pack is preserved; matching user pack and preset IDs are updated.'),
                          size=9, wrap=True)
        row = self._notice.row()
        row.button(tr('确认保存', 'Confirm save'), text_scaling=True, size=11, on_clicked=click(lambda: self._save(
            str(pack_box.get_text()).strip(), str(preset_box.get_text()).strip(),
            str(name_box.get_text()), preset_name=str(preset_name_box.get_text()))))
        row.button(tr('取消', 'Cancel'), text_scaling=True, size=11, on_clicked=click(self._cancel_switch))

    def _save(self, pack_id, preset, name, preset_only=False, preset_name=None, section=None):
        if preset_only:
            return self._save_library_preset(preset_name or name or preset,section)
        try:
            if not self.apply_curves():
                return
            if self._errors:
                raise ValueError(next(iter(self._errors.values())))
            pack_name = self.pack.name if name == str(name_text(self.pack.name)) else {'zh': name, 'en': name}
            saved = self.draft.save(pack_id, name=pack_name, preset=preset, params=self._values(), preset_name=preset_name)
            pending = self._pending_switch
            self._pending_switch = None
            self.cancel_job()
            self._select_pack(saved.pack.id, preset, draft=saved)
            self._changed()
            self.redraw()
            self._set_status(tr('用户资源包已保存；请重新准备资源。', 'User pack saved. Prepare resources again.'))
            if pending:
                pending()
        except Exception as exc:
            self._set_status(str(exc))
