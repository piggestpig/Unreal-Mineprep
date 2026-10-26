# 内容扩展接口（格式 2）

## 参考地表有效区域

包可声明`reference_mask_field: "island_presence"`，引用一个已注册二维字段，返回与参考区域同形的有限0～1数值；低于0.5的列在景观、地表、群系及高度参考图中显示为空白背景。它只描述参考地表是否存在，不裁切实际密度或景物。字段随World／Overview保留，子包继承，也可用null清除；未声明时沿用原显示。末地用此项区分岛屿与虚空，完整体积预览仍取实际实体表面。

## 分布遮罩

WorldSpec的可选`vegetation_mask`／`clearance_mask`为`{"path": "绝对路径", "region": [x0,z0,width,depth]}`，通过`api.with_vegetation_mask`／`with_clearance_mask`绑定或移除。没有输入时不序列化新增键；既有配置保持可读。图像格式、坐标、密度和净空语义见[MASKS](MASKS.md)。遮罩参与实体生成身份，不改变高度、水位、群系或地形规划身份。

内容包用现有景观category声明作用范围：

```json
"mask_categories": {
  "vegetation": ["trees", "vegetation", "aquatic"],
  "clearance": ["trees", "vegetation", "aquatic", "decorations"]
}
```

两组分别继承；子包声明其中一组时替换该组的整个列表，空列表禁用该组作用，没有声明的独立包默认为空。类别名称为不重复的标识符，不猜测方块名称或复用布尔参数来判定植物。surface_processors可声明可选`category`，其补种或替换输出也按该类别筛选；默认空字符串不参与遮罩。多格完整景物应使用FeatureBatch／TemplateBatch，SurfacePatch仍按单格补丁工作。

## WorldSpec文件高度输入（0.47.0）

WorldSpec格式2新增可空heightmap描述；格式1继续读取，视为无文件输入。使用`api.with_heightmap(spec,path,mode='faithful',region=None,input_range=(0,1),output_range=None)`返回新Spec；path=None清除，配置不读文件。region为Region或四元组，省略时固定为绑定时的Spec.region，后续replace(region=...)不拉伸。描述序列化绝对路径、mode、region和两对范围，不含像素。

仅支持vanilla及保留height_lowlands→height_custom→height_islands→height_badlands→height_before_rivers→height链的派生包。add保留已有height_custom，在其后叠加；faithful使用绝对高度并临时关闭后续高度塑形及自动水系，保留群系／材料／植被／洞穴。平坦模式的文件输入优先，add以flat_height为基底；原参数不被改写。无法接入的字段链明确报错。

PNG8／16按255／65535归一化，默认映射到world.y_min..world.y_max；浮点EXR保留数值，默认输出0..1形成恒等映射。可修改输入／输出范围，线性外推，最终遵守世界高度裁切。没有观察值归一化、sRGB转换或UE压缩类型判定。允许RGB一致的灰度彩色图，Alpha忽略；实际彩色、非有限值、损坏或超16,777,216像素输入报错。数组[Z,X]，双线性列中心采样，覆盖区外边缘延伸。

generate／overview／fields／check／locate／prepare及水系／洞穴规划共用文件输入；`heightmap_value`可通过fields查询映射的绝对高度或增量。describe.heightmap公布格式、模式及包支持情况。World／Overview的pack.heightmap持有只读输入快照；独立预览不读取最新文件。生成stats.heightmap记录read_seconds、hash_seconds、decode_seconds、sample_seconds、sample_points和array_bytes；采样计时为实际工作累计，不冒充并行墙钟。

面板“自定义”配置作为操作偏好／会话／原生快照保存，缺省关闭。“保存用户资源包”及参数预设不复制图片。图片文件变化使生成／物理规划失效；模式和映射同时参与身份。详见[R21](HEIGHTMAP.md)及[CACHE](CACHE.md)。

## 群系颜色与BCT（0.62.0）

