"""Serper.dev (Google SERP proxy) HTTP 客户端。

环境变量：
- SERPER_API_KEY     必填
- SERPER_GL          可选，地区，默认 sg
- SERPER_HL          可选，语言，默认 en
"""
from __future__ import annotations

import os
from typing import Any

import requests

ENDPOINT = "https://google.serper.dev/search"


def _api_key() -> str:
    """从环境变量读取 Serper API Key，未设置则抛错。"""
    key = os.environ.get("SERPER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("SERPER_API_KEY not set")
    return key


def search(query: str, *, page_size: int = 8) -> dict[str, Any]:
    """POST google.serper.dev/search，返回原始 JSON。"""
    body = {
        "q": query,
        "num": min(max(int(page_size), 1), 20),
        "gl": os.environ.get("SERPER_GL", "sg"),
        "hl": os.environ.get("SERPER_HL", "en"),
    }
    headers = {"X-API-KEY": _api_key(), "Content-Type": "application/json"}
    resp = requests.post(ENDPOINT, json=body, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Serper search failed ({resp.status_code}): {resp.text[:1500]}")
    return resp.json()


def extract_links(payload: dict[str, Any]) -> list[str]:
    """从 Serper 响应 organic 结果提取链接。"""
    out: list[str] = []
    for item in payload.get("organic") or []:
        u = item.get("link")
        if isinstance(u, str) and u.startswith("http"):
            out.append(u.split("#")[0])
    return out


def search_urls(query: str, *, page_size: int = 8) -> list[str]:
    """发现流程入口：搜索并直接返回 URL 列表（供 discover_all 调用）。"""
    return extract_links(search(query, page_size=page_size))
