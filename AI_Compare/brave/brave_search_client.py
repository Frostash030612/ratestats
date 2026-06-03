"""Brave Search HTTP 客户端。

环境变量：
- BRAVE_API_KEY      必填（X-Subscription-Token）
- BRAVE_COUNTRY      可选，默认 sg
"""
from __future__ import annotations

import os
from typing import Any

import requests

ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


def _api_key() -> str:
    """从环境变量读取 Brave API Key（X-Subscription-Token）。"""
    key = os.environ.get("BRAVE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("BRAVE_API_KEY not set")
    return key


def search(query: str, *, page_size: int = 8) -> dict[str, Any]:
    """GET Brave Web Search API，返回原始 JSON。"""
    params = {
        "q": query,
        "count": min(max(int(page_size), 1), 20),
        # Brave API 无 SG，用 ALL；可设 BRAVE_COUNTRY=MY 等邻近市场
        "country": os.environ.get("BRAVE_COUNTRY", "ALL").upper(),
        "safesearch": "moderate",
    }
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": _api_key(),
    }
    resp = requests.get(ENDPOINT, params=params, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Brave search failed ({resp.status_code}): {resp.text[:1500]}")
    return resp.json()


def extract_links(payload: dict[str, Any]) -> list[str]:
    """从 Brave 响应 web.results 提取链接。"""
    out: list[str] = []
    for item in (payload.get("web") or {}).get("results") or []:
        u = item.get("url")
        if isinstance(u, str) and u.startswith("http"):
            out.append(u.split("#")[0])
    return out


def search_urls(query: str, *, page_size: int = 8) -> list[str]:
    """发现流程入口：搜索并返回 URL 列表。"""
    return extract_links(search(query, page_size=page_size))
