"""Brave Search provider（stub：需要 BRAVE_API_KEY）。

文档：https://api.search.brave.com/app/documentation/web-search/get-started
"""
from __future__ import annotations

import os
import time

import requests

from .base import ProviderResult


class BraveProvider:
    name = "brave"
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, *, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("BRAVE_API_KEY", "").strip()

    def available(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, page_size: int = 10) -> ProviderResult:
        if not self.available():
            return ProviderResult(error="BRAVE_API_KEY not set")
        params = {
            "q": query,
            "count": min(max(int(page_size), 1), 20),
            "country": os.environ.get("BRAVE_COUNTRY", "ALL").upper(),
        }
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        t0 = time.perf_counter()
        try:
            r = requests.get(self.endpoint, params=params, headers=headers, timeout=30)
        except Exception as e:
            return ProviderResult(
                error=f"request failed: {e}",
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code != 200:
            return ProviderResult(error=f"HTTP {r.status_code}: {r.text[:500]}", latency_ms=latency_ms)
        data = r.json()
        urls: list[str] = []
        for item in (data.get("web") or {}).get("results") or []:
            u = item.get("url")
            if isinstance(u, str) and u.startswith("http"):
                urls.append(u.split("#")[0])
        return ProviderResult(urls=urls, latency_ms=latency_ms, raw=data)
