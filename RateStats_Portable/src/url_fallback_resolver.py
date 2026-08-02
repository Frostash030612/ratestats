"""发现阶段 fallback：优先手动 url_params.xlsx，其次代码内 DEFAULT_*。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from url_config_loader import DEFAULT_URL_CONFIG, load_url_config
from url_key_aliases import URL_PARAM_DEST_KEYS

_SCRIPT_DIR = Path(__file__).resolve().parent


def _code_defaults() -> dict[str, str]:
    """与 _discovery_common / vertex_url_discovery 中的 DEFAULT_FALLBACK 同源。"""
    from url_sources import (  # noqa: WPS433 — 局部 import 避免循环
        DEFAULT_BEA_FCY_BOARD_API_URL,
        DEFAULT_BEA_FCY_PROMO_URL,
        DEFAULT_BEA_SGD_BOARD_API_URL,
        DEFAULT_BEA_SGD_PROMO_URL,
        DEFAULT_BOC_BOARD_URL,
        DEFAULT_BOC_PROMO_URL,
        DEFAULT_CIMB_FCY_URL,
        DEFAULT_CIMB_SGD_URL,
        DEFAULT_CIMB_FCY_BOARD_URL,
        DEFAULT_CITI_SGD_BOARD_URL,
        DEFAULT_DBS_FCY_BOARD_API_URL,
        DEFAULT_DBS_SGD_BOARD_URL,
        DEFAULT_HL_FCY_BOARD_URL,
        DEFAULT_HL_FD_URL,
        DEFAULT_HL_SGD_BOARD_URL,
        DEFAULT_HLF_FD_URL,
        DEFAULT_HLF_SGD_BOARD_URL,
        DEFAULT_HSBC_FCY_BOARD_URL,
        DEFAULT_HSBC_FCY_PROMO_URL,
        DEFAULT_HSBC_SGD_BOARD_URL,
        DEFAULT_HSBC_TD_URL,
        DEFAULT_ICBC_FCY_BOARD_URL,
        DEFAULT_ICBC_FD_URL,
        DEFAULT_ICBC_SGD_BOARD_URL,
        DEFAULT_MAYBANK_FCY_BOARD_URL,
        DEFAULT_MAYBANK_SGD_BOARD_URL,
        DEFAULT_MAYBANK_SGD_PROMO_URL,
        DEFAULT_OCBC_FCY_BOARD_URL,
        DEFAULT_OCBC_FD_URL,
        DEFAULT_OCBC_SGD_BOARD_URL,
        DEFAULT_RHB_FCY_BOARD_PDF_URL,
        DEFAULT_RHB_FCY_FD_URL,
        DEFAULT_RHB_FD_URL,
        DEFAULT_RHB_SGD_BOARD_PDF_URL,
        DEFAULT_SBI_FCY_BOARD_URL,
        DEFAULT_SBI_SGD_BOARD_URL,
        DEFAULT_SBI_SGD_PROMO_URL,
        DEFAULT_SBI_USD_PROMO_URL,
        DEFAULT_SCB_FCY_BOARD_URL,
        DEFAULT_SCB_FCY_FD_URL,
        DEFAULT_SCB_SGD_BOARD_URL,
        DEFAULT_SCB_SGD_TD_URL,
        DEFAULT_SIF_FD_URL,
        DEFAULT_SIF_SGD_BOARD_URL,
        DEFAULT_UOB_FCY_BOARD_URL,
        DEFAULT_UOB_SGD_BOARD_URL,
        DEFAULT_UOB_SGD_TD_URL,
        DEFAULT_URL,
    )

    return {
        "url": DEFAULT_URL,
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
        "bea_sgd_board_api_url": DEFAULT_BEA_SGD_BOARD_API_URL,
        "bea_fcy_board_api_url": DEFAULT_BEA_FCY_BOARD_API_URL,
        "boc_board_url": DEFAULT_BOC_BOARD_URL,
        "bea_sgd_promo_url": DEFAULT_BEA_SGD_PROMO_URL,
        "bea_fcy_promo_url": DEFAULT_BEA_FCY_PROMO_URL,
        "maybank_sgd_promo_url": DEFAULT_MAYBANK_SGD_PROMO_URL,
        "hsbc_fcy_promo_url": DEFAULT_HSBC_FCY_PROMO_URL,
        "dbs_fcy_board_api_url": DEFAULT_DBS_FCY_BOARD_API_URL,
        "ocbc_fcy_board_url": DEFAULT_OCBC_FCY_BOARD_URL,
        "uob_fcy_board_url": DEFAULT_UOB_FCY_BOARD_URL,
        "hl_fcy_board_url": DEFAULT_HL_FCY_BOARD_URL,
        "hsbc_fcy_board_url": DEFAULT_HSBC_FCY_BOARD_URL,
        "maybank_fcy_board_url": DEFAULT_MAYBANK_FCY_BOARD_URL,
        "scb_fcy_board_url": DEFAULT_SCB_FCY_BOARD_URL,
        "sbi_fcy_board_url": DEFAULT_SBI_FCY_BOARD_URL,
        "rhb_fcy_board_pdf_url": DEFAULT_RHB_FCY_BOARD_PDF_URL,
    }


@lru_cache(maxsize=4)
def build_fallback_map(manual_xlsx: str | None = None) -> dict[str, str]:
    """手动 url_params 覆盖代码默认；未配置的 dest 仍用 DEFAULT_*。"""
    out = _code_defaults()
    from project_paths import ASSETS_DIR
    path = manual_xlsx or str(ASSETS_DIR / "url_params.xlsx")
    manual = load_url_config(path) if Path(path).is_file() else {}
    for dest in URL_PARAM_DEST_KEYS:
        u = (manual.get(dest) or "").strip()
        if u:
            out[dest] = u
    return out
