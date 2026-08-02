#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
chmod +x ./sh/*.sh ./*.command 2>/dev/null || true
for f in ./sh/*.sh; do [ -f "$f" ] && sed -i '' $'s/\r$//' "$f" 2>/dev/null; done
exec ./sh/打开API钥匙设置.sh
