# Agent：地形、方块作品与场景组合

```python
from mods.WorldGenerator import api
```

先读 `api.catalog()` 和所选包的 `api.describe('vanilla')`。生成地形用 WorldGenerator；已有 NBT／schematic 用公共 `mineprep.spawn_structure`。单次建筑无需创建内容包；反复随机散布的新景观再读[内容包指南](CONTENT_PACK_GUIDE.md)。

通过MCP查询时，在编辑器端筛选结果再返回，避免完整`describe()`被截断。例如只查询预设、群系ID和树木参数：

```python
info = api.describe('vanilla')
summary = dict(presets=info['presets'], biomes=[b['id'] for b in info['biomes']],
    params={k: v for k, v in info['params'].items() if k.startswith('trees.')})
summary  # 作为桥接代码的最后一个表达式；不返回整个info或World。
```

只发现能力不需要UE。默认在32～128格小区域离线检查，再按用户请求扩大或输出到引擎。热带草原使用主世界`vanilla`的`savanna`群系。

## 生成恶地

```python
spec = api.spec('vanilla', 'badlands', seed=42, region=(-64,-64,128,128))
world = api.generate(spec)
print(api.check(world, expect_biomes=('badlands',)))
api.snapshot(world, 'delivery/badlands.png')
```

`overview` 是参考地图；`generate` 才产生地形、植被与模型。`locate` 定位参考列，不搜索树或建筑。参数范围、预设与群系 ID 从 `describe` 获取，不把候选概率当面积百分比。

`volume_decoration` 表示显式三维选址／volume_floor路径可用，不表示旧地表景观自动兼容volume；用 `check` 查看实际启用结果及不支持项。

## 批量构建作品

```python
b = api.builder((16,12,16), origin=(-8,0,-8))
b.box('oak_planks', (-6,0,-6), (6,8,6), hollow=True)
b.box('air', (-1,1,-6), (1,4,-5))
b.set('oak_stairs', [(-1,0,-7),(0,0,-7)], facing='north', half='bottom', shape='straight')
room = b.freeze('room')
room.save('delivery/room.json')
api.snapshot(room, 'delivery/room.png')
```

全部坐标为 **MC XYZ、Y 高、单位格**，对应格的最小角（UE 的水平 X／Y 就是 MC 的 X／Z，换算用 `api.to_ue()`）；框上限不包含在内。默认最大16,777,216格，可显式设置 `max_cells`。创建和修改构建器不导入资产。

| 操作 | 用法 |
| --- | --- |
| 点／批量坐标／选区 | `set(block, xyz, **states)`；XYZ、整数 `[N,3]` 或同一Builder的Selection；包含空气，返回self |
| 长方体 | `box(block, lo=None, hi=None, hollow=False, **states)`；省略范围为整个网格；hollow 只绘制一格厚外壳，保留内部已有内容 |
| 椭球／球 | `ellipsoid(block, center, radii, **states)`；radii 为 XYZ 或单个半径 |
| 圆柱 | `cylinder(block, base, radius, height, direction='y', **states)`；base 是底面圆心 |
| 线段 | `line(block, start, end, **states)`；包含两端，单格宽，斜线允许对角连接 |
| 路径管体 | `tube(block, points, radii=1., **states)`；圆头折线段并集，统一或逐点半径，允许零半径收尖 |
| 截面挤出 | `extrude(block, profile, base, height, direction='y', end_scale=1., **states)`；凹／凸二维轮廓沿轴正向挤出，可线性缩放 |
| 替换／删除 | `replace(old, new, lo=None, hi=None, **states)`；匹配 old 的全部状态；new 使用指定状态；`air` 删除 |
| 复制 | `piece = b.copy(lo, hi)`；复制包含空气的区域，坐标重置到零 |
| 粘贴 | `b.paste(piece, at, mode='replace', rotation=0)`；0／90／180／270度，at 是旋转后目标框最小角；replace 包含空气，keep 仅填目标空气 |
| 镜像 | `b.mirror('x', lo=None, hi=None)`；X／Z轴穿过选区中心，含空气翻转并替换原选区，不复制副本 |
| 自动连接 | `b.connect(lo=None, hi=None, families=None)`；只更新选区，读取整个网格的邻居；families 为 fence／pane／wall／gate／stairs 的子集，省略表示全部 |
| 选区 | `b.select(lo=None, hi=None, blocks=None, surface=None)`；返回可交并差的 Selection，见下节 |
| 上色 | `b.paint(material, selection=None, mode='solid', scale=8., seed=42, salt='paint', blend=1., **states)`；只替换当前非空气格，见下节 |
| 保存／再编辑 | `api.Structure.load(path)`、`structure.edit()`、`freeze(name)` |

形状以格中心判定，椭球与圆柱裁到构建器边界；显式框、点、线与粘贴越界报错。楼梯、半砖、原木、栅栏沿用公共 blockstate；几何搭好后可显式调用 `connect()` 推导连接与楼梯转角，冻结与放置不自动重算。

