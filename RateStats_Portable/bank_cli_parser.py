from __future__ import annotations

"""
可移植版本：CLI 参数解析模块（RateStats_Portable/bank_all_promo_rates.py 用）。

该模块与主目录 `bank_cli_parser.py` 保持一致，目的只是确保在 portable 目录独立运行时
也能正确定位到 portable 版本的 `url_config_loader.DEFAULT_URL_CONFIG`。
"""

import argparse
from typing import List, Optional

from bank_safety import auto_wrap_module_functions, safe_call
from url_config_loader import DEFAULT_URL_CONFIG
from url_sources import (
    DEFAULT_URL,
    DEFAULT_CIMB_FCY_URL,
    DEFAULT_CIMB_SGD_URL,
    DEFAULT_HL_FD_URL,
    DEFAULT_HLF_FD_URL,
    DEFAULT_HSBC_TD_URL,
    DEFAULT_ICBC_FD_URL,
    DEFAULT_OCBC_FD_URL,
    DEFAULT_RHB_FD_URL,
    DEFAULT_RHB_FCY_FD_URL,
    DEFAULT_SCB_SGD_TD_URL,
    DEFAULT_SCB_FCY_FD_URL,
    DEFAULT_SIF_FD_URL,
    DEFAULT_SBI_SGD_PROMO_URL,
    DEFAULT_SBI_USD_PROMO_URL,
    DEFAULT_UOB_SGD_TD_URL,
    DEFAULT_BOC_PROMO_URL,
    DEFAULT_BEA_SGD_PROMO_URL,
    DEFAULT_BEA_FCY_PROMO_URL,
    DEFAULT_MAYBANK_SGD_PROMO_URL,
    DEFAULT_HSBC_FCY_PROMO_URL,
    DEFAULT_DBS_FCY_BOARD_API_URL,
    DEFAULT_CITI_SGD_BOARD_URL,
    DEFAULT_DBS_SGD_BOARD_URL,
    DEFAULT_HL_SGD_BOARD_URL,
    DEFAULT_HLF_SGD_BOARD_URL,
    DEFAULT_HSBC_SGD_BOARD_URL,
    DEFAULT_ICBC_SGD_BOARD_URL,
    DEFAULT_ICBC_FCY_BOARD_URL,
    DEFAULT_MAYBANK_SGD_BOARD_URL,
    DEFAULT_OCBC_SGD_BOARD_URL,
    DEFAULT_RHB_SGD_BOARD_PDF_URL,
    DEFAULT_SIF_SGD_BOARD_URL,
    DEFAULT_SCB_SGD_BOARD_URL,
    DEFAULT_SBI_SGD_BOARD_URL,
    DEFAULT_UOB_SGD_BOARD_URL,
    DEFAULT_HL_FCY_BOARD_URL,
    DEFAULT_HSBC_FCY_BOARD_URL,
    DEFAULT_MAYBANK_FCY_BOARD_URL,
    DEFAULT_SCB_FCY_BOARD_URL,
    DEFAULT_SBI_FCY_BOARD_URL,
    DEFAULT_OCBC_FCY_BOARD_URL,
    DEFAULT_UOB_FCY_BOARD_URL,
    DEFAULT_RHB_FCY_BOARD_PDF_URL,
    DEFAULT_BEA_SGD_BOARD_API_URL,
    DEFAULT_BEA_FCY_BOARD_API_URL,
    DEFAULT_BOC_BOARD_URL,
)


