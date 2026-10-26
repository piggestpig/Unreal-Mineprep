# 三维密度接口

## 有界物理占据查询（0.53.0）

`core.volume_query.VolumeQuery(pack, params, seed, resources, field=None)`要求volume配方。`occupied(integer_xyz[N,3])`返回只读布尔[N]；`profiles(integer_xz[N,2], lower, upper)`返回只读布尔[upper-lower,N]。高度跨度最多4096，候选按128列分批，使用物理密度、不应用world.y_min/y_max。`air_runs(column)`返回半开空气区间；调用方排除物理边界外部空气并选择真实洞底／洞顶。无整区体积缓存，取消在分批前检查。

field缺省为最终密度，装饰会避开岩柱；岩柱规划显式读取nether_base防止递归。选址回调与普通方块批次见[扩展接口](EXTENSIONS.md#体积景观选址0530)，代码和512²测量见R32（见 Git 历史）。

## 自然表层深度（0.52.0，可选）

`shell_materials.surface_depth`为0—4的整数，默认0。非零时在现有slab两端仅扩展必要Y halo；材料上下文追加只读`floor_depth`／`ceiling_depth`数组，分别表示向上／向下遇到原始密度空气前的实体层数：邻接空气为0，找不到时为声明上限。输出裁切先后不改变这些深度，仍只给真实暴露的壳层着色。包须排除物理世界外部空气；nether按独立floor/roof过滤，裁切封口不成为新地表。共享接口不保存三维体积，也不改变实体占据。

`surface_depth_enabled_param`可引用布尔参数，关闭时连扩展采样一起跳过。未启用时两个数组为None，旧sampler和其他包保持原路径。nether声明采样上限4，实际覆盖厚度由`soul.surface_depth`（1—4，默认3）决定；稀疏岩柱独立并入最终占据，原始`nether_base`用于规划，避免递归。见R31（见 Git 历史）。

## 格点共享与参考阶段

格点块在同一进程的同一次生成内共享（`density.task_scope(key)`），不跨生成保留；重复 XZ 平面和相同窗口在一次生成内只插值一次。上下文复用插值索引和权重，非格点仍按原 float64 运算顺序计算。格点按世界对齐，节点值与求值分组无关。

生成先在工作域上建二维字段库（见 [CACHE](CACHE.md)），再处理实体；最终植物仍检查真实支撑。`api.generate(...,on_stage=callback)` 在字段库完成后提前通知参考地表，最终返回值仍为 World。参考 World 的 stats.reference=True，arrays 为空，不能当作完整世界。

正密度为实体，零或负为空气；不是材料或真实距离。布局资源→密度→占据与六邻接外壳→材料/合并→既有稀疏纹理输出。主世界和未来下界共享核心，使用独立配方。

## 声明与插值

```python
import numpy as np
from ...core.density import density

@density("shape", res=(4, 8, 4))
def shape(ctx):
    return ctx.noise("custom/shape", (32, 14, 32), octaves=2)

@density("solid", deps=("shape",))
def solid(ctx, shape):
    return np.minimum(ctx.base_density, .18-shape).astype(np.float32)
```

返回有限 float 数组、布局 [Z,Y,X]，验证后以只读 float32 使用。ctx 提供世界单元原点 x/y/z、params、seed、noise、warp、base_density、resource 与 get。噪声默认采单元中心。函数参数为 ctx 加按声明顺序的依赖。

res 可为1/2/4/8/16/32或 XYZ 三元组，例如(4,8,4)。节点在世界对齐格点上先求完整表达式，再插值到请求坐标。若把 abs/min/max 放进粗节点，是先组合再插值；若仅输入节点粗采样，末端 res=1 组合，是先插值再组合。二者不等价，原版 noodle 使用后一种结构。缓存不会调整插值位置。

axes 默认为 "xyz"，可声明 "xz"、单轴或 ""（常量）。只在声明轴上求值，其他轴广播，不猜测任意 Python 函数。依赖轴必须包含在当前节点声明中，否则载包失败；字段作者必须准确声明轴。axes 降维与 res 是独立决定。

## Pack

```json
{"modules":["terrain","recipe"],
 "density":{"field":"solid","base":"height","enabled_param":"caves.enabled","bounds":"recipe:bounds"}}
```

base 为 height 或 volume。height 的可选 enabled_param 必须为布尔参数，关闭直接使用高度列；bounds 回调签名 (pack,params,seed,region,resources)，返回完整整数半开 XYZ 盒元组，None/未声明走完整三维，空元组表示与高度基底相同。volume 无门控和局部 bounds，实体上下高度应来自独立几何参数。子包 density:null 清入口，显式配方替换继承入口。geometry/geometry_bounds 已删除，旧包直接拒绝。

density 与二维 field 分开注册，可同名。材料与流体独立于密度。World.heights/api.fields 仍是参考地表。api.section(field="solid"|"density") 和 api.projection 沿用只读坐标契约。

## 采样与诊断

- 32³ 核心、三轴一格邻域，世界直接采样邻格，裁切外为空气，内部块无额外外壳。无局部 bounds 时128²×32流式采样；volume始终完整覆盖。
- 节点按规范32格块单归属；键含种子、参数、包指纹、节点名/轴/分辨率及密度版本。相邻缺失节点批量求值，批次不得比缺失体积多25%，随后拆回规范块；不保留全世界体素。
- 主体连续洞网在4×8×4节点上组合；细通道输入各自粗采样后在体素处组合。XZ字段跨高度共享。生成/剖面/植物支撑共用密度中的湿列与顶底保护，没有末端回填。
- 不以未解析细字段的八角符号推断整个块为空或实体。bounds 必须保守，未知时完整处理。
- stats 包含布局、geometry_sampling/culling/materials、density_noise/density_interpolation、projection、density_samples、请求样本、工作数组估计与输出数；计时可能嵌套，不能求和得到总时间。
- 工作数组字节不代表完整临时峰值、RSS或GPU/FPS。投影在已有核心占据上汇总，每轴≤512像素，不额外采三维场。

volume_fixture 是源码测试使用的多层实体/空气夹具，位于 tests/packs，不随模组分发。当前普通洞穴顶棚8格、底面4格，入口附近和露天峡谷有受控例外。vanilla洞穴默认关闭，显式开启后使用自然配方；volume基底仍独立运行。声明方式见[扩展参考](EXTENSIONS.md)。
