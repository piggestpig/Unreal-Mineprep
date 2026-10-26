# 植被分布与留空区域

在“自定义”页点击顶部的“植被分布”或“留空区域”，选择遮罩文件或有Source的Texture2D。一次只显示当前图像的设置，切换不改变其他图像的启用状态。三种图像分别启用，不必同时使用；主世界和下界都支持遮罩。

- **植被分布**：白色保持原有密度，黑色不生成，灰色降低密度。它不会在不适合的群系、地表或水深中强行种树，也不会提高原有密度。
- **留空区域**：白色不生成植物和零散景物，黑色保持原状；大于等于0.5视为留空。树冠或倒木跨入区域时整株／整件跳过，不会截断模型，也不按矩形包围盒扩大空地。

密度在植物锚点（通常是树根）采样，所以区外的树冠可能伸入黑色密度区。需要整片空地时用留空遮罩。两图同时启用时，先减少候选，再对完整景物做净空检查。

## 脚本

```python
from mods.WorldGenerator import api

spec = api.spec(region=(-128, -128, 256, 256))
spec = api.with_vegetation_mask(spec, 'E:/maps/vegetation.png')
spec = api.with_clearance_mask(spec, 'E:/maps/clearance.png')
world = api.generate(spec)
api.snapshot(world, 'E:/maps/result.png')

# 覆盖范围在绑定时固定；也可以显式指定
spec = api.with_clearance_mask(spec, 'E:/maps/yard.png', region=(0, 0, 32, 24))
spec = api.with_vegetation_mask(spec, None)  # 移除对应输入
```

PNG8／16按位深归一化，浮点EXR使用0～1原值，越界和非有限值会报错。彩色输入读取R通道，忽略G／B／Alpha；不做sRGB转换或按图片极值拉伸。可以用NumPy生成二维数组，再用OpenCV保存。UE纹理通过现有[纹理导出入口](PUBLIC_TEXTURE_API.md)冻结为文件，UObject不会传入生成线程。

图片列对应MC X、行对应MC Z，首行为最小Z，按格中心采样。植被图双线性采样，留空图最近邻采样；覆盖范围外不施加限制。改变输出尺寸不会拉伸已有遮罩，需要重新铺满时点击“使用当前世界范围”，或重新指定API的region。

WorldSpec保存图片绝对路径与覆盖范围，不嵌入像素。分享时同时带上图片并重新绑定路径；图片内容变更会使生成缓存失效，已有World保留自己的快照。UE纹理重导入后自动刷新来源，虚拟纹理和没有Source的纹理不支持。

## 作用范围

vanilla的植被包括树、草、花和水草；净空还排除石头与倒木。下界的植被包括菌树、菌类、根和藤蔓；净空还排除火、化石与萤石。地形、水面、冰山、冰刺、岩浆柱和手动compose的建筑不会改变。`api.scatter`仍按调用者显式给出的density／where工作，不自动删掉作者摆放的结构。

内容包按category声明参与类别，继承和自定义规则见[内容包规范](EXTENSIONS.md#分布遮罩)。未声明类别的自定义内容不会被猜测为植物。普通地形预览只显示参考地表；检查树草避让需要生成完整预览。

## 对照示例

运行[mask_workflow.py](../examples/mask_workflow.py)，用`--output`指定新目录，`--size 128`调试或`--size 256`查看更大范围。输出包含输入图、修改前后预览、配置、检查记录和PCG放置脚本。移动目录后放置脚本会重新绑定图片，不修改已有输出或关卡。
