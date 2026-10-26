# 多方块景观、植物与自然装饰（格式 2）

0.60.1下界默认均衡四群系，“所有群系”加入三角洲，另有五种纯群系快捷项。三角洲小／大柱簇约2∶1，目标柱长2—7／7—15格，默认候选强度0.85、间距11；熔池强度0.70、间距20，采用岩石间的零散岩浆面，仅部分池岸点缀岩浆块。柱簇依赖真实洞底／浅海底并在洞顶停止；熔池保持底部和侧壁封闭，独立于岩浆海开关。`basalt.*`可调开关、候选强度、间距和区域；`nether.basalt_enabled`仍只控制原有岩石斑块。没有新方块ID、逐柱Actor或流体传播，见[R47](../README.md#内置内容)。

0.59.1修复整株共享材质动画：母材质按源PNG尺寸选择，应用已有`.mcmeta`播放设置。诡异菌索／下界苗默认概率降至0.15／0.05，小菌保持0.03；下界矿石总量默认0.22，旧保存值保持。重新生成、准备、放置后应用新配置，旧资产不被批量修改。用法与性能记录见R45（见 Git 历史）。

0.59.0新增诡异森林：六款独立整株、丰富逐方块菌树、菌光体、小诡异菌、菌索、下界苗及地面向上的缠怨藤，见诡异森林（见 Git 历史）。整株开关在“下界形状”页统一控制两种森林；下界整株单面、主世界双面规则见材质单双面（见 Git 历史）。绯红林地植物参数见R42（见 Git 历史）。

绯红森林提供六款共享整株菌树及更丰富的逐方块模式，菌岩依据真实洞底。0.58.1按UE反馈改为缺口／裙边菌盖并自带垂泪藤，加密候选，允许有限菌盖交叠且避让菌柄。三维景观支持TemplateBatch，模型参与占据、竞争、剥顶和切面；高度裁切保留整株规则。当前用法、形态及验证见菌树改进（见 Git 历史），首版记录见R40（见 Git 历史）。

群系绑定、表面处理和最小包的完整示例见 [扩展接口](EXTENSIONS.md)。本页保留原版景观的形状、支撑、碰撞和性能约定。

0.54.0的nether萤石使用volume专用ceiling支撑，锚点上方实体、向下生成小簇，沿用普通FeatureBatch与既有缓存／输出。石英、金矿及岩浆块通过壳层材料替换，不进入景观实例规划，也不生成深埋矿体；见矿物与洞顶萤石（见 Git 历史）。

0.53.0为multi_block增加显式三维选址回调；nether化石复用FeatureBatch、旋转、局部竞争及三后端输出。共享物理查询同时用于洞顶岩柱，旧地表景观仍使用原路径。接口和首版边界见[三维选址](EXTENSIONS.md#体积景观选址0530)，三类骨架与性能见R32（见 Git 历史）。

默认开启`vegetation.simplified`：四种树采用整树模板，按根归属输出；橡树、白桦、云杉含高矮及覆雪最多四种，暖区金合欢仅两种高度、无覆雪。普通草地和水下生成单格矮草、矮海草；沙漠保留单格枯木、仙人掌和高枯草丛。不生成两格高草、高海草、花、蕨类或海带。关闭后恢复完整植被，包括下述逐方块树木和两格植物。整树记录在`World.model_instances`，不进入`feature_cells`；资源准备在普通方块合并后追加完整模型。树冠可伸出输出边界，稀疏列占据保留空隙。资源与验收见整树模板（见 Git 历史）。

整树及下界巨型菌模板启用 `TemplateDefinition.scale_jitter=True`（其他模板默认False）：最终渲染实例按绝对锚点坐标稳定生成0.999～1的统一缩放，减少相交树冠的共面闪烁；树根底面保持原高度。ISM／PCG／Niagara共用该变换，分块和输出顺序不影响比例。逻辑格、占据、包围盒及诊断预览仍按原尺寸，建筑结构、逐方块输出和共享烘焙网格保持原样。微缩降低共面风险，不保证消除所有深度冲突；既有Actor需重新准备并放置后才会使用新变换。

0.40.1单格简化草复用实体分块的二维参考和`plant_ids`，不进入多方块候选、景观窗口缓存或包围盒竞争。`surface_scatter`声明`habitat`、`soft`和`allow_overlap_categories`；软草可与树类别重叠，岩石、倒木和冰体仍排除草。洞穴复用支撑／上方占据切片检查；soft_mask不参与积雪支撑、天空遮挡或实体阻挡，列景观删除草时同步预览和计数。详见[单格接口](EXTENSIONS.md#单格软散布0401)及实现记录（见 Git 历史）。3×3草、CoverBatch及软模板角色已经删除。

0.35.0 的冻洋冰体使用通用 `column_field`，独立窗口按列计算并合并连续来源与稀疏形状，再局部裁切与一次实心展开；不参与树木等多方块包围盒竞争。旧 `FeatureBatch` 的完整支撑与整座拒绝契约保留。两条入口共用冰山形状函数，没有两套形状实现。列占据和顶面查询保留摘要，不扫描内部每个方块；仍使用现有实体合并。实现与真实区域对照见 连续冻洋冰体（见 Git 历史）。

vanilla包含三类森林及草原／山地树木，完整模式可生成稀疏两格高花草；自然装饰（小岩石和倒木）默认关闭，可独立开启，保存值不改写。树木、草／灌木、自然装饰、水生植物开关独立；关闭树木仍可生成简化草。海草默认密度0.08，简化模式为每列概率；完整模式仍用原候选算法。原版无关规划可按[缓存依赖](CACHE.md)复用。`enabled_when`与绑定启用条件共同生效，禁用景观在候选、噪声和生成器前跳过；无有效硬景观时跳过多方块路径。0.46.0普通草原只绑定稀疏橡树，`trees.plains_density`默认0.01；不绑定白桦或云杉。`trees.density`控制山地橡树，正式森林及金合欢独立；保留旧白桦／云杉参数供原有绑定及用户包使用。volume地形暂不生成这些景观，在`feature_unsupported`中报告启用的特征ID。

0.46.2将混合林、针叶林与覆雪针叶林的forest_region下限进一步放宽至-0.5，四类森林humidity下限为-0.2；温度、优先级及各森林树密度保持。白桦林仍由forest_region≥0.25选择。金合欢默认密度保持0.28，已有显式保存值不改写。

## 沙漠植物

沙漠在混合世界和单群系预设中使用相同配方，仅放在干燥、坡度合适的沙面。简化模式生成单格枯木、仙人掌和高枯草丛；完整模式增加矮枯草丛，仙人掌按稳定随机键生成1～3格。高、矮枯草都是原生单格模型。仙人掌两种模式共用候选位置，沿用多方块景观的支撑与碰撞检查；枯草和枯木沿用单格散布。

| 参数 | 默认值与含义 |
| --- | --- |
| `vegetation.bush_density` | 0.01，枯木的逐列概率 |
| `vegetation.cactus_density` | 0.05，每6格候选位置的保留概率 |
| `vegetation.dry_grass_density` | 0.004，每种枯草的逐列概率；简化模式仅有高枯草 |

全部服从`vegetation.enabled`、`vegetation.patch_scale`和`vegetation.max_slope`，也受植被分布与留空遮罩约束。仙人掌不作为完整实体方块合并或遮挡相邻面。恶地沿用原有枯木配方。

## 手动调整森林面积与树密度

森林面积看`packs/vanilla/biomes/forest.json`、`birch_forest.json`、`taiga.json`、`snowy_taiga.json`的climate。forest_region下限越低，宏观森林区域越大；humidity下限越低，允许略干的区域长森林。混合林当前为`forest_region: [-0.5,0.25]`、`humidity: [-0.2,null]`；白桦林保持区域下限0.25，针叶林与覆雪针叶林区域上限为null。保留温度、水域和前置特殊群系条件；效果需在实际种子／区域检查，不能把阈值当面积百分比。

林内树密度的默认值在`packs/vanilla/pack.json`的params，各群系features绑定使用`$参数名`引用。可优先在“植被→森林／树木”面板调整；直接修改default只影响没有显式值的新请求，保存值需主动调整。

| 参数 | 当前默认 | 作用 |
| --- | ---: | --- |
| forest.mixed_oak_density | 0.60 | 混合林橡树候选概率 |
| forest.mixed_birch_density | 0.20 | 混合林白桦候选概率 |
| forest.birch_density | 0.75 | 白桦林白桦候选概率 |
| forest.spruce_density | 0.70 | 针叶林／覆雪针叶林云杉候选概率 |
| trees.plains_density | 0.01 | 普通草原稀疏橡树 |
| trees.acacia_density | 0.28 | 热带草原金合欢 |
| trees.density | 0.30 | 山地橡树 |

forest.region_scale默认512格，改变森林块的尺度，不等于提高覆盖率；trees.patch_scale控制林内斑块，trees.max_slope控制可植树坡度。最终树数还受真实支撑、占据和树冠竞争限制，候选概率与株数不成简单比例。`terrain.py`负责区域噪声，调面积或疏密通常无需改它；调整后重新获取当前包快照生成／准备，已有场景不会自动更新。用户包有自己的声明，旧草稿不会自动同步vanilla文件。

## Python使用

```python
from mods.WorldGenerator import api
spec = api.spec(seed=42, region=(0, 0, 256, 256), params={
    'vegetation.simplified': False,  # 此示例查看完整模式的逐方块景观。
    'trees.enabled': True, 'trees.plains_density': 0.01,
    'trees.density': 0.30, 'trees.height': 5,
    'trees.birch_density': 0.08, 'trees.spruce_density': 0.06,
    'vegetation.tall_grass_density': 0.01, 'vegetation.tall_flower_density': 0.003,
})
world = api.generate(spec)  # 无需UE、面板或Actor
print(world.stats['feature_instances'], world.stats['feature_cells'])
print(world.stats['stages']['features'])
for tree in world.feature_instances[:3]:
    print(tree.id, tree.anchor, tree.bounds, tree.block_count)
cells = world.feature_cells
# cells.xyz相对于world.region的水平原点，MC Y保持绝对高度。
# cells.types索引cells.names；它们与world.arrays使用相同的压缩ID。
```

`feature_instances`是不可变元组。ID为`(feature_id, seed, cell_x, cell_z)`，锚点和半开包围盒为绝对MC XYZ。旧FeatureBatch的`block_count`为请求范围内实际输出数，根在范围外、树冠伸入范围的树也计入；TemplateBatch只按根归属，`block_count`为整模板逻辑单元数。跨tile只计一次。`feature_candidates`计数概率筛选后锚点在请求水平范围内的候选，还没有排除不适宜地面或冲突。

`feature_cells`是未合并方块的只读`WorldArrays`视图，共享完整输出的坐标与类型内存，`solid_count=0`；它不包含整树模板或二维单格散布。树木与两格植物不改变参考高度、地形实体数或洞穴密度。旧普通草按原占据规则移除；简化软草按声明类别允许树草重叠，硬障碍仍排除。景观图／植被图／场景剖面叠加全部特征；地表图和洞穴诊断仍只表示地形。

`feature_added_instances`为特征方块数＋模板实例数−`feature_removed_plants`，表示净增未合并实例；`tree_trunk_cells`、`tree_leaf_cells`及`feature_counts[id].blocks`包含模板逻辑单元。`feature_block_counts`继续描述普通特征方块，模板另有`model_logical_cells`。两格植物不计入树木统计。旧树干允许合并；模板不拉伸合并，最终实例数量以prepare结果为准，不能用逻辑树格数代替。

原版“植被”页按包内元数据包含树木、草与灌木、自然装饰及水生植物分组，开关独立；旧页面偏好由一次性迁移转换，参数 ID 和有效值保持不变。参数的 enabled_param 声明控制调节项的显示。共享树木高级参数为斑块尺度8..512（默认48）、最大坡度0..4（默认0.8）。三种树沿用原有形状，正式森林和覆雪针叶林分别在群系绑定中控制分布；冷区技术包已转为测试夹具。

| 内容 | 密度参数／默认 | 高度参数／默认及范围 | 模板 |
|---|---|---|---|
| 橡树 | 草原trees.plains_density／0.01；山地trees.density／0.30；混合林独立 | trees.height／5，3..8 | 四层冠，半径2，高树半径3，含覆雪最多256格 |
| 白桦 | trees.birch_density／0.08 | trees.birch_height／6，3..8 | 较窄四层冠，半径2，最多128格 |
| 云杉 | trees.spruce_density／0.06 | trees.spruce_height／8，5..12 | 分层尖顶冠，半径最多3，最多256格 |
| 金合欢 | trees.acacia_density／0.28 | trees.acacia_height／5，3..8 | 连通斜干、分叉平冠，两档高度、四向旋转，最多128格，无雪 |
| 高草、大蕨 | vegetation.tall_grass_density／0.01 | 固定两格 | 稳定随机键等概率选型 |
| 丁香、玫瑰丛 | vegetation.tall_flower_density／0.003 | 固定两格 | 稳定随机键等概率选型 |
| 小岩石 | decorations.rock_density／0.12 | 最多两格高 | 石头、安山岩、苔石，最多7格 |
| 倒木 | decorations.log_density／0.06 | 一格高、2..4格长 | 水平X／Z橡木，允许长方体合并 |

密度范围0..1；三种树干高度均浮动±1，树冠额外向上延伸2格；简化模板仅保留低／高两档，旧路径包含中间高度。白桦／橡树候选格6格，云杉8格，两格植物3格，岩石8格，倒木12格。高草和花丛共享vegetation.enabled、patch_scale、max_slope。自然装饰共享decorations.enabled、patch_scale（默认64，8..512）、max_slope（默认0.8，0..4）。岩石允许草地及露岩，倒木只在草地；整个底部必须有同高、干燥且允许的实体表面，不铺平地形，也不填洞。完整树形、整株植物或自然装饰若与地形、水体或高度边界冲突则拒绝；旧方块路径水平裁切，整树模板保持完整。

金合欢在热带草原独立绑定，不复用橡树密度。当前候选格12格，高度为基准或加1，两个输出模式共用同一形状与四向旋转；非原生／变换模型覆盖走普通FeatureBatch。金合欢共享trees.patch_scale／max_slope及树木总开关。上述±1仅指原有三种树；热带草原不绑定其他树或花，snow_cover=0保留无雪约束。裸地参数savanna.bare_scale／bare_threshold不改变高度，草只放在合法草面。0.46.0的savanna.coverage／region_scale控制宏观成片区域，细温湿度不切碎内部；水域、寒地、恶地、山地、沙漠优先，详见R20（见 Git 历史）。

可选support默认anchor，仅检查锚点支撑；footprint额外批量检查所有offset.y=0方块的下方，任一无实体、湿格或不符合surface即拒绝整个候选，没有底部方块也拒绝。岩石和倒木使用footprint。树木priority=0，自然装饰5，两格植物10，较小优先。自然装饰计入feature_block_counts和feature_instances，保持地形实体和树木统计的含义。

上述支撑描述适用于默认 dry 和已有 underwater。0.34.0 新增通用 `habitat: water_surface`：锚点是显示水面整数格，surface 检查显示水面材料，`ctx.water_depths` 为只读可用水深。所有输出列须有显示水面且逻辑水位相同，形状可向下伸入水中；地形、岸边、其他景观和高度边界冲突整座拒绝。完整遮挡实体替代的显示水面不再输出，在预算分配前扣除，参考水面掩码与湿域保持；`feature_replaced_surface_cells` 记录替代数。隐藏或不生成水体时不生成这些景观，volume 模式继续明确报告不支持。冰山是该接口的内容实例，见 冻洋与冰山（见 Git 历史）。

倒木和直立原木共用`oak_log`网格与材质，通过实例旋转改变朝向：沿MC X使用码20，沿MC Z使用码8。无需轴向方块声明、临时JSON或额外网格。缓存、裁切和合并保留旋转，不同方向不合并；树干／树叶计数按树木特征归属统计，倒木不会计入树干。

## 内容包接口

`features.json`定义景观形状与固定查询语义。`surface_scatter`声明type、block，可选category、habitat、soft及allow_overlap_categories；`enabled_when`可用于各景观类型，缺省保持原行为。分布仍由群系绑定声明，不在核心判断植物名称。完整格式见[EXTENSIONS](EXTENSIONS.md)。多方块条目：

```json
{
  "oak": {
    "type": "multi_block", "generator": "trees:build",
    "blocks": ["oak_log", "oak_leaves"],
    "bounds": [[-3, 0, -3], [4, 11, 4]], "max_blocks": 128, "cell_size": 6,
    "category": "trees"
  }
}
```

分布写入每个适用的群系 JSON：`features.oak = {"enabled_param":"trees.enabled", "surface":["grass_block"], "density":"$trees.density", "patch_scale":"$trees.patch_scale", "max_slope":"$trees.max_slope"}`。群系按 ID 整份覆盖，不隐式追加绑定；景观定义按 ID 继承覆盖。

示例中的键必需，另可声明整数`priority`，默认0，较小优先；树木使用0，两格植物使用10，同级沿用稳定随机键。`blocks`必须是已声明的cube或decor；decor必须不遮挡、不合并，不接受surface。不从方块名猜测透明或缩放权限。原版树干`merge=xyz`，叶片`merge=none`、`occludes=false`；选择cuboids时连续树干可纵向合并，rectangles／runs仍只水平合并，none关闭合并。两格植物分别引用bottom／top模型，均为不遮挡、不合并的decor，不能将单格模型拉伸。密度、斑块和坡度接受数值或现有数字参数引用；开关引用bool。`bounds`为整数半开XYZ范围，`cell_size`为1..1024整数。生成函数首先在声明包查找，找不到模块时沿继承链向最近的父包查找，支持只修改规则的草稿／子包。函数和辅助模块仍使用私有源码快照，采用`.helper`、`..vanilla.helper`等相对导入。

```python
import numpy as np
from ...core.features import FeatureBatch

def build(ctx, anchors, keys):
    # ctx.seed、ctx.params、ctx.feature、ctx.block_ids只读使用。
    # anchors: int64[N,3]世界坐标；keys: uint64[N]稳定随机键。
    # 返回局部坐标，不访问地形，不修改锚点，不使用全局random。
    n = len(anchors)
    return FeatureBatch(
        np.zeros((n, 3), np.int32),
        np.full(n, ctx.block_ids['oak_log'], np.uint16),
        np.arange(n, dtype=np.int32),
    )
```

返回`offsets[N,3]`、`types[N]`、`owners[N]`三个整数数组；types使用pack ID，owners索引本次输入锚点。可选`rotations[N]`为整数码0..23，缺省为零，例如`rotations=np.full(n, 20, np.uint8)`。非零旋转以只读uint8数组传递；全部为零时保留None，`world.feature_cells.rotations`共享输出内存。每个owner可输出0格，不能重复坐标、超过声明边界／数量或引用未声明方块。核心统一选址、检查支撑与空间、处理冲突和裁切，生成器只构造形状。以后方块模板与其他Python形状生成器可使用相同接口；首版不支持修改地形、地下基础或游戏更新逻辑。

0.34.0 的通用校验一次排序同时检查重复坐标、提取 owner/X/Z 列的 Y 极值及包围盒。无洞穴时按列检查高度、水域和边界，洞穴范围内保留精确实体查询；底部支撑和整株拒绝不变，FeatureBatch 与完整实体输出不变。没有逐格按材料优先级裁掉冲突部分，也没有长期形状缓存。

## 一致性、缓存与性能

0.35.1 的列组装按每种方块的布尔分类表识别显示水面／装饰，不再构造逐单元字符串分类。没有实体阻挡时不创建整批过滤副本；空允许区域跳过列生成器。旧 FeatureBatch 及其实体保留、完整支撑、确定性竞争和缓存契约仍保留。vanilla 先合并冰体列再润色两圈，使用自己的12格查询半径，不扩大此处多方块景观的查询窗口。

0.36.0 的 soil_depth_field 只控制地形外壳的 top／under／deep 材料角色。景观候选仍查询实际顶层材质；材料变化可改变合法水草／草地支撑，但候选盐、树型、窗口及竞争规则不变。参考查询复用材料有限邻域的已算高度／水域；不为岸边材料新增景观阶段、体积数组或缓存，见 材料过渡（见 Git 历史）。

候选由世界坐标、种子和特征ID决定。小预览使用96²内部窗口；宽场景无洞穴使用256²、洞穴使用128²，自定义查询预算或世界边界不允许扩大时退回96²。窗口查询分块外的树冠及邻居；先按声明priority、再按稳定随机键局部拒绝重叠包围盒，植物不能挤掉树木，不采用依赖遍历顺序的递归／贪心算法。内部缓存只保存纯数据，每进程上限64MiB（含保守元数据估算），按需占用，沿用single-flight发布与完整reload清理，不写Saved。4个工作进程的特征缓存上限合计256MiB，主进程若也有缓存则另计。扩大缓存主要减少重复生成或返回近期配置时的淘汰，不减少首次求值，也不保证已经命中缓存的小区域继续提速。每批最多128候选。查询保护上限为每个局部特征65,536候选、地表1,048,576格，过大声明明确报错；这些是内存保护预算，不是UE渲染能力。

关洞穴使用二维地表。开洞穴按已有修改范围，只批量查询可能受影响的根与树形空间；支持成对稀疏坐标和现有密度窗口缓存，不分配全区三维植被数组。预算包括树木，超限报错而不是丢树。ISM／PCG／Niagara按方块和整模型模板批量输出，不每棵树创建Actor。

```powershell
# 先按README配置UE Python 3.11和PipInstall PYTHONPATH。
python -B tools/test.py related --group features
# 显式性能工具，不属于常规测试：
python -B tools/golden.py --scene default --mode serial --profile default.txt
```

`tools/golden.py` 记录冷启动耗时与完整摘要；分块／执行器一致性由 `test_determinism` 检查。进程不共享特征缓存；渲染成本与CPU生成成本分开验收。整树已交付，远景LOD按实际瓶颈另行设计。
