"""MC动画转换器面板（动作库浏览器 + 跨物种表情预设与自动眨眼）。"""
from functools import partial
from pathlib import Path

import mineprep
from mineprep import i18n
import unreal

from . import face_presets, library, ops, util
from .props import AutoBlinkProps, FaceProps, Props

_ACTIVE_RGBA = (0.28, 0.65, 1.0, 1.0)
_NORMAL_RGBA = (1.0, 1.0, 1.0, 1.0)
_PRIMARY_RGBA = (0.24, 0.58, 0.96, 1.0)
_CARD_RGBA = (0.05, 0.05, 0.06, 0.72)


def _color(rgba):
    return unreal.LinearColor(*rgba)


def _alive(node) -> bool:
    target = getattr(node, 'target', None)
    if not target:
        return False
    try:
        return bool(unreal.SystemLibrary.is_valid(target))
    except Exception:
        return False


_SOURCE_TABS = (
    ('all', i18n('全部', 'All')),
    ('custom', i18n('自制', 'Custom')),
    ('vanilla', i18n('原版', 'Vanilla')),
    ('external', i18n('外部文件', 'External')),
)

_SKELETON_LABELS = {
    'biped': i18n('玩家 / 人形', 'Player / Biped'),
    'quadruped': i18n('通用四足', 'Quadruped'),
    'camel': i18n('骆驼', 'Camel'),
    'frog': i18n('青蛙', 'Frog'),
    'warden': i18n('监守者', 'Warden'),
    'pig': i18n('猪', 'Pig'),
    'creaking': i18n('嘎枝', 'Creaking'),
    'axolotl_baby': i18n('幼年美西螈', 'Baby Axolotl'),
    'other': i18n('其他骨架', 'Other'),
}

_PRESET_CATEGORIES = (
    ('emotion', i18n('情绪预设（默认重置眉/嘴/眼形，保留视线与眨眼）', 'Emotions (resets emotion curves, keeps gaze & blink)')),
    ('gaze', i18n('视线方向（叠加眼球，不覆盖嘴/眉）', 'Gaze (layer eyes without overwriting mouth/brows)')),
    ('blink', i18n('眨眼与单眼（叠加眼睑）', 'Blink & Wink (layer eyelids)')),
)

_GAZE_ARROWS = {
    'look_left': '← ',
    'look_right': '→ ',
    'look_up': '↑ ',
    'look_down': '↓ ',
}


def _fmt_text(pattern: str, **kwargs):
    """Build a culture-reactive unreal.Text while staying safe under offline Lazy stubs."""
    text_cls = getattr(unreal, 'Text', None)
    if text_cls is None or not callable(getattr(text_cls, 'format', None)):
        return pattern.format(**kwargs)
    return text_cls(pattern).format(**kwargs)


def _join_text(sep: str, *parts):
    """Join mixed unreal.Text / str items into a live culture-reactive unreal.Text."""
    items = [p for p in parts if p is not None and str(p) != '']
    if not items:
        return ''
    if len(items) == 1:
        return items[0]
    pattern = sep.join(f'{{p{i}}}' for i in range(len(items)))
    return _fmt_text(pattern, **{f'p{i}': item for i, item in enumerate(items)})


def short_clip_name(clip: str) -> str:
    """Return a concise readable display name while keeping the full canonical key intact."""
    text = str(clip or '').strip()
    for prefix in ('animation.mineprep.', 'animation.'):
        if text.startswith(prefix) and len(text) > len(prefix):
            return text[len(prefix):]
    return text


def skeleton_group_key(skeleton: str | None) -> str:
    """Normalize raw library skeleton identifiers into clean UI filter buckets."""
    raw = str(skeleton or '').strip().lower()
    if not raw:
        return 'other'
    if raw.startswith('minecraft:'):
        raw = raw[len('minecraft:'):]
    if '#' in raw:
        raw = raw.split('#', 1)[0]
    if raw in ('bedrock_player', 'player', 'biped'):
        return 'biped'
    return raw


def skeleton_group_label(group_key: str):
    if group_key in _SKELETON_LABELS:
        return _SKELETON_LABELS[group_key]
    return group_key.replace('_', ' ').title()


def _build_memory_catalog(records: dict[str, dict], namespace: str):
    """Build a read-only Mineprep memory localization catalog from `{key: record}` entries."""
    i18n_cls = getattr(mineprep, 'Internationalization', None)
    if not records or i18n_cls is None:
        return None
    try:
        return i18n_cls.from_data(records, namespace=namespace)
    except Exception:
        return None


def _lookup_localized(catalog, key: str, record: dict | None, fallback: str):
    if catalog is not None and record:
        try:
            return catalog(fallback, key=key)
        except Exception:
            pass
    if record:
        return record.get('zh') or record.get('en') or fallback
    return fallback


