# 模组清单与打包

所有模组都需要声明字典 `mod_info`。文件夹模组可以额外提供 `mod_manifest.toml`，单文件模组继续只写 `mod_info`。

使用Python 3.11起内置的tomllib读取，不需要额外安装依赖。

```toml
schema_version = 2
Name = ["示例模组", "Example Mod"]
Description = "一个简单的模组"
Version = "1.0"
CreatedBy = "Pig"
EnabledByDefault = false
ReloadWithMineprep = true
Priority = 0
Advanced = false

[build]
paths_exclude_pattern = ["/Saved/", "/tests/", "/tools/", "/docs/dev/"]
```

`schema_version` 必须为整数 `2`，与模组的 `Version` 无关。其他元数据沿用 `mod_info` 的大小写；`Version`、`CreatedBy` 为字符串，三个开关为布尔值，`Priority` 为整数。未知元数据会保留。

缺省值：名称为文件夹名，简介和作者为空，版本为 `-`；默认停用、不随 Mineprep 重载、不隐藏到高级选项，优先级为 `0`。有清单时不会导入程序补齐信息。格式错误或不支持的版本会报告错误，不回退导入，也不影响其他模组。

## 文本写法

`Name`、`Description` 支持以下三种形式，实际使用时择一：

```toml
Name = "Example Mod"
Name = ["示例模组", "Example Mod"]
Name = { chinese = "示例模组", english = "Example Mod" }
```

字符串原样保留；数组展开为 `bilingual(*value)`，可写一个或两个字符串；字典展开为 `bilingual(**value)`，使用 `chinese` 和可选的 `english`。省略英文时沿用中文。

## 加载与状态

有清单的模组先读取元数据，默认停用时不会因启动或面板列表扫描而导入。没有清单时仍须导入并读取 `mod_info`。优先级越大越先启用，同优先级按模块名排序。

启用时检查 `mod_info`，比较同名项，再以有效清单信息原地更新它，保留额外字段。文本按当前语言的显示值比较；差异通过 `mineprep.debug(..., autolog=True, warning=True)` 提示。`schema_version` 和 `build` 不写入 `mod_info`。

`EnabledByDefault` 只声明启动默认值；当前启用状态由 `mcvars.EnabledMods` 记录。手动启停不会改写声明，完整重载恢复操作后的状态。状态不跨 UE 重启保存。`ReloadWithMineprep` 仅控制已经导入的模组，重载不会因此导入原本未导入的停用模组。

## 打包规则

不写 `[build]` 时扫描整个模组。始终过滤 `.git`、`.hg`、`.svn`、`__pycache__`、`.pytest_cache` 目录以及 `.pyc`、`.pyo` 文件；不会因名字自动排除 `tests`、`tools`、`cache`、`Saved`。

`paths_exclude_pattern` 使用 Blender 风格的路径模式：

| 模式 | 含义 |
| --- | --- |
| `/tests/` | 根目录下的 tests 目录 |
| `tests/` | 各层名为 tests 的目录 |
| `*.pyc` | 各层同后缀文件 |
| `a/**/b.txt` | a 下零层或多层子目录中的 b.txt |
| `file?.[ch]` | 单字符与字符集合匹配 |
| `!keep.txt` | 保留匹配项，不能恢复强制过滤的缓存或版本库 |

路径使用 `/`。例外优先，不按 Git 的“后写覆盖前写”处理；被排除目录不会继续遍历，因此子文件例外不能单独恢复整个被排除的父目录。这不是完整的 gitignore 实现。

也可以明确列出文件，两种方式不能同时声明：

```toml
[build]
paths = ["__init__.py", "panel.py", "ops.py"]
```

`paths` 只接受模组内已有文件，不展开目录或通配符；没有 `include_pattern`。清单始终附带，模组入口不能遗漏。输出保持“模组名/文件”结构；单文件模组 ZIP 中为“模组名.py”。

打包不导入、启停或改写模组。ZIP 须保存在模组目录外；链接、越界路径及未经明确允许的覆盖会被拒绝。
