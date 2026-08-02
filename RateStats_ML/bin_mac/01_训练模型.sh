#!/usr/bin/env bash
set -euo pipefail
ML_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RATESTATS_ROOT="$(cd "$ML_ROOT/.." && pwd)"
PORTABLE_SRC="$RATESTATS_ROOT/RateStats_Portable/src"
export PYTHONUTF8=1

if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi

cd "$ML_ROOT"
"$PY" -m pip install -r requirements.txt -q
"$PY" train.py --use-discovery
