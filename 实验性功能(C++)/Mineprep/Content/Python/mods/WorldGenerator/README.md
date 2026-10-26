# WorldGenerator 0.64.7

用 Python／NumPy 生成 Minecraft 风格的大场景，输出到 UE 的 ISM、PCG 或 Niagara，用于动画渲染。不追求与原版种子逐方块一致。

脚本与 agent 入口：`from mods.WorldGenerator import api`。生成数据不需要连接 UE。

“自定义”页支持[植被分布与留空遮罩](docs/MASKS.md)：用图片减少树草，或为道路和建筑留出整片空地；也可通过API使用。

## 内置内容

| 包 | 内容 |
| --- | --- |
| 主世界 `vanilla` | 16 种群系（含森林、热带草原、恶地、冰刺、冻洋），河湖海洋、群岛、可选洞穴／峡谷／地下水、覆雪与冰体；整树模板或逐方块植被 |
| 下界 `nether` | 荒地、灵魂沙峡谷、绯红森林、诡异森林、玄武岩三角洲；岩浆海与岩浆柱、化石、矿物、火、萤石、菌树与藤蔓 |
| 末地 `end` | 默认外岛、八款高矮不同的紫颂树，可整棵或逐方块输出；完整布局包含中央岛、黑曜石柱、静态传送门及约1024格外的外岛 |

主世界顶部依次为资源包默认、默认＋洞穴、草原、混合林、白桦林、针叶林、覆雪针叶林、热带草原、山地、沙漠、恶地、雪地、冰刺之地、海洋、冻洋。“资源包默认”保持混合群系且关闭洞穴；`default_caves`只开启自然洞穴。洞穴页继续提供`caves_natural`与`caves_grand`两种风格，地下水与湖海连接默认关闭。

单群系预设ID与群系ID一致，例如`api.spec(preset='savanna')`生成热带草原。群系统计仅包含目标群系；适合的陆地景观保留河道，不另切换为河流群系。普通陆地采用接近水面的缓丘，山地保留山脊，恶地保留彩色台地。沙漠有稀疏河流，不生成湖泊和水塘；恶地与冰刺之地没有河湖，海洋和冻洋没有陆岛。脚本需要平坦地形时使用`params={'terrain.flat': True}`，其他地形参数仍可照常调整。

