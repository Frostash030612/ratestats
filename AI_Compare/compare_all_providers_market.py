#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量对比：手动 Market vs 各 AI provider 的 Market 输出，并汇总一张总表。"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

_THIS = Path(__file__).resolve().parent
if str(_THIS) not in sys.path:
    sys.path.insert(0, str(_THIS))

from compare_market_data import run_compare  # noqa: E402

DEFAULT_MANUAL = _THIS.parent / "RateStats_Portable" / "20260518" / "MarketRateData_20260518_17.32.xlsx"
DEFAULT_AI_DIR = _THIS.parent / "RateStats_Portable" / "20260519"
DEFAULT_AI_GLOB = "MarketRateData_20260519_14.28_*.xlsx"

PROVIDER_FROM_NAME = (
    ("AISearch", "Vertex_AISearch"),
    ("_Vertex_", "Vertex"),
    ("Vertex", "Vertex"),
    ("Serper", "Serper"),
    ("Brave", "Brave"),
    ("Tavily", "Tavily"),
)


def _provider_label(ai_path: Path) -> str:
    """从 Market 文件名推断 provider 显示名（Vertex/Serper/Brave 等）。"""
    name = ai_path.stem
    for key, label in PROVIDER_FROM_NAME:
        if key in name:
            return label
    return ai_path.stem


def main() -> int:
    """CLI：对 ai-dir 下多个 AI Market 各跑 run_compare，汇总 market_compare_all_providers_*.xlsx。"""
    ap = argparse.ArgumentParser(description="批量对比手动 Market vs 多家 AI Market")
    ap.add_argument("--manual", default=str(DEFAULT_MANUAL))
    ap.add_argument("--ai-dir", default=str(DEFAULT_AI_DIR))
    ap.add_argument("--ai-glob", default=DEFAULT_AI_GLOB)
    ap.add_argument(
        "--exclude-name-substr",
        default="manual",
        help="文件名（不含路径）包含该子串则跳过对比，默认排除手动 Market（如 *manual*）",
    )
    ap.add_argument("--out-dir", default=str(_THIS / "results"))
    ap.add_argument("--tol", type=float, default=0.011)
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    manual = Path(args.manual)
    ai_dir = Path(args.ai_dir)
    out_dir = Path(args.out_dir)

    if not manual.is_file():
        print(f"[ERROR] 手动基准不存在: {manual}", file=sys.stderr)
        return 1

    raw = sorted(ai_dir.glob(args.ai_glob))
    ex = (args.exclude_name_substr or "").strip().lower()
    ai_files = [p for p in raw if not ex or ex not in p.name.lower()]
    if not raw:
        print(f"[ERROR] 未找到匹配文件: {ai_dir / args.ai_glob}", file=sys.stderr)
        return 1
    if not ai_files:
        print(
            f"[ERROR] glob 匹配 {len(raw)} 个文件，但均被 --exclude-name-substr={ex!r} 排除",
            file=sys.stderr,
        )
        return 1

    ts = datetime.now().strftime("%Y%m%d_%H.%M")
    batch_dir = out_dir / f"market_compare_batch_{ts}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    summaries: list[dict] = []
    url_diff_counts: list[dict] = []
    report_paths: list[tuple[str, Path]] = []

    print(f"手动基准: {manual}")
    print(f"AI 文件数: {len(ai_files)}\n")

    for ai_path in ai_files:
        provider = _provider_label(ai_path)
        print(f"--- {provider} ---")
        print(f"  AI: {ai_path.name}")
        provider_dir = batch_dir / provider
        provider_dir.mkdir(parents=True, exist_ok=True)
        try:
            out_path = run_compare(manual, ai_path, provider_dir, tol=args.tol)
        except Exception as e:
            print(f"  [FAIL] {e}")
            summaries.append({"provider": provider, "ai_file": ai_path.name, "error": str(e)})
            continue

        report_paths.append((provider, out_path))
        df_sum = pd.read_excel(out_path, sheet_name="summary")
        for _, row in df_sum.iterrows():
            summaries.append(
                {
                    "provider": provider,
                    "ai_file": ai_path.name,
                    "sheet": row.get("sheet", ""),
                    "manual_rows": row.get("manual_rows", ""),
                    "ai_rows": row.get("ai_rows", ""),
                    "match_rows": row.get("match_rows", ""),
                    "rate_mismatch_rows": row.get("rate_mismatch_rows", ""),
                    "only_manual_rows": row.get("only_manual_rows", ""),
                    "only_ai_rows": row.get("only_ai_rows", ""),
                }
            )

        try:
            df_url = pd.read_excel(out_path, sheet_name="url_diff")
            url_diff_counts.append(
                {
                    "provider": provider,
                    "url_diff_rows": len(df_url),
                    "exact_match": int((df_url.get("match", pd.Series()) == "exact").sum())
                    if "match" in df_url.columns and len(df_url)
                    else "",
                }
            )
        except Exception:
            url_diff_counts.append({"provider": provider, "url_diff_rows": 0})

        print()

    # 汇总 Excel
    master = batch_dir / f"market_compare_all_providers_{ts}.xlsx"
    with pd.ExcelWriter(master, engine="openpyxl") as w:
        pd.DataFrame(summaries).to_excel(w, index=False, sheet_name="summary_by_provider")
        if url_diff_counts:
            pd.DataFrame(url_diff_counts).to_excel(w, index=False, sheet_name="url_diff_stats")
        pd.DataFrame(
            [{"provider": p, "detail_report": str(r)} for p, r in report_paths]
        ).to_excel(w, index=False, sheet_name="reports")

        # 各 provider 的 summary 横向透视（仅三大主 sheet）
        df_all = pd.DataFrame(summaries)
        if not df_all.empty and "sheet" in df_all.columns:
            for metric in (
                "match_rows",
                "only_manual_rows",
                "rate_mismatch_rows",
                "ai_rows",
                "manual_rows",
            ):
                if metric not in df_all.columns:
                    continue
                pivot = df_all.pivot_table(
                    index="sheet",
                    columns="provider",
                    values=metric,
                    aggfunc="first",
                )
                pivot.to_excel(w, sheet_name=f"pivot_{metric}"[:31])

    print("=" * 60)
    print(f"[汇总] {master}")
    if summaries:
        df_p = pd.DataFrame(summaries)
        show = df_p.groupby("provider")[
            ["match_rows", "only_manual_rows", "rate_mismatch_rows"]
        ].sum(numeric_only=True)
        print("\n各 provider 合计（含三主表 + 挂牌_* 全部 sheet）:")
        print(show.to_string())
    print(f"\n明细报告目录: {batch_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
