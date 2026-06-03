#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 MarketRateData 生成新彩虹表（基于模板）。

本脚本重点保证：
1) `SGD Promotional Rate`：按 Bank+Condition 匹配市场促销表并写入；生成后与市场对账
2) `SGD Board Rate`：按 Bank+Amount 落到 Market 挂牌表对应行
3) `SGD Board Rate Ranked`：按各期限 Market 行 Rate 全局排序后写入名次行；生成后与排序结果对账
4) `Sheet3`：Bank+Amount 矩阵与各期限利率对账

任一步骤校验失败会抛出 `RainbowVerificationError`，信息中包含工作表、检查项、行/列/期限与期望/实际值。

`USD Rate + Other Currency Rates`：尚未与市场表自动同步（模板保留手工维护）；后续对接后可按同样模式增加更新与校验。
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import os
import re
import shutil
from dataclasses import dataclass
from typing import Any, Optional

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
    "red": PatternFill("solid", fgColor="FFFF0000"),
    "orange": PatternFill("solid", fgColor="FFFFA500"),
    "yellow": PatternFill("solid", fgColor="FFFFFF00"),
    "green": PatternFill("solid", fgColor="FF00B050"),
    "blue": PatternFill("solid", fgColor="FF5B9BD5"),
    "purple": PatternFill("solid", fgColor="FF7030A0"),
}


class RainbowVerificationError(RuntimeError):
    """生成后与市场对账失败。args[0] 为多行可读说明（含工作表、检查项、明细）。"""


def raise_verification_error(
    sheet: str,
    check_name: str,
    mismatches: list[dict[str, Any]],
    extra: str = "",
) -> None:
    lines = [
        "Rainbow 校验失败",
        f"  工作表 (sheet): {sheet}",
        f"  检查项: {check_name}",
        f"  不匹配条数: {len(mismatches)}",
    ]
    if extra:
        lines.append(f"  补充说明: {extra}")
    n = min(25, len(mismatches))
    lines.append(f"  前 {n} 条明细:")
    for i, m in enumerate(mismatches[:25], 1):
        parts = [f"{k}={v!r}" for k, v in m.items()]
        lines.append(f"    [{i}] " + "; ".join(parts))
    raise RainbowVerificationError("\n".join(lines))


def asof_to_date(s: str) -> dt.date:
    s = s.strip()
    if re.fullmatch(r"\d{8}", s):
        return dt.datetime.strptime(s, "%Y%m%d").date()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return dt.datetime.strptime(s, "%Y-%m-%d").date()
    raise ValueError(f"Invalid asof date: {s!r}")


def normalize_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace(" ", "").replace("\u3000", "")
    s = s.replace(",", "")
    return s


def canonical_bank_name(s: Any) -> str:
    t = normalize_text(str(s or ""))
    t = t.replace("&", "").replace("/", "")
    alias = {
        "citibank": "citi",
        "citi": "citi",
        "dbsposb": "dbsposb",
        "dbs": "dbsposb",
        "posb": "dbsposb",
        "uob": "uob",
        "ocbc": "ocbc",
        "icbc": "icbc",
        "scb": "scb",
        "standardchartered": "scb",
        "sbi": "sbi",
        "boc": "boc",
        "bankofchina": "boc",
        "maybank": "maybank",
        "cimb": "cimb",
        "hsbc": "hsbc",
        "bea": "bea",
        "bankofeastasia": "bea",
        "rhb": "rhb",
        "hlb": "hlb",
        "hlbank": "hlb",
        "hongleong": "hlb",
        "singfinance": "singfinance",
        "sif": "singfinance",
    }
    for k, v in alias.items():
        if k in t:
            return v
    return t


def bank_name_matches(template_bank: Any, market_bank: Any) -> bool:
    t = canonical_bank_name(template_bank)
    m = canonical_bank_name(market_bank)
    return bool(t) and bool(m) and t == m


def market_value_to_decimal(v: Any, percent_unit: bool) -> Optional[float]:
    dec = maybe_parse_rate_to_decimal(v)
    if dec is None:
        return None
    if percent_unit:
        return float(dec) / 100.0
    return float(dec)


def is_new_market_promo_layout(ws) -> bool:
    for c in range(1, ws.max_column + 1):
        v = ws.cell(1, c).value
        if isinstance(v, str) and re.fullmatch(r"(?:\d+M|7D|14D)_pct", v.strip()):
            return True
    return False


def is_new_market_board_layout(ws) -> bool:
    for c in range(1, ws.max_column + 1):
        v = ws.cell(1, c).value
        if isinstance(v, str) and re.fullmatch(r"(?:\d+M|7D|14D)_pct", v.strip()):
            return True
    return False


_NUM_TOKEN_RE = re.compile(r"\d+(?:,\d+)*(?:\s*(?:k|K|m|M|mil|MIL))?")


def extract_number_tokens(s: str) -> set[str]:
    s = s or ""
    out: set[str] = set()
    for m in _NUM_TOKEN_RE.finditer(s):
        tok = m.group(0).lower().replace(",", "").strip()
        # normalize "mil" -> "m" for simplicity
        tok = tok.replace("mil", "m")

        # Expand unit-based tokens into canonical digits.
        if tok.endswith("k"):
            num = tok[:-1].strip()
            if num.isdigit():
                out.add(str(int(num) * 1000))
                continue
        if tok.endswith("m"):
            num = tok[:-1].strip()
            if num.isdigit():
                out.add(str(int(num) * 1000000))
                continue

        # No unit: keep plain digits
        if tok.isdigit():
            out.add(tok)
    return out


def maybe_parse_rate_to_decimal(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dt.datetime):
        return None
    if isinstance(v, str):
        s = v.strip()
        # e.g. "1.50%(Online)"
        m = re.search(r"(\d+(?:\.\d+)?)\s*%", s)
        if m:
            return float(m.group(1)) / 100.0
        # numeric string (already decimal)
        if re.fullmatch(r"-?\d+(?:\.\d+)?", s):
            return float(s)
    return None


def rate_to_color(rate_decimal: float) -> str:
    for name, thr in RATE_THRESHOLDS:
        if rate_decimal >= thr:
            return name
    return "purple"


def get_effective_cell_value(ws, row: int, col: int) -> Any:
    """
    兼容 merged cells：当 cell.value 为 None 时，返回该位置 merged range 左上角的值。
    """
    v = ws.cell(row, col).value
    if v is not None:
        return v
    try:
        for rng in ws.merged_cells.ranges:
            min_col, min_row, max_col, max_row = rng.bounds
            if min_col <= col <= max_col and min_row <= row <= max_row:
                return ws.cell(min_row, min_col).value
    except Exception:
        pass
    return v


