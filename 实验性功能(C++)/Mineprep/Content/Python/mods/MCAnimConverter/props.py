"""MC动画转换器面板属性。"""

import mineprep
import unreal

class Props(mineprep.PropertyGroup):
    _autosave_ = True
    Actor: unreal.SkeletalMeshActor
    JsonPath: unreal.FilePath = (
        unreal.FilePath(),
        {'FilePathFilter': 'Animation files (*.json;*.bbmodel)|*.json;*.bbmodel'},
    )
    CreateNewSequence: bool = True
    LevelSequenceName: str = ('', {'EditCondition': 'CreateNewSequence'})
    StartAtPlayhead: bool = (False, {'EditCondition': '!CreateNewSequence'})
    AnimSequenceName: str = ''
    TimeScale: float = 1.0

Props.localize()
