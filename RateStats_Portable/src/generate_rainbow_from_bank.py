#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于 MarketRateData 输出表，按“彩虹表 20260311.xlsx”样式输出新彩虹表。

说明：
1) 样式来自模板（不会把模板中的旧数据当来源）
2) 数据来源来自 source Excel（默认最新 MarketRateData_*.xlsx）
3) 当前更新的模板 sheet：
   - SGD Promotional Rate
   - SGD Board Rate
   - SGD Board Rate Ranked
   - Sheet3（SGD board 矩阵）
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import math
import os
import re
import shutil
from typing import Any, Dict, List, Optional

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import PatternFill


RATE_THRESHOLDS = [
    ("red", 0.0140),
    ("orange", 0.0130),
    ("yellow", 0.0120),
    ("green", 0.0110),
    ("blue", 0.0080),
]

FILL_BY_NAME = {
    # Lighter pastel palette for rainbow table.
    "red": PatternFill("solid", fgColor="FFF4CCCC"),
    "orange": PatternFill("solid", fgColor="FFFCE5CD"),
    "yellow": PatternFill("solid", fgColor="FFFFF2CC"),
    "green": PatternFill("solid", fgColor="FFD9EAD3"),
    "blue": PatternFill("solid", fgColor="FFD0E0E3"),
    "purple": PatternFill("solid", fgColor="FFD9D2E9"),
}

TENORS_PROMO = ["1M", "3M", "5M", "6M", "9M", "12M", "18M", "24M"]
TENORS_BOARD = ["7D", "1M", "2M", "3M", "4M", "5M", "6M", "7M", "8M", "9M", "10M", "11M", "12M", "18M", "24M", "36M"]

_BANK_ALIASES = {
    "BOC SG": "BOC",
    "BOC": "BOC",
    "SBI SG": "SBI",
    "SBI": "SBI",
    "HL BANK": "HLB",
    "HLB": "HLB",
    "SINGFINANCE SG": "SINGFINANCE",
    "SINGFINANCE": "SINGFINANCE",
    "SING FINANCE": "SINGFINANCE",
    "ICBC SG": "ICBC",
    "ICBC": "ICBC",
    "HSBC SG": "HSBC",
    "HSBC": "HSBC",
    "OCBC SG": "OCBC",
    "OCBC": "OCBC",
    "MAYBANK SG": "MAYBANK",
    "MAYBANK": "MAYBANK",
    "RHB SG": "RHB",
    "RHB": "RHB",
    "SCB SG": "SCB",
    "SCB": "SCB",
    "CITIBANK": "CITI",
    "CITI": "CITI",
    "DBS/POSB": "DBS",
    "DBS": "DBS",
    "POSB": "DBS",
    "UOB": "UOB",
    "CIMB": "CIMB",
    "BEA": "BEA",
    "HLF": "HLF",
}


def normalize_text(s: Any) -> str:
    "统一清洗文本，便于做银行名与金额区间匹配。"
    t = str(s or "").strip().lower()
    t = t.replace(" ", "").replace("\u3000", "").replace(",", "")
    return t


def extract_number_tokens(s: Any) -> set[str]:
    "从金额文本中提取数字 token（支持 k/m/mil）。"
    txt = str(s or "")
    out: set[str] = set()
    for m in re.finditer(r"\d+(?:,\d+)*(?:\s*(?:k|m|mil))?", txt, flags=re.I):
        tok = m.group(0).lower().replace(",", "").strip().replace("mil", "m")
        if tok.endswith("k") and tok[:-1].isdigit():
            out.add(str(int(tok[:-1]) * 1000))
            continue
        if tok.endswith("m") and tok[:-1].isdigit():
            out.add(str(int(tok[:-1]) * 1000000))
            continue
        if tok.isdigit():
            out.add(tok)
    return out


