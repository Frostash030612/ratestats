#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比手动 Market 的 url 快照 vs AI 流程的 url_params_ai.xlsx。"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

_THIS = Path(__file__).resolve().parent
_PORTABLE = _THIS.parent / "RateStats_Portable"
if str(_PORTABLE) not in sys.path:
    sys.path.insert(0, str(_PORTABLE))

from url_config_loader import load_url_config  # noqa: E402
from url_key_aliases import URL_KEY_ALIASES  # noqa: E402
from eval_metrics import normalize_url, same_host_rank  # noqa: E402


def _same_host(a: str, b: str) -> bool:
    """两 URL 是否同域名（不要求路径相同）。"""
    return same_host_rank(a, [b]) > 0 if a and b else False


def _load_by_dest(path: Path) -> dict[str, str]:
    """加载 xlsx/json 为 dest→url 字典。"""
    return load_url_config(str(path))


def _friendly_for_dest(dest: str) -> str:
    """dest 转 Excel 友好列名 key。"""
    for k, d in URL_KEY_ALIASES.items():
        if d == dest:
            return k
    return dest


def run(manual_xlsx: Path, ai_xlsx: Path, out_dir: Path) -> Path:
    """逐 dest 对比手动快照与 AI 配置 URL，写 manual_vs_ai_urls_*.xlsx。"""
    manual = _load_by_dest(manual_xlsx)
    ai = _load_by_dest(ai_xlsx)
    all_dests = sorted(set(manual) | set(ai))

    rows = []
    same_url = same_host_n = diff = only_m = only_a = 0
    for dest in all_dests:
        mu = manual.get(dest, "")
        au = ai.get(dest, "")
        mn, an = normalize_url(mu), normalize_url(au)
        if mn and an and mn == an:
            match = "exact"
            same_url += 1
        elif mu and au and _same_host(mu, au):
            match = "same_host"
            same_host_n += 1
        elif mu and au:
            match = "diff"
            diff += 1
        elif mu:
            match = "manual_only"
            only_m += 1
        elif au:
            match = "ai_only"
            only_a += 1
        else:
            match = "empty"
        rows.append(
            {
                "dest": dest,
                "key": _friendly_for_dest(dest),
                "manual_url": mu,
                "ai_url": au,
                "match": match,
            }
        )

    df = pd.DataFrame(rows)
    ts = datetime.now().strftime("%Y%m%d_%H.%M")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"manual_vs_ai_urls_{ts}.xlsx"
    summary = pd.DataFrame(
        [
            {
                "manual_file": str(manual_xlsx),
                "ai_file": str(ai_xlsx),
                "dest_count": len(all_dests),
                "exact_match": same_url,
                "same_host": same_host_n,
                "diff": diff,
                "manual_only": only_m,
                "ai_only": only_a,
            }
        ]
    )
    with pd.ExcelWriter(out_path, engine="openpyxl") as w:
        summary.to_excel(w, index=False, sheet_name="summary")
        df.to_excel(w, index=False, sheet_name="detail")
    print(f"[OK] {out_path}")
    print(
        f"     exact={same_url} same_host={same_host_n} diff={diff} "
        f"manual_only={only_m} ai_only={only_a}"
    )
    return out_path


def main() -> int:
    """CLI：--manual 与 --ai 两份 URL 配置表对比。"""
    ap = argparse.ArgumentParser()
    ap.add_argument("--manual", required=True, help="url_YYYYMMDD.xlsx（手动 Market 快照）")
    ap.add_argument("--ai", default=None, help="url_params_ai.xlsx，默认 assets/url_params_ai.xlsx")
    ap.add_argument("--out-dir", default=None, help="输出目录，默认 AI_Compare/results")
    args = ap.parse_args()
    manual = Path(args.manual)
    ai = Path(args.ai) if args.ai else _PORTABLE / "assets" / "url_params_ai.xlsx"
    out_dir = Path(args.out_dir) if args.out_dir else _THIS / "results"
    if not manual.is_file():
        print(f"[ERROR] 不存在: {manual}", file=sys.stderr)
        return 1
    if not ai.is_file():
        print(f"[ERROR] 不存在: {ai}", file=sys.stderr)
        return 1
    run(manual, ai, out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
