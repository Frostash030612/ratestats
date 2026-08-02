#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在发现报告上网格搜索 blend_rule_weight / min_ml_proba，写入 models/picker_tuning.json。"""
from __future__ import annotations

import argparse
import itertools
from datetime import datetime
from pathlib import Path

import pandas as pd

from _portable import DEFAULT_MANUAL_XLSX, MODEL_DIR, OUTPUT_DIR
from dataset import load_gold_manual
from eval_summaries import summarize_overall
from evaluate_picker import _candidates_from_row
from ml_discovery_dirs import default_discovery_dirs, iter_discovery_reports
from picker import pick_best_url_ml
from picker_config import PickerTuning, save_picker_tuning

if str(Path(__file__).resolve().parent.parent / "RateStats_Portable") not in __import__("sys").path:
    pass

import sys

from _portable import PORTABLE_DIR

if str(PORTABLE_DIR) not in sys.path:
    sys.path.insert(0, str(PORTABLE_DIR))

from eval_metrics import normalize_url  # noqa: E402
from url_discovery_pick import pick_best_url  # noqa: E402
from url_fallback_resolver import build_fallback_map  # noqa: E402


def _eval_params(
    report_paths: list[Path],
    gold: dict[str, str],
    *,
    blend: float,
    min_p: float,
    use_gate: bool,
    margin: float,
) -> dict[str, float]:
    fb_map = build_fallback_map(str(DEFAULT_MANUAL_XLSX))
    tuning = PickerTuning(
        blend_rule_weight=blend,
        min_ml_proba=min_p,
        use_ambiguous_gate=use_gate,
        ambiguous_rule_margin=margin,
    )
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
            fb = fb_map.get(dest, ref)
            base_url, _ = pick_best_url(cands, dest, fb)
            ml_url, _ = pick_best_url_ml(cands, dest, fb, tuning=tuning)
            rows.append(
                {
                    "baseline_hit": int(normalize_url(base_url) == normalize_url(ref)),
                    "ml_hit": int(normalize_url(ml_url) == normalize_url(ref)),
                }
            )
    if not rows:
        return {"baseline_hit_rate": 0.0, "ml_hit_rate": 0.0, "ml_improved": 0.0, "ml_regressed": 0.0}
    d = pd.DataFrame(rows)
    return {
        "baseline_hit_rate": float(d["baseline_hit"].mean()),
        "ml_hit_rate": float(d["ml_hit"].mean()),
        "ml_improved": float(((d["ml_hit"] == 1) & (d["baseline_hit"] == 0)).sum()),
        "ml_regressed": float(((d["ml_hit"] == 0) & (d["baseline_hit"] == 1)).sum()),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="网格搜索 ML 融合参数")
    ap.add_argument("--manual", default=str(DEFAULT_MANUAL_XLSX))
    ap.add_argument(
        "--blend-grid",
        default="0.15,0.22,0.28,0.35,0.45",
        help="逗号分隔 blend_rule_weight",
    )
    ap.add_argument(
        "--min-proba-grid",
        default="0.12,0.18,0.25,0.32",
        help="逗号分隔 min_ml_proba",
    )
    ap.add_argument("--ambiguous-margin", type=float, default=0.12)
    ap.add_argument("--no-ambiguous-gate", action="store_true")
    args = ap.parse_args(argv)

    if not (MODEL_DIR / "url_ranker.joblib").is_file():
        print("[ERROR] 请先运行 train.py", file=sys.stderr)
        return 1

    gold = load_gold_manual(Path(args.manual))
    reports = list(iter_discovery_reports(default_discovery_dirs()))
    if not reports:
        print("[ERROR] 未找到发现报告", file=sys.stderr)
        return 1

    blends = [float(x) for x in args.blend_grid.split(",") if x.strip()]
    min_ps = [float(x) for x in args.min_proba_grid.split(",") if x.strip()]
    use_gate = not args.no_ambiguous_gate

    grid_rows = []
    best = None
    best_score = -1.0

    for blend, min_p in itertools.product(blends, min_ps):
        m = _eval_params(
            reports,
            gold,
            blend=blend,
            min_p=min_p,
            use_gate=use_gate,
            margin=args.ambiguous_margin,
        )
        # 优先提高 ml_hit，其次减少 ml_regressed
        score = m["ml_hit_rate"] * 1000 - m["ml_regressed"] * 5 + m["ml_improved"] * 2
        row = {"blend_rule_weight": blend, "min_ml_proba": min_p, "score": score, **m}
        grid_rows.append(row)
        if score > best_score:
            best_score = score
            best = (blend, min_p, m)

    assert best is not None
    tuning = PickerTuning(
        blend_rule_weight=best[0],
        min_ml_proba=best[1],
        use_ambiguous_gate=use_gate,
        ambiguous_rule_margin=args.ambiguous_margin,
    )
    out_json = save_picker_tuning(tuning)

    from project_paths import ml_eval_dir

    out_dir = ml_eval_dir()
    ts = datetime.now().strftime("%Y%m%d_%H.%M")
    out_xlsx = out_dir / f"picker_tune_{ts}.xlsx"
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as w:
        pd.DataFrame(grid_rows).sort_values("score", ascending=False).to_excel(
            w, index=False, sheet_name="grid"
        )
        from evaluate_picker import evaluate_on_discovery_reports

        df_ref = evaluate_on_discovery_reports(reports, gold)
        summarize_overall(df_ref).to_excel(w, index=False, sheet_name="baseline_on_reports")
        pd.DataFrame([{"key": k, "value": v} for k, v in tuning.__dict__.items()]).to_excel(
            w, index=False, sheet_name="best_params"
        )

    print(f"[BEST] blend={best[0]} min_proba={best[1]} ml_hit={best[2]['ml_hit_rate']:.4f}")
    print(f"[OK] {out_json}")
    print(f"[OK] {out_xlsx}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
