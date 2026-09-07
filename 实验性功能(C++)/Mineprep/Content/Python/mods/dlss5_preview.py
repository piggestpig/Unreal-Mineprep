import mineprep
import unreal

mod_info = {
    'Name': mineprep.bilingual('DLSS5 预览', 'DLSS5 Preview'),
    'Description': mineprep.bilingual(
        '调整非官方 DLSS Neural Rendering（r.DLSS5.*）参数',
        'Tune unofficial DLSS Neural Rendering (r.DLSS5.*) cvars',
    ),
    'Version': '1.0',
    'CreatedBy': '',
    'EnabledByDefault': True,
    'ReloadWithMineprep': True,
}

_INT_CVARS = {
    'Enable': 'r.DLSS5.Enable',
    'Order': 'r.DLSS5.Order',
    'ColorFormat': 'r.DLSS5.ColorFormat',
    'Preset': 'r.DLSS5.Preset',
    'Style': 'r.DLSS5.Style',
}
_FLOAT_CVARS = {
    'Intensity': 'r.DLSS5.Intensity',
    'LocalTone': 'r.DLSS5.LocalTone',
    'LocalStructure': 'r.DLSS5.LocalStructure',
    'SkinStructure': 'r.DLSS5.SkinStructure',
    'MotionScaleX': 'r.DLSS5.MotionScaleX',
    'MotionScaleY': 'r.DLSS5.MotionScaleY',
}


def _set_cvar(name, value):
    cmd = f'{name} {value}'
    mineprep.debug(f'[DLSS5] console: {cmd}')
    unreal.SystemLibrary.execute_console_command(mineprep.world(), cmd)


class DLSS5Props(mineprep.PropertyGroup):
    Enable: bool = False
    Order: int = (0, {'ClampMin': 0, 'ClampMax': 1, 'UIMin': 0, 'UIMax': 1})
    ColorFormat: int = (1, {'ClampMin': 0, 'ClampMax': 1, 'UIMin': 0, 'UIMax': 1})
    Preset: int = (1, {'ClampMin': 0, 'ClampMax': 4, 'UIMin': 0, 'UIMax': 4})
    Style: int = (0, {'ClampMin': 0, 'ClampMax': 2, 'UIMin': 0, 'UIMax': 2})
    Intensity: float = (1.0, {'UIMin': 0.0, 'UIMax': 2.0, 'ClampMin': 0.0})
    LocalTone: float = (1.0, {'UIMin': 0.0, 'UIMax': 2.0, 'ClampMin': 0.0})
    LocalStructure: float = (1.0, {'UIMin': 0.0, 'UIMax': 2.0, 'ClampMin': 0.0})
    SkinStructure: float = (1.0, {'UIMin': 0.0, 'UIMax': 2.0, 'ClampMin': 0.0})
    MotionScaleX: float = (1.0, {'UIMin': 0.0, 'UIMax': 4.0})
    MotionScaleY: float = (1.0, {'UIMin': 0.0, 'UIMax': 4.0})


DLSS5Props.localize('DLSS5Props', 'DLSS5 参数', 'DLSS5 Settings', 'DLSS5 參數')
DLSS5Props.localize('Enable', '启用 Neural Rendering', 'Enable Neural Rendering', '啟用 Neural Rendering')
DLSS5Props.localize('Order', '顺序 (0=先超分再NR，1=先NR再超分)', 'Order (0=SR then NR, 1=NR then SR)', '順序 (0=先超分再NR，1=先NR再超分)')
DLSS5Props.localize('ColorFormat', '颜色格式 (0=RGBA8 SDR，1=RGBA16F HDR)', 'Color format (0=RGBA8 SDR, 1=RGBA16F HDR)', '顏色格式 (0=RGBA8 SDR，1=RGBA16F HDR)')
DLSS5Props.localize('Preset', '预设 (0=Default, 1-4=A-D，会重建会话)', 'Preset (0=Default, 1-4=A-D, recreates session)', '預設 (0=Default, 1-4=A-D，會重建會話)')
DLSS5Props.localize('Style', '风格 (0-2)', 'Style (0-2)', '風格 (0-2)')
DLSS5Props.localize('Intensity', '强度', 'Intensity', '強度')
DLSS5Props.localize('LocalTone', '局部色调', 'Local Tone', '局部色調')
DLSS5Props.localize('LocalStructure', '局部结构', 'Local Structure', '局部結構')
DLSS5Props.localize('SkinStructure', '皮肤结构', 'Skin Structure', '皮膚結構')
DLSS5Props.localize('MotionScaleX', '运动矢量 X', 'Motion Scale X', '運動矢量 X')
DLSS5Props.localize('MotionScaleY', '运动矢量 Y', 'Motion Scale Y', '運動矢量 Y')


