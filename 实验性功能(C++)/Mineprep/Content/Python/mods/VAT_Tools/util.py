"""VAT Tools 共享常量与小工具。"""

import unreal
import mineprep

BONE_POSITION_SUFFIX = 'BPT📍'
BONE_ROTATION_SUFFIX = 'BRT↻'
BONE_WEIGHTS_SUFFIX = 'BWT📊'
PREMUL_SUFFIX = '预乘'

MC_VAT_CLASS_PATH = (
    '/Game/Mineprep/MC_Blueprint/Niagara/Core/MC_VAT数据资产.MC_VAT数据资产_C'
)

MAT_BPT = '/Game/Mineprep/生物模型rigs/VAT粒子/VAT烘焙BPT材质.VAT烘焙BPT材质'
MAT_BRT = '/Game/Mineprep/生物模型rigs/VAT粒子/VAT烘焙BRT材质.VAT烘焙BRT材质'
MAT_BWT = '/Game/Mineprep/生物模型rigs/VAT粒子/VAT烘焙BWT材质.VAT烘焙BWT材质'
MIC_TEMPLATE = '/Game/Mineprep/生物模型rigs/VAT粒子/VAT纹理集合材质_Inst.VAT纹理集合材质_Inst'


def notify(msg: str):
    mineprep.prints(msg)


def asset_tools():
    return unreal.AssetToolsHelpers.get_asset_tools()


def save(asset: unreal.Object | None):
    if asset:
        unreal.EditorAssetLibrary.save_loaded_asset(asset)


def world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def display_name(obj: unreal.Object | None) -> str:
    if not obj:
        return ''
    try:
        return unreal.SystemLibrary.get_display_name(obj)
    except Exception:
        return obj.get_name()


def package_path(obj: unreal.Object) -> str:
    path = obj.get_path_name()
    if '.' in path:
        path = path.rsplit('.', 1)[0]
    return path


def package_dir(obj: unreal.Object) -> str:
    path = package_path(obj)
    return path.rsplit('/', 1)[0] if '/' in path else path


def load_or_none(directory: str, name: str):
    full = f'{directory}/{name}'
    if unreal.EditorAssetLibrary.does_asset_exist(full):
        return unreal.load_asset(full)
    return None


def create_asset(directory: str, name: str, asset_class, factory=None):
    existing = load_or_none(directory, name)
    if existing:
        return existing
    asset = asset_tools().create_asset(name, directory, asset_class, factory)
    save(asset)
    return asset


def duplicate_or_load(directory: str, name: str, original: unreal.Object):
    existing = load_or_none(directory, name)
    if existing:
        return existing
    asset = asset_tools().duplicate_asset(name, directory, original)
    save(asset)
    return asset


def ensure_dir(directory: str) -> str:
    directory = (directory or '').rstrip('/')
    if not directory:
        raise ValueError('保存路径为空')
    if not unreal.EditorAssetLibrary.does_directory_exist(directory):
        unreal.EditorAssetLibrary.make_directory(directory)
    return directory


def delete_dir(directory: str) -> bool:
    """删除 Content 目录（如 .../cache）。"""
    directory = (directory or '').rstrip('/')
    if not directory or not unreal.EditorAssetLibrary.does_directory_exist(directory):
        return False
    return bool(unreal.EditorAssetLibrary.delete_directory(directory))


def vec3_to_linear(v) -> unreal.LinearColor:
    if v is None:
        return unreal.LinearColor(0.0, 0.0, 0.0, 1.0)
    return unreal.LinearColor(float(v.get_editor_property('x')),
                              float(v.get_editor_property('y')),
                              float(v.get_editor_property('z')),
                              1.0)


def int_xy_to_linear(x: int, y: int = 0, z: int = 0) -> unreal.LinearColor:
    return unreal.LinearColor(float(x), float(y), float(z), 1.0)


def texture_size(tex: unreal.Texture2D) -> tuple[int, int]:
    try:
        return int(tex.blueprint_get_size_x()), int(tex.blueprint_get_size_y())
    except Exception:
        return 256, 256


def assign_soft_prop(props, name: str, asset: unreal.Object):
    """可靠写入 SoftObjectPath（UE5.8 SoftObjectPath(str) 构造可能为空）。"""
    if not asset:
        return
    sp = unreal.SoftObjectPath()
    sp.import_text(asset.get_path_name())
    props.uobject.set_editor_property(name, sp)


def resolve_mc_vat(value):
    """SoftObjectPath / 已加载资产 → MC_VAT（AnimToTextureDataAsset 子类）。"""
    if value is None:
        return None
    if isinstance(value, unreal.AnimToTextureDataAsset):
        return value
    path = None
    if isinstance(value, unreal.SoftObjectPath):
        try:
            path = value.export_text()
        except Exception:
            path = str(value)
    elif isinstance(value, str):
        path = value
    if not path:
        return None
    path = path.strip().strip("'\"")
    if "'" in path:
        path = path.split("'")[-2] if path.count("'") >= 2 else path
    asset = unreal.load_asset(path)
    return asset if isinstance(asset, unreal.AnimToTextureDataAsset) else None


def strip_da_vat_prefix(name: str) -> str:
    """去掉资产名开头的 DA_VAT_（若有）。"""
    prefix = 'DA_VAT_'
    if name and name.startswith(prefix):
        return name[len(prefix):]
    return name or ''


def open_mod_script():
    import pathlib
    mineprep.startfile(str(pathlib.Path(__file__).resolve().parent))
