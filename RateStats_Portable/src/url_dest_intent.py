"""每个 dest 的 URL 意图：严格模式硬匹配；宽松模式仅软加分 + 少量硬拒绝。"""
from __future__ import annotations

import re
from urllib.parse import urlparse

# (必须包含任一), (必须全部包含), (禁止包含任一)
_Intent = tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]

_DEST_INTENT: dict[str, _Intent] = {
    # --- 促销 ---
    "url": (
        ("fixed-deposit-account",),
        (),
        ("wealth", "insurance", "credit-card", "business-banking"),
    ),
    "citi_all_promo_url": (
        ("all-promo",),
        (),
        ("wealth", "insurance", "credit-card", "business-banking"),
    ),
    "bea_sgd_promo_url": (
        ("index.html", "formid=rate"),
        (),
        ("formid=sg001", "beasg-rates-sgd-fixed-deposit-rates", "business-banking"),
    ),
    "bea_fcy_promo_url": (
        ("fcfdr", "ratetype=fcfdr"),
        (),
        ("beasg-rates", "fixed-deposit-account.html"),
    ),
    "hsbc_url": (
        ("time-deposit",),
        ("zh-sg",),
        ("foreign-currency-time-deposit", "foreign-currency-time-deposits"),
    ),
    "hsbc_fcy_promo_url": (
        ("foreign-currency-time-deposit",),
        ("usd-time-deposit",),
        ("fcy-time-deposits-pb.pdf",),
    ),
    "hl_url": (
        ("fixed-deposit-promotion",),
        ("personal-banking",),
        ("business-banking/promotions",),
    ),
    "hlf_url": (
        ("fixed-deposits-promotion-singapore",),
        (),
        (),
    ),
    "ocbc_url": (
        ("fixed-deposit-account",),
        (),
        (),
    ),
    "maybank_sgd_promo_url": (
        ("sgd-time-deposit",),
        (),
        ("deposits/index.page",),
    ),
    "cimb_sgd_url": (
        ("sgd-fixed-deposit-rates",),
        (),
        ("/accounts/deposits.html", "/accounts/deposits."),
    ),
    "cimb_url": (
        ("foreign-currency-fixed-deposit", "cimb-foreign-currency"),
        (),
        ("/accounts/deposits.html",),
    ),
    "scb_url": (
        ("singapore-dollar-time-deposit",),
        (),
        ("business-time-deposits", "business-yield", "/help/faqs/"),
    ),
    "scb_fcy_url": (
        ("foreign-currency-time-deposits",),
        ("save/time-deposits",),
        ("/help/faqs/",),
    ),
    "uob_url": (
        ("singapore-dollar-fixed-deposit",),
        (),
        ("online-rates/index",),
    ),
  # --- 挂牌 ---
    "dbs_fcy_board_api_url": (
        ("sg-rates-api",),
        ("getsgfcfdrates",),
        (
            "digital-services",
            "treasury-api",
            "global-financial-markets",
            "personal/deposits/fixed-deposits",
            "personal/support",
        ),
    ),
    "maybank_board_url": (
        ("deposit_rate.jsp",),
        ("sslsecure.maybank.com.sg",),
        ("maybank2u.com.sg",),
    ),
    "maybank_fcy_board_url": (
        ("deposit_rate.jsp",),
        ("sslsecure.maybank.com.sg",),
        ("maybank2u.com.sg",),
    ),
    "ocbc_board_url": (
        ("fixed-deposit-sgd-interest-rates", "sgd-fixed-deposit-interest-rates"),
        (),
        ("business-banking", "premier-banking", "corporate-banking"),
    ),
    "hl_board_url": (
        ("help-support/fixed-deposit-rate", "fixed-deposit-rate.html"),
        (),
        ("deposits/fixed-deposit-account/fixed-deposit-account", "fixed-deposit-promotion"),
    ),
    "hsbc_board_url": (
        ("singapore-dollar-deposits",),
        (),
        ("foreign-currency-time-deposit", ".pdf"),
    ),
    "hsbc_fcy_board_url": (
        ("foreign-currency-time-deposits",),
        (),
        (".pdf",),
    ),
    "hlf_board_url": (
        ("fixed-deposits-singapore",),
        (),
        ("current-account", "sme-and-corporate"),
    ),
    "citi_board_url": (
        ("fixed-deposit-account",),
        (),
        ("/interest-rate/",),
    ),
    "rhb_board_pdf_url": (
        ("depositrates.pdf",),
        ("98394f8b-4141-4685-bfdc-494135e614f3",),
        ("rhb/personal/promotions", "latest-promotions", "rates-and-charges"),
    ),
    "rhb_fcy_board_pdf_url": (
        ("depositrates.pdf",),
        ("98394f8b-4141-4685-bfdc-494135e614f3",),
        ("rhb/personal/promotions", "latest-promotions", "rates-and-charges", "rhb/business"),
    ),
    "uob_board_url": (
        ("singapore-dollar-time-fixed-deposit-rates",),
        (),
        ("online-rates/index.page",),
    ),
    "uob_fcy_board_url": (
        ("foreign-currency-fixed-deposit",),
        ("uobgroup.com",),
        ("uob.com.sg/personal/online-rates/index",),
    ),
    "scb_board_url": (
        ("sgd-time-deposit-interest-rates",),
        (),
        (),
    ),
    "scb_fcy_board_url": (
        ("foreign-currency-interest-rates",),
        (),
        (),
    ),
    "rhb_url": (
        ("fixed-deposit-campaign",),
        ("promotions",),
        ("/deposits/foreign-currency-fixed-deposit-account",),
    ),
    "rhb_fcy_url": (
        ("foreign-currency-fixed-deposit-campaign",),
        ("promotions",),
        ("/deposits/foreign-currency-fixed-deposit-account",),
    ),
    "boc_url": (
        ("bocinfo/bi3/bi31",),
        ("t20", ".html"),
        ("business-banking",),
    ),
    "boc_board_url": (
        ("bocinfo/bi3/bi32",),
        ("t20", ".html"),
        ("business-banking",),
    ),
}