def build_clip_entries(path: str = '') -> list[dict]:
    """Build normalized clip entry dicts from either an external file or the dual library index."""
    if path:
        file_name = Path(path).name
        fmt = 'BBModel' if str(path).lower().endswith('.bbmodel') else 'External'
        return [
            {
                'id': str(i),
                'source': 'external',
                'path': Path(path),
                'file': file_name,
                'clip': clip,
                'short': short_clip_name(clip),
                'name': None,
                'skeleton': '',
                'group': 'external',
                'loop': None,
                'format': fmt,
                'desc': str(path),
            }
            for i, clip in enumerate(library.clips(path))
        ]

    entries = []
    for i, item in enumerate(library.catalog()):
        file_rel = str(item.get('file') or '')
        fmt = 'Java' if file_rel.lower().endswith('.clip.json') else 'Bedrock'
        entries.append({
            'id': str(i),
            'source': item['source'],
            'path': item['path'],
            'file': file_rel,
            'clip': item['clip'],
            'short': short_clip_name(item['clip']),
            'name': item.get('name'),
            'skeleton': item.get('skeleton') or '',
            'skeleton_mode': item.get('skeleton_mode'),
            'group': skeleton_group_key(item.get('skeleton')),
            'loop': item.get('loop'),
            'format': fmt,
            'desc': item.get('source_version') or '',
        })
    return entries


def filter_clip_entries(entries: list[dict], *, source: str = 'all', group: str = 'all', query: str = '') -> list[dict]:
    """Filter normalized clip entries by source, skeleton group, and free-text query."""
    q = str(query or '').strip().lower()
    out = []
    for entry in entries:
        if source != 'all' and entry['source'] != source:
            continue
        if group != 'all' and entry['group'] != group:
            continue
        if q:
            name_rec = entry.get('name') or {}
            name_terms = [v for k, v in name_rec.items() if not str(k).startswith('_') and isinstance(v, str)]
            hay = ' '.join((
                entry['clip'], entry['short'], entry['file'],
                entry['skeleton'], entry['group'], entry['desc'], *name_terms,
            )).lower()
            if q not in hay:
                continue
        out.append(entry)
    return out


