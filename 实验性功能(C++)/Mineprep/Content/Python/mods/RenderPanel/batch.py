"""项目内的配置库与顺序动画／HDR 队列；关闭 UI 不影响当前批次。"""
from copy import deepcopy
from pathlib import Path
from weakref import WeakSet

import mineprep
import unreal
from mineprep import i18n

from . import ops
from .presets import Store, name_text

_store = None
_panels = WeakSet()
_state = dict(running=False, stopping=False, index=0, total=0, current='', current_id=None, error=None, active_ids=[])


class RenderPanelQueueSettings(mineprep.PropertyGroup):
    _unique_ = True
    _autosave_ = True
    RemoveCompleted: bool = False


def get_store():
    global _store
    if _store is None:
        _store = Store(Path(unreal.Paths.project_dir()).resolve())
    return _store


def get_state():
    return dict(deepcopy(_state), items=deepcopy(get_store().queue),
                phase=(ops._active or {}).get('phase', ''),
                background_count=sum(bool(job.get('render_released')) for job in ops._background.values()))


def _changed():
    for panel in list(_panels):
        try:
            panel.refresh_queue()
        except Exception as exc:
            mineprep.warn(i18n('刷新渲染队列界面失败：{exc}').format(exc=str(exc)))


def edit_queue(action, *args, **kwargs):
    """编辑未来任务；当前项从提交到收尾期间保持不变。"""
    if action not in ('enqueue', 'enqueue_settings', 'update_item', 'move_item', 'remove_item',
                      'copy_item', 'requeue', 'clear_finished'):
        raise ValueError(i18n('未知队列操作：{action}').format(action=str(action)))
    if (args and args[0] in _state['active_ids']
            and action in ('update_item', 'move_item', 'remove_item', 'requeue')):
        raise RuntimeError(i18n('当前任务仍在运行'))
    store = get_store()
    if action == 'enqueue' and store.preset(args[0]).get('context') == 'current':
        preset = store.preset(args[0])
        result = store.enqueue_settings(str(name_text(preset)), preset['backend'], ops._preset_settings(preset),
            kind=preset.get('kind', 'animation'), preset_id=preset['id'])
    else:
        result = getattr(store, action)(*args, **kwargs)
    _changed()
    return result


def enqueue_hdr(options=None):
    """固定当前帧与参数，加入一个 SDR → HDR → 合成任务；不会启动渲染。"""
    from . import hdr
    if (ops._active or {}).get('legacy_switching'):
        raise RuntimeError(i18n('HDR 切换中，请使用预设或等待当前项结束'))
    settings = hdr.capture_settings(options)
    return edit_queue('enqueue_settings', 'HDR JPG', 'MRQ', settings, kind='hdr')


def stop_after_current():
    if _state['running']:
        _state['stopping'] = True
        _changed()


def _pending(item_ids=None):
    return [row for row in get_store().queue if row['enabled'] and row['state'] == 'pending'
            and (item_ids is None or row['id'] in item_ids)]


def run_queue(*, item_ids=None, on_item_done=None, on_done=None, remove_completed=None):
    """按当前顺序逐项取任务；item_ids 用于只执行“立即渲染”的新任务。"""
    ops._idle_subsystem()
    item_ids = set(item_ids) if item_ids is not None else None
    if not _pending(item_ids):
        raise ValueError(i18n('没有已启用的待渲染任务'))
    if remove_completed is None:
        remove_completed = RenderPanelQueueSettings().RemoveCompleted
    owner = object()
    ops._batch_owner = owner
    _state.update(running=True, stopping=False, index=0, total=len(_pending(item_ids)),
                  current='', current_id=None, error=None, active_ids=[])
    try:
        task = _run(item_ids, owner, on_item_done, remove_completed)
        if on_done:
            task.on_done = on_done
        _changed()
        return task
    except Exception:
        ops._batch_owner = None
        _state['running'] = False
        raise


