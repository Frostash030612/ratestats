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

from project_paths import (  # noqa: E402
    ai_discovery_report_path,
    default_date_run_dir,
    find_latest_url_params_ai,
    url_params_ai_paths,
)


def _resolve_ai_url_xlsx(out_dir: Path) -> Path:
    local, _ = url_params_ai_paths(out_dir)
    if local.is_file():
        return local
    latest = find_latest_url_params_ai()
    if latest and latest.is_file():
        return latest
    return local


def _sync_ai_json(xlsx_path: Path) -> int:
    from sync_url_params_ai_to_json import sync_url_params_ai

    return int(sync_url_params_ai(xlsx_path))


def _run_fetch(market_out: Path, url_xlsx: Path) -> int:
    from bank_all_promo_rates import main as fetch_main

    if not url_xlsx.is_file():
        print(f"[AI] 缺少 {url_xlsx}，请先运行发现链接（勿使用 url_params.xlsx）", file=sys.stderr)
        return 1

    argv = ["--url-config", str(url_xlsx), "--xlsx-out", str(market_out)]
    print(f"[AI] 使用配置: {url_xlsx}")
    print(f"[AI] 开始抓取并生成: {market_out}")
    return int(fetch_main(argv))


def main(argv: list[str] | None = None) -> int:
    """CLI：可选 Vertex 发现 → 同步 JSON → 抓取 → MarketRateData_*_AISearch.xlsx。"""
    p = argparse.ArgumentParser(
        description="AI 搜索链接 + 生成 MarketRateData_*_AISearch（url_params_ai 写入 runs 批次目录）"
    )
    p.add_argument(
        "--skip-discover",
        action="store_true",
        help="跳过 Vertex 搜索，沿用 runs 批次或最新 url_params_ai.xlsx",
    )
    p.add_argument("--discover-only", action="store_true", help="仅搜索并写入配置/发现报告，不抓取")
    p.add_argument("--out-dir", default=None, help="输出根目录（默认项目 runs/；在其下创建 YYYYMMDD 子目录）")
    p.add_argument("--output-folder", default=None, help="直接指定输出文件夹（与 03/06 批处理同一天目录时用）")
    p.add_argument("--run-tag", default=None, help="输出文件名时间标签，格式 YYYYMMDD_HH.mm")
    p.add_argument("--sleep", type=float, default=0.4, help="每次 Vertex 搜索间隔秒数")
    p.add_argument(
        "--intent-mode",
        choices=("relaxed", "strict"),
        default="strict",
        help="发现选链模式：strict=严格对齐路径(默认); relaxed=优先适应改版",
    )
    args = p.parse_args(argv)

    tag = args.run_tag or datetime.now().strftime("%Y%m%d_%H.%M")
    date_folder = datetime.now().strftime("%Y%m%d")
    if args.output_folder:
        out_dir = Path(args.output_folder).resolve()
    elif args.out_dir:
        out_root = Path(args.out_dir).resolve()
        legacy_cwd = {".", "./", str(_SCRIPT_DIR), str(_SCRIPT_DIR.resolve())}
        out_dir = (
            out_root / date_folder
            if str(out_root) in legacy_cwd or args.out_dir in (".", "./")
            else out_root
        )
    else:
        out_dir = default_date_run_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[AI] 输出目录: {out_dir}")

    ai_url_xlsx, _ = url_params_ai_paths(out_dir)
    report_path = ai_discovery_report_path(tag, run_dir=out_dir)
    ai_suffix = "_AISearch" if "_AISearch" not in tag else ""
    market_out = out_dir / f"MarketRateData_{tag}{ai_suffix}.xlsx"

    try:
        if not args.skip_discover:
            from vertex_url_discovery import discover_all, write_discovery_report, write_url_params_xlsx

            print(f"[AI] Vertex 搜索发现链接中…（intent-mode={args.intent_mode}）")
            results = discover_all(sleep_sec=args.sleep, intent_mode=args.intent_mode)
            write_url_params_xlsx(results, ai_url_xlsx)
            write_discovery_report(results, report_path)
            print(f"[AI] 已写入: {ai_url_xlsx}")
            print(f"[AI] 发现报告: {report_path}")
            vertex_n = sum(1 for r in results if r.source == "vertex")
            print(f"[AI] 来源统计: vertex={vertex_n} fallback={len(results) - vertex_n}")
        else:
            ai_url_xlsx = _resolve_ai_url_xlsx(out_dir)

        if args.discover_only:
            if not args.skip_discover:
                return _sync_ai_json(ai_url_xlsx)
            return 0

        if _sync_ai_json(ai_url_xlsx) != 0:
            return 1
        return _run_fetch(market_out, ai_url_xlsx)
    except Exception as e:
        print(f"[AI] 失败: {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
