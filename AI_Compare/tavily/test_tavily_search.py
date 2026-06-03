"""单条 Tavily 搜索冒烟测试。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from load_keys import ensure_keys_loaded

ensure_keys_loaded()

from tavily_search_client import search_urls


def main() -> int:
    if not os.environ.get("TAVILY_API_KEY", "").strip():
        print("[ERROR] 请先设置环境变量 TAVILY_API_KEY。", file=sys.stderr)
        return 1
    query = "cimb singapore sgd fixed deposit rates"
    print(f"[INFO] query={query!r}")
    try:
        links = search_urls(query, page_size=5)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    print(f"[OK] 返回链接 {len(links)} 条：")
    for i, link in enumerate(links, 1):
        print(f"  {i}. {link}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
