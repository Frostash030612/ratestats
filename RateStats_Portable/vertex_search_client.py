"""Vertex AI Search (Discovery Engine) HTTP client for RateStats."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

_SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_KEY_FILE = _SCRIPT_DIR / "assets" / "ratestatsearch-f5f95dab974f.json"

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "ratestatsearch")
APP_ID = os.environ.get("VERTEX_ENGINE_ID", "ratestats-sg-links_1778827558801")


def _key_file() -> Path:
    """解析 Vertex 服务账号 JSON 路径（环境变量或 assets 默认文件）。"""
    return Path(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", DEFAULT_KEY_FILE))


def get_access_token() -> str:
    """用服务账号刷新并返回 Google Cloud OAuth2 access token。"""
    key_file = _key_file()
    if not key_file.is_file():
        raise FileNotFoundError(f"Service account key not found: {key_file}")
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    creds = service_account.Credentials.from_service_account_file(str(key_file), scopes=scopes)
    creds.refresh(Request())
    return creds.token


def search_url(query: str, *, page_size: int = 8) -> dict[str, Any]:
    """调用 Vertex AI Search (Discovery Engine) API，返回原始 JSON 响应。"""
    token = get_access_token()
    url = (
        f"https://discoveryengine.googleapis.com/v1/projects/{PROJECT}/locations/global/"
        f"collections/default_collection/engines/{APP_ID}/servingConfigs/default_search:search"
    )
    body = {
        "query": query,
        "pageSize": page_size,
        "params": {"user_country_code": "sg"},
    }
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Vertex search failed ({resp.status_code}): {resp.text[:1500]}")
    return resp.json()


def extract_links(payload: dict[str, Any]) -> list[str]:
    """从 Vertex 搜索响应中解析 http(s) 链接列表（去 fragment）。"""
    links: list[str] = []
    for item in payload.get("results") or []:
        doc = item.get("document") or {}
        data = doc.get("derivedStructData") or doc.get("derived_struct_data") or {}
        link = data.get("link") or data.get("uri") or data.get("url")
        if isinstance(link, str) and link.startswith("http"):
            links.append(link.split("#")[0].rstrip())
    return links