@dataclass(frozen=True)
class MarketSheets:
    promo_ws: Any
    board_ws: Any


def find_market_sheets(market_wb) -> MarketSheets:
    promo_ws = None
    board_ws = None

    for ws in market_wb.worksheets:
        try:
            # 旧版 promo: A2 == "1 Month"；新版 promo: row1 含 *_pct 列且是「新元定存促销」
            if ws.cell(2, 1).value == "1 Month":
                promo_ws = ws
            if "新元定存促销" in str(getattr(ws, "title", "")) and is_new_market_promo_layout(ws):
                promo_ws = ws
            # 旧版 board: row2 col1 == "Bank" 且 row2 col3 == "7D"；新版 board: 「新元挂牌利率」+ *_pct
            if ws.cell(2, 1).value == "Bank" and ws.cell(2, 3).value == "7D":
                board_ws = ws
            if "新元挂牌利率" in str(getattr(ws, "title", "")) and is_new_market_board_layout(ws):
                board_ws = ws
        except Exception:
            continue

    if promo_ws is None or board_ws is None:
        titles = [getattr(w, "title", "") for w in market_wb.worksheets]
        hint = f"Cannot locate SGD promo/board sheets in market workbook. sheets={titles!r}"
        raise RuntimeError(hint)
    return MarketSheets(promo_ws=promo_ws, board_ws=board_ws)


def find_date_col_in_row(ws, date_header_row: int, target_date: Optional[dt.date]) -> tuple[int, dt.date]:
    dates: list[tuple[int, dt.date]] = []
    for c in range(1, ws.max_column + 1):
        v = ws.cell(date_header_row, c).value
        if isinstance(v, dt.datetime):
            dates.append((c, v.date()))
    if not dates:
        raise RuntimeError(f"No datetime columns found at header row {date_header_row}")
    if target_date is None:
        col, chosen = max(dates, key=lambda x: x[1])
        return col, chosen
    match = [c for c, d in dates if d == target_date]
    if not match:
        col, chosen = max(dates, key=lambda x: x[1])
        print(f"[WARN] asof {target_date} not found in market; fallback to {chosen}")
        return col, chosen
    return match[0], target_date


def build_sgd_promo_sections(market_promo_ws) -> dict[str, dict[str, Any]]:
    tenor_to_label = {
        "1M": "1 Month",
        "3M": "3 Months",
        "6M": "6 Months",
        "9M": "9 Months",
        "12M": "12 Months",
    }

    start_rows: dict[str, int] = {}
    for r in range(1, market_promo_ws.max_row + 1):
        v = market_promo_ws.cell(r, 1).value
        if isinstance(v, str):
            v2 = v.strip()
            for tk, label in tenor_to_label.items():
                if v2 == label:
                    start_rows[tk] = r

    if not start_rows:
        raise RuntimeError("Cannot find promo tenor sections in market promo sheet")

    # determine end rows
    ordered = sorted(start_rows.items(), key=lambda x: x[1])
    sections: dict[str, dict[str, Any]] = {}
    for i, (tk, sr) in enumerate(ordered):
        next_sr = ordered[i + 1][1] if i + 1 < len(ordered) else market_promo_ws.max_row + 1
        sections[tk] = {
            "start_row": sr,
            "end_row": next_sr - 1,
            "date_header_row": sr + 1,
        }
    return sections


def apply_colors_to_rate_columns(ws, rate_cols: list[int]) -> None:
    for r in range(1, ws.max_row + 1):
        for c in rate_cols:
            v = ws.cell(r, c).value
            dec = maybe_parse_rate_to_decimal(v)
            if dec is None:
                continue
            ws.cell(r, c).fill = FILL_BY_NAME[rate_to_color(dec)]


def detect_template_sgd_promo_tenors(template_ws) -> dict[str, int]:
    """
    在 `SGD Promotional Rate`，row4 中的列值为 1M/3M/6M/9M/12M。
    该列值为 tenor_label_col；其右侧：
      tenor_label_col+1: Promo Rate
      tenor_label_col+2: Condition
    """
    header_row = 4
    out: dict[str, int] = {}
    tenor_labels = {"1M", "3M", "6M", "9M", "12M"}
    for c in range(1, template_ws.max_column + 1):
        v = template_ws.cell(header_row, c).value
        if isinstance(v, str) and v.strip() in tenor_labels:
            out[v.strip()] = c
    if not out:
        raise RuntimeError("Cannot detect tenor label columns in template SGD Promotional Rate")
    return out


def match_market_row_for_bank_condition(
    market_ws,
    section: dict[str, Any],
    bank_name: str,
    template_condition: Any,
    amount_scan_col_end: int = 25,
) -> Optional[int]:
    """
    在市场 promo section 内，找 bank_name 对应的 offer 行，并按 template_condition 做评分。
    """
    if template_condition is None:
        return None
    cond_text = str(template_condition)
    cond_tokens = extract_number_tokens(cond_text)
    cond_norm = normalize_text(cond_text)
    keywords = ["online", "fresh", "fund", "personal", "mobile", "counter", "premier", "wealth", "deposit", "bundle", "branch", "others"]
    kw = [k for k in keywords if k in cond_norm]

    best_r = None
    best_score = -1
    start_row = section["start_row"] + 2
    end_row = section["end_row"]

    for mr in range(start_row, end_row + 1):
        bank_v = get_effective_cell_value(market_ws, mr, 1)
        if not isinstance(bank_v, str) or not bank_name_matches(bank_name, bank_v):
            continue
        # promo 在 market_ws 的“条件文本”通常在列2（合并/编码可能出现怪字符也没关系）
        market_cond = get_effective_cell_value(market_ws, mr, 2)
        if market_cond is None:
            market_cond = ""
        market_cond_str = str(market_cond)
        market_norm = normalize_text(market_cond_str)

        score = 0
        for k in kw:
            if k in market_norm:
                score += 4
        inter = cond_tokens & extract_number_tokens(market_cond_str)
        score += len(inter) * 5
        # 额外：如果模板条件整体包含的归一化片段在市场条件里
        if cond_norm and cond_norm in market_norm:
            score += 3

        if score > best_score:
            best_score = score
            best_r = mr

    # 与 Board 一致：无有效匹配分时不得落行，避免误填
    if best_r is None or best_score <= 0:
        return None
    return best_r


