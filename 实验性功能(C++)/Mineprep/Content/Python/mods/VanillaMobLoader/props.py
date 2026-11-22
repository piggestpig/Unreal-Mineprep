"""生物模型导入与放置选项。"""
import unreal
import mineprep
from mineprep import face
from .composition import DEFAULT_SAVE_PATH

_DEFAULT_MOUTH_CAVITY_RGBA = face.hex_to_linear_rgba(face.DEFAULT_FACE_OPTIONS['mouth_cavity_color'])


class LoaderOptions(mineprep.PropertyGroup):
    ShowDetails: bool = False
    PreferJava: bool = (True, {'ToolTip': '单选且找到对应的本地 Java GLB 时使用层级骨架。多选组合及缺少 GLB 时使用 CEM。'})
    TrySplitHead: bool = (False, {'ToolTip': '尝试从本地 Java GLB 拆出头部，保留一体模型，并共享材质和贴图。不能拆分时沿用一体模型。'})
    SavePath: str = DEFAULT_SAVE_PATH
    SaveName: str = ''
    EyeDepth: float = (0.12, {'ClampMin': 0.02, 'UIMax': 0.5, 'Delta': 0.01,
        'EditCondition': "ShowDetails", 'EditConditionHides': True,
        'ToolTip': '3D 表情眼窝内凹深度（MC 像素单位，1 像素 = 6.25 cm）'})
    MouthDepth: float = (0.22, {'ClampMin': 0.02, 'UIMax': 0.6, 'Delta': 0.01,
        'EditCondition': "ShowDetails", 'EditConditionHides': True,
        'ToolTip': '3D 表情口腔内凹深度（MC 像素单位，1 像素 = 6.25 cm）'})
    UseTeeth: bool = (False, {'EditCondition': "ShowDetails", 'EditConditionHides': True,
        'ToolTip': '3D 表情张嘴时生成上排牙齿；关闭则为纯深色口腔（默认关闭，更贴近常见 MC 动画）'})
    MouthCavityColor: unreal.LinearColor = (_DEFAULT_MOUTH_CAVITY_RGBA, {'HideAlphaChannel': True,
        'EditCondition': "ShowDetails", 'EditConditionHides': True,
        'ToolTip': '3D 表情口腔内部颜色（默认深黑，导入后也可在材质实例中随时调整）'})
    BrowThickness: float = (0.08, {'ClampMin': 0.0, 'UIMax': 0.4, 'Delta': 0.01,
        'EditCondition': "ShowDetails", 'EditConditionHides': True,
        'ToolTip': '3D 表情眉毛前凸厚度（MC 像素单位，0 为不凸起）'})
    BrowHeight: float = (0.50, {'ClampMin': 0.15, 'UIMax': 1.2, 'Delta': 0.05,
        'EditCondition': "ShowDetails", 'EditConditionHides': True,
        'ToolTip': '3D 表情眉毛粗细高度（MC 像素单位）'})
    BrowFollowBlink: bool = (False, {'EditCondition': "ShowDetails", 'EditConditionHides': True,
        'ToolTip': '眨眼时带动眉毛完整下移一格；关闭则与眨眼完全解耦，由 face_brow_y 独立控制'})
    LayerExpansion: float = (0.01, {'ClampMin': 0.0, 'UIMax': 0.2, 'EditCondition': "ShowDetails", 'EditConditionHides': True,
        'ToolTip': '组合多个模型时按选择顺序逐层向外微扩，避免不同模型层贴图闪烁'})
    RandomScale: float = (0.001, {'ClampMin': 0.0, 'UIMax': 0.01, 'EditCondition': "ShowDetails", 'EditConditionHides': True,
        'ToolTip': '按部位名称固定生成微小扩缩偏移（可正可负），避免同一模型内部共面闪烁'})
    ModelScale: float = (1.0, {'ClampMin': 0.01, 'UIMax': 100.0, 'EditCondition': "ShowDetails", 'EditConditionHides': True})


LoaderOptions.localize(tooltip='zh')
