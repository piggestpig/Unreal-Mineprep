"""Entity import options. Scale applies to instances, not saved geometry."""
import mineprep


class LoaderOptions(mineprep.PropertyGroup):
    ShowDetails: bool = False
    SavePath: str = '/Game/mc/mob/'
    SaveName: str = ''
    LayerExpansion: float = (0.01, {'ClampMin': 0.0, 'UIMax': 0.2, 'EditCondition':"ShowDetails", 'EditConditionHides':True})
    RandomScale: float = (0.001, {'ClampMin': 0.0, 'UIMax': 0.01, 'EditCondition':"ShowDetails", 'EditConditionHides':True})
    ModelScale: float = (1.0, {'ClampMin': 0.01, 'UIMax': 100.0, 'EditCondition':"ShowDetails", 'EditConditionHides':True})


LoaderOptions.localize('LoaderOptions', '导入选项', 'Import Options', '導入選項')
LoaderOptions.localize('ShowDetails', '显示细节', 'Show details', '顯示細節')
LoaderOptions.localize('SavePath', '保存路径', 'Save path', '儲存路徑')
LoaderOptions.localize('SaveName', '保存名称', 'Save name', '儲存名稱')
LoaderOptions.localize('LayerExpansion', '多选外扩量（像素/层）', 'Multi-select expansion (pixels)', '多選外擴量（像素/層）')
LoaderOptions.localize('RandomScale', '部位随机外扩（像素）', 'Random part scale (pixels)', '部位隨機外擴（像素）')
LoaderOptions.localize('ModelScale', '模型缩放', 'Model scale', '模型縮放')