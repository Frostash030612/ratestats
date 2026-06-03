from __future__ import annotations

"""
Citibank 抓取与汇总模块（fetch_and_extract）。

这份模块把主脚本里的“抓取总入口”函数单独拆出来，降低主脚本主干的体积。

注意：
- 各银行解析函数已迁移到 `bank_extractors.impl` 包，本模块在模块级 `import` 后直接使用，
  不再依赖 `import __main__`。
"""

from typing import Any, Dict, List, Optional

from bank_safety import safe_call
from datetime import datetime, timezone

import contextlib
import re
import socket
import time
from urllib.parse import urljoin

import requests
from requests.exceptions import ChunkedEncodingError
from bs4 import BeautifulSoup

from url_sources import (
    DEFAULT_CIMB_FCY_URL,
    DEFAULT_CIMB_SGD_URL,
    DEFAULT_HL_FD_URL,
    DEFAULT_HLF_FD_URL,
    DEFAULT_HSBC_TD_URL,
    DEFAULT_ICBC_FD_URL,
    DEFAULT_OCBC_FD_URL,
    DEFAULT_RHB_FD_URL,
    DEFAULT_RHB_FCY_FD_URL,
    DEFAULT_SCB_SGD_TD_URL,
    DEFAULT_SCB_FCY_FD_URL,
    DEFAULT_SIF_FD_URL,
    DEFAULT_SBI_SGD_PROMO_URL,
    DEFAULT_SBI_USD_PROMO_URL,
    DEFAULT_UOB_SGD_TD_URL,
    DEFAULT_BOC_PROMO_URL,
    DEFAULT_CITI_SGD_BOARD_URL,
    DEFAULT_DBS_SGD_BOARD_URL,
    DEFAULT_HL_SGD_BOARD_URL,
    DEFAULT_HLF_SGD_BOARD_URL,
    DEFAULT_HSBC_SGD_BOARD_URL,
    DEFAULT_ICBC_SGD_BOARD_URL,
    DEFAULT_ICBC_FCY_BOARD_URL,
    DEFAULT_MAYBANK_SGD_BOARD_URL,
    DEFAULT_OCBC_SGD_BOARD_URL,
    DEFAULT_RHB_SGD_BOARD_PDF_URL,
    DEFAULT_SIF_SGD_BOARD_URL,
    DEFAULT_SCB_SGD_BOARD_URL,
    DEFAULT_SBI_SGD_BOARD_URL,
    DEFAULT_UOB_SGD_BOARD_URL,
    DEFAULT_HL_FCY_BOARD_URL,
    DEFAULT_HSBC_FCY_BOARD_URL,
    DEFAULT_MAYBANK_FCY_BOARD_URL,
    DEFAULT_SCB_FCY_BOARD_URL,
    DEFAULT_SBI_FCY_BOARD_URL,
    DEFAULT_OCBC_FCY_BOARD_URL,
    DEFAULT_UOB_FCY_BOARD_URL,
    DEFAULT_RHB_FCY_BOARD_PDF_URL,
    DEFAULT_BEA_SGD_BOARD_API_URL,
    DEFAULT_BEA_FCY_BOARD_API_URL,
    DEFAULT_BOC_BOARD_URL,
    DEFAULT_BEA_SGD_PROMO_URL,
    DEFAULT_BEA_FCY_PROMO_URL,
    DEFAULT_MAYBANK_SGD_PROMO_URL,
    DEFAULT_HSBC_FCY_PROMO_URL,
    DEFAULT_DBS_FCY_BOARD_API_URL,
)

from bank_extractors import impl as _x
from bank_constants import NA


def _boc_sg_promo_and_board_index_urls(promo_url: str, board_url: str) -> tuple[str, str]:
    """
    中行新加坡「栏目列表页」：文档顺序下第一条 `t20*.html` 为当前置顶稿（与官网一致）。
    英文站域名含 `bank-of-china.com`，中文默认 `bankofchina.com` + `/sg/cn/`。
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


def _boc_sg_first_article_url_from_index_html(
    html: str,
    index_url: str,
    bi_segment: str,
) -> Optional[str]:
    """从栏目页 HTML 中取第一条匹配的定存利率公告 `.../bi3/bi31|bi32/yyyymm/t*.html` 完整 URL。"""
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


def _resolve_boc_sg_article_via_index(
    sess: requests.Session,
    *,
    configured_url: str,
    index_url: str,
    bi_segment: str,
    timeout: float,
    enabled: bool,
) -> tuple[str, Dict[str, Any]]:
    """
    若 enabled：GET 栏目页并取第一条公告链；解析失败或异常则回退 configured_url。
    返回 (实际用于 GET 的 URL, 元数据 dict)。
    """
    meta: Dict[str, Any] = {
        "configured_url": configured_url,
        "index_url": index_url,
        "bi_segment": bi_segment,
        "follow_latest_from_index": bool(enabled),
    }
    if not enabled or not (configured_url or "").strip():
        meta["fetch_url"] = configured_url
        return configured_url, meta
    try:
        ridx = sess.get(index_url, timeout=timeout)
        ridx.raise_for_status()
        ridx.encoding = ridx.apparent_encoding or ridx.encoding
        latest = _boc_sg_first_article_url_from_index_html(ridx.text, index_url, bi_segment)
        meta["latest_from_index"] = latest
        if latest:
            a, b = latest.rstrip("/"), configured_url.rstrip("/")
            meta["switched_from_configured"] = a != b
            use = latest
        else:
            meta["switched_from_configured"] = False
            meta["index_parse_empty"] = True
            use = configured_url
        meta["fetch_url"] = use
        return use, meta
    except requests.RequestException as e:
        meta["index_error"] = str(e)
        meta["fetch_url"] = configured_url
        return configured_url, meta


def _supplement_hl_fcy_promo_from_board(
    fx_merged: List[Dict[str, Any]],
    fx_board_merged: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    HL 促销页已无线索外币定存表格时，仍希望「外币定存促销」中有 HL 的 USD/AUD 参考行：
    用外币挂牌页 `extract_hl_fcy_board` 的结果各补一行（与促销页分支 promo 行区分）。
    """
    if not fx_board_merged:
        return fx_merged
    has_hl_branch_promo = any(
        isinstance(r, dict)
        and str(r.get("data_source", "")).startswith("HL Bank Branch FD promo")
        for r in fx_merged
    )
    if has_hl_branch_promo:
        return fx_merged
    out = list(fx_merged)
    for cur in ("USD", "AUD"):
        if any(
            isinstance(r, dict)
            and r.get("currency") == cur
            and str(r.get("data_source", "")).startswith("HL Bank")
            for r in out
        ):
            continue
        board_rows = [
            r
            for r in fx_board_merged
            if isinstance(r, dict)
            and r.get("data_source") == "HL Bank"
            and r.get("currency") == cur
        ]
        if not board_rows:
            continue
        pick = board_rows[0]
        out.append(
            {
                "currency": cur,
                "rate_1m": NA,
                "rate_3m": pick.get("rate_3m_pct"),
                "rate_6m": pick.get("rate_6m_pct"),
                "rate_9m": NA,
                "rate_12m": pick.get("rate_12m_pct"),
                "min_deposit_text": NA,
                "max_deposit_text": NA,
                "page_text_1m": NA,
                "data_source": "HL Bank — 外币定存挂牌（促销页无外币表；此行取自挂牌页）",
            }
        )
    return out


def _get_with_hsbc_rates_fallback(sess, url: str, timeout: float):
    """
    HSBC rates 页面偶发/区域化路由问题：
    - `.../zh-sg/rates/...` 可能返回 404
    - 对该情况自动回退重试 `.../rates/...`
    - 偶发连接中断（Connection reset / chunked）：有限次重试
    """
    transient = (
        ChunkedEncodingError,
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
    )
    for attempt in range(3):
        try:
            r = sess.get(url, timeout=timeout)
            if r.status_code == 404 and "/zh-sg/rates/" in (url or "").lower():
                fallback = url.replace("/zh-sg/rates/", "/rates/")
                r2 = sess.get(fallback, timeout=timeout)
                if r2.status_code < 400:
                    return r2
            return r
        except transient:
            if attempt < 2:
                time.sleep(1.0 * (2**attempt))
                continue
            raise


