from __future__ import annotations

"""
CLI URL 配置应用模块。

把 `bank_all_promo_rates.py` / portable 里的这段逻辑抽离出来：
1) 读取 `--url-config` 文件（xlsx/json 等）
2) 获取脚本内置默认 URL 映射（argparse dest -> 默认 URL）
3) 把外部配置“作为默认值覆盖”，但保持 CLI 显式传参优先级
"""

from typing import Any

from url_config_loader import load_url_config
from url_defaults import get_url_defaults
from url_args_override import apply_url_config_defaults

from bank_safety import safe_call


@safe_call(
    context="应用 URL 配置到 CLI args",
    default_value=None,
)
def apply_url_config_to_cli_args(args: Any) -> None:
    """
    根据 `args.url_config` 把外部配置应用为 argparse 的“默认值覆盖”。

    关键点（与 argparse 优先级相关）：
    - `apply_url_config_defaults()` 的实现会检查“当前 args.dest 的值是否仍等于脚本内置默认值”
      若等于，说明用户没有在 CLI 显式覆盖它，那么才把外部配置写回 args；
    - 若用户在命令行显式给了该参数，则 `current_val != default_val`，外部配置不会覆盖，
      从而保证 CLI 优先级。
    """

    url_config = load_url_config(args.url_config)
    url_defaults = get_url_defaults()
    apply_url_config_defaults(args, url_config, url_defaults)


# Safety net: 自动给本模块中所有 def 加异常兜底
from bank_safety import auto_wrap_module_functions as _auto_wrap_module_functions

_auto_wrap_module_functions(globals(), module_name=__name__)

