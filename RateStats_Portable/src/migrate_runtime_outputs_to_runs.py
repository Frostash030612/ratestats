#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将仓库内遗留的运行产物迁入 runs/（按文件名/目录名中的日期归档）。"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from project_paths import (
    ASSETS_DIR,
    PACKAGE_DIR,
    PROJECT_ROOT,
    get_runs_root,
    parse_discovery_report_date,
    parse_run_date_tag,
    portable_legacy_batch_dirs,
    runs_log_dir,
)

_SCRIPT_DIR = PACKAGE_DIR
_ML_OUTPUT = PROJECT_ROOT / "RateStats_ML" / "output"
_AI_OUTPUT = PROJECT_ROOT / "AI_Compare" / "output"
_AI_RESULTS = PROJECT_ROOT / "AI_Compare" / "results"
_AI_RAW_CACHE = PROJECT_ROOT / "AI_Compare" / "raw_cache"
_ASSETS = ASSETS_DIR
_TEMP = PORTABLE_DIR / "temp"

_DATE_RE = re.compile(r"(20\d{6})")
_ORPHAN_DATE_HINTS: tuple[tuple[str, str], ...] = (
    ("ocbcfix2", "20260603"),
    ("ocbcfix", "20260603"),
)

_DISCOVERY_GLOBS = ("ai_search_discovered_*.xlsx", "ai_search_discovered_ml_*.xlsx")
_RUNTIME_ASSET_NAMES = {
    "ai_search_last_run.log",
    "email_last_run.log",
    "url_params_ai.xlsx",
    "url_params_ai.json",
}


def _date_from_path(path: Path) -> str | None:
    for part in (path.name, path.stem, path.parent.name):
        tag = parse_run_date_tag(part)
        if tag:
            return tag
    stem_lower = path.stem.lower()
    for hint, date_tag in _ORPHAN_DATE_HINTS:
        if hint in stem_lower:
            return date_tag
    return None


def _move_file(src: Path, dest: Path, *, dry_run: bool) -> str:
    if dest.resolve() == src.resolve():
        return f"SKIP(same): {src}"
    if dest.exists():
        try:
            same = dest.stat().st_size == src.stat().st_size
        except OSError:
            same = False
        if same:
            if dry_run:
                return f"DRY-RUN(remove dup): {src} (kept {dest})"
            src.unlink()
            return f"REMOVED(dup): {src} (kept {dest})"
        alt = dest.parent / "_superseded" / src.name
        if dry_run:
            return f"DRY-RUN(conflict): {src} -> {alt}"
        alt.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(alt))
        return f"MOVED(conflict): {src} -> {alt}"
    if dry_run:
        return f"DRY-RUN: {src} -> {dest}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    return f"MOVED: {src} -> {dest}"


def _migrate_discovery_in_dir(src_dir: Path, *, runs_root: Path, dry_run: bool) -> list[str]:
    msgs: list[str] = []
    if not src_dir.is_dir():
        return msgs
    for pattern in _DISCOVERY_GLOBS:
        for src in sorted(src_dir.rglob(pattern)):
            date_tag = parse_discovery_report_date(src) or _date_from_path(src)
            if not date_tag:
                msgs.append(f"SKIP(no date): {src}")
                continue
            dest = runs_root / date_tag / src.name
            msgs.append(_move_file(src, dest, dry_run=dry_run))
    return msgs


def _migrate_assets_runtime(*, runs_root: Path, dry_run: bool) -> list[str]:
    msgs: list[str] = []
    if not _ASSETS.is_dir():
        return msgs

    msgs.extend(_migrate_discovery_in_dir(_ASSETS, runs_root=runs_root, dry_run=dry_run))

    for name in _RUNTIME_ASSET_NAMES:
        src = _ASSETS / name
        if not src.is_file():
            continue
        if name.endswith(".log"):
            dest = runs_log_dir() / name
        else:
            date_tag = datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y%m%d")
            dest = runs_root / date_tag / name
        msgs.append(_move_file(src, dest, dry_run=dry_run))
    return msgs


def _migrate_ml_output(*, runs_root: Path, dry_run: bool) -> list[str]:
    msgs: list[str] = []
    if not _ML_OUTPUT.is_dir():
        return msgs

    for src in sorted(_ML_OUTPUT.rglob("*")):
        if not src.is_file():
            continue
        if src.suffix.lower() not in {".xlsx", ".json", ".csv", ".log"}:
            continue

        name = src.name
        parent = src.parent.name

        if name.startswith("picker_eval_") or name.startswith("picker_tune_"):
            date_tag = _date_from_path(src) or datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y%m%d")
            dest = runs_root / "ml_eval" / date_tag / name
        elif parent.startswith("compare_"):
            date_tag = parse_run_date_tag(parent) or parse_run_date_tag(name)
            sub = parent if parent.startswith("compare_") else "compare"
            dest = runs_root / (date_tag or "unknown") / "ml_compare" / sub / name
        elif _DATE_RE.search(parent):
            date_tag = parse_run_date_tag(parent) or parent[:8]
            dest = runs_root / date_tag / name
        elif _DATE_RE.search(name):
            date_tag = _date_from_path(name)
            dest = runs_root / (date_tag or "unknown") / name
        else:
            date_tag = _date_from_path(src) or datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y%m%d")
            dest = runs_root / date_tag / "ml_legacy" / src.relative_to(_ML_OUTPUT).as_posix().replace("/", "__")

        msgs.append(_move_file(src, dest, dry_run=dry_run))
    return msgs