def build_arg_parser() -> argparse.ArgumentParser:
    "构建命令行参数解析器并声明全部 URL/输出相关选项。"
    p = argparse.ArgumentParser(description="Extract rates from Citi SG all-promo page.")

    p.add_argument(
        "--url-config",
        default=DEFAULT_URL_CONFIG,
        help="URL 参数配置文件（推荐 xlsx；只覆盖脚本内默认值；命令行显式传参仍优先）。",
    )
    p.add_argument("--url", default=DEFAULT_URL, help="Page URL (default: stable all-promo link).")

    p.add_argument(
        "--cimb-url",
        default=DEFAULT_CIMB_FCY_URL,
        help="CIMB Foreign Currency FD page (multi-tenor promo for USD/AUD/GBP).",
    )
    p.add_argument("--no-cimb", action="store_true", help="Do not fetch CIMB FCY page.")

    p.add_argument(
        "--cimb-sgd-url",
        default=DEFAULT_CIMB_SGD_URL,
        help="CIMB SGD fixed deposit rates page.",
    )
    p.add_argument("--no-cimb-sgd", action="store_true", help="Do not fetch CIMB SGD rates.")

    p.add_argument("--hl-url", default=DEFAULT_HL_FD_URL, help="HL Bank fixed deposit promotion page.")
    p.add_argument("--no-hl", action="store_true", help="Do not fetch HL Bank page.")

    p.add_argument("--hlf-url", default=DEFAULT_HLF_FD_URL, help="HLF SGD fixed deposit promotion page.")
    p.add_argument("--no-hlf", action="store_true", help="Do not fetch HLF promo page.")

    p.add_argument("--hsbc-url", default=DEFAULT_HSBC_TD_URL, help="HSBC Singapore SGD time deposit page.")
    p.add_argument("--no-hsbc", action="store_true", help="Do not fetch HSBC Singapore SGD page.")

    p.add_argument("--icbc-url", default=DEFAULT_ICBC_FD_URL, help="ICBC Singapore fixed deposit promotion page.")
    p.add_argument("--no-icbc", action="store_true", help="Do not fetch ICBC Singapore FD promo page.")

    p.add_argument("--ocbc-url", default=DEFAULT_OCBC_FD_URL, help="OCBC Singapore SGD time deposit promotional page.")
    p.add_argument("--no-ocbc", action="store_true", help="Do not fetch OCBC Singapore promo page.")

    p.add_argument("--rhb-url", default=DEFAULT_RHB_FD_URL, help="RHB Singapore fixed deposit campaign page.")
    p.add_argument("--no-rhb", action="store_true", help="Do not fetch RHB Singapore campaign page.")

    p.add_argument("--rhb-fcy-url", default=DEFAULT_RHB_FCY_FD_URL, help="RHB Singapore foreign currency fixed deposit campaign page.")
    p.add_argument("--no-rhb-fcy", action="store_true", help="Do not fetch RHB Singapore FCY campaign page.")

    p.add_argument("--sif-url", default=DEFAULT_SIF_FD_URL, help="SingFinance FD Online promotional page.")
    p.add_argument("--no-sif", action="store_true", help="Do not fetch SingFinance FD Online promotional page.")

    p.add_argument("--scb-url", default=DEFAULT_SCB_SGD_TD_URL, help="Standard Chartered SGD time deposit promo page.")
    p.add_argument("--no-scb", action="store_true", help="Do not fetch Standard Chartered SGD promo page.")

    p.add_argument("--scb-fcy-url", default=DEFAULT_SCB_FCY_FD_URL, help="Standard Chartered foreign currency time deposit promo page.")
    p.add_argument("--no-scb-fcy", action="store_true", help="Do not fetch Standard Chartered FCY promo page.")

    p.add_argument("--sbi-url", default=DEFAULT_SBI_SGD_PROMO_URL, help="SBI Singapore SGD promotions page.")
    p.add_argument("--no-sbi", action="store_true", help="Do not fetch SBI Singapore SGD promotions page.")

    p.add_argument("--sbi-usd-url", default=DEFAULT_SBI_USD_PROMO_URL, help="SBI Singapore USD promotions page.")
    p.add_argument("--no-sbi-usd", action="store_true", help="Do not fetch SBI Singapore USD promotions page.")

    p.add_argument("--uob-url", default=DEFAULT_UOB_SGD_TD_URL, help="UOB Singapore Dollar Time/Fixed Deposit promotional page.")
    p.add_argument("--no-uob", action="store_true", help="Do not fetch UOB promotional page.")

    p.add_argument("--boc-url", default=DEFAULT_BOC_PROMO_URL, help="BOC Singapore personal fixed deposit promotions page (SGD + FCY).")
    p.add_argument("--no-boc", action="store_true", help="Do not fetch BOC fixed deposit promotions page.")
    p.add_argument(
        "--no-boc-follow-latest",
        action="store_false",
        dest="boc_follow_latest_from_index",
        default=True,
        help=(
            "Do not open BOC SG listing pages to pick the newest bi31/bi32 article; "
            "use --boc-url and --boc-board-url exactly as given."
        ),
    )

    p.add_argument("--no-sgd-board", action="store_true", help="Do not fetch SGD board-rate pages.")

    # SGD board URLs
    p.add_argument("--citi-board-url", default=DEFAULT_CITI_SGD_BOARD_URL, help="Citibank Singapore SGD board rates page.")
    p.add_argument("--dbs-board-url", default=DEFAULT_DBS_SGD_BOARD_URL, help="DBS Singapore SGD board rates page.")
    p.add_argument("--hl-board-url", default=DEFAULT_HL_SGD_BOARD_URL, help="HL Bank SGD board rates page.")
    p.add_argument("--hlf-board-url", default=DEFAULT_HLF_SGD_BOARD_URL, help="HLF SGD board rates page.")
    p.add_argument("--hsbc-board-url", default=DEFAULT_HSBC_SGD_BOARD_URL, help="HSBC SGD board rates page.")
    p.add_argument("--icbc-board-url", default=DEFAULT_ICBC_SGD_BOARD_URL, help="ICBC SGD board rates page.")
    p.add_argument(
        "--icbc-fcy-board-url",
        default=DEFAULT_ICBC_FCY_BOARD_URL,
        help="ICBC foreign-currency FD board page (often same URL as SGD board).",
    )
    p.add_argument("--maybank-board-url", default=DEFAULT_MAYBANK_SGD_BOARD_URL, help="Maybank SGD board rates page.")
    p.add_argument("--ocbc-board-url", default=DEFAULT_OCBC_SGD_BOARD_URL, help="OCBC SGD board rates page.")
    p.add_argument("--rhb-board-pdf-url", default=DEFAULT_RHB_SGD_BOARD_PDF_URL, help="RHB SGD board PDF.")
    p.add_argument("--sif-board-url", default=DEFAULT_SIF_SGD_BOARD_URL, help="SingFinance SGD board rates page.")
    p.add_argument("--scb-board-url", default=DEFAULT_SCB_SGD_BOARD_URL, help="Standard Chartered SGD board rates page.")
    p.add_argument("--sbi-board-url", default=DEFAULT_SBI_SGD_BOARD_URL, help="SBI SGD board rates page.")
    p.add_argument("--uob-board-url", default=DEFAULT_UOB_SGD_BOARD_URL, help="UOB SGD board rates page.")
    p.add_argument(
        "--ocbc-fcy-board-url",
        default=DEFAULT_OCBC_FCY_BOARD_URL,
        help="OCBC foreign-currency TD daily rates HTML (default daily_price_fd.html).",
    )
    p.add_argument(
        "--uob-fcy-board-url",
        default=DEFAULT_UOB_FCY_BOARD_URL,
        help="UOB Group FCY FD rates page (Referer for JSON API).",
    )

    # FCY board URLs
    p.add_argument("--hl-fcy-board-url", default=DEFAULT_HL_FCY_BOARD_URL, help="HL FCY board rates page.")
    p.add_argument("--hsbc-fcy-board-url", default=DEFAULT_HSBC_FCY_BOARD_URL, help="HSBC FCY board rates page.")
    p.add_argument("--maybank-fcy-board-url", default=DEFAULT_MAYBANK_FCY_BOARD_URL, help="Maybank FCY board rates page.")
    p.add_argument("--scb-fcy-board-url", default=DEFAULT_SCB_FCY_BOARD_URL, help="SCB FCY board rates page.")
    p.add_argument("--sbi-fcy-board-url", default=DEFAULT_SBI_FCY_BOARD_URL, help="SBI FCY board rates page.")
    p.add_argument("--rhb-fcy-board-pdf-url", default=DEFAULT_RHB_FCY_BOARD_PDF_URL, help="RHB FCY board PDF.")

    # BEA/BOC board URLs
    p.add_argument("--bea-sgd-board-api-url", default=DEFAULT_BEA_SGD_BOARD_API_URL, help="BEA SGD board API endpoint.")
    p.add_argument("--bea-fcy-board-api-url", default=DEFAULT_BEA_FCY_BOARD_API_URL, help="BEA FCY board API endpoint.")
    p.add_argument("--boc-board-url", default=DEFAULT_BOC_BOARD_URL, help="BOC board rates page (SGD + FCY).")

    p.add_argument("--bea-sgd-promo-url", default=DEFAULT_BEA_SGD_PROMO_URL, help="BEA Singapore SGD FD promotion page.")
    p.add_argument("--bea-fcy-promo-url", default=DEFAULT_BEA_FCY_PROMO_URL, help="BEA Singapore FCY FD promotion page.")
    p.add_argument(
        "--maybank-sgd-promo-url",
        default=DEFAULT_MAYBANK_SGD_PROMO_URL,
        help="Maybank2u SGD time deposit promotion page.",
    )
    p.add_argument(
        "--hsbc-fcy-promo-url",
        default=DEFAULT_HSBC_FCY_PROMO_URL,
        help="HSBC FCY time deposit promo source (.pdf or HTML page linking to PDFs).",
    )
    p.add_argument(
        "--dbs-fcy-board-api-url",
        default=DEFAULT_DBS_FCY_BOARD_API_URL,
        help="DBS Singapore FCY FD board JSON API URL (GET with FETCH_LATEST query).",
    )

    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--use-env-proxy", action="store_true", help="Honor HTTP(S)_PROXY from environment.")
    p.add_argument("--json-out", help="Write JSON to this file (UTF-8).")
    p.add_argument(
        "--xlsx-out",
        nargs="?",
        const=".",
        default=None,
        metavar="FILE_OR_DIR",
        help=(
            "Write Excel (.xlsx). If FILE_OR_DIR is a directory, write the file inside it. "
            "If a .xlsx path is given, insert _YYYYMMDD_HH.mm before .xlsx when not already tagged."
        ),
    )
    p.add_argument("--print-json", action="store_true", help="Also print JSON to stdout when using --xlsx-out.")
    p.add_argument("--pretty", action="store_true", help="Indent JSON output.")

    return p


def _fallback_namespace() -> argparse.Namespace:
    "当 argparse 解析失败时，构造最小可运行的回退参数对象。"
    try:
        return build_arg_parser().parse_args([])
    except Exception:
        return argparse.Namespace()


@safe_call(
    context="解析 CLI 参数（portable）",
    default_factory=lambda e, a, k: _fallback_namespace(),
)
def parse_cli_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    "解析命令行参数；失败时返回带默认值的回退命名空间。"
    parser = build_arg_parser()
    return parser.parse_args(argv)


auto_wrap_module_functions(globals(), module_name=__name__)

