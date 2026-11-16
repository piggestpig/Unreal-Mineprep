"""Minecraft 材质准备、默认规则与资源贴图识别；业务层不读取面板。"""
try:
    import unreal
except ModuleNotFoundError:
    from mc_utils import Lazy as unreal
import json
import re
import struct
from fnmatch import fnmatchcase
from pathlib import Path

from mc_config import paths
from mc_utils import debug, show_editor_task
from mc_material import material_parameter_type, get_material_param, set_material_param, tex_source_files, _set_material_param
from mc_parallel import asynctask

ANIMATION_PARAMETER_NAME = '动画速度/步长/列数/渐变'

MCprepDataCache = None

_active_preparation = None


def _running_preparation():
    """Return the current job before reading new targets or panel settings."""
    if _active_preparation is not None:
        unreal.log_warning('已有准备任务正在运行；忽略本次新目标和参数')
        return _active_preparation.runner
    return None


class _PreparationTask:
    """One runner and optional notification shared by preparation entry points."""

    def __init__(self, title, notify):
        self.title = self.text = title
        self.runner = self.notification = None
        self.started = not notify
        self.finished = self.native_cancel = False
        self.success = False

    def begin(self, notification):
        self.notification = notification
        self.started = True
        notification.set_task_notification_text(self.text)
        if self.finished:
            notification.finish_executing_task(self.success)

    def stage(self, text):
        self.text = f'{self.title}：{text}'
        if self.notification is not None and self.started and not self.finished:
            self.notification.set_task_notification_text(self.text)

    def cancel(self, notification):
        # UE finishes its notification after this callback; do not finish it twice.
        self.native_cancel = True
        self.runner.destroy()

    def finish(self, success, state):
        global _active_preparation
        self.stage(state)
        self.success = success
        self.finished = True
        if _active_preparation is self:
            _active_preparation = None
        if self.notification is not None and self.started and not self.native_cancel:
            self.notification.finish_executing_task(success)

    @asynctask
    def run(self, steps):
        success, state = False, '已取消，保留已完成修改'
        try:
            yield  # Return the runner before any work, including queued notification startup.
            while not self.started:
                yield
            result = yield from steps
            success, state = True, '完成'
            return result
        except Exception:
            state = '失败，详情见输出日志'
            raise
        finally:
            steps.close()
            self.finish(success, state)


def _start_preparation(title, steps, *args, notify=True):
    global _active_preparation
    task = _PreparationTask(title, notify)
    _active_preparation = task
    try:
        if notify:
            task.notification = show_editor_task(title, begin=task.begin, cancel=task.cancel)
        task.runner = task.run(steps(*args, task))
        return task.runner
    except Exception:
        task.finish(False, '启动失败')
        raise

def load_mcprep_data():
    """加载并缓存 mcprep_data.json"""
    global MCprepDataCache
    if MCprepDataCache:
        return MCprepDataCache
    with open(paths.mcprep_data, 'r') as f:
        MCprepDataCache = json.load(f)
    return MCprepDataCache


def _apply_emission_default(mat, texture_source):
    """若贴图名称匹配 mcprep_data.json 的自发光列表，则将材质的“发光亮度”默认设为 0.1。"""
    if texture_source is None:
        return
    name = str(texture_source).replace('\\', '/').lower()
    if '/textures/' in name:
        name = name.split('/textures/', 1)[1]
    if name.endswith('.png'):
        name = name[:-4]
    candidates = (name, Path(name).name)
    if any(fnmatchcase(candidate, str(pattern).replace('\\', '/').lower())
           for pattern in load_mcprep_data()['blocks']['emit'] for candidate in candidates):
        set_material_param(mat, '发光亮度', 0.1)
        return True
    return False


def prep_texture(tex, compression=unreal.TextureCompressionSettings.TC_EDITOR_ICON, detect_normal=False) -> unreal.Texture:
    """将贴图设为最近邻过滤并刷新，适合像素风材质。

    detect_normal 为 True 时按资产名是否以 _n 结尾区分法线与颜色贴图，
    并盖掉导入时引擎对蓝色贴图的法线误判。
    """
    props = dict(filter=unreal.TextureFilter.TF_NEAREST,
                 compression_settings=compression,
                 oodle_preserve_extremes=True)

    if detect_normal:
        if tex.get_name().endswith('_n'):
            props.update(compression_settings=unreal.TextureCompressionSettings.TC_NORMALMAP,
                         srgb=False, lod_group=unreal.TextureGroup.TEXTUREGROUP_WORLD_NORMAL_MAP)
        else:
            props.update(srgb=True, lod_group=unreal.TextureGroup.TEXTUREGROUP_WORLD)
    tex.set_editor_properties(props)

    finish = getattr(getattr(unreal, 'mineprep', None), 'finish_build_texture', None)
    if finish:
        finish(tex)
    else:
        unreal.LandmassBlueprintFunctionLibrary.force_update_texture(tex)
    return tex


def colorize_material(mat, color=None, *, texture_source=None):
    """设置材质实例“纹理颜色”；未指定时按 mcprep 去饱和色表匹配"""
    if color is not None:
        set_material_param(mat, '纹理颜色', color)
        return

    color_dict = load_mcprep_data()['blocks']['desaturated']
    mat_name = (Path(texture_source).stem if texture_source is not None
                else re.sub(r'[^a-zA-Z0-9_]', '', mat.get_name()))
    if mat_name in color_dict:
        r, g, b = color_dict[mat_name]
        color = unreal.LinearColor(r, g, b, 1.0)
        set_material_param(mat, '纹理颜色', color)
    elif texture_source is not None:
        set_material_param(mat, '纹理颜色', unreal.LinearColor(1, 1, 1, 1))


def _read_png_size(source) -> tuple[int, int]:
    """读取 PNG 宽高"""
    with source.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Not a PNG file")
    width, height = struct.unpack(">II", header[16:24])
    return int(width), int(height)


def _animation_step(indices, frame_count):
    """识别序列帧是顺序循环 (1) 还是往返循环 (-1)，不支持的自定义帧序返回 None。"""
    count = len(indices)
    if count == frame_count and all(indices[(i+1) % count] == (value+1) % frame_count
                                    for i, value in enumerate(indices)):
        return 1
    if count == 2*(frame_count-1) and indices.count(0) == 1:
        start = indices.index(0)
        expected = (*range(frame_count), *range(frame_count-2, 0, -1))
        if all(indices[(start+i) % count] == value for i, value in enumerate(expected)):
            return -1
    return None


