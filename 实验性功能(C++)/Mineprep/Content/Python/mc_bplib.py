# -*- coding: utf-8 -*-
"""
Mineprep 蓝图函数库 (Blueprint Function Library) 反射调用器与语法糖包装。

支持纯蓝图函数库在 Python 中的多种优雅调用方式：
    - 函数式调用: BPLib('ASCII码表')、EditorBPLib('限制小数位数', 123.45678, 3)
    - 属性式调用: BPLib.ASCII码表()、EditorBPLib.限制小数位数(123.45678, 3)
    - 索引式调用: BPLib['ASCII码表']()
    - 智能代码补全: dir(BPLib) 自动列出全部蓝图函数名
    - 友好纠错推荐: 调用不存在的函数时自动模糊匹配并建议正确名称
"""

try:
    import unreal
except ModuleNotFoundError:
    from mc_utils import Lazy as unreal
import difflib
from typing import Any, List, Optional
from mc_utils import prints, warn, throw, world


class BPLibCaller:
    """通用蓝图函数库（Blueprint Function Library）反射调用器。
    
    自动处理 BlueprintGeneratedClass 加载、CDO 单例获取、隐式 world_context 参数注入与返回值解包。
    """

    def __init__(self, asset_path: str, display_name: Optional[str] = None):
        self.asset_path = asset_path.rstrip('/')
        self.cls_name = self.asset_path.split('/')[-1] + '_C'
        self.class_path = f"{self.asset_path}.{self.cls_name}"
        self.display_name = display_name or self.asset_path.split('/')[-1]
        
        self._gen_cls = None
        self._cdo = None
        self._functions = None

    @property
    def gen_cls(self) -> unreal.Class:
        """延迟加载并缓存 BlueprintGeneratedClass"""
        if self._gen_cls is None:
            self._gen_cls = unreal.load_class(None, self.class_path)
            if not self._gen_cls:
                asset = unreal.load_asset(self.asset_path)
                if asset and hasattr(asset, 'generated_class'):
                    self._gen_cls = asset.generated_class()
            if not self._gen_cls:
                throw(f"无法加载蓝图类: {self.class_path} (资产路径: {self.asset_path})")
        return self._gen_cls

    @property
    def cdo(self) -> unreal.Object:
        """获取类默认对象 (Class Default Object)"""
        if self._cdo is None:
            self._cdo = unreal.get_default_object(self.gen_cls)
            if not self._cdo:
                throw(f"无法获取类默认对象 (CDO): {self.class_path}")
        return self._cdo

    def _get_world(self) -> Optional[unreal.World]:
        """获取当前世界上下文 (优先使用 mc_utils.world()，回退为编辑器世界)"""
        try:
            return world()
        except Exception:
            subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
            return subsystem.get_editor_world() if subsystem else None

    @property
    def functions(self) -> List[str]:
        """获取该蓝图函数库中定义的所有函数名称列表"""
        if self._functions is None:
            func_names = []
            try:
                from editor_toolset.toolsets.blueprint import BlueprintTools
                tools = BlueprintTools()
                bp = unreal.load_asset(self.asset_path)
                if bp:
                    func_names = [g.get_name() for g in tools.list_graphs(bp) if g.get_name() != 'EventGraph']
            except Exception:
                pass
            self._functions = sorted(func_names)
        return self._functions

    def call(self, func_name: str, *args, **kwargs) -> Any:
        """调用蓝图函数库中的具体函数。
        
        自动注入当前 WorldContext，并具备智能容错与多参数适配能力。
        """
        cdo = self.cdo
        w = kwargs.pop('world', None) or self._get_world()
        
        # 1. 优先尝试在末尾追加 world_context (绝大部分蓝图静态函数的底层约定)
        if w is not None:
            try:
                return cdo.call_method(func_name, tuple(args) + (w,))
            except TypeError as e:
                err_msg = str(e)
                # 若提示参数过多或函数本身无需 world_context
                if "too many" in err_msg or "takes" in err_msg:
                    return cdo.call_method(func_name, tuple(args))
                # 若提示在第 1 个参数位置要求传入 world_context
                elif "world_context" in err_msg and "(pos 1)" in err_msg:
                    return cdo.call_method(func_name, (w,) + tuple(args))
                throw(e)
            except Exception as e:
                self._handle_call_exception(func_name, e)
        
        # 2. 无可用 world 上下文时直接调用
        try:
            return cdo.call_method(func_name, tuple(args))
        except Exception as e:
            self._handle_call_exception(func_name, e)

    def _handle_call_exception(self, func_name: str, exc: Exception):
        """增强异常提示，提供拼写相似的函数候选"""
        err_msg = str(exc)
        if "Failed to find function" in err_msg or "not found" in err_msg:
            matches = difflib.get_close_matches(func_name, self.functions, n=3, cutoff=0.3)
            suggestion = f"\n你是否想调用: {', '.join(repr(m) for m in matches)}?" if matches else ""
            throw(f"蓝图函数库 '{self.display_name}' 中未找到函数 '{func_name}'。{suggestion}")
        throw(exc)

    def __call__(self, func_name: str, *args, **kwargs) -> Any:
        """支持函数式风格调用: BPLib('函数名', *args)"""
        return self.call(func_name, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        """支持属性式风格调用: BPLib.函数名(*args)"""
        if name.startswith('_'):
            throw(AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'"))
        return lambda *args, **kwargs: self.call(name, *args, **kwargs)

    def __getitem__(self, name: str) -> Any:
        """支持下标字典风格调用: BPLib['函数名'](*args)"""
        return lambda *args, **kwargs: self.call(name, *args, **kwargs)

    def __dir__(self) -> List[str]:
        """返回所有标准属性以及当前蓝图函数名，支持交互式控制台中的自动补全"""
        std_attrs = super().__dir__()
        return sorted(set(std_attrs) | set(self.functions))

    def __repr__(self) -> str:
        count_str = f"{len(self.functions)} 个函数" if self._functions is not None else "未初始化"
        return f"<BPLibCaller '{self.display_name}' ({count_str}) -> {self.asset_path}>"

    def help(self, func_name: Optional[str] = None):
        """打印函数库帮助信息或所有可用函数清单"""
        if func_name:
            if func_name in self.functions:
                prints(f"[{self.display_name}] 函数: {func_name}")
            else:
                matches = difflib.get_close_matches(func_name, self.functions, n=3, cutoff=0.3)
                warn(f"[{self.display_name}] 未找到函数 '{func_name}'" + (f"，相似函数: {matches}" if matches else ""))
            return

        lines = [f"=== {self.display_name} 可用函数列表 ({len(self.functions)} 个) ==="]
        for i, fn in enumerate(self.functions, 1):
            lines.append(f"{i:2d}. {fn}")
        prints("\n".join(lines), duration=10.0)


################################################################################

class CoreBPLib(BPLibCaller):
    """Minecraft 核心自定义函数库 (/Game/Mineprep/MC_Blueprint/Core/自定义函数)"""
    def __init__(self):
        super().__init__('/Game/Mineprep/MC_Blueprint/Core/自定义函数', display_name='BPLib')


class EditorBPLibClass(BPLibCaller):
    """Mineprep 插件通用函数库 (/Game/Mineprep/插件贴图/插件函数库)"""
    def __init__(self):
        super().__init__('/Game/Mineprep/插件贴图/插件函数库', display_name='EditorBPLib')


BPLib = CoreBPLib()
EditorBPLib = EditorBPLibClass()
