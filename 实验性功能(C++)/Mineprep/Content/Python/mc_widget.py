import unreal
import uuid
import random
import mcvars
from mc_utils import construct, uasset, enum, uclass, copy, warn, debug, SafeList, resolve_soft
from mc_config import paths, wclass
from typing import TypeVar

T = TypeVar('T')
WidgetsCache = {}
props = {}
widgets = []


class MetaProperty(type):
    #获取属性时, 在props中找到对象并调用get_editor_property
    def __getattribute__(cls, name):
        if name.startswith("_"):
            return super().__getattribute__(name)
        value = props[cls].get_editor_property(name)
        if name in super().__getattribute__('_soft_props_'):
            return resolve_soft(value)
        return value

    #设置属性时, 在props中找到对象并调用set_editor_property
    def __setattr__(cls, name, value):
        if name.startswith("_"):
            super().__setattr__(name, value)
            return
        if name in cls._soft_props_:
            if isinstance(value, unreal.Object):
                value = unreal.SoftObjectPath(value.get_path_name())
            elif isinstance(value, str):
                value = unreal.SoftObjectPath(value)
        props[cls].set_editor_property(name, value)


class PropertyGroup(metaclass=MetaProperty):
    _unique_ = False
    _soft_actor_ = True

    _soft_props_ = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._soft_props_ = {}

        if cls._unique_:
            for existing_cls, obj in props.items():
                if existing_cls.__name__ == cls.__name__:
                    props[cls] = obj
                    # 仍按新类注解收集软引用字段，供 get/set 转换
                    if cls._soft_actor_:
                        for name, t in getattr(cls, '__annotations__', {}).items():
                            if isinstance(t, type) and issubclass(t, unreal.Actor):
                                cls._soft_props_[name] = t
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

        def register_soft_actor(name, t, meta=None):
            """unreal.Actor 注解 → SoftObjectPath + AllowedClasses"""
            properties[name] = 'unreal.SoftObjectPath'
            cls._soft_props_[name] = t
            m = meta if meta is not None else {'Category': cls.__name__}
            m.setdefault('AllowedClasses', t.static_class().get_path_name())
            metas[name] = m

        # 1. 提取带类型注解的变量
        if hasattr(cls, "__annotations__"):
            for name, t in cls.__annotations__.items():
                if cls._soft_actor_ and isinstance(t, type) and issubclass(t, unreal.Actor):
                    register_soft_actor(name, t)
                else:
                    properties[name] = get_ue_type_str(t)

        # 2. 提取类变量；值为 (default, meta_dict) 时拆出 meta
        for name, val in cls.__dict__.items():
            if name.startswith("_") or callable(val):
                continue
            meta = metas.get(name, {'Category': cls.__name__})
            if isinstance(val, tuple):
                val, extra = val
                meta.update(extra)
            if name not in properties:
                t = type(val)
                if cls._soft_actor_ and isinstance(t, type) and issubclass(t, unreal.Actor):
                    register_soft_actor(name, t, meta)
                else:
                    properties[name] = get_ue_type_str(t)
                    metas[name] = meta
            else:
                metas[name] = meta
            defaults[name] = val

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
            if default_val is not None:
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


def add_widget(root, widget: T,
               padding=unreal.Margin(3,1,3,1), align=(1,1), fill=False,
               clip=False, tooltip='') -> T:
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

    if hasattr(slot, 'set_horizontal_alignment'):
        h,v = alignment(align)
        slot.set_horizontal_alignment(h)
        slot.set_vertical_alignment(v)

        if fill:
            try:
                slot.set_editor_property('Size', unreal.SlateChildSize(float(fill), unreal.SlateSizeRule.FILL))
            except:
                if mcvars.DebugMode:
                    unreal.log(f"【跳过】控件{root.get_name()}.slot不支持设置填充方式")
    elif mcvars.DebugMode:
        unreal.log(f"【跳过】控件{root.get_name()}.slot不支持设置padding和对齐方式")

    if tooltip:
        widget.set_tool_tip_text(tooltip)

    widget.set_clipping(clip if isinstance(clip, unreal.WidgetClipping) else enum(unreal.WidgetClipping)[int(clip)])
    widgets.append(widget)
    return widget


