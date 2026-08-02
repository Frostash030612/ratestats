"""
Centralized URL constants for `bank_all_promo_rates.py` (portable copy).

Keeping these in a separate module makes the main script easier to read.
"""

DEFAULT_URL = (
    "https://www.citibank.com.sg/personal-banking/deposits/fixed-deposit-account"
    "?icid=SGENCBGBAMITLCitiTimeDeposits&ecid=PSGONSGWFAENDB&lid=SGENCBGBAMITALAccountsAndDeposits"
)

DEFAULT_CIMB_FCY_URL = (
    "https://www.cimb.com.sg/en/personal/banking-with-us/accounts/fixed-deposit/"
    "cimb-foreign-currency-fixed-deposit-account.html"
)
DEFAULT_CIMB_SGD_URL = (
    "https://www.cimb.com.sg/en/personal/help-support/rates-charges/rates/"
    "sgd-fixed-deposit-rates.html"
)

DEFAULT_HL_FD_URL = (
    "https://www.hlbank.com.sg/en/personal-banking/promotions/"
    "fixed-deposit-promotion-2026.html"
)
DEFAULT_HLF_FD_URL = (
    "https://www.hlf.com.sg/personal/promotions/fixed-deposits-promotion-singapore.php"
)

DEFAULT_HSBC_TD_URL = (
    "https://www.hsbc.com.sg/zh-sg/accounts/products/time-deposit/"
)
# 官网已改版为 /en/column/ 路径；Fixed Deposit 栏目同页含促销 + 挂牌表。
DEFAULT_ICBC_FD_URL = (
    "https://singapore.icbc.com.cn/en/column/1438059017468788838.html"
)
DEFAULT_OCBC_FD_URL = (
    "https://www.ocbc.com/personal-banking/deposits/fixed-deposit-account"
)
DEFAULT_RHB_FD_URL = (
    "https://rhbgroup.com.sg/rhb/personal/promotions/fixed-deposit-campaign"
)
DEFAULT_RHB_FCY_FD_URL = (
    "https://rhbgroup.com.sg/rhb/personal/promotions/foreign-currency-fixed-deposit-campaign"
)
DEFAULT_SCB_SGD_TD_URL = (
    "https://www.sc.com/sg/save/time-deposits/singapore-dollar-time-deposit/"
)
DEFAULT_SCB_FCY_FD_URL = (
    "https://www.sc.com/sg/save/time-deposits/foreign-currency-time-deposits/"
)
DEFAULT_SIF_FD_URL = (
    "https://www.singfinance.com.sg/fixed-deposit-fd-online/"
)
DEFAULT_SBI_SGD_PROMO_URL = "https://sg.statebank/sgd-promotions"
DEFAULT_SBI_USD_PROMO_URL = "https://sg.statebank/usd-promotions"
DEFAULT_UOB_SGD_TD_URL = (
    "https://www.uob.com.sg/personal/save/fixed-deposits/singapore-dollar-fixed-deposit.page"
)

# BEA / Maybank / HSBC（促销）与 DBS 外币挂牌 API（可在 url_params.xlsx 覆盖）
DEFAULT_BEA_SGD_PROMO_URL = "https://www.hkbea.com.sg/html/en/index.html"
DEFAULT_BEA_FCY_PROMO_URL = (
    "https://www.hkbea.com.sg/sg-form/?formId=RATE&rateType=fcfdr#/forms/MISC"
)
DEFAULT_MAYBANK_SGD_PROMO_URL = (
    "https://www.maybank2u.com.sg/en/promotions/deposits/sgd-time-deposit.page"
)
DEFAULT_HSBC_FCY_PROMO_URL = (
    "https://www.hsbc.com.sg/content/dam/hsbc/sg/documents/rates/fcy-time-deposits-pb.pdf"
)
DEFAULT_DBS_FCY_BOARD_API_URL = (
    "https://www.dbs.com.sg/sg-rates-api/v1/api/sgrates/getSGFCFDRates"
)

DEFAULT_BOC_PROMO_URL = (
    "https://www.bankofchina.com/sg/cn/bocinfo/bi3/bi31/202605/t20260511_25666275.html"
)