def _texture_animation(texture_source):
    """解析贴图同名 .png.mcmeta 中的动画配置，返回 (播放速度, 步长, 是否插值)，无动画或格式不支持时返回 None。"""
    if texture_source is None:
        return None
    source = Path(texture_source)
    metadata = Path(str(source) + '.mcmeta')
    if source.suffix.lower() != '.png' or not metadata.is_file():
        return None

    def positive(value):
        return type(value) is int and 0 < value <= 2**31-1

    try:
        raw = json.loads(metadata.read_text(encoding='utf-8-sig'))
        if isinstance(raw, dict) and 'animation' not in raw:
            return None
        animation = raw.get('animation')
        frametime = animation.get('frametime', 1)
        interpolate = animation.get('interpolate', False)
        width, height = _read_png_size(source)
        # MC 规范：只指定宽或高时，另一维默认取整张贴图尺寸
        fw = animation.get('width', width if 'height' in animation else min(width, height))
        fh = animation.get('height', height if 'width' in animation else min(width, height))
    except (OSError, ValueError, AttributeError) as exc:
        debug(f'Animation metadata skipped: {metadata}: {exc}')
        return None
    if not all(positive(v) for v in (fw, fh, frametime)) or type(interpolate) is not bool:
        debug(f'Animation metadata skipped: {metadata}: invalid dimensions, frametime or interpolate')
        return None
    if width <= 0 or height <= width or height % width or fw != width or fh != width:
        debug(f'Animation metadata skipped: {metadata}: only vertical square-frame strips are supported')
        return None

    duration, step = frametime, 1
    notes = []
    if 'frames' in animation:
        frames = animation['frames']
        if not isinstance(frames, list) or not frames:
            debug(f'Animation metadata: {metadata}: custom frames ignored: expected a nonempty list')
            return 20.0/frametime, 1, int(interpolate)
        indices, times = [], []
        for frame in frames:
            index = frame.get('index') if isinstance(frame, dict) else frame
            time = frame.get('time', frametime) if isinstance(frame, dict) else frametime
            if type(index) is not int or not 0 <= index < height//width or not positive(time):
                debug(f'Animation metadata: {metadata}: custom frames ignored: invalid index or time')
                return 20.0/frametime, 1, int(interpolate)
            indices.append(index)
            times.append(time)
        if len(set(times)) == 1:
            duration = times[0]
        else:
            notes.append('variable frame times ignored; using global frametime')
        recognized = _animation_step(indices, height//width)
        if recognized is None:
            notes.append('custom frame order ignored; using forward playback')
        else:
            step = recognized
    if notes:
        debug(f'Animation metadata: {metadata}: ' + '; '.join(notes))
    return 20.0/duration, step, int(interpolate)


def _apply_texture_animation(material, texture_source):
    """根据 .png.mcmeta 将序列帧动画参数写入材质实例。"""
    values = _texture_animation(texture_source)
    if values is None:
        return
    if material_parameter_type(material, ANIMATION_PARAMETER_NAME) != 'vector':
        debug(f'Animation parameter not found: {ANIMATION_PARAMETER_NAME}: {texture_source}')
        return
    fps, step, interpolate = values
    flow = Path(texture_source).stem.lower() in {'lava_flow', 'water_flow'}
    set_material_param(
            material, ANIMATION_PARAMETER_NAME,
            unreal.LinearColor(fps, 2 if flow else step, 2 if flow else 1, interpolate))
    return True


def apply_mc_material_defaults(material, texture_source):
    """按源贴图应用染色、默认发光和动画布局；清理上一张图的自动值。

    支持 MIC/MID，只更新目标声明的参数。用户覆盖值应在本调用之后应用。
    不改变父材质、绑定贴图或保存资产；不支持的动画布局按静态图处理。
    """
    if material_parameter_type(material, '纹理颜色') == 'vector':
        colorize_material(material, texture_source=texture_source if texture_source is not None else '')
    if material_parameter_type(material, '发光亮度') == 'scalar':
        if not _apply_emission_default(material, texture_source):
            set_material_param(material, '发光亮度', 0.0)
    if material_parameter_type(material, ANIMATION_PARAMETER_NAME) == 'vector':
        if not _apply_texture_animation(material, texture_source):
            set_material_param(material, ANIMATION_PARAMETER_NAME, unreal.LinearColor(0, 1, 1, 0))
    return material


def _texture_id(value):
    """从规范标识或旧源路径恢复 namespace:texture/path，不要求源文件仍存在。"""
    value = str(value).replace('\\', '/').strip()
    match = re.search(r'(?:^|/)assets/([^/]+)/textures/(.+)$', value)
    if match:
        value = match[1] + ':' + match[2]
    elif '/textures/' in value:
        value = 'minecraft:' + value.split('/textures/', 1)[1]
    elif value.startswith('textures/'):
        value = 'minecraft:' + value[len('textures/'):]
    elif ':' not in value and '/' in value and not value.startswith('/'):
        value = 'minecraft:' + value
    value = re.sub(r'\.(png|jpg|jpeg)$', '', value, flags=re.I)
    if not re.fullmatch(r'[a-z0-9_.-]+:[a-z0-9_./-]+', value):
        return None
    _, path = value.split(':', 1)
    if any(part in ('', '.', '..') for part in path.split('/')):
        return None
    return value


def _mapped_texture_id(name):
    name = re.sub(r'\.(?:png|jpg|jpeg)$', '', str(name), flags=re.I)
    name = re.sub(r'\.\d+$', '', name).removeprefix('minecraft_block-')
    blocks = load_mcprep_data()['blocks']
    for table in ('block_mapping_mc', 'block_mapping_jmc', 'block_mapping_mineways'):
        mapping = blocks[table]
        value = mapping.get(name, mapping.get(name.lower()))
        if value:
            return _texture_id(value if '/' in value or ':' in value else 'block/' + value)
    return None


def identify_mc_texture(target):
    """从材质/Texture2D/源路径识别 MC 纹理标识，无法识别返回 None。

    优先使用绑定的「纹理贴图」、规范来源路径，再使用 MCprep 名称映射。
    保留 namespace 与 block/item/entity 等完整路径，不搜索同名图片。
    """
    material = target if isinstance(target, unreal.MaterialInterface) else None
    if material is not None:
        target = get_material_param(material, '纹理贴图')
    if isinstance(target, unreal.Texture2D):
        tagged = unreal.EditorAssetLibrary.get_metadata_tag(target, 'Mineprep.TextureID')
        if tagged:
            return _texture_id(tagged)
        identities = {identity for source in tex_source_files(target)
                      if (identity := _texture_id(source)) is not None}
        if len(identities) > 1:
            return None
        if identities:
            return identities.pop()
        name = target.get_name()
    elif isinstance(target, (str, Path)):
        identity = _texture_id(target)
        if identity:
            return identity
        name = str(target).replace('\\', '/').rsplit('/', 1)[-1]
    else:
        name = ''
    return _mapped_texture_id(name) or (_mapped_texture_id(material.get_name()) if material else None)


def resolve_mc_texture(texture_id, resource_pack):
    """在指定资源包中精确查找纹理，返回 id/base/normal/specular/mcmeta。

    接收 namespace:path 或默认命名空间下的分类路径；base 不存在时抛出
    FileNotFoundError，缺失的辅助贴图和元数据返回 None，不做递归同名回退。
    """
    identity = _texture_id(texture_id)
    if identity is None:
        raise ValueError('需要带分类的纹理标识，例如 minecraft:block/stone')
    namespace, name = identity.split(':', 1)
    root = Path(resource_pack).expanduser().resolve()
    directories = [root / 'assets' / namespace / 'textures', root / namespace / 'textures']
    if namespace == 'minecraft':
        directories.append(root / 'textures')
    base = next((directory / (name + extension) for directory in directories
                 for extension in ('.png', '.jpg', '.jpeg')
                 if (directory / (name + extension)).is_file()), None)
    if base is None:
        raise FileNotFoundError(f'{identity}: {root}')
    normal = base.with_name(base.stem + '_n.png')
    specular = base.with_name(base.stem + '_s.png')
    mcmeta = Path(str(base) + '.mcmeta')
    return dict(id=identity, base=base, normal=normal if normal.is_file() else None,
                specular=specular if specular.is_file() else None,
                mcmeta=mcmeta if mcmeta.is_file() else None)


# Exact template boundaries keep profile defaults out of copied user overrides.
_LABPBR_FAMILIES = (
    tuple(f'/Game/Mineprep/材质/Core/LabPBR{i}_{label}_材质实例'
          for i, label in enumerate(('基础', '动画', '附魔摇摆', '视差'), 1)),
    tuple(f'/Game/Mineprep/材质/Core/LabPBR单面{i}_材质实例' for i in range(1, 5)),
    tuple(f'/Game/Mineprep/材质/半透明Core/LabPBR半透明{i}_Inst' for i in range(1, 5)),
)
_LABPBR_TEMPLATES = {f'{path}.{path.rsplit("/", 1)[-1]}': (family, level)
                     for family in _LABPBR_FAMILIES for level, path in enumerate(family, 1)}
_TEXTURE_PARAMETERS = {'base': '纹理贴图', 'normal': '法线贴图', 'specular': '高光贴图'}
_DEFAULT_PBR_TEXTURES = {
    'normal': '/Game/Mineprep/材质/Core/Tex/LabPBR法线默认贴图_n',
    'specular': '/Game/Mineprep/材质/Core/Tex/LabPBR高光默认贴图_s',
}


def _parameter_value(value):
    if isinstance(value, unreal.LinearColor):
        return (value.r, value.g, value.b, value.a)
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return value


def _labpbr_source(material):
    """Keep effective sidedness, and parameter overrides below the template only."""
    overrides = {}
    two_sided = None
    while isinstance(material, unreal.MaterialInstance):
        base = material.get_editor_property('base_property_overrides')
        if two_sided is None and base.get_editor_property('override_two_sided'):
            two_sided = base.get_editor_property('two_sided')
        profile = _LABPBR_TEMPLATES.get(material.get_path_name())
        if profile:
            family, level = profile
            if family in _LABPBR_FAMILIES[:2] and two_sided is not None:
                family = _LABPBR_FAMILIES[0 if two_sided else 1]
            return family, level, overrides
        for kind in ('scalar', 'vector', 'texture'):
            for entry in material.get_editor_property(kind + '_parameter_values'):
                info = entry.parameter_info
                if info.association == unreal.MaterialParameterAssociation.GLOBAL_PARAMETER:
                    name = str(info.name)
                    overrides.setdefault(name, _parameter_value(entry.parameter_value))
        material = material.get_editor_property('parent')
    return None


def _ordinary_source(material):
    """Extract the first BaseColor texture and obvious multipliers; keep the source intact."""
    root = material
    two_sided = blend_mode = None
    while isinstance(root, unreal.MaterialInstance):
        props = root.get_editor_property('base_property_overrides')
        if two_sided is None and props.get_editor_property('override_two_sided'):
            two_sided = props.get_editor_property('two_sided')
        if blend_mode is None and props.get_editor_property('override_blend_mode'):
            blend_mode = props.get_editor_property('blend_mode')
        root = root.get_editor_property('parent')
    if not isinstance(root, unreal.Material):
        return None
    library = unreal.MaterialEditingLibrary
    base_color = library.get_material_property_input_node(root, unreal.MaterialProperty.MP_BASE_COLOR)

    def inputs(node):
        return library.get_inputs_for_material_expression(root, node)

    texture_node = texture = None
    pending, visited = [base_color], set()
    while pending:
        node = pending.pop()
        if node is None or node in visited:
            continue
        visited.add(node)
        if isinstance(node, unreal.MaterialExpressionTextureSample):
            value = (get_material_param(material, str(node.get_editor_property('parameter_name')))
                     if isinstance(node, unreal.MaterialExpressionTextureSampleParameter)
                     else node.get_editor_property('texture'))
            if isinstance(value, unreal.Texture2D):
                texture_node, texture = node, value
                break
        pending.extend(reversed(inputs(node)))
    if texture is None:
        return None

    def value(node):
        if isinstance(node, unreal.MaterialExpressionConstant):
            return node.get_editor_property('r')
        if isinstance(node, (unreal.MaterialExpressionConstant3Vector, unreal.MaterialExpressionConstant4Vector)):
            return _parameter_value(node.get_editor_property('constant'))
        if isinstance(node, (unreal.MaterialExpressionScalarParameter, unreal.MaterialExpressionVectorParameter)):
            return _parameter_value(get_material_param(material, str(node.get_editor_property('parameter_name'))))
        return None

    def factors(node):
        if isinstance(node, unreal.MaterialExpressionMultiply):
            result = []
            for child, name in zip(inputs(node), ('const_a', 'const_b')):
                result.extend(factors(child) if child is not None else [node.get_editor_property(name)])
            return result
        if isinstance(node, unreal.MaterialExpressionReroute):
            return factors(inputs(node)[0])
        return [node]

    overrides = {}
    terms = factors(base_color)
    if texture_node in terms:
        tint, vertex_color = [1.0, 1.0, 1.0], False
        for term in terms:
            vertex_color |= isinstance(term, unreal.MaterialExpressionVertexColor)
            multiplier = term if isinstance(term, (int, float)) else value(term)
            if multiplier is not None:
                for channel in range(3):
                    tint[channel] *= multiplier[channel] if isinstance(multiplier, tuple) else multiplier
        overrides['纹理颜色'] = (*tint, 1.0)
        overrides['顶点颜色'] = float(vertex_color)
    blend_mode = root.get_editor_property('blend_mode') if blend_mode is None else blend_mode
    two_sided = root.get_editor_property('two_sided') if two_sided is None else two_sided
    translucent = blend_mode in (unreal.BlendMode.BLEND_TRANSLUCENT,
                                unreal.BlendMode.BLEND_TRANSLUCENT_COLORED_TRANSMITTANCE)
    opacity = value(library.get_material_property_input_node(root,
        unreal.MaterialProperty.MP_OPACITY if translucent else unreal.MaterialProperty.MP_OPACITY_MASK))
    if isinstance(opacity, (int, float)):
        overrides['不透明R~G+B*A'] = (None, None, None, opacity)
    family = _LABPBR_FAMILIES[2 if translucent else 0 if two_sided else 1]
    return family, overrides, texture


def _material_components(targets):
    targets = getattr(targets, 'target', targets)
    if isinstance(targets, (unreal.Actor, unreal.MeshComponent)):
        targets = (targets,)
    found = {}
    for target in targets:
        target = getattr(target, 'target', target)
        if isinstance(target, unreal.Actor):
            components = target.get_components_by_class(unreal.MeshComponent)
        elif isinstance(target, unreal.MeshComponent):
            components = (target,)
        else:
            raise TypeError('targets 需要 Actor、MeshComponent 或它们的集合')
        for component in components:
            found[component.get_path_name()] = component
    return tuple(found.values())


def _ordinary_component(component, scope):
    return (scope is None
            or ('static' in scope and isinstance(component, unreal.StaticMeshComponent))
            or ('skeletal' in scope and isinstance(component, unreal.SkeletalMeshComponent)))


def _material_slots(component, scope=None):
    if _ordinary_component(component, scope):
        for index in range(component.get_num_materials()):
            yield 'material', index, component.get_material(index)
    if scope is not None and 'overlay' not in scope:
        return
    yield 'overlay', 0, component.get_overlay_material()
    overlays = list(component.get_editor_property('material_slots_overlay_material'))
    # Asset defaults are read, then written as component overrides; never edit the mesh.
    defaults = ()
    if isinstance(component, unreal.StaticMeshComponent) and component.static_mesh:
        defaults = component.static_mesh.get_editor_property('static_materials')
    elif isinstance(component, unreal.SkinnedMeshComponent) and component.get_skinned_asset():
        defaults = component.get_skinned_asset().get_editor_property('materials')
    for index in range(max(len(overlays), len(defaults))):
        material = overlays[index] if index < len(overlays) else None
        if material is None and index < len(defaults):
            material = defaults[index].overlay_material_interface
        yield 'slot_overlay', index, material


def _bind_material(component, kind, index, material):
    if kind == 'material':
        component.set_material(index, material)
    elif kind == 'overlay':
        component.set_overlay_material(material)
    else:
        overlays = list(component.get_editor_property('material_slots_overlay_material'))
        overlays.extend([None] * (index + 1 - len(overlays)))
        overlays[index] = material
        component.set_editor_property('material_slots_overlay_material', overlays)


def _asset_label(name):
    return re.sub(r'\W+', '_', str(name)).strip('_') or 'Resource'


def _texture_directory(component, resource_pack):
    mesh = None
    if isinstance(component, unreal.StaticMeshComponent):
        mesh = component.static_mesh
    elif isinstance(component, unreal.SkinnedMeshComponent):
        mesh = component.get_skinned_asset()
    if mesh is None:
        raise ValueError(f'换包需要组件绑定静态或骨骼网格资产: {component.get_path_name()}')
    return _asset_texture_directory(mesh, resource_pack)


def _asset_texture_directory(asset, resource_pack):
    asset_path = asset.get_path_name().split('.', 1)[0]
    if not asset_path.startswith('/Game/'):
        raise ValueError(f'请先将资产放入工程内容目录后换包: {asset_path}')
    pack = resource_pack.parent if resource_pack.name == 'assets' else resource_pack
    return asset_path.rsplit('/', 1)[0] + '/' + _asset_label(pack.name)


def _material_stem(source_material, identity, texture_source, kind, index):
    label = (identity.rsplit('/', 1)[-1] if identity else
             Path(texture_source).stem if texture_source else source_material.get_name())
    suffix = f'_{index}' if kind == 'material' else (
        '_Overlay' if kind == 'overlay' else f'_Overlay_{index}')
    return 'MID_' + _asset_label(label) + suffix


def _unique_mid_name(component, stem):
    name, index = stem, 1
    while unreal.find_object(component, name) is not None:
        name = f'{stem}_{index}'
        index += 1
    return name


def _prep_texture_name(identity, role):
    namespace, path = identity.split(':', 1)
    # Keep vanilla block names short; other categories and namespaces stay explicit.
    if namespace == 'minecraft' and path.startswith('block/'):
        path = path[len('block/'):]
    if namespace != 'minecraft':
        path = namespace + '/' + path
    suffix = {'base': '', 'normal': '_n', 'specular': '_s'}[role]
    return 'T_' + _asset_label(path) + suffix


def _import_prep_texture(source, role, identity, destination, imported):
    source = source.resolve()
    name = _prep_texture_name(identity, role)

    compression = (unreal.TextureCompressionSettings.TC_EDITOR_ICON if role == 'base'
                   else unreal.TextureCompressionSettings.TC_BC7)
    factory = unreal.TextureFactory()
    factory.set_editor_properties(dict(create_material=False, no_alpha=False,
                                       compression_settings=compression))
    task = unreal.AssetImportTask()
    task.set_editor_properties(dict(filename=str(source), destination_path=destination,
                                    destination_name=name, automated=True, replace_existing=True,
                                    replace_existing_settings=True, save=False, factory=factory))
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    objects = list(task.get_objects())
    if not objects or not isinstance(objects[0], unreal.Texture2D):
        raise RuntimeError(f'贴图导入失败: {source}')
    texture = objects[0]
    texture.set_editor_properties(dict(srgb=role == 'base', compression_no_alpha=False,
                                       flip_green_channel=False,
                                       lod_group=unreal.TextureGroup.TEXTUREGROUP_WORLD))
    prep_texture(texture, compression=compression)
    unreal.EditorAssetLibrary.set_metadata_tag(texture, 'Mineprep.TextureID', identity)
    if not unreal.EditorAssetLibrary.save_loaded_asset(texture):
        raise RuntimeError(f'贴图保存失败: {texture.get_path_name()}')
    imported.append(texture.get_path_name())
    return texture


def _parameter_kind(records, name):
    kinds = [kind for kind, names in records.items() if str(name).casefold() in names]
    if len(kinds) > 1:
        raise ValueError('材质参数名称对应多个类型: ' + str(name))
    return kinds[0] if kinds else None


def _apply_parameters(material, parameters, records):
    for name, value in parameters.items():
        kind = _parameter_kind(records, name)
        if kind is None:
            continue  # A different quality level may not declare this override.
        if isinstance(value, tuple) and any(v is None for v in value):
            current = material.get_vector_parameter_value(name)
            value = tuple(old if new is None else new for old, new in
                          zip((current.r, current.g, current.b, current.a), value, strict=True))
        _set_material_param(material, name, value, kind)


def _parameter_records(parent):
    """Resolve editor GUIDs once per template without flattening MID defaults.

    Runtime MID setters intentionally leave new entries' ExpressionGUID invalid;
    InlineMaterialInstance hides those entries. The engine exposes GUID rebuilding
    only for MICs, so use a transient MIC as the metadata source, never an asset.
    """
    properties = {'parent': parent}
    for kind, entry_type in (('scalar', unreal.ScalarParameterValue),
                             ('vector', unreal.VectorParameterValue),
                             ('texture', unreal.TextureParameterValue)):
        names = getattr(unreal.MaterialEditingLibrary, 'get_' + kind + '_parameter_names')(parent)
        getter = getattr(parent, 'get_' + kind + '_parameter_value')
        properties[kind + '_parameter_values'] = [entry_type(
            parameter_info=unreal.MaterialParameterInfo(name=name), parameter_value=getter(name))
            for name in names]
    metadata = unreal.MaterialInstanceConstant()
    metadata.set_editor_properties(properties)
    unreal.MaterialEditingLibrary.update_material_instance(metadata)
    return {kind: {str(entry.parameter_info.name).casefold(): entry.copy()
                   for entry in metadata.get_editor_property(kind + '_parameter_values')}
            for kind in ('scalar', 'vector', 'texture')}


def _sync_parameter_metadata(material, records):
    properties = {}
    for kind, by_name in records.items():
        entries = []
        for entry in material.get_editor_property(kind + '_parameter_values'):
            record = by_name.get(str(entry.parameter_info.name).casefold())
            if (record is not None
                    and entry.parameter_info.association == unreal.MaterialParameterAssociation.GLOBAL_PARAMETER):
                record = record.copy()
                record.parameter_info = entry.parameter_info
                record.parameter_value = entry.parameter_value
                entry = record
            entries.append(entry)
        properties[kind + '_parameter_values'] = entries
    material.set_editor_properties(properties)


def _save_preparation(task):
    task.stage('保存全部脏资源和关卡')
    yield  # Last cancellation opportunity before the synchronous editor save.
    if not unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True):
        raise RuntimeError('准备任务保存失败；已完成修改保留，请检查输出日志')
    return True


