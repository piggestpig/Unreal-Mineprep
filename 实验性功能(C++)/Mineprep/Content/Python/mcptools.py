"""通过 MCP 在编辑器中执行 Python。

由 init_unreal.py 注册为 mcptools.PythonTools。调用之间保留变量，reset() 清空会话。
执行结果和日志以 JSON 返回。
"""

from __future__ import annotations

import ast
import json
import math
import os
import re
import traceback
import uuid
from typing import Any

import unreal
import toolset_registry

_SESSION: dict[str, Any] = {'__name__': 'mcptools_session'}
_MAX_SEQ = 80
_MAX_MAP = 80
_MAX_REPR = 2000
_MAX_JSON = 200_000
_MAX_LOG_LINES = 2000
_MAX_LOG_CHARS = 80_000
_TOOLSET_WINDOW = 20_000
_MAX_TRUNCATION_DETAILS = 32


class _Truncations:
    """记录截断位置和数量，限制详情条数；保留数量不含省略提示。"""

    def __init__(self):
        self.fields = []
        self.details = []
        self.omitted = 0

    def add(self, path, reason, original=None, retained=None, unit=None):
        field = path.split('/', 1)[0]
        if field not in self.fields:
            self.fields.append(field)
        detail = {'path': path[:256], 'reason': reason}
        if len(path) > 256:
            detail['path_truncated'] = True
        if original is not None:
            detail['original'] = original
        if retained is not None:
            detail['retained'] = retained
        if unit:
            detail['unit'] = unit
        if len(self.details) < _MAX_TRUNCATION_DETAILS:
            self.details.append(detail)
            return detail
        self.omitted += 1
        return None

    def apply(self, payload):
        if self.fields:
            payload['truncated'] = list(self.fields)
            payload['truncation_details'] = list(self.details)
            if self.omitted:
                payload['truncation_details'].append(
                    {'reason': 'details_limit', 'omitted': self.omitted})

# loglevel=0: Warning/Error/Fatal, except LogSlate* warnings (including continuations).
# loglevel=1 (default): also keep these categories.
_LOG_KEEP = (
    'LogPython',
    'LogTemp',
    'LogBlueprintUserMessages',
)

# loglevel=2: drop editor/MCP noise; keep engine C++ categories. 3: unfiltered.
_LOG_DROP = (
    'LogSlate',
    'LogSlateStyle',
    'LogConfig',
    'LogConsoleManager',
    'LogHttp',
    'LogModelContextProtocol',
    'LogOutputDevice',
)

_LOG_CATEGORY_RE = re.compile(r'^(?:\[[^\]]*\])*(\w+):')
_SEVERITY_RE = re.compile(r':\s*(Warning|Error|Fatal):', re.IGNORECASE)


def _session() -> dict[str, Any]:
    """取得会话命名空间，并更新 unreal 和 mineprep 引用。"""
    import mineprep

    _SESSION['__name__'] = 'mcptools_session'
    _SESSION['unreal'] = unreal
    _SESSION['mineprep'] = mineprep
    return _SESSION


def reset_session() -> None:
    _SESSION.clear()
    _SESSION['__name__'] = 'mcptools_session'


def _async_view(runner) -> dict[str, Any]:
    """把尚未跑完或已经结束的 asynctask 句柄收成可序列化的状态。"""
    view = {'pending': not runner.done, 'name': runner.func_name}
    if not runner.done:
        return view
    if runner.error:
        view['error'] = runner.error
    else:
        view['result'] = runner.result
    return view


def _capture_async(ns: dict[str, Any], result: Any, before: set) -> Any:
    """表达式结果是 runner，或赋值启动了唯一任务时，记下 _async 并返回状态。"""
    import mc_parallel

    runner = result if isinstance(result, mc_parallel.AsyncTaskRunner) else None
    if runner is None and result is None:
        started = [item for item in mc_parallel._active_async if item not in before]
        if len(started) == 1:
            runner = started[0]
    if runner is None:
        return result
    ns['_async'] = runner
    return _async_view(runner)


