# MC 标题生成器

用 Minecraft Title Generator 的模型字库生成立体标题，支持字体变体、多行文字和五种输出。不支持中文或系统字体。

在模组管理器启用「MC标题生成器」，或在 UE Python 控制台运行：

```python
import mineprep
mineprep.mods.register('mods.TitleGenerator')
```

首次点击顶部左侧「刷新资源」，从原作者仓库一次下载全部受支持的模型、贴图、叠加层和 ABC 示例；状态显示在按钮右侧。模组不附带素材，启动、选择和生成均只读取本地缓存，刷新完成后可离线使用。

输入文字，选择字体、外观和输出模式，点击「新建标题」。选中标题根物体或任意输出对象，点击「追加文字」。左右分栏可拖动、独立滚动；底部操作区固定，面板关闭时保存设置。

## 排版与外观

- 多行共享设置。忽略首尾空行，中间空行保留行距但不生成网格。每行最多 256 个字符，不支持的字符会报告输入行号。
- 主标题在批次内从上到下排列；行号向上递增，后续追加的主标题批次位于已有行上方。底部、小字各自沿原有方向递增。可指定起始行号。
- 模型正面朝 UE +X、Z 向上，正面视角从左到右沿 −Y 排列；位置单位为厘米，默认字号 100 cm。根物体可整体移动、旋转和缩放。
- 大写 A 使用苦力怕字形，小写 a 使用普通字形。保留原字库字距修正、端部装饰和自动外框；字距、行距最小值为 0。
- 支持预制图集及变体、本地图集、双色渐变、单层叠加、整体染色和描边颜色。本地图集须匹配字体 UV；合图保留 Alpha。
- 默认无光照；场景受光模式让主体参与灯光，反向描边保持无光照、不投影。单面 Masked 母材质自动创建。
- 网格使用全精度 UV，保留有符号的反向外壳及正确的顶／底面映射，避免黑色描边缺口。

字体、贴图和叠加层下拉框的展开条目及选中项均显示 48×24 等比缩略图。字体使用 Flat 示例，贴图使用对应变体示例，叠加层使用原版深灰字底的效果示例（含「无」）；这些图片随刷新资源缓存，无需额外生成。右上角共用同一纹理缓存。渐变／本地模式仅展示基础字形，不预览输入文字、染色或叠加。PNG 首次使用时创建瞬态纹理，关闭面板释放；刷新资源后清空纹理缓存。缺图提示刷新，不自动联网，也不阻止生成。

## 五种输出

| 模式 | `output_mode` | 输出 |
|---|---|---|
| 完整模型 | `merged` | 每个非空行一个网格、一个 Actor，枢轴位于整行底部中心 |
| 多个 Actor（默认） | `actors` | 每字独立、底部中心枢轴，适合逐字动画 |
| 实例化网格体（CPU） | `ism` | 每种字形一个 ISM Actor |
| PCG（GPU） | `pcg` | 现有 PCG 蓝图读取模型列表和结构纹理 |
| Niagara（GPU） | `niagara` | 现有 Niagara 蓝图读取模型列表和结构纹理 |

每批次共享图集、材质和重复字形网格；CPU／GPU 可跨行合批。追加可独立选择模式，不重新生成已有行。GPU 每组最多 256 种模型，PCG 按类型数均分，Niagara 使用公共成本分组函数，无需启用 WorldGenerator。

输出位于 `/Game/mc/titles/<独立名称>/Line…`，同名自动递增；根物体标签仅保存输出路径和各布局行计数。母材质位于 `/Game/mc/titles/_Materials`。

「Actor标签」默认为空，自动取文本首个非空行去除首尾空白后的前 16 个字符。填写时使用自定义标签，不受 16 字符限制；根空物体及其下方的所有输出 Actor 均通过 `mineprep.set_actor_label` 设置此标签，重名自动添加数字后缀。脚本对应 `options['name']`；追加时只设置本批次新增 Actor 的标签，保留原根物体标签。

模组缓存位于 `TitleGenerator/__pycache__`：`cache/` 保存下载素材及来源许可证，`atlases/` 保存合成图集源文件，`instances/` 保存 GPU 编码源文件。设置也保存在此目录，打包时整个目录排除。清理生成源文件不影响已经导入的 UE 贴图，但这些文件将不能用于原文件重导入。

## Python 调用

在 UE 主线程提交，无需打开面板：

```python
from mods.TitleGenerator import ops

# 首次单独运行，等待 refresh.done 后再生成。
refresh = ops.refresh_catalog(progress={})

# 在后续编辑器帧中确认 refresh.done 且没有 refresh.error，再运行：
job = ops.generate('MINEPREP\nTITLE GENERATOR', options={
    'name': 'MyTitle', 'source': 'gradient',
    'gradient_top': '#FFCF76', 'gradient_bottom': '#DA371E',
    'height_cm': 100, 'location': (0, 0, 200),
    'output_mode': 'actors',
})

# 后续调用，不要在主线程循环等待：
# print(job.done, job.error)
# if job.done and not job.error:
#     more = ops.generate('SUBTITLE', parent=job.result['root'],
#                         options={'layout': 'bottom', 'output_mode': 'merged'})
```

- `ops.catalog(font='minecraft-ten')`：只读取本地目录，返回 `font/fonts/textures/overlays`；未缓存时返回空选项。
- `ops.refresh_catalog(*, font='minecraft-ten', refresh=True, progress=None, on_done=None)`：异步刷新全部素材，唯一正常联网入口。`refresh=False` 只读取本地目录；进度含 `stage/downloaded/done/total`。失败保留已有缓存，取消停止后续写入。
- `ops.generate(text, *, parent=None, options=None, on_done=None)`：新建或追加一批文字，返回 Mineprep AsyncTaskRunner，通过 `done/result/error` 查询，成功后 `on_done(result)` 只调用一次。

结果含 `root/actors/output_mode/character_count/line_count/render_state`、`characters/decorations`、`asset_path/line_path/assets/timings`。`line_count` 是非空行数，`line_path` 指本批次目录。`characters/decorations` 仅逐字 Actor 模式有值。

GPU 返回 `render_state='pending'` 表示资产已保存、Actor 已配置，实际 GPU 生成仍需后续帧；其他模式返回 `ready`。失败或取消清理本批次新增 Actor，保留已经写入的资产并报告目录；不改变原标题行计数。`destroy()` 停止后续任务，模组卸载会取消自身任务。

选项与默认值见 `ops.DEFAULTS`。颜色使用 `#RRGGBB`，叠加方式为 `normal/multiply/screen/overlay`，不透明度 0～1；`row=None` 自动递增。切换面板选项不会修改已生成对象。

## 来源

模型、图集、示例和排版设计来自 Ewan Howell 的 [Minecraft Title Generator](https://github.com/ewanhowell5195/MinecraftTitleGenerator)，实现参考原版 JS 与本地 Blender 版。下载仅读取 JSON／PNG 和作者许可证，不执行远程脚本；素材授权说明见缓存中的 LICENSE.md。无需额外 Python 依赖。
