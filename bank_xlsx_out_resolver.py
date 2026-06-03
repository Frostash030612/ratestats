from __future__ import annotations

"""
MarketRateData .xlsx 输出路径解析器。

把 `bank_all_promo_rates.py` / `RateStats_Portable/bank_all_promo_rates.py` 里
`resolve_xlsx_out()` 的重复逻辑抽离出来，保证两端行为一致。
"""

import os
import re
from datetime import datetime
from typing import Optional

from bank_safety import safe_call


@safe_call(
    context="解析 --xlsx-out 参数",
    default_value=None,
)
def resolve_xlsx_out(raw: Optional[str]) -> Optional[str]:
    """
    将 CLI 的 `--xlsx-out` 参数解析为最终输出文件路径。

    约定行为（与旧脚本保持一致）：
    - `--xlsx-out` 单独出现（Flag）：输出到当前目录，文件名为 `MarketRateData_YYYYMMDD_HH.mm.xlsx`
    - `--xlsx-out` 传一个“已有目录路径”：输出到该目录下
    - `--xlsx-out` 传一个 `.xlsx` 文件路径：
        - 若文件名（不含后缀）已以 `_{YYYYMMDD}`、`_{YYYYMMDD}_{HH.mm}`、`_{YYYYMMDD}_{HHmmss}` 或 `_{YYYYMMDDHHmmss}` 结尾，则直接使用
        - 否则把 `_{YYYYMMDD}_{HH.mm}` 插入到后缀前

    Parameters
    ----------
    raw:
        CLI 传入的字符串（可能为 None）。

    Returns
    -------
    Optional[str]
        最终输出的绝对路径；若 raw 为 None 则返回 None。
    """

    if raw is None:
        return None

    # 例如 20260513_18.00（抓取日期 + 小时.分钟）
    capture_tag = datetime.now().strftime("%Y%m%d_%H.%M")
    expanded = os.path.expanduser(raw)
    # _YYYYMMDD、_YYYYMMDD_HH.mm、_YYYYMMDD_HHmmss、_YYYYMMDDHHmmss（旧重试名）
    _tagged = re.compile(r"_(\d{8}(_\d{2}\.\d{2}|_\d{6})?|\d{14})$")

    # 目录：直接拼接 MarketRateData_{capture_tag}.xlsx
    if expanded == "." or os.path.isdir(expanded):
        folder = os.path.abspath(expanded if expanded != "." else os.getcwd())
        return os.path.join(folder, f"MarketRateData_{capture_tag}.xlsx")

    # 文件路径：确保后缀是 .xlsx
    root, ext = os.path.splitext(expanded)
    if ext.lower() != ".xlsx":
        expanded = expanded + ".xlsx"
        root, ext = os.path.splitext(expanded)

    base = os.path.basename(root)
    # 已带 _YYYYMMDD 或 _YYYYMMDD_HH.mm（或旧版重试用 _YYYYMMDD_HHmmss）：不再插入
    if _tagged.search(base):
        return os.path.abspath(expanded)

    # 未带上述后缀：在后缀前插入抓取时间标签
    return os.path.abspath(f"{root}_{capture_tag}{ext}")


# Safety net: 自动给本模块中所有 def 加异常兜底
from bank_safety import auto_wrap_module_functions as _auto_wrap_module_functions

_auto_wrap_module_functions(globals(), module_name=__name__)

