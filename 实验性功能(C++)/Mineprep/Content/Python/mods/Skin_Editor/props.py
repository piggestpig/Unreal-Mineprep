"""皮肤编辑器面板的属性定义。"""
import mineprep
import unreal


class SkinEditorOptions(mineprep.PropertyGroup):
    _autosave_ = True
    Body: bool = True
    Head: bool = True

SkinEditorOptions.localize()


_VIEW_KEY = unreal.Key()
_VIEW_KEY.import_text('LeftAlt')
_PICK_KEY = unreal.Key()
_PICK_KEY.import_text('LeftShift')


class SkinPaintTools(mineprep.PropertyGroup):
    _autosave_ = True
    Texture: unreal.Texture2D = None
    Overlay: unreal.Texture2D = None
    ViewSize: float = (512, {'ClampMin': 64, 'ClampMax': 2048, 'UIMin': 128, 'UIMax': 1024,})
    BrushSize: float = (1, {'ClampMin': 1, 'ClampMax': 1024, 'UIMin': 1, 'UIMax': 64,})
    Color: unreal.LinearColor = unreal.LinearColor(1, 1, 1, 1)
    Round: bool = (False, {'EditCondition':"Advanced", 'EditConditionHides':True})
    WriteAlpha: bool = (False, {'EditCondition':"Advanced", 'EditConditionHides':True})
    PeekKey: unreal.Key = _VIEW_KEY
    PickKey: unreal.Key = _PICK_KEY
    SavePath: str = ''
    ExportPath: str = ''
    Advanced: bool = True

SkinPaintTools.localize()


script = """\
#tex/overlay 是 2D LinearColor 数组
#使用 main 函数修改 tex
#以下是从 64x64 皮肤中删去眼睛的示例

def main(tex, overlay):
    tex[11, 9:11] = tex[11,11]
    tex[11, 13:15] = tex[11,12]

    tex[12, 9:11] = tex[12,11]
    tex[12, 13:15] = tex[12,12]

    #tex[13, 9:11] = tex[13,11]
    #tex[13, 13:15] = tex[13,12]
    #tex[14, 9:11] = tex[14,11]
    #tex[14, 13:15] = tex[14,12]
    return tex
"""

class SkinCodeTools(mineprep.PropertyGroup):
    Code: str = (script, {'MultiLine': True})

SkinCodeTools.localize()


class SkinBatchTools(mineprep.PropertyGroup):
    BesideOriginal: bool = False
    Textures: list[unreal.Texture2D] = []
    NewTextures: list[unreal.Texture2D] = []

SkinBatchTools.localize()
