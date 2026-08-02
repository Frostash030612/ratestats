#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
chmod +x ./sh/*.sh ./*.command 2>/dev/null || true
for f in ./sh/*.sh; do [ -f "$f" ] && sed -i '' $'s/\r$//' "$f" 2>/dev/null; done
./sh/01_首次安装依赖.sh
echo
read -r -p "按回车关闭窗口..."