def update_sgd_promotional_rate(template_ws, market_promo_ws, target_date: Optional[dt.date]) -> dt.date:
    tenor_label_cols = detect_template_sgd_promo_tenors(template_ws)
    bank_col = 2  # 模板中银行名在B列
    chosen_asof: Optional[dt.date] = None

    if is_new_market_promo_layout(market_promo_ws):
        # 新版：row1 是 *_pct 列，不区分日期列（由流水线当日生成）
        promo_tenor_cols: dict[str, int] = {}
        for c in range(1, market_promo_ws.max_column + 1):
            v = market_promo_ws.cell(1, c).value
            if isinstance(v, str):
                m = re.fullmatch(r"(1M|3M|6M|9M|12M)_pct", v.strip())
                if m:
                    promo_tenor_cols[m.group(1)] = c
        chosen_asof = target_date or dt.date.today()

        for r in range(1, template_ws.max_row + 1):
            bank_name = template_ws.cell(r, bank_col).value
            if not isinstance(bank_name, str) or not bank_name.strip():
                continue
            if bank_name.strip().lower().startswith("ftp"):
                continue

            for tk, tenor_col in tenor_label_cols.items():
                m_col = promo_tenor_cols.get(tk)
                if not m_col:
                    continue
                rate_col = tenor_col + 1
                cond_col = tenor_col + 2
                template_cond = template_ws.cell(r, cond_col).value

                best_r = None
                best_sc = -1
                for mr in range(2, market_promo_ws.max_row + 1):
                    market_bank = get_effective_cell_value(market_promo_ws, mr, 1)
                    if not isinstance(market_bank, str) or not bank_name_matches(bank_name, market_bank):
                        continue
                    market_cond = f"{get_effective_cell_value(market_promo_ws, mr, 2) or ''} {get_effective_cell_value(market_promo_ws, mr, 5) or ''}"
                    sc = score_amount_match(template_cond, market_cond)
                    if sc > best_sc:
                        best_sc = sc
                        best_r = mr
                if best_r is None or best_sc <= 0:
                    continue
                dec = market_value_to_decimal(market_promo_ws.cell(best_r, m_col).value, percent_unit=True)
                if dec is None:
                    continue
                template_ws.cell(r, rate_col).value = float(dec)
    else:
        sections = build_sgd_promo_sections(market_promo_ws)
        tenor_to_date_col: dict[str, int] = {}
        for tk, sec in sections.items():
            date_col, asof_date = find_date_col_in_row(market_promo_ws, sec["date_header_row"], target_date)
            tenor_to_date_col[tk] = date_col
            chosen_asof = asof_date

        for r in range(1, template_ws.max_row + 1):
            bank_name = template_ws.cell(r, bank_col).value
            if not isinstance(bank_name, str) or not bank_name.strip():
                continue
            if bank_name.strip().lower().startswith("ftp"):
                continue

            for tk, tenor_col in tenor_label_cols.items():
                rate_col = tenor_col + 1
                cond_col = tenor_col + 2
                template_cond = template_ws.cell(r, cond_col).value
                sec = sections[tk]
                mr = match_market_row_for_bank_condition(market_promo_ws, sec, bank_name.strip(), template_cond)
                if mr is None:
                    continue
                dec = market_value_to_decimal(market_promo_ws.cell(mr, tenor_to_date_col[tk]).value, percent_unit=False)
                if dec is None:
                    continue
                template_ws.cell(r, rate_col).value = float(dec)

    # apply colors to all promo rate columns
    rate_cols = [tenor_col + 1 for tenor_col in tenor_label_cols.values()]
    apply_colors_to_rate_columns(template_ws, rate_cols)
    return chosen_asof or dt.date.today()


def verify_sgd_promotional_rate(
    template_ws,
    market_promo_ws,
    target_date: Optional[dt.date],
) -> None:
    """
    与 `update_sgd_promotional_rate` 相同匹配逻辑：若某格能唯一确定市场行且市场有利率，
    则模板对应利率列必须与之一致。
    """
    sheet_name = getattr(template_ws, "title", "SGD Promotional Rate")
    tenor_label_cols = detect_template_sgd_promo_tenors(template_ws)
    bank_col = 2
    tol = 1e-15
    mismatches: list[dict[str, Any]] = []
    if is_new_market_promo_layout(market_promo_ws):
        promo_tenor_cols: dict[str, int] = {}
        for c in range(1, market_promo_ws.max_column + 1):
            v = market_promo_ws.cell(1, c).value
            if isinstance(v, str):
                m = re.fullmatch(r"(1M|3M|6M|9M|12M)_pct", v.strip())
                if m:
                    promo_tenor_cols[m.group(1)] = c

        for r in range(1, template_ws.max_row + 1):
            bank_name = template_ws.cell(r, bank_col).value
            if not isinstance(bank_name, str) or not bank_name.strip():
                continue
            if bank_name.strip().lower().startswith("ftp"):
                continue
            for tk, tenor_col in tenor_label_cols.items():
                m_col = promo_tenor_cols.get(tk)
                if not m_col:
                    continue
                rate_col = tenor_col + 1
                cond_col = tenor_col + 2
                template_cond = template_ws.cell(r, cond_col).value
                best_r = None
                best_sc = -1
                for mr in range(2, market_promo_ws.max_row + 1):
                    market_bank = get_effective_cell_value(market_promo_ws, mr, 1)
                    if not isinstance(market_bank, str) or not bank_name_matches(bank_name, market_bank):
                        continue
                    market_cond = f"{get_effective_cell_value(market_promo_ws, mr, 2) or ''} {get_effective_cell_value(market_promo_ws, mr, 5) or ''}"
                    sc = score_amount_match(template_cond, market_cond)
                    if sc > best_sc:
                        best_sc = sc
                        best_r = mr
                if best_r is None or best_sc <= 0:
                    continue
                dec = market_value_to_decimal(market_promo_ws.cell(best_r, m_col).value, percent_unit=True)
                if dec is None:
                    continue
                exp = float(dec)
                tv = template_ws.cell(r, rate_col).value
                t_dec = maybe_parse_rate_to_decimal(tv)
                if t_dec is None or abs(float(t_dec) - exp) > tol:
                    mismatches.append(
                        {
                            "row": r,
                            "tenor": tk,
                            "rate_col": rate_col,
                            "bank": bank_name.strip(),
                            "异常": "模板利率与市场不一致",
                            "期望利率": exp,
                            "模板实际值": tv,
                        }
                    )
    else:
        sections = build_sgd_promo_sections(market_promo_ws)
        tenor_to_date_col: dict[str, int] = {}
        for tk, sec in sections.items():
            date_col, _ = find_date_col_in_row(market_promo_ws, sec["date_header_row"], target_date)
            tenor_to_date_col[tk] = date_col
        for r in range(1, template_ws.max_row + 1):
            bank_name = template_ws.cell(r, bank_col).value
            if not isinstance(bank_name, str) or not bank_name.strip():
                continue
            if bank_name.strip().lower().startswith("ftp"):
                continue
            for tk, tenor_col in tenor_label_cols.items():
                if tk not in sections:
                    continue
                rate_col = tenor_col + 1
                cond_col = tenor_col + 2
                template_cond = template_ws.cell(r, cond_col).value
                sec = sections[tk]
                mr = match_market_row_for_bank_condition(market_promo_ws, sec, bank_name.strip(), template_cond)
                if mr is None:
                    continue
                dec = market_value_to_decimal(market_promo_ws.cell(mr, tenor_to_date_col[tk]).value, percent_unit=False)
                if dec is None:
                    continue
                exp = float(dec)
                tv = template_ws.cell(r, rate_col).value
                t_dec = maybe_parse_rate_to_decimal(tv)
                if t_dec is None or abs(float(t_dec) - exp) > tol:
                    mismatches.append(
                        {
                            "row": r,
                            "tenor": tk,
                            "rate_col": rate_col,
                            "bank": bank_name.strip(),
                            "异常": "模板利率与市场不一致",
                            "期望利率": exp,
                            "模板实际值": tv,
                        }
                    )

    if mismatches:
        raise_verification_error(
            sheet_name,
            "SGD Promotional Rate 与市场促销表对账",
            mismatches,
        )