def _is_core_asset(asset):
    return asset.get_path_name().split('.', 1)[0].casefold().startswith('/game/mineprep/材质/core/')


def _sharpen_asset_textures(assets, report, task):
    materials, textures = set(), set()
    for asset in assets:
        path = asset.get_path_name()
        task.stage(f'收集贴图 · {asset.get_name()}')
        if isinstance(asset, unreal.Texture2D):
            used = [asset]
        else:
            if isinstance(asset, unreal.MaterialInterface):
                surfaces = [asset]
            elif isinstance(asset, (unreal.StaticMesh, unreal.SkeletalMesh)):
                slots = asset.get_editor_property('static_materials' if isinstance(asset, unreal.StaticMesh)
                                                 else 'materials')
                surfaces = [material for slot in slots for material in
                            (slot.material_interface, slot.overlay_material_interface) if material]
            else:
                report['skipped'].append(dict(asset=path, reason='unsupported_asset'))
                yield
                continue
            used = []
            for material in surfaces:
                if material not in materials:
                    materials.add(material)
                    if _is_core_asset(material):
                        report['skipped'].append(dict(asset=material.get_path_name(), reason='protected_core_asset'))
                    else:
                        used.extend(unreal.MaterialEditingLibrary.get_material_used_textures(material))
        for texture in used:
            if texture in textures:
                continue
            textures.add(texture)
            path = texture.get_path_name()
            if _is_core_asset(texture):
                report['skipped'].append(dict(asset=path, reason='protected_core_asset'))
            elif not isinstance(texture, unreal.Texture2D) or not path.startswith('/Game/'):
                report['skipped'].append(dict(asset=path, reason='non_project_texture'))
            elif texture.get_editor_property('filter') != unreal.TextureFilter.TF_NEAREST:
                task.stage(f'清晰化 · {texture.get_name()}')
                with unreal.ScopedEditorTransaction('Mineprep: sharpen texture'):
                    texture.modify()
                    texture.set_editor_property('filter', unreal.TextureFilter.TF_NEAREST)
                report['changed'].append(dict(asset=path, action='sharpen'))
            yield
        yield


