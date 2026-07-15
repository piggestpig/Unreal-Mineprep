import unreal
import importlib
from pathlib import Path
from mc_config import wclass
from mc_widget import Layout, copy

class mods():

    @staticmethod
    def register_all():
        mods_dir = Path(__file__).with_name('mods')
        if mods_dir.is_dir():
            for entry in sorted(mods_dir.iterdir()):
                if entry.name.startswith('_'):
                    continue
                if entry.is_file() and entry.suffix == '.py':
                    name = f'mods.{entry.stem}'
                elif entry.is_dir() and (entry / '__init__.py').is_file():
                    name = f'mods.{entry.name}'
                else:
                    continue
                mod = importlib.import_module(name)
                info = getattr(mod, 'mod_info', None)
                if info and info.get('EnabledByDefault') and callable(getattr(mod, 'register', None)):
                    mod.register()
                    unreal.log(f'已注册 mod: {name}')


class Mod():
    layout: Layout = None

    def __new__(cls):
        """在/Game/mc/mods/创建同名控件蓝图"""
        instance = super().__new__(cls)

        widget_path = f"/Game/mc/mods/{cls.__name__}"
        if not unreal.EditorAssetLibrary.does_asset_exist(widget_path):
            copy(wclass.mod_panel, widget_path)
            unreal.log(f"已创建自定义控件蓝图: {widget_path}")
        else:
            unreal.log(f"自定义控件蓝图已存在: {widget_path}")

        widget_bp = unreal.load_asset(widget_path)
        subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
        widget = subsystem.find_utility_widget_from_blueprint(widget_bp)

        if widget:
            instance.layout = Layout(widget.find_child_widget_by_name('Root'))
        else:
            instance.layout = Layout(widget_path)
        return instance