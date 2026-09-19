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
    LevelSequenceName: str = ''
    AnimSequenceName: str = ''
    StartAtPlayhead: bool = False
    TimeScale: float = 1.0
    BoneMap: str = (DEFAULT_BONE_MAP_TEXT, {'MultiLine': True})

Props.localize('Props', '属性', 'Properties', '屬性')
Props.localize('Actor', '目标角色', 'Actor', '目標角色')
Props.localize('JsonPath', 'json动画文件', 'json anim file', 'json 動畫文件')
Props.localize('CreateNewSequence', '创建新关卡序列', 'Create new Level Sequence', '建立新關卡序列')
Props.localize('LevelSequenceName', '关卡序列名称', 'Level Sequence name', '關卡序列名稱')
Props.localize('AnimSequenceName', '动画序列名称', 'Anim Sequence name', '動畫序列名稱')
Props.localize('StartAtPlayhead', '从播放头开始', 'Start at playhead', '從播放頭開始')
Props.localize('TimeScale', '时间缩放', 'Time scale', '時間縮放')
Props.localize('BoneMap', '骨骼重定向', 'Retarget', '骨骼重定向')
