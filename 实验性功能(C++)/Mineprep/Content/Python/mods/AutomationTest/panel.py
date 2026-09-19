import inspect
from functools import partial

import unreal
import mineprep
from . import tests


def tr(zh, en):
    return mineprep.bilingual(zh, en)


_UNTESTED = unreal.LinearColor(1, 1, 1, 1)
_RUNNING = unreal.LinearColor(1.0, 0.82, 0.12, 1.0)
_PASS = unreal.LinearColor(0.35, 0.85, 0.4, 1.0)
_FAIL = unreal.LinearColor(1.0, 0.35, 0.3, 1.0)


class AutomationTest(mineprep.Mod):
    _unique_ = True
    _label_ = tr('自动化测试', 'Automation Test')

    def __init__(self, context=None):
        self.closed = False
        self._busy = False
        self._runner = None
        self._rows = []
        super().__init__(context)

    def draw(self, context=None):
        layout = self.layout
        self._run_all = layout.button(
            tr('运行所有项目', 'Run all tests'), on_clicked=self.run_all, padding=4)

        self._rows = []
        for i, spec in enumerate(tests.TESTS):
            row = layout.row(padding=(0, 2))
            button = row.button(spec['label'], on_clicked=partial(self.run_one, i), padding=3)
            status = row.text(tr('未测试', 'Not tested'), wrap=True, padding=(8, 2), align=(1,2), fill=1)
            self._rows.append(dict(spec=spec, button=button, status=status))

    def run_all(self):
        self._start(self._rows)

    def run_one(self, index):
        self._start([self._rows[index]])

    def _set_enabled(self, enabled):
        if self.closed:
            return
        self._run_all.set_is_enabled(enabled)
        for row in self._rows:
            row['button'].set_is_enabled(enabled)

    def _set_status(self, row, text, color):
        if self.closed:
            return
        row['status'].set_text(text)
        row['status'].set_color_and_opacity(unreal.SlateColor(color))

    def _call_test(self, row):
        def status(text, color=_RUNNING):
            self._set_status(row, text, color)

        fn = row['spec']['fn']
        params = inspect.signature(fn).parameters
        if 'status' in params or any(p.kind is p.VAR_KEYWORD for p in params.values()):
            return fn(status=status)
        return fn()

    def _start(self, rows):
        if self.closed or self._busy or not rows:
            return
        self._busy = True
        self._set_enabled(False)
        queue = list(rows)

        @mineprep.asynctask
        def run():
            try:
                for row in queue:
                    if self.closed:
                        return
                    self._set_status(row, tr('运行中…', 'Running…'), _RUNNING)
                    try:
                        result = self._call_test(row)
                        if inspect.isgenerator(result):
                            yield from result
                        if self.closed:
                            return
                        self._set_status(row, tr('通过', 'Passed'), _PASS)
                    except Exception as exc:
                        if self.closed:
                            return
                        self._set_status(row, str(exc).strip() or type(exc).__name__, _FAIL)
                        mineprep.warn('AutomationTest', exc)
                    yield 0.1
            finally:
                self._busy = False
                self._runner = None
                if not self.closed:
                    self._set_enabled(True)

        self._runner = run()

    def destruct(self):
        self.closed = True
        if self._runner is not None:
            self._runner.destroy()
            self._runner = None
        self._busy = False