def _migrate_ai_compare_output(*, runs_root: Path, dry_run: bool) -> list[str]:
    msgs: list[str] = []
    if not _AI_OUTPUT.is_dir():
        return msgs
    for tag_dir in sorted(_AI_OUTPUT.iterdir()):
        if not tag_dir.is_dir():
            continue
        date_tag = parse_run_date_tag(tag_dir.name) or datetime.now().strftime("%Y%m%d")
        for src in sorted(tag_dir.rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(tag_dir)
            dest = runs_root / date_tag / "ai_compare" / tag_dir.name / rel
            msgs.append(_move_file(src, dest, dry_run=dry_run))
    return msgs


def _migrate_ai_results(*, runs_root: Path, dry_run: bool) -> list[str]:
    msgs: list[str] = []
    for root in (_AI_RESULTS, _AI_RAW_CACHE):
        if not root.is_dir():
            continue
        for src in sorted(root.rglob("*")):
            if not src.is_file():
                continue
            date_tag = _date_from_path(src) or datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y%m%d")
            rel = src.relative_to(root)
            bucket = "ai_eval" if root.name == "results" else "ai_eval_raw_cache"
            dest = runs_root / bucket / date_tag / rel
            msgs.append(_move_file(src, dest, dry_run=dry_run))
    return msgs


def _migrate_portable_root(*, runs_root: Path, dry_run: bool) -> list[str]:
    msgs: list[str] = []
    for src in sorted(PORTABLE_DIR.glob("url_health_report_*.json")):
        date_tag = _date_from_path(src) or datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y%m%d")
        dest = runs_root / date_tag / "audit" / src.name
        msgs.append(_move_file(src, dest, dry_run=dry_run))
    return msgs


def _migrate_repo_root(*, runs_root: Path, dry_run: bool) -> list[str]:
    msgs: list[str] = []
    patterns = ("_tmp_verify_*.xlsx", "MarketRateData_*.xlsx", "rate_output_*.xlsx")
    for pattern in patterns:
        for src in sorted(PROJECT_ROOT.glob(pattern)):
            if not src.is_file():
                continue
            date_tag = _date_from_path(src) or datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y%m%d")
            dest = runs_root / date_tag / src.name
            msgs.append(_move_file(src, dest, dry_run=dry_run))
    return msgs


def _migrate_temp_scratch(*, runs_root: Path, dry_run: bool) -> list[str]:
    msgs: list[str] = []
    if not _TEMP.is_dir():
        return msgs
    scratch = runs_root / ".scratch"
    for src in sorted(_TEMP.glob("MarketRateData_work_*.xlsx")):
        date_tag = _date_from_path(src) or datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y%m%d")
        dest = scratch / date_tag / src.name
        msgs.append(_move_file(src, dest, dry_run=dry_run))
    return msgs


def _migrate_legacy_batch_dirs(*, runs_root: Path, dry_run: bool) -> list[str]:
    msgs: list[str] = []
    for src in portable_legacy_batch_dirs():
        dest = runs_root / src.name
        if dest.exists():
            msgs.append(f"SKIP(batch exists): {src}")
            continue
        if dry_run:
            msgs.append(f"DRY-RUN(batch): {src} -> {dest}")
            continue
        shutil.move(str(src), str(dest))
        msgs.append(f"MOVED(batch): {src} -> {dest}")
    return msgs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="迁移运行产物到 runs/")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-legacy-dirs", action="store_true", help="跳过 Portable 内历史日期目录")
    args = ap.parse_args(argv)

    runs_root = get_runs_root()
    print(f"[migrate-runtime] 目标: {runs_root}")

    all_msgs: list[str] = []
    all_msgs.extend(_migrate_assets_runtime(runs_root=runs_root, dry_run=args.dry_run))
    all_msgs.extend(_migrate_ml_output(runs_root=runs_root, dry_run=args.dry_run))
    all_msgs.extend(_migrate_ai_compare_output(runs_root=runs_root, dry_run=args.dry_run))
    all_msgs.extend(_migrate_ai_results(runs_root=runs_root, dry_run=args.dry_run))
    all_msgs.extend(_migrate_portable_root(runs_root=runs_root, dry_run=args.dry_run))
    all_msgs.extend(_migrate_repo_root(runs_root=runs_root, dry_run=args.dry_run))
    all_msgs.extend(_migrate_temp_scratch(runs_root=runs_root, dry_run=args.dry_run))
    if not args.skip_legacy_dirs:
        all_msgs.extend(_migrate_legacy_batch_dirs(runs_root=runs_root, dry_run=args.dry_run))

    moved = sum(1 for m in all_msgs if m.startswith("MOVED") or m.startswith("DRY-RUN"))
    skipped = sum(1 for m in all_msgs if m.startswith("SKIP"))
    for m in all_msgs:
        if m:
            print(f"[migrate-runtime] {m}")
    print(f"[migrate-runtime] 完成: {moved} 迁移, {skipped} 跳过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
