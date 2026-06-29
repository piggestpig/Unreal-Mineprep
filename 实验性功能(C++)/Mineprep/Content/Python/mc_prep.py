import unreal
import json
import re

from mc_config import paths

MCprepDataCache = None

def load_mcprep_data():
    global MCprepDataCache
    if MCprepDataCache:
        return MCprepDataCache
    with open(paths.mcprep_data, 'r') as f:
        MCprepDataCache = json.load(f)
    return MCprepDataCache

def prep_texture(tex, compression=unreal.TextureCompressionSettings.TC_EDITOR_ICON):
    tex.set_editor_property('filter', unreal.TextureFilter.TF_NEAREST)
    tex.set_editor_property('compression_settings', compression)
    tex.set_editor_property('oodle_preserve_extremes', True)
    unreal.LandmassBlueprintFunctionLibrary.force_update_texture(tex)
    return tex

def colorize_material(mat, color=None):
    if color:
        unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mat, '纹理颜色', color)
        return

    color_dict = load_mcprep_data()['blocks']['desaturated']
    mat_name = re.sub(r'[^a-zA-Z0-9_]', '', mat.get_name())
    if mat_name in color_dict:
        r, g, b = color_dict[mat_name]
        color = unreal.LinearColor(r, g, b, 1.0)
        unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(mat, '纹理颜色', color)
