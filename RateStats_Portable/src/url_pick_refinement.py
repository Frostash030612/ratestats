"""pick_best_url 前对候选做 dest 级处理。严格模式可过滤；宽松模式仅保留硬约束。"""
from __future__ import annotations

from typing import Union

from url_dest_intent import (
    is_bea_fcy_promo_form_url,
    is_boc_board_rate_page,
    is_boc_promo_rate_page,
    is_citi_all_promo_url,
    is_dbs_fcy_board_api_url,
    is_hl_sgd_board_page,
    is_ocbc_sgd_board_page,
    is_rhb_deposit_rates_board_pdf,
    url_hard_reject,
    url_meets_dest_intent,
)
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
        api = [(u, s) for u, s in ranked if is_dbs_fcy_board_api_url(u)]
        if api:
            return api
        if fallback and is_dbs_fcy_board_api_url(fallback):
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
        personal = [(u, s) for u, s in ranked if is_ocbc_sgd_board_page(u)]
        if personal:
            return personal
        if fallback and is_ocbc_sgd_board_page(fallback):
            return fallback, "fallback_ocbc_sgd_board_page"

    if dest == "hl_board_url":
        board = [(u, s) for u, s in ranked if is_hl_sgd_board_page(u)]
        if board:
            return board
        if fallback and is_hl_sgd_board_page(fallback):
            return fallback, "fallback_hl_sgd_board_page"

    if dest in ("rhb_board_pdf_url", "rhb_fcy_board_pdf_url"):
        pdf = [(u, s) for u, s in ranked if is_rhb_deposit_rates_board_pdf(u)]
        if pdf:
            return pdf
        if fallback and is_rhb_deposit_rates_board_pdf(fallback):
            return fallback, "fallback_rhb_board_pdf"

    if dest in ("boc_url", "boc_board_url"):
        from boc_url_resolve import boc_article_sort_key, pick_boc_url_for_dest

        valid = [
            (u, s)
            for u, s in ranked
            if (
                is_boc_promo_rate_page(u)
                if dest == "boc_url"
                else is_boc_board_rate_page(u)
            )
        ]
        if valid:
            valid.sort(key=lambda x: (-boc_article_sort_key(x[0])[0], -boc_article_sort_key(x[0])[1], x[0]))
            return valid
        picked, src = pick_boc_url_for_dest(
            dest,
            candidates=[u for u, _ in ranked],
            configured_url=fallback,
        )
        if picked:
            return picked, src
        if fallback:
            return fallback, (
                "fallback_boc_promo_page" if dest == "boc_url" else "fallback_boc_board_page"
            )

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

    if dest == "citi_all_promo_url":
        lid = [
            (u, s)
            for u, s in ranked
            if is_citi_all_promo_url(u) and "lid=" in u.lower()
        ]
        if lid:
            return lid
        promo = [(u, s) for u, s in ranked if is_citi_all_promo_url(u)]
        if promo:
            return promo
        if fallback and is_citi_all_promo_url(fallback):
            return fallback, "fallback_citi_all_promo"

    if dest == "url":
        fd = [
            (u, s)
            for u, s in ranked
            if "fixed-deposit-account" in u.lower() and "all-promo" not in u.lower()
        ]
        if fd:
            return fd
        if fallback and "fixed-deposit-account" in fallback.lower():
            return fallback, "fallback_citi_fd_account"

    if dest == "bea_fcy_promo_url":
        form = [(u, s) for u, s in ranked if is_bea_fcy_promo_form_url(u)]
        if form:
            return form
        if fallback and is_bea_fcy_promo_form_url(fallback):
            return fallback, "fallback_bea_fcy_form"

    return ranked


