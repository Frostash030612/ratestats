from __future__ import annotations

"""
与 Citi 抓取/写入相关的“固定常量”集中管理模块。

这些常量不涉及网络、解析、IO，也不会依赖主脚本的运行流程，
因此适合被抽成独立模块，降低主脚本阅读负担，并避免 portable 与非 portable
版本维护出现偏差。
"""

from typing import List

# 统一的缺失值标记（写入 Excel / JSON 时使用）。
NA = "N/A"

# Internal keys for sgd_board_merged (written to sheet 新元挂牌利率).
# 写入「新元挂牌利率」sheet 前的列名；与 _empty_sgd_board_row 一一对应。
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

# 写入「外币挂牌」各币种 sheet 前的列名；与 _empty_fx_board_row 一一对应。
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

# 用于 HTTP 请求的固定 User-Agent。
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

