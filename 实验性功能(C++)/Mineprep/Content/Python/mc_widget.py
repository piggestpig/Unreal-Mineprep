import json
import inspect
import unreal
import uuid
import random
import mcvars
from pathlib import Path
from mc_utils import (construct, uasset, enum, uclass, copy, debug, SafeList,
                      resolve_soft, get_tex_size, get_hotkey_object)
from mc_config import paths, wclass
from mc_localization import localize
from typing import TypeVar, Callable, Any

T = TypeVar('T')
padding_align_fill_clip_tooltip_hidden_subclass = dict

WidgetsCache = {}
widgets = []
mcvars.Props = {}  # PropertyGroup 类 → 实例（_unique_ 热重载复用）


def _get_ue_type_str(t):
    """将注解类型转为可写入 uproperty(...) 的表达式字符串"""
    if isinstance(t, str):
        # from __future__ import annotations / 部分 exec 场景下注解为字符串
        if t in ('int', 'float', 'bool', 'str', 'bytes'):
            return t
        if hasattr(unreal, t):
            return f'unreal.{t}'
        return t

    origin = getattr(t, '__origin__', None)
    args = getattr(t, '__args__', None) or ()

    if origin is list:
        return f'unreal.Array({_get_ue_type_str(args[0])})'
    if origin is set:
        return f'unreal.Set({_get_ue_type_str(args[0])})'
    if origin is dict:
        return f'unreal.Map({_get_ue_type_str(args[0])}, {_get_ue_type_str(args[1])})'

    tname = type(t).__name__
    if tname in ('Array', 'FixedArray', 'Set', 'Map'):
        if tname == 'Map' and len(args) >= 2:
            return f'unreal.Map({_get_ue_type_str(args[0])}, {_get_ue_type_str(args[1])})'
        if args:
            return f'unreal.{tname}({_get_ue_type_str(args[0])})'
        if tname == 'Map':
            key = getattr(t, 'key_type', None) or getattr(t, '_key_type', None)
            val = getattr(t, 'value_type', None) or getattr(t, '_value_type', None)
            return f'unreal.Map({_get_ue_type_str(key)}, {_get_ue_type_str(val)})'
        inner = getattr(t, 'type', None) or getattr(t, '_type', None) or getattr(t, 'inner', None)
        return f'unreal.{tname}({_get_ue_type_str(inner)})'

    name = getattr(t, '__name__', None)
    if name and hasattr(unreal, name) and getattr(unreal, name) is t:
        return f'unreal.{name}'
    if name:
        return name
    raise TypeError(f'不支持的属性类型: {t!r}')


def _is_actor_type(t):
    if isinstance(t, str):
        try:
            t = getattr(unreal, t, None)
        except Exception:
            return False
    return isinstance(t, type) and issubclass(t, unreal.Actor)


def resolve_prop_object(data):
    """layout.prop 用：UObject / PropertyGroup 实例 → UObject。"""
    if isinstance(data, unreal.Object):
        return data
    # duck typing：热重载后 isinstance(PropertyGroup) 可能因类对象更换而失败
    uobj = getattr(data, 'uobject', None)
    if uobj is None:
        uobj = getattr(data, '_uobj', None)
    if isinstance(uobj, unreal.Object):
        return uobj
    if isinstance(data, type) and (
        data is PropertyGroup
        or getattr(data, '__name__', None) == 'PropertyGroup'
        or any(getattr(b, '__name__', None) == 'PropertyGroup' for b in getattr(data, '__mro__', ()))
    ):
        raise TypeError(
            f'{data.__name__} 需要先实例化，例如: Props = {data.__name__}()'
        )
    raise TypeError(f'不支持的 prop 数据: {data!r}')


def _to_jsonable(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, unreal.Object):
        return value.get_path_name() if value else None
    tname = type(value).__name__
    if isinstance(value, (list, set, tuple)) or tname in ('Array', 'FixedArray', 'Set'):
        return [_to_jsonable(v) for v in value]
    if hasattr(value, 'export_text'):
        return value.export_text()
    raise TypeError(tname)


