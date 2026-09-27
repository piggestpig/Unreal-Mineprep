import unreal
import os
import gzip
import struct
import json
import numpy as np
from pathlib import Path
from pprint import pformat
from mc_utils import lazy_import
from mc_config import paths
from mc_importer import (
    _make_import_task, _run_import_task, _load_mc_model,
    resolve_block_json_path, import_block,
)
from mc_prep import prep_texture

if __name__ == "__main__":
    import numpy as np
    import cv2

# ==========================================
# 0. 全局常量配置
# ==========================================
# 支持 .nbt / .mcstructure / .schematic / .schem
BLOCK_SIZE = 100.0
_NEIGHBOR_OFFSETS = (
    (1, 0, 0), (-1, 0, 0),
    (0, 1, 0), (0, -1, 0),
    (0, 0, 1), (0, 0, -1),
)


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

def _read_int32_array(stream, length, endian):
    """整段读入 int32。空列表返回长度为 0 的数组。"""
    if not length or length < 0:
        return np.empty(0, dtype=np.int32)
    raw = stream.read(length * 4)
    if len(raw) != length * 4:
        raise ValueError(f"NBT int array truncated: {len(raw)} < {length * 4}")
    src = np.dtype('<i4' if endian == '<' else '>i4')
    return np.frombuffer(raw, dtype=src).astype(np.int32, copy=False)

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
        # 保持 bytes，避免 数百万元素 list↔bytes 往返
        return stream.read(length) if length and length > 0 else b""
    elif tag_type == 8: return read_string(stream, endian)
    elif tag_type == 9:
        sub_type = read_numeric(stream, 'b', endian)
        length = read_numeric(stream, 'i', endian)
        if sub_type == 3:
            return _read_int32_array(stream, length, endian)
        if not length or length < 0:
            return []
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
        return _read_int32_array(stream, length, endian)
    elif tag_type == 12:
        length = read_numeric(stream, 'i', endian)
        return list(struct.unpack(f"{endian}{length}q", stream.read(length * 8))) if length > 0 else []
    return None

def load_nbt_file(stream, endian='>'):
    """从二进制流读取 NBT 根标签"""
    root_type = read_numeric(stream, 'b', endian)
    if root_type == 10:
        _ = read_string(stream, endian)
        return parse_nbt_value(stream, 10, endian)
    return None

# ==========================================
# 2. 各格式核心转换逻辑 (过滤空气并移除前缀)
# ==========================================

_LEGACY_BLOCK_IDS_CACHE = None
_LEGACY_UNKNOWN_WARNED = set()


def _parse_blockstate_string(raw_string):
    """minecraft:oak_stairs[facing=east,...] → (name, props)"""
    raw_string = str(raw_string).replace("minecraft:", "")
    if raw_string in {"air", "cave_air", "void_air"} or raw_string.startswith("air["):
        return "air", {}
    name, props = raw_string, {}
    if "[" in raw_string and raw_string.endswith("]"):
        name, props_str = raw_string.split("[", 1)
        props_str = props_str[:-1]
        for pair in props_str.split(","):
            if "=" in pair:
                pk, pv = pair.split("=", 1)
                props[pk.strip()] = pv.strip()
    return name, props


