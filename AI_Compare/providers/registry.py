"""Provider 注册表与自动检测。"""
from __future__ import annotations

from typing import Type

from .base import Provider
from .bing import BingProvider
from .brave import BraveProvider
from .serper import SerperProvider
from .tavily import TavilyProvider
from .vertex import VertexProvider

# 评测顺序：Vertex 优先，其余按「易获取 / 常用」排列
ALL_PROVIDER_NAMES: tuple[str, ...] = ("vertex", "serper", "brave", "tavily", "bing")

PROVIDER_CLASSES: dict[str, Type[Provider]] = {
    "vertex": VertexProvider,
    "serper": SerperProvider,
    "brave": BraveProvider,
    "tavily": TavilyProvider,
    "bing": BingProvider,
}


def instantiate(name: str) -> Provider | None:
    cls = PROVIDER_CLASSES.get(name)
    if cls is None:
        return None
    return cls()


def detect_available(*, verbose: bool = True) -> list[str]:
    """返回所有已配置且可用的 provider 名称（保持 ALL_PROVIDER_NAMES 顺序）。"""
    found: list[str] = []
    for name in ALL_PROVIDER_NAMES:
        prov = instantiate(name)
        if prov is None:
            continue
        if prov.available():
            found.append(name)
            if verbose:
                print(f"  [OK] {name}")
        elif verbose:
            print(f"  [--] {name}  （未配置，跳过）")
    return found


def env_hint(name: str) -> str:
    hints = {
        "vertex": "GOOGLE_APPLICATION_CREDENTIALS 或 RateStats_Portable/assets/*.json",
        "serper": "SERPER_API_KEY",
        "brave": "BRAVE_API_KEY",
        "tavily": "TAVILY_API_KEY",
        "bing": "BING_API_KEY（旧 API 已退役，一般无法新申请）",
    }
    return hints.get(name, "")
