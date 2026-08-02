#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 MarketRateData 的「元数据」sheet 导出 url_YYYYMMDD.xlsx（与 url_params.xlsx 同格式）。"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from url_config_loader import load_url_config
from url_key_aliases import URL_KEY_ALIASES

_SCRIPT_DIR = Path(__file__).resolve().parent
from project_paths import ASSETS_DIR

_TEMPLATE_XLSX = ASSETS_DIR / "url_params.xlsx"

# 元数据「项目」列 -> argparse dest（与 bank_excel_data_builder 元数据行一致）
META_PROJECT_TO_DEST: dict[str, str] = {
    "Citibank 来源链接": "url",
    "Citibank 外币 FX 定存促销页": "citi_all_promo_url",
    "CIMB FCY 页面链接": "cimb_url",
    "CIMB 新元定存利率页": "cimb_sgd_url",
    "CIMB 外币挂牌利率页": "cimb_fcy_board_url",
    "HL Bank 定存促销页": "hl_url",
    "HLF 新元促销页": "hlf_url",
    "Maybank 新元定存促销页": "maybank_sgd_promo_url",
    "汇丰新加坡 新币定期存款页": "hsbc_url",
    "HSBC 外币定存促销页": "hsbc_fcy_promo_url",
    "工行新加坡 定存促销页": "icbc_url",
    "OCBC 新元定存促销页": "ocbc_url",
    "RHB 新元定存促销页": "rhb_url",
    "RHB 外币定存促销页": "rhb_fcy_url",
    "SingFinance 新元定存促销页": "sif_url",
    "UOB 新元定存促销页": "uob_url",
    "SCB 新元定存促销页": "scb_url",
    "SCB 外币定存促销页": "scb_fcy_url",
    "SBI 新元定存促销页": "sbi_url",
    "SBI 外币定存促销页": "sbi_usd_url",
    "中国银行新加坡 定存促销页": "boc_url",
    "BEA 新元定存促销页": "bea_sgd_promo_url",
    "BEA 外币定存促销页": "bea_fcy_promo_url",
    "Citibank SGD 挂牌利率页": "citi_board_url",
    "DBS SGD 挂牌利率页": "dbs_board_url",
    "HL Bank SGD 挂牌利率页": "hl_board_url",
    "HLF SGD 挂牌利率页": "hlf_board_url",
    "汇丰 SGD 挂牌利率页": "hsbc_board_url",
    "工行新加坡 SGD 挂牌利率页": "icbc_board_url",
    "Maybank SGD 挂牌利率页": "maybank_board_url",
    "OCBC SGD 挂牌利率页": "ocbc_board_url",
    "RHB SGD 挂牌利率 PDF": "rhb_board_pdf_url",
    "SingFinance SGD 挂牌利率页": "sif_board_url",
    "SCB SGD 挂牌利率页": "scb_board_url",
    "SBI SGD 挂牌利率页": "sbi_board_url",
    "UOB SGD 挂牌利率页": "uob_board_url",
    "HL Bank 外币挂牌利率页": "hl_fcy_board_url",
    "HSBC 外币挂牌利率页": "hsbc_fcy_board_url",
    "Maybank 外币挂牌利率页": "maybank_fcy_board_url",
    "DBS 外币挂牌利率页": "dbs_fcy_board_api_url",
    "SCB 外币挂牌利率页": "scb_fcy_board_url",
    "SBI 外币挂牌利率页": "sbi_fcy_board_url",
    "RHB 外币挂牌利率 PDF": "rhb_fcy_board_pdf_url",
    "BEA 新元挂牌利率 API": "bea_sgd_board_api_url",
    "BEA 外币挂牌利率 API": "bea_fcy_board_api_url",
    "BOC 新元挂牌利率页": "boc_board_url",
    "BOC 外币挂牌利率页": "boc_board_url",
    "工行新加坡 外币挂牌利率页": "icbc_fcy_board_url",
    "OCBC 外币定存利率页（官方日价表）": "ocbc_fcy_board_url",
    "UOB 外币挂牌利率页": "uob_fcy_board_url",
    "BEA 新元定存促销页": "bea_sgd_promo_url",
    "BEA 外币定存促销页": "bea_fcy_promo_url",
    "BEA 新元定存促销页面": "bea_sgd_promo_url",
    "BEA 外币定存促销页面": "bea_fcy_promo_url",
    "Maybank 新元定存促销页面": "maybank_sgd_promo_url",
    "HSBC 外币定存促销页面": "hsbc_fcy_promo_url",
    "DBS 外币挂牌利率页": "dbs_fcy_board_api_url",
    "DBS 外币挂牌利率页面": "dbs_fcy_board_api_url",
}


