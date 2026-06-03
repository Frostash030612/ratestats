#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""候选 URL 特征：复用 Portable 规则分 + 与手动黄金链的相似度。"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from _portable import PORTABLE_DIR  # noqa: F401 — 触发 path

from url_discovery_pick import score_url  # noqa: E402
from url_host_rules import url_matches_dest  # noqa: E402

FEATURE_NAMES: tuple[str, ...] = (
    "rule_score",
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
    "path_depth",
    "candidate_rank",
    "url_len",
)


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
    tokens_u = _path_tokens(url)
    tokens_r = _path_tokens(ref)
    ref_path = urlparse(ref).path.lower().rstrip("/")

    return {
        "rule_score": rule,
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


def feature_vector(
    url: str,
    dest: str,
    *,
    reference_url: str = "",
    candidate_rank: int = 0,
) -> list[float]:
    d = extract_features(url, dest, reference_url=reference_url, candidate_rank=candidate_rank)
    return [d[k] for k in FEATURE_NAMES]


def rows_to_matrix(rows: list[dict[str, float]]) -> list[list[float]]:
    return [[r[k] for k in FEATURE_NAMES] for r in rows]
