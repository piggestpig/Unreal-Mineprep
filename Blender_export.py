import bpy
import re

def link(name_1,name_2a,name_2b,name_3,name_4):
	try:
		node1 = material.node_tree.nodes.get(name_1)
		try:
			node2 = material.node_tree.nodes.get(name_2a)
			node2.name = name_2b
		except:
			pass
		try:
			node2 = material.node_tree.nodes.get(name_2b)
		except:
			pass
		node1out = node1.outputs.get(name_3)
		node2in = node2.inputs.get(name_4)
		# 连接节点
		material.node_tree.links.new(node1out, node2in)
	except:
		pass
	
# 获取当前选中的所有物体
selected_objects = bpy.context.selected_objects

# 遍历每个选中的物体
for obj in selected_objects:
	# 遍历每个物体的所有材质
	for slot in obj.material_slots:
		# 获取当前材质
		material = slot.material
		link("Diffuse Texture","原理化BSDF","Principled BSDF","Color","Base Color")
		link("Diffuse Texture","原理化BSDF","Principled BSDF","Alpha","Alpha")
		link("Specular Texture","原理化BSDF","Principled BSDF","Color","Specular")
		link("Specular Texture","原理化BSDF","Principled BSDF","Color","Roughness")
		link("Normal Texture","法线贴图","Normal Map","Color","Color")
		link("Principled BSDF","材质输出","Material Output","BSDF","Surface")

# 遍历所有的材质
for material in bpy.data.materials:
	# 获取节点树
	node_tree = material.node_tree
	try:
		# 遍历所有的节点
		for node in node_tree.nodes:
			# 检查节点是否是图像纹理节点，并且节点有图像
			if isinstance(node, bpy.types.ShaderNodeTexImage) and node.image:
				# 获取图像名称
				image_name = node.image.name
				# 检查图像名称是否以 .001, .002, .003 等结尾
				if re.search(r'\.\d+$', image_name):
					# 检查是否存在一个没有 .xxx 后缀的图像
					new_image_name = re.sub(r'\.\d+$', '', image_name)
					if new_image_name in bpy.data.images:
						# 将节点的图像替换为新图像
						node.image = bpy.data.images[new_image_name]
	except:
		pass

# 遍历所有的材质
for material in bpy.data.materials:
	# 获取节点树
	node_tree = material.node_tree
	try:
		# 遍历所有的节点
		for node in node_tree.nodes:
			# 检查节点是否是图像纹理节点，并且节点有图像
			if isinstance(node, bpy.types.ShaderNodeTexImage) and node.image:
				# 获取图像名称
				image_name = node.image.name
				# 检查是否存在一个名为 "xxx_y.png" 的图像
				new_image_name = image_name.rsplit('.', 1)[0] + '_y.png'
				if new_image_name in bpy.data.images:
					# 将节点的图像替换为新图像
					node.image = bpy.data.images[new_image_name]
	except:
		pass
		