def _load_legacy_block_ids():
    """加载 1.12 id:meta → 现代方块名 映射表（mc_default/assets/minecraft）"""
    global _LEGACY_BLOCK_IDS_CACHE
    if _LEGACY_BLOCK_IDS_CACHE is not None:
        return _LEGACY_BLOCK_IDS_CACHE
    # paths.blockstates = .../assets/minecraft/blockstates
    path = os.path.join(os.path.dirname(paths.blockstates), "legacy_block_ids.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            _LEGACY_BLOCK_IDS_CACHE = json.load(handle)
    except (OSError, json.JSONDecodeError):
        unreal.log_warning(f"未能加载 legacy_block_ids.json: {path}")
        _LEGACY_BLOCK_IDS_CACHE = {}
    return _LEGACY_BLOCK_IDS_CACHE


def _legacy_id_to_block(block_id, meta):
    """经典 schematic 数字 ID+meta → (name, props)"""
    mapping = _load_legacy_block_ids()
    key = f"{int(block_id)}:{int(meta) & 0xF}"
    raw = mapping.get(key)
    if raw is None:
        raw = mapping.get(f"{int(block_id)}:0")
    if raw is None:
        if key not in _LEGACY_UNKNOWN_WARNED:
            _LEGACY_UNKNOWN_WARNED.add(key)
            unreal.log_warning(f"未知旧版方块 ID {key}，已跳过")
        return "air", {}
    return _parse_blockstate_string(raw)


def process_java_nbt(data):
    """将 Java .nbt 结构转为稀疏字典 {(x,y,z): {name, properties}}。

    26.3（DataVersion 5023）调色板字段是 id / properties；
    旧结构仍是 Name / Properties。
    """
    palette = []
    for item in data.get('palette', []):
        raw = item.get('id', item.get('Name', 'air'))
        props = item.get('properties', item.get('Properties')) or {}
        palette.append((str(raw).replace("minecraft:", ""), props))
    sparse_dict = {}
    for b in data.get('blocks', []):
        pos = tuple(b.get('pos', [0, 0, 0]))
        state_idx = b.get('state', 0)
        if state_idx < len(palette):
            name, props = palette[state_idx]
            if name != 'air': sparse_dict[pos] = {"name": name, "properties": props}
    return sparse_dict

def process_bedrock_structure(data):
    """将基岩版 .mcstructure 转为稀疏字典 {(x,y,z): {name, properties}}"""
    structure = data.get('structure', {})
    block_indices = structure.get('block_indices', [])
    if not block_indices: return {}
    size = data.get('size', [0, 0, 0])
    sx, sy, sz = int(size[0]), int(size[1]), int(size[2])
    layer0 = np.asarray(block_indices[0], dtype=np.int32)
    volume = sx * sy * sz
    if volume <= 0 or layer0.size == 0:
        return {}
    if layer0.size > volume:
        layer0 = layer0[:volume]
    palette_data = structure.get('palette', {}).get('default', {}).get('block_palette', [])
    palette = [(item.get('name', 'air').replace("minecraft:", ""), item.get('states', {})) for item in palette_data]
    position_data = structure.get('palette', {}).get('default', {}).get('block_position_data') or {}
    palette_len = len(palette)
    stride_x = sy * sz

    sparse_dict = {}
    for linear in np.flatnonzero(layer0 != -1):
        linear = int(linear)
        state_idx = int(layer0[linear])
        if state_idx < 0 or state_idx >= palette_len:
            continue
        name, props = palette[state_idx]
        if name == 'air':
            continue
        if name == 'bed' or name.endswith('_bed'):
            extra = position_data.get(str(linear)) or {}
            entity = extra.get('block_entity_data') or {}
            if 'color' in entity:
                props = dict(props)
                props['color'] = entity['color']
        x = linear // stride_x
        rem = linear % stride_x
        y = rem // sz
        z = rem % sz
        sparse_dict[(x, y, z)] = {"name": name, "properties": props}
    return sparse_dict


def process_classic_schematic(schem):
    """经典 MCEdit .schematic：Blocks(byte)+Data(meta)，YZX 顺序"""
    width = int(schem.get("Width", 0) or 0)
    height = int(schem.get("Height", 0) or 0)
    length = int(schem.get("Length", 0) or 0)
    blocks = schem.get("Blocks") or b""
    data = schem.get("Data") or b""
    if not width or not height or not length or not blocks:
        return {}

    expected = width * height * length
    if len(blocks) < expected:
        unreal.log_warning(
            f"经典 schematic Blocks 长度不足: {len(blocks)} < {expected}"
        )
        expected = len(blocks)

    # NBT ByteArray 现为 bytes；兼容旧 list
    if isinstance(blocks, (bytes, bytearray)):
        blocks_u8 = blocks
    else:
        blocks_u8 = bytes((b & 0xFF) for b in blocks)
    if isinstance(data, (bytes, bytearray)):
        data_u8 = data
    elif data:
        data_u8 = bytes((d & 0xFF) for d in data)
    else:
        data_u8 = b""

    layer = length * width
    data_len = len(data_u8)
    resolve_cache = {}  # (bid, meta) -> (name, props)
    info_cache = {}  # (bid, meta) -> 共享的 {"name","properties"}，避免每格 new dict
    sparse_dict = {}
    for i in range(expected):
        bid = blocks_u8[i]
        if bid == 0:
            continue
        meta = data_u8[i] & 0xF if i < data_len else 0
        key = (bid, meta)
        info = info_cache.get(key)
        if info is None:
            resolved = resolve_cache.get(key)
            if resolved is None:
                resolved = _legacy_id_to_block(bid, meta)
                resolve_cache[key] = resolved
            name, props = resolved
            if name == "air":
                info_cache[key] = False  # 哨兵：空气
                continue
            info = {"name": name, "properties": props}
            info_cache[key] = info
        elif info is False:
            continue
        # index = (Y * length + Z) * width + X
        y, rem = divmod(i, layer)
        z, x = divmod(rem, width)
        sparse_dict[(x, y, z)] = info
    return sparse_dict


def process_sponge_schematic(data):
    """将 Sponge .schem（v2/v3）转为稀疏字典 {(x,y,z): {name, properties}}"""
    schem = data.get('Schematic', data) if 'Schematic' in data else data

    width = int(schem.get('Width', 0) or 0)
    height = int(schem.get('Height', 0) or 0)
    length = int(schem.get('Length', 0) or 0)

    # v3: Blocks.{Palette, Data}；v2: 顶层 Palette + BlockData
    blocks_tag = schem.get('Blocks')
    if isinstance(blocks_tag, dict) and (
        blocks_tag.get('Palette') is not None or blocks_tag.get('Data') is not None
    ):
        palette_data = blocks_tag.get('Palette') or {}
        block_bytes = blocks_tag.get('Data') or b""
        version = schem.get('Version', 3)
    else:
        palette_data = schem.get('Palette') or {}
        block_bytes = schem.get('BlockData') or b""
        version = schem.get('Version', 2)

    if isinstance(block_bytes, list):
        block_bytes = bytes((b & 0xFF) for b in block_bytes)
    elif not isinstance(block_bytes, (bytes, bytearray)):
        unreal.log_warning(
            f"Sponge schematic BlockData 类型异常: {type(block_bytes).__name__}"
        )
        return {}

    if not palette_data or not block_bytes:
        unreal.log_warning(
            f"Sponge schematic 缺少 Palette/Data "
            f"(v{version}, {width}x{height}x{length}, keys={list(schem.keys())[:20]})"
        )
        return {}

    unreal.log(
        f"Sponge schematic v{version} "
        f"({width}x{height}x{length}, palette={len(palette_data)}, data={len(block_bytes)}B)"
    )

    inv_palette = {v: k.replace("minecraft:", "") for k, v in palette_data.items()}

    varints = []
    idx, n = 0, len(block_bytes)
    while idx < n:
        value, shift = 0, 0
        while True:
            b = block_bytes[idx]
            idx += 1
            value |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
        varints.append(value)

    sparse_dict = {}
    v_idx = 0
    expected = width * height * length
    for y in range(height):
        for z in range(length):
            for x in range(width):
                if v_idx >= len(varints):
                    break
                val_id = varints[v_idx]
                v_idx += 1
                raw_string = inv_palette.get(val_id, 'air')
                name, props = _parse_blockstate_string(raw_string)
                if name == 'air':
                    continue
                sparse_dict[(x, y, z)] = {"name": name, "properties": props}

    if v_idx < expected:
        unreal.log_warning(
            f"Sponge BlockData 方块数不足: {v_idx} < {expected}"
        )
    return sparse_dict

# ==========================================
# 3. 虚幻引擎数据结构组装逻辑 (新增 center 参数)
# ==========================================

# 高草/大型花卉：half=lower|upper → *_bottom / *_top
_DOUBLE_PLANT_NAMES = frozenset({
    "tall_grass", "large_fern", "sunflower", "lilac", "rose_bush", "peony",
    "pitcher_plant",
})
_DOUBLE_SLAB_MODEL_CACHE = {}


def _double_slab_model_name(slab_name):
    """type=double 时查 blockstate，多数映射到完整方块（stone_bricks 等）"""
    name = str(slab_name).lower().replace("minecraft:", "")
    cached = _DOUBLE_SLAB_MODEL_CACHE.get(name)
    if cached is not None:
        return cached

    result = f"{name}_double"
    try:
        bs_path = Path(paths.blockstates) / f"{name}.json"
        with bs_path.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
        model_ref = (data.get("variants") or {}).get("type=double") or {}
        if isinstance(model_ref, dict):
            model_ref = model_ref.get("model", "")
        model_ref = str(model_ref).replace("minecraft:block/", "").replace("block/", "")
        if model_ref:
            result = model_ref
    except (OSError, json.JSONDecodeError, TypeError, AttributeError):
        pass

    _DOUBLE_SLAB_MODEL_CACHE[name] = result
    return result


_BEDROCK_BED_DIRECTION = {0: "south", 1: "west", 2: "north", 3: "east"}
# 基岩床方块实体 color，与染料序号一致：0 白 … 14 红 … 15 黑
_DYE_COLORS = (
    "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
    "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black",
)


def _dye_color_name(value):
    """染料序号或颜色名 → white / red / …"""
    if isinstance(value, str) and not value.strip().lstrip("-").isdigit():
        return value.lower().replace("minecraft:", "")
    try:
        index = int(value)
    except (TypeError, ValueError):
        return None
    if 0 <= index < len(_DYE_COLORS):
        return _DYE_COLORS[index]
    return None


def _bed_base_name(name, props):
    """基岩旧版方块名 bed 的颜色在方块实体 color 里，不在 states。"""
    if name != "bed":
        return name
    color = _dye_color_name((props or {}).get("color"))
    if not color:
        color = "red"
    if color.endswith("_bed"):
        return color
    return f"{color}_bed"


def _bed_part(props):
    """head_piece_bit 或 part → head / foot"""
    props = props or {}
    if "head_piece_bit" in props:
        return "head" if str(props.get("head_piece_bit")).lower() in {"1", "true"} else "foot"
    return "head" if str(props.get("part", "foot")).lower() == "head" else "foot"


# 基岩楼梯 weirdo_direction：0 东、1 西、2 南、3 北
_BEDROCK_STAIR_FACING = {0: "east", 1: "west", 2: "south", 3: "north"}


def _stair_facing_shape_half(props):
    """楼梯状态 → (facing, shape, half)。基岩用 weirdo_direction / corner / upside_down_bit。"""
    props = props or {}
    if "facing" not in props and "weirdo_direction" in props:
        try:
            facing = _BEDROCK_STAIR_FACING.get(int(props["weirdo_direction"]), "east")
        except (TypeError, ValueError):
            facing = "east"
    else:
        facing = str(props.get("facing", "east")).lower()

    corner = props.get("minecraft:corner", props.get("corner"))
    if corner is not None and "shape" not in props:
        corner = str(corner).lower()
        shape = "straight" if corner in {"", "none"} else corner
    else:
        shape = str(props.get("shape", "straight")).lower()

    if "half" not in props and "upside_down_bit" in props:
        upside = str(props.get("upside_down_bit")).lower() in {"1", "true"}
        half = "top" if upside else "bottom"
    else:
        half = str(props.get("half", "bottom")).lower()
    return facing, shape, half


# 基岩门 direction：0 东、1 南、2 西、3 北。导出值比门扇法线逆时针偏 90°，
# 这样 3 像素厚的门板落在外墙而不是内墙。合页位在上门。
_BEDROCK_DOOR_FACING = {0: "east", 1: "south", 2: "west", 3: "north"}
_FACING_CCW = {"north": "west", "west": "south", "south": "east", "east": "north"}
_LEGACY_BLOCK_NAMES = {
    "wooden_door": "oak_door",
    "wooden_pressure_plate": "oak_pressure_plate",
    "fence_gate": "oak_fence_gate",
}
_TORCH_AWAY = {"north": "south", "south": "north", "east": "west", "west": "east"}


def _door_base_name(name):
    return _LEGACY_BLOCK_NAMES.get(name, name)


def _plain_facing(props, default="south"):
    """Java facing，或基岩 cardinal_direction。不做门那套 90° 修正。"""
    props = props or {}
    if props.get("facing"):
        return str(props["facing"]).lower()
    cardinal = props.get("minecraft:cardinal_direction", props.get("cardinal_direction"))
    if cardinal:
        return str(cardinal).lower().replace("minecraft:", "")
    return default


def _pressure_plate_model_name(name, props):
    signal = (props or {}).get("redstone_signal", (props or {}).get("powered", "0"))
    powered = str(signal).lower() not in {"0", "false", ""}
    return f"{name}_down" if powered else name


def _fence_gate_model_name(name, props):
    props = props or {}
    in_wall = str(props.get("in_wall", props.get("in_wall_bit", "false"))).lower() in {"1", "true"}
    opened = str(props.get("open", props.get("open_bit", "false"))).lower() in {"1", "true"}
    suffix = "_wall" if in_wall else ""
    if opened:
        suffix += "_open"
    return f"{name}{suffix}"


def _door_facing(props):
    """Java facing。基岩 cardinal_direction / direction 要再逆时针转 90°，门板才贴外墙。"""
    props = props or {}
    if props.get("facing"):
        return str(props["facing"]).lower()
    cardinal = props.get("minecraft:cardinal_direction", props.get("cardinal_direction"))
    if cardinal:
        raw = str(cardinal).lower().replace("minecraft:", "")
        return _FACING_CCW.get(raw, raw)
    if "direction" in props:
        try:
            raw = _BEDROCK_DOOR_FACING.get(int(props["direction"]), "north")
        except (TypeError, ValueError):
            raw = "north"
        return _FACING_CCW.get(raw, raw)
    return "north"


def _wall_torch_java_facing(props):
    """基岩 torch_facing_direction 指向所贴的方块，Java wall_torch 的 facing 是火把伸出的方向。"""
    props = props or {}
    raw = props.get("torch_facing_direction", props.get("facing_direction"))
    if raw is None:
        return None
    text = str(raw).lower()
    if text in {"", "none", "unknown", "top", "up"}:
        return None
    return _TORCH_AWAY.get(text)


def _torch_model_name(name, props):
    if _wall_torch_java_facing(props) is None:
        return name
    if name == "torch":
        return "wall_torch"
    if name.endswith("_torch") and not name.startswith("wall_"):
        return f"{name[:-5]}wall_torch"
    return name


def _door_half_hinge_open(props):
    """→ (half, hinge, open)。half 为 lower/upper。"""
    props = props or {}
    if "upper_block_bit" in props and "half" not in props:
        upper = str(props.get("upper_block_bit")).lower() in {"1", "true"}
        half = "upper" if upper else "lower"
    else:
        half = str(props.get("half", "lower")).lower()
    if "door_hinge_bit" in props and "hinge" not in props:
        right = str(props.get("door_hinge_bit")).lower() in {"1", "true"}
        hinge = "right" if right else "left"
    else:
        hinge = str(props.get("hinge", "left")).lower()
    if hinge not in {"left", "right"}:
        hinge = "left"
    if "open_bit" in props and "open" not in props:
        opened = str(props.get("open_bit")).lower() in {"1", "true"}
    else:
        opened = str(props.get("open", "false")).lower() == "true"
    return half, hinge, opened


def _bed_facing(props):
    """基岩 direction 0–3 或 Java facing → north/east/south/west"""
    props = props or {}
    if "direction" in props and not props.get("facing"):
        try:
            return _BEDROCK_BED_DIRECTION.get(int(props["direction"]), "south")
        except (TypeError, ValueError):
            return "south"
    return str(props.get("facing", "north")).lower()


def _structure_model_name(name, props):
    """将 NBT 方块名+属性映射为可导入的模型文件名（不含 .json）"""
    name = str(name).lower().replace("minecraft:", "")
    name = _LEGACY_BLOCK_NAMES.get(name, name)
    props = props or {}

    # 旧版短草更名
    if name == "grass":
        return "short_grass"

    # 积雪层：layers=1..8 → snow_height{2..14} / snow_block
    if name == "snow":
        try:
            layers = int(props.get("layers", 1))
        except (TypeError, ValueError):
            layers = 1
        layers = max(1, min(8, layers))
        if layers >= 8:
            return "snow_block"
        return f"snow_height{layers * 2}"

    # 墙：无连接信息时用 inventory 模型（经典 schematic 连接全为 none）
    if name.endswith("_wall") and "banner" not in name:
        return f"{name}_inventory"

    # 活板门：half/open → *_bottom / *_top / *_open
    if name.endswith("_trapdoor"):
        if str(props.get("open", "false")).lower() == "true":
            return f"{name}_open"
        half = str(props.get("half", "bottom")).lower()
        return f"{name}_top" if half == "top" else f"{name}_bottom"

    # 半砖：type=bottom|top|double → name / name_top / 完整方块（读 blockstate）
    if name.endswith("_slab"):
        slab_type = str(props.get("type", "bottom")).lower()
        if slab_type == "top":
            return f"{name}_top"
        if slab_type == "double":
            return _double_slab_model_name(name)
        return name

    # 双高植物
    if name in _DOUBLE_PLANT_NAMES:
        half = str(props.get("half", "lower")).lower()
        return f"{name}_top" if half in {"upper", "top"} else f"{name}_bottom"

    # 玻璃板：multipart，见 _structure_parts（不再回退成整块玻璃）

    if name.endswith("_pressure_plate"):
        return _pressure_plate_model_name(name, props)

    if name.endswith("_fence_gate"):
        return _fence_gate_model_name(name, props)

    # 楼梯：shape / 基岩 corner → oak_stairs / oak_stairs_inner / oak_stairs_outer
    if name.endswith("_stairs"):
        _facing, shape, _half = _stair_facing_shape_half(props)
        if shape.startswith("inner"):
            return f"{name}_inner"
        if shape.startswith("outer"):
            return f"{name}_outer"
        return name

    if name == "torch" or name.endswith("_torch"):
        torch_name = _torch_model_name(name, props)
        if torch_name != name:
            return torch_name

    # 门：half/hinge/open → oak_door_bottom_left / oak_door_top_left_open
    # 基岩旧名 wooden_door，合页用 door_hinge_bit，上下用 upper_block_bit。
    if name.endswith("_door"):
        name = _door_base_name(name)
        half, hinge, opened = _door_half_hinge_open(props)
        half_part = "bottom" if half in {"lower", "bottom"} else "top"
        open_part = "_open" if opened else ""
        return f"{name}_{half_part}_{hinge}{open_part}"

    # 床：part / head_piece_bit → red_bed_head / red_bed_foot。基岩旧版方块名是 bed。
    if name == "bed" or name.endswith("_bed"):
        return f"{_bed_base_name(name, props)}_{_bed_part(props)}"

    return name


# 原版 fence_side 默认朝北（MC -Z）；blockstate y → UE yaw
_FENCE_SIDE_YAW = (("north", 0.0), ("east", 90.0), ("south", 180.0), ("west", 270.0))

# 原版 glass_pane multipart：连接用 side/side_alt，未连接用 noside/noside_alt
# (direction, connected_suffix, disconnected_suffix, connected_yaw, disconnected_yaw)
_PANE_DIR_PARTS = (
    ("north", "side", "noside", 0.0, 0.0),
    ("east", "side", "noside_alt", 90.0, 0.0),
    ("south", "side_alt", "noside_alt", 0.0, 90.0),
    ("west", "side_alt", "noside", 90.0, 270.0),
)


def _yaw_rot(yaw):
    """返回 (pitch, yaw, roll)；Yaw 绕 UE Z"""
    return (0.0, float(yaw), 0.0)


def _dir_connected(props, direction):
    """Java `north=true`，或基岩 `minecraft:connection_north=1`。"""
    props = props or {}
    if direction in props:
        return str(props[direction]).lower() == "true"
    for key in (f"minecraft:connection_{direction}", f"connection_{direction}"):
        if key in props:
            return str(props[key]).lower() in {"1", "true"}
    return False


def _structure_parts(raw_name, props):
    """一个 NBT 方块拆成 [(模型名, pitch, yaw, roll), ...]；栅栏/玻璃板为 multipart"""
    name = str(raw_name).lower().replace("minecraft:", "")
    props = props or {}

    if name.endswith("_fence"):
        parts = [(f"{name}_post", *_yaw_rot(0.0))]
        for direction, yaw in _FENCE_SIDE_YAW:
            if _dir_connected(props, direction):
                parts.append((f"{name}_side", *_yaw_rot(yaw)))
        return parts

    if name.endswith("_pane"):
        parts = [(f"{name}_post", *_yaw_rot(0.0))]
        for direction, conn_sfx, disc_sfx, conn_yaw, disc_yaw in _PANE_DIR_PARTS:
            connected = str(props.get(direction, "false")).lower() == "true"
            if connected:
                parts.append((f"{name}_{conn_sfx}", *_yaw_rot(conn_yaw)))
            else:
                parts.append((f"{name}_{disc_sfx}", *_yaw_rot(disc_yaw)))
        return parts

    pitch, yaw, roll = _block_rotation(raw_name, props)
    return [(_structure_model_name(raw_name, props), pitch, yaw, roll)]


def structure_parts(name, properties=None):
    """MC blockstate → [(model_name, pitch, yaw, roll), ...]。

    与 spawn_structure 同一套展开：楼梯用 facing/shape/half；
    栅栏/玻璃板用 north/east/south/west（同格 multipart，不是自己摆 side 网格）。
    """
    return _structure_parts(name, properties or {})


# 原版 stairs blockstate：MC Y 旋转（绕竖直轴）。模型默认 facing=east。
# 键: (facing, shape) -> y；half=top 时另有 x=180，且部分 shape 的 y 不同。
_STAIR_Y_BOTTOM = {
    ("east", "straight"): 0, ("east", "inner_right"): 0, ("east", "outer_right"): 0,
    ("east", "inner_left"): 270, ("east", "outer_left"): 270,
    ("west", "straight"): 180, ("west", "inner_right"): 180, ("west", "outer_right"): 180,
    ("west", "inner_left"): 90, ("west", "outer_left"): 90,
    ("south", "straight"): 90, ("south", "inner_right"): 90, ("south", "outer_right"): 90,
    ("south", "inner_left"): 0, ("south", "outer_left"): 0,
    ("north", "straight"): 270, ("north", "inner_right"): 270, ("north", "outer_right"): 270,
    ("north", "inner_left"): 180, ("north", "outer_left"): 180,
}
_STAIR_Y_TOP = {
    ("east", "straight"): 0, ("east", "inner_left"): 0, ("east", "outer_left"): 0,
    ("east", "inner_right"): 90, ("east", "outer_right"): 90,
    ("west", "straight"): 180, ("west", "inner_left"): 180, ("west", "outer_left"): 180,
    ("west", "inner_right"): 270, ("west", "outer_right"): 270,
    ("south", "straight"): 90, ("south", "inner_left"): 90, ("south", "outer_left"): 90,
    ("south", "inner_right"): 180, ("south", "outer_right"): 180,
    ("north", "straight"): 270, ("north", "inner_left"): 270, ("north", "outer_left"): 270,
    ("north", "inner_right"): 0, ("north", "outer_right"): 0,
}


def _block_rotation(name, props):
    """按方块类型计算 UE 欧拉角 (pitch, yaw, roll)。
    坐标约定：MC(X,Z,Y) → UE(X,Y,Z)，故 MC 绕 Y 的 blockstate.y → UE Yaw；
    MC 绕 X 的 blockstate.x → UE Roll。
    注意：unreal.Rotator 位置参是 (roll, pitch, yaw)，此处一律用关键字构造。
    """
    props = props or {}
    pitch = 0.0
    yaw = 0.0
    roll = 0.0
    raw_name = str(name).lower().replace("minecraft:", "")

    if raw_name.endswith("_stairs"):
        facing, shape, half = _stair_facing_shape_half(props)
        table = _STAIR_Y_TOP if half == "top" else _STAIR_Y_BOTTOM
        yaw = float(table.get((facing, shape), table.get((facing, "straight"), 0)))
        if half == "top":
            roll = 180.0
        return (pitch, yaw, roll)

    # 活板门：open 模型默认在 MC 南面；blockstate.y 顺时针（俯视）南→西…
    # MC y 直接作 UE yaw：east:y=90 → 面板转到西面（贴向东侧邻格的方块）
    if raw_name.endswith("_trapdoor"):
        if str(props.get("open", "false")).lower() == "true":
            facing = str(props.get("facing", "north")).lower()
            yaw = {"north": 0.0, "east": 90.0, "south": 180.0, "west": 270.0}.get(facing, 0.0)
        return (0.0, yaw, 0.0)

    if "torch" in raw_name:
        facing = _wall_torch_java_facing(props)
        if facing is None and ("wall_torch" in raw_name or raw_name.startswith("wall_")):
            facing = str(props.get("facing", "east")).lower()
        if facing:
            yaw = {"east": 0.0, "south": 90.0, "west": 180.0, "north": 270.0}.get(facing, 0.0)
            return (0.0, yaw, 0.0)
        return (0.0, 0.0, 0.0)

    # 栅栏门：模型默认朝南（y=0）。south 0、west 90、north 180、east 270
    if raw_name == "fence_gate" or raw_name.endswith("_fence_gate"):
        facing = _plain_facing(props)
        yaw = {"south": 0.0, "west": 90.0, "north": 180.0, "east": 270.0}.get(facing, 0.0)
        return (0.0, yaw, 0.0)

    # 门：模型默认朝向与楼梯类似（east=0 系）
    if raw_name.endswith("_door"):
        facing = _door_facing(props)
        yaw = {"east": 0.0, "south": 90.0, "west": 180.0, "north": 270.0}.get(facing, 0.0)
        return (0.0, yaw, 0.0)

    # 床：原版 blockstate y（north=0, east=90…）→ UE yaw；勿走下方 east=0 通用 facing
    if raw_name == "bed" or raw_name.endswith("_bed"):
        facing = _bed_facing(props)
        yaw = {"north": 0.0, "east": 90.0, "south": 180.0, "west": 270.0}.get(facing, 0.0)
        return (0.0, yaw, 0.0)

    # 铁砧：原版模型默认朝南；blockstate y 原样作 UE yaw（south=0, west=90, north=180, east=270）
    if raw_name in {"anvil", "chipped_anvil", "damaged_anvil"} or raw_name.endswith("_anvil"):
        facing = str(props.get("facing", "south")).lower()
        yaw = {"south": 0.0, "west": 90.0, "north": 180.0, "east": 270.0}.get(facing, 0.0)
        return (0.0, yaw, 0.0)

    # 半砖用独立 top/double 模型，不要再 roll 180
    if raw_name.endswith("_slab"):
        return (0.0, 0.0, 0.0)

    if "facing" in props:
        facing = str(props["facing"]).lower()
        if facing == "east":
            yaw = 0.0
        elif facing == "south":
            yaw = 90.0
        elif facing == "west":
            yaw = 180.0
        elif facing == "north":
            yaw = 270.0

    if props.get("half") == "top" or props.get("upside_down_bit") == 1:
        roll = 180.0

    return (pitch, yaw, roll)


def _structure_center_offsets(sparse_dict):
    """底面居中：返回 (ox, oy, oz)，已含半格 pivot，可直接 loc = m*BLOCK_SIZE + o*"""
    if not sparse_dict:
        half = BLOCK_SIZE * 0.5
        return half, half, 0.0

    it = iter(sparse_dict)
    mx0, my0, mz0 = next(it)
    min_x = max_x = mx0
    min_y = max_y = my0
    min_z = max_z = mz0
    for mx, my, mz in it:
        if mx < min_x:
            min_x = mx
        elif mx > max_x:
            max_x = mx
        if my < min_y:
            min_y = my
        elif my > max_y:
            max_y = my
        if mz < min_z:
            min_z = mz
        elif mz > max_z:
            max_z = mz

    half = BLOCK_SIZE * 0.5
    center_offset_x = ((min_x + max_x) * BLOCK_SIZE + BLOCK_SIZE) / 2.0
    center_offset_y = ((min_z + max_z) * BLOCK_SIZE + BLOCK_SIZE) / 2.0
    center_offset_z = min_y * BLOCK_SIZE
    return half - center_offset_x, half - center_offset_y, -center_offset_z


def _norm_deg_90(deg):
    """角度规范到 {0, 90, 180, 270}"""
    a = float(deg) % 360.0
    if a < 0.0:
        a += 360.0
    return float((int(round(a / 90.0)) % 4) * 90)


# 方块实例离散朝向 → BRT.A 序号；与 HLSL Rotation[8] 一一对应
# (yaw, roll)；当前管线 pitch 恒为 0
_BLOCK_ROT_ID = {
    (0.0, 0.0): 0,
    (90.0, 0.0): 1,
    (180.0, 0.0): 2,
    (270.0, 0.0): 3,
    (0.0, 180.0): 4,
    (90.0, 180.0): 5,
    (180.0, 180.0): 6,
    (270.0, 180.0): 7,
}


def _euler_to_rot_id(pitch, yaw, roll):
    """(pitch,yaw,roll) → 0..7；非 90° 倍数或非零 pitch 时回退 0"""
    if abs(float(pitch)) > 1e-3:
        return 0
    key = (_norm_deg_90(yaw), _norm_deg_90(roll))
    return _BLOCK_ROT_ID.get(key, 0)


_ROT_ID_TO_EULER = {
    0: (0.0, 0.0, 0.0),
    1: (0.0, 90.0, 0.0),
    2: (0.0, 180.0, 0.0),
    3: (0.0, 270.0, 0.0),
    4: (0.0, 0.0, 180.0),
    5: (0.0, 90.0, 180.0),
    6: (0.0, 180.0, 180.0),
    7: (0.0, 270.0, 180.0),
}

# rot_id → 将世界 UE 轴向尺寸 (wx,wy,wz) 转为局部 Scale3D
# yaw 90/270 交换 X/Y；roll 180 不改变轴向尺寸
_ROT_ID_LOCAL_SCALE = {
    0: lambda wx, wy, wz: (wx, wy, wz),
    1: lambda wx, wy, wz: (wy, wx, wz),
    2: lambda wx, wy, wz: (wx, wy, wz),
    3: lambda wx, wy, wz: (wy, wx, wz),
    4: lambda wx, wy, wz: (wx, wy, wz),
    5: lambda wx, wy, wz: (wy, wx, wz),
    6: lambda wx, wy, wz: (wx, wy, wz),
    7: lambda wx, wy, wz: (wy, wx, wz),
}


def _is_leaves_model(model_name) -> bool:
    """树叶方块（正方体但不做 uvlock / 不合并）"""
    stem = str(model_name).lower().replace("minecraft:", "")
    return stem.endswith("_leaves") or stem == "leaves"


def _is_mergeable_cube(model_name) -> bool:
    """仅完整正方体可合并；排除树叶"""
    return _is_solid_block(model_name) and not _is_leaves_model(model_name)


def _greedy_merge_1d(cells):
    """merge=1：沿 X→Z→Y 贪婪拉长条"""
    remaining = set(cells)
    boxes = []
    for axis in (0, 2, 1):
        for start in sorted(remaining):
            if start not in remaining:
                continue
            length = 1
            while True:
                nxt = [start[0], start[1], start[2]]
                nxt[axis] += length
                if tuple(nxt) not in remaining:
                    break
                length += 1
            size = [1, 1, 1]
            size[axis] = length
            boxes.append((start[0], start[1], start[2], size[0], size[1], size[2]))
            for i in range(length):
                p = [start[0], start[1], start[2]]
                p[axis] += i
                remaining.discard(tuple(p))
    return boxes


def _greedy_merge_2d(cells):
    """merge=2：按 Y 层贪婪矩形（+X 宽，再 +Z 深）"""
    by_y = {}
    for x, y, z in cells:
        by_y.setdefault(y, set()).add((x, z))

    boxes = []
    for y, xz_set in by_y.items():
        remaining = set(xz_set)
        for x, z in sorted(remaining):
            if (x, z) not in remaining:
                continue
            w = 1
            while (x + w, z) in remaining:
                w += 1
            d = 1
            while all((x + i, z + d) in remaining for i in range(w)):
                d += 1
            for i in range(w):
                for j in range(d):
                    remaining.discard((x + i, z + j))
            boxes.append((x, y, z, w, 1, d))
    return boxes


def _greedy_merge_3d(cells):
    """merge=3：2D 矩形后再沿 +Y 叠成柱体"""
    rects = _greedy_merge_2d(cells)
    by_foot = {}
    for x, y, z, sx, _sy, sz in rects:
        by_foot.setdefault((x, z, sx, sz), []).append(y)

    boxes = []
    for (x, z, sx, sz), ys in by_foot.items():
        ys.sort()
        i = 0
        n = len(ys)
        while i < n:
            y0 = ys[i]
            h = 1
            while i + h < n and ys[i + h] == y0 + h:
                h += 1
            boxes.append((x, y0, z, sx, h, sz))
            i += h
    return boxes


def _merge_cells(cells, merge_mode):
    """对同一 (model, rot) 的格点集做贪婪合并 → [(x,y,z,sx,sy,sz), ...]"""
    if not cells:
        return []
    mode = int(merge_mode)
    if mode <= 0:
        return [(x, y, z, 1, 1, 1) for x, y, z in cells]
    if mode == 1:
        return _greedy_merge_1d(cells)
    if mode == 2:
        return _greedy_merge_2d(cells)
    return _greedy_merge_3d(cells)


def _collect_merged_boxes(sparse_dict, merge=0):
    """展开 multipart 后合并：返回 [(model_name, rot_id, x,y,z, sx,sy,sz), ...]
    坐标为 MC 整数格 (X,Y,Z)。
    """
    merge_mode = int(merge)
    parts_cache = {}
    mergeable = {}
    passthrough = []

    for (mx, my, mz), block_info in sparse_dict.items():
        props = block_info["properties"]
        raw_name = block_info["name"]
        try:
            cache_key = (raw_name, frozenset((props or {}).items()))
        except TypeError:
            cache_key = (raw_name, id(props))
        parts = parts_cache.get(cache_key)
        if parts is None:
            parts = _structure_parts(raw_name, props)
            parts_cache[cache_key] = parts

        for model_name, pitch, yaw, roll in parts:
            rot_id = _euler_to_rot_id(pitch, yaw, roll)
            if merge_mode > 0 and _is_mergeable_cube(model_name):
                mergeable.setdefault((model_name, rot_id), set()).add((mx, my, mz))
            else:
                passthrough.append((model_name, rot_id, mx, my, mz, 1, 1, 1))

    boxes = list(passthrough)
    for (model_name, rot_id), cells in mergeable.items():
        for x, y, z, sx, sy, sz in _merge_cells(cells, merge_mode):
            boxes.append((model_name, rot_id, x, y, z, sx, sy, sz))
    return boxes


def _mc_box_ue_location_scale(x, y, z, sx, sy, sz, rot_id, ox, oy, oz):
    """MC 轴对齐盒 → UE 位置（底面中心）与局部 Scale3D。
    网格水平居中、Z 从底面起算（与 _mc_point_to_ue 一致）。
    rot_id≥4（roll=180）时绕底面翻转，Z 再抬 BLOCK_SIZE，使几何回到本格（楼梯 half=top）。
    """
    # UE: (MC_X, MC_Z, MC_Y)；水平取 AABB 中心，竖直取底面
    loc_x = (x + (sx - 1) * 0.5) * BLOCK_SIZE + ox
    loc_y = (z + (sz - 1) * 0.5) * BLOCK_SIZE + oy
    loc_z = y * BLOCK_SIZE + oz
    if int(rot_id) >= 4:
        loc_z += BLOCK_SIZE
    # 世界 UE 轴向尺寸
    wx, wy, wz = float(sx), float(sz), float(sy)
    remap = _ROT_ID_LOCAL_SCALE.get(int(rot_id), _ROT_ID_LOCAL_SCALE[0])
    return (loc_x, loc_y, loc_z), remap(wx, wy, wz)


def convert_to_unreal_transforms(sparse_dict, center=False, merge=0):
    """将稀疏字典转换为 {方块名称: list(unreal.Transform)}；merge>0 时合并完整正方体"""
    ox = oy = BLOCK_SIZE * 0.5
    oz = 0.0
    if center:
        ox, oy, oz = _structure_center_offsets(sparse_dict)

    rot_cache = {}
    lists = {}
    for model_name, rot_id, x, y, z, sx, sy, sz in _collect_merged_boxes(sparse_dict, merge=merge):
        loc, scale = _mc_box_ue_location_scale(x, y, z, sx, sy, sz, rot_id, ox, oy, oz)
        pitch, yaw, roll = _ROT_ID_TO_EULER.get(int(rot_id), (0.0, 0.0, 0.0))
        rot_key = (pitch, yaw, roll)
        ue_rot = rot_cache.get(rot_key)
        if ue_rot is None:
            ue_rot = unreal.Rotator(pitch=pitch, yaw=yaw, roll=roll)
            rot_cache[rot_key] = ue_rot
        bucket = lists.get(model_name)
        if bucket is None:
            bucket = []
            lists[model_name] = bucket
        bucket.append(
            unreal.Transform(
                location=unreal.Vector(loc[0], loc[1], loc[2]),
                rotation=ue_rot,
                scale=unreal.Vector(scale[0], scale[1], scale[2]),
            )
        )
    return lists


def convert_to_packed_arrays(sparse_dict, center=False, merge=0):
    """{model: {"pos":(N,3) float32, "rot":(N,) int32, "scale":(N,3) float32}}"""
    ox = oy = BLOCK_SIZE * 0.5
    oz = 0.0
    if center:
        ox, oy, oz = _structure_center_offsets(sparse_dict)

    packed = {}
    for model_name, rot_id, x, y, z, sx, sy, sz in _collect_merged_boxes(sparse_dict, merge=merge):
        loc, scale = _mc_box_ue_location_scale(x, y, z, sx, sy, sz, rot_id, ox, oy, oz)
        bucket = packed.get(model_name)
        if bucket is None:
            bucket = {"pos": [], "rot": [], "scale": []}
            packed[model_name] = bucket
        bucket["pos"].append(loc)
        bucket["rot"].append(int(rot_id))
        bucket["scale"].append(scale)
    for bucket in packed.values():
        bucket["pos"] = np.asarray(bucket["pos"], dtype=np.float32)
        bucket["rot"] = np.asarray(bucket["rot"], dtype=np.int32)
        bucket["scale"] = np.asarray(bucket["scale"], dtype=np.float32)
    return packed


_INSTANCE_BATCH = 8192


def add_packed_instances(ism, payload):
    """按批把 packed 的 pos/rot/scale 写入 ISM，批结束后释放 Transform 列表。"""
    pos = payload["pos"]
    rot = payload["rot"]
    scale = payload["scale"]
    count = int(len(pos))
    rot_cache = {}
    for start in range(0, count, _INSTANCE_BATCH):
        stop = min(start + _INSTANCE_BATCH, count)
        batch = []
        for i in range(start, stop):
            rot_id = int(rot[i])
            ue_rot = rot_cache.get(rot_id)
            if ue_rot is None:
                pitch, yaw, roll = _ROT_ID_TO_EULER.get(rot_id, (0.0, 0.0, 0.0))
                ue_rot = unreal.Rotator(pitch=pitch, yaw=yaw, roll=roll)
                rot_cache[rot_id] = ue_rot
            point = pos[i]
            extent = scale[i]
            batch.append(unreal.Transform(
                location=unreal.Vector(float(point[0]), float(point[1]), float(point[2])),
                rotation=ue_rot,
                scale=unreal.Vector(float(extent[0]), float(extent[1]), float(extent[2])),
            ))
        ism.add_instances(batch, False, False, True)
        del batch


_CULL_FLUID_NAMES = frozenset({"water", "flowing_water"})
_CUBE_FACE_NAMES = frozenset({"down", "up", "north", "south", "west", "east"})
_SOLID_NAME_CACHE = {}


def _element_is_full_cube(element) -> bool:
    """单个 element 是否为 0–16 且含六面的完整正方体"""
    frm = element.get("from")
    to = element.get("to")
    if not frm or not to or len(frm) != 3 or len(to) != 3:
        return False
    try:
        if any(abs(float(frm[i]) - 0.0) > 1e-6 for i in range(3)):
            return False
        if any(abs(float(to[i]) - 16.0) > 1e-6 for i in range(3)):
            return False
    except (TypeError, ValueError):
        return False
    faces = element.get("faces") or {}
    return _CUBE_FACE_NAMES.issubset(faces.keys())


def _model_is_full_cube(model_data) -> bool:
    """合并 parent 后的模型是否含完整正方体（可有 overlay 等额外 element）"""
    elements = model_data.get("elements") or []
    return any(_element_is_full_cube(el) for el in elements)


def _is_water_block(block_name) -> bool:
    """判断是否为水流方块名"""
    return str(block_name).lower() in _CULL_FLUID_NAMES


def _is_solid_block(block_name) -> bool:
    """可剔除实心：对应 block 模型含 0–16 六面正方体（按方块名缓存）"""
    name = str(block_name).lower().replace("minecraft:", "")
    cached = _SOLID_NAME_CACHE.get(name)
    if cached is not None:
        return cached

    result = False
    try:
        path = resolve_block_json_path(name)
        if path is not None:
            result = _model_is_full_cube(_load_mc_model(path))
    except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError):
        result = False

    _SOLID_NAME_CACHE[name] = result
    return result


