#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vertex 发现 + ML 选链 → url_params_ai_ml.xlsx → 可选抓取 Market。"""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from _portable import DEFAULT_MANUAL_XLSX, MODEL_DIR, PORTABLE_DIR, RUNS_ROOT
from picker import pick_best_url_ml

if str(PORTABLE_DIR) not in sys.path:
    sys.path.insert(0, str(PORTABLE_DIR))

from url_fallback_resolver import build_fallback_map  # noqa: E402
from url_key_aliases import URL_KEY_ALIASES, URL_PARAM_DEST_KEYS  # noqa: E402
from vertex_search_client import extract_links, search_url  # noqa: E402

try:
    from vertex_url_discovery import QUERY_BY_DEST, _canonical_friendly_keys  # noqa: E402
except ImportError:
    QUERY_BY_DEST = {}
    _canonical_friendly_keys = None


@dataclass
class DiscoverResult:
    key: str
    dest: str
    query: str
    url: str
    source: str
    candidates: str
    ml_proba: float


def discover_all_ml(
    *,
    sleep_sec: float = 0.4,
    manual_fallback_xlsx: str | None = None,
    model_path: Path | None = None,
) -> list[DiscoverResult]:
    if _canonical_friendly_keys:
        dest_to_key = _canonical_friendly_keys()
    else:
        dest_to_key = {d: d for d in URL_PARAM_DEST_KEYS}
        for friendly, dest in URL_KEY_ALIASES.items():
            dest_to_key.setdefault(dest, friendly)

    fallback_map = build_fallback_map(manual_fallback_xlsx or str(DEFAULT_MANUAL_XLSX))
    results: list[DiscoverResult] = []

    for dest in sorted(URL_PARAM_DEST_KEYS):
        key = dest_to_key.get(dest, dest)
        query = QUERY_BY_DEST.get(dest, f"singapore bank {dest.replace('_', ' ')} fixed deposit rates")
        fallback = fallback_map.get(dest, "")

        try:
            payload = search_url(query, page_size=8)
            links = extract_links(payload)
        except Exception:
            links = []

        url, source = pick_best_url_ml(links, dest, fallback, model_path=model_path)
        from picker import ml_score

        proba = ml_score(url, dest, reference_url=fallback) if url else 0.0
        tag = "vertex_ml" if source == "ml_pick" else source

        results.append(
            DiscoverResult(
                key=key,
                dest=dest,
                query=query,
                url=url,
                source=tag,
                candidates=" | ".join(links[:5]),
                ml_proba=round(proba, 4),
            )
        )
        time.sleep(sleep_sec)

    return results


def write_url_params_xlsx(results: list[DiscoverResult], path: Path) -> None:
    rows = [{"key": r.key, "url": r.url} for r in results if r.url]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.xlsx")
    pd.DataFrame(rows).to_excel(tmp, index=False)
    tmp.replace(path)


def write_discovery_report(results: list[DiscoverResult], path: Path) -> None:
    df = pd.DataFrame(
        [
            {
                "key": r.key,
                "dest": r.dest,
                "query": r.query,
                "url": r.url,
                "source": r.source,
                "ml_proba": r.ml_proba,
                "candidates_top5": r.candidates,
            }
            for r in results
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Vertex + ML 选链发现")
    ap.add_argument("--manual", default=str(DEFAULT_MANUAL_XLSX), help="训练/回退用的手动配置")
    ap.add_argument("--model", default=str(MODEL_DIR / "url_ranker.joblib"))
    ap.add_argument("--discover-only", action="store_true")
    ap.add_argument(
        "--out-dir",
        default=str(RUNS_ROOT),
        help="批次输出根目录（默认项目 runs/；实际写入 runs/<run-tag>/）",
    )
    ap.add_argument("--run-tag", default=None)
    ap.add_argument("--sleep", type=float, default=0.4)
    ap.add_argument("--fetch", action="store_true", help="发现后抓取 Market（需模型与配置就绪）")
    args = ap.parse_args(argv)

    model_path = Path(args.model)
    if not model_path.is_file():
        print(f"[ERROR] 请先训练模型: python train.py\n  缺少: {model_path}", file=sys.stderr)
        return 1

    tag = args.run_tag or datetime.now().strftime("%Y%m%d_%H.%M")
    out_dir = Path(args.out_dir) / tag
    out_dir.mkdir(parents=True, exist_ok=True)

    url_xlsx = out_dir / "url_params_ai_ml.xlsx"
    report_xlsx = out_dir / f"ai_search_discovered_ml_{tag}.xlsx"

    try:
        results = discover_all_ml(
            sleep_sec=args.sleep,
            manual_fallback_xlsx=str(Path(args.manual)),
            model_path=model_path,
        )
        write_url_params_xlsx(results, url_xlsx)
        write_discovery_report(results, report_xlsx)
        n_ml = sum(1 for r in results if "ml" in r.source)
        print(f"[OK] {url_xlsx}")
        print(f"[OK] {report_xlsx}")
        print(f"[OK] ml_pick={n_ml} total={len(results)}")

        if args.fetch:
            market_out = out_dir / f"MarketRateData_{tag}_ML.xlsx"
            from bank_all_promo_rates import main as fetch_main

            rc = int(fetch_main(["--url-config", str(url_xlsx), "--xlsx-out", str(market_out)]))
            print(f"[FETCH] rc={rc} -> {market_out}")
            return rc

        return 0
    except Exception as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
