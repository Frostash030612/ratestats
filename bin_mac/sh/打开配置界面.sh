#!/usr/bin/env bash
# 打开 RateStats 可视化配置界面（邮件 + 定时）
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
rs_portable_init
rs_require_tk
rs_run_py "$SRC/config_gui.py"