def execute_snippet(code: str, ns: dict[str, Any]) -> Any:
    """在指定命名空间执行代码；若最后一条语句是表达式，返回其值，否则返回 None。"""
    tree = ast.parse(code, filename='<mcp>')
    if not tree.body:
        return None
    last = tree.body[-1]
    if isinstance(last, ast.Expr):
        preamble = ast.Module(body=tree.body[:-1], type_ignores=[])
        ast.fix_missing_locations(preamble)
        if preamble.body:
            exec(compile(preamble, '<mcp>', 'exec'), ns)  # noqa: S102
        expr = ast.Expression(body=last.value)
        ast.fix_missing_locations(expr)
        return eval(compile(expr, '<mcp>', 'eval'), ns)  # noqa: S307
    ast.fix_missing_locations(tree)
    exec(compile(tree, '<mcp>', 'exec'), ns)  # noqa: S102
    return None


def _json_ready(value: Any, depth: int = 0, *, truncations=None, path='result') -> Any:
    def record(reason, original=None, retained=None, unit=None):
        if truncations is not None:
            truncations.add(path, reason, original, retained, unit)

    def child(item, key):
        # 转义路径中的 ~ 和 /，避免与字典键混淆。
        key = str(key).replace('~', '~0').replace('/', '~1')
        return _json_ready(item, depth + 1, truncations=truncations,
                           path=f'{path}/{key}')

    def preview(reason=None):
        text = repr(value)
        if reason:
            record(reason, len(text), min(len(text), _MAX_REPR), 'characters')
        if len(text) > _MAX_REPR:
            record('text_limit', len(text), _MAX_REPR, 'characters')
        return text[:_MAX_REPR]

    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return value.decode('utf-8', 'replace')
    if depth >= 5:
        return preview('depth_limit')

    target = getattr(value, 'target', None)
    if (
        target is not None
        and target is not value
        and type(value).__module__ in ('mineprep', 'mc_utils', 'mc_widget')
    ):
        packed = {'handle': type(value).__name__, 'target': child(target, 'target')}
        label = getattr(value, 'name', None)
        if label:
            packed['name'] = str(label)
        return packed

    if isinstance(value, dict):
        out = {}
        for i, (key, item) in enumerate(value.items()):
            if i >= _MAX_MAP:
                record('map_limit', len(value), _MAX_MAP, 'items')
                out['...'] = f'+{len(value) - _MAX_MAP} more'
                break
            out[str(key)] = child(item, key)
        return out

    if isinstance(value, (list, tuple, set)):
        seq = list(value)
        out = [child(item, i) for i, item in enumerate(seq[:_MAX_SEQ])]
        if len(seq) > _MAX_SEQ:
            record('sequence_limit', len(seq), _MAX_SEQ, 'items')
            out.append(f'... +{len(seq) - _MAX_SEQ} more')
        return out

    get_path = getattr(value, 'get_path_name', None)
    get_label = getattr(value, 'get_actor_label', None)
    if callable(get_path):
        try:
            packed = {'uobject': get_path()}
            if callable(get_label):
                packed['label'] = get_label()
            return packed
        except Exception:
            pass

    try:
        json.dumps(value)
        return value
    except Exception:
        return preview()


def _clamp_loglevel(loglevel: int) -> int:
    try:
        level = int(loglevel)
    except Exception:
        level = 1
    if level < 0:
        return 0
    if level > 3:
        return 3
    return level


def _line_category(line: str) -> str | None:
    match = _LOG_CATEGORY_RE.search(line)
    return match.group(1) if match else None


def _filter_logs(lines: list[str], loglevel: int) -> list[str]:
    """0 仅警告错误；1 加指定类别；2 排除杂项类别；3 保留全部。"""
    level = _clamp_loglevel(loglevel)
    if level >= 3:
        return list(lines)
    keep = set(_LOG_KEEP)
    drop = set(_LOG_DROP)
    out: list[str] = []
    previous_kept = False
    for line in lines:
        cat = _line_category(line)
        severity = _SEVERITY_RE.search(line)
        severe = bool(severity)
        if level == 0 and cat and cat.startswith('LogSlate') and severity and severity.group(1).lower() == 'warning':
            previous_kept = False
            continue
        if cat is None:
            if previous_kept or severe:
                out.append(line)
            continue
        previous_kept = severe or (level == 1 and cat in keep) or (level == 2 and cat not in drop)
        if previous_kept:
            out.append(line)
    return out


