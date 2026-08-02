"""工行新加坡促销/挂牌 URL：每次运行从官网导航动态解析当前生效的 column 路径。

背景：官网从 /en/page/<id>.html 改版为 /en/column/<id>.html（域名不变）。
为避免路径再次变化导致链接失效，这里不依赖写死的页面 ID：
1) 请求官网入口页，从导航里按「Fixed Deposit」文字找到当前定存栏目 column URL；
2) 该栏目同页含促销（SGD/USD/RMB Promotion Rates）与挂牌（board）表，
   促销/挂牌三个 dest 统一用它作为抓取入口；
3) 导航解析失败时回退内置栏目 URL，再回退配置 URL（并做域名规范化）。
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
from functools import lru_cache
from typing import Optional
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

ICBC_CANONICAL_HOST = "singapore.icbc.com.cn"
ICBC_HOST_ALIASES = (
    "www.icbc.com.sg",
    "icbc.com.sg",
    "singapore.icbc.com.sg",
)

# 导航发现的入口页（任一官网页面的导航都含 Fixed Deposit 链接）。
ICBC_NAV_ENTRY_URL = f"https://{ICBC_CANONICAL_HOST}/en/column/1438058394388152562.html"

# 导航解析失败时的兜底（2026-07 官网现状）。
ICBC_FD_COLUMN_FALLBACK_URL = (
    f"https://{ICBC_CANONICAL_HOST}/en/column/1438059017468788838.html"
)

ICBC_DESTS = ("icbc_url", "icbc_board_url", "icbc_fcy_board_url")

_PAGE_PATH = re.compile(r"/en/(?:page|column)/(\d+)\.html", re.I)
_FD_LINK_TEXT = re.compile(r"^\s*Fixed\s+Deposit\s*$", re.I)


def normalize_icbc_url(url: str) -> str:
    """将 icbc.com.sg 等别名主机改写为 singapore.icbc.com.cn，路径保持不变。"""
    u = (url or "").strip()
    if not u.startswith("http"):
        return u
    p = urlparse(u)
    host = (p.hostname or "").lower()
    if host in ICBC_HOST_ALIASES or host.endswith(".icbc.com.sg"):
        netloc = ICBC_CANONICAL_HOST
        if p.port and p.port not in (80, 443):
            netloc = f"{ICBC_CANONICAL_HOST}:{p.port}"
        return urlunparse((p.scheme or "https", netloc, p.path, p.params, p.query, p.fragment))
    return u


def icbc_page_id(url: str) -> str:
    m = _PAGE_PATH.search(url or "")
    return m.group(1) if m else ""


def _icbc_session() -> requests.Session:
    """工行站点在部分 OpenSSL 3 环境需允许旧式服务端重协商。"""

    class _IcbcTlsAdapter(HTTPAdapter):
        def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
            ctx = ssl.create_default_context()
            if hasattr(ssl, "OP_LEGACY_SERVER_CONNECT"):
                ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
            pool_kwargs["ssl_context"] = ctx
            return super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)

    s = requests.Session()
    s.headers.update({"User-Agent": "RateStats-ICBC-index/1.0"})
    s.mount(f"https://{ICBC_CANONICAL_HOST}", _IcbcTlsAdapter())
    return s


def fd_column_url_from_nav_html(html: str, base_url: str) -> Optional[str]:
    """从任意官网页面导航 HTML 中找「Fixed Deposit」栏目链接。"""
    base = base_url if base_url.endswith("/") else base_url + "/"
    soup = BeautifulSoup(html or "", "lxml")
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        if not _FD_LINK_TEXT.match(text):
            continue
        full = normalize_icbc_url(urljoin(base, (a.get("href") or "").strip()).split("#")[0])
        if "/en/column/" in full.lower():
            return full
    return None


@lru_cache(maxsize=4)
def _fetch_fd_column_cached(entry_url: str, timeout: float) -> Optional[str]:
    try:
        with _icbc_session() as sess:
            r = sess.get(entry_url, timeout=timeout)
            r.raise_for_status()
            r.encoding = r.apparent_encoding or r.encoding
            return fd_column_url_from_nav_html(r.text, entry_url)
    except requests.RequestException:
        return None


def fetch_icbc_fd_column_url(
    *,
    entry_url: str = ICBC_NAV_ENTRY_URL,
    timeout: float = 20.0,
) -> Optional[str]:
    """GET 官网入口页并返回导航中的 Fixed Deposit 栏目链；失败返回 None（进程内缓存）。"""
    found = _fetch_fd_column_cached(entry_url, float(timeout))
    if found:
        return found
    # 入口页本身失效时，直接探测兜底栏目 URL 是否可用。
    try:
        with _icbc_session() as sess:
            r = sess.get(ICBC_FD_COLUMN_FALLBACK_URL, timeout=timeout)
            if r.status_code < 400:
                return ICBC_FD_COLUMN_FALLBACK_URL
    except requests.RequestException:
        pass
    return None


def resolve_icbc_url(
    dest: str,
    *,
    configured_url: str,
    try_index: bool = True,
    index_timeout: float = 20.0,
) -> tuple[str, dict]:
    """
    解析 ICBC dest 的实际抓取 URL（促销/挂牌三个 dest 统一走 Fixed Deposit 栏目）。
    返回 (fetch_url, meta)；meta 含 configured_url / latest_from_index / switched_from_configured。
    """
    cfg = normalize_icbc_url(configured_url or "")
    meta: dict = {
        "configured_url": configured_url or "",
        "normalized_configured_url": cfg,
        "follow_latest_from_index": bool(try_index),
        "dest": dest,
    }

    if dest not in ICBC_DESTS:
        meta["fetch_url"] = cfg
        meta["switched_from_configured"] = False
        return cfg, meta

    meta["index_url"] = ICBC_NAV_ENTRY_URL
    if not try_index or not cfg:
        meta["fetch_url"] = cfg
        meta["switched_from_configured"] = bool(cfg and cfg != (configured_url or "").strip())
        return cfg, meta

    latest = fetch_icbc_fd_column_url(timeout=index_timeout)
    meta["latest_from_index"] = latest
    if latest:
        meta["switched_from_configured"] = latest.rstrip("/") != cfg.rstrip("/")
        meta["fetch_url"] = latest
        return latest, meta

    meta["index_parse_empty"] = True
    meta["switched_from_configured"] = cfg != (configured_url or "").strip()
    meta["fetch_url"] = cfg
    return cfg, meta


def pick_icbc_url_for_dest(
    dest: str,
    *,
    candidates: list[str],
    configured_url: str,
    try_index: bool = True,
    index_timeout: float = 20.0,
) -> tuple[str, str]:
    """AI 选链：优先官网导航解析到的最新栏目链，否则规范化后的配置/候选。"""
    if dest not in ICBC_DESTS:
        raise ValueError(dest)

    url, meta = resolve_icbc_url(
        dest,
        configured_url=configured_url,
        try_index=try_index,
        index_timeout=index_timeout,
    )
    if meta.get("latest_from_index"):
        return url, "icbc_index_latest"

    cfg = normalize_icbc_url(configured_url or "")
    if cfg:
        tag = "fallback_icbc_normalized" if cfg != (configured_url or "").strip() else f"fallback_{dest}"
        return cfg, tag

    for c in candidates:
        n = normalize_icbc_url(c)
        if n and ICBC_CANONICAL_HOST in n:
            return n, "icbc_candidate_normalized"
    return "", "fallback_empty"


def resolve_all_icbc_urls(*, timeout: float = 20.0) -> dict[str, dict]:
    """一次解析促销/挂牌最新路径，便于巡检与测试对比。"""
    out: dict[str, dict] = {}
    for dest in ICBC_DESTS:
        url, meta = resolve_icbc_url(
            dest,
            configured_url=ICBC_FD_COLUMN_FALLBACK_URL,
            try_index=True,
            index_timeout=timeout,
        )
        out[dest] = {"url": url, **meta}
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="解析工行新加坡官网当前促销/挂牌页面路径")
    p.add_argument("--timeout", type=float, default=20.0)
    p.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = p.parse_args(argv)

    _fetch_fd_column_cached.cache_clear()
    data = resolve_all_icbc_urls(timeout=args.timeout)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("[ICBC] 官网导航解析到的当前路径（促销与挂牌同页）：")
        for dest, info in data.items():
            print(f"  {dest}: {info.get('url') or ''}")
            if info.get("latest_from_index") is None:
                print("    note: 导航解析失败，已用兜底/配置 URL，请检查网络或官网改版")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
