try:
    import unreal
except ModuleNotFoundError:
    from mc_utils import Lazy as unreal
import os
import re
import json
from collections.abc import Iterable
from pathlib import Path

import mc_importer, mc_utils, mc_prep, mc_localization, mc_structure, mc_config
import mc_widget, mc_mod, mc_mesh, mc_material, mc_parallel, mc_bplib, mc_math
import mc_handle, mc_rig, mc_sequencer, mc_blockstates, mc_model
from mc_bplib import BPLibCaller, BPLib, EditorBPLib
from mc_handle import (
    MineprepAPIHandle, actor, actors, camera, selected, component, components, materials,
    sequencer, bindings, tracks, sections, channels, keys,
    spawn_camera, new_sequence, keyframes,
)
from mc_importer import import_block, import_item, resolve_block_json_path, get_all_blocks
from mc_utils import (reload, cast, uclass, bpclass, world, prints, warn, throw, panic,
                      enum, askopenfilename, askopenfilenames, send2trash, set_actor_label, select_actors,
                      undo, open_main_panel, get_hotkey_object, construct, uasset, copy,
                      List, SafeList, WrapList, iscollection, debug, resolve_soft, dialog,
                      askdirectory, asksaveasfilename, startfile, screenshot, Lazy,
                      left_mouse_down, middle_mouse_down, right_mouse_down, show_editor_task, unwrap_rotations)
from mc_parallel import (
    delay, tick, asynctask, thread, asyncthread, until,
    DelayRunner, TickRunner, AsyncTaskRunner, ThreadRunner,
)
from mc_prep import (
    prep_texture, load_mcprep_data, colorize_material,
    apply_mc_material_defaults, identify_mc_texture, resolve_mc_texture,
    prepare_materials, replace_materials, prepare_scene, prepare_assets,
)
from mc_material import (
    tex_to_color, color_to_tex, ColorList,
    register_biome_tex, clear_biome_tex,
    tex_source_files, export_tex_cache, import_data_tex,
)
from mc_localization import (
    localize, loctext, nsloctext, loctable_col, bilingual, tooltip,
    Internationalization, i18n, I18N,
    collect_i18n, check_i18n,
    copy_engine_culture, editor_has_culture,
)
from mc_structure import (
    parse_structure, structure_to_tex, structure_parts, Blocks,
    convert_to_unreal_transforms, convert_to_packed_arrays, add_packed_instances,
    spawn_structure,
)
import mcvars
from mc_math import boxes_to_packed, encode_rotation, decode_rotation, wave, unwrap_angles
from mc_blockstates import rotate_state, mirror_state
from mc_config import config, paths, wclass
from mc_rig import Rig
from mc_sequencer import keyframe
from mc_widget import Layout, PropertyGroup, add_widget, ui, make_combo_text
from mc_mod import mods, Mod
from mc_mesh import merge_skm
from mc_model import LowPolyModel, SkeletalModel


####################################################################################

def help():
    """打印Mineprep Python API的默认提示"""
    return prints(tooltip('help'), duration=5)

