import unreal
import mineprep
from mineprep import i18n

from . import ops
from .props import Props, PromptProps

_IDLE = unreal.LinearColor(1, 1, 1, 1)
_RUNNING = unreal.LinearColor(1.0, 0.82, 0.12, 1.0)
_DONE = unreal.LinearColor(0.35, 0.85, 0.4, 1.0)
_FAIL = unreal.LinearColor(1.0, 0.35, 0.3, 1.0)


class LocalizationBoard(mineprep.Mod):
    _unique_ = True
    _label_ = i18n('本地化控制板', 'Localization Board')

    def __init__(self, context=None):
        self.closed = False
        self._busy = False
        self._runner = None
        self._has_cpp = ops.has_cpp_gather()
        self.props = None
        self.prompt_props = None
        if self._has_cpp:
            self.props = Props()
            self.prompt_props = PromptProps()
        super().__init__(context)

    def draw(self, context=None):
        layout = self.layout
        if not self._has_cpp:
            layout.text(
                i18n(
                    '未找到 C++ 函数 unreal.mineprep.gather_property_names，请先编译 Mineprep 插件。',
                    'C++ function unreal.mineprep.gather_property_names not found. Compile the Mineprep plugin first.',
                ),
                wrap=True,
                padding=6,
                fill=1,
            )
            return
        layout.prop(self.props, align=(0, 1))

        row = layout.row(padding=(0, 4))
        self._btn_gather = row.button(
            i18n('开始收集', 'Gather'),
            on_clicked=self.start_gather,
            padding=3,
            fill=1,
        )
        self._btn_cancel = row.button(
            i18n('取消', 'Cancel'),
            on_clicked=self.cancel,
            padding=3,
            fill=1,
        )
        self._btn_refresh = row.button(
            i18n('刷新待翻译表', 'Refresh Untranslated'),
            on_clicked=self.refresh_todo,
            padding=3,
            fill=1,
        )
        self._btn_open = row.button(
            i18n('打开 CSV 文件夹', 'Open CSV Folder'),
            on_clicked=lambda: ops.open_csv_folder(),
            padding=3,
            fill=1,
        )
        self._status = layout.text(
            i18n('空闲。设置扫描路径后点击「开始收集」。',
                      'Idle. Set the scan path, then click Gather.'),
            wrap=True,
            align=(1, 3),
            padding=6,
            fill=1,
        )
        self._prompt_view = layout.prop(
            self.prompt_props, 'Prompt', align=(0, 1), fill=1)
        self._prompt_view.hide(True)
        self._sync_buttons()

    def _sync_buttons(self):
        if self.closed or not self._has_cpp:
            return
        busy = self._busy
        self._btn_gather.set_is_enabled(not busy)
        self._btn_refresh.set_is_enabled(not busy)
        self._btn_cancel.set_is_enabled(busy)
        self._btn_open.set_is_enabled(True)

    def _set_status(self, text, color=_IDLE):
        if self.closed or not self._has_cpp:
            return
        self._status.set_text(text)
        self._status.set_color_and_opacity(unreal.SlateColor(color))

    def start_gather(self):
        if self.closed or self._busy or not self._has_cpp:
            return
        self._busy = True
        self._sync_buttons()
        if hasattr(self, '_prompt_view'):
            self._prompt_view.hide(True)
        self._set_status(
            i18n('正在列出资产…', 'Listing assets…'),
            _RUNNING,
        )

        self._runner = ops.start_gather(
            self.props.ScanPath, set_enum_key=self.props.SetEnumKey,
            on_progress=self._on_progress, on_done=self._finished)

    def _finished(self, job):
        self._busy = False
        self._runner = None
        if not self.closed:
            if job.error:
                self._set_status(str(job.error), _FAIL)
            else:
                self._report(job.result or {'cancelled': True})
            self._sync_buttons()

    def _on_progress(self, text):
        self._set_status(text, _RUNNING)

    def _report(self, stats):
        if not stats:
            return
        extra = i18n(
            "新增 {added}，复用 {reused}，失败 {failed}，共 {total} 行，待翻译 {untranslated} 行",
            'Added {added}, reused {reused}, failed {failed} ({total} total, {untranslated} untranslated)',
        ).format(added=stats.get('added', 0), reused=stats.get('reused', 0), failed=stats.get('failed', 0),
                 total=stats.get('total', 0), untranslated=stats.get('untranslated', 0))
        if stats.get('cancelled'):
            self._set_status(
                str(i18n('已取消。', 'Cancelled. ')) + str(extra),
                _FAIL,
            )
        else:
            self._set_status(
                str(i18n('完成。', 'Done. ')) + str(extra),
                _FAIL if stats.get('failed') else _DONE,
            )
        self._show_prompt()

    def _show_prompt(self):
        if self.closed or not self.prompt_props:
            return
        self.prompt_props.Prompt = ops.make_prompt()
        if hasattr(self, '_prompt_view'):
            self._prompt_view.hide(False)

    def refresh_todo(self):
        if self.closed or self._busy or not self._has_cpp:
            return
        try:
            stats = ops.refresh_todo()
        except Exception as exc:
            mineprep.warn('LocalizationBoard', exc)
            self._set_status(str(exc).strip() or type(exc).__name__, _FAIL)
            return
        self._set_status(
            str(i18n(
                '已刷新待翻译表：{untranslated} / {total} 行',
                'Refreshed untranslated table: {untranslated} / {total} rows',
            ).format(untranslated=stats['untranslated'], total=stats['total'])),
            _DONE,
        )

    def cancel(self):
        runner = self._runner
        self._runner = None
        if runner is not None:
            runner.cancel()
        self._busy = False
        if not self.closed:
            self._sync_buttons()

    def destruct(self):
        self.closed = True
        if self._runner is not None:
            self._runner.cancel(save_partial=False)
            self._runner = None
        self._busy = False
