"""生物模型导入与放置选项。"""
import mineprep


class LoaderOptions(mineprep.PropertyGroup):
    ShowDetails: bool = False
    SavePath: str = '/Game/mc/mob/'
    SaveName: str = ''
    LayerExpansion: float = (0.01, {'ClampMin': 0.0, 'UIMax': 0.2, 'EditCondition': "ShowDetails", 'EditConditionHides': True,
        'ToolTip': '组合多个模型时按选择顺序逐层向外微扩，避免不同模型层贴图闪烁'})
    RandomScale: float = (0.001, {'ClampMin': 0.0, 'UIMax': 0.01, 'EditCondition': "ShowDetails", 'EditConditionHides': True,
        'ToolTip': '按部位名称固定生成微小扩缩偏移（可正可负），避免同一模型内部共面闪烁'})
    ModelScale: float = (1.0, {'ClampMin': 0.01, 'UIMax': 100.0, 'EditCondition': "ShowDetails", 'EditConditionHides': True})


LoaderOptions.localize(tooltip='zh')
