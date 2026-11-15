# 模型来源

要把模型放进关卡并添加动作，见 [UE 动画制作速查](../MCAnimConverter/QUICKSTART.md)。

面板通过 CEM 目录浏览。默认勾选「优先使用层级模型（Java GLB）」，单选时优先导入匹配的本地 GLB。多选、取消勾选或文件缺失时使用 CEM。已有 GLB 导入失败时会显示文件路径与错误。

Java GLB 清单中的编辑骨架配置由 [HUMANOIDS](java_models.py) 与 [QUADRUPEDS](java_models.py) 统一管理：`HUMANOIDS` 中的 31 个人形模型（含无独立双臂的折叠抱臂系 `villager`、`villager_baby`、`wandering_trader`、`witch`，以及上肢已挂在 `body` 下的 `copper_golem`）默认使用 `biped` 编辑骨架（`body` 和 `pelvis` 的参考枢轴都位于两髋中点，头、双臂与抱臂跟随 `body`，双腿跟随 `pelvis`）；`QUADRUPEDS`（37 个四足及其幼体：在首批 30 个常见扁平四足基础上纳入 `camel`、`camel_baby`、`horse`、`horse_baby`、`armadillo`、`armadillo_baby` 与 `ravager`）默认使用 `quadruped_edit` 编辑骨架（`pelvis` 与 `body` 共置于后髋中心对称线高度，前腿及附着在 `root` 下的 `head` / `head_parts` / `neck` / `hump` / `upper_body` / `left_chest` / `right_chest` / `egg_belly` 跟随 `body`，已有层级如 `head_parts -> head`、`neck -> head` 与 `body -> tail` 保持原父子连接，后腿及挂在 `root` 下的 `tail` / `tail1` 跟随 `pelvis`，`tail2` 挂在 `tail1` 下；另注：`armadillo` / `armadillo_baby` 在 `root` 下保留原版卷壳节点 `cube`，默认展开态预览时会遮挡躯干与四肢，属已知限制）。模组导入时从原版 GLB 生成对应骨架，默认网格名为 `SKM_<Name>`。脚本传 `edit_rig=False` 可导入原版 Java 扁平层级，未指定名称时使用 `_Raw` 后缀。需要并存 Java 与 CEM 输出时，为另一份指定独立的 `name`。

`mineprep.paths.glb` 默认指向安装包内的 `Blender扩展资源/GLB`。在 `Mineprep_config.txt` 的 `Settings` 中设置 `glb_dir` 可指定另一处绝对目录，例如 `"glb_dir": "E:/Models/Minecraft/GLB"`。设置在 Mineprep 初始化时读取。自定义目录缺文件时使用 CEM。

新资产默认保存到 `/Game/mc/entity/<名称>/`。Java 模型使用与 CEM 相同的 LabPBR 皮肤材质，半透明层使用 LabPBR 半透明材质。重新导入会保留已有 Skeleton，骨骼名称或父子关系改变时需另存。贴图按内嵌图像内容复用，材质按贴图和 LabPBR 模板复用。换皮会创建新版本，旧资产继续供已有引用使用。

勾选「尝试头身分离」后，本地 Java GLB 可按 `head` 骨骼分支拆分。同一文件夹保留 `SKM_<名称>`，并生成 `SKM_<名称>_body` 与 `SKM_<名称>_head`，三个模型引用一体模型的材质和皮肤贴图。身体保留完整骨架，头部以自身枢轴为原点、沿原 `head` 骨骼的局部轴导出。玩家 biped 的独立头部面向 +X，附加到身体时局部变换为单位变换。无 head 分支、蒙皮跨界或使用 CEM 时，返回原因并沿用一体模型。

头身拆分实现在模组内的 `gltf.split_head`，由 `java_models.split_source` 管理生成文件；GLB 读写复用核心 `mc_model`，不另设顶层拆分模块。

生成的编辑骨架 GLB 缓存在模组的 `__pycache__/resources/generated/humanoid_edit/` 与 `quadruped_edit/`，文件名为 `<模型>_<8 位内容哈希>.glb`。导入后的资产可能引用此文件作为重新导入来源。制作新动画时，可以用构建结果中的 `rig_profile`（`'biped'`、`'quadruped_edit'` 或 `None`）确认编辑骨架。

# 物理资产生成

导入骨骼网格体完成后，`api.build_entity()` 和 `api.spawn()` 默认会检查并绑定物理资产（`physics=True`）：

