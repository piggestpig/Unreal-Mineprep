import math
import os

import numpy as np
import unreal
import mineprep
from mineprep import bilingual


def reshape(arr, dim=2):
    # 计算尽可能接近的各轴长度
    l, shape = len(arr), []
    for i in range(dim, 0, -1):
        side = math.ceil(l ** (1 / i))
        shape.append(side)
        l = math.ceil(l / side)

    # 用-1填充末尾并重塑形状
    padded = np.pad(arr, (0, np.prod(shape) - len(arr)), constant_values=-1)
    return padded.reshape(shape)


def coords_dict(arr, step=100, offset=(0, 0, 0)):
    arr = np.asarray(arr)
    result = {}

    for idx, val in np.ndenumerate(arr):
        # 将坐标补齐为3维，并乘以步长
        coord = tuple(idx[i] * step + offset[i] if i < len(idx) else offset[i] for i in range(3))
        result[coord] = val

    return result


def placeholder(*args, **kwargs):
    pass


def spawn_oak(status=placeholder, loc=(0, 0, 0), step=800):
    h = 5
    b = mineprep.Blocks(name='oak')
    for y in range(h):
        b.add('oak_log', 0, y, 0, axis='y')
    for y, r in ((h - 2, 2), (h - 1, 2), (h, 1), (h + 1, 1)):
        for x in range(-r, r + 1):
            for z in range(-r, r + 1):
                if x == 0 and z == 0 and y < h:
                    continue
                if abs(x) == r and abs(z) == r:
                    continue
                b.add('oak_leaves', x, y, z)

    modes = (
        (0, '实例化网格体', 'ISM'),
        (1, 'PCG', 'PCG'),
        (2, '粒子', 'Niagara'),
    )
    for i, (gpu, zh, en) in enumerate(modes):
        status(bilingual(f'正在生成{zh}橡树', f'Spawning {en} oak'))
        pos = (loc[0] + i * step, loc[1], loc[2])
        out = mineprep.spawn_structure(b, loc=pos, gpu=gpu, name=f'oak_{en.lower()}')
        if not out:
            raise RuntimeError(str(bilingual(f'{zh}橡树生成失败', f'{en} oak spawn failed')))
        yield 0.5


def mob_spawner(status=placeholder, step=250, offset=(0, 0, 1000)):
    options = mineprep.panel('生成器子面板.放置生物选项').get(list)
    options = coords_dict(reshape(options), step=step, offset=offset)
    for pos, name in options.items():
        if name == -1 or name == '-1':
            continue
        status(bilingual(f'正在生成 {name}', f'Spawning {name}'))
        mineprep.spawn_mob(name, pos)
        yield


def intro_tutorial(status=placeholder):
    sky_class = mineprep.uclass('/Game/Mineprep/MC_Blueprint/Core/天空/MC天空')
    status(bilingual('生成MC天空', 'Spawning MC sky'))
    mineprep.panel('生成MC天空_可右键').click(-1)

    def find_sky():
        found = unreal.GameplayStatics.get_all_actors_of_class(mineprep.world(), sky_class)
        return found[0] if len(found) == 1 else None

    sky = yield from mineprep.until(find_sky, label='MC天空')
    sky.set_actor_location(unreal.Vector(0, 0, 0), False, True)

    status(bilingual('生成结构粒子', 'Spawning structure particles'))
    source = os.path.join(mineprep.paths.installer, 'Blender扩展资源', 'mcstructure_test.mcstructure')
    actors = mineprep.spawn_structure(source, gpu=2)
    particle = yield from mineprep.until(lambda: actors[0] if actors else None, label='结构粒子')

    status(bilingual('创建效应器', 'Creating effector'))
    before = {a.get_path_name() for a in particle.get_attached_actors()}
    particle.call_method('创建链接效应器')

    def find_effector():
        selected = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_selected_level_actors()
        for item in list(selected) + list(particle.get_attached_actors()):
            if item.get_path_name() in before or item == particle:
                continue
            if item.get_class().get_name() == 'CEEffectorActor':
                return item
        return None

    effector = yield from mineprep.until(find_effector, label='Effector')
    effector.set_actor_location(unreal.Vector(0, 1000, 0), False, True)
    comp = effector.get_component_by_class(unreal.CEEffectorComponent)
    effect = next(e for e in comp.get_active_effects() if isinstance(e, unreal.CEEffectorDelayEffect))
    effect.set_delay_enabled(True)
    effect.set_delay_in_duration(0.0)
    effect.set_delay_out_duration(0.5)
    effect.set_delay_spring_frequency(1.0)
    effect.set_delay_spring_falloff(1.0)

    status(bilingual('设置关卡序列', 'Setting up level sequence'))
    seq = mineprep.copy('/Game/Mineprep/Render/MC关卡序列', '/Game/demo')
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq)
    unreal.MovieSceneSequenceExtensions.set_playback_start(seq, 0)
    unreal.MovieSceneSequenceExtensions.set_playback_end(seq, 180)

    cam = yield from mineprep.until(
        lambda: mineprep.sequencer(seq).bindings('MC摄像机').actor(),
        label='MC摄像机',
    )
    c = mineprep.actor(cam)
    c.key('Location', unreal.Vector(-2000, 1150, 850), 0)
    c.key('Rotation', unreal.Rotator(roll=0.0, pitch=-11.0, yaw=-30.0), 0)

    actor = mineprep.actor(effector)
    actor.key('Location', unreal.Vector(0, 1100, 0), 0)
    actor.key('Location', unreal.Vector(0, 1000, 0), 30)
    actor.key('Location', unreal.Vector(0, -1000, 0), 120)

    status(bilingual('正在渲染', 'Rendering'))
    yield 1
    mineprep.panel('渲染输出子面板.画质预设选项').select(-1)
    yield 1
    mineprep.panel('渲染输出子面板.ue一键渲染按钮').click(-1)

    def render_done():
        sub = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
        if sub.is_rendering():
            return None
        return True

    yield from mineprep.until(render_done, timeout=60, step=1, delay=1, label='渲染完成')
    mineprep.prints('渲染完成！')


TESTS = [
    {
        'id': 'spawn_oak',
        'label': mineprep.bilingual('生成橡树', 'Spawn oak'),
        'fn': spawn_oak,
    },
    {
        'id': 'mob_spawner',
        'label': mineprep.bilingual('生成生物', 'Spawn mobs'),
        'fn': mob_spawner,
    },
    {
        'id': 'intro_tutorial',
        'label': mineprep.bilingual('入门教程示例', 'Getting started example'),
        'fn': intro_tutorial,
    },
]
