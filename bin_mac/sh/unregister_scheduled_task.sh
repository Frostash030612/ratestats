#!/usr/bin/env bash
set -euo pipefail
SH_DIR="$(cd "$(dirname "$0")" && pwd)"
exec bash "$SH_DIR/卸载定时任务.sh"
