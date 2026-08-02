#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一轮对比：规则 Vertex 配置 vs ML 配置 vs 手动（链接 + Market）。"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from _portable import AI_COMPARE_DIR, ASSETS_DIR, DEFAULT_MANUAL_XLSX, ML_ROOT, OUTPUT_DIR, PORTABLE_DIR, RUNS_ROOT, _SRC
from dataset import load_gold_manual
from evaluate_picker import evaluate_on_discovery_reports, _candidates_from_row
from picker import pick_best_url_ml
from project_paths import find_latest_url_params_ai, parse_run_date_tag

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(AI_COMPARE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_COMPARE_DIR))

from compare_market_data import run_compare  # noqa: E402
from eval_metrics import normalize_url  # noqa: E402
from url_config_loader import load_url_config  # noqa: E402
from url_discovery_pick import pick_best_url  # noqa: E402
from url_fallback_resolver import build_fallback_map  # noqa: E402
from url_key_aliases import URL_PARAM_DEST_KEYS  # noqa: E402


def compare_url_configs(manual: dict[str, str], ml_cfg: dict[str, str], rule_cfg: dict[str, str]) -> pd.DataFrame:
    rows = []
    for dest in sorted(URL_PARAM_DEST_KEYS):
        mu = manual.get(dest, "")
        mlu = ml_cfg.get(dest, "")
        ru = rule_cfg.get(dest, "")
        rows.append(
            {
                "dest": dest,
                "manual_url": mu[:100],
                "ml_url": mlu[:100],
                "rule_vertex_url": ru[:100],
                "ml_eq_manual": int(normalize_url(mlu) == normalize_url(mu)) if mu and mlu else "",
                "rule_eq_manual": int(normalize_url(ru) == normalize_url(mu)) if mu and ru else "",
                "ml_eq_rule": int(normalize_url(mlu) == normalize_url(ru)) if mlu and ru else "",
            }
        )
    return pd.DataFrame(rows)


def compare_picks_on_ml_report(report: Path, gold: dict[str, str]) -> pd.DataFrame:
    df = pd.read_excel(report)
    fb = build_fallback_map(str(DEFAULT_MANUAL_XLSX))
    rows = []
    for _, row in df.iterrows():
        dest = str(row.get("dest", "") or "").strip()
        if dest not in gold:
            continue
        ref = gold[dest]
        cands = _candidates_from_row(row)
        if not cands:
            continue
        b_url, _ = pick_best_url(cands, dest, fb.get(dest, ""))
        ml_url, ml_src = pick_best_url_ml(cands, dest, fb.get(dest, ""))
        picked = str(row.get("url", "") or "")
        rows.append(
            {
                "dest": dest,
                "gold_hit_baseline": int(normalize_url(b_url) == normalize_url(ref)),
                "gold_hit_ml": int(normalize_url(ml_url) == normalize_url(ref)),
                "ml_run_picked_eq_gold": int(normalize_url(picked) == normalize_url(ref)),
                "baseline_pick": b_url[:80],
                "ml_pick": ml_url[:80],
                "ml_run_url": picked[:80],
                "ml_source": ml_src,
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="run_vertex_ml_discovery 的 run-tag")
    ap.add_argument("--manual-market", default=None, help="手动 Market xlsx；默认在 runs/ 下自动查找最新 *_manual*.xlsx")
    args = ap.parse_args()

    tag = args.tag
    run_dir = RUNS_ROOT / tag
    if not run_dir.is_dir():
        run_dir = OUTPUT_DIR / tag
    ml_report = run_dir / f"ai_search_discovered_ml_{tag}.xlsx"
    ml_cfg_path = run_dir / "url_params_ai_ml.xlsx"
    ml_market = run_dir / f"MarketRateData_{tag}_ML.xlsx"
    if not ml_market.is_file():
        found = sorted(run_dir.glob(f"MarketRateData_{tag}_ML*.xlsx"), reverse=True)
        ml_market = found[0] if found else ml_market
    rule_cfg_path = find_latest_url_params_ai() or (ASSETS_DIR / "url_params_ai.xlsx")

    if not ml_report.is_file():
        print(f"[ERROR] 缺少 {ml_report}", file=sys.stderr)
        return 1

    gold = load_gold_manual()
    manual_cfg = gold
    ml_cfg = load_url_config(str(ml_cfg_path)) if ml_cfg_path.is_file() else {}
    rule_cfg = load_url_config(str(rule_cfg_path)) if rule_cfg_path.is_file() else {}

    date_tag = parse_run_date_tag(tag) or datetime.now().strftime("%Y%m%d")
    compare_dir = RUNS_ROOT / date_tag / "ml_compare" / f"compare_{tag}"
    compare_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H.%M")
    out = compare_dir / f"ml_vs_manual_{ts}.xlsx"

    with pd.ExcelWriter(out, engine="openpyxl") as w:
        compare_url_configs(manual_cfg, ml_cfg, rule_cfg).to_excel(w, index=False, sheet_name="url_config")
        compare_picks_on_ml_report(ml_report, gold).to_excel(w, index=False, sheet_name="pick_on_candidates")

        df_pick = compare_picks_on_ml_report(ml_report, gold)
        if not df_pick.empty:
            pd.DataFrame(
                [
                    {"metric": "baseline_hit_rate", "value": df_pick["gold_hit_baseline"].mean()},
                    {"metric": "ml_hit_rate", "value": df_pick["gold_hit_ml"].mean()},
                    {"metric": "ml_run_hit_rate", "value": df_pick["ml_run_picked_eq_gold"].mean()},
                    {
                        "metric": "ml_better_than_baseline",
                        "value": int(
                            ((df_pick["gold_hit_ml"] == 1) & (df_pick["gold_hit_baseline"] == 0)).sum()
                        ),
                    },
                ]
            ).to_excel(w, index=False, sheet_name="pick_summary")

        manual_market = Path(args.manual_market) if args.manual_market else None
        if manual_market is None or not manual_market.is_file():
            found = sorted(RUNS_ROOT.rglob("MarketRateData_*_manual*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
            manual_market = found[0] if found else None
        if manual_market and manual_market.is_file() and ml_market.is_file():
            mkt_out = compare_dir / f"market_compare_{ts}.xlsx"
            run_compare(manual_market, ml_market, compare_dir, tol=0.011)
            # run_compare creates market_data_compare_{ts}.xlsx in compare_dir
            for p in sorted(compare_dir.glob("market_data_compare_*.xlsx"), reverse=True):
                df = pd.read_excel(p, sheet_name="summary")
                df.insert(0, "compare_type", "manual_vs_ml_market")
                df.to_excel(w, index=False, sheet_name="market_summary")
                break
        else:
            pd.DataFrame(
                [{"note": f"缺少 manual={manual_market} 或 ml={ml_market}"}]
            ).to_excel(w, index=False, sheet_name="market_summary")

    print(f"[OK] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
