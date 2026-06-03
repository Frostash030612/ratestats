"""Tavily AI Search HTTP 客户端。

环境变量：
- TAVILY_API_KEY    必填（tvly-xxx）
- TAVILY_DEPTH      可选，basic 或 advanced，默认 basic
"""
from __future__ import annotations

import os
from typing import Any

import requests

ENDPOINT = "https://api.tavily.com/search"


def _api_key() -> str:
    """从环境变量读取 Tavily API Key。"""
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("TAVILY_API_KEY not set")
    return key


def search(query: str, *, page_size: int = 8) -> dict[str, Any]:
    """POST api.tavily.com/search，返回原始 JSON。"""
    body = {
        "api_key": _api_key(),
        "query": query,
        "search_depth": os.environ.get("TAVILY_DEPTH", "basic"),
        "max_results": min(max(int(page_size), 1), 20),
        "include_answer": False,
        "include_raw_content": False,
    }
    resp = requests.post(ENDPOINT, json=body, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Tavily search failed ({resp.status_code}): {resp.text[:1500]}")
    return resp.json()


def extract_links(payload: dict[str, Any]) -> list[str]:
    """从 Tavily 响应 results 提取 url 字段。"""
    out: list[str] = []
    for item in payload.get("results") or []:
        u = item.get("url")
        if isinstance(u, str) and u.startswith("http"):
            out.append(u.split("#")[0])
    return out


def search_urls(query: str, *, page_size: int = 8) -> list[str]:
    """发现流程入口：搜索并返回 URL 列表。"""
    return extract_links(search(query, page_size=page_size))
