"""pick_best_url 前对候选做 dest 级处理。严格模式可过滤；宽松模式仅保留硬约束。"""
from __future__ import annotations

from typing import Union

from url_dest_intent import url_hard_reject, url_meets_dest_intent
from url_discovery_config import is_relaxed_mode

Ranked = list[tuple[str, int]]
EarlyReturn = tuple[str, str]
RefineResult = Union[Ranked, EarlyReturn]


def refine_ranked_candidates_strict(dest: str, ranked: Ranked, fallback: str) -> RefineResult:
    """严格：过滤不符合路径意图的候选；无候选则回退。"""
    if ranked:
        ranked = [(u, s) for u, s in ranked if url_meets_dest_intent(dest, u)]

    if not ranked and fallback:
        if url_meets_dest_intent(dest, fallback):
            return fallback, f"fallback_{dest}_intent"
        return fallback, f"fallback_{dest}_empty"

    if dest == "dbs_fcy_board_api_url":
        api = [
            (u, s)
            for u, s in ranked
            if "sg-rates-api" in u.lower() and "getsgfcfdrates" in u.lower().replace("-", "")
        ]
        if api:
            return api
        if fallback and "sg-rates-api" in fallback.lower():
            return fallback, "fallback_dbs_fcy_api_required"

    if dest in ("maybank_board_url", "maybank_fcy_board_url"):
        jsp = [
            (u, s)
            for u, s in ranked
            if "sslsecure.maybank.com.sg" in u.lower() and "deposit_rate.jsp" in u.lower()
        ]
        if jsp:
            return jsp
        if fallback and "sslsecure.maybank.com.sg" in fallback.lower():
            return fallback, "fallback_maybank_sslsecure_required"

    if dest == "ocbc_board_url":
        personal = [(u, s) for u, s in ranked if "sgd-fixed-deposit-interest" in u.lower()]
        if personal:
            return personal
        if fallback and "sgd-fixed-deposit-interest" in fallback.lower():
            return fallback, "fallback_ocbc_sgd_board_page"

    if dest == "hsbc_url" and fallback and "zh-sg" in fallback.lower():
        zh = [(u, s) for u, s in ranked if "zh-sg" in u.lower() and "time-deposit" in u.lower()]
        if zh:
            return zh
        if ranked and "zh-sg" not in ranked[0][0].lower():
            return fallback, "fallback_hsbc_zh_sg"

    if dest == "bea_sgd_promo_url" and fallback and "index.html" in fallback.lower():
        idx = [(u, s) for u, s in ranked if "index.html" in u.lower()]
        if idx:
            return idx
        if ranked and "index.html" not in ranked[0][0].lower():
            return fallback, "fallback_bea_index"

    return ranked


def refine_ranked_candidates_relaxed(dest: str, ranked: Ranked, fallback: str) -> RefineResult:
    """宽松：不滤掉候选；仅当第一名硬拒绝时尝试次优或回退。"""
    if not ranked:
        if fallback:
            return fallback, f"fallback_{dest}_empty"
        return ranked

    cleaned = [(u, s) for u, s in ranked if not url_hard_reject(dest, u)]
    if cleaned:
        return cleaned
    if fallback and not url_hard_reject(dest, fallback):
        return fallback, f"fallback_{dest}_hard_reject"
    return ranked


def refine_ranked_candidates(dest: str, ranked: Ranked, fallback: str) -> RefineResult:
    """按当前 intent 模式分发到 strict 或 relaxed 精炼逻辑。"""
    if is_relaxed_mode():
        return refine_ranked_candidates_relaxed(dest, ranked, fallback)
    return refine_ranked_candidates_strict(dest, ranked, fallback)
