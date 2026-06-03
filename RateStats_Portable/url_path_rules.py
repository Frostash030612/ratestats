"""各 dest 的路径级打分修正（与 url_host_rules 域名约束配合使用）。"""
from __future__ import annotations

from urllib.parse import urlparse


def path_score_adjustment(dest: str, url: str) -> int:
    """在通用打分之外，按银行/产品页路径加减分。"""
    if not url:
        return 0

    full = url.lower()
    path = (urlparse(url).path or "").lower()
    score = 0

    # Maybank 挂牌：sslsecure JSP，避免 maybank2u 储蓄利率页超时
    if dest in ("maybank_board_url", "maybank_fcy_board_url"):
        if "sslsecure.maybank.com.sg" in full and "deposit_rate.jsp" in full:
            score += 45
        if "jspscripts" in full and "mbb_rates" in full:
            score += 20
        if "maybank2u.com.sg" in full:
            score -= 50

    # HLF 挂牌：定存页，排除往来户 / SME
    if dest == "hlf_board_url":
        if "fixed-deposits-singapore" in full:
            score += 45
        if "current-account" in full:
            score -= 65
        if "sme-and-corporate" in full:
            score -= 35

    # Citi 挂牌：主产品页，避免仅 interest-rate 子页
    if dest == "citi_board_url":
        if "fixed-deposit-account" in full and "/interest-rate" not in path:
            score += 30
        if "/interest-rate" in path:
            score -= 40

    # OCBC 新币挂牌：个人页，排除 business-banking
    if dest == "ocbc_board_url":
        if "sgd-fixed-deposit-interest-rates" in full:
            score += 48
        if "personal-banking/deposits" in full and "sgd-fixed-deposit" not in full:
            score -= 40
        if "business-banking" in full:
            score -= 55

    # DBS 外币挂牌 API
    if dest == "dbs_fcy_board_api_url":
        if "sg-rates-api" in full and "getsgfcfdrates" in full.replace("-", ""):
            score += 55
        if "treasury-api" in full or "global-financial-markets" in full:
            score -= 55

    # HSBC 外币促销 PDF
    if dest == "hsbc_fcy_promo_url":
        if "fcy-time-deposits-pb.pdf" in full:
            score += 50
        if "usd-time-deposit-promotion" in full:
            score -= 45

    # BEA 新元促销：表单入口
    if dest == "bea_sgd_promo_url":
        if "sg-form" in full or "formid=rate" in full:
            score += 38
        if "beasg-rates-sgd-fixed-deposit-rates" in full:
            score -= 30

    # BEA 外币促销
    if dest == "bea_fcy_promo_url":
        if "fcfdr" in full or "rateType=fcfdr".lower() in full:
            score += 35
        if "beasg-rates-sgd-fixed-deposit-rates" in full:
            score -= 25

    # UOB 外币挂牌：uobgroup 专页
    if dest == "uob_fcy_board_url":
        if "uobgroup.com" in full and "foreign-currency-fixed-deposit" in full:
            score += 38
        if "uob.com.sg" in full and "/online-rates/index" in full:
            score -= 32

    # OCBC 外币挂牌：日价页
    if dest == "ocbc_fcy_board_url":
        if "daily_price_fd" in full:
            score += 35
        if "personal-banking/deposits/interest-rates" in full:
            score -= 25

    # HL 外币挂牌：产品页优于 help-support 汇总
    if dest == "hl_fcy_board_url":
        if "foreign-currency-fd.html" in full:
            score += 30
        if "help-support/foreign-rate" in full:
            score -= 20

    # SBI：惩罚非标准域名（Vertex 常返回 sg.statebank/...）
    if dest.startswith("sbi"):
        host = (urlparse(url).netloc or "").lower()
        if "statebank" in host and not host.endswith("statebank.com.sg") and "statebank.com" not in host:
            score -= 85

    # RHB PDF：www 与无 www 等价，略偏好与默认一致的 host
    if dest in ("rhb_board_pdf_url", "rhb_fcy_board_pdf_url"):
        if "rhbgroup.com.sg" in full and ".pdf" in full:
            score += 15

    return score
