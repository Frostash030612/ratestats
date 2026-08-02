from __future__ import annotations

"""
可移植版本的 Citi 常量模块。

内容与主目录 `bank_constants.py` 保持一致，用于 portable 脚本独立运行时
不会依赖主目录结构。
"""

from typing import List

NA = "N/A"

SGD_BOARD_INTERNAL_COLS: List[str] = [
    "data_source",
    "product_line",
    "min_amount_text",
    "max_amount_text",
    "placement_range_text",
    "rate_1w_pct",
    "rate_2w_pct",
    "rate_1m_pct",
    "rate_2m_pct",
    "rate_3m_pct",
    "rate_4m_pct",
    "rate_5m_pct",
    "rate_6m_pct",
    "rate_7m_pct",
    "rate_8m_pct",
    "rate_9m_pct",
    "rate_10m_pct",
    "rate_11m_pct",
    "rate_12m_pct",
    "rate_18m_pct",
    "rate_24m_pct",
    "rate_36m_pct",
    "page_raw",
]

FX_BOARD_INTERNAL_COLS: List[str] = [
    "data_source",
    "currency",
    "product_line",
    "min_amount_text",
    "max_amount_text",
    "placement_range_text",
    "rate_1w_pct",
    "rate_2w_pct",
    "rate_1m_pct",
    "rate_2m_pct",
    "rate_3m_pct",
    "rate_6m_pct",
    "rate_9m_pct",
    "rate_12m_pct",
    "rate_18m_pct",
    "rate_24m_pct",
    "rate_36m_pct",
    "rate_48m_pct",
    "rate_60m_pct",
    "page_raw",
]

# MarketRateData 不输出这些外币挂牌分表（业务不需要）。
FX_BOARD_EXCLUDED_CURRENCIES = frozenset({"JPY", "CHF", "IDR", "THB"})

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

