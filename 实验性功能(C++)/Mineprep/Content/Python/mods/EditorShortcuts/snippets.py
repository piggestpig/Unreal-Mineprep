# -*- coding: utf-8 -*-
"""EditorShortcuts 预设快捷键。

每条预设是一个英文函数，可直接调用。get_snippet 只取出函数体，
供快捷键代码框直接执行。SHORTCUTS 把快捷键名称映射到这些函数。
"""

import inspect
import io
import tokenize

import mineprep
import unreal


def place_empty():
    asset = unreal.load_asset('/Game/Mineprep/MC_Blueprint/Core/空物体.空物体')
    actor = mineprep.EditorBPLib['放置模型并选中'](asset, False, 'None', False, True)
    if actor:
        mineprep.EditorBPLib['设置Actor标签+后缀'](actor, '空物体', unreal.Actor)


def deselect_half():
    import random
    actors = mineprep.selected[:]
    if len(actors) > 1:
        random.shuffle(actors)
        mineprep.select_actors(actors[:0.5])


def toggle_camera_preview():
    from mods.EditorShortcuts.ops import _cpp_function
    curr = _cpp_function('get_project_setting')('bPreviewSelectedCameras')
    _cpp_function('set_project_setting')('bPreviewSelectedCameras', str(curr != 'True'))


def toggle_toolbar_icons():
    from mods.EditorShortcuts.ops import _cpp_function
    curr = _cpp_function('get_project_setting')('bUseSmallToolBarIcons')
    _cpp_function('set_project_setting')('bUseSmallToolBarIcons', str(curr != 'True'))


def toggle_blueprint_components():
    from mods.EditorShortcuts.ops import _cpp_function
    curr = _cpp_function('get_project_setting')('bHideConstructionScriptComponentsInDetailsView')
    _cpp_function('set_project_setting')('bHideConstructionScriptComponentsInDetailsView', str(curr != 'True'))


def toggle_selection_outline():
    from mods.EditorShortcuts.ops import _cpp_function
    curr = _cpp_function('get_project_setting')('bUseSelectionOutline')
    _cpp_function('set_project_setting')('bUseSelectionOutline', str(curr != 'True'))


def move_to_front():
    actors = mineprep.selected()
    if actors:
        loc = mineprep.EditorBPLib['编辑器视口线条追踪'](True)
        with unreal.ScopedEditorTransaction(mineprep.bilingual('移动到面前', 'Move To Front')):
            actors.set_actor_location(loc, False, False)


def key_visible():
    actors = mineprep.selected()
    if actors:
        f = mineprep.sequencer.frame()
        with unreal.ScopedEditorTransaction(mineprep.bilingual('添加可视性关键帧', 'Add Visibility Keyframe')):
            actors.key('bHidden', True, f - 1)
            actors.key('bHidden', False, f)


def key_hidden():
    actors = mineprep.selected()
    if actors:
        f = mineprep.sequencer.frame()
        with unreal.ScopedEditorTransaction(mineprep.bilingual('设置隐藏关键帧', 'Add Hidden Keyframe')):
            actors.key('bHidden', False, f - 1)
            actors.key('bHidden', True, f)


def recompile_blueprints():
    skel = mineprep.selected().comps(unreal.SkeletalMeshComponent)
    if skel:
        skel.set_update_animation_in_editor(True)
    bps = []
    seen = set()
    for actor in mineprep.selected[:]:
        bp, has_bp = unreal.BlueprintEditorLibrary.get_blueprint_for_class(actor.get_class())
        if has_bp and bp:
            path = bp.get_path_name()
            if path not in seen:
                seen.add(path)
                bps.append(bp)
    for bp in bps:
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)


def swap_positions():
    actors = mineprep.selected[:]
    if len(actors) >= 2:
        transforms = [(a.get_actor_location(), a.get_actor_rotation()) for a in actors]
        with unreal.ScopedEditorTransaction(mineprep.bilingual('交换对象位置', 'Swap Actor Positions')):
            for i, a in enumerate(actors):
                next_loc, next_rot = transforms[(i + 1) % len(actors)]
                a.set_actor_location_and_rotation(next_loc, next_rot, False, True)


def pilot_camera():
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if level_subsystem and level_subsystem.get_pilot_level_actor():
        level_subsystem.eject_pilot_level_actor()
    else:
        cams = mineprep.selected(lambda a: a.get_component_by_class(unreal.CameraComponent))
        if not cams:
            cams = mineprep.actors(lambda a: a.actor_has_tag('camera'))
        if cams and level_subsystem:
            level_subsystem.pilot_level_actor(cams[0])
        else:
            mineprep.warn('未找到选中的摄像机或带有 camera 标签的摄像机！')


