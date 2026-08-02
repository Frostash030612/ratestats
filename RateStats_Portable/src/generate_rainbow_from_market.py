#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 MarketRateData 生成彩虹表（三 sheet 合一，新版式）。"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path

from create_rainbow_workbook import (
    build_rainbow_workbook,
    rainbow_zh_filename,
    run_tag_from_market_path,
)
from generate_rainbow_from_bank import resolve_latest_source


def _dedupe_output_path(path: Path) -> Path:
    if not path.exists():
        return path
    base = path.with_suffix("")
    ext = path.suffix
    i = 1
    while True:
        candidate = Path(f"{base}_{i}{ext}")
        if not candidate.exists():
            return candidate
        i += 1


def main() -> None:
    ap = argparse.ArgumentParser(description="从 MarketRateData 生成彩虹表工作簿")
    ap.add_argument("--source", default=None, help="MarketRateData Excel 路径")
    ap.add_argument("--out", default=None, help="输出 .xlsx 路径")
    ap.add_argument(
        "--out-dir-zh",
        default=None,
        metavar="DIR",
        help="输出目录；与 --out-tag 同时使用时写入中文名彩虹表",
    )
    ap.add_argument(
        "--out-tag",
        default=None,
        metavar="TAG",
        help="与 --out-dir-zh 搭配，例如 20260709_15.03",
    )
    args = ap.parse_args()

    work_dir = os.path.dirname(os.path.abspath(__file__))
    source_path = Path(args.source) if args.source else Path(resolve_latest_source(work_dir))
    if not source_path.is_absolute():
        source_path = Path(work_dir) / source_path
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    if args.out_dir_zh and args.out_tag:
        if args.out:
            ap.error("不要同时使用 --out 与 --out-dir-zh/--out-tag")
        out_path = Path(args.out_dir_zh).resolve() / rainbow_zh_filename(args.out_tag)
    elif args.out_dir_zh or args.out_tag:
        ap.error("--out-dir-zh 与 --out-tag 须同时提供")
    elif args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = Path(work_dir) / out_path
    else:
        run_tag = run_tag_from_market_path(source_path)
        out_path = source_path.parent / rainbow_zh_filename(run_tag)

    out_path = _dedupe_output_path(out_path)

    result = build_rainbow_workbook(source_path, out_path)
    print(f"Generated: {result['output']}")
    print(f"Source:    {result['source']}")
    promo = result["promo_rows"]
    board = result["board_rows"]
    print("SGD Promo rows:", ", ".join(f"{k}={v}" for k, v in promo.items()))
    print("SGD Board rows:", ", ".join(f"{k}={v}" for k, v in board.items()))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ENTRY] generate_rainbow_from_market 失败：{e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        raise SystemExit(1)
