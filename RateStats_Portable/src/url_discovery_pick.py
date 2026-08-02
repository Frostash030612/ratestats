"""AI 发现：统一打分与选链（宽松默认，参考手动 url 作软加分）。"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from url_dest_intent import (
    intent_score_adjustment,
    is_boc_board_rate_page,
    is_boc_promo_rate_page,
    is_dbs_fcy_board_api_url,
    is_hl_sgd_board_page,
    is_ocbc_sgd_board_page,
    is_rhb_deposit_rates_board_pdf,
    url_hard_reject,
    url_meets_dest_intent,
)
from url_discovery_config import get_intent_mode, is_relaxed_mode
from url_host_rules import (
    ICBC_BOARD_PAGE_ID,
    ICBC_FD_COLUMN_ID,
    ICBC_PROMO_PAGE_ID,
    host_fragments_for_dest,
    url_matches_dest,
)
from url_path_rules import path_score_adjustment
from url_pick_refinement import refine_ranked_candidates_relaxed

BLOCK_PATH = (
    "careers",
    "login",
    "privacy",
    "cookie",
    "newsroom",
    "about-us",
    "/business/",
    "/corporate/",
    "wealth",
    "insurance-only",
)
POSITIVE = ("deposit", "fixed", "rate", "rates", "interest", "time-deposit", "promo", "promotion", "campaign")
API_HINTS = ("api", "eform-api", "sg-rates-api", ".jsp")
PDF_HINTS = (".pdf",)


def score_url(url: str, dest: str, *, reference_url: str = "") -> int:
    """对单个候选 URL 打分（越高越优先）。

    综合：屏蔽路径、API/PDF 提示、促销/挂牌关键词、银行域名、ICBC 页 ID、
    路径规则 (url_path_rules)、意图软加分 (url_dest_intent)。
    reference_url 通常为手动 fallback，用于宽松模式下与已知好链对齐。
    """
    p = urlparse(url)
    path = (p.path or "").lower()
    host = (p.netloc or "").lower()
    full = url.lower()
    score = 0
    relaxed = is_relaxed_mode()

    if any(b in path for b in BLOCK_PATH):
        score -= 50 if relaxed else 80
    if "bankofchina.com" in host and "/sg/" not in path:
        score -= 40 if relaxed else 60
    if "sc.com" in host and "/sg/" not in path:
        score -= 25 if relaxed else 40
    if dest.endswith("_api_url") or "api" in dest:
        if any(h in full for h in API_HINTS):
            score += 35
        else:
            score -= 8 if relaxed else 15
    if "pdf" in dest or dest.endswith("_pdf_url"):
        if any(h in full for h in PDF_HINTS):
            score += 30
        else:
            score -= 5 if relaxed else 10
    if dest == "citi_all_promo_url":
        if "all-promo" in full:
            if "lid=" in full:
                score += 22
            else:
                score += 8
    if dest == "url" or dest == "citi_board_url":
        if "fixed-deposit-account" in full:
            score += 18
        if "all-promo" in full:
            score -= 10
    if "promo" in dest or dest in ("url", "hl_url", "hlf_url", "ocbc_url", "rhb_url", "sbi_url", "sbi_usd_url"):
        if any(k in full for k in ("promo", "promotion", "campaign", "all-promo")):
            score += 12
    if dest == "citi_all_promo_url" and "all-promo" in full:
        score += 12
    if "board" in dest or "rates" in dest or dest.endswith("_board_url"):
        if any(k in full for k in ("rate", "rates", "interest", "board", "online-rates", "daily_price")):
            score += 12
    if dest == "hl_board_url":
        if "help-support/fixed-deposit-rate" in full:
            score += 40
        if "deposits/fixed-deposit-account/fixed-deposit-account" in full:
            score -= 50
    if any(k in full for k in POSITIVE):
        score += 8
    if "/en/" in path or "/personal/" in path:
        score += 3

    if host_fragments_for_dest(dest):
        if url_matches_dest(dest, url):
            score += 25
        else:
            score -= 120

    if host_fragments_for_dest(dest) and "singapore.icbc.com.cn" in host:
        # 新版官网：Fixed Deposit 栏目（column）同页含促销 + 挂牌，对所有 icbc dest 都是首选。
        if ICBC_FD_COLUMN_ID in full and dest.startswith("icbc"):
            score += 45
        if ICBC_BOARD_PAGE_ID in full and ("board" in dest or dest.endswith("_board_url")):
            score += 45
        if ICBC_PROMO_PAGE_ID in full and ("board" in dest or dest.endswith("_board_url")):
            score -= 55
        if ICBC_PROMO_PAGE_ID in full and dest == "icbc_url":
            score += 35
        if ICBC_BOARD_PAGE_ID in full and dest == "icbc_url":
            score -= 20

    score += path_score_adjustment(dest, url)
    score += intent_score_adjustment(dest, url, reference_url=reference_url)
    return score


def pick_best_url(candidates: list[str], dest: str, fallback: str) -> tuple[str, str]:
    """从搜索引擎返回的链接列表中选出最终 URL。

    返回 (url, source_tag)：source_tag 为 "ai" 表示选中 AI 结果，
    否则为 fallback_* 原因（低分、错域名、硬拒绝、意图不符等）。
    """
    mode = get_intent_mode()
    if not candidates:
        return fallback, "fallback"

    unique = list(dict.fromkeys(candidates))
    ranked = sorted(
        ((u, score_url(u, dest, reference_url=fallback)) for u in unique),
        key=lambda x: (-x[1], x[0]),
    )

    on_bank = [(u, s) for u, s in ranked if url_matches_dest(dest, u)]
    if on_bank:
        ranked = on_bank
    elif fallback and url_matches_dest(dest, fallback):
        return fallback, "fallback_no_bank_host_in_results"
    else:
        return fallback, "fallback_no_bank_host_in_results"

    if dest.startswith("icbc") and ("board" in dest or dest.endswith("_board_url")):
        has_board_page = any(
            ICBC_BOARD_PAGE_ID in u or ICBC_FD_COLUMN_ID in u for u, _ in ranked
        )
        if (
            not has_board_page
            and fallback
            and (ICBC_BOARD_PAGE_ID in fallback or ICBC_FD_COLUMN_ID in fallback)
        ):
            return fallback, "fallback_icbc_board_page_not_in_index"

    if is_relaxed_mode():
        ranked = refine_ranked_candidates_relaxed(dest, ranked, fallback)
        if isinstance(ranked, tuple):
            return ranked
    else:
        from url_pick_refinement import refine_ranked_candidates

        refined = refine_ranked_candidates(dest, ranked, fallback)
        if isinstance(refined, tuple):
            return refined
        ranked = refined

    best_url, best_score = ranked[0]

    if dest == "ocbc_board_url" and not is_ocbc_sgd_board_page(best_url or ""):
        if fallback and is_ocbc_sgd_board_page(fallback) and url_matches_dest(dest, fallback):
            return fallback, "fallback_ocbc_sgd_board_page"

    if dest == "hl_board_url" and not is_hl_sgd_board_page(best_url or ""):
        if fallback and is_hl_sgd_board_page(fallback) and url_matches_dest(dest, fallback):
            return fallback, "fallback_hl_sgd_board_page"

    if dest == "dbs_fcy_board_api_url" and not is_dbs_fcy_board_api_url(best_url or ""):
        if fallback and is_dbs_fcy_board_api_url(fallback) and url_matches_dest(dest, fallback):
            return fallback, "fallback_dbs_fcy_api_required"

    if dest in ("rhb_board_pdf_url", "rhb_fcy_board_pdf_url") and not is_rhb_deposit_rates_board_pdf(
        best_url or ""
    ):
        if fallback and is_rhb_deposit_rates_board_pdf(fallback) and url_matches_dest(dest, fallback):
            return fallback, "fallback_rhb_board_pdf"

    if dest == "boc_url" and not is_boc_promo_rate_page(best_url or ""):
        if fallback and is_boc_promo_rate_page(fallback) and url_matches_dest(dest, fallback):
            return fallback, "fallback_boc_promo_page"

    if dest == "boc_board_url" and not is_boc_board_rate_page(best_url or ""):
        if fallback and is_boc_board_rate_page(fallback) and url_matches_dest(dest, fallback):
            return fallback, "fallback_boc_board_page"

    if url_hard_reject(dest, best_url):
        if fallback and url_matches_dest(dest, fallback) and not url_hard_reject(dest, fallback):
            return fallback, "fallback_hard_reject"
        if len(ranked) > 1 and not url_hard_reject(dest, ranked[1][0]):
            return ranked[1][0], "ai"
        return fallback, "fallback_hard_reject"

    if dest in ("boc_url", "boc_board_url"):
        from boc_url_resolve import pick_boc_url_for_dest

        companion = ""
        try:
            from url_fallback_resolver import build_fallback_map

            fb_map = build_fallback_map()
            companion = fb_map.get(
                "boc_board_url" if dest == "boc_url" else "boc_url",
                "",
            )
        except Exception:
            pass
        all_cands = [u for u, _ in ranked]
        picked, boc_src = pick_boc_url_for_dest(
            dest,
            candidates=all_cands,
            configured_url=fallback,
            companion_url=companion,
        )
        if picked:
            return picked, boc_src

    if dest in ("icbc_url", "icbc_board_url", "icbc_fcy_board_url"):
        from icbc_url_resolve import pick_icbc_url_for_dest

        all_cands = [u for u, _ in ranked]
        picked, icbc_src = pick_icbc_url_for_dest(
            dest,
            candidates=all_cands,
            configured_url=fallback,
        )
        if picked:
            return picked, icbc_src

    low_threshold = -15 if is_relaxed_mode() else 0
    if best_score < low_threshold:
        return fallback, "fallback_low_score"
    if not url_matches_dest(dest, best_url):
        return fallback, "fallback_wrong_host"

    if mode == "strict":
        if not url_meets_dest_intent(dest, best_url):
            if fallback and url_matches_dest(dest, fallback) and url_meets_dest_intent(dest, fallback):
                return fallback, "fallback_dest_intent"
            return fallback, "fallback_dest_intent_no_valid_candidate"

    return best_url, "ai"
