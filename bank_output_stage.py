from __future__ import annotations

"""
输出阶段处理模块。

把 `bank_all_promo_rates.py` / portable 脚本中 `main()` 的输出逻辑抽离出来：
1) 计算 `xlsx_path`（由 `--xlsx-out` 决定）
2) 写 Excel（可选）
3) 序列化 JSON（用于 `--json-out` 或 stdout）
4) 写 JSON 文件（可选）
5) 决定是否打印 JSON 到 stdout（与 `--print-json` / 是否写 xlsx 相关）

实现目标：
- 任何一步出错都不会“崩溃式抛出”，而是捕获异常并返回非 0 退出码。
- 模块函数本身包含足够的 try/except，保证稳定性。
"""

import json
import os
import sys
from typing import Any, Callable, Dict, Optional

from bank_xlsx_out_resolver import resolve_xlsx_out


def run_output_stage(
    *,
    data: Dict[str, Any],
    args: Any,
    excel_writer: Callable[[Dict[str, Any], str], None],
) -> int:
    """
    执行输出阶段，并返回退出码。

    Parameters
    ----------
    data:
        `fetch_and_extract()` 产出的 payload（同时也用于 JSON 序列化）。
    args:
        argparse 的 args 对象（包含 `xlsx_out/json_out/print_json/pretty` 等字段）。
    excel_writer:
        写 Excel 的回调函数（由主脚本提供：`write_rates_excel`）。

    Returns
    -------
    int:
        0 表示成功；非 0 表示某一步失败。
    """

    # 1) Resolve xlsx path (may be None)
    try:
        xlsx_path: Optional[str] = resolve_xlsx_out(args.xlsx_out)
    except Exception as e:
        print(f"Failed to resolve xlsx output path: {e}", file=sys.stderr)
        return 1

    # 2) Write xlsx if requested
    if xlsx_path:
        try:
            excel_writer(data, xlsx_path)
        except Exception as e:
            print(f"写入 Excel 失败：{e}", file=sys.stderr)
            return 1

        # 降级校验：即使 excel_writer 内部吞掉异常，也确保最终文件存在
        try:
            if not os.path.exists(xlsx_path):
                print(f"写入 Excel 失败：文件未生成（{xlsx_path} 不存在）", file=sys.stderr)
                return 1
        except Exception as e:
            # exists() 理论上不会抛，但为了符合“所有异常都 try/except”，这里兜底
            print(f"校验 Excel 文件存在失败：{e}", file=sys.stderr)
            return 1

    # 3) Serialize JSON (used for file write + stdout)
    indent = 2 if getattr(args, "pretty", False) else None
    try:
        text = json.dumps(data, ensure_ascii=False, indent=indent)
    except Exception as e:
        print(f"JSON 序列化失败：{e}", file=sys.stderr)
        return 1

    # 4) Optional json file write
    json_out_path = getattr(args, "json_out", None)
    if json_out_path:
        try:
            with open(json_out_path, "w", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception as e:
            print(f"写入 JSON 文件失败：{e}", file=sys.stderr)
            return 1

    # 5) Stdout emission rules
    # - If xlsx is NOT requested: always print JSON to stdout (same as old main)
    # - If xlsx requested:
    #     - print JSON only when --print-json is set
    #     - otherwise just print "Written: <path>"
    try:
        emit_json_stdout = (xlsx_path is None) or getattr(args, "print_json", False)
        if emit_json_stdout:
            # Avoid mojibake on Windows consoles that are not UTF-8.
            stdout_encoding = getattr(sys.stdout, "encoding", None)
            if stdout_encoding and stdout_encoding.lower() in ("utf-8", "utf8"):
                print(text)
            else:
                sys.stdout.buffer.write((text + "\n").encode("utf-8"))
        elif xlsx_path:
            # 保持与旧脚本的 ASCII 输出一致，避免 Windows 控制台编码问题。
            print("Written:", xlsx_path)
    except Exception as e:
        print(f"向 stdout 输出失败：{e}", file=sys.stderr)
        return 1

    return 0


# Safety net: 自动给本模块中所有 def 加异常兜底
from bank_safety import auto_wrap_module_functions as _auto_wrap_module_functions

_auto_wrap_module_functions(globals(), module_name=__name__)