def detect_template_sgd_board_tenor_blocks(template_ws, header_row: int) -> dict[str, tuple[int, int, int]]:
    """
    返回 tenor_key -> (bank_col, rate_col, amount_col)
    在 SGD Board Rate 模板中：tenor_label_col 其右侧依次为 Highest Rate / Amount。
    """
    tenor_keys = {"7D", "1M", "3M", "6M", "9M", "12M", "18M", "24M", "36M"}
    out: dict[str, tuple[int, int, int]] = {}
    for c in range(1, template_ws.max_column + 1):
        v = template_ws.cell(header_row, c).value
        if isinstance(v, str) and v.strip() in tenor_keys:
            tk = v.strip()
            out[tk] = (c, c + 1, c + 2)
    return out


def build_market_tenor_col_map(board_ws) -> dict[str, int]:
    """
    支持两种 market 布局：
    - 旧版：row2 列头为 7D/1M/...
    - 新版：row1 列头为 7D_pct/1M_pct/...
    """
    tenor_keys = {"7D", "1M", "2M", "3M", "4M", "5M", "6M", "7M", "8M", "9M", "10M", "11M", "12M", "18M", "24M", "36M"}
    out: dict[str, int] = {}
    if is_new_market_board_layout(board_ws):
        for c in range(1, board_ws.max_column + 1):
            v = board_ws.cell(1, c).value
            if not isinstance(v, str):
                continue
            m = re.fullmatch(r"(7D|\d+M)_pct", v.strip())
            if m and m.group(1) in tenor_keys:
                out[m.group(1)] = c
    else:
        for c in range(1, board_ws.max_column + 1):
            v = board_ws.cell(2, c).value
            if isinstance(v, str) and v.strip() in tenor_keys:
                out[v.strip()] = c
    return out


def get_market_board_layout(board_ws) -> dict[str, Any]:
    if is_new_market_board_layout(board_ws):
        return {
            "is_new": True,
            "bank_col": 1,
            "amount_col": 5,
            "data_start_row": 2,
            "percent_unit": True,
        }
    return {
        "is_new": False,
        "bank_col": 1,
        "amount_col": 2,
        "data_start_row": 3,
        "percent_unit": False,
    }


def score_amount_match(template_amount: Any, market_amount: Any) -> int:
    if template_amount is None or market_amount is None:
        return 0
    t = str(template_amount)
    m = str(market_amount)
    t_norm = normalize_text(t)
    m_norm = normalize_text(m)
    if t_norm == m_norm:
        return 30
    # digits overlap
    t_tokens = extract_number_tokens(t)
    m_tokens = extract_number_tokens(m)
    inter = t_tokens & m_tokens
    if inter:
        return 10 * len(inter) + (5 if t_tokens <= m_tokens else 0)
    # substring fallback
    if t_tokens and any(tok in m_norm for tok in t_tokens):
        return 6
    return 0


def find_best_market_row_for_bank_amount(
    market_board_ws,
    bank_col: int,
    amount_col: int,
    bank_name: str,
    template_amount: Any,
) -> Optional[int]:
    best_r = None
    best_score = -1

    for mr in range(1, market_board_ws.max_row + 1):
        b = get_effective_cell_value(market_board_ws, mr, bank_col)
        if not isinstance(b, str) or not bank_name_matches(bank_name, b):
            continue
        a = get_effective_cell_value(market_board_ws, mr, amount_col)
        if not isinstance(a, str):
            continue
        sc = score_amount_match(template_amount, a)
        # 关键加固：如果完全无法匹配（sc==0），不允许“随便选第一行”导致写错利率
        if sc <= 0:
            continue
        if sc > best_score:
            best_score = sc
            best_r = mr

    return best_r


def update_sgd_board_rate(template_ws, market_board_ws, target_date: Optional[dt.date]) -> None:
    # header row for SGD Board Rate: template historically uses row 5
    header_row = 5
    tenor_blocks = detect_template_sgd_board_tenor_blocks(template_ws, header_row)
    market_tenor_col = build_market_tenor_col_map(market_board_ws)
    board_layout = get_market_board_layout(market_board_ws)

    if not tenor_blocks:
        raise RuntimeError("Cannot detect tenor blocks in template SGD Board Rate")

    def resolve_rate_amount_cols(r: int, rate_col_guess: int, amount_col_guess: int) -> tuple[int, int]:
        """
        针对模板里可能存在的 merged/variant 行：rate_col_guess 与 amount_col_guess 在某些行里可能对调。
        规则：哪个列能解析成利率(非None)就是 rate 列；另一个就是 amount 列。
        """
        v_rate_guess = maybe_parse_rate_to_decimal(get_effective_cell_value(template_ws, r, rate_col_guess))
        v_amt_guess = get_effective_cell_value(template_ws, r, amount_col_guess)
        v_amt_guess_is_rate = maybe_parse_rate_to_decimal(v_amt_guess) is not None

        if v_rate_guess is not None and not v_amt_guess_is_rate:
            return rate_col_guess, amount_col_guess
        if v_rate_guess is None and v_amt_guess_is_rate:
            return amount_col_guess, rate_col_guess
        # default: assume normal mapping
        return rate_col_guess, amount_col_guess

    # Apply per tenor
    for tk, (bank_col, rate_col_guess, amount_col_guess) in tenor_blocks.items():
        m_col = market_tenor_col.get(tk)
        if not m_col:
            continue
        market_bank_col = int(board_layout["bank_col"])
        market_amount_col = int(board_layout["amount_col"])

        for r in range(1, template_ws.max_row + 1):
            bank_name = get_effective_cell_value(template_ws, r, bank_col)
            if not isinstance(bank_name, str) or not bank_name.strip():
                continue
            if bank_name.strip().lower().startswith("ftp"):
                continue
            rate_col, amount_col = resolve_rate_amount_cols(r, rate_col_guess, amount_col_guess)
            templ_amt = get_effective_cell_value(template_ws, r, amount_col)
            if templ_amt is None or not isinstance(templ_amt, str) or not templ_amt.strip():
                continue

            mr = find_best_market_row_for_bank_amount(
                market_board_ws=market_board_ws,
                bank_col=market_bank_col,
                amount_col=market_amount_col,
                bank_name=bank_name,
                template_amount=templ_amt,
            )
            if mr is None:
                continue
            v = market_board_ws.cell(mr, m_col).value
            dec = market_value_to_decimal(v, percent_unit=bool(board_layout["percent_unit"]))
            if dec is None:
                continue
            template_ws.cell(r, rate_col).value = float(dec)

        # color candidate columns (rate_col_guess and amount_col_guess) because some rows may be swapped
        apply_colors_to_rate_columns(template_ws, [rate_col_guess, amount_col_guess])


