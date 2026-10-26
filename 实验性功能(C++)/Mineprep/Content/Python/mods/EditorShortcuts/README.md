# Python 调用

没有安装 Mineprep C++ 实验性功能插件时，面板仍可打开、编辑和保存配置，并通过执行按钮运行普通 Python 代码；全局按键绑定不可用。修改编辑器偏好和翻译鼠标下文本等依赖 C++ 的操作会提示缺少插件。现有配置中的代码不会自动改写。

在 UE 主线程中导入 `ops` 即可查询、修改或执行快捷键，不必打开面板：

```python
from mods.EditorShortcuts import ops

items = ops.get_shortcuts()          # 名称 -> {chord_text, tooltip, code}
ops.execute_shortcut('放置空物体')    # 立即执行，无返回值
mineprep.hotkey()                      # 打印全部快捷键：按键、提示
mineprep.hotkey('放置空物体')           # 公共入口，内部同样调用 execute_shortcut

name = ops.add_shortcut('我的快捷键')
code = "unreal.log('hello')"
ok, err = ops.validate_code(code, name)
ops.update_code(name, code)
chord = '(Key=F1,bShift=False,bCtrl=True,bAlt=False,bCmd=False)'
conflict, owner = ops.check_chord_conflict(name, chord)
if ok and not conflict:
    ops.update_chord_text(name, chord)  # 写入配置并注册到编辑器
```

配置文件是 `Content/Mineprep/Editor_Shortcuts.txt`，主键是快捷键名称。`chord_text` 用 `InputChord.export_text()` 的字符串；空字符串不注册。当前列表以该文件为准，预设名称在 `ops.DEFAULT_SHORTCUTS`，默认代码是 `snippets` 里的函数。`SHORTCUTS` 把快捷键名称映射到英文函数，例如 `place_empty`、`attach_to_last`。`get_snippet(名称)` 用 `inspect.getsource` 取出函数体，代码框里不带 `def` 和调用。

`update_chord_text`、`update_tooltip` 和 `rename_shortcut` 会注销再注册。`update_code` 只保存，下次按下即执行新代码。名称不存在时，更新和删除直接跳过。`rename_shortcut(old, new)` 在旧名缺失、新名为空或重名时返回 False，成功时保持原顺序。`add_shortcut` 省略名称时生成「新建快捷键」或带序号的名称；名称已存在则原样返回，不覆盖。直接改 `get_shortcuts()` 的字典后需自行 `save_shortcuts()`，改按键还要 `reregister_hotkey(name)`。

`execute_shortcut` 在有代码时先接上 `import unreal` 和 `import mineprep`，再在 `ops` 模块的全局命名空间中执行。异常通过 `mineprep.warn` 显示。代码为空，或名称不在配置中时，改为调用蓝图 `/Mineprep/Mineprep自定义快捷键` 上的同名函数。代码里启动的 `mineprep.asynctask` 会在本次调用返回后继续运行。

`check_chord_conflict` 只查本模组列表，`update_chord_text` 仍会写入。与编辑器已有快捷键的冲突由 C++ `register_hotkey` 拒绝，Python 不返回该结果，失败写在输出日志。`validate_code` 只做语法检查，空代码视为通过。`delete_shortcut(name)` 会删除并注销。`reset_to_defaults()` 会清掉全部自定义项并写回预设。

模组默认启用，启用时完成按键绑定。脚本改完即可用，不必重开面板。原面板的增删改和执行按钮调用同一套函数。

快捷键监听随模组启用和停用，不依赖面板是否打开。模组会保留事件委托，并在停用时解绑，避免回调代理被垃圾回收后按键失效。
