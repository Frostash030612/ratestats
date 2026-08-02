#!/usr/bin/env bash
# 按 assets/schedule_params.log 中的 label 卸载定时任务
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
rs_portable_init

CFG="$ASSETS/schedule_params.log"
rs_run_py "$SRC/register_mac_schedule.py" --config "$CFG" --unregister