class MineprepAddonHandle(MineprepAPIHandle):
    def get(self, prop: type=None):
        """获取属性值，自动转换为prop类型；如果target是数组，则返回数组"""
        value = None
        cast_type = prop if isinstance(prop, type) else None
        type_str = cast_type.__name__ if cast_type else str(prop)

        if cast(self.target, wclass.checkbox):
            state = self.target.get_checked_state()
            if state == unreal.CheckBoxState.CHECKED:
                value = 1
            elif state == unreal.CheckBoxState.UNCHECKED:
                value = 0
            else:
                value = -1

        elif cast(self.target, wclass.MCimage):
            value = self.target.get_editor_property('当前状态')

        elif cast(self.target, wclass.slider):
            value = self.target.get_value()

        elif cast(self.target, wclass.option):
            if cast_type in (int, float):
                value = self.target.get_selected_index()
            elif issubclass(cast_type, Iterable) and not issubclass(cast_type, (str, bytes)):
                value = [self.target.get_option_at_index(i) for i in range(self.target.get_option_count())]
            else:
                value = self.target.get_selected_option()

        elif cast(self.target, wclass.textbox):
            value = self.target.get_text()

        elif cast(self.target, wclass.prop):
            prop_name = self.target.get_property_name()
            outer_widget = unreal.UserWidgetFunctionLibrary.get_outer_user_widget(self.target)
            value = outer_widget.get_editor_property(prop_name)

        else:
            value = self.target.get_editor_property(type_str)

        try:
            value = eval(str(value))
        except:
            pass
        return cast_type(value) if cast_type else value

    def get_value(self, prop: type=None) -> float:
        """获取属性值并转为浮点数"""
        return float(self.get(prop))

    def get_string(self, prop: type=None) -> str:
        """获取属性值并转为字符串"""
        return str(self.get(prop))

    #############################################################################################

    def trigger(self, name: str = ''):
        """触发按钮"""
        trigger_name = name if name else self.label
        return get_hotkey_object().call_method('Trigger', (self.target, str(trigger_name)))

    def click(self, index: int = -1):
        """模拟点击按钮, -1左键, 0中键, 1右键, 2双击"""
        return get_hotkey_object().call_method('Click', (self.target, int(index)))

    def set(self, value = ''):
        """按值类型自动调用 set_value 或 set_string"""
        if isinstance(value, (int, float, bool)):
            return self.set_value(value)
        return self.set_string(str(value))

    def set_string(self, value: str = ''):
        """用字符串设置控件值（选项/文本框/复选框等）"""
        value = str(value)
        if cast(self.target, wclass.checkbox):
            if value.lower() in ('true', '1'):
                return self.select(1)
            elif value.lower() in ('false', '0'):
                return self.select(0)
            else:
                return self.select(int(value))

        elif cast(self.target, wclass.slider):
            return self.set_value(float(value))

        elif cast(self.target, wclass.option):
            self.target.set_selected_option(value)
            self.target.on_selection_changed.broadcast(value, unreal.SelectInfo.ON_MOUSE_CLICK)
            return True

        elif cast(self.target, wclass.textbox):
            self.target.set_text(value)
            self.target.on_text_changed.broadcast(value)
            self.target.on_text_committed.broadcast(value, unreal.TextCommit.ON_ENTER)
            return True

        elif cast(self.target, wclass.prop):
            prop_name = self.target.get_property_name()
            outer_widget = unreal.UserWidgetFunctionLibrary.get_outer_user_widget(self.target)
            value = eval(value)
            unreal.log(f"设置属性 {prop_name} 的值为 {value}")
            outer_widget.set_editor_property(prop_name, value)
            self.target.on_property_changed.broadcast(prop_name)
            return True

    def set_value(self, value: float = 0.0):
        """用数值设置控件值（滑块/复选框/选项等）"""
        if cast(self.target, wclass.checkbox):
            return self.select(int(value))

        elif cast(self.target, wclass.slider):
            self.target.set_value(float(value))
            self.target.on_value_changed.broadcast(float(value))
            return True

        elif cast(self.target, wclass.option):
            return self.select(int(value))

        elif cast(self.target, wclass.textbox):
            return self.set_string(str(value))

    def select(self, index: int = 0) -> bool:
        """用整数设置选项"""
        if cast(self.target, wclass.checkbox):
            state = unreal.CheckBoxState.UNDETERMINED
            if index > 0:
                state = unreal.CheckBoxState.CHECKED
            elif index == 0:
                state = unreal.CheckBoxState.UNCHECKED
            self.target.set_checked_state(state)
            self.target.on_check_state_changed.broadcast(index > 0)
            return True

        elif cast(self.target, wclass.slider):
            return self.set_value(float(index))

        elif cast(self.target, wclass.option):
            option_count = self.target.get_option_count()
            if index < 0:
                index = option_count + index
            index = max(0, min(index, option_count - 1))
            self.target.set_selected_index(index)
            string = self.target.get_option_at_index(index)
            self.target.on_selection_changed.broadcast(string, unreal.SelectInfo.ON_MOUSE_CLICK)
            return True

        elif cast(self.target, wclass.MCimage):
            state = self.target.get_editor_property('当前状态')
            if index == state:
                return True
            if index > 0:
                self.click() #左键点击
            elif index < 0:
                self.click(1) #右键点击
            elif state > 0:
                self.click() #左键点击还原为0
            else:
                self.click(1) #右键点击还原为0
            return True

        return False



class panel(MineprepAddonHandle):
    def __init__(self, name = ''):
        """按名称获取插件面板控件；空名称时打印所有可用面板"""
        label = name
        target = None
        if not name:
            id_cls_map = {k:bpclass(v).get_name() for k,v in mc_widget.WidgetsCache.items() if v}
            prints(tooltip('所有插件面板'), id_cls_map)
            return

        target = mc_widget.WidgetsCache.get(name)
        if not target:
            candidate = [k for k in mc_widget.WidgetsCache.keys() if name.lower() in k.lower()]
            warn(tooltip('未找到面板', name), '---------------', tooltip('你可能在寻找'), candidate)
        super().__init__(target, label)


