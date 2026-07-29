"""VAT Tools 合并面板：左栏烘焙动画 / 右栏从骨骼创建"""
import mineprep
from mineprep import localize
from . import bake_anim_ops
from . import copy_ops
from . import init_ops
from . import util
from .props import BakeAnimProps, CopyProps, InitSkmProps, VATToolsOptions


class VATTools(mineprep.Mod):
    _label_ = localize('VAT顶点动画工具', 'VAT顶点动画工具', 'VAT Tools', 'VAT頂點動畫工具')

    def __init__(self, context=None):
        self.bake_props = BakeAnimProps()
        self.copy_props = CopyProps()
        self.init_props = InitSkmProps()
        self.options = VATToolsOptions()
        super().__init__(context)

    def draw(self, context=None):
        layout = self.layout

        header = layout.row()
        header.scalebox(align=(1, 2), padding=(5, 3)).title('VAT Tools', size=16)
        header.scalebox(align=3, fill=1).button(
            localize('打开模组', '打开模组', 'Open Mod', '打開模組'),
            on_clicked=util.open_mod_script,
            align=3, size=12,
        )

        row = layout.row(align=(0, 1))

        left = row.col(fill=1, padding=3)
        left.text(
            localize('烘焙动画至现有数据集', '烘焙动画至现有数据集',
                     'Bake Animation to Data Asset', '烘焙動畫至現有數據集'),
            size=13, clip=True
        )
        left.button(
            localize('烘焙动画', '烘焙动画', 'Bake Animation', '烘焙動畫'),
            on_clicked=lambda: bake_anim_ops.bake_animation(
                self.bake_props,
                auto_clean_cache=bool(self.options.AutoCleanCache),
            ),
            padding=3,
        )
        left.prop(
            self.bake_props,
            on_property_changed=lambda name: bake_anim_ops.on_bake_props_changed(self, name),
            align=(0, 1),
        )
        left.text(
            localize('动画组索引012...', '0:待机, 1:常规移动/行走, 2:快速移动/奔跑',
                     '0: Idle, 1: Walk, 2: Run', '0: 待機, 1: 常規移動/行走, 2: 快速移動/奔跑'),
            size=12, padding=6, clip=True
        )

        left.spacer(5)

        left.button(
            localize('复制数据集', '复制数据集', 'Copy Data Asset', '複製數據集'),
            on_clicked=lambda: copy_ops.copy_data_asset(self),
            padding=3,
        )
        left.prop(self.copy_props, align=(0, 1))

        right = row.col(fill=1, padding=3)
        right.text(
            localize('从骨骼创建数据集', '从骨骼创建数据集',
                     'Create Data Asset from Skeletal Mesh', '從骨骼創建數據集'),
            size=13,
        )
        right.button(
            localize('创建数据资产', '创建数据资产', 'Create Data Asset', '創建數據資產'),
            on_clicked=lambda: init_ops.create_vat_from_skm(self),
            padding=3,
        )
        right.prop(
            self.init_props,
            on_property_changed=lambda name: init_ops.on_init_props_changed(self, name),
            align=(0, 1),
        )

        layout.prop(
            self.options, 'AutoCleanCache',
            localize('自动清理缓存', '自动清理缓存', 'Auto Clean Cache', '自動清理緩存'),
            align=(1, 3), fill=1,
        )

        layout.prop(
            self.options, 'HideInitSkm',
            localize('隐藏右栏', '隐藏右栏', 'Hide Right Panel', '隱藏右欄'),
            align=(1, 3),
            on_property_changed=lambda x: right.hide(self.options.HideInitSkm),
        )
