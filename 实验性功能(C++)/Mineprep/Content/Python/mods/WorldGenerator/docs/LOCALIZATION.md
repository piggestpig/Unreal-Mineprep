# 内容包文本与本地化（格式 3）

生成定义只保存稳定 ID、数值和布局。名称、说明、参数标签、提示、群系与预设名称位于各包的 `i18n.json`；固定界面使用模组根词典。原文也在词典中，不在资源定义里重复保存。

## 文件约定

```json
{
  "WorldGenerator.pack.my_world": {
    "pack.name": {"_native": "en", "en": "My world", "zh": "我的世界"},
    "params.terrain.mountain_height": {"zh": "山体高度", "en": "Mountain height"},
    "biomes.my_meadow.name": {"zh": "我的草甸", "en": "My meadow"}
  }
}
```

namespace 后缀是该文件所属包的 ID。词条省略 `_native` 时源语言为 `zh`；源语言必须有非空文本。中文使用 `zh`，台繁使用 `zh-Hant`；`zh-Hant-HK` 只填写香港差异，缺省回退到 `zh-Hant`。用户自取名称只有一份原文也有效，无需复制成多种语言。

内置MC专名按Java 26.3的[台繁语言文件](https://resources.download.minecraft.net/4e/4ef0b17ab30fdd102c142fcd7d40ce21e4524628)与[港繁语言文件](https://resources.download.minecraft.net/cc/cc2aa19ce2fc167cff61947ab4dc57c69e50a0b2)校对，自定义地形的修饰语保留实际含义。界面区分“重設／預設值”与表示Preset的“預設”；上述游戏语言文件仅供离线校对。

| 语义键 | 用途 |
| --- | --- |
| `pack.name`、`pack.description` | 包名称与说明 |
| `params.<参数键>`、`.tooltip` | 参数名称与提示 |
| `pages.<页ID>` | 原生属性分类 |
| `sections.<板块ID>` | 导航板块；自动板块沿用对应 pages 文本 |
| `groups.<板块ID>.<组ID>` | 折叠组名称 |
| `rows.<行ID>` | 组合行名称 |
| `rows.<行ID>.components.<参数键>` | 组合行各分量名称 |
| `biomes.<群系ID>.name` | 群系名称 |
| `presets.<预设ID>.name` | 包内预设名称 |

`pack.json` 必须声明 `"format_version": 3`。`pages` 为有序 ID 列表；`ui_sections` 与 groups 不再含 label；参数定义不再含 label／tooltip；群系和包内预设文件不再含 name。组合行是稳定 ID 映射，例如：

```json
{
  "ui_rows": {
    "height_range": {"keys": ["world.y_min", "world.y_max"]}
  }
}
```

行 ID 不随分量顺序改变。磁盘不保存 `terrain__mountain_height` 等 UE 属性别名；适配器在内存中生成绑定。原生分类仍包含稳定宿主包 ID，避免不同包的同名分类互相覆盖。

## 继承与刷新

沿父包到子包按 key 合并，子包声明的词条整条覆盖父词条；不逐语言合并。子包声明新中文原文而省略英文时，英文回退到该新原文。父译文不抄写进子包。

词典文件排除于内容文件戳、生成／资源指纹、模块源码快照和草稿基础检查。仅修改译文不会使已有 World 失效。0.76.1起不再后台监控词典文件；外部修改后用 `mineprep.reload()` 更新本地化缓存，显式载入资源包和编辑保存仍刷新相关词典。语言切换时继续更新导航、组标题、群系列表、预设选项和已有属性类，不重建整页或绘图控件；语言检查不读取磁盘词典。

`localization.py` 只保留有界的已解析数据；UE 文本缓存与批量注册使用公共 `Internationalization.from_data()`。TextKey 为普通不可变描述，不含 UE 对象。生成核心、Spec 和 worker 不携带翻译器。`api.catalog()`／`api.describe()` 返回 JSON 友好的原文字符串；离线图例继续选用英文并允许源文回退。

## 编辑与保存

`PackDraft.set_text(key, value, language='zh')` 修改工作词条；`draft.text(...)` 读取有效文本。文字修改计入未保存状态，但不创建新的几何修订或临时 namespace。草稿检查点保存文字修改，重新打开时保留未编辑的最新磁盘词条。

保存用户包时只写本包词条，保留继承关系。未改名时保留完整译文；仅更改包ID仍保留显示名称及继承，明确改名才替换为用户原文。用户预设库名称为普通字符串；从包内预设导出时取源文，不依赖编辑器当前语言。保存过程中同一个词条被外部修改会拒绝覆盖；其他外部词条保留。

旧格式无运行时兼容或自动升级。旧 Saved、会话、原图和资产保留；不支持的文件给出格式提示，不在打开面板时改写它们。

## 在UE中为资源包补词

`api.pack_i18n(pack_id, *, langs=None)`为已经注册的包创建公共`Internationalization`实例，指定该包自己的`i18n.json`和完整的`WorldGenerator.pack.<id>`命名空间。例如，在UE Python控制台或蓝图的Execute Python Script中给自定义包`my_world`补词：

```python
from mods.WorldGenerator import api

texts = api.pack_i18n('my_world', langs=('en', 'zh', 'zh-Hant'))
texts.biomes.my_meadow.name('My meadow', '我的草甸', '我的草甸')
```

也可以用`texts('My meadow', key='biomes.my_meadow.name', zh='我的草甸')`指定语义键。`langs`省略时沿用Mineprep的语言顺序；上例明确使用英文原文。构造实例和节点不写文件，首次补词才创建词典及父目录；已有JSON原文和译文优先，重复调用不会替换已有名称。这是创作脚本的补词入口，修改已有名称继续使用`PackDraft.set_text()`或直接编辑JSON。

入口只负责选择已注册包的目录与命名空间，收集、合并和注册全部复用公共API，不把继承后的有效词典交给文件写入器。只写目标包，父包、模组根词典和生成身份不变。补词后，面板按原有文件戳机制刷新；脚本直接读取元数据时可用`api.describe('my_world')`或`catalog(pack.name).refresh()`刷新已有Catalog。

采集应在UE主线程的创作脚本中执行，生成配方和worker保持纯数据。父子包继承后的展示、属性别名和派生提示继续走只读`from_data()`；面板名称编辑和用户包保存继续走草稿／冲突检查，不调用这个直接写文件的采集入口。

需要自选JSON位置时可直接使用`mineprep.Internationalization(namespace=..., file=...)`；WorldGenerator加载器仍从各包根目录的`i18n.json`读取，不会自动查找其他位置。自定义实例的动态路径不由离线静态采集器展开。

## 固定界面与验证

固定文本直接用 `mineprep.i18n`，固定属性类统一调用 `localize()`。动态数值先格式化，再传给 UE Text，例如 `i18n('位置 {x}').format(x=f'{x:.1f}')`。后台只报告普通消息数据，主线程负责翻译。

公共离线采集不理解包的语义键、动态选项及消息表；`unused` 不能作为删除清单，港繁缺省也不表示缺译。相关纯数据行为由 `tests/test_localization.py` 检查。真实四语 Details、分类、下拉框、刷新和绘图交互仍需在 UE 验收。
