#!/usr/bin/env bash
# 读取 assets/schedule_params.log，注册/更新 macOS 定时任务
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
rs_portable_init

CFG="$ASSETS/schedule_params.log"
if [ ! -f "$CFG" ]; then
  echo "[ERROR] 缺少配置: $CFG"
  echo "请从便携包 assets/schedule_params.log 拷贝，或新建后再运行。"
  exit 1
fi

echo "[INFO] 使用配置: $CFG"
rs_run_py "$SRC/register_mac_schedule.py" --config "$CFG"
