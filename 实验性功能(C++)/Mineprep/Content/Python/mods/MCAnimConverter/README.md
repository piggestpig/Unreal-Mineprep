# MC动画转换器

从本地库或外部 JSON 选择片段，将动作写入可编辑的 FK Replace 轨，并可将序列烘焙为 AnimSequence。

要在 UE 里从零放置生物并添加动作，见 [制作速查](QUICKSTART.md)。

- **选片**。留空「动画 JSON」可浏览本地库。选择外部 `.json` 或 `.bbmodel` 文件后，下拉框列出该文件中的完整动画键。
- **Java**。每个 `.clip.json` 自带 `clip`、`bones`（名称和父级索引）、`bind`、`fps` 与 `frames`。普通片段沿用列主序 ModelPart 矩阵，可用于对应 Java 模型或 VanillaMobLoader 的编辑骨架（`biped` 与 `quadruped_edit`）。带 `space="local_trs"` 的片段保存局部位移、四元数和三轴缩放，要求目标层级和绑定姿势与源一致。青蛙鼓腮和吐舌使用此格式（暂不开启 `skeleton_mode` 与 `ignore_missing_bones`，但支持 `bones` 写入遮罩）。
- **Bedrock（多模式与共有骨骼）**。支持数值常量、线性（`linear`）、Catmull-Rom 平滑曲线（`catmullrom`）及数值 `pre/post` 跳变（含纯数字字符串）。跳变写在序列的相邻 tick 上，烘焙资产按序列显示帧率采样；MoLang 表达式、时间轴事件和游戏控制器超出当前范围。`apply_animation(..., bones=None, ignore_missing_bones=False, skeleton_mode=None)` 提供三条显式语义路径：
  - `skeleton_mode='biped'`（默认，含 `bedrock_player` 索引条目）：使用已知玩家参考骨架重定向至 VanillaMobLoader 人形骨架（兼容 `left_arm` / `left_leg` 等 snake_case，并支持仅含抱臂 `arms` 的村民系人形；复用含双臂的动作时传入 `ignore_missing_bones=True` 可跳过缺失双臂）；校验失败直接报错，不静默回退为 `local`。
  - `skeleton_mode='quadruped'`（索引 `skeleton="quadruped"` 自动选用，或显式覆盖）：将平级 MC 基岩四足动画经组件空间重定向至原始四足或 `quadruped_edit` 编辑骨架（兼容 `head -> body`、`head_parts -> head`、`neck -> head`、`hump` 与尾部父链；走／跑循环下 `body` 不会错误连带前腿和头，而源片段直接包含 `head_parts`/`neck` 时会跟随其带动 `head`；不允许源片段直接包含 `pelvis`）。
  - `skeleton_mode='local'`（显式传入或索引覆盖，如针对 `quadruped_edit` 的 `pelvis` 分层表演动画及非四足通用骨架）：将动画视为目标自身绑定姿势上的局部偏移，要求目标为 `EulerTransform` 控件且具有零绑定旋转（`<= 0.1°`）与单位绑定缩放；支持精确、大小写、camelCase/snake_case 及显式别名匹配。
  - **共享骨骼与写入遮罩**：`bones` 在建轨或打开序列前预检并限定本次写入的目标控件（`biped` 会先按完整父链解算再过滤写入，适合叠加局部上身动作）；`ignore_missing_bones=True` 跳过目标骨架缺失的源骨骼并汇总到 `skipped_bones`（若目标本身不满足前置校验，例如用 `pig` 导入 `biped` 片段，仍直接报错）。
- **Blockbench（`.bbmodel`）**。当前支持 `meta.format_version="5.0"`、`meta.model_format="free"`（通用模型），可导入单段或多动画工程中的指定片段（单动画工程可省略 `clip`，多动画工程须指定 `clip`）。支持 `step`、`linear`、`catmullrom` 与加权 `bezier` 曲线（含混合插值优先级、`pre/post` 不连续跳变及显式中性通道复位）：位移、缩放及单轴旋转优先保持稀疏/加权 UE 曲线，多轴耦合旋转自动拟合为高精度三维 Hermite 曲线。支持 `bones` 遮罩；目标骨骼须为 `EulerTransform` 控件，且名称、父级与绑定局部姿势（位置容差 `1.0 cm`、旋转零值容差 `0.1°`、缩放 `1.0`）须与导出源一致；MoLang 表达式、时间轴特效脚本、全局旋转/四元数插值开关及非正缩放过冲会明确报错。
- **头身分离**。支持 VanillaMobLoader 生成的身体与 `Head` 组件：身体保留完整动画，Head 同步接收共有且绑定局部姿势一致的子骨骼通道；根 `head` 与 Head 专属额外骨骼（如表情骨骼）保持原样，不补中性姿势也不清键。两组件使用相同时间和区间替换规则。

