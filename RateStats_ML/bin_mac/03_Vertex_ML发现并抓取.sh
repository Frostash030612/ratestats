#!/usr/bin/env bash
set -euo pipefail
ML_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi

if [ ! -f "$ML_ROOT/models/url_ranker.joblib" ]; then
  echo "请先运行 bin_mac/01_训练模型.sh"
  exit 1
fi

TAG="$(date +%Y%m%d)"
DATE_TAG="$(date +%Y%m%d)"
cd "$ML_ROOT"
"$PY" run_vertex_ml_discovery.py --run-tag "$DATE_TAG" --fetch