def _norm(url: str) -> str:
    """URL 转小写，供路径片段匹配。"""
    return (url or "").lower()


def url_meets_dest_intent(dest: str, url: str) -> bool:
    """严格模式：路径意图必须满足。宽松模式：仅排除硬拒绝项。"""
    from url_discovery_config import is_relaxed_mode

    if is_relaxed_mode():
        return not url_hard_reject(dest, url)
    if not url or not str(url).startswith("http"):
        return False
    spec = _DEST_INTENT.get(dest)
    if not spec:
        return True
    any_of, all_of, forbid = spec
    low = _norm(url)
    path = _norm(urlparse(url).path)

    if forbid:
        for f in forbid:
            f = f.lower()
            if f.endswith("$"):
                if path.rstrip("/").endswith(f[:-1]):
                    return False
            elif f in low:
                return False
    if any_of and not any(x.lower() in low for x in any_of):
        return False
    if all_of:
        combined = low.replace("-", "")
        for a in all_of:
            if a.lower().replace("-", "") not in combined and a.lower() not in low:
                return False
    return True


def filter_by_intent(dest: str, urls: list[str]) -> list[str]:
    """仅保留满足当前模式意图规则的 URL 列表。"""
    return [u for u in urls if url_meets_dest_intent(dest, u)]


# 宽松模式下仍拒绝的「明显错页」（跨产品/非 API 冒充 API）
_HARD_REJECT: dict[str, tuple[str, ...]] = {
    "hsbc_url": ("foreign-currency-time-deposit", "foreign-currency-time-deposits"),
    "dbs_fcy_board_api_url": (
        "digital-services",
        "treasury-api",
        ".page",
        "global-financial-markets",
        "personal/support",
        "fixed-deposits/fixed-deposit",
        "foreign-currency-fixed-deposit",
        "singapore-dollar-fixed-deposit",
    ),
    "hlf_board_url": ("current-account",),
    "hsbc_board_url": ("fcy-time-deposits-pb.pdf",),
    "scb_url": ("business-time-deposits", "business-yield"),
    "scb_fcy_url": ("/help/faqs/",),
    "bea_sgd_promo_url": ("formid=sg001",),
    "bea_fcy_promo_url": ("beasg-cyberbanking", "beasg-personal-banking-fixed-deposit"),
    "url": ("wealth", "insurance-only", "credit-card"),
    "citi_all_promo_url": ("wealth", "insurance-only", "credit-card"),
    # OCBC 新币挂牌：business 页无 18/24/36M 等个人定存期限列
    "ocbc_board_url": (
        "business-banking",
        "corporate-banking",
        "sme-and-corporate",
        "premier-banking",
    ),
    "hl_board_url": (
        "deposits/fixed-deposit-account/fixed-deposit-account",
        "fixed-deposit-promotion",
    ),
    "rhb_board_pdf_url": (
        "/rhb/personal/promotions",
        "/rhb/latest-promotions",
        "rates-and-charges",
        "fixed-deposit-campaign",
        "tcs%20governing",
        "pricing%20guide",
        "fd%20promo",
    ),
    "rhb_fcy_board_pdf_url": (
        "/rhb/personal/promotions",
        "/rhb/latest-promotions",
        "rates-and-charges",
        "fixed-deposit-campaign",
        "rhb/business/",
        "tcs%20governing",
        "pricing%20guide",
        "fd%20promo",
    ),
    "boc_url": ("/bocinfo/bi3/bi32/", "business-banking"),
    "boc_board_url": ("/bocinfo/bi3/bi31/", "business-banking"),
}


