"""VAT Tools 面板属性。"""
import unreal
import mineprep

from .util import MC_VAT_CLASS_PATH


class BakeAnimProps(mineprep.PropertyGroup):
    """左栏：已有 MC_VAT 时烘焙动画组。数组下标即动画组索引。"""
    DataAsset: unreal.SoftObjectPath = (None, {'AllowedClasses': MC_VAT_CLASS_PATH})
    AnimSeq: list[unreal.AnimSequence] = [None, None, None]
    bOverrideFramerate: bool = (False, {'InlineEditConditionToggle': True})
    Framerate: int = (60, {'UIMin': 24, 'UIMax': 120, 'ClampMin': 1, 'EditCondition': 'bOverrideFramerate'})

BakeAnimProps.localize()


class CopyProps(mineprep.PropertyGroup):
    """左栏脚注下方：复制数据集目标与依赖选项。"""
    TargetPath: str = '/Game/mc/VAT'
    NewName: str = ''
    CopyDeps: bool = False

CopyProps.localize()


class InitSkmProps(mineprep.PropertyGroup):
    """右栏：无数据资产时从骨骼网格体初始化。"""
    SKM: unreal.SkeletalMesh = None
    bIsItem: bool = False
    bOverwriteModel: bool = False
    SavePath: str = ''

InitSkmProps.localize()


class VATToolsOptions(mineprep.PropertyGroup):
    """面板底部选项（不进 Details）"""
    _autosave_ = True
    AutoCleanCache: bool = False
    HideInitSkm: bool = False

VATToolsOptions.localize()
