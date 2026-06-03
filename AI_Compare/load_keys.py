"""从本地 keys.txt / keys.env 加载 API Key 到当前进程环境变量。

不把 Key 写进 Windows 系统环境变量时，用本模块即可。
文件应放在 AI_Compare 目录下，且不要提交到 Git。

支持格式（每行一条）：
  SERPER_API_KEY=你的key
  # 井号开头为注释
  BRAVE_API_KEY=xxx

已存在的环境变量不会被覆盖（便于临时覆盖测试）。
"""
from __future__ import annotations

import os
from pathlib import Path

_AI_COMPARE = Path(__file__).resolve().parent
_KEY_FILENAMES = ("keys.txt", "keys.env")


def _parse_line(line: str) -> tuple[str, str] | None:
    """解析 keys.txt 一行 KEY=VALUE；注释或空行返回 None。"""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if "=" not in line:
        return None
    key, _, value = line.partition("=")
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    if not key:
        return None
    return key, value


def load_keys_from_file(path: Path, *, overwrite: bool = False) -> int:
    """加载单个文件，返回写入的变量个数。"""
    if not path.is_file():
        return 0
    count = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_line(raw)
        if parsed is None:
            continue
        key, value = parsed
        if not value:
            continue
        if not overwrite and os.environ.get(key, "").strip():
            continue
        os.environ[key] = value
        count += 1
    return count


def ensure_keys_loaded(*, base_dir: Path | None = None, verbose: bool = False) -> Path | None:
    """按顺序尝试 keys.txt、keys.env，返回实际使用的文件路径；都没有则返回 None。"""
    base = base_dir or _AI_COMPARE
    for name in _KEY_FILENAMES:
        path = base / name
        n = load_keys_from_file(path)
        if n > 0:
            if verbose:
                print(f"[load_keys] 已从 {path.name} 加载 {n} 个变量")
            return path
    if verbose:
        print("[load_keys] 未找到 keys.txt / keys.env（可复制 keys.txt.example）")
    return None


def main() -> int:
    """命令行：加载 keys 并打印已设置的环境变量名（不打印值）。"""
    import argparse

    p = argparse.ArgumentParser(description="从 keys.txt 加载 API Key 到当前进程")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()
    path = ensure_keys_loaded(verbose=args.verbose or True)
    if path is None:
        print("未找到 keys.txt 或 keys.env")
        return 1
    # 只打印变量名，不打印值
    for name in _KEY_FILENAMES:
        fp = _AI_COMPARE / name
        if fp == path:
            for raw in fp.read_text(encoding="utf-8").splitlines():
                parsed = _parse_line(raw)
                if parsed and parsed[1] and os.environ.get(parsed[0]):
                    print(f"  OK  {parsed[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
