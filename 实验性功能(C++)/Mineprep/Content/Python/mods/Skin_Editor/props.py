"""Skin Editor footer options and paint page groups."""
import mineprep
import unreal


class SkinEditorOptions(mineprep.PropertyGroup):
    Body: bool = True
    Head: bool = True

SkinEditorOptions.localize('Body', '身体', 'Body', '身體')
SkinEditorOptions.localize('Head', '头部', 'Head', '頭部')


_VIEW_KEY = unreal.Key()
_VIEW_KEY.import_text('LeftAlt')


class SkinPaintTools(mineprep.PropertyGroup):
    Texture: unreal.Texture2D = None
    Overlay: unreal.Texture2D = None
    ViewSize: float = (512, {'ClampMin': 64, 'ClampMax': 2048, 'UIMin': 128, 'UIMax': 1024,})
    BrushSize: float = (1, {'ClampMin': 1, 'ClampMax': 1024, 'UIMin': 1, 'UIMax': 64,})
    Round: bool = False
    Color: unreal.LinearColor = unreal.LinearColor(1, 1, 1, 1)
    WriteAlpha: bool = False
    PeekKey: unreal.Key = _VIEW_KEY
    SavePath: str = ''
    ExportPath: str = ''

SkinPaintTools.localize('SkinPaintTools', '画笔与保存', 'Brush & Save', '畫筆與保存')
SkinPaintTools.localize('Texture', '皮肤纹理', 'Skin Texture', '皮膚紋理')
SkinPaintTools.localize('Overlay', '叠加纹理', 'Overlay Texture', '疊加紋理')
SkinPaintTools.localize('ViewSize', '画布大小', 'Canvas Size', '畫布大小')
SkinPaintTools.localize('BrushSize', '画笔尺寸', 'Brush Size', '畫筆尺寸')
SkinPaintTools.localize('Round', '圆形笔触', 'Round Brush', '圓形筆觸')
SkinPaintTools.localize('Color', '颜色', 'Color', '顏色')
SkinPaintTools.localize('WriteAlpha', '直接写入透明度', 'Direct Set Alpha', '直接寫入透明度')
SkinPaintTools.localize('PeekKey', '查看原图按键', 'View Source Key', '查看原圖按鍵')
SkinPaintTools.localize('SavePath', '保存路径', 'Save Path', '保存路徑')
SkinPaintTools.localize('ExportPath', '导出PNG路径', 'Export PNG Path', '導出PNG路徑')