def _between(lines: list[str], begin: str, end: str) -> list[str]:
    start_i = end_i = -1
    for i, line in enumerate(lines):
        if begin in line:
            start_i = i
        if end in line:
            end_i = i
    if start_i < 0:
        return []
    chunk = lines[start_i + 1 : end_i] if end_i > start_i else lines[start_i + 1 :]
    return [ln for ln in chunk if ln.strip() and begin not in ln and end not in ln]


def _session_log_path(marker: str) -> str:
    """根据本次调用的日志标记查找当前进程的日志文件。"""
    log_dir = unreal.Paths.project_log_dir()
    candidates = []
    try:
        for name in os.listdir(log_dir):
            if not name.lower().endswith('.log'):
                continue
            path = os.path.join(log_dir, name)
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            candidates.append((mtime, path))
    except OSError:
        return ''
    for _, path in sorted(candidates, reverse=True):
        try:
            start = max(0, os.path.getsize(path) - 65536)
            if any(marker in line for line in _read_tail_lines(path, start)):
                return path
        except OSError:
            continue
    return ''


def _read_tail_lines(path: str, start: int) -> list[str]:
    try:
        with open(path, 'rb') as handle:
            handle.seek(start)
            data = handle.read()
    except OSError:
        return []
    if not data:
        return []
    text = None
    for encoding in ('utf-8', 'utf-16'):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = data.decode('utf-8', 'replace')
    return text.splitlines()


def _toolset_tail(begin: str, end: str, max_entries: int, truncations=None) -> list[str]:
    getter = getattr(getattr(unreal, 'LogsToolset', None), 'get_log_entries', None)
    if getter is None:
        return []
    try:
        raw = getter('', '', max_entries)
    except Exception:
        return []
    lines = [str(item) for item in (raw or [])]
    if len(lines) >= max_entries and not any(begin in line for line in lines):
        if truncations is not None:
            truncations.add('logs', 'log_window_limit', retained=0, unit='lines')
    return _between(lines, begin, end)


def _capture_logs(begin: str, end: str, start_pos: int, log_path: str, loglevel: int,
                  truncations=None) -> list[str]:
    unreal.log_flush()
    lines: list[str] = []
    if log_path:
        lines = _between(_read_tail_lines(log_path, start_pos), begin, end)
    if not lines:
        lines = _toolset_tail(begin, end, _TOOLSET_WINDOW, truncations)
    return _filter_logs(lines, loglevel)


def _trim_logs(logs: list[str], truncations=None) -> list[str]:
    trimmed = list(logs)
    extra = 0
    if len(trimmed) > _MAX_LOG_LINES:
        if truncations is not None:
            truncations.add('logs', 'log_lines_limit', len(trimmed), _MAX_LOG_LINES, 'lines')
        extra = len(trimmed) - _MAX_LOG_LINES
        trimmed = trimmed[:_MAX_LOG_LINES]
    size = sum(len(line) for line in trimmed)
    if size > _MAX_LOG_CHARS:
        kept: list[str] = []
        used = 0
        for line in trimmed:
            if used + len(line) > _MAX_LOG_CHARS:
                extra += len(trimmed) - len(kept)
                break
            kept.append(line)
            used += len(line) + 1
        trimmed = kept
        if truncations is not None:
            truncations.add('logs', 'log_characters_limit', size,
                            sum(len(line) for line in kept), 'characters')
    if extra:
        trimmed.append(f'... truncated {extra} log lines')
    return trimmed


