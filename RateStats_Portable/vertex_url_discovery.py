"""Discover bank URLs via Vertex AI Search and write url_params_ai.xlsx."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from url_key_aliases import URL_KEY_ALIASES, URL_PARAM_DEST_KEYS
from url_sources import (
    DEFAULT_BEA_FCY_BOARD_API_URL,
    DEFAULT_BEA_FCY_PROMO_URL,
    DEFAULT_BEA_SGD_BOARD_API_URL,
    DEFAULT_BEA_SGD_PROMO_URL,
    DEFAULT_BOC_BOARD_URL,
    DEFAULT_BOC_PROMO_URL,
    DEFAULT_CIMB_FCY_URL,
    DEFAULT_CIMB_SGD_URL,
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
from url_discovery_pick import pick_best_url as _pick_best_url_shared
from url_fallback_resolver import build_fallback_map
from vertex_search_client import extract_links, search_url

_SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_FALLBACK: dict[str, str] = {
    "url": DEFAULT_URL,
    "cimb_url": DEFAULT_CIMB_FCY_URL,
    "cimb_sgd_url": DEFAULT_CIMB_SGD_URL,
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

# dest -> Vertex search query
QUERY_BY_DEST: dict[str, str] = {
    "url": "citibank singapore all promo fixed deposit",
    "cimb_sgd_url": "cimb singapore sgd fixed deposit rates",
    "cimb_url": "cimb singapore foreign currency fixed deposit account",
    "hl_url": "hong leong bank singapore fixed deposit promotion",
    "hlf_url": "hong leong finance fixed deposit promotion singapore",
    "hsbc_url": "hsbc singapore time deposit account",
    "icbc_url": "icbc singapore fixed deposit promotion",
    "ocbc_url": "ocbc singapore fixed deposit account promotion",
    "rhb_url": "rhb singapore fixed deposit campaign",
    "rhb_fcy_url": "rhb singapore foreign currency fixed deposit campaign",
    "sif_url": "singfinance singapore fixed deposit",
    "scb_url": "standard chartered singapore dollar time deposit",
    "scb_fcy_url": "standard chartered singapore foreign currency time deposit",
    "sbi_url": "sbi singapore sgd fixed deposit promotions",
    "sbi_usd_url": "sbi singapore usd fixed deposit promotions",
    "uob_url": "uob singapore fixed deposit promotion",
    "boc_url": "bank of china singapore deposit promotion fixed",
    "citi_board_url": "citibank singapore fixed deposit account board rates",
    "dbs_board_url": "dbs singapore dollar fixed deposit rate online",
    "hl_board_url": "hong leong bank singapore fixed deposit rate",
    "hlf_board_url": "hong leong finance fixed deposits singapore rates",
    "hsbc_board_url": "hsbc singapore dollar deposits interest rates",
    "icbc_board_url": "icbc singapore deposit interest rates sgd usd table board",
    "icbc_fcy_board_url": "icbc singapore deposit interest rates foreign currency usd rmb board table",
    "maybank_board_url": "maybank singapore deposit interest rates",
    "ocbc_board_url": "ocbc sgd fixed deposit interest rates",
    "rhb_board_pdf_url": "rhb singapore deposit rates pdf",
    "sif_board_url": "singfinance singapore deposit rates",
    "scb_board_url": "standard chartered singapore sgd time deposit interest rates",
    "sbi_board_url": "sbi singapore interest rates deposit",
    "uob_board_url": "uob singapore dollar time fixed deposit rates",
    "bea_sgd_board_api_url": "bea singapore fixed deposit rate enquiry api",
    "bea_fcy_board_api_url": "bea singapore foreign currency fixed deposit rate api",
    "boc_board_url": "bank of china singapore deposit rates board",
    "bea_sgd_promo_url": "bank of east asia singapore deposit promotion",
    "bea_fcy_promo_url": "bea singapore foreign currency deposit promotion",
    "maybank_sgd_promo_url": "maybank singapore sgd time deposit promotion",
    "hsbc_fcy_promo_url": "hsbc singapore foreign currency time deposit rates pdf",
    "dbs_fcy_board_api_url": "dbs singapore foreign currency fixed deposit rates api",
    "ocbc_fcy_board_url": "ocbc daily price foreign currency fixed deposit rates",
    "uob_fcy_board_url": "uob foreign currency fixed deposit rates singapore",
    "hl_fcy_board_url": "hong leong bank foreign currency fixed deposit singapore",
    "hsbc_fcy_board_url": "hsbc foreign currency time deposits rates singapore",
    "maybank_fcy_board_url": "maybank singapore foreign currency deposit rates",
    "scb_fcy_board_url": "standard chartered foreign currency interest rates singapore",
    "sbi_fcy_board_url": "sbi singapore interest rates foreign currency",
    "rhb_fcy_board_pdf_url": "rhb singapore foreign currency deposit rates pdf",
}

BLOCK_PATH = (
    "careers",
    "login",
    "privacy",
    "cookie",
    "newsroom",
    "about-us",
    "/business/",
    "/corporate/",
    "wealth",
    "insurance-only",
)
POSITIVE = ("deposit", "fixed", "rate", "rates", "interest", "time-deposit", "promo", "promotion", "campaign")
API_HINTS = ("api", "eform-api", "sg-rates-api", ".jsp")
PDF_HINTS = (".pdf",)


@dataclass
class DiscoverResult:
    """单个 dest 的发现结果（用于写 xlsx 与发现报告）。"""

    key: str
    dest: str
    query: str
    url: str
    source: str
    candidates: str


def _canonical_friendly_keys() -> dict[str, str]:
    """dest → Excel 友好列名（key），与 url_params 表头一致。"""
    dest_to_key: dict[str, str] = {}
    for friendly, dest in URL_KEY_ALIASES.items():
        dest_to_key.setdefault(dest, friendly)
    for dest in sorted(URL_PARAM_DEST_KEYS):
        dest_to_key.setdefault(dest, dest)
    return dest_to_key


def pick_best_url(candidates: list[str], dest: str, fallback: str) -> tuple[str, str]:
    """Vertex 封装：调用共享选链，将 source "ai" 重命名为 "vertex"。"""
    url, raw = _pick_best_url_shared(candidates, dest, fallback)
    return url, ("vertex" if raw == "ai" else raw)


def discover_all(
    *,
    sleep_sec: float = 0.4,
    intent_mode: str | None = None,
    manual_fallback_xlsx: str | None = None,
) -> list[DiscoverResult]:
    """遍历全部 dest：Vertex 搜索 → 选链 → 汇总 DiscoverResult 列表。"""
    import os

    if intent_mode:
        os.environ["RATESTATS_INTENT_MODE"] = intent_mode.strip().lower()

    fallback_map = build_fallback_map(manual_fallback_xlsx)
    dest_to_key = _canonical_friendly_keys()
    results: list[DiscoverResult] = []

    for dest in sorted(URL_PARAM_DEST_KEYS):
        key = dest_to_key[dest]
        query = QUERY_BY_DEST.get(dest, f"singapore bank {dest.replace('_', ' ')} fixed deposit rates")
        fallback = fallback_map.get(dest, "")

        try:
            payload = search_url(query, page_size=8)
            links = extract_links(payload)
        except Exception:
            links = []

        url, source = pick_best_url(links, dest, fallback)
        results.append(
            DiscoverResult(
                key=key,
                dest=dest,
                query=query,
                url=url,
                source=source,
                candidates=" | ".join(links[:5]),
            )
        )
        time.sleep(sleep_sec)

    return results


def write_url_params_xlsx(results: list[DiscoverResult], path: Path) -> None:
    """将发现结果写成 url_params_ai 格式（key, url 两列）。"""
    rows = [{"key": r.key, "url": r.url} for r in results if r.url]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.xlsx")
    pd.DataFrame(rows).to_excel(tmp, index=False)
    try:
        tmp.replace(path)
    except OSError:
        # 目标文件可能被 Excel 打开；保留 .tmp 供调用方回退读取
        raise


def write_discovery_report(results: list[DiscoverResult], path: Path) -> None:
    """写详细发现报告（含 query、source、candidates_top5）供人工排查。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        [
            {
                "key": r.key,
                "dest": r.dest,
                "query": r.query,
                "url": r.url,
                "source": r.source,
                "candidates_top5": r.candidates,
            }
            for r in results
        ]
    )
    df.to_excel(path, index=False)


def run_discovery(
    *,
    url_params_path: Path | None = None,
    report_path: Path | None = None,
) -> list[DiscoverResult]:
    """一键发现：discover_all + 写 url_params_ai.xlsx + 发现报告。"""
    tag = datetime.now().strftime("%Y%m%d_%H.%M")
    url_params_path = url_params_path or (_SCRIPT_DIR / "assets" / "url_params_ai.xlsx")
    report_path = report_path or (_SCRIPT_DIR / "assets" / f"ai_search_discovered_{tag}.xlsx")
    results = discover_all()
    write_url_params_xlsx(results, url_params_path)
    write_discovery_report(results, report_path)
    return results
