#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""命名统一入口：从 MarketRateData 生成彩虹表。"""

import sys
import traceback

from generate_rainbow_from_bank import main


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ENTRY] generate_rainbow_from_market 失败：{e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        raise SystemExit(1)