def _pack(ok: bool, result: Any, logs: list[str], error: str | None, truncations=None) -> str:
    if truncations is None:
        truncations = _Truncations()
    payload = {
        'ok': ok,
        'result': _json_ready(result, truncations=truncations) if ok else None,
        'logs': _trim_logs(logs, truncations),
        'error': error,
    }
    truncations.apply(payload)
    def encode(value):
        return json.dumps(value, ensure_ascii=False, allow_nan=False,
                          default=lambda o: repr(o)[:_MAX_REPR])

    text = encode(payload)
    if len(text) > _MAX_JSON:
        # 先缩短最大的字段，再重新编码，避免截断 JSON 结构。
        for field in sorted(('result', 'logs', 'error'),
                            key=lambda key: len(encode(payload[key])), reverse=True):
            if len(encode(payload)) <= _MAX_JSON:
                break
            original = payload[field]
            preview = original if isinstance(original, str) else encode(original)
            detail = truncations.add(field, 'json_limit', len(preview), 0, 'characters')
            truncations.apply(payload)
            def replace(size):
                value = preview[:size] + ' ... <truncated>'
                payload[field] = [value] if field == 'logs' else value
                if detail is not None:
                    detail['retained'] = size
            replace(0)
            if len(encode(payload)) > _MAX_JSON:
                continue
            low, high = 0, len(preview)
            while low < high:
                mid = (low + high + 1) // 2
                replace(mid)
                if len(encode(payload)) <= _MAX_JSON:
                    low = mid
                else:
                    high = mid - 1
            replace(low)
        text = encode(payload)
    return text


def run_code(code: str, loglevel: int = 1) -> str:
    """执行编辑器 Python，返回包含 ok、result、logs 和 error 的 JSON。"""
    level = _clamp_loglevel(loglevel)
    if not code or not str(code).strip():
        return _pack(False, None, [], 'empty code')

    ns = _session()
    marker = f'MCPTOOLS_{uuid.uuid4().hex[:10]}'
    begin, end = f'{marker}_BEGIN', f'{marker}_END'
    unreal.log(begin)
    unreal.log_flush()
    log_path = _session_log_path(begin)
    start_pos = 0
    if log_path:
        try:
            start_pos = max(0, os.path.getsize(log_path) - 65536)
        except OSError:
            start_pos = 0

    result = None
    error = None
    ok = True
    try:
        import mc_parallel
        before = set(mc_parallel._active_async)
        result = _capture_async(ns, execute_snippet(str(code), ns), before)
    except Exception as exc:
        ok = False
        tb = traceback.format_exc().rstrip()
        error = f'{type(exc).__name__}: {exc}\n{tb}'
        try:
            unreal.log_error(tb)
        except Exception:
            pass
    finally:
        unreal.log(end)

    truncations = _Truncations()
    logs = _capture_logs(begin, end, start_pos, log_path, level, truncations)
    return _pack(ok, result if ok else None, logs, error, truncations)


@unreal.uclass()
class PythonTools(unreal.ToolsetDefinition):
    """供 MCP 客户端调用的编辑器 Python 工具。"""

    @toolset_registry.tool_call
    @staticmethod
    def run(code: str = '', loglevel: int = 1) -> str:
        """在编辑器中执行 Python，返回结果和日志。
        
        自动提供 unreal 和 mineprep，每次调用更新模块引用。变量保留到 reset()。
        
        Args:
            code: Python 代码。最后一条表达式的值作为 result 返回。
            loglevel: 日志级别。0 仅警告、错误及后续行（排除 LogSlate* 警告）；1 默认加上 Python、Temp、
                BlueprintUserMessages；2 过滤 Slate、HTTP、MCP 等杂项；3 不过滤。
        
        Returns:
            JSON，包含 ok、result、logs 和 error。UObject 返回路径和可用的名称。
            print 和引擎日志统一放在 logs 中；内容截断时附带 truncated 和截断详情。
            结果是 asynctask 句柄时返回 pending 状态，并把句柄存在 _async。"""
        return run_code(code, loglevel)

    @toolset_registry.tool_call
    @staticmethod
    def reset() -> str:
        """清空会话变量；下次 run 时重新提供 unreal 和 mineprep。"""
        reset_session()
        return _pack(True, 'reset', [], None)


def register() -> bool:
    """注册 mcptools.PythonTools，可重复调用。"""
    from toolset_registry.registration import Registration

    if not unreal.ToolsetRegistry.is_available():
        unreal.log_warning('[mcptools] ToolsetRegistry unavailable')
        return False
    try:
        unreal.ToolsetRegistry.unregister_toolset_class(PythonTools)
    except Exception:
        pass
    if not Registration([PythonTools]).register():
        unreal.log_warning('[mcptools] register_toolset_class failed')
        return False
    unreal.log('[mcptools] MCP toolset mcptools.PythonTools registered')
    return True
