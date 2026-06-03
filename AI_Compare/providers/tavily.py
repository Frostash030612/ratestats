"""Tavily AI Search provider（需要 TAVILY_API_KEY）。

文档：https://docs.tavily.com/
"""
from __future__ import annotations

import os
import time

import requests

from .base import ProviderResult


class TavilyProvider:
    name = "tavily"
    endpoint = "https://api.tavily.com/search"

    def __init__(self, *, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY", "").strip()

    def available(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, page_size: int = 10) -> ProviderResult:
        if not self.available():
            return ProviderResult(error="TAVILY_API_KEY not set")
        body = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": os.environ.get("TAVILY_DEPTH", "basic"),
            "max_results": min(max(int(page_size), 1), 20),
            "include_answer": False,
            "include_raw_content": False,
        }
        t0 = time.perf_counter()
        try:
            r = requests.post(self.endpoint, json=body, timeout=30)
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
        for item in data.get("results") or []:
            u = item.get("url")
            if isinstance(u, str) and u.startswith("http"):
                urls.append(u.split("#")[0])
        return ProviderResult(urls=urls, latency_ms=latency_ms, raw=data)
