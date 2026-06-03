#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 assets/url_params_ai.xlsx 同步写入 assets/url_params_ai.json（仅 AI 流程使用）。"""

from __future__ import annotations

import json
import os
import sys

from url_config_loader import load_url_config

_AI_XLSX = "url_params_ai.xlsx"
_AI_JSON = "url_params_ai.json"


def main() -> int:
    """读取 assets/url_params_ai.xlsx，写入 assets/url_params_ai.json。"""
    base = os.path.dirname(os.path.abspath(__file__))
    xlsx_path = os.path.join(base, "assets", _AI_XLSX)
    json_path = os.path.join(base, "assets", _AI_JSON)

    cfg = load_url_config(xlsx_path)
    if not cfg:
        print(f"[SYNC-AI] {_AI_XLSX} 未读取到有效配置。", file=sys.stderr)
        return 1

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"[SYNC-AI] 已同步 {len(cfg)} 项: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
