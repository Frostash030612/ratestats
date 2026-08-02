"""One-off: test Vertex AI Search (Discovery Engine) API with a service account key."""
from __future__ import annotations

import json
import os
import sys

from vertex_search_client import APP_ID, PROJECT, _key_file, extract_links, search_url


def main() -> int:
    key_file = _key_file()
    if not key_file.is_file():
        print(f"[ERROR] Service account key not found: {key_file}", file=sys.stderr)
        return 1

    print(f"[INFO] project={PROJECT} engine={APP_ID}")
    try:
        data = search_url("cimb sgd fixed deposit rates", page_size=3)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    links = extract_links(data)
    print(f"[OK] results={len(data.get('results') or [])} links_extracted={len(links)}")
    for i, link in enumerate(links, 1):
        print(f"  {i}. {link}")

    # Optional: dump JSON for field inspection (ASCII-safe on Windows console)
    if os.environ.get("VERTEX_DUMP_JSON", "").strip() in ("1", "true", "yes"):
        snippet = json.dumps(data, indent=2, ensure_ascii=True)[:3500]
        print("\n--- response (first 3500 chars, ASCII) ---")
        print(snippet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
