from __future__ import annotations

"""
可移植版本的 CLI URL 配置应用模块。

逻辑与主目录 `bank_cli_url_config_applier.py` 一致。
"""

from typing import Any
import sys
import traceback

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
    根据 `args.url_config` 把外部配置应用为 argparse 的默认值覆盖（CLI 显式传参优先）。
    """

    try:
        url_config = load_url_config(args.url_config)
        url_defaults = get_url_defaults()
        apply_url_config_defaults(args, url_config, url_defaults)
    except Exception as e:
        print(f"[PARAM] apply_url_config_to_cli_args 失败：{e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        raise


# Safety net: 自动给本模块中所有 def 加异常兜底
from bank_safety import auto_wrap_module_functions as _auto_wrap_module_functions

_auto_wrap_module_functions(globals(), module_name=__name__)