@contextlib.contextmanager
def _maybank_ipv4_gai_only():
    """
    仅对 urllib3 的 getaddrinfo 族选择强制 IPv4。
    部分网络环境下 Python 默认会优先走异常慢的 IPv6，而本机浏览器可能走 IPv4。
    """
    try:
        import urllib3.util.connection as _uconn
    except ImportError:
        yield
        return
    old = getattr(_uconn, "allowed_gai_family", None)
    if old is None or not callable(old):
        yield
        return

    def _ipv4_family() -> int:
        return socket.AF_INET

    _uconn.allowed_gai_family = _ipv4_family  # type: ignore[assignment]
    try:
        yield
    finally:
        _uconn.allowed_gai_family = old  # type: ignore[assignment]


def _get_maybank2u_sgd_promo_page(
    main_sess: requests.Session,
    promo_url: str,
    read_timeout: float,
) -> Any:
    """
    Maybank2u 促销页：站点/CDN 对「脚本式」简单请求头常会拖死或断连；
    用更接近浏览器的头、先访问英文首页拿 Cookie，并尽量走 IPv4。

    若已安装 ``curl_cffi``，优先用其 **Chrome TLS 模拟**（与真机浏览器更接近），
    可显著改善「浏览器秒开、requests 一直超时」的情况；未安装则回退 ``requests``。
    """
    connect_s = min(25.0, max(12.0, float(read_timeout) * 0.2))
    read_s = max(90.0, float(read_timeout))
    tup_to = (connect_s, read_s)
    home = "https://www.maybank2u.com.sg/en/"

    try:
        from curl_cffi import requests as _creq  # type: ignore[import-not-found]
    except ImportError:
        _creq = None
    if _creq is not None:
        for _imp in ("chrome131", "chrome124", "chrome120", "chrome"):
            try:
                cs = _creq.Session(impersonate=_imp)
                if hasattr(cs, "trust_env"):
                    cs.trust_env = main_sess.trust_env
                try:
                    cs.get(home, timeout=min(40.0, read_s))
                except Exception:
                    pass
                r_cf = cs.get(
                    promo_url,
                    headers={"Referer": home, "Accept-Language": "en-SG,en;q=0.9"},
                    timeout=read_s,
                )
                r_cf.raise_for_status()
                return r_cf
            except Exception:
                continue

    mb_ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    base_headers = {
        "User-Agent": mb_ua,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-SG,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }

    s = requests.Session()
    s.trust_env = main_sess.trust_env
    s.headers.clear()
    s.headers.update(base_headers)

    with _maybank_ipv4_gai_only():
        try:
            s.get(home, timeout=(connect_s, min(40.0, read_s)))
        except requests.RequestException:
            pass
        nav_headers = {
            **base_headers,
            "Sec-Fetch-Site": "same-origin",
            "Referer": home,
        }
        return s.get(promo_url, headers=nav_headers, timeout=tup_to)


