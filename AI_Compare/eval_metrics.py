"""命中率与排名指标。所有比较都先做 URL 规范化。"""
from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def normalize_url(u: str) -> str:
    """规范化 URL（scheme/host/path），用于精确命中比较。"""
    if not isinstance(u, str):
        return ""
    s = u.strip()
    if not s:
        return ""
    p = urlparse(s)
    scheme = (p.scheme or "https").lower()
    netloc = p.netloc.lower()
    path = (p.path or "/").rstrip("/")
    if not path:
        path = "/"
    return urlunparse((scheme, netloc, path, "", "", ""))


def host_of(u: str) -> str:
    """返回 URL 主机名（小写）。"""
    return urlparse(u or "").netloc.lower()


def rank_in_topn(gold: str, candidates: list[str]) -> int:
    """返回 1-based 排名；未命中返回 0。"""
    g = normalize_url(gold)
    if not g:
        return 0
    for i, c in enumerate(candidates, 1):
        if normalize_url(c) == g:
            return i
    return 0


def hit_at_k(rank: int, k: int) -> int:
    """Hit@K：黄金 URL 是否出现在前 K 条候选（rank 为 1-based）。"""
    return 1 if 0 < rank <= k else 0


def mrr(rank: int) -> float:
    """Mean Reciprocal Rank：1/rank，未命中为 0。"""
    return 1.0 / rank if rank > 0 else 0.0


def same_host_rank(gold: str, candidates: list[str]) -> int:
    """同域命中排名（不要求路径相同），未命中返回 0。"""
    gh = host_of(gold)
    if not gh:
        return 0
    for i, c in enumerate(candidates, 1):
        if host_of(c) == gh:
            return i
    return 0