_BOC_RATE_ARTICLE = re.compile(r"/t20\d{6}_\d+\.html", re.I)


def _boc_host_ok(host: str) -> bool:
    h = (host or "").lower()
    if h.startswith("www."):
        h = h[4:]
    return h.endswith("bankofchina.com") or ".bankofchina.com" in h


def _boc_section_dated_html(path: str, section: str) -> bool:
    """BOC 利率/促销：bocinfo/bi3/bi31|bi32 下带日期的 .html 文章（非目录页）。"""
    low = (path or "").lower()
    if f"/bocinfo/bi3/{section}/" not in low and f"/cn/bocinfo/bi3/{section}/" not in low:
        return False
    if not _BOC_RATE_ARTICLE.search(low):
        return False
    tail = low.rstrip("/").split("/")[-1]
    if tail in ("bi3", "bi31", "bi32"):
        return False
    return True


def is_boc_promo_rate_page(url: str) -> bool:
    """BOC 定存促销：bi31 目录下 dated html（手动链多为 /sg/cn/bocinfo/...）。"""
    if not url or not str(url).startswith("http"):
        return False
    parsed = urlparse(url)
    if not _boc_host_ok(parsed.netloc or ""):
        return False
    if "/sg/" not in (parsed.path or "").lower():
        return False
    return _boc_section_dated_html(parsed.path or "", "bi31")


def is_boc_board_rate_page(url: str) -> bool:
    """BOC 挂牌利率：bi32 目录下 dated html。"""
    if not url or not str(url).startswith("http"):
        return False
    parsed = urlparse(url)
    if not _boc_host_ok(parsed.netloc or ""):
        return False
    if "/sg/" not in (parsed.path or "").lower():
        return False
    return _boc_section_dated_html(parsed.path or "", "bi32")


# RHB 挂牌利率 PDF（新元/外币共用 Depositrates.pdf）
_RHB_BOARD_PDF_JCR_ID = "98394f8b-4141-4685-bfdc-494135e614f3"


def _rhb_host_ok(host: str) -> bool:
    h = (host or "").lower()
    if h.startswith("www."):
        h = h[4:]
    return h in ("rhbgroup.com.sg", "rhbgroup.com")


def is_rhb_deposit_rates_board_pdf(url: str) -> bool:
    """RHB 挂牌 Depositrates.pdf（非促销 T&C、非 rates-and-charges HTML）。"""
    low = (url or "").lower()
    if not low.startswith("http"):
        return False
    parsed = urlparse(low)
    if not _rhb_host_ok(parsed.netloc or ""):
        return False
    path = (parsed.path or "").lower()
    if not path.endswith(".pdf"):
        return False
    if _RHB_BOARD_PDF_JCR_ID not in path:
        return False
    return "depositrates.pdf" in path


def is_dbs_fcy_board_api_url(url: str) -> bool:
    """DBS 外币挂牌 JSON API（非个人定存 HTML 页 / treasury 页）。"""
    low = (url or "").lower()
    if not low.startswith("http"):
        return False
    combined = low.replace("-", "")
    if "sgratesapi" not in combined and "sg-rates-api" not in low:
        return False
    if "getsgfcfdrates" not in combined:
        return False
    if any(
        x in low
        for x in (
            "digital-services",
            "treasury-api",
            "global-financial-markets",
            "personal/support",
        )
    ):
        return False
    if "/personal/deposits" in low or "/fixed-deposits/" in low:
        return False
    return True


def is_hl_sgd_board_page(url: str) -> bool:
    """HL Bank SGD 挂牌：help-support 下的 fixed-deposit-rate 表（含 BOARD RATES 列）。"""
    low = (url or "").lower()
    if "hlbank.com.sg" not in low:
        return False
    return "help-support/fixed-deposit-rate" in low or (
        "fixed-deposit-rate.html" in low and "help-support" in low
    )


