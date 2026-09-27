# Python 调用

在 UE 主线程中导入 `api`，传入骨骼网格体和动画资产即可，无需打开面板：

```python
import unreal
from mods.VAT_Tools import api

skm = unreal.load_asset('/Game/Characters/MyMesh')
anim = unreal.load_asset('/Game/Characters/Walk')
dataset = api.create_from_skm(skm, save_path='/Game/mc/VAT/MyMesh')
result = api.bake(dataset, [anim, None, anim], override_framerate=True, framerate=30)
assert result['ok'], result['errors']
copied = api.copy_dataset(dataset, '/Game/mc/VAT/Copy', 'DA_Copy', copy_dependencies=True)
```

创建和复制返回 MC_VAT 资产；失败抛异常，已生成的资产不会自动回滚。创建时省略 `save_path` 使用网格体旁的原默认目录；`is_item=True` 使用物品命名和材质设置，`overwrite_model=True` 允许重建已有静态网格体。其余同名资产沿用原复用规则。

烘焙同步执行，返回 `ok`、`dataset`、`succeeded`、`failed`、`cleared` 和按槽位索引记录的 `errors`。输入列表顺序不变，`None` 清空对应纹理组，重复动画复用本轮纹理。单槽失败会继续其他槽；`ok` 只有全部成功才为 True。`auto_clean_cache=True` 会在结束后删除该数据集目录下的 `cache`。

复制依赖包括静态网格体、材质、纹理集合和动画纹理；骨骼网格体、动画及材质普通贴图仍共享。`copy_dependencies=False` 仅复制数据集。同名目标会复用并更新引用，操作会保存资产，建议给独立数据集使用独立目录。

原面板入口仍可用；`bake_animation(...)` 保留原布尔返回规则（至少一个动画成功即 True），新脚本用 `api.bake` 获取完整结果。
