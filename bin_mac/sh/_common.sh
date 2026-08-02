#!/usr/bin/env bash
# RateStats — Mac 公共环境（由 bin_mac/sh/*.sh source）
# 布局（与 assets 同级）：
#   RateStats/bin_mac/*.command  +  RateStats/bin_mac/sh/*.sh
set -euo pipefail

rs_portable_init() {
  # 本文件在 RateStats/bin_mac/sh/_common.sh
  SH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  BIN="$(cd "$SH_DIR/.." && pwd)"
  ROOT="$(cd "$BIN/.." && pwd)"
  PKG="$ROOT/RateStats_Portable"
  SRC="$PKG/src"
  DOCS="$PKG/docs"
  ASSETS="$ROOT/assets"
  export BIN SH_DIR ROOT PKG SRC ASSETS DOCS

  # launchd 定时任务的 PATH 极短，常找不到 Homebrew；先补常见路径
  export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/local/opt/python@3.12/bin:/usr/local/opt/python@3.11/bin:/opt/homebrew/opt/python@3.12/bin:/opt/homebrew/opt/python@3.11/bin:/Library/Frameworks/Python.framework/Versions/3.12/bin:/Library/Frameworks/Python.framework/Versions/3.11/bin:${PATH:-/usr/bin:/bin:/usr/sbin:/sbin}"

  # 优先带绝对路径的 3.11/3.12（有现成 wheel）；避开过新的 3.14
  PY_CMD=""
  for cand in \
    /usr/local/opt/python@3.11/bin/python3.11 \
    /opt/homebrew/opt/python@3.11/bin/python3.11 \
    /usr/local/opt/python@3.12/bin/python3.12 \
    /opt/homebrew/opt/python@3.12/bin/python3.12 \
    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 \
    /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 \
    /usr/local/bin/python3.11 \
    /usr/local/bin/python3.12 \
    /opt/homebrew/bin/python3.11 \
    /opt/homebrew/bin/python3.12 \
    python3.11 \
    python3.12 \
    python3.10 \
    python3
  do
    if [[ "$cand" == /* ]]; then
      [ -x "$cand" ] || continue
      py="$cand"
    else
      command -v "$cand" >/dev/null 2>&1 || continue
      py="$(command -v "$cand")"
    fi
    # 优先选用已安装 pandas 的解释器（定时任务尤其需要）
    if "$py" -c "import pandas" >/dev/null 2>&1; then
      PY_CMD="$py"
      break
    fi
    if [ -z "$PY_CMD" ]; then
      PY_CMD="$py"
    fi
  done
  # 若上面「先记下无 pandas 的、再找有 pandas 的」只留下无包的，再扫描一次强制找有 pandas 的
  if ! "$PY_CMD" -c "import pandas" >/dev/null 2>&1; then
    for cand in \
      /usr/local/opt/python@3.11/bin/python3.11 \
      /opt/homebrew/opt/python@3.11/bin/python3.11 \
      /usr/local/bin/python3.11 \
      /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 \
      /usr/local/opt/python@3.12/bin/python3.12 \
      python3.11 \
      python3.12 \
      python3
    do
      if [[ "$cand" == /* ]]; then
        [ -x "$cand" ] || continue
        py="$cand"
      else
        command -v "$cand" >/dev/null 2>&1 || continue
        py="$(command -v "$cand")"
      fi
      if "$py" -c "import pandas" >/dev/null 2>&1; then
        PY_CMD="$py"
        break
      fi
    done
  fi

  if [ -z "$PY_CMD" ]; then
    echo "[ERROR] 未找到 Python 3。请先安装：brew install python@3.11"
    exit 1
  fi
  export PY_CMD

  PY_VER="$("$PY_CMD" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  PY_MINOR="$("$PY_CMD" -c 'import sys; print(sys.version_info.minor)')"
  if [ "${PY_MINOR}" -ge 14 ]; then
    echo "[ERROR] 当前 Python 为 ${PY_VER}（$PY_CMD），过新。"
    echo "        cryptography / pandas 等常无现成包，需改用 3.11 或 3.12："
    echo "          brew install python@3.11"
    echo "          然后重新打开终端，再运行本脚本。"
    echo "        或从 python.org 安装 3.12，并确保 PATH 里 python3.12 / python3.11 优先于 3.14。"
    exit 1
  fi
  if ! "$PY_CMD" -c "import pandas" >/dev/null 2>&1; then
    echo "[ERROR] $PY_CMD 未安装 pandas。"
    echo "        请双击 bin_mac/01_首次安装依赖.command，或执行："
    echo "          \"$PY_CMD\" -m pip install -r \"$DOCS/requirements.txt\" --break-system-packages"
    exit 1
  fi
  echo "[PY] 使用: $PY_CMD ($PY_VER)"

  mkdir -p "$ASSETS"
  export PYTHONUTF8=1
  export LC_ALL="${LC_ALL:-en_US.UTF-8}"
  export LANG="${LANG:-en_US.UTF-8}"
}

rs_date_tags() {
  DATE_TAG="$(date +%Y%m%d)"
  RUN_TAG="$(date +%Y%m%d_%H.%M)"
  export DATE_TAG RUN_TAG
}

rs_set_runs_out_dir() {
  if [ -n "${RATESTATS_RUNS_ROOT:-}" ]; then
    RUNS_ROOT="$RATESTATS_RUNS_ROOT"
  else
    RUNS_ROOT="$(cd "$ROOT/runs" && pwd)"
  fi
  if [ -n "${BATCH_NAME:-}" ]; then
    OUT_DIR="$RUNS_ROOT/$BATCH_NAME"
  elif [ -n "${DATE_TAG:-}" ]; then
    OUT_DIR="$RUNS_ROOT/$DATE_TAG"
  else
    echo "[set_runs_out_dir] ERROR: 需要 DATE_TAG 或 BATCH_NAME"
    exit 1
  fi
  mkdir -p "$OUT_DIR"
  export RUNS_ROOT OUT_DIR
}

rs_confirm_send_mail() {
  local prompt="${1:-发送邮件?}"
  if [ -t 0 ]; then
    read -r -p "$prompt [y/N]: " reply
    case "$reply" in
      y|Y|yes|Yes|YES) return 0 ;;
      *) return 1 ;;
    esac
  fi
  return 1
}

rs_run_py() {
  # shellcheck disable=SC2068
  "$PY_CMD" "$@"
}

rs_require_tk() {
  # 图形界面：在 PATH / 常见安装路径里找「带 tkinter」的 3.10–3.13
  local cand py
  local -a cands=()
  for cand in \
    python3.12 python3.11 python3.10 python3.13 \
    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 \
    /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 \
    /usr/local/bin/python3.12 \
    /usr/local/bin/python3.11
  do
    cands+=("$cand")
  done
  if [ -n "${PY_CMD:-}" ]; then
    cands=("$PY_CMD" "${cands[@]}")
  fi

  for cand in "${cands[@]}"; do
    if [[ "$cand" == /* ]]; then
      [ -x "$cand" ] || continue
      py="$cand"
    else
      command -v "$cand" >/dev/null 2>&1 || continue
      py="$(command -v "$cand")"
    fi
    if "$py" -c "import tkinter" >/dev/null 2>&1; then
      local ver minor
      ver="$("$py" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
      minor="$("$py" -c 'import sys; print(sys.version_info.minor)')"
      if [ "${minor}" -ge 14 ]; then
        continue
      fi
      PY_CMD="$py"
      export PY_CMD
      echo "[PY] 图形界面改用带 tkinter 的: $PY_CMD ($ver)"
      return 0
    fi
  done

  echo "[ERROR] 本机没有可用的 tkinter（图形界面需要）。"
  echo
  echo "用 Homebrew 安装（你当前是 python@3.11）："
  echo "  1) /usr/local/opt/python@3.11/bin/python3.11 -m ensurepip --upgrade"
  echo "  2) /usr/local/opt/python@3.11/bin/python3.11 -m pip install --upgrade pip"
  echo "  3) brew install python-tk@3.11"
  echo "  4) python3.11 -c \"import tkinter; print('ok')\""
  echo
  echo "若第 3 步仍失败：brew reinstall python@3.11 python-tk@3.11"
  echo "临时改配置也可直接编辑 AI_Compare/keys.txt 、assets/email_params.log"
  echo
  exit 1
}

rs_fix_crlf_in_sh() {
  for f in "$SH_DIR"/*.sh; do
    [ -f "$f" ] || continue
    sed -i '' $'s/\r$//' "$f" 2>/dev/null || true
  done
}
