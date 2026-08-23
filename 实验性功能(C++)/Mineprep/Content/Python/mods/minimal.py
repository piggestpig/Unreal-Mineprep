import mineprep

mod_info = {
    "EnabledByDefault": False,
    "ReloadWithMineprep": True,
    "Advanced": True,
}

def register():
    mineprep.ui(f'layout.button("最小模组, 点我打开Python文件", on_clicked=lambda: mineprep.startfile(r"{__file__}"))')