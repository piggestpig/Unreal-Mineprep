"""插件更新与迁移工具 — 面板属性。"""
import mineprep
import unreal


class Props(mineprep.PropertyGroup):
    _autosave_ = True
    TargetDir: unreal.DirectoryPath = unreal.DirectoryPath(path='')
    ClearDest: bool = False
    UpdateInstaller: bool = False
    RunScript: bool = (True, {'EditCondition': 'UpdateInstaller', 'EditConditionHides': True})
    CopyPythonLib: bool = (True, {'EditCondition': '!UpdateInstaller', 'EditConditionHides': True})


Props.localize('Props', '属性', 'Properties', '屬性')
Props.localize(
    'UpdateInstaller',
    '用当前内容更新安装包',
    'Update installer with current content',
    '用目前內容更新安裝包',
)
Props.localize('TargetDir', '目标文件夹', 'Target folder', '目標資料夾')
Props.localize(
    'ClearDest',
    '清空目标路径再复制文件',
    'Clear destination then copy',
    '清空目標路徑再複製檔案',
)
Props.localize(
    'RunScript',
    '运行自动化处理脚本',
    'Run automation script',
    '執行自動化處理腳本',
)
Props.localize(
    'CopyPythonLib',
    '复制 Python 库',
    'Copy Python libraries',
    '複製 Python 庫',
)


class SkipProps(mineprep.PropertyGroup):
    _autosave_ = True
    Script: str = ('def skip(path: str) -> bool:\n    return False', {'MultiLine': True})


SkipProps.localize('SkipProps', '自定义过滤', 'Custom Filter', '自訂過濾')
SkipProps.localize('Script', '过滤脚本', 'Filter script', '過濾腳本')


class FilterProps(mineprep.PropertyGroup):
    _autosave_ = False
    FilterNew: bool = False
    NewFiles: dict[str, bool] = ({}, {'EditCondition': 'FilterNew', 'EditConditionHides': True})
    FilterNewer: bool = False
    NewerFiles: dict[str, bool] = ({}, {'EditCondition': 'FilterNewer', 'EditConditionHides': True})
    FilterOlder: bool = False
    OlderFiles: dict[str, bool] = ({}, {'EditCondition': 'FilterOlder', 'EditConditionHides': True})
    EntryDefault: unreal.LightingChannels = unreal.LightingChannels(True, True, True)

FilterProps.localize('FilterProps', '文件过滤', 'File Filters', '檔案過濾')
FilterProps.localize('FilterNew', '过滤新增文件', 'Filter new files', '過濾新增檔案')
FilterProps.localize('NewFiles', '新增文件', 'New files', '新增檔案')
FilterProps.localize('FilterNewer', '过滤变新的文件', 'Filter newer files', '過濾變新的檔案')
FilterProps.localize('NewerFiles', '变新的文件', 'Newer files', '變新的檔案')
FilterProps.localize('FilterOlder', '过滤变旧的文件', 'Filter older files', '過濾變舊的檔案')
FilterProps.localize('OlderFiles', '变旧的文件', 'Older files', '變舊的檔案')
FilterProps.localize(
    'EntryDefault',
    '默认值 (新增 / 变新 / 变旧)',
    'Defaults (new / newer / older)',
    '預設值 (新增 / 變新 / 變舊)',
)


class ExtraProps(mineprep.PropertyGroup):
    _autosave_ = False
    RemoveExtra: bool = False
    ExtraFiles: dict[str, bool] = ({}, {'EditCondition': 'RemoveExtra', 'EditConditionHides': True})
    EntryDefault: bool = False


ExtraProps.localize('ExtraProps', '多余文件', 'Extra Files', '多餘檔案')
ExtraProps.localize(
    'RemoveExtra',
    '移除目标路径多余文件',
    'Remove extra files in target',
    '移除目標路徑多餘檔案',
)
ExtraProps.localize('ExtraFiles', '多余文件', 'Extra files', '多餘檔案')
ExtraProps.localize('EntryDefault', '各条目默认值', 'Default for each entry', '各條目預設值')
