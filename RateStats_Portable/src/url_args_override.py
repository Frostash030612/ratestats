from __future__ import annotations

"""
可移植版本的 CLI 参数覆盖辅助模块。

该模块与主目录 `url_args_override.py` 语义一致，用于在 portable 脚本中
同样遵守“命令行显式传参优先”的覆盖规则。
"""

from typing import Any, Mapping
import sys
import traceback

from bank_safety import safe_call


@safe_call(
    context="应用 URL 配置到 argparse args（portable）",
    default_value=None,
)
def apply_url_config_defaults(
    args: Any,
    url_config: Mapping[str, str],
    url_defaults: Mapping[str, str],
) -> None:
    """
    将外部 URL 配置覆盖到 argparse 的 args 上（就地修改）。

    覆盖规则：
    - 遍历 url_defaults 的每个 dest
    - 只有当 dest 存在于 url_config 且 args 当前值等于脚本内置默认值时，
      才用 url_config[dest] 替换。

    这样保证：用户如果通过命令行显式传参（args != 默认值），就不会被外部配置覆盖。
    """
    try:
        for dest, default_val in url_defaults.items():
            # 只遍历我们“关心并可能被覆盖”的 dest 集合；避免 url_config 里出现未知字段时误覆盖。
            if dest not in url_config:
                continue

            # 当前 args.dest 的值：如果等于内置默认值，说明用户没有通过命令行显式改它。
            current_val = getattr(args, dest, None)
            if current_val == default_val:
                # 保持 CLI 优先：当且仅当用户未显式覆盖时，使用外部配置写回。
                setattr(args, dest, url_config[dest])
    except Exception as e:
        print(f"[PARAM] apply_url_config_defaults 失败：{e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        raise


# Safety net: 自动给本模块中所有 def 加异常兜底
from bank_safety import auto_wrap_module_functions as _auto_wrap_module_functions

_auto_wrap_module_functions(globals(), module_name=__name__)

