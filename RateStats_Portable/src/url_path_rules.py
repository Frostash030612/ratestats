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

    # OCBC 新币挂牌：个人 fixed-deposit-sgd-interest-rates.page，强惩罚 business/premier
    if dest == "ocbc_board_url":
        if "fixed-deposit-sgd-interest-rates" in full:
            score += 70
        elif "fixed-deposit-sgd-interest" in full:
            score += 55
        if "sgd-fixed-deposit-interest-rates" in full and "business-banking" not in full:
            score += 20
        if "personal-banking/deposits" in full and "fixed-deposit-sgd-interest" not in full:
            score -= 45
        if "fixed-deposit-account" in full and "fixed-deposit-sgd-interest" not in full:
            score -= 55
        if "premier-banking" in full:
            score -= 95
        if "business-banking" in full:
            score -= 95
        if "corporate-banking" in full or "sme-and-corporate" in full:
            score -= 70

    # DBS 外币挂牌 API（必须 sg-rates-api + getSGFCFDRates）
    if dest == "dbs_fcy_board_api_url":
        if "sg-rates-api" in full and "getsgfcfdrates" in full.replace("-", ""):
            score += 70
        if "personal/deposits" in full or "/fixed-deposits/" in full:
            score -= 90
        if "personal/support" in full:
            score -= 85
        if "treasury-api" in full or "global-financial-markets" in full:
            score -= 90
        if "digital-services" in full:
            score -= 80

    # HSBC 外币促销：产品页 HTML（旧 PDF 仅为挂牌参考）
    if dest == "hsbc_fcy_promo_url":
        if "foreign-currency-time-deposit" in full and "/accounts/products/" in full:
            score += 55
        if "fcy-time-deposits-pb.pdf" in full:
            score += 15
        if "usd-time-deposit-promotion-terms" in full:
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

    # BOC：促销 bi31 / 挂牌 bi32 须为 dated html，惩罚目录索引页
    if dest == "boc_url":
        from url_dest_intent import is_boc_promo_rate_page

        if is_boc_promo_rate_page(url):
            score += 70
        if "/cn/bocinfo/bi3/bi31/" in full:
            score += 15
        if "/bocinfo/bi3/bi31/" in full and "/cn/" not in full:
            score -= 25
        if "/bocinfo/bi3/bi32/" in full:
            score -= 80
        if full.rstrip("/").endswith("/bi3") or full.rstrip("/").endswith("/bi31"):
            score -= 90
    if dest == "boc_board_url":
        from url_dest_intent import is_boc_board_rate_page

        if is_boc_board_rate_page(url):
            score += 70
        if "/cn/bocinfo/bi3/bi32/" in full:
            score += 15
        if "/bocinfo/bi3/bi32/" in full and "/cn/" not in full:
            score -= 25
        if "/bocinfo/bi3/bi31/" in full:
            score -= 80
        if full.rstrip("/").endswith("/bi3") or full.rstrip("/").endswith("/bi32"):
            score -= 90

    # RHB 挂牌 PDF：Depositrates.pdf（固定 jcr id）
    if dest in ("rhb_board_pdf_url", "rhb_fcy_board_pdf_url"):
        from url_dest_intent import is_rhb_deposit_rates_board_pdf

        if is_rhb_deposit_rates_board_pdf(url):
            score += 75
        elif "rhbgroup.com" in full and ".pdf" in full:
            score -= 50
        if "/rhb/personal/promotions" in full or "fixed-deposit-campaign" in full:
            score -= 90
        if "rates-and-charges" in full and not full.endswith(".pdf"):
            score -= 85
        if "latest-promotions" in full:
            score -= 85
        if "/rhb/business/" in full:
            score -= 80

    return score
