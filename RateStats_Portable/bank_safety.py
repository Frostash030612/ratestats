from __future__ import annotations

"""
可移植版本：通用安全执行装饰器。

与主目录 `bank_safety.py` 逻辑一致。
"""

import functools
import sys
import traceback
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")


def _summarize_call_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    "生成简短参数摘要，避免日志过长。"
    try:
        arg_types = [type(v).__name__ for v in args[:6]]
        kw_keys = list(kwargs.keys())[:10]
        return f"args_types={arg_types}, kwargs_keys={kw_keys}"
    except Exception:
        return "args_summary_unavailable"


class SafeProxy:
    """
    一个“尽量不崩”的空对象，用作异常时的安全默认返回值。
    """

    def __init__(self, default: Any = None):
        "初始化安全代理对象，并记录默认回退值。"
        self._default = default

    def get(self, key: Any, default: Any = None) -> Any:
        "模拟 dict.get 行为，异常场景下返回安全默认值。"
        return default if default is not None else self._default

    def __getitem__(self, key: Any) -> Any:
        "模拟下标读取，始终返回默认回退值。"
        return self._default

    def __contains__(self, item: Any) -> bool:
        "模拟 in 判断，始终返回 False。"
        return False

    def __iter__(self):
        "返回空迭代器，避免上层遍历崩溃。"
        return iter(())

    def __len__(self) -> int:
        "长度固定为 0，用于安全空集合语义。"
        return 0

    def __bool__(self) -> bool:
        "布尔值恒为 False，便于 if 判空。"
        return False

    def __str__(self) -> str:
        "将回退值转换为字符串输出。"
        return "" if self._default is None else str(self._default)

    def __repr__(self) -> str:
        "用于调试显示当前安全代理类型。"
        return "SafeProxy()"

    def __getattr__(self, name: str) -> Any:
        "返回 no-op 函数，链式访问时继续提供安全代理。"
        def _noop(*args: Any, **kwargs: Any) -> Any:
            "拦截未知调用并返回新的安全代理对象。"
            return SafeProxy(self._default)

        return _noop


def safe_call(
    *,
    context: Optional[str] = None,
    default_factory: Optional[Callable[[BaseException, tuple[Any, ...], dict[str, Any]], Any]] = None,
    default_value: Any = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    "装饰器工厂：为函数统一加异常兜底与可选默认返回。"
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        "包装目标函数并注入异常处理逻辑。"
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            "实际调用层：执行目标函数，异常时按策略回退。"
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                ctx = context or fn.__name__
                print(f"[ERROR] {ctx} 失败：{e}", file=sys.stderr)
                print(f"[ERROR] {ctx} 调用参数：{_summarize_call_args(args, kwargs)}", file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                if default_factory is not None:
                    return default_factory(e, args, kwargs)
                if default_value is not None:
                    return default_value
                return SafeProxy()  # type: ignore[return-value]

        # 标记：避免被 auto_wrap_module_functions 重复包一层
        setattr(wrapper, "_citi_safe_wrapped", True)

        return wrapper

    return decorator


def auto_wrap_module_functions(
    module_globals: dict[str, Any],
    *,
    module_name: Optional[str] = None,
    exclude: Optional[set[str]] = None,
) -> None:
    """
    自动给模块里的函数加异常兜底（同主目录逻辑）。
    """

    import types

    exclude = exclude or set()
    if module_name is None:
        module_name = module_globals.get("__name__")

    for name, obj in list(module_globals.items()):
        if name in exclude:
            continue
        if not isinstance(obj, types.FunctionType):
            continue
        if module_name and getattr(obj, "__module__", None) != module_name:
            continue
        if getattr(obj, "_citi_safe_wrapped", False):
            continue

        wrapped = safe_call(
            context=f"{module_name}.{name}",
            default_value=None,
        )(obj)
        setattr(wrapped, "_citi_safe_wrapped", True)
        module_globals[name] = wrapped


def auto_wrap_loaded_modules_functions(
    *,
    name_prefixes: Optional[tuple[str, ...]] = None,
    file_path_contains: Optional[tuple[str, ...]] = ("RateStats",),
    exclude_modules: Optional[set[str]] = None,
) -> None:
    """
    运行时“二次兜底”：遍历当前已导入的模块，对项目内模块的顶层 `def` 再做自动包裹。
    """

    import types
    import os

    exclude_modules = exclude_modules or {"citi_safety"}
    prefixes = name_prefixes or ("citi_", "url_")
    exclude_func_names = {
        "safe_call",
        "auto_wrap_module_functions",
        "auto_wrap_loaded_modules_functions",
    }

    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        mod_name = getattr(mod, "__name__", "")
        if not mod_name or mod_name in exclude_modules:
            continue

        if not any(mod_name.startswith(p) for p in prefixes):
            continue

        mod_file = getattr(mod, "__file__", None)
        if not mod_file:
            continue

        try:
            mod_file_norm = str(mod_file).lower()
        except Exception:
            continue

        if file_path_contains:
            if not any(token.lower() in mod_file_norm for token in file_path_contains):
                continue

        if "site-packages" in mod_file_norm or "dist-packages" in mod_file_norm:
            continue

        mod_dict = getattr(mod, "__dict__", None)
        if not isinstance(mod_dict, dict):
            continue

        try:
            auto_wrap_module_functions(
                mod_dict,
                module_name=mod_name,
                exclude=exclude_func_names,
            )
        except Exception as e:
            print(f"自动兜底：模块 {mod_name} 包装失败：{e}", file=sys.stderr)


