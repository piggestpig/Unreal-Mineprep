import unreal

# 获取UE编辑器
menus = unreal.ToolMenus.get()

# 获取UE编辑器的主窗口
edit = menus.find_menu(unreal.Name("LevelEditor.MainMenu"))

# 创建菜单栏按钮
tree_menu = edit.add_sub_menu(owner=unreal.Name(edit.get_name()),
                              section_name=unreal.Name('ceshi_tree'),
                              name=unreal.Name('ceshi_tree'),
                              label=unreal.Text('MC'))

# 子目录创建
sub_menu = tree_menu.add_sub_menu(owner=unreal.Name(edit.get_name()),
                                  section_name=unreal.Name('sub_menu'),
                                  name=unreal.Name('sub_menu'),
                                  label=unreal.Text('优化材质'),
                                  tool_tip=unreal.Text('子目录提示'))

# 菜单项1创建
menu_entry = unreal.ToolMenuEntry(
    name=unreal.Name('menu_entry'),
    type=unreal.MultiBlockType.MENU_ENTRY,
)
menu_entry.set_label(unreal.Text('快速优化'))
menu_entry.set_string_command(type=unreal.ToolMenuStringCommandType.PYTHON,
                              custom_type=unreal.Name(''),
                              string='''
# 获取纹理贴图路径列表
texture_paths = unreal.EditorAssetLibrary.list_assets('/Game/mc/import')
# 遍历纹理贴图路径列表
for path in texture_paths:
    try:
        # 加载纹理贴图
        asset = unreal.load_asset(path)
        # 将TextureFilter设置为nearest
        asset.set_editor_property('Filter', unreal.TextureFilter.TF_NEAREST)
        # 保存纹理贴图
        unreal.EditorAssetLibrary.save_loaded_asset(asset)
    except:
        pass''')

# 菜单项2创建
menu_entry2 = unreal.ToolMenuEntry(
    name=unreal.Name('menu_entry2'),
    type=unreal.MultiBlockType.MENU_ENTRY,
)
menu_entry2.set_label(unreal.Text('完整优化'))
menu_entry2.set_string_command(type=unreal.ToolMenuStringCommandType.PYTHON,
                               custom_type=unreal.Name(''),
                               string='''
# 获取纹理贴图路径列表
texture_paths = unreal.EditorAssetLibrary.list_assets('/Game/mc/import')
# 遍历纹理贴图路径列表
for path in texture_paths:
    try:
        # 加载纹理贴图
        asset = unreal.load_asset(path)
        # 将TextureFilter设置为nearest
        asset.set_editor_property('Filter', unreal.TextureFilter.TF_NEAREST)
        #if asset.get_editor_property('CompressionSettings') != unreal.TextureCompressionSettings.TC_NORMALMAP :
        #    asset.set_editor_property('CompressionSettings', unreal.TextureCompressionSettings.TC_EDITOR_ICON)
        # 保存纹理贴图
        #unreal.EditorAssetLibrary.save_loaded_asset(asset)
    except:
        pass
        
# 获取所有材质
materials = unreal.EditorAssetLibrary.list_assets('/Game/mc/import')
# 遍历所有材质
for material_path in materials:
    try:
        # 加载材质
        material = unreal.load_asset(material_path)
        node_tex = unreal.MaterialEditingLibrary.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
        unreal.MaterialEditingLibrary.connect_material_property(from_expression=node_tex
                                                             , from_output_name="A"
                                                             , property_=unreal.MaterialProperty.MP_OPACITY_MASK)
        #1-x节点(invert color)
        node_tex = unreal.MaterialEditingLibrary.get_material_property_input_node(material, unreal.MaterialProperty.MP_ROUGHNESS)
        if node_tex != None:
            node_one_minus = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionOneMinus, node_pos_x=-50, node_pos_y=-100)
            unreal.MaterialEditingLibrary.connect_material_expressions(from_expression=node_tex, from_output_name="", to_expression=node_one_minus, to_input_name="")
            unreal.MaterialEditingLibrary.connect_material_property(from_expression=node_one_minus
                                                                , from_output_name=""
                                                                , property_=unreal.MaterialProperty.MP_ROUGHNESS)
    except:
        pass

# 获取所有材质
materials = unreal.EditorAssetLibrary.list_assets('/Game/mc/import')
# 遍历所有材质
for material_path in materials:
    try:
        # 加载材质
        material = unreal.load_asset(material_path)
        #将材质的Blend Mode属性设置为'Masked'
        material.set_editor_property('BlendMode', unreal.BlendMode.BLEND_MASKED)
        material.set_editor_property('TwoSided', True)
        # 保存材质
        unreal.EditorAssetLibrary.save_loaded_asset(material)
    except:
        pass


# 获取静态网格体路径列表
static_mesh_paths = unreal.EditorAssetLibrary.list_assets('/Game/mc/import')
# 遍历静态网格体路径列表
for path in static_mesh_paths:
   try:
      # 加载静态网格体
      asset = unreal.load_asset(path)
      # 检查资产是否为静态网格体
      if isinstance(asset, unreal.StaticMesh):
         print(asset)
         # 将碰撞复杂度设置为“将复杂碰撞用作简单碰撞”
         bodysetup = asset.get_editor_property('BodySetup')
         bodysetup.set_editor_property('CollisionTraceFlag', unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
         # 保存静态网格体
         unreal.EditorAssetLibrary.save_loaded_asset(asset)
   except Exception as e:
      print(e)
''')