def _is_internal_block(pos, occupied) -> bool:
    """六邻域均被占用时视为内部方块"""
    return all(
        (pos[0] + dx, pos[1] + dy, pos[2] + dz) in occupied
        for dx, dy, dz in _NEIGHBOR_OFFSETS
    )


def _cull_internal_blocks_per_type(sparse_dict):
    """按方块类型分别剔除内部实心块（cull=1）"""
    positions_by_name = {}
    for pos, block_info in sparse_dict.items():
        name = block_info["name"]
        if not (_is_solid_block(name) or _is_water_block(name)):
            continue
        positions_by_name.setdefault(name, set()).add(pos)

    culled = {}
    for pos, block_info in sparse_dict.items():
        name = block_info["name"]
        if name not in positions_by_name:
            culled[pos] = block_info
            continue
        if _is_internal_block(pos, positions_by_name[name]):
            continue
        culled[pos] = block_info
    return culled


def _cull_internal_blocks_unified_solids(sparse_dict):
    """全体实心块统一剔除内部，保留流体外壳（cull=2）"""
    solid_positions = set()
    water_positions = set()
    for pos, block_info in sparse_dict.items():
        name = block_info["name"]
        if _is_water_block(name):
            water_positions.add(pos)
        elif _is_solid_block(name):
            solid_positions.add(pos)

    culled = {}
    for pos, block_info in sparse_dict.items():
        name = block_info["name"]
        if _is_water_block(name):
            occupied = water_positions
        elif _is_solid_block(name):
            occupied = solid_positions
        else:
            culled[pos] = block_info
            continue
        if _is_internal_block(pos, occupied):
            continue
        culled[pos] = block_info
    return culled