沙漠有低矮、弯曲的沙丘，默认高度4格、间距约64格，可在地形页高级参数中调整；沙丘沿用现有河谷塑形。独立沙漠预设默认关闭“简化植被模型”，生成1～3格仙人掌、枯木及高矮枯草；勾选后生成单格枯木、仙人掌和高枯草。两种枯草都是单格模型，整体分布稀疏。混合世界保留原有植被模式默认值。密度可在植被页调整，详见[植物说明](docs/FEATURES.md#沙漠植物)。

下界默认（资源包默认）均衡四种群系，不含三角洲；预设 `all_biomes` 加入三角洲，另有 `nether_wastes`、`soul_valley`、`crimson_forest`、`warped_forest`、`basalt_deltas` 单群系预设。三角洲成本较高，因此默认关闭。

## 离线生成

末地默认直接生成外岛。选择“主岛-虚空-外岛”时，主岛中心固定在世界(0,0)，可用原点(-128,-128)、尺寸256×256查看整座主岛；切换预设不会改动生成范围。用法与参数见[末地](docs/END.md)。

使用 UE 自带的 Python 3.11 与项目依赖（NumPy、OpenCV）：

```powershell
$projectRoot = 'E:/ue/Mineprep_5_8'
$python = 'D:/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe'
$env:PYTHONPATH = "$projectRoot/Plugins/Mineprep/Content/Python;$projectRoot/Intermediate/PipInstall/Lib/site-packages"
$env:OPENCV_IO_ENABLE_OPENEXR = '1'
& $python -B -c "from mods.WorldGenerator import api; print(api.catalog())"
```

```python
from mods.WorldGenerator import api

info = api.describe('vanilla')            # 参数、预设、群系；只取需要的键
spec = api.spec('vanilla', seed=42, region=(-256, -512, 128, 128),
                params={'caves.enabled': False})
world = api.generate(spec)                # execution='serial' | 'threads' | 'processes'
print(world.biome_fractions(), world.stats['build_wall_seconds'])
api.snapshot(world, 'E:/ue/Mineprep_5_8/Intermediate/first_world.png')
```

- 坐标规则：Python 生成数据一律是 MC 格坐标（Y 高）；UE 场景与面板一律用 UE 轴（Z 高，放置位置为厘米）。UE 的水平 X／Y 就是 MC 的 X／Z，没有符号变化，换算用 `api.to_ue()`／`from_ue()`。
- `region=(x0, z0, width, depth)` 是世界格坐标，面板“生成原点”的 X／Y 即这里的 x0／z0；二维数组为 `[Z, X]`，1 格 = 100 厘米。
- `api.overview(spec)` 只算参考地图（地形、群系、水），不含洞穴、树草与覆雪，不能用于准备资源。
- `api.check(world)` 汇总群系与景观；`api.locate(overview, biome='savanna')` 找本区最近的匹配参考列。
- `spec.with_params({...})` 返回新配置；`api.spec()` 会校验未知参数与范围。WorldSpec 可 `to_json()`／`from_json()`，只保存显式覆盖的值。
- 多进程脚本把生成调用放在 `if __name__ == '__main__':` 下。

## 在编辑器中使用

从 Mineprep 模组菜单打开“MC世界生成器”：调整参数，“生成预览 → 准备资源 → 放置到场景”。“自动概览”默认勾选，在参数停顿 300 毫秒后刷新参考地图（最大 512²）。新 Actor 归入“输出名称”文件夹；已有 Actor 不会随参数自动更新。

面板中的生成范围超出水系规划时，会自动平移规划窗口，必要时扩大到16格的倍数，并保存调整后的规划参数。同一规划内移动或裁切不会改变水系；规划窗口改变时，河湖会重新规划。脚本创建的 `WorldSpec` 仍使用明确的固定规划范围，拼接多个区域时应共用同一组 `hydrology.origin_x`、`hydrology.origin_z` 和 `hydrology.size`。

曲线编辑停顿300毫秒后自动应用；勾选“自动概览”时会接着刷新地图。关闭自动概览仍会应用曲线，点击“生成预览”“准备资源”或保存时也会立即提交尚未应用的修改。切线和插值按生成样条重建，不保存手动切线、其他插值模式或外部 CurveFloat；无效输入会提示原因并保留上次有效参数。

脚本中的准备与放置是 UE 主线程上的异步 Job，用完成回调继续：

```python
from mods.WorldGenerator import api

spec = api.spec('vanilla', seed=42, region=(-256, -512, 128, 128))

def on_prepared(job):
    if job.state == 'completed':
        api.place(job.result, name='FirstWorld', location=(0, 0, 0),
                  on_done=lambda placed: print(placed.state, placed.error))
    else:
        print(job.state, job.error)

job = api.prepare(spec, name='FirstWorld', backend='pcg', on_done=on_prepared)
```

输出参数、数量上限、模型分组与群系颜色纹理见 [输出说明](docs/OUTPUT.md)。

1024²／2048²场景的完整生成和渲染成本会明显增加。整树、长方体合并和减少不需要的景物可用于控制负担，但当前还没有统一的粗地形或静态LOD设置；参考概览的速度也不能代表完整场景速度。

## 方块作品与场景组合

```python
b = api.builder((16, 12, 16), origin=(-8, 0, -8))
b.box('oak_planks', (-6, 0, -6), (6, 8, 6), hollow=True)
room = b.freeze('room')
scene = api.compose(world, room.at((10, 80, 10), rotation=90))
print(api.check(scene)); api.snapshot(scene, 'E:/ue/Mineprep_5_8/Intermediate/scene.png')
```

完整用法见 [Agent指南](docs/AGENT_GUIDE.md)。

局部创作工具支持选区／paint、tube／extrude、接地／地基／散布，以及模型与图片转换；冻结后共用Structure和现有输出流程：

```python
# 模型先由UE导入；资产／纹理入口在编辑器主线程调用
model = api.mesh_structure('/Game/Models/SM_Model', resolution=128,
                           textures={0: '/Game/Models/T_BaseColor'})
# 本地图片仍可离线转换
art = api.image_structure('photo.jpg', size=128, colors=16, smooth=.6)
relief = api.image_structure('photo.jpg', depth=(2,12))
```

image_structure默认保持比例、最长边不超过128格；depth还可传二维图或接收RGBA的函数。网格默认表面壳层，图片浮雕为实心柱列。
仅使用引擎／已启用引擎插件提供的Python库，不需额外安装依赖。OBJ／GLTF／GLB／FBX先用UE导入器导入，mesh_structure读取网格资产／组件或纯数组；普通UE材质通过textures指定底色贴图，Mineprep皮肤可自动读取。
[山谷驿站](examples/README.md)提供河谷森林、石拱桥和木石屋舍的完整示例，可生成预览与UE放置脚本；旧树屋和Steve仍可使用。

## 自定义内容

- 高度图：`api.with_heightmap(spec, path)`，见 [高度图](docs/HEIGHTMAP.md)。
- 内容包：`api.create_pack('my_world')` 在 `Saved/packs/` 创建继承 vanilla 的包；新解释器中需 `api.register_pack_root(...)`。新群系、树形与地形字段见 [内容包入门](docs/CONTENT_PACK_GUIDE.md)，全部声明见 [EXTENSIONS](docs/EXTENSIONS.md)。
- 预设：面板“另存预设”保存到 `Saved/presets/`；API 用 `api.preset_library()`、`api.apply_preset()`，见 [预设库](docs/PRESET_LIBRARY.md)。

## 固定约定

- 方块模型以格中心为原点。水面模型是方块顶面换水材质、删去其余五面并略微下移，中心原点下局部平面 43.7 cm，**模型 offset 必须为零**；不要另加水位补偿。见 [CENTER_FRAME](docs/CENTER_FRAME.md)。
- 只输出静态水平水面，不填水体、不做流体；水下视觉由 UE 场景的后期处理体积负责。
- `water.generate=False` 停止所有水体规划与塑形；`water.enabled=False` 只隐藏水面，保留湿域语义。
- `Saved/` 保存用户包、草稿、预设、会话与偏好，不要整目录删除。

## 文档

[文档索引](docs/README.md) · [示例说明](examples/README.md)

分发包包含程序、内置内容包、示例源码和使用文档。用户自己的内容、预设和会话在首次使用后写入`Saved/`，不随分发包附带。