def update_sgd_board_ranked(template_ws, market_board_ws, target_date: Optional[dt.date]) -> None:
    # header row for ranked is row 1 in template
    header_row = 1
    tenor_blocks = detect_template_sgd_board_tenor_blocks(template_ws, header_row)
    market_tenor_col = build_market_tenor_col_map(market_board_ws)
    board_layout = get_market_board_layout(market_board_ws)
    if not tenor_blocks:
        raise RuntimeError("Cannot detect tenor blocks in template SGD Board Rate Ranked")

    # market bank/amount cols
    market_bank_col = int(board_layout["bank_col"])
    market_amount_col = int(board_layout["amount_col"])

    def resolve_rate_amount_cols(r: int, rate_col_guess: int, amount_col_guess: int) -> tuple[int, int]:
        v_rate_guess = maybe_parse_rate_to_decimal(get_effective_cell_value(template_ws, r, rate_col_guess))
        v_amt_guess = get_effective_cell_value(template_ws, r, amount_col_guess)
        v_amt_guess_is_rate = maybe_parse_rate_to_decimal(v_amt_guess) is not None
        if v_rate_guess is not None and not v_amt_guess_is_rate:
            return rate_col_guess, amount_col_guess
        if v_rate_guess is None and v_amt_guess_is_rate:
            return amount_col_guess, rate_col_guess
        return rate_col_guess, amount_col_guess

    for tk, (bank_col, rate_col_guess, amount_col_guess) in tenor_blocks.items():
        m_col = market_tenor_col.get(tk)
        if not m_col:
            continue

        # rank rows = where bank cell is non-empty
        rank_rows: list[int] = []
        for r in range(header_row + 1, template_ws.max_row + 1):
            b = template_ws.cell(r, bank_col).value
            if isinstance(b, str) and b.strip():
                rank_rows.append(r)
        if not rank_rows:
            continue

        offers: list[tuple[str, Any, float]] = []
        for mr in range(int(board_layout["data_start_row"]), market_board_ws.max_row + 1):
            bank_v = get_effective_cell_value(market_board_ws, mr, market_bank_col)
            amt_v = get_effective_cell_value(market_board_ws, mr, market_amount_col)
            rate_dec = market_value_to_decimal(
                market_board_ws.cell(mr, m_col).value,
                percent_unit=bool(board_layout["percent_unit"]),
            )
            if not isinstance(bank_v, str) or not bank_v.strip():
                continue
            if not isinstance(amt_v, str) or not amt_v.strip():
                continue
            if rate_dec is None:
                continue
            offers.append((bank_v.strip(), amt_v, float(rate_dec)))

        # Sort by rate desc; tie-break by amount token string for stability
        def _amt_key(a: Any) -> str:
            return normalize_text(str(a))

        offers.sort(key=lambda x: (-x[2], _amt_key(x[1])))

        # fill
        for i, r in enumerate(rank_rows):
            if i >= len(offers):
                resolved_rate_col, resolved_amount_col = resolve_rate_amount_cols(
                    r, rate_col_guess, amount_col_guess
                )
                template_ws.cell(r, bank_col).value = None
                template_ws.cell(r, resolved_rate_col).value = None
                template_ws.cell(r, resolved_amount_col).value = None
                continue

            bank_name, amt_v, rate_dec = offers[i]
            template_ws.cell(r, bank_col).value = bank_name
            resolved_rate_col, resolved_amount_col = resolve_rate_amount_cols(
                r, rate_col_guess, amount_col_guess
            )
            template_ws.cell(r, resolved_rate_col).value = float(rate_dec)
            template_ws.cell(r, resolved_amount_col).value = amt_v

        # 颜色：rate_col_guess 和 amount_col_guess 这两列里可能存在交换，简单起见两列都尝试
        apply_colors_to_rate_columns(template_ws, [rate_col_guess, amount_col_guess])


