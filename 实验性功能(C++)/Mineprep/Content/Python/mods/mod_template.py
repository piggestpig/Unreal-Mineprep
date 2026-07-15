import mineprep
import unreal

mod_info = {
    "Version": 1,
    "CreatedBy": "",
    "Description": "mod模板",
    "EnabledByDefault": False,
    "ReloadWithMineprep": True,
}

class props(mineprep.PropertyGroup):
    string: str = "Hello World!"

class mod_template(mineprep.Mod):
    def __init__(self):
        layout = self.layout
        layout.text("这是一个mod模板")
        layout.button("点我打印下方文字", on_clicked=lambda: mineprep.prints(props.string))
        layout.prop(props, "string", text="可修改的字符串")

def register():
    mod_template()

def unregister():
    pass

if __name__ == "__main__":
    register()