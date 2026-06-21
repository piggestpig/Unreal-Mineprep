import unreal
import os
import gzip
import struct
import json
from pprint import pformat
from mc_utils import lazy_import
from mc_config import paths
from mc_importer import _make_import_task, _run_import_task
from mc_prep import prep_texture

if __name__ == "__main__":
    import numpy as np
    import cv2

# ==========================================
# 0. 全局常量配置
# ==========================================
# 支持 .nbt / .mcstructure / .schematic / .schem
BLOCK_SIZE = 100.0 


# ==========================================
# 1. 解析 NBT 格式
# ==========================================

def read_numeric(stream, fmt, endian):
    size = struct.calcsize(endian + fmt)
    data = stream.read(size)
    if len(data) < size: return None
    return struct.unpack(endian + fmt, data)[0]

def read_string(stream, endian):
    length = read_numeric(stream, 'H', endian)
    if length is None or length == 0: return ""
    return stream.read(length).decode('utf-8', errors='ignore')

def parse_nbt_value(stream, tag_type, endian):
    if tag_type == 0:   return None
    elif tag_type == 1: return read_numeric(stream, 'b', endian)
    elif tag_type == 2: return read_numeric(stream, 'h', endian)
    elif tag_type == 3: return read_numeric(stream, 'i', endian)
    elif tag_type == 4: return read_numeric(stream, 'q', endian)
    elif tag_type == 5: return read_numeric(stream, 'f', endian)
    elif tag_type == 6: return read_numeric(stream, 'd', endian)
    elif tag_type == 7:
        length = read_numeric(stream, 'i', endian)
        return list(stream.read(length)) if length > 0 else []
    elif tag_type == 8: return read_string(stream, endian)
    elif tag_type == 9:
        sub_type = read_numeric(stream, 'b', endian)
        length = read_numeric(stream, 'i', endian)
        return [parse_nbt_value(stream, sub_type, endian) for _ in range(length)]
    elif tag_type == 10:
        res = {}
        while True:
            sub_type = read_numeric(stream, 'b', endian)
            if sub_type == 0 or sub_type is None: break
            name = read_string(stream, endian)
            val = parse_nbt_value(stream, sub_type, endian)
            res[name] = val
        return res
    elif tag_type == 11:
        length = read_numeric(stream, 'i', endian)
        return list(struct.unpack(f"{endian}{length}i", stream.read(length * 4))) if length > 0 else []
    elif tag_type == 12:
        length = read_numeric(stream, 'i', endian)
        return list(struct.unpack(f"{endian}{length}q", stream.read(length * 8))) if length > 0 else []
    return None

def load_nbt_file(stream, endian='>'):
    root_type = read_numeric(stream, 'b', endian)
    if root_type == 10:
        _ = read_string(stream, endian)
        return parse_nbt_value(stream, 10, endian)
    return None

# ==========================================
# 2. 各格式核心转换逻辑 (过滤空气并移除前缀)
# ==========================================

def process_java_nbt(data):
    palette = [(item.get('Name', 'air').replace("minecraft:", ""), item.get('Properties', {})) 
               for item in data.get('palette', [])]
    sparse_dict = {}
    for b in data.get('blocks', []):
        pos = tuple(b.get('pos', [0, 0, 0]))
        state_idx = b.get('state', 0)
        if state_idx < len(palette):
            name, props = palette[state_idx]
            if name != 'air': sparse_dict[pos] = {"name": name, "properties": props}
    return sparse_dict

def process_bedrock_structure(data):
    structure = data.get('structure', {})
    block_indices = structure.get('block_indices', [])
    if not block_indices: return {}
    size = data.get('size', [0, 0, 0])
    layer0 = block_indices[0]
    palette_data = structure.get('palette', {}).get('default', {}).get('block_palette', [])
    palette = [(item.get('name', 'air').replace("minecraft:", ""), item.get('states', {})) for item in palette_data]
    
    sparse_dict = {}
    idx = 0
    for x in range(size[0]):
        for y in range(size[1]):
            for z in range(size[2]):
                if idx >= len(layer0): break
                state_idx = layer0[idx]
                idx += 1
                if state_idx != -1 and state_idx < len(palette):
                    name, props = palette[state_idx]
                    if name != 'air': sparse_dict[(x, y, z)] = {"name": name, "properties": props}
    return sparse_dict

def process_sponge_schematic(data):
    schem = data.get('Schematic', data) if 'Schematic' in data else data
    width, height, length = schem.get('Width', 0), schem.get('Height', 0), schem.get('Length', 0)
    palette_data = schem.get('Palette', {})
    inv_palette = {v: k.replace("minecraft:", "") for k, v in palette_data.items()}
    block_bytes = schem.get('BlockData', [])
    
    varints = []
    idx, n = 0, len(block_bytes)
    while idx < n:
        value, shift = 0, 0
        while True:
            b = block_bytes[idx]
            idx += 1
            value |= (b & 0x7F) << shift
            if not (b & 0x80): break
            shift += 7
        varints.append(value)
        
    sparse_dict = {}
    v_idx = 0
    for y in range(height):
        for z in range(length):
            for x in range(width):
                if v_idx >= len(varints): break
                val_id = varints[v_idx]
                v_idx += 1
                raw_string = inv_palette.get(val_id, 'air')
                if raw_string == 'air' or raw_string.startswith('air['): continue
                
                name, props = raw_string, {}
                if '[' in raw_string and raw_string.endswith(']'):
                    name, props_str = raw_string.split('[', 1)
                    props_str = props_str[:-1]
                    for pair in props_str.split(','):
                        if '=' in pair:
                            pk, pv = pair.split('=', 1)
                            props[pk] = pv
                sparse_dict[(x, y, z)] = {"name": name, "properties": props}
    return sparse_dict

