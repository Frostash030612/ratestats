from __future__ import annotations

"""
CLI 参数覆盖辅助模块。

该模块的唯一职责是：把外部配置（`url_params.xlsx/json`）映射到 argparse
解析后的 `args` 上，并严格遵守“命令行显式传参优先”的规则。

核心策略：
- 在 main() 中先为每个 URL dest 构建 `url_defaults`（dest -> 脚本内置默认值）
- 再加载外部 `url_config`（dest -> URL）
- 对于每个 dest：
  - 如果 `args.dest` 仍等于脚本内置默认值，说明用户没有显式改动它
  - 此时才用外部配置覆盖
  - 否则（用户显式传了值，或至少 args != default_val）就保持不动
"""

from typing import Any, Mapping

from bank_safety import safe_call


@safe_call(
    context="应用 URL 配置到 argparse args",
    default_value=None,
)
def apply_url_config_defaults(
    args: Any,
    url_config: Mapping[str, str],
    url_defaults: Mapping[str, str],
) -> None:
    """
    把 `url_config` 里的 URL 应用到 argparse 的 `args` 对象上。

    参数：
        args:
            argparse parse_args 得到的对象（包含大量 URL_* / *_url / *_board_url dest）。
        url_config:
            外部配置解析后的结果（dest -> url 字符串）。
        url_defaults:
            每个 dest 对应的脚本内置默认值（用于判断“是否被命令行覆盖”）。

    逻辑：
        对于每个 dest：
        1) 如果 url_config 中没有该 dest，跳过
        2) 如果 getattr(args, dest) 仍等于 url_defaults[dest]，
           视为用户未显式传参，则用 url_config[dest] 覆盖到 args
        3) 否则保持 args 不变（命令行显式传参优先）

    返回：
        None（直接就地修改 args）。
    """
    for dest, default_val in url_defaults.items():
        # 只遍历我们“关心并可能被覆盖”的 dest 集合；避免 url_config 里出现未知字段时误覆盖。
        if dest not in url_config:
            continue

        # 当前 args.dest 的值：如果等于内置默认值，说明用户没有通过命令行显式改它。
        current_val = getattr(args, dest, None)
        if current_val == default_val:
            # 只有在“未显式覆盖”的情况下，才把外部配置写回到 args（保证 CLI 优先级）。
            # 仅当当前值等于内置默认值，才认为是“未显式传参”，可以安全覆盖。
            setattr(args, dest, url_config[dest])


# Safety net: 自动给本模块中所有 def 加异常兜底
from bank_safety import auto_wrap_module_functions as _auto_wrap_module_functions

_auto_wrap_module_functions(globals(), module_name=__name__)