- **资产命名与复用**：按显式传入的 `asset_name` 完整生成并绑定 `PA_<名称>`；成功头身分离时，`SKM_<名称>` 与 `SKM_<名称>_body` 共用 `PA_<名称>`，独立头部 `SKM_<名称>_head` 另外生成 `PA_<名称>_head`。使用 `SPLIT_ACTOR` 放置时，`Head` 附着组件本身保持 `NoCollision` 且不参与模拟，不与全身碰撞体重复碰撞；`SKM_<名称>_head` 仅在单独放置时使用自身物理资产。放置后的生物组件默认保持不开启物理模拟（`SimulatePhysics = False`）。
- **重导保留与显式重建**：`reload=True` 重新导入网格体时，若 `rebuild_physics=False`（默认）会优先复用已绑定或同目录下兼容的物理资产（仅在尚无可用物理资产时补建），不覆盖手工调整过的盒体；若 `PA_<名称>` 已存在但与当前骨架不兼容，则保留原资产不覆盖、输出 warning 并改用唯一后缀命名（后续重导优先复用该新物理资产）。传 `rebuild_physics=True` 才重建并覆盖目标物理资产。传 `physics=False` 可跳过自动生成。
- **`biped` 盒体规则与回退**：当插件提供盒体构建绑定 `unreal.mineprep.build_box_physics_asset` 且可通过资产关联 GLB 的纯 Python `mc_model.glb_bone_bounds()`（或在无可用 GLB 时回退可选实验接口 `get_bone_local_bounds`）获取骨骼局部顶点包围盒时，对于 `rig_profile == 'biped'` 启用 `VanillaMobLoader/physics.py` 拟合盒体：`root` 保留小型代理盒、无约束且屏蔽内部碰撞；`pelvis` 保留小型无碰撞代理盒并约束连接 `body` / `left_leg` / `right_leg`（带合理质量覆盖）；主肢体之间默认**保留相互碰撞**，使用内缩与关节退让盒体，自动排除外层皮肤骨骼并消除初始重叠。对存在长袍下摆且躯干包围盒明显下探覆盖腿部的人形（如灾厄村民、僵尸村民等），自动将 `body` 下缘裁剪至髋部高度以免挤压腿部厚度；对带有抱臂骨骼 `arms` 的模型，检查 `arms` 及其子孙骨骼（如 `left_shoulder`、`right_hand`、`middlearm_r1`）的包围盒与源 GLB 贴图 Alpha 通道（`villager` 系、`evoker`、`vindicator`、`illusioner` 合并 `arms` 子树作为胸前抱臂刚体，在无独立 `left_arm`/`right_arm` 或贴图不透明时替代双臂并约束到 `body` 且屏蔽 `arms-body` 内部碰撞；`arms` 全透明的 `pillager` 仍保留独立双臂）。
- **非 `biped` 通用盒体规则**：对非人形 Java GLB（含 `quadruped_edit` 四足编辑骨架，自动跳过无顶点的 `pelvis`）、`edit_rig=False` 原始扁平骨架（含未列入编辑清单的标准网格模型如村民）、单体/复杂 CEM 以及组合 CEM 模型，启用 `compute_generic_physics_layout` 自动生成通用盒体物理资产：存在空 `root` 时保留一致的小型无约束代理盒并屏蔽对内碰撞，保持蓝图 `SetAllBodiesBelowSimulatePhysics("root", ..., false)` 行为统一；保留骨骼层级关系并基于核心躯干与组件空间表面距离构建连通 Prim 关节树；主碰撞体对非着地侧执行适度内缩（大尺度轴向约 `14%` 缩放余量并随角色尺度计算相邻分离间隙与近邻禁用边距）以避免落地自碰撞反弹；有主骨骼祖先的装饰/外层/覆盖件交由父骨骼自动刚性带动，直接挂在 `root` 或空枢轴下的面饰与嵌套配件则生成无碰撞辅助体并 `Locked` 约束至宿主骨骼；为优先确保密集关节体 Chaos 模拟稳定，**所有直接相连的约束对与退让后仍临近（`< close_margin`）/穿插的肢体对均禁用相互碰撞**（仅远端非相邻刚体保留互撞；作为稳定性取舍，相邻肢体大角度弯折后可能轻度穿入），并钳制极小部件与最重主体的质量比上限（`<= 14:1`）。
- **引擎默认回退与保存校验**：当 `build_box_physics_asset` 不可用、既无匹配可读 GLB 又缺少可选 `get_bone_local_bounds`（或布局构建失败）时，均附带 warning 回退到引擎 `SkeletalMeshEditorSubsystem.create_physics_asset` 默认生成。回退生成遇到同名已有资产时同样保留旧资产而不删除，改为新建唯一名称的物理资产并绑定；保存物理资产失败时（`save_loaded_asset` 返回 `False` 或异常）会输出 warning。

# 名称与搜索

卡片、详情、提示和新放置 Actor 的标签使用当前语言的生物名称，支持简中、英文、台湾繁体和香港繁体。切换语言后重新打开面板即可刷新全部显示；已有 Actor 标签不自动更名。

搜索同时匹配四语名称、英文 ID、文件名和常用幼体别名，多个词取交集。例如 `僵尸 baby`、`oak 船`、`沉屍 外層`、`小鸡`、`牛犊`。空搜索仍按原分类和变体展开状态浏览。未收录名称回退英文，不保证完整翻译所有新增模板或上游说明。

基础译名只读使用 Python 根目录的 `i18n_entities.json`，词缀模板在本模组的 `i18n.json`；没有共享词典时基础名称回退英文。目录构建及搜索只处理普通 Python 数据，名称和搜索词在构建目录时预计算。UE Text 在主线程批量注册，不由下载线程注册，也不在搜索时读取词典。