def refine_ranked_candidates_relaxed(dest: str, ranked: Ranked, fallback: str) -> RefineResult:
    """宽松：不滤掉候选；仅当第一名硬拒绝时尝试次优或回退。"""
    if not ranked:
        if fallback:
            return fallback, f"fallback_{dest}_empty"
        return ranked

    cleaned = [(u, s) for u, s in ranked if not url_hard_reject(dest, u)]

    # 宽松模式也强制 OCBC 新币挂牌走 personal 利率页（避免 business 页缺 18/24/36M）
    if dest == "ocbc_board_url":
        personal = [(u, s) for u, s in cleaned if is_ocbc_sgd_board_page(u)]
        if personal:
            return personal
        if fallback and is_ocbc_sgd_board_page(fallback):
            return fallback, "fallback_ocbc_sgd_board_page"

    if dest == "hl_board_url":
        board = [(u, s) for u, s in cleaned if is_hl_sgd_board_page(u)]
        if board:
            return board
        if fallback and is_hl_sgd_board_page(fallback):
            return fallback, "fallback_hl_sgd_board_page"

    if dest == "dbs_fcy_board_api_url":
        api = [(u, s) for u, s in cleaned if is_dbs_fcy_board_api_url(u)]
        if api:
            return api
        if fallback and is_dbs_fcy_board_api_url(fallback):
            return fallback, "fallback_dbs_fcy_api_required"

    if dest in ("rhb_board_pdf_url", "rhb_fcy_board_pdf_url"):
        pdf = [(u, s) for u, s in cleaned if is_rhb_deposit_rates_board_pdf(u)]
        if pdf:
            return pdf
        if fallback and is_rhb_deposit_rates_board_pdf(fallback):
            return fallback, "fallback_rhb_board_pdf"

    if dest in ("boc_url", "boc_board_url"):
        from boc_url_resolve import boc_article_sort_key, pick_boc_url_for_dest

        valid = [
            (u, s)
            for u, s in cleaned
            if (
                is_boc_promo_rate_page(u)
                if dest == "boc_url"
                else is_boc_board_rate_page(u)
            )
        ]
        if valid:
            valid.sort(key=lambda x: (-boc_article_sort_key(x[0])[0], -boc_article_sort_key(x[0])[1], x[0]))
            return valid
        picked, src = pick_boc_url_for_dest(
            dest,
            candidates=[u for u, _ in cleaned],
            configured_url=fallback,
        )
        if picked:
            return picked, src
        if fallback and (
            is_boc_promo_rate_page(fallback) if dest == "boc_url" else is_boc_board_rate_page(fallback)
        ):
            return fallback, (
                "fallback_boc_promo_page" if dest == "boc_url" else "fallback_boc_board_page"
            )

    # BEA SGD 促销：relaxed 模式也强制回到 index.html（手动黄金页），避免误选
    # beasg-personal-banking-fixed-deposit-account.html 导致 extract_bea_sgd_promo 提取不到促销片段。
    if dest == "bea_sgd_promo_url" and fallback and "index.html" in fallback.lower():
        idx = [(u, s) for u, s in cleaned if "index.html" in u.lower()]
        if idx:
            return idx
        if cleaned and "index.html" not in cleaned[0][0].lower():
            return fallback, "fallback_bea_index"

    if dest == "citi_all_promo_url":
        lid = [
            (u, s)
            for u, s in cleaned
            if is_citi_all_promo_url(u) and "lid=" in u.lower()
        ]
        if lid:
            return lid
        promo = [(u, s) for u, s in cleaned if is_citi_all_promo_url(u)]
        if promo:
            return promo
        if fallback and is_citi_all_promo_url(fallback):
            return fallback, "fallback_citi_all_promo"

    if dest == "url":
        fd = [
            (u, s)
            for u, s in cleaned
            if "fixed-deposit-account" in u.lower() and "all-promo" not in u.lower()
        ]
        if fd:
            return fd
        if fallback and "fixed-deposit-account" in fallback.lower():
            return fallback, "fallback_citi_fd_account"

    if dest == "bea_fcy_promo_url":
        form = [(u, s) for u, s in cleaned if is_bea_fcy_promo_form_url(u)]
        if form:
            return form
        if fallback and is_bea_fcy_promo_form_url(fallback):
            return fallback, "fallback_bea_fcy_form"

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
