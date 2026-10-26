# 自定义高度图

“自定义”页同时提供独立的[植被分布与留空区域](MASKS.md)，不启用高度图也可使用。

支持 vanilla 及保留其高度链（`height_lowlands → height_custom → height_islands → height_badlands → height_before_rivers`）的派生包。声明格式见 [EXTENSIONS](EXTENSIONS.md)，缓存失效见 [CACHE](CACHE.md)。

## 用法

```python
from mods.WorldGenerator import api

spec = api.spec(region=(-256, -512, 512, 512))
spec = api.with_heightmap(spec, 'E:/maps/terrain.exr')            # 默认 faithful，EXR 原值即格数
spec = api.with_heightmap(spec, 'E:/maps/delta.png', mode='add', output_range=(-16, 16))
overview = api.overview(spec)   # 参考地图，无实体
world = api.generate(spec)      # 实际树草、洞穴、覆雪
spec = api.with_heightmap(spec, None)  # 移除
```

- **faithful**（直接使用）：映射值是绝对高度，只按海平面放水，跳过岛屿、恶地高度、海床和自动河湖塑形；群系、材料、植被和洞穴照常生成。
- **add**（叠加）：映射值作为增量加在 `height_custom` 之后，后续自然塑形继续生效；平坦模式以 `flat_height` 为基底。
- PNG8／16 归一化到 0～1，默认映射到 `world.y_min..world.y_max`；浮点 EXR 保留原值。可用 `input_range`／`output_range` 线性映射，范围外线性外推，最后按世界高度裁切。不做 sRGB 转换或按图片极值重新归一化。
- 彩色图只读 R 通道，忽略 G／B／Alpha。最多 16,777,216 像素；非有限值、损坏或缺失文件报错。
- 图片横向为 MC X，纵向为 MC Z，首行是覆盖区最小 Z；双线性、列中心采样，覆盖区外延伸边缘。覆盖区在绑定时固定为当时的 `spec.region`，之后裁切或扩大不会拉伸；要重新铺满新区，传 `region=` 或在面板点“使用当前世界范围”。
- `api.fields(spec, 'heightmap_value')` 查询映射后的高度或增量；`world.stats['heightmap']` 记录读取、解码、采样耗时。

## 面板与 UE 纹理

“自定义”页位于方块与输出之间。顶部选择“高度图”“植被分布”或“留空区域”，一次编辑一种图像；切换不会改变各自的启用状态。界面会记住上次选择。

高度图默认关闭；选择文件或有 Source 的 Texture2D 即启用，清除则禁用。输入范围、自动／手动输出范围在默认收起的“数值映射”中，展开状态也会记住。“查看图像”只预览映射结果，不生成地形。虚拟纹理、RenderTarget、无 Source 纹理会被拒绝。

脚本中使用 UE 资产：在主线程 `path = mineprep.export_tex_cache(texture)`，再 `api.with_heightmap(spec, path)`；这是文件快照，资产改动后需重新导出、重新绑定。公共导出函数见 [PUBLIC_TEXTURE_API](PUBLIC_TEXTURE_API.md)。

## 保存与分享

WorldSpec 格式 2 保存绝对路径、模式、覆盖区和映射范围，不含像素；图片内容摘要参与生成与规划身份。保存用户包或参数预设不复制图片，分享 Spec 需携带图片并重新绑定路径。已有 World／Overview 保留自己的输入快照，不读取最新文件。
