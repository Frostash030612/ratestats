#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
rs_portable_init

rs_run_py "$SRC/sync_url_params_to_json.py"
rs_run_py "$SRC/check_url_health.py"