@safe_call(
    context="抓取与汇总（fetch_and_extract）",
    default_factory=lambda e, a, k: {},
)
def fetch_and_extract(
    url: str,
    timeout: float,
    use_env_proxy: bool,
    cimb_fcy_url: Optional[str] = DEFAULT_CIMB_FCY_URL,
    cimb_sgd_url: Optional[str] = DEFAULT_CIMB_SGD_URL,
    hl_fd_url: Optional[str] = DEFAULT_HL_FD_URL,
    hlf_promo_url: Optional[str] = DEFAULT_HLF_FD_URL,
    hsbc_td_url: Optional[str] = DEFAULT_HSBC_TD_URL,
    icbc_fd_url: Optional[str] = DEFAULT_ICBC_FD_URL,
    ocbc_fd_url: Optional[str] = DEFAULT_OCBC_FD_URL,
    rhb_fd_url: Optional[str] = DEFAULT_RHB_FD_URL,
    rhb_fcy_fd_url: Optional[str] = DEFAULT_RHB_FCY_FD_URL,
    sif_fd_url: Optional[str] = DEFAULT_SIF_FD_URL,
    scb_sgd_fd_url: Optional[str] = DEFAULT_SCB_SGD_TD_URL,
    scb_fcy_fd_url: Optional[str] = DEFAULT_SCB_FCY_FD_URL,
    sbi_sgd_fd_url: Optional[str] = DEFAULT_SBI_SGD_PROMO_URL,
    sbi_fcy_fd_url: Optional[str] = DEFAULT_SBI_USD_PROMO_URL,
    uob_sgd_fd_url: Optional[str] = DEFAULT_UOB_SGD_TD_URL,
    boc_promo_url: Optional[str] = DEFAULT_BOC_PROMO_URL,
    include_sgd_board: bool = True,
    citi_sgd_board_url: Optional[str] = DEFAULT_CITI_SGD_BOARD_URL,
    dbs_sgd_board_url: Optional[str] = DEFAULT_DBS_SGD_BOARD_URL,
    hl_sgd_board_url: Optional[str] = DEFAULT_HL_SGD_BOARD_URL,
    hlf_sgd_board_url: Optional[str] = DEFAULT_HLF_SGD_BOARD_URL,
    hsbc_sgd_board_url: Optional[str] = DEFAULT_HSBC_SGD_BOARD_URL,
    icbc_sgd_board_url: Optional[str] = DEFAULT_ICBC_SGD_BOARD_URL,
    icbc_fcy_board_url: Optional[str] = DEFAULT_ICBC_FCY_BOARD_URL,
    maybank_sgd_board_url: Optional[str] = DEFAULT_MAYBANK_SGD_BOARD_URL,
    ocbc_sgd_board_url: Optional[str] = DEFAULT_OCBC_SGD_BOARD_URL,
    rhb_sgd_board_pdf_url: Optional[str] = DEFAULT_RHB_SGD_BOARD_PDF_URL,
    sif_sgd_board_url: Optional[str] = DEFAULT_SIF_SGD_BOARD_URL,
    scb_sgd_board_url: Optional[str] = DEFAULT_SCB_SGD_BOARD_URL,
    sbi_sgd_board_url: Optional[str] = DEFAULT_SBI_SGD_BOARD_URL,
    uob_sgd_board_url: Optional[str] = DEFAULT_UOB_SGD_BOARD_URL,
    ocbc_fcy_board_url: Optional[str] = DEFAULT_OCBC_FCY_BOARD_URL,
    uob_fcy_board_url: Optional[str] = DEFAULT_UOB_FCY_BOARD_URL,
    hl_fcy_board_url: Optional[str] = DEFAULT_HL_FCY_BOARD_URL,
    hsbc_fcy_board_url: Optional[str] = DEFAULT_HSBC_FCY_BOARD_URL,
    maybank_fcy_board_url: Optional[str] = DEFAULT_MAYBANK_FCY_BOARD_URL,
    scb_fcy_board_url: Optional[str] = DEFAULT_SCB_FCY_BOARD_URL,
    sbi_fcy_board_url: Optional[str] = DEFAULT_SBI_FCY_BOARD_URL,
    rhb_fcy_board_pdf_url: Optional[str] = DEFAULT_RHB_FCY_BOARD_PDF_URL,
    bea_sgd_board_api_url: Optional[str] = DEFAULT_BEA_SGD_BOARD_API_URL,
    bea_fcy_board_api_url: Optional[str] = DEFAULT_BEA_FCY_BOARD_API_URL,
    boc_board_url: Optional[str] = DEFAULT_BOC_BOARD_URL,
    boc_follow_latest_from_index: bool = True,
    bea_sgd_promo_url: Optional[str] = DEFAULT_BEA_SGD_PROMO_URL,
    bea_fcy_promo_url: Optional[str] = DEFAULT_BEA_FCY_PROMO_URL,
    maybank_sgd_promo_url: Optional[str] = DEFAULT_MAYBANK_SGD_PROMO_URL,
    hsbc_fcy_promo_url: Optional[str] = DEFAULT_HSBC_FCY_PROMO_URL,
    dbs_fcy_board_api_url: Optional[str] = DEFAULT_DBS_FCY_BOARD_API_URL,
) -> Dict[str, Any]:
    """
    抓取 Citi 主页面 + 可选各家银行促销页/挂牌页，并汇总为统一 payload。

    payload 结构的目的：
    - 供后续 `write_rates_excel(data, ...)` 写入多 sheet Excel
    - 或供 `main()` 输出 JSON

    关键行为（与原主脚本保持一致）：
    1) 必抓 `url`（Citi all-promo）并抽取：
       - `sgd_time_deposit`
       - `fx_time_deposit_1m`
       - `other`（脚注/杂项利率，使用正则 best-effort）
    2) 若 URL 参数开启，则按银行逐一抓取其页面，并把解析结果合并到：
       - `sgd_merged`：新元相关利率合并结果
       - `fx_merged`：外币相关利率合并结果
    3) 若 `include_sgd_board=True`，则继续抓取/解析各家“挂牌板块”并写入：
       - `sgd_board_merged` + 各银行 `*_sgd_board` 元信息
       - `fx_board_merged` + 各银行 `*_fcy_board` 元信息
    4) 默认对中行新加坡促销/挂牌：先请求官网栏目列表页，按文档顺序取第一条 `bi31`/`bi32`
       公告 HTML 再抓取；`boc_follow_latest_from_index=False` 时严格使用传入的直达 URL。
    """
    # 解析函数来自 bank_extractors.impl（与主脚本解耦）
    _session = _x._session
    _icbc_singapore_get = _x._icbc_singapore_get
    extract_sgd_time_deposit = _x.extract_sgd_time_deposit
    extract_fx_time_deposit = _x.extract_fx_time_deposit

    extract_cimb_fcy_promo = _x.extract_cimb_fcy_promo
    merge_fx_citi_cimb = _x.merge_fx_citi_cimb
    extract_cimb_sgd_rates = _x.extract_cimb_sgd_rates
    build_sgd_merged = _x.build_sgd_merged

    extract_hl_sgd_promo = _x.extract_hl_sgd_promo
    extract_hl_fcy_promo = _x.extract_hl_fcy_promo
    append_hl_sgd_rows = _x.append_hl_sgd_rows
    append_hl_fcy_rows = _x.append_hl_fcy_rows

    extract_hlf_sgd_promo = _x.extract_hlf_sgd_promo
    append_hlf_sgd_rows = _x.append_hlf_sgd_rows

    extract_hsbc_sgd_promo = _x.extract_hsbc_sgd_promo
    append_hsbc_sgd_rows = _x.append_hsbc_sgd_rows
    append_hsbc_fcy_promo_rows = _x.append_hsbc_fcy_promo_rows
    extract_hsbc_fcy_board = _x.extract_hsbc_fcy_board
    extract_maybank_sgd_promo = _x.extract_maybank_sgd_promo
    append_maybank_sgd_rows = _x.append_maybank_sgd_rows

    extract_icbc_fd_promo = _x.extract_icbc_fd_promo
    append_icbc_sgd_rows = _x.append_icbc_sgd_rows
    append_icbc_fx_rows = _x.append_icbc_fx_rows

    extract_ocbc_sgd_promo = _x.extract_ocbc_sgd_promo
    append_ocbc_sgd_rows = _x.append_ocbc_sgd_rows

    extract_rhb_fd_promo = _x.extract_rhb_fd_promo
    append_rhb_sgd_rows = _x.append_rhb_sgd_rows
    extract_rhb_fcy_promo = _x.extract_rhb_fcy_promo
    append_rhb_fcy_rows = _x.append_rhb_fcy_rows

    extract_sif_fd_promo = _x.extract_sif_fd_promo
    append_sif_sgd_rows = _x.append_sif_sgd_rows

    extract_uob_sgd_promo = _x.extract_uob_sgd_promo
    extract_uob_fcy_promo = _x.extract_uob_fcy_promo
    append_uob_sgd_rows = _x.append_uob_sgd_rows
    append_uob_fcy_rows = _x.append_uob_fcy_rows

    extract_scb_sgd_fd_promo = _x.extract_scb_sgd_fd_promo
    append_scb_sgd_rows = _x.append_scb_sgd_rows
    extract_scb_fcy_fd_promo = _x.extract_scb_fcy_fd_promo
    append_scb_fcy_rows = _x.append_scb_fcy_rows

    extract_sbi_sgd_promo = _x.extract_sbi_sgd_promo
    append_sbi_sgd_rows = _x.append_sbi_sgd_rows
    extract_sbi_fcy_promo = _x.extract_sbi_fcy_promo
    append_sbi_fcy_rows = _x.append_sbi_fcy_rows

    extract_boc_promo = _x.extract_boc_promo
    append_boc_sgd_rows = _x.append_boc_sgd_rows
    append_boc_fx_rows = _x.append_boc_fx_rows
    extract_bea_sgd_promo = _x.extract_bea_sgd_promo
    append_bea_sgd_promo_rows = _x.append_bea_sgd_promo_rows
    append_bea_fcy_promo_rows = _x.append_bea_fcy_promo_rows

    extract_cimb_sgd_board = _x.extract_cimb_sgd_board
    extract_citi_sgd_board = _x.extract_citi_sgd_board
    extract_dbs_sgd_board = _x.extract_dbs_sgd_board
    extract_dbs_fcy_board_from_api = _x.extract_dbs_fcy_board_from_api
    extract_hl_sgd_board = _x.extract_hl_sgd_board
    extract_hlf_sgd_board = _x.extract_hlf_sgd_board
    extract_hsbc_sgd_board = _x.extract_hsbc_sgd_board
    extract_icbc_sgd_board = _x.extract_icbc_sgd_board
    extract_icbc_fcy_board = _x.extract_icbc_fcy_board
    extract_ocbc_fcy_board = _x.extract_ocbc_fcy_board
    extract_uob_fcy_board_from_api = _x.extract_uob_fcy_board_from_api
    extract_maybank_sgd_board = _x.extract_maybank_sgd_board
    extract_ocbc_sgd_board = _x.extract_ocbc_sgd_board
    extract_rhb_sgd_board_pdf = _x.extract_rhb_sgd_board_pdf
    extract_sif_sgd_board = _x.extract_sif_sgd_board
    extract_scb_sgd_board = _x.extract_scb_sgd_board
    extract_sbi_sgd_board = _x.extract_sbi_sgd_board
    extract_uob_sgd_board = _x.extract_uob_sgd_board

    extract_hl_fcy_board = _x.extract_hl_fcy_board
    extract_hsbc_fcy_board = _x.extract_hsbc_fcy_board
    extract_maybank_fcy_board = _x.extract_maybank_fcy_board
    extract_scb_fcy_board = _x.extract_scb_fcy_board
    extract_sbi_fcy_board = _x.extract_sbi_fcy_board
    extract_rhb_fcy_board_pdf = _x.extract_rhb_fcy_board_pdf

    extract_bea_sgd_board_from_json = _x.extract_bea_sgd_board_from_json
    extract_bea_fcy_board_from_json = _x.extract_bea_fcy_board_from_json
    extract_boc_sgd_fcy_board = _x.extract_boc_sgd_fcy_board

    # 1) 先抓 Citi all-promo 主页面并抽取最基础的核心 payload。
    sess = _session(use_env_proxy)
    r = sess.get(url, timeout=timeout)
    r.raise_for_status()
    html = r.text
    soup = BeautifulSoup(html, "lxml")
    payload: Dict[str, Any] = {
        "source_url": r.url,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "sgd_time_deposit": extract_sgd_time_deposit(soup),
        "fx_time_deposit_1m": extract_fx_time_deposit(soup),
        # 业务侧已弃用“其他利率”抓取，保持空对象以兼容下游 DataFrame 构建逻辑。
        "other": {},
    }

    # 2) CIMB FCY promo + merge 到 fx_merged
    cimb_block: Dict[str, Any] = {}
    if cimb_fcy_url:
        try:
            r2 = sess.get(cimb_fcy_url, timeout=timeout)
            r2.raise_for_status()
            soup2 = BeautifulSoup(r2.text, "lxml")
            cimb_block = extract_cimb_fcy_promo(soup2)
            cimb_block["source_url"] = r2.url
        except requests.RequestException as e:
            cimb_block = {
                "error": str(e),
                "currencies": {},
                "notes": [],
                "source_url": cimb_fcy_url,
            }
    payload["cimb_fcy_promo"] = cimb_block
    payload["fx_merged"] = merge_fx_citi_cimb(
        payload["fx_time_deposit_1m"],
        cimb_block if cimb_block and not cimb_block.get("error") else None,
    )

    # 3) CIMB SGD rates -> build sgd_merged
    cimb_sgd_soup: Optional[BeautifulSoup] = None
    cimb_sgd_block: Dict[str, Any] = {}
    if cimb_sgd_url:
        try:
            r3 = sess.get(cimb_sgd_url, timeout=timeout)
            r3.raise_for_status()
            cimb_sgd_soup = BeautifulSoup(r3.text, "lxml")
            cimb_sgd_block = extract_cimb_sgd_rates(cimb_sgd_soup)
            cimb_sgd_block["source_url"] = r3.url
        except requests.RequestException as e:
            cimb_sgd_block = {"error": str(e), "source_url": cimb_sgd_url}
    payload["cimb_sgd_rates"] = cimb_sgd_block
    payload["sgd_merged"] = build_sgd_merged(
        payload["sgd_time_deposit"],
        cimb_sgd_block if cimb_sgd_block and not cimb_sgd_block.get("error") else None,
    )

    # 4) HL：SGD+FCY promo 同页（把 rows append 进 merged）
    hl_block: Dict[str, Any] = {}
    if hl_fd_url:
        try:
            r4 = sess.get(hl_fd_url, timeout=timeout)
            r4.raise_for_status()
            soup4 = BeautifulSoup(r4.text, "lxml")
            hl_block = extract_hl_sgd_promo(soup4)
            hl_block.update(extract_hl_fcy_promo(soup4))
            hl_block["source_url"] = r4.url
        except requests.RequestException as e:
            hl_block = {"error": str(e), "source_url": hl_fd_url}
    payload["hl_fd_promo"] = hl_block
    if hl_block and not hl_block.get("error"):
        payload["sgd_merged"] = append_hl_sgd_rows(payload["sgd_merged"], hl_block)
        payload["fx_merged"] = append_hl_fcy_rows(payload["fx_merged"], hl_block)

    # 5) HLF：只做 SGD merge
    hlf_block: Dict[str, Any] = {}
    if hlf_promo_url:
        try:
            r5 = sess.get(hlf_promo_url, timeout=timeout)
            r5.raise_for_status()
            soup5 = BeautifulSoup(r5.text, "lxml")
            hlf_block = extract_hlf_sgd_promo(soup5)
            hlf_block["source_url"] = r5.url
        except requests.RequestException as e:
            hlf_block = {"error": str(e), "source_url": hlf_promo_url}
    payload["hlf_promo"] = hlf_block
    if hlf_block and not hlf_block.get("error"):
        payload["sgd_merged"] = append_hlf_sgd_rows(payload["sgd_merged"], hlf_block)

    # 6) HSBC：SGD merge
    hsbc_block: Dict[str, Any] = {}
    if hsbc_td_url:
        try:
            hs_headers = {
                **dict(sess.headers),
                "Accept-Language": "zh-SG,zh-CN;q=0.9,en-SG;q=0.8,en;q=0.7",
            }
            r6 = sess.get(hsbc_td_url, timeout=timeout, headers=hs_headers)
            r6.raise_for_status()
            soup6 = BeautifulSoup(r6.text, "lxml")
            hsbc_block = extract_hsbc_sgd_promo(soup6)
            hsbc_block["source_url"] = r6.url
        except requests.RequestException as e:
            hsbc_block = {"error": str(e), "source_url": hsbc_td_url}
    payload["hsbc_td_promo"] = hsbc_block
    if hsbc_block and not hsbc_block.get("error"):
        payload["sgd_merged"] = append_hsbc_sgd_rows(payload["sgd_merged"], hsbc_block)
    hsbc_fcy_src = (hsbc_fcy_promo_url or "").strip()
    hsbc_fcy_promo: Dict[str, Any] = {}
    _transient_dl = (
        ChunkedEncodingError,
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
    )
    last_hsfxp_err: BaseException | None = None
    if hsbc_fcy_src:
        for _pdf_attempt in range(3):
            try:
                r_hsfxp = sess.get(hsbc_fcy_src, timeout=timeout)
                r_hsfxp.raise_for_status()
                low = hsbc_fcy_src.lower().split("?", 1)[0]
                if low.endswith(".pdf"):
                    hsbc_fcy_rows = _x._extract_hsbc_fcy_board_from_pdf(r_hsfxp.content, "Personal Banking")
                else:
                    hsbc_fcy_rows = extract_hsbc_fcy_board(BeautifulSoup(r_hsfxp.text, "lxml"))
                if not hsbc_fcy_rows:
                    raise ValueError("HSBC FCY promo: no rows extracted")
                hsbc_fcy_promo = {"source_url": r_hsfxp.url, "row_count": len(hsbc_fcy_rows)}
                payload["fx_merged"] = append_hsbc_fcy_promo_rows(payload["fx_merged"], hsbc_fcy_rows)
                last_hsfxp_err = None
                break
            except _transient_dl as e:
                last_hsfxp_err = e
                if _pdf_attempt < 2:
                    time.sleep(1.0 * (2**_pdf_attempt))
            except requests.RequestException as e:
                last_hsfxp_err = e
                break
            except Exception as e:
                last_hsfxp_err = e
                break
        if last_hsfxp_err is not None and hsbc_fcy_promo.get("row_count") is None and not hsbc_fcy_promo.get("error"):
            hsbc_fcy_promo = {"error": str(last_hsfxp_err), "source_url": hsbc_fcy_src}
    payload["hsbc_fcy_promo"] = hsbc_fcy_promo

    mb_primary = (maybank_sgd_promo_url or "").strip()
    _mb_default = "https://www.maybank2u.com.sg/en/promotions/deposits/sgd-time-deposit.page"
    maybank_sgd_promo_urls_list: List[str] = []
    if mb_primary:
        maybank_sgd_promo_urls_list.append(mb_primary)
    if _mb_default not in maybank_sgd_promo_urls_list:
        maybank_sgd_promo_urls_list.append(_mb_default)
    maybank_sgd_promo_urls = tuple(maybank_sgd_promo_urls_list)
    maybank_sgd_promo: Dict[str, Any] = {}
    last_mb_err: Optional[BaseException] = None
    mb_ok = False
    mb_timeouts = (
        max(float(timeout), 45.0),
        max(float(timeout), 75.0),
        max(float(timeout), 120.0),
        max(float(timeout), 180.0),
    )
    for mb_url in maybank_sgd_promo_urls:
        for mb_attempt in range(len(mb_timeouts)):
            t_mb = mb_timeouts[mb_attempt]
            try:
                r_mb = _get_maybank2u_sgd_promo_page(sess, mb_url, t_mb)
                r_mb.raise_for_status()
                maybank_sgd_promo = extract_maybank_sgd_promo(BeautifulSoup(r_mb.text, "lxml"))
                maybank_sgd_promo["source_url"] = r_mb.url
                last_mb_err = None
                mb_ok = True
                break
            except Exception as e:
                last_mb_err = e
                if mb_attempt < len(mb_timeouts) - 1:
                    time.sleep(1.0 * (2**mb_attempt))
        if mb_ok:
            break
    if not mb_ok and last_mb_err is not None:
        maybank_sgd_promo = {"error": str(last_mb_err), "source_url": maybank_sgd_promo_urls[0]}
    payload["maybank_sgd_promo"] = maybank_sgd_promo
    if maybank_sgd_promo and not maybank_sgd_promo.get("error"):
        payload["sgd_merged"] = append_maybank_sgd_rows(payload["sgd_merged"], maybank_sgd_promo)

    # 7) ICBC：SGD + FCY
    icbc_block: Dict[str, Any] = {}
    if icbc_fd_url:
        try:
            r7 = _icbc_singapore_get(sess, icbc_fd_url, timeout=timeout)
            r7.raise_for_status()
            soup7 = BeautifulSoup(r7.text, "lxml")
            icbc_block = extract_icbc_fd_promo(soup7)
            icbc_block["source_url"] = r7.url
        except requests.RequestException as e:
            icbc_block = {"error": str(e), "source_url": icbc_fd_url}
    payload["icbc_fd_promo"] = icbc_block
    if icbc_block and not icbc_block.get("error"):
        payload["sgd_merged"] = append_icbc_sgd_rows(payload["sgd_merged"], icbc_block)
        payload["fx_merged"] = append_icbc_fx_rows(payload["fx_merged"], icbc_block)

    # 8) OCBC：SGD
    ocbc_block: Dict[str, Any] = {}
    if ocbc_fd_url:
        try:
            r8 = sess.get(ocbc_fd_url, timeout=timeout)
            r8.raise_for_status()
            soup8 = BeautifulSoup(r8.text, "lxml")
            ocbc_block = extract_ocbc_sgd_promo(soup8)
            ocbc_block["source_url"] = r8.url
        except requests.RequestException as e:
            ocbc_block = {"error": str(e), "source_url": ocbc_fd_url}
    payload["ocbc_fd_promo"] = ocbc_block
    if ocbc_block and not ocbc_block.get("error"):
        payload["sgd_merged"] = append_ocbc_sgd_rows(payload["sgd_merged"], ocbc_block)

    # 9) RHB：SGD + FCY
    rhb_block: Dict[str, Any] = {}
    if rhb_fd_url:
        try:
            r9 = sess.get(rhb_fd_url, timeout=timeout)
            r9.raise_for_status()
            soup9 = BeautifulSoup(r9.text, "lxml")
            rhb_block = extract_rhb_fd_promo(soup9)
            rhb_block["source_url"] = r9.url
        except requests.RequestException as e:
            rhb_block = {"error": str(e), "source_url": rhb_fd_url}
    payload["rhb_fd_promo"] = rhb_block
    if rhb_block and not rhb_block.get("error"):
        payload["sgd_merged"] = append_rhb_sgd_rows(payload["sgd_merged"], rhb_block)

    rhb_fcy_block: Dict[str, Any] = {}
    if rhb_fcy_fd_url:
        try:
            r9b = sess.get(rhb_fcy_fd_url, timeout=timeout)
            r9b.raise_for_status()
            soup9b = BeautifulSoup(r9b.text, "lxml")
            rhb_fcy_block = extract_rhb_fcy_promo(soup9b)
            rhb_fcy_block["source_url"] = r9b.url
        except requests.RequestException as e:
            rhb_fcy_block = {"error": str(e), "source_url": rhb_fcy_fd_url}
    payload["rhb_fcy_fd_promo"] = rhb_fcy_block
    if rhb_fcy_block and not rhb_fcy_block.get("error"):
        payload["fx_merged"] = append_rhb_fcy_rows(payload["fx_merged"], rhb_fcy_block)

    # 10) SingFinance：SGD
    sif_block: Dict[str, Any] = {}
    if sif_fd_url:
        try:
            r10 = sess.get(sif_fd_url, timeout=timeout)
            r10.raise_for_status()
            soup10 = BeautifulSoup(r10.text, "lxml")
            sif_block = extract_sif_fd_promo(soup10)
            sif_block["source_url"] = r10.url
        except requests.RequestException as e:
            sif_block = {"error": str(e), "source_url": sif_fd_url}
    payload["sif_fd_promo"] = sif_block
    if sif_block and not sif_block.get("error"):
        payload["sgd_merged"] = append_sif_sgd_rows(payload["sgd_merged"], sif_block)

    # 11) UOB：同页检测 FCY promo 并分别 merge
    uob_block_sgd: Dict[str, Any] = {}
    uob_block_fcy: Dict[str, Any] = {}
    if uob_sgd_fd_url:
        try:
            r_uob = sess.get(uob_sgd_fd_url, timeout=timeout)
            r_uob.raise_for_status()
            soup_uob = BeautifulSoup(r_uob.text, "lxml")
            uob_block_sgd = extract_uob_sgd_promo(soup_uob)
            uob_block_sgd["source_url"] = r_uob.url

            # Same page: detect FCY promo table existence (and parse if present).
            uob_block_fcy = extract_uob_fcy_promo(soup_uob)
            uob_block_fcy["source_url"] = r_uob.url
        except requests.RequestException as e:
            uob_block_sgd = {"error": str(e), "source_url": uob_sgd_fd_url}
            uob_block_fcy = {"error": str(e), "source_url": uob_sgd_fd_url}
    payload["uob_sgd_fd_promo"] = uob_block_sgd
    payload["uob_fcy_promo"] = uob_block_fcy
    if uob_block_sgd and not uob_block_sgd.get("error"):
        payload["sgd_merged"] = append_uob_sgd_rows(payload["sgd_merged"], uob_block_sgd)
    if uob_block_fcy and not uob_block_fcy.get("error"):
        if uob_block_fcy.get("has_fcy_promo_table"):
            payload["fx_merged"] = append_uob_fcy_rows(payload["fx_merged"], uob_block_fcy)

    # 12) SCB：SGD + FCY
    scb_block: Dict[str, Any] = {}
    if scb_sgd_fd_url:
        try:
            r11 = sess.get(scb_sgd_fd_url, timeout=timeout)
            r11.raise_for_status()
            soup11 = BeautifulSoup(r11.text, "lxml")
            scb_block = extract_scb_sgd_fd_promo(soup11)
            scb_block["source_url"] = r11.url
        except requests.RequestException as e:
            scb_block = {"error": str(e), "source_url": scb_sgd_fd_url}
    payload["scb_sgd_promo"] = scb_block
    if scb_block and not scb_block.get("error"):
        payload["sgd_merged"] = append_scb_sgd_rows(payload["sgd_merged"], scb_block)

    scb_fcy_block: Dict[str, Any] = {}
    if scb_fcy_fd_url:
        try:
            r12 = sess.get(scb_fcy_fd_url, timeout=timeout)
            r12.raise_for_status()
            soup12 = BeautifulSoup(r12.text, "lxml")
            scb_fcy_block = extract_scb_fcy_fd_promo(soup12)
            scb_fcy_block["source_url"] = r12.url
        except requests.RequestException as e:
            scb_fcy_block = {"error": str(e), "source_url": scb_fcy_fd_url}
    payload["scb_fcy_fd_promo"] = scb_fcy_block
    if scb_fcy_block and not scb_fcy_block.get("error"):
        payload["fx_merged"] = append_scb_fcy_rows(payload["fx_merged"], scb_fcy_block)

    # 13) SBI：SGD + FCY（FCY 即 USD 表/同源）
    sbi_block: Dict[str, Any] = {}
    if sbi_sgd_fd_url:
        try:
            r13 = sess.get(sbi_sgd_fd_url, timeout=timeout)
            r13.raise_for_status()
            soup13 = BeautifulSoup(r13.text, "lxml")
            sbi_block = extract_sbi_sgd_promo(soup13)
            sbi_block["source_url"] = r13.url
        except requests.RequestException as e:
            sbi_block = {"error": str(e), "source_url": sbi_sgd_fd_url}
    payload["sbi_sgd_promo"] = sbi_block
    if sbi_block and not sbi_block.get("error"):
        payload["sgd_merged"] = append_sbi_sgd_rows(payload["sgd_merged"], sbi_block)

    sbi_fcy_block: Dict[str, Any] = {}
    if sbi_fcy_fd_url:
        try:
            r14 = sess.get(sbi_fcy_fd_url, timeout=timeout)
            r14.raise_for_status()
            soup14 = BeautifulSoup(r14.text, "lxml")
            sbi_fcy_block = extract_sbi_fcy_promo(soup14)
            sbi_fcy_block["source_url"] = r14.url
        except requests.RequestException as e:
            sbi_fcy_block = {"error": str(e), "source_url": sbi_fcy_fd_url}
    payload["sbi_fcy_promo"] = sbi_fcy_block
    if sbi_fcy_block and not sbi_fcy_block.get("error"):
        payload["fx_merged"] = append_sbi_fcy_rows(payload["fx_merged"], sbi_fcy_block)

    # 14) BOC：SGD + FCY 同页面抓取与 merge（默认同次运行先读栏目页取置顶公告链）
    boc_block: Dict[str, Any] = {}
    if boc_promo_url:
        promo_index_url, _board_index_for_locale = _boc_sg_promo_and_board_index_urls(
            boc_promo_url or "",
            boc_board_url or "",
        )
        boc_promo_fetch, boc_promo_res = _resolve_boc_sg_article_via_index(
            sess,
            configured_url=boc_promo_url,
            index_url=promo_index_url,
            bi_segment="bi31",
            timeout=timeout,
            enabled=boc_follow_latest_from_index,
        )
        try:
            rboc = sess.get(boc_promo_fetch, timeout=timeout)
            rboc.raise_for_status()
            rboc.encoding = rboc.apparent_encoding or rboc.encoding
            sboc = BeautifulSoup(rboc.text, "lxml")
            boc_block = extract_boc_promo(sboc)
            boc_block["source_url"] = rboc.url
            boc_block["fetched_at_utc"] = payload.get("fetched_at_utc")
            boc_block["url_resolution"] = boc_promo_res
        except requests.RequestException as e:
            boc_block = {"error": str(e), "source_url": boc_promo_fetch}
            boc_block["url_resolution"] = boc_promo_res
    payload["boc_promo"] = boc_block
    if boc_block and not boc_block.get("error"):
        payload["sgd_merged"] = append_boc_sgd_rows(payload["sgd_merged"], boc_block)
        payload["fx_merged"] = append_boc_fx_rows(payload["fx_merged"], boc_block)

    # 14.5) BEA promo pages（URL 可由 url_params.xlsx 覆盖）
    bea_sgd_promo: Dict[str, Any] = {}
    _bea_sgd_u = (bea_sgd_promo_url or "").strip()
    if _bea_sgd_u:
        try:
            r_bea_p = sess.get(_bea_sgd_u, timeout=timeout)
            r_bea_p.raise_for_status()
            s_bea_p = BeautifulSoup(r_bea_p.text, "lxml")
            bea_sgd_promo = extract_bea_sgd_promo(s_bea_p)
            bea_sgd_promo["source_url"] = r_bea_p.url
        except requests.RequestException as e:
            bea_sgd_promo = {"error": str(e), "source_url": _bea_sgd_u}
    payload["bea_sgd_promo"] = bea_sgd_promo
    if bea_sgd_promo and not bea_sgd_promo.get("error"):
        payload["sgd_merged"] = append_bea_sgd_promo_rows(payload["sgd_merged"], bea_sgd_promo)

    bea_fcy_promo: Dict[str, Any] = {}
    _bea_fcy_u = (bea_fcy_promo_url or "").strip()
    if _bea_fcy_u:
        try:
            r_bea_fp = sess.get(_bea_fcy_u, timeout=timeout)
            r_bea_fp.raise_for_status()
            txt = re.sub(r"\s+", " ", BeautifulSoup(r_bea_fp.text, "lxml").get_text(" ", strip=True))
            bea_fcy_promo = {
                "source_url": r_bea_fp.url,
                "note_text": txt[:240] if txt else "",
            }
        except requests.RequestException as e:
            bea_fcy_promo = {"error": str(e), "source_url": _bea_fcy_u}
    payload["bea_fcy_promo"] = bea_fcy_promo
    if bea_fcy_board_api_url:
        try:
            r_bea_fp_api = sess.post(bea_fcy_board_api_url, timeout=timeout)
            r_bea_fp_api.raise_for_status()
            bea_fcy_rows_for_promo = extract_bea_fcy_board_from_json(r_bea_fp_api.json())
            payload["fx_merged"] = append_bea_fcy_promo_rows(
                payload["fx_merged"],
                bea_fcy_rows_for_promo,
            )
        except requests.RequestException:
            pass

    # ------------------------------------------------------------
    # 15) SGD/FCY board（挂牌板块）可选抓取与合并
    # ------------------------------------------------------------
    sgd_board_merged: List[Dict[str, Any]] = []
    citi_sgd_board_meta: Dict[str, Any] = {}
    dbs_sgd_board_meta: Dict[str, Any] = {}
    hl_sgd_board_meta: Dict[str, Any] = {}
    hlf_sgd_board_meta: Dict[str, Any] = {}
    hsbc_sgd_board_meta: Dict[str, Any] = {}
    icbc_sgd_board_meta: Dict[str, Any] = {}
    maybank_sgd_board_meta: Dict[str, Any] = {}
    dbs_fcy_board_meta: Dict[str, Any] = {}
    ocbc_sgd_board_meta: Dict[str, Any] = {}
    rhb_sgd_board_meta: Dict[str, Any] = {}
    sif_sgd_board_meta: Dict[str, Any] = {}
    scb_sgd_board_meta: Dict[str, Any] = {}
    sbi_sgd_board_meta: Dict[str, Any] = {}
    uob_sgd_board_meta: Dict[str, Any] = {}

    fx_board_merged: List[Dict[str, Any]] = []
    hl_fcy_board_meta: Dict[str, Any] = {}
    hsbc_fcy_board_meta: Dict[str, Any] = {}
    maybank_fcy_board_meta: Dict[str, Any] = {}
    scb_fcy_board_meta: Dict[str, Any] = {}
    sbi_fcy_board_meta: Dict[str, Any] = {}
    rhb_fcy_board_meta: Dict[str, Any] = {}
    bea_sgd_board_meta: Dict[str, Any] = {}
    bea_fcy_board_meta: Dict[str, Any] = {}
    boc_sgd_board_meta: Dict[str, Any] = {}
    boc_fcy_board_meta: Dict[str, Any] = {}
    icbc_fcy_board_meta: Dict[str, Any] = {}
    ocbc_fcy_board_meta: Dict[str, Any] = {}
    uob_fcy_board_meta: Dict[str, Any] = {}

    if include_sgd_board:
        # 15.1) Citi board / 各银行 SGD board
        if cimb_sgd_soup is not None:
            sgd_board_merged.extend(extract_cimb_sgd_board(cimb_sgd_soup))
        if citi_sgd_board_url:
            try:
                rc = sess.get(citi_sgd_board_url, timeout=timeout)
                rc.raise_for_status()
                sc = BeautifulSoup(rc.text, "lxml")
                cr = extract_citi_sgd_board(sc)
                sgd_board_merged.extend(cr)
                citi_sgd_board_meta = {"source_url": rc.url, "row_count": len(cr)}
            except requests.RequestException as e:
                citi_sgd_board_meta = {"error": str(e), "source_url": citi_sgd_board_url}

        if dbs_sgd_board_url:
            try:
                rd = sess.get(dbs_sgd_board_url, timeout=timeout)
                rd.raise_for_status()
                sd = BeautifulSoup(rd.text, "lxml")
                dr = extract_dbs_sgd_board(sd)
                sgd_board_merged.extend(dr)
                dbs_sgd_board_meta = {"source_url": rd.url, "row_count": len(dr)}
            except requests.RequestException as e:
                dbs_sgd_board_meta = {"error": str(e), "source_url": dbs_sgd_board_url}

        if hl_sgd_board_url:
            try:
                rh = sess.get(hl_sgd_board_url, timeout=timeout)
                rh.raise_for_status()
                sh = BeautifulSoup(rh.text, "lxml")
                hr = extract_hl_sgd_board(sh)
                sgd_board_merged.extend(hr)
                hl_sgd_board_meta = {"source_url": rh.url, "row_count": len(hr)}
            except requests.RequestException as e:
                hl_sgd_board_meta = {"error": str(e), "source_url": hl_sgd_board_url}

        if hlf_sgd_board_url:
            try:
                rf = sess.get(hlf_sgd_board_url, timeout=timeout)
                rf.raise_for_status()
                sf = BeautifulSoup(rf.text, "lxml")
                fr = extract_hlf_sgd_board(sf)
                sgd_board_merged.extend(fr)
                hlf_sgd_board_meta = {"source_url": rf.url, "row_count": len(fr)}
            except requests.RequestException as e:
                hlf_sgd_board_meta = {"error": str(e), "source_url": hlf_sgd_board_url}

        if hsbc_sgd_board_url:
            try:
                rh_sb = _get_with_hsbc_rates_fallback(sess, hsbc_sgd_board_url, timeout)
                rh_sb.raise_for_status()
                sh_sb = BeautifulSoup(rh_sb.text, "lxml")
                hsr = extract_hsbc_sgd_board(sh_sb)
                sgd_board_merged.extend(hsr)
                hsbc_sgd_board_meta = {"source_url": rh_sb.url, "row_count": len(hsr)}
            except requests.RequestException as e:
                hsbc_sgd_board_meta = {"error": str(e), "source_url": hsbc_sgd_board_url}

        icbc_board_soup: Optional[BeautifulSoup] = None
        icbc_board_source_url: Optional[str] = None
        if icbc_sgd_board_url:
            try:
                ri_bc = _icbc_singapore_get(sess, icbc_sgd_board_url, timeout=timeout)
                ri_bc.raise_for_status()
                icbc_board_soup = BeautifulSoup(ri_bc.text, "lxml")
                icbc_board_source_url = ri_bc.url
                icr = extract_icbc_sgd_board(icbc_board_soup)
                sgd_board_merged.extend(icr)
                icbc_sgd_board_meta = {"source_url": ri_bc.url, "row_count": len(icr)}
            except requests.RequestException as e:
                icbc_sgd_board_meta = {"error": str(e), "source_url": icbc_sgd_board_url}

        if icbc_fcy_board_url:
            try:
                same_icbc_page = (
                    icbc_sgd_board_url
                    and icbc_fcy_board_url
                    and icbc_sgd_board_url.rstrip("/").lower()
                    == icbc_fcy_board_url.rstrip("/").lower()
                )
                if same_icbc_page and icbc_board_soup is not None:
                    fcy_soup = icbc_board_soup
                    fcy_src = icbc_board_source_url or icbc_fcy_board_url
                else:
                    r_if = _icbc_singapore_get(sess, icbc_fcy_board_url, timeout=timeout)
                    r_if.raise_for_status()
                    fcy_soup = BeautifulSoup(r_if.text, "lxml")
                    fcy_src = r_if.url
                rows_if = extract_icbc_fcy_board(fcy_soup)
                fx_board_merged.extend(rows_if)
                icbc_fcy_board_meta = {"source_url": fcy_src, "row_count": len(rows_if)}
            except requests.RequestException as e:
                icbc_fcy_board_meta = {
                    "error": str(e),
                    "source_url": icbc_fcy_board_url,
                }

        if maybank_sgd_board_url:
            try:
                rm = sess.get(maybank_sgd_board_url, timeout=timeout)
                rm.raise_for_status()
                sm = BeautifulSoup(rm.text, "lxml")
                mr = extract_maybank_sgd_board(sm)
                sgd_board_merged.extend(mr)
                maybank_sgd_board_meta = {"source_url": rm.url, "row_count": len(mr)}
            except requests.RequestException as e:
                maybank_sgd_board_meta = {"error": str(e), "source_url": maybank_sgd_board_url}

        if ocbc_sgd_board_url:
            try:
                ro = sess.get(ocbc_sgd_board_url, timeout=timeout)
                ro.raise_for_status()
                so = BeautifulSoup(ro.text, "lxml")
                ocr = extract_ocbc_sgd_board(so)
                sgd_board_merged.extend(ocr)
                ocbc_sgd_board_meta = {"source_url": ro.url, "row_count": len(ocr)}
            except requests.RequestException as e:
                ocbc_sgd_board_meta = {"error": str(e), "source_url": ocbc_sgd_board_url}

        if rhb_sgd_board_pdf_url:
            try:
                rr = sess.get(rhb_sgd_board_pdf_url, timeout=timeout)
                rr.raise_for_status()
                rhb_pdf_rows = extract_rhb_sgd_board_pdf(rr.content)
                sgd_board_merged.extend(rhb_pdf_rows)
                rhb_sgd_board_meta = {"source_url": rr.url, "row_count": len(rhb_pdf_rows)}
            except requests.RequestException as e:
                rhb_sgd_board_meta = {"error": str(e), "source_url": rhb_sgd_board_pdf_url}

        if sif_sgd_board_url:
            try:
                rsf = sess.get(sif_sgd_board_url, timeout=timeout)
                rsf.raise_for_status()
                ssf = BeautifulSoup(rsf.text, "lxml")
                sfr = extract_sif_sgd_board(ssf)
                sgd_board_merged.extend(sfr)
                sif_sgd_board_meta = {"source_url": rsf.url, "row_count": len(sfr)}
            except requests.RequestException as e:
                sif_sgd_board_meta = {"error": str(e), "source_url": sif_sgd_board_url}

        if scb_sgd_board_url:
            try:
                rscb = sess.get(scb_sgd_board_url, timeout=timeout)
                rscb.raise_for_status()
                sscb = BeautifulSoup(rscb.text, "lxml")
                scr = extract_scb_sgd_board(sscb)
                sgd_board_merged.extend(scr)
                scb_sgd_board_meta = {"source_url": rscb.url, "row_count": len(scr)}
            except requests.RequestException as e:
                scb_sgd_board_meta = {"error": str(e), "source_url": scb_sgd_board_url}

        if sbi_sgd_board_url:
            try:
                rsbi = sess.get(sbi_sgd_board_url, timeout=timeout)
                rsbi.raise_for_status()
                ssbi = BeautifulSoup(rsbi.text, "lxml")
                sbr = extract_sbi_sgd_board(ssbi)
                sgd_board_merged.extend(sbr)
                sbi_sgd_board_meta = {"source_url": rsbi.url, "row_count": len(sbr)}
            except requests.RequestException as e:
                sbi_sgd_board_meta = {"error": str(e), "source_url": sbi_sgd_board_url}

        if uob_sgd_board_url:
            try:
                ruob = sess.get(uob_sgd_board_url, timeout=timeout)
                ruob.raise_for_status()
                suob = BeautifulSoup(ruob.text, "lxml")
                ubr = extract_uob_sgd_board(suob)
                sgd_board_merged.extend(ubr)
                uob_sgd_board_meta = {"source_url": ruob.url, "row_count": len(ubr)}
            except requests.RequestException as e:
                uob_sgd_board_meta = {"error": str(e), "source_url": uob_sgd_board_url}

        # 15.2) FCY board（外币挂牌）
        if hl_fcy_board_url:
            try:
                r_hlfx = sess.get(hl_fcy_board_url, timeout=timeout)
                r_hlfx.raise_for_status()
                rows_hlfx = extract_hl_fcy_board(BeautifulSoup(r_hlfx.text, "lxml"))
                fx_board_merged.extend(rows_hlfx)
                hl_fcy_board_meta = {"source_url": r_hlfx.url, "row_count": len(rows_hlfx)}
            except requests.RequestException as e:
                hl_fcy_board_meta = {"error": str(e), "source_url": hl_fcy_board_url}

        if ocbc_fcy_board_url:
            try:
                r_ocfx = sess.get(ocbc_fcy_board_url, timeout=timeout)
                r_ocfx.raise_for_status()
                rows_ocfx = extract_ocbc_fcy_board(BeautifulSoup(r_ocfx.text, "lxml"))
                fx_board_merged.extend(rows_ocfx)
                ocbc_fcy_board_meta = {"source_url": r_ocfx.url, "row_count": len(rows_ocfx)}
                if not rows_ocfx:
                    if "interest-rates" in (ocbc_fcy_board_url or "").lower():
                        ocbc_fcy_board_meta["note"] = (
                            "该 URL 为 CSR 综合利率页，首包无外币表；请改用 ocbc.com/rates/daily_price_fd.html。"
                        )
            except requests.RequestException as e:
                ocbc_fcy_board_meta = {
                    "error": str(e),
                    "source_url": ocbc_fcy_board_url,
                }

        if uob_fcy_board_url:
            try:
                ref = uob_fcy_board_url.strip()
                if not ref.lower().startswith(("http://", "https://")):
                    ref = "https://" + ref.lstrip("/")
                r_uobfx = sess.get(
                    _x.UOB_FCY_BOARD_JSON_URL,
                    headers={"Referer": ref, "Accept": "application/json,*/*;q=0.8"},
                    timeout=timeout,
                )
                r_uobfx.raise_for_status()
                rows_uobfx = extract_uob_fcy_board_from_api(r_uobfx.json())
                fx_board_merged.extend(rows_uobfx)
                uob_fcy_board_meta = {
                    "source_url": ref,
                    "api_url": r_uobfx.url,
                    "row_count": len(rows_uobfx),
                }
            except (requests.RequestException, ValueError) as e:
                uob_fcy_board_meta = {"error": str(e), "source_url": uob_fcy_board_url}

        if hsbc_fcy_board_url:
            try:
                r_hsfx = _get_with_hsbc_rates_fallback(sess, hsbc_fcy_board_url, timeout)
                r_hsfx.raise_for_status()
                rows_hsfx = extract_hsbc_fcy_board(BeautifulSoup(r_hsfx.text, "lxml"))
                fx_board_merged.extend(rows_hsfx)
                hsbc_fcy_board_meta = {"source_url": r_hsfx.url, "row_count": len(rows_hsfx)}
            except requests.RequestException as e:
                hsbc_fcy_board_meta = {"error": str(e), "source_url": hsbc_fcy_board_url}

        if maybank_fcy_board_url:
            try:
                r_mfx = sess.get(maybank_fcy_board_url, timeout=timeout)
                r_mfx.raise_for_status()
                rows_mfx = extract_maybank_fcy_board(BeautifulSoup(r_mfx.text, "lxml"))
                fx_board_merged.extend(rows_mfx)
                maybank_fcy_board_meta = {"source_url": r_mfx.url, "row_count": len(rows_mfx)}
            except requests.RequestException as e:
                maybank_fcy_board_meta = {"error": str(e), "source_url": maybank_fcy_board_url}
        # 15.25) DBS FCY board via SG rates API
        _dbs_api_base = (dbs_fcy_board_api_url or DEFAULT_DBS_FCY_BOARD_API_URL).strip()
        for dbs_api_attempt in range(3):
            try:
                r_dbs_fcy = sess.get(
                    _dbs_api_base,
                    params={"FETCH_LATEST": str(int(datetime.now(timezone.utc).timestamp()))},
                    timeout=timeout,
                )
                r_dbs_fcy.raise_for_status()
                dbs_fcy_rows = extract_dbs_fcy_board_from_api(r_dbs_fcy.json())
                fx_board_merged.extend(dbs_fcy_rows)
                dbs_fcy_board_meta = {"source_url": r_dbs_fcy.url, "row_count": len(dbs_fcy_rows)}
                break
            except requests.RequestException as e:
                if dbs_api_attempt < 2:
                    time.sleep(1.0 * (2**dbs_api_attempt))
                    continue
                dbs_fcy_board_meta = {
                    "error": str(e),
                    "source_url": _dbs_api_base,
                }

        if scb_fcy_board_url:
            try:
                r_scbfx = sess.get(scb_fcy_board_url, timeout=timeout)
                r_scbfx.raise_for_status()
                rows_scbfx = extract_scb_fcy_board(BeautifulSoup(r_scbfx.text, "lxml"))
                fx_board_merged.extend(rows_scbfx)
                scb_fcy_board_meta = {"source_url": r_scbfx.url, "row_count": len(rows_scbfx)}
            except requests.RequestException as e:
                scb_fcy_board_meta = {"error": str(e), "source_url": scb_fcy_board_url}

        if sbi_fcy_board_url:
            try:
                r_sbifx = sess.get(sbi_fcy_board_url, timeout=timeout)
                r_sbifx.raise_for_status()
                rows_sbifx = extract_sbi_fcy_board(BeautifulSoup(r_sbifx.text, "lxml"))
                fx_board_merged.extend(rows_sbifx)
                sbi_fcy_board_meta = {"source_url": r_sbifx.url, "row_count": len(rows_sbifx)}
            except requests.RequestException as e:
                sbi_fcy_board_meta = {"error": str(e), "source_url": sbi_fcy_board_url}

        if rhb_fcy_board_pdf_url:
            try:
                r_rhbfx = sess.get(rhb_fcy_board_pdf_url, timeout=timeout)
                r_rhbfx.raise_for_status()
                rows_rhbfx = extract_rhb_fcy_board_pdf(r_rhbfx.content)
                fx_board_merged.extend(rows_rhbfx)
                rhb_fcy_board_meta = {"source_url": r_rhbfx.url, "row_count": len(rows_rhbfx)}
            except requests.RequestException as e:
                rhb_fcy_board_meta = {"error": str(e), "source_url": rhb_fcy_board_pdf_url}

        # 15.3) BEA boards：JSON API
        if bea_sgd_board_api_url:
            try:
                r_bea_sgd = sess.post(bea_sgd_board_api_url, timeout=timeout)
                r_bea_sgd.raise_for_status()
                bea_sgd_json = r_bea_sgd.json()
                bea_sgd_rows = extract_bea_sgd_board_from_json(bea_sgd_json)
                sgd_board_merged.extend(bea_sgd_rows)
                bea_sgd_board_meta = {
                    "source_url": r_bea_sgd.url,
                    "row_count": len(bea_sgd_rows),
                }
            except (requests.RequestException, ValueError) as e:
                bea_sgd_board_meta = {"error": str(e), "source_url": bea_sgd_board_api_url}

        if bea_fcy_board_api_url:
            try:
                r_bea_fcy = sess.post(bea_fcy_board_api_url, timeout=timeout)
                r_bea_fcy.raise_for_status()
                bea_fcy_json = r_bea_fcy.json()
                bea_fcy_rows = extract_bea_fcy_board_from_json(bea_fcy_json)
                fx_board_merged.extend(bea_fcy_rows)
                bea_fcy_board_meta = {
                    "source_url": r_bea_fcy.url,
                    "row_count": len(bea_fcy_rows),
                }
            except (requests.RequestException, ValueError) as e:
                bea_fcy_board_meta = {"error": str(e), "source_url": bea_fcy_board_api_url}

        # 15.4) BOC board：同页同时包含 SGD/FCY
        if boc_board_url:
            _promo_index_unused, board_index_url = _boc_sg_promo_and_board_index_urls(
                boc_promo_url or "",
                boc_board_url or "",
            )
            board_fetch, board_res = _resolve_boc_sg_article_via_index(
                sess,
                configured_url=boc_board_url,
                index_url=board_index_url,
                bi_segment="bi32",
                timeout=timeout,
                enabled=boc_follow_latest_from_index,
            )
            try:
                rbcb = sess.get(board_fetch, timeout=timeout)
                rbcb.raise_for_status()
                rbcb.encoding = rbcb.apparent_encoding or rbcb.encoding
                sbcb = BeautifulSoup(rbcb.text, "lxml")
                boc_rows = extract_boc_sgd_fcy_board(sbcb)
                s_rows = boc_rows.get("sgd_rows") or []
                f_rows = boc_rows.get("fx_rows") or []
                sgd_board_merged.extend(s_rows)
                fx_board_merged.extend(f_rows)
                boc_sgd_board_meta = {
                    "source_url": rbcb.url,
                    "row_count": len(s_rows),
                    "url_resolution": board_res,
                }
                boc_fcy_board_meta = {
                    "source_url": rbcb.url,
                    "row_count": len(f_rows),
                    "url_resolution": board_res,
                }
            except requests.RequestException as e:
                boc_sgd_board_meta = {"error": str(e), "source_url": board_fetch, "url_resolution": board_res}
                boc_fcy_board_meta = {"error": str(e), "source_url": board_fetch, "url_resolution": board_res}

    # 16) 收尾：把 board merge 结果写回 payload。
    payload["fx_merged"] = _supplement_hl_fcy_promo_from_board(
        payload.get("fx_merged") or [], fx_board_merged
    )

    payload["sgd_board_merged"] = sgd_board_merged
    payload["citi_sgd_board"] = citi_sgd_board_meta
    payload["dbs_sgd_board"] = dbs_sgd_board_meta
    payload["hl_sgd_board"] = hl_sgd_board_meta
    payload["hlf_sgd_board"] = hlf_sgd_board_meta
    payload["hsbc_sgd_board"] = hsbc_sgd_board_meta
    payload["icbc_sgd_board"] = icbc_sgd_board_meta
    payload["icbc_fcy_board"] = icbc_fcy_board_meta
    payload["maybank_sgd_board"] = maybank_sgd_board_meta
    payload["ocbc_sgd_board"] = ocbc_sgd_board_meta
    payload["rhb_sgd_board_pdf"] = rhb_sgd_board_meta
    payload["sif_sgd_board"] = sif_sgd_board_meta
    payload["scb_sgd_board"] = scb_sgd_board_meta
    payload["sbi_sgd_board"] = sbi_sgd_board_meta
    payload["uob_sgd_board"] = uob_sgd_board_meta

    payload["fx_board_merged"] = fx_board_merged
    payload["hl_fcy_board"] = hl_fcy_board_meta
    payload["ocbc_fcy_board"] = ocbc_fcy_board_meta
    payload["uob_fcy_board"] = uob_fcy_board_meta
    payload["hsbc_fcy_board"] = hsbc_fcy_board_meta
    payload["maybank_fcy_board"] = maybank_fcy_board_meta
    payload["dbs_fcy_board"] = dbs_fcy_board_meta
    payload["scb_fcy_board"] = scb_fcy_board_meta
    payload["sbi_fcy_board"] = sbi_fcy_board_meta
    payload["rhb_fcy_board_pdf"] = rhb_fcy_board_meta
    payload["bea_sgd_board"] = bea_sgd_board_meta
    payload["bea_fcy_board"] = bea_fcy_board_meta
    payload["boc_sgd_board"] = boc_sgd_board_meta
    payload["boc_fcy_board"] = boc_fcy_board_meta

    return payload


# ---------------------------------------------------------------------------
# Safety net: 自动给本模块中所有 def 加异常兜底。
# 这样即使中间 helper 出错，也不会让整体流程因未捕获异常崩溃。
# ---------------------------------------------------------------------------
from bank_safety import auto_wrap_module_functions as _auto_wrap_module_functions

_auto_wrap_module_functions(
    globals(),
    module_name=__name__,
    exclude={
        "_get_with_hsbc_rates_fallback",
        "_maybank_ipv4_gai_only",
        "_get_maybank2u_sgd_promo_page",
    },
)

