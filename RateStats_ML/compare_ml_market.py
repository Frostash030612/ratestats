#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比手动 Market vs ML 发现后抓取的 Market。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _portable import AI_COMPARE_DIR, OUTPUT_DIR

if str(AI_COMPARE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_COMPARE_DIR))

from compare_market_data import run_compare  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manual", required=True)
    ap.add_argument("--ai", required=True)
    ap.add_argument("--out-dir", default=str(OUTPUT_DIR))
    args = ap.parse_args()
    out = Path(args.out_dir)
    run_compare(Path(args.manual), Path(args.ai), out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
