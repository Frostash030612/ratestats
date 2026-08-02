#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包 macOS 便携 zip（bin_mac + 不含 Windows .bat）。"""
from __future__ import annotations

import stat
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_NAME = f"RateStats_便携运行包_Mac_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
OUT_ZIP = ROOT / OUT_NAME

INCLUDE_TOP = (
    "assets",
    "bin_mac",
    "RateStats_Portable",
    "AI_Compare",
    "RateStats_ML",
    "runs",
)

SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".cursor",
    "temp",
    "run_output",
    "output",
    "results",
    "raw_cache",
    "mcps",
}

SKIP_FILE_NAMES = {
    "url_params.tmp.xlsx",
    "_uob.html",
    "package_portable_zip.py",
    "package_portable_zip_mac.py",
}

SKIP_SUFFIXES = (".pyc", ".pyo", ".zip", ".bat")

PORTABLE_ALLOW = {"src", "docs", "README.txt"}
ML_ALLOW = {"bin_mac", "models", "data", "docs", "requirements.txt", "README.md"}
ML_ALLOW_FILES = set()  # unused after simplify


def _skip_asset_noise(name: str) -> bool:
    if name in {"email_params.log", "schedule_params.log"}:
        return False
    if name.endswith(".log"):
        return True
    if name.startswith("ai_search_discovered_") and name.endswith(".xlsx"):
        return True
    return False


def should_skip(rel: Path) -> bool:
    parts = rel.parts
    if any(p in SKIP_DIR_NAMES for p in parts):
        return True
    if rel.name in SKIP_FILE_NAMES:
        return True
    if rel.suffix.lower() in SKIP_SUFFIXES:
        return True
    if parts[0] == "RateStats_Portable":
        if len(parts) >= 2 and parts[1] not in PORTABLE_ALLOW:
            return True
    if parts[0] == "RateStats_ML":
        if "output" in parts:
            return True
        if rel.suffix.lower() == ".bat":
            return True
    if "assets" in parts and _skip_asset_noise(rel.name):
        return True
    if parts[0] == "runs" and len(parts) > 1:
        return True
    return False


def iter_files() -> list[tuple[Path, Path]]:
    items: list[tuple[Path, Path]] = []
    for top in INCLUDE_TOP:
        base = ROOT / top
        if top == "runs":
            readme = base / "README.md"
            if readme.is_file():
                items.append((readme, Path("runs") / "README.md"))
            continue
        if not base.is_dir():
            continue
        if top == "RateStats_ML":
            for path in base.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(ROOT)
                if should_skip(rel):
                    continue
                items.append((path, rel))
            continue
        if top == "RateStats_Portable":
            for path in base.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(ROOT)
                if should_skip(rel):
                    continue
                items.append((path, rel))
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if should_skip(rel):
                continue
            items.append((path, rel))
    return items


def deploy_readme_mac() -> str:
    return """RateStats 便携运行包 — macOS 版
================================

目录结构：
  RateStats/
    assets/               手动配置（url_params、email、模板）
    bin_mac/*.command     双击入口（与 assets 同级）
    bin_mac/sh/*.sh       实际脚本
    RateStats_Portable/
      src/                Python 源码
      docs/               说明（含 README_mac.md）
    RateStats_ML/bin_mac/ ML 脚本
    runs/                 运行产物

首次使用：
  1. 安装 Python 3.11/3.12（勿用 3.14；可 brew install python@3.11）
  2. 解压到无空格路径，例如 ~/RateStats
  3. chmod +x bin_mac/*.command bin_mac/sh/*.sh
  4. chmod +x RateStats_ML/bin_mac/*.sh
  5. 双击 bin_mac/01_首次安装依赖.command
  6. 双击 bin_mac/06_一键生成Market彩虹表与AI搜索.command

详细说明：RateStats_Portable/docs/README_mac.md

生成时间：{ts}
""".format(ts=datetime.now().strftime("%Y-%m-%d %H:%M"))


def _zip_write(zf: zipfile.ZipFile, src: Path, arc: Path) -> None:
    if arc.suffix in {".sh", ".command"}:
        # Mac 脚本必须用 LF；若在 Windows 上写入会带 CRLF，执行时会报 No such file
        data = src.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        info = zipfile.ZipInfo((Path("RateStats") / arc).as_posix())
        info.create_system = 3  # Unix
        info.external_attr = (stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH) << 16
        zf.writestr(info, data)
    else:
        zf.write(src, (Path("RateStats") / arc).as_posix())


def main() -> None:
    files = iter_files()
    if OUT_ZIP.exists():
        OUT_ZIP.unlink()
    with zipfile.ZipFile(OUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("RateStats/部署说明_Mac.txt", deploy_readme_mac().encode("utf-8"))
        for src, arc in files:
            _zip_write(zf, src, arc)
    size_mb = OUT_ZIP.stat().st_size / (1024 * 1024)
    print(f"OK: {OUT_ZIP}")
    print(f"Files: {len(files) + 1}")
    print(f"Size:  {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
