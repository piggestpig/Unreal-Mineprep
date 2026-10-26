try:
    import unreal
except ModuleNotFoundError:
    from mc_utils import Lazy as unreal
import json
import re
from fnmatch import fnmatchcase
from pathlib import Path

from mc_config import paths

MCprepDataCache = None

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
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mat, '发光亮度', 0.1)


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


def colorize_material(mat, color=None):
    """设置材质实例“纹理颜色”；未指定时按 mcprep 去饱和色表匹配"""
    if color:
        unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mat, '纹理颜色', color)
        return

    color_dict = load_mcprep_data()['blocks']['desaturated']
    mat_name = re.sub(r'[^a-zA-Z0-9_]', '', mat.get_name())
    if mat_name in color_dict:
        r, g, b = color_dict[mat_name]
        color = unreal.LinearColor(r, g, b, 1.0)
        unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mat, '纹理颜色', color)