def _cull_bbox_sides_and_bottom(sparse_dict):
    """剔除结构 AABB 的四个侧面与底面方块，保留顶面（cull=3 第二步）"""
    if not sparse_dict:
        return sparse_dict

    it = iter(sparse_dict)
    x0, y0, z0 = next(it)
    min_x = max_x = x0
    min_y = y0
    min_z = max_z = z0
    for x, y, z in it:
        if x < min_x:
            min_x = x
        elif x > max_x:
            max_x = x
        if y < min_y:
            min_y = y
        if z < min_z:
            min_z = z
        elif z > max_z:
            max_z = z

    culled = {}
    for (x, y, z), block_info in sparse_dict.items():
        if y == min_y:
            continue
        if x == min_x or x == max_x or z == min_z or z == max_z:
            continue
        culled[(x, y, z)] = block_info
    return culled


def _fix_open_trapdoor_facings(sparse_dict):
    """修正错误 facing：开启活板门若恰有一个完整方块邻居，facing 应背离该邻居
    （与 test.schematic 灯柱一致；部分 .schem 导出 facing 错乱）。
    """
    if not sparse_dict:
        return sparse_dict

    solids = {
        pos for pos, info in sparse_dict.items()
        if _is_solid_block(info["name"])
    }
    # (邻格相对位移) → 背离该邻格时应有的 facing
    away_facing = {
        (1, 0, 0): "west",
        (-1, 0, 0): "east",
        (0, 0, 1): "north",
        (0, 0, -1): "south",
    }

    fixed = 0
    for pos, info in list(sparse_dict.items()):
        name = str(info["name"]).lower().replace("minecraft:", "")
        if not name.endswith("_trapdoor"):
            continue
        props = info.get("properties") or {}
        if str(props.get("open", "false")).lower() != "true":
            continue

        hits = []
        for delta, facing in away_facing.items():
            npos = (pos[0] + delta[0], pos[1] + delta[1], pos[2] + delta[2])
            if npos in solids:
                hits.append(facing)
        if len(hits) != 1:
            continue
        if str(props.get("facing", "")).lower() == hits[0]:
            continue
        new_props = dict(props)
        new_props["facing"] = hits[0]
        sparse_dict[pos] = {"name": info["name"], "properties": new_props}
        fixed += 1

    if fixed:
        unreal.log(f"已修正 {fixed} 个开启活板门的 facing（按邻接实心块）")
    return sparse_dict


