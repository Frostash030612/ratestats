from __future__ import annotations

"""
可移植版本的 MarketRateData Excel 数据准备器。

与主目录 `bank_excel_data_builder.py` 逻辑一致，用于
`RateStats_Portable/bank_all_promo_rates.py` 在独立运行时避免模块解析路径问题。
"""

from typing import Any, Dict, List

import pandas as pd

from bank_safety import safe_call


def _icbc_resolution_meta_rows(label: str, block: dict) -> List[Dict[str, str]]:
    """若栏目解析切到新链，追加配置链/最新链两行，方便测试对比。"""
    ur = (block or {}).get("url_resolution") or {}
    if not ur.get("switched_from_configured"):
        return []
    rows: List[Dict[str, str]] = []
    cfg = (ur.get("configured_url") or "").strip()
    latest = (ur.get("latest_from_index") or ur.get("fetch_url") or "").strip()
    if cfg:
        rows.append({"项目": f"{label}（配置）", "内容": cfg})
    if latest:
        rows.append({"项目": f"{label}（官网栏目最新）", "内容": latest})
    return rows


@safe_call(
    context="准备 MarketRateData Excel 数据（portable）",
    default_factory=lambda e, a, k: {
        "df_meta": pd.DataFrame(columns=["项目", "内容"]),
        "df_sgd": pd.DataFrame(),
        "df_sgd_board": pd.DataFrame(),
        "df_fx": pd.DataFrame(),
        "df_fx_notes": pd.DataFrame(columns=["说明"]),
        "df_other": pd.DataFrame(columns=["类别", "指标", "数值"]),
        "df_fx_board": pd.DataFrame(columns=["币种"]),
    },
)
def prepare_market_rate_excel_data(data: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    """
    从 `fetch_and_extract()` 产出的 payload 生成写 Excel 所需的 DataFrame。

    约定与风险提示：
    - 本模块只负责“字段重命名/列顺序整理”，最终写入由 `bank_excel_template_writer.py` 完成。
    - 因为 pandas 写入时不会校验“列名是否与模板一致”，所以只要列顺序或列名映射错了，
      Excel 可能依然能生成，但内容会错位而不易被立即察觉。

    详见主目录同名模块。
    """

    cimb_url = (data.get("cimb_fcy_promo") or {}).get("source_url", "")
    cimb_sgd_url = (data.get("cimb_sgd_rates") or {}).get("source_url", "")
    cimb_sgd_err = (data.get("cimb_sgd_rates") or {}).get("error")
    hl_url = (data.get("hl_fd_promo") or {}).get("source_url", "")
    hl_err = (data.get("hl_fd_promo") or {}).get("error")
    hlf_url = (data.get("hlf_promo") or {}).get("source_url", "")
    hlf_err = (data.get("hlf_promo") or {}).get("error")
    maybank_promo_url = (data.get("maybank_sgd_promo") or {}).get("source_url", "")
    maybank_promo_err = (data.get("maybank_sgd_promo") or {}).get("error")
    hsbc_url = (data.get("hsbc_td_promo") or {}).get("source_url", "")
    hsbc_err = (data.get("hsbc_td_promo") or {}).get("error")
    hsbc_fcy_promo_url = (data.get("hsbc_fcy_promo") or {}).get("source_url", "")
    hsbc_fcy_promo_err = (data.get("hsbc_fcy_promo") or {}).get("error")
    icbc_url = (data.get("icbc_fd_promo") or {}).get("source_url", "")
    icbc_err = (data.get("icbc_fd_promo") or {}).get("error")
    ocbc_url = (data.get("ocbc_fd_promo") or {}).get("source_url", "")
    ocbc_err = (data.get("ocbc_fd_promo") or {}).get("error")
    rhb_url = (data.get("rhb_fd_promo") or {}).get("source_url", "")
    rhb_err = (data.get("rhb_fd_promo") or {}).get("error")
    rhb_fcy_url = (data.get("rhb_fcy_fd_promo") or {}).get("source_url", "")
    rhb_fcy_err = (data.get("rhb_fcy_fd_promo") or {}).get("error")
    sif_url = (data.get("sif_fd_promo") or {}).get("source_url", "")
    sif_err = (data.get("sif_fd_promo") or {}).get("error")
    uob_url = (data.get("uob_sgd_fd_promo") or {}).get("source_url", "")
    uob_err = (data.get("uob_sgd_fd_promo") or {}).get("error")
    uob_has_fcy = (data.get("uob_fcy_promo") or {}).get("has_fcy_promo_table", None)
    scb_url = (data.get("scb_sgd_promo") or {}).get("source_url", "")
    scb_err = (data.get("scb_sgd_promo") or {}).get("error")
    scb_fcy_url = (data.get("scb_fcy_fd_promo") or {}).get("source_url", "")
    scb_fcy_err = (data.get("scb_fcy_fd_promo") or {}).get("error")
    sbi_url = (data.get("sbi_sgd_promo") or {}).get("source_url", "")
    sbi_err = (data.get("sbi_sgd_promo") or {}).get("error")
    sbi_fcy_url = (data.get("sbi_fcy_promo") or {}).get("source_url", "")
    sbi_fcy_err = (data.get("sbi_fcy_promo") or {}).get("error")
    boc_url = (data.get("boc_promo") or {}).get("source_url", "")
    boc_err = (data.get("boc_promo") or {}).get("error")
    bea_sgd_promo_url = (data.get("bea_sgd_promo") or {}).get("source_url", "")
    bea_sgd_promo_err = (data.get("bea_sgd_promo") or {}).get("error")
    bea_fcy_promo_url = (data.get("bea_fcy_promo") or {}).get("source_url", "")
    bea_fcy_promo_err = (data.get("bea_fcy_promo") or {}).get("error")

    citi_b = data.get("citi_sgd_board") or {}
    dbs_b = data.get("dbs_sgd_board") or {}
    hl_b = data.get("hl_sgd_board") or {}
    hlf_b = data.get("hlf_sgd_board") or {}
    hsbc_b = data.get("hsbc_sgd_board") or {}
    icbc_b = data.get("icbc_sgd_board") or {}
    may_b = data.get("maybank_sgd_board") or {}
    ocbc_b = data.get("ocbc_sgd_board") or {}
    rhb_pdf_b = data.get("rhb_sgd_board_pdf") or {}
    sif_b = data.get("sif_sgd_board") or {}
    scb_b = data.get("scb_sgd_board") or {}
    sbi_b = data.get("sbi_sgd_board") or {}
    uob_b = data.get("uob_sgd_board") or {}
    hl_fcy_b = data.get("hl_fcy_board") or {}
    hsbc_fcy_b = data.get("hsbc_fcy_board") or {}
    maybank_fcy_b = data.get("maybank_fcy_board") or {}
    dbs_fcy_b = data.get("dbs_fcy_board") or {}
    scb_fcy_b = data.get("scb_fcy_board") or {}
    sbi_fcy_b = data.get("sbi_fcy_board") or {}
    rhb_fcy_b = data.get("rhb_fcy_board_pdf") or {}
    bea_sgd_b = data.get("bea_sgd_board") or {}
    bea_fcy_b = data.get("bea_fcy_board") or {}
    boc_sgd_b = data.get("boc_sgd_board") or {}
    boc_fcy_b = data.get("boc_fcy_board") or {}
    icbc_fcy_b = data.get("icbc_fcy_board") or {}
    cimb_fcy_b = data.get("cimb_fcy_board") or {}
    ocbc_fcy_b = data.get("ocbc_fcy_board") or {}
    uob_fcy_b = data.get("uob_fcy_board") or {}

    citi_b_err = citi_b.get("error")
    dbs_b_err = dbs_b.get("error")
    hl_b_err = hl_b.get("error")
    hlf_b_err = hlf_b.get("error")
    hsbc_b_err = hsbc_b.get("error")
    icbc_b_err = icbc_b.get("error")
    may_b_err = may_b.get("error")
    ocbc_b_err = ocbc_b.get("error")
    rhb_pdf_b_err = rhb_pdf_b.get("error")
    sif_b_err = sif_b.get("error")
    scb_b_err = scb_b.get("error")
    sbi_b_err = sbi_b.get("error")
    uob_b_err = uob_b.get("error")
    hl_fcy_b_err = hl_fcy_b.get("error")
    hsbc_fcy_b_err = hsbc_fcy_b.get("error")
    maybank_fcy_b_err = maybank_fcy_b.get("error")
    dbs_fcy_b_err = dbs_fcy_b.get("error")
    scb_fcy_b_err = scb_fcy_b.get("error")
    sbi_fcy_b_err = sbi_fcy_b.get("error")
    rhb_fcy_b_err = rhb_fcy_b.get("error")
    bea_sgd_b_err = bea_sgd_b.get("error")
    bea_fcy_b_err = bea_fcy_b.get("error")
    boc_sgd_b_err = boc_sgd_b.get("error")
    boc_fcy_b_err = boc_fcy_b.get("error")
    icbc_fcy_b_err = icbc_fcy_b.get("error")
    cimb_fcy_b_err = cimb_fcy_b.get("error")
    ocbc_fcy_b_err = ocbc_fcy_b.get("error")
    uob_fcy_b_err = uob_fcy_b.get("error")

    # -----------------------------------------------------------------------
    # 1) 元数据表（元数据 sheet）
    # -----------------------------------------------------------------------
    # 两列结构：`项目` / `内容`。
    # 其中包含各来源链接与抓取失败原因，方便排查后续数据空缺。
    citi_fx = data.get("fx_time_deposit_1m") or {}
    citi_all_promo_url = citi_fx.get("source_url", "")

    meta_rows: List[Dict[str, Any]] = [
        {"项目": "抓取时间", "内容": data.get("fetched_at_utc", "")},
        {"项目": "Citibank 来源链接", "内容": data.get("source_url", "")},
        {"项目": "Citibank 外币 FX 定存促销页", "内容": citi_all_promo_url},
        {"项目": "CIMB FCY 页面链接", "内容": cimb_url},
        {"项目": "CIMB 新元定存利率页", "内容": cimb_sgd_url},
        {
            "项目": "CIMB SGD 挂牌利率",
            "内容": "与「CIMB 新元定存利率页」同源（同页中的 Board 表）",
        },
        {"项目": "CIMB 外币挂牌利率页", "内容": cimb_fcy_b.get("source_url", "")},
        {"项目": "HL Bank 定存促销页", "内容": hl_url},
        {"项目": "HLF 新元促销页", "内容": hlf_url},
        {"项目": "Maybank 新元定存促销页", "内容": maybank_promo_url},
        {"项目": "汇丰新加坡 新币定期存款页", "内容": hsbc_url},
        {"项目": "HSBC 外币定存促销页", "内容": hsbc_fcy_promo_url},
        {"项目": "工行新加坡 定存促销页", "内容": icbc_url},
        {"项目": "OCBC 新元定存促销页", "内容": ocbc_url},
        {"项目": "RHB 新元定存促销页", "内容": rhb_url},
        {"项目": "RHB 外币定存促销页", "内容": rhb_fcy_url},
        {"项目": "SingFinance 新元定存促销页", "内容": sif_url},
        {"项目": "UOB 新元定存促销页", "内容": uob_url},
        {"项目": "SCB 新元定存促销页", "内容": scb_url},
        {"项目": "SCB 外币定存促销页", "内容": scb_fcy_url},
        {"项目": "SBI 新元定存促销页", "内容": sbi_url},
        {"项目": "SBI 外币定存促销页", "内容": sbi_fcy_url},
        {"项目": "中国银行新加坡 定存促销页", "内容": boc_url},
        {"项目": "BEA 新元定存促销页", "内容": bea_sgd_promo_url},
        {"项目": "BEA 外币定存促销页", "内容": bea_fcy_promo_url},
        {"项目": "Citibank SGD 挂牌利率页", "内容": citi_b.get("source_url", "")},
        {"项目": "DBS SGD 挂牌利率页", "内容": dbs_b.get("source_url", "")},
        {"项目": "HL Bank SGD 挂牌利率页", "内容": hl_b.get("source_url", "")},
        {"项目": "HLF SGD 挂牌利率页", "内容": hlf_b.get("source_url", "")},
        {"项目": "汇丰 SGD 挂牌利率页", "内容": hsbc_b.get("source_url", "")},
        {"项目": "工行新加坡 SGD 挂牌利率页", "内容": icbc_b.get("source_url", "")},
        {"项目": "Maybank SGD 挂牌利率页", "内容": may_b.get("source_url", "")},
        {"项目": "OCBC SGD 挂牌利率页", "内容": ocbc_b.get("source_url", "")},
        {"项目": "RHB SGD 挂牌利率 PDF", "内容": rhb_pdf_b.get("source_url", "")},
        {"项目": "SingFinance SGD 挂牌利率页", "内容": sif_b.get("source_url", "")},
        {"项目": "SCB SGD 挂牌利率页", "内容": scb_b.get("source_url", "")},
        {"项目": "SBI SGD 挂牌利率页", "内容": sbi_b.get("source_url", "")},
        {"项目": "UOB SGD 挂牌利率页", "内容": uob_b.get("source_url", "")},
        {"项目": "HL Bank 外币挂牌利率页", "内容": hl_fcy_b.get("source_url", "")},
        {"项目": "HSBC 外币挂牌利率页", "内容": hsbc_fcy_b.get("source_url", "")},
        {"项目": "Maybank 外币挂牌利率页", "内容": maybank_fcy_b.get("source_url", "")},
        {"项目": "DBS 外币挂牌利率页", "内容": dbs_fcy_b.get("source_url", "")},
        {"项目": "SCB 外币挂牌利率页", "内容": scb_fcy_b.get("source_url", "")},
        {"项目": "SBI 外币挂牌利率页", "内容": sbi_fcy_b.get("source_url", "")},
        {"项目": "RHB 外币挂牌利率 PDF", "内容": rhb_fcy_b.get("source_url", "")},
        {"项目": "BEA 新元挂牌利率 API", "内容": bea_sgd_b.get("source_url", "")},
        {"项目": "BEA 外币挂牌利率 API", "内容": bea_fcy_b.get("source_url", "")},
        {"项目": "BOC 新元挂牌利率页", "内容": boc_sgd_b.get("source_url", "")},
        {"项目": "BOC 外币挂牌利率页", "内容": boc_fcy_b.get("source_url", "")},
        {"项目": "工行新加坡 外币挂牌利率页", "内容": icbc_fcy_b.get("source_url", "")},
        {"项目": "OCBC 外币定存利率页（官方日价表）", "内容": ocbc_fcy_b.get("source_url", "")},
        {
            "项目": "UOB 外币挂牌利率页",
            "内容": (
                (uob_fcy_b.get("source_url") or "")
                + (
                    f"\n（API: {uob_fcy_b['api_url']}）"
                    if uob_fcy_b.get("api_url")
                    else ""
                )
            ).strip(),
        },
    ]
    meta_rows.extend(
        _icbc_resolution_meta_rows("工行新加坡 定存促销页", data.get("icbc_fd_promo") or {})
    )
    meta_rows.extend(_icbc_resolution_meta_rows("工行新加坡 SGD 挂牌利率页", icbc_b))
    meta_rows.extend(_icbc_resolution_meta_rows("工行新加坡 外币挂牌利率页", icbc_fcy_b))

    if cimb_sgd_err:
        meta_rows.append({"项目": "CIMB 新元页面", "内容": f"抓取失败: {cimb_sgd_err}"})
    if hl_err:
        meta_rows.append({"项目": "HL Bank 页面", "内容": f"抓取失败: {hl_err}"})
    if hlf_err:
        meta_rows.append({"项目": "HLF 页面", "内容": f"抓取失败: {hlf_err}"})
    if maybank_promo_err:
        meta_rows.append({"项目": "Maybank 新元定存促销页面", "内容": f"抓取失败: {maybank_promo_err}"})
    if hsbc_err:
        meta_rows.append({"项目": "汇丰新币定存页面", "内容": f"抓取失败: {hsbc_err}"})
    if hsbc_fcy_promo_err:
        meta_rows.append({"项目": "HSBC 外币定存促销页面", "内容": f"抓取失败: {hsbc_fcy_promo_err}"})
    if icbc_err:
        meta_rows.append({"项目": "工行新加坡定存促销页面", "内容": f"抓取失败: {icbc_err}"})
    if ocbc_err:
        meta_rows.append({"项目": "OCBC 新元定存促销页面", "内容": f"抓取失败: {ocbc_err}"})
    if rhb_err:
        meta_rows.append({"项目": "RHB 新元定存促销页面", "内容": f"抓取失败: {rhb_err}"})
    if rhb_fcy_err:
        meta_rows.append({"项目": "RHB 外币定存促销页面", "内容": f"抓取失败: {rhb_fcy_err}"})
    if sif_err:
        meta_rows.append({"项目": "SingFinance 新元定存促销页面", "内容": f"抓取失败: {sif_err}"})
    if uob_err:
        meta_rows.append({"项目": "UOB 新元定存促销页面", "内容": f"抓取失败: {uob_err}"})
    if uob_has_fcy is not None:
        meta_rows.append(
            {
                "项目": "UOB 外币促销表检测结果",
                "内容": "已发现外币促销表" if uob_has_fcy else "未发现外币促销表",
            }
        )
    if scb_err:
        meta_rows.append({"项目": "SCB 新元定存促销页面", "内容": f"抓取失败: {scb_err}"})
    if scb_fcy_err:
        meta_rows.append({"项目": "SCB 外币定存促销页面", "内容": f"抓取失败: {scb_fcy_err}"})
    if sbi_err:
        meta_rows.append({"项目": "SBI 新元定存促销页面", "内容": f"抓取失败: {sbi_err}"})
    if sbi_fcy_err:
        meta_rows.append({"项目": "SBI 外币定存促销页面", "内容": f"抓取失败: {sbi_fcy_err}"})
    if boc_err:
        meta_rows.append({"项目": "中国银行新加坡定存促销页面", "内容": f"抓取失败: {boc_err}"})
    if bea_sgd_promo_err:
        meta_rows.append({"项目": "BEA 新元定存促销页面", "内容": f"抓取失败: {bea_sgd_promo_err}"})
    if bea_fcy_promo_err:
        meta_rows.append({"项目": "BEA 外币定存促销页面", "内容": f"抓取失败: {bea_fcy_promo_err}"})

    if citi_b_err:
        meta_rows.append({"项目": "Citibank SGD 挂牌利率页面", "内容": f"抓取失败: {citi_b_err}"})
    if dbs_b_err:
        meta_rows.append({"项目": "DBS SGD 挂牌利率页面", "内容": f"抓取失败: {dbs_b_err}"})
    if hl_b_err:
        meta_rows.append({"项目": "HL Bank SGD 挂牌利率页面", "内容": f"抓取失败: {hl_b_err}"})
    if hlf_b_err:
        meta_rows.append({"项目": "HLF SGD 挂牌利率页面", "内容": f"抓取失败: {hlf_b_err}"})
    if hsbc_b_err:
        meta_rows.append({"项目": "汇丰 SGD 挂牌利率页面", "内容": f"抓取失败: {hsbc_b_err}"})
    if icbc_b_err:
        meta_rows.append({"项目": "工行新加坡 SGD 挂牌利率页面", "内容": f"抓取失败: {icbc_b_err}"})
    if may_b_err:
        meta_rows.append({"项目": "Maybank SGD 挂牌利率页面", "内容": f"抓取失败: {may_b_err}"})
    if ocbc_b_err:
        meta_rows.append({"项目": "OCBC SGD 挂牌利率页面", "内容": f"抓取失败: {ocbc_b_err}"})
    if rhb_pdf_b_err:
        meta_rows.append({"项目": "RHB SGD 挂牌利率 PDF", "内容": f"抓取失败: {rhb_pdf_b_err}"})
    if sif_b_err:
        meta_rows.append({"项目": "SingFinance SGD 挂牌利率页面", "内容": f"抓取失败: {sif_b_err}"})
    if scb_b_err:
        meta_rows.append({"项目": "SCB SGD 挂牌利率页面", "内容": f"抓取失败: {scb_b_err}"})
    if sbi_b_err:
        meta_rows.append({"项目": "SBI SGD 挂牌利率页面", "内容": f"抓取失败: {sbi_b_err}"})
    if uob_b_err:
        meta_rows.append({"项目": "UOB SGD 挂牌利率页面", "内容": f"抓取失败: {uob_b_err}"})
    if hl_fcy_b_err:
        meta_rows.append({"项目": "HL Bank 外币挂牌利率页面", "内容": f"抓取失败: {hl_fcy_b_err}"})
    if hsbc_fcy_b_err:
        meta_rows.append({"项目": "HSBC 外币挂牌利率页面", "内容": f"抓取失败: {hsbc_fcy_b_err}"})
    if maybank_fcy_b_err:
        meta_rows.append({"项目": "Maybank 外币挂牌利率页面", "内容": f"抓取失败: {maybank_fcy_b_err}"})
    if dbs_fcy_b_err:
        meta_rows.append({"项目": "DBS 外币挂牌利率页面", "内容": f"抓取失败: {dbs_fcy_b_err}"})
    if scb_fcy_b_err:
        meta_rows.append({"项目": "SCB 外币挂牌利率页面", "内容": f"抓取失败: {scb_fcy_b_err}"})
    if sbi_fcy_b_err:
        meta_rows.append({"项目": "SBI 外币挂牌利率页面", "内容": f"抓取失败: {sbi_fcy_b_err}"})
    if rhb_fcy_b_err:
        meta_rows.append({"项目": "RHB 外币挂牌利率 PDF", "内容": f"抓取失败: {rhb_fcy_b_err}"})
    if bea_sgd_b_err:
        meta_rows.append({"项目": "BEA 新元挂牌利率 API", "内容": f"抓取失败: {bea_sgd_b_err}"})
    if bea_fcy_b_err:
        meta_rows.append({"项目": "BEA 外币挂牌利率 API", "内容": f"抓取失败: {bea_fcy_b_err}"})
    if boc_sgd_b_err:
        meta_rows.append({"项目": "BOC 新元挂牌利率页面", "内容": f"抓取失败: {boc_sgd_b_err}"})
    if boc_fcy_b_err:
        meta_rows.append({"项目": "BOC 外币挂牌利率页面", "内容": f"抓取失败: {boc_fcy_b_err}"})
    if icbc_fcy_b_err:
        meta_rows.append(
            {"项目": "工行新加坡 外币挂牌利率页面", "内容": f"抓取失败: {icbc_fcy_b_err}"}
        )
    if cimb_fcy_b_err:
        meta_rows.append(
            {"项目": "CIMB 外币挂牌利率页面", "内容": f"抓取失败: {cimb_fcy_b_err}"}
        )
    if ocbc_fcy_b_err:
        meta_rows.append(
            {"项目": "OCBC 外币定存利率页面", "内容": f"抓取失败: {ocbc_fcy_b_err}"}
        )
    if uob_fcy_b_err:
        meta_rows.append({"项目": "UOB 外币挂牌利率页面", "内容": f"抓取失败: {uob_fcy_b_err}"})

    if ocbc_fcy_b.get("note"):
        meta_rows.append({"项目": "OCBC 外币挂牌", "内容": ocbc_fcy_b["note"]})

    df_meta = pd.DataFrame(meta_rows)

    # -----------------------------------------------------------------------
    # 2) 新元促销（SGD time deposit promo）：df_sgd
    # -----------------------------------------------------------------------
    # 把 payload 字段重命名并按模板要求固定列顺序后写入 `新元定存促销`。
    sgd_merged = data.get("sgd_merged") or []
    df_sgd = pd.DataFrame(sgd_merged)
    sgd_col_order = [
        "数据来源",
        "产品或客群",
        "起存金额_页面",
        "上限金额_页面",
        "资金区间_页面",
        "1M_pct",
        "3M_pct",
        "5M_pct",
        "6M_pct",
        "9M_pct",
        "12M_pct",
        "18M_pct",
        "24M_pct",
        "页面原文摘录",
    ]
    if not df_sgd.empty:
        df_sgd = df_sgd.rename(
            columns={
                "data_source": "数据来源",
                "product_line": "产品或客群",
                "min_amount_text": "起存金额_页面",
                "max_amount_text": "上限金额_页面",
                "placement_range_text": "资金区间_页面",
                "rate_1m_pct": "1M_pct",
                "rate_3m_pct": "3M_pct",
                "rate_5m_pct": "5M_pct",
                "rate_6m_pct": "6M_pct",
                "rate_9m_pct": "9M_pct",
                "rate_12m_pct": "12M_pct",
                "rate_18m_pct": "18M_pct",
                "rate_24m_pct": "24M_pct",
                "page_raw": "页面原文摘录",
            }
        )
        df_sgd = df_sgd[[c for c in sgd_col_order if c in df_sgd.columns]]
    else:
        df_sgd = pd.DataFrame(columns=sgd_col_order)

    # -----------------------------------------------------------------------
    # 3) 外币促销（FCY time deposit promo）：df_fx
    # -----------------------------------------------------------------------
    # 写入 `外币定存促销`；同时下面的 df_fx_notes 写入 `外币定存备注`。
    fx = data.get("fx_time_deposit_1m") or {}
    merged = data.get("fx_merged") or []
    df_fx = pd.DataFrame(merged)
    fx_cols_order = [
        "币种",
        "1M_pct",
        "3M_pct",
        "6M_pct",
        "9M_pct",
        "12M_pct",
        "18M_pct",
        "24M_pct",
        "起存金额_页面",
        "上限金额_页面",
        "数据来源",
        "页面_1M原文",
    ]
    if not df_fx.empty:
        df_fx = df_fx.rename(
            columns={
                "currency": "币种",
                "rate_1m": "1M_pct",
                "rate_3m": "3M_pct",
                "rate_6m": "6M_pct",
                "rate_9m": "9M_pct",
                "rate_12m": "12M_pct",
                "rate_18m": "18M_pct",
                "rate_24m": "24M_pct",
                "min_deposit_text": "起存金额_页面",
                "max_deposit_text": "上限金额_页面",
                "page_text_1m": "页面_1M原文",
                "data_source": "数据来源",
            }
        )
        df_fx = df_fx[[c for c in fx_cols_order if c in df_fx.columns]]
    else:
        df_fx = pd.DataFrame(columns=fx_cols_order)

    notes = list(fx.get("notes") or [])
    if fx.get("error"):
        notes.insert(0, "[Citibank FX] 抓取失败: " + str(fx["error"]))
    cimb = data.get("cimb_fcy_promo") or {}
    if cimb.get("promotion_intro"):
        notes.insert(0, "[CIMB] " + str(cimb["promotion_intro"]))
    for n in cimb.get("notes") or []:
        if n and n not in notes:
            notes.append("[CIMB] " + n)
    if cimb.get("error"):
        notes.append("[CIMB] 抓取失败: " + str(cimb["error"]))

    # `df_fx_notes`：说明列表（主要是 CIMB 的 promotion_intro + notes + error）
    df_fx_notes = pd.DataFrame({"说明": notes} if notes else {"说明": []})

    # -----------------------------------------------------------------------
    # 4) 其它利率：df_other
    # -----------------------------------------------------------------------
    # 包含 Quick Cash、AIA 等额外指标，写入 `其它利率` sheet。
    other = data.get("other") or {}
    other_rows: List[Dict[str, Any]] = []

    qc = other.get("citi_quick_cash")
    if isinstance(qc, dict):
        other_rows.append(
            {
                "类别": "Citi Quick Cash",
                "指标": "宣传利率_p.a._pct",
                "数值": qc.get("advertised_rate_pa_percent"),
            }
        )
        other_rows.append(
            {
                "类别": "Citi Quick Cash",
                "指标": "EIR_p.a._pct",
                "数值": qc.get("eir_pa_percent"),
            }
        )

    aia = other.get("citi_aia_insurance_time_deposit")
    if isinstance(aia, dict):
        other_rows.append(
            {
                "类别": "Citi-AIA 保险配套（2个月定存宣传）",
                "指标": "最高年利率_p.a._pct",
                "数值": aia.get("max_promo_td_pa_percent"),
            }
        )
        other_rows.append(
            {
                "类别": "Citi-AIA 保险配套（2个月定存宣传）",
                "指标": "页面重复出现次数",
                "数值": aia.get("occurrences"),
            }
        )

    df_other = pd.DataFrame(other_rows)
    if df_other.empty:
        df_other = pd.DataFrame(columns=["类别", "指标", "数值"])

    # -----------------------------------------------------------------------
    # 5) 新元挂牌：df_sgd_board
    # -----------------------------------------------------------------------
    # 对应模板 sheet：`新元挂牌利率`。
    sgd_board_merged = data.get("sgd_board_merged") or []
    df_sgd_board = pd.DataFrame(sgd_board_merged)
    sgd_board_rename = {
        "data_source": "数据来源",
        "product_line": "产品或档位",
        "min_amount_text": "起存金额_页面",
        "max_amount_text": "上限金额_页面",
        "placement_range_text": "资金区间_页面",
        "rate_1w_pct": "7D_pct",
        "rate_2w_pct": "14D_pct",
        "rate_1m_pct": "1M_pct",
        "rate_2m_pct": "2M_pct",
        "rate_3m_pct": "3M_pct",
        "rate_4m_pct": "4M_pct",
        "rate_5m_pct": "5M_pct",
        "rate_6m_pct": "6M_pct",
        "rate_7m_pct": "7M_pct",
        "rate_8m_pct": "8M_pct",
        "rate_9m_pct": "9M_pct",
        "rate_10m_pct": "10M_pct",
        "rate_11m_pct": "11M_pct",
        "rate_12m_pct": "12M_pct",
        "rate_18m_pct": "18M_pct",
        "rate_24m_pct": "24M_pct",
        "rate_36m_pct": "36M_pct",
        "page_raw": "页面原文摘录",
    }
    sgd_board_col_order = list(sgd_board_rename.values())
    if not df_sgd_board.empty:
        df_sgd_board = df_sgd_board.rename(columns=sgd_board_rename)
        df_sgd_board = df_sgd_board[
            [c for c in sgd_board_col_order if c in df_sgd_board.columns]
        ]
    else:
        df_sgd_board = pd.DataFrame(columns=sgd_board_col_order)

    # -----------------------------------------------------------------------
    # 6) 外币挂牌：df_fx_board（仅用于分组创建多 sheet）
    # -----------------------------------------------------------------------
    # 模板写入器会根据 `df_fx_board['币种']` 拆分并创建 `挂牌_{币种}` sheet。
    fx_board_merged = data.get("fx_board_merged") or []
    df_fx_board = pd.DataFrame(fx_board_merged)
    fx_board_rename = {
        "data_source": "数据来源",
        "currency": "币种",
        "product_line": "产品或档位",
        "min_amount_text": "起存金额_页面",
        "max_amount_text": "上限金额_页面",
        "placement_range_text": "资金区间_页面",
        "rate_1w_pct": "7D_pct",
        "rate_2w_pct": "14D_pct",
        "rate_1m_pct": "1M_pct",
        "rate_2m_pct": "2M_pct",
        "rate_3m_pct": "3M_pct",
        "rate_6m_pct": "6M_pct",
        "rate_9m_pct": "9M_pct",
        "rate_12m_pct": "12M_pct",
        "rate_18m_pct": "18M_pct",
        "rate_24m_pct": "24M_pct",
        "rate_36m_pct": "36M_pct",
        "rate_48m_pct": "48M_pct",
        "rate_60m_pct": "60M_pct",
        "page_raw": "页面原文摘录",
    }
    fx_board_col_order = list(fx_board_rename.values())
    if not df_fx_board.empty:
        df_fx_board = df_fx_board.rename(columns=fx_board_rename)
        df_fx_board = df_fx_board[[c for c in fx_board_col_order if c in df_fx_board.columns]]
    else:
        df_fx_board = pd.DataFrame(columns=fx_board_col_order)

    return {
        "df_meta": df_meta,
        "df_sgd": df_sgd,
        "df_sgd_board": df_sgd_board,
        "df_fx": df_fx,
        "df_fx_notes": df_fx_notes,
        "df_other": df_other,
        "df_fx_board": df_fx_board,
    }


# Safety net: 自动给本模块中所有 def 加异常兜底
from bank_safety import auto_wrap_module_functions as _auto_wrap_module_functions

_auto_wrap_module_functions(globals(), module_name=__name__)