`Entry.name` 和资产元数据 `VanillaMobLoader.Name` 保留来源英文；`Entry.translations` 提供四语字符串。`names.text(entry.name)` 在主线程取得本地化 Text，组合名称也可直接传入；`names.description(entry)` 将上游说明的 `{0}` 替换为本地化名称。保存名称、资产路径、目录 key 和配方身份始终不受显示语言影响。放置缓存模型时根据英文名称重新查译名，不需要重新导入；不迁移旧资产。

# Python 调用

在 UE 主线程中加载目录、构建资产，不必打开模组面板。最简方式是用 `api.spawn()` 按英文 ID 一行提交（内部自动加载目录、查找、构建并放置，按编辑器帧推进并复用相同任务句柄）：

```python
from mods.VanillaMobLoader import api
spawn_job = api.spawn('player', name='ShotSteve', try_split_head=True)
# 完成后从 spawn_job.result['actor'] 取已放置的 Actor，其余构建字段与 build_entity 相同
```

传入 `catalog=` 时会同步校验参数与 ID（无效或歧义 ID 立即抛错）；未传入 `catalog` 时，目录加载与 ID 解析在任务内部异步执行，失败通过 `spawn_job.state == 'failed'` 与 `spawn_job.error` 获取。若需要搜索交互或先看变体，可分步调用：

```python
from mods.VanillaMobLoader import api, importer, names
catalog_job = api.load_catalog()  # 优先缓存；refresh=True 强制重新下载目录
```

每步任务均按编辑器帧推进。在后续 Python 调用中检查状态，再开始依赖它的下一步；不要在 UE 主线程循环等待：

```python
assert catalog_job.state == 'completed', catalog_job.status()
catalog = catalog_job.result['catalog']
names.register(catalog)  # 主线程批量注册显示名称；搜索本身不需要这一步
choices = [(e.key, str(names.text(e.name))) for e in catalog.search(query='猪')]
key = choices[0][0]  # 按实际目录选择；组合时传多个 key，顺序决定主模型
job = api.build_entity(catalog, [key], name='MyPig', try_split_head=True)
```

```python
assert job.state == 'completed', job.status()
mesh = job.result['mesh']
actor = importer.place(mesh, scale=1.0, head_mesh=job.result['head_mesh'])
# 显式位置：importer.place(mesh, target=(unreal.Vector(0, 0, 100), False))
```

`job.status()` 返回 `state/result/error`，终态为 `completed/failed/cancelled`。构建结果含 `mesh/full_mesh/head_mesh/physics_asset/head_physics_asset/path/name/reused/warnings/source/rig_profile`，其中 `name` 是本次构建的本地化显示名称。拆分成功时，`mesh` 为身体，`head_mesh` 为独立头部，`full_mesh` 始终为一体模型，`physics_asset` 由完整与身体共用，`head_physics_asset` 为独立头部物理资产。未拆分时 `head_mesh=None` 且 `head_physics_asset=None`。`importer.place(full_mesh)` 和 `importer.place(head_mesh)` 可分别独立放置，普通骨骼模型使用基础生物模型蓝图，传入 `head_mesh=` 时使用头身分离绑定基础生物模型蓝图。

传 `prefer_java=False` 强制使用 CEM，传 `edit_rig=False` 跳过编辑骨架改用原始扁平骨架。`source` 返回 `java_glb` 或 `cem`，`rig_profile` 返回 `'biped'`、`'quadruped_edit'` 或 `None`。`reload=True` 重新导入，默认复用匹配的已有资产；`rebuild_physics=True` 显式重建物理资产。依赖缺失和导入失败详情见 `error`。

骨骼冲突默认失败，明确传 `conflict_policy='keep_first'` 才采用主模型骨骼；也可用 `on_conflict(conflicts)` 返回 True 接受。`load_catalog` 和 `build_entity` 都支持 `cache=目录`、`stall_timeout=10`、`on_progress(text)`、`on_stall()`、`on_done(job)`。停滞默认失败，`on_stall` 返回 True 可继续等待；所有回调在主线程调用。构建参数在提交时读取，不跟随面板选择改变。

`job.cancel()` 关闭本任务的资源并阻止后续导入；已完成的同步 UE 导入和资产写入不会回滚。下载/几何在 worker 上进行，UE 导入留在主线程。不要同时构建到同一目标。模组卸载会取消活动任务。

面板支持多选组合、自动命名、骨骼冲突确认及模型缩放；“放置生物”在构建完成后放置到场景，“重新加载生物”只更新资产。“刷新资源”会下载目录并补齐全部缩略图；脚本调用 `load_catalog` 则只加载目录，不预下载全部缩略图。本模组不解析执行 CEM 动画表达式。

面板刷新使用现有后台线程池下载，主线程逐帧检查完成状态，不弹出阻塞式进度对话框。进度显示在面板状态栏，每帧最多导入一张缩略图；等待下载时编辑器可继续操作。关闭面板会停止刷新调度并取消尚未启动的下载，正在执行的网络请求结束后不会继续更新面板。
