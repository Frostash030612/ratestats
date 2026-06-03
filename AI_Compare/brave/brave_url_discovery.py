"""用 Brave Search 跑全量 URL 发现。"""
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

from brave_search_client import search_urls  # noqa: E402


def main() -> int:
    """单独跑 Brave 全量发现，输出到 brave/output/（默认 sleep 1.1s 防限流）。"""
    import argparse

    parser = argparse.ArgumentParser(description="AI_Compare/brave: Brave 全量 URL 发现")
    # 免费档限 1 req/s，所以默认 sleep 提到 1.1s。
    parser.add_argument("--sleep", type=float, default=1.1)
    args = parser.parse_args()

    results = run_provider_discovery(
        provider_dir=_THIS,
        search_fn=search_urls,
        source_tag="brave",
        sleep_sec=args.sleep,
    )
    n = sum(1 for r in results if r.source == "brave")
    print(f"[Brave] total={len(results)} brave={n} fallback={len(results) - n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