连接与变换共用 `mc_blockstates`。完整块判定只读本地模型 JSON，不读贴图；资源目录沿用现有配置或 `WG_MC_ASSETS`。双层半砖与八层雪可作为完整支撑，树叶、门等连接限制沿用公共规则，其他部分碰撞形状不模拟。局部连接不更新选区另一侧；需要双方更新时扩大选区。

粘贴和镜像按唯一 palette 状态变换，支持公共 API 的 Java `facing`、轴、四向连接、门合页、楼梯左右角及站立旋转；省略的常见方向沿用公共 API 默认值。Bedrock 专有方向编码保留原值，不承诺旋转／镜像后方向正确。已有 `Structure.at(rotation=...)` 是整体网格旋转，不重复改写原生状态。

## 路径与截面造型

`tube(block, points, radii=1., **states)` 接受至少两个有限 MC XYZ 点，允许浮点坐标，相邻点须不同。
radii 为非负统一半径或逐点半径，至少一个半径为正；线段投影处线性插值半径，圆头线段取并集。
端点半径为0可收尖；首尾点相同可闭环。路径保持输入折线，需要平滑曲线时由配方提供更密的采样点。

`extrude(block, profile, base, height, *, direction='y', end_scale=1., **states)` 使用相对 base 的二维简单多边形。
至少三个点，自动闭合，支持凹形及两种绕序；不支持带孔或自相交轮廓。
沿X／Y／Z挤出时，截面UV分别对应YZ／XZ／XY；height为正，沿轴正向延伸，上限不包含，多边形边界包含在内。
截面绕 base 从底部的1线性缩放到非负 end_scale；1为直挤出，0为收尖，大于1为扩张。

```python
b = api.builder((32,32,32), origin=(-16,0,-16))
b.tube('oak_log', [(-10,3,0),(0,15,0),(10,24,3)], [3,2,0], axis='y')
b.extrude('sandstone', [(-4,-4),(4,-4),(4,4),(-4,4)],
          (8,0,-8), 18, end_scale=.25)
piece = b.freeze('paths_and_profiles')
```

两项均返回 self，按格中心采样并裁到 Builder 边界；细于格子分辨率的形状可能没有格中心落入。
材质与 states 按显式输入使用，不沿曲线自动旋转原木等方块，也不自动 connect。
可以随后用 select／paint 改材质。通用截面沿曲线扫掠、多轮廓放样和壳厚仍留待实际需求。

`examples/geometry_workflow.py --output <新目录>` 导出变半径管体、三角／凹截面挤出和渐变宽度对照展台，附冻结JSON、诊断图和用户放置片段。

## 可组合选区、写入与 paint

`b.select(lo=None, hi=None, *, blocks=None, surface=None)` 返回 `api.Selection`。
`blocks` 是方块名或名称序列，匹配该名称的全部状态；范围、方块名与表面条件取交集。
选区支持 `&` 交集、`|` 并集、`-` 差集和 `.count`，只能在同一个 Builder 内组合和使用。
省略全部条件时选中整个范围（包括空气）。选区是**位置快照**，不会随材质或占用变化重算；需要更新时再次 select。

`selection.shift(dx=0, dy=0, dz=0)` 按整数MC XYZ偏移返回新位置快照，不移动方块或重新判断表面。
越界部分裁掉，不回绕、不扩容；完全移出后为空，后续反向偏移也不会恢复已经裁掉的位置。
选区仍属于原Builder，可继续交并差或用于set／paint；空选区写入为空操作。

`b.set(block, selection, **states)` 在选中的位置写入指定方块与完整状态，可填空气、替换已有方块，显式air删除。
需要只填当前空气时，在写入前与 `b.select(blocks='air')` 求交集。例如：

```python
roof = b.select(roof_lo, roof_hi, surface='top')
snow = roof.shift(dy=1) & b.select(blocks='air')
b.set('snow', snow, layers=1)
```

屋顶范围由配方指定，Builder需预留上方空间；这里按格邻接处理，不模拟楼梯碰撞形状或自动计算附着法线。

`surface` 可为 `exposed/top/bottom/sides`，分别表示任意六面、+Y、−Y、水平四面有空气邻居的非空气格。
读取整个 Builder 的邻居，Builder 外视为空气；包含空腔表面，top 不是“每列最高格”。
玻璃、树叶及部分模型均按非空气占用处理，不查询贴图、透明度或碰撞形状。

```python
b = api.builder((32,24,16)).box('stone', (0,0,0), (32,24,4))
walls = b.select(blocks='stone', surface='sides')
protected = b.select((12,0,0), (20,12,16))
b.paint('stone_bricks', walls & protected)
b.paint([('stone',3), ('andesite',1)], walls-protected,
        mode='noise', scale=6, seed=42)
b.paint([(0,'black_concrete'), (12,'gray_concrete'), (24,'white_concrete')],
        b.select(surface='top'), mode='height')
result = b.freeze('painted')
```

`paint(material, selection=None, *, mode='solid', scale=8., seed=42, salt='paint', blend=1., **states)` 返回 self：

