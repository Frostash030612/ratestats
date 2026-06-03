"""One-off: test Vertex AI Search (Discovery Engine) API with a service account key."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

_SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_KEY_FILE = _SCRIPT_DIR / "assets" / "ratestatsearch-f5f95dab974f.json"

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "ratestatsearch")
APP_ID = os.environ.get("VERTEX_ENGINE_ID", "ratestats-sg-links_1778827558801")
KEY_FILE = Path(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", DEFAULT_KEY_FILE))


def _extract_links(payload: dict) -> list[str]:
    links: list[str] = []
    for item in payload.get("results") or []:
        doc = item.get("document") or {}
        data = doc.get("derivedStructData") or doc.get("derived_struct_data") or {}
        link = data.get("link") or data.get("uri") or data.get("url")
        if isinstance(link, str) and link.startswith("http"):
            links.append(link)
    return links


def main() -> int:
    if not KEY_FILE.is_file():
        print(f"[ERROR] Service account key not found: {KEY_FILE}", file=sys.stderr)
        return 1

    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    creds = service_account.Credentials.from_service_account_file(str(KEY_FILE), scopes=scopes)
    creds.refresh(Request())
    token = creds.token

    url = (
        f"https://discoveryengine.googleapis.com/v1/projects/{PROJECT}/locations/global/"
        f"collections/default_collection/engines/{APP_ID}/servingConfigs/default_search:search"
    )
    body = {"query": "cimb sgd fixed deposit rates", "pageSize": 3}

    print(f"[INFO] project={PROJECT} engine={APP_ID}")
    print(f"[INFO] POST {url}")

    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
        timeout=60,
    )
    print(f"[INFO] status={resp.status_code}")

    try:
        data = resp.json()
    except json.JSONDecodeError:
        print(resp.text[:2000])
        return 1

    if resp.status_code != 200:
        print(json.dumps(data, indent=2, ensure_ascii=False)[:4000])
        return 1

    links = _extract_links(data)
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
