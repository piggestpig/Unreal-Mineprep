# UE 动画制作速查

**已有角色和 AnimSequence** 时，可以跳过模型构建与 JSON 导入，直接用 `mineprep.actor(actor).play_anim(anim, start=0, end=171, sequence=seq)` 上轨。整数是帧，浮点数是秒。省略 `end` 时覆盖一个周期，延长片段可循环。

**需要新角色和源动画** 时，可在 UE Python 控制台或 Mineprep Python MCP 中运行以下两步。提交异步任务后让编辑器推进，再执行下一步。

## 1. 按英文 ID 构建并放置模型

```python
import mineprep
import unreal
from mods.VanillaMobLoader import api
from mods.MCAnimConverter import library, ops

build_job = api.spawn(
    'player', name='ShotSteve', try_split_head=True,
    target=(unreal.Vector(120, 1680, 0), False),
)
```

`api.spawn()` 支持直接传英文 ID（如 `'player'`、`'player_slim'`、`'pig'`、`'warden'`）或目录 key（多模型组合传列表），内部自动加载目录、查找、构建并放置。需要模糊搜索或查看变体时可改用 `catalog_job = api.load_catalog()` + `catalog.search(...)` + `api.build_entity(...)` + `importer.place(...)`。

## 2. 写入动作

```python
assert build_job.state == 'completed', build_job.status()
result = build_job.result
assert result['rig_profile'] == 'biped', result['source']
actor = result['actor']
anim_job = ops.apply_animation(
    'animation.mineprep.player.walk_mojang', actor,
    sequence='/Game/mc/anim/LS_ShotSteve',
    start_time=0.0, resize_playback=True, save=True,
)

# 等 anim_job 完成后，可用 bones 仅重写走姿的头和右臂
assert anim_job.done and not anim_job.error, anim_job.error
upper_body_job = ops.apply_animation(
    'animation.mineprep.player.walk_mojang', actor,
    sequence='/Game/mc/anim/LS_ShotSteve',
    bones=['head', 'right_arm'], start_time=0.0,
)
```

`target=(位置, False)`（或直接传 `unreal.Vector`）使用明确的 UE 厘米坐标，省略 `target` 则按视口放置。每次调用 `spawn()` 或 `place()` 都会新增 Actor。继续给同一个角色加动作时，复用返回的 `actor` 和序列。

`try_split_head` 默认关闭。成功拆分时，一体、身体和头部模型存于同一文件夹，共用材质和贴图。用 `importer.place(result['head_mesh'])` 可单独放置头部，用 `result['full_mesh']` 可放置一体模型。

`apply_animation()` 支持直接传本地索引中的完整 `clip` 键（也可用 `library.catalog()` / `library.info()` 查询 `source`、`skeleton`、`loop`、`source_version`），或传外部 `.json` / `.bbmodel` 路径、内存动画字典。公开发行包仅保留 `Anim/custom/` 自制库（含 `walk_mojang`、`run_mojang`、`quadruped.walk_mojang`、`quadruped.run_mojang` 与由 `Anim/custom/authors/` 生成的 `wolf.play_bow`）、排除本地 `Anim/vanilla/`，未收进索引的外部动作可传入文件路径或字典。Java 生物动作使用匹配的模型骨架或对应编辑骨架（`biped` 已含 `villager` 系抱臂人形与 `copper_golem`，`quadruped_edit` 已含 `pig`、`wolf`、`fox`、`cow`、`cat`、`llama`、`camel`、`horse`、`armadillo`、`ravager` 等 37 个四足及幼体）；Bedrock 支持 `skeleton_mode='biped'`（玩家参考骨架，含 `walk_mojang` 等，不自动回退；无独立双臂的 `villager` 等人形复用玩家动作时需传 `ignore_missing_bones=True`）、`skeleton_mode='quadruped'`（`quadruped` 走跑重定向上原始与 `quadruped_edit` 四足骨架）与 `skeleton_mode='local'`（零绑定旋转 `<= 0.1°` 局部偏移动画，如直接控制 `pelvis`/`upper_body`/`real_tail` 的 `wolf.play_bow`），并用 `ignore_missing_bones=True` 在目标校验通过后按共有骨骼跳过多余源骨骼（跨生物复用时若仅需部分部位，还可配合 `bones=[...]`）。自研片段导入前可用纯 Python `mods.MCAnimConverter.contact.analyze_contacts()` 检查支撑接地高度、滑步与关节脱节。Blockbench 外部 `.bbmodel`（`format_version="5.0"`、`model_format="free"`，可用 `list(library.clips(...))` 列出片段）支持 `step`、`linear`、`catmullrom` 与加权 `bezier` 曲线及多轴耦合旋转；工程骨骼层级和绑定局部姿势（位置容差 `1.0 cm`、零绑定旋转与单位缩放）须与目标 UE 角色匹配，且不包含 MoLang / 非正缩放。

