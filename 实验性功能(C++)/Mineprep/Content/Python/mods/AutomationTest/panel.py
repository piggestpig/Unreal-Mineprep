from functools import partial

import unreal
import mineprep
from . import tests, ops


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

    def _start(self, rows):
        if self.closed or self._busy or not rows:
            return
        self._busy = True
        self._set_enabled(False)
        by_id = {row['spec']['id']: row for row in rows}

        def progress(item, text, color):
            labels = {'running': tr('运行中…', 'Running…'), 'passed': tr('通过', 'Passed'),
                      'cancelled': tr('已取消', 'Cancelled'), 'failed': item['error'] or tr('失败', 'Failed')}
            self._set_status(by_id[item['id']], text or labels.get(item['state'], ''),
                             color if color is not None else _PASS if item['state'] == 'passed' else
                             _FAIL if item['state'] == 'failed' else _RUNNING)

        def finished(job):
            self._busy, self._runner = False, None
            for item in job.result:
                progress(item, None, None)
            self._set_enabled(True)

        self._runner = ops.run_cases(list(by_id), on_progress=progress, on_done=finished)

    def destruct(self):
        self.closed = True
        if self._runner is not None:
            self._runner.cancel()
            self._runner = None
        self._busy = False
