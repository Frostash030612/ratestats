#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 url_params_ai.xlsx 同步为同目录 url_params_ai.json（仅 AI 流程使用）。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from url_config_loader import load_url_config

_SCRIPT_DIR = Path(__file__).resolve().parent


def sync_url_params_ai(xlsx_path: Path) -> int:
    """读取 xlsx，写入同目录 url_params_ai.json。"""
    xlsx_path = xlsx_path.resolve()
    json_path = xlsx_path.with_name("url_params_ai.json")
    cfg = load_url_config(str(xlsx_path))
    if not cfg:
        print(f"[SYNC-AI] {xlsx_path.name} 未读取到有效配置。", file=sys.stderr)
        return 1
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[SYNC-AI] 已同步 {len(cfg)} 项: {json_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="url_params_ai.xlsx → url_params_ai.json")
    ap.add_argument(
        "--xlsx",
        default=None,
        help="xlsx 路径（默认 runs 下最新 url_params_ai.xlsx，否则 assets 遗留）",
    )
    args = ap.parse_args(argv)

    if args.xlsx:
        xlsx_path = Path(args.xlsx)
    else:
        from project_paths import ASSETS_DIR, find_latest_url_params_ai

        xlsx_path = find_latest_url_params_ai() or (ASSETS_DIR / "url_params_ai.xlsx")

    if not xlsx_path.is_file():
        print(f"[SYNC-AI] 缺少 {xlsx_path}", file=sys.stderr)
        return 1
    return sync_url_params_ai(xlsx_path)


if __name__ == "__main__":
    raise SystemExit(main())
