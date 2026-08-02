from __future__ import annotations

from typing import Dict

# 这个文件只包含“数据表里写的 key”到“脚本里 argparse dest”的映射，以及 dest 白名单。
# 可移植版本和主版本内容保持一致，便于两份脚本独立运行时的维护一致性。

# 该模块专门承载 URL 配置的“键映射”规则，用于把用户在 Excel/JSON 里写的
# 友好 key（中文描述）转换成脚本里 argparse 最终使用的参数 dest（例如 `boc_board_url`）。
#
# 该文件与主目录下同名模块内容保持一致，只是为了便于可移植版本独立运行。

# 友好 key -> argparse dest 的别名映射。
# 说明：脚本只关心最终 dest（例如 `boc_board_url`）；友好 key 仅是为了方便维护配置。
URL_KEY_ALIASES: Dict[str, str] = {
    # Citibank: 定存产品页覆盖 SGD/USD；all-promo 覆盖多币种 FX 1M
    "CITIBANK 新币促销利率": "url",
    "CITIBANK 促销利率": "url",
    "CITIBANK 新元美元促销页": "url",
    "CITIBANK 定存促销页": "url",
    "citi_url": "url",
    "citibank_url": "url",
    "citi_fd_promo_url": "url",
    "citi_fd_promo_ref_url": "url",
    "CITIBANK 外币促销利率": "citi_all_promo_url",
    "CITIBANK 外币 FX 定存促销页": "citi_all_promo_url",
    "CITIBANK all-promo": "citi_all_promo_url",
    "citi_all_promo_url": "citi_all_promo_url",
    # CIMB
    "CIMB 新币促销利率": "cimb_sgd_url",
    "CIMB 外币促销利率": "cimb_url",
    "CIMB 外币挂牌利率": "cimb_fcy_board_url",
    "CIMB 外币挂牌利率页": "cimb_fcy_board_url",
    "cimb_fcy_board_url": "cimb_fcy_board_url",
    # HL
    "HL 新币促销利率": "hl_url",
    "HL 外币促销利率": "hl_url",
    # HLF
    "HLF 新币促销利率": "hlf_url",
    # HSBC
    "HSBC 新币促销利率": "hsbc_url",
    # ICBC
    "ICBC 新币促销利率": "icbc_url",
    "ICBC 外币促销利率": "icbc_url",
    # OCBC
    "OCBC 新币促销利率": "ocbc_url",
    # RHB
    "RHB 新币促销利率": "rhb_url",
    "RHB 外币促销利率": "rhb_fcy_url",
    # SingFinance
    "SIF 新币促销利率": "sif_url",
    # SCB
    "SCB 新币促销利率": "scb_url",
    "SCB 外币促销利率": "scb_fcy_url",
    # SBI
    "SBI 新币促销利率": "sbi_url",
    "SBI 外币促销利率": "sbi_usd_url",
    # UOB
    "UOB 新币促销利率": "uob_url",
    "UOB 外币促销利率": "uob_url",
    # BOC
    "BOC 新币促销利率": "boc_url",
    "BOC 外币促销利率": "boc_url",

    # SGD board（新币挂牌）
    "CITIBANK 新币挂牌利率": "citi_board_url",
    "DBS 新币挂牌利率": "dbs_board_url",
    "HL 新币挂牌利率": "hl_board_url",
    "HLF 新币挂牌利率": "hlf_board_url",
    "HSBC 新币挂牌利率": "hsbc_board_url",
    "ICBC 新币挂牌利率": "icbc_board_url",
    "MAYBANK 新币挂牌利率": "maybank_board_url",
    "OCBC 新币挂牌利率": "ocbc_board_url",
    "RHB 新币挂牌利率": "rhb_board_pdf_url",
    "SIF 新币挂牌利率": "sif_board_url",
    "SCB 新币挂牌利率": "scb_board_url",
    "SBI 新币挂牌利率": "sbi_board_url",
    "UOB 新币挂牌利率": "uob_board_url",
    "BEA 新币挂牌利率": "bea_sgd_board_api_url",
    "BOC 新币挂牌利率": "boc_board_url",

    # BEA / Maybank / HSBC 促销页（非挂牌 API）
    "BEA 新元定存促销页": "bea_sgd_promo_url",
    "BEA 外币定存促销页": "bea_fcy_promo_url",
    "MAYBANK 新元定存促销页": "maybank_sgd_promo_url",
    "HSBC 外币定存促销页": "hsbc_fcy_promo_url",
    "bea_sgd_promo_url": "bea_sgd_promo_url",
    "bea_fcy_promo_url": "bea_fcy_promo_url",
    "maybank_sgd_promo_url": "maybank_sgd_promo_url",
    "hsbc_fcy_promo_url": "hsbc_fcy_promo_url",
    # FCY board（外币挂牌）
    "HL 外币挂牌利率": "hl_fcy_board_url",
    "HSBC 外币挂牌利率": "hsbc_fcy_board_url",
    "MAYBANK 外币挂牌利率": "maybank_fcy_board_url",
    "ICBC 外币挂牌利率": "icbc_fcy_board_url",
    "ICBC 外币挂牌利率页": "icbc_fcy_board_url",
    "icbc_fcy_board_url": "icbc_fcy_board_url",
    "RHB 外币挂牌利率": "rhb_fcy_board_pdf_url",
    "SCB 外币挂牌利率": "scb_fcy_board_url",
    "SBI 外币挂牌利率": "sbi_fcy_board_url",
    "BEA 外币挂牌利率": "bea_fcy_board_api_url",
    "DBS 外币挂牌利率页": "dbs_fcy_board_api_url",
    "DBS 外币挂牌利率": "dbs_fcy_board_api_url",
    "dbs_fcy_board_api_url": "dbs_fcy_board_api_url",
    "BOC 外币挂牌利率": "boc_board_url",
    "OCBC 外币挂牌利率": "ocbc_fcy_board_url",
    "OCBC 外币挂牌利率页": "ocbc_fcy_board_url",
    "ocbc_fcy_board_url": "ocbc_fcy_board_url",
    "UOB 外币挂牌利率": "uob_fcy_board_url",
    "UOB 外币挂牌利率页": "uob_fcy_board_url",
    "uob_fcy_board_url": "uob_fcy_board_url",
}

