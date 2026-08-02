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
from picker_config import PickerTuning, load_picker_tuning

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


def ml_score(
    url: str,
    dest: str,
    *,
    reference_url: str = "",
    candidate_rank: int = 0,
    model_path: Path | None = None,
) -> float:
    """模型 P(正类=黄金链)；无模型时返回 0.5。"""
    pack = load_ranker(model_path)
    if not pack:
        return 0.5
    clf = pack["model"]
    names = tuple(pack.get("feature_names") or FEATURE_NAMES)
    drop_rs = "rule_score" not in names
    x = np.array(
        [
            feature_vector(
                url,
                dest,
                reference_url=reference_url,
                candidate_rank=candidate_rank,
                drop_rule_score=drop_rs,
            )
        ]
    )
    proba = clf.predict_proba(x)[0, 1]
    return float(proba)


def _rule_margin(pool: list[str], rule_scores: list[int]) -> float:
    if len(rule_scores) < 2:
        return 1.0
    ordered = sorted(rule_scores, reverse=True)
    span = (ordered[0] - ordered[-1]) or 1
    return (ordered[0] - ordered[1]) / span


def pick_best_url_ml(
    candidates: list[str],
    dest: str,
    fallback: str,
    *,
    blend_rule_weight: float | None = None,
    min_ml_proba: float | None = None,
    model_path: Path | None = None,
    tuning: PickerTuning | None = None,
) -> tuple[str, str]:
    """
    ML + 规则融合选链。

    参数未显式传入时读取 models/picker_tuning.json（由 tune_picker.py 生成）。
    """
    from url_discovery_pick import pick_best_url, score_url  # noqa: E402
    from url_host_rules import url_matches_dest  # noqa: E402
    from url_dest_intent import url_hard_reject  # noqa: E402

    cfg = tuning or load_picker_tuning()
    blend = blend_rule_weight if blend_rule_weight is not None else cfg.blend_rule_weight
    min_p = min_ml_proba if min_ml_proba is not None else cfg.min_ml_proba

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

    rule_scores = [score_url(u, dest, reference_url=fallback) for u in pool]
    margin = _rule_margin(pool, rule_scores)

    if cfg.use_ambiguous_gate and margin >= cfg.ambiguous_rule_margin:
        url, src = pick_best_url(candidates, dest, fallback)
        return url, ("ml_skip_clear_rule_" + src) if src == "ai" else src

    scored: list[tuple[str, float, float]] = []
    r_min, r_max = min(rule_scores), max(rule_scores)
    r_span = (r_max - r_min) or 1.0

    for rank, (u, rs) in enumerate(zip(pool, rule_scores)):
        if url_hard_reject(dest, u):
            continue
        ml_p = ml_score(u, dest, reference_url=fallback, candidate_rank=rank, model_path=model_path)
        rule_norm = (rs - r_min) / r_span
        combined = blend * rule_norm + (1.0 - blend) * ml_p
        scored.append((u, combined, ml_p))

    if not scored:
        url, src = pick_best_url(candidates, dest, fallback)
        return url, ("ml_fallback_" + src) if src.startswith("fallback") else "ml_" + src

    scored.sort(key=lambda x: (-x[1], x[0]))
    best_url, _best_combined, best_ml = scored[0]

    if best_ml < min_p and fallback:
        url, src = pick_best_url(candidates, dest, fallback)
        if src == "ai":
            return url, "ml_low_confidence_rule_ai"
        return fallback, "ml_low_confidence_fallback"

    return best_url, "ml_pick"