def _replace_asset_textures(assets, resource_pack, report, task):
    textures = {}
    for number, material in enumerate(assets, 1):
        path = material.get_path_name()
        task.stage(f'材质实例 {number}/{len(assets)} · {material.get_name()}')
        if not isinstance(material, unreal.MaterialInstanceConstant) or not path.startswith('/Game/'):
            report['skipped'].append(dict(asset=path, reason='unsupported_asset'))
            yield
            continue
        if any(material_parameter_type(material, name) != 'texture' for name in _TEXTURE_PARAMETERS.values()):
            report['skipped'].append(dict(asset=path, reason='unsupported_material'))
            yield
            continue
        identity = identify_mc_texture(material)
        if identity is None:
            report['skipped'].append(dict(asset=path, reason='unknown_texture'))
            yield
            continue
        try:
            files = resolve_mc_texture(identity, resource_pack)
        except FileNotFoundError:
            report['skipped'].append(dict(asset=path, reason='missing_base', texture_id=identity))
            yield
            continue
        destination = _asset_texture_directory(material, resource_pack)
        bindings = {}
        for role, name in _TEXTURE_PARAMETERS.items():
            source = files[role]
            if source is None:
                bindings[name] = unreal.load_asset(_DEFAULT_PBR_TEXTURES[role])
            else:
                key = (destination, source, role)
                if key not in textures:
                    task.stage(f'导入 · {source.name}')
                    textures[key] = _import_prep_texture(source, role, identity, destination,
                                                        report['imported_assets'])
                    yield
                bindings[name] = textures[key]
        with unreal.ScopedEditorTransaction('Mineprep: replace material asset textures'):
            material.modify()
            for name, texture in bindings.items():
                _set_material_param(material, name, texture, 'texture')
            if material_parameter_type(material, ANIMATION_PARAMETER_NAME) == 'vector':
                if not _apply_texture_animation(material, files['base']):
                    _set_material_param(material, ANIMATION_PARAMETER_NAME,
                                        unreal.LinearColor(0, 1, 1, 0), 'vector')
            unreal.MaterialEditingLibrary.update_material_instance(material)
        report['changed'].append(dict(asset=path, action='replace_textures', texture_id=identity))
        yield


