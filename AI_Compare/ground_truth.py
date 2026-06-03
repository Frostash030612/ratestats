"""读取评测黄金答案：优先 url_YYYYMMDD.xlsx（当次 Market 元数据快照），否则 url_params.json。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_RATESTATS = _THIS_DIR.parent / "RateStats_Portable"
DEFAULT_GOLD_JSON = _RATESTATS / "assets" / "url_params.json"


def _load_via_portable_loader(path: Path) -> dict[str, str]:
    """通过 RateStats_Portable 的 url_config_loader 读取 xlsx → dest→url。"""
    portable = str(_RATESTATS)
    if portable not in sys.path:
        sys.path.insert(0, portable)
    from url_config_loader import load_url_config  # noqa: E402

    return load_url_config(str(path))


def load_gold_from_json(path: Path) -> dict[str, str]:
    """从 url_params.json 读取 dest→url 黄金答案。"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {str(k): str(v) for k, v in data.items() if isinstance(v, str) and v.strip()}


def load_gold(path: Path | str | None = None) -> dict[str, str]:
    """
    返回 dest -> url。

    path 可为：
    - url_YYYYMMDD.xlsx / url_params.xlsx（经 url_config_loader 解析为 dest）
    - url_params.json（已是 dest 键）
    """
    if path is None:
        raise FileNotFoundError("未指定黄金答案路径")

    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"未找到黄金答案文件：{p}")

    ext = p.suffix.lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        cfg = _load_via_portable_loader(p)
        if not cfg:
            raise ValueError(f"无法从 {p} 解析 URL 配置")
        return cfg
    return load_gold_from_json(p)


def find_latest_url_snapshot(search_root: Path | None = None) -> Path | None:
    """在目录树中查找最新 url_YYYYMMDD.xlsx（手动 Market 导出的黄金 URL）。"""
    root = search_root or _RATESTATS
    if not root.is_dir():
        return None
    candidates: list[tuple[str, Path]] = []
    pat = re.compile(r"^url_(\d{8})\.xlsx$", re.I)
    for p in root.rglob("url_*.xlsx"):
        m = pat.match(p.name)
        if m:
            candidates.append((m.group(1), p))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def resolve_gold_path(
    explicit: Path | str | None = None,
    *,
    prefer_snapshot: bool = True,
) -> Path:
    """
    解析黄金答案路径。

    explicit:
      - None + prefer_snapshot=True → 最新 url_YYYYMMDD.xlsx，否则 assets/url_params.json
      - "auto" → 同上
      - 具体路径 → 使用该文件
    """
    if explicit is not None and str(explicit).strip().lower() not in ("", "auto"):
        p = Path(explicit)
        if not p.is_file():
            raise FileNotFoundError(f"未找到黄金答案：{p}")
        return p

    if prefer_snapshot:
        snap = find_latest_url_snapshot()
        if snap is not None:
            return snap

    if DEFAULT_GOLD_JSON.is_file():
        return DEFAULT_GOLD_JSON

    raise FileNotFoundError(
        "未找到黄金答案：请先生成 MarketRateData（会自动产出 url_YYYYMMDD.xlsx），"
        f"或保留 {_RATESTATS / 'assets' / 'url_params.json'}"
    )
