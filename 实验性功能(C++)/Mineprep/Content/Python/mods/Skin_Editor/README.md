# MC 皮肤图片转换

`api.py` 在普通 Python 中使用 Pillow 处理图片，不需要 UE、面板或 ColorList。先在该 Python 环境安装 `Pillow`，把插件的 `Content/Python` 加入模块路径：

```python
import sys
sys.path.insert(0, 'E:/ue/Mineprep_5_8/Plugins/Mineprep/Content/Python')
from mods.Skin_Editor import api

slim = api.slim_arms('skin.png', 'skin_slim.png')
api.wide_arms('skin_slim.png', 'skin_wide.png')
api.keep_layer(slim, 'outer', 'skin_outer.png')
# 只转换左臂内层：
api.slim_arms('skin.png', 'left_inner.png', arm='left', layer='inner')
```

输入可以是文件路径或 Pillow Image；返回新的 RGBA Image，不修改输入对象。输出路径可省略，指定时写 PNG（已有文件会覆盖）。支持 64×64 及其整数倍方形皮肤，不支持旧版 64×32。左右按角色自身方向命名。宽转细会丢列，细转宽按原模组规则复制邻列补宽，并非无损逆变换；调用方须知道源布局，不能重复执行同一转换。

`arm` 可取 `both/right/left`，`layer` 可取 `both/inner/outer`。四块手臂区域的左上角如下，每块占 16×16 基础像素；实际面片宽度随宽臂/细臂布局变化。完整分层区域见 `LAYER_UV`，共用的手臂移位规则见 `arm_boxes()`。

| 手臂 | 内层 | 外层 |
|---|---|---|
| 右 | (40, 16) | (40, 32) |
| 左 | (32, 48) | (48, 48) |

`keep_layer` 只保留指定层的原 UV 区域，其余像素变透明，不搬移或合并层。转换直接复制 RGBA 像素，不插值、不做颜色空间转换。皮肤图片转换不会改变模型几何，使用细臂皮肤时还需选择匹配的模型。

## 与 UE 交换图片

在 **UE 编辑器 Python** 中导出纹理的源图片（不含材质渲染效果）：

```python
import unreal
task = unreal.AssetExportTask()
task.object = unreal.load_asset('/Game/Skins/MySkin')
task.filename = 'E:/Temp/skin.png'  # 父目录需已存在
task.exporter = unreal.TextureExporterPNG()
task.automated = True
task.prompt = False
task.replace_identical = True
assert unreal.Exporter.run_asset_export_task(task)
```

在外部 Python 中处理后，回到 UE 导入 PNG。下面创建或更新指定纹理资产，已有材质引用该资产时无需重新绑定；如果换了资产路径，需要自行更新材质引用。

```python
task = unreal.AssetImportTask()
task.filename = 'E:/Temp/skin_slim.png'
task.destination_path = '/Game/Skins'
task.destination_name = 'MySkinSlim'
task.automated = True
task.replace_existing = True
task.save = True
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
texture = task.get_objects()[0]
texture.set_editor_property('srgb', True)
texture.set_editor_property('filter', unreal.TextureFilter.TF_NEAREST)
texture.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_EDITOR_ICON)
assert unreal.EditorAssetLibrary.save_loaded_asset(texture)
```

这组设置适合带透明度的像素皮肤；导出需要纹理源数据，只有运行时 RT 的情况不在此示例范围内。原面板和画图功能保留，四个转换预设直接内嵌 UV 坐标，可独立复制运行，不导入 api.py；UE 内无需安装 Pillow。