# 玻璃板 NESW → 邻格相对位移（MC）
_PANE_CONNECT_DIRS = (
    ("north", (0, 0, -1)),
    ("east", (1, 0, 0)),
    ("south", (0, 0, 1)),
    ("west", (-1, 0, 0)),
)


def _sync_bedrock_door_halves(sparse_dict):
    """下门的朝向为准（上门常被写成 south）。合页记在上门，抄到下门。"""
    if not sparse_dict:
        return sparse_dict
    for pos, info in list(sparse_dict.items()):
        name = str(info["name"]).lower().replace("minecraft:", "")
        if not name.endswith("_door"):
            continue
        props = info.get("properties") or {}
        if str(props.get("upper_block_bit", "")).lower() not in {"0", "false"}:
            continue
        above_pos = (pos[0], pos[1] + 1, pos[2])
        above = sparse_dict.get(above_pos)
        if not above:
            continue
        above_name = str(above["name"]).lower().replace("minecraft:", "")
        if above_name != name:
            continue
        above_props = above.get("properties") or {}

        if "door_hinge_bit" in above_props and str(props.get("door_hinge_bit")) != str(above_props.get("door_hinge_bit")):
            new_props = dict(props)
            new_props["door_hinge_bit"] = above_props["door_hinge_bit"]
            sparse_dict[pos] = {"name": info["name"], "properties": new_props}

        new_upper = None
        for key in ("minecraft:cardinal_direction", "cardinal_direction", "direction", "open_bit"):
            if key in props and str(above_props.get(key)) != str(props.get(key)):
                if new_upper is None:
                    new_upper = dict(above_props)
                new_upper[key] = props[key]
        if new_upper is not None:
            sparse_dict[above_pos] = {"name": above["name"], "properties": new_upper}
    return sparse_dict