def _from_jsonable(group, name, raw, hint=None):
    if raw is None or isinstance(raw, (bool, int, float)):
        return raw
    if isinstance(raw, list):
        cur = hint if hint is not None else group._uobj.get_editor_property(name)
        out = []
        for i, item in enumerate(raw):
            elem = None
            try:
                elem = cur[i]
            except Exception:
                pass
            out.append(_from_jsonable(group, name, item, elem))
        return out
    if not isinstance(raw, str):
        return raw
    if hint is None:
        try:
            hint = group._uobj.get_editor_property(name)
        except Exception:
            pass
    if name in type(group)._soft_path_names_:
        sp = unreal.SoftObjectPath()
        if raw:
            sp.import_text(raw)
        return sp
    hint_name = type(hint).__name__ if hint is not None else ''
    if hint_name in ('FilePath', 'DirectoryPath'):
        inst = type(hint)()
        if raw and not raw.lstrip().startswith('('):
            prop = 'file_path' if hint_name == 'FilePath' else 'path'
            inst.set_editor_property(prop, raw)
            return inst
        inst.import_text(raw)
        return inst
    if raw.startswith('/') and not isinstance(hint, str):
        obj = unreal.load_asset(raw) or unreal.find_object(None, raw)
        if obj:
            return obj
    if hint is not None and hasattr(hint, 'import_text') and not isinstance(hint, unreal.Object):
        inst = type(hint)()
        inst.import_text(raw)
        return inst
    return raw


