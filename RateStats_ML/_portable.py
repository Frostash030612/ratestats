"""将 RateStats_Portable 加入 sys.path（不修改旧方案代码）。"""
from __future__ import annotations

import sys
from pathlib import Path

_ML_ROOT = Path(__file__).resolve().parent
_RATESTATS = _ML_ROOT.parent
_PACKAGE = _RATESTATS / "RateStats_Portable"
_PORTABLE = _PACKAGE
_SRC = _PACKAGE / "src"
ASSETS_DIR = _RATESTATS / "assets"
_AI_COMPARE = _RATESTATS / "AI_Compare"

for p in (_SRC, _AI_COMPARE, _ML_ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

PORTABLE_DIR = _PORTABLE
AI_COMPARE_DIR = _AI_COMPARE
ML_ROOT = _ML_ROOT
DEFAULT_MANUAL_XLSX = ASSETS_DIR / "url_params.xlsx"
MODEL_DIR = _ML_ROOT / "models"
DATA_DIR = _ML_ROOT / "data"

from project_paths import get_runs_root, ml_eval_dir  # noqa: E402

RUNS_ROOT = get_runs_root()


def get_output_dir() -> Path:
    """ML 评估/对比报告目录（runs/ml_eval/YYYYMMDD/）。"""
    return ml_eval_dir()


OUTPUT_DIR = get_output_dir()