def _fix_pane_connections(sparse_dict):
    """部分 .schem 玻璃板无 NESW，按邻格（板条/实心）补全连接。已有任一连接则跳过。"""
    if not sparse_dict:
        return sparse_dict

    attach = set()
    panes = []
    for pos, info in sparse_dict.items():
        name = str(info["name"]).lower().replace("minecraft:", "")
        if name.endswith("_pane") or name == "iron_bars":
            attach.add(pos)
            if name.endswith("_pane"):
                panes.append((pos, info))
        elif _is_solid_block(info["name"]):
            attach.add(pos)

    if not panes:
        return sparse_dict

    fixed = 0
    for pos, info in panes:
        props = info.get("properties") or {}
        if any(str(props.get(d, "false")).lower() == "true" for d, _ in _PANE_CONNECT_DIRS):
            continue
        new_props = dict(props)
        any_true = False
        for direction, (dx, dy, dz) in _PANE_CONNECT_DIRS:
            connected = (pos[0] + dx, pos[1] + dy, pos[2] + dz) in attach
            new_props[direction] = "true" if connected else "false"
            any_true = any_true or connected
        if not any_true:
            continue
        sparse_dict[pos] = {"name": info["name"], "properties": new_props}
        fixed += 1

    if fixed:
        unreal.log(f"已补全 {fixed} 个玻璃板的 NESW 连接（按邻格）")
    return sparse_dict


