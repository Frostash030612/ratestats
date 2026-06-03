"""Vertex AI Search provider（直接调 discoveryengine REST）。

复用 RateStats_Portable/assets 下的服务账号 JSON（与现有 vertex_search_client 一致）。
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from .base import ProviderResult

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_KEY = _REPO_ROOT / "RateStats_Portable" / "assets" / "ratestatsearch-f5f95dab974f.json"


class VertexProvider:
    name = "vertex"

    def __init__(
        self,
        *,
        project: str | None = None,
        engine_id: str | None = None,
        key_file: Path | None = None,
    ) -> None:
        self.project = project or os.environ.get("GOOGLE_CLOUD_PROJECT", "ratestatsearch")
        self.engine_id = engine_id or os.environ.get(
            "VERTEX_ENGINE_ID", "ratestats-sg-links_1778827558801"
        )
        self.key_file = Path(
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", str(key_file or _DEFAULT_KEY))
        )
        self._token: str = ""

    def available(self) -> bool:
        return self.key_file.is_file()

    def _get_token(self) -> str:
        if self._token:
            return self._token
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        creds = service_account.Credentials.from_service_account_file(
            str(self.key_file), scopes=scopes
        )
        creds.refresh(Request())
        self._token = creds.token
        return self._token

    def search(self, query: str, page_size: int = 10) -> ProviderResult:
        if not self.available():
            return ProviderResult(error=f"missing key file: {self.key_file}")
        url = (
            f"https://discoveryengine.googleapis.com/v1/projects/{self.project}/locations/global/"
            f"collections/default_collection/engines/{self.engine_id}/servingConfigs/default_search:search"
        )
        body = {
            "query": query,
            "pageSize": min(max(int(page_size), 1), 25),
            "params": {"user_country_code": "sg"},
        }
        t0 = time.perf_counter()
        try:
            resp = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._get_token()}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=60,
            )
        except Exception as e:
            return ProviderResult(
                error=f"request failed: {e}",
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        if resp.status_code != 200:
            return ProviderResult(
                error=f"HTTP {resp.status_code}: {resp.text[:500]}",
                latency_ms=latency_ms,
            )
        data = resp.json()
        urls: list[str] = []
        for item in data.get("results") or []:
            doc = item.get("document") or {}
            d = doc.get("derivedStructData") or doc.get("derived_struct_data") or {}
            link = d.get("link") or d.get("uri") or d.get("url")
            if isinstance(link, str) and link.startswith("http"):
                urls.append(link.split("#")[0].rstrip())
        return ProviderResult(urls=urls, latency_ms=latency_ms, raw=data)
