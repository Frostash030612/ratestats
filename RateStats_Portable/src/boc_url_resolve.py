"""中行新加坡促销/挂牌 URL：与 bank_fetch_and_extract 栏目页置顶逻辑一致。"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from url_dest_intent import is_boc_board_rate_page, is_boc_promo_rate_page

_BOC_ARTICLE_PATH = re.compile(
    r"/bocinfo/bi3/(bi31|bi32)/(\d{6})/(t\d{8})_\d+\.html",
    re.I,
)


def boc_sg_promo_and_board_index_urls(promo_url: str, board_url: str) -> tuple[str, str]:
    """
    栏目列表页 URL。文档顺序下第一条 t20*.html 为当前置顶稿（与官网一致）。
    英文站 bank-of-china.com；中文默认 bankofchina.com + /sg/cn/。
    """
    for u in (promo_url or "", board_url or ""):
        if "bank-of-china.com" in (u or "").lower():
            return (
                "https://www.bank-of-china.com/sg/bocinfo/bi3/bi31/",
                "https://www.bank-of-china.com/sg/bocinfo/bi3/bi32/",
            )
    return (
        "https://www.bankofchina.com/sg/cn/bocinfo/bi3/bi31/",
        "https://www.bankofchina.com/sg/cn/bocinfo/bi3/bi32/",
    )


def boc_bi_segment_for_dest(dest: str) -> str:
    if dest == "boc_url":
        return "bi31"
    if dest == "boc_board_url":
        return "bi32"
    raise ValueError(f"not a BOC dest: {dest}")


def boc_first_article_url_from_index_html(
    html: str,
    index_url: str,
    bi_segment: str,
) -> Optional[str]:
    """从栏目页 HTML 取第一条匹配的定存利率公告完整 URL。"""
    base = index_url if index_url.endswith("/") else index_url + "/"
    sub = re.escape(bi_segment)
    inner = re.compile(rf"/bocinfo/bi3/{sub}/\d{{6}}/t\d{{8}}_\d+\.html", re.I)

    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue
        full = urljoin(base, href)
        full = full.split("#")[0].rstrip("/")
        if inner.search(full):
            return full
    return None


@lru_cache(maxsize=8)
def _fetch_boc_latest_cached(index_url: str, bi_segment: str, timeout: float) -> Optional[str]:
    try:
        r = requests.get(
            index_url,
            timeout=timeout,
            headers={"User-Agent": "RateStats-BOC-index/1.0"},
        )
        r.raise_for_status()
        r.encoding = r.apparent_encoding or r.encoding
        return boc_first_article_url_from_index_html(r.text, index_url, bi_segment)
    except requests.RequestException:
        return None


def fetch_boc_latest_article_url(
    *,
    index_url: str,
    bi_segment: str,
    timeout: float = 20.0,
) -> Optional[str]:
    """GET 栏目页并返回置顶公告链；失败返回 None（同 index 进程内缓存）。"""
    return _fetch_boc_latest_cached(index_url, bi_segment, float(timeout))


def boc_article_sort_key(url: str) -> tuple[int, int, str]:
    """候选 dated 文章排序键（栏目抓取失败时，在候选中取日期最新）。"""
    m = _BOC_ARTICLE_PATH.search(url or "")
    if not m:
        return (0, 0, url or "")
    yyyymm = int(m.group(2))
    ttag = m.group(3)
    tday = int(ttag[1:9]) if len(ttag) >= 9 and ttag[1:9].isdigit() else 0
    return (yyyymm, tday, url)


def _is_valid_for_dest(dest: str, url: str) -> bool:
    if dest == "boc_url":
        return is_boc_promo_rate_page(url)
    if dest == "boc_board_url":
        return is_boc_board_rate_page(url)
    return False


def pick_boc_url_for_dest(
    dest: str,
    *,
    candidates: list[str],
    configured_url: str,
    companion_url: str = "",
    try_index: bool = True,
    index_timeout: float = 20.0,
) -> tuple[str, str]:
    """
    与手动抓取一致：优先读 bi31/bi32 栏目页置顶链；否则在候选中取最新 dated 文；
    再回退 configured_url。
    """
    if dest not in ("boc_url", "boc_board_url"):
        raise ValueError(dest)

    section = boc_bi_segment_for_dest(dest)
    promo_cfg = configured_url if dest == "boc_url" else companion_url
    board_cfg = configured_url if dest == "boc_board_url" else companion_url
    promo_idx, board_idx = boc_sg_promo_and_board_index_urls(
        promo_cfg or configured_url,
        board_cfg or configured_url,
    )
    index_url = promo_idx if dest == "boc_url" else board_idx

    if try_index:
        latest = fetch_boc_latest_article_url(
            index_url=index_url,
            bi_segment=section,
            timeout=index_timeout,
        )
        if latest and _is_valid_for_dest(dest, latest):
            return latest, "boc_index_latest"

    pool = list(dict.fromkeys(u for u in candidates if _is_valid_for_dest(dest, u)))
    if pool:
        best = max(pool, key=boc_article_sort_key)
        return best, "boc_candidate_latest"

    if configured_url and _is_valid_for_dest(dest, configured_url):
        tag = "fallback_boc_promo_page" if dest == "boc_url" else "fallback_boc_board_page"
        return configured_url, tag

    if configured_url:
        return configured_url, f"fallback_{dest}"

    return "", "fallback_empty"


def boc_reference_url_for_eval(
    dest: str,
    *,
    configured_url: str,
    companion_url: str = "",
    candidates: list[str] | None = None,
) -> str:
    """评估用：与选链相同逻辑得到应对齐的参考 URL（栏目置顶优先）。"""
    url, _ = pick_boc_url_for_dest(
        dest,
        candidates=candidates or [],
        configured_url=configured_url,
        companion_url=companion_url,
        try_index=True,
    )
    return url or configured_url
