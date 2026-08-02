#!/usr/bin/env bash
# Finder 双击入口：调用 sh/ 下同名脚本
cd "$(dirname "$0")" || exit 1
chmod +x ./sh/*.sh ./sh/*.command 2>/dev/null || true
chmod +x ./*.command 2>/dev/null || true
for f in ./sh/*.sh; do
  [ -f "$f" ] || continue
  sed -i '' $'s/\r$//' "$f" 2>/dev/null || true
done
exec ./sh/打开配置界面.sh
