#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将手动 url_params.xlsx 合并进 AI 专用 url_params_ai.xlsx。

典型场景：Vertex 发现的链接能跑通，但少数银行 URL 与人工维护不一致，导致
Market 行数变少。本脚本在保留 AI 发现结果的同时，用手动配置覆盖同 dest 的 URL。

用法（在 RateStats_Portable 目录）：
  python seed_url_params_ai_from_manual.py
  python seed_url_params_ai_from_manual.py --discover-first
  python seed_url_params_ai_from_manual.py --mode replace
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from url_config_loader import DEFAULT_URL_CONFIG, load_url_config
from url_key_aliases import URL_PARAM_DEST_KEYS
from url_fallback_resolver import build_fallback_map

_SCRIPT_DIR = Path(__file__).resolve().parent
from project_paths import ASSETS_DIR, default_date_run_dir, url_params_ai_paths

_MANUAL_XLSX = ASSETS_DIR / "url_params.xlsx"
_AI_XLSX = default_date_run_dir() / "url_params_ai.xlsx"


def _canonical_friendly_keys() -> dict[str, str]:
    from vertex_url_discovery import _canonical_friendly_keys as fn

    return fn()


def _dest_urls_from_ai_xlsx(path: Path) -> dict[str, str]:
    return load_url_config(str(path)) if path.is_file() else {}


def _merge_dest_maps(
    *,
    manual: dict[str, str],
    ai: dict[str, str],
    code_defaults: dict[str, str],
    mode: str,
) -> tuple[dict[str, str], list[str]]:
    """返回 dest→url 及变更说明。"""
    out: dict[str, str] = {}
    notes: list[str] = []
    for dest in sorted(URL_PARAM_DEST_KEYS):
        m = (manual.get(dest) or "").strip()
        a = (ai.get(dest) or "").strip()
        d = (code_defaults.get(dest) or "").strip()

        if mode == "replace":
            url = m or a or d
            src = "manual" if m else ("ai" if a else "default")
        elif mode == "fill_gaps":
            url = a or m or d
            src = "ai" if a else ("manual" if m else "default")
        else:  # overlay — 手动优先
            url = m or a or d
            src = "manual" if m else ("ai" if a else "default")

        if url:
            out[dest] = url
        if m and a and m != a and mode == "overlay":
            notes.append(f"{dest}: manual 覆盖 AI")
        elif m and not a:
            notes.append(f"{dest}: 从手动补入")
    return out, notes


def _write_ai_xlsx(dest_map: dict[str, str], path: Path) -> int:
    dest_to_key = _canonical_friendly_keys()
    rows = []
    for dest in sorted(URL_PARAM_DEST_KEYS):
        url = (dest_map.get(dest) or "").strip()
        if not url:
            continue
        rows.append({"key": dest_to_key.get(dest, dest), "url": url})
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.xlsx")
    pd.DataFrame(rows).to_excel(tmp, index=False)
    tmp.replace(path)
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="将手动 URL 配置合并进 url_params_ai.xlsx")
    p.add_argument(
        "--manual",
        default=str(_MANUAL_XLSX),
        help="手动配置 xlsx（默认 assets/url_params.xlsx）",
    )
    p.add_argument(
        "--ai-out",
        default=str(_AI_XLSX),
        help="输出 AI 配置 xlsx（默认 assets/url_params_ai.xlsx）",
    )
    p.add_argument(
        "--mode",
        choices=("overlay", "replace", "fill_gaps"),
        default="overlay",
        help="overlay=手动优先覆盖同 dest；replace=几乎全用手动；fill_gaps=仅补 AI 空缺",
    )
    p.add_argument(
        "--discover-first",
        action="store_true",
        help="先跑 Vertex 发现，再按 --mode 合并手动配置",
    )
    p.add_argument("--sleep", type=float, default=0.4, help="Vertex 搜索间隔秒数")
    p.add_argument(
        "--intent-mode",
        choices=("relaxed", "strict"),
        default="relaxed",
    )
    p.add_argument(
        "--no-sync-json",
        action="store_true",
        help="不写 url_params_ai.json",
    )
    args = p.parse_args(argv)

    manual_path = Path(args.manual).resolve()
    ai_out = Path(args.ai_out).resolve()
    if not manual_path.is_file():
        print(f"[SEED] 缺少手动配置: {manual_path}", file=sys.stderr)
        return 1

    manual = load_url_config(str(manual_path))
    ai: dict[str, str] = {}
    if args.discover_first:
        from project_paths import ai_discovery_report_path, default_date_run_dir
        from vertex_url_discovery import discover_all, write_discovery_report

        tag = datetime.now().strftime("%Y%m%d_%H.%M")
        report = ai_discovery_report_path(tag, run_dir=default_date_run_dir())
        print(f"[SEED] Vertex 发现中… (intent-mode={args.intent_mode})")
        results = discover_all(
            sleep_sec=args.sleep,
            intent_mode=args.intent_mode,
            manual_fallback_xlsx=str(manual_path),
        )
        ai = {r.dest: r.url for r in results if r.url}
        write_discovery_report(results, report)
        print(f"[SEED] 发现报告: {report}")
        vertex_n = sum(1 for r in results if r.source == "vertex")
        print(f"[SEED] 发现统计: vertex={vertex_n} fallback={len(results) - vertex_n}")
    else:
        ai = _dest_urls_from_ai_xlsx(ai_out)

    code_defaults = build_fallback_map(None)
    merged, notes = _merge_dest_maps(
        manual=manual,
        ai=ai,
        code_defaults=code_defaults,
        mode=args.mode,
    )
    n = _write_ai_xlsx(merged, ai_out)
    print(f"[SEED] 已写入 {n} 项 → {ai_out} (mode={args.mode})")
    for line in notes[:20]:
        print(f"  · {line}")
    if len(notes) > 20:
        print(f"  · … 另有 {len(notes) - 20} 项")

    if not args.no_sync_json:
        from sync_url_params_ai_to_json import main as sync_main

        return int(sync_main())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
