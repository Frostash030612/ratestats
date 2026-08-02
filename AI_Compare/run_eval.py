#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跑各 AI provider，对比效果，输出 results/ai_provider_compare_*.xlsx。

用法：
  python run_eval.py --auto              # 自动检测所有已配置 Key 的 provider
  python run_eval.py --list              # 列出各 provider 是否可用
  python run_eval.py --providers vertex,serper,brave
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent

if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from load_keys import ensure_keys_loaded

ensure_keys_loaded()

from eval_metrics import hit_at_k, mrr, normalize_url, rank_in_topn, same_host_rank
from ground_truth import load_gold, resolve_gold_path
from providers.base import ProviderResult
from providers.registry import (
    ALL_PROVIDER_NAMES,
    detect_available,
    env_hint,
    instantiate,
    PROVIDER_CLASSES,
)
from queries import QUERY_BY_DEST


def _build_providers(names: list[str], *, skip_unavailable: bool = True):
    """按名称实例化 provider 对象，跳过未配置或不可用的。"""
    out = []
    for name in names:
        if name not in PROVIDER_CLASSES:
            print(f"[WARN] 未知 provider: {name}", file=sys.stderr)
            continue
        prov = instantiate(name)
        if prov is None:
            continue
        if skip_unavailable and not prov.available():
            print(
                f"[WARN] {name} 未配置（需要 {env_hint(name)}），已跳过。",
                file=sys.stderr,
            )
            continue
        out.append(prov)
    return out


def _effective_sleep(provider_names: list[str], sleep_sec: float) -> float:
    """Brave 免费档 1 req/s，自动抬高间隔。"""
    if "brave" in provider_names and sleep_sec < 1.1:
        return 1.1
    return sleep_sec


