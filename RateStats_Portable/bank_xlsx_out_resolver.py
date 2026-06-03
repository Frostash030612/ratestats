from __future__ import annotations

"""
可移植版本的 MarketRateData .xlsx 输出路径解析器。

用于 `RateStats_Portable/bank_all_promo_rates.py`，保证在 portable 目录运行时，
仍能获得与主脚本一致的输出路径行为。
"""

import os
import re
from datetime import datetime
from typing import Optional

from bank_safety import safe_call


@safe_call(
    context="解析 --xlsx-out 参数（portable）",
    default_value=None,
)
def resolve_xlsx_out(raw: Optional[str]) -> Optional[str]:
    """
    将 CLI 的 `--xlsx-out` 参数解析为最终输出文件路径（与主目录一致）。
    """

    if raw is None:
        return None

    capture_tag = datetime.now().strftime("%Y%m%d_%H.%M")
    expanded = os.path.expanduser(raw)
    # MarketRateData_YYYYMMDD_HH.mm | _HH | _AISearch variants
    _tagged = re.compile(r"_\d{8}(_\d{2}(\.\d{2})?)?(_AISearch)?$|_\d{14}(_AISearch)?$")

    if expanded == "." or os.path.isdir(expanded):
        folder = os.path.abspath(expanded if expanded != "." else os.getcwd())
        return os.path.join(folder, f"MarketRateData_{capture_tag}.xlsx")

    root, ext = os.path.splitext(expanded)
    if ext.lower() != ".xlsx":
        expanded = expanded + ".xlsx"
        root, ext = os.path.splitext(expanded)

    base = os.path.basename(root)
    if _tagged.search(base):
        return os.path.abspath(expanded)

    return os.path.abspath(f"{root}_{capture_tag}{ext}")


# Safety net: 自动给本模块中所有 def 加异常兜底
from bank_safety import auto_wrap_module_functions as _auto_wrap_module_functions

_auto_wrap_module_functions(globals(), module_name=__name__)