`.bbmodel` 的 Catmull-Rom 区间端点暂不支持双值 `data_points`（包括相等的 `pre/post`）：Blockbench 会为它裁剪样条邻点，普通四点公式无法等价还原。预检会明确拒绝；可将该区间改为 Linear / Bezier，或先烘焙为采样动画。Linear / Bezier 的首、末及单键双值跳变正常支持。

### 自制宣传片风循环动作（`Anim/custom/Bedrock/`）

随模组分发的 `Anim/custom/` 提供 4 段参考 Mojang 宣传片风格制作的原地走跑循环。下表速度是当前模型的调试起点，需结合腿长和实际支撑阶段调整；匀速移动本身不保证消除滑步。

| Clip 键 | 骨架语义 | 周期 | 建议移动速度 | 说明 |
| --- | --- | --- | --- | --- |
| `animation.mineprep.player.walk_mojang` | `bedrock_player` | `1.00s` | `~1.7 blocks/s` | 舒缓步频玩家行走 |
| `animation.mineprep.player.run_mojang` | `bedrock_player` | `0.60s` | `~4.8 blocks/s` | 参考 Blender 手 K 的前倾摆臂、腾空与后踢；腿根跟随躯干下缘 |
| `animation.mineprep.quadruped.walk_mojang` | `quadruped` | `0.90s` | `~0.7 blocks/s`（猪）/ `~0.8 blocks/s`（狼） | 四拍接地弹性漫步 |
| `animation.mineprep.quadruped.run_mojang` | `quadruped` | `0.60s` | `~1.4 blocks/s`（猪）/ `~1.7 blocks/s`（狼） | 明显左右交错四足奔跑（wolf 等额外骨骼设 `ignore_missing_bones=True`） |
| `animation.mineprep.wolf.play_bow` | `quadruped`（`skeleton_mode="local"`） | `1.60s` | 原地 | 适配 `wolf` `quadruped_edit` 层级（联动 `pelvis`/`body`/`upper_body`/`head`/`tail`/`real_tail`/四腿）的前扑邀玩摇尾循环 |

`animation.mineprep.wolf.play_bow` 的程序化生成源码保留在 `Anim/custom/authors/`，可用 `python Plugins/Mineprep/Content/Python/mods/MCAnimConverter/Anim/custom/authors/generate.py --check` 校验一致（另外 4 段 Mojang 风格走跑循环以精调后的 `Anim/custom/Bedrock/*.animation.json` 为准，不由 `generate` 覆盖）；需要离线预检脚底接触高度、支撑滑步或髋/肩关节错位时，可显式调用纯 Python 的 `mods.MCAnimConverter.contact.analyze_contacts()`（支持 `compensate_stance_root_z()` 与 `compensate_limb_attachment()` 作图前辅助）。

```python
from mods.MCAnimConverter import library, ops

# 查询本地库元数据（source / skeleton / loop / source_version）
meta = library.info('animation.mineprep.player.walk_mojang')
matches = library.catalog(skeleton='quadruped', loop=True)

# 局部写入示例：仅更新走姿的头和右臂，不覆盖其他骨骼
job = ops.apply_animation(
    'animation.mineprep.player.walk_mojang', actor,
    sequence=seq.target, start_time=0.0, bones=['head', 'right_arm'],
)

# 跨四足生物复用 quadruped 动作；若源/目标存在多余骨骼可加 ignore_missing_bones=True
qjob = ops.apply_animation(
    'animation.mineprep.quadruped.run_mojang', pig_actor,
    sequence='/Game/mc/anim/LS_Pig', resize_playback=True,
)

# 查询外部 .json / .bbmodel 文件包含的动画名称
clips = list(library.clips('path/to/Mineprep_Biped_Curves.bbmodel'))

# 也可直接导入 .bbmodel（单动画可省略 clip，多动画须指定 clip=...）
job = ops.apply_animation(
    'path/to/Mineprep_Biped_Curves.bbmodel', actor,
    clip='animation.mineprep.demo.04_bezier_single', sequence=seq.target,
    start_time=0, resize_playback=True,
)

# 直接传单个动画体字典时，需显式提供 clip 名称
custom_clip = {
    'animation_length': 1.0,
    'bones': {
        'rightArm': {
            'rotation': {
                '0.0': [0, 0, 0],
                '0.5': {'lerp_mode': 'catmullrom', 'post': [-90, 0, 0]},
                '1.0': [0, 0, 0],
            },
        },
    },
}
ops.apply_animation(custom_clip, actor, sequence=seq.target, clip='agent_wave')
```

### Bedrock 玩家源骨架与空间约定（Agent 编写动作字典参考）

