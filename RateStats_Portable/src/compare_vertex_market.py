#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比手动 Market 与 Vertex AISearch（含三主表 + 挂牌_*），供 06 一键批处理调用。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from project_paths import PROJECT_ROOT

_AI_COMPARE = PROJECT_ROOT / "AI_Compare"
if str(_AI_COMPARE) not in sys.path:
    sys.path.insert(0, str(_AI_COMPARE))

from compare_market_data import run_compare  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="手动 vs Vertex AISearch Market 对比")
    ap.add_argument("--manual", required=True, help="手动 MarketRateData xlsx")
    ap.add_argument("--ai", required=True, help="Vertex AISearch xlsx")
    ap.add_argument("--out-dir", required=True, help="对比报告输出目录")
    ap.add_argument(
        "--run-tag",
        default=None,
        help="输出文件名标签；默认取 ai 文件名中的 RUN_TAG 或当前时间",
    )
    ap.add_argument("--tol", type=float, default=0.011)
    args = ap.parse_args(argv)

    manual = Path(args.manual).resolve()
    ai = Path(args.ai).resolve()
    out_dir = Path(args.out_dir).resolve()
    if not manual.is_file():
        print(f"[COMPARE] 缺少手动表: {manual}", file=sys.stderr)
        return 1
    if not ai.is_file():
        print(f"[COMPARE] 缺少 AI 表: {ai}", file=sys.stderr)
        return 1

    tag = args.run_tag
    if not tag:
        stem = ai.stem
        if "_AISearch" in stem:
            tag = stem.replace("MarketRateData_", "").replace("_AISearch", "")
        else:
            from datetime import datetime

            tag = datetime.now().strftime("%Y%m%d_%H.%M")

    before = {p.resolve() for p in out_dir.glob("market_data_compare_*.xlsx")}
    run_compare(manual, ai, out_dir, tol=args.tol)
    after = [p.resolve() for p in out_dir.glob("market_data_compare_*.xlsx")]
    new_files = [p for p in after if p not in before]
    if not new_files:
        new_files = sorted(after, key=lambda p: p.stat().st_mtime)[-1:]
    src = max(new_files, key=lambda p: p.stat().st_mtime)
    dest = out_dir / f"market_data_compare_{tag}_Vertex.xlsx"
    if src != dest.resolve():
        dest.unlink(missing_ok=True)
        src.replace(dest)
    print(f"[COMPARE] 已写入: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
