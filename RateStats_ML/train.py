#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用手动 url_params 训练 URL 排序模型（不修改旧方案）。"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import cross_val_predict, cross_val_score

from _portable import DATA_DIR, DEFAULT_MANUAL_XLSX, MODEL_DIR, PORTABLE_DIR
from dataset import (
    build_training_rows,
    iter_discovery_reports,
    load_discovery_report_rows,
    load_gold_manual,
    rows_with_features,
    save_dataset_csv,
)
from features import FEATURE_NAMES

MODEL_FILE = MODEL_DIR / "url_ranker.joblib"
META_FILE = MODEL_DIR / "url_ranker_meta.json"


def _build_Xy(
    manual_xlsx: Path,
    *,
    use_discovery: bool,
    discovery_dirs: list[Path],
) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    gold = load_gold_manual(manual_xlsx)
    rows = build_training_rows(gold)
    if use_discovery:
        for p in iter_discovery_reports(discovery_dirs):
            try:
                rows.extend(load_discovery_report_rows(p))
            except Exception as e:
                print(f"[WARN] skip {p}: {e}")
    X, y, meta = rows_with_features(rows)
    return np.array(X, dtype=np.float64), np.array(y, dtype=np.int32), meta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="训练 ML 选链模型（标签=手动 url_params）")
    ap.add_argument("--manual", default=str(DEFAULT_MANUAL_XLSX), help="手动黄金 url_params.xlsx")
    ap.add_argument(
        "--use-discovery",
        action="store_true",
        help="额外并入 Portable/assets 与 AI_Compare/output 下的发现报告候选",
    )
    ap.add_argument("--cv", type=int, default=5, help="交叉验证折数")
    args = ap.parse_args(argv)

    manual = Path(args.manual)
    discovery_dirs = [
        PORTABLE_DIR / "assets",
        PORTABLE_DIR.parent / "AI_Compare" / "output",
    ]
    X, y, meta = _build_Xy(manual, use_discovery=args.use_discovery, discovery_dirs=discovery_dirs)
    if len(y) < 20 or len(set(y)) < 2:
        print("[ERROR] 样本过少或缺少正负类", file=__import__("sys").stderr)
        return 1

    save_dataset_csv(
        [{"dest": m["dest"], "url": m["url"], "label": m["label"], "reference_url": m["reference_url"],
          "candidate_rank": m.get("candidate_rank", 0), "sample_type": m.get("sample_type", "")} for m in meta],
        DATA_DIR / "training_set_latest.csv",
    )

    clf = HistGradientBoostingClassifier(
        max_depth=6,
        learning_rate=0.08,
        max_iter=200,
        random_state=42,
    )

    cv_scores = cross_val_score(clf, X, y, cv=min(args.cv, 5), scoring="roc_auc")
    print(f"[CV] ROC-AUC mean={cv_scores.mean():.4f} std={cv_scores.std():.4f}")

    y_prob = cross_val_predict(clf, X, y, cv=min(args.cv, 5), method="predict_proba")[:, 1]
    try:
        print(f"[CV] ROC-AUC (OOF) = {roc_auc_score(y, y_prob):.4f}")
    except ValueError:
        pass

    clf.fit(X, y)
    y_hat = clf.predict(X)
    print(classification_report(y, y_hat, digits=3))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": clf, "feature_names": list(FEATURE_NAMES)}, MODEL_FILE)

    meta_out = {
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "manual_xlsx": str(manual.resolve()),
        "n_samples": int(len(y)),
        "n_positive": int((y == 1).sum()),
        "n_negative": int((y == 0).sum()),
        "feature_names": list(FEATURE_NAMES),
        "cv_roc_auc_mean": float(cv_scores.mean()),
        "model_type": "HistGradientBoostingClassifier",
    }
    META_FILE.write_text(json.dumps(meta_out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] 模型: {MODEL_FILE}")
    print(f"[OK] 元数据: {META_FILE}")
    print(f"[OK] 训练集导出: {DATA_DIR / 'training_set_latest.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