# ==========================================
# 3. 虚幻引擎数据结构组装逻辑 (新增 center 参数)
# ==========================================

def convert_to_unreal_transforms(sparse_dict, center=False):
    """将通用稀疏字典转换为 {方块名称: list(unreal.Transform)} 结构"""
    ue_transform_dict = {}
    
    # 初始化中心偏移量
    center_offset_x = 0.0
    center_offset_y = 0.0
    center_offset_z = 0.0
    
    # 如果开启居中且字典不为空，计算整包方块的 Bounding Box 中心
    if center and sparse_dict:
        all_mx = [pos[0] for pos in sparse_dict.keys()]
        all_my = [pos[1] for pos in sparse_dict.keys()]
        all_mz = [pos[2] for pos in sparse_dict.keys()]
        
        # X 轴与 Y 轴（MC中的Z）计算几何几何中心（包含方块自身大小的边界处理）
        center_offset_x = ((min(all_mx) + max(all_mx)) * BLOCK_SIZE + BLOCK_SIZE) / 2.0
        center_offset_y = ((min(all_mz) + max(all_mz)) * BLOCK_SIZE + BLOCK_SIZE) / 2.0
        # Z 轴（MC中的Y）对齐最底面方块的底部（不进行高度折半，实现底面中心对齐）
        center_offset_z = min(all_my) * BLOCK_SIZE
    
    for (mx, my, mz), block_info in sparse_dict.items():
        name = block_info["name"]
        props = block_info["properties"]
        
        # 1. 坐标修正：针对底面中心 Pivot，X和Y向格内平移半格(50单位)，Z轴保持底部不变
        offset_x = BLOCK_SIZE / 2.0
        offset_y = BLOCK_SIZE / 2.0
        offset_z = 0.0
        
        # 减去整体计算出的中心偏移，将原点拉回底面几何中心
        ue_loc = unreal.Vector(
            mx * BLOCK_SIZE + offset_x - center_offset_x, 
            mz * BLOCK_SIZE + offset_y - center_offset_y, 
            my * BLOCK_SIZE + offset_z - center_offset_z
        )
        
        # 基础角度
        yaw = 0.0
        pitch = 0.0
        roll = 0.0
        
        if "facing" in props:
            facing = str(props["facing"]).lower()
            if facing == "east":     yaw = 0.0     # MC+X -> UE+X (正前)
            elif facing == "south":  yaw = 90.0    # MC+Z -> UE+Y (正右)
            elif facing == "west":   yaw = 180.0   # MC-X -> UE-X (正后)
            elif facing == "north":  yaw = -90.0   # MC-Z -> UE-Y (正左)
            
        # 3. 处理屋顶的倒置楼梯（Java版 half=top 或 基岩版 upside_down_bit=1）
        if props.get("half") == "top" or props.get("upside_down_bit") == 1:
            roll = 180.0  # 沿自身轴翻转180度实现倒挂
            
        ue_rot = unreal.Rotator(pitch=pitch, yaw=yaw, roll=roll)
        
        # 4. 组装 Transform
        transform = unreal.Transform(location=ue_loc, rotation=ue_rot)
        
        if name not in ue_transform_dict:
            ue_transform_dict[name] = []
        ue_transform_dict[name].append(transform)
        
    return ue_transform_dict

# ==========================================
# 4. 主函数 (新增 center 参数)
# ==========================================

def parse_structure(filepath='', center=True):
    if not os.path.exists(filepath):
        unreal.log_error(f"未能找到结构文件: {filepath}")
        return {}

    ext = os.path.splitext(filepath)[1].lower()
    sparse_dict = {}
    
    if ext in ['.nbt', '.schematic', '.schem']:
        with gzip.open(filepath, 'rb') as f:
            nbt_data = load_nbt_file(f, endian='>')
        if ext == '.nbt':
            sparse_dict = process_java_nbt(nbt_data)
        else:
            sparse_dict = process_sponge_schematic(nbt_data)
    elif ext == '.mcstructure':
        with open(filepath, 'rb') as f:
            nbt_data = load_nbt_file(f, endian='<')
        sparse_dict = process_bedrock_structure(nbt_data)
    else:
        unreal.log_warning(f"不支持的文件格式: {ext}")
        return {}

    # 核心转换：将 center 参数传递给转换逻辑
    ue_data = convert_to_unreal_transforms(sparse_dict, center=center)
    print(pformat(ue_data))

    return ue_data




