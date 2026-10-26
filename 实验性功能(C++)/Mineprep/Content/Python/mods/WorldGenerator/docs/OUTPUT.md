# 输出到 UE：准备、放置、数量上限与颜色纹理

参数速查和完整异步示例见 [Agent指南](AGENT_GUIDE.md#准备与放置仅用户要求引擎操作时执行)；本页说明各项输出设置的含义与约定。坐标与模型原点见 [CENTER_FRAME](CENTER_FRAME.md)。

## 流程

- `api.prepare(target)` 接受 WorldSpec、Scene 或单个 Structure，生成或复用完整世界，创建资源但不放 Actor；`api.place(prepared)` 放置。两者都在 UE 主线程调用并返回异步 Job，状态为 `running/completed/failed/cancelled`。用完成回调或后续查询读取结果，不要忙等或 sleep。
- 离线 `generate()` 的 World 不进入编辑器缓存；编辑器 `api.preview(spec)` 的完整世界可被同配置 prepare 复用，参考概览不能。
- 三个后端 `ism`／`pcg`／`niagara`；合并模式 `none`／`runs`／`rectangles`／`cuboids`。API 默认串行、长方体；面板新会话默认 4 进程、长方体，保存过的选择保留。
- PCG／Niagara 完成回调时 GPU 仍可能在异步生成，`instance_count=None`、`render_state='pending'`；ISM 返回已配置实例数。Job 完成不等于画面已验收。
- 已有 Actor 不自动更新；改参数后需要重新准备、放置。重复调用 place 会新增输出。
- UE 资源目录为 `/Game/mc/WorldGenerator/World_<短哈希>/`，模型在 `models/<类型>_<短哈希>/`；完整元数据校验后复用，同配置改名复用首个目录，手删资产后重新准备即可。
- 模板网格在 `templates/`；逐方块模板使用原生模型名称，例如 `SM_chorus_plant_<8位摘要>`，不把内部单格编号叠进文件名。遇到短摘要重名时才逐步延长；资源身份仍按完整元数据校验。旧资产保留，新命名在重载后重新准备资源时生效。

## 数量上限（预算）

四项数量上限互相独立：

| 参数 | 单位与检查时机 |
| --- | --- |
| `max_cells` | 二维列数（宽×深），任务入口 |
| `max_instances` | 合并前的原始输出格数，生成过程中 |
| `max_preprocess_cells` | 宽×深×输出高度，完整预览／准备开始前；面板默认 2147483647 |
| `max_output_instances` | 合并并追加整模型后的实例总数，写纹理前；面板默认 2000000 |

面板“数量上限（预处理格数／最终实例数）”对应后两项。整树／建筑每次摆放计一个实例；超限时不写输出纹理、不产生成功结果或 Actor。

## 分区与分组

- ISM“区块数”（`chunk_count`，默认 1）是空间区域总数，按最长边递归二分；每区按模型类型建 Actor，共用该区最小角原点，世界位置不变。大于 1 时关闭 BCT 并赋 None，偏好保留。`place` 沿用准备值。
- PCG／Niagara“模型分组数”（`type_group_count`，默认 1）将模型分成多个输出组（按实例数最小化各组“种类数×实例数”之和，同种模型不拆分）。每组一对 BPT／BRT 和一个 Actor，共享原点与 BCT。多组 Actor 附加到第一组，移动首项即可整体移动。
- 新 Actor 归入“输出名称”文件夹；多组标签带从 1 开始的组号，后缀冲突由公共 `set_actor_label` 处理。放置失败会清理本次全部 Actor 并取消事务。

## 群系颜色纹理（BCT）

BCT 是草方块、植物和树叶共用的调色数据，不是植被覆盖图，不改变群系或几何。

- 精度为每像素格数，默认 4（512² 世界得到 128²），先做 9×9 格局部平均再面积降采样。FP16 EXR，TC_HDR、`srgb=False`、Clamp、无 Mip、不流送。
- PCG／Niagara 使用组件局部范围 A=(0,0,0)、B=(宽,长,垂直范围)×100；ISM 按用户蓝图自动边界采样，属已接受的近似。
- 纯调色或切换模式保留 World 与预览，下一次准备只换 BCT，复用合并数据、模型和 BPT／BRT。

### RGB 与 HSV 模式

面板“群系颜色模式”（`biome_color_mode`，默认 `rgb`）选择整张纹理的编码，两套配置独立保存，模式不进入 WorldSpec。

- RGB：线性倍率，`[1,1,1]` 不变，允许大于 1；包内 `vegetation_tint`。
- HSV：`[H,S,V]`，H 范围 0.5～1.5，偏移 `(H−1)×360°`；S／V 为倍率；包内 `vegetation_hsv`。
- 群系色彩指数（`biome_color_power`，默认 1）：先对正数三分量逐项 `pow`，HSV 再取负编码，最后平滑和降采样。0 得中性色板，1 保持默认；乘方后 H 不再裁回输入范围。

**母材质约定**：RGB 原值写入，材质用 `C1*tint`。HSV 三项取负写入；材质以 `tint.r < 0` 识别 HSV，`abs(tint)` 解码后对原颜色 H 加 `H−1` 圈、S 乘 S 并限制到 0～1、V 乘 V，再转回 RGB。HSV 中性像素为 `(-1,-1,-1)`。原颜色与转换都在线性空间。母材质由用户手动维护。

内置主世界 HSV 默认（RGB 默认中性，热带草原 RGB `[1.45,0.95,0.70]`）：

| 群系 | H / S / V |
| --- | --- |
| 热带草原 | 0.90 / 0.90 / 1.00 |
| 沙漠、恶地 | 0.88 / 0.85 / 1.00 |
| 混合林 | 1.00 / 1.05 / 0.90 |
| 白桦林 | 0.99 / 0.90 / 1.03 |
| 针叶林 | 1.04 / 0.85 / 0.90 |
| 覆雪针叶林、雪原、冰刺 | 1.04 / 0.65 / 1.05 |
| 山地 | 1.02 / 0.90 / 0.95 |
| 草原、水域 | 1.00 / 1.00 / 1.00 |

```python
from mods.WorldGenerator import api

world = api.generate(api.spec(params={'terrain.flat': True}, region=(-16, -16, 32, 32)))
api.write_biome_texture(world, 'E:/ue/Mineprep_5_8/Intermediate/BCT.exr',
                        biome_color_mode='hsv', vegetation_hsv={'savanna': [0.9, 0.9, 1.0]})
# UE 主线程：job = api.prepare(world.spec, biome_color_mode='hsv', biome_color_power=2.)
```

## 方块材质覆盖

`blocks.json` 的 `material.emission`／`material.lighting`，或 prepare 的 `block_materials={'lava': {'emission': .2}}`。只接受有限非负数，显式 0 有效，允许大于 1；prepare 中字段为 None 表示取消包内该项覆盖。覆盖作用于全部材质槽，创建专用子材质与网格副本，不修改原资产；无覆盖时资源身份不变。公共导入对匹配 MCprep `blocks.emit` 的贴图默认设置发光 0.1。

## 纹理就绪

BCT 与 BPT／BRT 导入时只记录预期尺寸，由统一构建收尾检查实际平台尺寸和内存。仍未就绪会警告并返回可放置结果，但不进入成功缓存；引用缺失、身份不符、保存失败报错。不使用固定等待。
