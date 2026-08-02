#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
rs_portable_init
rs_run_py "$SRC/seed_url_params_ai_from_manual.py" "$@"