class PropertyGroup:
    """自定义属性集，需要实例化再引用成员变量"""
    _unique_ = False
    _autosave_ = False  # True → 实例化 load 默认 json；setattr / Details 改值时 save
    _softcast_ = True # Actor→SoftObjectPath；取值时解析所有 SoftObjectPath / SoftClassPath

    _soft_props_ = {}
    _soft_path_names_ = frozenset()
    _prop_names_ = frozenset()
    _ue_class_ = None
    _ue_class_name_ = None
    _schema_ = None  # (properties, defaults, metas, ordered)
    _instance_ = None  # _unique_ 单例

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._soft_props_ = {}
        cls._ue_class_ = None
        cls._schema_ = None
        cls._instance_ = None

        # _unique_ 热重载：复用同名类已有的 uclass / 实例
        if cls._unique_:
            for existing_cls, obj in list(mcvars.Props.items()):
                if getattr(existing_cls, '__name__', None) != cls.__name__:
                    continue
                cls._prop_names_ = getattr(existing_cls, '_prop_names_', frozenset())
                cls._soft_path_names_ = getattr(existing_cls, '_soft_path_names_', frozenset())
                cls._soft_props_ = dict(getattr(existing_cls, '_soft_props_', {}))
                cls._ue_class_ = getattr(existing_cls, '_ue_class_', None)
                cls._ue_class_name_ = getattr(existing_cls, '_ue_class_name_', None)
                cls._schema_ = getattr(existing_cls, '_schema_', None)
                if isinstance(obj, PropertyGroup):
                    cls._instance_ = obj
                if cls._softcast_:
                    for name, t in getattr(cls, '__annotations__', {}).items():
                        if _is_actor_type(t):
                            cls._soft_props_[name] = t
                mcvars.Props[cls] = cls._instance_ or obj
                unreal.log(f"{cls.__name__}设置了 _unique_ = True, 直接使用已创建的属性集")
                return

        properties = {}
        defaults = {}
        metas = {}

        def register_soft_actor(name, t, meta=None):
            properties[name] = 'unreal.SoftObjectPath'
            cls._soft_props_[name] = t
            m = meta if meta is not None else {'Category': cls.__name__}
            m.setdefault('AllowedClasses', t.static_class().get_path_name())
            metas[name] = m

        if hasattr(cls, '__annotations__'):
            for name, t in cls.__annotations__.items():
                if cls._softcast_ and _is_actor_type(t):
                    register_soft_actor(name, t)
                else:
                    properties[name] = _get_ue_type_str(t)

        for name, val in cls.__dict__.items():
            if name.startswith('_') or callable(val):
                continue
            meta = metas.get(name, {'Category': cls.__name__})
            if isinstance(val, tuple):
                val, extra = val
                meta.update(extra)
            if name not in properties:
                t = type(val)
                if cls._softcast_ and _is_actor_type(t):
                    register_soft_actor(name, t, meta)
                elif isinstance(val, list) and val:
                    properties[name] = f'unreal.Array({_get_ue_type_str(type(val[0]))})'
                    metas[name] = meta
                elif isinstance(val, set) and val:
                    properties[name] = f'unreal.Set({_get_ue_type_str(type(next(iter(val))))})'
                    metas[name] = meta
                elif isinstance(val, dict) and val:
                    k, v = next(iter(val.items()))
                    properties[name] = (
                        f'unreal.Map({_get_ue_type_str(type(k))}, {_get_ue_type_str(type(v))})'
                    )
                    metas[name] = meta
                else:
                    properties[name] = _get_ue_type_str(t)
                    metas[name] = meta
            else:
                metas[name] = meta
            defaults[name] = val

        ordered = [n for n in getattr(cls, '__annotations__', {}) if n in properties]
        ordered += [n for n in cls.__dict__ if n in properties and n not in ordered]
        ordered += [n for n in properties if n not in ordered]
        for i, name in enumerate(ordered, 1):
            metas.setdefault(name, {'Category': cls.__name__}).setdefault('DisplayPriority', i)

        # 预先分配 GUID 类名，供 localize 在实例化前登记
        guid = uuid.uuid4().hex[:8]
        cls._ue_class_name_ = f'{cls.__name__}_GUID{guid}'
        cls._prop_names_ = frozenset(properties)
        cls._soft_path_names_ = frozenset(
            n for n, t in properties.items()
            if 'SoftObjectPath' in t or 'SoftClassPath' in t
        )
        cls._schema_ = (properties, defaults, metas, ordered)

        # 去掉类上的默认值属性，避免遮蔽实例 __getattr__/__setattr__
        for name in properties:
            if name in cls.__dict__:
                try:
                    delattr(cls, name)
                except Exception:
                    pass

    @classmethod
    def _ensure_ue_class(cls):
        """首次实例化时注册带 GUID 的 uclass（每 Python 类只注册一次）。"""
        if cls._ue_class_ is not None:
            return cls._ue_class_
        if not cls._schema_:
            raise RuntimeError(f'{cls.__name__} 无属性 schema，无法注册 uclass')

        properties, defaults, metas, ordered = cls._schema_
        ue_class_name = cls._ue_class_name_
        code_lines = [
            '@unreal.uclass()',
            f'class {ue_class_name}(unreal.Object):',
        ]
        for prop_name in ordered:
            meta = metas.get(prop_name, {'Category': cls.__name__})
            meta.setdefault('DisplayName', prop_name)
            code_lines.append(
                f'    {prop_name} = unreal.uproperty({properties[prop_name]}, meta={meta!r})'
            )
        code_lines.append('')

        exec_code = '\n'.join(code_lines)
        unreal.log(f'\n[注册数据对象] >>>\n{exec_code}\n<<< [End]')
        exec(exec_code, globals())
        cls._ue_class_ = eval(ue_class_name, globals())
        cdo = unreal.get_default_object(cls._ue_class_)
        for prop_name, default_val in defaults.items():
            if default_val is not None:
                cdo.set_editor_property(prop_name, default_val)
        return cls._ue_class_

    def __new__(cls, *args, **kwargs):
        if cls._unique_ and cls._instance_ is not None:
            return cls._instance_
        return super().__new__(cls)

    def __init__(self):
        if getattr(self, '_uobj', None) is not None:
            return
        ue_cls = type(self)._ensure_ue_class()
        object.__setattr__(self, '_uobj', construct(ue_cls))
        if type(self)._unique_:
            type(self)._instance_ = self
            mcvars.Props[type(self)] = self
        if type(self)._autosave_:
            self.load()

    @property
    def uobject(self):
        """底层 UObject，供 DetailsView / 外部 API 使用。"""
        return object.__getattribute__(self, '_uobj')

    def __getattr__(self, name):
        prop_names = type(self)._prop_names_
        if name not in prop_names:
            raise AttributeError(f'{type(self).__name__!r} object has no attribute {name!r}')
        value = self._uobj.get_editor_property(name)
        if type(self)._softcast_ and isinstance(
            value, (unreal.SoftObjectPath, unreal.SoftClassPath)
        ):
            return resolve_soft(value)
        return value

    def __setattr__(self, name, value):
        if name.startswith('_') or name not in type(self)._prop_names_:
            object.__setattr__(self, name, value)
            return
        if name in type(self)._soft_path_names_:
            if isinstance(value, unreal.Object):
                value = unreal.SoftObjectPath(value.get_path_name())
            elif isinstance(value, str):
                value = unreal.SoftObjectPath(value)
        self._uobj.set_editor_property(name, value)
        if type(self)._autosave_:
            self.save()

    def _json_path(self, path=''):
        if path:
            return Path(path)
        try:
            py = inspect.getfile(type(self))
        except TypeError:
            return None
        if not py or py.startswith('<'):
            return None
        return Path(py).resolve().parent / '__pycache__' / f'{type(self).__name__}.json'

    def save(self, path=''):
        """把字段写到 JSON。path 为空则用定义类的 .py 旁 __pycache__/{类名}.json；无源文件则跳过。"""
        dest = self._json_path(path)
        if not dest:
            return
        cls_name = type(self).__name__
        data = {}
        for name in type(self)._prop_names_:
            try:
                data[name] = _to_jsonable(self._uobj.get_editor_property(name))
            except Exception as exc:
                debug(f'{cls_name}.{name}: {exc}')
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as exc:
            debug(f'{cls_name}.save: {exc}')

    def load(self, path=''):
        """从 JSON 读字段。缺文件或单项失败只 debug，不打断。"""
        src = self._json_path(path)
        if not src:
            return
        cls_name = type(self).__name__
        if not src.is_file():
            debug(f'{cls_name}.load: missing {src}')
            return
        try:
            data = json.loads(src.read_text(encoding='utf-8'))
        except Exception as exc:
            debug(f'{cls_name}.load: {exc}')
            return
        names = type(self)._prop_names_
        for name, raw in data.items():
            if name not in names:
                continue
            try:
                self._uobj.set_editor_property(name, _from_jsonable(self, name, raw))
            except Exception as exc:
                debug(f'{cls_name}.{name}: {exc}')

    @classmethod
    def localize(cls, source: str, *args, **kwargs):
        """为变量或类别注入本地化翻译（可在实例化前调用）。
        args 对应 mcvars.Languages 的各语言翻译。
        kwargs 可传入自定义语言代码的翻译。
        """
        if source in cls._prop_names_ or source in getattr(cls, '__annotations__', {}):
            localize(source, *args, key=f'{cls._ue_class_name_}:{source}', **kwargs)
        else:
            localize(source, *args, namespace='UObjectCategory', **kwargs)


