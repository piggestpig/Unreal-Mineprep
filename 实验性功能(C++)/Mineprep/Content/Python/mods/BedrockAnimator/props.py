"""基岩版动画转换器面板属性。"""
import pprint

import mineprep
import unreal

# (ue_bone, pos, rot, scale). rot 输出是 UE X=Roll Y=Pitch Z=Yaw。
DEFAULT_BONE_MAP = {
    'root': ('root', 'x-zy', 'x-zy', 'xzy'),
    'hip': ('spine_01', 'x-y-z', 'xyz', 'xyz'),
    'waist': ('spine_01', 'x-y-z', 'xyz', 'xyz'),
    'torso': ('spine_01', 'x-y-z', 'xyz', 'xyz'),
    'body': ('spine_03', 'x-y-z', 'xyz', 'xyz'),
    'head': ('head', 'x-y-z', 'xyz', 'zxy'),
    'rightArm': ('upperarm_r', 'xyz', 'x-y-z', 'xyz'),
    'leftArm': ('upperarm_l', 'xyz', 'x-y-z', 'xyz'),
    'rightLeg': ('thigh_r', 'xyz', 'x-y-z', 'xyz'),
    'leftLeg': ('thigh_l', 'xyz', 'x-y-z', 'xyz'),
}
DEFAULT_BONE_MAP_TEXT = pprint.pformat(DEFAULT_BONE_MAP, width=88, sort_dicts=False)
DEFAULT_JSON = (
    'c:/XboxGames/Minecraft for Windows/Content/data/resource_packs'
    '/persona/pieces/emote_wave/overhead_wave.animation.json'
)


class Props(mineprep.PropertyGroup):
    _autosave_ = True
    Actor: unreal.SkeletalMeshActor
    JsonPath: unreal.FilePath = (
        unreal.FilePath(file_path=DEFAULT_JSON),
        {'FilePathFilter': 'json'},
    )
    CreateNewSequence: bool = True
    LevelSequenceName: str = ('', {'EditCondition': 'CreateNewSequence'})
    StartAtPlayhead: bool = (False, {'EditCondition': '!CreateNewSequence'})
    AnimSequenceName: str = ''
    TimeScale: float = 1.0
    BoneMap: str = (DEFAULT_BONE_MAP_TEXT, {'MultiLine': True})

Props.localize()
