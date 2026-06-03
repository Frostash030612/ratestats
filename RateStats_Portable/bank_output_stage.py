from __future__ import annotations

"""
可移植版本的输出阶段处理模块。

逻辑与主目录 `bank_output_stage.py` 一致，只是把 xlsx path resolver
改为 portable 目录内的实现，避免运行时路径解析差异。
"""

import json
import os
import sys
import traceback
from typing import Any, Callable, Dict, Optional

from bank_xlsx_out_resolver import resolve_xlsx_out


def run_output_stage(
    *,
    data: Dict[str, Any],
    args: Any,
    excel_writer: Callable[[Dict[str, Any], str], None],
) -> int:
    """
    执行输出阶段，并返回退出码（0 成功 / 非 0 失败）。
    """

    print("[OUTPUT] STEP 1/5 解析 Excel 输出路径...", file=sys.stderr)
    try:
        xlsx_path: Optional[str] = resolve_xlsx_out(args.xlsx_out)
        print(f"[OUTPUT] STEP 1/5 完成: xlsx_path={xlsx_path}", file=sys.stderr)
    except Exception as e:
        print(f"解析 Excel 输出路径失败：{e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1

    if xlsx_path:
        print("[OUTPUT] STEP 2/5 写入 Excel...", file=sys.stderr)
        try:
            excel_writer(data, xlsx_path)
            print("[OUTPUT] STEP 2/5 完成", file=sys.stderr)
        except Exception as e:
            print(f"写入 Excel 失败：{e}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            return 1

        print("[OUTPUT] STEP 3/5 校验 Excel 文件是否存在...", file=sys.stderr)
        try:
            if not os.path.exists(xlsx_path):
                print(f"写入 Excel 失败：文件未生成（{xlsx_path} 不存在）", file=sys.stderr)
                return 1
            print("[OUTPUT] STEP 3/5 完成", file=sys.stderr)
        except Exception as e:
            print(f"校验 Excel 文件存在失败：{e}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            return 1

        print("[OUTPUT] STEP 3.1/5 从元数据导出 url_YYYYMMDD.xlsx...", file=sys.stderr)
        try:
            from export_market_url_snapshot import export_url_snapshot_from_market

            export_url_snapshot_from_market(xlsx_path)
            print("[OUTPUT] STEP 3.1/5 完成", file=sys.stderr)
        except Exception as e:
            print(f"[URL_SNAPSHOT] 导出失败（不影响 Market 主流程）：{e}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)

    indent = 2 if getattr(args, "pretty", False) else None
    print("[OUTPUT] STEP 4/5 序列化 JSON...", file=sys.stderr)
    try:
        text = json.dumps(data, ensure_ascii=False, indent=indent)
        print("[OUTPUT] STEP 4/5 完成", file=sys.stderr)
    except Exception as e:
        print(f"JSON 序列化失败：{e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1

    json_out_path = getattr(args, "json_out", None)
    if json_out_path:
        print("[OUTPUT] STEP 4.1/5 写 JSON 文件...", file=sys.stderr)
        try:
            with open(json_out_path, "w", encoding="utf-8") as f:
                f.write(text + "\n")
            print("[OUTPUT] STEP 4.1/5 完成", file=sys.stderr)
        except Exception as e:
            print(f"写入 JSON 文件失败：{e}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            return 1

    print("[OUTPUT] STEP 5/5 输出到 stdout...", file=sys.stderr)
    try:
        emit_json_stdout = (xlsx_path is None) or getattr(args, "print_json", False)
        if emit_json_stdout:
            stdout_encoding = getattr(sys.stdout, "encoding", None)
            if stdout_encoding and stdout_encoding.lower() in ("utf-8", "utf8"):
                print(text)
            else:
                sys.stdout.buffer.write((text + "\n").encode("utf-8"))
        elif xlsx_path:
            print("Written:", xlsx_path)
        print("[OUTPUT] STEP 5/5 完成", file=sys.stderr)
    except Exception as e:
        print(f"向 stdout 输出失败：{e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return 1

    return 0


# Safety net: 自动给本模块中所有 def 加异常兜底
from bank_safety import auto_wrap_module_functions as _auto_wrap_module_functions

_auto_wrap_module_functions(globals(), module_name=__name__)

