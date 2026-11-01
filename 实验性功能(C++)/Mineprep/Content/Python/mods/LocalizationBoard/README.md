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

## 翻译列

固定列序为 `Namespace, Key, Source String, zh, en, zh-Hant, zh-Hant-HK`。前三列用于 UE 绑定，不要手工改动；后四列分别填写简中、英文、台繁和港繁，港译列也必须完整填写。

旧六列表可以读取，缺少的港译列补为空并进入待翻译表。合并时保留已有港译；中文自动填充不会代填港译。导出工作表和待翻译表时统一为七列、UTF-8 BOM。

## 避免 Excel 损坏文本

CSV 不保存列类型。Excel 可能把 `+文本`、`-还原` 等值解析为公式，再保存成 `#NAME?`；CSV 的双引号只负责字段分隔，不能声明文本类型。也不要给真实 key 或源文添加单引号、制表符或 `="文本"` 包装，这些字符可能进入 UE 的绑定数据。

正式词典推荐用 VS Code 等文本编辑器维护。若必须使用 Excel：

1. 先备份 CSV，不要直接双击打开并覆盖保存。
2. 使用文本导入向导，选择 UTF-8、逗号分隔，将**所有列**的列数据格式设为“文本”。新版 Excel 可先启用“从文本（旧版）”。参见 [Microsoft 文本导入向导](https://support.microsoft.com/en-us/excel/text-import-wizard)。
3. 仅编辑四个语言列；需要反复编辑时可先保存为 `.xlsx` 副本，保留文本格式。
4. 发布 CSV UTF-8 副本后，用文本编辑器与备份比较前三列、记录顺序及特殊符号；确认没有新增 `#NAME?` 等错误，再替换正式表。重新双击 CSV 打开，仍可能触发自动转换。

已经变成 `#NAME?` 的内容无法仅靠 CSV 通用还原；应对照备份或重新收集资产元数据。收集器不会给文本添加防公式前缀，也不会自行猜测修复未知条目。

可选的 `on_progress(text)` 和 `on_done(job)` 回调都在 UE 主线程调用。任务先返回句柄再扫描，即使目录为空也会正常通知完成。一个 CSV 目录同一时间只运行一个收集或刷新操作。

面板的“取消”按钮保留已收集的阶段结果，关闭面板或卸载模组则丢弃本轮未提交的 CSV。兼容接口 `iter_gather(props, on_status, is_closed, out=None)` 继续可用；脚本调用推荐使用 `start_gather`。