def _panel_material_parameters(rows=None):
    """Read checked rows, or all explicitly named shortcut rows, without changing UI."""
    parameters = {}
    for path in tuple(mc_widget.WidgetsCache):
        if not path.startswith('材质参数_') or not path.endswith('.🔲启用'):
            continue
        root = path.rsplit('.', 1)[0]
        if rows is not None:
            if root not in rows:
                continue
        elif panel(path).get(int) != 1:
            continue
        row = unreal.UserWidgetFunctionLibrary.get_outer_user_widget(panel(path).target)
        name = str(row.get_editor_property('解析参数名'))
        if name in ('', 'None'):
            continue
        channel = row.get_editor_property('解析颜色通道')
        if channel == 4:
            color = panel(root + '.颜色选择框').get()
            parameters[name] = [color.r, color.g, color.b, color.a]
        elif channel == -1:
            parameters[name] = panel(root + '.➖滑条').get(float)
        else:
            parameters.setdefault(name, [None] * 4)[channel] = panel(root + '.➖滑条').get(float)
    return parameters


def prep_from_browser(action='sharpen', *, resource_pack=None, save=True):
    """一次性读取内容浏览器资产并准备；不递归文件夹，不改变主面板范围开关。

    action 为 sharpen/replace_textures；换包未传路径时选包，取消返回 None 且不修改配置。
    返回共用互斥的 AsyncTaskRunner，save=True 成功后保存全部脏资源和关卡。
    """
    running = mc_prep._running_preparation()
    if running is not None:
        return running
    if action not in ('sharpen', 'replace_textures'):
        raise ValueError('未知资产准备动作: ' + str(action))
    assets = tuple(unreal.EditorUtilityLibrary.get_selected_assets())
    if not assets:
        raise ValueError('请先在内容浏览器选择需要处理的资产')
    if action == 'replace_textures' and resource_pack is None:
        resource_pack = askdirectory(title='选择 Minecraft 资源包')
        if not resource_pack:
            return None
        resource_pack = Path(resource_pack).expanduser().resolve()
        if not resource_pack.is_dir():
            raise NotADirectoryError(resource_pack)
        mc_config.config.load()
        settings = dict(mc_config.config.config_dict.get('Settings', {}))
        settings['texture_pack_path'] = str(resource_pack)
        mc_config.config['Settings'] = settings
        if 'ue材质包路径' in mc_widget.WidgetsCache:
            panel('ue材质包路径').set(str(resource_pack))
    return prepare_assets(assets, action=action, resource_pack=resource_pack, save=save)