def align_camera():
    ue_subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    cam = None
    try:
        frame = mineprep.sequencer.frame()
        cuts = mineprep.sequencer().tracks(unreal.MovieSceneCameraCutTrack).sections()
        for cut in cuts:
            if cut.get_start_frame() <= frame <= cut.get_end_frame():
                bound = unreal.LevelSequenceEditorBlueprintLibrary.get_bound_objects(cut.get_camera_binding_id())
                if bound and isinstance(bound[0], unreal.Actor):
                    cam = bound[0]
                    break
    except Exception:
        pass
    if not cam:
        cams = mineprep.selected(lambda a: a.get_component_by_class(unreal.CameraComponent))
        if not cams:
            cams = mineprep.actors(lambda a: a.actor_has_tag('camera'))
        if cams:
            cam = cams[0]
    if cam:
        with unreal.ScopedEditorTransaction(mineprep.bilingual('对齐摄像机至视图', 'Align Camera to View')):
            loc, rot = ue_subsystem.get_level_viewport_camera_info()
            cam.set_actor_location_and_rotation(loc, rot, False, False)
            if level_subsystem:
                level_subsystem.pilot_level_actor(cam)
            mineprep.select_actors([cam])
    else:
        mineprep.warn('未找到可对齐的摄像机！')


def attach_to_last():
    from functools import partial
    picked = mineprep.selected[:]
    if len(picked) < 2:
        mineprep.warn('请至少选中 2 个物体')
    else:
        parent, children = picked[-1], picked[:-1]
        items = [{'label': '⭐' + parent.get_actor_label(), 'comp': None, 'sockets': []}]
        for comp in parent.get_components_by_class(unreal.SceneComponent):
            sockets = []
            if isinstance(comp, unreal.SkeletalMeshComponent):
                sockets = [str(name) for name in comp.get_all_socket_names()]
            items.append({'label': comp.get_name(), 'comp': comp, 'sockets': sockets})

        class AttachParent(mineprep.Mod):
            def draw(self, context=None):
                frame = self.layout.sizebox(480, 560, padding=0)
                row = frame.row(fill=1, align=(0, 0), padding=0)
                self.left = row.col(fill=1, align=(0, 0), padding=(0, 4))
                right = row.col(fill=1, align=(0, 0), padding=(4, 4))
                self.right = right.scrollbox(fill=1, align=(0, 0), clip=True).col()
                for item in items:
                    self.left.button(item['label'], on_clicked=partial(self.attach, item, ''),
                                    on_hovered=partial(self.show_sockets, item), size=12)

            def show_sockets(self, item):
                self.right.clear_children()
                for socket in item['sockets']:
                    self.right.button(socket, on_clicked=partial(self.attach, item, socket), size=12)

            def attach(self, item, socket_name):
                comp = item['comp']
                rule = unreal.AttachmentRule.KEEP_WORLD
                socket = unreal.Name(socket_name) if socket_name else unreal.Name()
                with unreal.ScopedEditorTransaction(mineprep.bilingual('绑定父级', 'Set Parent')):
                    for child in children:
                        root = child.root_component
                        if root:
                            root.set_mobility(unreal.ComponentMobility.MOVABLE)
                        if comp:
                            child.attach_to_component(comp, socket, rule, rule, rule, False)
                        else:
                            child.attach_to_actor(parent, unreal.Name(), rule, rule, rule, False)
                self.close()

        AttachParent()


def render_image():
    panel = mineprep.EditorBPLib('插件面板')
    if panel:
        panel.get_editor_property('渲染输出子面板').call_method('渲染图片')
    else:
        unreal.EditorLevelLibrary.execute_console_command('HighResShot 1')


def render_video():
    panel = mineprep.EditorBPLib('插件面板')
    if panel:
        panel.get_editor_property('渲染输出子面板').call_method('一键渲染')
    elif mineprep.sequencer():
        unreal.LevelSequenceEditorBlueprintLibrary.play()
    else:
        mineprep.warn('未打开关卡序列！')


