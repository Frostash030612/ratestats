"""用 Tavily AI Search 跑全量 URL 发现。"""
from __future__ import annotations

import sys
from pathlib import Path

_THIS = Path(__file__).resolve().parent
_AI_COMPARE = _THIS.parent
if str(_AI_COMPARE) not in sys.path:
    sys.path.insert(0, str(_AI_COMPARE))

from load_keys import ensure_keys_loaded  # noqa: E402

ensure_keys_loaded()

from _discovery_common import run_provider_discovery  # noqa: E402

from tavily_search_client import search_urls  # noqa: E402


def main() -> int:
    """单独跑 Tavily 全量发现，输出到 tavily/output/。"""
    import argparse

    parser = argparse.ArgumentParser(description="AI_Compare/tavily: Tavily 全量 URL 发现")
    parser.add_argument("--sleep", type=float, default=0.4)
    args = parser.parse_args()

    results = run_provider_discovery(
        provider_dir=_THIS,
        search_fn=search_urls,
        source_tag="tavily",
        sleep_sec=args.sleep,
    )
    n = sum(1 for r in results if r.source == "tavily")
    print(f"[Tavily] total={len(results)} tavily={n} fallback={len(results) - n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
