#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发现报告搜索路径（含 runs/ 下历史批次）。"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from _portable import RUNS_ROOT

DISCOVERY_GLOBS = (
    "ai_search_discovered_*.xlsx",
    "ai_search_discovered_ml_*.xlsx",
)


def default_discovery_dirs() -> list[Path]:
    return [RUNS_ROOT]


def iter_discovery_reports(search_dirs: list[Path] | None = None) -> Iterator[Path]:
    """在 runs/** 下递归查找发现报告。"""
    dirs = search_dirs or default_discovery_dirs()
    seen: set[str] = set()
    for d in dirs:
        if not d.is_dir():
            continue
        for pattern in DISCOVERY_GLOBS:
            for p in sorted(d.rglob(pattern)):
                key = str(p.resolve())
                if key not in seen:
                    seen.add(key)
                    yield p