@lazy_import
def structure_to_tex(ue_data, name='structure', fp32=False):
    dtype = np.float32 # if fp32 else np.float16
    exr_type = cv2.IMWRITE_EXR_TYPE_FLOAT if fp32 else cv2.IMWRITE_EXR_TYPE_HALF

    if not ue_data:
        unreal.log_warning("ue_data 为空，取消贴图导出。")
        return

    # 提取所有非空方块类型，建立唯一的资产索引表
    block_types = list(ue_data.keys())
    
    # 将稀疏字典摊平为一维单层列表，方便像素映射
    flat_blocks = []
    for block_name, transforms in ue_data.items():
        type_idx = block_types.index(block_name)
        for t in transforms:
            flat_blocks.append((type_idx, t))
            
    total_blocks = len(flat_blocks)
    if total_blocks == 0:
        unreal.log_warning("未发现有效的方块转换数据，取消贴图导出。")
        return

    # 动态计算正方形贴图的边长 (保证能装下所有方块)
    side = int(np.ceil(np.sqrt(total_blocks)))
    unreal.log(f"开始生成数据贴图：总方块数 = {total_blocks}, 分辨率 = {side} x {side}")

    # BPT 初始化：RGB默认为0，A(方块类型索引)默认为 -1.0。
    bpt_img = np.zeros((side, side, 4), dtype=dtype)
    bpt_img[:, :, 3] = -1.0 

    # BRT 初始化：默认填充单位四元数 Quaternion(0, 0, 0, 1)，即没有任何旋转。
    brt_img = np.zeros((side, side, 4), dtype=dtype)
    brt_img[:, :, 3] = 1.0  # W 轴默认为 1.0

    # 循环遍历数据，填入像素
    for i, (type_idx, transform) in enumerate(flat_blocks):
        row = i // side
        col = i % side
        
        # --- 提取位置并归一化（每个方块单位为1） ---
        loc = transform.translation
        bx = loc.x / 100.0
        by = loc.y / 100.0
        bz = loc.z / 100.0
        
        # 填充 BPT 贴图 (OpenCV BGRA 对应 EXR 的 RGBA)
        bpt_img[row, col, 0] = bz          # OpenCV Channel 0 (B) -> EXR B 通道 (Z轴坐标)
        bpt_img[row, col, 1] = by          # OpenCV Channel 1 (G) -> EXR G 通道 (Y轴坐标)
        bpt_img[row, col, 2] = bx          # OpenCV Channel 2 (R) -> EXR R 通道 (X轴坐标)
        bpt_img[row, col, 3] = float(type_idx) # OpenCV Channel 3 (A) -> EXR A 通道 (方块类型ID)
        
        # --- 提取旋转四元数 ---
        quat = transform.rotation
        
        # 填充 BRT 贴图 (对应关系：EXR 的 RGBA 对应四元数的 X, Y, Z, W)
        brt_img[row, col, 0] = quat.z      # OpenCV Channel 0 (B) -> EXR B 通道 (Quat Z)
        brt_img[row, col, 1] = quat.y      # OpenCV Channel 1 (G) -> EXR G 通道 (Quat Y)
        brt_img[row, col, 2] = quat.x      # OpenCV Channel 2 (R) -> EXR R 通道 (Quat X)
        brt_img[row, col, 3] = quat.w      # OpenCV Channel 3 (A) -> EXR A 通道 (Quat W)

    # 6. 确保本地目录存在，写入 EXR 文件
    if not os.path.exists(paths.cache):
        os.makedirs(paths.cache)
        
    bpt_path = os.path.join(paths.cache, f"{name}_BPT.exr")
    brt_path = os.path.join(paths.cache, f"{name}_BRT.exr")
    json_path = os.path.join(paths.cache, f"{name}_names.json")
    
    cv2.imwrite(bpt_path, bpt_img, [cv2.IMWRITE_EXR_TYPE, exr_type])
    cv2.imwrite(brt_path, brt_img, [cv2.IMWRITE_EXR_TYPE, exr_type])
    
    # 7. 导出 JSON 对照表
    mapping_data = {idx: name for idx, name in enumerate(block_types)}
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(mapping_data, f, indent=4, ensure_ascii=False)
        
    print(f"成功导出贴图！\n位置图: {bpt_path}\n旋转图: {brt_path}\n索引表: {json_path}")

    #导入引擎
    BPT_Tex = _run_import_task(_make_import_task(bpt_path, paths.game + f'mc/structure'))[0]
    BRT_Tex = _run_import_task(_make_import_task(brt_path, paths.game + f'mc/structure'))[0]
    prep_texture(BPT_Tex, unreal.TextureCompressionSettings.TC_HDR)
    prep_texture(BRT_Tex, unreal.TextureCompressionSettings.TC_HDR)
    unreal.EditorAssetLibrary.set_metadata_tag(BPT_Tex, '方块映射', pformat(mapping_data))
    unreal.EditorAssetLibrary.set_metadata_tag(BRT_Tex, '方块映射', pformat(mapping_data))

    return BPT_Tex, BRT_Tex, mapping_data