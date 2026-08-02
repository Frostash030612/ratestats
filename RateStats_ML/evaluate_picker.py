#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评估：规则选链 vs ML 选链（以手动 url 为黄金标准）。"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from _portable import DEFAULT_MANUAL_XLSX, OUTPUT_DIR, PORTABLE_DIR
from dataset import load_gold_manual
from eval_summaries import (
    summarize_by_category,
    summarize_by_dest,
    summarize_baseline_misses,
    summarize_overall,
)
from ml_discovery_dirs import default_discovery_dirs, iter_discovery_reports
from picker import pick_best_url_ml

if str(PORTABLE_DIR) not in sys.path:
    sys.path.insert(0, str(PORTABLE_DIR))

from eval_metrics import normalize_url, picker_url_hit, rank_in_topn  # noqa: E402
from url_discovery_pick import pick_best_url  # noqa: E402
from url_fallback_resolver import build_fallback_map  # noqa: E402


def _candidates_from_row(row: pd.Series) -> list[str]:
    raw = str(row.get("candidates_top5", "") or "")
    cands = [c.strip() for c in raw.split("|") if c.strip().startswith("http")]
    picked = str(row.get("url", "") or "").strip()
    if picked.startswith("http") and picked not in cands:
        cands.insert(0, picked)
    return cands


def evaluate_on_discovery_reports(
    report_paths: list[Path],
    gold: dict[str, str],
) -> pd.DataFrame:
    fallback_map = build_fallback_map(str(DEFAULT_MANUAL_XLSX))
    rows = []

    for rp in report_paths:
        df = pd.read_excel(rp)
        for _, row in df.iterrows():
            dest = str(row.get("dest", "") or "").strip()
            if dest not in gold:
                continue
            ref = gold[dest]
            cands = _candidates_from_row(row)
            if not cands:
                continue
            fb = fallback_map.get(dest, ref)
            boc_companion = ""
            if dest in ("boc_url", "boc_board_url"):
                boc_companion = fallback_map.get(
                    "boc_board_url" if dest == "boc_url" else "boc_url",
                    "",
                )

            base_url, _ = pick_best_url(cands, dest, fb)
            ml_url, ml_src = pick_best_url_ml(cands, dest, fb)

            base_hit = picker_url_hit(
                dest, base_url, ref, candidates=cands, gold_companion=boc_companion
            )
            ml_hit = picker_url_hit(
                dest, ml_url, ref, candidates=cands, gold_companion=boc_companion
            )
            gold_rank = rank_in_topn(ref, cands)

            rows.append(
                {
                    "report": rp.name,
                    "dest": dest,
                    "gold_rank_in_candidates": gold_rank,
                    "baseline_hit": base_hit,
                    "ml_hit": ml_hit,
                    "baseline_picked": base_url[:120],
                    "ml_picked": ml_url[:120],
                    "ml_source": ml_src,
                    "n_candidates": len(cands),
                }
            )

    return pd.DataFrame(rows)


def evaluate_synthetic_live_search(
    gold: dict[str, str],
    *,
    provider: str = "vertex",
    limit: int | None = 10,
    sleep_sec: float = 0.4,
) -> pd.DataFrame:
    """对若干 dest 实时搜索，对比 baseline / ML 命中率。"""
    import time

    from url_key_aliases import URL_PARAM_DEST_KEYS  # noqa: E402

    try:
        from vertex_search_client import extract_links, search_url  # noqa: E402
    except ImportError:
        raise RuntimeError("需要 RateStats_Portable 与 Vertex 配置")

    try:
        from vertex_url_discovery import QUERY_BY_DEST  # noqa: E402
    except ImportError:
        QUERY_BY_DEST = {}

    fallback_map = build_fallback_map(str(DEFAULT_MANUAL_XLSX))
    dests = sorted(URL_PARAM_DEST_KEYS)
    if limit:
        dests = dests[:limit]

    rows = []
    for dest in dests:
        query = QUERY_BY_DEST.get(dest, f"singapore bank {dest} fixed deposit")
        ref = gold.get(dest, "")
        fb = fallback_map.get(dest, "")
        try:
            payload = search_url(query, page_size=8)
            cands = extract_links(payload)
        except Exception as e:
            cands = []
            rows.append({"dest": dest, "error": str(e)})
            continue

        boc_companion = ""
        if dest in ("boc_url", "boc_board_url"):
            boc_companion = fallback_map.get(
                "boc_board_url" if dest == "boc_url" else "boc_url",
                "",
            )
        base_url, _ = pick_best_url(cands, dest, fb)
        ml_url, ml_src = pick_best_url_ml(cands, dest, fb)
        rows.append(
            {
                "dest": dest,
                "query": query,
                "gold_rank_in_candidates": rank_in_topn(ref, cands),
                "baseline_hit": picker_url_hit(
                    dest, base_url, ref, candidates=cands, gold_companion=boc_companion
                ),
                "ml_hit": picker_url_hit(
                    dest, ml_url, ref, candidates=cands, gold_companion=boc_companion
                ),
                "ml_source": ml_src,
                "n_candidates": len(cands),
            }
        )
        time.sleep(sleep_sec)

    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="对比规则选链 vs ML 选链")
    ap.add_argument("--manual", default=str(DEFAULT_MANUAL_XLSX))
    ap.add_argument(
        "--reports-dir",
        default=None,
        help="额外发现报告目录（默认仅扫描 runs/）",
    )
    ap.add_argument("--live-search", action="store_true", help="额外对 Vertex 做实时搜索评估（较慢）")
    ap.add_argument("--live-limit", type=int, default=15)
    args = ap.parse_args(argv)

    gold = load_gold_manual(Path(args.manual))
    dirs = default_discovery_dirs()
    if args.reports_dir:
        dirs = [Path(args.reports_dir)] + dirs
    reports = list(iter_discovery_reports(dirs))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H.%M")
    from project_paths import ml_eval_dir

    out = ml_eval_dir() / f"picker_eval_{ts}.xlsx"

    with pd.ExcelWriter(out, engine="openpyxl") as w:
        if reports:
            df = evaluate_on_discovery_reports(reports, gold)
            df.to_excel(w, index=False, sheet_name="from_discovery_reports")
            if not df.empty:
                summarize_overall(df).to_excel(w, index=False, sheet_name="summary")
                summarize_by_dest(df).to_excel(w, index=False, sheet_name="by_dest")
                summarize_baseline_misses(df).to_excel(w, index=False, sheet_name="baseline_miss_dest")
                summarize_by_category(df).to_excel(w, index=False, sheet_name="by_category")
                print(summarize_overall(df).to_string(index=False))
                miss = summarize_baseline_misses(df)
                if not miss.empty:
                    print("\n[baseline 未满分 dest]")
                    print(miss.head(15).to_string(index=False))
        else:
            pd.DataFrame([{"note": "未找到 ai_search_discovered_*.xlsx"}]).to_excel(
                w, index=False, sheet_name="from_discovery_reports"
            )
            print("[WARN] 无发现报告，请先跑 AI 发现或指定 --reports-dir")

        if args.live_search:
            df_live = evaluate_synthetic_live_search(gold, limit=args.live_limit)
            df_live.to_excel(w, index=False, sheet_name="live_vertex_sample")
            if "baseline_hit" in df_live.columns:
                print("\n[Live Vertex sample]")
                print(f"  baseline hit@pick: {df_live['baseline_hit'].mean():.3f}")
                print(f"  ml hit@pick:       {df_live['ml_hit'].mean():.3f}")

    print(f"\n[OK] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
