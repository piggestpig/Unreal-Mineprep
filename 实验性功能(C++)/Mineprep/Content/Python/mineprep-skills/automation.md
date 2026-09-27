# Scene automation example

Reference only, not a rule or a required sequence. This is one editor session: sky, a particle structure, an effector, keys on a copied 60fps sequence, then a render click. After the click it polls `MoviePipelineQueueSubsystem.is_rendering()` once a second and prints when that returns false. Paths, coordinates, frame numbers, and the effector delay belong to that session.

For a new request, follow [api.md](api.md) and [parallel.md](parallel.md). Do not copy these choices unless the user asked for them.

```python
import os
import mineprep
import unreal

@mineprep.asynctask
def task():
    sky_class = mineprep.uclass('/Game/Mineprep/MC_Blueprint/Core/天空/MC天空')
    mineprep.panel('生成MC天空_可右键').click(-1)

    def find_sky():
        found = unreal.GameplayStatics.get_all_actors_of_class(mineprep.world(), sky_class)
        return found[0] if len(found) == 1 else None

    sky = yield from mineprep.until(find_sky, label='MC天空')
    sky.set_actor_location(unreal.Vector(0, 0, 0), False, True)

    source = os.path.join(mineprep.paths.installer, 'Blender扩展资源', 'mcstructure_test.mcstructure')
    actors = mineprep.spawn_structure(source, gpu=2)
    particle = yield from mineprep.until(lambda: actors[0] if actors else None, label='结构粒子')

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
    delay = next(e for e in comp.get_active_effects() if isinstance(e, unreal.CEEffectorDelayEffect))
    delay.set_delay_enabled(True)
    delay.set_delay_in_duration(0.0)
    delay.set_delay_out_duration(0.5)
    delay.set_delay_spring_frequency(1.0)
    delay.set_delay_spring_falloff(1.0)

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

    e = mineprep.actor(effector)
    e.key('Location', unreal.Vector(0, 1100, 0), 0)
    e.key('Location', unreal.Vector(0, 1000, 0), 30)
    e.key('Location', unreal.Vector(0, -1000, 0), 120)

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

task()
```
