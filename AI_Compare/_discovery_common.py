"""URL discovery 共享逻辑（QUERY / FALLBACK / 打分 / 挑选 / IO）。

每个 provider 子目录只需实现 `search_urls(query) -> list[str]`，
然后调用 `discover_all(search_fn=..., source_tag="bing")` 即可。

通过 sys.path 注入 RateStats_Portable，复用 `url_key_aliases` / `url_sources`。
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd

_THIS = Path(__file__).resolve().parent
_RATESTATS = _THIS.parent / "RateStats_Portable"
if str(_RATESTATS) not in sys.path:
    sys.path.insert(0, str(_RATESTATS))

# noqa: E402 - sys.path 设置后再 import
from url_discovery_config import get_intent_mode  # noqa: E402
from url_fallback_resolver import build_fallback_map  # noqa: E402
from url_discovery_pick import pick_best_url  # noqa: E402
from url_key_aliases import URL_KEY_ALIASES, URL_PARAM_DEST_KEYS  # noqa: E402

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

@dataclass
class DiscoverResult:
    """单条 dest 的发现记录（Serper/Brave/Tavily/Vertex 共用结构）。"""

    key: str
    dest: str
    query: str
    url: str
    source: str
    candidates: str


def canonical_friendly_keys() -> dict[str, str]:
    """dest → Excel 列名 key（与 url_params 表头一致）。"""
    dest_to_key: dict[str, str] = {}
    for friendly, dest in URL_KEY_ALIASES.items():
        dest_to_key.setdefault(dest, friendly)
    for dest in sorted(URL_PARAM_DEST_KEYS):
        dest_to_key.setdefault(dest, dest)
    return dest_to_key


def discover_all(
    *,
    search_fn: Callable[[str], list[str]],
    source_tag: str,
    sleep_sec: float = 0.4,
    intent_mode: str | None = None,
    manual_fallback_xlsx: str | None = None,
) -> list[DiscoverResult]:
    """对每个 dest 调一次 search_fn，挑出最佳 URL。

    search_fn(query) 需要返回去掉 fragment 的 URL 列表。
    source_tag 仅用于回填 "source" 列（如 "bing"/"serper"/"brave"/"tavily"）。
    """
    if intent_mode:
        os.environ["RATESTATS_INTENT_MODE"] = intent_mode.strip().lower()

    fallback_map = build_fallback_map(manual_fallback_xlsx)
    dest_to_key = canonical_friendly_keys()
    results: list[DiscoverResult] = []

    for dest in sorted(URL_PARAM_DEST_KEYS):
        key = dest_to_key[dest]
        query = QUERY_BY_DEST.get(dest, f"singapore bank {dest.replace('_', ' ')} fixed deposit rates")
        fallback = fallback_map.get(dest, "")

        try:
            links = list(search_fn(query)) or []
        except Exception as exc:
            print(f"[{source_tag}] {dest} search failed: {exc}")
            links = []

        url, raw_source = pick_best_url(links, dest, fallback)
        source = source_tag if raw_source == "ai" else raw_source
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
    """写出 url_params_ai 格式 xlsx（key + url）。"""
    rows = [{"key": r.key, "url": r.url} for r in results if r.url]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.xlsx")
    pd.DataFrame(rows).to_excel(tmp, index=False)
    try:
        tmp.replace(path)
    except OSError:
        raise


def write_discovery_report(results: list[DiscoverResult], path: Path) -> None:
    """写发现明细报表（query、source、候选 Top5）。"""
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


def default_output_paths(provider_dir: Path) -> tuple[Path, Path]:
    """返回 (url_params_ai.xlsx, ai_search_discovered_<tag>.xlsx)。"""
    tag = datetime.now().strftime("%Y%m%d_%H.%M")
    out_dir = provider_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "url_params_ai.xlsx", out_dir / f"ai_search_discovered_{tag}.xlsx"


def run_provider_discovery(
    *,
    provider_dir: Path,
    search_fn: Callable[[str], list[str]],
    source_tag: str,
    sleep_sec: float = 0.4,
    intent_mode: str | None = None,
    manual_fallback_xlsx: str | None = None,
) -> list[DiscoverResult]:
    """统一入口：跑发现 + 写 url_params_ai.xlsx + 写 discovery 报表。"""
    url_xlsx, report_xlsx = default_output_paths(provider_dir)
    results = discover_all(
        search_fn=search_fn,
        source_tag=source_tag,
        sleep_sec=sleep_sec,
        intent_mode=intent_mode,
        manual_fallback_xlsx=manual_fallback_xlsx,
    )
    write_url_params_xlsx(results, url_xlsx)
    write_discovery_report(results, report_xlsx)
    return results
