#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""训练集：以手动 url_params 为黄金标签，构造正/负样本。"""
from __future__ import annotations

import random
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pandas as pd

from _portable import DEFAULT_MANUAL_XLSX, DATA_DIR, PORTABLE_DIR
from features import extract_features, FEATURE_NAMES
from hard_negatives import build_hard_negative_rows
from ml_discovery_dirs import iter_discovery_reports

# 触发 Portable imports
import sys

if str(PORTABLE_DIR) not in sys.path:
    sys.path.insert(0, str(PORTABLE_DIR))

from url_config_loader import load_url_config  # noqa: E402
from url_key_aliases import URL_PARAM_DEST_KEYS  # noqa: E402


def load_gold_manual(path: Path | None = None) -> dict[str, str]:
    """dest -> 手动维护的黄金 URL。"""
    p = path or DEFAULT_MANUAL_XLSX
    cfg = load_url_config(str(p))
    return {d: cfg[d] for d in URL_PARAM_DEST_KEYS if cfg.get(d, "").strip()}


def _mutate_path(url: str, rng: random.Random) -> str:
    """生成看似同银行但路径错误的负样本。"""
    p = urlparse(url)
    path = p.path or "/"
    variants = [
        path + "/promotions",
        path.replace("fixed-deposit", "savings"),
        "/en/personal-banking/deposits",
        path + "/help/faqs",
        "/business-banking",
    ]
    new_path = rng.choice(variants)
    return urlunparse((p.scheme, p.netloc, new_path, p.params, p.query, ""))


def build_training_rows(
    gold: dict[str, str],
    *,
    negatives_per_dest: int = 8,
    seed: int = 42,
) -> list[dict]:
    """
    每个 dest：
      - 正样本：黄金 URL
      - 负样本：其它 dest 的黄金 URL + 路径扰动
    """
    rng = random.Random(seed)
    dests = sorted(gold.keys())
    all_gold_urls = list(gold.values())
    rows: list[dict] = []

    for dest in dests:
        ref = gold[dest]
        if not ref.startswith("http"):
            continue

        # positive
        rows.append(
            {
                "dest": dest,
                "url": ref,
                "label": 1,
                "reference_url": ref,
                "candidate_rank": 0,
                "sample_type": "gold_positive",
            }
        )

        negs: set[str] = set()
        # 其它 dest 的 URL（硬负样本）
        for other in dests:
            if other == dest:
                continue
            u = gold[other]
            if u.startswith("http"):
                negs.add(u)

        # 路径扰动
        for _ in range(4):
            negs.add(_mutate_path(ref, rng))

        # 随机补足
        while len(negs) < negatives_per_dest and all_gold_urls:
            negs.add(rng.choice(all_gold_urls))

        for i, u in enumerate(list(negs)[:negatives_per_dest]):
            if u == ref:
                continue
            rows.append(
                {
                    "dest": dest,
                    "url": u,
                    "label": 0,
                    "reference_url": ref,
                    "candidate_rank": i + 1,
                    "sample_type": "negative",
                }
            )

    return rows


def build_full_training_rows(
    gold: dict[str, str],
    *,
    use_hard_negatives: bool = True,
    negatives_per_dest: int = 8,
    seed: int = 42,
) -> list[dict]:
    """黄金正负样本 + 可选典型错链负样本。"""
    rows = build_training_rows(gold, negatives_per_dest=negatives_per_dest, seed=seed)
    if use_hard_negatives:
        rows.extend(build_hard_negative_rows(gold))
    return rows


def rows_with_features(
    rows: list[dict],
    *,
    drop_rule_score: bool = False,
) -> tuple[list[list[float]], list[int], list[dict], tuple[str, ...]]:
    from features import active_feature_names

    names = active_feature_names(drop_rule_score=drop_rule_score)
    X, y, meta = [], [], []
    for r in rows:
        feats = extract_features(
            r["url"],
            r["dest"],
            reference_url=r["reference_url"],
            candidate_rank=int(r.get("candidate_rank", 0)),
        )
        X.append([feats[k] for k in names])
        y.append(int(r["label"]))
        meta.append(r)
    return X, y, meta, names


def load_discovery_report_rows(path: Path) -> list[dict]:
    """从 ai_search_discovered_*.xlsx 解析候选，用同目录手动黄金打标签。"""
    df = pd.read_excel(path)
    gold = load_gold_manual()
    rows: list[dict] = []
    for _, row in df.iterrows():
        dest = str(row.get("dest", "") or "").strip()
        if dest not in gold:
            continue
        ref = gold[dest]
        raw = str(row.get("candidates_top5", "") or "")
        candidates = [c.strip() for c in raw.split("|") if c.strip().startswith("http")]
        if not candidates:
            picked = str(row.get("url", "") or "").strip()
            if picked.startswith("http"):
                candidates = [picked]
        for rank, u in enumerate(candidates):
            from eval_metrics import normalize_url  # noqa: E402

            label = 1 if normalize_url(u) == normalize_url(ref) else 0
            rows.append(
                {
                    "dest": dest,
                    "url": u,
                    "label": label,
                    "reference_url": ref,
                    "candidate_rank": rank,
                    "sample_type": "discovery_candidate",
                    "report": path.name,
                }
            )
    return rows


def save_dataset_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flat = []
    for r in rows:
        feats = extract_features(
            r["url"], r["dest"], reference_url=r["reference_url"], candidate_rank=r.get("candidate_rank", 0)
        )
        flat.append({**{k: r[k] for k in ("dest", "url", "label", "sample_type")}, **feats})
    pd.DataFrame(flat).to_csv(path, index=False, encoding="utf-8-sig")
