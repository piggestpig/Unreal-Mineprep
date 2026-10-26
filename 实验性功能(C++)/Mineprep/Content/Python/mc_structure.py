try:
    import unreal
except ModuleNotFoundError:
    from mc_utils import Lazy as unreal
import os
import gzip
import struct
import json
import math
import numpy as np
import mc_blockstates
from mc_structure_data import CellData, decode_varints
from pathlib import Path
from pprint import pformat
from mc_utils import warn, uclass, set_actor_label, select_actors
from mc_localization import loctable_col
from mc_config import paths
from mc_math import boxes_to_packed, decode_rotation, encode_rotation, validate_packed, partition_types
from mc_importer import (
    _make_import_task, _run_import_task, _load_mc_model,
    _model_data_is_full_cube, _resolve_texture_reference,
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
        # 保持 bytes，避免数百万元素的 list 与 bytes 往返转换
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


def _java_data(data):
    palette = [{'name':str(c.get('id',c.get('Name','air'))).replace('minecraft:',''),
                'properties':c.get('properties',c.get('Properties')) or {}}
               for c in data.get('palette',[])]
    blocks = data.get('blocks',[])
    size = data.get('size')
    return CellData([b.get('pos',[0,0,0]) for b in blocks],
                    [b.get('state',0) for b in blocks], palette,
                    tuple(map(int,size)) if size is not None else None)


def _bedrock_data(data):
    size = tuple(map(int,data.get('size',[0,0,0])))
    structure = data.get('structure',{})
    layers = structure.get('block_indices',[])
    if not layers or math.prod(size) <= 0:
        return CellData(source_size=size)
    default = structure.get('palette',{}).get('default',{})
    palette = [{'name':c.get('name','air').replace('minecraft:',''),
                'properties':c.get('states') or {}} for c in default.get('block_palette',[])]
    values = np.asarray(layers[0],np.int32).copy()
    for key, extra in (default.get('block_position_data') or {}).items():
        linear = int(key)
        entity = extra.get('block_entity_data') or {}
        if not 0 <= linear < len(values) or 'color' not in entity:
            continue
        t = int(values[linear])
        if 0 <= t < len(palette) and (palette[t]['name'] == 'bed' or palette[t]['name'].endswith('_bed')):
            cell = palette[t]
            values[linear] = len(palette)
            palette.append({'name':cell['name'], 'properties':{**cell['properties'],'color':entity['color']}})
    return CellData.linear(values,size,palette,order='xyz',source_size=size)


def _schematic_size(schem):
    return tuple(int(schem.get(key,0) or 0) & 0xFFFF for key in ('Width','Height','Length'))


def _byte_values(raw):
    return (np.frombuffer(raw,np.uint8) if isinstance(raw,(bytes,bytearray))
            else np.asarray(raw,np.int64).astype(np.uint8))


def _classic_data(schem):
    size = _schematic_size(schem)
    blocks = _byte_values(schem.get('Blocks') or b'')[:math.prod(size)]
    if math.prod(size) <= 0 or not len(blocks):
        return CellData(source_size=size)
    meta = _byte_values(schem.get('Data') or b'')
    pairs = blocks.astype(np.uint16) << 4
    count = min(len(meta),len(pairs))
    pairs[:count] |= meta[:count] & 15
    palette, remap = [], np.empty(4096,np.int32)
    for pair in np.unique(pairs):
        name, props = _legacy_id_to_block(int(pair)>>4,int(pair)&15) if pair>>4 else ('air',{})
        remap[pair] = len(palette)
        palette.append({'name':name,'properties':props})
    return CellData.linear(remap[pairs],size,palette,source_size=size)


def _sponge_data(data):
    schem = data.get('Schematic',data)
    size = _schematic_size(schem)
    tag = schem.get('Blocks')
    if isinstance(tag,dict) and ('Palette' in tag or 'Data' in tag):
        palette_map, raw = tag.get('Palette') or {}, tag.get('Data') or b''
    else:
        palette_map, raw = schem.get('Palette') or {}, schem.get('BlockData') or b''
    if not palette_map or not len(raw) or math.prod(size) <= 0:
        return CellData(source_size=size)
    inv = {i:state for state,i in palette_map.items()}
    keys = np.asarray(sorted(inv),np.uint32)
    palette = []
    for key in keys:
        name, props = _parse_blockstate_string(inv[int(key)])
        palette.append({'name':name,'properties':props})
    values = decode_varints(_byte_values(raw).tobytes())
    if not np.array_equal(keys,np.arange(len(keys),dtype=np.uint32)):
        at = np.searchsorted(keys,values)
        bounded = np.minimum(at,len(keys)-1)
        values = np.where((at < len(keys)) & (keys[bounded] == values),bounded,-1)
    unreal.log(f"Sponge schematic v{schem.get('Version',2)} ({size}, palette={len(palette)}, data={len(raw)}B)")
    return CellData.linear(values,size,palette,source_size=size)


def process_java_nbt(data):
    """将 Java 版 .nbt 数据解析为 {(x, y, z): {'name', 'properties'}} 稀疏字典。"""
    return _java_data(data).to_cells()


def process_bedrock_structure(data):
    """将基岩版 .mcstructure 数据解析为稀疏方块字典。"""
    return _bedrock_data(data).to_cells()


def process_classic_schematic(data):
    """将经典 .schematic 数据解析为稀疏方块字典。"""
    return _classic_data(data).to_cells()


def process_sponge_schematic(data):
    """将 Sponge .schem 数据解析为稀疏方块字典。"""
    return _sponge_data(data).to_cells()

# ==========================================
# 3. 方块状态映射与虚幻引擎数据结构组装
# ==========================================

# 高草/大型花卉：half=lower|upper → *_bottom / *_top
_DOUBLE_PLANT_NAMES = frozenset({
    "tall_grass", "large_fern", "sunflower", "lilac", "rose_bush", "peony",
    "pitcher_plant",
})


def _double_slab_model_name(slab_name):
    """type=double 时查 blockstate，多数映射到完整方块（stone_bricks 等）"""
    name = str(slab_name).lower().replace("minecraft:", "")
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
    """基岩 direction 0~3 或 Java facing -> north/east/south/west"""
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

    # 玻璃板属于多部件模型，在 _structure_parts 中展开

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
    """一个 MC 格子拆成 [(模型名, pitch, yaw, roll), ...]。"""
    name = str(raw_name).lower().replace("minecraft:", "")
    props = props or {}

    if name == 'chorus_plant':
        parts = []
        # 对应原版模型首个变体；MC 绕 X 轴旋转对应 UE Roll
        for direction, cap, yaw, roll in (
                ('north', 'noside', 0, 0), ('east', 'noside1', 90, 0),
                ('south', 'noside2', 180, 0), ('west', 'noside3', 270, 0),
                ('up', 'noside', 0, 90), ('down', 'noside3', 0, 270)):
            suffix = 'side' if _dir_connected(props, direction) else cap
            parts.append(('chorus_plant_' + suffix, 0., float(yaw), float(roll)))
        return parts

    if name.endswith("_fence"):
        parts = [(f"{name}_post", *_yaw_rot(0.0))]
        for direction, yaw in _FENCE_SIDE_YAW:
            if _dir_connected(props, direction):
                parts.append((f"{name}_side", *_yaw_rot(yaw)))
        return parts

    if name.endswith("_pane"):
        parts = [(f"{name}_post", *_yaw_rot(0.0))]
        for direction, conn_sfx, disc_sfx, conn_yaw, disc_yaw in _PANE_DIR_PARTS:
            connected = _dir_connected(props, direction)
            if connected:
                parts.append((f"{name}_{conn_sfx}", *_yaw_rot(conn_yaw)))
            else:
                parts.append((f"{name}_{disc_sfx}", *_yaw_rot(disc_yaw)))
        return parts

    if name == 'iron_bars':
        parts = [('iron_bars_post_ends', *_yaw_rot(0))]
        links = [d for d, _ in _FENCE_SIDE_YAW if _dir_connected(props, d)]
        if not links:
            parts.append(('iron_bars_post', *_yaw_rot(0)))
        for direction, yaw in _FENCE_SIDE_YAW:
            if direction not in links:
                continue
            suffix = '_alt' if direction in ('south', 'west') else ''
            angle = yaw % 180
            if len(links) == 1:
                parts.append(('iron_bars_cap' + suffix, *_yaw_rot(angle)))
            parts.append(('iron_bars_side' + suffix, *_yaw_rot(angle)))
        return parts

    if name.endswith('_wall') and any(k in props for k in ('up', 'north', 'east', 'south', 'west')):
        parts = []
        if str(props.get('up', 'true')).lower() == 'true':
            parts.append((name + '_post', *_yaw_rot(0)))
        for direction, yaw in _FENCE_SIDE_YAW:
            side = props.get(direction, 'none')
            if side in ('low', 'tall'):
                suffix = '_side_tall' if side == 'tall' else '_side'
                parts.append((name + suffix, *_yaw_rot(yaw)))
        return parts

    pitch, yaw, roll = _block_rotation(raw_name, props)
    return [(_structure_model_name(raw_name, props), pitch, yaw, roll)]


def structure_parts(name, properties=None):
    """将单个方块的名称与状态属性展开为 [(模型名, pitch, yaw, roll), ...]。

    楼梯等单模型方块返回单个元素；栅栏、玻璃板、铁栏杆、石墙等多部件方块会在同一格内拆分为柱体与各方向连接面。
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


_COLUMN_SUFFIXES = ("_log", "_wood", "_stem", "_hyphae", "_pillar")
_COLUMN_NAMES = frozenset({
    "basalt", "polished_basalt", "bone_block", "chain", "hay_block", "bamboo_block",
    "deepslate", "polished_deepslate", "deepslate_bricks", "deepslate_tiles",
    "cracked_deepslate_bricks", "cracked_deepslate_tiles",
    "ochre_froglight", "verdant_froglight", "pearlescent_froglight",
})
_COLUMN_EULER = {"x": (0.0, 90.0, 90.0), "z": (0.0, 0.0, 90.0), "y": (0.0, 0.0, 0.0)}


def _prop(props, *names):
    props = props or {}
    for name in names:
        if name in props:
            return props[name]
        prefixed = f"minecraft:{name}"
        if prefixed in props:
            return props[prefixed]
    return None


def _is_column_block(raw_name):
    if raw_name.endswith("_portal"):
        return False
    return raw_name in _COLUMN_NAMES or raw_name.endswith(_COLUMN_SUFFIXES)


def _column_euler(raw_name, props):
    if not _is_column_block(raw_name):
        return None
    axis = _prop(props, "pillar_axis", "axis")
    if axis is None:
        return None
    return _COLUMN_EULER.get(str(axis).lower())


def _is_standing_rot16(raw_name):
    """站立告示牌、旗帜、头颅使用 rotation (0~15)，墙挂款使用 facing。"""
    if (
        raw_name.endswith("_wall_sign") or raw_name in {"wall_sign", "wall_hanging_sign"}
        or raw_name.endswith("_wall_hanging_sign")
        or raw_name.endswith("_wall_banner")
        or raw_name.endswith("_wall_head") or raw_name.endswith("_wall_skull")
    ):
        return False
    return (
        raw_name == "sign" or raw_name.endswith("_sign") or raw_name.endswith("_hanging_sign")
        or raw_name.endswith("_banner")
        or raw_name.endswith("_head") or raw_name.endswith("_skull")
    )


def _rotation16_euler(raw_name, props):
    if not _is_standing_rot16(raw_name):
        return None
    raw = _prop(props, "rotation", "ground_sign_direction")
    if raw is None:
        return None
    try:
        step = int(raw) % 16
    except (TypeError, ValueError):
        return None
    return (0.0, step * 22.5, 0.0)


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

    column = _column_euler(raw_name, props)
    if column is not None:
        return column
    standing = _rotation16_euler(raw_name, props)
    if standing is not None:
        return standing

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
    """计算将结构包围盒底部中心对齐到原点的 UE 坐标偏移量（厘米）。"""
    if not sparse_dict:
        return 0.0, 0.0, 0.0

    if isinstance(sparse_dict, CellData):
        lo, hi = sparse_dict.bounds()
        half = BLOCK_SIZE / 2
        return (-float(lo[0]+hi[0])*half, -float(lo[2]+hi[2])*half, -float(lo[1])*BLOCK_SIZE)
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

    center_offset_x = ((min_x + max_x) * BLOCK_SIZE + BLOCK_SIZE) / 2.0
    center_offset_y = ((min_z + max_z) * BLOCK_SIZE + BLOCK_SIZE) / 2.0
    center_offset_z = min_y * BLOCK_SIZE
    return -center_offset_x, -center_offset_y, -center_offset_z


def _discrete_rot_id(rot):
    """0..23 返回整数编号；负 yaw 与其它值返回 None，不参与格盒合并。"""
    rot = float(rot)
    if rot < 0.0:
        return None
    nearest = int(round(rot))
    if abs(rot - nearest) > 1e-3 or nearest < 0 or nearest > 23:
        return None
    return nearest


def _is_leaves_model(model_name) -> bool:
    """树叶方块（正方体但不做 uvlock / 不合并）"""
    stem = str(model_name).lower().replace("minecraft:", "")
    return stem.endswith("_leaves") or stem == "leaves"


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
            if length == 1 and axis != 1:
                continue
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
    facts = _BlockModelFacts() if merge_mode > 0 else None

    for (mx, my, mz), block_info in sparse_dict.items():
        props = block_info["properties"]
        raw_name = block_info["name"]
        try:
            cache_key = (raw_name, frozenset((props or {}).items()))
        except TypeError:
            cache_key = (raw_name, id(props))
        parts = parts_cache.get(cache_key)
        if parts is None:
            parts = tuple((model, encode_rotation(pitch=pitch, yaw=yaw, roll=roll))
                          for model, pitch, yaw, roll in _structure_parts(raw_name, props))
            parts_cache[cache_key] = parts

        for model_name, rot in parts:
            discrete = _discrete_rot_id(rot)
            if (facts is not None and discrete is not None
                    and not _is_leaves_model(model_name) and facts.model(model_name)[2]):
                mergeable.setdefault((model_name, discrete), set()).add((mx, my, mz))
            else:
                passthrough.append((model_name, rot, mx, my, mz, 1, 1, 1))

    boxes = list(passthrough)
    for (model_name, rot_id), cells in mergeable.items():
        for x, y, z, sx, sy, sz in _merge_cells(cells, merge_mode):
            boxes.append((model_name, rot_id, x, y, z, sx, sy, sz))
    return boxes


def convert_to_unreal_transforms(sparse_dict, center=False, merge=0, *, origin=(0, 0, 0)):
    """将稀疏字典转换为 {方块名称: list(unreal.Transform)}；merge>0 时合并完整正方体"""
    rot_cache = {}
    lists = {}
    for model_name, payload in convert_to_packed_arrays(sparse_dict, center, merge, origin=origin).items():
        bucket = lists[model_name] = []
        for loc, code, scale in zip(payload['pos'], payload['rot'], payload['scale']):
            code = float(code)
            ue_rot = rot_cache.get(code)
            if ue_rot is None:
                pitch, yaw, roll = decode_rotation(code)
                ue_rot = unreal.Rotator(pitch=pitch, yaw=yaw, roll=roll)
                rot_cache[code] = ue_rot
            bucket.append(unreal.Transform(location=unreal.Vector(*map(float, loc)),
                                           rotation=ue_rot, scale=unreal.Vector(*map(float, scale))))
    return lists


def convert_to_packed_arrays(sparse_dict, center=False, merge=0, *, origin=(0, 0, 0)):
    """将稀疏方块字典转换为按模型分组的打包数组：{模型名: {'pos': (N,3), 'rot': (N,), 'scale': (N,3)}}。"""
    if center:
        origin = np.asarray(origin, dtype=np.float64) + _structure_center_offsets(sparse_dict)

    grouped = {}
    for model_name, rot_id, x, y, z, sx, sy, sz in _collect_merged_boxes(sparse_dict, merge=merge):
        grouped.setdefault(model_name, []).append((x, y, z, sx, sy, sz, rot_id))
    packed = {}
    for model, rows in grouped.items():
        rows = np.asarray(rows, dtype=np.float64)
        packed[model] = boxes_to_packed(rows[:, :3], rows[:, 3:6], rows[:, 6], origin=origin)
    return packed


_INSTANCE_BATCH = 8192


def add_packed_instances(ism, payload):
    """按批把 packed 的 pos/rot/scale 写入 ISM，批结束后释放 Transform 列表。"""
    payload = validate_packed(payload)
    pos = payload["pos"]
    rot = payload["rot"]
    scale = payload["scale"]
    count = int(len(pos))
    rot_cache = {}
    for start in range(0, count, _INSTANCE_BATCH):
        stop = min(start + _INSTANCE_BATCH, count)
        batch = []
        for i in range(start, stop):
            rot_value = float(rot[i])
            ue_rot = rot_cache.get(rot_value)
            if ue_rot is None:
                pitch, yaw, roll = decode_rotation(rot_value)
                ue_rot = unreal.Rotator(pitch=pitch, yaw=yaw, roll=roll)
                rot_cache[rot_value] = ue_rot
            point = pos[i]
            extent = scale[i]
            batch.append(unreal.Transform(
                location=unreal.Vector(float(point[0]), float(point[1]), float(point[2])),
                rotation=ue_rot,
                scale=unreal.Vector(float(extent[0]), float(extent[1]), float(extent[2])),
            ))
        ism.add_instances(batch, False, False, True)
        del batch


class _BlockModelFacts:
    """单次结构操作内的方块模型与贴图透明度查询缓存。"""

    def __init__(self):
        self.models, self.states, self.opacity, self.textures = {}, {}, {}, {}

    def model(self, name):
        if name not in self.models:
            path = resolve_block_json_path(name)
            data = {}
            try:
                if path is not None:
                    data = _load_mc_model(path)
            except (OSError, json.JSONDecodeError):
                pass
            self.models[name] = path, data, _model_data_is_full_cube(data)
        return self.models[name]

    def state_model(self, name, properties):
        key = name, frozenset(properties.items())
        if key not in self.states:
            parts = _structure_parts(name, properties)
            self.states[key] = parts[0][0] if len(parts) == 1 else None
        return self.states[key]

    def full(self, name, properties):
        model = self.state_model(name, properties)
        return model is not None and self.model(model)[2]

    def opaque(self, name, properties):
        model = self.state_model(name, properties)
        if model not in self.opacity:
            self.opacity[model] = self._opaque_model(model) if model is not None else False
        return self.opacity[model]

    def _opaque_model(self, model):
        path, data, full = self.model(model)
        textures = data.get('textures') or {}
        if not full or any(isinstance(v, dict) and v.get('force_translucent')
                           for v in textures.values()):
            return False
        from PIL import Image
        for element in data.get('elements') or ():
            for face in (element.get('faces') or {}).values():
                reference = face.get('texture')
                if not reference or reference in ('#overlay', 'overlay'):
                    continue  # 与导入器一致，跳过 #overlay 层
                texture = _resolve_texture_reference(path, textures, reference)
                if texture not in self.textures:
                    try:
                        with Image.open(texture) as image:
                            self.textures[texture] = image.convert('RGBA').getchannel('A').getextrema()[0] == 255
                    except OSError:
                        self.textures[texture] = False
                if not self.textures[texture]:
                    return False
        return True




def _fix_open_trapdoor_facings(sparse_dict, *, positions=None, facts=None):
    """修正错误 facing：开启活板门若恰有一个完整方块邻居，facing 应背离该邻居
    （与 test.schematic 灯柱一致；部分 .schem 导出 facing 错乱）。
    """
    if not sparse_dict:
        return sparse_dict

    facts = facts or _BlockModelFacts()
    # (邻格相对位移) → 背离该邻格时应有的 facing
    away_facing = {
        (1, 0, 0): "west",
        (-1, 0, 0): "east",
        (0, 0, 1): "north",
        (0, 0, -1): "south",
    }

    fixed = 0
    for pos in sparse_dict if positions is None else positions:
        info = sparse_dict[pos]
        name = str(info["name"]).lower().replace("minecraft:", "")
        if not name.endswith("_trapdoor"):
            continue
        props = info.get("properties") or {}
        if str(props.get("open", "false")).lower() != "true":
            continue

        hits = []
        for delta, facing in away_facing.items():
            npos = (pos[0] + delta[0], pos[1] + delta[1], pos[2] + delta[2])
            neighbour = sparse_dict.get(npos)
            if neighbour and facts.full(neighbour['name'], neighbour.get('properties') or {}):
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


def _sync_bedrock_door_halves(sparse_dict, *, positions=None):
    """下门的朝向为准（上门常被写成 south）。合页记在上门，抄到下门。"""
    if not sparse_dict:
        return sparse_dict
    for pos in sparse_dict if positions is None else positions:
        info = sparse_dict[pos]
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


def _fix_pane_connections(sparse_dict, *, facts=None):
    """只补全完全缺少连接属性的玻璃板；保留明确写入的 false。"""
    keys = tuple(k for d in mc_blockstates.DIRECTIONS
                 for k in (d, 'minecraft:connection_' + d, 'connection_' + d))
    def missing(cell):
        return (str(cell['name']).endswith('_pane')
                and not any(k in (cell.get('properties') or {}) for k in keys))
    pending = (sparse_dict.positions(missing) if isinstance(sparse_dict, CellData)
               else (p for p,cell in sparse_dict.items() if missing(cell)))
    mc_blockstates.connect(sparse_dict, is_full_cube=(facts or _BlockModelFacts()).full,
                           families=('pane',), positions=pending)
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
    """按模式剔除被遮挡的内部方块（兼容稀疏字典与 CellData）。"""
    mode = int(cull)
    if mode not in (1,2,3):
        return sparse_dict
    numeric = isinstance(sparse_dict, CellData)
    data = sparse_dict if numeric else CellData.from_cells(sparse_dict)
    data.cull(mode, _BlockModelFacts())
    return data if numeric else data.to_cells()


def _load_structure_data(filepath, *, repair_trapdoors=False):
    """读取结构文件，并执行玻璃板连接补全与基岩版上下门同步。"""
    if not filepath or not os.path.exists(filepath):
        unreal.log_error(f"未能找到结构文件: {filepath}")
        return CellData()

    ext = os.path.splitext(filepath)[1].lower()
    if ext in ['.nbt', '.schematic', '.schem']:
        with gzip.open(filepath, 'rb') as f:
            nbt_data = load_nbt_file(f, endian='>')
    elif ext == '.mcstructure':
        with open(filepath, 'rb') as f:
            nbt_data = load_nbt_file(f, endian='<')
    else:
        unreal.log_warning(f"不支持的文件格式: {ext}")
        return CellData()

    if ext == '.nbt':
        data = _java_data(nbt_data)
    elif ext == '.schematic':
        data = _classic_data(nbt_data.get('Schematic',nbt_data))
    elif ext == '.schem':
        data = _sponge_data(nbt_data)
    else:
        data = _bedrock_data(nbt_data)

    facts = _BlockModelFacts()
    if repair_trapdoors:
        positions = data.positions(lambda c:c['name'].endswith('_trapdoor'))
        _fix_open_trapdoor_facings(data, positions=positions, facts=facts)
    _fix_pane_connections(data, facts=facts)
    positions = data.positions(lambda c:c['name'].endswith('_door')
                               and 'upper_block_bit' in c['properties'])
    _sync_bedrock_door_halves(data, positions=positions)
    return data


def _load_structure_sparse(filepath, *, repair_trapdoors=False):
    data = _load_structure_data(filepath,repair_trapdoors=repair_trapdoors)
    return data.to_cells(), data.source_size


# ==========================================
# 结构解析入口
# ==========================================

def parse_structure(filepath='', center=False, cull=0, packed=False, merge=0, *, repair_trapdoors=False):
    """解析 .nbt/.schem/.mcstructure。
    packed=False → {方块名: [Transform]}（ISM）
    packed=True  → {方块名: {"pos":[...], "rot":[...], "scale":[...]}}（PCG/粒子）
    cull=1 按类型剔除内部；cull=2 不透明完整块统一遮挡，透明完整块只遮挡同类；
    cull=3 在 2 基础上再剔除 AABB 侧面与底面（保留顶面）
    merge=0 关；1 长条；2 平面；3 长方体（仅完整正方体；cull 优先于 merge）
    repair_trapdoors=True 才按邻居猜测开启活板门朝向；默认保留文件原状态。
    """
    from time import perf_counter
    started = perf_counter()
    sparse_dict = _load_structure_data(filepath, repair_trapdoors=repair_trapdoors)
    if not sparse_dict:
        return {}

    origin = _structure_center_offsets(sparse_dict) if center else (0, 0, 0)
    sparse_dict = _apply_cull(sparse_dict, cull)
    merge_mode = int(merge)
    if packed:
        ue_data = convert_to_packed_arrays(sparse_dict, merge=merge_mode, origin=origin)
        total = sum(len(v["pos"]) for v in ue_data.values())
    else:
        ue_data = convert_to_unreal_transforms(sparse_dict, merge=merge_mode, origin=origin)
        total = sum(len(v) for v in ue_data.values())

    unreal.log(
        f"结构解析完成: {len(ue_data)} 种方块, {total} 个实例 "
        f"(文件 {os.path.basename(filepath)}, packed={packed}, cull={int(cull)}, merge={merge_mode}, "
        f"CPU {perf_counter()-started:.3f}s)"
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
        self._source_size = None

    @property
    def source_size(self):
        """从结构文件加载时的原始尺寸 (X, Y, Z)；手动创建的实例为 None。"""
        return self._source_size

    def bounds(self):
        """实时计算当前非空气方块的坐标范围 (lo, hi)，hi 为开区间上界；为空时返回 None。"""
        positions = (p for p, cell in self._cells.items()
                     if cell['name'].removeprefix('minecraft:') not in ('air', 'cave_air', 'void_air'))
        first = next(positions, None)
        if first is None:
            return None
        lo, hi = list(first), list(first)
        for point in positions:
            for axis in range(3):
                if point[axis] < lo[axis]:
                    lo[axis] = point[axis]
                if point[axis] > hi[axis]:
                    hi[axis] = point[axis]
        return tuple(map(int, lo)), tuple(int(v) + 1 for v in hi)

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
        """兼容旧接口：仅重新计算栅栏、玻璃板与铁栏杆的连接状态。"""
        return self.connect(families=('fence', 'pane'))

    def connect(self, *, families=None, positions=None):
        """根据邻接关系更新栅栏、玻璃板、铁栏杆、石墙、栅栏门和楼梯的连接状态。"""
        mc_blockstates.connect(self._cells, is_full_cube=_BlockModelFacts().full,
                               families=families, positions=positions)
        return self

    def rotate(self, rotation=90, *, pivot=(0, 0, 0)):
        """绕 pivot（MC 格子中心坐标）顺时针旋转结构（90 度的倍数），同步更新坐标与朝向。"""
        self._cells = mc_blockstates.rotate_cells(self._cells, rotation, pivot=pivot)
        return self

    def mirror(self, axis='x', *, pivot=0):
        """沿 MC 的 X 或 Z 轴镜像翻转结构，同步更新坐标与朝向。"""
        self._cells = mc_blockstates.mirror_cells(self._cells, axis, pivot=pivot)
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
    def from_file(cls, filepath, *, repair_trapdoors=False):
        """从结构文件（.nbt / .schem / .schematic / .mcstructure）加载可编辑的 Blocks 实例。"""
        cells, source_size = _load_structure_sparse(filepath, repair_trapdoors=repair_trapdoors)
        result = cls(name=Path(filepath).stem, cells=cells, copy=False)
        result._source_size = source_size
        return result

    def bake(self, *, destination_path="/Game/mc/baked", asset_name=None,
             pivot=(0, 0, 0), cull="opaque", merge_faces=True, reload=False,
             two_sided=None):
        """将当前方块烘焙并保存为单个 StaticMesh 资产，不向场景放置 Actor。

        pivot 为模型轴心所在的 MC 格子中心坐标。
        cull 可选 'opaque'（默认，剔除不透明邻格遮挡面）、'same'（同时剔除同类透明方块的相邻面）或 'none'。
        two_sided 可显式指定双面或单面材质；默认 None 在 cull='same' 时使用双面材质。
        目标路径已存在不同配方的网格时需传入 reload=True 覆盖。
        """
        from mc_mesh import bake_blocks
        return bake_blocks(self, destination_path=destination_path,
                           asset_name=asset_name, pivot=pivot, cull=cull,
                           merge_faces=merge_faces, reload=reload, two_sided=two_sided)

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

    def spawn(self, *, loc=(0, 0, 0), rot=(0, 0, 0), gpu=0, cull=0, merge=0,
              reload=False, name='', center=False, groups=1):
        """将当前 Blocks 生成到关卡中，参数与 spawn_structure 一致，返回生成的 Actor 列表。"""
        return spawn_structure(self, loc=loc, rot=rot, gpu=gpu, cull=cull,
                               merge=merge, reload=reload, name=name, center=center, groups=groups)


def spawn_structure(source='', loc=(0,0,0), rot=(0,0,0), gpu=0, cull=0, merge=0,
                    reload=False, name='', center=False, *, groups=1,
                    repair_trapdoors=False) -> list[unreal.Actor]:
    """在关卡中生成 MC 结构。source 可为文件路径或 Blocks 实例。
    gpu=0 使用实例化静态网格体 (ISM)，gpu=1 使用 PCG，gpu=2 使用 Niagara 粒子。
    cull=1 按同类剔除内部；cull=2 不透明完整块统一遮挡、透明完整块仅遮挡同类；
    cull=3 在 2 的基础上继续剔除包围盒侧面与底面（仅保留顶面）。
    merge=0 不合并，1 合并长条，2 合并平面，3 合并长方体（仅合并完整正方体，在 cull 之后执行）。
    groups 指定 GPU 模式的分组数（单组最多 256 种模型，超出时自动增加分组并发出警告；后续 Actor 自动挂载到首个 Actor 下）。
    repair_trapdoors=True 时按邻接实心方块修正旧版导出中错乱的开启活板门朝向。
    """
    from time import perf_counter
    started = perf_counter()
    if type(groups) is not int or groups < 1:
        raise ValueError('groups must be a positive integer')
    if not gpu and groups != 1:
        raise ValueError('groups > 1 requires PCG (gpu=1) or Niagara (gpu=2)')
    if gpu not in (0, 1, 2):
        raise ValueError('gpu must be 0, 1 or 2')
    if isinstance(source, Blocks):
        filename = name or source.name or 'structure'
        cells = source.copy_cells()
    else:
        if not source:
            warn('spawn_structure 需要文件路径或 Blocks')
            return []
        loaded = _load_structure_data(source, repair_trapdoors=repair_trapdoors)
        if not loaded:
            return []
        filename = name or Path(str(source)).stem
        cells = loaded

    read_done = perf_counter()
    origin = _structure_center_offsets(cells) if center else (0, 0, 0)
    cells = _apply_cull(cells, cull)
    payload_map = convert_to_packed_arrays(cells, merge=merge, origin=origin)
    cells = None
    process_done = perf_counter()
    if not any(len(p['pos']) for p in payload_map.values()):
        return []

    inventory = loctable_col(6,2)
    actors = []
    meshes = {}
    available = {}

    for model_name, payload in payload_map.items():
        if not len(payload['pos']):
            continue
        try:
            path = resolve_block_json_path(model_name)
            if path is None:
                # 只接受同名或下划线后的后缀，避免 bed 匹配到 bedrock
                candidate = next((n for n in inventory if n == model_name or n.startswith(f'{model_name}_')), None)
                path = resolve_block_json_path(candidate) if candidate else None
            if path is not None:
                mesh = import_block(path, asset_name=model_name, reload=reload)
            else:
                warn(f'未找到{model_name}模型')
                continue
            if mesh is None:
                warn(f'导入{model_name}模型失败，已跳过')
                continue
        except Exception as exc:
            warn(f'导入{model_name}模型失败，已跳过: {exc}')
            continue
        meshes[model_name] = mesh
        available[model_name] = payload
    payload_map = available
    if not payload_map:
        return []
    models_done = perf_counter()

    if not gpu:
        loaded_class = uclass('/Game/Mineprep/MC_Blueprint/Core/实例化方块.实例化方块')
        for model_name, payload in payload_map.items():
            actor = unreal.EditorLevelLibrary.spawn_actor_from_class(loaded_class, loc, rot)
            ism = actor.root_component
            ism.set_editor_property('StaticMesh', meshes[model_name])
            ism.clear_instances()
            add_packed_instances(ism, payload)
            actor.set_folder_path(filename)
            actors.append(actor)
            set_actor_label(actor, f'{filename}_{model_name}')

    else:
        names = tuple(payload_map)
        counts = [len(payload_map[n]['pos']) for n in names]
        if gpu == 1:
            # PCG 按模型种类数均分即可，无需像 Niagara 那样按实例数优化渲染代价
            count = min(len(names), max(groups, (len(names) + 255) // 256))
            size, extra = divmod(len(names), count)
            layouts, start = [], 0
            for i in range(count):
                end = start + size + (i < extra)
                layouts.append((tuple(range(start, end)), sum(counts[start:end])))
                start = end
        else:
            layouts = partition_types(names, counts, groups, max_types=256)
        if len(layouts) > groups:
            warn(f'{"PCG" if gpu == 1 else "Niagara"}: {len(names)} 种模型，单个 Actor 最多 256 种；'
                 f'groups 已自动从 {groups} 提高到 {len(layouts)}')
            groups = len(layouts)
        limit = (unreal.SystemLibrary.get_console_variable_int_value('fx.MaxNiagaraGPUParticlesSpawnPerFrame')
                 if gpu == 2 else 0)
        # 写入纹理前先校验各组的纹理尺寸与 Niagara 单帧粒子上限
        for i, (ids, count) in enumerate(layouts, 1):
            side = math.isqrt(count - 1) + 1
            if side > 16384:
                raise ValueError(f'group {i}: texture dimension capacity exceeded; types are indivisible')
            if limit > 0 and side * side > limit:
                raise ValueError(f'Niagara group {i}: {count} instances require {side*side} spawn slots; '
                                 f'fx.MaxNiagaraGPUParticlesSpawnPerFrame={limit}; types are indivisible')
        loaded_class = uclass('/Game/Mineprep/MC_Blueprint/PCG/PCG实例化方块.PCG实例化方块' if gpu == 1 else
                              '/Game/Mineprep/MC_Blueprint/Niagara/动态地形粒子/动态结构粒子.动态结构粒子')
        if loaded_class is None:
            raise RuntimeError('structure Actor class missing')
        prepared = []
        for i, (ids, _) in enumerate(layouts, 1):
            label = filename if groups == 1 else f'{filename}_{i}'
            payloads = {names[t]: payload_map[names[t]] for t in ids}
            bpt, brt, _ = structure_to_tex(payloads, label)
            if bpt is None or brt is None:
                raise RuntimeError('structure texture import failed: ' + label)
            prepared.append((label, [meshes[n] for n in payloads], bpt, brt))
        # 将所有分组 Actor 的生成与父子挂载合并到同一个撤销事务中
        with unreal.ScopedEditorTransaction('Mineprep: place ' + filename) as transaction:
            try:
                for label, palette, bpt, brt in prepared:
                    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(loaded_class, loc, rot)
                    if actor is None:
                        raise RuntimeError('structure Actor creation failed')
                    actors.append(actor)
                    actor.modify()
                    actor.set_folder_path('Structures')
                    set_actor_label(actor, label)
                    if gpu == 1:
                        actor.set_editor_properties(dict(
                            Blocks=[unreal.SystemLibrary.get_soft_object_path(m) for m in palette],
                            PosTex=bpt, RotTex=brt))
                    else:
                        actor.set_editor_property('方块', palette)
                        actor.root_component.set_variable_texture('方块位置纹理', bpt)
                        actor.root_component.set_variable_texture('方块旋转纹理', brt)
                if len(actors) > 1:
                    keep = unreal.AttachmentRule.KEEP_WORLD
                    actors[0].root_component.modify()
                    for actor in actors[1:]:
                        actor.root_component.modify()
                        if not actor.attach_to_actor(parent_actor=actors[0], socket_name='',
                                location_rule=keep, rotation_rule=keep, scale_rule=keep,
                                weld_simulated_bodies=False):
                            raise RuntimeError('structure Actor attachment failed')
            except Exception as exc:
                subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
                residual = []
                for actor in reversed(actors):
                    if not unreal.SystemLibrary.is_valid(actor):
                        continue
                    try:
                        if not subsystem.destroy_actor(actor):
                            residual.append(actor.get_path_name())
                    except Exception:
                        residual.append(actor.get_path_name())
                if residual:
                    raise RuntimeError(f'{exc}; residual Actors: {residual}') from exc
                transaction.cancel()
                raise

    select_actors(actors)
    unreal.log(f'结构提交耗时: 源数据 {read_done-started:.3f}s; '
               f'剔除/合并 {process_done-read_done:.3f}s; 模型 {models_done-process_done:.3f}s; '
               f'输出 {perf_counter()-models_done:.3f}s; 总计 {perf_counter()-started:.3f}s')
    return actors


def _is_packed_structure_data(ue_data) -> bool:
    """判断是否为 packed 格式 {name: {pos, rot, scale?}}"""
    if not ue_data:
        return False
    sample = next(iter(ue_data.values()))
    return isinstance(sample, dict) and "pos" in sample and "rot" in sample


def import_structure_textures(files, destination=None):
    """将生成的 BPT/BRT EXR 贴图导入为 UE 资产并写入方块映射元数据。"""
    destination = destination or paths.game + 'mc/structure'
    textures = []
    for key in ('BPT', 'BRT'):
        imported = _run_import_task(_make_import_task(files[key], destination))
        if not imported:
            raise RuntimeError(f'{key} texture import failed')
        texture = imported[0]
        prep_texture(texture, unreal.TextureCompressionSettings.TC_HDR_F32)
        if 'side' in files and (texture.blueprint_get_size_x() != files['side']
                                or texture.blueprint_get_size_y() != files['side']):
            raise RuntimeError('imported structure texture size does not match encoded data')
        unreal.EditorAssetLibrary.set_metadata_tag(texture, '方块映射', pformat(files['mapping']))
        textures.append(texture)
    return textures[0], textures[1], files['mapping']


def structure_to_tex(ue_data, name='structure', fp32=True):
    """将结构数据编码为 BPT/BRT 贴图并导入到 UE（支持 Transform 列表或打包数组格式）。"""
    from mc_structure_tex import write_structure_textures
    if not ue_data:
        unreal.log_warning('ue_data 为空，取消贴图导出。')
        return
    if _is_packed_structure_data(ue_data):
        payloads = ue_data
    else:
        payloads = {}
        for model, transforms in ue_data.items():
            payloads[model] = {
                'pos': np.array([[t.translation.x, t.translation.y, t.translation.z]
                                 for t in transforms], dtype=np.float32).reshape(-1, 3),
                'rot': np.array([encode_rotation(t.rotation.pitch, t.rotation.yaw, t.rotation.roll)
                                 for t in transforms], dtype=np.float32),
                'scale': np.array([[t.scale3d.x, t.scale3d.y, t.scale3d.z]
                                   for t in transforms], dtype=np.float32).reshape(-1, 3),
            }
    if not any(len(p['pos']) for p in payloads.values()):
        unreal.log_warning('未发现有效的方块转换数据，取消贴图导出。')
        return
    files = write_structure_textures(payloads, paths.cache, name, fp32)
    return import_structure_textures(files)
