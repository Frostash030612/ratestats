#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计 AI 流程：链接错误、抓取失败、数据缺失/不一致。"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

_PORTABLE = Path(__file__).resolve().parent.parent / "RateStats_Portable"
_SRC = _PORTABLE / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from project_paths import ASSETS_DIR  # noqa: E402

from export_market_url_snapshot import META_PROJECT_TO_DEST, dest_urls_from_market_meta
from url_config_loader import load_url_config
from url_host_rules import url_matches_dest
from url_key_aliases import URL_KEY_ALIASES, URL_PARAM_DEST_KEYS

SHEET_PROMO = "新元定存促销"
SHEET_BOARD = "新元挂牌利率"
SHEET_FX = "外币定存促销"


def _norm_host(url: str) -> str:
    """提取 URL 主机名（小写）。"""
    return (urlparse(url).netloc or "").lower()


def _same_url(a: str, b: str) -> bool:
    """忽略 query 与尾部斜杠，判断两 URL 是否同一页。"""
    return a.split("?")[0].rstrip("/") == b.split("?")[0].rstrip("/")


def audit_urls(manual_xlsx: Path, ai_xlsx: Path, ai_cfg: Path) -> pd.DataFrame:
    """对比手动与 AI 的 dest→URL：空链、错域名、错行、同银行不同页。"""
    manual = load_url_config(str(manual_xlsx)) if manual_xlsx.suffix == ".xlsx" else {}
    if not manual:
        manual = load_url_config(str(ASSETS_DIR / "url_params.json"))
    ai = load_url_config(str(ai_cfg))
    meta_m = dest_urls_from_market_meta(manual_xlsx) if manual_xlsx.is_file() else {}
    meta_a = dest_urls_from_market_meta(ai_xlsx) if ai_xlsx.is_file() else {}

    rows = []
    for dest in sorted(URL_PARAM_DEST_KEYS):
        mu = manual.get(dest, "") or meta_m.get(dest, "")
        au = ai.get(dest, "") or meta_a.get(dest, "")
        issue = []
        if not au:
            issue.append("AI链接为空")
        elif not url_matches_dest(dest, au):
            issue.append("AI链接域名错行")
        elif mu and not _same_url(mu, au):
            if _norm_host(mu) != _norm_host(au):
                issue.append("链接错行")
            else:
                issue.append("同银行不同页")
        if not issue:
            continue
        rows.append(
            {
                "dest": dest,
                "key": next((k for k, d in URL_KEY_ALIASES.items() if d == dest), dest),
                "manual_url": mu[:120],
                "ai_url": au[:120],
                "issue_type": "; ".join(issue),
            }
        )
    return pd.DataFrame(rows)


def _meta_errors(xlsx: Path) -> list[dict]:
    """从 Market 元数据 sheet 提取「抓取失败」等错误行。"""
    out = []
    if not xlsx.is_file():
        return out
    meta = pd.read_excel(xlsx, sheet_name=0)
    c0, c1 = meta.columns[0], meta.columns[1]
    for _, r in meta.iterrows():
        lab = str(r[c0]).strip()
        val = str(r[c1]).strip() if pd.notna(r[c1]) else ""
        if "抓取失败" in val or (val.startswith("抓取失败")):
            out.append({"项目": lab, "错误": val[:200]})
        if "失败" in lab and val:
            out.append({"项目": lab, "错误": val[:200]})
    return out


def _banks_in_sheet(xlsx: Path, sheet: str) -> set[str]:
    """读取某 sheet 第一列出现的银行名集合。"""
    if not xlsx.is_file():
        return set()
    try:
        df = pd.read_excel(xlsx, sheet_name=sheet)
    except Exception:
        return set()
    if df.empty:
        return set()
    return {str(x).strip() for x in df.iloc[:, 0].dropna().unique()}


def _count_rows_by_bank(xlsx: Path, sheet: str) -> dict[str, int]:
    """按银行统计某 sheet 的数据行数。"""
    if not xlsx.is_file():
        return {}
    try:
        df = pd.read_excel(xlsx, sheet_name=sheet)
    except Exception:
        return {}
    if df.empty:
        return {}
    col = df.columns[0]
    return df.groupby(df[col].astype(str).str.strip()).size().to_dict()


