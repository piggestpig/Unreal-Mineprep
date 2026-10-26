# 中心原点与批量变换

## 坐标契约

- MC格坐标是格盒最小角，MC Y向上；UE Z向上。
- JSON方块模型以固定(8,8,8)为原点，完整cube在UE中为[-50,50]³厘米。台阶、楼梯、植物保留在格内的位置，不按实际包围盒重新居中。
- MC格盒最小角(x,y,z)、尺寸(sx,sy,sz)对应UE中心`100*(x+sx/2,z+sz/2,y+sy/2)+origin`。中心与旋转无关。
- `mc_math.boxes_to_packed`接受批量坐标、尺寸和旋转，返回连续float32的pos／rot／scale；通过24行轴交换表求局部尺寸，无逐实例三角函数。未合并单位格可使用负偏航码；正码须为整数0..23。
- 世界坐标offset不旋转、不随合并尺寸放大；模型scale作用于局部MC轴、围绕中心。
- 文件与Blocks入口默认center=False。center=True是整座结构底面居中，锚点根据剔除／合并前范围确定。
- packed、纹理和ISM写入共享校验。空结构直接返回[]，不创建纹理或Actor。纹理版本为`mc_structure_tex.ENCODING_VERSION = bpt-brt-f32-3`。

完整入口与离线示例见[公共结构API](../../../mineprep-skills/structure.md)。24方向的编码由Mineprep的mc_math模块统一处理。导入、准备、放置需要UE，数学计算及WorldGenerator生成无需UE。

## WorldGenerator

FeatureBatch新增可选rotations，限定整数0..23。全零时为None；非零以只读uint8数组经过缓存、筛选、裁切、分块和视图，上传转为float32。合并同时区分类型、旋转与高度偏移。

倒木使用同一个oak_log网格／材质：沿MC X码20、沿MC Z码8，删除fallen_oak_x/z、axis声明及临时JSON生成。树木计数按特征归属汇总，倒木不再因同用oak_log而计入树干。完整cube准备校验改为中心范围[-50,50]³。

## 水面与外部模型

水面资产 `/Game/Mineprep/MC_Blueprint/模型/方块/水面` 的局部平面应位于 Z≈43.7cm，X／Y 范围为 [-50,50]cm，方块 offset 为 (0,0,0)。已符合此约定的资产无需调整，也不需要改变水位或添加放置偏移。

新生成JSON网格带`MineprepModelFrame=cell-center-1`，旧版本不再直接复用。外部FBX／OBJ及手工StaticMesh须由作者提供正确格中心，不猜测包围盒原点。独立物品、生物和骨骼模型不套用此转换。

`/Game/Mineprep/MC_Blueprint/PCG/PCG_GPU_Structure` 的 HLSL 位置为 `PosColor.xyz*BlockSize+Offset`，24 方向表与 Python 及 `/Game/Mineprep/MC_Blueprint/Niagara/动态地形粒子/NS_ClonerMCstructure` 一致。