def _is_fence_cell_name(name):
    raw = str(name).lower().replace("minecraft:", "")
    return raw.endswith("_fence") and "gate" not in raw


def _is_pane_cell_name(name):
    raw = str(name).lower().replace("minecraft:", "")
    return raw.endswith("_pane") or raw == "iron_bars"


def _connect_fences_and_panes(sparse_dict):
    """按邻格重写栅栏/玻璃板 NESW（compose 用；总是覆盖已有连接）。"""
    if not sparse_dict:
        return sparse_dict
    for pos, info in list(sparse_dict.items()):
        name = info["name"]
        if _is_fence_cell_name(name):
            props = dict(info.get("properties") or {})
            for direction, (dx, dy, dz) in _PANE_CONNECT_DIRS:
                nbr = sparse_dict.get((pos[0] + dx, pos[1] + dy, pos[2] + dz))
                props[direction] = "true" if nbr and _is_fence_cell_name(nbr["name"]) else "false"
            sparse_dict[pos] = {"name": name, "properties": props}
            continue
        if str(name).lower().replace("minecraft:", "").endswith("_pane"):
            props = dict(info.get("properties") or {})
            for direction, (dx, dy, dz) in _PANE_CONNECT_DIRS:
                nbr = sparse_dict.get((pos[0] + dx, pos[1] + dy, pos[2] + dz))
                connected = bool(
                    nbr and (_is_pane_cell_name(nbr["name"]) or _is_solid_block(nbr["name"]))
                )
                props[direction] = "true" if connected else "false"
            sparse_dict[pos] = {"name": name, "properties": props}
    return sparse_dict


