"""Provider 通用接口。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ProviderResult:
    urls: list[str] = field(default_factory=list)
    latency_ms: int = 0
    raw: dict | None = None
    error: str = ""


class Provider(Protocol):
    name: str

    def available(self) -> bool: ...

    def search(self, query: str, page_size: int = 10) -> ProviderResult: ...
