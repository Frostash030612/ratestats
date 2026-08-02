#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历史/典型错链负样本（与线上 Vertex 混淆一致，优于随机路径扰动）。"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pandas as pd

from _portable import DATA_DIR

# dest -> 明确错误但常出现在搜索候选中的 URL（可继续往 data/hard_negatives.csv 追加）
DEST_HARD_NEGATIVE_URLS: dict[str, tuple[str, ...]] = {
    "ocbc_board_url": (
        "https://www.ocbc.com/premier-banking/our-solutions/deposits/time-deposit",
        "https://www.ocbc.com/business-banking/sgd-fixed-deposit-interest-rates",
        "https://www.ocbc.com/personal-banking/deposits/fixed-deposit-account",
        "https://www.ocbc.com/business-banking/smes/accounts/singapore-dollar-time-deposit",
    ),
    "dbs_fcy_board_api_url": (
        "https://www.dbs.com.sg/personal/deposits/fixed-deposits/foreign-currency-fixed-deposit",
        "https://www.dbs.com.sg/personal/deposits/fixed-deposits/singapore-dollar-fixed-deposit",
        "https://www.dbs.com.sg/personal/deposits/fixed-deposits/fixed-deposit",
        "https://www.dbs.com.sg/personal/deposits",
        "https://www.dbs.com.sg/global-financial-markets/dbs-treasury-api",
        "https://www.dbs.com.sg/personal/deposits/digital-services/default.page",
        "https://www.dbs.com.sg/personal/support/bank-general-swift-code-details.html",
    ),
    "dbs_board_url": (
        "https://www.dbs.com.sg/personal/deposits/fixed-deposits/singapore-dollar-fixed-deposit",
        "https://www.dbs.com.sg/personal/deposits",
    ),
    "hsbc_board_url": (
        "https://www.hsbc.com.sg/foreign-currency-time-deposits/",
        "https://www.hsbc.com.sg/accounts/products/foreign-currency-time-deposit/",
    ),
    "hsbc_url": (
        "https://www.hsbc.com.sg/foreign-currency-time-deposits/",
        "https://www.hsbc.com.sg/accounts/products/foreign-currency-time-deposit/",
    ),
    "uob_board_url": (
        "https://www.uob.com.sg/personal/online-rates/index.page",
    ),
    "scb_url": (
        "https://www.sc.com/sg/business/deposits/business-time-deposits/",
        "https://www.sc.com/sg/help/faqs/business-yield/",
    ),
    "hlf_board_url": (
        "https://www.hlf.com.sg/personal-banking/deposits/current-account",
    ),
    "bea_sgd_promo_url": (
        "https://www.beabank.com.sg/beasg-rates-sgd-fixed-deposit-rates",
        "https://www.beabank.com.sg/formid=sg001",
    ),
    "rhb_board_pdf_url": (
        "https://rhbgroup.com.sg/rhb/personal/promotions/fixed-deposit-campaign",
        "https://rhbgroup.com.sg/rhb/personal/rates-and-charges",
        "https://rhbgroup.com.sg/rhb/latest-promotions",
        "https://rhbgroup.com.sg/dam/jcr:f538a27e-83be-478d-9fdf-efab285ad68d/TCs%20Governing%20Fixed%20Deposit%202025%20FD%20Promo%20(eff%2025%20July%202025).pdf",
        "https://rhbgroup.com.sg/dam/jcr:9883ff55-00e1-4af0-bbf9-b200aee6294e/Personal%20Pricing%20Guide%20for%20Deposit%20Accounts%20and%20Services%20(07082023).pdf",
    ),
    "rhb_fcy_board_pdf_url": (
        "https://rhbgroup.com.sg/rhb/personal/promotions/fixed-deposit-campaign",
        "https://rhbgroup.com.sg/rhb/business/rates-and-charges",
        "https://rhbgroup.com.sg/rhb/latest-promotions",
        "https://rhbgroup.com.sg/dam/jcr:9883ff55-00e1-4af0-bbf9-b200aee6294e/Personal%20Pricing%20Guide%20for%20Deposit%20Accounts%20and%20Services%20(07082023).pdf",
    ),
    "boc_url": (
        "https://www.bankofchina.com/sg/bocinfo/bi3/",
        "https://www.bankofchina.com/sg/bocinfo/bi3/bi31/",
        "https://www.bankofchina.com/sg/bocinfo/bi3/bi32/202605/t20260504_25664330.html",
        "https://www.bankofchina.com/business-banking",
    ),
    "boc_board_url": (
        "https://www.bankofchina.com/sg/bocinfo/bi3/",
        "https://www.bankofchina.com/sg/bocinfo/bi3/bi31/",
        "https://www.bankofchina.com/sg/bocinfo/bi3/bi31/202604/t20260413_25660784.html",
        "https://www.bankofchina.com/sg/",
    ),
}

HARD_NEGATIVES_CSV = DATA_DIR / "hard_negatives.csv"


def _load_csv_negatives() -> dict[str, list[str]]:
    if not HARD_NEGATIVES_CSV.is_file():
        return {}
    df = pd.read_csv(HARD_NEGATIVES_CSV)
    if "dest" not in df.columns or "url" not in df.columns:
        return {}
    out: dict[str, list[str]] = {}
    for _, row in df.iterrows():
        dest = str(row["dest"]).strip()
        url = str(row["url"]).strip()
        if dest and url.startswith("http"):
            out.setdefault(dest, []).append(url)
    return out


def iter_hard_negative_urls(dest: str) -> Iterator[str]:
    """合并内置模板与 data/hard_negatives.csv。"""
    seen: set[str] = set()
    csv_map = _load_csv_negatives()
    for u in list(DEST_HARD_NEGATIVE_URLS.get(dest, ())) + csv_map.get(dest, []):
        if u not in seen:
            seen.add(u)
            yield u


def build_hard_negative_rows(gold: dict[str, str]) -> list[dict]:
    """为各 dest 追加典型错链负样本。"""
    rows: list[dict] = []
    for dest, ref in gold.items():
        if not ref.startswith("http"):
            continue
        for rank, url in enumerate(iter_hard_negative_urls(dest)):
            if url == ref:
                continue
            rows.append(
                {
                    "dest": dest,
                    "url": url,
                    "label": 0,
                    "reference_url": ref,
                    "candidate_rank": rank + 1,
                    "sample_type": "hard_negative",
                }
            )
    return rows
