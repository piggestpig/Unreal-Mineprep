import mineprep
import unreal

# 在此填写模组相关信息，设置EnabledByDefault=True会在引擎启动时自动加载模组
# Advanced=True会被模组管理器隐藏到高级选项里，开发普通模组时不用写
mod_info = {
    "Name": mineprep.bilingual("Mod模板", "Mod Template"),
    "Description": mineprep.bilingual("面向开发者的普通mod模板", "A simple mod template for developers"),
    "Version": "1.0",
    "CreatedBy": "",
    "EnabledByDefault": False,
    "ReloadWithMineprep": True,
    "Advanced": True,
}


# mineprep.Mod在__init__中调用draw()构建界面；需要重绘时可绑定self.redraw到on_clicked等事件
# 如果不需要UI界面，可以重载__new__，此时 self.layout 默认为 None
class mod_template(mineprep.Mod):
    def draw(self, context):
        layout = self.layout
        layout.text(mineprep.bilingual("这是一个mod模板", "This is a mod template"))
        layout.button(mineprep.bilingual("打开Python文件", "Open Python File"),
                      on_clicked=lambda: mineprep.startfile(__file__))


# 模组管理器会调用register()来注册模组。如果是写成文件夹的大型模组，需要手动注册子模块
def register():
    mod_template.register(True)


# 写成文件夹的大型模组可在此注销子模块，参见ModManager的__init__.py
def unregister():
    pass