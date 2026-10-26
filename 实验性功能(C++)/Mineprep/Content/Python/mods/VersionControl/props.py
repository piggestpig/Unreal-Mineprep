"""插件更新与迁移工具 — 面板属性。"""
import mineprep
import unreal


class Props(mineprep.PropertyGroup):
    _autosave_ = True
    TargetDir: unreal.DirectoryPath = unreal.DirectoryPath(path='')
    ClearDest: bool = False
    UseModManifest: bool = (False, {'ToolTip': str(mineprep.bilingual(
        '使用模组清单中的打包规则，跳过不需要分发的文件。',
        'Use mod manifest build rules to skip files not needed for distribution.',
    ))})
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
    'UseModManifest',
    '按模组清单筛选文件',
    'Filter files using mod manifests',
    '依模組清單篩選檔案',
)
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
    SkipFolders: list[str] = (['Tests', 'tests'], {'ToolTip': str(mineprep.bilingual(
        '按名称跳过任意层级的同名文件夹，区分大小写；清空列表可取消这项过滤。',
        'Skip folders with these exact, case-sensitive names at any depth. Clear the list to disable this filter.',
    ))})
    Script: str = ('def skip(path: str) -> bool:\n    return False', {'MultiLine': True})


SkipProps.localize('SkipProps', '自定义过滤', 'Custom Filter', '自訂過濾')
SkipProps.localize('SkipFolders', '跳过文件夹', 'Skip folders', '略過資料夾')
SkipProps.localize('Script', '过滤脚本', 'Filter script', '過濾腳本')


class FilterProps(mineprep.PropertyGroup):
    _autosave_ = False
    FilterNew: bool = (False, {'ToolTip': str(mineprep.bilingual(
        '列出目标目录中尚不存在的文件；列表内勾选表示复制，取消勾选表示跳过。',
        'List files not yet in the destination; checked entries are copied, unchecked are skipped.',
    ))})
    NewFiles: dict[str, bool] = ({}, {'EditCondition': 'FilterNew', 'EditConditionHides': True})
    FilterNewer: bool = (False, {'ToolTip': str(mineprep.bilingual(
        '按文件修改时间判断（当前工程比目标目录更新）；列表内勾选表示复制，取消勾选表示跳过。',
        'Compared by file modification time (source newer than destination); checked = copy, unchecked = skip.',
    ))})
    NewerFiles: dict[str, bool] = ({}, {'EditCondition': 'FilterNewer', 'EditConditionHides': True})
    FilterOlder: bool = (False, {'ToolTip': str(mineprep.bilingual(
        '按文件修改时间判断（当前工程比目标目录更旧）；列表内勾选表示复制，取消勾选表示跳过。',
        'Compared by file modification time (destination newer than source); checked = copy, unchecked = skip.',
    ))})
    OlderFiles: dict[str, bool] = ({}, {'EditCondition': 'FilterOlder', 'EditConditionHides': True})
    EntryDefault: unreal.LightingChannels = (unreal.LightingChannels(True, True, True), {'ToolTip': str(mineprep.bilingual(
        '对应通道 0/1/2：展开新增、源文件较新、目标文件较新列表时，各条目的初始勾选状态（勾选=复制，取消=跳过）。',
        'Channels 0/1/2: initial checked state for New / Newer / Older file lists (checked = copy, unchecked = skip).',
    ))})

FilterProps.localize('FilterProps', '文件过滤', 'File Filters', '檔案過濾')
FilterProps.localize('FilterNew', '逐项选择新增文件', 'Select new files individually', '逐項選擇新增檔案')
FilterProps.localize('NewFiles', '新增文件（勾选=复制）', 'New files (checked = copy)', '新增檔案（勾選=複製）')
FilterProps.localize('FilterNewer', '逐项选择源文件较新的文件', 'Select newer source files individually', '逐項選擇來源較新的檔案')
FilterProps.localize('NewerFiles', '源文件较新的文件（勾选=复制）', 'Newer source files (checked = copy)', '來源較新的檔案（勾選=複製）')
FilterProps.localize('FilterOlder', '逐项选择目标文件较新的文件', 'Select older source files individually', '逐項選擇目標較新的檔案')
FilterProps.localize('OlderFiles', '目标文件较新的文件（勾选=复制）', 'Older source files (checked = copy)', '目標較新的檔案（勾選=複製）')
FilterProps.localize(
    'EntryDefault',
    '默认勾选 (新增 / 源较新 / 目标较新)',
    'Default checked (new / newer / older)',
    '預設勾選 (新增 / 來源較新 / 目標較新)',
)


class ExtraProps(mineprep.PropertyGroup):
    _autosave_ = False
    RemoveExtra: bool = (False, {'ToolTip': str(mineprep.bilingual(
        '列出目标目录中有而当前工程中没有的文件；列表内勾选表示移除，取消勾选表示保留。',
        'List files present only in destination; checked entries are removed, unchecked are kept.',
    ))})
    ExtraFiles: dict[str, bool] = ({}, {'EditCondition': 'RemoveExtra', 'EditConditionHides': True})
    EntryDefault: bool = False


ExtraProps.localize('ExtraProps', '多余文件', 'Extra Files', '多餘檔案')
ExtraProps.localize(
    'RemoveExtra',
    '移除目标路径多余文件',
    'Remove extra files in target',
    '移除目標路徑多餘檔案',
)
ExtraProps.localize('ExtraFiles', '多余文件（勾选=移除）', 'Extra files (checked = remove)', '多餘檔案（勾選=移除）')
ExtraProps.localize('EntryDefault', '默认勾选移除', 'Default checked to remove', '預設勾選移除')
