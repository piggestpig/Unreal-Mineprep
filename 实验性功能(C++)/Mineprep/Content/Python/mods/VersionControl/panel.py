import unreal
import mineprep
from mineprep import bilingual

from . import ops
from .props import ExtraProps, FilterProps, Props, SkipProps

_HINT_YELLOW = unreal.LinearColor(1.0, 0.82, 0.12, 1.0)


class VersionControl(mineprep.Mod):
    _unique_ = True
    _label_ = bilingual('插件更新与迁移工具', 'Plugin Update & Migration')

    def __init__(self, context=None):
        self.props = Props()
        self.script = SkipProps()
        self.filters = FilterProps()
        self.extras = ExtraProps()
        if self.props.UpdateInstaller:
            self._fill_installer_dir()
        super().__init__(context)

    def draw(self, context=None):
        layout = self.layout
        row = layout.row()

        left = row.col(fill=0.7, padding=3)
        left.prop(self.props, on_property_changed=self.on_props)
        self._hint = left.text('', size=10, color=_HINT_YELLOW, padding=(6, 2))
        self._btn_update = left.button(
            bilingual('更新安装包', 'Update Installer'),
            on_clicked=lambda: ops.update_installer(
                self.props, self.filters, self.extras, self.script,
            ),
            padding=3,
        )
        self._btn_migrate = left.button(
            bilingual('迁移插件', 'Migrate Plugin'),
            on_clicked=lambda: ops.migrate_plugin(
                self.props, self.filters, self.extras, self.script,
            ),
            padding=3,
        )
        left.button(
            bilingual('打开目标文件夹', 'Open Target Folder'),
            on_clicked=lambda: ops.open_target(self.props),
            padding=3,
        )

        self._right = row.col(fill=1, padding=3)
        self._right.prop(self.script, on_property_changed=self.on_script)
        self._right.prop(self.filters, on_property_changed=self.on_filters)
        self._right.prop(self.extras, on_property_changed=self.on_extras)

        self._sync_buttons()
        self._sync_hint()
        self._sync_right()

    def _skip_fn(self):
        return ops.load_skip_fn(self.script)

    def on_props(self, name):
        if name == 'UpdateInstaller':
            if self.props.UpdateInstaller:
                self._fill_installer_dir()
            self._sync_buttons()
        if name == 'ClearDest':
            self._sync_right()
        self._sync_hint()
        if name in ('TargetDir', 'UpdateInstaller'):
            self._refresh_maps(name)

    def on_script(self, name):
        self._refresh_maps(name)

    def on_filters(self, name):
        ops.refresh_filters(self.filters, self.props, name, skip_fn=self._skip_fn())

    def on_extras(self, name):
        ops.refresh_extras(self.extras, self.props, name, skip_fn=self._skip_fn())

    def _refresh_maps(self, name=None):
        skip_fn = self._skip_fn()
        ops.refresh_filters(self.filters, self.props, name, skip_fn=skip_fn)
        ops.refresh_extras(self.extras, self.props, name, skip_fn=skip_fn)

    def _fill_installer_dir(self):
        path = ops.installer_dir()
        if path:
            ops.set_target_dir(self.props, path)

    def _sync_buttons(self):
        update = bool(self.props.UpdateInstaller)
        self._btn_update.hide(not update)
        self._btn_migrate.hide(update)

    def _sync_right(self):
        self._right.hide(bool(self.props.ClearDest))

    def _sync_hint(self):
        msg = ops.path_warnings(self.props, require_uproject=not self.props.UpdateInstaller)
        self._hint.target.set_text(msg)
        self._hint.hide(not msg)
