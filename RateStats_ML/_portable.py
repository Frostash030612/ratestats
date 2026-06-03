"""将 RateStats_Portable 加入 sys.path（不修改旧方案代码）。"""
from __future__ import annotations

import sys
from pathlib import Path

_ML_ROOT = Path(__file__).resolve().parent
_RATESTATS = _ML_ROOT.parent
_PORTABLE = _RATESTATS / "RateStats_Portable"
_AI_COMPARE = _RATESTATS / "AI_Compare"

for p in (_PORTABLE, _AI_COMPARE, _ML_ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

PORTABLE_DIR = _PORTABLE
AI_COMPARE_DIR = _AI_COMPARE
ML_ROOT = _ML_ROOT
DEFAULT_MANUAL_XLSX = _PORTABLE / "assets" / "url_params.xlsx"
MODEL_DIR = _ML_ROOT / "models"
DATA_DIR = _ML_ROOT / "data"
OUTPUT_DIR = _ML_ROOT / "output"