@mineprep.asynctask
def _run(item_ids, owner, on_item_done, remove_completed):
    results = {}
    launched = []
    children = []
    success = False
    failed = False
    try:
        yield 0  # 退出 Slate 回调，给调用方时间接收句柄。
        while children or _pending(item_ids):
            settled = False
            for item, child, launch_error in list(children):
                if child is not None and not child.done and child.gen is not None:
                    continue
                result = child.result if child is not None and child.done and not child.error else None
                error = launch_error or (child.error if child is not None else None)
                if child is not None and not child.done:
                    error = str(i18n('渲染协程已被停止，UE 渲染可能仍在收尾'))
                if error:
                    state = 'failed'
                else:
                    state = 'completed' if result['success'] else 'incomplete'
                    if state == 'incomplete':
                        error = '; '.join(result.get('errors', [])) or str(i18n('渲染失败或已取消，未完整完成'))
                get_store().update_item(item['id'], state=state, result=result, error=error)
                row = deepcopy(get_store().item(item['id']))
                results[item['id']] = row
                children.remove((item, child, launch_error))
                _state['active_ids'].remove(item['id'])
                if _state['current_id'] == item['id']:
                    _state['current_id'] = None
                if on_item_done:
                    try:
                        on_item_done(deepcopy(row))
                    except Exception as exc:
                        mineprep.warn(i18n('渲染项完成回调失败：{exc}').format(exc=str(exc)))
                if remove_completed and state == 'completed' and any(
                        row['id'] == item['id'] and row['state'] == 'completed' for row in get_store().queue):
                    get_store().remove_item(item['id'])
                failed = failed or state != 'completed'
                settled = True
            if settled:
                _changed()
                yield 0  # 完成结算后下一帧才提交新的渲染。
                continue
            rendering = any(child is not None and not child.done and not any(
                state.get('task') is child and state.get('render_released')
                for state in ops._background.values()) for _, child, _ in children)
            failed = failed or any(state.get('render_released') and state.get('finished') and not state.get('success')
                                   for state in ops._background.values() if state.get('queue_id') in _state['active_ids'])
            pending = _pending(item_ids)
            if not rendering and pending and not failed and not _state['stopping']:
                item = deepcopy(pending[0])
                launched.append(item['id'])
                title = str(i18n('HDR JPG · 第 {frame} 帧').format(frame=item['settings']['frame'])) if item.get('kind') == 'hdr' else item['label']
                _state.update(index=len(launched), total=len(launched) + len(pending) - 1,
                              current=title, current_id=item['id'])
                _state['active_ids'].append(item['id'])
                get_store().update_item(item['id'], state='running', result=None, error=None)
                child, error = None, None
                try:
                    if item.get('kind') == 'hdr':
                        from . import hdr
                        child = hdr._start_pair(item['settings'], notify=False, owner=owner)
                    else:
                        kwargs = {'kind': 'still'} if item.get('kind') == 'still' else {}
                        child = ops._start_animation(item['settings'], item['backend'], notify=False, owner=owner, **kwargs)
                    for state in ops._background.values():
                        if state.get('task') is child:
                            state['queue_id'] = item['id']
                except Exception as exc:
                    error = f'{type(exc).__name__}: {exc}'
                children.append((item, child, error))
                _changed()
            elif not children:
                break
            yield 0
        success = bool(results) and not _pending(item_ids) and all(row['state'] == 'completed' for row in results.values())
    except Exception as exc:
        _state['error'] = f'{type(exc).__name__}: {exc}'
        mineprep.warn(i18n('渲染队列已停止：{exc}').format(exc=str(exc)))
    finally:
        try:
            if not success:
                mineprep.prints(i18n('渲染队列已停止，未执行项已保留'))
            output_dir = str(Path(unreal.Paths.project_dir()).resolve() / 'Saved/MovieRenders')
            ops._finish(ops._runtime_settings(), output_dir, success, label=i18n('批量渲染完成'), refresh=False)
        except Exception as exc:
            mineprep.warn(i18n('队列已结束，但完成通知失败：{exc}').format(exc=str(exc)))
        finally:
            ops._batch_owner = None
            _state.update(running=False, current_id=None, active_ids=[])
            _changed()
    return dict(success=success, stopped=not success, items=[results[key] for key in launched if key in results], error=_state['error'])
