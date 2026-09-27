# Python 调用

在 UE 编辑器的 Python 中可以直接转换、烘焙动画，不必打开本模组面板。传入角色和关卡序列，避免依赖当前选择。下面的 `actor` 是已有的骨骼网格体 Actor，JSON 路径请换成自己的文件。

```python
from mods.BedrockAnimator import ops, util

seq = util.open_or_create_sequence('/Game/mc/anim/LS_Wave')
job = ops.apply_animation(
    'E:/animations/wave.animation.json', actor,
    sequence=seq, time_scale=1.0, start_time=0.0,
    resize_playback=True, save=True,
)
```

转换会先准备 Control Rig，等编辑器一帧后写键。稍后的 Python 调用中查看 `job.done`、`job.error` 和 `job.result`，不要在编辑器主线程里循环等待。结果包含 `keys`（控制器写键次数）、`channel_keys`（实际通道键数）、`skipped`（未找到的骨骼）、`actor` 和 `sequence`。失败会记录在 `job.error`，成功后可继续烘焙：

```python
assert job.done and not job.error
anim = ops.bake_animation(actor, seq, '/Game/mc/anim/Wave')
```

apply_animation 的 `bone_map` 可传字典或原面板中的字典文本；省略时使用原默认映射，传 `{}` 时按同名骨骼和 xyz 轴处理。时间参数均为秒，`time_scale` 必须大于零。只读取 JSON 中的第一个动画。

转换保留原来的行为：清除目标角色所用 Control Rig 轨道上的旧键，再写入动画。默认不修改播放范围、不保存序列；示例显式开启了这两项。烘焙会保存并更新同路径的 AnimSequence，已有资产必须类型及骨架匹配。只传名称时，创建辅助和烘焙使用 `/Game/mc/anim`。

所有调用都在 UE 主线程执行。等待期间不要切换 Sequencer 或对同一序列并发写键；切换后任务会报错退出。需要取消时，在任务尚未完成时调用 `job.destroy()`；它停止后续写键，但不回滚已经创建的绑定，也不会把 `done` 改成 True。重载前先完成或取消脚本任务。

原面板仍调用同一套实现，名称同步和按钮功能保持原样。`apply(mod)` 现在也返回异步句柄，不再立即返回键数；`bake(mod)` 仍返回动画资产。
