#!/usr/bin/env bash
# 定时任务专用：手动 Market + 彩虹表 + Vertex AI + 对比 + 自动发邮件（无 pause、不交互）
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
rs_portable_init
rs_date_tags
rs_set_runs_out_dir

MARKET_OUT="$OUT_DIR/MarketRateData_${RUN_TAG}.xlsx"
MARKET_AI_OUT="$OUT_DIR/MarketRateData_${RUN_TAG}_AISearch.xlsx"
COMPARE_OUT="$OUT_DIR/market_data_compare_${RUN_TAG}_Vertex.xlsx"
EMAIL_CFG="$ASSETS/email_params.log"
LOG="$OUT_DIR/scheduled_run_${RUN_TAG}.log"

{
  echo "============================================================"
  echo "[SCHEDULED] $(date) RUN_TAG=$RUN_TAG"
  echo "[SCHEDULED] OUT_DIR=$OUT_DIR"
  echo "[SCHEDULED] PY=$PY_CMD"
  echo "============================================================"
} >"$LOG"

fail() {
  echo "[FAIL] exit $? at $(date)" >>"$LOG"
  exit 1
}

echo "[A0] sync url_params" >>"$LOG"
rs_run_py "$SRC/sync_url_params_to_json.py" >>"$LOG" 2>&1 || fail

echo "[A1] manual MarketRateData" >>"$LOG"
rs_run_py "$SRC/market_rate_data_generator.py" --xlsx-out "$MARKET_OUT" >>"$LOG" 2>&1 || fail

echo "[A2] rainbow" >>"$LOG"
rs_run_py "$SRC/generate_rainbow_from_market.py" \
  --source "$MARKET_OUT" \
  --out-dir-zh "$OUT_DIR" \
  --out-tag "$RUN_TAG" >>"$LOG" 2>&1 || fail

echo "[B] Vertex AI discover + fetch" >>"$LOG"
rs_run_py "$SRC/run_market_rate_ai_search.py" \
  --output-folder "$OUT_DIR" \
  --run-tag "$RUN_TAG" >>"$LOG" 2>&1 || fail

if [ ! -f "$MARKET_AI_OUT" ]; then
  echo "[FAIL] missing AI market: $MARKET_AI_OUT" >>"$LOG"
  exit 1
fi

echo "[C] compare manual vs AI" >>"$LOG"
rs_run_py "$SRC/compare_vertex_market.py" \
  --manual "$MARKET_OUT" \
  --ai "$MARKET_AI_OUT" \
  --out-dir "$OUT_DIR" \
  --run-tag "$RUN_TAG" >>"$LOG" 2>&1 || fail

echo "[D] send email" >>"$LOG"
if rs_run_py "$SRC/send_report_email.py" \
  --config-log "$EMAIL_CFG" \
  --market "$MARKET_OUT" \
  --market-ai "$MARKET_AI_OUT" \
  --compare "$COMPARE_OUT" \
  --rainbow-dir-zh "$OUT_DIR" \
  --rainbow-tag "$RUN_TAG" \
  --date-tag "$RUN_TAG" >>"$LOG" 2>&1; then
  echo "[MAIL] OK" >>"$LOG"
else
  echo "[MAIL] send failed, see log" >>"$LOG"
fi

echo "[OK] finished $(date)" >>"$LOG"
exit 0
