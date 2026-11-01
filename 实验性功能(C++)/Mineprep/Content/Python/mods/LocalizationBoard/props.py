"""本地化翻译控制板 — 面板属性。"""
import mineprep


class Props(mineprep.PropertyGroup):
    _autosave_ = True
    ScanPath: str = '/Game/Mineprep/'
    SetEnumKey: bool = True


Props.localize()


class PromptProps(mineprep.PropertyGroup):
    _autosave_ = False
    Prompt: str = ('', {'MultiLine': True})


PromptProps.localize()
