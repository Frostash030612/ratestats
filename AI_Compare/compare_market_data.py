#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比手动 MarketRateData 与 *_AISearch 表中的实际利率数据。"""
from __future__ import annotations

import argparse
import math
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

_THIS = Path(__file__).resolve().parent
_PORTABLE = _THIS.parent / "RateStats_Portable"
if str(_PORTABLE) not in sys.path:
    sys.path.insert(0, str(_PORTABLE))

from export_market_url_snapshot import dest_urls_from_market_meta  # noqa: E402

# 与模板一致的数据 sheet（不含元数据、外币备注）
DATA_SHEETS = ("新元定存促销", "新元挂牌利率", "外币定存促销")
# 模板实际 sheet 名为 挂牌_USD、挂牌_EUR…（非 外币挂牌_）
FX_SHEET_PREFIX = "挂牌_"


def _pct_cols(df: pd.DataFrame) -> list[str]:
    """找出 DataFrame 中所有利率百分比列（列名以 _pct 结尾）。"""
    return [c for c in df.columns if str(c).endswith("_pct")]


def _row_key(row: pd.Series, key_cols: list[str]) -> str:
    """用非利率列拼成行唯一键，用于手动/AI 行对齐。"""
    parts = []
    for c in key_cols:
        v = row.get(c, "")
        if pd.isna(v):
            v = ""
        parts.append(str(v).strip())
    return " | ".join(parts)


def _norm_rate(v) -> float | None:
    """将单元格利率规范为 float（保留 4 位小数），无效则 None。"""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return None


def _rates_equal(a, b, tol: float = 0.011) -> bool:
    """判断两个利率是否在容差 tol（百分点）内相等。"""
    na, nb = _norm_rate(a), _norm_rate(b)
    if na is None and nb is None:
        return True
    if na is None or nb is None:
        return False
    return abs(na - nb) <= tol


def compare_sheet(
    df_m: pd.DataFrame,
    df_a: pd.DataFrame,
    sheet: str,
    *,
    tol: float,
) -> tuple[list[dict], dict]:
    """返回 (detail_rows, summary_stats)。"""
    if df_m.empty and df_a.empty:
        return [], {"sheet": sheet, "status": "both_empty"}

    key_cols = [str(c) for c in df_m.columns if not str(c).endswith("_pct") and "原文" not in str(c)][:4]
    if not key_cols:
        key_cols = [str(df_m.columns[0])]

    pct_cols = sorted(set(_pct_cols(df_m)) | set(_pct_cols(df_a)))
    m_map = {_row_key(r, key_cols): r for _, r in df_m.iterrows()}
    a_map = {_row_key(r, key_cols): r for _, r in df_a.iterrows()}
    all_keys = sorted(set(m_map) | set(a_map))

    detail: list[dict] = []
    match_rows = only_m = only_a = mismatch_rows = 0

    for k in all_keys:
        rm, ra = m_map.get(k), a_map.get(k)
        if rm is not None and ra is None:
            only_m += 1
            detail.append(
                {
                    "sheet": sheet,
                    "row_key": k,
                    "status": "仅手动有",
                    "manual_source": rm.get(key_cols[0], ""),
                    "diff_cols": "",
                    "manual_vals": "",
                    "ai_vals": "",
                }
            )
            continue
        if ra is not None and rm is None:
            only_a += 1
            detail.append(
                {
                    "sheet": sheet,
                    "row_key": k,
                    "status": "仅AI有",
                    "manual_source": "",
                    "diff_cols": "",
                    "manual_vals": "",
                    "ai_vals": ra.get(key_cols[0], ""),
                }
            )
            continue

        diffs = []
        m_vals = []
        a_vals = []
        for c in pct_cols:
            vm, va = rm.get(c), ra.get(c)
            if not _rates_equal(vm, va, tol):
                diffs.append(c)
                m_vals.append(f"{c}={vm}")
                a_vals.append(f"{c}={va}")
        if diffs:
            mismatch_rows += 1
            detail.append(
                {
                    "sheet": sheet,
                    "row_key": k,
                    "status": "利率不一致",
                    "manual_source": rm.get(key_cols[0], ""),
                    "diff_cols": ", ".join(diffs),
                    "manual_vals": "; ".join(m_vals[:6]),
                    "ai_vals": "; ".join(a_vals[:6]),
                }
            )
        else:
            match_rows += 1

    summary = {
        "sheet": sheet,
        "manual_rows": len(m_map),
        "ai_rows": len(a_map),
        "match_rows": match_rows,
        "rate_mismatch_rows": mismatch_rows,
        "only_manual_rows": only_m,
        "only_ai_rows": only_a,
    }
    return detail, summary


