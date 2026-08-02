#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
rs_portable_init

echo "[CHECK] Vertex 环境与密钥"
# 密钥、项目 ID、引擎 ID 由 API 配置界面保存，测试脚本统一读取。
rs_run_py "$SRC/test_vertex_search.py"
