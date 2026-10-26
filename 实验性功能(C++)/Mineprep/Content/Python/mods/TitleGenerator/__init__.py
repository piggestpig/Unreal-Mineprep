"""像素标题生成器模组入口。"""

mod_info = {
    'Version': '2.0',
    'EnabledByDefault': True,
    'ReloadWithMineprep': True,
}


def register():
    from .panel import TitleGenerator
    TitleGenerator.register(True)


def unregister():
    from . import ops
    from .panel import TitleGenerator
    ops.cancel_all()
    TitleGenerator.unregister()