class Layout():
    """ 控件包装器, 可使用 layout.text(), layout.row() 等方法添加子控件  
    参数中的**kwargs可传入以下通用参数

    padding = unreal.Margin(3,1,3,1)
        可简写为(3,1), 也可简写至一个数字
    align = (1,1)
        (水平, 垂直) 对齐方式, 0填充, 1靠左/靠上, 2居中, 3靠右/靠下
    fill = False
        是否撑满整个区域, 传入小数表示比例
    clip = False
        是否裁剪超出部分
    tooltip = ''
        鼠标悬停提示文本
    """
    target = None
    _public_ = False

    def __str__(self):
        return f"{self.target.get_name() if self.target else 'None'}"

    def __repr__(self):
        return f"<{self.target.get_name() if self.target else 'None'}>"

    def __init__(self, target=None, root: unreal.Name='Root', public=False):
        subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
        if isinstance(target, unreal.Object):
            self.target = target
        elif isinstance(target, int):
            widget = subsystem.spawn_and_register_tab_with_id(uasset(wclass.mod_panel), str(target))
            self.target = widget.find_child_widget_by_name(root)
            unreal.log(f"已生成自定义控件面板, TabID: {target}")
        elif isinstance(target, str):
            tab_id = str(random.randint(0, 999999999))
            widget = subsystem.spawn_and_register_tab_with_id(uasset(target), tab_id)
            self.target = widget.find_child_widget_by_name(root)
            unreal.log(f"已生成自定义控件面板{target}, TabID: {tab_id}")
        else:
            tab_id = str(random.randint(0, 999999999))
            widget = subsystem.spawn_and_register_tab_with_id(uasset(wclass.mod_panel), tab_id)
            self.target = widget.find_child_widget_by_name(root)
            unreal.log(f"已生成自定义控件面板, TabID: {tab_id}")

        if self.target:
            if public:
                self._public_ = True
                debug(f"已缓存 mineprep.panel('{self.path}')")
                WidgetsCache[self.path] = self.target

            if mcvars.PythonTooltips and not str(self.target.get_editor_property('ToolTipText')):
                self.target.set_tool_tip_text(f"mineprep.panel('{self.path}')")


    #调用不存在的属性或函数时, 自动转发到target
    def __getattr__(self, name):
        return getattr(self.target, name)

    @property
    def parent(self):
        """获取父控件"""
        return self.target.get_parent()

    @property
    def outer(self):
        """获取整个控件窗口"""
        return unreal.UserWidgetFunctionLibrary.get_outer_user_widget(self.target)

    @property
    def children(self):
        """获取直属子控件数组"""
        try:
            return SafeList(Layout(child) for child in self.target.get_all_children())
        except:
            return SafeList()

    @property
    def hierarchy(self):
        """获取从根到自身的父级控件链（原始 UObject，避免再包 Layout 造成递归）"""
        array = []
        current = self.target
        while current:
            array.append(current)
            current = current.get_parent()
        return array[::-1]

    @property
    def path(self):
        """获取控件在层级中的路径"""
        parts = [widget.get_name() for widget in self.hierarchy]
        outer_name = self.outer.get_name()
        return outer_name + '.' + '.'.join(parts)

    def get(self, prop):
        """获取当前控件的编辑器属性"""
        return self.target.get_editor_property(prop)

    def set(self, prop, value):
        """设置当前控件的编辑器属性"""
        self.target.set_editor_property(prop, value)


    def prop(self, data, property: str=None, text: str=None, on_property_changed=None, **kwargs):
        """添加属性视图；指定 property 为单属性，否则为完整细节面板"""
        if property:
            viewer = add_widget(self.target, unreal.SinglePropertyView, **kwargs)
            viewer.set_object(data if isinstance(data, unreal.Object) else props[data])
            viewer.set_property_name(property)
            if text:
                viewer.set_name_override(text)
        else:
            viewer = add_widget(self.target, unreal.DetailsView, **kwargs)
            viewer.set_object(data if isinstance(data, unreal.Object) else props[data])

        if on_property_changed:
            viewer.on_property_changed.add_callable(on_property_changed)
        return Layout(viewer, public=self._public_)


    def label(self, text='', size=14, color=unreal.LinearColor(1, 1, 1, 1), **kwargs):
        """添加文本标签"""
        text_block = add_widget(self.target, unreal.TextBlock, **kwargs)
        text_block.set_text(text)
        text_block.set_color_and_opacity(unreal.SlateColor(color))
        text_block.set_font(unreal.SlateFontInfo(
            font_object=uasset("/Engine/EditorResources/DefaultEditorFont.DefaultEditorFont"),
            size=size))
        return Layout(text_block, public=self._public_)

    def text(self, text='', size=14, color=unreal.LinearColor(1, 1, 1, 1), **kwargs):
        return self.label(text, size, color, **kwargs)

    def title(self, text='', size=14, color=unreal.LinearColor(1, 1, 1, 1), align=(2, 1), **kwargs):
        return self.label(text, size, color, align=align, **kwargs)


    def image(self, image, color=unreal.LinearColor(1, 1, 1, 1), size=unreal.Vector2D(64, 64), **kwargs):
        """添加图片控件"""
        image_widget = add_widget(self.target, unreal.Image, **kwargs)
        image_widget.set_brush_resource_object(uasset(image))
        image_widget.set_color_and_opacity(color)
        image_widget.set_desired_size_override(size)
        return Layout(image_widget, public=self._public_)


    def button(self, text='', size=14, text_color=(1,1,1,1), text_padding=2,
               on_clicked=None, align=(0, 1),**kwargs):
        """添加按钮，可绑定 on_clicked 回调"""
        button = add_widget(self.target, unreal.EditorUtilityButton, align=align, **kwargs)
        style = button.get_editor_property('widget_style')
        style.normal.tint_color.specified_color = unreal.LinearColor(0.039546, 0.039546, 0.039546, 0.8)
        style.normal.outline_settings.corner_radii = unreal.Vector4(0, 0, 0, 0)
        style.hovered.tint_color.specified_color = unreal.LinearColor(0.095307, 0.095307, 0.095307, 1)
        style.hovered.outline_settings.corner_radii = unreal.Vector4(0, 0, 0, 0)
        style.pressed.tint_color.specified_color = unreal.LinearColor(0.028426, 0.028426, 0.028426, 1)
        style.pressed.outline_settings.corner_radii = unreal.Vector4(0, 0, 0, 0)
        button.set_style(style)

        if on_clicked:
            button.on_clicked.add_callable(on_clicked)

        button_widget = Layout(button, public=self._public_)
        button_text = button_widget.text(text, size=size, align=(2, 1),
                                         color=text_color, padding=text_padding)

        return button_widget


    def operator(self, text='', size=14, on_clicked=None, align=(0, 1), **kwargs):
        return self.button(text, size, on_clicked, align=align, **kwargs)


    def checkbox(self, text='', size=14, on_check_state_changed=None, align=(0, 1), **kwargs):
        """添加复选框，可绑定 on_check_state_changed 回调"""
        checkbox = add_widget(self.target, unreal.EditorUtilityCheckBox, align=align, **kwargs)
        style = checkbox.get_editor_property('widget_style')
        style.padding = unreal.Margin(4, 0, 0, 0)
        checkbox.set_editor_property('widget_style', style)

        checkbox_text = construct(unreal.TextBlock, self.target)
        checkbox_text.set_text(text)
        checkbox_text.set_font(unreal.SlateFontInfo(
            font_object=uasset("/Engine/EditorResources/DefaultEditorFont.DefaultEditorFont"),
            size=size))
        checkbox.set_content(checkbox_text)

        if on_check_state_changed:
            checkbox.on_check_state_changed.add_callable(on_check_state_changed)
        return Layout(checkbox, public=self._public_)


    def row(self, align=(0, 1), **kwargs):
        """添加水平布局容器"""
        return Layout(add_widget(self.target, unreal.HorizontalBox, align=align, **kwargs), public=self._public_)


    def column(self, align=(0, 1), **kwargs):
        """添加垂直布局容器"""
        return Layout(add_widget(self.target, unreal.VerticalBox, align=align, **kwargs), public=self._public_)

    def col(self, align=(0, 1), **kwargs):
        return self.column(align=align, **kwargs)


    def spacer(self, size=unreal.Vector2D(1, 1), align=(0, 1), **kwargs):
        """添加空白占位"""
        spacer = add_widget(self.target, unreal.Spacer, align=align, **kwargs)
        size = (size, size) if isinstance(size, (int, float)) else size
        spacer.set_size(size)
        return Layout(spacer, public=self._public_)


    def overlay(self, padding=0, align=(0, 0), fill=True, **kwargs):
        """添加叠加布局容器"""
        return Layout(add_widget(self.target, unreal.Overlay, padding=padding, align=align, fill=fill, **kwargs), public=self._public_)


    def switcher(self, animated=False, align=(0, 1), **kwargs):
        """添加页面切换器；animated=True 使用动画切换"""
        switcher_type = unreal.CommonAnimatedSwitcher if animated else unreal.WidgetSwitcher
        return Layout(add_widget(self.target, switcher_type, align=align, **kwargs), public=self._public_)


    def scalebox(self, scale: float=None, padding=0, align=(0, 1), **kwargs):
        """添加缩放容器，可指定scale为固定缩放比例。若要动态调整scale，需设置默认值"""
        scalebox = add_widget(self.target, unreal.ScaleBox, padding=padding, align=align, **kwargs)
        if scale:
            scalebox.set_editor_property('Stretch', unreal.Stretch.USER_SPECIFIED)
            scalebox.set_editor_property('UserSpecifiedScale', float(scale))
        return Layout(scalebox, public=self._public_)


    def scrollbox(self, smooth_scroll=False, horizontal=False, align=(0, 1), **kwargs):
        """添加滚动容器；smooth_scroll 可传速度，horizontal 开启横向滚动"""
        scrollbox = add_widget(self.target, unreal.ScrollBox, align=align, **kwargs)
        if smooth_scroll:
            scrollbox.set_animate_wheel_scrolling(True)
            scrollbox.set_scroll_animation_interpolation_speed(float(smooth_scroll))
        if horizontal:
            scrollbox.set_orientation(unreal.Orientation.ORIENT_HORIZONTAL)
        return Layout(scrollbox, public=self._public_)


    def custom(self, widget, align=(0, 1), **kwargs):
        """添加自定义控件类型或实例"""
        return Layout(add_widget(self.target, widget, align=align, **kwargs), public=self._public_)


def ui(script='', save_path=None, run=True):
    """创建一个新的自定义控件并运行, 可设置保存名称或路径，输入名称时会自动保存到/Game/mc/mods/"""
    save_script = f"""
layout = mineprep.Layout(context.find_child_widget_by_name('Root'))
{script}
"""
    compile_script = f"""
import mineprep
layout = mineprep.Layout()
{script}
"""
    compiled_code = compile(compile_script, '<mineprep.ui>', 'exec')

    if save_path:
        #是否是包含'/'的路径
        if not '/' in save_path:
            save_path = '/Game/mc/mods/' + save_path
        widget = copy(wclass.mod_panel, save_path)
        bp = unreal.get_default_object(uclass(widget))
        bp.set_editor_property('Script', save_script)
        bp.set_editor_property('TabDisplayName', '')
        subsystem = unreal.get_editor_subsystem(unreal.EditorUtilitySubsystem)
        if run:
            subsystem.spawn_and_register_tab_with_id(widget, str(random.randint(0, 999999999)))
        return widget
    elif run:
        exec(compiled_code, globals())

