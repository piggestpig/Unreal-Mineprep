# 示例

这里保存生成程序和它们使用的小内容包。运行后才会生成高度图、模型和预览图片，安装包不附带这些输出。

群系分布图的最小对照见[biome_map_workflow.py](biome_map_workflow.py)，生成透明PNG、带色差PNG、容差32／0对照预览和WorldSpec；运行方式见[群系图](../docs/BIOME_MAP.md)。

[biome_paint_workflow.py](biome_paint_workflow.py)使用真实分类画布绘制森林／沙漠并擦出自动选择区域，检查撤销重做后输出相同，生成PNG／色板及同地形前后预览。引擎内分类RT的可选检查见[paint_rt_check.py](paint_rt_check.py)。

## 山谷驿站

河道穿过树林，石拱桥连接两岸。桥头是带门廊的木石驿站，旁边有柴棚、货物和歇脚的平台，背后是山脊。

- [valley_outpost.py](valley_outpost.py)：河湾、树林、石桥与木石屋舍。
- [valley_outpost_gemini.py](valley_outpost_gemini.py)：群山环绕的版本，增加屋顶窗、屋檐细节、凉亭和灯柱。

在 WorldGenerator 目录使用 UE 自带的 Python 运行，将引擎路径和输出位置换成自己的：

```powershell
& 'D:/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe' -B -X utf8 examples/valley_outpost.py --output 'E:/ue/Mineprep_5_8/Intermediate/MyValleyOutpost'
```

换成 `examples/valley_outpost_gemini.py` 即可运行另一个版本。默认256×256、种子42；`--size 128`生成较小的版本，`--seed`改变地形细节和植被。输出目录必须是新目录，两个版本使用不同目录。

输出包含地形配置、16位高度图、模型、摆放记录、小内容包、预览和放置脚本。整个输出文件夹可以一起移动，加载器会重新绑定高度图和内容包。

在 UE 输出日志中切换到 Python，运行输出中的脚本：

```python
import runpy
runpy.run_path(r'E:/ue/Mineprep_5_8/Intermediate/MyValleyOutpost/place_in_editor.py')
```

脚本先准备资源，完成后再通过 PCG 放置到独立命名的场景组，不保存关卡。在单独关卡查看，或先移除旧版生成组，避免地形重叠。

## 生成与调整

两个版本都用 NumPy 安排河床、山坡、道路与屋舍台地，再通过忠实高度图入口生成地形。自动河湖塑形关闭，水平水面保留在32格。建筑使用 Builder 搭建原生 MC 方块，冻结模型后重复使用，通过接地与地基接口组合到地形上。

修改地形和布局可查看各自内容包中的 layout.py、landscape.py；建筑在主脚本的 `inn()`、`woodshed()`、`rest_deck()`、`bridge()`、`cargo()` 中。模型也可使用 `api.Structure.load(...).edit()`继续修改。

`scene.png`查看整体，`buildings.png`查看建筑，`inn.png`、`bridge.png`查看细节，`inn_site.png`、`shed_site.png`查看屋舍与周围坡面的衔接。`checks.json`记录碰撞、接地、数量与耗时。图片采用离线平均色，实际贴图、透明部分和光照在 UE 中查看。

## 其他示例

[paint_rt_check.py](paint_rt_check.py)在UE中检查绘图RT的编译、数值误差、取消、历史与图层切换，并可分别测512／2048画布的CPU提交成本；执行方法写在文件开头。不生成地形或改动关卡，验证性读回不用于日常绘图。

植被与空地对照使用[mask_workflow.py](mask_workflow.py)，例如`--output E:/maps/mask-study --size 128`。输出包含两张遮罩、修改前后预览、配置和PCG放置脚本；遮罩用法见[说明](../docs/MASKS.md)。

选区、材质、连接、散布、图片和网格转换的示例见[创作用法](../docs/AGENT_GUIDE.md#示例入口)。[agent_workflows.py](agent_workflows.py)中的树屋、恶地和Steve配方也可继续使用。
