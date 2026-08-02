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
from sklearn.utils.class_weight import compute_sample_weight

from _portable import DATA_DIR, DEFAULT_MANUAL_XLSX, MODEL_DIR
from dataset import (
    build_full_training_rows,
    iter_discovery_reports,
    load_discovery_report_rows,
    load_gold_manual,
    rows_with_features,
    save_dataset_csv,
)
from features import FEATURE_NAMES
from ml_discovery_dirs import default_discovery_dirs

MODEL_FILE = MODEL_DIR / "url_ranker.joblib"
META_FILE = MODEL_DIR / "url_ranker_meta.json"


def _build_Xy(
    manual_xlsx: Path,
    *,
    use_discovery: bool,
    use_hard_negatives: bool,
    drop_rule_score: bool,
    discovery_dirs: list[Path] | None,
) -> tuple[np.ndarray, np.ndarray, list[dict], tuple[str, ...]]:
    gold = load_gold_manual(manual_xlsx)
    rows = build_full_training_rows(gold, use_hard_negatives=use_hard_negatives)
    if use_discovery:
        for p in iter_discovery_reports(discovery_dirs):
            try:
                rows.extend(load_discovery_report_rows(p))
            except Exception as e:
                print(f"[WARN] skip {p}: {e}")
    X, y, meta, names = rows_with_features(rows, drop_rule_score=drop_rule_score)
    return np.array(X, dtype=np.float64), np.array(y, dtype=np.int32), meta, names


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="训练 ML 选链模型（标签=手动 url_params）")
    ap.add_argument("--manual", default=str(DEFAULT_MANUAL_XLSX), help="手动黄金 url_params.xlsx")
    ap.add_argument(
        "--use-discovery",
        action="store_true",
        help="并入 runs/ 下的发现报告候选",
    )
    ap.add_argument(
        "--no-hard-negatives",
        action="store_true",
        help="不加入典型错链负样本（OCBC premier、DBS API 等）",
    )
    ap.add_argument(
        "--drop-rule-score",
        action="store_true",
        help="训练时不使用 rule_score 特征（减轻「只复制规则」）",
    )
    ap.add_argument("--cv", type=int, default=5, help="交叉验证折数")
    args = ap.parse_args(argv)

    manual = Path(args.manual)
    X, y, meta, feature_names = _build_Xy(
        manual,
        use_discovery=args.use_discovery,
        use_hard_negatives=not args.no_hard_negatives,
        drop_rule_score=args.drop_rule_score,
        discovery_dirs=default_discovery_dirs(),
    )
    if len(y) < 20 or len(set(y)) < 2:
        print("[ERROR] 样本过少或缺少正负类", file=__import__("sys").stderr)
        return 1

    save_dataset_csv(
        [
            {
                "dest": m["dest"],
                "url": m["url"],
                "label": m["label"],
                "reference_url": m["reference_url"],
                "candidate_rank": m.get("candidate_rank", 0),
                "sample_type": m.get("sample_type", ""),
            }
            for m in meta
        ],
        DATA_DIR / "training_set_latest.csv",
    )

    sample_w = compute_sample_weight("balanced", y)
    clf = HistGradientBoostingClassifier(
        max_depth=6,
        learning_rate=0.08,
        max_iter=200,
        random_state=42,
    )

    cv_folds = min(args.cv, 5, max(2, int((y == 1).sum())))
    cv_scores = cross_val_score(clf, X, y, cv=cv_folds, scoring="roc_auc")
    print(f"[CV] ROC-AUC mean={cv_scores.mean():.4f} std={cv_scores.std():.4f}")

    y_prob = cross_val_predict(clf, X, y, cv=cv_folds, method="predict_proba")[:, 1]
    try:
        print(f"[CV] ROC-AUC (OOF) = {roc_auc_score(y, y_prob):.4f}")
    except ValueError:
        pass

    clf.fit(X, y, sample_weight=sample_w)
    y_hat = clf.predict(X)
    print(classification_report(y, y_hat, digits=3))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": clf, "feature_names": list(feature_names)}, MODEL_FILE)

    meta_out = {
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "manual_xlsx": str(manual.resolve()),
        "n_samples": int(len(y)),
        "n_positive": int((y == 1).sum()),
        "n_negative": int((y == 0).sum()),
        "feature_names": list(feature_names),
        "cv_roc_auc_mean": float(cv_scores.mean()),
        "model_type": "HistGradientBoostingClassifier",
        "use_discovery": args.use_discovery,
        "use_hard_negatives": not args.no_hard_negatives,
        "drop_rule_score": args.drop_rule_score,
        "class_weight": "balanced",
    }
    META_FILE.write_text(json.dumps(meta_out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] 模型: {MODEL_FILE}")
    print(f"[OK] 元数据: {META_FILE}")
    print(f"[OK] 训练集导出: {DATA_DIR / 'training_set_latest.csv'}")
    print(f"[OK] 特征数: {len(feature_names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