def _stringify_block_prop(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _copy_sparse_cells(sparse_dict):
    return {
        pos: {"name": info["name"], "properties": dict(info.get("properties") or {})}
        for pos, info in (sparse_dict or {}).items()
    }


def _apply_cull(sparse_dict, cull=0):
    """cull 标志与 parse_structure / spawn_structure 相同；返回新 dict 或原引用（cull=0）。"""
    cull_mode = int(cull)
    if cull_mode == 1:
        return _cull_internal_blocks_per_type(sparse_dict)
    if cull_mode in (2, 3):
        culled = _cull_internal_blocks_unified_solids(sparse_dict)
        if cull_mode == 3:
            culled = _cull_bbox_sides_and_bottom(culled)
        return culled
    return sparse_dict


def _load_structure_sparse(filepath):
    """文件 → 稀疏格子（含活板门/玻璃板修正）。不做 cull/merge。"""
    if not filepath or not os.path.exists(filepath):
        unreal.log_error(f"未能找到结构文件: {filepath}")
        return {}

    ext = os.path.splitext(filepath)[1].lower()
    sparse_dict = {}

    if ext in ['.nbt', '.schematic', '.schem']:
        with gzip.open(filepath, 'rb') as f:
            nbt_data = load_nbt_file(f, endian='>')
    elif ext == '.mcstructure':
        with open(filepath, 'rb') as f:
            nbt_data = load_nbt_file(f, endian='<')
    else:
        unreal.log_warning(f"不支持的文件格式: {ext}")
        return {}

    if ext == '.nbt':
        sparse_dict = process_java_nbt(nbt_data)
    elif ext == '.schematic':
        schem = nbt_data.get('Schematic', nbt_data) if isinstance(nbt_data, dict) and 'Schematic' in nbt_data else nbt_data
        unreal.log(
            f"经典 MCEdit schematic "
            f"({schem.get('Width')}x{schem.get('Height')}x{schem.get('Length')})"
        )
        sparse_dict = process_classic_schematic(schem)
    elif ext == '.schem':
        sparse_dict = process_sponge_schematic(nbt_data)
    else:
        sparse_dict = process_bedrock_structure(nbt_data)

    sparse_dict = _fix_open_trapdoor_facings(sparse_dict)
    sparse_dict = _fix_pane_connections(sparse_dict)
    sparse_dict = _sync_bedrock_door_halves(sparse_dict)
    return sparse_dict


# ==========================================
# 结构解析入口
# ==========================================

def parse_structure(filepath='', center=True, cull=0, packed=False, merge=0):
    """解析 .nbt/.schem/.mcstructure。
    packed=False → {方块名: [Transform]}（ISM）
    packed=True  → {方块名: {"pos":[...], "rot":[...], "scale":[...]}}（PCG/粒子）
    cull=1 按类型剔除内部；cull=2 全体实心统一剔除内部；
    cull=3 在 2 基础上再剔除 AABB 侧面与底面（保留顶面）
    merge=0 关；1 长条；2 平面；3 长方体（仅完整正方体；cull 优先于 merge）
    """
    sparse_dict = _load_structure_sparse(filepath)
    if not sparse_dict:
        return {}

    sparse_dict = _apply_cull(sparse_dict, cull)
    merge_mode = int(merge)
    if packed:
        ue_data = convert_to_packed_arrays(sparse_dict, center=center, merge=merge_mode)
        total = sum(len(v["pos"]) for v in ue_data.values())
    else:
        ue_data = convert_to_unreal_transforms(sparse_dict, center=center, merge=merge_mode)
        total = sum(len(v) for v in ue_data.values())

    unreal.log(
        f"结构解析完成: {len(ue_data)} 种方块, {total} 个实例 "
        f"(文件 {os.path.basename(filepath)}, packed={packed}, cull={int(cull)}, merge={merge_mode})"
    )
    if total <= 200 and not packed:
        unreal.log(pformat(ue_data))

    return ue_data


class Blocks:
    """MC 格子容器：{(x,y,z): {name, properties}}。types() 才展开成 mesh。"""

    def __init__(self, name='structure', cells=None, copy=True):
        self.name = name or 'structure'
        if cells and copy:
            self._cells = _copy_sparse_cells(cells)
        else:
            self._cells = cells if cells is not None else {}
        self._mesh_cache = {}

    def _pos(self, x, y, z):
        return (int(x), int(y), int(z))

    def add(self, name, x, y, z, **props):
        clean = {key: _stringify_block_prop(val) for key, val in props.items()}
        self._cells[self._pos(x, y, z)] = {
            "name": str(name).lower().replace("minecraft:", ""),
            "properties": clean,
        }
        return self

    def remove(self, x, y, z):
        return self._cells.pop(self._pos(x, y, z), None) is not None

    def get(self, x, y, z):
        info = self._cells.get(self._pos(x, y, z))
        if info is None:
            return None
        return info["name"], dict(info.get("properties") or {})

    def connect_fences(self):
        _connect_fences_and_panes(self._cells)
        return self

    def copy_cells(self):
        return _copy_sparse_cells(self._cells)

    def __len__(self):
        return len(self._cells)

    def __contains__(self, pos):
        if not isinstance(pos, tuple) or len(pos) != 3:
            return False
        return self._pos(*pos) in self._cells

    def __iter__(self):
        return iter(self._cells)

    @classmethod
    def from_file(cls, filepath):
        cells = _load_structure_sparse(filepath)
        return cls(name=Path(filepath).stem, cells=cells, copy=False)

    def types(self, merge=0, center=False, reload=False):
        """展开 structure_parts → 按模型分组，yield (StaticMesh, [Transform])。"""
        grouped = convert_to_unreal_transforms(self._cells, center=center, merge=merge)
        for model_name, transforms in grouped.items():
            mesh = None if reload else self._mesh_cache.get(model_name)
            if mesh is None:
                path = resolve_block_json_path(model_name)
                if path is None:
                    continue
                mesh = import_block(path, asset_name=model_name, reload=reload)
                if mesh is None:
                    continue
                self._mesh_cache[model_name] = mesh
            yield mesh, transforms


def _is_packed_structure_data(ue_data) -> bool:
    """判断是否为 packed 格式 {name: {pos, rot, scale?}}"""
    if not ue_data:
        return False
    sample = next(iter(ue_data.values()))
    return isinstance(sample, dict) and "pos" in sample and "rot" in sample


@lazy_import
def structure_to_tex(ue_data, name='structure', fp32=True):
    """将结构数据烘焙为位置/旋转贴图。支持 Transform 列表或 packed 数组。
    BRT：RGB=局部缩放 (X,Y,Z)，A=旋转序号 0..7（查 HLSL Rotation[]）。
    """
    dtype = np.float32  # if fp32 else np.float16
    exr_type = cv2.IMWRITE_EXR_TYPE_FLOAT if fp32 else cv2.IMWRITE_EXR_TYPE_HALF

    if not ue_data:
        unreal.log_warning("ue_data 为空，取消贴图导出。")
        return

    packed = _is_packed_structure_data(ue_data)
    block_types = list(ue_data.keys())
    if packed:
        total_blocks = sum(len(v["pos"]) for v in ue_data.values())
    else:
        total_blocks = sum(len(v) for v in ue_data.values())

    if total_blocks == 0:
        unreal.log_warning("未发现有效的方块转换数据，取消贴图导出。")
        return

    side = int(np.ceil(np.sqrt(total_blocks)))
    unreal.log(f"开始生成数据贴图：总方块数 = {total_blocks}, 分辨率 = {side} x {side}")

    bpt_img = np.zeros((side, side, 4), dtype=dtype)
    bpt_img[:, :, 3] = -1.0
    brt_img = np.zeros((side, side, 4), dtype=dtype)
    brt_img[:, :, 0] = 1.0
    brt_img[:, :, 1] = 1.0
    brt_img[:, :, 2] = 1.0
    brt_img[:, :, 3] = 0.0

    if packed:
        i = 0
        for type_idx, payload in enumerate(ue_data.values()):
            pos = np.asarray(payload["pos"], dtype=dtype)
            rot = np.asarray(payload["rot"], dtype=dtype)
            scale = payload.get("scale")
            if scale is None:
                scale_arr = np.ones((pos.shape[0], 3), dtype=dtype)
            else:
                scale_arr = np.asarray(scale, dtype=dtype)
            n = int(pos.shape[0])
            if n == 0:
                continue
            idx = np.arange(i, i + n)
            rows = idx // side
            cols = idx % side
            # OpenCV BGRA → EXR：B=Z/100, G=Y/100, R=X/100, A=type
            bpt_img[rows, cols, 0] = pos[:, 2] / 100.0
            bpt_img[rows, cols, 1] = pos[:, 1] / 100.0
            bpt_img[rows, cols, 2] = pos[:, 0] / 100.0
            bpt_img[rows, cols, 3] = float(type_idx)
            # BRT：B=scale.Z G=scale.Y R=scale.X → UE RGB=(X,Y,Z)；A=rot_id
            brt_img[rows, cols, 0] = scale_arr[:, 2]
            brt_img[rows, cols, 1] = scale_arr[:, 1]
            brt_img[rows, cols, 2] = scale_arr[:, 0]
            brt_img[rows, cols, 3] = rot
            i += n
    else:
        i = 0
        for type_idx, transforms in enumerate(ue_data.values()):
            for transform in transforms:
                row = i // side
                col = i % side
                loc = transform.translation
                bpt_img[row, col, 0] = loc.z / 100.0
                bpt_img[row, col, 1] = loc.y / 100.0
                bpt_img[row, col, 2] = loc.x / 100.0
                bpt_img[row, col, 3] = float(type_idx)
                rot = transform.rotation
                sc = transform.scale3d
                brt_img[row, col, 0] = float(sc.z)
                brt_img[row, col, 1] = float(sc.y)
                brt_img[row, col, 2] = float(sc.x)
                brt_img[row, col, 3] = float(
                    _euler_to_rot_id(rot.pitch, rot.yaw, rot.roll)
                )
                i += 1

    if not os.path.exists(paths.cache):
        os.makedirs(paths.cache)

    bpt_path = os.path.join(paths.cache, f"{name}_BPT.exr")
    brt_path = os.path.join(paths.cache, f"{name}_BRT.exr")
    json_path = os.path.join(paths.cache, f"{name}_names.json")

    cv2.imwrite(bpt_path, bpt_img, [cv2.IMWRITE_EXR_TYPE, exr_type])
    cv2.imwrite(brt_path, brt_img, [cv2.IMWRITE_EXR_TYPE, exr_type])

    mapping_data = {idx: n for idx, n in enumerate(block_types)}
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(mapping_data, f, indent=4, ensure_ascii=False)

    unreal.log(f"成功导出贴图！\n位置图: {bpt_path}\n旋转图: {brt_path}\n索引表: {json_path}")

    BPT_Tex = _run_import_task(_make_import_task(bpt_path, paths.game + f'mc/structure'))[0]
    BRT_Tex = _run_import_task(_make_import_task(brt_path, paths.game + f'mc/structure'))[0]
    prep_texture(BPT_Tex, unreal.TextureCompressionSettings.TC_HDR_F32)
    prep_texture(BRT_Tex, unreal.TextureCompressionSettings.TC_HDR_F32)
    unreal.EditorAssetLibrary.set_metadata_tag(BPT_Tex, '方块映射', pformat(mapping_data))
    unreal.EditorAssetLibrary.set_metadata_tag(BRT_Tex, '方块映射', pformat(mapping_data))

    return BPT_Tex, BRT_Tex, mapping_data
