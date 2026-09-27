# Python 调用

在 UE 编辑器的 Python 中导入 `ops` 即可收集变量名，无需打开模组面板。可以将 CSV 写到单独的目录；省略 `csv_root` 时仍使用工程的 `Content/Mineprep/插件贴图`。

```python
import unreal
from mods.LocalizationBoard import ops

folder = unreal.Paths.project_saved_dir() + 'LocalizationReview'
job = ops.start_gather(
    '/Game/MyAssets', csv_root=folder, set_enum_key=False,
)
```

任务按编辑器帧逐个扫描资产。在稍后的 Python 调用中用 `job.status()` 查看状态、结果和错误；不要阻塞主线程等待。正常终态是 `completed`，结果包含扫描、新增、复用、失败及待翻译数量，还有生成的 CSV 路径。单个资产失败会计入 `failed` 并继续，整个任务无法执行时状态为 `failed`，异常保存在 `job.error`。

```python
job.status()
job.cancel()                 # 取消并保存已经收集的条目
# job.cancel(False)          # 取消且不写入本轮 CSV
stats = ops.refresh_todo(csv_root=folder)  # 收集结束后再刷新待翻译表
```

CSV 保留原来的文件名、列序、已有译文复用和中文填充规则，只更新工作表及待翻译表，不覆盖原翻译表。`set_enum_key` 默认 True，会允许 C++ 收集函数写枚举 DisplayName Key；只收集时可像示例一样传 False。取消不回滚此前已发生的枚举修改。

可选的 `on_progress(text)` 和 `on_done(job)` 回调都在 UE 主线程调用。任务先返回句柄再扫描，即使目录为空也会正常通知完成。一个 CSV 目录同一时间只运行一个收集或刷新操作。

面板的“取消”保留阶段结果，关闭面板或卸载模组丢弃未提交的 CSV。原 `iter_gather(props, on_status, is_closed, out=None)` 仍可用；新脚本直接使用上面的入口即可。