- `solid`：material 为方块名；默认模式。
- `noise`：material 为名称列表或 `(方块名, 正权重)` 列表；三维连续斑块，scale 为正的格单位，内部用两层 fBm。复用地表候选解析，权重为近似分布，不保证实际面积比例，不按选区重新归一化。
- `height`：material 为至少两个严格递增的 `(有限高度, 方块名)` 控制点；格中心 Y 在相邻控制点间线性改变两种方块的概率，固定种子逐格选择，两端之外使用端点材质。不会产生连续色材质或额外 UE 材质。

height 模式的 `blend` 控制混色带宽度：默认1保持完整过渡，0～1按比例缩窄且中心位于相邻控制点的中点。
0关闭随机混色，按最近控制点清晰分层，中点取较高控制点材质；此时seed不影响结果。
例如 `b.paint([(0,'blackstone'),(20,'calcite')], mode='height', blend=.35)`。
blend不是与原方块的改色强度；完全不改色时跳过paint。其他模式不使用blend。

省略 selection 表示整个 Builder；写入时始终跳过当前空气格。显式输出 air 表示删除，填充空气仍用 box／set／replace。
指定 states 构成完整目标状态，不保留源状态；例如 `paint('oak_log', selection, axis='z')`。
噪声与渐变锚定 Builder 的 MC 坐标、seed 和 salt，改变选区或分批大小不会改变相同坐标的结果。
冻结、粘贴、镜像及 `Structure.at()` 都复用已上色的格子，不重新采样；不会自动 connect。
Selection 仅用于当前编辑，不写入版本1冻结文件；保存的是最终方块和状态。

可运行 `examples/material_workflow.py --output <新目录>`，生成受保护门框、噪声石墙、高度渐变纪念柱及组合场景的冻结 JSON、前后诊断图和 `place_in_editor.py`。UE 视觉由用户验收。

## 与公共 Blocks 互通

```python
# 对象转换；from_blocks 本身不导入 Unreal。
structure = api.from_blocks(blocks, name='Imported')

# 以下两种入口需要 Mineprep／UE，调用时才导入。
structure = api.from_blocks(r'C:\models\house.nbt')
blocks = api.to_blocks(structure)
mesh = blocks.bake(destination_path='/Game/mc/MyImportedHouse')
```

文件输入接受 `.nbt`／`.schem`／`.schematic`／`.mcstructure`，复用 `Blocks.from_file`；默认保留活板门朝向，可显式传 `repair_trapdoors=True` 修正旧导出文件。保留原坐标和 native states，包括 Bedrock 的命名空间属性键；不重居中。

`from_blocks` 直接生成稀疏 `Structure`，内存随占用格数增长，不创建包围盒体积的网格。导入边界是占用格 AABB；空源是1×1×1的空结构。Blocks 不保存外围空气范围，因此往返保证占用格与状态一致，外围空气边界可能收缩。保存格式仍为版本1；若稀疏范围超过默认编辑预算，`Structure.load(max_cells=...)` 与 `edit(max_cells=...)` 分别显式设置，后者才会分配稠密网格。

可运行小示例：`examples/module_workflow.py --output <新目录>`。生成原模块、镜像模块、四向组合的冻结 JSON、诊断预览与 `place_in_editor.py`；放置片段通过 Blocks 往返后使用现有异步 prepare／place。已打开的编辑器先用 `mineprep.reload()` 加载本轮源码并检查重载日志，再运行片段。预览不代表 UE 渲染验收，输出目录必须不存在以保留既有产物。

雕像用真实彩色方块，例如 `cyan_concrete`、`blue_wool`、`white_terracotta`。`api.palette('concrete'|'wool'|'terracotta')` 返回16种方块及诊断预览色，不改变实际材质。

## 组合与检查

```python
scene = api.compose(world, room.at((10,80,10), rotation=90))
# 独立作品：api.compose(None, room.at((0,0,0)))
print(api.check(scene))
api.snapshot(scene, 'delivery/scene.png')
```

建筑绕局部零点旋转，支持0／90／180／270度；复制区域的零点是原复制框最小角。地形组合必须完整位于已生成 XZ 范围与输出高度内，越界需先扩展 World。

`compose` 保留原 World；`check` 查询真实岩体、逐格景观、模型、水面和其他作品，返回碰撞分类、有限坐标样本及接地格数。软草只在实际相交格过滤；硬冲突会阻止准备。接地格数不代表结构力学稳定。树屋示例自行构建树与房屋，不搜索或替换已有树。

Scene 是只读组合快照；保留 Python 配方、地形 Spec 和冻结结构以重建。它不改变 WorldSpec 格式2，不编辑已放置 PCG。自定义 JSON／UE 网格继续使用内容包。

`compose` 默认参考面积上限16,777,216列、总格／模型逻辑格上限4,000,000；可通过 `max_cells`／`max_instances` 显式调整。准备时再次执行预算与碰撞检查，包括缓存命中。

## 接地与地基

