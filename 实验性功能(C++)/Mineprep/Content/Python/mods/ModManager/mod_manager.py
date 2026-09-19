import sys
import shutil
import zipfile
from pathlib import Path
from pprint import pformat
from functools import partial

import unreal
import mineprep
from mineprep import bilingual, Layout, askopenfilename, send2trash, dialog
from mc_mod import iter_mod_modules

MODS_DIR = Path(__file__).resolve().parent.parent


class Props(mineprep.PropertyGroup):
    _unique_ = True
    _autosave_ = True
    advanced: bool = False

props = Props()


def _mod_stem(name):
    return name[5:] if name.startswith('mods.') else name


def _info(name, info):
    desc = str(info.get('Description') or '')
    text = f'<{_mod_stem(name)}>\n{desc}'
    if props.advanced:
        body = {
            k: v if isinstance(v, (bool, int, float)) or v is None else str(v)
            for k, v in info.items()
        }
        text += f'\n\n{pformat(body, sort_dicts=False)}'
    return text


class ModManager(mineprep.Mod):
    _unique_ = True
    _label_ = bilingual("模组管理器", "Mod Manager")

    def draw(self, context=None):
        layout = self.layout
        layout.button(bilingual("安装模组", "Install Mod"), on_clicked=self.install_mod)

        header = layout.row(padding=(3,9))
        header.scalebox(align=2,fill=1).text(bilingual("模组", "Mod"), align=2)
        header.scalebox(align=2,fill=1).text(bilingual("版本", "Version"), align=2)
        header.scalebox(align=2,fill=1).text(bilingual("状态", "Status"), align=2)
        header.scalebox(align=2,fill=1).text(bilingual("操作", "Action"), align=2)
        if props.advanced:
            header.scalebox(align=2,fill=0.75).text(bilingual("卸载", "Uninstall"), align=2)

        # 跳过自身模组；Advanced 模组排在后面，且仅在勾选高级选项时显示
        normal, extra = [], []
        for name, mod in iter_mod_modules():
            if self.__class__.__module__ == name or self.__class__.__module__.startswith(name + '.'):
                continue
            info = getattr(mod, 'mod_info', None) or {}
            (extra if info.get('Advanced') else normal).append((name, mod))
        for name, mod in normal:
            self.add_mod_row(layout, name, mod)
        if props.advanced:
            for name, mod in extra:
                self.add_mod_row(layout, name, mod)

        layout.prop(props, "advanced", bilingual("显示高级选项", "Show Advanced Options"),
                    on_property_changed=lambda x: self.redraw(),
                    align=(1, 3), fill=1)


    def add_mod_row(self, parent: Layout, name, mod):
        info = getattr(mod, "mod_info", None) or {}
        enabled = bool(info.get("EnabledByDefault"))
        mod_name = info.get("Name", _mod_stem(name))
        version = str(info.get("Version", "-"))
        status = bilingual("已启用", "Enabled") if enabled else bilingual("已禁用", "Disabled")
        color = unreal.LinearColor(1,1,1,1) if enabled else unreal.LinearColor(1,1,1,0.5)

        row = parent.row()
        row.scalebox(align=2,fill=1).text(mod_name, align=2, color=color, tooltip=_info(name, info))
        row.scalebox(align=2,fill=1).text(version, align=2, color=color)
        row.scalebox(align=2,fill=1).text(status, align=2, color=color)
        if enabled:
            row.scalebox(align=2,fill=1).button(bilingual("禁用", "Disable"),
                    on_clicked=partial(self.disable_mod, mod), align=2, fill=1)
        else:
            row.scalebox(align=2,fill=1).button(bilingual("启用", "Enable"),
                    on_clicked=partial(self.enable_mod, mod), align=2, fill=1)
        if props.advanced:
            row.scalebox(align=2,fill=0.75).button("🗑️", text_padding=(0,2),
                    on_clicked=partial(self.uninstall_mod, name, mod), align=2, fill=1)


    def enable_mod(self, mod):
        mineprep.mods.register(mod)
        self.redraw()


    def disable_mod(self, mod):
        mineprep.mods.unregister(mod)
        self.redraw()


    def install_mod(self):
        path = askopenfilename(
            title=str(bilingual("选择模组 (.py / .zip)", "Select Mod (.py / .zip)")),
            filetypes=[
                (str(bilingual("Python / 压缩包", "Python / Archive")), "*.py *.zip"),
                ("Python", "*.py"),
                ("Zip", "*.zip"),
            ]
        )
        if not path:
            return

        src = Path(path)
        if src.suffix.lower() == '.py':
            shutil.copy2(src, MODS_DIR / src.name)
        elif src.suffix.lower() == '.zip':
            with zipfile.ZipFile(src) as zf:
                zf.extractall(MODS_DIR)
        else:
            mineprep.warn(bilingual(f"不支持的文件类型: {src.suffix}", f"Unsupported file type: {src.suffix}"))
            return
        mineprep.prints(bilingual(f"已安装模组: {src.name}", f"Installed mod: {src.name}"))
        self.redraw()


    def uninstall_mod(self, name, mod):
        info = getattr(mod, "mod_info", None) or {}
        stem = _mod_stem(name)
        display = str(info.get("Name") or stem)
        if dialog(bilingual(f'卸载 {display}', f'Uninstall {display}'),
                  bilingual(f'你确定要删除这个模组吗？\n"{stem}"将会消失很久！（真的很久！）',
                            f'Are you sure you want to delete this mod?\n"{stem}" will be lost forever! (A long time!)')):

            mineprep.mods.unregister(mod)
            target = MODS_DIR / f"{stem}.py"
            if not target.exists():
                target = MODS_DIR / stem
            send2trash(target)

            for key in list(sys.modules):
                if key == name or key.startswith(name + '.'):
                    sys.modules.pop(key, None)
            mineprep.prints(bilingual(f"已卸载模组: {stem}", f"Uninstalled mod: {stem}"))
            self.redraw()
