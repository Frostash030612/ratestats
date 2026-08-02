#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""命名统一入口：生成 MarketRateData_YYYYMMDD_HH.mm.xlsx。"""

import sys
import traceback

from bank_all_promo_rates import main


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as e:
        print(f"[ENTRY] market_rate_data_generator 失败：{e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        raise SystemExit(1)