def score_amount_match(template_amount: Any, source_amount: Any) -> int:
    "为模板金额与来源金额打分，选择最匹配记录。"
    t = str(template_amount or "")
    s = str(source_amount or "")
    if not t.strip() or not s.strip():
        return 0
    t_norm = normalize_text(t)
    s_norm = normalize_text(s)
    if t_norm == s_norm:
        return 40
    score = 0
    t_tokens = extract_number_tokens(t)
    s_tokens = extract_number_tokens(s)
    inter = t_tokens & s_tokens
    if inter:
        score += 10 * len(inter)
    # Directional cue matching: < / <= / up to / below / 以下  vs  > / >= / above / 及以上
    t_low = any(k in t_norm for k in ["<", "<=", "≤", "＜", "upto", "below", "lessthan", "以下"])
    t_high = any(k in t_norm for k in [">", ">=", "≥", "＞", "above", "atleast", "andabove", "及以上"])
    s_low = any(k in s_norm for k in ["<", "<=", "≤", "＜", "upto", "below", "lessthan", "以下"])
    s_high = any(k in s_norm for k in [">", ">=", "≥", "＞", "above", "atleast", "andabove", "及以上"])
    if t_low and s_low:
        score += 12
    if t_high and s_high:
        score += 12
    # Range-like cue
    t_range = any(k in t_norm for k in ["-", "to", "至"])
    s_range = any(k in s_norm for k in ["-", "to", "至"])
    if t_range and s_range:
        score += 6
    return score


def rate_to_color(rate_decimal: float) -> str:
    "按利率阈值返回彩虹色名称。"
    for name, thr in RATE_THRESHOLDS:
        if rate_decimal >= thr:
            return name
    return "purple"


def pct_to_decimal(v: Any) -> Optional[float]:
    "把百分比值安全转换为小数利率。"
    if v is None:
        return None
    if isinstance(v, str) and not v.strip():
        return None
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(fv):
        return None
    return fv / 100.0


def maybe_parse_decimal(v: Any) -> Optional[float]:
    "宽松解析数值文本为小数，失败返回 None。"
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def canonical_bank_name(s: Any) -> str:
    "归一化银行名称，兼容中英文别名与 SG 后缀。"
    raw = str(s or "").strip()
    up = re.sub(r"\s+", " ", raw).upper()
    up = re.sub(r"\s+SG$", "", up).strip()
    if up in _BANK_ALIASES:
        return _BANK_ALIASES[up]
    for k, v in _BANK_ALIASES.items():
        if up == k or up.startswith(k + " ") or k.startswith(up):
            return v
    return up


def banks_match(template_bank: Any, source_bank: Any) -> bool:
    "判断模板银行名与来源银行名是否同一机构。"
    return canonical_bank_name(template_bank) == canonical_bank_name(source_bank)


def get_effective_cell_value(ws, row: int, col: int) -> Any:
    "读取合并单元格中的有效值（向上追溯）。"
    v = ws.cell(row, col).value
    if v is not None:
        return v
    for rng in ws.merged_cells.ranges:
        min_col, min_row, max_col, max_row = rng.bounds
        if min_col <= col <= max_col and min_row <= row <= max_row:
            return ws.cell(min_row, min_col).value
    return None


def detect_template_sgd_promo_tenors(ws) -> Dict[str, int]:
    "识别 SGD Promotional Rate 表头中的期数字段（支持 Before/After 两段表头）。"
    out: Dict[str, int] = {}
    allowed = set(TENORS_PROMO)
    for header_row in (4, 41):
        if header_row > ws.max_row:
            continue
        for c in range(1, ws.max_column + 1):
            v = ws.cell(header_row, c).value
            if isinstance(v, str):
                t = v.strip()
                if t in allowed and t not in out:
                    out[t] = c
    return out


def ensure_promo_tenor_columns(ws) -> None:
    "在促销表 Before/After 表头行补齐 18M / 24M 列组（若模板尚无）。"
    extra = [t for t in ("18M", "24M") if t not in detect_template_sgd_promo_tenors(ws)]
    if not extra:
        return
    for header_row in (4, 41):
        if header_row > ws.max_row:
            continue
        last_tenor_col = 2
        for c in range(1, ws.max_column + 1):
            v = ws.cell(header_row, c).value
            if isinstance(v, str) and v.strip() in TENORS_PROMO:
                last_tenor_col = max(last_tenor_col, c)
        next_col = last_tenor_col + 3
        for tenor in extra:
            ws.cell(header_row, next_col).value = tenor
            ws.cell(header_row, next_col + 1).value = "Promo Rate"
            ws.cell(header_row, next_col + 2).value = "Condition"
            next_col += 3


