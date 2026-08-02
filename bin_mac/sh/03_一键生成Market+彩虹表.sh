#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
rs_portable_init
rs_date_tags
rs_set_runs_out_dir

MARKET_OUT="$OUT_DIR/MarketRateData_${RUN_TAG}.xlsx"
EMAIL_CFG="$ASSETS/email_params.log"
MAIL_LOG="$OUT_DIR/logs/email_last_run.log"

echo "[0] Sync url_params"
rs_run_py "$SRC/sync_url_params_to_json.py"

echo "[1] MarketRateData"
rs_run_py "$SRC/market_rate_data_generator.py" --xlsx-out "$MARKET_OUT"

echo "[2] Rainbow"
rs_run_py "$SRC/generate_rainbow_from_market.py" --source "$MARKET_OUT" --out-dir-zh "$OUT_DIR" --out-tag "$RUN_TAG"

mkdir -p "$OUT_DIR/logs"
echo "---- $(date) DATE_TAG=$DATE_TAG RUN_TAG=$RUN_TAG ----" >>"$MAIL_LOG"

if rs_confirm_send_mail "发送邮件"; then
  echo "[MAIL] Sending..."
  if rs_run_py "$SRC/send_report_email.py" \
    --config-log "$EMAIL_CFG" \
    --market "$MARKET_OUT" \
    --rainbow-dir-zh "$OUT_DIR" \
    --rainbow-tag "$RUN_TAG" \
    --date-tag "$RUN_TAG"; then
    echo "[MAIL] OK"
  else
    echo "[MAIL] Failed. Check $EMAIL_CFG"
  fi
else
  echo "[MAIL] Skipped"
fi

echo "[OK] Output: $OUT_DIR"
