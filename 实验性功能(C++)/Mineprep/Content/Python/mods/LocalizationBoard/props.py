"""本地化翻译控制板 — 面板属性。"""
import mineprep


class Props(mineprep.PropertyGroup):
    _autosave_ = True
    ScanPath: str = '/Game/Mineprep/'
    SetEnumKey: bool = True


Props.localize('Props', '属性', 'Properties', '屬性')
Props.localize('ScanPath', '扫描路径', 'Scan Path', '掃描路徑')
Props.localize(
    'SetEnumKey',
    '写入枚举 DisplayName Key',
    'Write enum DisplayName keys',
    '寫入列舉 DisplayName Key',
)


class PromptProps(mineprep.PropertyGroup):
    _autosave_ = False
    Prompt: str = ('', {'MultiLine': True})


PromptProps.localize('PromptProps', '提示词', 'Prompt', '提示詞')
PromptProps.localize('Prompt', '提示词', 'Prompt', '提示詞')
