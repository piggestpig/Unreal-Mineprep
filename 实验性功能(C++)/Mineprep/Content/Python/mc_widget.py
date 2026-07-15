import unreal
import uuid
import random
from mc_utils import construct, uasset, enum, uclass, copy, warn
from mc_config import paths, wclass

props = {}
widgets = []

class MetaProperty(type):
    #获取属性时, 在props中找到对象并调用get_editor_property
    def __getattribute__(cls, name):
        if name.startswith("_"):
            return super().__getattribute__(name)
        return props[cls].get_editor_property(name)

    #设置属性时, 在props中找到对象并调用set_editor_property
    def __setattr__(cls, name, value):
        if name.startswith("_"):
            super().__setattribute__(name, value)
            return
        props[cls].set_editor_property(name, value)


class PropertyGroup(metaclass=MetaProperty):
    _unique_ = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if cls._unique_:
            for existing_cls, obj in props.items():
                if existing_cls.__name__ == cls.__name__:
                    props[cls] = obj
                    unreal.log(f"{cls.__name__}设置了 _unique_ = True, 直接使用已创建的属性集")
                    return

        properties = {}
        defaults = {}
        metas = {}

        def get_ue_type_str(t):
            # 如果在 unreal 模块中能找到这个类型的名字，加上 "unreal." 前缀
            if hasattr(unreal, t.__name__):
                return f"unreal.{t.__name__}"
            return t.__name__  # 否则认为是 int, str 等内建类型

        # 1. 提取带类型注解的变量
        if hasattr(cls, "__annotations__"):
            for name, t in cls.__annotations__.items():
                properties[name] = get_ue_type_str(t)

        # 2. 提取类变量；值为 (default, meta_dict) 时拆出 meta
        for name, val in cls.__dict__.items():
            if name.startswith("_") or callable(val):
                continue
            meta = {'Category': cls.__name__}
            if isinstance(val, tuple):
                val, extra = val
                meta.update(extra)
            if name not in properties:
                properties[name] = get_ue_type_str(type(val))
            defaults[name] = val
            metas[name] = meta

        # 3. 动态构建满足虚幻要求的代码
        guid = uuid.uuid4().hex[:8]
        ue_class_name = f"{cls.__name__}_GUID{guid}"

        code_lines = [
            "@unreal.uclass()",
            f"class {ue_class_name}(unreal.Object):"
        ]

        for prop_name, prop_type in properties.items():
            meta = metas.get(prop_name, {'Category': cls.__name__})
            code_lines.append(f"    {prop_name} = unreal.uproperty({prop_type}, meta={meta!r})")

        code_lines.append("")

        for prop_name, default_val in defaults.items():
            code_lines.append(f"unreal.get_default_object({ue_class_name}).set_editor_property({repr(prop_name)}, {repr(default_val)})")

        exec_code = "\n".join(code_lines)

        unreal.log(f"\n[注册数据对象] >>>\n{exec_code}\n<<< [End]")
        exec(exec_code, globals())
        props[cls] = construct(eval(ue_class_name))


def alignment(HVtuple: int | tuple[int, int] =(1,1)):
    """解析 (水平, 垂直) 对齐方式, 0填充, 1靠左/靠上, 2居中, 3靠右/靠下"""
    if isinstance(HVtuple, (int, unreal.EnumBase)):
        HVtuple = (HVtuple, HVtuple)
    h,v = HVtuple
    h = h if isinstance(h, unreal.EnumBase) else enum(unreal.HorizontalAlignment)[h]
    v = v if isinstance(v, unreal.EnumBase) else enum(unreal.VerticalAlignment)[v]
    return (h,v)


def add_widget(root, widget,
               padding=unreal.Margin(3, 1, 3, 1), align=(1,1), fill=False):
    """添加子控件到根控件"""
    if not isinstance(widget, unreal.Object):
        widget = construct(uclass(widget), root)
    slot = root.add_child(widget)

    if hasattr(slot, 'set_padding') and not isinstance(root, unreal.ScaleBox):
        if isinstance(padding, (int, float)):
            padding = unreal.Margin(padding, padding, padding, padding)
        elif isinstance(padding, (list, tuple)) and len(padding) == 2:
            padding = unreal.Margin(padding[0], padding[1], padding[0], padding[1])
        slot.set_padding(padding)
        h,v = alignment(align)
        slot.set_horizontal_alignment(h)
        slot.set_vertical_alignment(v)

        if fill:
            try:
                slot.set_editor_property('Size', unreal.SlateChildSize(1, unreal.SlateSizeRule.FILL))
            except:
                unreal.log(f"【跳过】控件{root.get_name()}.slot不支持设置填充方式")
    else:
        unreal.log(f"【跳过】控件{root.get_name()}.slot不支持设置padding和对齐方式")

    widgets.append(widget)
    return widget


