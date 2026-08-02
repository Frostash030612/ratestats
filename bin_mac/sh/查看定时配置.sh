#!/usr/bin/env bash
# 仅显示 schedule_params.log 解析结果，不改系统
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
rs_portable_init
rs_run_py "$SRC/register_mac_schedule.py" --config "$ASSETS/schedule_params.log" --show
