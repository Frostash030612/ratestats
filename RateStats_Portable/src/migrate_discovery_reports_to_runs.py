#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 assets / ML output 等处的 ai_search_discovered*.xlsx 迁入 runs/YYYYMMDD/。"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from project_paths import ASSETS_DIR, get_runs_root

_SCRIPT_DIR = Path(__file__).resolve().parent
_ML_OUTPUT = _SCRIPT_DIR.parent / "RateStats_ML" / "output"

_DISCOVERY_GLOBS = (
    "ai_search_discovered_*.xlsx",
    "ai_search_discovered_ml_*.xlsx",
)
_DATE_RE = re.compile(r"(20\d{6})")
# 无日期后缀的历史实验文件 → 批次日期
_ORPHAN_DATE_HINTS: tuple[tuple[str, str], ...] = (
    ("ocbcfix2", "20260603"),
    ("ocbcfix", "20260603"),
)


def parse_discovery_report_date(path: Path) -> str | None:
    """从文件名或父目录名解析 YYYYMMDD。"""
    for part in (path.stem, path.parent.name):
        m = _DATE_RE.search(part)
        if m:
            return m.group(1)
    stem_lower = path.stem.lower()
    for hint, date_tag in _ORPHAN_DATE_HINTS:
        if hint in stem_lower:
            return date_tag
    return None


def default_source_dirs() -> list[Path]:
    return [
        ASSETS_DIR,
        _ML_OUTPUT,
    ]


def iter_discovery_files(source_dirs: list[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for d in source_dirs:
        if not d.is_dir():
            continue
        for pattern in _DISCOVERY_GLOBS:
            for p in sorted(d.rglob(pattern)):
                key = str(p.resolve())
                if key in seen:
                    continue
                seen.add(key)
                out.append(p)
    return out


def target_path(src: Path, *, runs_root: Path) -> Path | None:
    date_tag = parse_discovery_report_date(src)
    if not date_tag:
        return None
    return runs_root / date_tag / src.name


def migrate_one(src: Path, *, runs_root: Path, dry_run: bool) -> str:
    dest = target_path(src, runs_root=runs_root)
    if dest is None:
        return f"SKIP(no date): {src}"
    if dest.resolve() == src.resolve():
        return f"SKIP(already in runs): {src}"
    if dest.exists():
        return f"SKIP(dest exists): {src} -> {dest}"
    if dry_run:
        return f"DRY-RUN: {src} -> {dest}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    return f"MOVED: {src} -> {dest}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="迁移 ai_search_discovered*.xlsx 到 runs/YYYYMMDD/")
    ap.add_argument(
        "--source",
        action="append",
        default=[],
        help="额外源目录（默认 assets + RateStats_ML/output）",
    )
    ap.add_argument("--dry-run", action="store_true", help="只打印，不移动")
    args = ap.parse_args(argv)

    runs_root = get_runs_root()
    sources = default_source_dirs()
    for s in args.source:
        sources.append(Path(s).resolve())

    files = iter_discovery_files(sources)
    if not files:
        print("[migrate-discovery] 未发现待迁移文件。")
        return 0

    print(f"[migrate-discovery] 目标根目录: {runs_root}")
    moved = skipped = 0
    for src in files:
        msg = migrate_one(src, runs_root=runs_root, dry_run=args.dry_run)
        print(f"[migrate-discovery] {msg}")
        if msg.startswith("MOVED") or msg.startswith("DRY-RUN"):
            moved += 1
        else:
            skipped += 1
    print(f"[migrate-discovery] 完成: {moved} 迁移, {skipped} 跳过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
