"""Bing Web Search v7 HTTP 客户端（已退役接口，仅供持有旧 key 的人用）。

环境变量：
- BING_API_KEY      Ocp-Apim-Subscription-Key
- BING_ENDPOINT     可选，默认 https://api.bing.microsoft.com/v7.0/search
- BING_MKT          可选，默认 en-SG
"""
from __future__ import annotations

import os
from typing import Any

import requests

DEFAULT_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"


def _api_key() -> str:
    key = os.environ.get("BING_API_KEY", "").strip()
    if not key:
        raise RuntimeError("BING_API_KEY not set")
    return key


def _endpoint() -> str:
    return os.environ.get("BING_ENDPOINT", DEFAULT_ENDPOINT).strip() or DEFAULT_ENDPOINT


def search(query: str, *, page_size: int = 8) -> dict[str, Any]:
    params = {
        "q": query,
        "count": min(max(int(page_size), 1), 50),
        "mkt": os.environ.get("BING_MKT", "en-SG"),
        "responseFilter": "Webpages",
        "safeSearch": "Moderate",
    }
    headers = {"Ocp-Apim-Subscription-Key": _api_key()}
    resp = requests.get(_endpoint(), params=params, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Bing search failed ({resp.status_code}): {resp.text[:1500]}")
    return resp.json()


def extract_links(payload: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in (payload.get("webPages") or {}).get("value") or []:
        u = item.get("url")
        if isinstance(u, str) and u.startswith("http"):
            out.append(u.split("#")[0])
    return out


def search_urls(query: str, *, page_size: int = 8) -> list[str]:
    return extract_links(search(query, page_size=page_size))
