#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
rs_portable_init
if [ -z "${DATE_TAG:-}" ] || [ -z "${RUN_TAG:-}" ]; then
  rs_date_tags
fi
rs_set_runs_out_dir

mkdir -p "$OUT_DIR/logs"
LOG="$OUT_DIR/logs/ai_search_last_run.log"
echo "---- $(date) ----" >>"$LOG"

AI_EXTRA=()
if [ -n "${OUTPUT_FOLDER:-}" ]; then
  AI_EXTRA+=(--output-folder "$OUTPUT_FOLDER")
fi
if [ -n "${RUN_TAG:-}" ]; then
  AI_EXTRA+=(--run-tag "$RUN_TAG")
fi

echo "[05] Vertex AI search + MarketRateData *_AISearch"
echo "[05] Log: $LOG"

"$PY_CMD" -m pip install google-auth requests -q >>"$LOG" 2>&1
rs_run_py "$SRC/run_market_rate_ai_search.py" "${AI_EXTRA[@]}" 2>&1 | tee -a "$LOG"

echo "[05] Done. Log: $LOG"