- **源骨骼层级**（大小写不敏感，`hip` 会映射为 `waist`，也接受 `left_arm` / `left_leg` 等 snake_case）：`root` → `waist` → `body` → `head` / `leftArm` / `rightArm`，以及 `root` → `leftLeg` / `rightLeg`。
- **单位与坐标**：`position` 为 MC 像素单位（`1 px = 6.25 cm`，`UE (cm) = (-pz, -px, py) * 6.25`）；`rotation` 为度制欧拉角 XYZ（ZYX 顺序，如 `rightArm: [-70, 0, 0]` 向前抬臂，`head: [0, -30, 0]` 转头）；`scale` 为 `[sx, sy, sz]`（`biped` 目标要求正等比缩放）。目标 UE Control Rig 控件名与局部轴向可用 `rig.describe()` 查询；人物动作创作与通用节奏技巧见 [人物动画制作指南](../../mineprep-skills/anim-biped.md)。

传入外部路径或内存字典时：Java 片段和单片段 `animations` 容器可省略 `clip`；多片段 `animations` 字典须指定 `clip=...`；直接传入单个动画体字典（含 `bones`、不含 `animations`）时必须显式提供 `clip=...`。传入本地库完整 `clip` 键（或 `json_path=None, clip=...`）时自动按索引定位文件。`start_time` 支持整数（目标序列显示帧）或浮点数（秒）；`time_scale` 为时长倍率（`2.0` 表示时长翻倍 / 0.5x 速度，Java 与 Bedrock 采样时间及 `pre/post` 阶跃均按 `source_times * time_scale` 写入 `TICK_RESOLUTION` 并对齐周期 `loop` 结束帧）。传入新建序列路径时，通过解析与匹配后创建 60 fps 序列并设置为精确的 `[start_frame, end_frame)` 范围；已有序列沿用自身帧率，仅在 `resize_playback=True` 时按需延长、不自动缩短。导入只替换目标控件在片段区间内的键，包括子帧键。

确认 `job.done` 且 `job.error` 为空后，`job.result` 包含 `start_frame`、`end_frame`（半开区间 `[start_frame, end_frame)`，目标序列显示帧，结束帧不包含）、`keys`、`channel_keys`、`matched_bones` 与 `skipped_bones`。可用 `ops.bake_animation(actor, job.result['sequence'], '/Game/mc/anim/Example', start=job.result['start_frame'], end=job.result['end_frame'])` 烘焙：

`bake_animation(..., start=None, end=None)` 统一采用半开区间 `[start, end)`（`int` 为帧、`float` 为秒，省略边界沿用原播放范围），身体与 Head 使用相同范围烘焙为从零开始播放的 `AnimSequence`，并在 `try/finally` 中恢复序列原播放范围。返回值仍为 `{'body': AnimSequence, 'head': AnimSequence或None}`，拆分头部追加 `_Head`。

复用时在新的 Level Sequence 中可直接把 `bake_animation` 返回的字典（或 `head=`）交给现有 Actor 句柄成对播放：`mineprep.actor(actor).play_anim(assets, start=0, end=...)`（`assets['head']` 为 `None` 时自动只播身体）；也可分别传入 `target='Head'` 单独上轨。完整示例见制作速查。

### 无 UI 直写 AnimSequence

不需要编辑器关卡 Actor 或打开 Sequencer 时，可直接调用同步函数 `ops.export_anim_sequence(json_path, target, output_path, *, clip=None, fps=60, time_scale=1.0, save=True, bones=None, ignore_missing_bones=False, skeleton_mode=None)` 编译全部既有格式（`.bbmodel`、Java `.clip.json`、Bedrock `biped` / `quadruped` / `local`）并直接写入目标骨架的全骨骼局部 TRS 轨道（未动画骨骼保持绑定姿势，采样帧率与 `PlatformTargetFrameRate` 保持一致）。`target` 支持 `SkeletalMesh`、`SkeletalMeshComponent`、带 PreviewMesh 的 `Skeleton`、资产路径、`Actor`/句柄，以及拆分头 `(body, head)` 或 `{'body', 'head'}`；返回值 `{'body', 'head', 'clip', 'fps', 'frames', 'keys', 'duration', 'matched_bones', 'skipped_bones', 'saved'}` 可直接传给 `mineprep.actor(actor).play_anim(...)`。

动作库拆分为两处索引：`Anim/custom/` 存放可随模组打包分发的自制动画与 `Anim/custom/index.json`；`Anim/vanilla/` 存放本地参考原版解包动画（`Java/`、`Bedrock/` 与 `vanilla/index.json`），由 `mod_manifest.toml` 与 `.gitignore` 排除。缺少 `vanilla/` 时仍可正常工作；两份索引若存在重复 `clip` 键会明确报错。`library.catalog(skeleton=..., loop=...)` 与 `library.info(clip)` 采用统一规则查询 `source`、`skeleton`、`loop`、`source_version`、`clip`、`file` 与 `path`（索引未注明时按需回读片段 JSON，仍无法确定的保持 `None`）。同一文件可登记多个片段。用 VersionControl 更新安装包时启用 `UseModManifest`。
