# 让 agent 协助迁移

本模组仍提供原有面板。agent 不需要调用模组函数或构造 Props；根据用户指令阅读源码、确定迁移内容，确认后使用自己的文件工具执行即可。

先区分“迁移到另一 UE 工程”和“更新安装包”。当前源码的 `_TREES` 列出 `Content/Mineprep`、`Plugins/Mineprep` 及两个可选插件 `InlineMaterialInstance`、`MoviePipelineMaskRenderPass`。查看 `dest_abs` 确认安装包布局，查看 `_iter_files`、`_copy_ignore_with_skip` 和过滤属性确认排除规则。这些是现有模组的行为参考，不是所有任务都应复制的固定清单。

迁移前先检查实际源、目标目录和 UE 版本，按用户需要列出具体复制、覆盖、删除路径，以及可选 Python 库、INI 修改、脚本执行。向用户展示该计划并确认后再执行；不因模组存在 `Clear` 或 `RunScript` 默认值就自动清空目录或运行脚本。目标不能等于源或位于源目录内部，删除前核对最终绝对路径及其所属目标目录。

`_write_project_ini` 包含渲染、输入、编辑器和 Python 等设置，按需挑选并保留目标已有的无关配置，不整份覆盖。`_copy_python_libs` 的源位于 `Intermediate/PipInstall/Lib/site-packages`，复制前检查目标 Python/UE 兼容性。`_run_installer_script` 指向安装包内的 `Readme素材/自动化处理脚本.py`；先阅读内容，将副作用列入确认范围，不直接执行模组入口。

使用文件工具按已确认清单迁移，必要时备份将被覆盖的目标文件。遇到权限、缺文件或复制失败应报告具体路径和部分结果，不默认强删后继续。完成后核对重要文件内容、数量和配置差异，列出失败项；是否启动目标工程验证由用户任务决定，不自动关闭当前工程。本 README 不新增迁移 API，模组版本和实现保持不变。
