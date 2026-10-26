# Python内容包入门（0.47.0）

先读[README](../README.md)的最小生成、用户目录注册和UE完成回调。本页帮助第一次制作内容包，声明细节按需查[EXTENSIONS](EXTENSIONS.md)。

## 先确定作品需要什么

| 需求 | 现有入口 | 注意 |
| --- | --- | --- |
| 改起伏、气候或现有植被密度 | api.spec(params=...)、spec.with_params、预设或包的params默认值 | 查api.describe的真实参数键与范围；预设／显式参数会覆盖默认值 |
| 新地形或空间位置控制 | vanilla派生包覆盖height_custom；独立包自行组织@field或整区@region_pass字段链 | 绝对高度，粗规划和最终地形共用；后续塑形仍生效 |
| 灰度文件控制高度 | api.with_heightmap(spec,path,mode='faithful'或'add') | vanilla及保留高度链的派生包；固定覆盖区、双线性采样、内容摘要失效 |
| 用图片控制植物疏密／留出空地 | api.with_vegetation_mask／with_clearance_mask | 主世界、下界及声明mask_categories的内容包；见[MASKS](MASKS.md) |
| 新群系／地表 | biomes/*.json、pack.json.biomes | 气候盒与顺序影响匹配，表面规则需要兜底 |
| 新单格植物 | surface_scatter及群系features绑定 | 复用现有二维散布，不恢复组块或逐株对象 |
| 新树形／小景观 | tree_template→TemplateBatch；其他形状仍可用FeatureBatch | 核心负责支撑、碰撞与裁切；助手仅支持原生树木模型 |
| 新材料资源 | blocks.json的builtin／json／mesh来源 | color只改变预览图；实际颜色由UE模型／材质／贴图决定 |
| 方块发光／照明强度 | blocks.json的material.emission／lighting；prepare的block_materials | 独立非负有限值，0有效、允许HDR；全部材质槽覆盖，使用隔离变体，详见[R39](OUTPUT.md) |
| 群系草／树叶颜色 | 群系JSON的vegetation_tint；面板原生颜色倍率控件 | 线性RGB倍率，缺省[1,1,1]；支持HDR，地图color另有用途 |
| 覆盖层／冻结 | surface_processors | 真实向上表面，sky_only声明决定是否只要露天输入 |
| 悬空岛与虚空 | 独立volume密度包，参见[end](END.md) | reference_mask_field区分参考地表与虚空；小型表面补丁可显式声明volume:true |

高度图使用正式文件输入：[R21](HEIGHTMAP.md)。PNG按整数位深归一化，浮点EXR默认保存格数；范围映射可以表达缩放、偏移及负增量。默认忠实模式不再自然塑形；add保留作者height_custom并在其后叠加。输入不是pack.json参数，也不随保存包复制文件；分享Spec需要携带图片。自定义字段自行读取其他外部文件仍没有自动依赖跟踪，应避免绕过这个入口。笔刷、群系图和方块区域删填尚未提供。

## 文件与继承

参数类型支持`float`、`int`、`bool`、`curve`和`str`。主世界的`climate.single_biome`为空字符串时使用混合群系，填写群系ID时固定群系选择；整套群系预设还会配置起伏、水体和冰雪，因此通常直接选用预设。

包可在`pack.json`声明`"preset_menu": ["my_preset", "other_preset"]`，按给定顺序显示全局快捷预设；ID须唯一且指向已存在的整套预设。空列表隐藏所有资源包快捷项，未声明（不自动继承父包此设置）则显示原有全部条目；用户预设仍可显示，预设库及API仍能访问未列出的预设。该字段只影响界面，不进入几何身份。`default_preset: ""`表示新请求直接采用参数默认值。

先用`folder = api.create_pack('my_world', extends='vanilla', name='My world')`创建最小派生包。默认写Saved/packs，可指定`root`；返回绝对Path并注册当前解释器。已有目录／已注册ID会拒绝，加载验证失败不发布包，不启动工作区迁移。只创建pack.json、空landscape.py、短README，默认输出继承父包；按需要添加以下文件：

```text
Saved/packs/my_world/
  pack.json            # ID、继承、模块、参数及群系顺序
  landscape.py         # 需要Python配方时加入modules
  biomes/my_biome.json  # 需要新群系时添加
  features.json        # 需要新景观定义时添加
  blocks.json          # 需要新材料／模型来源时添加
```

这些文件按实际需要创建，不要求复制整套vanilla。create_pack已经把landscape加入modules；写辅助模块时再按声明需要加入。内置savanna／金合欢可直接使用，无需另建热带草原包；以下流程用于自己的新内容。

`api.register_pack_root(root)`只增加搜索路径，不创建包。重新打开纯API解释器后要重新注册；请求会把根目录传给工作进程。`api.edit()`返回PackDraft，可以编辑规则并save到用户工作区，但初始化会执行工作区升级检查，不是只读查询。

参数定义按键合并，新参数须声明类型、默认值及必要范围。群系按ID整份覆盖；省略pack.json.biomes时保留基包的既有顺序，新增文件不会自动进入该顺序。新增群系时，用 `api.describe('vanilla')['biomes']` 查看顺序，把完整目标列表写入子包；不要假定新文件会自动优先于沙漠。features定义按ID继承覆盖，实际分布写在群系features绑定中。

先保留默认的保守缓存失效。planning_params不从父包继承，只有梳理完整间接依赖后才显式声明；不能为提速照抄父包参数清单。声明、源码生命周期及依赖规则见[缓存契约](CACHE.md)。

例如生成待写入`pack.json.biomes`的显式顺序，加载器语义保持：

```python
order = api.biome_order('vanilla', insert='my_biome', before='grassland')
print(order)  # 写入完整列表，并另建biomes/my_biome.json
```

insert也支持多个新ID，保持传入顺序；插入时before／after二选一，锚点必须存在。已有ID不能重复插入；调整已有顺序仍由作者编辑完整列表。工具不会检查未创建的文件或写入manifest。describe的inactive_biomes与check配置warning指出当前包本地文件未启用，区别于已启用群系在本区占比为零。

最小可运行示例，先按README设置Python 3.11、NumPy和导入路径；绘图另需cv2：

```python
import json
from mods.WorldGenerator import api

folder = api.create_pack('my_meadow')  # 已有目录会拒绝，请用自己的新ID
(folder / 'biomes').mkdir()
biome = {'id': 'my_meadow', 'name': {'zh': '我的草甸', 'en': 'My meadow'},
         'climate': [{'water_kind': [0, 0]}],
         'surface': [{'top': 'grass_block', 'under': 'dirt', 'deep': 'stone'}]}
(folder / 'biomes/my_meadow.json').write_text(json.dumps(biome), encoding='utf8')
meta = json.loads((folder / 'pack.json').read_text(encoding='utf8'))
meta['biomes'] = api.biome_order(insert='my_meadow', before='lake')
(folder / 'pack.json').write_text(json.dumps(meta), encoding='utf8')
spec = api.spec('my_meadow', region=(-19, -23, 32, 32),
                params={'terrain.flat': True, 'water.generate': False})
data = api.overview(spec)
print(api.check(data, expect_biomes='my_meadow'))
print(api.locate(data, biome='my_meadow'))
world = api.generate(spec)  # 只在需要实体／实际景观时生成
print(api.check(world))
```

示例故意把干地规则放在最前面以保证小区域可观察；正式混合群系需按作品的气候条件选择顺序，避免抢占现有陆地。这里只加地表，群系未声明features便不会继承别的群系的树草绑定；新增树形／景观需添加features.json并在该群系中绑定。只用已有方块无需blocks.json。

群系climate是闭区间；surface／locate上限排除。api.describe的blocks为名称列表、block_defs为定义映射；api.pack().blocks则是名称元组。报告和测量脚本放在包目录外，包内Python／JSON参与源码指纹。

## 复用地图检查与取景

0.45.0支持`"vegetation_tint": [1.3, 0.9, 0.62]`，由BCT传入用户材质，与原贴图相乘。`[1,1,1]`不变、`[0.8,0.8,0.8]`变暗；三个值非负、有限且≤65504。省略保持原颜色；子包整份群系覆盖、草稿恢复及保存沿用既有规则，颜色文件变化仍使完整生成指纹失效。

群系color仍为地图标识，方块color仍用于诊断图。`api.write_biome_texture(data, path_to_exr, cell_size=4)`只读World／Overview自身快照，不重载文件。固定格级混合再降采样；边缘复制本区颜色，单独生成相邻区域的最外圈不承诺相同混合输入。

可用vegetation_tints={'savanna': [1.8, 0.8, 0.35]}覆盖write_biome_texture或prepare的输出色板，遗漏ID使用快照倍率；未知ID和非法RGB报错，输入会冻结，不改包或World。面板内部仅调色时保留生成版本及预览，准备只换BCT；公开draft.spec仍包含全部当前修改，保存包仍写vegetation_tint，普通文件指纹规则保持。

```python
spec = api.spec('my_world', region=(-256, -512, 128, 128))
data = api.overview(spec, keep_fields='humidity')
print(api.check(data, expect_biomes='grassland'))
spot = api.locate(data, biome='grassland', where={'height': {'min': 34, 'max': 60}},
                  origin=(-192, -448))
print(spot)
```

只调用一次overview，两次查询只读复用。群系名先查describe；换独立包时不要沿用vanilla的ID。报告scope=reference时没有计算实际树草／冰体／覆雪，景观状态not_sampled不表示生成失败。需要实际分布时`world = api.generate(spec)`，再`api.check(world, expect_features=('my_tree',))`；也可直接check(spec, full=True)，但已有World不应重复生成。列景观以cells判断实际输出，instances=0正常。

报告保留零占比与四种景观状态：not_sampled、disabled、not_observed、present。disabled指启用条件不满足、密度零或无有效绑定；不猜测碰撞原因。显式expect目标缺失只写warnings，未知ID写errors；ok表示检查完成且无errors，不承诺作品符合所有视觉预期。本区没有观察到不能推断全球不可达。

locate返回最近匹配参考列，不搜索真实树木／结构、不计算洞后支撑。条件写成`{'字段': {'min': 数值, 'max': 数值}}`，可只写一端，min包含／max排除；通用height读最终参考高度，其他名称需包声明且已保留。Spec输入自动保留查询字段；已有结果缺字段明确报错，不偷偷重采样。None仅表示当前区域没找到，可显式扩大Spec.region后再生成概览，仍须落在已配置的水系规划范围。

## Python形状与地形

包模块使用 `.helper` 导入本包、`..vanilla.helper` 导入已声明继承链中的模块、`...core.fields`等导入核心。不要硬编码公开packs路径去绕过私有源码快照。形状生成器不得访问UE、改输入或自行循环查询地形；复用ctx.reference的只读高度、湿域、水位和材料。

多方块输出用 `FeatureBatch(offsets,types,owners,rotations=None)`；整模型用 `TemplateDefinition(id,offsets,types,boxes,bake_cells)`与 `TemplateBatch(templates,template_ids,owners,rotations)`。偏移为局部整数MC XYZ，types为包方块ID，owners指输入anchors；模板检查盒为半开范围，四向旋转为0–3。完整边界及示例见[模板契约](EXTENSIONS.md#整模型模板0390)。

**热带草原的正常暖区应无雪，不要求给草原树制作覆雪变体。** 若作品要求全域无雪，可在自身配置中明确关闭cold.enabled；不要为一个暖区包删除通用覆雪能力。自定义树的寒地复用是另一个场景：需要时用独立小寒地配置检查模板覆雪，不纳入草原主场景。当前整树内部固定，覆雪几何应由生成器选择另一模板，不能期待表面处理器直接改树内部。

### 斜树干：默认无雪

在自身模块中构造局部整数MC XYZ，不调用vanilla私有函数：

```python
import numpy as np
from ...core.templates import tree_template, TemplateBatch

def trees(ctx, anchors, keys):
    tree = tree_template('slanted_tree',
        [[0, 0, 0], [0, 1, 0], [1, 2, 0], [1, 3, 0]],
        [[1, 4, 0], [0, 4, 0], [2, 4, 0], [1, 4, 1], [1, 4, -1]],
        trunk_block='oak_log', foliage_block='oak_leaves',
        block_ids=ctx.block_ids, block_defs=ctx.block_defs)
    n = len(anchors)
    return TemplateBatch((tree,), np.zeros(n, np.int32),
        np.arange(n, dtype=np.int32),
        ((keys >> np.uint64(8)) % np.uint64(4)).astype(np.uint8))
```

`features.json`可声明下例；群系另绑定`slanted_tree`的surface、density、patch_scale、max_slope及trees.enabled。仅定义生成器不产生候选。

```json
{
  "slanted_tree": {
    "type": "multi_block", "generator": "landscape:trees",
    "blocks": ["oak_log", "oak_leaves"],
    "bounds": [[-3, 0, -3], [4, 6, 4]], "max_blocks": 9,
    "cell_size": 12, "category": "trees"
  }
}
```

助手稳定去重，交叠单元树干优先，自动生成材料、烘焙记录、树干与分层树冠检查盒；四向旋转由TemplateBatch选择，不增加烘焙变体。木／叶须为无偏移、单位缩放的builtin cube；JSON、mesh或变换模型明确报错，需自行使用FeatureBatch。

默认`snow_layer=0`，不会读取cold参数或气候，也不查询雪材料。需要覆雪变体时只传`snow_layer=2`等整数1–8，每层1/8格；拒绝布尔值、小数和越界值。助手按约定读取逻辑材料`snow_layer_N`，校验其builtin模型：1–7层为`snow_height{2*N}`，8层为`snow_block`。模型名里的高度以1/16格为单位，所以两层对应`snow_height4`，不是`snow_height2`。不需要第二个材料或厚度参数。

雪层须声明shape=cube、occludes=false，单位缩放、零偏移；vanilla及派生包已具备八种定义，独立包只需声明所用雪层。例如两层：

```json
{
  "snow_layer_2": {
    "source": {"builtin": "snow_height4"},
    "shape": "cube", "occludes": false, "merge": "xz"
  }
}
```

在景观blocks、边界和max_blocks中计入雪；仅最高单元为树叶的列加一个雪单元。烘焙记录仍使用原生snow的layers属性。地面及整树统一解析相同薄雪模型，不额外缩放或下移。包自行选择裸树／雪树，不自动给暖区树覆雪；UI的cold.snow_layers保留，vanilla将选定层数传给助手。

### 局部高原：在水系前修饰高度

vanilla及派生包的链为“低地 → height_custom → 岛屿 → 恶地 → 海床 → 水系”。`height_custom`默认直接返回height_lowlands，返回的是修饰后的绝对高度，不是增量。将下例加入pack.json.modules声明的模块即可覆盖：

```python
import numpy as np
from ...core.fields import field

@field('height_custom', deps=('height_lowlands',))
def plateau(ctx, baseline):
    if ctx.param('terrain.flat'):
        return baseline
    # 世界坐标权重：中心(-32,-32)，半径128格，最高抬升12格。
    weight = np.clip(1 - ((ctx.x + 32)**2 + (ctx.z + 32)**2) / 128**2, 0, 1)**2
    return baseline + 12 * weight
```

粗水系规划预置原低地DEM后经过同一字段；最终地形也经过它，关闭水体时仍保留修饰。返回遵守字段广播规则，进入岛屿／后续地形前拒绝NaN、Inf。平坦模式接入层采用原低地高度，配方也应提前短路以避免无效采样；依赖会先求值，因此不要把昂贵噪声写成平坦时仍执行的上游依赖。

不要依赖最终height、由最终高度派生的biome_ids或水系资源反向塑形；声明的字段循环由图校验拒绝，水系资源也不能递归请求自身。后续岛屿、恶地、海床和水系仍可修改结果，不能承诺高原的每格最终高度不变。需要大半径平滑、距离场等整区非局部处理时，可用 `@region_pass(name, deps=..., margin=..., region=..., outside=...)`（见 [EXTENSIONS](EXTENSIONS.md)）。独立包自行组织字段链，不要求使用该名字；没有任意阶段插件框架。可查询`height_lowlands/height_custom/height_islands/height`观察各步。

## 看见结果再调整

1. 注册根目录，用api.catalog与api.spec定位包结构、参数和字段错误。
2. 从128²左右的串行完整生成开始，用api.snapshot或adapters.preview.write_views输出图。Overview仅检查参考地形／群系，不能证明树草、洞口或覆雪正确。
3. 看world.biome_fractions、stats.feature_counts／feature_categories、stats.column_features、soft_plants与output_model_types。这是当前区域的结果；占比零可能源于气候、顺序、裁切或随机分布，不能直接判定全球不可达。列景观没有逐对象实例，不能用实例数零判失败。
4. 记录参数与seed／region，改包后重新构建请求。保持世界坐标键、有限邻域和批量求值；不要为预览图好看单独修改颜色来代替实际材质验收。
5. 只有需要输出到UE时才走README的prepare→完成回调→place。离线World、Overview和PreparedWorld用途不同，不能互相替代；生成、资源准备与实际画面分别验收。

首个包完成后，先通过小范围生成和预览确认结果，再逐步增加内容。[源码示例](../examples/README.md)可作为起点。
