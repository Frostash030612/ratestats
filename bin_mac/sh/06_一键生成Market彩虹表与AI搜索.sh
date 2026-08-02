#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
rs_portable_init
rs_date_tags
rs_set_runs_out_dir
BASE_OUT_DIR="$OUT_DIR"
OUT_DIR="$BASE_OUT_DIR/full_pipeline_${RUN_TAG}"
mkdir -p "$OUT_DIR"

MARKET_OUT="$OUT_DIR/MarketRateData_${RUN_TAG}.xlsx"
MARKET_AI_OUT="$OUT_DIR/MarketRateData_${RUN_TAG}_AISearch.xlsx"
COMPARE_OUT="$OUT_DIR/market_data_compare_${RUN_TAG}_Vertex.xlsx"
EMAIL_CFG="$ASSETS/email_params.log"

echo "============================================================"
echo "[06] RUN_TAG=$RUN_TAG"
echo "[06] OUT_DIR=$OUT_DIR"
echo "============================================================"

echo "[A0] Sync url_params"
rs_run_py "$SRC/sync_url_params_to_json.py"

echo "[A1] Manual MarketRateData"
rs_run_py "$SRC/market_rate_data_generator.py" --xlsx-out "$MARKET_OUT"

echo "[A2] Rainbow"
rs_run_py "$SRC/generate_rainbow_from_market.py" --source "$MARKET_OUT" --out-dir-zh "$OUT_DIR" --out-tag "$RUN_TAG"

rs_run_py -c "
import shutil
from pathlib import Path
tag='$RUN_TAG'
src=Path('$OUT_DIR')/f'彩虹表_按MarketRateData更新_{tag}.xlsx'
dst=Path('$BASE_OUT_DIR')/src.name
if src.is_file():
    shutil.copy2(src, dst)
    print('Rainbow copy:', dst)
else:
    raise FileNotFoundError(src)
"

echo "[B] AI search"
export OUTPUT_FOLDER="$OUT_DIR"
export RUN_TAG
export CALLER_COMBINED=1
bash "$SH_DIR/05_run_ai_search.sh"

echo "[C] Compare manual vs AI"
if [ -f "$MARKET_OUT" ] && [ -f "$MARKET_AI_OUT" ]; then
  rs_run_py "$SRC/compare_vertex_market.py" \
    --manual "$MARKET_OUT" \
    --ai "$MARKET_AI_OUT" \
    --out-dir "$OUT_DIR" \
    --run-tag "$RUN_TAG"
else
  echo "[C] WARN: missing market files, skip compare"
fi

mkdir -p "$BASE_OUT_DIR/logs"
MAIL_LOG="$BASE_OUT_DIR/logs/email_last_run.log"
echo "---- $(date) [06] RUN_TAG=$RUN_TAG ----" >>"$MAIL_LOG"

if rs_confirm_send_mail "发送报告邮件"; then
  echo "[MAIL] Sending..."
  rs_run_py "$SRC/send_report_email.py" \
    --config-log "$EMAIL_CFG" \
    --market "$MARKET_OUT" \
    --market-ai "$MARKET_AI_OUT" \
    --compare "$COMPARE_OUT" \
    --rainbow-dir-zh "$OUT_DIR" \
    --rainbow-tag "$RUN_TAG" \
    --date-tag "$RUN_TAG" || echo "[MAIL] Failed. Check $EMAIL_CFG"
else
  echo "[MAIL] Skipped"
fi

echo "[06] All done."
echo "  Manual: $MARKET_OUT"
echo "  AI:     $MARKET_AI_OUT"
echo "  Compare:$COMPARE_OUT"