def detect_template_sgd_board_tenor_blocks(ws, header_row: int) -> Dict[str, tuple[int, int, int]]:
    "识别 SGD Board 表中的利率列分组信息。"
    out: Dict[str, tuple[int, int, int]] = {}
    for c in range(1, ws.max_column + 1):
        v = ws.cell(header_row, c).value
        if isinstance(v, str) and v.strip() in {"7D", "1M", "3M", "6M", "9M", "12M", "18M", "24M", "36M"}:
            out[v.strip()] = (c, c + 1, c + 2)  # bank/rate/amount
    return out


def apply_colors_to_rate_columns(ws, rate_cols: List[int]) -> None:
    "根据利率区间给目标列批量着色。"
    for r in range(1, ws.max_row + 1):
        for c in rate_cols:
            v = ws.cell(r, c).value
            if isinstance(v, (int, float)):
                ws.cell(r, c).fill = FILL_BY_NAME[rate_to_color(float(v))]


def pick_best_promo_row(
    df_bank: pd.DataFrame,
    template_cond: Any,
    tenor: Optional[str] = None,
) -> Optional[pd.Series]:
    "在促销数据中挑选与模板行最匹配的一条记录（可按期限过滤）。"
    if df_bank.empty:
        return None
    col = f"{tenor}_pct" if tenor else None
    cond_text = str(template_cond or "")
    cond_norm = normalize_text(cond_text)
    cond_tokens = extract_number_tokens(cond_text)
    best_idx = None
    best_score = -1
    for i, row in df_bank.iterrows():
        if col and col in df_bank.columns:
            if pct_to_decimal(row.get(col)) is None:
                continue
        s = " ".join(
            str(row.get(k, "") or "")
            for k in ("产品或客群", "资金区间_页面", "起存金额_页面", "上限金额_页面")
        )
        n = normalize_text(s)
        score = 0
        if cond_norm and cond_norm in n:
            score += 10
        score += score_amount_match(template_cond, s)
        score += 5 * len(cond_tokens & extract_number_tokens(s))
        # ICBC 等分档：$200K / 20K 条件优先匹配高档位行
        if "ICBC" in canonical_bank_name(row.get("数据来源", "")):
            if any(k in cond_norm for k in ["200k", "20k", "200000"]):
                if "20k" in n:
                    score += 25
            if any(k in cond_norm for k in ["500", "200k"]) and "500" in cond_norm:
                if "500" in n and "20k" not in n:
                    score += 15
        if score > best_score:
            best_score = score
            best_idx = i
    if best_idx is None and col and col in df_bank.columns:
        ranked = df_bank.copy()
        ranked["_dec"] = ranked[col].apply(pct_to_decimal)
        ranked = ranked.dropna(subset=["_dec"]).sort_values("_dec", ascending=False)
        if not ranked.empty:
            return ranked.iloc[0]
        return None
    if best_idx is None:
        return None
    return df_bank.loc[best_idx]


def _is_text_rate_cell(v: Any) -> bool:
    return isinstance(v, str) and "%" in v