DEFAULT_CITI_SGD_BOARD_URL = (
    "https://www.citibank.com.sg/personal-banking/deposits/fixed-deposit-account"
)
DEFAULT_CITI_FD_PROMO_URL = (
    "https://www.citibank.com.sg/personal-banking/deposits/fixed-deposit-account"
    "?icid=SGENCBGBAMITLCitiTimeDeposits&ecid=PSGONSGWFAENDB&lid=SGENCBGBAMITALAccountsAndDeposits"
)
DEFAULT_DBS_SGD_BOARD_URL = (
    "https://www.dbs.com.sg/personal/rates-online/fixed-deposit-rate-singapore-dollar.page"
)
DEFAULT_HL_SGD_BOARD_URL = (
    "https://www.hlbank.com.sg/en/personal-banking/help-support/fixed-deposit-rate.html"
)
DEFAULT_HLF_SGD_BOARD_URL = (
    "https://www.hlf.com.sg/personal/deposits/fixed-deposits-singapore.php"
)
DEFAULT_HSBC_SGD_BOARD_URL = (
    "https://www.hsbc.com.sg/rates/singapore-dollar-deposits/"
)
DEFAULT_ICBC_SGD_BOARD_URL = (
    "https://singapore.icbc.com.cn/en/column/1438059017468788838.html"
)
# 与 SGD 挂牌同页：含 Amount(USD)、Amount(RMB) 等外币挂牌表。
DEFAULT_ICBC_FCY_BOARD_URL = DEFAULT_ICBC_SGD_BOARD_URL
DEFAULT_MAYBANK_SGD_BOARD_URL = (
    "https://sslsecure.maybank.com.sg/cgi-bin/mbs/JSPscripts/mbb_rates/deposit_rate.jsp"
)
DEFAULT_OCBC_SGD_BOARD_URL = (
    "https://www.ocbc.com/personal-banking/deposits/fixed-deposit-sgd-interest-rates.page"
)
DEFAULT_RHB_SGD_BOARD_PDF_URL = (
    "https://www.rhbgroup.com.sg/dam/jcr:98394f8b-4141-4685-bfdc-494135e614f3/Depositrates.pdf"
)
DEFAULT_SIF_SGD_BOARD_URL = "https://www.singfinance.com.sg/rates/"
DEFAULT_SCB_SGD_BOARD_URL = (
    "https://www.sc.com/sg/help/faqs/sgd-time-deposit-interest-rates/"
)
DEFAULT_SBI_SGD_BOARD_URL = "https://sg.statebank/interest-rates"
DEFAULT_UOB_SGD_BOARD_URL = (
    "https://www.uob.com.sg/personal/online-rates/singapore-dollar-time-fixed-deposit-rates.page"
)

DEFAULT_HL_FCY_BOARD_URL = (
    "https://www.hlbank.com.sg/en/personal-banking/deposits/fixed-deposit-account/foreign-currency-fd.html"
)
DEFAULT_HSBC_FCY_BOARD_URL = (
    "https://www.hsbc.com.sg/rates/foreign-currency-time-deposits/"
)
DEFAULT_MAYBANK_FCY_BOARD_URL = (
    "https://sslsecure.maybank.com.sg/cgi-bin/mbs/JSPscripts/mbb_rates/deposit_rate.jsp"
)
DEFAULT_SCB_FCY_BOARD_URL = (
    "https://www.sc.com/sg/help/faqs/foreign-currency-interest-rates/"
)
DEFAULT_SBI_FCY_BOARD_URL = "https://sg.statebank/interest-rates"
# 外币定存「日价」静态 HTML（各币种分档 + 多期限）；个人站 interest-rates 外币块多为 CSR。
DEFAULT_OCBC_FCY_BOARD_URL = "https://www.ocbc.com/rates/daily_price_fd.html"
DEFAULT_UOB_FCY_BOARD_URL = (
    "https://www.uobgroup.com/online-rates/foreign-currency-fixed-deposits.page"
)
DEFAULT_RHB_FCY_BOARD_PDF_URL = (
    "https://www.rhbgroup.com.sg/dam/jcr:98394f8b-4141-4685-bfdc-494135e614f3/Depositrates.pdf"
)

DEFAULT_BEA_SGD_BOARD_API_URL = (
    "https://www.hkbea.com.sg/sg-form/eform-api/v1/misc/enquiry/RATE/fdr"
)
DEFAULT_BEA_FCY_BOARD_API_URL = (
    "https://www.hkbea.com.sg/sg-form/eform-api/v1/misc/enquiry/RATE/fcfdr"
)

DEFAULT_BOC_BOARD_URL = (
    "https://www.bankofchina.com/sg/cn/bocinfo/bi3/bi32/202605/t20260504_25664331.html"
)