# 菜单项3创建
menu_entry3 = unreal.ToolMenuEntry(
    name=unreal.Name('menu_entry3'),
    type=unreal.MultiBlockType.MENU_ENTRY,
)
menu_entry3.set_label(unreal.Text('test'))
menu_entry3.set_string_command(type=unreal.ToolMenuStringCommandType.PYTHON,
                               custom_type=unreal.Name(''),
                               string='''
print("hello")
''')

# 将菜单项附加在子目录上
sub_menu.add_menu_entry(section_name=unreal.Name(''), args=menu_entry)
sub_menu.add_menu_entry(section_name=unreal.Name(''), args=menu_entry2)
sub_menu.add_menu_entry(section_name=unreal.Name(''), args=menu_entry3)

'''
# 获取所有材质
materials = unreal.EditorAssetLibrary.list_assets('/Game/')
# 遍历所有材质
for material_path in materials:
    try:
        # 加载材质
        material = unreal.load_asset(material_path)
        # 创建1-x节点
        node_one_minus = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionOneMinus, node_pos_x=-50, node_pos_y=-100)
        node_tex = unreal.MaterialEditingLibrary.get_material_property_input_node(material, unreal.MaterialProperty.MP_ROUGHNESS)
        if node_tex != None:
            unreal.MaterialEditingLibrary.connect_material_expressions(from_expression=node_tex, from_output_name="", to_expression=node_one_minus, to_input_name="")
            unreal.MaterialEditingLibrary.connect_material_property(from_expression=node_one_minus
                                                                , from_output_name=""
                                                                , property_=unreal.MaterialProperty.MP_ROUGHNESS)
    except:
        pass'''


   
'''asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
my_mat = asset_tools.create_asset("M_CreatedByPython", "/Game/CreatedByPython", unreal.Material, unreal.MaterialFactoryNew())
unreal.EditorAssetLibrary.save_asset(my_mat.get_path_name())

node_add = unreal.MaterialEditingLibrary.create_material_expression(my_mat, unreal.MaterialExpressionAdd, node_pos_x=-200, node_pos_y=0)

node_tex = unreal.MaterialEditingLibrary.create_material_expression(my_mat, unreal.MaterialExpressionTextureSampleParameter2D
            , node_pos_x=-600, node_pos_y=0)

texture_asset = unreal.load_asset("/Game/StarterContent/Textures/T_Brick_Clay_Beveled_D")
node_tex.set_editor_property("texture", texture_asset)
# use MaterialEditingLibrary
unreal.MaterialEditingLibrary.connect_material_property(from_expression=node_tex
                                                    , from_output_name=""
                                                    , property_=unreal.MaterialProperty.MP_BASE_COLOR)

unreal.MaterialEditingLibrary.connect_material_expressions(from_expression=node_tex, from_output_name="", to_expression=node_add, to_input_name="A")
'''








'''material = unreal.load_asset("/Game/CreatedByPython/M_CreatedByPython")
node_tex = unreal.MaterialEditingLibrary.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
print(node_tex)
print("aaaaaaaaaa")
#unreal.EditorAssetLibrary.save_loaded_asset(material)
unreal.MaterialEditingLibrary.connect_material_property(from_expression=node_tex
                                                    , from_output_name="A"
                                                    , property_=unreal.MaterialProperty.MP_OPACITY_MASK)
'''



'''# 获取纹理贴图路径列表
texture_paths = unreal.EditorAssetLibrary.list_assets('/Game/StarterContent/Textures/')
# 遍历纹理贴图路径列表
for path in texture_paths:
    # 加载纹理贴图
    asset = unreal.load_asset(path)
    # 将TextureFilter设置为nearest
    asset.set_editor_property('Filter', unreal.TextureFilter.TF_DEFAULT)
    # 保存纹理贴图
    unreal.EditorAssetLibrary.save_loaded_asset(asset)'''


'''
    except Exception as e:
        # 捕获异常并输出错误信息
        print("An error occurred:", e)
'''

