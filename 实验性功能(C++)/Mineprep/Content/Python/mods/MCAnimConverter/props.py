"""MC动画转换器面板属性。"""

import mineprep
import unreal


class Props(mineprep.PropertyGroup):
    _autosave_ = True
    Actor: unreal.SkeletalMeshActor
    FollowSelection: bool = True
    JsonPath: unreal.FilePath = (
        unreal.FilePath(),
        {'FilePathFilter': 'Animation files (*.json;*.bbmodel)|*.json;*.bbmodel'},
    )
    CreateNewSequence: bool = True
    LevelSequenceName: str = ('', {'EditCondition': 'CreateNewSequence', 'EditConditionHides': True})
    StartAtPlayhead: bool = (False, {'EditCondition': '!CreateNewSequence', 'EditConditionHides': True})
    UseLayeredRig: bool = False
    AnimSequenceName: str = ''
    TimeScale: float = (1.0, {'ClampMin': 0.05, 'UIMin': 0.1, 'UIMax': 4.0, 'Delta': 0.05})
    ShowAdvanced: bool = False
    IgnoreMissingBones: bool = (False, {'EditCondition': 'ShowAdvanced', 'EditConditionHides': True})
    ExportFps: int = (60, {'ClampMin': 1, 'ClampMax': 240, 'EditCondition': 'ShowAdvanced', 'EditConditionHides': True})


class FaceProps(mineprep.PropertyGroup):
    _autosave_ = True
    AutoApply: bool = False
    Strength: float = (1.0, {'ClampMin': 0.0, 'ClampMax': 2.0, 'UIMin': 0.0, 'UIMax': 1.5, 'Delta': 0.05})
    BlendIn: float = (0.0, {'ClampMin': 0.0, 'UIMax': 1.0, 'Delta': 0.05, 'Units': 's'})
    Hold: float = (0.0, {'ClampMin': 0.0, 'UIMax': 5.0, 'Delta': 0.1, 'Units': 's'})
    BlendOut: float = (0.0, {'ClampMin': 0.0, 'UIMax': 1.0, 'Delta': 0.05, 'Units': 's'})
    StartAtPlayhead: bool = True
    UseLayeredRig: bool = True


class AutoBlinkProps(mineprep.PropertyGroup):
    _autosave_ = True
    Duration: float = (0.0, {'ClampMin': 0.0, 'UIMax': 30.0, 'Delta': 0.5, 'Units': 's'})
    MinInterval: float = (2.4, {'ClampMin': 0.4, 'UIMax': 8.0, 'Delta': 0.1, 'Units': 's'})
    MaxInterval: float = (4.4, {'ClampMin': 0.5, 'UIMax': 12.0, 'Delta': 0.1, 'Units': 's'})
    BlinkDuration: float = (0.21, {'ClampMin': 0.06, 'UIMax': 0.8, 'Delta': 0.01, 'Units': 's'})
    HoldClosed: float = (0.08, {'ClampMin': 0.0, 'UIMax': 0.5, 'Delta': 0.01, 'Units': 's'})
    DoubleBlinkChance: float = (0.15, {'ClampMin': 0.0, 'ClampMax': 1.0, 'Delta': 0.05})
    Seed: int = (0, {'ClampMin': 0})


Props.localize()
FaceProps.localize()
AutoBlinkProps.localize()
