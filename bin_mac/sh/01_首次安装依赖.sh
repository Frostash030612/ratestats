#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=_common.sh
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
rs_portable_init

echo "[1/5] 升级 pip..."
"$PY_CMD" -m pip install --upgrade pip

echo "[2/5] RateStats_Portable 依赖..."
"$PY_CMD" -m pip install -r "$DOCS/requirements.txt"

echo "[3/5] RateStats_ML 依赖..."
"$PY_CMD" -m pip install -r "$ROOT/RateStats_ML/requirements.txt"

echo "[4/5] AI_Compare 依赖..."
"$PY_CMD" -m pip install -r "$ROOT/AI_Compare/requirements.txt"

echo "[5/5] curl_cffi（部分银行站点 TLS 模拟）..."
"$PY_CMD" -m pip install "curl_cffi>=0.7.0"

cat <<'EOF'

全部依赖安装完成（手动 / Vertex AI / ML 选链）。

常用入口：
  双击 bin_mac 目录下的 *.command（推荐）
  或进入 bin_mac/sh 运行对应 .sh

EOF
