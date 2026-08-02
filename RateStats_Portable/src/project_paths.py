#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批次输出与目录布局（便携包标准布局）。

RateStats/
  assets/                 手动配置（url_params、email、模板、Vertex 密钥）
  bin_mac/                macOS 双击入口（*.command）与 sh/*.sh
  RateStats_Portable/
    bin/                  Windows 批处理入口
    src/                  Python 源码
    docs/                 说明与 requirements
  runs/                   运行产物
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = SRC_DIR.parent
PROJECT_ROOT = PACKAGE_DIR.parent
_PARENT = PROJECT_ROOT.parent

if (PROJECT_ROOT / "RateStats_Portable").resolve() == PACKAGE_DIR.resolve():
    pass
elif (PACKAGE_DIR / "src" / "project_paths.py").resolve() == Path(__file__).resolve():
    PROJECT_ROOT = PACKAGE_DIR.parent
else:
    PROJECT_ROOT = PACKAGE_DIR.parent

_RUNS_ENV = os.environ.get("RATESTATS_RUNS_ROOT", "").strip()
RUNS_ROOT = Path(_RUNS_ENV).expanduser().resolve() if _RUNS_ENV else (PROJECT_ROOT / "runs")

ASSETS_DIR = PROJECT_ROOT / "assets"
BIN_DIR = PACKAGE_DIR / "bin"
BIN_MAC_DIR = PROJECT_ROOT / "bin_mac"
DOCS_DIR = PACKAGE_DIR / "docs"

# 兼容旧名
PORTABLE_DIR = PACKAGE_DIR

BATCH_DIR_PATTERN = re.compile(
    r"^(20\d{6}(_\d{2}\.\d{2})?|sameday_\d{8}|manual_vs_ai_\d{8}_\d{2}\.\d{2})$"
)


def get_runs_root() -> Path:
    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    return RUNS_ROOT


def run_dir_for_date(date_tag: str | None = None, *, runs_root: Path | None = None) -> Path:
    root = runs_root or get_runs_root()
    tag = date_tag or datetime.now().strftime("%Y%m%d")
    p = root / tag
    p.mkdir(parents=True, exist_ok=True)
    return p


def run_dir_named(name: str, *, runs_root: Path | None = None) -> Path:
    root = runs_root or get_runs_root()
    p = root / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def default_date_run_dir() -> Path:
    return run_dir_for_date()


def parse_run_date_tag(name: str) -> str | None:
    m = re.search(r"(20\d{6})", name)
    return m.group(1) if m else None


def parse_discovery_report_date(path: Path) -> str | None:
    for part in (path.stem, path.parent.name):
        tag = parse_run_date_tag(part)
        if tag:
            return tag
    return None


def ml_eval_dir(date_tag: str | None = None, *, runs_root: Path | None = None) -> Path:
    root = runs_root or get_runs_root()
    tag = date_tag or datetime.now().strftime("%Y%m%d")
    p = root / "ml_eval" / tag
    p.mkdir(parents=True, exist_ok=True)
    return p


def ai_compare_config_dir(run_tag: str, *, run_dir: Path | None = None) -> Path:
    date_tag = parse_run_date_tag(run_tag) or datetime.now().strftime("%Y%m%d")
    base = run_dir or run_dir_for_date(date_tag)
    p = base / "ai_compare" / run_tag
    p.mkdir(parents=True, exist_ok=True)
    return p


def compare_out_dir(date_tag: str | None = None, *, runs_root: Path | None = None) -> Path:
    d = run_dir_for_date(date_tag, runs_root=runs_root) / "compare"
    d.mkdir(parents=True, exist_ok=True)
    return d


def audit_out_dir(*, run_dir: Path | None = None) -> Path:
    d = (run_dir or default_date_run_dir()) / "audit"
    d.mkdir(parents=True, exist_ok=True)
    return d


def runs_log_dir(*, run_dir: Path | None = None) -> Path:
    if run_dir:
        d = run_dir / "logs"
    else:
        d = get_runs_root() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def url_params_ai_paths(run_dir: Path) -> tuple[Path, Path]:
    xlsx = run_dir / "url_params_ai.xlsx"
    return xlsx, xlsx.with_name("url_params_ai.json")


def find_latest_url_params_ai(*, runs_root: Path | None = None) -> Path | None:
    root = runs_root or get_runs_root()
    if not root.is_dir():
        return None
    latest: Path | None = None
    latest_mtime = 0.0
    for p in root.rglob("url_params_ai.xlsx"):
        mt = p.stat().st_mtime
        if mt > latest_mtime:
            latest_mtime = mt
            latest = p
    return latest


def ai_discovery_report_path(tag: str, *, run_dir: Path | None = None) -> Path:
    d = run_dir or default_date_run_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / f"ai_search_discovered_{tag}.xlsx"


def is_legacy_batch_dir(path: Path) -> bool:
    return bool(BATCH_DIR_PATTERN.match(path.name))


def portable_legacy_batch_dirs() -> list[Path]:
    if not PACKAGE_DIR.is_dir():
        return []
    out: list[Path] = []
    for p in PACKAGE_DIR.iterdir():
        if p.is_dir() and is_legacy_batch_dir(p):
            out.append(p)
    return sorted(out, key=lambda x: x.name)