def _asset_steps(assets, action, resource_pack, save, task):
    report = dict(changed=[], skipped=[], imported_assets=[], saved=False)
    yield
    editable = []
    for asset in assets:
        if _is_core_asset(asset):
            report['skipped'].append(dict(asset=asset.get_path_name(), reason='protected_core_asset'))
        else:
            editable.append(asset)
    assets = tuple(editable)
    if action == 'sharpen':
        yield from _sharpen_asset_textures(assets, report, task)
    else:
        yield from _replace_asset_textures(assets, resource_pack, report, task)
    if save:
        report['saved'] = yield from _save_preparation(task)
    return report


def prepare_assets(assets, *, action='sharpen', resource_pack=None, save=True):
    """处理明确传入的资产，不读取选择或面板；返回共用互斥的 AsyncTaskRunner。

    sharpen 仅设工程贴图最近邻；replace_textures 原地更新 MC 参数约定的 MIC。
    result 为 changed/skipped/imported_assets/saved。取消保留已完成修改；换包纹理即时保存。
    save=True 成功后保存全部脏资源和关卡，包括其他编辑。
    """
    running = _running_preparation()
    if running is not None:
        return running
    if action not in ('sharpen', 'replace_textures'):
        raise ValueError('未知资产准备动作: ' + str(action))
    assets = getattr(assets, 'target', assets)
    if isinstance(assets, unreal.Object):
        assets = (assets,)
    assets = tuple(dict.fromkeys(getattr(asset, 'target', asset) for asset in assets))
    if not assets:
        raise ValueError('请提供需要处理的资产')
    if action == 'replace_textures':
        if resource_pack is None:
            raise ValueError('资产换包需要指定 resource_pack')
        resource_pack = Path(resource_pack).expanduser().resolve()
        if not resource_pack.is_dir():
            raise NotADirectoryError(resource_pack)
    title = '清晰化纹理' if action == 'sharpen' else '更换材质实例贴图'
    return _start_preparation(title, _asset_steps, assets, action, resource_pack, save)


