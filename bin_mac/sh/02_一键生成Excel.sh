#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
rs_portable_init
rs_date_tags
rs_set_runs_out_dir

MARKET_OUT="$OUT_DIR/MarketRateData_${RUN_TAG}.xlsx"

echo "[0] Sync url_params.xlsx -> url_params.json"
rs_run_py "$SRC/sync_url_params_to_json.py"

echo "[1] Generate MarketRateData -> $MARKET_OUT"
rs_run_py "$SRC/market_rate_data_generator.py" --xlsx-out "$MARKET_OUT"

echo "[OK] $MARKET_OUT"
