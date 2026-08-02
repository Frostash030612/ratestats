from __future__ import annotations

"""
URL 默认值映射模块（可移植版本）。

把主脚本中 `main()` 的 dest->DEFAULT_* 超长字典集中到这里，减少维护成本并提升可读性。
"""

from typing import Dict

from url_sources import (
    DEFAULT_URL,
    DEFAULT_CITI_ALL_PROMO_URL,
    DEFAULT_CIMB_FCY_URL,
    DEFAULT_CIMB_SGD_URL,
    DEFAULT_CIMB_FCY_BOARD_URL,
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
    DEFAULT_BEA_SGD_PROMO_URL,
    DEFAULT_BEA_FCY_PROMO_URL,
    DEFAULT_MAYBANK_SGD_PROMO_URL,
    DEFAULT_HSBC_FCY_PROMO_URL,
    DEFAULT_DBS_FCY_BOARD_API_URL,
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
)


def get_url_defaults() -> Dict[str, str]:
    """
    返回 `argparse dest -> 脚本内置默认 URL` 的映射。

    用于 `apply_url_config_defaults(...)`：
    当 args.dest 没有被命令行显式覆盖时，允许外部 url_config 覆盖该 dest 的默认 URL。
    """
    # 返回的 dict key 必须与 argparse 的 dest 名完全一致；
    # 否则 `apply_url_config_defaults()` 无法正确判断/覆盖。
    return {
        # Citi + promo pages
        "url": DEFAULT_URL,
        "citi_all_promo_url": DEFAULT_CITI_ALL_PROMO_URL,
        "cimb_url": DEFAULT_CIMB_FCY_URL,
        "cimb_sgd_url": DEFAULT_CIMB_SGD_URL,
        "cimb_fcy_board_url": DEFAULT_CIMB_FCY_BOARD_URL,
        "hl_url": DEFAULT_HL_FD_URL,
        "hlf_url": DEFAULT_HLF_FD_URL,
        "hsbc_url": DEFAULT_HSBC_TD_URL,
        "icbc_url": DEFAULT_ICBC_FD_URL,
        "ocbc_url": DEFAULT_OCBC_FD_URL,
        "rhb_url": DEFAULT_RHB_FD_URL,
        "rhb_fcy_url": DEFAULT_RHB_FCY_FD_URL,
        "sif_url": DEFAULT_SIF_FD_URL,
        "scb_url": DEFAULT_SCB_SGD_TD_URL,
        "scb_fcy_url": DEFAULT_SCB_FCY_FD_URL,
        "sbi_url": DEFAULT_SBI_SGD_PROMO_URL,
        "sbi_usd_url": DEFAULT_SBI_USD_PROMO_URL,
        "uob_url": DEFAULT_UOB_SGD_TD_URL,
        "boc_url": DEFAULT_BOC_PROMO_URL,

        "bea_sgd_promo_url": DEFAULT_BEA_SGD_PROMO_URL,
        "bea_fcy_promo_url": DEFAULT_BEA_FCY_PROMO_URL,
        "maybank_sgd_promo_url": DEFAULT_MAYBANK_SGD_PROMO_URL,
        "hsbc_fcy_promo_url": DEFAULT_HSBC_FCY_PROMO_URL,
        "dbs_fcy_board_api_url": DEFAULT_DBS_FCY_BOARD_API_URL,

        # SGD board rates
        "citi_board_url": DEFAULT_CITI_SGD_BOARD_URL,
        "dbs_board_url": DEFAULT_DBS_SGD_BOARD_URL,
        "hl_board_url": DEFAULT_HL_SGD_BOARD_URL,
        "hlf_board_url": DEFAULT_HLF_SGD_BOARD_URL,
        "hsbc_board_url": DEFAULT_HSBC_SGD_BOARD_URL,
        "icbc_board_url": DEFAULT_ICBC_SGD_BOARD_URL,
        "icbc_fcy_board_url": DEFAULT_ICBC_FCY_BOARD_URL,
        "maybank_board_url": DEFAULT_MAYBANK_SGD_BOARD_URL,
        "ocbc_board_url": DEFAULT_OCBC_SGD_BOARD_URL,
        "rhb_board_pdf_url": DEFAULT_RHB_SGD_BOARD_PDF_URL,
        "sif_board_url": DEFAULT_SIF_SGD_BOARD_URL,
        "scb_board_url": DEFAULT_SCB_SGD_BOARD_URL,
        "sbi_board_url": DEFAULT_SBI_SGD_BOARD_URL,
        "uob_board_url": DEFAULT_UOB_SGD_BOARD_URL,
        "ocbc_fcy_board_url": DEFAULT_OCBC_FCY_BOARD_URL,
        "uob_fcy_board_url": DEFAULT_UOB_FCY_BOARD_URL,

        # FCY board rates
        "hl_fcy_board_url": DEFAULT_HL_FCY_BOARD_URL,
        "hsbc_fcy_board_url": DEFAULT_HSBC_FCY_BOARD_URL,
        "maybank_fcy_board_url": DEFAULT_MAYBANK_FCY_BOARD_URL,
        "scb_fcy_board_url": DEFAULT_SCB_FCY_BOARD_URL,
        "sbi_fcy_board_url": DEFAULT_SBI_FCY_BOARD_URL,
        "rhb_fcy_board_pdf_url": DEFAULT_RHB_FCY_BOARD_PDF_URL,

        # BEA / BOC boards
        "bea_sgd_board_api_url": DEFAULT_BEA_SGD_BOARD_API_URL,
        "bea_fcy_board_api_url": DEFAULT_BEA_FCY_BOARD_API_URL,
        "boc_board_url": DEFAULT_BOC_BOARD_URL,
    }


# Safety net: 自动给本模块中所有 def 加异常兜底
from bank_safety import auto_wrap_module_functions as _auto_wrap_module_functions

_auto_wrap_module_functions(globals(), module_name=__name__)

