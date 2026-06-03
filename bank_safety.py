from __future__ import annotations

"""
通用安全执行装饰器。

目标：
- 给函数加 try/except：捕获异常、用“中文原因”打印到 stderr；
- 返回“安全默认值”（由 default_factory 决定），避免程序因子步骤失败而崩溃。
"""

import functools
import sys
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")


class SafeProxy:
    """
    一个“尽量不崩”的空对象，用作异常时的安全默认返回值。

    设计目标：当下游代码只做常见的读取/条件判断/方法调用时，避免因 None/类型错误导致整体崩溃。
    """

    def __init__(self, default: Any = None):
        self._default = default

    def get(self, key: Any, default: Any = None) -> Any:
        return default if default is not None else self._default

    def __getitem__(self, key: Any) -> Any:
        return self._default

    def __contains__(self, item: Any) -> bool:
        return False

    def __iter__(self):
        return iter(())

    def __len__(self) -> int:
        return 0

    def __bool__(self) -> bool:
        return False

    def __str__(self) -> str:
        return "" if self._default is None else str(self._default)

    def __repr__(self) -> str:
        return "SafeProxy()"

    def __getattr__(self, name: str) -> Any:
        # 返回一个“空操作方法”，避免 `.foo()` 调用时崩溃。
        def _noop(*args: Any, **kwargs: Any) -> Any:
            return SafeProxy(self._default)

        return _noop


def safe_call(
    *,
    context: Optional[str] = None,
    default_factory: Optional[Callable[[BaseException, tuple[Any, ...], dict[str, Any]], Any]] = None,
    default_value: Any = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    装饰器：当被装饰函数抛出异常时：
    1) 在 stderr 打印：`<context or function_name> 失败：<exception>`
    2) 返回 default_value 或 default_factory(...) 的结果

    Parameters
    ----------
    context:
        错误输出使用的上下文字符串；为空则使用函数名。
    default_factory:
        可选。接收 (exc, args_tuple, kwargs_dict) -> 返回安全默认值。
    default_value:
        default_factory 为空时返回该值。
    """

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                ctx = context or fn.__name__
                print(f"{ctx} 失败：{e}", file=sys.stderr)
                if default_factory is not None:
                    return default_factory(e, args, kwargs)
                if default_value is not None:
                    return default_value
                # 如果调用方没有提供默认值，用 SafeProxy 降级，尽量让后续逻辑继续跑。
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
    自动给模块里的函数加异常兜底。

    会遍历 `module_globals`，把满足条件的 `def` 用 safe_call 包起来：
    - 函数名不在 exclude 内
    - 函数对象的 `__module__` 与 module_name（或当前模块名）一致
    - 跳过已被 safe_call 包过的函数（wrapper 上打了标记）
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

    为什么需要它：
    - 你之前要求“全部都加”，但手工逐文件逐函数很容易遗漏某些中间模块。
    - 通过 sys.modules + 文件路径过滤，可以把覆盖面扩大到“运行时实际导入过的模块”。

    过滤策略（尽量不碰第三方库）：
    - 仅处理模块名满足 `name_prefixes` 的模块；
    - 且模块 `__file__` 路径中包含 `file_path_contains` 中的任意 token。
    - 默认排除 `citi_safety` 自身，避免对安全基础设施再包一层。
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

        # 避免对 site-packages 之类依赖库生效
        if "site-packages" in mod_file_norm or "dist-packages" in mod_file_norm:
            continue

        mod_dict = getattr(mod, "__dict__", None)
        if not isinstance(mod_dict, dict):
            continue

        # 对模块内顶层函数包异常兜底
        try:
            auto_wrap_module_functions(
                mod_dict,
                module_name=mod_name,
                exclude=exclude_func_names,
            )
        except Exception as e:
            # 二次兜底本身也要尽量不中断主流程
            print(f"自动兜底：模块 {mod_name} 包装失败：{e}", file=sys.stderr)


