#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四家 AI 搜索（Vertex / Serper / Brave / Tavily）分别发现 URL 并生成 Market Excel。

每家独立：
  - url_params_ai_<provider>.xlsx
  - ai_search_discovered_<provider>_<tag>.xlsx
  - MarketRateData_<tag>_<Provider>.xlsx

不覆盖手动 url_params.xlsx；默认也不覆盖 assets/url_params_ai.xlsx（仅 Vertex 可选用 --also-write-portable-vertex）。
"""
from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path

_THIS = Path(__file__).resolve().parent
_PORTABLE = _THIS.parent / "RateStats_Portable"
_SRC = _PORTABLE / "src"
_ASSETS = _THIS.parent / "assets"

if str(_THIS) not in sys.path:
    sys.path.insert(0, str(_THIS))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from load_keys import ensure_keys_loaded  # noqa: E402
from project_paths import default_date_run_dir  # noqa: E402

PROVIDER_LABELS = {
    "vertex": "Vertex",
    "serper": "Serper",
    "brave": "Brave",
    "tavily": "Tavily",
}

DEFAULT_PROVIDERS = ("vertex", "serper", "brave", "tavily")


def _provider_configured(name: str) -> bool:
    """检查该 provider 是否已配置（Vertex 看 json 密钥，其余看环境变量 Key）。"""
    import os

    if name == "vertex":
        return bool(list(_ASSETS.glob("ratestatsearch-*.json")))
    keys = {
        "serper": "SERPER_API_KEY",
        "brave": "BRAVE_API_KEY",
        "tavily": "TAVILY_API_KEY",
    }
    return bool(os.environ.get(keys[name], "").strip())


def _discover_api_provider(
    name: str,
    sleep_sec: float,
    url_xlsx: Path,
    report_xlsx: Path,
    intent_mode: str | None,
    manual_fallback_xlsx: str | None,
):
    """Serper/Brave/Tavily：加载 search_client → discover_all → 写 xlsx 与报告。"""
    from _discovery_common import discover_all, write_discovery_report, write_url_params_xlsx

    provider_dir = _THIS / name
    sub = str(provider_dir)
    if sub not in sys.path:
        sys.path.insert(0, sub)
    if name == "serper":
        from serper_search_client import search_urls  # noqa: WPS433
    elif name == "brave":
        from brave_search_client import search_urls  # noqa: WPS433
    elif name == "tavily":
        from tavily_search_client import search_urls  # noqa: WPS433
    else:
        raise ValueError(name)

    results = discover_all(
        search_fn=search_urls,
        source_tag=name,
        sleep_sec=sleep_sec,
        intent_mode=intent_mode,
        manual_fallback_xlsx=manual_fallback_xlsx,
    )
    url_xlsx.parent.mkdir(parents=True, exist_ok=True)
    write_url_params_xlsx(results, url_xlsx)
    write_discovery_report(results, report_xlsx)
    return results


def sync_url_json(xlsx_path: Path, json_path: Path) -> int:
    """将某 provider 的 url_params_ai_<name>.xlsx 同步为同名 .json。"""
    import json

    from url_config_loader import load_url_config

    cfg = load_url_config(str(xlsx_path))
    if not cfg:
        print(f"[SYNC] 无法读取 {xlsx_path}", file=sys.stderr)
        return 1
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[SYNC] {len(cfg)} 项 → {json_path.name}")
    return 0


def fetch_market(url_xlsx: Path, market_out: Path) -> int:
    """用指定 AI 配置 xlsx 抓取并生成 MarketRateData Excel。"""
    from bank_all_promo_rates import main as fetch_main

    market_out.parent.mkdir(parents=True, exist_ok=True)
    print(f"[FETCH] {url_xlsx.name} → {market_out.name}")
    return int(fetch_main(["--url-config", str(url_xlsx), "--xlsx-out", str(market_out)]))


def run_one_provider(
    name: str,
    *,
    tag: str,
    out_dir: Path,
    assets_dir: Path,
    sleep_sec: float,
    skip_discover: bool,
    discover_only: bool,
    also_write_portable_vertex: bool,
    intent_mode: str = "relaxed",
    manual_fallback_xlsx: str | None = None,
) -> int:
    """单 provider 全流程：发现（可选）→ 同步 JSON → 抓取 Market。"""
    label = PROVIDER_LABELS[name]
    url_xlsx = assets_dir / f"url_params_ai_{name}.xlsx"
    report_xlsx = assets_dir / f"ai_search_discovered_{name}_{tag}.xlsx"
    market_out = out_dir / f"MarketRateData_{tag}_{label}.xlsx"
    json_path = assets_dir / f"url_params_ai_{name}.json"

    try:
        if not skip_discover:
            if name == "vertex":
                from vertex_url_discovery import discover_all, write_discovery_report, write_url_params_xlsx

                results = discover_all(
                    sleep_sec=sleep_sec,
                    intent_mode=intent_mode,
                    manual_fallback_xlsx=manual_fallback_xlsx,
                )
                write_url_params_xlsx(results, url_xlsx)
                write_discovery_report(results, report_xlsx)
                if also_write_portable_vertex:
                    portable_xlsx = _ASSETS / "url_params_ai.xlsx"
                    write_url_params_xlsx(results, portable_xlsx)
                    print(f"[vertex] 同时写入 {portable_xlsx}")
                n_v = sum(1 for r in results if r.source == "vertex")
                print(f"[vertex] vertex={n_v} fallback={len(results) - n_v}")
            else:
                results = _discover_api_provider(
                    name, sleep_sec, url_xlsx, report_xlsx, intent_mode, manual_fallback_xlsx
                )
                n_ok = sum(1 for r in results if r.source == name)
                print(f"[{name}] {name}={n_ok} fallback={len(results) - n_ok}")

        if discover_only:
            if not skip_discover:
                return sync_url_json(url_xlsx, json_path)
            return 0

        if not url_xlsx.is_file():
            print(f"[{name}] 缺少 {url_xlsx}，请先发现或去掉 --skip-discover", file=sys.stderr)
            return 1
        if sync_url_json(url_xlsx, json_path) != 0:
            return 1
        return fetch_market(url_xlsx, market_out)
    except Exception as e:
        print(f"[{name}] 失败: {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    """CLI：按 --providers 依次跑四家（或子集）发现 + 抓取。"""
    ap = argparse.ArgumentParser(description="四家 AI 搜索分别发现 URL 并抓取 Market")
    ap.add_argument(
        "--providers",
        default=",".join(DEFAULT_PROVIDERS),
        help="逗号分隔: vertex,serper,brave,tavily",
    )
    ap.add_argument("--skip-discover", action="store_true")
    ap.add_argument("--discover-only", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.4)
    ap.add_argument("--out-dir", default=None, help="Market 输出目录，默认项目 runs/YYYYMMDD/")
    ap.add_argument("--run-tag", default=None)
    ap.add_argument(
        "--also-write-portable-vertex",
        action="store_true",
        help="Vertex 发现结果同时写入 RateStats_Portable/assets/url_params_ai.xlsx",
    )
    ap.add_argument("--skip-missing-keys", action="store_true", help="跳过未配置 Key 的 API 提供商")
    ap.add_argument(
        "--intent-mode",
        choices=("relaxed", "strict"),
        default="relaxed",
        help="发现选链：relaxed=软加分+手动url回退(默认); strict=严格路径",
    )
    args = ap.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")
    ensure_keys_loaded(verbose=False)

    names = [p.strip().lower() for p in args.providers.split(",") if p.strip()]
    for n in names:
        if n not in PROVIDER_LABELS:
            print(f"未知 provider: {n}", file=sys.stderr)
            return 1

    from project_paths import ai_compare_config_dir, default_date_run_dir

    tag = args.run_tag or datetime.now().strftime("%Y%m%d_%H.%M")
    out_dir = Path(args.out_dir).resolve() if args.out_dir else default_date_run_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = ai_compare_config_dir(tag, run_dir=out_dir)

    print(f"输出目录: {out_dir}")
    print(f"配置/发现报告: {assets_dir}")
    print(f"Run tag: {tag}")
    print(f"Intent mode: {args.intent_mode}（fallback 优先 assets/url_params.xlsx）")

    manual_fb = str(_ASSETS / "url_params.xlsx")
    rc = 0
    for name in names:
        if name != "vertex" and not _provider_configured(name):
            msg = f"[{name}] 未配置 API Key，跳过"
            if args.skip_missing_keys:
                print(msg)
                continue
            print(msg, file=sys.stderr)
            rc = 1
            continue
        if run_one_provider(
            name,
            tag=tag,
            out_dir=out_dir,
            assets_dir=assets_dir,
            sleep_sec=args.sleep,
            skip_discover=args.skip_discover,
            discover_only=args.discover_only,
            also_write_portable_vertex=args.also_write_portable_vertex,
            intent_mode=args.intent_mode,
            manual_fallback_xlsx=manual_fb,
        ) != 0:
            rc = 1

    if rc == 0:
        print("\n[完成] 各 provider 输出:")
        for name in names:
            label = PROVIDER_LABELS[name]
            print(f"  - {assets_dir / f'url_params_ai_{name}.xlsx'}")
            if not args.discover_only:
                print(f"  - {out_dir / f'MarketRateData_{tag}_{label}.xlsx'}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
