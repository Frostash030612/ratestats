"""AI 发现链接：全局模式（宽松默认，利于银行改版）。"""
from __future__ import annotations

import os

# relaxed | strict
_DEFAULT_MODE = "relaxed"


def get_intent_mode() -> str:
    """读取当前选链模式：环境变量 RATESTATS_INTENT_MODE，默认 relaxed。"""
    m = (os.environ.get("RATESTATS_INTENT_MODE") or _DEFAULT_MODE).strip().lower()
    return m if m in ("relaxed", "strict") else _DEFAULT_MODE


def is_relaxed_mode() -> bool:
    """是否为宽松模式（软加分 + 少量硬拒绝，便于适应银行改版）。"""
    return get_intent_mode() == "relaxed"
