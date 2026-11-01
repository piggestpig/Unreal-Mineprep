"""插件更新与迁移工具 — 面板属性。"""
import mineprep
import unreal


class Props(mineprep.PropertyGroup):
    _autosave_ = True
    TargetDir: unreal.DirectoryPath = unreal.DirectoryPath(path='')
    ClearDest: bool = False
    UseModManifest: bool = (False, {'ToolTip': '使用模组清单中的打包规则，跳过不需要分发的文件。'})
    UpdateInstaller: bool = False
    RunScript: bool = (True, {'EditCondition': 'UpdateInstaller', 'EditConditionHides': True})
    CopyPythonLib: bool = (True, {'EditCondition': '!UpdateInstaller', 'EditConditionHides': True})


Props.localize(tooltip='zh')


class SkipProps(mineprep.PropertyGroup):
    _autosave_ = True
    SkipFolders: list[str] = (['Tests', 'tests'], {'ToolTip': '按名称跳过任意层级的同名文件夹，区分大小写；清空列表可取消这项过滤。'})
    Script: str = ('def skip(path: str) -> bool:\n    return False', {'MultiLine': True})


SkipProps.localize(tooltip='zh')


class FilterProps(mineprep.PropertyGroup):
    _autosave_ = False
    FilterNew: bool = (False, {'ToolTip': '列出目标目录中尚不存在的文件；列表内勾选表示复制，取消勾选表示跳过。'})
    NewFiles: dict[str, bool] = ({}, {'EditCondition': 'FilterNew', 'EditConditionHides': True})
    FilterNewer: bool = (False, {'ToolTip': '按文件修改时间判断（当前工程比目标目录更新）；列表内勾选表示复制，取消勾选表示跳过。'})
    NewerFiles: dict[str, bool] = ({}, {'EditCondition': 'FilterNewer', 'EditConditionHides': True})
    FilterOlder: bool = (False, {'ToolTip': '按文件修改时间判断（当前工程比目标目录更旧）；列表内勾选表示复制，取消勾选表示跳过。'})
    OlderFiles: dict[str, bool] = ({}, {'EditCondition': 'FilterOlder', 'EditConditionHides': True})
    EntryDefault: unreal.LightingChannels = (unreal.LightingChannels(True, True, True), {'ToolTip': '对应通道 0/1/2：展开新增、源文件较新、目标文件较新列表时，各条目的初始勾选状态（勾选=复制，取消=跳过）。'})

FilterProps.localize(tooltip='zh')


class ExtraProps(mineprep.PropertyGroup):
    _autosave_ = False
    RemoveExtra: bool = (False, {'ToolTip': '列出目标目录中有而当前工程中没有的文件；列表内勾选表示移除，取消勾选表示保留。'})
    ExtraFiles: dict[str, bool] = ({}, {'EditCondition': 'RemoveExtra', 'EditConditionHides': True})
    EntryDefault: bool = False


ExtraProps.localize(tooltip='zh')