class MCAnimConverter(mineprep.Mod):
    _label_ = i18n('MC动画转换器', 'Minecraft Animation Converter')
    _unique_ = True

    def __init__(self, context=None):
        self._runner = None
        self._sel_hook = None
        self._clip_loc = None
        self._preset_loc = None

        self.props = Props()
        self.face_props = FaceProps()
        self.blink_props = AutoBlinkProps()

        self.active_tab = 0
        self.source_filter = 'external' if util.json_file(self.props) else 'all'
        self.skeleton_filter = 'all'
        self.search_query = ''
        self.skeleton_mode = 'auto'
        self.face_reset_mode = 'auto'

        self.entries = []
        self.clips = {}
        self.clip_id = None
        self._clip_buttons = {}
        self._clip_groups = {}

        self.presets = face_presets.load_presets(reload=True)
        self._rebuild_preset_loc()
        self.preset_id = self.presets[0]['id'] if self.presets else None
        self._preset_buttons = {}
        self._tab_buttons = {}
        self._source_buttons = {}

        super().__init__(context)

    def _rebuild_preset_loc(self):
        records = {f"preset.{p['id']}": p['name'] for p in self.presets if p.get('name')}
        self._preset_loc = _build_memory_catalog(records, 'MCAnimConverter.presets')

    def _rebuild_clip_loc(self):
        records = {f"clip.{e['clip']}": e['name'] for e in self.entries if e.get('name')}
        self._clip_loc = _build_memory_catalog(records, 'MCAnimConverter.clips')

    def _clip_display_text(self, entry: dict):
        return _lookup_localized(self._clip_loc, f"clip.{entry['clip']}", entry.get('name'), entry['short'])

    def _preset_display_text(self, preset: dict):
        return _lookup_localized(self._preset_loc, f"preset.{preset['id']}", preset.get('name'), preset['id'])

    def draw(self, context=None):
        frame = self.layout.sizebox(900, 600, padding=0)
        root = frame.col(align=(0, 0), padding=8)

        # --- Top Bar: Mode Tabs + Refresh ---
        topbar = root.row(padding=(0, 4))
        self._tab_buttons = {
            0: topbar.button(i18n('动作导入', 'Animations'), size=12, padding=(0, 0, 6, 0),
                             on_clicked=partial(self._set_tab, 0)),
            1: topbar.button(i18n('表情预设', 'Facial Presets'), size=12, padding=(0, 0, 6, 0),
                             on_clicked=partial(self._set_tab, 1)),
        }
        topbar.spacer(fill=1)
        topbar.button(i18n('刷新', 'Refresh'), size=11, on_clicked=self._refresh_all)

        # --- Main Split Workspace ---
        split = root.splitter(ratio=0.58, limits=(0.40, 0.76), fill=1)

        # Left Pane Switcher
        self.left_switcher = split.first.switcher(align=(0, 0), fill=1)
        self._build_anim_browser(self.left_switcher.col(align=(0, 0), padding=(0, 4, 6, 0)))
        self._build_face_studio(self.left_switcher.col(align=(0, 0), padding=(0, 4, 6, 0)))

        # Right Pane: Shared Actor Picker + FollowSelection + Mode Inspector Switcher
        right = split.second.col(align=(0, 0), fill=1, padding=(6, 4, 0, 0))
        right.prop(
            self.props,
            properties=['Actor', 'FollowSelection'],
            on_property_changed=self.on_props,
            pass_rootname=True,
        )
        self.right_switcher = right.switcher(align=(0, 0), fill=1)
        self._build_anim_inspector(self.right_switcher.col(align=(0, 0)))
        self._build_face_inspector(self.right_switcher.col(align=(0, 0)))

        # --- Bottom Status Footer ---
        self.status_text = root.text('', size=10, wrap=True, padding=(2, 4, 2, 0))

        self._bind_selection()
        self._sync_from_selection()
        self.update_clips()
        self._refresh_face_inspector()
        self._set_tab(self.active_tab)

    # ------------------------------------------------------------------
    # Viewport Selection Delegate (Follows Hair.py pattern)
    # ------------------------------------------------------------------

    def _bind_selection(self):
        self._unbind_selection()
        try:
            sel = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).get_selection_set()
        except Exception:
            return
        if not sel:
            return

        def _on_sel_changed(_selection_set=None):
            if not _alive(getattr(self, 'status_text', None)):
                self._unbind_selection()
                return
            self._sync_from_selection()

        sel.on_selection_change.add_callable(_on_sel_changed)
        self._sel_hook = (sel, _on_sel_changed)

    def _unbind_selection(self):
        hook = getattr(self, '_sel_hook', None)
        if not hook:
            return
        sel, cb = hook
        try:
            sel.on_selection_change.remove_callable(cb)
        except Exception:
            pass
        self._sel_hook = None

    def _sync_from_selection(self):
        if not bool(getattr(self.props, 'FollowSelection', False)):
            return
        try:
            sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
            selected = list(sub.get_selected_level_actors() or ()) if sub else []
        except Exception:
            return
        target = next((a for a in selected if util.is_skm_actor(a)), None)
        if target is None or target == self.props.Actor:
            return
        self.props.Actor = target
        if self.clip_id is not None and self.clip_id in self.clips:
            util.sync_asset_names(self.props, self.selected_clip()[1])

    # ------------------------------------------------------------------
    # Tab 1: Animation Browser & Inspector
    # ------------------------------------------------------------------

    def _build_anim_browser(self, parent):
        src_row = parent.row(padding=(0, 0, 0, 4))
        self._source_buttons = {}
        for key, label in _SOURCE_TABS:
            btn = src_row.button(
                label, size=11, padding=(0, 0, 4, 0),
                on_clicked=partial(self._set_source, key),
            )
            self._source_buttons[key] = btn

        self.lib_filter_row = parent.row(padding=(0, 2, 0, 4))
        self.skel_combo_box = self.lib_filter_row.sizebox(148, padding=(0, 0, 6, 0))
        self.search_box = self.lib_filter_row.textbox(
            hint=i18n('搜索片段名或骨架…', 'Search clip or skeleton…'),
            fill=1, align=(0, 2),
            on_text_changed=self._on_search_changed,
        )
        self.lib_filter_row.button(
            i18n('清除', 'Clear'), size=11, padding=(4, 0, 0, 0),
            on_clicked=self._clear_search,
        )

        self.ext_file_box = parent.col(padding=(0, 0, 0, 4))
        self.ext_file_box.prop(
            self.props,
            properties=['JsonPath'],
            on_property_changed=self.on_props,
            pass_rootname=True,
        )

        self.clip_count_text = parent.text('', size=10, padding=(2, 2))
        self.clip_scroll = parent.scrollbox(fill=1, align=(0, 0), clip=True)
        self.clip_view = self.clip_scroll.col(padding=0)

    def _build_anim_inspector(self, parent):
        card = parent.border(color=_color(_CARD_RGBA), padding=(0, 4))
        card_col = card.col(padding=(8, 6))
        self.clip_title = card_col.text(i18n('未选择动画片段', 'No clip selected'), size=13, wrap=True)
        self.clip_meta = card_col.text('', size=10, wrap=True, padding=(0, 2, 0, 0))
        self.clip_detail = card_col.text('', size=9, wrap=True, padding=(0, 3, 0, 0))

        opt_scroll = parent.scrollbox(fill=1, align=(0, 0), clip=True, padding=(0, 4))
        opt_col = opt_scroll.col(padding=0)
        opt_col.prop(
            self.props,
            properties=[
                'CreateNewSequence', 'LevelSequenceName', 'StartAtPlayhead',
                'UseLayeredRig', 'AnimSequenceName', 'TimeScale',
                'ShowAdvanced', 'IgnoreMissingBones', 'ExportFps',
            ],
            on_property_changed=self.on_props,
            pass_rootname=True,
        )
        self.skel_mode_row = opt_col.row(padding=(4, 4))
        self.skel_mode_row.text(i18n('骨架模式', 'Skeleton Mode'), size=10, align=(1, 2), padding=(0, 0, 8, 0))
        self.skel_mode_combo = self.skel_mode_row.combo(
            {
                'auto': i18n('自动（按索引）', 'Auto (from index)'),
                'biped': 'Biped',
                'quadruped': 'Quadruped',
                'local': 'Local',
            },
            selected=self.skeleton_mode,
            fill=1,
            on_selection_changed=self._on_skel_mode_changed,
        )
        self.skel_mode_row.hide(not bool(self.props.ShowAdvanced))

        apply_btn = parent.button(
            i18n('写入 Sequencer', 'Key to Sequencer', key='将动画写入 Sequencer'),
            size=12, padding=(0, 3), on_clicked=self.apply,
        )
        apply_btn.set_background_color(_color(_PRIMARY_RGBA))

        sub_row = parent.row(padding=(0, 2, 0, 0))
        sub_row.button(
            i18n('烘焙动画序列', 'Bake Anim Sequence'),
            size=11, fill=1, padding=(0, 0, 3, 0), on_clicked=self.bake,
        )
        sub_row.button(
            i18n('直出动画资产', 'Export AnimSequence'),
            size=11, fill=1, padding=(3, 0, 0, 0), on_clicked=self.export_direct,
        )

    # ------------------------------------------------------------------
    # Tab 2: Facial Presets & Auto-Blink Studio
    # ------------------------------------------------------------------

    def _build_face_studio(self, parent):
        scroll = parent.scrollbox(fill=1, align=(0, 0), clip=True)
        col = scroll.col(padding=(0, 2))
        self._preset_buttons = {}

        for cat_key, cat_label in _PRESET_CATEGORIES:
            cat_items = [p for p in self.presets if p['category'] == cat_key]
            if not cat_items:
                continue
            col.text(cat_label, size=11, padding=(2, 6, 2, 4))
            wrap = col.wrapbox(inner_padding=5, padding=(0, 0, 0, 6))
            for preset in cat_items:
                pid = preset['id']
                arrow = _GAZE_ARROWS.get(pid, '')
                disp = self._preset_display_text(preset)
                label = _fmt_text('{arrow}{name}', arrow=arrow, name=disp) if arrow else disp
                cell = wrap.sizebox(98, 32, padding=0)
                btn = cell.button(
                    label, size=11, padding=0, align=(0, 0),
                    on_clicked=partial(self._select_preset, pid),
                )
                btn.set_tool_tip_text(self._format_preset_tooltip(preset))
                self._preset_buttons[pid] = btn

        col.text(i18n('自动生理眨眼（稀疏关键帧 · 仅眼睑）', 'Procedural Auto-Blink (sparse · eyelids only)'),
                 size=11, padding=(2, 8, 2, 4))
        blink_card = col.border(color=_color(_CARD_RGBA), padding=0)
        blink_col = blink_card.col(padding=(8, 6))
        blink_col.text(
            i18n('仅在眨眼瞬间写入关键帧；时长为 0 时自动铺满当前序列，种子为 0 时每次随机。',
                 'Writes sparse keys only at blink transitions; Duration 0 spans the active sequence, Seed 0 randomizes.'),
            size=9, wrap=True, padding=(2, 0, 2, 4),
        )
        blink_col.prop(self.blink_props)
        blink_btn = blink_col.button(
            i18n('生成自动眨眼到当前序列', 'Generate Auto-Blink to Sequence'),
            size=11, padding=(0, 4, 0, 0), on_clicked=self.apply_auto_blink,
        )
        blink_btn.set_background_color(_color(_PRIMARY_RGBA))

    def _build_face_inspector(self, parent):
        card = parent.border(color=_color(_CARD_RGBA), padding=(0, 4))
        card_col = card.col(padding=(8, 6))
        self.preset_title = card_col.text('', size=13, wrap=True)
        self.preset_meta = card_col.text('', size=10, wrap=True, padding=(0, 2, 0, 0))
        self.preset_curves_text = card_col.text('', size=9, wrap=True, padding=(0, 4, 0, 0))

        opt_scroll = parent.scrollbox(fill=1, align=(0, 0), clip=True, padding=(0, 4))
        opt_col = opt_scroll.col(padding=0)
        opt_col.text(
            i18n('淡入/保持/淡出均为 0 时，在播放头写入单帧姿势关键帧；勾选「自动应用动画」后点按钮直接写入时间轴。',
                 'With BlendIn/Hold/BlendOut at 0, stamps a single pose key at playhead; enable Auto Apply to key immediately on click.'),
            size=9, wrap=True, padding=(2, 0, 2, 4),
        )
        opt_col.prop(self.face_props)
        mode_row = opt_col.row(padding=(4, 4))
        mode_row.text(i18n('叠加策略', 'Layer Mode'), size=10, align=(1, 2), padding=(0, 0, 8, 0))
        self.face_mode_combo = mode_row.combo(
            {
                'auto': i18n('自动（情绪重置，视线/眨眼保留）', 'Auto (reset emotion scope, keep gaze/blink)'),
                'layer': i18n('仅写入本预设声明通道', 'Layer preset curves only'),
                'reset': i18n('重置全部 15 条表情曲线', 'Reset all 15 facial curves'),
            },
            selected=self.face_reset_mode,
            fill=1,
            on_selection_changed=lambda key, _: setattr(self, 'face_reset_mode', str(key)),
        )

        apply_face_btn = parent.button(
            i18n('应用表情到 Sequencer', 'Apply Expression to Sequencer'),
            size=12, padding=(0, 3), on_clicked=self.apply_face_preset,
        )
        apply_face_btn.set_background_color(_color(_PRIMARY_RGBA))
        reset_btn = parent.button(
            i18n('归零全部表情', 'Reset All Expressions'),
            size=11, padding=(0, 2, 0, 0), on_clicked=self.reset_face_curves,
        )
        reset_btn.set_tool_tip_text(i18n(
            '在当前播放头将全部表情曲线写入 0.0。Replace 轨道会直接归零；Layered 叠加轨道仅归零当前层，不影响其他层已有权重。',
            'Keys all facial curves to 0.0 at playhead. On a Replace track this zeroes the face; on a Layered/Additive track it only zeroes the active layer without clearing other layers.',
        ))

    # ------------------------------------------------------------------
    # Tab & Filter State Management
    # ------------------------------------------------------------------

    def _set_tab(self, index: int):
        self.active_tab = int(index)
        self.left_switcher.set_active_widget_index(self.active_tab)
        self.right_switcher.set_active_widget_index(self.active_tab)
        for idx, btn in self._tab_buttons.items():
            btn.set_background_color(_color(_ACTIVE_RGBA if idx == self.active_tab else _NORMAL_RGBA))

    def _set_source(self, source: str):
        self.source_filter = source
        self.skeleton_filter = 'all'
        self._update_source_buttons()
        self.update_clips()

    def _update_source_buttons(self):
        is_ext = self.source_filter == 'external'
        for key, btn in self._source_buttons.items():
            btn.set_background_color(_color(_ACTIVE_RGBA if key == self.source_filter else _NORMAL_RGBA))
        if hasattr(self, 'lib_filter_row'):
            self.lib_filter_row.hide(is_ext)
        if hasattr(self, 'ext_file_box'):
            self.ext_file_box.hide(not is_ext)

    def _on_search_changed(self, text):
        cleaned = str(text or '').replace('\r', '').replace('\n', '')
        self.search_query = cleaned
        self._apply_clip_filters()

    def _clear_search(self):
        self.search_query = ''
        if hasattr(self, 'search_box'):
            self.search_box.set_text('')
        self._apply_clip_filters()

    def _on_skel_filter_changed(self, key, _reason=None):
        self.skeleton_filter = str(key or 'all')
        self._apply_clip_filters()

    def _on_skel_mode_changed(self, key, _reason=None):
        self.skeleton_mode = str(key or 'auto')

    def _refresh_all(self):
        self.presets = face_presets.load_presets(reload=True)
        self._rebuild_preset_loc()
        self.update_clips()
        self._refresh_face_inspector()
        self._set_status(i18n('已刷新本地动作库与表情预设', 'Refreshed clip library and facial presets'))

    # ------------------------------------------------------------------
    # Clip Catalog Build, Filter & Selection (Zero-Flicker Cached Rows)
    # ------------------------------------------------------------------

    def update_clips(self):
        self.clip_view.clear_children()
        self.entries = []
        self.clips = {}
        self._clip_buttons = {}
        self._clip_groups = {}
        prev_clip = self.clip_id
        self.clip_id = None

        is_ext = getattr(self, 'source_filter', 'all') == 'external'
        path = util.json_file(self.props) if is_ext else ''
        if hasattr(self, '_source_buttons') and self._source_buttons:
            self._update_source_buttons()

        if is_ext and not path:
            self.clip_view.text(i18n('请选择外部 .json 或 .bbmodel 动画文件', 'Choose an external .json or .bbmodel file'), size=11, padding=6)
            self._update_clip_inspector()
            self._update_clip_count(0, 0)
            return

        try:
            self.entries = build_clip_entries(path)
        except (OSError, ValueError, KeyError) as exc:
            self.clip_view.text(str(exc), size=10, wrap=True, padding=6)
            self._report_error(i18n('读取动画失败', 'Failed to load clips'), exc)
            self._update_clip_inspector()
            self._update_clip_count(0, 0)
            return

        if not self.entries:
            self.clip_view.text(i18n('请选择动画 JSON', 'Choose an animation JSON'), size=11, padding=6)
            self._update_clip_inspector()
            self._update_clip_count(0, 0)
            return

        self._rebuild_clip_loc()
        self.clips = {e['id']: (e['path'], e['clip']) for e in self.entries}
        self._rebuild_skeleton_combo()

        grouped: dict[tuple[str, str], list[dict]] = {}
        for entry in self.entries:
            grouped.setdefault((entry['source'], entry['group']), []).append(entry)

        self.clip_empty_text = self.clip_view.text(
            i18n('没有匹配的动画片段', 'No matching clips'), size=11, padding=6,
        )
        self.clip_empty_text.hide(True)

        for gkey, items in grouped.items():
            src, skel_grp = gkey
            sec = self.clip_view.col(padding=(0, 2, 0, 4))
            src_label = (
                i18n('自制', 'Custom') if src == 'custom'
                else (i18n('原版', 'Vanilla') if src == 'vanilla' else i18n('外部文件', 'External'))
            )
            header_text = (
                _join_text(' · ', src_label, items[0]['file']) if src == 'external'
                else _join_text(' · ', src_label, skeleton_group_label(skel_grp))
            )
            hdr = sec.text(header_text, size=10, padding=(4, 4, 4, 2))
            item_ids = []
            for entry in items:
                eid = entry['id']
                item_ids.append(eid)
                btn = sec.button(padding=(0, 1), align=(0, 0), on_clicked=partial(self.select_clip, eid))
                row = btn.row(padding=(6, 3), align=(0, 2))
                row.text(self._clip_display_text(entry), size=11, fill=1, align=(1, 2))
                tag_parts = [entry['format']]
                if entry['loop'] is True:
                    tag_parts.append(i18n('循环', 'Loop'))
                elif entry['loop'] is False:
                    tag_parts.append(i18n('单次', 'Once'))
                row.text(_join_text(' · ', *tag_parts), size=9, align=(3, 2))
                tip_lines = [entry['clip'], entry['file']]
                if entry['desc']:
                    tip_lines.append(entry['desc'])
                btn.set_tool_tip_text('\n'.join(tip_lines))
                self._clip_buttons[eid] = btn
            self._clip_groups[gkey] = (sec, hdr, item_ids)

        if prev_clip in self.clips:
            self.clip_id = prev_clip
        self._apply_clip_filters()

    def _rebuild_skeleton_combo(self):
        if not hasattr(self, 'skel_combo_box'):
            return
        self.skel_combo_box.clear_children()
        groups = []
        for entry in self.entries:
            if self.source_filter in ('all', entry['source']) and entry['group'] not in groups:
                groups.append(entry['group'])
        options = {'all': i18n('全部骨架', 'All Skeletons')}
        for g in groups:
            options[g] = skeleton_group_label(g)
        if self.skeleton_filter not in options:
            self.skeleton_filter = 'all'
        self.skel_filter_combo = self.skel_combo_box.combo(
            options,
            selected=self.skeleton_filter,
            fill=1,
            on_selection_changed=self._on_skel_filter_changed,
        )

    def _apply_clip_filters(self):
        src = 'all' if self.source_filter == 'external' else self.source_filter
        grp = 'all' if self.source_filter == 'external' else self.skeleton_filter
        visible_entries = filter_clip_entries(self.entries, source=src, group=grp, query=self.search_query)
        visible_ids = {e['id'] for e in visible_entries}

        for eid, btn in self._clip_buttons.items():
            btn.hide(eid not in visible_ids)
        for sec, _, item_ids in self._clip_groups.values():
            sec.hide(not any(eid in visible_ids for eid in item_ids))
        if hasattr(self, 'clip_empty_text'):
            self.clip_empty_text.hide(bool(visible_entries))

        if self.clip_id not in visible_ids:
            self.clip_id = visible_entries[0]['id'] if visible_entries else None
            if self.clip_id is not None:
                util.sync_asset_names(self.props, self.selected_clip()[1])

        self._highlight_clips()
        self._update_clip_inspector()
        self._update_clip_count(len(visible_entries), len(self.entries))

    def _highlight_clips(self):
        for eid, btn in self._clip_buttons.items():
            btn.set_background_color(_color(_ACTIVE_RGBA if eid == self.clip_id else _NORMAL_RGBA))

    def _update_clip_count(self, shown: int, total: int):
        if hasattr(self, 'clip_count_text'):
            self.clip_count_text.set_text(
                i18n('显示 {shown} / {total} 个片段', 'Showing {shown} / {total} clips').format(
                    shown=str(shown), total=str(total),
                )
            )

    def _update_clip_inspector(self):
        if not hasattr(self, 'clip_title'):
            return
        entry = next((e for e in self.entries if e['id'] == self.clip_id), None)
        if entry is None:
            self.clip_title.set_text(i18n('未选择动画片段', 'No clip selected'))
            self.clip_meta.set_text('')
            self.clip_detail.set_text('')
            return
        self.clip_title.set_text(self._clip_display_text(entry))
        src_text = (
            i18n('自制', 'Custom') if entry['source'] == 'custom'
            else (i18n('原版', 'Vanilla') if entry['source'] == 'vanilla' else i18n('外部文件', 'External'))
        )
        meta_parts = [src_text, entry['format']]
        if entry['skeleton']:
            meta_parts.append(entry['skeleton'])
        if entry['loop'] is True:
            meta_parts.append(i18n('循环', 'Loop'))
        elif entry['loop'] is False:
            meta_parts.append(i18n('单次', 'Once'))
        self.clip_meta.set_text(_join_text(' · ', *meta_parts))
        detail_lines = [entry['clip'], entry['file']]
        if entry['desc']:
            detail_lines.append(entry['desc'])
        self.clip_detail.set_text('\n'.join(detail_lines))

    def select_clip(self, key, _reason=None):
        self.clip_id = str(key)
        self._highlight_clips()
        self._update_clip_inspector()
        if self.clip_id in self.clips:
            util.sync_asset_names(self.props, self.selected_clip()[1])

    def selected_clip(self):
        if self.clip_id is None or self.clip_id not in self.clips:
            raise ValueError('请选择动画片段')
        return self.clips[self.clip_id]

    # ------------------------------------------------------------------
    # Facial Preset Selection & Inspector
    # ------------------------------------------------------------------

    def _format_preset_tooltip(self, preset: dict) -> str:
        curves = preset.get('curves') or {}
        if not curves:
            return f"{preset['zh']} / {preset['en']} ({preset['id']}): all curves -> 0.0"
        lines = [f"{preset['zh']} / {preset['en']} ({preset['id']})"]
        for k, v in curves.items():
            if isinstance(v, dict):
                lines.append(f'  {k}: animated ({len(v)} keys)')
            else:
                lines.append(f'  {k}: {float(v):+.2f}')
        return '\n'.join(lines)

    def _select_preset(self, preset_id: str):
        self.preset_id = preset_id
        self._refresh_face_inspector()
        if bool(getattr(self.face_props, 'AutoApply', False)):
            self.apply_face_preset()

    def _refresh_face_inspector(self):
        for pid, btn in self._preset_buttons.items():
            btn.set_background_color(_color(_ACTIVE_RGBA if pid == self.preset_id else _NORMAL_RGBA))
        if not hasattr(self, 'preset_title'):
            return
        preset = next((p for p in self.presets if p['id'] == self.preset_id), None)
        if preset is None:
            self.preset_title.set_text(i18n('未选择表情预设', 'No preset selected'))
            self.preset_meta.set_text('')
            self.preset_curves_text.set_text('')
            return
        disp = self._preset_display_text(preset)
        self.preset_title.set_text(_fmt_text('{name} ({pid})', name=disp, pid=preset['id']))
        scope = preset.get('reset_scope') or ('all' if preset.get('reset_others') else 'none')
        if scope == 'all':
            behavior = i18n('默认归零全部 15 条曲线', 'Resets all 15 curves by default')
        elif scope == 'emotion':
            behavior = i18n('默认仅重置情绪曲线（保留视线/眨眼）', 'Resets emotion curves only (keeps gaze/blink)')
        else:
            behavior = i18n('默认仅叠加相关曲线', 'Layers only its own curves by default')
        kind = i18n('动态片段', 'Animated clip') if face_presets.is_animated_preset(preset) else i18n('姿势预设', 'Pose preset')
        self.preset_meta.set_text(_join_text(' · ', kind, behavior))
        curves = preset.get('curves') or {}
        if not curves:
            self.preset_curves_text.set_text(i18n('全部 15 条表情曲线归零', 'Resets all 15 facial curves to 0.0'))
        else:
            lines = []
            for k, v in curves.items():
                short_k = k[5:] if k.startswith('face_') else k
                if isinstance(v, dict):
                    lines.append(f"{short_k}: {preset.get('animation_length', 0.21)}s ({len(v)} keys)")
                else:
                    lines.append(f'{short_k}: {float(v):+.2f}')
            self.preset_curves_text.set_text('   '.join(lines))

    # ------------------------------------------------------------------
    # Actions & On-Screen Error Reporting
    # ------------------------------------------------------------------

    def _set_status(self, message):
        if _alive(getattr(self, 'status_text', None)):
            self.status_text.set_text(message)

    def _report_error(self, label_text, err):
        msg = _fmt_text('{label}: {err}', label=label_text, err=str(err))
        self._set_status(msg)
        mineprep.warn(str(msg))

    def _run_async(self, label_text, factory):
        if self._runner is not None and not self._runner.done:
            self._set_status(i18n('已有转换任务正在执行，请稍候…', 'Another task is still running…'))
            return None
        try:
            runner = factory()
        except Exception as exc:
            self._report_error(label_text, exc)
            return None
        self._runner = runner
        if runner is not None:
            if getattr(runner, 'done', False):
                if getattr(runner, 'error', None):
                    self._report_error(label_text, runner.error)
                else:
                    self._on_async_done(label_text, runner.result)
            else:
                self._set_status(_fmt_text('{label}…', label=label_text))
                runner.on_done = partial(self._on_async_done, label_text)
        return runner

    def _on_async_done(self, label_text, result):
        if isinstance(result, dict):
            clip = result.get('clip') or ''
            keys = result.get('keys', 0)
            notes = []
            skipped = result.get('skipped_bones') or []
            if skipped:
                notes.append(f'skipped bones {len(skipped)}')
            unsupported = result.get('unsupported_curves') or []
            if unsupported:
                notes.append(f'unsupported curves {len(unsupported)}')
            rig_modes = result.get('rig_modes') or {}
            if rig_modes:
                modes = '/'.join(dict.fromkeys(rig_modes.values()))
                notes.append(modes)
            suffix = f" ({', '.join(notes)})" if notes else ''
            self._set_status(_fmt_text(
                '{label}: {clip} · {keys} keys{suffix}',
                label=label_text, clip=short_clip_name(clip), keys=str(keys), suffix=suffix,
            ))
        else:
            self._set_status(_fmt_text('{label}: OK', label=label_text))

    def apply(self):
        return self._run_async(i18n('写入 Sequencer', 'Key to Sequencer', key='将动画写入 Sequencer'),
                               lambda: ops.apply(self))

    def bake(self):
        if self._runner is not None and not self._runner.done:
            self._set_status(i18n('已有转换任务正在执行，请稍候…', 'Another task is still running…'))
            return None
        try:
            res = ops.bake(self)
            names = [a.get_name() for a in (res or {}).values() if a is not None]
            self._set_status(_fmt_text('{label}: {names}', label=i18n('烘焙完成', 'Baked'), names=', '.join(names)))
            return res
        except Exception as exc:
            self._report_error(i18n('烘焙失败', 'Bake failed'), exc)
            return None

    def export_direct(self):
        if self._runner is not None and not self._runner.done:
            self._set_status(i18n('已有转换任务正在执行，请稍候…', 'Another task is still running…'))
            return None
        try:
            res = ops.export_direct(self)
            body = res.get('body').get_name() if res and res.get('body') else ''
            head = f" + {res['head'].get_name()}" if res and res.get('head') else ''
            frames = res.get('frames', 0) if res else 0
            self._set_status(_fmt_text(
                '{label}: {body}{head} ({frames}f)',
                label=i18n('直出完成', 'Exported'), body=body, head=head, frames=str(frames),
            ))
            return res
        except Exception as exc:
            self._report_error(i18n('直出失败', 'Export failed'), exc)
            return None

    def apply_face_preset(self):
        if not self.preset_id:
            self._report_error(i18n('应用表情', 'Apply Expression'),
                               i18n('请先选择一个表情预设', 'Choose a facial preset first'))
            return None
        reset_opt = (
            None if self.face_reset_mode == 'auto'
            else ('all' if self.face_reset_mode == 'reset' else 'none')
        )
        fp = self.face_props
        layered_opt = 'auto' if bool(getattr(fp, 'UseLayeredRig', True)) else False

        def _launch():
            target = util.resolve_actor(self.props)
            start_t = None if fp.StartAtPlayhead else 0
            return ops.apply_face_preset(
                target, self.preset_id,
                start_time=start_t,
                strength=fp.Strength,
                blend_in=fp.BlendIn,
                hold=fp.Hold,
                blend_out=fp.BlendOut,
                reset_others=reset_opt,
                layered=layered_opt,
            )

        return self._run_async(i18n('应用表情', 'Apply Expression'), _launch)

    def reset_face_curves(self):
        fp = self.face_props
        layered_opt = 'auto' if bool(getattr(fp, 'UseLayeredRig', True)) else False

        def _launch():
            target = util.resolve_actor(self.props)
            start_t = None if fp.StartAtPlayhead else 0
            return ops.apply_face_preset(
                target, 'neutral',
                start_time=start_t,
                strength=1.0,
                blend_in=fp.BlendIn,
                hold=0.0,
                blend_out=0.0,
                reset_others=True,
                layered=layered_opt,
            )

        return self._run_async(i18n('归零表情', 'Reset Expression'), _launch)

    def apply_auto_blink(self):
        bp = self.blink_props
        fp = self.face_props
        layered_opt = 'auto' if bool(getattr(fp, 'UseLayeredRig', True)) else False

        def _launch():
            target = util.resolve_actor(self.props)
            seed = int(bp.Seed) if int(bp.Seed) > 0 else None
            dur = float(bp.Duration) if float(bp.Duration) > 0.0 else None
            return ops.apply_auto_blink(
                target,
                start_time=0,
                duration=dur,
                min_interval=bp.MinInterval,
                max_interval=bp.MaxInterval,
                blink_duration=bp.BlinkDuration,
                hold_closed=bp.HoldClosed,
                double_blink_chance=bp.DoubleBlinkChance,
                seed=seed,
                layered=layered_opt,
            )

        return self._run_async(i18n('生成自动眨眼', 'Auto-Blink'), _launch)

    def destruct(self):
        self._unbind_selection()
        if self._runner is not None:
            self._runner.destroy()
            self._runner = None

    def on_props(self, name):
        if name == 'FollowSelection' and bool(self.props.FollowSelection):
            self._sync_from_selection()
        if name in ('JsonPath', 'FilePath'):
            if util.json_file(self.props):
                self.source_filter = 'external'
            self.update_clips()
        if name == 'ShowAdvanced' and hasattr(self, 'skel_mode_row'):
            self.skel_mode_row.hide(not bool(self.props.ShowAdvanced))
        if name in ('Actor', 'JsonPath', 'FilePath') and self.clip_id is not None and self.clip_id in self.clips:
            util.sync_asset_names(self.props, self.selected_clip()[1])
