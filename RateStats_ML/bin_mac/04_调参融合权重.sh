#!/usr/bin/env bash
set -euo pipefail
ML_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
cd "$ML_ROOT"
"$PY" tune_picker.py