# argparse dest keys（也用于过滤：只接受我们能用上的键）。
URL_PARAM_DEST_KEYS: set[str] = {
    "url",
    "citi_all_promo_url",
    "cimb_url",
    "cimb_sgd_url",
    "cimb_fcy_board_url",
    "hl_url",
    "hlf_url",
    "hsbc_url",
    "icbc_url",
    "ocbc_url",
    "rhb_url",
    "rhb_fcy_url",
    "sif_url",
    "scb_url",
    "scb_fcy_url",
    "sbi_url",
    "sbi_usd_url",
    "uob_url",
    "boc_url",
    "citi_board_url",
    "dbs_board_url",
    "hl_board_url",
    "hlf_board_url",
    "hsbc_board_url",
    "icbc_board_url",
    "icbc_fcy_board_url",
    "maybank_board_url",
    "ocbc_board_url",
    "rhb_board_pdf_url",
    "sif_board_url",
    "scb_board_url",
    "sbi_board_url",
    "uob_board_url",
    "ocbc_fcy_board_url",
    "uob_fcy_board_url",
    "hl_fcy_board_url",
    "hsbc_fcy_board_url",
    "maybank_fcy_board_url",
    "scb_fcy_board_url",
    "sbi_fcy_board_url",
    "rhb_fcy_board_pdf_url",
    "bea_sgd_board_api_url",
    "bea_fcy_board_api_url",
    "boc_board_url",
    "bea_sgd_promo_url",
    "bea_fcy_promo_url",
    "maybank_sgd_promo_url",
    "hsbc_fcy_promo_url",
    "dbs_fcy_board_api_url",
}

