from __future__ import annotations

"""
可移植版本：fetch_and_extract 输入参数构建器。

逻辑与主目录 `bank_cli_fetch_params.py` 一致。
"""

from typing import Any, Dict, Tuple
import sys
import traceback

from bank_safety import safe_call


@safe_call(
    context="构建 fetch_and_extract 输入参数",
    default_factory=lambda e, a, k: (
        getattr(a[0], "url", ""),
        getattr(a[0], "timeout", 60.0),
        getattr(a[0], "use_env_proxy", False),
        {"include_sgd_board": not getattr(a[0], "no_sgd_board", False)},
    ),
)
def build_fetch_and_extract_inputs(args: Any) -> Tuple[str, float, bool, Dict[str, Any]]:
    """
    从 argparse 的 `args` 生成 `fetch_and_extract()` 的完整调用参数。

    说明与主目录同名模块一致，请参考 `bank_cli_fetch_params.py`。
    """

    try:
        # 基础抓取参数：主 URL、超时、代理策略。
        url = args.url
        timeout = args.timeout
        use_env_proxy = args.use_env_proxy

        # 各家促销页 URL：遵循 no_* 开关，关闭时置为 None。
        citi_all_promo_url = None if args.no_citi_all_promo else args.citi_all_promo_url
        cimb_fcy_url = None if args.no_cimb else args.cimb_url
        cimb_sgd_url = None if args.no_cimb_sgd else args.cimb_sgd_url
        hl_fd_url = None if args.no_hl else args.hl_url
        hlf_promo_url = None if args.no_hlf else args.hlf_url
        hsbc_td_url = None if args.no_hsbc else args.hsbc_url
        icbc_fd_url = None if args.no_icbc else args.icbc_url
        ocbc_fd_url = None if args.no_ocbc else args.ocbc_url
        rhb_fd_url = None if args.no_rhb else args.rhb_url
        rhb_fcy_fd_url = None if args.no_rhb_fcy else args.rhb_fcy_url
        sif_fd_url = None if args.no_sif else args.sif_url
        scb_sgd_fd_url = None if args.no_scb else args.scb_url
        scb_fcy_fd_url = None if args.no_scb_fcy else args.scb_fcy_url
        sbi_sgd_fd_url = None if args.no_sbi else args.sbi_url
        sbi_fcy_fd_url = None if args.no_sbi_usd else args.sbi_usd_url
        uob_sgd_fd_url = None if args.no_uob else args.uob_url
        boc_promo_url = None if args.no_boc else args.boc_url

        # 挂牌相关开关与 URL：复用 no_sgd_board 作为总开关。
        include_sgd_board = not args.no_sgd_board

        citi_sgd_board_url = None if args.no_sgd_board else args.citi_board_url
        dbs_sgd_board_url = None if args.no_sgd_board else args.dbs_board_url
        hl_sgd_board_url = None if args.no_sgd_board else args.hl_board_url
        hlf_sgd_board_url = None if args.no_sgd_board else args.hlf_board_url
        hsbc_sgd_board_url = None if args.no_sgd_board else args.hsbc_board_url
        icbc_sgd_board_url = None if args.no_sgd_board else args.icbc_board_url
        icbc_fcy_board_url = None if args.no_sgd_board else args.icbc_fcy_board_url
        cimb_fcy_board_url = None if args.no_sgd_board else args.cimb_fcy_board_url
        maybank_sgd_board_url = None if args.no_sgd_board else args.maybank_board_url
        ocbc_sgd_board_url = None if args.no_sgd_board else args.ocbc_board_url
        rhb_sgd_board_pdf_url = None if args.no_sgd_board else args.rhb_board_pdf_url
        sif_sgd_board_url = None if args.no_sgd_board else args.sif_board_url
        scb_sgd_board_url = None if args.no_sgd_board else args.scb_board_url
        sbi_sgd_board_url = None if args.no_sgd_board else args.sbi_board_url
        uob_sgd_board_url = None if args.no_sgd_board else args.uob_board_url
        ocbc_fcy_board_url = None if args.no_sgd_board else args.ocbc_fcy_board_url
        uob_fcy_board_url = None if args.no_sgd_board else args.uob_fcy_board_url

        hl_fcy_board_url = None if args.no_sgd_board else args.hl_fcy_board_url
        hsbc_fcy_board_url = None if args.no_sgd_board else args.hsbc_fcy_board_url
        maybank_fcy_board_url = None if args.no_sgd_board else args.maybank_fcy_board_url
        scb_fcy_board_url = None if args.no_sgd_board else args.scb_fcy_board_url
        sbi_fcy_board_url = None if args.no_sgd_board else args.sbi_fcy_board_url
        rhb_fcy_board_pdf_url = None if args.no_sgd_board else args.rhb_fcy_board_pdf_url

        bea_sgd_board_api_url = None if args.no_sgd_board else args.bea_sgd_board_api_url
        bea_fcy_board_api_url = None if args.no_sgd_board else args.bea_fcy_board_api_url
        boc_board_url = None if args.no_sgd_board else args.boc_board_url

        # 汇总为 fetch_and_extract 的关键字参数字典。
        fetch_kwargs: Dict[str, Any] = {
            "citi_all_promo_url": citi_all_promo_url,
            "cimb_fcy_url": cimb_fcy_url,
            "cimb_sgd_url": cimb_sgd_url,
            "hl_fd_url": hl_fd_url,
            "hlf_promo_url": hlf_promo_url,
            "hsbc_td_url": hsbc_td_url,
            "icbc_fd_url": icbc_fd_url,
            "ocbc_fd_url": ocbc_fd_url,
            "rhb_fd_url": rhb_fd_url,
            "rhb_fcy_fd_url": rhb_fcy_fd_url,
            "sif_fd_url": sif_fd_url,
            "scb_sgd_fd_url": scb_sgd_fd_url,
            "scb_fcy_fd_url": scb_fcy_fd_url,
            "sbi_sgd_fd_url": sbi_sgd_fd_url,
            "sbi_fcy_fd_url": sbi_fcy_fd_url,
            "uob_sgd_fd_url": uob_sgd_fd_url,
            "boc_promo_url": boc_promo_url,
            "bea_sgd_promo_url": args.bea_sgd_promo_url,
            "bea_fcy_promo_url": args.bea_fcy_promo_url,
            "maybank_sgd_promo_url": args.maybank_sgd_promo_url,
            "hsbc_fcy_promo_url": args.hsbc_fcy_promo_url,
            "include_sgd_board": include_sgd_board,
            "citi_sgd_board_url": citi_sgd_board_url,
            "dbs_sgd_board_url": dbs_sgd_board_url,
            "hl_sgd_board_url": hl_sgd_board_url,
            "hlf_sgd_board_url": hlf_sgd_board_url,
            "hsbc_sgd_board_url": hsbc_sgd_board_url,
            "icbc_sgd_board_url": icbc_sgd_board_url,
            "icbc_fcy_board_url": icbc_fcy_board_url,
            "cimb_fcy_board_url": cimb_fcy_board_url,
            "maybank_sgd_board_url": maybank_sgd_board_url,
            "ocbc_sgd_board_url": ocbc_sgd_board_url,
            "rhb_sgd_board_pdf_url": rhb_sgd_board_pdf_url,
            "sif_sgd_board_url": sif_sgd_board_url,
            "scb_sgd_board_url": scb_sgd_board_url,
            "sbi_sgd_board_url": sbi_sgd_board_url,
            "uob_sgd_board_url": uob_sgd_board_url,
            "ocbc_fcy_board_url": ocbc_fcy_board_url,
            "uob_fcy_board_url": uob_fcy_board_url,
            "hl_fcy_board_url": hl_fcy_board_url,
            "hsbc_fcy_board_url": hsbc_fcy_board_url,
            "maybank_fcy_board_url": maybank_fcy_board_url,
            "scb_fcy_board_url": scb_fcy_board_url,
            "sbi_fcy_board_url": sbi_fcy_board_url,
            "rhb_fcy_board_pdf_url": rhb_fcy_board_pdf_url,
            "bea_sgd_board_api_url": bea_sgd_board_api_url,
            "bea_fcy_board_api_url": bea_fcy_board_api_url,
            "boc_board_url": boc_board_url,
            "dbs_fcy_board_api_url": None if args.no_sgd_board else args.dbs_fcy_board_api_url,
            "boc_follow_latest_from_index": getattr(args, "boc_follow_latest_from_index", True),
            "icbc_follow_latest_from_index": getattr(args, "icbc_follow_latest_from_index", True),
        }

        return url, timeout, use_env_proxy, fetch_kwargs
    except Exception as e:
        print(f"[PARAM] build_fetch_and_extract_inputs 失败：{e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        raise


# Safety net: 自动给本模块中所有 def 加异常兜底
from bank_safety import auto_wrap_module_functions as _auto_wrap_module_functions

_auto_wrap_module_functions(globals(), module_name=__name__)