def verify_sgd_board_ranked(template_ws, market_board_ws) -> None:
    """
    与 `update_sgd_board_ranked` 一致：各期限按市场全量 offers 降序排序后，
    模板中「非空银行名」的行从上到下应与 offers[0], offers[1], ... 一致。
    """
    sheet_name = getattr(template_ws, "title", "SGD Board Rate Ranked")
    header_row = 1
    tenor_blocks = detect_template_sgd_board_tenor_blocks(template_ws, header_row)
    market_tenor_col = build_market_tenor_col_map(market_board_ws)
    board_layout = get_market_board_layout(market_board_ws)
    market_bank_col = int(board_layout["bank_col"])
    market_amount_col = int(board_layout["amount_col"])
    tol = 1e-15

    def resolve_rate_amount_cols(r: int, rate_col_guess: int, amount_col_guess: int) -> tuple[int, int]:
        v_rate_guess = maybe_parse_rate_to_decimal(get_effective_cell_value(template_ws, r, rate_col_guess))
        v_amt_guess = get_effective_cell_value(template_ws, r, amount_col_guess)
        v_amt_guess_is_rate = maybe_parse_rate_to_decimal(v_amt_guess) is not None
        if v_rate_guess is not None and not v_amt_guess_is_rate:
            return rate_col_guess, amount_col_guess
        if v_rate_guess is None and v_amt_guess_is_rate:
            return amount_col_guess, rate_col_guess
        return rate_col_guess, amount_col_guess

    for tk, (bank_col, rate_col_guess, amount_col_guess) in tenor_blocks.items():
        m_col = market_tenor_col.get(tk)
        if not m_col:
            continue

        offers: list[tuple[str, Any, float]] = []
        for mr in range(int(board_layout["data_start_row"]), market_board_ws.max_row + 1):
            bank_v = get_effective_cell_value(market_board_ws, mr, market_bank_col)
            amt_v = get_effective_cell_value(market_board_ws, mr, market_amount_col)
            rate_dec = market_value_to_decimal(
                market_board_ws.cell(mr, m_col).value,
                percent_unit=bool(board_layout["percent_unit"]),
            )
            if not isinstance(bank_v, str) or not bank_v.strip():
                continue
            if not isinstance(amt_v, str) or not amt_v.strip():
                continue
            if rate_dec is None:
                continue
            offers.append((bank_v.strip(), amt_v, float(rate_dec)))

        def _amt_key(a: Any) -> str:
            return normalize_text(str(a))

        offers.sort(key=lambda x: (-x[2], _amt_key(x[1])))

        rank_rows: list[int] = []
        for r in range(header_row + 1, template_ws.max_row + 1):
            b = template_ws.cell(r, bank_col).value
            if isinstance(b, str) and b.strip():
                rank_rows.append(r)

        mismatches: list[dict[str, Any]] = []

        for i, r in enumerate(rank_rows):
            if i < len(offers):
                exp_bank, exp_amt, exp_rate = offers[i]
                rate_col, amount_col = resolve_rate_amount_cols(r, rate_col_guess, amount_col_guess)
                act_bank = get_effective_cell_value(template_ws, r, bank_col)
                act_rate_v = get_effective_cell_value(template_ws, r, rate_col)
                act_amt_v = get_effective_cell_value(template_ws, r, amount_col)

                if not isinstance(act_bank, str) or act_bank.strip() != exp_bank:
                    mismatches.append(
                        {
                            "期限": tk,
                            "row": r,
                            "bank_col": bank_col,
                            "异常": "银行名与排序结果不一致",
                            "期望银行": exp_bank,
                            "模板银行": act_bank,
                        }
                    )
                if isinstance(act_amt_v, str):
                    exp_amt_s = str(exp_amt).strip()
                    act_amt_s = act_amt_v.strip()
                    if exp_amt_s != act_amt_s:
                        mismatches.append(
                            {
                                "期限": tk,
                                "row": r,
                                "amount_col": amount_col,
                                "异常": "金额/条件文本与排序结果不一致",
                                "期望": exp_amt_s,
                                "模板": act_amt_s,
                            }
                        )
                elif exp_amt is not None:
                    mismatches.append(
                        {
                            "期限": tk,
                            "row": r,
                            "amount_col": amount_col,
                            "异常": "模板缺少金额档位文本",
                            "期望": str(exp_amt),
                            "模板": act_amt_v,
                        }
                    )

                act_dec = maybe_parse_rate_to_decimal(act_rate_v)
                if act_dec is None or abs(float(act_dec) - exp_rate) > tol:
                    mismatches.append(
                        {
                            "期限": tk,
                            "row": r,
                            "rate_col": rate_col,
                            "异常": "利率与排序结果不一致",
                            "期望利率": exp_rate,
                            "模板实际": act_rate_v,
                        }
                    )
            else:
                # 应已清空
                b = get_effective_cell_value(template_ws, r, bank_col)
                rate_col, amount_col = resolve_rate_amount_cols(r, rate_col_guess, amount_col_guess)
                rv = get_effective_cell_value(template_ws, r, rate_col)
                av = get_effective_cell_value(template_ws, r, amount_col)
                if (isinstance(b, str) and b.strip()) or rv is not None or av is not None:
                    mismatches.append(
                        {
                            "期限": tk,
                            "row": r,
                            "异常": "名次行应已清空但仍有余留数据",
                            "bank": b,
                            "rate": rv,
                            "amount": av,
                        }
                    )

        if mismatches:
            raise_verification_error(
                sheet_name,
                f"SGD Board Rate Ranked 期限 {tk} 与排序后对账",
                mismatches,
            )


def update_sheet3_matrix(template_ws, market_board_ws) -> None:
    """
    更新模板 Sheet3（银行矩阵）：
    - 模板表头在 row=2：Bank/Amount/7D/1M/3M/6M/9M/12M/18M/24M/36M
    - 市场表使用 MarketRateData11 的 'SGD挂牌'：Bank/Amount/7D/1M/2M/3M/4M/.../36M
    - 只填模板 Sheet3 里存在的 tenor 列
    - 按阈值对更新后的 rate 单元格重新上色
    """

    tenor_set = {"7D", "1M", "3M", "6M", "9M", "12M", "18M", "24M", "36M"}

    # detect tenor columns in template sheet3 header row2
    header_row = 2
    tenor_cols: dict[str, int] = {}
    for c in range(1, template_ws.max_column + 1):
        v = template_ws.cell(header_row, c).value
        if isinstance(v, str) and v.strip() in tenor_set:
            tenor_cols[v.strip()] = c

    if not tenor_cols:
        raise RuntimeError("Cannot detect tenor columns in template Sheet3")

    # detect tenor columns in market board (row2)
    market_header_row = 2
    market_tenor_cols: dict[str, int] = {}
    if is_new_market_board_layout(market_board_ws):
        for c in range(1, market_board_ws.max_column + 1):
            v = market_board_ws.cell(1, c).value
            if isinstance(v, str):
                m = re.fullmatch(r"(7D|\d+M)_pct", v.strip())
                if m and m.group(1) in tenor_set:
                    market_tenor_cols[m.group(1)] = c
    else:
        for c in range(1, market_board_ws.max_column + 1):
            v = market_board_ws.cell(market_header_row, c).value
            if isinstance(v, str) and v.strip() in tenor_set:
                market_tenor_cols[v.strip()] = c

    if set(tenor_cols.keys()) - set(market_tenor_cols.keys()):
        missing = set(tenor_cols.keys()) - set(market_tenor_cols.keys())
        raise RuntimeError(f"Market board missing tenors for Sheet3: {sorted(missing)}")

    # Collect market rows by bank (for fuzzy amount matching)
    board_layout = get_market_board_layout(market_board_ws)
    market_rows_by_bank: dict[str, list[int]] = {}
    for r in range(int(board_layout["data_start_row"]), market_board_ws.max_row + 1):
        bank_v = get_effective_cell_value(market_board_ws, r, int(board_layout["bank_col"]))
        amt_v = get_effective_cell_value(market_board_ws, r, int(board_layout["amount_col"]))
        if not isinstance(bank_v, str) or not bank_v.strip():
            continue
        if not isinstance(amt_v, str) or not amt_v.strip():
            continue
        b = canonical_bank_name(bank_v)
        market_rows_by_bank.setdefault(b, []).append(r)

    # Fill template
    for r in range(1, template_ws.max_row + 1):
        bank_v = get_effective_cell_value(template_ws, r, 1)
        amt_v = get_effective_cell_value(template_ws, r, 2)
        if not isinstance(bank_v, str) or not bank_v.strip():
            continue
        if not isinstance(amt_v, str) or not amt_v.strip():
            continue

        b = canonical_bank_name(bank_v)
        candidates = market_rows_by_bank.get(b, [])
        if not candidates:
            continue

        best_mr = None
        best_sc = -1
        for mr in candidates:
            market_amt_v = get_effective_cell_value(market_board_ws, mr, int(board_layout["amount_col"]))
            sc = score_amount_match(amt_v, market_amt_v)
            if sc <= 0:
                continue
            if sc > best_sc:
                best_sc = sc
                best_mr = mr

        if best_mr is None:
            continue

        for tk, tc in tenor_cols.items():
            mv = market_board_ws.cell(best_mr, market_tenor_cols[tk]).value
            dec = market_value_to_decimal(mv, percent_unit=bool(board_layout["percent_unit"]))
            if dec is None:
                template_ws.cell(r, tc).value = mv
            else:
                template_ws.cell(r, tc).value = float(dec)

    # Re-apply colors only to tenor columns that are numeric rates
    for r in range(1, template_ws.max_row + 1):
        for tk, tc in tenor_cols.items():
            cell = template_ws.cell(r, tc)
            dec = maybe_parse_rate_to_decimal(cell.value)
            if dec is None:
                continue
            cell.fill = FILL_BY_NAME[rate_to_color(dec)]