当前0.46.2的混合林／针叶林／覆雪针叶林forest_region下限为-0.5，四类森林humidity下限为-0.2；温度、优先级及各树密度保持。金合欢默认0.28，下文0.46.0的0.36为历史值。没有新增字段、参数或接口；手动调整见[面积与密度](FEATURES.md#手动调整森林面积与树密度)，保存的显式配置不会自动升级。

0.46.0只调整vanilla配方与默认内容，公共接口保持。普通草原与水域倍率为[1,1,1]；BCT白色表示中性倍率，不表示没有植被，实际统计使用generate及check(World)。`savanna_weight`是16格两层宏观气候权重，`savanna_mask`是限制为0～1的边界扰动结果；可通过fields查询。宏观温湿度包含用户偏移，不含高度降温及细边缘噪声，群系使用mask≥0.5、干域且无雪，优先级保持。coverage默认0.75、0跳过专用采样，region_scale默认768。普通草原仅绑定oak与trees.plains_density（0.01）；旧trees.density及自定义包绑定保持。金合欢候选格12、默认密度0.36。用户显式配置与旧快照不自动重写，格式仍为2。

群系JSON可选vegetation_tint: [r,g,b]和vegetation_hsv: [h,s,v]，各缺省[1,1,1]。RGB为线性乘法倍率，非负有限且≤65504；HSV的H为0.5～1.5，偏移(H−1)×360°，S／V为非负有限倍率且≤65504。与地图color独立，不拆草／叶通道；describe.biomes公开两套解析值。继承仍整份覆盖。面板RGB使用LinearColor，Alpha固定1不保存；HSV为三个数值控件。

`api.write_biome_texture(World或Overview, path, cell_size=4, vegetation_tints=None, biome_color_mode='rgb', vegetation_hsv=None)`只读快照，返回path、width、height、cell_size、biome_color_mode、key、map_seconds、encode_seconds、seconds；只接受.exr。两项覆盖均为群系ID→三分量映射，使用当前模式的表，遗漏采用快照声明，未知ID报错。HSV三分量在平滑前取负；整张纹理不混用模式。9×9局部平均（边缘复制）后面积降采样；尺寸各轴ceil(格数/cell_size)，整数精度1..16，单边上限16384。FP16 RGB EXR，数组[Z,X]；OpenCV写入只交换RGB/BGR，不翻转空间轴。

map_seconds包含映射、平均与降采样；encode_seconds包含EXR编码、写文件和身份计算；seconds为本次完整导出壁钟，不含UE导入或纹理构建。离线启动需在首次导入cv2前设置OPENCV_IO_ENABLE_OPENEXR=1，已导入但未启用时需重启解释器。

`prepare(..., biome_texture=True, biome_cell_size=4, vegetation_tints=None, biome_color_mode='rgb', vegetation_hsv=None, chunk_count=1)`是输出选项。PreparedWorld保存biome_texture／biome_key／biome_enabled／biome_cell_size、biome_color_mode、冻结的vegetation_tints／vegetation_hsv正数ID/三元组、chunk_count及base_reused；入口校验并冻结两套表，reused仍表示完整准备命中。textures仍为BPT／BRT。模式／色板／精度／启停变化复用同世界、后端、合并及资源依赖的准备基底，颜色身份只算一次，biome_seconds在实际生成时包括该次身份及EXR导出，biome_import_seconds单列。源、资源、预算及纹理就绪检查不跳过。

ISM只须提供生物群系纹理，不读写两个边界点；PCG／Niagara仍要求三属性并赋组件局部A=(0,0,0)，B=(width,depth,y_max-y_min)×100。纹理TC_HDR、srgb=False、Clamp、无Mip、不流送，独立于结构F32数据纹理。ISM整区各模型Actor共享BCT，自动边界的近似偏移按用户选择保留。

chunk_count是空间区块总数，整数1..region.cells，默认1；仅ISM生效，其他后端规范为1。按最长边递归二分，面积比例向下取整分配数量并按两侧容量约束；同长先X、低坐标优先编号。WorldArrays.groups(count)返回(chunk_id,type_id,indices)，按锚点归属，不切开合并方块或整树。ISM分区时BCT实际关闭，UI隐藏相关控件但保留偏好；Actor纹理为None。place(prepared,chunk_count=None)沿用准备值，显式值必须一致，旧chunk_size删除。

核心固定流程为：参考场 → 实体查询与景观放置 → 地形及显示水面输出 → 列景观 → 表面处理 → 结果汇总与输出准备。vanilla气候阈值由群系文件声明，候选使用世界坐标随机键；0.35.0增加细网格采样和通用列景观。无需安装Unreal即可导入`api`、加载包和生成NumPy数据。

## 作者接口（0.44.0）

```text
api.create_pack(pack_id, *, extends='vanilla', root=None, name=None)
api.biome_order(pack_id='vanilla', *, insert=(), before=None, after=None)
api.check(source, *, full=False, expect_biomes=(), expect_features=(), **options)
api.locate(source, *, biome=None, where=None, origin=None, **options)
```

create_pack返回绝对Path，默认根为Saved/packs，创建pack.json、空landscape.py和README，继承父包、不追加内容。ID与父包先校验，拒绝覆盖目录或遮蔽已注册同名ID；临时目录加载和解析成功、父包仍有效才发布并注册。新解释器仍要register_pack_root；不初始化PackDraft或运行迁移，不继承planning_params声明。

check与locate的source接受WorldSpec、Overview或World。Spec分别调用一次overview或generate（仅check的full=True）；已有结果只读复用其自身包快照，来源文件后续修改不导致重采样。已有结果不接受生成选项；Overview的full检查明确报错。Spec选项沿用所选入口的执行器、取消与预算参数，不新增预算或缓存。

check返回JSON友好字典：ok、scope（reference/full）、pack、fingerprint、seed、region、terrain（min/max/mean/cells/wet_cells）、biomes（全部ID占比）、features、errors、warnings、seconds。景观项包括enabled、cells、instances、unsupported、status。未计算时计数为None；状态为not_sampled、disabled、not_observed或present，列景观按实际cells判定。disabled依据绑定启用条件和非零密度，不解释选址／碰撞失败。默认零占比不报警；expect可用单字符串或ID列表，局部缺失写warnings，未知ID写errors。ok表示检查完成且无errors，不表示警告为空或全世界可达。包加载、参数或生成异常形成错误报告；GenerationCancelled及PackChangedError继续抛出，不发布成功报告。接口类型／复用选项错误直接报错。

locate至少指定biome或where。biome为一个包群系ID；where为`{'字段名': {'min': 数值, 'max': 数值}}`，至少一端、数值有限，不支持回调、扰动或参数表达式。条件相交，下限包含／上限排除。height读取通用最终参考高度，其他名称须为包声明的数值字段；Spec自动将它们加入keep_fields，已有结果缺字段报错并提示重新获取。origin为MC水平(X,Z)，默认列坐标的区域中心；最小水平距离命中，等距按X、Z排序。返回x、z、height、biome、distance、reference=True；None仅代表source.region内未找到。不能据此承诺洞后真实支撑或定位实际结构，不自动扩大规划／区域。

fields的names、generate／overview的keep_fields接受单字符串或原有列表／元组。generate的None仍保留默认群系字段；overview默认空字段，显式None仍为错误，fields的names也不接受None。fields的region接受Region或四元组／四元素列表，其他类型明确报错。示例与显式扩大区域、复用概览见[内容包入门](CONTENT_PACK_GUIDE.md#复用地图检查与取景)。

作者工具补充：biome_order返回当前顺序的新列表，不写文件。不传insert返回副本；insert支持单字符串或列表／元组，插入时before／after必须且只能指定一个，锚点须存在。新ID可以还没有文件，但须符合群系ID规则；重复、已启用ID及无效组合报错。不支持移动已有群系，返回值需写入pack.json.biomes才能生效。

Pack.inactive_biomes记录当前包的本地文件中未进入最终顺序的ID，按ID排序；不包含父包的未启用文件，不自动启用或推断气候可达性。describe及check以同名列表公开，check给非致命配置warning；expect_biomes明确请求该ID时在errors说明缺少顺序声明。已有快照只查询当时的记录，不扫描现有文件。默认区域零占比仍不报警。

## 水系前高度入口（0.42.0）与整区处理 `@region_pass`

vanilla及派生包可覆盖`@field('height_custom', deps=('height_lowlands',))`，返回修饰后的绝对高度；默认原样返回低地。高度链为低地→height_custom→岛屿→恶地→海床→水系，粗规划注入原低地DEM后经过同一入口。标量／可广播二维结果沿用字段规则，进入后续高度链前检查有限值；平坦模式使用原低地，配方需自行提前跳过无效噪声。声明依赖最终height的循环会被字段图拒绝。

关闭水体仍保留修饰；后续塑形仍生效。入口不保证绝对最终高度，不允许递归请求水系规划，独立包自行组织字段链。局部高原示例见[内容包入门](CONTENT_PACK_GUIDE.md)。没有新增阶段框架、缓存或包格式键。

需要在二维字段图里做整区非局部运算（如大半径平滑、侵蚀、距离场或图章）时，使用 `@region_pass(name, *, deps=(), margin=0, region=None, outside=None, resources=())`，函数签名同 `@field`（`fn(ctx, *deps)`，固定 `res=1`）。不依赖规划资源的整区处理在 `planning` 前于工作域（或显式固定 `region=(x0, z0, w, d)`）外扩下游 `halo + margin` 后整块求值一次并裁回，水系规划（粗网格与细化窗口）、`FieldStore` 条带、地表规则与景观均切片读取同一只读数组；覆盖域之外回退到 `outside`（字段名或有限常数，缺省取首依赖或 `0.0`）。未固定 `region` 的整区处理随请求工作域变化，不满足“扩大区域重叠不变”，规划资源键自动纳入请求 `region`。`api.describe().fields[name]` 公布 `region_pass`、`margin`、`region`、`outside`。

整区结果的传输窗口包含下游 `halo`、`margin` 与粗格点插值支撑范围。实体阶段的远距离地表查询还需覆盖地表缓存的整块范围；有此类查询的规划对象可实现 `surface_region(region) -> Region`，返回该查询域涉及的保守地表范围，核心会合并各规划范围。固定域与任务窗口不相交时直接使用 `outside`，不重复执行整区函数。

## 群系与景观

`pack.json` 声明 `format_version: 2`。群系文件按 ID 整份覆盖；`features.json` 按景观 ID 继承覆盖，不能在景观定义里放群系列表或分布参数。群系负责全部分布条件：

```json
"features": {
  "pillar": {
    "surface": ["grass_block"],
    "density": "$pillars.density",
    "patch_scale": 32,
    "max_slope": 2,
    "enabled_param": "pillars.enabled"
  }
}
```

绑定需要声明 surface、density、patch_scale、max_slope，启用参数可省略。密度在 [0,1]，斑块尺度大于零，坡度非负，数值可使用 `$参数键`。加载器校验并编译绑定；同一个景观可以在不同群系使用不同密度。群系覆盖后的绑定不隐式追加。

气候盒保持闭区间和列表优先级：显式 fallback 包按顺序匹配，按需读取字段，全部位置确定后停止；没有 fallback 的包使用归一化最近盒距离。vanilla 的 climate.warp_strength／warp_scale 控制共用气候采样位移，强度 0 恢复原坐标；它不是新增核心选择器或格式字段。实现、二维对照及性能分拆见 冻洋修订（见 Git 历史）。

景观定义仅声明生成器、方块、有限形状、候选间距、支撑、碰撞优先级与统计分类。例如：

```json
"pillar": {
  "type": "multi_block", "generator": "landscape:pillars",
  "blocks": ["stone"], "bounds": [[0,0,0],[1,7,1]],
  "max_blocks": 7, "cell_size": 12, "category": "pillars"
}
```

Python 生成器仍是 `fn(ctx, anchors, keys) → FeatureBatch(offsets, types, owners, rotations=None)`。偏移采用 MC XYZ，包方块 ID 来自 `ctx.block_ids`，owners 指向输入锚点。不要访问 UE，不要自行查询地形或修改输入。生成器必须遵守半开形状边界和最大方块数；核心提供支撑、真实占据、碰撞、裁剪和预算检查。`surface_scatter` 定义仅需 type、block、可选 category；分布也放在群系。

多方块景观可声明 `habitat: dry|underwater|water_surface`，默认 dry。水面锚点位于 `floor(逻辑水位)`，绑定的 surface 检查包声明的显示水面方块；只读 `ctx.water_depths` 提供锚点下方、实体地面上方可容纳的完整水格数。形状允许跨水面向下延伸，所有水平投影列均须有已显示水面且逻辑水位相同，地形、岸边、其他景观及高度冲突整座拒绝。隐藏水面或关闭水体生成时不生成水面景观。完整遮挡实体占据显示水面单元时，组装阶段移除该水面输出，在分配预算前扣除，保留参考 water_mask／wet_mask；统计为 `feature_replaced_surface_cells`。`api.describe().capabilities.water_surface_features` 说明高度地形可用性，体积模式继续报告不支持。

`planner_gates` 将规划资源映射到布尔参数列表；全部为真才启用。`feature_counts` 和 `feature_categories` 按景观归属记录实例数、单元数及方块计数，包含散布景观。`feature_metrics` 可声明 `{category, blocks}` 汇总指标；vanilla 树干／树叶指标来自包声明。表面处理新增单元单独计入 `surface_added`，替换计入 `surface_replaced`，不算作生成器实例。

## 单格软散布（0.40.1）

所有景观可选`enabled_when:{布尔参数名:布尔值}`，与群系绑定的enabled_param同时满足才执行。未知／非布尔参数及非布尔条件拒绝；默认空条件保持原行为，禁用景观在候选和噪声之前跳过。格式版本仍为2。

`surface_scatter`沿用block及群系的surface／density／patch_scale／max_slope／enabled_param绑定，增加可选habitat（默认dry，可选underwater）、soft（默认false）与allow_overlap_categories（默认空列表）。材料仍须为decor；这些选项分别校验合法湿域、布尔类型及类别名列表。未声明时保留原规则。水下散布要求物理水域启用，且完整单格位于整数水面以下；显示水面开关不改变物理水域。

核心直接使用实体分块参考数据、斑块噪声和稳定世界坐标键，每列最多一株，没有形状生成器、组块网格、旋转、预算回退或逐株FeatureInstance。草不进入多方块包围盒竞争；按景观归属批量排除实际硬单元及模型，类别豁免仅作用于景观，洞穴真实支撑及占据仍检查。

World.soft_mask为与普通arrays对齐的只读软标识，plant_ids保留方块ID+1，plant_owners为对应包景观定义序号+1。软草不进入真实实体、支撑和天空遮挡索引，仍用于绘图与统计。列实体删除草时同步plant_ids、plant_owners、soft_mask与归属计数，冰体不为草留洞；表面新增实体的软标识为false。模板不再声明soft角色，仍采用原真实占据语义。

stats.soft_plants统计最终软单格草，feature_counts／feature_categories统计景观归属；output_model_types统计实际使用的普通类型与整树模板。0.40.0的surface_cover、CoverBatch、软模板及组块统计已删除，不维护兼容层，格式仍为2。vanilla草密度默认0.05，海草密度默认0.08；简化模式海草表示每列概率，完整模式沿用原候选语义，保存参数不自动改写。

## 精确参考概览（0.37.0）

0.38.0起，参考顶面也调用可选terrain_materials，概览可显示实际陶瓦色带；仍不生成外壳、洞穴开口或景观。

`api.overview(spec, keep_fields=(), execution='serial', workers=4, tile_size=256, ...)` 返回独立 Overview：spec、key、pack、params、heights、biome_ids、columns、water_levels、wet_mask、water_mask、fields 和 stats。数组为只读，坐标和参考语义与完整生成一致；没有 arrays、景观、实际洞穴表面、覆盖或准备状态。面积预算、取消、任务进度及固定包源码快照检查均有效。

概览使用同一个参考求值器和分块收集器。规划器在字段实际请求时加载并校验当前区域，未引用的规划器不会被预热；自定义参考字段依赖洞穴等资源时仍按声明执行。没有新增包声明或低分辨率采样。

`api.describe()['capabilities']['overview']` 标记此能力。`ops.preview_overview()` 是 UE 主线程启动的图片 Job，计算／写PNG在后台，返回 OverviewResult，不进入完整世界／准备缓存。可以传回同一有效 Overview 重绘；包指纹、世界键和面积预算每次重新检查。温湿度未声明的包不提供相应概览视图。

自动概览只支持景观、地表、群系、高度和可用温湿度；其他视图提示手动生成完整预览。概览与完整结果分开保存，不能让旧世界或准备结果恢复有效；旧结果、失败、取消和切包仍使用任务版本控制。完整生成已有的参考阶段回调契约保持。

## 按列覆盖厚度（0.36.0）

包可声明 `"soil_depth_field": "cover_depth"`；字段通过现有 `@field` 注册，返回参考区域 `[Z,X]` 的整数值厚度（0–32）。整数值的浮点数组也可使用；标量按既有字段规则广播。缺省时继承基包声明，独立包缺省或显式 `null` 使用 `surface.soil_depth`。字段名、形状、有限值、范围及整数值严格校验；非法结果报出字段名。

共用参考查询只求值一次，将变化厚度保存为阶段内只读 uint8 网格，常量退化为标量。高度快路径、完整洞穴外壳和局部外壳共用角色判定：深度0为 top，1到该列厚度为 under，其余为 deep；深度仍取原参考顶面，不将洞顶改认成地面。它只选材料，不新增实体，不修改密度或水体。

材料字段的有限 halo 在加载时确定。参考入口复用最大邻域中已有的声明字段，避免再次计算同一区域的高度／水域；私有配方缓存不搬运，阶段结束释放，没有新增长期缓存。水面掩码仍使用裁切后的参考高度。规则按原顺序、原随机盐选择，未命中的条件和已完成的材料角色跳过后续求值。

`api.describe()` 提供 `soil_depth_field` 及 `capabilities.per_column_soil_depth`。vanilla 的岸边厚度及暖干山脚选择都在 `surface_fields.py` 和群系规则内；核心不检查具体群系或方块名。现有 API、格式2和旧标量路径保持，见 材料过渡与验证（见 Git 历史）。

## 细网格采样与列景观（0.35.0）

字段上下文提供 `ctx.grid_sample(name, step=4, strength=1.8, salt='climate/cells')`。世界对齐网格四角具有稳定偏移，选择扰动距离最近的一角读取字段；不会对映射结果再次平滑。同一上下文共享源网格与角点选择，结束即释放。强度0完全走原字段路径。vanilla 五个基础气候字段共享此映射；高度降温、雪线和物理地形／水系保持真实坐标。

```json
"body": {"type":"column_field", "generator":"landscape:columns",
         "blocks":["stone"], "radius":4, "max_height":48,
         "habitat":"water_surface", "category":"bodies"}
```

群系绑定沿用 surface、density、patch_scale、max_slope、enabled_param。函数 `fn(ctx) → ColumnBatch(xz, lower, upper, types, diagnostics={})` 返回绝对整数水平坐标 `[N,2]`、半开Y区间和包材料ID `[N]`；材料必须是完整遮挡立方体。`ctx.region` 是当前输出区，`ctx.reference` 是带有限 radius 的只读参考，`ctx.allowed` 是群系／材料／湿域条件，另有 seed、params、block_ids、density、patch_scale。只能提交输出区；相邻材料区间允许，重叠区间明确报错，包内先合并重复来源。

核心按独立256格输出窗口调用，不扩大树木候选窗口。区间按地形与高度边界裁切；已输出实体优先保留，被占据的显示水面与装饰删除。列内部完整方块只展开一次，保留列摘要供占据与顶面查询，使用既有合并。水面列要求已有显示水面；隐藏水面或关闭水体时跳过。生成前检查预算，超限报错。体积模式报告列景观不支持；`api.describe().capabilities.column_features` 提供能力说明。

`stats.column_features` 按景观ID记录列数、最终单元数、连续列数、独立候选数和区间数组字节数；耗时在 `stages.column_features`。列景观的 feature_counts 实例数保持0，不能将列数当成冰山座数。`column_work_array_bytes` 是组装阶段同时存活的主要数组规模估计，不是进程RSS或全部分配的实测峰值。

现有 multi_block 的完整支撑与整座拒绝契约保留。列景观采用局部裁切，并不修改旧 FeatureBatch 的规则。vanilla 配方与真实区域对照见 连续冻洋冰体（见 Git 历史）。

0.35.1 的 vanilla 冰体先合并连续来源与独立宽丘，再在最终覆盖外侧两圈柔化地上高度；声明 radius=12 包含独立形状的10格范围与2格邻域。顶型按独立盐的64格区域键平滑混合，地下基底独立保留原深度曲线；雪帽适配润色后的高度。只有地上顶型取消提前取整和饱和截断，基底曲线仍有独立的有界噪声。局部裁切、实心输出和合并保持。核心遇到空 allowed 区域直接跳过生成器，包内 isolated_fraction=0 跳过独立候选计算；未增加长期缓存或类型专用线程池，见 润色记录（见 Git 历史）。

## 整模型模板（0.39.0）

0.42.0公开树木助手；0.42.1简化为`core.templates.tree_template(id, trunk, foliage, *, trunk_block, foliage_block, block_ids, block_defs, snow_layer=0)`，返回现有TemplateDefinition。局部整数MC XYZ稳定去重、树干优先，自动生成材料／烘焙记录及树干与分层树冠半开盒；不修改输入。仅支持builtin cube及单位变换木／叶，其他来源报错并提示FeatureBatch。

snow_layer为整数0–8，默认0无雪；布尔值、小数、越界值拒绝。1–8读取约定的逻辑材料snow_layer_N：builtin模型必须为snow_height{2*N}（1–7层）或snow_block（8层），shape=cube、occludes=false、单位缩放、零偏移。缺失或不匹配报错，不扫描猜选材料。最高实体为树叶的列才加雪；不读取气候或cold参数。烘焙记录仍为原生snow的layers属性，包自行选择变体并返回TemplateBatch。旧助手snow_block／snow_layers参数删除，不保留未发布接口兼容层。完整示例见[内容包入门](CONTENT_PACK_GUIDE.md)；原版树的ID、形状、旋转及覆雪烘焙配方保持。

已有`multi_block`生成器可返回`core.templates.TemplateBatch`，无需新增JSON类型。构造`TemplateDefinition(id, offsets, types, boxes, bake_cells)`：offsets为整数局部MC XYZ[N,3]，types为包内方块ID[N]；boxes为1–8个半开检查盒[K,2,3]，须覆盖所有单元。bake_cells是不可变元组，每项`(x,y,z,原生模型名,属性键值元组)`，与逻辑坐标逐项对应，例如`(0,4,0,'snow',(('layers','1'),))`。ID必须是合法Python标识符，同一World中同名定义不得冲突。

`TemplateBatch(templates, template_ids, owners, rotations)`的三个一维整数数组等长：template_ids索引定义，owners索引输入anchors且不得重复，rotations为0–3个正向UE yaw的90°旋转。核心校验材料声明、单模板max_blocks、原始及旋转边界、检查盒和输出实例预算。生成器可读取`ctx.reference.height/levels/wet/biomes/columns/x/z`或`ctx.reference.get(字段名)`的只读视图，复用当前参考求值；`ctx.block_defs`提供只读资源声明。

`TemplateDefinition`可设`cellwise=True`：仍按完整景物做选址、碰撞、遮罩和竞争，输出时再拆为单格实例，按原生模型名与属性复用单格网格。这样能保留紫颂树等连接状态；普通FeatureBatch只携带方块ID和旋转，不能直接携带这些属性。单格输出沿用原景物的朝向、材质单双面设置，不使用整树微缩，水平范围外的方块会被裁掉。

无洞穴时投影少量检查盒做批量高度／水体检查；有洞穴时保留受影响模板的真实实体查询。模板与旧FeatureBatch共用候选盐、支撑和包围盒竞争，检查盒有保守性。所有实际单元在定义时形成四种旋转的列区间及顶面记录，保留内部空隙；不是以整个包围盒作为占据。

World.model_instances保存完整模板实例，World.arrays只含普通单元。模板按锚点归属输出，不裁树冠；普通FeatureBatch继续按单元裁切。模板内部固定，不向SurfaceBatch枚举为可编辑方块，但参与occupied、遮挡、地面覆盖及列景观保留实体的查询。改变内部覆雪等几何应由生成器选择另一模板。

prepare只将实际用到的配方烘焙为版本化UE资产，在普通方块合并后追加一个不拉伸的模型实例，复用三个后端；来源指纹包含配方、属性、blockstate、模型继承与贴图。详见 使用与验收（见 Git 历史）。公共调用流程及格式2不变；未声明三维选址的景观在volume模式中继续报告不支持。

0.39.1网格统一位于templates，旁边mat／tex按资源来源共享；模板几何改变不再复制相同贴图。0.39.3收尾对本次模板及结构纹理按路径去重，检查源尺寸与非空平台数据。异常资源优先调用可选的`unreal.mineprep.finish_build_texture`后保存；无绑定则统一等真实下一帧，对仍异常者换构建键并保存一次。引用缺失／身份错误／保存失败报错；平台数据仍未就绪则逐资产警告并允许放置，结果不进入准备成功缓存。健康模型与纹理复用，不再逐纹理重试。公共Blocks、模板数据契约和几何身份不变。

## 表面处理

包内 `surface_processors` 为有序列表，子包声明列表时整体替换父包列表：

```json
[{"id":"cover", "function":"demo:cover", "blocks":["demo_snow"], "radius":0, "enabled_param":"cold.cover"}]
```

可选`volume: true`显式允许处理器在三维体积地形中运行，仍使用已有SurfacePatch与真实占据查询。默认false，原有高度地形处理器不会被隐式启用到体积地形。末地以此添加静态传送门表面；三维地形本体仍由密度与壳层材料负责。

可选布尔字段 `sky_only` 默认 `false`，保持全部真实向上表面的输入。设为 `true` 表示处理器只需要 `sky_open=True` 的表面：核心先按当前立方体、列景观和模型顶面计算天空遮挡，再对露天候选做真实占据查询，避免为积雪等处理枚举洞内表面。水面也按同一天空判定筛选，洞口仍使用实际支撑。vanilla 的 `cold_surfaces` 已声明 `sky_only:true`；子包继承声明，自定义实现若需要洞内表面应显式设为 `false` 或替换处理器列表。格式版本保持2。

函数为 `fn(ctx, surfaces) → SurfacePatch(xyz, types, replace)`。XYZ 是绝对整数世界坐标，types 是包方块 ID，replace 为布尔数组。新增必须在空单元，替换必须有已输出单元；重复坐标、未声明方块、越界、错误数组或超预算均报错。只能提交 `ctx.region` 内且在世界 Y 范围内的结果。核心按固定 256 格输出块调用，输入含所声明半径（0–64）内的已生成表面，结果与地形计算分块及执行器无关。

`SurfaceBatch` 数组只读：xyz 为支撑单元，types 为包方块 ID，kind 为 0 地形／1 景观／2 显示水平水面，biomes 为群系索引，sky_open 为上方没有实体遮挡，water_levels 仅在水面记录中提供逻辑水位，其余为 NaN。参考高度不是实体表面：洞口内不能以参考高度为支撑；水面独立于物理湿域。处理器可通过 `ctx.query.reference(region)` 查询高度、坡度、群系、地表材料、水位及湿域，通过 `ctx.query.occupied(xyz)` 查询真实地形／景观占据。查询半径超限报错；引用查询按需求值，不分配完整体积。

表面枚举限于本次生成区域及其已生成单元；区域外邻域可以查询参考和占据，不会提供未生成的覆盖层。处理器如读取邻域，必须使最终决策只依赖世界坐标和声明的有限邻域；不要依赖批次排列或外部可变状态。按顺序运行时，后处理器能看到前处理器新增／替换的单元。

只需高度、坡度、水位、湿域和字段时，可使用 `ctx.query.reference(region, include_surface=False)`，跳过群系选择和材料规则，返回的 `biomes`、`columns` 为 None，其他查询语义不变。默认仍返回完整参考。占据查询复用当前阶段坐标索引；关闭洞穴时从本次地形外壳提取精确整数列顶面，排除景观及立方体散布植物，不用 float32 参考高度推断整数边界。洞穴、区域外及未持有精确顶面的独立查询保留原始精度路径；必要的 64 格高度小块只在本次调用内复用，结束即释放，不跨世界或跨进程共享。

景观预览读取表面处理后的最高实体／水面材料，显示覆盖和替换颜色；地表、植被和水系诊断图继续描述各自的参考数据。预览着色不能代替 UE 模型与材质观感验收。

高度地形及其洞穴支持向上的真实实体表面（地面、树冠）和静态水面。三维体积配方对未声明placement的多方块景观返回`feature_unsupported`，对表面处理器仍返回`surface_unsupported`；显式三维选址见下文。关闭全部处理器时直接保留原始输出。

## 体积景观选址（0.53.0）

multi_block可选声明`"placement": "module:function"`。volume模式仅执行显式声明的选址；旧地表分支不变，不以参考height猜测洞穴地面。cell_size支持原整数或`"$section.integer_param"`，参数默认值和运行值均须在1—1024内。

显式volume景观可选`"collision": "cells"`，在包围盒粗筛后按实际格细查，默认`bounds`保留原规则。可配`"overlap_blocks": ["nether_wart_block", "shroomlight"]`允许小范围冠层交叠：每对最多为较小侧可交叠格数的1/8（至少1格），且交叠双方都在列表中；任何其他格接触仍拒绝。列表只能引用本景观声明方块，height配方不能启用cells。两者仍用现有优先级和局部最小值规则，不做跨查询边界的贪心链；逐方块同格输出按优先级／候选键去重，模型索引合并相交区间。此选项解决复杂冠层包围盒过度排斥邻株的问题，例子见菌树改进（见 Git 历史）。

选址函数`fn(ctx, candidate_xz, keys)`接收只读整数XZ与固定候选键，返回`core.volume_features.Anchors(positions, candidates, materials, slopes)`。positions为绝对整数[N,3]，candidates为输入候选索引[N]，每候选最多一个锚点且保持XZ；materials是配方报告的支撑类型ID，slopes是非负有限局部坡度，继续接受群系绑定surface和max_slope筛选。nether报告岩体基材netherrack，覆盖着色不决定承载；其他配方须按自身支撑语义填写，核心不会从二维columns推断。

ctx提供pack、params、seed、feature、block_ids、resources和query（VolumeQuery）。配方负责物理高度、洞底／洞顶选择、水位及落点策略；选址不读取输出裁切。核心在生成后批量复核支撑和所有实际方块净空，再用原包围盒优先级和预算；最后按输出XYZ裁切。anchor检查锚点下方；footprint要求底部实际方块至少一个有支撑，配方可更严格（化石要求至少三分之一落点）。

0.54.0增加`support="ceiling"`：锚点须为空气，其上方一格为实体；声明要求volume密度及显式placement，否则加载报错。萤石以真实洞顶下首格为锚点，几何向负Y延伸。生成器与选址函数分别按各自模块解析所属包，子包可覆写其中一个并复用祖先的另一个。已有anchor／footprint行为保持。

此入口从0.58.0起同时接受FeatureBatch和TemplateBatch。体积模板沿用材料、旋转、边界、预算验证，按实际格检查物理净空，footprint要求全部底面格有支撑；旧FeatureBatch支撑语义保持。整株按锚点归属输出，高度裁切碰到模型则整株跳过，普通格逐格裁切。分段朝上露面参与剥顶预览，全局ModelIndex过滤跨块洞底散布。实例见packs/nether的crimson与fossils模块；无需改公共spawn_structure、WorldSpec2或输出分组。墙面支撑及全部表面处理器仍未开放。

0.53.1的volume生成上下文增加`ctx.query`（同一VolumeQuery），用于有界的贴地补格。补格仍受声明bounds、max_blocks、完整净空、冲突和裁切校验；普通高度生成上下文该字段为None。nether化石只延长原贴地支脚，最多3格，不改变地形或破损悬臂。

二维字段库 `core.store.FieldStore` 是地形、景观、列景观与表面处理共用的参考地表入口，在工作域（输出区域 + 包外边距）内按条带只算一遍，下游按窗口切片读取。`Resources.report` 保存阶段计数和诊断（分块诊断按底层键名统一汇总，例如密度求值计数为 `density_samples`、阶段为 `density_noise`／`density_interpolation`，`_bytes` 后缀键取分块峰值），世界 `stats.stages` 汇总阶段耗时；取消、进度和参考地表回调保持原有约定。

### 生成阶段与计时（0.39.4）

`api.generate(..., on_phase=callback)` 的回调为 `callback(name)`，只在组织生成的调用线程运行，不传入线程／进程分块任务。顺序为 `planning`、可选的 `reference`／`reference_publish`、`entities`、`assembly`、`column_features`、`surface_processing`、`finalize`。参考阶段只在订阅 `on_stage` 时执行；旧 `progress(done,total)` 仍仅报告实体分块，回调异常传播，阶段边界检查取消。

`stats.phase_seconds` 为这些根阶段不重叠的壁钟耗时；`build_wall_seconds` 覆盖整个 `build_world`，包含参考发布回调、模型索引和最终检查。参考发布回调若绘图，该时间包含在 `reference_publish` 中。旧 `seconds`／`stages` 保留原口径，后者包含并行分块工作量和嵌套子项，不能相加当作壁钟。表面统计 `surface_candidates_before`／`surface_candidates_after` 为各处理器露天筛选前后的候选总数，`surface_probe_points` 仅计表面提取时对立方体上方的真实占据查询点，不包含处理器和补丁校验的查询。

编辑器任务经 `Job.report` 在主线程显示阶段；完整世界缓存命中显示复用结果，跳过生成阶段。统计区分生成流程、表面处理、参考／最终绘图、参考／最终UE导入及请求总等待。绘图和导入可能与后台工作重叠，不把这些指标相加估算请求等待。

## UI、目录与快照

`ui_sections` 是有序映射。每节可声明 label、pages、controls、shared_group、groups、editor。groups 的字段为 id、label、pages、fold、default_open；editor 可选 biomes、surface、features、water。未归属的参数页自动生成独立节。重复归属和无效控制参数在加载时报错；共享原生参数组只由 shared_group 决定。

参数可声明 `enabled_param` 布尔开关。`ui_rows` 声明 label、keys 和可选 components（每个分量的中英文标签），保留原标量参数键与有效值。世界范围、预览、内容编辑、输出操作沿用原有工具。包无需添加 UI 专用分支。

`api.catalog()` 逐包返回 id、name、status、error，坏包不会阻断健康包。`api.pack()` 仍严格报错。`api.describe()` 包括群系绑定、生成器、处理器、参数 UI 元数据、启停条件与能力说明，主流程仍为 `spec → generate → prepare → place`。0.42.0补充最终`height_field`、参数`tooltip/advanced`及处理器`sky_only`，旧键保留；元数据是继承后的定义和默认值，当前Spec解析值仍用`api.pack(spec.pack).resolve(spec)`查询。

加载缓存为 32 条 LRU。Pack 持有私有源码快照，会话内保留已加载版本；旧版本的相对延迟导入读取捕获的源码。进程任务传递请求描述与字段库切片，工作进程验证指纹后就地构建三维实体，不再回传二维参考数组。

可选 `biome_selector: "module:function"` 接收参考 Context，可以返回与 ctx.shape 同形的有效整数群系索引数组、一个已声明的群系ID字符串，或`None`。字符串按ID查找后填满当前区域；`None`及省略回调时都调用正常多维气候选择器。原数组回调保持兼容。主世界的`climate.single_biome`通过这一入口选择群系，地形、冰雪与材料仍由内容配方负责。高度图入口见[高度图](HEIGHTMAP.md)。

## vanilla 水下岸坡（0.41.1）

`height_before_rivers`的16格邻域提供一次八邻域岸线距离查询，供原岸带扰动及水下深度上限复用。盆地、起伏和沉积仍基于原水深；仅原有且扰动后仍湿的列在完整塑形后限制深度，新淹没原干列不二次塑形。第一湿列最多1格深，16格处已允许全部可用水深，远处海床保持。`seabed.coast_drop`键、默认6及保存值保持，语义改为沿连续岸坡分配的允许下潜幅度，越大允许下降越快，不再单独挖沟；没有新增控制项。关闭水体生成、平坦模式或关闭`seabed.shaping`沿用原路径，关闭岛屿仍修复大陆岸坡。API、格式2与规划参数依赖保持，源码指纹负责失效。细节及证据见水下岸坡（见 Git 历史）。

## vanilla 普通海岛（0.41.0）

vanilla增加`islands.enabled/coverage/scale/height`，默认true／0.25／256／24；coverage表示宏观出现强度而非面积配额。`island_weight`为0..1的原海域抬升权重，`height_islands`是低地之后、恶地及海床之前的高度；均通过既有`api.fields`或`keep_fields`查询。世界对齐8格岛形、16格出现区域与现有massif组成二维配方，原有干陆地抬升为零。水系粗规划与最终地形使用同一配方；沉积查询读取新海岸。关闭岛屿、强度／高度为0或平坦模式跳过岛屿噪声，关闭水体仍保留岛屿高度。普通岛上沿用现有群系、植被和表面处理，未增加核心接口、群系类型、模板或格式版本。详见取景及验证（见 Git 历史）。

## vanilla 森林扩展示例

0.31.0 的 `forest`、`birch_forest` 和 `taiga` 是内容包扩展的正式实例。三份群系 JSON 复用草原表面规则，在自己的 `features` 绑定中设置橡树／白桦／云杉密度；树型定义无需改动。包内 `terrain.py` 声明世界对齐的 `forest_region` 字段，`pack.json` 声明气候选择维度、群系顺序、五个参数及森林折叠分组。植被节使用 `shared_group: true`，让森林参数的原生 EditCondition 能读取既有 `trees.enabled`。核心和通用 UI 没有原版森林分支。

```python
from mods.WorldGenerator import api
spec = api.spec('vanilla', seed=42, region=(-256,-512,512,512), params={
    'caves.enabled': False, 'forest.region_scale': 512,
    'forest.mixed_oak_density': .60, 'forest.mixed_birch_density': .20,
    'forest.birch_density': .75, 'forest.spruce_density': .70,
})
world = api.generate(spec)
job = api.prepare(spec, name='Forests', backend='pcg')  # UE 主线程
# 等待 completed 后，在自己选择的场景调用 api.place(job.result)。
```

布局条件、边界优先级和旧参数语义见 森林说明（见 Git 历史）。这个区域同时包含三类森林，但它不是三维观感或 GPU 性能验收的替代品。

## vanilla 积雪与内陆冰面

0.32.0 新增 `snowy_taiga`，条件为 `snow_cover >= .5`、湿度和 `forest_region` 非负，位于水体之后、雪地兜底之前。雪林使用既有云杉生成器和森林密度；两种雪地保留草地／泥土基底、陡坡及岸边规则。暖区气候阈值不变。

包声明 `cold_surfaces:apply`，以一次批量处理返回雪层新增和冰面替换。半径为 0，依赖现有真实表面、露天与占据查询；没有通用 UI 或核心里的冷区分支。0.42.1起雪层使用原版snow_height2～14及第8层snow_block，单位缩放、零偏移，只水平合并；冰使用普通ice方块，不改变水位或湿域。

“气候与群系 → 积雪与冻结”包含 `cold.enabled`（默认开）、`cold.snow_layers`（0–8，默认1）、`cold.canopy`（默认开）、`cold.freeze`（默认开）。内部参数页为 `cold_surfaces`，避免与技术样例的 `cold` 页面重名。关闭总开关跳过处理器；层数为 0 只关闭覆雪。`cold.freeze` 只冻结露天河湖塘的已输出水面，地下水不冻结，冰面不叠雪。0.34.0 的海面浮冰由同一处理器及独立冻洋参数控制。

```python
from mods.WorldGenerator import api
spec = api.spec(seed=42, region=(-256, -512, 512, 512), params={
    'caves.enabled': False, 'climate.temperature_offset': -1.5,
    'cold.enabled': True, 'cold.snow_layers': 1,
    'cold.canopy': True, 'cold.freeze': True,
})
world = api.generate(spec)
job = api.prepare(spec, name='ColdWorld', backend='pcg')  # UE 主线程
# 等待 completed 后，在自己选择的场景调用 api.place(job.result)。
```

关闭处理器保留的是新版配方的处理前输出，并不恢复旧版的整块雪地基底或旧群系列表。参数有效值与格式 2 保持；用法、性能和验收边界见 积雪与冰面（见 Git 历史）。

## vanilla 冰刺之地

0.33.0 增加 `ice_spikes`，顺序为水体 → `snowy_taiga` → `ice_spikes` → `snowy_plains`。包内世界对齐字段 `ice_region` 使用独立盐、16 格采样和两层噪声；群系条件为 `snow_cover >= .5` 与 `ice_region >= .25`，地表沿用普通雪地，只有 `ice_spike` 景观绑定。

`ice_spikes:build` 返回实心渐尖的浮冰单元，普通高度为基础高度 ±2，高刺为三倍 ±4。景观声明完整底部支撑、12 格候选间距、优先级 20、有限边界和 1,536 单元预算。支撑、水下、冲突和上界拒绝由既有核心完成。`packed_ice` 为可 XYZ 合并的完整实体，包内覆雪处理器排除其顶面；雪地不生成浮冰斑块。

“气候与群系 → 冰刺之地”包含总开关、区域尺度、密度、基础高度和高刺概率，高级项为斑块尺度与坡度。关闭冰刺总开关时字段返回 −1，群系回到普通雪地；`cold.enabled` 仍只影响覆雪与冻结。用法、完整参数范围、缓存检查及验收边界见 冰刺说明（见 Git 历史）。实现只涉及 vanilla 内容，公共 API、格式、核心与通用 UI 不变。

## vanilla 冻洋与冰山

0.34.0 增加 `frozen_ocean`，顺序为湖泊／水塘／河流 → 冻洋 → 普通海洋 → 既有陆地。`frozen_ocean_mask` 复用已有寒地判定及总开关，海床和水草绑定沿用海洋。`ocean_ice_patch` 使用独立盐、16 格采样和两层噪声，在已有冷区表面遍历中替换部分露天海面；覆盖率 0／1 对应不冻结／全部合格水面冻结，不改变湿域和水位。

`icebergs:build` 使用 `water_surface`、48 格候选间距、完整水面支撑、有限边界及 32,768 单元预算。旋转椭圆、偏移峰脊、大小变体和 2–6 格有限水下冰体均来自候选形状键；主体是 `packed_ice`，默认 30% 候选的上部局部替换成 1–3 格完整 `snow_block`，不增加高度。两种完整材料均可 XYZ 合并，薄雪处理器排除它们。

参数由“水面 → 冻洋”元数据声明。关闭总开关回到普通海洋；关闭海面冻结保留冰山，密度 0 保留浮冰；关闭 `cold.enabled` 停止表面冻结和覆雪，保留冰山及结构雪帽。旧包显式群系列表不追加，API 主流程及格式 2 保持。完整参数、调用示例与测量见 冻洋说明（见 Git 历史）。通用核心只增加水面锚点、支撑与水面替代规则，没有冻洋 ID 或冰山方块名分支；测试中的独立包使用自己的水面和实体名称验证契约。

## 稀疏地形材料（0.38.0）

可选声明如下；缺省继承，显式null禁用。旧包未声明时不增加材料查询。

```json
"terrain_materials": {
  "sampler": "recipe:sample", "inputs": ["stone"], "blocks": ["andesite"],
  "fields": ["band_offset"], "enabled_param": "paint.enabled"
}
```

`fn(ctx)`返回与ctx.materials等长的一维整数包材料ID，只能保留原材料或使用声明输出。输入／输出须完整遮挡立方体；核心校验材料、字段、查询范围和取消，不允许改变坐标、占据或预算。

上下文提供pack、params、seed、世界x/y/z、materials、biomes、block_index、column_index。ctx.fields是声明参考字段的只读映射，数组按参考区域展平；`ctx.fields[name][ctx.column_index]`读取单元所在水平列，不重复计算体积噪声。fields可省略，启用参数必须是布尔。

高度快路径和完整／局部洞穴外壳共用入口，在加入流体和景观前执行；参考顶面调用同一函数。原shell_materials仍仅处理洞穴切面，两者共用校验。无输入材料时跳过字段求值；没有新体积查询或长期缓存。api.describe提供声明与能力，vanilla实例见 恶地（见 Git 历史）。

恶地高度涉及基础气候，因此相关气候键现在影响物理规划，色带厚度和climate.boundary_detail仍不影响高度／水系缓存键。grid_sample源网格复用阶段内粗网格，采样输出保持，不新增长期缓存。

0.38.1恶地改用两层宏观温湿度的较小暖干分数，字段名和接口保持，默认区域尺度768格；不再乘细气候与独立区域掩码。vanilla包内_climate_noise在当前Context中按随机盐、尺度及层数复用结果，Context的坐标、种子和参数固定；跨Context不共享这些缓存项。关闭内容应在专用字段求值前退出；空区域可以跳过形状，但确定区域的必要计算及更广范围水系规划仍存在，不能以群系面积推断全部开销。

## 两个技术验收夹具

`minimal_world` 不继承 vanilla：双色地形和石柱，独立参数页，没有水／树／洞穴参数。`cold_extension_demo` 继承 vanilla：两个群系使用不同云杉密度、少量冰刺、地面和树冠的简化覆盖、露天显示水面替换。其条带群系选择器与起伏高度场仅为接口演示，不改变 vanilla 布局。覆盖避开物理湿域内的地面；冻结不修改湿域、水位或地下水连通性。夹具继续验证接口；正式森林、积雪与冰面已获用户确认，正式冰刺由 vanilla 提供，场景观感待用户验收。

森林观感确认后，这两个包已从公开 `packs/` 转到 `tests/packs/`。测试引导显式注册夹具目录，常规面板不注册它们；原有独立包、覆盖、冻结、湿域和分块契约测试保留在 `tests/test_extension_packs.py`。日常验证用 `python -B tools/test.py related --test test_extension_packs --json`。上面的 vanilla 森林例子是当前公开教程，两个旧样例的 UE 技术验收记录继续保留。

## 一次性迁移与恢复

面板及 PackDraft 启动调用 `migration.upgrade_workspace(SAVED_DIR, roots=pack_roots())`，也可离线显式调用。只升级活动用户包、草稿、会话、参数库和页偏好；保留 Saved 位置及历史目录。包先按继承依赖升级，再在隔离目录校验暂存版本，最后发布；原字节保存在 `Saved/migrations/<时间-随机ID>/`，files.json 记录恢复路径。失败恢复已发布原件并逐项报告；不能无损转换的包／会话保留原件。

格式 2 可重复执行，不重复迁移。旧景观分布转入相应群系，参数值、局部预设范围、未保存内容和会话状态保留。运行时只解析新景观结构；未升级／损坏包会明确报错。不要清空 Saved，也不要把迁移备份或用户内容加入 Git。