def compare_metadata_urls(manual_xlsx: Path, ai_xlsx: Path) -> list[dict]:
    """对比两份 Market 元数据 sheet 中各 dest 的抓取 URL。"""
    from export_market_url_snapshot import META_PROJECT_TO_DEST
    from url_key_aliases import URL_KEY_ALIASES

    dm = dest_urls_from_market_meta(manual_xlsx)
    da = dest_urls_from_market_meta(ai_xlsx)
    dest_to_label = {}
    for proj, dest in META_PROJECT_TO_DEST.items():
        dest_to_label.setdefault(dest, proj)

    rows = []
    for dest in sorted(set(dm) | set(da)):
        mu, au = dm.get(dest, ""), da.get(dest, "")
        if not mu and not au:
            continue
        if mu.rstrip("/") == au.rstrip("/") or (mu and au and mu.split("?")[0] == au.split("?")[0]):
            st = "链接一致"
        elif mu and au:
            st = "链接不同"
        elif mu:
            st = "仅手动有链接"
        else:
            st = "仅AI有链接"
        rows.append(
            {
                "dest": dest,
                "meta_label": dest_to_label.get(dest, dest),
                "status": st,
                "manual_url": mu,
                "ai_url": au,
            }
        )
    return rows


def run_compare(manual_path: Path, ai_path: Path, out_dir: Path, *, tol: float = 0.011) -> Path:
    """对比手动与 AI 两份 Market：各 sheet 行对齐 + 利率差 + URL 差，写 Excel 报告。"""
    if not manual_path.is_file():
        raise FileNotFoundError(manual_path)
    if not ai_path.is_file():
        raise FileNotFoundError(ai_path)

    xl_m = pd.ExcelFile(manual_path)
    xl_a = pd.ExcelFile(ai_path)
    sheets_m = set(xl_m.sheet_names)
    sheets_a = set(xl_a.sheet_names)

    all_detail: list[dict] = []
    summaries: list[dict] = []

    for sheet in DATA_SHEETS:
        if sheet not in sheets_m and sheet not in sheets_a:
            continue
        df_m = pd.read_excel(manual_path, sheet_name=sheet) if sheet in sheets_m else pd.DataFrame()
        df_a = pd.read_excel(ai_path, sheet_name=sheet) if sheet in sheets_a else pd.DataFrame()
        d, s = compare_sheet(df_m, df_a, sheet, tol=tol)
        all_detail.extend(d)
        summaries.append(s)

    # 外币挂牌按币种
    fx_sheets = sorted(
        {s for s in sheets_m | sheets_a if str(s).startswith(FX_SHEET_PREFIX)}
    )
    for sheet in fx_sheets:
        df_m = pd.read_excel(manual_path, sheet_name=sheet) if sheet in sheets_m else pd.DataFrame()
        df_a = pd.read_excel(ai_path, sheet_name=sheet) if sheet in sheets_a else pd.DataFrame()
        d, s = compare_sheet(df_m, df_a, sheet, tol=tol)
        all_detail.extend(d)
        summaries.append(s)

    url_rows = compare_metadata_urls(manual_path, ai_path)
    only_in_m = sorted(sheets_m - sheets_a)
    only_in_a = sorted(sheets_a - sheets_m)

    ts = datetime.now().strftime("%Y%m%d_%H.%M")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"market_data_compare_{ts}.xlsx"

    df_sum = pd.DataFrame(summaries)
    df_detail = pd.DataFrame(all_detail)
    df_url = pd.DataFrame(url_rows)
    df_extra = pd.DataFrame(
        [
            {"type": "仅手动有的sheet", "name": s} for s in only_in_m
        ]
        + [{"type": "仅AI有的sheet", "name": s} for s in only_in_a]
    )

    with pd.ExcelWriter(out_path, engine="openpyxl") as w:
        df_sum.to_excel(w, index=False, sheet_name="summary")
        if not df_detail.empty:
            df_detail.to_excel(w, index=False, sheet_name="data_mismatch")
        if not df_url.empty:
            df_url.to_excel(w, index=False, sheet_name="url_diff")
        if not df_extra.empty:
            df_extra.to_excel(w, index=False, sheet_name="sheet_diff")

    print(f"[OK] {out_path}")
    if not df_sum.empty:
        print(df_sum.to_string(index=False))
    return out_path


def main() -> int:
    """CLI：--manual 与 --ai 两份 xlsx，输出 market_data_compare_*.xlsx。"""
    ap = argparse.ArgumentParser(description="对比手动 vs AISearch Market 数据")
    ap.add_argument("--manual", required=True)
    ap.add_argument("--ai", required=True)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--tol", type=float, default=0.011, help="利率容差（百分点）")
    args = ap.parse_args()
    out = Path(args.out_dir) if args.out_dir else _THIS / "results"
    try:
        run_compare(Path(args.manual), Path(args.ai), out, tol=args.tol)
        return 0
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