def extract_url_from_meta_content(content: Any) -> str:
    """从元数据「内容」单元格提取主 URL（支持 UOB 多行 + API 附注）。"""
    s = str(content or "").strip()
    if not s or s.startswith("抓取失败") or s.startswith("与「") or "未发现" in s[:20]:
        return ""
    for line in s.splitlines():
        line = line.strip()
        if line.startswith("http"):
            return line.split()[0].rstrip("）").rstrip("(")
    if s.startswith("http"):
        return s.split()[0]
    return ""


def _read_meta_sheet(market_xlsx: Path) -> pd.DataFrame:
    xl = pd.ExcelFile(market_xlsx)
    sheet = "元数据" if "元数据" in xl.sheet_names else xl.sheet_names[0]
    return pd.read_excel(market_xlsx, sheet_name=sheet, dtype=str)


def dest_urls_from_market_meta(market_xlsx: Path) -> dict[str, str]:
    """解析元数据 sheet，返回 dest -> url。"""
    df = _read_meta_sheet(market_xlsx)
    if df.empty or len(df.columns) < 2:
        return {}

    col0, col1 = df.columns[0], df.columns[1]
    dest_to_url: dict[str, str] = {}

    for _, row in df.iterrows():
        project = str(row.get(col0, "") or "").strip()
        if not project:
            continue
        dest = META_PROJECT_TO_DEST.get(project)
        if not dest:
            continue
        url = extract_url_from_meta_content(row.get(col1, ""))
        if url:
            dest_to_url[dest] = url
    return dest_to_url


def _template_keys() -> list[str]:
    if not _TEMPLATE_XLSX.is_file():
        return []
    df = pd.read_excel(_TEMPLATE_XLSX, dtype=str)
    if df.empty:
        return []
    key_col = df.columns[0]
    return [str(k).strip() for k in df[key_col].tolist() if str(k).strip()]


def build_url_snapshot_rows(dest_to_url: dict[str, str]) -> list[dict[str, str]]:
    """按 url_params.xlsx 的 key 顺序生成行；同一 dest 可对应多行 key。"""
    keys = _template_keys()
    if not keys:
        keys = sorted({URL_KEY_ALIASES.get(d, d) for d in dest_to_url})

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for key in keys:
        dest = URL_KEY_ALIASES.get(key, key)
        url = dest_to_url.get(dest, "")
        if not url:
            continue
        pair = (key, url)
        if pair in seen:
            continue
        seen.add(pair)
        rows.append({"key": key, "url": url})
    return rows


def url_snapshot_filename(for_date: datetime | None = None) -> str:
    d = for_date or datetime.now()
    return f"url_{d.strftime('%Y%m%d')}.xlsx"


def export_url_snapshot_from_market(
    market_xlsx: str | Path,
    *,
    out_path: str | Path | None = None,
    for_date: datetime | None = None,
) -> Path | None:
    """
    从 MarketRateData xlsx 元数据导出 url_YYYYMMDD.xlsx。

    默认写在 Market 文件同目录；out_path 可显式指定。
    返回写出路径；无有效 URL 时返回 None。
    """
    market_path = Path(market_xlsx)
    if not market_path.is_file():
        raise FileNotFoundError(f"Market 文件不存在: {market_path}")

    dest_to_url = dest_urls_from_market_meta(market_path)
    rows = build_url_snapshot_rows(dest_to_url)
    if not rows:
        print(f"[URL_SNAPSHOT] 未从元数据解析到有效链接，跳过: {market_path}", flush=True)
        return None

    if out_path is None:
        out_path = market_path.parent / url_snapshot_filename(for_date)
    else:
        out_path = Path(out_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(out_path, index=False)
    print(f"[URL_SNAPSHOT] 已写出 {len(rows)} 条: {out_path}", flush=True)
    return out_path


def load_gold_from_snapshot(path: str | Path) -> dict[str, str]:
    """读取 url_YYYYMMDD.xlsx / json，返回 dest -> url（供评测用）。"""
    return load_url_config(str(path))


def find_latest_url_snapshot(search_root: str | Path | None = None) -> Path | None:
    """在 RateStats_Portable 下查找最新的 url_YYYYMMDD.xlsx。"""
    root = Path(search_root) if search_root else _SCRIPT_DIR
    candidates: list[tuple[str, Path]] = []
    pat = re.compile(r"^url_(\d{8})\.xlsx$", re.I)
    for p in root.rglob("url_*.xlsx"):
        m = pat.match(p.name)
        if m:
            candidates.append((m.group(1), p))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="从 MarketRateData 元数据导出 url_YYYYMMDD.xlsx")
    ap.add_argument("market_xlsx", help="MarketRateData_*.xlsx 路径")
    ap.add_argument("--out", default=None, help="输出路径（默认与 Market 同目录）")
    args = ap.parse_args()
    try:
        out = export_url_snapshot_from_market(args.market_xlsx, out_path=args.out)
        return 0 if out else 1
    except Exception as e:
        print(f"[ERROR] {e}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