def _material_steps(components, level, parameters, resource_pack, scope, effect, save, task):
    report = dict(components=0, modified_slots=0, converted_slots=0, imported_assets=[], changed=[], skipped=[],
                  component_changes=[], saved=False)
    textures = {}
    ordinary_sources = {}
    parameter_records = {}
    complete = False
    try:
        yield  # Allow cancellation before the first component, and keep startup cheap.
        for number, component in enumerate(components, 1):
            task.stage(f'材质 {number}/{len(components)} · {component.get_name()}')
            pending = []
            for kind, index, source_material in _material_slots(component, scope):
                slot = dict(component=component.get_path_name(), kind=kind, index=index)
                profile = _labpbr_source(source_material)
                converted = profile is None
                if converted:
                    if source_material not in ordinary_sources:
                        ordinary_sources[source_material] = _ordinary_source(source_material)
                    source = ordinary_sources[source_material]
                    if source is None:
                        report['skipped'].append(dict(slot, reason='empty' if source_material is None
                                                       else 'no_base_texture'))
                        continue
                    family, overrides, base = source
                else:
                    family, old_level, overrides = profile
                    base = get_material_param(source_material, '纹理贴图')
                sources = tex_source_files(base) if isinstance(base, unreal.Texture2D) else ()
                texture_source = sources[0] if len(sources) == 1 else None
                if converted:
                    old_level = 2 if _texture_animation(texture_source) is not None else 1
                target_level = old_level if level is None else level
                if effect in ('enchant', 'wind'):
                    target_level = max(old_level, target_level, 3)
                elif effect == 'interpolate':
                    target_level = max(old_level, target_level, 2)
                elif effect == 'disenchant':
                    target_level = old_level
                elif effect == 'translucent':
                    # 半透明暂用单面以减少排序问题；待 UE 5.9 的排序方案验证后再评估双面。
                    family = _LABPBR_FAMILIES[2]
                parent = unreal.load_asset(family[target_level - 1])
                if parent not in parameter_records:
                    parameter_records[parent] = _parameter_records(parent)
                for name, value in parameters.items():
                    declared = _parameter_kind(parameter_records[parent], name)
                    if declared is None:
                        raise ValueError(f'目标模板没有参数: {name}: {parent.get_path_name()}')
                    if isinstance(value, tuple) and any(v is None for v in value):
                        if declared != 'vector' or len(value) != 4:
                            raise ValueError(f'局部通道覆盖需要四分量向量: {name}')
                bindings = {}
                identity = identify_mc_texture(base) if converted else identify_mc_texture(source_material)
                if resource_pack is not None:
                    if identity is None:
                        report['skipped'].append(dict(slot, reason='unknown_texture'))
                        continue
                    try:
                        files = resolve_mc_texture(identity, resource_pack)
                    except FileNotFoundError:
                        report['skipped'].append(dict(slot, reason='missing_base', texture_id=identity))
                        continue
                    texture_source = files['base']
                    destination = _texture_directory(component, resource_pack)
                    for role, name in _TEXTURE_PARAMETERS.items():
                        path = files[role]
                        if path is None:
                            bindings[name] = unreal.load_asset(_DEFAULT_PBR_TEXTURES[role])
                        else:
                            key = (destination, path, role)
                            if key not in textures:
                                task.stage(f'材质 {number}/{len(components)} · 导入 {path.name}')
                                textures[key] = _import_prep_texture(
                                    path, role, identity, destination, report['imported_assets'])
                                yield
                            bindings[name] = textures[key]
                    overrides = {name: value for name, value in overrides.items()
                                 if name not in (*_TEXTURE_PARAMETERS.values(), ANIMATION_PARAMETER_NAME)}
                elif converted:
                    bindings = {'纹理贴图': base, **{_TEXTURE_PARAMETERS[role]: unreal.load_asset(path)
                                for role, path in _DEFAULT_PBR_TEXTURES.items()}}
                else:
                    # Preserve inherited texture bindings even when changing the template.
                    bindings = {name: get_material_param(source_material, name)
                                for name in _TEXTURE_PARAMETERS.values()
                                if material_parameter_type(source_material, name) == 'texture'}
                pending.append((slot, source_material, parent, texture_source, overrides, bindings, identity, converted))

            if pending:
                with unreal.ScopedEditorTransaction('Mineprep: prepare component materials'):
                    component.modify()
                    for slot, source_material, parent, texture_source, overrides, bindings, identity, converted in pending:
                        stem = _material_stem(source_material, identity, texture_source,
                                              slot['kind'], slot['index'])
                        name = source_material.get_name()
                        slot_name = (name == stem or (name.startswith(stem + '_')
                                     and name[len(stem) + 1:].isdigit()))
                        reusable = (isinstance(source_material, unreal.MaterialInstanceDynamic)
                                    and source_material.get_outer() == component
                                    and slot_name
                                    and source_material.get_editor_property('parent') == parent)
                        if reusable:
                            material = source_material
                            material.modify()
                        else:
                            # Python UObject construction sets RF_Transactional; the editor
                            # parent property change initializes the MID render resources.
                            material = unreal.MaterialInstanceDynamic(outer=component,
                                name=_unique_mid_name(component, stem))
                            material.set_editor_property('parent', parent)
                        apply_mc_material_defaults(material, texture_source)
                        records = parameter_records[parent]
                        _apply_parameters(material, overrides, records)
                        _apply_parameters(material, bindings, records)
                        _apply_parameters(material, parameters, records)
                        _sync_parameter_metadata(material, parameter_records[parent])
                        _bind_material(component, slot['kind'], slot['index'], material)
                        report['changed'].append(dict(slot, texture_id=identity,
                            material=material.get_path_name(), reused=reusable,
                            source_material=source_material.get_path_name(), converted=converted))
                        report['modified_slots'] += 1
                        report['converted_slots'] += int(converted)
                    actions = []
                    if effect == 'wind' and isinstance(component, unreal.StaticMeshComponent):
                        component.set_evaluate_world_position_offset_in_ray_tracing(True)
                        actions.append('ray_tracing_wpo')
                    elif effect == 'emissive':
                        component.set_emissive_light_source(True)
                        actions.append('emissive_light_source')
                    if actions:
                        report['component_changes'].append(dict(component=component.get_path_name(), actions=actions))
            report['components'] += 1
            yield
        if save:
            report['saved'] = yield from _save_preparation(task)
        complete = True
        return report
    finally:
        state = '完成' if complete else '取消或中止'
        unreal.log(f'Mineprep 材质{state}: {report["components"]} 个组件，'
                   f'{report["modified_slots"]} 个槽（转换 {report["converted_slots"]}），'
                   f'{len(report["imported_assets"])} 张导入/覆盖贴图，'
                   f'{len(report["skipped"])} 项跳过')


