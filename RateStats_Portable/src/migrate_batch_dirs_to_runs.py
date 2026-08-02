#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 Portable 内遗留的 2026xxxx / sameday_* / manual_vs_ai_* 目录迁入 runs/。"""
from __future__ import annotations

import shutil
import sys

from project_paths import get_runs_root, portable_legacy_batch_dirs


def main() -> int:
    legacy = portable_legacy_batch_dirs()
    if not legacy:
        print("[migrate] Portable 内无待迁移批次目录。")
        return 0

    root = get_runs_root()
    print(f"[migrate] 目标: {root}")
    for src in legacy:
        dest = root / src.name
        if dest.exists():
            print(f"[migrate] 跳过（目标已存在）: {src.name}")
            continue
        print(f"[migrate] {src} -> {dest}")
        shutil.move(str(src), str(dest))
    print("[migrate] 完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