```python
p = api.ground(world, room.at((10,0,10), rotation=90))
footing = api.foundation(world, p, block='stone_bricks', max_depth=16)
parts = [p]
if footing.count:
    parts.append(footing.at((0,0,0)))  # 地基已使用世界 MC 坐标。
scene = api.compose(world, *parts)
print(api.check(scene))
```

`ground(world, placement)` 返回新 Placement，保留结构、X/Z 与旋转，只重算平移 Y，输入 Y 不作为搜索起点。
它按旋转后每个占用 XZ 列的最低方块求出位于地形最上方的最低合法高度；外围空气不参与。
普通地形取 `ceil(height)-1` 为最高实体格；受密度修改的列分批查询实际地形，包含洞口与高于参考高度的实体。
树木、装饰和水不作为地形支撑；函数不自动避让硬景观，组合后仍需 check。模型整体须位于已生成的 XZ 和输出 Y 范围。

`foundation(world, *placements, block='stone', max_depth=16, max_cells=4_000_000, **states)`
从各模型实际最低 Y 层的非空气格向下填充，直到首次遇到真实地形；不从高处门楣、屋檐自动长出墙体。
max_depth 是允许新增的最大竖直格数；0 只允许已接地。找不到地形、遇硬景观／水面／其他传入模型、越出高度范围时抛出带坐标的错误，不返回半截地基。
软草允许覆盖，沿用 compose 的相交过滤。目标 states 使用原生方块规则，不自动 connect。

返回一份合并去重的稀疏 Structure，可保存、加载和编辑；没有待填格时为1×1×1空结构，组合时跳过它。
主体结构保持不变并共享模板，地基单独烘焙。max_cells 限制本次新增格的工作量，compose／prepare 仍执行各自总预算。
两函数保持离线可用，只接受已生成的地表 World；volume 下界的多层地面需要另行指定楼层，当前不支持。
最低层是承托约定，不保证力学稳定；复杂错层支柱由 Builder 明确建模。

`examples/grounding_workflow.py --output <新目录>` 导出128²山坡、三向共享亭子、独立地基、前后诊断图和用户可运行的放置脚本。诊断图不证明 UE 的贴图与光照效果。

## 图片转像素画与浮雕

```python
art = api.image_structure(r'E:/art/logo.png')  # 最长边不超过128格，保持比例，厚度1
coarse = api.image_structure('logo.png', size=64)  # 更粗的像素画
clean = api.image_structure('photo.jpg', size=128, colors=16, smooth=.6)
relief = api.image_structure('/Game/Mineprep/材质/皮肤/tex/steve_bare_bones',
                             size=(128,128), depth=(2,14))
# 反转厚度范围使暗部凸起、亮部凹下；也可直接传入二维厚度图。
inverted = api.image_structure('logo.png', depth=(14,2))

import numpy as np
def waves(rgba):
    y,x = np.indices(rgba.shape[:2])
    return 5 + 3*np.sin(x/5)*np.cos(y/7)
custom = api.image_structure('logo.png', depth=waves)
```

`image_structure(source, *, size=128, depth=1, axis='z', palette=None,
resample='box', colors=None, smooth=0., alpha_cutoff=.5, name='Image', max_cells=4_000_000)` 返回普通Structure，可保存、编辑、组合与放置。

- source接受本地图片、uint8 RGB／RGBA数组，以及UE Texture2D对象或`/Game/...`资产路径。
  UE入口在主线程读取实际TextureSource，不依赖原始导入文件；无Source的临时纹理会报错。
  图像按8位sRGB底色处理；HDR／高精度高度数据继续使用独立的heightmap流程。
- size默认为128：整数表示最长边上限，保持宽高比，不放大小图；`size=64`提供更粗的像素风格。
  `(宽,高)`仍表示指定精确尺寸，可改变比例或放大；`None`显式使用原图尺寸，仍受max_cells限制。
  默认`resample='box'`按区域平均缩图，适合照片；`'nearest'`保留素材硬边。文件在转为NumPy前完成缩放，
  避免先展开全分辨率的选区／厚度中间数组；文件解码本身仍需读取源图。mesh／UV贴图仍按原尺寸最近邻读取。
  alpha规则与mesh_structure一致：低于阈值或完全透明留空，不自动生成玻璃。
- colors为实际使用的方块颜色数量上限，默认None保留完整候选池；例如8为较强简化，16～24通常保留更多层次。
  直接从palette的真实方块颜色里选取能降低Lab误差的子集，再匹配像素；不先生成虚拟颜色再二次匹配。
  调色板拟合最多取16384个均匀位置样本；候选较多时减少样本，使预计算距离表最多1048576项。
  候选按64种一组计算距离，操作内复用；确定性取样，无随机种子或全局随机状态。
  上限不要求恰好用满；透明像素和厚度0像素不参与选择。输出palette保留原候选顺序，只限制实际使用的types。
