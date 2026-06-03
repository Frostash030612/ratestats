"""每个 dest 的 URL 意图：严格模式硬匹配；宽松模式仅软加分 + 少量硬拒绝。"""
from __future__ import annotations

import re
from urllib.parse import urlparse

# (必须包含任一), (必须全部包含), (禁止包含任一)
_Intent = tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]

_DEST_INTENT: dict[str, _Intent] = {
    # --- 促销 ---
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
    "hsbc_fcy_promo_url": (("fcy-time-deposits-pb.pdf",), (), ()),
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
        ("digital-services", "treasury-api"),
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
        ("sgd-fixed-deposit-interest-rates",),
        (),
        ("business-banking",),
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
    "dbs_fcy_board_api_url": ("digital-services", "treasury-api", ".page"),
    "hlf_board_url": ("current-account",),
    "hsbc_board_url": ("fcy-time-deposits-pb.pdf",),
    "scb_url": ("business-time-deposits", "business-yield"),
    "scb_fcy_url": ("/help/faqs/",),
    "bea_sgd_promo_url": ("formid=sg001",),
}


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