def _material_inputs(targets, level, parameters, scope):
    if level is not None and (type(level) is not int or level not in range(1, 5)):
        raise ValueError('LabPBR 等级只能为 1–4 或 None；不支持等级 0')
    if scope is not None:
        scope = frozenset((scope,) if isinstance(scope, str) else scope)
        if scope - {'static', 'skeletal', 'overlay'}:
            raise ValueError('scope 只能包含 static、skeletal、overlay')
    components = _material_components(targets)
    parameters = {str(name): _parameter_value(value) for name, value in (parameters or {}).items()}
    return components, parameters, scope


def _start_material_task(targets, level, parameters, resource_pack, scope, effect=None, save=False):
    running = _running_preparation()
    if running is not None:
        return running
    titles = dict(enchant='附魔', disenchant='祛魔', wind='植物摇摆', translucent='半透明',
                  emissive='自发光', interpolate='渐变动画纹理')
    if effect is not None and effect not in titles:
        raise ValueError('effect 只能为 enchant/disenchant/wind/translucent/emissive/interpolate 或 None')
    if effect == 'disenchant':
        parameters = {**(parameters or {}), '附魔颜色': (None, None, None, 0)}
    components, parameters, scope = _material_inputs(targets, level, parameters, scope)
    if effect == 'translucent':
        opacity = parameters.get('不透明R~G+B*A', (None, None, None, None))
        parameters['不透明R~G+B*A'] = (0, 1, opacity[2], opacity[3])
    if resource_pack is not None:
        resource_pack = Path(resource_pack).expanduser().resolve()
        if not resource_pack.is_dir():
            raise NotADirectoryError(resource_pack)
    title = titles[effect] if effect is not None else ('准备材质' if resource_pack is None else '更换材质')
    return _start_preparation(title, _material_steps,
        components, level, parameters, resource_pack, scope, effect, save, notify=effect is None)


def prepare_materials(targets, *, level=None, parameters=None, scope=None, effect=None, save=False):
    """将 Actor/网格组件材质准备为独立、持久化 LabPBR MID，沿用绑定贴图。

    level 为 1–4 或 None；parameters 按实际参数名覆盖，向量 None 保留对应通道。
    scope 选择 static/skeletal/overlay，effect 选择快捷效果；普通材质尽力提取基础贴图。
    返回 AsyncTaskRunner，result 汇总槽位、转换及组件改动；忙碌时返回当前任务。
    效果操作无通知；destroy() 保留已完成部分。save=True 保存全部脏资源和关卡。
    """
    return _start_material_task(targets, level, parameters, None, scope, effect, save)


def replace_materials(targets, resource_pack, *, level=None, parameters=None, scope=None):
    """为 LabPBR 组件 MID 精确换包；缺基础图不动该槽，缺辅助图使用默认图。

    参数与 prepare_materials 相同；返回 AsyncTaskRunner，贴图和动画采用新来源。
    纹理保存至模型目录/资源包名称，按纹理 ID 命名，无哈希，同名覆盖并即时保存。
    忙碌时返回当前任务；取消保留已完成部分，关卡不自动保存。
    """
    return _start_material_task(targets, level, parameters, resource_pack, scope)


def _facet_mesh_data(mesh, subsystem):
    """Read supported source geometry before opening an edit transaction."""
    if mesh.get_editor_property('nanite_settings').enabled:
        return None, 'nanite'
    if subsystem.get_lod_count(mesh) > 1:
        return None, 'multiple_lods'
    lod = unreal.GeometryScriptMeshReadLOD(lod_type=unreal.GeometryScriptLODType.SOURCE_MODEL, lod_index=0)
    library = unreal.GeometryScript_AssetUtils
    if library.check_static_mesh_has_available_lod(mesh, lod) != unreal.GeometryScriptSearchOutcomePins.FOUND:
        return None, 'missing_source_lod'
    dynamic, outcome = library.copy_mesh_from_static_mesh_v2(
        mesh, unreal.DynamicMesh(), unreal.GeometryScriptCopyMeshFromAssetOptions(
            apply_build_settings=False, request_tangents=False, use_build_scale=True), lod,
        use_section_materials=True)
    if outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
        return None, 'unreadable_source_lod'
    unreal.GeometryScript_Normals.set_per_face_normals(dynamic)
    return dynamic, None


