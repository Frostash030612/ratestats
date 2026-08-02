#!/usr/bin/env bash
# 兼容旧入口：改为调用「注册定时任务.sh」（读取 assets/schedule_params.log）
set -euo pipefail
SH_DIR="$(cd "$(dirname "$0")" && pwd)"
exec bash "$SH_DIR/注册定时任务.sh"
