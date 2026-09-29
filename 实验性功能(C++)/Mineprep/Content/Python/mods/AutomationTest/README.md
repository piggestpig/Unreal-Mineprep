# Python 调用

在 UE 主线程中显式选择用例，无需打开测试面板：

```python
from mods.AutomationTest import ops
job = ops.run_cases(['spawn_oak'])
# 在稍后的 Python 调用中查看；不要阻塞主线程等待。
job.status()
# job.cancel()
```

现有 ID 为 `spawn_oak`、`mob_spawner`、`intro_tutorial`。这些是会生成场景或渲染的演示，后两项仍依赖主生成器面板，不是无副作用单元测试。接口不默认运行全部项目，也不自动清理演示产物。

`status()` 返回队列状态、逐项结果和队列错误。逐项记录 `id/state/result/error/seconds`，只有函数及其返回的生成器、AsyncTaskRunner 或带 `status()/cancel()` 的模组任务实际完成后才判定。同步返回 False、字典 `ok=False` 或异常均为失败；失败后继续下一项，未知异步类型报错。所有项目通过时队列为 `completed`，存在失败为 `failed`，取消为 `cancelled`。

可传 `on_progress(item, text, color)` 和 `on_done(job)`，在主线程收到状态或原用例的进度通知。任务先返回句柄再执行。取消只停止后续用例及当前返回的可取消任务；不会回滚已生成的资产，也不能中断正在执行的同步 UE 操作。面板关闭只取消自己发起的队列，模组卸载取消本模组活动队列。