def is_citi_all_promo_url(url: str) -> bool:
    """Citibank SG 定存促销汇总页（含 International 标签页内 FX 促销）。"""
    low = (url or "").lower()
    if "citibank.com.sg" not in low:
        return False
    return "all-promo" in low


def is_bea_fcy_promo_form_url(url: str) -> bool:
    """BEA SG 外币定存促销利率表单页。"""
    low = (url or "").lower()
    if "hkbea.com.sg" not in low:
        return False
    return "ratetype=fcfdr" in low or "fcfdr" in low or "formid=rate" in low


def is_ocbc_sgd_board_page(url: str) -> bool:
    """OCBC 新币挂牌：个人 fixed-deposit-sgd-interest-rates 页（非 business/premier）。"""
    low = (url or "").lower()
    if not low.startswith("http"):
        return False
    if any(
        x in low
        for x in ("business-banking", "corporate-banking", "sme-and-corporate", "premier-banking")
    ):
        return False
    if "fixed-deposit-sgd-interest" in low:
        return True
    if "personal-banking" in low and "sgd-fixed-deposit-interest" in low:
        return True
    return False


def _path_tokens(url: str) -> set[str]:
    """从 URL 路径/查询中提取有意义 token，用于与 reference_url 比对相似度。"""
    low = (url or "").lower()
    parts = re.split(r"[/?.=&_-]+", urlparse(low).path + "?" + (urlparse(low).query or ""))
    return {p for p in parts if len(p) >= 5 and p not in ("html", "page", "personal", "banking")}


def url_hard_reject(dest: str, url: str) -> bool:
    """宽松模式下仍一票否决的明显错页（如 HSBC 定存页混入外币页）。"""
    if not url or not str(url).startswith("http"):
        return True
    low = url.lower()
    for frag in _HARD_REJECT.get(dest, ()):
        if frag.lower() in low:
            return True
    if dest == "dbs_fcy_board_api_url":
        if is_dbs_fcy_board_api_url(url):
            return False
        if "dbs.com.sg" in low or "dbs.com" in low:
            return True
    if dest in ("rhb_board_pdf_url", "rhb_fcy_board_pdf_url"):
        if is_rhb_deposit_rates_board_pdf(url):
            return False
        if _rhb_host_ok(urlparse(low).netloc or "") or "rhbgroup.com" in low:
            return True
    if dest == "boc_url":
        if is_boc_promo_rate_page(url):
            return False
        if _boc_host_ok(urlparse(low).netloc or "") and "bocinfo/bi3" in low:
            return True
    if dest == "boc_board_url":
        if is_boc_board_rate_page(url):
            return False
        if _boc_host_ok(urlparse(low).netloc or "") and "bocinfo/bi3" in low:
            return True
    if dest == "ocbc_board_url":
        if "fixed-deposit-account" in low and "fixed-deposit-sgd-interest" not in low:
            return True
        if "time-deposit" in low and not is_ocbc_sgd_board_page(url):
            return True
    return False


def intent_score_adjustment(dest: str, url: str, *, reference_url: str = "") -> int:
    """宽松模式：参考手动链接做软加分；路径意图不满足时减分但不一票否决。"""
    from url_discovery_config import is_relaxed_mode

    if not url:
        return -50
    score = 0
    low = url.lower()

    if reference_url:
        ref_tokens = _path_tokens(reference_url)
        url_tokens = _path_tokens(url)
        overlap = ref_tokens & url_tokens
        score += min(24, len(overlap) * 6)
        ref_path = urlparse(reference_url).path.lower()
        if ref_path and ref_path.rstrip("/") in urlparse(url).path.lower():
            score += 18

    spec = _DEST_INTENT.get(dest)
    if spec:
        any_of, all_of, forbid = spec
        if any_of and any(x.lower() in low for x in any_of):
            score += 14 if is_relaxed_mode() else 0
        if all_of:
            combined = low.replace("-", "")
            if all(a.lower().replace("-", "") in combined or a.lower() in low for a in all_of):
                score += 10 if is_relaxed_mode() else 0
        if forbid:
            for f in forbid:
                if f.lower() in low:
                    score -= 22 if is_relaxed_mode() else 0

    if url_hard_reject(dest, url):
        score -= 80
    return score
