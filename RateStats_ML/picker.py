#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ML 增强选链：在规则 pick_best_url 基础上用训练模型对候选重排序。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import joblib
import numpy as np

from _portable import MODEL_DIR
from features import FEATURE_NAMES, feature_vector

MODEL_FILE = MODEL_DIR / "url_ranker.joblib"

_model_cache: Optional[dict] = None


def load_ranker(path: Path | None = None) -> Optional[dict]:
    """加载 joblib 模型包；不存在则返回 None（回退纯规则）。"""
    global _model_cache
    p = path or MODEL_FILE
    if _model_cache is not None and _model_cache.get("_path") == str(p.resolve()):
        return _model_cache
    if not p.is_file():
        return None
    pack = joblib.load(p)
    pack["_path"] = str(p.resolve())
    _model_cache = pack
    return pack


def ml_score(url: str, dest: str, *, reference_url: str = "", candidate_rank: int = 0) -> float:
    """模型 P(正类=黄金链)；无模型时返回 0.5。"""
    pack = load_ranker()
    if not pack:
        return 0.5
    clf = pack["model"]
    x = np.array([feature_vector(url, dest, reference_url=reference_url, candidate_rank=candidate_rank)])
    proba = clf.predict_proba(x)[0, 1]
    return float(proba)


def pick_best_url_ml(
    candidates: list[str],
    dest: str,
    fallback: str,
    *,
    blend_rule_weight: float = 0.35,
    min_ml_proba: float = 0.25,
    model_path: Path | None = None,
) -> tuple[str, str]:
    """
    ML + 规则融合选链。

    - 先复用 Portable 的域名过滤与硬拒绝逻辑（通过 score_url + url_matches_dest）
    - 综合分 = blend_rule_weight * 规则分(归一化) + (1-blend) * ML概率
    - 无模型或候选为空 → 回退 url_discovery_pick.pick_best_url
    """
    from url_discovery_pick import pick_best_url, score_url  # noqa: E402
    from url_host_rules import url_matches_dest  # noqa: E402
    from url_dest_intent import url_hard_reject  # noqa: E402

    if model_path:
        global _model_cache
        _model_cache = None
        load_ranker(model_path)

    if not candidates:
        return pick_best_url(candidates, dest, fallback)

    pack = load_ranker(model_path)
    if not pack:
        url, src = pick_best_url(candidates, dest, fallback)
        return url, ("ml_" + src) if src == "ai" else src

    unique = list(dict.fromkeys(candidates))
    on_bank = [u for u in unique if url_matches_dest(dest, u)]
    pool = on_bank if on_bank else unique

    if not on_bank and fallback and url_matches_dest(dest, fallback):
        return fallback, "fallback_no_bank_host_in_results"

    scored: list[tuple[str, float, float]] = []
    rule_scores = [score_url(u, dest, reference_url=fallback) for u in pool]
    r_min, r_max = min(rule_scores), max(rule_scores)
    r_span = (r_max - r_min) or 1.0

    for rank, (u, rs) in enumerate(zip(pool, rule_scores)):
        if url_hard_reject(dest, u):
            continue
        ml_p = ml_score(u, dest, reference_url=fallback, candidate_rank=rank)
        rule_norm = (rs - r_min) / r_span
        combined = blend_rule_weight * rule_norm + (1.0 - blend_rule_weight) * ml_p
        scored.append((u, combined, ml_p))

    if not scored:
        url, src = pick_best_url(candidates, dest, fallback)
        return url, ("ml_fallback_" + src) if src.startswith("fallback") else "ml_" + src

    scored.sort(key=lambda x: (-x[1], x[0]))
    best_url, best_combined, best_ml = scored[0]

    if best_ml < min_ml_proba and fallback:
        url, src = pick_best_url(candidates, dest, fallback)
        if src == "ai":
            return url, "ml_low_confidence_rule_ai"
        return fallback, "ml_low_confidence_fallback"

    # 与黄金路径极似时优先 ML 第一名
    return best_url, "ml_pick"