```python
# 四足生物走／跑复用示例（索引骨架 quadruped 自动启用 quadruped 重定向模式）
quad_job = ops.apply_animation(
    'animation.mineprep.quadruped.run_mojang', pig_actor,
    sequence='/Game/mc/anim/LS_ShotPig',
    start_time=0.0, resize_playback=True, save=True,
)

# 直接导入外部 .bbmodel 工程中的曲线动画
bb_job = ops.apply_animation(
    'path/to/Mineprep_Biped_Curves.bbmodel', actor,
    clip='animation.mineprep.demo.04_bezier_single',
    sequence='/Game/mc/anim/LS_ShotSteve',
    start_time=0.0, resize_playback=True, save=True,
)
```

Catmull-Rom 区间端点使用双值 `pre/post` 时会在预检时报错；请改用 Linear / Bezier，或先烘焙为采样动画。

## 检查结果或烘焙

```python
assert anim_job.done and not anim_job.error, anim_job.error
res = anim_job.result
seq = res['sequence']
# 可传 start/end（int 帧或 float 秒，半开区间 [start, end)）；省略时沿用序列播放范围
assets = ops.bake_animation(actor, seq, '/Game/mc/anim/AN_ShotSteve',
                            start=res['start_frame'], end=res['end_frame'])
```

`assets['body']` 是身体动画；拆分模型还会返回 `assets['head']`，资产名称追加 `_Head`。普通模型的 `head` 为 `None`。拆分模型的头部子骨骼会同步导入和烘焙，Head 根 `head` 不重复接收身体的头部运动。

在新的序列中播放烘焙结果（本例使用 60 fps），原地循环移动时按推荐地面速度（如 `walk_mojang` `170 cm/s`、`run_mojang` `480 cm/s`、`quadruped.walk_mojang` 猪 `70 cm/s` / 狼 `80 cm/s`、`quadruped.run_mojang` 猪 `140 cm/s` / 狼 `170 cm/s`）关键帧推进 Actor X 位置，并可用 `mods.RenderPanel.ops.render_preset('quick_video', sequence=playback.target, name='Preview/Out')` 输出 MP4 快速目检：

```python
playback = mineprep.new_sequence('ShotSteve_Baked', fps=60,
    duration=assets['body'].get_play_length(), open=True)
end = playback.target.get_playback_end()
# 支持直接传入 bake_animation 返回的 {'body', 'head'} 字典，或 head=...
sections = mineprep.actor(actor).play_anim(assets, start=0, end=end, sequence=playback)
```

如果只从 `SkeletalMesh` / 资产路径直接生成 `AnimSequence`（无需打开 Sequencer 或放置 Actor）：

```python
from mods.MCAnimConverter.ops import export_anim_sequence

direct = export_anim_sequence(
    'animation.mineprep.player.walk_mojang',
    ('/Game/.../SKM_Villager', '/Game/.../SKM_Villager_Head'),
    '/Game/Animations/Walk_Villager',
    fps=60,
    ignore_missing_bones=True,
)
# 返回的 {'body', 'head', ...} 同样可直接传给 play_anim(...)
sections = mineprep.actor(actor).play_anim(direct, start=0, end=direct['frames'], sequence=playback)
```

想用面板操作时，在 VanillaMobLoader 选择玩家条目并放置，再在 MCAnimConverter 选中场景 Actor 和 Clip，点击「写入 Sequencer」。
