#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""候选 URL 特征：规则分子项 + 错页模式 + 与手动黄金链相似度。"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from _portable import PORTABLE_DIR  # noqa: F401 — 触发 path

from url_discovery_pick import score_url  # noqa: E402
from url_host_rules import url_matches_dest  # noqa: E402
from url_path_rules import path_score_adjustment  # noqa: E402
from url_dest_intent import (  # noqa: E402
    intent_score_adjustment,
    is_boc_board_rate_page,
    is_boc_promo_rate_page,
    is_dbs_fcy_board_api_url,
    is_ocbc_sgd_board_page,
    is_rhb_deposit_rates_board_pdf,
    url_hard_reject,
)

FEATURE_NAMES: tuple[str, ...] = (
    "rule_score",
    "path_rule_adj",
    "intent_rule_adj",
    "hard_reject_flag",
    "matches_dest",
    "same_host_as_ref",
    "path_jaccard_ref",
    "path_prefix_match_ref",
    "dest_is_board",
    "dest_is_promo",
    "dest_is_api",
    "dest_is_pdf",
    "url_has_api_hint",
    "url_has_pdf",
    "url_has_promo_kw",
    "url_has_board_kw",
    "pat_premier_banking",
    "pat_business_banking",
    "pat_fixed_deposit_sgd",
    "pat_sgd_fd_business",
    "pat_sg_rates_api",
    "pat_treasury_api",
    "pat_fd_account_only",
    "pat_ocbc_valid_board",
    "pat_dbs_fcy_api_valid",
    "pat_rhb_board_pdf_valid",
    "pat_boc_promo_valid",
    "pat_boc_board_valid",
    "path_depth",
    "candidate_rank",
    "url_len",
)

# 训练时可从特征矩阵中剔除（迫使模型不只复制 rule_score）
OPTIONAL_DROP_FEATURES: frozenset[str] = frozenset({"rule_score"})


def _path_tokens(url: str) -> set[str]:
    low = (url or "").lower()
    parts = re.split(r"[/?.=&_-]+", urlparse(low).path + "?" + (urlparse(low).query or ""))
    return {p for p in parts if len(p) >= 4 and p not in ("html", "page", "personal", "banking", "index")}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _dest_flags(dest: str) -> tuple[int, int, int, int]:
    d = dest or ""
    return (
        1 if "board" in d else 0,
        1 if "promo" in d or d in ("url", "hl_url", "hlf_url", "ocbc_url", "rhb_url", "sbi_url", "sbi_usd_url") else 0,
        1 if "api" in d else 0,
        1 if "pdf" in d else 0,
    )


def _path_pattern_flags(url: str, dest: str) -> dict[str, float]:
    full = (url or "").lower()
    low = full
    fd_account = "fixed-deposit-account" in low and "fixed-deposit-sgd-interest" not in low
    return {
        "pat_premier_banking": 1.0 if "premier-banking" in low else 0.0,
        "pat_business_banking": 1.0 if "business-banking" in low else 0.0,
        "pat_fixed_deposit_sgd": 1.0 if "fixed-deposit-sgd-interest" in low else 0.0,
        "pat_sgd_fd_business": 1.0
        if "sgd-fixed-deposit-interest" in low and "business-banking" in low
        else 0.0,
        "pat_sg_rates_api": 1.0
        if "sg-rates-api" in low and "getsgfcfdrates" in low.replace("-", "")
        else 0.0,
        "pat_treasury_api": 1.0 if "treasury-api" in low or "global-financial-markets" in low else 0.0,
        "pat_fd_account_only": 1.0 if fd_account else 0.0,
        "pat_ocbc_valid_board": 1.0 if dest == "ocbc_board_url" and is_ocbc_sgd_board_page(url) else 0.0,
        "pat_dbs_fcy_api_valid": 1.0
        if dest == "dbs_fcy_board_api_url" and is_dbs_fcy_board_api_url(url)
        else 0.0,
        "pat_rhb_board_pdf_valid": 1.0
        if dest in ("rhb_board_pdf_url", "rhb_fcy_board_pdf_url")
        and is_rhb_deposit_rates_board_pdf(url)
        else 0.0,
        "pat_boc_promo_valid": 1.0 if dest == "boc_url" and is_boc_promo_rate_page(url) else 0.0,
        "pat_boc_board_valid": 1.0 if dest == "boc_board_url" and is_boc_board_rate_page(url) else 0.0,
    }


def extract_features(
    url: str,
    dest: str,
    *,
    reference_url: str = "",
    candidate_rank: int = 0,
) -> dict[str, float]:
    """单条候选 → 特征字典（与 FEATURE_NAMES 顺序一致）。"""
    full = (url or "").lower()
    path = (urlparse(url).path or "").lower()
    ref = reference_url or ""
    ref_host = urlparse(ref).netloc.lower()
    url_host = urlparse(url).netloc.lower()

    board_f, promo_f, api_f, pdf_f = _dest_flags(dest)
    rule = float(score_url(url, dest, reference_url=ref))
    path_adj = float(path_score_adjustment(dest, url))
    intent_adj = float(intent_score_adjustment(dest, url, reference_url=ref))
    tokens_u = _path_tokens(url)
    tokens_r = _path_tokens(ref)
    ref_path = urlparse(ref).path.lower().rstrip("/")

    base = {
        "rule_score": rule,
        "path_rule_adj": path_adj,
        "intent_rule_adj": intent_adj,
        "hard_reject_flag": 1.0 if url_hard_reject(dest, url) else 0.0,
        "matches_dest": 1.0 if url_matches_dest(dest, url) else 0.0,
        "same_host_as_ref": 1.0 if ref_host and url_host == ref_host else 0.0,
        "path_jaccard_ref": _jaccard(tokens_u, tokens_r),
        "path_prefix_match_ref": 1.0 if ref_path and ref_path in path else 0.0,
        "dest_is_board": float(board_f),
        "dest_is_promo": float(promo_f),
        "dest_is_api": float(api_f),
        "dest_is_pdf": float(pdf_f),
        "url_has_api_hint": 1.0 if any(x in full for x in ("api", "sg-rates-api", ".jsp")) else 0.0,
        "url_has_pdf": 1.0 if ".pdf" in full else 0.0,
        "url_has_promo_kw": 1.0 if any(x in full for x in ("promo", "promotion", "campaign")) else 0.0,
        "url_has_board_kw": 1.0 if any(x in full for x in ("rate", "rates", "interest", "board")) else 0.0,
        "path_depth": float(path.count("/")),
        "candidate_rank": float(candidate_rank),
        "url_len": float(len(url or "")),
    }
    base.update(_path_pattern_flags(url, dest))
    return base


def active_feature_names(*, drop_rule_score: bool = False) -> tuple[str, ...]:
    if drop_rule_score:
        return tuple(k for k in FEATURE_NAMES if k not in OPTIONAL_DROP_FEATURES)
    return FEATURE_NAMES


def feature_vector(
    url: str,
    dest: str,
    *,
    reference_url: str = "",
    candidate_rank: int = 0,
    drop_rule_score: bool = False,
) -> list[float]:
    d = extract_features(url, dest, reference_url=reference_url, candidate_rank=candidate_rank)
    names = active_feature_names(drop_rule_score=drop_rule_score)
    return [d[k] for k in names]


def rows_to_matrix(
    rows: list[dict[str, float]],
    *,
    feature_names: tuple[str, ...] | None = None,
) -> list[list[float]]:
    names = feature_names or FEATURE_NAMES
    return [[r[k] for k in names] for r in rows]