def attach_to_empty():
    panel = mineprep.EditorBPLib('插件面板')
    if panel:
        panel.get_editor_property('生成器子面板').call_method('附加组件', (18,))
    else:
        actors = mineprep.selected[:]
        if actors:
            asset = unreal.load_asset('/Game/Mineprep/MC_Blueprint/Core/空物体.空物体')
            parent = mineprep.EditorBPLib['放置模型并选中'](asset, False, 'None', False, True)
            if parent:
                mineprep.EditorBPLib['设置Actor标签+后缀'](parent, '空物体', unreal.Actor)
                rule = unreal.AttachmentRule.KEEP_WORLD
                with unreal.ScopedEditorTransaction(mineprep.bilingual('绑定至空物体', 'Attach to Null Actor')):
                    for child in actors:
                        child.attach_to_actor(parent, unreal.Name(), rule, rule, rule, False)
                    mineprep.select_actors([parent])
        else:
            mineprep.warn('请先选择要绑定的物体！')


def preview_final_quality():
    director = mineprep.BPLib('导播台')
    if director:
        @mineprep.asynctask
        def toggle_quality():
            director.call_method('设置画质', (True,))
            yield 1.0
            director.call_method('设置画质', (False,))
        toggle_quality()


def temp_test():
    actor = mineprep.selected[0]
    if actor:
        unreal.get_editor_subsystem(unreal.EditorActorSubsystem).duplicate_actor(actor)


def show_shortcuts():
    from mods.EditorShortcuts.panel import EditorShortcuts
    EditorShortcuts.register(True)


def translate_under_mouse():
    from mods.EditorShortcuts.ops import _cpp_function
    _cpp_function('loc_widget_text_under_mouse')()


def fly_camera():
    subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    cam_loc, cam_rot = subsystem.get_level_viewport_camera_info()
    fwd = cam_rot.get_forward_vector()
    hit = unreal.SystemLibrary.line_trace_single(
        subsystem.get_editor_world(), cam_loc, cam_loc + fwd * 1000000.0,
        unreal.TraceTypeQuery.ECC_CAMERA, True, [], unreal.DrawDebugTrace.NONE, True
    )
    values = hit.to_tuple() if hit else ()
    if values and values[0]:
        target_loc = values[5] - fwd * 250.0
        @mineprep.asynctask
        def fly():
            for i in range(1, 31):
                alpha = i / 30.0
                cam_loc, cam_rot = subsystem.get_level_viewport_camera_info()
                new_loc = unreal.MathLibrary.v_lerp(cam_loc, target_loc, alpha)
                subsystem.set_level_viewport_camera_info(new_loc, cam_rot)
                yield 0.01
        fly()


# 快捷键名称 -> 函数。
SHORTCUTS = {
    '放置空物体': place_empty,
    '随机弃选一半选中项': deselect_half,
    '启用/禁用预览摄像机窗口': toggle_camera_preview,
    '仅显示工具栏图标': toggle_toolbar_icons,
    '显示蓝图生成的组件': toggle_blueprint_components,
    '高亮选中项': toggle_selection_outline,
    '移动选中项到面前': move_to_front,
    '设置可视性关键帧': key_visible,
    '设置隐藏关键帧': key_hidden,
    '刷新选中项，重新编译蓝图': recompile_blueprints,
    '交换选中对象位置': swap_positions,
    '进入摄像机视图': pilot_camera,
    '对齐摄像机至视图': align_camera,
    '绑定其他选中项至最后选中项': attach_to_last,
    '渲染图片': render_image,
    '渲染视频': render_video,
    '绑定选中项至空物体': attach_to_empty,
    '预览最终画质': preview_final_quality,
    '临时测试': temp_test,
    '显示快捷键信息': show_shortcuts,
    '翻译鼠标下文本': translate_under_mouse,
    '传送摄像机至前方物体': fly_camera,
}


def get_snippet(name: str) -> str:
    """返回可直接 exec 的默认代码，只含函数体。"""
    # 已保存的快捷键名称也可读取同一份预设代码。
    if name == '刷选选中项，重新编译蓝图':
        name = '刷新选中项，重新编译蓝图'
    fn = SHORTCUTS.get(name)
    if fn is None:
        return ''
    source = inspect.getsource(fn)
    string_lines = set()
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.STRING and tok.end[0] > tok.start[0]:
            string_lines.update(range(tok.start[0] + 1, tok.end[0] + 1))
    rows = list(enumerate(source.splitlines()[1:], start=2))
    while rows and not rows[0][1].strip():
        rows.pop(0)
    indent = 0
    for lineno, line in rows:
        if lineno in string_lines or not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        break
    prefix = ' ' * indent
    body = []
    for lineno, line in rows:
        if indent and lineno not in string_lines and line.startswith(prefix):
            line = line[indent:]
        body.append(line)
    text = '\n'.join(body).rstrip()
    return text + '\n' if text else ''


def get_all_snippets() -> dict[str, str]:
    """快捷键名称到默认代码的映射。"""
    return {name: get_snippet(name) for name in SHORTCUTS}
