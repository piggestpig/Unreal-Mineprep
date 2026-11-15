"""生物模型导入与放置选项。"""
import mineprep
from .composition import DEFAULT_SAVE_PATH


class LoaderOptions(mineprep.PropertyGroup):
    ShowDetails: bool = False
    PreferJava: bool = (True, {'ToolTip': '单选且找到对应的本地 Java GLB 时使用层级骨架。多选组合及缺少 GLB 时使用 CEM。'})
    TrySplitHead: bool = (False, {'ToolTip': '尝试从本地 Java GLB 拆出头部，保留一体模型，并共享材质和贴图。不能拆分时沿用一体模型。'})
    SavePath: str = DEFAULT_SAVE_PATH
    SaveName: str = ''
    LayerExpansion: float = (0.01, {'ClampMin': 0.0, 'UIMax': 0.2, 'EditCondition': "ShowDetails", 'EditConditionHides': True,
        'ToolTip': '组合多个模型时按选择顺序逐层向外微扩，避免不同模型层贴图闪烁'})
    RandomScale: float = (0.001, {'ClampMin': 0.0, 'UIMax': 0.01, 'EditCondition': "ShowDetails", 'EditConditionHides': True,
        'ToolTip': '按部位名称固定生成微小扩缩偏移（可正可负），避免同一模型内部共面闪烁'})
    ModelScale: float = (1.0, {'ClampMin': 0.01, 'UIMax': 100.0, 'EditCondition': "ShowDetails", 'EditConditionHides': True})


LoaderOptions.localize(tooltip='zh')
