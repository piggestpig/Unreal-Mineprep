from pathlib import Path
from pprint import pformat
from functools import partial

import unreal
import mineprep
import mcvars
from mineprep import i18n, Layout, askopenfilename, asksaveasfilename, dialog
from mc_mod import iter_mod_infos
from . import ops

MODS_DIR = Path(__file__).resolve().parent.parent


class Props(mineprep.PropertyGroup):
    _unique_ = True
    _autosave_ = True
    advanced: bool = False

Props.localize()

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
    _label_ = i18n("模组管理器", "Mod Manager")
    _menu_ = "modules"

    def draw(self, context=None):
        layout = self.layout
        layout.button(i18n("安装模组", "Install Mod"), on_clicked=self.install_mod)

        header = layout.row(padding=(3,9))
        header.scalebox(align=2,fill=1).text(i18n("模组", "Mod"), align=2)
        header.scalebox(align=2,fill=1).text(i18n("版本", "Version"), align=2)
        header.scalebox(align=2,fill=1).text(i18n("状态", "Status"), align=2)
        header.scalebox(align=2,fill=1).text(i18n("操作", "Action"), align=2)
        if props.advanced:
            header.scalebox(align=2,fill=0.75).text(i18n("卸载", "Uninstall"), align=2)

        # 跳过自身模组；Advanced 模组排在后面，且仅在勾选高级选项时显示
        normal, extra = [], []
        for name, info in iter_mod_infos():
            if self.__class__.__module__ == name or self.__class__.__module__.startswith(name + '.'):
                continue
            (extra if info.get('Advanced') else normal).append((name, info))
        for name, info in normal:
            self.add_mod_row(layout, name, info)
        if props.advanced:
            for name, info in extra:
                self.add_mod_row(layout, name, info)

        layout.prop(props, "advanced", i18n("显示高级选项", "Show Advanced Options"),
                    on_property_changed=lambda x: self.redraw(),
                    align=(1, 3), fill=1)


    def add_mod_row(self, parent: Layout, name, info):
        enabled = name in mcvars.EnabledMods
        mod_name = info.get("Name", _mod_stem(name))
        version = str(info.get("Version", "-"))
        status = i18n("已启用", "Enabled") if enabled else i18n("已禁用", "Disabled")
        color = unreal.LinearColor(1,1,1,1) if enabled else unreal.LinearColor(1,1,1,0.5)

        row = parent.row()
        row.scalebox(align=2,fill=1).text(mod_name, align=2, color=color, tooltip=_info(name, info))
        row.scalebox(align=2,fill=1).text(version, align=2, color=color)
        row.scalebox(align=2,fill=1).text(status, align=2, color=color)
        actions = row.scalebox(align=2,fill=1).row()
        if enabled:
            actions.button(i18n("禁用", "Disable"),
                    on_clicked=partial(self.disable_mod, name), align=2, fill=1)
        else:
            actions.button(i18n("启用", "Enable"),
                    on_clicked=partial(self.enable_mod, name), align=2, fill=1)
        if props.advanced:
            actions.button(i18n("打包", "Package"), on_clicked=partial(self.package_mod, name), align=2, fill=1)
            row.scalebox(align=2,fill=0.75).button("🗑️", text_padding=(0,2),
                    on_clicked=partial(self.uninstall_mod, name, info), align=2, fill=1)


    def enable_mod(self, mod):
        mineprep.mods.register(mod)
        self.redraw()


    def disable_mod(self, mod):
        mineprep.mods.unregister(mod)
        self.redraw()


    def install_mod(self):
        path = askopenfilename(
            title=str(i18n("选择模组 (.py / .zip)", "Select Mod (.py / .zip)")),
            filetypes=[
                (str(i18n("Python / 压缩包", "Python / Archive")), "*.py *.zip"),
                ("Python", "*.py"),
                ("Zip", "*.zip"),
            ]
        )
        if not path:
            return

        try:
            try:
                result = ops.install_mod(path, mods_dir=MODS_DIR)
            except FileExistsError as exc:
                if not dialog(i18n('覆盖安装', 'Overwrite installation'), str(exc)):
                    return
                result = ops.install_mod(path, mods_dir=MODS_DIR, overwrite=True)
        except (OSError, ValueError) as exc:
            mineprep.warn(str(exc))
            return
        src = Path(path)
        mineprep.prints(i18n("已安装模组: {name}", "Installed mod: {name}").format(name=src.name))
        self.redraw()
        return result


    def package_mod(self, name):
        path = asksaveasfilename(title=str(i18n('打包模组', 'Package Mod')),
                                 initialfile=_mod_stem(name) + '.zip', defaultextension='.zip',
                                 filetypes=[('Zip', '*.zip')])
        if not path:
            return
        try:
            try:
                result = ops.package_mod(name, path, mods_dir=MODS_DIR)
            except FileExistsError as exc:
                if not dialog(i18n('覆盖压缩包', 'Overwrite Archive'), str(exc)):
                    return
                result = ops.package_mod(name, path, mods_dir=MODS_DIR, overwrite=True)
        except (OSError, ValueError) as exc:
            mineprep.warn(str(exc))
            return
        mineprep.prints(i18n(
            "已打包 {count} 个文件，{size} KiB：{path}",
            "Packaged {count} files, {size} KiB: {path}").format(
                count=len(result['files']), size=f"{result['archive_bytes']/1024:.1f}", path=str(result['path'])))
        return result


    def uninstall_mod(self, name, info):
        stem = _mod_stem(name)
        display = str(info.get("Name") or stem)
        if dialog(i18n('卸载 {display}', 'Uninstall {display}').format(display=display),
                  i18n('你确定要删除这个模组吗？\n"{stem}"将会消失很久！（真的很久！）',
                       'Are you sure you want to delete this mod?\n"{stem}" will be lost forever! (A long time!)').format(stem=stem)):

            try:
                result = ops.uninstall_mod(name, mods_dir=MODS_DIR)
            except (OSError, ValueError, RuntimeError) as exc:
                mineprep.warn(str(exc))
                return
            mineprep.prints(i18n("已卸载模组: {stem}", "Uninstalled mod: {stem}").format(stem=stem))
            self.redraw()
            return result