- smooth为0～1的色块整理强度，默认0保留原结果；它在真实方块标签上结合颜色误差和四邻域一致性，
  合并相近颜色的零碎杂点，原图强边缘会降低合并倾向。固定两轮交替格网更新，不在RGB图上做模糊或添加抖动。
  更强的整理会牺牲部分装饰细节；原有像素画可保留0。colors=None、smooth=0保持上一版生成指纹。
  这些选项只改方块材质，不改变透明孔洞、占用格或浮雕厚度；depth函数仍收到原始缩放RGBA。
  复杂封面／人物可显式size=256；脸部本来只有几像素时，仅调整颜色无法还原细节。
  若更在意材质表面统一，可配合现有`palette=api.palette('concrete')`，但它会减少可用色域。
- depth为固定厚度、**二元素tuple**`(黑色厚度,白色厚度)`、`[高,宽]`数组或函数。
  tuple按sRGB亮度`.2126R+.7152G+.0722B`线性映射，不按图片实际明暗范围归一化；端点可以反转。
  函数只调用一次，接收缩放后的uint8 RGBA副本，返回标量或同尺寸二维厚度数组；不逐像素调用Python。
  厚度须有限且非负，小数按`floor(d+.5)`取整；0表示此像素不生成。
- 所有像素从同一背面沿指定轴的正方向生成**实心柱列**，柱侧沿用该像素方块；不只生成浮雕表壳。
  最小角固定为原点，完整图片宽高包含透明边缘，深度取有效像素最大厚度（全空时为1）。
  `axis='z'`：图像向右为+X、向上为+Y，沿+Z挤出；`'x'`：向右+Z、向上+Y，沿+X挤出；
  `'y'`：向右+X、向上+Z，沿+Y挤出，可作地面图案。浮雕起伏面在挤出轴的正侧。
- 共用真实方块贴图代表色的Lab匹配与48种默认候选；palette和mesh_structure相同。
  先按唯一颜色匹配，再批量复制柱列，不建立完整三维网格；max_cells限制实际占用格。
  默认最多128²个图像像素，但自定义厚度仍可能超过占用格预算；保存后不会在放置时重新采样图片或函数。

`examples/image_workflow.py --output <新目录> [--source <本地图片>] [--size 128] [--colors 16] [--smooth .6]`
（也支持`--resample nearest`）导出单层像素画、
亮度浮雕、自定义波纹浮雕、源图、冻结结构、四向诊断图和用户放置脚本。离线诊断图不代表UE贴图／光照。