def _write_facet_mesh(mesh, dynamic, subsystem):
    build = subsystem.get_lod_build_settings(mesh, 0)
    reduction = subsystem.get_lod_reduction_settings(mesh, 0)
    options = unreal.GeometryScriptCopyMeshToAssetOptions(
        enable_recompute_normals=False, enable_recompute_tangents=True,
        enable_remove_degenerates=build.remove_degenerates, use_build_scale=True,
        replace_materials=False, clean_assigned_materials=False,
        emit_transaction=False, defer_mesh_post_edit_change=True)
    _, outcome = unreal.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(
        dynamic, mesh, options, unreal.GeometryScriptMeshWriteLOD(lod_index=0),
        use_section_materials=True)
    if outcome != unreal.GeometryScriptOutcomePins.SUCCESS:
        raise RuntimeError(f'平直法线写回失败: {mesh.get_path_name()}')
    # Geometry Script resets reduction settings; restore them and preserve all
    # build settings except the normals/tangents we deliberately changed.
    if subsystem.get_lod_reduction_settings(mesh, 0) != reduction:
        subsystem.set_lod_reduction_settings(mesh, 0, reduction)
    build.recompute_normals = False
    build.recompute_tangents = True
    subsystem.set_lod_build_settings(mesh, 0, build)


def _mesh_scene_steps(meshes, complex_collision, flat_shading, report, task):
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    for number, mesh in enumerate(meshes, 1):
        task.stage(f'网格 {number}/{len(meshes)} · {mesh.get_name()}')
        path = mesh.get_path_name()
        dynamic = None
        if flat_shading:
            dynamic, reason = _facet_mesh_data(mesh, subsystem)
            if reason:
                report['skipped'].append(dict(mesh=path, step='flat_shading', reason=reason))
        body = mesh.get_editor_property('body_setup')
        desired = (unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE if complex_collision
                   else unreal.CollisionTraceFlag.CTF_USE_SIMPLE_AND_COMPLEX)
        change_collision = (complex_collision is not None and body is not None
                            and body.get_editor_property('collision_trace_flag') != desired)
        if complex_collision is not None and body is None:
            report['skipped'].append(dict(mesh=path, step='complex_collision', reason='missing_body_setup'))
        if complex_collision is False and body is not None and (
                subsystem.get_simple_collision_count(mesh) + subsystem.get_convex_collision_count(mesh) == 0):
            report['warnings'].append(dict(mesh=path, reason='missing_simple_collision'))
        if dynamic is not None or change_collision:
            actions = []
            with unreal.ScopedEditorTransaction('Mineprep: prepare mesh asset'):
                mesh.modify()
                if body is not None:
                    body.modify()
                    collision_shapes = unreal.GeometryScript_Collision.get_simple_collision_from_static_mesh(mesh)
                if dynamic is not None:
                    _write_facet_mesh(mesh, dynamic, subsystem)
                    actions.append('flat_shading')
                if change_collision:
                    body.set_editor_property('collision_trace_flag', desired)
                    actions.append('complex_collision')
                if body is not None:
                    # This copies the complete AggGeom back unchanged, invalidates
                    # cooked collision and refreshes every component using the mesh.
                    unreal.GeometryScript_Collision.set_simple_collision_of_static_mesh(
                        collision_shapes, mesh, unreal.GeometryScriptSetSimpleCollisionOptions(emit_transaction=False),
                        unreal.GeometryScriptSetStaticMeshCollisionOptions(mark_as_customized=False))
            report['meshes'].append(dict(mesh=path, actions=actions))
        yield


def _scene_steps(components, collision, complex_collision, flat_shading,
                 ray_tracing_wpo, level, parameters, scope, save, with_materials, task):
    report = dict(meshes=[], components=[], materials=None, skipped=[], warnings=[], saved=False)
    complete = False
    try:
        yield
        ordinary = tuple(c for c in components if _ordinary_component(c, scope))
        meshes = tuple(dict.fromkeys(c.static_mesh for c in ordinary
                       if isinstance(c, unreal.StaticMeshComponent) and c.static_mesh))
        if flat_shading or complex_collision is not None:
            yield from _mesh_scene_steps(meshes, complex_collision, flat_shading, report, task)
        owners = set()
        for number, component in enumerate(ordinary, 1):
            task.stage(f'组件 {number}/{len(ordinary)} · {component.get_name()}')
            actions = []
            set_wpo = ray_tracing_wpo is not None and isinstance(component, unreal.StaticMeshComponent)
            if collision is not None or set_wpo:
                with unreal.ScopedEditorTransaction('Mineprep: prepare scene component'):
                    component.modify()
                    if collision is not None:
                        owner = component.get_owner()
                        if collision and owner is not None and owner not in owners:
                            owner.modify()
                            owner.set_actor_enable_collision(True)
                            owners.add(owner)
                        component.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
                        actions.append('collision')
                    if set_wpo:
                        component.set_evaluate_world_position_offset_in_ray_tracing(ray_tracing_wpo)
                        actions.append('ray_tracing_wpo')
                report['components'].append(dict(component=component.get_path_name(), actions=actions))
            yield
        # yield from shares this runner's lifetime: cancellation closes all steps.
        if with_materials:
            report['materials'] = yield from _material_steps(components, level, parameters, None, scope, None, False, task)
        if save:
            report['saved'] = yield from _save_preparation(task)
        complete = True
        return report
    finally:
        unreal.log(f'Mineprep {task.title}{"完成" if complete else "取消或中止"}: '
                   f'{len(report["meshes"])} 个网格资产，{len(report["components"])} 个组件')


def _prepare_scene_shortcut(targets, action, state, scope):
    """Run one legacy scene setting without materials, WPO, notification or save."""
    running = _running_preparation()
    if running is not None:
        return running
    components, parameters, scope = _material_inputs(targets, None, None, scope)
    setting = None if state == -1 else state == 1
    titles = dict(collision='启用碰撞', complex_collision='仅复杂碰撞', flat_shading='平直着色')
    return _start_preparation(titles[action], _scene_steps, components,
        setting if action == 'collision' else None,
        setting if action == 'complex_collision' else None,
        action == 'flat_shading' and setting is True,
        None, None, parameters, scope, False, False, notify=False)


def prepare_scene(targets, *, collision=None, complex_collision=None, flat_shading=False,
                  ray_tracing_wpo=True, level=None, parameters=None, scope=None, save=True):
    """准备目标组件及共享静态网格，最后复用材质准备；返回 AsyncTaskRunner。

    collision/complex_collision/WPO 的 None 保留；关闭碰撞不改变资产复杂度。
    flat_shading 处理单 LOD、非 Nanite 静态网格；scope/level/parameters 同材质准备。
    result 汇总 meshes/components/materials、跳过项及 saved；忙碌时返回当前任务。
    通知可取消并保留部分改动；save=True 默认保存全部脏资源和关卡，包括其他编辑。
    """
    running = _running_preparation()
    if running is not None:
        return running
    components, parameters, scope = _material_inputs(targets, level, parameters, scope)
    return _start_preparation('准备场景', _scene_steps, components, collision,
        None if collision is False else complex_collision, flat_shading,
        ray_tracing_wpo, level, parameters, scope, save, True)