def alignment(HVtuple: int | tuple[int, int] =(1,1)):
    """解析 (水平, 垂直) 对齐方式, 0填充, 1靠左/靠上, 2居中, 3靠右/靠下"""
    if isinstance(HVtuple, (int, unreal.EnumBase)):
        HVtuple = (HVtuple, HVtuple)
    h,v = HVtuple
    h = h if isinstance(h, unreal.EnumBase) else enum(unreal.HorizontalAlignment)[h]
    v = v if isinstance(v, unreal.EnumBase) else enum(unreal.VerticalAlignment)[v]
    return (h,v)


def text_slot(align=(0, 1)):
    """TextBlock 槽位水平始终填充；align 的水平 1/2/3 映射为 justification。"""
    if isinstance(align, (int, unreal.EnumBase)):
        align = (align, align)
    justification = {
        2: unreal.TextJustify.CENTER,
        3: unreal.TextJustify.RIGHT,
        unreal.HorizontalAlignment.H_ALIGN_CENTER: unreal.TextJustify.CENTER,
        unreal.HorizontalAlignment.H_ALIGN_RIGHT: unreal.TextJustify.RIGHT,
    }.get(align[0], unreal.TextJustify.LEFT)
    return (0, align[1]), justification


def add_widget(root, widget: T,
               padding=unreal.Margin(3,1,3,1), align=(0,1), fill=False,
               clip=False, hidden=False, tooltip='', subclass=None) -> T:
    """添加子控件到根控件"""
    if subclass and unreal.MathLibrary.class_is_child_of(uclass(subclass), uclass(widget)):
        widget = subclass
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

    if hidden:
        widget.set_visibility(enum(unreal.SlateVisibility)[int(hidden)])

    widget.set_clipping(clip if isinstance(clip, unreal.WidgetClipping) else enum(unreal.WidgetClipping)[int(clip)])
    widgets.append(widget)
    return widget


def make_combo_text(item, texts=None, outer=None):
    """ComboBoxKey 默认条目：TextBlock。layout.combo 绑定前会传入 outer 与 FText 表。"""
    block = construct(unreal.TextBlock, outer)
    key = str(item)
    label = (texts or {}).get(key)
    if label is None:
        label = item if isinstance(item, unreal.Text) else unreal.Text(key)
    elif not isinstance(label, unreal.Text):
        label = unreal.Text(str(label))
    block.set_text(label)
    block.set_font(unreal.SlateFontInfo(
        font_object=uasset('/Engine/EditorResources/DefaultEditorFont.DefaultEditorFont'),
        size=10))
    return block


