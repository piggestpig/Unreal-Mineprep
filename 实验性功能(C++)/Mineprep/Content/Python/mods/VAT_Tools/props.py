"""VAT Tools 面板属性。"""
import unreal
import mineprep

from .util import MC_VAT_CLASS_PATH


class BakeAnimProps(mineprep.PropertyGroup):
    """左栏：已有 MC_VAT 时烘焙动画组。数组下标即动画组索引。"""
    DataAsset: unreal.SoftObjectPath = (None, {'AllowedClasses': MC_VAT_CLASS_PATH})
    AnimSeq: list[unreal.AnimSequence] = [None, None, None]
    bOverrideFramerate: bool = False
    Framerate: int = (60, {'UIMin': 24, 'UIMax': 120, 'ClampMin': 1, 'EditCondition':"bOverrideFramerate", 'EditConditionHides':True})

BakeAnimProps.localize('BakeAnimProps', '烘焙动画', 'Bake Anim', '烘焙動畫')
BakeAnimProps.localize('DataAsset', '动画数据集', 'Anim Data Asset', '動畫數據集')
BakeAnimProps.localize('AnimSeq', '动画序列', 'Anim Sequences', '動畫序列')
BakeAnimProps.localize('bOverrideFramerate', '重载烘焙帧率', 'Override Framerate', '重載烘焙幀率')
BakeAnimProps.localize('Framerate', '烘焙帧率', 'Framerate', '烘焙幀率')


class CopyProps(mineprep.PropertyGroup):
    """左栏脚注下方：复制数据集目标与依赖选项。"""
    TargetPath: str = '/Game/mc/VAT'
    NewName: str = ''
    CopyDeps: bool = False

CopyProps.localize('CopyProps', '复制数据集', 'Copy Data Asset', '複製數據集')
CopyProps.localize('TargetPath', '目标路径', 'Target Path', '目標路徑')
CopyProps.localize('NewName', '新名称', 'New Name', '新名稱')
CopyProps.localize('CopyDeps', '复制所有依赖项', 'Copy All Dependencies', '複製所有依賴項')


class InitSkmProps(mineprep.PropertyGroup):
    """右栏：无数据资产时从骨骼网格体初始化。"""
    SKM: unreal.SkeletalMesh = None
    bIsItem: bool = False
    bOverwriteModel: bool = False
    SavePath: str = ''

InitSkmProps.localize('InitSkmProps', '从骨骼创建', 'Create From SKM', '從骨骼創建')
InitSkmProps.localize('SKM', '骨骼网格体', 'Skeletal Mesh', '骨骼網格體')
InitSkmProps.localize('bIsItem', '是手持物品', 'Handheld Item', '是手持物品')
InitSkmProps.localize('bOverwriteModel', '覆写现有模型', 'Overwrite Existing Mesh', '覆寫現有模型')
InitSkmProps.localize('SavePath', '保存路径', 'Save Path', '保存路徑')


class VATToolsOptions(mineprep.PropertyGroup):
    """面板底部选项（不进 Details）"""
    _autosave_ = True
    AutoCleanCache: bool = False
    HideInitSkm: bool = False

VATToolsOptions.localize('VATToolsOptions', '设置', 'Options', '設置')
VATToolsOptions.localize('AutoCleanCache', '自动清理缓存', 'Auto Clean Cache', '自動清理緩存')
VATToolsOptions.localize('HideInitSkm', '隐藏右栏', 'Hide Right Panel', '隱藏右欄')
