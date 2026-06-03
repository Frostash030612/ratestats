"""
Fetch Citibank Singapore "all promotions" page and extract advertised interest rates.

The listing URL is stable; figures change when Citi updates the page HTML.

Optional: merge CIMB Singapore Foreign Currency FD online promotion (multi-tenor) for
USD/AUD/GBP; other currencies remain Citibank 1-month FX TD only.

Also optional: HSBC SG (Chinese UI), ICBC SG (SGD/USD/RMB FD promo page), OCBC SG (SGD TD promo),
RHB SG / SingFinance SG (SGD promo + FCY presence check), HL Bank, HLF, etc.

SGD board (挂牌) rates from selected banks (incl. HSBC / ICBC SG / Maybank / OCBC / RHB PDF)
are written to a separate Excel sheet from promos.

Maintenance markers (quick search):
- HOTSPOT_URL: URL constants / CLI URL args that are likely to change.
- HOTSPOT_DOM: DOM/PDF parsing rules likely to break when page structure changes.
Use: rg "HOTSPOT_(URL|DOM)" bank_all_promo_rates.py

---------------------------------------------------------------------------
中文说明 · 文件结构（便于维护）
---------------------------------------------------------------------------
1) 默认 URL / 常量（DEFAULT_*）
   各银行促销页、新元挂牌页、外币挂牌页、BEA API、BOC 挂牌等入口链接；站点改版时优先改这里。

2) 内部列名（SGD_BOARD_INTERNAL_COLS / FX_BOARD_INTERNAL_COLS）
   与 pandas 写出 Excel 前的列键一致；空行模板见 _empty_sgd_board_row / _empty_fx_board_row。

3)–6) 解析与合并逻辑见主目录 `bank_extractors.impl`（便携版通过 sys.path 引用主目录实现）。

7) write_rates_excel 与 _unique_excel_sheet_name 等
   生成 MarketRateData 多工作表 xlsx（元数据、促销、挂牌、外币挂牌按币种分表、样式）。

8) main / resolve_xlsx_out
   命令行参数解析、输出路径与日期后缀。

9) 其它利率 / 杂项
   页面脚注中的 Quick Cash、AIA 配套等见 extract_misc_rates。
---------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import html as html_module
import io
import json
import math
import os
import re
import sys
import shutil
import traceback
from copy import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from bank_output_stage import run_output_stage

# Excel 样式 helper（抽取自 write_rates_excel 的嵌套 def）
from bank_excel_style_helpers import (
    apply_bank_colors as _apply_bank_colors,
    center_align_rate_columns as _center_align_rate_columns,
    style_sgd_board_sheet as _style_sgd_board_sheet,
)

# 模板复制 + overlay 写入 + FX 多币种 sheet 创建（从 write_rates_excel 抽离）
from bank_excel_template_writer import (
    write_market_rate_excel_with_template as _write_market_rate_excel_with_template,
)

# DataFrame 准备器（可移植版）
from bank_excel_data_builder import (
    prepare_market_rate_excel_data as _prepare_market_rate_excel_data,
)

from url_sources import (
    DEFAULT_URL,
    DEFAULT_CIMB_FCY_URL,
    DEFAULT_CIMB_SGD_URL,
    DEFAULT_HL_FD_URL,
    DEFAULT_HLF_FD_URL,
    DEFAULT_HSBC_TD_URL,
    DEFAULT_ICBC_FD_URL,
    DEFAULT_OCBC_FD_URL,
    DEFAULT_RHB_FD_URL,
    DEFAULT_RHB_FCY_FD_URL,
    DEFAULT_SCB_SGD_TD_URL,
    DEFAULT_SCB_FCY_FD_URL,
    DEFAULT_SIF_FD_URL,
    DEFAULT_SBI_SGD_PROMO_URL,
    DEFAULT_SBI_USD_PROMO_URL,
    DEFAULT_UOB_SGD_TD_URL,
    DEFAULT_BOC_PROMO_URL,
    DEFAULT_CITI_SGD_BOARD_URL,
    DEFAULT_DBS_SGD_BOARD_URL,
    DEFAULT_HL_SGD_BOARD_URL,
    DEFAULT_HLF_SGD_BOARD_URL,
    DEFAULT_HSBC_SGD_BOARD_URL,
    DEFAULT_ICBC_SGD_BOARD_URL,
    DEFAULT_ICBC_FCY_BOARD_URL,
    DEFAULT_MAYBANK_SGD_BOARD_URL,
    DEFAULT_OCBC_SGD_BOARD_URL,
    DEFAULT_RHB_SGD_BOARD_PDF_URL,
    DEFAULT_SIF_SGD_BOARD_URL,
    DEFAULT_SCB_SGD_BOARD_URL,
    DEFAULT_SBI_SGD_BOARD_URL,
    DEFAULT_UOB_SGD_BOARD_URL,
    DEFAULT_HL_FCY_BOARD_URL,
    DEFAULT_HSBC_FCY_BOARD_URL,
    DEFAULT_MAYBANK_FCY_BOARD_URL,
    DEFAULT_SCB_FCY_BOARD_URL,
    DEFAULT_SBI_FCY_BOARD_URL,
    DEFAULT_OCBC_FCY_BOARD_URL,
    DEFAULT_UOB_FCY_BOARD_URL,
    DEFAULT_RHB_FCY_BOARD_PDF_URL,
    DEFAULT_BEA_SGD_BOARD_API_URL,
    DEFAULT_BEA_FCY_BOARD_API_URL,
    DEFAULT_BOC_BOARD_URL,
)

from url_config_loader import DEFAULT_URL_CONFIG

from bank_cli_url_config_applier import apply_url_config_to_cli_args
from bank_cli_fetch_params import build_fetch_and_extract_inputs
from bank_cli_parser import parse_cli_args

# 覆盖：优先使用 portable 目录内的模块版 fetch_and_extract。
# 如本地不存在，再回退到上级目录实现，保证兼容历史环境。
try:
    from bank_fetch_and_extract import fetch_and_extract as fetch_and_extract
except Exception:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from bank_fetch_and_extract import fetch_and_extract as fetch_and_extract


# ---------------------------------------------------------------------------
# Excel 输出：MarketRateData 多 sheet（元数据、促销、挂牌、外币挂牌按币种分表、行色与边框）
# ---------------------------------------------------------------------------


def write_rates_excel(data: Dict[str, Any], path: str) -> None:
    """Write extracted fields to a multi-sheet .xlsx (requires pandas + openpyxl).

    将 fetch_and_extract 返回的 payload 写成 MarketRateData：元数据、新元/外币促销、
    新元挂牌、外币挂牌（按币种多 sheet）、备注与其它利率等。
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)

    # 版本差异说明：
    # - 旧代码里也实现过一套 DataFrame 构建逻辑（很长，且已被主脚本抽离模块复用）。
    # - 为保证行为一致、且让 portable 也复用同一套“DataFrame 准备 + 模板写入”流程，
    #   这里直接调用抽离模块，然后立即 return，避免后续旧逻辑再次执行/覆盖。
    prepared = _prepare_market_rate_excel_data(data)
    df_meta = prepared["df_meta"]
    df_sgd = prepared["df_sgd"]
    df_sgd_board = prepared["df_sgd_board"]
    df_fx = prepared["df_fx"]
    df_fx_notes = prepared["df_fx_notes"]
    df_other = prepared["df_other"]
    df_fx_board = prepared["df_fx_board"]

    script_dir = os.path.dirname(os.path.abspath(__file__))
    _write_market_rate_excel_with_template(
        df_meta=df_meta,
        df_sgd=df_sgd,
        df_sgd_board=df_sgd_board,
        df_fx=df_fx,
        df_fx_notes=df_fx_notes,
        df_other=df_other,
        df_fx_board=df_fx_board,
        path=path,
        script_dir=script_dir,
    )
    return

    """
    Legacy write_rates_excel DataFrame 构建逻辑已被抽离模块替换。
    该段代码保留在此处仅用于对照/回溯，不再执行。

    cimb_url = (data.get("cimb_fcy_promo") or {}).get("source_url", "")
    cimb_sgd_url = (data.get("cimb_sgd_rates") or {}).get("source_url", "")
    cimb_sgd_err = (data.get("cimb_sgd_rates") or {}).get("error")
    hl_url = (data.get("hl_fd_promo") or {}).get("source_url", "")
    hl_err = (data.get("hl_fd_promo") or {}).get("error")
    hlf_url = (data.get("hlf_promo") or {}).get("source_url", "")
    hlf_err = (data.get("hlf_promo") or {}).get("error")
    hsbc_url = (data.get("hsbc_td_promo") or {}).get("source_url", "")
    hsbc_err = (data.get("hsbc_td_promo") or {}).get("error")
    icbc_url = (data.get("icbc_fd_promo") or {}).get("source_url", "")
    icbc_err = (data.get("icbc_fd_promo") or {}).get("error")
    ocbc_url = (data.get("ocbc_fd_promo") or {}).get("source_url", "")
    ocbc_err = (data.get("ocbc_fd_promo") or {}).get("error")
    rhb_url = (data.get("rhb_fd_promo") or {}).get("source_url", "")
    rhb_err = (data.get("rhb_fd_promo") or {}).get("error")
    rhb_fcy_url = (data.get("rhb_fcy_fd_promo") or {}).get("source_url", "")
    rhb_fcy_err = (data.get("rhb_fcy_fd_promo") or {}).get("error")
    sif_url = (data.get("sif_fd_promo") or {}).get("source_url", "")
    sif_err = (data.get("sif_fd_promo") or {}).get("error")
    uob_url = (data.get("uob_sgd_fd_promo") or {}).get("source_url", "")
    uob_err = (data.get("uob_sgd_fd_promo") or {}).get("error")
    uob_has_fcy = (data.get("uob_fcy_promo") or {}).get(
        "has_fcy_promo_table", None
    )
    scb_url = (data.get("scb_sgd_promo") or {}).get("source_url", "")
    scb_err = (data.get("scb_sgd_promo") or {}).get("error")
    scb_fcy_url = (data.get("scb_fcy_fd_promo") or {}).get("source_url", "")
    scb_fcy_err = (data.get("scb_fcy_fd_promo") or {}).get("error")
    sbi_url = (data.get("sbi_sgd_promo") or {}).get("source_url", "")
    sbi_err = (data.get("sbi_sgd_promo") or {}).get("error")
    sbi_fcy_url = (data.get("sbi_fcy_promo") or {}).get("source_url", "")
    sbi_fcy_err = (data.get("sbi_fcy_promo") or {}).get("error")
    boc_url = (data.get("boc_promo") or {}).get("source_url", "")
    boc_err = (data.get("boc_promo") or {}).get("error")
    citi_b = data.get("citi_sgd_board") or {}
    dbs_b = data.get("dbs_sgd_board") or {}
    hl_b = data.get("hl_sgd_board") or {}
    hlf_b = data.get("hlf_sgd_board") or {}
    hsbc_b = data.get("hsbc_sgd_board") or {}
    icbc_b = data.get("icbc_sgd_board") or {}
    may_b = data.get("maybank_sgd_board") or {}
    ocbc_b = data.get("ocbc_sgd_board") or {}
    rhb_pdf_b = data.get("rhb_sgd_board_pdf") or {}
    sif_b = data.get("sif_sgd_board") or {}
    scb_b = data.get("scb_sgd_board") or {}
    sbi_b = data.get("sbi_sgd_board") or {}
    uob_b = data.get("uob_sgd_board") or {}
    hl_fcy_b = data.get("hl_fcy_board") or {}
    hsbc_fcy_b = data.get("hsbc_fcy_board") or {}
    maybank_fcy_b = data.get("maybank_fcy_board") or {}
    scb_fcy_b = data.get("scb_fcy_board") or {}
    sbi_fcy_b = data.get("sbi_fcy_board") or {}
    rhb_fcy_b = data.get("rhb_fcy_board_pdf") or {}
    bea_sgd_b = data.get("bea_sgd_board") or {}
    bea_fcy_b = data.get("bea_fcy_board") or {}
    boc_sgd_b = data.get("boc_sgd_board") or {}
    boc_fcy_b = data.get("boc_fcy_board") or {}
    citi_b_err = citi_b.get("error")
    dbs_b_err = dbs_b.get("error")
    hl_b_err = hl_b.get("error")
    hlf_b_err = hlf_b.get("error")
    hsbc_b_err = hsbc_b.get("error")
    icbc_b_err = icbc_b.get("error")
    may_b_err = may_b.get("error")
    ocbc_b_err = ocbc_b.get("error")
    rhb_pdf_b_err = rhb_pdf_b.get("error")
    sif_b_err = sif_b.get("error")
    scb_b_err = scb_b.get("error")
    sbi_b_err = sbi_b.get("error")
    uob_b_err = uob_b.get("error")
    hl_fcy_b_err = hl_fcy_b.get("error")
    hsbc_fcy_b_err = hsbc_fcy_b.get("error")
    maybank_fcy_b_err = maybank_fcy_b.get("error")
    scb_fcy_b_err = scb_fcy_b.get("error")
    sbi_fcy_b_err = sbi_fcy_b.get("error")
    rhb_fcy_b_err = rhb_fcy_b.get("error")
    bea_sgd_b_err = bea_sgd_b.get("error")
    bea_fcy_b_err = bea_fcy_b.get("error")
    boc_sgd_b_err = boc_sgd_b.get("error")
    boc_fcy_b_err = boc_fcy_b.get("error")
    meta_rows = [
        {"项目": "抓取时间", "内容": data.get("fetched_at_utc", "")},
        {"项目": "Citibank 来源链接", "内容": data.get("source_url", "")},
        {"项目": "CIMB FCY 页面链接", "内容": cimb_url},
        {"项目": "CIMB 新元定存利率页", "内容": cimb_sgd_url},
        {
            "项目": "CIMB SGD 挂牌利率",
            "内容": "与「CIMB 新元定存利率页」同源（同页中的 Board 表）",
        },
        {"项目": "HL Bank 定存促销页", "内容": hl_url},
        {"项目": "HLF 新元促销页", "内容": hlf_url},
        {"项目": "汇丰新加坡 新币定期存款页", "内容": hsbc_url},
        {"项目": "工行新加坡 定存促销页", "内容": icbc_url},
        {"项目": "OCBC 新元定存促销页", "内容": ocbc_url},
        {"项目": "RHB 新元定存促销页", "内容": rhb_url},
        {"项目": "RHB 外币定存促销页", "内容": rhb_fcy_url},
        {"项目": "SingFinance 新元定存促销页", "内容": sif_url},
        {"项目": "UOB 新元定存促销页", "内容": uob_url},
        {"项目": "SCB 新元定存促销页", "内容": scb_url},
        {"项目": "SCB 外币定存促销页", "内容": scb_fcy_url},
        {"项目": "SBI 新元定存促销页", "内容": sbi_url},
        {"项目": "SBI 外币定存促销页", "内容": sbi_fcy_url},
        {"项目": "中国银行新加坡 定存促销页", "内容": boc_url},
        {"项目": "Citibank SGD 挂牌利率页", "内容": citi_b.get("source_url", "")},
        {"项目": "DBS SGD 挂牌利率页", "内容": dbs_b.get("source_url", "")},
        {"项目": "HL Bank SGD 挂牌利率页", "内容": hl_b.get("source_url", "")},
        {"项目": "HLF SGD 挂牌利率页", "内容": hlf_b.get("source_url", "")},
        {"项目": "汇丰 SGD 挂牌利率页", "内容": hsbc_b.get("source_url", "")},
        {"项目": "工行新加坡 SGD 挂牌利率页", "内容": icbc_b.get("source_url", "")},
        {"项目": "Maybank SGD 挂牌利率页", "内容": may_b.get("source_url", "")},
        {"项目": "OCBC SGD 挂牌利率页", "内容": ocbc_b.get("source_url", "")},
        {"项目": "RHB SGD 挂牌利率 PDF", "内容": rhb_pdf_b.get("source_url", "")},
        {"项目": "SingFinance SGD 挂牌利率页", "内容": sif_b.get("source_url", "")},
        {"项目": "SCB SGD 挂牌利率页", "内容": scb_b.get("source_url", "")},
        {"项目": "SBI SGD 挂牌利率页", "内容": sbi_b.get("source_url", "")},
        {"项目": "UOB SGD 挂牌利率页", "内容": uob_b.get("source_url", "")},
        {"项目": "HL Bank 外币挂牌利率页", "内容": hl_fcy_b.get("source_url", "")},
        {"项目": "HSBC 外币挂牌利率页", "内容": hsbc_fcy_b.get("source_url", "")},
        {"项目": "Maybank 外币挂牌利率页", "内容": maybank_fcy_b.get("source_url", "")},
        {"项目": "SCB 外币挂牌利率页", "内容": scb_fcy_b.get("source_url", "")},
        {"项目": "SBI 外币挂牌利率页", "内容": sbi_fcy_b.get("source_url", "")},
        {"项目": "RHB 外币挂牌利率 PDF", "内容": rhb_fcy_b.get("source_url", "")},
        {"项目": "BEA 新元挂牌利率 API", "内容": bea_sgd_b.get("source_url", "")},
        {"项目": "BEA 外币挂牌利率 API", "内容": bea_fcy_b.get("source_url", "")},
        {"项目": "BOC 新元挂牌利率页", "内容": boc_sgd_b.get("source_url", "")},
        {"项目": "BOC 外币挂牌利率页", "内容": boc_fcy_b.get("source_url", "")},
    ]
    if cimb_sgd_err:
        meta_rows.append({"项目": "CIMB 新元页面", "内容": f"抓取失败: {cimb_sgd_err}"})
    if hl_err:
        meta_rows.append({"项目": "HL Bank 页面", "内容": f"抓取失败: {hl_err}"})
    if hlf_err:
        meta_rows.append({"项目": "HLF 页面", "内容": f"抓取失败: {hlf_err}"})
    if hsbc_err:
        meta_rows.append({"项目": "汇丰新币定存页面", "内容": f"抓取失败: {hsbc_err}"})
    if icbc_err:
        meta_rows.append({"项目": "工行新加坡定存促销页面", "内容": f"抓取失败: {icbc_err}"})
    if ocbc_err:
        meta_rows.append({"项目": "OCBC 新元定存促销页面", "内容": f"抓取失败: {ocbc_err}"})
    if rhb_err:
        meta_rows.append({"项目": "RHB 新元定存促销页面", "内容": f"抓取失败: {rhb_err}"})
    if rhb_fcy_err:
        meta_rows.append({"项目": "RHB 外币定存促销页面", "内容": f"抓取失败: {rhb_fcy_err}"})
    if sif_err:
        meta_rows.append({"项目": "SingFinance 新元定存促销页面", "内容": f"抓取失败: {sif_err}"})
    if uob_err:
        meta_rows.append({"项目": "UOB 新元定存促销页面", "内容": f"抓取失败: {uob_err}"})
    if uob_has_fcy is not None:
        meta_rows.append(
            {
                "项目": "UOB 外币促销表检测结果",
                "内容": "已发现外币促销表" if uob_has_fcy else "未发现外币促销表",
            }
        )
    if scb_err:
        meta_rows.append({"项目": "SCB 新元定存促销页面", "内容": f"抓取失败: {scb_err}"})
    if scb_fcy_err:
        meta_rows.append({"项目": "SCB 外币定存促销页面", "内容": f"抓取失败: {scb_fcy_err}"})
    if sbi_err:
        meta_rows.append({"项目": "SBI 新元定存促销页面", "内容": f"抓取失败: {sbi_err}"})
    if sbi_fcy_err:
        meta_rows.append({"项目": "SBI 外币定存促销页面", "内容": f"抓取失败: {sbi_fcy_err}"})
    if boc_err:
        meta_rows.append({"项目": "中国银行新加坡定存促销页面", "内容": f"抓取失败: {boc_err}"})
    if citi_b_err:
        meta_rows.append(
            {"项目": "Citibank SGD 挂牌利率页面", "内容": f"抓取失败: {citi_b_err}"}
        )
    if dbs_b_err:
        meta_rows.append({"项目": "DBS SGD 挂牌利率页面", "内容": f"抓取失败: {dbs_b_err}"})
    if hl_b_err:
        meta_rows.append(
            {"项目": "HL Bank SGD 挂牌利率页面", "内容": f"抓取失败: {hl_b_err}"}
        )
    if hlf_b_err:
        meta_rows.append({"项目": "HLF SGD 挂牌利率页面", "内容": f"抓取失败: {hlf_b_err}"})
    if hsbc_b_err:
        meta_rows.append(
            {"项目": "汇丰 SGD 挂牌利率页面", "内容": f"抓取失败: {hsbc_b_err}"}
        )
    if icbc_b_err:
        meta_rows.append(
            {"项目": "工行新加坡 SGD 挂牌利率页面", "内容": f"抓取失败: {icbc_b_err}"}
        )
    if may_b_err:
        meta_rows.append(
            {"项目": "Maybank SGD 挂牌利率页面", "内容": f"抓取失败: {may_b_err}"}
        )
    if ocbc_b_err:
        meta_rows.append(
            {"项目": "OCBC SGD 挂牌利率页面", "内容": f"抓取失败: {ocbc_b_err}"}
        )
    if rhb_pdf_b_err:
        meta_rows.append(
            {"项目": "RHB SGD 挂牌利率 PDF", "内容": f"抓取失败: {rhb_pdf_b_err}"}
        )
    if sif_b_err:
        meta_rows.append(
            {"项目": "SingFinance SGD 挂牌利率页面", "内容": f"抓取失败: {sif_b_err}"}
        )
    if scb_b_err:
        meta_rows.append(
            {"项目": "SCB SGD 挂牌利率页面", "内容": f"抓取失败: {scb_b_err}"}
        )
    if sbi_b_err:
        meta_rows.append(
            {"项目": "SBI SGD 挂牌利率页面", "内容": f"抓取失败: {sbi_b_err}"}
        )
    if uob_b_err:
        meta_rows.append(
            {"项目": "UOB SGD 挂牌利率页面", "内容": f"抓取失败: {uob_b_err}"}
        )
    if hl_fcy_b_err:
        meta_rows.append(
            {"项目": "HL Bank 外币挂牌利率页面", "内容": f"抓取失败: {hl_fcy_b_err}"}
        )
    if hsbc_fcy_b_err:
        meta_rows.append(
            {"项目": "HSBC 外币挂牌利率页面", "内容": f"抓取失败: {hsbc_fcy_b_err}"}
        )
    if maybank_fcy_b_err:
        meta_rows.append(
            {"项目": "Maybank 外币挂牌利率页面", "内容": f"抓取失败: {maybank_fcy_b_err}"}
        )
    if scb_fcy_b_err:
        meta_rows.append(
            {"项目": "SCB 外币挂牌利率页面", "内容": f"抓取失败: {scb_fcy_b_err}"}
        )
    if sbi_fcy_b_err:
        meta_rows.append(
            {"项目": "SBI 外币挂牌利率页面", "内容": f"抓取失败: {sbi_fcy_b_err}"}
        )
    if rhb_fcy_b_err:
        meta_rows.append(
            {"项目": "RHB 外币挂牌利率 PDF", "内容": f"抓取失败: {rhb_fcy_b_err}"}
        )
    if bea_sgd_b_err:
        meta_rows.append(
            {"项目": "BEA 新元挂牌利率 API", "内容": f"抓取失败: {bea_sgd_b_err}"}
        )
    if bea_fcy_b_err:
        meta_rows.append(
            {"项目": "BEA 外币挂牌利率 API", "内容": f"抓取失败: {bea_fcy_b_err}"}
        )
    if boc_sgd_b_err:
        meta_rows.append(
            {"项目": "BOC 新元挂牌利率页面", "内容": f"抓取失败: {boc_sgd_b_err}"}
        )
    if boc_fcy_b_err:
        meta_rows.append(
            {"项目": "BOC 外币挂牌利率页面", "内容": f"抓取失败: {boc_fcy_b_err}"}
        )
    df_meta = pd.DataFrame(meta_rows)

    sgd_merged = data.get("sgd_merged") or []
    df_sgd = pd.DataFrame(sgd_merged)
    sgd_col_order = [
        "数据来源",
        "产品或客群",
        "起存金额_页面",
        "上限金额_页面",
        "资金区间_页面",
        "1M_pct",
        "3M_pct",
        "5M_pct",
        "6M_pct",
        "9M_pct",
        "12M_pct",
        "页面原文摘录",
    ]
    if not df_sgd.empty:
        df_sgd = df_sgd.rename(
            columns={
                "data_source": "数据来源",
                "product_line": "产品或客群",
                "min_amount_text": "起存金额_页面",
                "max_amount_text": "上限金额_页面",
                "placement_range_text": "资金区间_页面",
                "rate_1m_pct": "1M_pct",
                "rate_3m_pct": "3M_pct",
                "rate_5m_pct": "5M_pct",
                "rate_6m_pct": "6M_pct",
                "rate_9m_pct": "9M_pct",
                "rate_12m_pct": "12M_pct",
                "page_raw": "页面原文摘录",
            }
        )
        df_sgd = df_sgd[[c for c in sgd_col_order if c in df_sgd.columns]]
    else:
        df_sgd = pd.DataFrame(columns=sgd_col_order)

    fx = data.get("fx_time_deposit_1m") or {}
    merged = data.get("fx_merged") or []
    df_fx = pd.DataFrame(merged)
    fx_cols_order = [
        "币种",
        "1M_pct",
        "3M_pct",
        "6M_pct",
        "9M_pct",
        "12M_pct",
        "起存金额_页面",
        "上限金额_页面",
        "数据来源",
        "页面_1M原文",
    ]
    if not df_fx.empty:
        df_fx = df_fx.rename(
            columns={
                "currency": "币种",
                "rate_1m": "1M_pct",
                "rate_3m": "3M_pct",
                "rate_6m": "6M_pct",
                "rate_9m": "9M_pct",
                "rate_12m": "12M_pct",
                "min_deposit_text": "起存金额_页面",
                "max_deposit_text": "上限金额_页面",
                "page_text_1m": "页面_1M原文",
                "data_source": "数据来源",
            }
        )
        df_fx = df_fx[[c for c in fx_cols_order if c in df_fx.columns]]
    else:
        df_fx = pd.DataFrame(columns=fx_cols_order)

    notes = list(fx.get("notes") or [])
    cimb = data.get("cimb_fcy_promo") or {}
    if cimb.get("promotion_intro"):
        notes.insert(0, "[CIMB] " + str(cimb["promotion_intro"]))
    for n in cimb.get("notes") or []:
        if n and n not in notes:
            notes.append("[CIMB] " + n)
    if (cimb.get("error")):
        notes.append("[CIMB] 抓取失败: " + str(cimb["error"]))
    df_fx_notes = pd.DataFrame({"说明": notes} if notes else {"说明": []})

    other = data.get("other") or {}
    other_rows: List[Dict[str, Any]] = []
    qc = other.get("citi_quick_cash")
    if isinstance(qc, dict):
        other_rows.append(
            {
                "类别": "Citi Quick Cash",
                "指标": "宣传利率_p.a._pct",
                "数值": qc.get("advertised_rate_pa_percent"),
            }
        )
        other_rows.append(
            {
                "类别": "Citi Quick Cash",
                "指标": "EIR_p.a._pct",
                "数值": qc.get("eir_pa_percent"),
            }
        )
    aia = other.get("citi_aia_insurance_time_deposit")
    if isinstance(aia, dict):
        other_rows.append(
            {
                "类别": "Citi-AIA 保险配套（2个月定存宣传）",
                "指标": "最高年利率_p.a._pct",
                "数值": aia.get("max_promo_td_pa_percent"),
            }
        )
        other_rows.append(
            {
                "类别": "Citi-AIA 保险配套（2个月定存宣传）",
                "指标": "页面重复出现次数",
                "数值": aia.get("occurrences"),
            }
        )
    df_other = pd.DataFrame(other_rows)
    if df_other.empty:
        df_other = pd.DataFrame(columns=["类别", "指标", "数值"])

    sgd_board_merged = data.get("sgd_board_merged") or []
    df_sgd_board = pd.DataFrame(sgd_board_merged)
    sgd_board_rename = {
        "data_source": "数据来源",
        "product_line": "产品或档位",
        "min_amount_text": "起存金额_页面",
        "max_amount_text": "上限金额_页面",
        "placement_range_text": "资金区间_页面",
        "rate_1w_pct": "7D_pct",
        "rate_2w_pct": "14D_pct",
        "rate_1m_pct": "1M_pct",
        "rate_2m_pct": "2M_pct",
        "rate_3m_pct": "3M_pct",
        "rate_4m_pct": "4M_pct",
        "rate_5m_pct": "5M_pct",
        "rate_6m_pct": "6M_pct",
        "rate_7m_pct": "7M_pct",
        "rate_8m_pct": "8M_pct",
        "rate_9m_pct": "9M_pct",
        "rate_10m_pct": "10M_pct",
        "rate_11m_pct": "11M_pct",
        "rate_12m_pct": "12M_pct",
        "rate_18m_pct": "18M_pct",
        "rate_24m_pct": "24M_pct",
        "rate_36m_pct": "36M_pct",
        "page_raw": "页面原文摘录",
    }
    sgd_board_col_order = list(sgd_board_rename.values())
    if not df_sgd_board.empty:
        df_sgd_board = df_sgd_board.rename(columns=sgd_board_rename)
        df_sgd_board = df_sgd_board[
            [c for c in sgd_board_col_order if c in df_sgd_board.columns]
        ]
    else:
        df_sgd_board = pd.DataFrame(columns=sgd_board_col_order)

    fx_board_merged = data.get("fx_board_merged") or []
    df_fx_board = pd.DataFrame(fx_board_merged)
    fx_board_rename = {
        "data_source": "数据来源",
        "currency": "币种",
        "product_line": "产品或档位",
        "min_amount_text": "起存金额_页面",
        "max_amount_text": "上限金额_页面",
        "placement_range_text": "资金区间_页面",
        "rate_1w_pct": "7D_pct",
        "rate_2w_pct": "14D_pct",
        "rate_1m_pct": "1M_pct",
        "rate_2m_pct": "2M_pct",
        "rate_3m_pct": "3M_pct",
        "rate_6m_pct": "6M_pct",
        "rate_9m_pct": "9M_pct",
        "rate_12m_pct": "12M_pct",
        "rate_18m_pct": "18M_pct",
        "rate_24m_pct": "24M_pct",
        "rate_36m_pct": "36M_pct",
        "rate_48m_pct": "48M_pct",
        "rate_60m_pct": "60M_pct",
        "page_raw": "页面原文摘录",
    }
    fx_board_col_order = list(fx_board_rename.values())
    if not df_fx_board.empty:
        df_fx_board = df_fx_board.rename(columns=fx_board_rename)
        df_fx_board = df_fx_board[
            [c for c in fx_board_col_order if c in df_fx_board.columns]
        ]
    else:
        df_fx_board = pd.DataFrame(columns=fx_board_col_order)
    """