def prep_from_panel(action='prepare', *, import_format=None):
    """读取旧面板的一次性准备配置，处理场景选中 Actor；不触发旧蓝图流程。

    action 选择 prepare/replace/scene/import_world、四个效果或碰撞/法线/渐变动作。
    普通准备读取明确勾选行；快捷动作只读所属设置，不读等级或无关参数行。
    import_world 固定等级1，格式1强制平直法线；scene/import_world 成功后全部保存。
    返回 AsyncTaskRunner，忙碌时返回当前任务；内容浏览器资产模式不支持。
    """
    effect_rows = {
        'enchant': ('材质参数_附魔颜色', '材质参数_附魔缩放', '材质参数_附魔速度', '材质参数_附魔对比度'),
        'wind': ('材质参数_摇摆速度', '材质参数_摇摆幅度'),
        'translucent': ('材质参数_不透明度',),
        'emissive': ('材质参数_发光亮度', '材质参数_照明强度'),
    }
    geometry_controls = {'collision': '🔲启用碰撞', 'complex_collision': '🔲复杂碰撞',
                         'flat_shading': '🔲平直着色'}
    if action not in ('prepare', 'replace', 'scene', 'import_world', 'interpolate', *effect_rows, *geometry_controls):
        raise ValueError('未知准备动作: ' + str(action))
    running = mc_prep._running_preparation()
    if running is not None:
        return running
    quality = panel('➖动态准备材质_滑条')
    if quality.target is None:
        raise RuntimeError('请先打开 Mineprep 旧面板')
    if action == 'import_world':
        if type(import_format) is not int:
            raise ValueError('import_world 需要传入整数 import_format；1 为 jmc2obj')
        scope = ('static',)
    else:
        if panel('🔲内容浏览器选中项').get(int) == 1:
            raise ValueError('当前材质入口只处理场景组件，请取消“内容浏览器选中项”')
        if panel('🔲视口选中项').get(int) != 1:
            raise ValueError('请勾选“视口选中项”，当前材质入口不处理内容浏览器资产')
        scope = tuple(kind for kind, control in (
            ('static', '🔲方块材质'), ('skeletal', '🔲生物材质'), ('overlay', '🔲覆层材质'))
            if panel(control).get(int) == 1)
        if not scope:
            raise ValueError('请至少勾选一种材质范围：方块、生物或覆层')
    targets = tuple(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_selected_level_actors())
    if not targets:
        raise ValueError('请先在场景中选择需要处理的 Actor')
    if action in geometry_controls:
        return mc_prep._prepare_scene_shortcut(targets, action, panel(geometry_controls[action]).get(int), scope)
    if action == 'interpolate':
        return prepare_materials(targets, scope=scope, effect=action,
            parameters={mc_prep.ANIMATION_PARAMETER_NAME:
                        (None, None, None, int(panel('🔲渐变动画纹理').get(int) == 1))})
    if action in effect_rows:
        if action == 'enchant' and panel('🔲祛魔').get(int) == 1:
            return prepare_materials(targets, scope=scope, effect='disenchant')
        return prepare_materials(targets, scope=scope, effect=action,
            parameters=_panel_material_parameters(effect_rows[action]))
    level = 1 if action == 'import_world' else int(quality.get(float))
    parameters = _panel_material_parameters()
    if action == 'replace':
        resource_pack = panel('ue材质包路径').get(str)
        return replace_materials(targets, resource_pack, level=level, parameters=parameters, scope=scope)
    if action in ('scene', 'import_world'):
        collision = panel('🔲启用碰撞').get(int)
        complexity = panel('🔲复杂碰撞').get(int)
        return prepare_scene(targets, collision=None if collision == -1 else collision == 1,
            complex_collision=None if complexity == -1 else complexity == 1,
            flat_shading=(action == 'import_world' and import_format == 1)
                         or panel('🔲平直着色').get(int) == 1,
            level=level, parameters=parameters, scope=scope)
    return prepare_materials(targets, level=level, parameters=parameters, scope=scope)


class toolbar(MineprepAddonHandle):
    def __init__(self, name = ''):
        """触发工具栏按钮"""
        get_hotkey_object().call_method('Toolbar', (str(name),))
        super().__init__(None, name)

class hotkey(MineprepAddonHandle):
    def __init__(self, name = ''):
        """执行自定义快捷键。不带名称时打印全部快捷键；有名称时优先运行保存的代码，代码为空时调用蓝图同名函数。"""
        from mods.EditorShortcuts.ops import execute_shortcut, get_shortcuts
        if not name:
            lines = [str(tooltip('所有快捷键'))]
            for shortcut_name, item in get_shortcuts().items():
                lines.append(shortcut_name)
                lines.append(f"  {i18n.hotkey.chord('按键', 'Chord')}: {self._chord_label(item.get('chord_text', ''))}")
                lines.append(f"  {i18n.hotkey.tooltip('提示', 'Tooltip')}: {item.get('tooltip', '')}")
                lines.append('')
            prints('\n'.join(lines), duration=8)
            return
        execute_shortcut(str(name))
        super().__init__(None, name)

    @staticmethod
    def _chord_label(chord_text: str) -> str:
        if not chord_text:
            return ''
        chord = unreal.InputChord()
        if not chord.import_text(chord_text):
            return chord_text
        return str(unreal.InputLibrary.input_chord_get_display_name(chord))

###########################################################################

def _path_coordinates(point):
    return (point.x, point.y, point.z) if isinstance(point, unreal.Vector) else point


def orbit(center, samples, *, radius, height=0, turns=1, start_angle=0, roll=0, duration=None):
    """返回环绕位置、连续旋转，可选厘米每秒的速度。"""
    positions, rotations, *velocity = mc_math.orbit(
        _path_coordinates(center), samples, radius=radius, height=height, turns=turns,
        start_angle=start_angle, roll=roll, duration=duration)
    result = ([unreal.Vector(*position) for position in positions],
              [unreal.Rotator(pitch=pitch, yaw=yaw, roll=roll) for pitch, yaw, roll in rotations])
    if duration is not None:
        return (*result, [unreal.Vector(*value) for value in velocity[0]])
    return result