class DLSS5Preview(mineprep.Mod):
    _label_ = mineprep.localize('DLSS5 预览', 'DLSS5 预览', 'DLSS5 Preview', 'DLSS5 預覽')
    _unique_ = True

    def __init__(self, context=None):
        self.props = DLSS5Props()
        self._syncing = False
        self._status = None
        super().__init__(context)
        self.pull()

    def draw(self, context=None):
        layout = self.layout
        layout.title(mineprep.bilingual('DLSS5 Neural Rendering', 'DLSS5 Neural Rendering'), size=16)
        layout.text(
            mineprep.bilingual(
                'D3D12 视口。Order 1 在 AfterDOF、内部分辨率跑 NR。改预设会 RecreateFeature。',
                'D3D12 viewport. Order 1 runs NR at AfterDOF (internal res). Changing Preset recreates Feature 18.',
            ),
            size=12,
            clip=True,
        )
        layout.prop(self.props, align=(0, 1), on_property_changed=self._on_changed)
        row = layout.row(padding=(0, 6))
        row.button(
            mineprep.bilingual('从引擎读取', 'Read from Engine'),
            on_clicked=self.pull,
            padding=3,
        )
        row.button(
            mineprep.bilingual('应用到引擎', 'Apply to Engine'),
            on_clicked=self.apply_all,
            padding=3,
        )
        row.button(
            mineprep.bilingual('重置历史', 'Reset History'),
            on_clicked=self.reset_history,
            padding=3,
        )
        self._status = layout.text('', align=(1, 3), padding=6, fill=1)

    def _status_text(self, message):
        if self._status is not None:
            self._status.set('text', message)

    def pull(self):
        self._syncing = True
        for field, cvar in _INT_CVARS.items():
            value = unreal.SystemLibrary.get_console_variable_int_value(cvar)
            setattr(self.props, field, bool(value) if field == 'Enable' else value)
        for field, cvar in _FLOAT_CVARS.items():
            setattr(self.props, field, unreal.SystemLibrary.get_console_variable_float_value(cvar))
        self._syncing = False
        self._status_text(mineprep.bilingual('已从引擎读取 r.DLSS5.*', 'Read r.DLSS5.* from engine'))

    def apply_field(self, name):
        mineprep.debug(f'[DLSS5] apply_field {name!r}={getattr(self.props, name, "<missing>")!r}')
        if name in _INT_CVARS:
            value = int(bool(self.props.Enable)) if name == 'Enable' else int(getattr(self.props, name))
            _set_cvar(_INT_CVARS[name], value)
            return
        if name in _FLOAT_CVARS:
            _set_cvar(_FLOAT_CVARS[name], float(getattr(self.props, name)))
            return
        mineprep.warn(f'[DLSS5] unknown property {name!r}')

    def apply_all(self):
        for name in list(_INT_CVARS) + list(_FLOAT_CVARS):
            self.apply_field(name)
        mineprep.debug(mineprep.bilingual('已应用 r.DLSS5.*', 'Applied r.DLSS5.*'))
        self._status_text(mineprep.bilingual('已应用到引擎', 'Applied to engine'))

    def reset_history(self):
        _set_cvar('r.DLSS5.Reset', 1)
        mineprep.debug(mineprep.bilingual('下一帧将重置 Feature 18 历史', 'Feature 18 history will reset next frame'))
        self._status_text(mineprep.bilingual('已请求 Reset', 'Reset requested'))

    def _on_changed(self, name):
        mineprep.debug(f'[DLSS5] on_changed {name!r} type={type(name)!r} syncing={self._syncing}')
        if self._syncing:
            return
        self.apply_field(name)
        cvar = _INT_CVARS.get(name) or _FLOAT_CVARS.get(name)
        self._status_text(f'{name} → {cvar}' if cvar else f'{name} (unknown)')


def register():
    DLSS5Preview.register()


def unregister():
    DLSS5Preview.unregister()
