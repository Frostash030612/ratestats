#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""选链评估汇总表（按 dest / 仅 baseline 失败）。"""
from __future__ import annotations

import pandas as pd


def _dest_category(dest: str) -> str:
    if "api" in dest:
        return "api"
    if "board" in dest:
        return "board"
    if "pdf" in dest or dest.endswith("_pdf"):
        return "pdf"
    if "promo" in dest or dest in ("url",):
        return "promo"
    return "other"


def summarize_overall(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "baseline_hit" not in df.columns:
        return pd.DataFrame([{"note": "无评估数据"}])
    return pd.DataFrame(
        [
            {"metric": "baseline_hit_rate", "value": df["baseline_hit"].mean()},
            {"metric": "ml_hit_rate", "value": df["ml_hit"].mean()},
            {
                "metric": "ml_improved_rows",
                "value": int(((df["ml_hit"] == 1) & (df["baseline_hit"] == 0)).sum()),
            },
            {
                "metric": "ml_regressed_rows",
                "value": int(((df["ml_hit"] == 0) & (df["baseline_hit"] == 1)).sum()),
            },
            {"metric": "n_rows", "value": len(df)},
        ]
    )


def summarize_by_dest(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "dest" not in df.columns:
        return pd.DataFrame()
    rows: list[dict] = []
    for dest, sub in df.groupby("dest"):
        row = {
            "dest": dest,
            "dest_category": _dest_category(dest),
            "n": len(sub),
            "baseline_hit_rate": sub["baseline_hit"].mean(),
            "ml_hit_rate": sub["ml_hit"].mean(),
            "ml_improved": int(((sub["ml_hit"] == 1) & (sub["baseline_hit"] == 0)).sum()),
            "ml_regressed": int(((sub["ml_hit"] == 0) & (sub["baseline_hit"] == 1)).sum()),
        }
        if "gold_rank_in_candidates" in sub.columns:
            row["gold_in_candidates_pct"] = (sub["gold_rank_in_candidates"].fillna(99) <= 5).mean()
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["baseline_hit_rate", "dest"])


def summarize_baseline_misses(df: pd.DataFrame) -> pd.DataFrame:
    """仅 baseline 未命中、用于优先加规则/样本的 dest。"""
    if df.empty:
        return pd.DataFrame()
    by = summarize_by_dest(df)
    if by.empty:
        return by
    return by[by["baseline_hit_rate"] < 1.0].sort_values("baseline_hit_rate")


def summarize_by_category(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "dest" not in df.columns:
        return pd.DataFrame()
    tmp = df.copy()
    tmp["dest_category"] = tmp["dest"].map(_dest_category)
    return (
        tmp.groupby("dest_category", as_index=False)
        .agg(
            n=("dest", "count"),
            baseline_hit_rate=("baseline_hit", "mean"),
            ml_hit_rate=("ml_hit", "mean"),
        )
        .sort_values("dest_category")
    )