def audit_data_gaps(manual_xlsx: Path, ai_xlsx: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """返回 (整行缺失银行, 行数差异)。"""
    missing = []
    for sheet in (SHEET_PROMO, SHEET_BOARD, SHEET_FX):
        bm = _banks_in_sheet(manual_xlsx, sheet)
        ba = _banks_in_sheet(ai_xlsx, sheet)
        for b in sorted(bm - ba):
            missing.append({"sheet": sheet, "bank": b, "issue": "AI表无此银行数据"})
        for b in sorted(ba - bm):
            missing.append({"sheet": sheet, "bank": b, "issue": "仅AI有(手动无)"})

    diff_rows = []
    for sheet in (SHEET_PROMO, SHEET_BOARD, SHEET_FX):
        cm = _count_rows_by_bank(manual_xlsx, sheet)
        ca = _count_rows_by_bank(ai_xlsx, sheet)
        for b in sorted(set(cm) | set(ca)):
            nm, na = cm.get(b, 0), ca.get(b, 0)
            if nm != na:
                diff_rows.append(
                    {
                        "sheet": sheet,
                        "bank": b,
                        "manual_rows": nm,
                        "ai_rows": na,
                        "delta": na - nm,
                    }
                )
    return pd.DataFrame(missing), pd.DataFrame(diff_rows)


def _read_discovery_report() -> pd.DataFrame | None:
    """读取 runs/ 下最新 ai_search_discovered_*.xlsx。"""
    from project_paths import RUNS_ROOT

    latest: Path | None = None
    latest_mtime = 0.0
    if not RUNS_ROOT.is_dir():
        return None
    for p in RUNS_ROOT.rglob("ai_search_discovered_*.xlsx"):
        mt = p.stat().st_mtime
        if mt > latest_mtime:
            latest_mtime = mt
            latest = p
    if latest is None:
        return None
    return pd.read_excel(latest)


def main() -> int:
    """CLI：汇总链接问题、元数据抓取失败、缺行/行数差、发现报告。"""
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--manual",
        default=str(_PORTABLE / "20260518" / "MarketRateData_20260518_17.32.xlsx"),
    )
    ap.add_argument(
        "--ai",
        default=str(_PORTABLE / "20260518" / "MarketRateData_20260518_17.32_AISearch.xlsx"),
    )
    from project_paths import audit_out_dir, find_latest_url_params_ai

    default_ai_cfg = find_latest_url_params_ai() or (ASSETS_DIR / "url_params_ai.xlsx")
    ap.add_argument("--ai-cfg", default=str(default_ai_cfg))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    manual_p = Path(args.manual)
    ai_p = Path(args.ai)
    ai_cfg = Path(args.ai_cfg)
    out_dir = Path(args.out) if args.out else audit_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    sys.stdout.reconfigure(encoding="utf-8")

    print("=== 1. 链接问题 (url_params / 元数据) ===")
    df_url = audit_urls(
        ASSETS_DIR / "url_params.xlsx",
        ai_p,
        ai_cfg,
    )
    if not df_url.empty:
        print(df_url.to_string(index=False))
    else:
        print("(无)")

    print("\n=== 2. AI 元数据抓取失败 ===")
    errs = _meta_errors(ai_p)
    if errs:
        for e in errs:
            print(f"  - {e['项目']}: {e['错误'][:120]}")
    else:
        print("(无显式抓取失败行)")

    print("\n=== 3. 整银行缺失 (对比手动 Market) ===")
    df_miss, df_delta = audit_data_gaps(manual_p, ai_p)
    if not df_miss.empty:
        print(df_miss.to_string(index=False))
    else:
        print("(无整银行缺失)")

    print("\n=== 4. 同银行行数差异 (可能少解析产品档) ===")
    if not df_delta.empty:
        print(df_delta[df_delta["delta"] != 0].to_string(index=False))
    else:
        print("(无)")

    disc = _read_discovery_report()
    if disc is not None:
        print("\n=== 5. Vertex 发现来源 (非 vertex 或 fallback) ===")
        sub = disc[disc["source"].astype(str).str.contains("fallback", na=False)]
        if not sub.empty:
            print(sub[["dest", "source", "url"]].head(20).to_string(index=False))
            if len(sub) > 20:
                print(f"  ... 共 {len(sub)} 条 fallback")

    ts = pd.Timestamp.now().strftime("%Y%m%d_%H.%M")
    out = out_dir / f"ai_issues_audit_{ts}.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df_url.to_excel(w, index=False, sheet_name="url_issues")
        pd.DataFrame(errs).to_excel(w, index=False, sheet_name="fetch_errors")
        df_miss.to_excel(w, index=False, sheet_name="bank_missing")
        df_delta.to_excel(w, index=False, sheet_name="row_count_diff")
        if disc is not None:
            disc.to_excel(w, index=False, sheet_name="vertex_discovery")
    print(f"\n[OK] 报告: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