def _cache_raw(raw_dir: Path, provider: str, dest: str, payload: ProviderResult) -> None:
    """将单次搜索原始结果缓存到 raw_cache/<ts>/<provider>/<dest>.json。"""
    sub = raw_dir / provider
    sub.mkdir(parents=True, exist_ok=True)
    out = {
        "urls": payload.urls,
        "latency_ms": payload.latency_ms,
        "error": payload.error,
        "raw": payload.raw,
    }
    with open(sub / f"{dest}.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


def run(
    providers: list[str],
    topn: int,
    sleep_sec: float,
    limit: int | None = None,
    *,
    gold_path: Path | None = None,
) -> Path:
    """对各 dest 调用各 provider 搜索，与黄金 URL 比 Hit@K/MRR，写对比 Excel。"""
    provider_objs = _build_providers(providers, skip_unavailable=True)
    if not provider_objs:
        raise RuntimeError(
            "没有可用的 provider。请先配置 Key，运行: python run_eval.py --list\n"
            "申请教程见 SETUP_KEYS.md"
        )

    active_names = [p.name for p in provider_objs]
    sleep_sec = _effective_sleep(active_names, sleep_sec)
    print(f"[INFO] 参与对比: {', '.join(active_names)}  请求间隔={sleep_sec}s")

    gp = gold_path or resolve_gold_path(prefer_snapshot=True)
    gold = load_gold(gp)
    print(f"[INFO] 黄金答案: {gp} ({len(gold)} 条 dest)")
    ts = datetime.now().strftime("%Y%m%d_%H.%M")
    from project_paths import get_runs_root, parse_run_date_tag

    date_tag = parse_run_date_tag(ts) or datetime.now().strftime("%Y%m%d")
    eval_root = get_runs_root() / "ai_eval" / date_tag
    results_dir = eval_root
    raw_dir = get_runs_root() / "ai_eval_raw_cache" / date_tag / ts
    results_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    detail_rows: list[dict] = []
    summary: dict[str, dict] = {
        p.name: {
            "hit1": [],
            "hit3": [],
            "hit5": [],
            "mrr": [],
            "same_host": [],
            "latency": [],
            "errors": 0,
            "miss": 0,
        }
        for p in provider_objs
    }

    keys = sorted(QUERY_BY_DEST.keys())
    if limit and limit > 0:
        keys = keys[:limit]
    total = len(keys)
    for idx, dest in enumerate(keys, 1):
        query = QUERY_BY_DEST[dest]
        gold_url = gold.get(dest, "")
        row: dict = {"dest": dest, "query": query, "gold": gold_url}

        for prov in provider_objs:
            res = prov.search(query, page_size=topn)
            _cache_raw(raw_dir, prov.name, dest, res)
            urls = res.urls[:topn]
            rank = rank_in_topn(gold_url, urls) if gold_url else 0
            sh_rank = same_host_rank(gold_url, urls) if gold_url else 0

            row[f"{prov.name}_top1"] = urls[0] if urls else ""
            row[f"{prov.name}_topN"] = " | ".join(urls)
            row[f"{prov.name}_hit@1"] = hit_at_k(rank, 1)
            row[f"{prov.name}_hit@3"] = hit_at_k(rank, 3)
            row[f"{prov.name}_hit@5"] = hit_at_k(rank, 5)
            row[f"{prov.name}_rank"] = rank
            row[f"{prov.name}_same_host_rank"] = sh_rank
            row[f"{prov.name}_mrr"] = round(mrr(rank), 4)
            row[f"{prov.name}_latency_ms"] = res.latency_ms
            row[f"{prov.name}_error"] = res.error

            s = summary[prov.name]
            s["hit1"].append(hit_at_k(rank, 1))
            s["hit3"].append(hit_at_k(rank, 3))
            s["hit5"].append(hit_at_k(rank, 5))
            s["mrr"].append(mrr(rank))
            s["same_host"].append(1 if sh_rank > 0 else 0)
            s["latency"].append(res.latency_ms)
            if res.error:
                s["errors"] += 1
            if rank == 0 and not res.error:
                s["miss"] += 1
            time.sleep(sleep_sec)

        detail_rows.append(row)
        print(f"[{idx}/{total}] {dest}")

    df_detail = pd.DataFrame(detail_rows)

    summary_rows = []
    for name, s in summary.items():
        n = max(len(s["hit1"]), 1)
        summary_rows.append(
            {
                "provider": name,
                "samples": n,
                "hit@1": round(sum(s["hit1"]) / n, 4),
                "hit@3": round(sum(s["hit3"]) / n, 4),
                "hit@5": round(sum(s["hit5"]) / n, 4),
                "MRR": round(sum(s["mrr"]) / n, 4),
                "same_host_rate": round(sum(s["same_host"]) / n, 4),
                "avg_latency_ms": int(statistics.mean(s["latency"])) if s["latency"] else 0,
                "errors": s["errors"],
                "miss_top10": s["miss"],
            }
        )
    df_summary = pd.DataFrame(summary_rows)

    disagree_rows = []
    for row in detail_rows:
        gold_n = normalize_url(row.get("gold", ""))
        if not gold_n:
            continue
        for prov in provider_objs:
            top1 = normalize_url(row.get(f"{prov.name}_top1", ""))
            if top1 and top1 != gold_n:
                disagree_rows.append(
                    {
                        "dest": row["dest"],
                        "provider": prov.name,
                        "gold": row["gold"],
                        "provider_top1": row[f"{prov.name}_top1"],
                        "provider_rank_in_topN": row[f"{prov.name}_rank"],
                        "provider_topN": row[f"{prov.name}_topN"],
                    }
                )
    df_disagree = pd.DataFrame(disagree_rows)

    out_path = results_dir / f"ai_provider_compare_{ts}.xlsx"
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df_summary.to_excel(writer, index=False, sheet_name="summary")
        df_detail.to_excel(writer, index=False, sheet_name="detail")
        if not df_disagree.empty:
            df_disagree.to_excel(writer, index=False, sheet_name="disagree")
    print(f"\n[OK] 报告已生成: {out_path}")
    print(f"[OK] 原始缓存: {raw_dir}")
    return out_path


def cmd_list() -> int:
    """打印各 provider 是否已配置 API Key。"""
    print("Provider 配置状态（[OK]=可用  [--]=未配置）：\n")
    for name in ALL_PROVIDER_NAMES:
        prov = instantiate(name)
        ok = prov is not None and prov.available()
        mark = "[OK]" if ok else "[--]"
        print(f"  {mark} {name:8}  {env_hint(name)}")
    print("\n配置教程: SETUP_KEYS.md")
    print("自动对比: python run_eval.py --auto")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI：--list / --auto / --providers 触发 URL 命中率评测。"""
    p = argparse.ArgumentParser(description="AI provider compare")
    p.add_argument(
        "--auto",
        action="store_true",
        help="自动检测并对比所有已配置 Key 的 provider（推荐）",
    )
    p.add_argument(
        "--list",
        action="store_true",
        help="列出各 provider 是否已配置，不跑评测",
    )
    p.add_argument(
        "--providers",
        default="",
        help="逗号分隔，例如 vertex,serper,brave（与 --auto 二选一；默认 --auto 行为）",
    )
    p.add_argument("--topn", type=int, default=10, help="每次查询取前 N 条（默认 10）")
    p.add_argument("--sleep", type=float, default=0.3, help="请求间隔秒数（默认 0.3；含 Brave 时至少 1.1）")
    p.add_argument("--limit", type=int, default=None, help="仅评测前 N 个 key（烟测用）")
    p.add_argument(
        "--gold",
        default="auto",
        help="黄金答案：auto=最新 url_YYYYMMDD.xlsx；或指定 xlsx/json 路径；legacy=assets/url_params.json",
    )
    args = p.parse_args(argv)

    if args.list:
        return cmd_list()

    if args.auto or not args.providers.strip():
        print("[INFO] 自动检测已配置的 provider：")
        names = detect_available(verbose=True)
        if not names:
            print("\n[ERROR] 未检测到任何 provider。请先按 SETUP_KEYS.md 配置 Key。", file=sys.stderr)
            return 1
        print()
    else:
        names = [x.strip() for x in args.providers.split(",") if x.strip()]

    if str(args.gold).strip().lower() == "legacy":
        gold_path = Path(__file__).resolve().parent.parent / "RateStats_Portable" / "assets" / "url_params.json"
    elif str(args.gold).strip().lower() in ("", "auto"):
        gold_path = None
    else:
        gold_path = Path(args.gold)

    try:
        run(names, args.topn, args.sleep, limit=args.limit, gold_path=gold_path)
        return 0
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