class Layout():
    """ 控件包装器, 可使用 layout.text(), layout.row() 等方法添加子控件  
    参数中的**kwargs可传入以下通用参数

    padding = unreal.Margin(3,1,3,1)
        可简写为(3,1), 也可简写至一个数字
    align = (0,0)
        (水平, 垂直) 对齐方式, 0填充, 1靠左/靠上, 2居中, 3靠右/靠下
    fill = False
        是否撑满整个区域, 传入小数表示比例
    clip = False
        是否裁剪超出部分
    tooltip = ''
        鼠标悬停提示文本
    hidden = False
        是否隐藏控件, 输入整数转化为SlateVisibility枚举
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
            if public or mcvars.DebugMode:
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

    def get(self, prop: str):
        """获取当前控件的编辑器属性"""
        return self.target.get_editor_property(prop)

    def set(self, prop: str, value):
        """设置当前控件的编辑器属性"""
        self.target.set_editor_property(prop, value)

    def hide(self, state: int | bool | unreal.SlateVisibility = True):
        """设置可视性, 隐藏控件"""
        if isinstance(state, unreal.SlateVisibility):
            self.target.set_visibility(state)
        else:
            self.target.set_visibility(enum(unreal.SlateVisibility)[int(state)])

    def get_local_size(self) -> unreal.Vector2D:
        """获取控件的本地尺寸"""
        return get_hotkey_object().call_method('GetLocalSize', (self.target,))

    def local_to_absolute(self, coord: unreal.Vector2D) -> unreal.Vector2D:
        """将本地坐标转换为绝对屏幕坐标"""
        return get_hotkey_object().call_method('LocalToAbsolute', (self.target, coord))

    def absolute_to_local(self, coord: unreal.Vector2D) -> unreal.Vector2D:
        """将绝对屏幕坐标转换为本地坐标"""
        return get_hotkey_object().call_method('AbsoluteToLocal', (self.target, coord))

    def get_mouse_local(self) -> unreal.Vector2D:
        """获取鼠标在控件本地坐标系中的位置"""
        position = unreal.WidgetLayoutLibrary.get_mouse_position_on_platform()
        return self.absolute_to_local(position)

    def get_mouse_uv(self) -> unreal.Vector2D:
        """获取鼠标在控件本地坐标系中的归一化坐标, 0~1表示鼠标在控件内"""
        local = self.get_mouse_local()
        size = self.get_local_size()
        return local / size if size.x and size.y else unreal.Vector2D(0, 0)

    def is_under_location(self, absolute_coord: unreal.Vector2D) -> bool:
        """检查绝对坐标是否在控件内部"""
        return get_hotkey_object().call_method('IsUnderLocation', (self.target, absolute_coord))


    ################################################################################


    def prop(self, data: unreal.Object | PropertyGroup, property: str=None, text: str=None,
             on_property_changed: Callable[[str], Any]=None,
             **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加属性视图；指定 property 为单属性，否则为完整细节面板。
        data 可为 UObject 或已实例化的 PropertyGroup。
        """
        obj = resolve_prop_object(data)
        if property:
            viewer = add_widget(self.target, unreal.SinglePropertyView, **kwargs)
            viewer.set_object(obj)
            viewer.set_property_name(property)
            if text:
                viewer.set_name_override(text)
        else:
            viewer = add_widget(self.target, unreal.DetailsView, **kwargs)
            viewer.set_object(obj)

        if on_property_changed or getattr(data, '_autosave_', False):
            pg, user = data, on_property_changed
            viewer.on_property_changed.add_callable(
                lambda n=None: (
                    pg.save() if getattr(pg, '_autosave_', False) else None,
                    user(str(n) if n else '') if user else None,
                )
            )
        return Layout(viewer, public=self._public_)


    def text(self, text='', size=14, wrap=False, color=unreal.LinearColor(1, 1, 1, 1),
             **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加文本。水平方向的align会传入文字的justification；文本框则在水平方向上撑满，适合wrap换行"""
        align, justify = text_slot(kwargs.pop('align', (0, 1)))
        text_block = add_widget(self.target, unreal.TextBlock, align=align, **kwargs)
        text_block.set_text(text)
        text_block.set_color_and_opacity(unreal.SlateColor(color))
        text_block.set_font(unreal.SlateFontInfo(
            font_object=uasset("/Engine/EditorResources/DefaultEditorFont.DefaultEditorFont"),
            size=size))
        text_block.set_editor_property('justification', justify)
        if wrap:
            text_block.set_auto_wrap_text(True)
            if type(wrap) in (int, float):
                text_block.set_editor_property('wrap_text_at', wrap)
        return Layout(text_block, public=self._public_)


    def title(self, text='', size=14, color=unreal.LinearColor(1, 1, 1, 1), align=(2, 1),
              **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加标题（默认居中的文本）"""
        return self.text(text, size, color=color, align=align, **kwargs)


    def image(self, image=None, color=unreal.LinearColor(1, 1, 1, 1), size=unreal.Vector2D(64, 64),
              **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加图片控件。不传入image为空白；标量 size 在有贴图时按比例，无贴图时为正方形。"""
        image_widget = add_widget(self.target, unreal.Image, **kwargs)
        tex = uasset(image) if image is not None else None
        if tex:
            image_widget.set_brush_resource_object(tex)
        image_widget.set_color_and_opacity(color)
        if isinstance(size, (int, float)):
            if tex:
                w, h = get_tex_size(tex)
                ratio = w / h if h else 1
                size = unreal.Vector2D(size, size / ratio) if ratio >= 1 else unreal.Vector2D(size * ratio, size)
            else:
                size = unreal.Vector2D(size, size)
        image_widget.set_desired_size_override(size)
        return Layout(image_widget, public=self._public_)


    def label(self, text='', size=14, color=unreal.LinearColor(1, 1, 1, 1),
              icon=None, icon_padding=unreal.Margin(0,0,4,0),
              **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加标签（可带图片的文本，icon为纹理资产路径），返回水平框"""
        label_row = self.row(**kwargs)
        if icon:
            w,h = get_tex_size(uasset(icon))
            ratio = w/h if h else 1
            #高度限定为1.4*size，宽度按比例缩放
            if ratio >= 1:
                icon_size = unreal.Vector2D(1.4*size, 1.4*size/ratio)
            else:
                icon_size = unreal.Vector2D(1.4*size*ratio, 1.4*size)
            label_row.image(icon, size=icon_size, padding=icon_padding, align=(1,2))
        label_text = label_row.text(text, size=size, color=color, padding=0)
        return label_row


    def button(self, text='', size=14, text_color=(1,1,1,1), text_padding=2,
               on_clicked: Callable[[], Any]=None,
               subclass: unreal.Button=unreal.EditorUtilityButton,
               **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加按钮，可绑定 on_clicked 回调"""
        button = add_widget(self.target, unreal.Button, subclass=subclass, **kwargs)
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

        if text:
            button_widget.text(text, size=size, align=(2, 1),
                               color=text_color, padding=text_padding)
        return button_widget


    def operator(self, text='', size=14, on_clicked: Callable[[], Any]=None,
                 **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        return self.button(text, size, on_clicked=on_clicked, **kwargs)


    def checkbox(self, text='', size=14,
                 on_check_state_changed: Callable[[bool], Any]=None,
                 subclass: unreal.CheckBox=unreal.EditorUtilityCheckBox,
                 **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加复选框，可绑定 on_check_state_changed 回调"""
        checkbox = add_widget(self.target, unreal.CheckBox, subclass=subclass, **kwargs)
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


    def spinbox(self, value=0.0, min: float=None, max: float=None, uimin: float=None, uimax: float=None,
                step: float=0, digits=2, size=10, width: float=None,
                on_value_changed: Callable[[float], Any]=None,
                on_value_committed: Callable[[float, unreal.TextCommit], Any]=None,
                subclass: unreal.SpinBox=unreal.EditorUtilitySpinBox,
                **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加数字滑块，可绑定 on_value_changed / on_value_committed 回调"""
        box = add_widget(self.target, unreal.SpinBox, subclass=subclass, **kwargs)
        box.set_editor_property('font', unreal.SlateFontInfo(
            font_object=uasset("/Engine/EditorResources/DefaultEditorFont.DefaultEditorFont"),
            size=size))
        if width is not None:
            box.set_editor_property('min_desired_width', float(width))
        if min is not None:
            box.set_min_value(float(min))
        if max is not None:
            box.set_max_value(float(max))
        if uimin is not None:
            box.set_min_slider_value(float(uimin))
        if uimax is not None:
            box.set_max_slider_value(float(uimax))
        box.set_editor_property('min_fractional_digits', digits)
        box.set_editor_property('max_fractional_digits', digits)
        box.set_editor_property('delta', float(step))
        box.set_editor_property('justification', unreal.TextJustify.CENTER)
        box.set_value(float(value))
        if on_value_changed:
            box.on_value_changed.add_callable(on_value_changed)
        if on_value_committed:
            box.on_value_committed.add_callable(on_value_committed)
        return Layout(box, public=self._public_)


    def textbox(self, text='', hint='',
                on_text_changed: Callable[[str], Any]=None,
                on_text_committed: Callable[[str, unreal.TextCommit], Any]=None,
                subclass: unreal.EditableTextBox=unreal.EditorUtilityEditableTextBox,
                **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加文本框，可绑定 on_text_changed / on_text_committed 回调"""
        box = add_widget(self.target, unreal.EditableTextBox, subclass=subclass, **kwargs)
        if text:
            box.set_text(text)
        if hint:
            box.set_hint_text(hint)
        if on_text_changed:
            box.on_text_changed.add_callable(on_text_changed)
        if on_text_committed:
            box.on_text_committed.add_callable(on_text_committed)
        return Layout(box, public=self._public_)



    def combo(self, options: list|dict=(), selected: str=None,
              on_generate_content_widget=make_combo_text,
              on_generate_item_widget=make_combo_text,
              on_selection_changed: Callable[[str, Any], Any]=None,
              on_opening: Callable[[], Any]=None,
              subclass: unreal.ComboBoxKey=unreal.EditorUtilityComboBoxKey,
              **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加下拉框（ComboBoxKey）。options 为列表（key=原文）或字典 {key: text}。"""

        def _combo_widget(result):
            return result.target if isinstance(result, Layout) else result

        def _combo_options(options):
            if isinstance(options, dict):
                items = options.items()
            else:
                items = ((str(opt), opt) for opt in (options or ()))
            keys, texts = [], {}
            for key, label in items:
                key = str(key)
                keys.append(key)
                texts[key] = label if isinstance(label, unreal.Text) else unreal.Text(str(label))
            return keys, texts

        def bind_generate(fn):
            if fn is make_combo_text:
                def wrapped(item):
                    return make_combo_text(str(item), texts=texts, outer=box)
                return wrapped
            def wrapped(item):
                return _combo_widget(fn(str(item)))
            return wrapped

        box = add_widget(self.target, unreal.ComboBoxKey, subclass=subclass, **kwargs)
        keys, texts = _combo_options(options)

        gen_content = bind_generate(on_generate_content_widget)
        gen_item = bind_generate(on_generate_item_widget)
        box.get_editor_property('on_generate_content_widget').bind_callable(gen_content)
        box.get_editor_property('on_generate_item_widget').bind_callable(gen_item)
        for key in keys:
            box.add_option(unreal.Name(key))
        if selected is not None and keys:
            if isinstance(selected, int):
                pick = keys[max(0, min(selected, len(keys) - 1))]
            else:
                pick = str(selected)
            if pick in keys:
                box.set_selected_option(unreal.Name(pick))

        node = Layout(box, public=self._public_)
        node._combo_texts = texts
        node._combo_keys = keys
        node._combo_gen_content = gen_content
        node._combo_gen_item = gen_item
        if on_selection_changed:
            def on_sel(name, reason):
                on_selection_changed(str(name), reason)
            box.on_selection_changed.add_callable(on_sel)
            node._combo_on_sel = on_sel
        if on_opening:
            box.on_opening.add_callable(on_opening)
            node._combo_on_open = on_opening
        return node


    def row(self, **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加水平布局容器"""
        return Layout(add_widget(self.target, unreal.HorizontalBox, **kwargs), public=self._public_)


    def column(self, **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加垂直布局容器"""
        return Layout(add_widget(self.target, unreal.VerticalBox, **kwargs), public=self._public_)


    def col(self, **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加垂直布局容器"""
        return self.column(**kwargs)


    def spacer(self, size=unreal.Vector2D(1, 1),
               **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加空白占位"""
        spacer = add_widget(self.target, unreal.Spacer, **kwargs)
        size = (size, size) if isinstance(size, (int, float)) else size
        spacer.set_size(size)
        return Layout(spacer, public=self._public_)


    def overlay(self, padding=0, align=(0, 0), fill=True,
                **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加叠加布局容器"""
        return Layout(add_widget(self.target, unreal.Overlay, padding=padding, align=align, fill=fill, **kwargs), public=self._public_)


    def switcher(self, animated=False,
                 **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加页面切换器；animated=True 使用动画切换"""
        switcher_type = unreal.CommonAnimatedSwitcher if animated else unreal.WidgetSwitcher
        return Layout(add_widget(self.target, switcher_type, **kwargs), public=self._public_)


    def scalebox(self, scale: float=None, padding=0,
                 **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加缩放容器，可指定scale为固定缩放比例。若要动态调整scale，需设置默认值"""
        scalebox = add_widget(self.target, unreal.ScaleBox, padding=padding, **kwargs)
        if scale is not None:
            scalebox.set_editor_property('Stretch', unreal.Stretch.USER_SPECIFIED)
            scalebox.set_editor_property('UserSpecifiedScale', float(scale))
        return Layout(scalebox, public=self._public_)


    def sizebox(self, width=None, height=None,
                **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """固定宽高的容器；省略的边不覆盖，之后仍可 set_width_override / set_height_override"""
        box = add_widget(self.target, unreal.SizeBox, **kwargs)
        if width is not None:
            box.set_width_override(float(width))
        if height is not None:
            box.set_height_override(float(height))
        return Layout(box, public=self._public_)


    def wrapbox(self, inner_padding=(0, 0),
                **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """自动换行容器；inner_padding 为格子间距（标量或 (x, y)）"""
        wrap = add_widget(self.target, unreal.WrapBox, **kwargs)
        if isinstance(inner_padding, (int, float)):
            inner_padding = (inner_padding, inner_padding)
        wrap.set_editor_property('inner_slot_padding', inner_padding)
        return Layout(wrap, public=self._public_)


    def scrollbox(self, smooth_scroll=False, horizontal=False,
                  subclass: unreal.ScrollBox=unreal.EditorUtilityScrollBox,
                  **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加滚动容器；smooth_scroll 可传速度，horizontal 开启横向滚动"""
        scrollbox = add_widget(self.target, unreal.ScrollBox, subclass=subclass, **kwargs)
        if smooth_scroll:
            scrollbox.set_animate_wheel_scrolling(True)
            scrollbox.set_scroll_animation_interpolation_speed(float(smooth_scroll))
        if horizontal:
            scrollbox.set_orientation(unreal.Orientation.ORIENT_HORIZONTAL)
        return Layout(scrollbox, public=self._public_)


    def border(self, color=unreal.LinearColor(0,0,0,0), padding=0,
               on_mouse_button_down: Callable[['Layout'], Any | unreal.EventReply]=None,
               on_mouse_button_up: Callable[['Layout'], Any | unreal.EventReply]=None,
               on_mouse_double_click: Callable[['Layout'], Any | unreal.EventReply]=None,
               on_mouse_move: Callable[['Layout'], Any | unreal.EventReply]=None,
               **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加边框容器，可绑定鼠标事件回调。
        回调参数本来是Geometry和PointerEvent，但它们传入python会变成空包 无法使用，
        因此把参数暂时设为控件自身的Layout包装器，可使用get_mouse_local()等函数"""
        border = Layout(add_widget(self.target, unreal.Border, padding=padding, **kwargs), public=self._public_)
        border.set_brush_color(color)

        def handled(func, *args):
            result = func(*args)
            if isinstance(result, unreal.EventReply):
                return result
            return unreal.WidgetLibrary.handled() if result else unreal.WidgetLibrary.unhandled()

        if on_mouse_button_down:
            border.get('on_mouse_button_down_event').bind_callable(
                lambda x,y : handled(on_mouse_button_down, border))
        if on_mouse_button_up:
            border.get('on_mouse_button_up_event').bind_callable(
                lambda x,y : handled(on_mouse_button_up, border))
        if on_mouse_double_click:
            border.get('on_mouse_double_click_event').bind_callable(
                lambda x,y : handled(on_mouse_double_click, border))
        if on_mouse_move:
            border.get('on_mouse_move_event').bind_callable(
                lambda x,y : handled(on_mouse_move, border))

        return border


    def custom(self, widget, **kwargs: padding_align_fill_clip_tooltip_hidden_subclass):
        """添加自定义控件类型或实例"""
        return Layout(add_widget(self.target, widget, **kwargs), public=self._public_)


def ui(script='', save_path=None, run=True):
    """创建一个新的自定义控件并运行, 可设置保存名称或路径，输入名称时会自动保存到/Game/mc/mods/"""
    if mcvars.DebugMode:
        unreal.log(script)

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