def _promo_section_ranges(ws) -> List[tuple[str, int, int]]:
    "返回促销表 Before/After 各段的数据行范围 (name, start_row, end_row)。"
    markers: List[tuple[int, str]] = []
    for r in range(1, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if v in ("Before", "After"):
            markers.append((r, str(v)))
    if not markers:
        return [("All", 5, ws.max_row)]
    out: List[tuple[str, int, int]] = []
    for i, (start_row, name) in enumerate(markers):
        data_start = start_row + 3
        data_end = markers[i + 1][0] - 1 if i + 1 < len(markers) else ws.max_row
        out.append((name, data_start, data_end))
    return out


def _iter_promo_stacks(ws, bank_col: int, data_start: int, data_end: int):
    "按列遍历银行堆叠行（同列连续多行属于同一银行变体）。"
    r = data_start
    while r <= data_end:
        bank = ws.cell(r, bank_col).value
        if isinstance(bank, str) and bank.strip():
            stack = [r]
            r2 = r + 1
            while r2 <= data_end:
                nb = ws.cell(r2, bank_col).value
                if isinstance(nb, str) and nb.strip():
                    break
                stack.append(r2)
                r2 += 1
            yield bank.strip(), stack
            r = r2
        else:
            r += 1


def _filter_promo_bank(df_promo: pd.DataFrame, template_bank: str) -> pd.DataFrame:
    cb = canonical_bank_name(template_bank)
    return df_promo[df_promo["_bank_canon"].apply(lambda x: canonical_bank_name(x) == cb)]


def _promo_row_text(row: pd.Series) -> str:
    return " ".join(
        str(row.get(k, "") or "")
        for k in ("产品或客群", "资金区间_页面", "起存金额_页面", "上限金额_页面")
    )


def _distinct_promo_offers_for_tenor(
    bank_df: pd.DataFrame,
    tenor: str,
) -> List[tuple[float, pd.Series]]:
    "按期限提取不重复的市场报价（同利率只保留一条，按利率降序）。"
    src_col = f"{tenor}_pct"
    if src_col not in bank_df.columns:
        return []
    seen: set[float] = set()
    offers: List[tuple[float, pd.Series]] = []
    for _, row in bank_df.iterrows():
        dec = pct_to_decimal(row.get(src_col))
        if dec is None:
            continue
        key = round(float(dec), 8)
        if key in seen:
            continue
        seen.add(key)
        offers.append((float(dec), row))
    offers.sort(key=lambda x: -x[0])
    return offers


def _writable_cell(ws, row: int, col: int):
    "返回可写入的单元格（合并区域内跳过非左上角）。"
    cell = ws.cell(row, col)
    if type(cell).__name__ == "MergedCell":
        for rng in ws.merged_cells.ranges:
            min_col, min_row, max_col, max_row = rng.bounds
            if min_col <= col <= max_col and min_row <= row <= max_row:
                if row != min_row or col != min_col:
                    return None
                return ws.cell(min_row, min_col)
        return None
    return cell


def _write_promo_rate_cell(ws, row: int, col: int, dec: float) -> None:
    cell = _writable_cell(ws, row, col)
    if cell is None:
        return
    cell.value = float(dec)
    cell.number_format = "0.00%"


def _clear_promo_rate_cell(ws, row: int, col: int) -> None:
    cell = _writable_cell(ws, row, col)
    if cell is not None:
        cell.value = None


def _fill_promo_stack(
    ws,
    stack_rows: List[int],
    rate_col: int,
    cond_col: int,
    tenor: str,
    df_promo: pd.DataFrame,
    bank_name: str,
) -> None:
    bank_df = _filter_promo_bank(df_promo, bank_name)
    offers = _distinct_promo_offers_for_tenor(bank_df, tenor)
    editable = [r for r in stack_rows if not _is_text_rate_cell(ws.cell(r, rate_col).value)]
    if not offers:
        for r in editable:
            _clear_promo_rate_cell(ws, r, rate_col)
        return

    used_indices: set[int] = set()
    used_rates: set[float] = set()

    for r in editable:
        cond = ws.cell(r, cond_col).value
        pick_i: Optional[int] = None
        best_score = -1
        if cond:
            for i, (dec, mrow) in enumerate(offers):
                if i in used_indices:
                    continue
                sc = score_amount_match(cond, _promo_row_text(mrow))
                if normalize_text(str(cond)) in normalize_text(_promo_row_text(mrow)):
                    sc += 10
                if sc > best_score:
                    best_score = sc
                    pick_i = i
        if pick_i is None or best_score <= 0:
            for i, (dec, mrow) in enumerate(offers):
                if i in used_indices:
                    continue
                if round(dec, 8) in used_rates:
                    continue
                pick_i = i
                break
        if pick_i is None:
            _clear_promo_rate_cell(ws, r, rate_col)
            continue
        dec, mrow = offers[pick_i]
        rate_key = round(dec, 8)
        if rate_key in used_rates:
            _clear_promo_rate_cell(ws, r, rate_col)
            continue
        used_indices.add(pick_i)
        used_rates.add(rate_key)
        _write_promo_rate_cell(ws, r, rate_col, dec)


def find_best_board_row(df_board: pd.DataFrame, bank_name: str, template_amount: Any) -> Optional[pd.Series]:
    "在挂牌数据中按银行+金额区间寻找最佳匹配行。"
    cbank = canonical_bank_name(bank_name)
    d = df_board[df_board["_bank_canon"].apply(lambda x: canonical_bank_name(x) == cbank)]
    if d.empty:
        return None
    best_idx = None
    best_score = -1
    for i, row in d.iterrows():
        s = " ".join(
            str(row.get(k, "") or "")
            for k in ("资金区间_页面", "起存金额_页面", "上限金额_页面", "产品或档位")
        )
        sc = score_amount_match(template_amount, s)
        if sc > best_score:
            best_score = sc
            best_idx = i
    if best_idx is None:
        return None
    return d.loc[best_idx]


def _is_amount_like(v: Any) -> bool:
    "判断文本是否像“金额/资金区间”描述。"
    if v is None:
        return False
    if isinstance(v, (int, float)):
        # pure numeric values are usually rates, not amount text
        return False
    s = str(v).strip()
    if not s:
        return False
    s_norm = normalize_text(s)
    keys = ["$", "sgd", "usd", "<", ">", "≤", "≥", "＜", "＞", "-", "to", "至", "以下", "及以上", "k", "m", "mil"]
    return any(k in s_norm for k in keys)


def resolve_rate_amount_cols(ws, r: int, rate_col_guess: int, amount_col_guess: int) -> tuple[int, int]:
    "自动识别源数据中的利率列与金额区间列。"
    rv = get_effective_cell_value(ws, r, rate_col_guess)
    av = get_effective_cell_value(ws, r, amount_col_guess)
    r_is_rate = maybe_parse_decimal(rv) is not None
    a_is_rate = maybe_parse_decimal(av) is not None
    r_is_amt = _is_amount_like(rv)
    a_is_amt = _is_amount_like(av)
    # If looks reversed (amount in rate col, rate in amount col), swap.
    if r_is_amt and a_is_rate:
        return amount_col_guess, rate_col_guess
    # Normal case.
    if r_is_rate and a_is_amt:
        return rate_col_guess, amount_col_guess
    # Fallback to template layout.
    return rate_col_guess, amount_col_guess


def normalize_rate_amount_layout(ws, blocks: Dict[str, tuple[int, int, int]], start_row: int) -> None:
    """
    Fix template rows where rate/amount values are physically written in reversed columns.
    """
    for _, (_, rate_col, amount_col) in blocks.items():
        for r in range(start_row, ws.max_row + 1):
            rv = ws.cell(r, rate_col).value
            av = ws.cell(r, amount_col).value
            if _is_amount_like(rv) and (maybe_parse_decimal(av) is not None):
                ws.cell(r, rate_col).value = av
                ws.cell(r, amount_col).value = rv


def _fill_promo_tenor_leader(
    ws,
    tenor: str,
    label_col: int,
    data_start: int,
    df_promo: pd.DataFrame,
    df_board: Optional[pd.DataFrame] = None,
) -> None:
    "为新加的期限列（如 18M/24M）填入市场最高报价（促销优先，无则回退挂牌）。"
    src_col = f"{tenor}_pct"
    bank_col, rate_col, cond_col = label_col, label_col + 1, label_col + 2
    if isinstance(ws.cell(data_start, bank_col).value, str) and str(ws.cell(data_start, bank_col).value).strip():
        return
    offers = pd.DataFrame()
    if src_col in df_promo.columns:
        offers = df_promo.dropna(subset=[src_col]).copy()
        offers["_dec"] = offers[src_col].apply(pct_to_decimal)
        offers = offers.dropna(subset=["_dec"])
    if offers.empty and df_board is not None and src_col in df_board.columns:
        offers = df_board.dropna(subset=[src_col]).copy()
        offers["_dec"] = offers[src_col].apply(pct_to_decimal)
        offers = offers.dropna(subset=["_dec"])
    if offers.empty:
        return
    offers = offers.sort_values("_dec", ascending=False)
    top = offers.iloc[0]
    disp_bank = re.sub(r"\s+SG$", "", str(top["数据来源"]), flags=re.I).strip()
    ws.cell(data_start, bank_col).value = disp_bank
    ws.cell(data_start, rate_col).value = float(top["_dec"])
    cond = str(top.get("起存金额_页面") or top.get("资金区间_页面") or top.get("产品或客群") or "").strip()
    if cond:
        ws.cell(data_start, cond_col).value = cond


def append_sheet_source_footer(ws, source_path: str, sheet_label: str) -> None:
    "在每个工作表底部标注数据来源文件与生成时间。"
    footer_row = ws.max_row + 2
    while footer_row > 1 and all(ws.cell(footer_row - 1, c).value is None for c in range(1, 6)):
        footer_row -= 1
        if footer_row <= 1:
            break
    footer_row = max(footer_row, ws.max_row + 1)
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    ws.cell(footer_row, 1).value = (
        f"数据来源：{os.path.basename(source_path)}（{sheet_label}）| 生成时间：{ts}"
    )


def load_source_tables(source_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    "读取来源工作簿，提取促销与挂牌两类 DataFrame。"
    df_promo = pd.read_excel(source_path, sheet_name="新元定存促销")
    df_board = pd.read_excel(source_path, sheet_name="新元挂牌利率")
    df_promo["_bank_canon"] = df_promo["数据来源"].map(canonical_bank_name)
    df_board["_bank_canon"] = df_board["数据来源"].map(canonical_bank_name)
    return df_promo, df_board


def update_sgd_promotional_rate(ws, df_promo: pd.DataFrame, df_board: Optional[pd.DataFrame] = None) -> None:
    "把来源促销利率写入模板 SGD Promotional Rate（竞争格局多行多列布局）。"
    ensure_promo_tenor_columns(ws)
    tenor_label_cols = detect_template_sgd_promo_tenors(ws)
    for _, data_start, data_end in _promo_section_ranges(ws):
        for tenor, label_col in tenor_label_cols.items():
            rate_col = label_col + 1
            bank_col = label_col
            cond_col = label_col + 2
            for bank_name, stack_rows in _iter_promo_stacks(ws, bank_col, data_start, data_end):
                _fill_promo_stack(ws, stack_rows, rate_col, cond_col, tenor, df_promo, bank_name)
            if tenor in ("18M", "24M"):
                _fill_promo_tenor_leader(ws, tenor, label_col, data_start, df_promo, df_board)
    apply_colors_to_rate_columns(ws, [c + 1 for c in tenor_label_cols.values()])


def update_sgd_board_rate(ws, df_board: pd.DataFrame) -> None:
    "把来源挂牌利率写入模板 SGD Board Rate。"
    blocks = detect_template_sgd_board_tenor_blocks(ws, header_row=5)
    # 先修正模板中可能存在的“利率列/金额列”反置问题，再开始回填。
    normalize_rate_amount_layout(ws, blocks, start_row=6)
    for tenor, (bank_col, rate_col_guess, amount_col_guess) in blocks.items():
        src_col = f"{tenor}_pct"
        if src_col not in df_board.columns:
            continue
        current_bank: Optional[str] = None
        for r in range(6, ws.max_row + 1):
            bank_cell = get_effective_cell_value(ws, r, bank_col)
            if isinstance(bank_cell, str) and bank_cell.strip():
                current_bank = bank_cell.strip()
            bank = current_bank
            if not bank:
                continue
            _, amount_col = resolve_rate_amount_cols(ws, r, rate_col_guess, amount_col_guess)
            templ_amt = get_effective_cell_value(ws, r, amount_col)
            picked = find_best_board_row(df_board, bank, templ_amt)
            if picked is None:
                continue
            dec = pct_to_decimal(picked.get(src_col))
            if dec is None:
                continue
            rate_col, _ = resolve_rate_amount_cols(ws, r, rate_col_guess, amount_col_guess)
            ws.cell(r, rate_col).value = float(dec)
        # Color only Highest Rate cells within the actual block rows.
        current_bank_for_color: Optional[str] = None
        for r in range(6, ws.max_row + 1):
            b = get_effective_cell_value(ws, r, bank_col)
            if isinstance(b, str) and b.strip():
                current_bank_for_color = b.strip()
            if not current_bank_for_color:
                continue
            v = ws.cell(r, rate_col_guess).value
            if isinstance(v, (int, float)):
                ws.cell(r, rate_col_guess).fill = FILL_BY_NAME[rate_to_color(float(v))]


def update_sgd_board_ranked(ws, df_board: pd.DataFrame) -> None:
    "更新模板 SGD Board Rate Ranked 的利率区域。"
    blocks = detect_template_sgd_board_tenor_blocks(ws, header_row=1)
    normalize_rate_amount_layout(ws, blocks, start_row=2)
    for tenor, (bank_col, rate_col_guess, amount_col_guess) in blocks.items():
        src_col = f"{tenor}_pct"
        if src_col not in df_board.columns:
            continue
        # 对每个 tenor 先按利率降序得到排行榜，再按模板行回填。
        offers = df_board[["数据来源", "资金区间_页面", src_col]].copy()
        offers = offers.dropna(subset=[src_col])
        offers["_dec"] = offers[src_col].apply(pct_to_decimal)
        offers = offers.dropna(subset=["_dec"]).sort_values("_dec", ascending=False).reset_index(drop=True)
        rank_rows = [r for r in range(2, ws.max_row + 1) if isinstance(ws.cell(r, bank_col).value, str)]
        for i, r in enumerate(rank_rows):
            if i >= len(offers):
                break
            ws.cell(r, bank_col).value = str(offers.iloc[i]["数据来源"])
            rate_col, amount_col = resolve_rate_amount_cols(ws, r, rate_col_guess, amount_col_guess)
            ws.cell(r, rate_col).value = float(offers.iloc[i]["_dec"])
            ws.cell(r, amount_col).value = offers.iloc[i]["资金区间_页面"]
        # Color only Highest Rate cells for populated ranking rows.
        for r in rank_rows:
            v = ws.cell(r, rate_col_guess).value
            if isinstance(v, (int, float)):
                ws.cell(r, rate_col_guess).fill = FILL_BY_NAME[rate_to_color(float(v))]


def update_sheet3_matrix(ws, df_board: pd.DataFrame) -> None:
    "更新模板 Sheet3 的矩阵利率区域。"
    tenor_cols: Dict[str, int] = {}
    for c in range(1, ws.max_column + 1):
        v = ws.cell(2, c).value
        if isinstance(v, str) and v.strip() in {"7D", "1M", "3M", "6M", "9M", "12M", "18M", "24M", "36M"}:
            tenor_cols[v.strip()] = c
    if not tenor_cols:
        return
    # 按银行与金额区间为矩阵每行匹配最佳来源记录。
    for r in range(1, ws.max_row + 1):
        bank = get_effective_cell_value(ws, r, 1)
        amt = get_effective_cell_value(ws, r, 2)
        if not isinstance(bank, str) or not bank.strip():
            continue
        picked = find_best_board_row(df_board, bank, amt)
        if picked is None:
            continue
        for tenor, c in tenor_cols.items():
            dec = pct_to_decimal(picked.get(f"{tenor}_pct"))
            if dec is not None:
                ws.cell(r, c).value = float(dec)
    apply_colors_to_rate_columns(ws, list(tenor_cols.values()))


def resolve_latest_source(work_dir: str) -> str:
    "自动选择目录中最新的可用来源工作簿。"
    pats = [
        "MarketRateData_*.xlsx",
        "marketratedata_*.xlsx",
        "bank_promo_rates_colored_centered_*.xlsx",
        "bank_promo_rates_colored_*.xlsx",
        "bank_promo_rates_*.xlsx",
    ]
    cands: List[str] = []
    for p in pats:
        cands.extend(glob.glob(os.path.join(work_dir, p)))
    if not cands:
        raise FileNotFoundError("Cannot find MarketRateData source workbook")
    cands.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return cands[0]


def resolve_template(work_dir: str, template_arg: str) -> str:
    "解析彩虹表模板路径（支持通配符）。"
    if "*" in template_arg or "?" in template_arg:
        cands = sorted(glob.glob(os.path.join(work_dir, template_arg)))
        if not cands:
            raise FileNotFoundError(f"No template matches: {template_arg}")
        return cands[0]
    p = os.path.join(work_dir, template_arg)
    if not os.path.exists(p):
        raise FileNotFoundError(p)
    return p


def _rainbow_zh_filename(run_tag: str) -> str:
    "与 03 批处理约定一致的中文输出名（仅含 ASCII 的 run_tag 由调用方传入）。"
    return f"彩虹表_按MarketRateData更新_{run_tag}.xlsx"


def main() -> None:
    "彩虹表生成入口（新版：三 sheet 合一，不再依赖旧模板）。"
    from generate_rainbow_from_market import main as _new_main

    print("[INFO] generate_rainbow_from_bank 已切换为新版彩虹表生成逻辑。")
    _new_main()


if __name__ == "__main__":
    main()