def verify_sheet3_matrix(template_ws, market_board_ws) -> None:
    sheet_name = getattr(template_ws, "title", "Sheet3")
    tenor_set = {"7D", "1M", "3M", "6M", "9M", "12M", "18M", "24M", "36M"}
    header_row = 2
    tenor_cols: dict[str, int] = {}
    for c in range(1, template_ws.max_column + 1):
        v = template_ws.cell(header_row, c).value
        if isinstance(v, str) and v.strip() in tenor_set:
            tenor_cols[v.strip()] = c
    if not tenor_cols:
        raise RuntimeError("Cannot detect tenor columns in template Sheet3")

    market_header_row = 2
    market_tenor_cols: dict[str, int] = {}
    if is_new_market_board_layout(market_board_ws):
        for c in range(1, market_board_ws.max_column + 1):
            v = market_board_ws.cell(1, c).value
            if isinstance(v, str):
                m = re.fullmatch(r"(7D|\d+M)_pct", v.strip())
                if m and m.group(1) in tenor_set:
                    market_tenor_cols[m.group(1)] = c
    else:
        for c in range(1, market_board_ws.max_column + 1):
            v = market_board_ws.cell(market_header_row, c).value
            if isinstance(v, str) and v.strip() in tenor_set:
                market_tenor_cols[v.strip()] = c

    board_layout = get_market_board_layout(market_board_ws)
    market_rows_by_bank: dict[str, list[int]] = {}
    for r in range(int(board_layout["data_start_row"]), market_board_ws.max_row + 1):
        bank_v = get_effective_cell_value(market_board_ws, r, int(board_layout["bank_col"]))
        amt_v = get_effective_cell_value(market_board_ws, r, int(board_layout["amount_col"]))
        if not isinstance(bank_v, str) or not bank_v.strip():
            continue
        if not isinstance(amt_v, str) or not amt_v.strip():
            continue
        market_rows_by_bank.setdefault(canonical_bank_name(bank_v), []).append(r)

    mismatches: list[dict[str, Any]] = []
    tol = 1e-15
    for r in range(1, template_ws.max_row + 1):
        bank_v = get_effective_cell_value(template_ws, r, 1)
        amt_v = get_effective_cell_value(template_ws, r, 2)
        if not isinstance(bank_v, str) or not bank_v.strip():
            continue
        if not isinstance(amt_v, str) or not amt_v.strip():
            continue

        b = canonical_bank_name(bank_v)
        candidates = market_rows_by_bank.get(b, [])
        if not candidates:
            continue

        best_mr = None
        best_sc = -1
        for mr in candidates:
            market_amt_v = get_effective_cell_value(market_board_ws, mr, int(board_layout["amount_col"]))
            sc = score_amount_match(amt_v, market_amt_v)
            if sc <= 0:
                continue
            if sc > best_sc:
                best_sc = sc
                best_mr = mr
        if best_mr is None:
            continue

        for tk, tc in tenor_cols.items():
            tv = template_ws.cell(r, tc).value
            mv = market_board_ws.cell(best_mr, market_tenor_cols[tk]).value
            dec_t = maybe_parse_rate_to_decimal(tv)
            dec_m = market_value_to_decimal(mv, percent_unit=bool(board_layout["percent_unit"]))

            if dec_t is None and dec_m is None:
                continue
            if dec_t is None or dec_m is None:
                mismatches.append(
                    {
                        "row": r,
                        "col": tc,
                        "期限": tk,
                        "bank": bank_v.strip(),
                        "amount": amt_v,
                        "异常": "模板与市场一侧能解析为利率、另一侧不能",
                        "模板值": tv,
                        "市场值": mv,
                    }
                )
                continue
            if abs(float(dec_t) - float(dec_m)) > tol:
                mismatches.append(
                    {
                        "row": r,
                        "col": tc,
                        "期限": tk,
                        "bank": bank_v.strip(),
                        "amount": amt_v,
                        "异常": "利率数值与市场不一致",
                        "期望利率": float(dec_m),
                        "模板利率": float(dec_t),
                    }
                )

    if mismatches:
        raise_verification_error(sheet_name, "Sheet3 矩阵与 SGD 挂牌表对账", mismatches)


