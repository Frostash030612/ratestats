#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读写 assets 下 key=value 配置（保留注释行）。"""
from __future__ import annotations

from pathlib import Path


def load_kv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def upsert_kv(path: Path, updates: dict[str, str], *, create_header: str | None = None) -> None:
    """就地更新 key=value；已有注释保留；缺失的 key 追加在文件末尾。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        lines = []
        if create_header:
            lines.extend(create_header.rstrip().splitlines())
            lines.append("")
        for k, v in updates.items():
            lines.append(f"{k}={v}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    lines = path.read_text(encoding="utf-8").splitlines()
    done: set[str] = set()
    new_lines: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith(";") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}")
                done.add(k)
                continue
        new_lines.append(raw)
    missing = [k for k in updates if k not in done]
    if missing:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.append("# --- GUI 追加字段 ---")
        for k in missing:
            new_lines.append(f"{k}={updates[k]}")
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
