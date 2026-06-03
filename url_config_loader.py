from __future__ import annotations

"""
URL 配置加载模块。

作用：把用户维护的 `url_params.xlsx` / `url_params.json` 解析成
`Dict[argparse_dest, url]`，并支持：
1) path 传目录时自动寻找 `url_params.xlsx` / `url_params.json`；
2) 缺省时使用脚本同目录下的 `assets/url_params.xlsx`，找不到则用 json；
3) 解析时支持用户在 Excel/JSON 中使用“友好 key”，并映射到脚本里 argparse 的 dest；
4) 对写不认识/不在白名单的 dest 做过滤，避免配置表里出现多余字段导致污染。
"""

import json
import os
from typing import Dict, Optional

import pandas as pd

from url_key_aliases import URL_KEY_ALIASES, URL_PARAM_DEST_KEYS

# 基于当前模块所在目录计算资源路径。
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_URL_CONFIG = os.path.join(_SCRIPT_DIR, "assets", "url_params.xlsx")
FALLBACK_URL_CONFIG_JSON = os.path.join(_SCRIPT_DIR, "assets", "url_params.json")


def load_url_config(path: Optional[str]) -> Dict[str, str]:
    """
    读取 URL 配置并转换为 `argparse_dest -> url` 的字典。

    参数：
        path:
            - None/空：使用内置 DEFAULT（xlsx 优先，json 回退）
            - 字符串：
                - 如果是目录：尝试该目录下的 `url_params.xlsx`，没有则 `url_params.json`
                - 如果是文件路径：按文件扩展名解析（xlsx/xls* 或 json）

    返回：
        只包含 dest 白名单里的键；若配置文件缺失/解析失败/内容为空，则返回空 dict。
    """
    try:
        # 允许用户传“目录”，脚本会自动在目录内找默认文件名。
        if path and os.path.isdir(path):
            cand_xlsx = os.path.join(path, "url_params.xlsx")
            cand_json = os.path.join(path, "url_params.json")
            path = cand_xlsx if os.path.exists(cand_xlsx) else cand_json

        # 缺省或指定路径不存在：回退到脚本内置 assets 里的默认文件。
        if not path or not os.path.exists(path):
            if os.path.exists(DEFAULT_URL_CONFIG):
                path = DEFAULT_URL_CONFIG
            elif os.path.exists(FALLBACK_URL_CONFIG_JSON):
                path = FALLBACK_URL_CONFIG_JSON
            else:
                return {}

        ext = os.path.splitext(path)[1].lower()

        # 1) Excel 格式解析：期望表格列包含 key/url（允许中英文列名别名）。
        if ext in (".xlsx", ".xlsm", ".xls"):
            df = pd.read_excel(path, dtype=str)
            if df is None or df.empty:
                return {}

            # 兼容用户可能把列名写成中英文/不同同义词。
            cols_lower = [str(c).strip().lower() for c in df.columns]
            key_col = None
            url_col = None
            for i, c in enumerate(cols_lower):
                if c in ("key", "键", "参数", "param"):
                    key_col = df.columns[i]
                if c in ("url", "链接", "地址"):
                    url_col = df.columns[i]

            # 若未识别到列名，就退化为：第 1 列 key，第 2 列 url（若列数不足则退化为第 1 列）。
            if key_col is None:
                key_col = df.columns[0]
            if url_col is None:
                url_col = df.columns[1] if len(df.columns) >= 2 else df.columns[0]

            out: Dict[str, str] = {}
            for _, row in df.iterrows():
                k = str(row.get(key_col, "") or "").strip()
                v = str(row.get(url_col, "") or "").strip()
                if not k or not v:
                    continue

                # 将用户写的“友好 key”映射成 argparse dest；否则直接把原始 key 当 dest。
                dest = URL_KEY_ALIASES.get(k, k)
                # 只保留脚本实际会使用的 dest，避免无关字段污染 defaults。
                if dest in URL_PARAM_DEST_KEYS:
                    out[dest] = v
            return out

        # 2) JSON 格式解析：期望 dict[str, str]
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        if isinstance(raw, dict):
            out: Dict[str, str] = {}
            for k, v in raw.items():
                if v is None:
                    continue
                kk = str(k).strip()
                dest = URL_KEY_ALIASES.get(kk, kk)
                if dest in URL_PARAM_DEST_KEYS:
                    out[dest] = str(v)
            return out

    except Exception:
        # 任何解析异常都回退为空 dict（上层会用内置 defaults）。
        return {}

    return {}


# Safety net: 自动给本模块中所有 def 加异常兜底
from bank_safety import auto_wrap_module_functions as _auto_wrap_module_functions

_auto_wrap_module_functions(globals(), module_name=__name__)