def verify_sgd_board(template_ws, market_board_ws) -> None:
    """
    严格验证 `SGD Board Rate`：每个模板写入的利率单元格，都必须能在 market 中用同逻辑找到对应值。
    """
    sheet_name = getattr(template_ws, "title", "SGD Board Rate")
    header_row = 5
    tenor_blocks = detect_template_sgd_board_tenor_blocks(template_ws, header_row)
    market_tenor_col = build_market_tenor_col_map(market_board_ws)
    board_layout = get_market_board_layout(market_board_ws)
    skip_unmatched_in_new_layout = bool(board_layout["is_new"])

    market_bank_col = int(board_layout["bank_col"])
    market_amount_col = int(board_layout["amount_col"])

    tol = 1e-15
    mismatches: list[dict[str, Any]] = []

    def resolve_rate_amount_cols(r: int, rate_col_guess: int, amount_col_guess: int) -> tuple[int, int]:
        v_rate_guess = maybe_parse_rate_to_decimal(get_effective_cell_value(template_ws, r, rate_col_guess))
        v_amt_guess = get_effective_cell_value(template_ws, r, amount_col_guess)
        v_amt_guess_is_rate = maybe_parse_rate_to_decimal(v_amt_guess) is not None
        if v_rate_guess is not None and not v_amt_guess_is_rate:
            return rate_col_guess, amount_col_guess
        if v_rate_guess is None and v_amt_guess_is_rate:
            return amount_col_guess, rate_col_guess
        return rate_col_guess, amount_col_guess

    for tk, (bank_col, rate_col_guess, amount_col_guess) in tenor_blocks.items():
        m_col = market_tenor_col.get(tk)
        if not m_col:
            continue
        row_start = header_row + 1
        for r in range(row_start, template_ws.max_row + 1):
            bank_name = get_effective_cell_value(template_ws, r, bank_col)
            rate_col, amount_col = resolve_rate_amount_cols(r, rate_col_guess, amount_col_guess)
            rate_out = get_effective_cell_value(template_ws, r, rate_col)
            amt = get_effective_cell_value(template_ws, r, amount_col)

            if not isinstance(bank_name, str) or not bank_name.strip():
                continue
            if not isinstance(rate_out, (int, float)):
                continue
            if amt is None:
                continue

            mr = find_best_market_row_for_bank_amount(
                market_board_ws=market_board_ws,
                bank_col=market_bank_col,
                amount_col=market_amount_col,
                bank_name=bank_name,
                template_amount=amt,
            )
            if mr is None:
                if skip_unmatched_in_new_layout:
                    continue
                mismatches.append(
                    {
                        "期限": tk,
                        "row": r,
                        "rate_col": rate_col,
                        "bank": bank_name.strip(),
                        "amount": amt,
                        "异常": "按 Bank+Amount 未能在市场表找到匹配行（档位得分<=0）",
                        "模板利率": rate_out,
                    }
                )
                continue
            exp_val = market_value_to_decimal(
                market_board_ws.cell(mr, m_col).value,
                percent_unit=bool(board_layout["percent_unit"]),
            )
            if exp_val is None:
                if skip_unmatched_in_new_layout:
                    continue
                mismatches.append(
                    {
                        "期限": tk,
                        "row": r,
                        "bank": bank_name.strip(),
                        "amount": amt,
                        "异常": "市场表对应单元格无法解析为利率",
                        "模板利率": rate_out,
                        "市场原始值": market_board_ws.cell(mr, m_col).value,
                    }
                )
                continue
            if abs(float(rate_out) - float(exp_val)) > tol:
                mismatches.append(
                    {
                        "期限": tk,
                        "row": r,
                        "rate_col": rate_col,
                        "bank": bank_name.strip(),
                        "amount": amt,
                        "异常": "模板利率与市场不一致",
                        "期望利率": float(exp_val),
                        "模板利率": float(rate_out),
                    }
                )

    if mismatches:
        raise_verification_error(sheet_name, "SGD Board Rate 与 SGD 挂牌表对账", mismatches)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="MarketRateData11.xlsx", help="市场调研表路径(Excel)")
    ap.add_argument("--template", default="*20260311*.xlsx", help="彩虹表模板(通配符)")
    ap.add_argument("--asof", default=None, help="目标日期(YYYYMMDD 或 YYYY-MM-DD)。默认取 market 最新列")
    ap.add_argument("--out", default=None, help="输出文件名(默认按 asof 自动生成)")
    args = ap.parse_args()

    work_dir = os.path.dirname(os.path.abspath(__file__))
    market_path = os.path.join(work_dir, args.market)
    if not os.path.exists(market_path):
        raise FileNotFoundError(market_path)

    # template resolve
    if "*" in args.template or "?" in args.template:
        candidates = sorted(glob.glob(os.path.join(work_dir, args.template)))
        if not candidates:
            raise FileNotFoundError(f"No template matches {args.template!r}")
        template_path = candidates[0]
    else:
        template_path = os.path.join(work_dir, args.template)
    if not os.path.exists(template_path):
        raise FileNotFoundError(template_path)

    target_date = asof_to_date(args.asof) if args.asof else None

    if args.out:
        out_path = os.path.join(work_dir, args.out)
    else:
        suffix = target_date.strftime("%Y%m%d") if target_date else dt.date.today().strftime("%Y%m%d")
        out_path = os.path.join(work_dir, f"彩虹表_自动生成_{suffix}.xlsx")
        # 不覆盖
        if os.path.exists(out_path):
            i = 1
            base, ext = os.path.splitext(out_path)
            while True:
                cand = f"{base}_{i}{ext}"
                if not os.path.exists(cand):
                    out_path = cand
                    break
                i += 1

    shutil.copyfile(template_path, out_path)

    market_wb = load_workbook(market_path, data_only=True)
    template_wb = load_workbook(out_path)

    sheets = find_market_sheets(market_wb)
    # template sheet titles
    sgd_promo_ws = template_wb["SGD Promotional Rate"]
    sgd_board_ws = template_wb["SGD Board Rate"]
    sgd_ranked_ws = template_wb["SGD Board Rate Ranked"]

    # 1) SGD Promotional
    chosen_asof = update_sgd_promotional_rate(sgd_promo_ws, sheets.promo_ws, target_date)

    # 2) SGD Board + Ranked
    update_sgd_board_rate(sgd_board_ws, sheets.board_ws, chosen_asof)
    update_sgd_board_ranked(sgd_ranked_ws, sheets.board_ws, chosen_asof)

    # 2.5) SGD Board Matrix (Sheet3)
    if "Sheet3" not in template_wb.sheetnames:
        raise RuntimeError(
            "彩虹表模板缺少工作表 'Sheet3'（银行×期限矩阵）。请使用包含 Sheet3 的模板后再运行。"
        )
    sheet3_ws = template_wb["Sheet3"]
    update_sheet3_matrix(sheet3_ws, sheets.board_ws)

    # 3) 全部更新后再逐项校验（失败时 RainbowVerificationError 会标明 sheet / 行 / 原因）
    verify_sgd_promotional_rate(sgd_promo_ws, sheets.promo_ws, target_date)
    verify_sgd_board(sgd_board_ws, sheets.board_ws)
    verify_sgd_board_ranked(sgd_ranked_ws, sheets.board_ws)
    verify_sheet3_matrix(sheet3_ws, sheets.board_ws)

    # 4) save
    template_wb.save(out_path)
    print(f"Generated: {out_path}")


if __name__ == "__main__":
    main()

