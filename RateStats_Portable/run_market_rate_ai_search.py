#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vertex AI Search 发现 URL -> url_params_ai.xlsx -> 抓取 -> MarketRateData_*_AISearch.xlsx

与手动流程完全分离：不读写 assets/url_params.xlsx / url_params.json。
手动流程仍用 02/03 批处理 + url_params.xlsx。

若需 Vertex + Serper + Brave + Tavily 四家分别发现并抓取，请用：
  AI_Compare/run_all_providers_market.py
"""
from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
AI_URL_XLSX = _SCRIPT_DIR / "assets" / "url_params_ai.xlsx"


def _sync_ai_json() -> int:
    """将 url_params_ai.xlsx 同步为 url_params_ai.json。"""
    from sync_url_params_ai_to_json import main as sync_main

    return int(sync_main())


def _run_fetch(market_out: Path) -> int:
    """用 url_params_ai.xlsx 调用 bank_all_promo_rates 生成 Market Excel。"""
    from bank_all_promo_rates import main as fetch_main

    if not AI_URL_XLSX.is_file():
        print(f"[AI] 缺少 {AI_URL_XLSX}，请先运行发现链接（勿使用 url_params.xlsx）", file=sys.stderr)
        return 1

    argv = [
        "--url-config",
        str(AI_URL_XLSX),
        "--xlsx-out",
        str(market_out),
    ]
    print(f"[AI] 使用配置: {AI_URL_XLSX}")
    print(f"[AI] 开始抓取并生成: {market_out}")
    return int(fetch_main(argv))


def main(argv: list[str] | None = None) -> int:
    """CLI：可选 Vertex 发现 → 同步 JSON → 抓取 → MarketRateData_*_AISearch.xlsx。"""
    p = argparse.ArgumentParser(
        description="AI 搜索链接 + 生成 MarketRateData_*_AISearch（独立 url_params_ai.*）"
    )
    p.add_argument(
        "--skip-discover",
        action="store_true",
        help="跳过 Vertex 搜索，沿用现有 assets/url_params_ai.xlsx",
    )
    p.add_argument(
        "--discover-only",
        action="store_true",
        help="仅搜索并写入 url_params_ai.xlsx / 发现报告，不抓取",
    )
    p.add_argument(
        "--out-dir",
        default=".",
        help="输出根目录（默认当前目录；会创建 YYYYMMDD 子目录）",
    )
    p.add_argument(
        "--output-folder",
        default=None,
        help="直接指定输出文件夹（与 03 批处理同一天目录时用，不再追加日期子目录）",
    )
    p.add_argument(
        "--run-tag",
        default=None,
        help="输出文件名时间标签，格式 YYYYMMDD_HH.mm（与 03 的 RUN_TAG 一致）",
    )
    p.add_argument(
        "--sleep",
        type=float,
        default=0.4,
        help="每次 Vertex 搜索间隔秒数（默认 0.4）",
    )
    p.add_argument(
        "--intent-mode",
        choices=("relaxed", "strict"),
        default="relaxed",
        help="发现选链模式：relaxed=优先适应改版(默认); strict=严格对齐路径",
    )
    args = p.parse_args(argv)

    tag = args.run_tag or datetime.now().strftime("%Y%m%d_%H.%M")
    date_folder = datetime.now().strftime("%Y%m%d")
    if args.output_folder:
        out_dir = Path(args.output_folder).resolve()
    else:
        out_root = Path(args.out_dir).resolve()
        out_dir = out_root / date_folder if args.out_dir in (".", "./") else out_root
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = _SCRIPT_DIR / "assets" / f"ai_search_discovered_{tag}.xlsx"
    market_out = out_dir / f"MarketRateData_{tag}_AISearch.xlsx"

    try:
        if not args.skip_discover:
            from vertex_url_discovery import discover_all, write_discovery_report, write_url_params_xlsx

            print(f"[AI] Vertex 搜索发现链接中…（intent-mode={args.intent_mode}）")
            results = discover_all(sleep_sec=args.sleep, intent_mode=args.intent_mode)
            write_url_params_xlsx(results, AI_URL_XLSX)
            write_discovery_report(results, report_path)
            print(f"[AI] 已写入: {AI_URL_XLSX}")
            print(f"[AI] 发现报告: {report_path}")
            vertex_n = sum(1 for r in results if r.source == "vertex")
            print(f"[AI] 来源统计: vertex={vertex_n} fallback={len(results) - vertex_n}")

        if args.discover_only:
            if not args.skip_discover:
                return _sync_ai_json()
            return 0

        if _sync_ai_json() != 0:
            return 1
        return _run_fetch(market_out)
    except Exception as e:
        print(f"[AI] 失败: {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
