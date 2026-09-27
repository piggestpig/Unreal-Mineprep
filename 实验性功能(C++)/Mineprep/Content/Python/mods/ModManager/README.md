# Python 调用

在 UE 的 Python 中直接安装或卸载，不必打开模组管理器：

```python
from mods.ModManager import ops

result = ops.install_mod('E:/Downloads/MyMod.zip')
print(result['modules'], result['paths'])
# 确认要合并覆盖已有文件时，显式传 overwrite=True。
# ops.uninstall_mod('mods.MyMod')
```

支持单个 `.py` 或包含模组文件/目录的 `.zip`。模组名须为 Python 标识符；拒绝路径越界、链接及同名冲突，覆盖需显式开启。安装不导入或自动启用，返回模块名、写入路径和被覆盖的模组名；覆盖采用合并方式，不移除旧目录中的额外文件。

`uninstall_mod(name)` 先注销已加载模组，再调用原有 `mineprep.send2trash` 移除文件，成功后清理模块缓存，返回模块名、路径和 `removed`。该公共删除函数在回收失败时可能彻底删除；卸载前请确认目标。失败抛异常，文件操作不承诺事务回滚。

两者都接受 `mods_dir=...`，可在临时目录测试；卸载时若已加载模块来自另一目录，会拒绝操作。启停继续使用 `mineprep.mods.register(module)` / `unregister(module)`，安装覆盖已加载模组后需重载才能使用新代码。