def spline(points, samples, *, closed=False, uniform_speed=False, tangents=False, duration=None):
    """返回通过航点的路径，可选单位切线或厘米每秒的速度。"""
    result = mc_math.spline((_path_coordinates(point) for point in points), samples,
                            closed=closed, uniform_speed=uniform_speed, tangents=tangents, duration=duration)
    if tangents or duration is not None:
        positions, vectors = result
        return [unreal.Vector(*point) for point in positions], [unreal.Vector(*vector) for vector in vectors]
    return [unreal.Vector(*point) for point in result]


def spawn_helper(button='', target='', loc=None, rot=None, scale=None, id=None) -> unreal.Actor:
    """通过生成器面板放置 Actor，可指定位置/旋转/缩放"""
    is_inventory = button in ('放置方块', '放置物品')
    mcvars.SpawnIDCache = None if is_inventory else (id if id else target if isinstance(target, int) else None)
    mcvars.SpawnNameCache = target if isinstance(target, str) else None
    mcvars.ActorCache = None

    try:
        option_widget = panel(f'生成器子面板.{button}选项')
        should_click = True
        if is_inventory:
            if isinstance(target, str):
                if target:
                    import mc_inventory

                    category = 'Blocks' if button == '放置方块' else 'Items'
                    should_click = bool(mc_inventory.select_option_by_target(option_widget.target, category, target))
            elif target:
                should_click = False
        else:
            option_widget.set_string(target)

        if should_click:
            panel(f'生成器子面板.{button}_可右键').click(0)
    finally:
        mcvars.SpawnIDCache = None
        mcvars.SpawnNameCache = None
    actor = mcvars.ActorCache

    if not actor:
        warn(i18n.spawn.target_missing('{button}: {target} 不存在', '{button}: {target} does not exist').format(
            button=str(button), target=str(target)))
        return None
    if loc:
        actor.set_actor_location(loc, False, True)
    if rot:
        actor.set_actor_rotation(rot, True)
    if scale:
        actor.set_actor_scale3d(scale)
    return actor


def spawn_block(target='', loc=None, rot=None, scale=None) -> unreal.Actor:
    """放置单个方块"""
    return spawn_helper('放置方块', target, loc, rot, scale)

def spawn_item(target='', loc=None, rot=None, scale=None) -> unreal.Actor:
    """放置物品"""
    return spawn_helper('放置物品', target, loc, rot, scale)

def spawn_mob(target='', loc=None, rot=None, scale=None, baby=False, id: int=None) -> unreal.Actor:
    """放置生物, 指定id时忽略target名称"""
    panel("生成器子面板.生物宝宝_可点击").select(int(baby))
    return spawn_helper('放置生物', target, loc, rot, scale, id)

def spawn_preset(target='', loc=None, rot=None, scale=None, id: int=None) -> unreal.Actor:
    """放置预设素材, 指定id时忽略target名称"""
    return spawn_helper('预设素材', target, loc, rot, scale, id)

def attach(target='', loc=None, rot=None, scale=None, id: int=None) -> unreal.Actor:
    """附加组件至选中项, 指定id时忽略target名称"""
    return spawn_helper('附加组件', target, loc, rot, scale, id)


def spawn_blocks(mesh=None, transforms=None, loc=(0,0,0), rot=(0,0,0), *, collision=None) -> unreal.Actor:
    """放置一个模型的实例；Transform 可为迭代器，仍采用 UE 厘米和局部变换。"""
    from mc_structure import _add_transform_instances
    if transforms is None:
        transforms = [unreal.Transform()]
    if isinstance(mesh, str):
        mesh = unreal.load_asset(mesh) if mesh.startswith('/') and not mesh.endswith('.json') else import_block(mesh)
        if not isinstance(mesh, unreal.StaticMesh):
            raise ValueError('spawn_blocks requires a StaticMesh or an importable block model')
    loaded_class = uclass('/Game/Mineprep/MC_Blueprint/Core/实例化方块.实例化方块')
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(loaded_class, loc, rot)
    if actor is None:
        raise RuntimeError('Cannot create instanced block Actor')
    ism = actor.root_component
    try:
        ism.set_editor_property('StaticMesh', mesh)
        if collision is not None:
            ism.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
            ism.set_editor_property('can_ever_affect_navigation', bool(collision))
        ism.clear_instances()
        _add_transform_instances(ism, transforms, update_navigation=collision is not False)
    except Exception:
        unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(actor)
        raise
    return actor

