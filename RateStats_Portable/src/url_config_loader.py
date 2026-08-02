from __future__ import annotations

"""
可移植版本的 URL 配置加载模块。

逻辑与主目录 `url_config_loader.py` 保持一致，但单独放一份以保证：
1) 在 `RateStats_Portable` 内独立运行时仍可找到本目录下的 `assets/url_params.*`；
2) 避免运行时修改 sys.path 带来的环境依赖。
"""

import json
import os
import sys
import traceback
from typing import Dict, Optional

import pandas as pd

from url_key_aliases import URL_KEY_ALIASES, URL_PARAM_DEST_KEYS

from project_paths import ASSETS_DIR

DEFAULT_URL_CONFIG = str(ASSETS_DIR / "url_params.xlsx")
FALLBACK_URL_CONFIG_JSON = str(ASSETS_DIR / "url_params.json")


def load_url_config(path: Optional[str]) -> Dict[str, str]:
    """
    读取 URL 配置并转换为 `argparse_dest -> url` 的字典。

    这是可移植目录版本的实现：逻辑与主目录完全一致，但仍保留完善注释，便于你在
    不同机器/不同目录结构下维护配置文件时快速定位问题。
    """
    try:
        # 允许用户传“目录”，脚本会自动在目录内找默认文件名。
        if path and os.path.isdir(path):
            cand_xlsx = os.path.join(path, "url_params.xlsx")
            cand_json = os.path.join(path, "url_params.json")
            path = cand_xlsx if os.path.exists(cand_xlsx) else cand_json

        # 缺省或指定路径不存在：回退到本目录下的 assets 默认文件。
        if not path or not os.path.exists(path):
            if os.path.exists(DEFAULT_URL_CONFIG):
                path = DEFAULT_URL_CONFIG
            elif os.path.exists(FALLBACK_URL_CONFIG_JSON):
                path = FALLBACK_URL_CONFIG_JSON
            else:
                return {}

        ext = os.path.splitext(path)[1].lower()

        # Excel：解析成两列表（key/url），并对 dest 做友好映射 + 白名单过滤。
        if ext in (".xlsx", ".xlsm", ".xls"):
            df = pd.read_excel(path, dtype=str)
            if df is None or df.empty:
                return {}

            cols_lower = [str(c).strip().lower() for c in df.columns]
            key_col = None
            url_col = None
            for i, c in enumerate(cols_lower):
                if c in ("key", "键", "参数", "param"):
                    key_col = df.columns[i]
                if c in ("url", "链接", "地址"):
                    url_col = df.columns[i]

            if key_col is None:
                key_col = df.columns[0]
            if url_col is None:
                url_col = df.columns[1] if len(df.columns) >= 2 else df.columns[0]

            # 遍历每行，把用户写入的友好 key -> argparse dest，并过滤不支持的 dest。
            out: Dict[str, str] = {}
            for _, row in df.iterrows():
                k = str(row.get(key_col, "") or "").strip()
                v = str(row.get(url_col, "") or "").strip()
                if not k or not v:
                    continue
                dest = URL_KEY_ALIASES.get(k, k)
                if dest in URL_PARAM_DEST_KEYS:
                    out[dest] = v
            return out

        # JSON：期望是 dict[str, str]，同样做友好 key 映射 + 白名单过滤。
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

    except Exception as e:
        # 解析异常直接回退空 dict，上层会用脚本内置 defaults。
        print(f"[PARAM] load_url_config 失败：{e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return {}

    return {}


# Safety net: 自动给本模块中所有 def 加异常兜底
from bank_safety import auto_wrap_module_functions as _auto_wrap_module_functions

_auto_wrap_module_functions(globals(), module_name=__name__)