class Layout():
    target = None

    def __init__(cls, target=None, root: unreal.Name='Root'):
        subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
        if isinstance(target, unreal.Object):
            cls.target = target
        elif isinstance(target, int):
            widget = subsystem.spawn_and_register_tab_with_id(uasset(wclass.mod_panel), str(target))
            cls.target = widget.find_child_widget_by_name(root)
            unreal.log(f"已生成自定义控件面板, TabID: {target}")
        elif isinstance(target, str):
            tab_id = str(random.randint(0, 999999999))
            widget = subsystem.spawn_and_register_tab_with_id(uasset(target), tab_id)
            cls.target = widget.find_child_widget_by_name(root)
            unreal.log(f"已生成自定义控件面板{target}, TabID: {tab_id}")
        else:
            tab_id = str(random.randint(0, 999999999))
            widget = subsystem.spawn_and_register_tab_with_id(uasset(wclass.mod_panel), tab_id)
            cls.target = widget.find_child_widget_by_name(root)
            unreal.log(f"已生成自定义控件面板, TabID: {tab_id}")


    #调用不存在的属性或函数时, 自动转发到target
    def __getattr__(cls, name):
        return getattr(cls.target, name)

    @property
    def parent(cls):
        return cls.target.get_parent()

    @property
    def outer(cls):
        return unreal.UserWidgetFunctionLibrary.get_outer_user_widget(cls.target)
    
    def get(cls, prop):
        return cls.target.get_editor_property(prop)
    
    def set(cls, prop, value):
        cls.target.set_editor_property(prop, value)

    def prop(cls, data, property: str=None, text: str=None, on_property_changed=None,
             padding=unreal.Margin(3, 1, 3, 1), align=(1,1), fill=False):
        if property:
            #单属性视图
            viewer = add_widget(cls.target, unreal.SinglePropertyView, padding, align, fill)
            viewer.set_object(data if isinstance(data, unreal.Object) else props[data])
            viewer.set_property_name(property)
            if text:
                viewer.set_name_override(text)
        else:
            #细节视图
            viewer = add_widget(cls.target, unreal.DetailsView, padding, align, fill)
            viewer.set_object(data if isinstance(data, unreal.Object) else props[data])

        if on_property_changed:
            viewer.on_property_changed.add_callable(on_property_changed)

        return Layout(viewer)


    def label(cls, text='', size=14, color=unreal.LinearColor(1, 1, 1, 1),
              padding=unreal.Margin(3, 1, 3, 1), align=(1,1), fill=False):
        text_block = add_widget(cls.target, unreal.TextBlock, padding, align, fill)
        text_block.set_text(text)
        text_block.set_color_and_opacity(unreal.SlateColor(color))

        font = unreal.SlateFontInfo(
            font_object=uasset("/Engine/EditorResources/DefaultEditorFont.DefaultEditorFont"),
            size=size
        )
        text_block.set_font(font)

        return Layout(text_block)

    def text(cls, text='', size=14, color=unreal.LinearColor(1, 1, 1, 1),
              padding=unreal.Margin(3, 1, 3, 1), align=(1,1), fill=False):
        return cls.label(text, size, color, padding, align, fill)

    def title(cls, text='', size=14, color=unreal.LinearColor(1, 1, 1, 1),
              padding=unreal.Margin(3, 1, 3, 1), align=(2,1), fill=False):
        return cls.label(text, size, color, padding, align, fill)


    def image(cls, image, color=unreal.LinearColor(1, 1, 1, 1), size=unreal.Vector2D(64, 64),
              padding=unreal.Margin(3, 1, 3, 1), align=(1,1), fill=False):
        image_widget = add_widget(cls.target, unreal.Image, padding, align, fill)
        image_widget.set_brush_resource_object(uasset(image))
        image_widget.set_color_and_opacity(color)
        image_widget.set_desired_size_override(size)
        return Layout(image_widget)


    def button(cls, text='', size=14, on_clicked=None,
               padding=unreal.Margin(3, 1, 3, 1), align=(0,1), fill=False):
        button = add_widget(cls.target, unreal.EditorUtilityButton, padding, align, fill)
        style = button.get_editor_property('widget_style')
        style.normal.tint_color.specified_color = unreal.LinearColor(0.039546, 0.039546, 0.039546, 0.8)
        style.normal.outline_settings.corner_radii=unreal.Vector4(0, 0, 0, 0)
        style.hovered.tint_color.specified_color = unreal.LinearColor(0.095307, 0.095307, 0.095307, 1)
        style.hovered.outline_settings.corner_radii=unreal.Vector4(0, 0, 0, 0)
        style.pressed.tint_color.specified_color = unreal.LinearColor(0.028426, 0.028426, 0.028426, 1)
        style.pressed.outline_settings.corner_radii=unreal.Vector4(0, 0, 0, 0)
        button.set_style(style)

        button_text = construct(unreal.TextBlock, cls.target)
        button_text.set_text(text)
        button_text.set_font(unreal.SlateFontInfo(
            font_object=uasset("/Engine/EditorResources/DefaultEditorFont.DefaultEditorFont"),
            size=size)
        )
        button.set_content(button_text)

        if on_clicked:
            button.on_clicked.add_callable(on_clicked)

        return Layout(button)


    def operator(cls, text='', size=14, on_clicked=None,
                 padding=unreal.Margin(3, 1, 3, 1), align=(0,1), fill=False):
        return cls.button(text, size, on_clicked, padding, align, fill)


    def checkbox(cls, text='', size=14, on_check_state_changed=None,
                padding=unreal.Margin(3, 1, 3, 1), align=(0,1), fill=False):
            checkbox = add_widget(cls.target, unreal.EditorUtilityCheckBox, padding, align, fill)
            style = checkbox.get_editor_property('widget_style')
            style.padding = unreal.Margin(4, 0, 0, 0)
            checkbox.set_editor_property('widget_style', style)

            checkbox_text = construct(unreal.TextBlock, cls.target)
            checkbox_text.set_text(text)
            checkbox_text.set_font(unreal.SlateFontInfo(
                font_object=uasset("/Engine/EditorResources/DefaultEditorFont.DefaultEditorFont"),
                size=size)
            )
            checkbox.set_content(checkbox_text)

            if on_check_state_changed:
                checkbox.on_check_state_changed.add_callable(on_check_state_changed)

            return Layout(checkbox)


    def row(cls, padding=unreal.Margin(3, 1, 3, 1), align=(0,1), fill=False):
        horizontal_box = add_widget(cls.target, unreal.HorizontalBox, padding, align, fill)
        return Layout(horizontal_box)


    def column(cls, padding=unreal.Margin(3, 1, 3, 1), align=(0,1), fill=False):
        vertical_box = add_widget(cls.target, unreal.VerticalBox, padding, align, fill)
        return Layout(vertical_box)

    def col(cls, padding=unreal.Margin(3, 1, 3, 1), align=(0,1), fill=False):
        return cls.column(padding, align, fill)


    def spacer(cls, size=unreal.Vector2D(1, 1),
               padding=unreal.Margin(3, 1, 3, 1), align=(0,1), fill=False):
        spacer = add_widget(cls.target, unreal.Spacer, padding, align, fill)
        size = (size, size) if isinstance(size, (int, float)) else size
        spacer.set_size(size)
        return Layout(spacer)


    def overlay(cls, padding=0, align=(0,0), fill=True):
        overlay = add_widget(cls.target, unreal.Overlay, padding, align, fill)
        return Layout(overlay)


    def switcher(cls, animated=False,
                 padding=unreal.Margin(3, 1, 3, 1), align=(0,1), fill=False):
        switcher_type = unreal.CommonAnimatedSwitcher if animated else unreal.WidgetSwitcher
        switcher = add_widget(cls.target, switcher_type, padding, align, fill)
        return Layout(switcher)

    def scalebox(cls, scale: float=None,
                 padding=0, align=(0,1), fill=False):
        scalebox = add_widget(cls.target, unreal.ScaleBox, padding, align, fill)
        if scale:
            scalebox.set_editor_property('Stretch', unreal.Stretch.USER_SPECIFIED)
            scalebox.set_editor_property('UserSpecifiedScale', scale)
        return Layout(scalebox)


    def custom(cls, widget, padding=unreal.Margin(3, 1, 3, 1), align=(0,1), fill=False):
        return Layout(add_widget(cls.target, widget, padding, align, fill))


def ui(script='', save_path=None, run=True):
    """创建一个新的自定义控件并运行, 可设置保存名称或路径，输入名称时会自动保存到/Game/mc/mods/"""
    check_script = f"""import unreal
import mineprep
layout = mineprep.Layout()
{script}
"""
    compiled_script = compile(check_script, '<mineprep.ui>', 'exec')

    if save_path:
        #是否是包含'/'的路径
        if not '/' in save_path:
            save_path = '/Game/mc/mods/' + save_path
        widget = copy(wclass.mod_panel, save_path)
        bp = unreal.get_default_object(uclass(widget))
        bp.set_editor_property('Script', script)
        bp.set_editor_property('TabDisplayName', '')
        subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
        if run:
            subsystem.spawn_and_register_tab_with_id(widget, str(random.randint(0, 999999999)))
        return widget
    elif run:
        exec(compiled_script, globals())

