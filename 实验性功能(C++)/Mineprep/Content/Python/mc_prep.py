import unreal

def prep_texture(tex: unreal.Texture):
    tex.set_editor_property('filter', unreal.TextureFilter.TF_NEAREST)
    tex.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_EDITOR_ICON)
    tex.set_editor_property('oodle_preserve_extremes', True)
    unreal.LandmassBlueprintFunctionLibrary.force_update_texture(tex)
    return tex