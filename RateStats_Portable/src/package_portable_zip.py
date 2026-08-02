#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 RateStats 可运行脚本与配置打包为 zip，便于拷贝到其他电脑。"""

from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PORTABLE = ROOT / "RateStats_Portable"
OUT_NAME = f"RateStats_便携运行包_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
OUT_ZIP = ROOT / OUT_NAME

# 打入 zip 的顶层目录（保持 RateStats/ 标准布局）
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
}

SKIP_SUFFIXES = (".pyc", ".pyo", ".zip")


def _skip_generated_outputs(name: str) -> bool:
    if name.startswith("彩虹表_"):
        return True
    return False


def _skip_asset_noise(name: str) -> bool:
    if name in {"email_params.log", "schedule_params.log"}:
        return False
    if name.endswith(".log"):
        return True
    if name.startswith("ai_search_discovered_") and name.endswith(".xlsx"):
        return True
    return False


PORTABLE_ALLOW = {"bin", "src", "docs", "README.txt"}


def should_skip(rel: Path) -> bool:
    parts = rel.parts
    if any(p in SKIP_DIR_NAMES for p in parts):
        return True
    if rel.name in SKIP_FILE_NAMES:
        return True
    if parts[0] == "RateStats_Portable":
        if len(parts) >= 2 and parts[1] not in PORTABLE_ALLOW:
            return True
        if len(parts) == 2 and parts[1] not in PORTABLE_ALLOW:
            return True
    if parts[0] == "RateStats_Portable" and "bin" not in parts and _skip_generated_outputs(rel.name):
        return True
    if rel.suffix.lower() in SKIP_SUFFIXES:
        return True
    if "assets" in parts and _skip_asset_noise(rel.name):
        return True
    # runs：只保留 README.md
    if parts[0] == "runs" and len(parts) > 1:
        return True
    # RateStats_ML 评估产出
    if parts[0] == "RateStats_ML" and "output" in parts:
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
        if top == "RateStats_Portable":
            for path in base.rglob("*"):
                if path.is_file():
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


def deploy_readme() -> str:
    return """RateStats 便携运行包 — 部署说明
================================

目录结构：
  RateStats/
    assets/               手动配置（url_params、email、模板）
    RateStats_Portable/
      bin/                批处理入口
      src/                Python 源码
      docs/               说明文档
    AI_Compare/           多 AI 引擎评测（可选）
    RateStats_ML/         ML 选链实验（可选）
    runs/                 批次输出目录（运行后自动生成子文件夹）

新电脑步骤：
  1. 解压整个 RateStats 文件夹到任意路径（建议路径不含中文空格）。
  2. 安装 Python 3.10+，勾选 Add Python to PATH。
  3. 进入 RateStats_Portable/bin，双击：01_首次安装依赖.bat
     （一次安装手动抓取 + Vertex AI + ML 选链全部依赖）
  4. 常用入口（输出均在 runs/YYYYMMDD/）：
     - 03_一键生成Market+彩虹表.bat
         手动 url_params.xlsx → Market + 彩虹表
     - 05_run_ai_search.bat / 06_一键生成Market彩虹表与AI搜索.bat
         Vertex AI 发现链接 → Market *_AISearch + 对比
     - RateStats_ML\03_Vertex_ML发现并抓取.bat
         ML 选链（需已训练模型，包内已含 models/）→ url_params_ai_ml + Market *_ML
  5. 首次使用 ML 可选：RateStats_ML\01_训练模型.bat（用 runs 历史发现报告重训）

AI_Compare（四家对比，可选）：
  复制 AI_Compare/keys.txt.example 为 keys.txt 并填入 Serper/Brave/Tavily Key
  双击 AI_Compare/run_all_providers_market.bat

RateStats_ML 训练/评估（可选）：
  01_训练模型.bat → 02_评估选链准确率.bat → 04_调参融合权重.bat
  03_Vertex_ML发现并抓取.bat 使用调参后的 picker

Vertex AI：
  服务账号 JSON 在 RateStats/assets/ 下。
  换电脑后若路径变化，一般无需改；若鉴权失败请检查该 JSON 是否存在。

邮件：
  配置 RateStats/assets/email_params.log

打包时已排除：历史 runs 数据、AI_Compare/output、ML output、运行日志。

所有运行产物默认写入 runs/（见 runs/README.md）。assets 仅保留手动配置。


生成时间：{ts}
""".format(ts=datetime.now().strftime("%Y-%m-%d %H:%M"))


def main() -> None:
    files = iter_files()
    if OUT_ZIP.exists():
        OUT_ZIP.unlink()
    with zipfile.ZipFile(OUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("RateStats/部署说明.txt", deploy_readme().encode("utf-8"))
        for src, arc in files:
            zf.write(src, (Path("RateStats") / arc).as_posix())
    size_mb = OUT_ZIP.stat().st_size / (1024 * 1024)
    print(f"OK: {OUT_ZIP}")
    print(f"Files: {len(files) + 1}")
    print(f"Size:  {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
