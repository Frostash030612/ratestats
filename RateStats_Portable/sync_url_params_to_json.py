#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 assets/url_params.xlsx 同步写入 assets/url_params.json。"""

from __future__ import annotations

import json
import os
import sys

from url_config_loader import load_url_config


def main() -> int:
    base = os.path.dirname(os.path.abspath(__file__))
    xlsx_path = os.path.join(base, "assets", "url_params.xlsx")
    json_path = os.path.join(base, "assets", "url_params.json")

    cfg = load_url_config(xlsx_path)
    if not cfg:
        print("[SYNC] url_params.xlsx 未读取到有效配置，已跳过同步。", file=sys.stderr)
        return 1

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"[SYNC] 已同步 {len(cfg)} 项: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
