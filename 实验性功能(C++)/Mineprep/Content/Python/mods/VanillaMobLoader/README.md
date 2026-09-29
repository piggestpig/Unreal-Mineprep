# Python 调用

在 UE 主线程中加载目录、构建资产，不必打开模组面板：

```python
from mods.VanillaMobLoader import api, importer
catalog_job = api.load_catalog()  # 优先缓存；refresh=True 强制重新下载目录
```

每步任务均按编辑器帧推进。在后续 Python 调用中检查状态，再开始依赖它的下一步；不要在 UE 主线程循环等待：

```python
assert catalog_job.state == 'completed', catalog_job.status()
catalog = catalog_job.result['catalog']
choices = [(e.key, e.name) for e in catalog.search(query='pig')]
key = choices[0][0]  # 按实际目录选择；组合时传多个 key，顺序决定主模型
job = api.build_entity(catalog, [key], save_path='/Game/mc/mob/MyPig', name='MyPig')
```

```python
assert job.state == 'completed', job.status()
mesh = job.result['mesh']
actor = importer.place(mesh, scale=1.0)  # 可选；默认按当前视口放置
# 显式位置：importer.place(mesh, target=(unreal.Vector(0, 0, 100), False))
```

`job.status()` 返回 `state/result/error`；终态为 `completed/failed/cancelled`。构建结果含 `mesh/path/name/reused/warnings`，不生成 Actor。默认保存目录为 `/Game/mc/mob/`，空名称从条目推导；`layer_expansion=0.01`、`random_scale=0.001` 与面板一致。`reload=True` 重新导入，默认复用匹配的已有资产。依赖缺失、失败详情见 `error`；缺皮肤可保留中性材质并返回警告。

骨骼冲突默认失败，明确传 `conflict_policy='keep_first'` 才采用主模型骨骼；也可用 `on_conflict(conflicts)` 返回 True 接受。`load_catalog` 和 `build_entity` 都支持 `cache=目录`、`stall_timeout=10`、`on_progress(text)`、`on_stall()`、`on_done(job)`。停滞默认失败，`on_stall` 返回 True 可继续等待；所有回调在主线程调用。构建参数在提交时读取，不跟随面板选择改变。

`job.cancel()` 关闭本任务的资源并阻止后续导入；已完成的同步 UE 导入和资产写入不会回滚。下载/几何在 worker 上进行，UE 导入留在主线程。不要同时构建到同一目标。模组卸载会取消活动任务。

原面板仍保留多选、命名回填、冲突确认及缩放；普通加载在构建后放置，重新加载只更新资产。“刷新资源”的缩略图流程维持原实现，仍可能阻塞；新的 `load_catalog` 只加载目录，不预下载全部缩略图。不会解析执行 CEM 动画表达式。
