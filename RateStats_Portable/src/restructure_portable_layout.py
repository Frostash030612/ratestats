#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重组便携包：bin/ 执行、src/ 源码、docs/ 文档、assets/ 提到 RateStats 根目录。"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "RateStats_Portable"
BIN = PKG / "bin"
SRC = PKG / "src"
DOCS = PKG / "docs"
ASSETS = ROOT / "assets"

BAT_HEADER = r"""@echo off
setlocal EnableExtensions
set "BIN=%~dp0"
set "SRC=%BIN%..\src"
set "ASSETS=%BIN%..\..\assets"
set "DOCS=%BIN%..\docs"
set "PKG=%BIN%.."
"""

DOC_NAMES = {
    "README_使用说明.txt",
    "维护文档_文件职责.md",
    "URL巡检清单.md",
    "requirements.txt",
    "requirements.full.txt",
}

PROJECT_PATHS = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批次输出与目录布局（便携包标准布局）。

RateStats/
  assets/                 手动配置（url_params、email、模板、Vertex 密钥）
  RateStats_Portable/
    bin/                  批处理入口
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
DOCS_DIR = PACKAGE_DIR / "docs"

# 兼容旧名
PORTABLE_DIR = PACKAGE_DIR

BATCH_DIR_PATTERN = re.compile(
    r"^(20\\d{6}(_\\d{2}\\.\\d{2})?|sameday_\\d{8}|manual_vs_ai_\\d{8}_\\d{2}\\.\\d{2})$"
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
    m = re.search(r"(20\\d{6})", name)
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
'''


def _move(src: Path, dest: Path) -> None:
    if not src.exists():
        return
    if dest.exists():
        if src.is_dir():
            return
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))


def move_assets() -> None:
    old = PKG / "assets"
    ASSETS.mkdir(parents=True, exist_ok=True)
    if old.is_dir():
        for p in old.iterdir():
            dest = ASSETS / p.name
            if p.name.endswith(".md"):
                _move(p, DOCS / p.name)
            else:
                _move(p, dest)
        if old.exists() and not any(old.iterdir()):
            old.rmdir()


def move_sources() -> None:
    BIN.mkdir(parents=True, exist_ok=True)
    SRC.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    for p in sorted(PKG.glob("*.bat")):
        _move(p, BIN / p.name)

    skip_py = {"restructure_portable_layout.py"}
    for p in sorted(PKG.glob("*.py")):
        if p.name in skip_py:
            continue
        _move(p, SRC / p.name)

    be = PKG / "bank_extractors"
    if be.is_dir():
        _move(be, SRC / "bank_extractors")

    for name in DOC_NAMES:
        _move(PKG / name, DOCS / name)

    stray = PKG / "url_params.json"
    if stray.is_file():
        _move(stray, ASSETS / "url_params.json")


def patch_bat(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    if 'set "SRC=%BIN%..\\src"' in text:
        return

    lines = text.splitlines()
    out: list[str] = []
    inserted = False
    for i, line in enumerate(lines):
        if not inserted and line.strip().lower().startswith("@echo off"):
            out.append(line)
            for h in BAT_HEADER.strip().splitlines()[1:]:
                out.append(h)
            inserted = True
            continue
        out.append(line)

    text = "\n".join(out)
    repl = [
        (r'pushd "%~dp0\."', 'pushd "%BIN%."'),
        (r'pushd "%~dp0"', 'pushd "%BIN%"'),
        (r'cd /d "%~dp0"', 'cd /d "%BIN%"'),
        ('%~dp0set_runs_out_dir.bat', '"%BIN%set_runs_out_dir.bat"'),
        ('call "%~dp0"05_run_ai_search.bat', 'call "%BIN%05_run_ai_search.bat"'),
        ('%~dp0create_rainbow', '"%SRC%\\create_rainbow'),
        (r'%CD%\assets\\', r'%ASSETS%\\'),
        (r'%CD%\assets\\', r'%ASSETS%\\'),
        ('assets\\email_params.log', r'%ASSETS%\email_params.log'),
        ('"assets\\email_params.log"', r'"%ASSETS%\email_params.log"'),
        ('if not exist "assets\\"', 'if not exist "%ASSETS%\\"'),
        ('mkdir "assets"', 'mkdir "%ASSETS%"'),
        ('-r requirements.txt', r'-r "%DOCS%\requirements.txt"'),
        ('"requirements.txt"', r'"%DOCS%\requirements.txt"'),
    ]
    for old, new in repl:
        text = text.replace(old, new)

    text = re.sub(
        r'(%PY_CMD%|call %PY_CMD%) "([A-Za-z0-9_]+\.py)"',
        r'\1 "%SRC%\\\2"',
        text,
    )

    path.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")


def patch_all_bats() -> None:
    set_runs = BIN / "set_runs_out_dir.bat"
    if set_runs.is_file():
        t = set_runs.read_text(encoding="utf-8")
        t = t.replace('%~dp0..\\runs', '%BIN%..\\..\\runs')
        set_runs.write_text(t, encoding="utf-8")
    for bat in BIN.glob("*.bat"):
        patch_bat(bat)


def patch_python_assets_imports() -> None:
    files_assets = [
        "url_config_loader.py",
        "sync_url_params_to_json.py",
        "check_url_health.py",
        "seed_url_params_ai_from_manual.py",
        "vertex_search_client.py",
        "test_vertex_search.py",
        "export_market_url_snapshot.py",
        "url_fallback_resolver.py",
        "bank_excel_template_writer.py",
        "_diag_verify.py",
    ]
    for name in files_assets:
        p = SRC / name
        if not p.is_file():
            continue
        t = p.read_text(encoding="utf-8")
        if "from project_paths import ASSETS_DIR" in t:
            continue
        if name == "url_config_loader.py":
            t = t.replace(
                '_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))\n'
                'DEFAULT_URL_CONFIG = os.path.join(_SCRIPT_DIR, "assets", "url_params.xlsx")\n'
                'FALLBACK_URL_CONFIG_JSON = os.path.join(_SCRIPT_DIR, "assets", "url_params.json")',
                "from project_paths import ASSETS_DIR\n\n"
                'DEFAULT_URL_CONFIG = str(ASSETS_DIR / "url_params.xlsx")\n'
                'FALLBACK_URL_CONFIG_JSON = str(ASSETS_DIR / "url_params.json")',
            )
        elif name == "sync_url_params_to_json.py":
            t = re.sub(
                r'base = os\.path\.dirname\(os\.path\.abspath\(__file__\)\)\s*'
                r'xlsx_path = os\.path\.join\(base, "assets", "url_params\.xlsx"\)\s*'
                r'json_path = os\.path\.join\(base, "assets", "url_params\.json"\)',
                'from project_paths import ASSETS_DIR\n\n'
                '    xlsx_path = str(ASSETS_DIR / "url_params.xlsx")\n'
                '    json_path = str(ASSETS_DIR / "url_params.json")',
                t,
                count=1,
            )
        elif name == "check_url_health.py":
            t = t.replace(
                'cfg_path = os.path.join(base, "assets", "url_params.json")',
                'from project_paths import ASSETS_DIR\n    cfg_path = str(ASSETS_DIR / "url_params.json")',
            )
        elif name == "seed_url_params_ai_from_manual.py":
            t = t.replace(
                "_MANUAL_XLSX = _SCRIPT_DIR / \"assets\" / \"url_params.xlsx\"\n"
                "_AI_XLSX = _SCRIPT_DIR / \"assets\" / \"url_params_ai.xlsx\"",
                "from project_paths import ASSETS_DIR, default_date_run_dir, url_params_ai_paths\n\n"
                "_MANUAL_XLSX = ASSETS_DIR / \"url_params.xlsx\"\n"
                "_AI_XLSX = default_date_run_dir() / \"url_params_ai.xlsx\"",
            )
        elif name in ("vertex_search_client.py", "test_vertex_search.py"):
            t = t.replace(
                'DEFAULT_KEY_FILE = _SCRIPT_DIR / "assets" / "ratestatsearch-f5f95dab974f.json"',
                'from project_paths import ASSETS_DIR\n\nDEFAULT_KEY_FILE = ASSETS_DIR / "ratestatsearch-f5f95dab974f.json"',
            )
        elif name == "export_market_url_snapshot.py":
            t = t.replace(
                '_TEMPLATE_XLSX = _SCRIPT_DIR / "assets" / "url_params.xlsx"',
                'from project_paths import ASSETS_DIR\n\n_TEMPLATE_XLSX = ASSETS_DIR / "url_params.xlsx"',
            )
        elif name == "url_fallback_resolver.py":
            t = t.replace(
                'path = manual_xlsx or str(_SCRIPT_DIR / "assets" / "url_params.xlsx")',
                'from project_paths import ASSETS_DIR\n    path = manual_xlsx or str(ASSETS_DIR / "url_params.xlsx")',
            )
        elif name == "bank_excel_template_writer.py":
            t = t.replace(
                '        os.path.join(script_dir, "assets", "MarketRateData_template.xlsx"),\n'
                '        os.path.join(script_dir, "..", "assets", "MarketRateData_template.xlsx"),',
                '        str((__import__("project_paths").ASSETS_DIR / "MarketRateData_template.xlsx")),',
            )
        elif name == "_diag_verify.py":
            t = t.replace(
                "CFG = json.load(open('assets/url_params.json', encoding='utf-8'))",
                'from project_paths import ASSETS_DIR\nCFG = json.load(open(ASSETS_DIR / "url_params.json", encoding="utf-8"))',
            )
        p.write_text(t, encoding="utf-8")

    mp = SRC / "migrate_runtime_outputs_to_runs.py"
    if mp.is_file():
        t = mp.read_text(encoding="utf-8")
        t = t.replace("_ASSETS = PORTABLE_DIR / \"assets\"", "_ASSETS = ASSETS_DIR")
        t = t.replace("from project_paths import (\n    PORTABLE_DIR,", "from project_paths import (\n    ASSETS_DIR,\n    PACKAGE_DIR,")
        t = t.replace("_SCRIPT_DIR = PORTABLE_DIR", "_SCRIPT_DIR = PACKAGE_DIR")
        mp.write_text(t, encoding="utf-8")

    md = SRC / "migrate_discovery_reports_to_runs.py"
    if md.is_file():
        t = md.read_text(encoding="utf-8")
        t = t.replace("_SCRIPT_DIR / \"assets\"", "ASSETS_DIR")
        t = t.replace("from project_paths import get_runs_root", "from project_paths import ASSETS_DIR, get_runs_root")
        md.write_text(t, encoding="utf-8")

    (SRC / "project_paths.py").write_text(PROJECT_PATHS, encoding="utf-8")


def patch_ml_portable() -> None:
    p = ROOT / "RateStats_ML" / "_portable.py"
    t = p.read_text(encoding="utf-8")
    t = t.replace(
        "_PORTABLE = _RATESTATS / \"RateStats_Portable\"",
        "_PACKAGE = _RATESTATS / \"RateStats_Portable\"\n_PORTABLE = _PACKAGE\n_SRC = _PACKAGE / \"src\"\nASSETS_DIR = _RATESTATS / \"assets\"",
    )
    t = t.replace(
        "DEFAULT_MANUAL_XLSX = _PORTABLE / \"assets\" / \"url_params.xlsx\"",
        "DEFAULT_MANUAL_XLSX = ASSETS_DIR / \"url_params.xlsx\"",
    )
    t = t.replace(
        "for p in (_PORTABLE, _AI_COMPARE, _ML_ROOT):",
        "for p in (_SRC, _AI_COMPARE, _ML_ROOT):",
    )
    p.write_text(t, encoding="utf-8")


def patch_package_zip() -> None:
    p = SRC / "package_portable_zip.py"
    if not p.is_file():
        return
    t = p.read_text(encoding="utf-8")
    t = t.replace(
        'INCLUDE_TOP = (\n    "RateStats_Portable",',
        'INCLUDE_TOP = (\n    "assets",\n    "RateStats_Portable",',
    )
    t = t.replace('ROOT = Path(__file__).resolve().parent.parent', 'ROOT = Path(__file__).resolve().parent.parent.parent')
    t = t.replace(
        "if parts[0] == \"RateStats_Portable\" and _skip_generated_outputs",
        'if parts[0] == "RateStats_Portable" and "bin" not in parts and _skip_generated_outputs',
    )
    t = t.replace(
        '  服务账号 JSON 已包含在 RateStats_Portable/assets/ 下。',
        '  服务账号 JSON 在 RateStats/assets/ 下。',
    )
    t = t.replace(
        '  配置 RateStats_Portable/assets/email_params.log',
        '  配置 RateStats/assets/email_params.log',
    )
    t = t.replace(
        '  3. 进入 RateStats_Portable，双击：01_首次安装依赖.bat',
        '  3. 进入 RateStats_Portable/bin，双击：01_首次安装依赖.bat',
    )
    t = t.replace(
        "目录结构：\n  RateStats/\n    RateStats_Portable/   主流程（Market、彩虹表、Vertex AI、对比、邮件）",
        "目录结构：\n  RateStats/\n    assets/               手动配置（url_params、email、模板）\n"
        "    RateStats_Portable/\n      bin/                批处理入口\n"
        "      src/                Python 源码\n"
        "      docs/               说明文档",
    )
    t = t.replace(
        '        if not base.is_dir():\n            continue\n        for path in base.rglob("*"):',
        '        if not base.is_dir():\n            continue\n        if top == "RateStats_Portable":\n'
        '            for path in base.rglob("*"):\n                if path.is_file():\n'
        '                    rel = path.relative_to(ROOT)\n'
        '                    if should_skip(rel):\n                        continue\n'
        '                    items.append((path, rel))\n            continue\n'
        '        for path in base.rglob("*"):',
    )
    p.write_text(t, encoding="utf-8")


def main() -> int:
    print("[restructure] ROOT:", ROOT)
    move_assets()
    move_sources()
    patch_all_bats()
    patch_python_assets_imports()
    patch_ml_portable()
    patch_package_zip()
    me = PKG / "restructure_portable_layout.py"
    if me.is_file():
        _move(me, SRC / me.name)
    print("[restructure] done.")
    print("  assets ->", ASSETS)
    print("  bin    ->", BIN)
    print("  src    ->", SRC)
    print("  docs   ->", DOCS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