调研依据：[Pixelated Image Abstraction](https://gfx.cs.princeton.edu/gfx/pubs/Gerstner_2012_PIA/Gerstner_2012_PIA_full.pdf)
强调像素结构和调色板的共同作用；[OpenCV双边滤波说明](https://docs.opencv.org/4.x/d4/d86/group__imgproc__filter.html)
介绍以颜色差异降低跨边缘混合的权重。这里采用轻量的真实方块选色和标签邻域代价，未引入论文的超像素框架。

## 带贴图模型转方块

```python
bee = api.mesh_structure('/Game/mc/mob/bee/SKM_bee', resolution=128, name='Bee')
# 外部模型先在内容浏览器导入，再指定网格和底色贴图。
model = api.mesh_structure('/Game/Models/SM_Model', resolution=128,
                           textures={0: '/Game/Models/T_BaseColor'},
                           palette=['white_concrete', 'black_concrete'])
```

`mesh_structure(source, *, resolution=128, palette=None, textures=None, up_axis=None,
alpha_cutoff=.5, name='Model', max_cells=4_000_000)` 返回普通稀疏Structure。
source接受UE StaticMesh／SkeletalMesh资产（含`/Game/...`、`/Engine/...`、`/Mineprep/...`路径）、
StaticMeshComponent／SkinnedMeshComponent，或下面的纯数组输入。OBJ／GLTF／GLB／FBX先用UE现有导入器导入，
不再直接读取模型文件，也不自动导入或创建临时UE资产。多网格场景按部件转换／组合，或先在UE中合并。

- 最长几何边等比缩放到resolution格，整体最小角移到原点。数组默认MC XYZ、Y向上；Z向上的数组设置`up_axis='z'`。UE自动使用现有`from_ue`坐标规则，组件含世界变换，不接受up_axis覆盖。
- SkeletalMesh资产为参考姿态；组件由Geometry Script读取当前CPU蒙皮姿态。先让编辑器完成目标帧求值，再调用；不改变动画、姿态或关卡。GPU材质位移不在范围内。
- 输出为相交表面壳层，不填内部、不补洞；透明贴图先按阈值裁出有效表面，覆盖格子边缘的细线也参与转换，不仅检查格中心。按有效表面的最近点UV取色，边界限制在所属UV区域内，避免读到邻近图集像素；多个面争同一格时选最近的不透明样本，等距按源三角形顺序。一个方块只有一种材质，不能逐面精确保留棱角色；低分辨率也会吞掉细节。
- 图片数组为uint8 RGB／RGBA；默认最近邻。底色贴图按sRGB处理，材质因子和顶点色按线性值相乘。alpha阈值默认.5；即使阈值为0，完全透明仍留空。半透明像素只按阈值取舍，不自动选择玻璃。
- 默认从48种混凝土／羊毛／陶瓦按实际贴图代表色做Lab匹配；palette接受名称序列或`api.palette()`的字典（使用键，重新读取真实颜色）。缺少候选模型／贴图会报错，不使用诊断回退色。
- `textures={0: 'skin.png'}` 可覆盖材质槽底色，值接受本地图片、RGB／RGBA数组或UE Texture2D／资产路径。UE自动读取Mineprep皮肤材质的“纹理贴图”TextureSource；其他材质按网格原有槽位显式提供覆盖，不猜测复杂着色图。无UV的数组模型可以使用纯色，不能指定贴图。
- max_cells限制最终占用格，而非包围盒体积；不分配整个三维体积。现有`Structure.load(..., max_cells=...)`仍检查包围盒体积，大分辨率稀疏模型加载时按实际需求显式提高该预算；`edit()`仍受稠密Builder预算约束。

纯数组输入为字典：`vertices[N,3]`（MC XYZ）、`triangles[T,3]`（整数下标），可选
`uv[T,3,2]`（逐角UV，V向下）、`material_ids[T]`、`colors[T,3,4]`（线性RGBA）。
`materials`是列表，每项支持`image`（路径或数组）、`factor`（默认线性白色RGBA）和
`wrap=('repeat','repeat')`（每轴可为repeat／clamp／mirror）。无材质时默认为白色。
这些是瞬时交换数据，不增加Structure保存格式，也不把UObject送入worker。

```python
boxes = [dict(origin=(-4,0,-2), size=(8,12,4),
              faces={'north': (20,20,28,32)}, transform=matrix4x4)]
piece = api.uv_structure('skin.png', boxes, texture_size=(64,64), scale=4)
```

`uv_structure(source, boxes, *, scale=1, texture_size=None, palette=None, alpha_cutoff=.5,
name='UVModel', max_cells=4_000_000)` 复用同一网格体素化核心。每盒包含origin、size、faces；
source使用与image_structure相同的图像读取路径，包含UE Texture2D／资产路径。
可选inflate（向外扩张的模型单位）、transform（模型坐标到整体坐标的仿射4×4矩阵）。
原点按模型坐标保留；边界为缩放后几何AABB，不按透明像素裁剪。六面命名为east／west／up／down／north／south，
对应+X／−X／+Y／−Y／−Z／+Z。faces中缺少的面不生成；UV矩形为左上图像坐标`(u1,v1,u2,v2)`，
可反向端点实现翻转，或使用`{'uv': rect, 'rotation': 90, 'mirror': True}`。
rotation顺时针旋转贴图，再做水平镜像；0／90／180／270。texture_size是UV参考图集大小，默认实际图片大小；
高分辨率同布局图片使用相同参考尺寸即可。薄盒允许一个尺寸为0。外层透明区域跳过，不擦除内层。

皮肤内外层／宽细臂由配方控制，参考Skin Editor规则；关节姿态先变换几何再体素化，核心不提供角色专用函数。
`examples/mesh_workflow.py` 提供实际蜜蜂输入捕获、坐姿Steve＋矿车、源色／方块色对照和用户放置脚本。
UE中先用`runpy.run_path(...)['capture_in_editor'](<新输入目录>)`捕获，再离线运行
`mesh_workflow.py --inputs <输入目录> --output <新输出目录>`。捕获只读取实际资产和模板并写派生文件，不放置Actor。
仅使用Python标准库和引擎／已启用引擎插件自带的库，不安装或打包额外第三方依赖。
数组、UV盒组和本地图片仍支持离线转换；UE资产／组件／纹理只在编辑器主线程读取，之后数值核心只处理数组。
所有PNG仍是现有平均色诊断图；UE贴图、光照和动态骨骼姿态的视觉由用户验收。
大场景先转换局部模型，再通过现有compose／scatter复用模板，避免将整片森林重新体素化成巨型模型。

## 通用模板散布

```python
world = api.generate(spec, keep_fields=('slope',))
result = api.scatter(world, [(room,3), (tower,1)], spacing=24, density=.7,
                     where={'slope':{'max':.5}}, max_depth=8)
print(result.stats)
if result.placements:
    footing = api.foundation(world, *result.placements, block='stone_bricks', max_depth=8)
    parts = list(result.placements)
    if footing.count:
        parts.append(footing.at((0,0,0)))
    scene = api.compose(world, *parts)
    print(api.check(scene))
```

`scatter(world, structures, *, region=None, spacing=16, density=1., biomes=None, where=None,
avoid_water=True, rotations=(0,90,180,270), max_depth=0, existing=(), seed=None, salt='scatter',
max_candidates=65_536, max_cells=4_000_000)` 返回 `ScatterResult(placements, stats)`，不改变World。
structures接受单个Structure、等权列表或`[(Structure,正权重), ...]`；实例共享原结构与原生状态，仅整体旋转和平移。

- region为MC `(x0,z0,width,depth)` 或Region，默认整个World。它限制锚点，实际模型及地基须完整位于World和输出高度内。旋转继续围绕结构局部零点，外围空气不扩大模型占地。
- spacing为正整数，保证本次新增实例锚点的最小XZ欧氏距离。世界对齐候选格、坐标哈希与局部竞争保证同输入重复／分批结果一致；在同一World和相同existing下对子区域调用，与整区对应锚点结果一致。局部竞争不保证最大填充率。
- density为`[0,1]`标量或与World.region对齐的`[Z,X]`概率数组，只读使用。它控制候选概率，最终数量及模板比例还受条件和碰撞影响。seed默认世界种子，salt区分独立布局；模板与rotations列表顺序也是输入的一部分。
- biomes按锚点筛选，接受群系ID或列表；where沿用`locate`的`{字段:{min,max}}`语义，含min、不含max。height直接取参考高度，slope与其他数值字段须用generate的keep_fields保留，缺少时提示，不重生成地形。where也是锚点参考筛选，不代表整栋的实际坡度。
- avoid_water默认按模型实际投影列排除物理湿区，隐藏水面不取消此筛选。设False只关闭湿区筛选，仍保留已有水面碰撞规则。
- max_depth=0要求实际最低层直接获得地形承托；设正值允许后续补地基，并预检支撑路径。散布不生成地基材质；之后显式调用foundation，深度至少与散布一致。
- existing只作为额外实际占据障碍，不自动加入返回结果，也不参与新增锚点的间距规则。已有作品的地基若需保护，也须一并传入。世界硬景观、水面和模型始终参与碰撞，软草仍由compose过滤。
- 包围盒仅作快速排除，精查允许空包围区域重叠。新候选之间同时排除主体与潜在地基的相交，避免后续地基穿模。
- max_candidates限制含竞争邻域的候选网格数量；max_cells限制廉价筛选后候选主体及潜在地基的逻辑格工作量，包含竞争淘汰者和邻域候选，不是最终输出格数。预算不足时明确报错，不静默截断。compose／prepare仍各自检查场景总预算。

stats包含本region候选数、accepted、按首个失败阶段计数的rejected、模板key计数、含邻域的queried_candidates及checked_cells；无可用位置返回空placements和原因统计。
一次调用共享查询、索引、密度修改范围及各模板方向轮廓，不逐候选调用完整compose／check。只接受已生成的地表World，保持离线可用；原版景观生成和三种输出后端不变。

`examples/scatter_workflow.py --output <新目录>` 导出128²山坡、加权模板、密度分区与保护走廊、已有门廊、统一地基及放置记录。诊断预览不证明UE贴图和光照效果。

## 准备与放置（仅用户要求引擎操作时执行）

在UE主线程执行，先核对项目、当前关卡和独立输出名称。以下是完整异步链；组合建筑时将`target`换成已检查的`scene`。默认不保存关卡或改原有Actor。

```python
from mods.WorldGenerator import api

target = api.spec('vanilla', seed=42, region=(-64, -64, 128, 128))

def placed(job):
    if job.state != 'completed':
        print(dict(state=job.state, error=job.error, warnings=job.warnings))
        return
    result = job.result
    print(dict(state=job.state, actors=len(result['actor_paths']),
        instances=result['instance_count'], expected=result['expected_instances'],
        render_state=result['render_state'], warnings=result['warnings']))

def ready(job):
    if job.state != 'completed':
        print(dict(state=job.state, error=job.error, warnings=job.warnings))
        return
    prepared = job.result
    print(dict(visible=prepared.visible_count, instances=prepared.instance_count,
        reused=prepared.reused, base_reused=prepared.base_reused, warnings=job.warnings))
    global place_job
    place_job = api.place(prepared, name='MyScene', location=(0, 0, 0), on_done=placed)

job = api.prepare(target, backend='pcg', merge='cuboids', name='MyScene',
    execution='serial', max_preprocess_cells=2147483647, max_output_instances=2000000,
    on_done=ready)
```

`prepare`接受WorldSpec、Scene或单个Structure；不直接接受离线World。离线`generate()`不会自动加入编辑器Job缓存，随后prepare可能再次生成；编辑器`api.preview(spec)`的完整World可供prepare复用，overview不能代替。相同作品共享整模型，材质动画、发光和单双面沿用公共处理。

### 输出参数速查

下表列出当前`api.prepare()`支持的选项；转发参数以[ops.prepare_world](../ops.py)为准，不能猜测不存在的`output_directory`等参数。

| 参数 | 默认／用途 |
| --- | --- |
| `name` | `'World'`，资源目录的可读名称；不改变资源内容身份，不是任意文件系统路径 |
| `backend` / `merge` | `'pcg'` / `'cuboids'`；后端`ism/pcg/niagara`，合并`none/runs/rectangles/cuboids` |
| `execution` / `workers` | `'serial'` / `4`；也可`threads/processes`，先用串行小区域排查 |
| `chunk_count` / `type_group_count` | 均为`1`；前者仅ISM空间区块，后者仅GPU模型分组；不是每种方块的Actor数量 |
| `biome_texture` / `biome_cell_size` | `True` / `4`，每像素覆盖1～16格；ISM分区数大于1时关闭BCT；独立作品没有地形时也关闭 |
| `biome_color_mode` / `biome_color_power` | `'rgb'` / `1.`；模式`rgb/hsv`，对正数色板先按群系色彩指数乘方，HSV再取负编码。协议见[OUTPUT](OUTPUT.md) |
| `vegetation_tints` / `vegetation_hsv` | `None`，按群系ID覆盖对应三分量；缺项跟随快照，不改变几何 |
| `block_materials` | `None`，按方块ID覆盖`emission/lighting`，显式0有效，字段为None时取消该覆盖；见[R39](OUTPUT.md) |
| `max_cells` / `max_instances` | `16777216` / `4000000`，二维列数／原始输出上限。后者不是合并后的数量 |
| `max_preprocess_cells` | `None`，可选宽×深×输出高度上限，任务入口检查；面板默认2147483647 |
| `max_output_instances` | `None`，可选最终合并实例总上限，写纹理前检查；面板默认2000000 |
| `refresh_resources` | `False`，按需显式刷新资源；纯调色无需批量刷新模型 |
| `on_progress` / `on_done` | `None`，分别接收阶段字符串／终态Job；回调在主线程执行 |

四项预算彼此独立；提高最终实例上限不会解除旧的原始输出上限。确需更大原始输出时另设`max_instances`，面板使用预处理上限承担这项保护。预算、颜色模式和分组数不写入WorldSpec；输出偏好与数值生成配置分开保存。

`api.place(prepared, location=(0,0,0), chunk_count=None, name='World', on_progress=None, on_done=None)`同样返回Job。位置为 **UE XYZ、Z高、厘米**；chunk_count缺省沿用准备值，不能临时改为另一分区数。重复调用会新增输出，不先查询状态就重试可能重复放置。

### 完成状态与图片

Job状态为`running/completed/failed/cancelled`。在后续MCP请求中可返回`dict(state=job.state, stage=job.stage, error=job.error, warnings=job.warnings)`；不要忙等、sleep阻塞主线程，或把含完整result的`job.status()`直接倾倒给MCP。取消用`job.cancel()`，等待终态再决定下一步。

ISM放置结果的`instance_count`是已配置实例数；PCG／Niagara返回`instance_count=None`、`render_state='pending'`，`expected_instances`只是预计数量。Job完成不等于GPU已经生成、材质编译完成或画面已验收，需检查实际场景后再声称成功。

离线 snapshot 默认输出正面、右侧、俯视和等轴测；显示格占据与材料平均色，不渲染楼梯细面、透明纹理或 UE 光照。

需要编辑器截图时优先使用现有MCP `EditorToolset.EditorAppToolset.CaptureViewport`，先发现实时schema并检查实际图片；高分辨率或Python会话用公共`screenshot()`。入口及可选参数见[Mineprep remote](../../../mineprep-skills/remote.md#viewport-screenshot-agent-can-read-the-png)。不新增WG截图封装；PNG需检查Alpha，改成jpg后缀不会转换编码。

## 示例入口

各脚本默认离线运行，向新目录输出冻结结构、诊断图及检查数据；支持放置的脚本另附用户可运行片段。
[山谷驿站](../examples/README.md)提供河谷森林、桥和木石屋舍的完整示例，支持128²／256²，附PCG放置脚本。旧示例仍可使用。

| 要验证的能力 | 脚本 |
| --- | --- |
| 河谷森林、驿站、石拱桥与完整场景交付 | [valley_outpost.py](../examples/valley_outpost.py) |
| 图片控制植物疏密、整株避让空地 | [mask_workflow.py](../examples/mask_workflow.py)，[遮罩说明](MASKS.md) |
| 连接、复制、旋转、镜像与模块组合 | [module_workflow.py](../examples/module_workflow.py) |
| 选区保护、噪声材质、高度渐变 | [material_workflow.py](../examples/material_workflow.py) |
| tube、extrude、blend宽度对照 | [geometry_workflow.py](../examples/geometry_workflow.py) |
| 山坡接地与独立地基 | [grounding_workflow.py](../examples/grounding_workflow.py) |
| 模板混合、条件散布与避让 | [scatter_workflow.py](../examples/scatter_workflow.py) |
| 真实蜜蜂输入、坐姿Steve＋矿车 | [mesh_workflow.py](../examples/mesh_workflow.py)，先按上文捕获实际输入，再离线转换 |
| 图片、浮雕、可调限色与色块整理 | [image_workflow.py](../examples/image_workflow.py) |

### 保留的旧示例

[agent_workflows.py](../examples/agent_workflows.py) 提供恶地、含入口／楼梯的树屋及128格高站姿史蒂夫，只使用公共接口，默认不操作UE。它保留为历史手工配方；当前示例参考上表。旧脚本仍可这样运行：

```powershell
& 'D:/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe' -B -X utf8 examples/agent_workflows.py --output E:/ue/Mineprep_5_8/Intermediate/WorldGenerator0610/examples
```

在模组目录执行，或使用脚本绝对路径；Python 需 NumPy、OpenCV。输出包含结构 JSON、地形 Spec、检查摘要和预览；实际材质与场景由用户验收。
