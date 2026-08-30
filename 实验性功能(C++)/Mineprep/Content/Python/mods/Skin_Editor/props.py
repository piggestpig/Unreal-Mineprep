"""Skin Editor footer options and paint page groups."""
import mineprep
import unreal


class SkinEditorOptions(mineprep.PropertyGroup):
    _autosave_ = True
    Body: bool = True
    Head: bool = True

SkinEditorOptions.localize('Body', '身体', 'Body', '身體')
SkinEditorOptions.localize('Head', '头部', 'Head', '頭部')


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

SkinPaintTools.localize('SkinPaintTools', '画笔与保存', 'Brush & Save', '畫筆與保存')
SkinPaintTools.localize('Texture', '皮肤纹理', 'Skin Texture', '皮膚紋理')
SkinPaintTools.localize('Overlay', '叠加纹理', 'Overlay Texture', '疊加紋理')
SkinPaintTools.localize('ViewSize', '画布大小', 'Canvas Size', '畫布大小')
SkinPaintTools.localize('BrushSize', '画笔尺寸', 'Brush Size', '畫筆尺寸')
SkinPaintTools.localize('Color', '颜色', 'Color', '顏色')
SkinPaintTools.localize('Round', '圆形笔触', 'Round Brush', '圓形筆觸')
SkinPaintTools.localize('WriteAlpha', '直接写入透明度', 'Direct Set Alpha', '直接寫入透明度')
SkinPaintTools.localize('PeekKey', '查看原图按键', 'View Source Key', '查看原圖按鍵')
SkinPaintTools.localize('PickKey', '吸取颜色按键', 'Pick Color Key', '吸取顏色按鍵')
SkinPaintTools.localize('SavePath', '保存路径', 'Save Path', '保存路徑')
SkinPaintTools.localize('ExportPath', '导出PNG路径', 'Export PNG Path', '導出PNG路徑')
SkinPaintTools.localize('Advanced', '高级选项', 'Advanced Options', '高級選項')


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

SkinCodeTools.localize('SkinCodeTools', '自定义代码', 'Script', '自定義代碼')
SkinCodeTools.localize('Code', '代码', 'Code', '代碼')


class SkinBatchTools(mineprep.PropertyGroup):
    BesideOriginal: bool = False
    Textures: list[unreal.Texture2D] = []
    NewTextures: list[unreal.Texture2D] = []

SkinBatchTools.localize('SkinBatchTools', '批量处理', 'Batch Process', '批量處理')
SkinBatchTools.localize('BesideOriginal', '保存至原纹理旁边', 'Save Beside Original', '保存至原紋理旁邊')
SkinBatchTools.localize('Textures', '纹理', 'Textures', '紋理')
SkinBatchTools.localize('NewTextures', '新纹理', 'New Textures', '新紋理')
