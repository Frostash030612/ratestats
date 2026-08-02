#!/usr/bin/env bash
# 打开 API Key 配置界面（与邮件/定时界面分开）
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
rs_portable_init
rs_require_tk
rs_run_py "$SRC/keys_gui.py"
