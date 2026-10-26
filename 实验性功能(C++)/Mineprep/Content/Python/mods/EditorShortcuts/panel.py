# -*- coding: utf-8 -*-
"""自定义快捷键管理面板：支持快捷键绑定、提示说明编辑与内联 Python 代码折叠框。"""
from functools import partial
import unreal
import mineprep

from .props import Settings
from . import ops


def compact_icon_button(box, text: str, on_clicked, tooltip: str = '', text_color=None, size: int = 12, text_padding=(-0.5, 1.5, 0, 0)):
    """创建紧凑小方块按钮。"""
    kwargs = {
        'size': size,
        'text_padding': text_padding,
        'on_clicked': on_clicked,
        'tooltip': tooltip,
        'align': (0, 0),
    }
    if text_color is not None:
        kwargs['text_color'] = text_color

    btn = box.button(text, **kwargs)
    target = btn.target
    style = target.get_editor_property('widget_style')
    style.normal_padding = unreal.Margin(0, 0, 0, 0)
    style.pressed_padding = unreal.Margin(0, 1, 0, 0)
    target.set_editor_property('widget_style', style)
    return btn


class EditorShortcuts(mineprep.Mod):
    """Mineprep 编辑器快捷键管理面板。"""
    _unique_ = True
    _label_ = mineprep.bilingual("自定义快捷键", "Editor Shortcuts")
    _menu_ = 'modules'

    def __init__(self, context=None):
        self.settings = Settings()
        self.expanded_keys = set()
        self.code_rows = {}
        super().__init__(context)

    def draw(self, context=None):
        layout = self.layout
        scalebox = layout.scalebox(scale=self.settings.scale)
        table = scalebox.col(fill=True)
        if ops.get_subsystem() is None:
            table.text(mineprep.bilingual(
                '未启用 Mineprep C++ 插件，无法绑定全局快捷键；仍可编辑并手动执行 Python 代码。',
                'Global hotkeys require the Mineprep C++ plugin; editing and manually running Python code remain available.',
            ), size=10, wrap=True, padding=5)

        # -------------------------------------------------------------
        # 1. 表头行
        # -------------------------------------------------------------
        header = table.row(padding=(4, 4))
        header.text(mineprep.bilingual('触发 / 名称', 'Trigger / Name'), size=13, fill=1.3, align=(1, 2))
        header.spacer(size=(8, 1))
        header.text(mineprep.bilingual('快捷键 (点击设置)', 'Shortcut (Click to Set)'), size=13, fill=1.2, align=(1, 2))
        header.spacer(size=(8, 1))
        header.text(mineprep.bilingual('提示说明', 'Tooltip Description'), size=13, fill=2.1, align=(1, 2))
        header.spacer(size=(6, 1))
        compact_icon_button(
            header,
            '{-}',
            text_padding=0,
            on_clicked=self.on_toggle_all_code_clicked,
            tooltip=mineprep.bilingual('全体展开 / 收起代码', 'Expand / Collapse All Code'),
            text_color=unreal.LinearColor(0.5, 0.8, 1.0, 1.0),
            size=9,
        )
        header.spacer(size=(4, 1))
        compact_icon_button(
            header,
            '+',
            text_padding=0,
            on_clicked=self.on_add_clicked,
            tooltip=mineprep.bilingual('添加新快捷键', 'Add New Shortcut'),
            text_color=unreal.LinearColor(0.35, 0.9, 0.45, 1.0),
            size=10,
        )

        # -------------------------------------------------------------
        # 2. 快捷键行列表（双行排版，第一行操作，第二行折叠代码）
        # -------------------------------------------------------------
        self.code_rows = {}
        shortcuts = ops.get_shortcuts()
        for name, info in shortcuts.items():
            chord_text = info.get('chord_text', '')
            tooltip = info.get('tooltip', '')
            code_text = info.get('code', '')

            item_box = table.col(padding=(0, 1.5))

            # --- 第一行：主功能行 ---
            row1 = item_box.row()

            # 左侧：触发按钮 (►) + 名称文本框
            name_cell = row1.row(fill=1.3, align=(0, 2))
            compact_icon_button(
                name_cell,
                '►',
                text_padding=0,
                on_clicked=partial(self.on_trigger_clicked, name),
                tooltip=mineprep.bilingual(f'点击执行: {name}', f'Run: {name}'),
            )
            name_cell.spacer(size=(2, 1))

            name_box = name_cell.textbox(
                name,
                hint=mineprep.bilingual('输入按键名称', 'Enter name'),
                fill=True,
                align=(0, 2),
                padding=(0, 1),
            )
            name_target = name_box.target
            name_target.on_text_committed.add_callable(
                partial(self.on_name_committed, name, name_target)
            )

            row1.spacer(size=(8, 1))

            # 中间：按键录入选择器 (EditorUtilityInputKeySelector)
            selector = row1.custom(unreal.EditorUtilityInputKeySelector, fill=1.2, align=(0, 2))
            sel_target = selector.target
            sel_target.set_allow_modifier_keys(True)
            sel_target.set_allow_gamepad_keys(False)
            chord = unreal.InputChord()
            if chord_text:
                chord.import_text(chord_text)
            sel_target.set_selected_key(chord)
            sel_target.on_key_selected.add_callable(
                partial(self.on_key_selected, name, sel_target)
            )

            row1.spacer(size=(8, 1))

            # 右侧：提示说明输入框
            tip_box = row1.textbox(
                tooltip,
                hint=mineprep.bilingual('输入功能提示说明', 'Enter tooltip'),
                fill=2.1,
                align=(0, 2),
                padding=(0, 1),
            )
            tip_target = tip_box.target
            tip_target.on_text_committed.add_callable(
                partial(self.on_tooltip_committed, name, tip_target)
            )

            row1.spacer(size=(6, 1))

            # --- 第二行：代码编辑区 (受 self.expanded_keys 状态控制) ---
            code_row = item_box.row(padding=(24, 2, 2, 4))
            self.code_rows[name] = code_row
            is_expanded = name in self.expanded_keys
            code_row.target.set_visibility(unreal.SlateVisibility.VISIBLE if is_expanded else unreal.SlateVisibility.COLLAPSED)

            code_box = code_row.textbox(
                code_text,
                hint=mineprep.bilingual(
                    '# 输入 Python 代码（已自动导入 unreal, mineprep），留空在蓝图中触发对应函数',
                    '# Enter Python code (unreal, mineprep imported). Empty to trigger BP function.'
                ),
                fill=True,
                align=(0, 0),
            )
            code_target = code_box.target
            code_target.on_text_committed.add_callable(
                partial(self.on_code_committed, name, code_target)
            )

            # 代码展开/收起按钮 ({-})
            compact_icon_button(
                row1,
                '{-}',
                text_padding=0,
                on_clicked=partial(self.toggle_code_visibility, name, code_row),
                tooltip=mineprep.bilingual(f'展开/收起 [{name}] 的 Python 代码', f'Toggle Python code for [{name}]'),
                text_color=unreal.LinearColor(0.5, 0.8, 1.0, 1.0),
                size=9,
            )

            row1.spacer(size=(4, 1))

            # 最右侧：删除按钮 (✕)
            compact_icon_button(
                row1,
                '✕',
                text_padding=0,
                on_clicked=partial(self.on_delete_clicked, name),
                tooltip=mineprep.bilingual(f'删除快捷键: {name}', f'Delete shortcut: {name}'),
                text_color=unreal.LinearColor(0.85, 0.4, 0.4, 1.0),
            )

        # -------------------------------------------------------------
        # 3. 底部控制栏（左下角缩放，右下角操作按钮）
        # -------------------------------------------------------------
        bottom_row = layout.row(align=(0, 2), padding=(2, 6, 2, 2))

        # 左下角：缩放控制
        scale_col = bottom_row.col(fill=1.0, align=(0, 2))
        scale_col.prop(
            self.settings,
            'scale',
            mineprep.bilingual('缩放', 'Scale'),
            align=(1, 3),
            on_property_changed=lambda _: scalebox.set('UserSpecifiedScale', self.settings.scale)
        )

        bottom_row.spacer(size=(12, 1))

        # 右下角按钮1：还原所有快捷键至初始状态
        bottom_row.button(
            mineprep.bilingual('还原默认', 'Reset Defaults'),
            size=11,
            text_padding=3,
            align=(2, 2),
            tooltip=mineprep.bilingual('将所有快捷键重置为初始预设状态', 'Reset all shortcuts to initial defaults'),
            on_clicked=self.on_reset_all_clicked,
        )

        bottom_row.spacer(size=(6, 1))

        # 右下角按钮2：打开自定义快捷键蓝图
        bottom_row.button(
            mineprep.bilingual('打开蓝图', 'Open BP'),
            size=11,
            text_padding=3,
            align=(2, 2),
            tooltip=mineprep.bilingual('在资产编辑器中打开快捷键蓝图 (/Mineprep/Mineprep自定义快捷键)', 'Open shortcuts blueprint in editor'),
            on_clicked=self.on_open_blueprint_clicked,
        )

    def on_reset_all_clicked(self):
        """还原所有快捷键至初始预设状态并刷新面板。"""
        ops.reset_to_defaults()
        self.expanded_keys.clear()
        self.redraw()

    def on_open_blueprint_clicked(self):
        """在资产编辑器中打开自定义快捷键蓝图。"""
        success = ops.open_blueprint()
        if not success:
            mineprep.warn(
                mineprep.bilingual("打开自定义快捷键蓝图失败，请检查资产是否存在", "Failed to open hotkey blueprint")
            )

    def toggle_code_visibility(self, name: str, code_row):
        """展开或收起代码编辑行。"""
        if name in self.expanded_keys:
            self.expanded_keys.remove(name)
            code_row.target.set_visibility(unreal.SlateVisibility.COLLAPSED)
        else:
            self.expanded_keys.add(name)
            code_row.target.set_visibility(unreal.SlateVisibility.VISIBLE)

    def on_toggle_all_code_clicked(self):
        """全体展开或收起所有快捷键的代码编辑行。"""
        all_keys = set(ops.get_shortcuts().keys())
        # 若当前所有快捷键都已展开，则收起全部；否则展开全部
        all_expanded = bool(all_keys and all_keys.issubset(self.expanded_keys))
        if all_expanded:
            self.expanded_keys.clear()
            target_visibility = unreal.SlateVisibility.COLLAPSED
        else:
            self.expanded_keys = set(all_keys)
            target_visibility = unreal.SlateVisibility.VISIBLE

        for code_row in self.code_rows.values():
            code_row.target.set_visibility(target_visibility)

    def on_trigger_clicked(self, name: str):
        """点击触发按钮执行对应快捷键程序。"""
        ops.execute_shortcut(name)

    def on_code_committed(self, name: str, box_target, new_text: str, commit_method: unreal.TextCommit):
        """代码提交时静态语法编译校验（自动注入 import 环境）。"""
        new_code = str(new_text).strip()
        old_code = ops.get_item(name).get('code', '').strip()

        if commit_method == unreal.TextCommit.ON_CLEARED:
            box_target.set_text(old_code)
            return

        if new_code == old_code:
            return

        is_valid, err_msg = ops.validate_code(new_code, name)
        if not is_valid:
            mineprep.prints(
                mineprep.bilingual(f"[{name}] 语法错误: {err_msg}，已还原", f"Syntax error in [{name}]: {err_msg}, reverted"),
                color=unreal.LinearColor(1.0, 0.3, 0.3, 1.0),
                duration=5,
            )
            box_target.set_text(old_code)
            return

        ops.update_code(name, new_code)
        unreal.log(f"[Mineprep] [{name}] 代码校验通过并已保存")

    def on_name_committed(self, old_name: str, box_target, new_text: str, commit_method: unreal.TextCommit):
        """名称提交时检测唯一性冲突并重命名主键。"""
        new_name = str(new_text).strip()

        if commit_method == unreal.TextCommit.ON_CLEARED:
            box_target.set_text(old_name)
            return

        if not new_name:
            mineprep.prints(
                mineprep.bilingual("名称不能为空，已还原", "Name cannot be empty, reverted"),
                color=unreal.LinearColor(1.0, 0.4, 0.4, 1.0),
                duration=3,
            )
            box_target.set_text(old_name)
            return

        if new_name == old_name:
            return

        if ops.check_name_conflict(old_name, new_name):
            mineprep.prints(
                mineprep.bilingual(f"名称冲突：'{new_name}' 已存在，已还原", f"Name conflict: '{new_name}' already exists, reverted"),
                color=unreal.LinearColor(1.0, 0.3, 0.3, 1.0),
                duration=4,
            )
            box_target.set_text(old_name)
            return

        # 更新展开集合中的键名
        if old_name in self.expanded_keys:
            self.expanded_keys.remove(old_name)
            self.expanded_keys.add(new_name)

        ops.rename_shortcut(old_name, new_name)
        self.redraw()
        unreal.log(f"[Mineprep] 已重命名快捷键: [{old_name}] -> [{new_name}]")

    def on_tooltip_committed(self, name: str, box_target, new_text: str, commit_method: unreal.TextCommit):
        """提示信息提交。"""
        new_tip = str(new_text).strip()
        old_tip = ops.get_item(name).get('tooltip', '')

        if commit_method == unreal.TextCommit.ON_CLEARED:
            box_target.set_text(old_tip)
            return

        if new_tip == old_tip:
            return

        ops.update_tooltip(name, new_tip)
        unreal.log(f"[Mineprep] 已更新 [{name}] 的提示信息")

    def on_key_selected(self, name: str, sel_target, selected_chord: unreal.InputChord):
        """按键录入提交时检测面板内按键冲突。"""
        new_chord_text = selected_chord.export_text()
        old_chord_text = ops.get_item(name).get('chord_text', '')

        if selected_chord.key.export_text() == 'None':
            ops.update_chord_text(name, new_chord_text)
            mineprep.prints(
                mineprep.bilingual(f"已清除 [{name}] 的按键绑定", f"Cleared hotkey for [{name}]"),
                color=unreal.LinearColor(0.8, 0.8, 0.8, 1.0),
                duration=3,
            )
            return

        if new_chord_text == old_chord_text:
            return

        conflict, conflict_name = ops.check_chord_conflict(name, new_chord_text)
        if conflict:
            mineprep.prints(
                mineprep.bilingual(f"快捷键冲突：该按键已被 [{conflict_name}] 占用，已还原", f"Key conflict: chord used by [{conflict_name}], reverted"),
                color=unreal.LinearColor(1.0, 0.3, 0.3, 1.0),
                duration=4,
            )
            old_chord = unreal.InputChord()
            if old_chord_text:
                old_chord.import_text(old_chord_text)
            sel_target.set_selected_key(old_chord)
            return

        ops.update_chord_text(name, new_chord_text)
        mineprep.prints(
            mineprep.bilingual(f"已设置 [{name}] 快捷键 -> {new_chord_text}", f"Set [{name}] hotkey -> {new_chord_text}"),
            color=unreal.LinearColor(0.95, 0.85, 0.2, 1.0),
            duration=3,
        )

    def on_delete_clicked(self, name: str):
        """删除该行快捷键并立即刷新面板。"""
        ops.delete_shortcut(name)
        if name in self.expanded_keys:
            self.expanded_keys.remove(name)
        self.code_rows.pop(name, None)
        self.redraw()
        mineprep.prints(
            mineprep.bilingual(f"已删除快捷键: [{name}]", f"Deleted shortcut: [{name}]"),
            color=unreal.LinearColor(0.95, 0.45, 0.35, 1.0),
            duration=3,
        )

    def on_add_clicked(self):
        """点击表头加号添加一行新快捷键并立即刷新面板。"""
        new_name = ops.add_shortcut()
        self.redraw()
        mineprep.prints(
            mineprep.bilingual(f"已添加新快捷键: [{new_name}]", f"Added shortcut: [{new_name}]"),
            color=unreal.LinearColor(0.35, 0.9, 0.45, 1.0),
            duration=3,
        )