# ---------------------------------------------------------------------------
# 命令行入口：解析参数、调用 fetch_and_extract 与 write_rates_excel
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    "命令行入口：解析参数、抓取聚合数据并统一走输出阶段。"
    print("[STEP 1/5] 解析 CLI 参数...", file=sys.stderr)
    try:
        args = parse_cli_args(argv)
        print("[STEP 1/5] 完成", file=sys.stderr)
    except Exception as e:
        print(f"[STEP 1/5] 失败：{e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1

    print("[STEP 2/5] 应用 URL 配置覆盖...", file=sys.stderr)
    try:
        apply_url_config_to_cli_args(args)
        print("[STEP 2/5] 完成", file=sys.stderr)
    except Exception as e:
        print(f"[STEP 2/5] 失败：{e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1

    print("[STEP 3/5] 构建 fetch_and_extract 传参...", file=sys.stderr)
    try:
        fetch_url, fetch_timeout, use_env_proxy, fetch_kwargs = build_fetch_and_extract_inputs(args)
        print(
            f"[STEP 3/5] 完成: timeout={fetch_timeout}, "
            f"use_env_proxy={use_env_proxy}, kwargs_count={len(fetch_kwargs)}",
            file=sys.stderr,
        )
    except Exception as e:
        print(f"[STEP 3/5] 失败：{e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1

    print("[STEP 4/5] 执行抓取与提取...", file=sys.stderr)
    try:
        data = fetch_and_extract(
            fetch_url,
            fetch_timeout,
            use_env_proxy,
            **fetch_kwargs,
        )
        print("[STEP 4/5] 完成", file=sys.stderr)
    except requests.RequestException as e:
        print(f"[STEP 4/5] Request failed: {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[STEP 4/5] 失败：{e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1

    print("[STEP 5/5] 执行输出阶段...", file=sys.stderr)
    try:
        rc = run_output_stage(data=data, args=args, excel_writer=write_rates_excel)
        print(f"[STEP 5/5] 完成: rc={rc}", file=sys.stderr)
        return rc
    except Exception as e:
        print(f"[STEP 5/5] 失败：{e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1
    """
    # HOTSPOT_URL: CLI URL overrides (fastest way to switch changed source links).
    p.add_argument(
        "--url-config",
        default=DEFAULT_URL_CONFIG,
        help="URL 参数配置文件（推荐 xlsx；只覆盖脚本内默认值；命令行显式传参仍优先）。",
    )
    p.add_argument("--url", default=DEFAULT_URL, help="Page URL (default: stable all-promo link).")
    p.add_argument(
        "--cimb-url",
        default=DEFAULT_CIMB_FCY_URL,
        help="CIMB Foreign Currency FD page (multi-tenor promo for USD/AUD/GBP).",
    )
    p.add_argument(
        "--no-cimb",
        action="store_true",
        help="Do not fetch CIMB FCY page; foreign-currency sheet uses Citibank 1M only (other tenors N/A).",
    )
    p.add_argument(
        "--cimb-sgd-url",
        default=DEFAULT_CIMB_SGD_URL,
        help="CIMB SGD fixed deposit rates page.",
    )
    p.add_argument(
        "--no-cimb-sgd",
        action="store_true",
        help="Do not fetch CIMB SGD rates; 新元定存促销 sheet is Citibank-only.",
    )
    p.add_argument(
        "--hl-url",
        default=DEFAULT_HL_FD_URL,
        help="HL Bank fixed deposit promotion page (SGD + USD/AUD branch rates).",
    )
    p.add_argument(
        "--no-hl",
        action="store_true",
        help="Do not fetch HL Bank page.",
    )
    p.add_argument(
        "--hlf-url",
        default=DEFAULT_HLF_FD_URL,
        help="Hong Leong Finance (HLF) SGD fixed deposit promotion page.",
    )
    p.add_argument(
        "--no-hlf",
        action="store_true",
        help="Do not fetch HLF (Hong Leong Finance) promo page.",
    )
    p.add_argument(
        "--hsbc-url",
        default=DEFAULT_HSBC_TD_URL,
        help="HSBC Singapore SGD time deposit page (Chinese UI; default HSBC SG TD URL).",
    )
    p.add_argument(
        "--no-hsbc",
        action="store_true",
        help="Do not fetch HSBC Singapore SGD time deposit page.",
    )
    p.add_argument(
        "--icbc-url",
        default=DEFAULT_ICBC_FD_URL,
        help="ICBC Singapore fixed deposit promotion page (SGD/USD/RMB).",
    )
    p.add_argument(
        "--no-icbc",
        action="store_true",
        help="Do not fetch ICBC Singapore FD promotion page.",
    )
    p.add_argument(
        "--ocbc-url",
        default=DEFAULT_OCBC_FD_URL,
        help="OCBC Singapore SGD time deposit (fixed deposit) promotional page.",
    )
    p.add_argument(
        "--no-ocbc",
        action="store_true",
        help="Do not fetch OCBC Singapore SGD time deposit promotion page.",
    )
    p.add_argument(
        "--rhb-url",
        default=DEFAULT_RHB_FD_URL,
        help="RHB Singapore fixed deposit campaign page.",
    )
    p.add_argument(
        "--no-rhb",
        action="store_true",
        help="Do not fetch RHB Singapore fixed deposit campaign page.",
    )
    p.add_argument(
        "--rhb-fcy-url",
        default=DEFAULT_RHB_FCY_FD_URL,
        help="RHB Singapore foreign currency fixed deposit campaign page.",
    )
    p.add_argument(
        "--no-rhb-fcy",
        action="store_true",
        help="Do not fetch RHB Singapore FCY fixed deposit campaign page.",
    )
    p.add_argument(
        "--sif-url",
        default=DEFAULT_SIF_FD_URL,
        help="SingFinance FD Online promotional page.",
    )
    p.add_argument(
        "--no-sif",
        action="store_true",
        help="Do not fetch SingFinance FD Online promotional page.",
    )
    p.add_argument(
        "--scb-url",
        default=DEFAULT_SCB_SGD_TD_URL,
        help="Standard Chartered Singapore Dollar Time Deposit promo page.",
    )
    p.add_argument(
        "--no-scb",
        action="store_true",
        help="Do not fetch Standard Chartered SGD time deposit promo page.",
    )
    p.add_argument(
        "--scb-fcy-url",
        default=DEFAULT_SCB_FCY_FD_URL,
        help="Standard Chartered foreign currency time deposit promo page.",
    )
    p.add_argument(
        "--no-scb-fcy",
        action="store_true",
        help="Do not fetch Standard Chartered foreign currency time deposit promo page.",
    )
    p.add_argument(
        "--sbi-url",
        default=DEFAULT_SBI_SGD_PROMO_URL,
        help="SBI Singapore SGD promotions page.",
    )
    p.add_argument(
        "--no-sbi",
        action="store_true",
        help="Do not fetch SBI Singapore SGD promotions page.",
    )
    p.add_argument(
        "--sbi-usd-url",
        default=DEFAULT_SBI_USD_PROMO_URL,
        help="SBI Singapore USD promotions page.",
    )
    p.add_argument(
        "--no-sbi-usd",
        action="store_true",
        help="Do not fetch SBI Singapore USD promotions page.",
    )
    p.add_argument(
        "--uob-url",
        default=DEFAULT_UOB_SGD_TD_URL,
        help="UOB Singapore Dollar Time/Fixed Deposit promotional page.",
    )
    p.add_argument(
        "--no-uob",
        action="store_true",
        help="Do not fetch UOB Singapore Dollar Time/Fixed Deposit promotions page.",
    )
    p.add_argument(
        "--boc-url",
        default=DEFAULT_BOC_PROMO_URL,
        help="BOC Singapore personal fixed deposit promotions page (SGD + FCY).",
    )
    p.add_argument(
        "--no-boc",
        action="store_true",
        help="Do not fetch BOC Singapore fixed deposit promotions page.",
    )
    p.add_argument(
        "--no-sgd-board",
        action="store_true",
        help="Do not fetch SGD board-rate pages; 新元挂牌利率 sheet will be empty.",
    )
    p.add_argument(
        "--citi-board-url",
        default=DEFAULT_CITI_SGD_BOARD_URL,
        help="Citibank Singapore SGD time deposit board rates page.",
    )
    p.add_argument(
        "--dbs-board-url",
        default=DEFAULT_DBS_SGD_BOARD_URL,
        help="DBS Singapore SGD fixed deposit board rates page.",
    )
    p.add_argument(
        "--hl-board-url",
        default=DEFAULT_HL_SGD_BOARD_URL,
        help="HL Bank Singapore fixed deposit board rates page.",
    )
    p.add_argument(
        "--hlf-board-url",
        default=DEFAULT_HLF_SGD_BOARD_URL,
        help="HLF Singapore fixed deposit board rates page.",
    )
    p.add_argument(
        "--hsbc-board-url",
        default=DEFAULT_HSBC_SGD_BOARD_URL,
        help="HSBC Singapore SGD deposit rates (board / published TD rates).",
    )
    p.add_argument(
        "--icbc-board-url",
        default=DEFAULT_ICBC_SGD_BOARD_URL,
        help="ICBC Singapore page containing SGD FD board rate table.",
    )
    p.add_argument(
        "--icbc-fcy-board-url",
        default=DEFAULT_ICBC_FCY_BOARD_URL,
        help="ICBC Singapore page with USD/RMB etc. FD board tables (default: same as SGD board page).",
    )
    p.add_argument(
        "--maybank-board-url",
        default=DEFAULT_MAYBANK_SGD_BOARD_URL,
        help="Maybank Singapore deposit rates (SGD TD board).",
    )
    p.add_argument(
        "--ocbc-board-url",
        default=DEFAULT_OCBC_SGD_BOARD_URL,
        help="OCBC Singapore SGD time deposit board rates page.",
    )
    p.add_argument(
        "--rhb-board-pdf-url",
        default=DEFAULT_RHB_SGD_BOARD_PDF_URL,
        help="RHB Singapore deposit rates PDF (SGD FD grid).",
    )
    p.add_argument(
        "--sif-board-url",
        default=DEFAULT_SIF_SGD_BOARD_URL,
        help="SingFinance rates page containing SGD FD board rates.",
    )
    p.add_argument(
        "--scb-board-url",
        default=DEFAULT_SCB_SGD_BOARD_URL,
        help="Standard Chartered SGD TD interest rates FAQ page.",
    )
    p.add_argument(
        "--sbi-board-url",
        default=DEFAULT_SBI_SGD_BOARD_URL,
        help="SBI Singapore interest rates page (SGD term deposit board).",
    )
    p.add_argument(
        "--uob-board-url",
        default=DEFAULT_UOB_SGD_BOARD_URL,
        help="UOB online rates page containing SGD TD board rates.",
    )
    p.add_argument(
        "--ocbc-fcy-board-url",
        default=DEFAULT_OCBC_FCY_BOARD_URL,
        help="OCBC foreign-currency TD daily rates HTML page (static tables; default daily_price_fd.html).",
    )
    p.add_argument(
        "--uob-fcy-board-url",
        default=DEFAULT_UOB_FCY_BOARD_URL,
        help="UOB Group FCY fixed deposit rates page (script uses data-api JSON with this Referer).",
    )
    p.add_argument(
        "--hl-fcy-board-url",
        default=DEFAULT_HL_FCY_BOARD_URL,
        help="HL Bank foreign-currency fixed deposit board rates page.",
    )
    p.add_argument(
        "--hsbc-fcy-board-url",
        default=DEFAULT_HSBC_FCY_BOARD_URL,
        help="HSBC foreign-currency time deposit rates page.",
    )
    p.add_argument(
        "--maybank-fcy-board-url",
        default=DEFAULT_MAYBANK_FCY_BOARD_URL,
        help="Maybank foreign-currency time deposit board rates page.",
    )
    p.add_argument(
        "--scb-fcy-board-url",
        default=DEFAULT_SCB_FCY_BOARD_URL,
        help="Standard Chartered foreign-currency interest rates page.",
    )
    p.add_argument(
        "--sbi-fcy-board-url",
        default=DEFAULT_SBI_FCY_BOARD_URL,
        help="SBI interest rates page (foreign-currency board section).",
    )
    p.add_argument(
        "--rhb-fcy-board-pdf-url",
        default=DEFAULT_RHB_FCY_BOARD_PDF_URL,
        help="RHB deposit rates PDF (foreign-currency board section).",
    )
    p.add_argument(
        "--bea-sgd-board-api-url",
        default=DEFAULT_BEA_SGD_BOARD_API_URL,
        help="BEA SGD board rates API endpoint.",
    )
    p.add_argument(
        "--bea-fcy-board-api-url",
        default=DEFAULT_BEA_FCY_BOARD_API_URL,
        help="BEA FCY board rates API endpoint.",
    )
    p.add_argument(
        "--boc-board-url",
        default=DEFAULT_BOC_BOARD_URL,
        help="BOC board rates page (contains both SGD and FCY board rates).",
    )
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument(
        "--use-env-proxy",
        action="store_true",
        help="Honor HTTP(S)_PROXY from environment (default: off, same idea as rate_crawler).",
    )
    p.add_argument("--json-out", help="Write JSON to this file (UTF-8).")
    p.add_argument(
        "--xlsx-out",
        nargs="?",
        const=".",
        default=None,
        metavar="FILE_OR_DIR",
        help=(
            "Write Excel (.xlsx). Omit the path to write MarketRateData_YYYYMMDD_HH.mm.xlsx in the "
            "current directory. If FILE_OR_DIR is a directory, write that file inside it. "
            "If a .xlsx path is given, insert _YYYYMMDD_HH.mm before .xlsx (unless already date/time tagged)."
        ),
    )
    p.add_argument(
        "--print-json",
        action="store_true",
        help="Also print JSON to stdout when using --xlsx-out.",
    )
    p.add_argument("--pretty", action="store_true", help="Indent JSON output.")
    args = p.parse_args(argv)

    # Apply URL config as *default override* (CLI explicit values keep precedence).
    apply_url_config_to_cli_args(args)

    try:
        fetch_url, fetch_timeout, use_env_proxy, fetch_kwargs = (
            build_fetch_and_extract_inputs(args)
        )
        data = fetch_and_extract(
            fetch_url,
            fetch_timeout,
            use_env_proxy,
            **fetch_kwargs,
        )
    except requests.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return 1

    return run_output_stage(data=data, args=args, excel_writer=write_rates_excel)


    """

# Safety net：自动给本模块中所有 def 加异常兜底。
from bank_safety import auto_wrap_module_functions as _auto_wrap_module_functions

_auto_wrap_module_functions(globals(), module_name=__name__)

# 再次覆盖：把已导入到运行时的项目模块也做顶层函数兜底包裹。
from bank_safety import auto_wrap_loaded_modules_functions as _auto_wrap_loaded_modules_functions

_auto_wrap_loaded_modules_functions()


if __name__ == "__main__":
    raise SystemExit(main())
