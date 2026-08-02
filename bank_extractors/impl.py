"""
利率抓取与解析实现（从 bank_all_promo_rates 抽离）。

本模块包含 HTTP 会话、各银行 HTML/PDF/JSON 的 extract_* / append_* / merge_* / build_* 等函数，
供 `bank_fetch_and_extract.fetch_and_extract` 直接导入使用，不再依赖 `import __main__`。

模块内大致顺序（与历史实现一致，便于 diff/排查）：
1. 通用工具：`_session`、`_parse_percent`、`_norm_currency_code`、空行模板等
2. 各银行挂牌：extract_*_board / PDF / JSON
3. 促销与合并：`build_sgd_merged`、`merge_fx_citi_cimb`、各 `append_*_rows`
4. Citi 主页面：`extract_sgd_time_deposit`、`extract_fx_time_deposit`、`extract_misc_rates`
"""
from __future__ import annotations

import html as html_module
import io
import json
import math
import re
from copy import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag

from bank_constants import (
    FX_BOARD_INTERNAL_COLS,
    NA,
    SGD_BOARD_INTERNAL_COLS,
    USER_AGENT,
)


def _session(use_env_proxy: bool) -> requests.Session:
    s = requests.Session()
    s.trust_env = use_env_proxy
    s.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-SG,en;q=0.9",
        }
    )
    return s


def _icbc_singapore_get(sess: requests.Session, url: str, timeout: float) -> requests.Response:
    """
    工行新加坡站点（*.icbc.com.cn）在部分 OpenSSL 3 环境下需允许旧式服务端重协商，
    否则握手阶段报 UNSAFE_LEGACY_RENEGOTIATION_DISABLED。
    """
    from urllib.parse import urlparse

    u = url or ""
    parsed = urlparse(u)
    host = (parsed.hostname or "").lower()
    if not host.endswith("icbc.com.cn"):
        return sess.get(u, timeout=timeout)

    import ssl

    from requests.adapters import HTTPAdapter

    class _IcbcTlsAdapter(HTTPAdapter):
        def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
            ctx = ssl.create_default_context()
            if hasattr(ssl, "OP_LEGACY_SERVER_CONNECT"):
                ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
            pool_kwargs["ssl_context"] = ctx
            return super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)

    scheme = parsed.scheme or "https"
    s2 = requests.Session()
    s2.headers.update(sess.headers)
    s2.trust_env = sess.trust_env
    s2.mount(f"{scheme}://{host}", _IcbcTlsAdapter())
    resp = s2.get(u, timeout=timeout)
    # 工行响应常缺 charset，requests 会落成 ISO-8859-1，全角标点会变成 ï¼/ï¼ 乱码。
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp


def _find_column_cmp_text(
    soup: BeautifulSoup,
    h2_text: str,
    fallback_tokens: Optional[List[str]] = None,
) -> Optional[Any]:
    h2 = soup.find("h2", class_="cmp-title__text", string=h2_text)
    if not h2:
        # 页面标题偶发改词（例如去掉/替换 FX），用 token 兜底定位。
        expected = [t.lower() for t in (fallback_tokens or [h2_text]) if str(t).strip()]
        for cand in soup.find_all("h2", class_="cmp-title__text"):
            txt = cand.get_text(" ", strip=True).lower()
            if expected and all(t in txt for t in expected):
                h2 = cand
                break
    if not h2:
        return None
    col = h2.find_parent("div", class_=lambda c: c and "space-y-5" in c)
    if not col:
        return None
    return col.find("div", class_="cmp-text")


def _parse_percent(cell: str) -> Optional[float]:
    m = re.search(r"([\d.]+)\s*%", cell.replace("\xa0", " "))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def parse_sgd_funds_placement(raw: str) -> Dict[str, Optional[str]]:
    """
    Extract new-funds placement range from SGD promo bullet text, e.g.
    '... placement of S$350,000 to S$10 million.'
    """
    norm = re.sub(r"\s+", " ", raw.replace("\xa0", " ")).strip()
    m = re.search(
        r"new funds placement of\s+"
        r"(S\$[\d,]+)\s+to\s+"
        r"(S\$[\d,]+(?:\.\d+)?\s+million)",
        norm,
        re.I,
    )
    if m:
        lo, hi = m.group(1).strip(), m.group(2).strip()
        return {
            "min_amount_text": lo,
            "max_amount_text": hi,
            "placement_range_text": f"{lo} to {hi}",
        }
    m2 = re.search(
        r"new funds placement of\s+(.+?)\.\s*[\^#*]?\s*T",
        norm,
        re.I,
    )
    if m2:
        clause = m2.group(1).strip()
        return {
            "min_amount_text": None,
            "max_amount_text": None,
            "placement_range_text": clause,
        }
    return {
        "min_amount_text": None,
        "max_amount_text": None,
        "placement_range_text": None,
    }


def parse_fx_deposit_limits(notes: List[str]) -> Dict[str, Optional[str]]:
    """
    From FX promo notes, e.g.
    'Minimum deposit of USD 50,000 equivalent and maximum deposit of USD5 million equivalent.'
    """
    for note in notes:
        low = note.lower()
        if "minimum deposit" not in low or "maximum deposit" not in low:
            continue
        min_m = re.search(
            r"Minimum deposit of\s+(.+?)\s+equivalent\s+and",
            note,
            re.I,
        )
        max_m = re.search(
            r"maximum deposit of\s+(.+?)\s+equivalent",
            note,
            re.I,
        )
        return {
            "min_deposit_text": min_m.group(1).strip() if min_m else None,
            "max_deposit_text": max_m.group(1).strip() if max_m else None,
            "terms_sentence": note.strip(),
        }
    return {
        "min_deposit_text": None,
        "max_deposit_text": None,
        "terms_sentence": None,
    }


# ---------------------------------------------------------------------------
# 各机构解析：按银行/页面从 HTML·PDF·JSON 抽取结构化行（extract_* / append_* / build_*）
# 促销与挂牌函数在文件中交错排列，请用 rg "^def extract_" 或 rg "^def append_" 检索。
# ---------------------------------------------------------------------------


def extract_cimb_fcy_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Parse CIMB FCY online promotion table (1/3/6/12 months) from product page HTML.
    See: https://www.cimb.com.sg/en/personal/banking-with-us/accounts/fixed-deposit/cimb-foreign-currency-fixed-deposit-account.html
    """
    out: Dict[str, Any] = {
        "currencies": {},
        "notes": [],
        "min_deposit_text": None,
        "promotion_intro": None,
    }
    h2 = soup.find("h2", string=re.compile(r"Exclusive Online Promotion", re.I))
    if h2:
        np = h2.find_next("p")
        if np:
            t = np.get_text(" ", strip=True)
            if t:
                out["promotion_intro"] = t
    for table in soup.find_all("table"):
        rows: List[List[str]] = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            rows.append(cells)
        header_idx: Optional[int] = None
        for i, row in enumerate(rows):
            joined = " ".join(row[:4]) if len(row) >= 4 else ""
            if len(row) >= 4 and "1 Month" in row[0] and "3 Month" in joined:
                header_idx = i
                break
        if header_idx is None:
            continue
        for row in rows[header_idx + 1 :]:
            if len(row) < 5:
                continue
            cur = re.sub(r"\s+", "", row[0]).upper()
            if len(cur) != 3 or not cur.isalpha():
                continue
            nums: List[float] = []
            ok = True
            for c in row[1:5]:
                m = re.search(r"([\d.]+)", c.replace(",", ""))
                if not m:
                    ok = False
                    break
                nums.append(float(m.group(1)))
            if not ok or len(nums) != 4:
                continue
            out["currencies"][cur] = {
                "1m": nums[0],
                "3m": nums[1],
                "6m": nums[2],
                "12m": nums[3],
            }
        if out["currencies"]:
            break
    for p in soup.find_all("p"):
        t = p.get_text(" ", strip=True)
        if "10,000" in t and "minimum" in t.lower():
            out["min_deposit_text"] = t
            if t not in out["notes"]:
                out["notes"].append(t)
            break
    return out


def _cimb_tenure_month_key(cell: str) -> Optional[str]:
    m = re.search(r"(\d+)\s*Months?", cell, re.I)
    if not m:
        return None
    return f"{int(m.group(1))}m"


def extract_cimb_sgd_rates(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    CIMB SGD FD rates page: online promo (Personal / Preferred) and WWFD-i promo.
    https://www.cimb.com.sg/en/personal/help-support/rates-charges/rates/sgd-fixed-deposit-rates.html
    """
    out: Dict[str, Any] = {
        "online_personal": {},
        "online_preferred": {},
        "online_tier_note": None,
        "why_wait_fd_i": {},
        "why_wait_tier_note": None,
    }
    h3 = soup.find(
        "h3",
        string=re.compile(r"Exclusive CIMB SGD Online Fixed Deposit Promotion", re.I),
    )
    if h3:
        table = h3.find_next("table")
        if table:
            trs = table.find_all("tr")
            if trs:
                hdr = [c.get_text(" ", strip=True) for c in trs[0].find_all(["th", "td"])]
                if any("10,000" in x for x in hdr):
                    out["online_tier_note"] = "S$10,000 and above (online promo)"
                for tr in trs[1:]:
                    cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                    if len(cells) < 3:
                        continue
                    tk = _cimb_tenure_month_key(cells[0])
                    if not tk:
                        continue
                    try:
                        p = float(re.findall(r"[\d.]+", cells[1].replace(",", ""))[0])
                        q = float(re.findall(r"[\d.]+", cells[2].replace(",", ""))[0])
                    except (IndexError, ValueError):
                        continue
                    out["online_personal"][tk] = p
                    out["online_preferred"][tk] = q

    h3w = soup.find(
        "h3",
        string=re.compile(r"Why Wait Fixed Deposit-i", re.I),
    )
    if h3w:
        table = h3w.find_next("table")
        if table:
            for tr in table.find_all("tr")[1:]:
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                if len(cells) < 2:
                    continue
                tk = _cimb_tenure_month_key(cells[0])
                if not tk:
                    continue
                try:
                    v = float(re.findall(r"[\d.]+", cells[1].replace(",", ""))[0])
                except (IndexError, ValueError):
                    continue
                out["why_wait_fd_i"][tk] = v
            out["why_wait_tier_note"] = "S$10,000 & Above (WWFD-i online promo)"
    return out


def _parse_board_rate_cell(cell: str) -> Optional[float]:
    if not cell:
        return None
    t = cell.replace(",", "").replace("%", "").strip()
    m = re.search(r"([\d.]+)", t)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _boc_fx_pct_normalize_for_sheet(currency_code: str, pct_val: float) -> float:
    """
    BOC SG 外币挂牌表在同一「年利率」栏混用两种写法：
    - 常见货币（如 GBP/USD/HKD）：数字即 **% p.a.**（例 1.50 = 1.50%）。
    - EUR、JPY 等低息币种：页面常写 **按年小数比例**（例 0.0001 表示 0.01% p.a.），
      若原样写入会与 BEA 等「直接百分数」不一致。

    规则：仅对 EUR/JPY，当 0 < 值 < 0.01 时乘以 100，转为与其它行一致的百分数。
    """
    if currency_code not in ("EUR", "JPY"):
        return pct_val
    if pct_val <= 0 or pct_val >= 0.01:
        return pct_val
    return pct_val * 100.0


def _empty_sgd_board_row(data_source: str, product_line: str) -> Dict[str, Any]:
    d = {k: NA for k in SGD_BOARD_INTERNAL_COLS}
    d["data_source"] = data_source
    d["product_line"] = product_line
    return d


def _empty_fx_board_row(data_source: str, currency: str, product_line: str) -> Dict[str, Any]:
    d = {k: NA for k in FX_BOARD_INTERNAL_COLS}
    d["data_source"] = data_source
    d["currency"] = currency
    d["product_line"] = product_line
    return d


def _month_key_from_int(n: int) -> Optional[str]:
    """Map month count (1–12, 18, 24, 36) to internal rate_*_pct keys."""
    m = {
        1: "rate_1m_pct",
        2: "rate_2m_pct",
        3: "rate_3m_pct",
        4: "rate_4m_pct",
        5: "rate_5m_pct",
        6: "rate_6m_pct",
        7: "rate_7m_pct",
        8: "rate_8m_pct",
        9: "rate_9m_pct",
        10: "rate_10m_pct",
        11: "rate_11m_pct",
        12: "rate_12m_pct",
        18: "rate_18m_pct",
        24: "rate_24m_pct",
        36: "rate_36m_pct",
    }
    return m.get(n)


def _fx_month_key_from_int(n: int) -> Optional[str]:
    m = {
        1: "rate_1m_pct",
        2: "rate_2m_pct",
        3: "rate_3m_pct",
        6: "rate_6m_pct",
        9: "rate_9m_pct",
        12: "rate_12m_pct",
        18: "rate_18m_pct",
        24: "rate_24m_pct",
        36: "rate_36m_pct",
        48: "rate_48m_pct",
        60: "rate_60m_pct",
    }
    return m.get(n)


def _norm_currency_code(raw: str) -> str:
    t = re.sub(r"\s+", " ", (raw or "").strip()).upper()
    direct = re.search(r"\b(USD|AUD|GBP|EUR|HKD|CNH|JPY|CAD|NZD|CHF|SGD)\b", t)
    if direct:
        return direct.group(1)
    mapping = {
        "UNITED STATES DOLLAR": "USD",
        "US DOLLAR": "USD",
        "U.S. DOLLAR": "USD",
        "STERLING POUND": "GBP",
        "BRITISH POUND": "GBP",
        "AUSTRALIAN DOLLAR": "AUD",
        "NEW ZEALAND DOLLAR": "NZD",
        "CANADIAN DOLLAR": "CAD",
        "SWISS FRANC": "CHF",
        "JAPANESE YEN": "JPY",
        "CHINESE YUAN": "CNH",
        "OFFSHORE CNY": "CNH",
        "EURO": "EUR",
    }
    for k, v in mapping.items():
        if k in t:
            return v
    return t[:3] if t else NA


def extract_cimb_sgd_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    CIMB SGD FD *board* rates (non-Islamic table):
    Tenure (Months) | S$1,000–$99,999 | S$100,000 & Above
    """
    rows: List[Dict[str, Any]] = []
    for table in soup.find_all("table"):
        ttxt = table.get_text(" ", strip=True)
        if "Islamic" in ttxt and "profit" in ttxt.lower():
            continue
        if "Exclusive CIMB SGD Online" in ttxt or "Why Wait" in ttxt:
            continue
        if "Board Rates" not in ttxt:
            continue
        if "Tenure" not in ttxt and "Months" not in ttxt:
            continue
        if "1,000" not in ttxt and "1.000" not in ttxt:
            continue
        if "100,000" not in ttxt and "100.000" not in ttxt:
            continue

        low = _empty_sgd_board_row("CIMB", "SGD FD Board — S$1,000-$99,999")
        low["placement_range_text"] = "Board: S$1,000 - $99,999"
        high = _empty_sgd_board_row("CIMB", "SGD FD Board — S$100,000 & above")
        high["placement_range_text"] = "Board: S$100,000 & above"
        note = (
            "Note: *1-month and 2-month tenors may require min S$5,000 (see CIMB page)."
        )
        low["page_raw"] = note
        high["page_raw"] = note

        for tr in table.find_all("tr")[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            ten = cells[0].strip()
            if re.match(r"^tenure", ten, re.I):
                continue
            mo = re.search(r"(\d+)", ten.replace("*", ""))
            if not mo:
                continue
            n = int(mo.group(1))
            rk = _month_key_from_int(n)
            if not rk:
                continue
            r0 = _parse_board_rate_cell(cells[1])
            r1 = _parse_board_rate_cell(cells[2])
            if r0 is not None:
                low[rk] = r0
            if r1 is not None:
                high[rk] = r1
        rows.extend([low, high])
        break
    return rows


def extract_citi_sgd_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    table = None
    for t in soup.find_all("table"):
        ttxt = t.get_text(" ", strip=True)
        if re.search(r"Board Rates of (Singapore Dollar )?Time Deposits", ttxt, re.I) and re.search(
            r"Singapore Dollar|SGD", ttxt, re.I
        ):
            table = t
            break
    if not table:
        for t in soup.find_all("table"):
            tx = t.get_text(" ", strip=True)
            if "Placement Amount" in tx and "Month" in tx and re.search(r"Week|Weeks", tx, re.I):
                table = t
                break
    if not table:
        return rows

    trs = table.find_all("tr")
    if len(trs) < 2:
        return rows
    header_cells = [c.get_text(" ", strip=True) for c in trs[0].find_all(["th", "td"])]
    col_map: Dict[str, int] = {}
    for i, h in enumerate(header_cells):
        hl = h.lower()
        if "placement" in hl and "amount" in hl:
            col_map["placement"] = i
        elif re.search(r"1\s*(to|-|–)?\s*2\s*weeks?", hl, re.I):
            col_map["1w2w"] = i
        elif re.search(r"1\s*week", hl, re.I):
            col_map["1w"] = i
        elif re.search(r"2\s*week", hl, re.I):
            col_map["2w"] = i
        elif re.search(r"\b1\s*month\b", hl, re.I):
            col_map["1m"] = i
        elif re.search(r"\b2\s*month\b", hl, re.I):
            col_map["2m"] = i
        elif re.search(r"\b3\s*month\b", hl, re.I):
            col_map["3m"] = i
        elif re.search(r"\b6\s*month\b", hl, re.I):
            col_map["6m"] = i
        elif re.search(r"\b12\s*month\b", hl, re.I):
            col_map["12m"] = i
        elif re.search(r"\b24\s*month\b", hl, re.I):
            col_map["24m"] = i
        elif re.search(r"\b36\s*month\b", hl, re.I):
            col_map["36m"] = i

    for tr in trs[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        placement = cells[col_map.get("placement", 0)] if col_map.get("placement") is not None else cells[0]
        if re.match(r"^placement", placement, re.I):
            continue
        row = _empty_sgd_board_row("Citibank", f"SGD TD Board — {placement}")
        row["placement_range_text"] = placement
        key_map = {
            "1w": "rate_1w_pct",
            "2w": "rate_2w_pct",
            "1m": "rate_1m_pct",
            "2m": "rate_2m_pct",
            "3m": "rate_3m_pct",
            "6m": "rate_6m_pct",
            "12m": "rate_12m_pct",
            "24m": "rate_24m_pct",
            "36m": "rate_36m_pct",
        }
        for ck, rk in key_map.items():
            if ck not in col_map:
                continue
            j = col_map[ck]
            if j < len(cells):
                v = _parse_percent(cells[j])
                if v is None:
                    v = _parse_board_rate_cell(cells[j])
                if v is not None:
                    row[rk] = v
        if "1w2w" in col_map:
            j = col_map["1w2w"]
            if j < len(cells):
                v = _parse_percent(cells[j])
                if v is None:
                    v = _parse_board_rate_cell(cells[j])
                if v is not None:
                    row["rate_1w_pct"] = v
                    row["rate_2w_pct"] = v
        rows.append(row)
    return rows


def _dbs_period_cell_to_months(cell: str) -> Optional[int]:
    s = cell.strip().lower()
    m = re.search(r"(\d+)\s*mths?", s)
    if m:
        return int(m.group(1))
    m2 = re.search(r"(\d+)\s*month", s)
    if m2:
        return int(m2.group(1))
    return None


def extract_dbs_sgd_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    DBS S$ FD rates page (Next.js): HTML contains a table with
    Period | $ bands... — rates are decimals without a % sign in cells.
    """
    rows: List[Dict[str, Any]] = []
    table = None
    for t in soup.find_all("table"):
        txt = t.get_text(" ", strip=True)
        if "Period" in txt and re.search(r"\d+\s*mths?", txt, re.I):
            table = t
            break
    if not table:
        return rows

    trs = table.find_all("tr")
    if len(trs) < 2:
        return rows
    header_cells = [c.get_text(" ", strip=True) for c in trs[0].find_all(["th", "td"])]
    if not header_cells:
        return rows
    period_hdr = header_cells[0].strip().lower()
    if "period" not in period_hdr:
        return rows

    bands = [h.strip() for h in header_cells[1:] if h.strip()]
    if not bands:
        return rows

    # band_label -> { rate_XXm_pct: float }
    acc: Dict[str, Dict[str, float]] = {b: {} for b in bands}

    for tr in trs[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        months = _dbs_period_cell_to_months(cells[0])
        if months is None:
            continue
        rk = _month_key_from_int(months)
        if not rk:
            continue
        for j, band in enumerate(bands):
            ci = j + 1
            if ci >= len(cells):
                continue
            v = _parse_percent(cells[ci]) or _parse_board_rate_cell(cells[ci])
            if v is not None:
                acc[band][rk] = v

    for band, tens in acc.items():
        if not tens:
            continue
        row = _empty_sgd_board_row("DBS", f"SGD FD Board — {band}")
        row["placement_range_text"] = band
        non_na_vals = [v for v in tens.values() if v is not None]
        if non_na_vals and len(set(non_na_vals)) == 1:
            # DBS 页面部分金额档位会出现“各期限同率”（例如全为 0.05），显式标注避免误判为抓取异常。
            row["page_raw"] = f"源站挂牌同率（各期限同率：{non_na_vals[0]}）"
        for rk, v in tens.items():
            row[rk] = v
        rows.append(row)
    return rows


def extract_dbs_fcy_board_from_api(data: Any) -> List[Dict[str, Any]]:
    """
    DBS FCY FD board rates from SG rates API:
    /sg-rates-api/v1/api/sgrates/getSGFCFDRates
    """
    rows: List[Dict[str, Any]] = []
    if not isinstance(data, list):
        return rows
    for blk in data:
        if not isinstance(blk, dict):
            continue
        rec_cols = blk.get("recCol") or []
        records = blk.get("records") or []
        if not isinstance(rec_cols, list) or not isinstance(records, list):
            continue
        cur = None
        if len(rec_cols) >= 1:
            mcur = re.search(r"\(([A-Z]{3})\)", str(rec_cols[0]))
            if mcur:
                cur = mcur.group(1).upper()
        if not cur:
            mcur2 = re.search(r"\b([A-Z]{3})\b", str(blk.get("name") or ""))
            cur = mcur2.group(1).upper() if mcur2 else None
        if not cur or not re.match(r"^[A-Z]{3}$", cur):
            continue
        for rec in records:
            if not isinstance(rec, dict):
                continue
            unit = str(rec.get("unit") or "").strip() or NA
            r = _empty_fx_board_row("DBS", cur, f"FCY FD Board — {cur} — {unit}")
            r["placement_range_text"] = unit
            # val1..val7 in API: 1 day, 1 week, 1m, 2m, 3m, 6m, 12m
            key_map = [
                ("val1", None),
                ("val2", "rate_1w_pct"),
                ("val3", "rate_1m_pct"),
                ("val4", "rate_2m_pct"),
                ("val5", "rate_3m_pct"),
                ("val6", "rate_6m_pct"),
                ("val7", "rate_12m_pct"),
            ]
            has_any = False
            for src_k, dst_k in key_map:
                if not dst_k:
                    continue
                pv = _parse_board_rate_cell(str(rec.get(src_k) or ""))
                if pv is None:
                    continue
                r[dst_k] = pv
                has_any = True
            if has_any:
                rows.append(r)
    return rows


def extract_hl_sgd_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """HL Bank: SGD baseline Board rates — 优先解析官方标注的 SGD 表。"""
    rows: List[Dict[str, Any]] = []
    tables: List[Any] = []
    t_sgd = soup.select_one('table[data-for-currency="SGD"]')
    if t_sgd is not None:
        tables.append(t_sgd)
    else:
        for table in soup.find_all("table"):
            ttxt = table.get_text(" ", strip=True)
            if "Oops" in ttxt and "problem" in ttxt.lower():
                continue
            if "TENOR" not in ttxt or "BOARD" not in ttxt.upper():
                continue
            if re.search(r"TENOR\s+RATES\s*%", ttxt, re.I) and not re.search(
                r"BOARD\s+RATES", ttxt, re.I
            ):
                continue
            probe = None
            for tr in table.find_all("tr")[1:4]:
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
                if len(cells) >= 2 and re.search(r"MONTH", cells[0], re.I):
                    probe = _parse_board_rate_cell(cells[1])
                    break
            if probe is not None and probe > 2.0:
                continue
            tables.append(table)
            break

    for table in tables:
        r = _empty_sgd_board_row("HL Bank", "SGD FD Board rates")
        r["placement_range_text"] = "Board (SGD)"
        if table.get("data-for-currency", "").upper() == "SGD":
            r["product_line"] = "SGD Board rates（HL 页面标注之 BOARD RATES；非促销档）"
            r["page_raw"] = (
                "table[data-for-currency=SGD]，第二列为 BOARD RATES % (p.a.)。"
                "较高利率见「新元定存促销」sheet（HL 促销页 Online/Branch）。"
            )
        for tr in table.find_all("tr")[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            ten = cells[0].upper()
            if "TENOR" in ten:
                continue
            mo = re.search(r"(\d+)\s*MONTH", ten)
            if not mo:
                continue
            n = int(mo.group(1))
            rk = _month_key_from_int(n)
            if not rk:
                continue
            v = _parse_percent(cells[1]) or _parse_board_rate_cell(cells[1])
            if v is not None:
                r[rk] = v
        rows.append(r)
    return rows


def extract_hlf_sgd_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for table in soup.find_all("table"):
        # HLF uses NBSP between "Board" and "Rates"; normalize before substring checks.
        ttxt = table.get_text(" ", strip=True).replace("\xa0", " ")
        if "Tenure" not in ttxt or "Board Rates" not in ttxt:
            continue
        # Second tier column may be split across tags; do not require substring "Special Rates".
        if "50,000" not in ttxt and "50000" not in ttxt.replace(",", ""):
            continue
        low = _empty_sgd_board_row("HLF", "SGD FD Board — <= S$50,000")
        low["placement_range_text"] = "Board Rates (<= S$50,000)"
        high = _empty_sgd_board_row("HLF", "SGD FD Board — > S$50,000")
        high["placement_range_text"] = "Special Rates (> S$50,000)"
        tr0 = table.find("tr")
        if not tr0:
            continue
        hdr = [c.get_text(" ", strip=True) for c in tr0.find_all(["th", "td"])]
        br_i = sp_i = None
        for i, h in enumerate(hdr):
            hl = h.lower()
            if "board" in hl and "rate" in hl:
                br_i = i
            if "special" in hl:
                sp_i = i
        if br_i is None and len(hdr) >= 3:
            br_i, sp_i = 1, 2
        for tr in table.find_all("tr")[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            ten = cells[0].strip()
            if re.match(r"^tenure", ten, re.I):
                continue
            mo = re.search(r"(\d+)", ten)
            if not mo:
                continue
            n = int(mo.group(1))
            rk = _month_key_from_int(n)
            if not rk:
                continue
            if br_i is not None and br_i < len(cells):
                v = _parse_board_rate_cell(cells[br_i])
                if v is not None:
                    low[rk] = v
            if sp_i is not None and sp_i < len(cells):
                v2 = _parse_board_rate_cell(cells[sp_i])
                if v2 is not None:
                    high[rk] = v2
        rows.extend([low, high])
        break
    return rows


def _hsbc_board_th_to_key(th_text: str) -> Optional[str]:
    t = re.sub(r"\s+", " ", th_text.replace("\xa0", " ")).strip().lower()
    m = re.search(r"(\d+)\s*month", t)
    if not m:
        return None
    return _month_key_from_int(int(m.group(1)))


def extract_hsbc_sgd_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: HSBC table caption/class/header wording may change.
    """
    HSBC Singapore SGD time deposit *board* tables (English rates page).
    https://www.hsbc.com.sg/rates/singapore-dollar-deposits/
    """
    rows: List[Dict[str, Any]] = []
    for table in soup.find_all("table", class_="desktop"):
        cap_el = table.find("caption")
        cap = cap_el.get_text(" ", strip=True) if cap_el else ""
        if "Personal Banking Interest Rates" in cap:
            segment = "Personal Banking"
        elif "Premier Interest Rates" in cap:
            segment = "Premier"
        else:
            continue
        thead = table.find("thead")
        tbody = table.find("tbody")
        if not thead or not tbody:
            continue
        hdr_tr = thead.find("tr")
        if not hdr_tr:
            continue
        ths = hdr_tr.find_all("th")
        if not ths or "placement" not in ths[0].get_text(" ", strip=True).lower():
            continue
        col_keys: List[Optional[str]] = []
        for th in ths[1:]:
            col_keys.append(_hsbc_board_th_to_key(th.get_text(" ", strip=True)))
        for tr in tbody.find_all("tr"):
            label_cell = tr.find(["th", "td"])
            if not label_cell:
                continue
            placement = re.sub(
                r"\s+", " ", label_cell.get_text(" ", strip=True).replace("\xa0", " ")
            )
            if not placement or placement.lower() == "placement amount":
                continue
            tds = tr.find_all("td")
            if len(tds) < len(col_keys):
                continue
            r = _empty_sgd_board_row(
                "HSBC",
                f"SGD TD board — {segment} — {placement}",
            )
            r["placement_range_text"] = placement
            for j, rk in enumerate(col_keys):
                if not rk or j >= len(tds):
                    continue
                v = _parse_percent(tds[j].get_text(" ", strip=True))
                if v is not None:
                    r[rk] = v
            rows.append(r)
    return rows


def extract_icbc_sgd_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: ICBC nested tables and header text "Amount (SGD)/Tenor" are brittle.
    """
    ICBC Singapore: SGD fixed deposit *board* table (section (3) on FD page).
    """
    rows: List[Dict[str, Any]] = []
    content = soup.find("td", id="mypagehtmlcontent")
    if not content:
        content = soup.find("td", class_=lambda c: c and "LinkSec" in (c or ""))
    if not content:
        return rows
    amount_td = None
    for td in content.find_all("td"):
        if "Amount (SGD)/Tenor" in td.get_text(" ", strip=True):
            if len(td.get_text(" ", strip=True)) < 48:
                amount_td = td
                break
    if not amount_td:
        return rows
    hdr_tr = amount_td.find_parent("tr")
    if not hdr_tr:
        return rows
    table = hdr_tr.find_parent("table")
    if not table:
        return rows
    tbody = table.find("tbody") or table
    body_trs = tbody.find_all("tr", recursive=False)
    hdr_cells = hdr_tr.find_all(["td", "th"])
    col_keys: List[Optional[str]] = [None]
    for hc in hdr_cells[1:]:
        ht = hc.get_text(" ", strip=True).lower()
        mk: Optional[str] = None
        if "1 month" in ht:
            mk = "rate_1m_pct"
        elif "3 month" in ht:
            mk = "rate_3m_pct"
        elif "6 month" in ht:
            mk = "rate_6m_pct"
        elif "9 month" in ht:
            mk = "rate_9m_pct"
        elif "12 month" in ht:
            mk = "rate_12m_pct"
        col_keys.append(mk)
    for tr in body_trs[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        band = re.sub(
            r"\s+", " ", cells[0].get_text(" ", strip=True).replace("\xa0", " ")
        )
        if (not band) or (
            "amount" in band.lower() and "tenor" in band.lower()
        ):
            continue
        r = _empty_sgd_board_row(
            "ICBC SG",
            f"SGD FD board — {band}",
        )
        r["placement_range_text"] = band
        for j, rk in enumerate(col_keys):
            if not rk or j >= len(cells):
                continue
            v = _parse_percent(cells[j].get_text(" ", strip=True))
            if v is None:
                v = _parse_board_rate_cell(cells[j].get_text(" ", strip=True))
            if v is not None:
                r[rk] = v
        rows.append(r)
    return rows


UOB_FCY_BOARD_JSON_URL = (
    "https://www.uobgroup.com/data-api-rates/data-api/fcfd"
    "?dcr=/online-rates/data/foreign-currency-fixed-deposits"
)


def _icbc_fcy_preceding_text_tail(table: Tag, max_chars: int = 420) -> str:
    parts: List[str] = []
    n = 0
    for s in table.find_all_previous(string=True, limit=160):
        if not isinstance(s, str):
            continue
        chunk = s.strip()
        if not chunk:
            continue
        parts.append(chunk)
        n += len(chunk)
        if n >= max_chars:
            break
    blob = " ".join(reversed(parts))
    return blob[-max_chars:] if len(blob) > max_chars else blob


def _icbc_fcy_table_is_interest_board(table: Tag) -> bool:
    tail = _icbc_fcy_preceding_text_tail(table).lower()
    if re.search(r"fixed\s+deposit\s+interest\s+board\s+rate", tail, re.I):
        return True
    if "interest board rate" in tail:
        return True
    return False


def _icbc_fcy_tenor_header_to_key(ht: str) -> Optional[str]:
    t = re.sub(r"\s+", " ", (ht or "").replace("\xa0", " ")).strip().lower()
    if not t:
        return None
    if "1 week" in t or re.fullmatch(r"1\s*w(eek)?", t):
        return "rate_1w_pct"
    if "2 week" in t or re.fullmatch(r"2\s*w(eek)?", t):
        return "rate_2w_pct"
    if "1 month" in t or t == "1 m":
        return "rate_1m_pct"
    if "2 month" in t:
        return "rate_2m_pct"
    if "3 month" in t:
        return "rate_3m_pct"
    if "6 month" in t:
        return "rate_6m_pct"
    if "9 month" in t:
        return "rate_9m_pct"
    if "12 month" in t or "1 year" in t or t == "1 yr":
        return "rate_12m_pct"
    if "18 month" in t:
        return "rate_18m_pct"
    if "24 month" in t or "2 year" in t:
        return "rate_24m_pct"
    return None


def extract_icbc_fcy_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: ICBC SG FD page nests SGD/USD/RMB board tables inside one giant cell.
    """
    ICBC Singapore: foreign-currency FD *board* tables on the same CMS page as SGD board
    (Amount(USD), Amount(RMB), …). RMB 表记为 CNH，与其它银行「离岸人民币」挂牌 sheet 一致。
    """
    rows: List[Dict[str, Any]] = []
    content = soup.find("td", id="mypagehtmlcontent")
    if not content:
        content = soup.find("td", class_=lambda c: c and "LinkSec" in (c or ""))
    if not content:
        return rows
    for table in content.find_all("table"):
        tr0 = table.find("tr")
        if not tr0:
            continue
        c0 = tr0.find(["td", "th"])
        if not c0:
            continue
        first_txt = c0.get_text(" ", strip=True)
        m_amt = re.match(r"Amount\s*\(([^)]+)\)\s*$", first_txt.strip(), re.I)
        if not m_amt:
            continue
        raw_ccy = m_amt.group(1).strip().upper()
        if raw_ccy in ("SGD",):
            continue
        if not _icbc_fcy_table_is_interest_board(table):
            continue
        if raw_ccy == "RMB":
            cur = "CNH"
        else:
            cur = _norm_currency_code(raw_ccy)
            if not re.match(r"^[A-Z]{3}$", cur):
                continue
        tbody = table.find("tbody") or table
        body_trs = tbody.find_all("tr", recursive=False)
        if len(body_trs) < 2:
            continue
        hdr_cells = body_trs[0].find_all(["td", "th"])
        col_keys: List[Optional[str]] = [None]
        for hc in hdr_cells[1:]:
            col_keys.append(_icbc_fcy_tenor_header_to_key(hc.get_text(" ", strip=True)))
        for tr in body_trs[1:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            band = re.sub(
                r"\s+", " ", cells[0].get_text(" ", strip=True).replace("\xa0", " ")
            )
            if not band or "amount" in band.lower():
                continue
            r = _empty_fx_board_row(
                "ICBC SG",
                cur,
                f"{cur} FD board — {band}",
            )
            r["placement_range_text"] = band
            for j, rk in enumerate(col_keys):
                if not rk or j >= len(cells):
                    continue
                raw_cell = cells[j].get_text(" ", strip=True)
                v = _parse_percent(raw_cell)
                if v is None:
                    v = _parse_board_rate_cell(raw_cell)
                if v is not None:
                    r[rk] = v
            rows.append(r)
    return rows


def extract_uob_fcy_board_from_api(rows_json: Any) -> List[Dict[str, Any]]:
    """
    UOB：外币定存挂牌利率来自 uobgroup.com 的 JSON API（列表页 tbody 由脚本填充）。
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(rows_json, list):
        return out
    key_map = {
        "W1": "rate_1w_pct",
        "W2": "rate_2w_pct",
        "M1": "rate_1m_pct",
        "M2": "rate_2m_pct",
        "M3": "rate_3m_pct",
        "M6": "rate_6m_pct",
        "M12": "rate_12m_pct",
    }
    for item in rows_json:
        if not isinstance(item, dict):
            continue
        raw_ccy = str(item.get("CCY") or "").strip().upper()
        if not re.match(r"^[A-Z]{3}$", raw_ccy):
            continue
        band = str(item.get("RATERANGE") or "").strip()
        if not band:
            continue
        r = _empty_fx_board_row(
            "UOB",
            raw_ccy,
            f"{raw_ccy} FD board — {band}",
        )
        r["placement_range_text"] = band
        for src, dst in key_map.items():
            raw_v = item.get(src)
            if raw_v is None:
                continue
            v = _parse_board_rate_cell(str(raw_v))
            if v is not None:
                r[dst] = v
        out.append(r)
    return out


def _ocbc_daily_fd_tenor_header_to_key(ht: str) -> Optional[str]:
    """Map OCBC daily FCY TD column header to internal rate_* key (5/7/8M 暂无列，略过)."""
    t = re.sub(r"\s+", " ", (ht or "").replace("\xa0", " ")).strip().lower()
    if not t or "value date" in t:
        return None
    if t == "1-month":
        return "rate_1m_pct"
    if t == "2-month":
        return "rate_2m_pct"
    if t == "3-month":
        return "rate_3m_pct"
    if t in ("5-month", "7-month", "8-month"):
        return None
    if t == "6-month":
        return "rate_6m_pct"
    if t == "9-month":
        return "rate_9m_pct"
    if t == "12-month":
        return "rate_12m_pct"
    return None


def _ocbc_table_has_daily_fd_header(table: Tag) -> bool:
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 3:
            continue
        if cells[0].strip().lower() == "time deposit amt" and "1-month" in cells[1].lower():
            return True
    return False


def _ocbc_extract_fcy_rows_from_daily_fd_table(table: Tag) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    cur: Optional[str] = None
    col_keys: List[Optional[str]] = []
    seen_header = False

    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if not cells:
            continue
        joined = " ".join(cells)

        if len(cells) <= 4 and "time deposit amt" not in joined.lower():
            m = re.search(r"\b([A-Z]{3})\s*-\s+", joined)
            if m:
                cur = m.group(1).upper()
                if cur in ("THE", "FOR", "AND"):
                    cur = None
                    continue
                col_keys = []
                seen_header = False
            continue

        c0 = cells[0].strip()
        c0l = c0.lower()
        if c0l == "time deposit amt" and len(cells) > 2 and "1-month" in cells[1].lower():
            col_keys = []
            for h in cells[1:]:
                ht = h.strip()
                if re.match(r"^value date", ht, re.I):
                    break
                col_keys.append(_ocbc_daily_fd_tenor_header_to_key(ht))
            seen_header = True
            continue

        if not (seen_header and cur and col_keys):
            continue
        if c0l in ("time deposit amt", "value date"):
            continue
        if "back to top" in c0l:
            continue

        band = c0
        if not band:
            continue

        value_date = ""
        rest = cells[1:]
        if rest and re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", rest[-1].strip()):
            value_date = rest[-1].strip()
            rate_cells = rest[:-1]
        else:
            rate_cells = rest

        if len(rate_cells) < len(col_keys):
            continue

        r = _empty_fx_board_row("OCBC", cur, f"{cur} FCY TD daily — {band}")
        r["placement_range_text"] = band
        if value_date:
            r["page_raw"] = f"Value date: {value_date}"
        for j, rk in enumerate(col_keys):
            if not rk or j >= len(rate_cells):
                continue
            v = _parse_board_rate_cell(rate_cells[j])
            if v is None:
                continue
            r[rk] = v
        rows.append(r)

    return rows


def extract_ocbc_fcy_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: `interest-rates` 页 #foreign-listing 常为 CSR；日价页 `daily_price_fd.html` 为静态多表。
    """
    OCBC 外币定存利率（挂牌/日价）：

    - 推荐数据源：`/rates/daily_price_fd.html`（各币种 + 分档 + 1/2/3/6/9/12 月等列；5/7/8 月列当前不入库）。
    - 若抓取的是 `interest-rates` 且首包无表，则返回空列表。
    """
    out: List[Dict[str, Any]] = []
    for table in soup.find_all("table"):
        if not _ocbc_table_has_daily_fd_header(table):
            continue
        out.extend(_ocbc_extract_fcy_rows_from_daily_fd_table(table))

    seen: set[tuple[Any, ...]] = set()
    dedup: List[Dict[str, Any]] = []
    for r in out:
        key = (
            r.get("currency"),
            r.get("placement_range_text"),
            r.get("rate_1m_pct"),
            r.get("rate_3m_pct"),
            r.get("rate_6m_pct"),
            r.get("rate_12m_pct"),
        )
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)

    if dedup:
        return dedup

    host = soup.find(id="foreign-listing")
    if host:
        blob = host.get_text(" ", strip=True).lower()
        if "loading" in blob and not host.find("table"):
            return []
    return []


def extract_maybank_sgd_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: Maybank HTML is semi-malformed (Month(s) may be outside <tr>).
    """
    Maybank Singapore: SGD time deposit board (anchor #sgtd, not CPF / iSAVvy).
    """
    table = None
    for t in soup.find_all("table"):
        blob = t.get_text(" ", strip=True)
        if "Singapore Dollar Time Deposit (%p.a.)" not in blob:
            continue
        if "CPF" in blob[:500] and "Singapore Dollar Time Deposit (CPF)" in blob[:800]:
            continue
        if "iSAVvy" in blob[:300]:
            continue
        if "Month(s)" not in blob:
            continue
        table = t
        break
    if not table:
        return []
    month_td = None
    for td in table.find_all("td"):
        tx = td.get_text(" ", strip=True).lower()
        if tx == "month(s)" or tx.startswith("month(s)"):
            month_td = td
            break
    if not month_td:
        return []
    hdr_tr = month_td.find_parent("tr")
    if hdr_tr:
        tier_cells = hdr_tr.find_all(["td", "th"])[1:]
    else:
        sibs = []
        for s in month_td.find_next_siblings(["td", "th"]):
            sibs.append(s)
        tier_cells = sibs
    tier_names = [
        re.sub(r"\s+", " ", c.get_text(" ", strip=True)) for c in tier_cells
    ]
    if not tier_names:
        return []
    acc: Dict[str, Dict[str, Any]] = {}
    for tname in tier_names:
        acc[tname] = _empty_sgd_board_row(
            "Maybank",
            f"SGD TD board — {tname}",
        )
        acc[tname]["placement_range_text"] = tname
    data_trs = table.find_all("tr")
    for tr in data_trs:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        if hdr_tr is not None and tr == hdr_tr:
            continue
        ten0 = cells[0].get_text(" ", strip=True).lower()
        if ten0.startswith("month"):
            continue
        ten = cells[0].get_text(" ", strip=True)
        ten = re.sub(r"\s+", " ", ten.replace("\xa0", " "))
        if "month" in ten.lower():
            continue
        mo = re.search(r"(\d+)", ten)
        if not mo:
            continue
        n = int(mo.group(1))
        rk = _month_key_from_int(n)
        if not rk:
            continue
        for j, tname in enumerate(tier_names):
            if j + 1 >= len(cells):
                break
            v = _parse_board_rate_cell(cells[j + 1].get_text(" ", strip=True))
            if v is not None:
                acc[tname][rk] = v
    return list(acc.values())


def _ocbc_tenure_cell_to_months(tenure_cell: str) -> List[int]:
    t = re.sub(r"\s+", " ", tenure_cell.replace("\xa0", " ")).strip()
    t = re.sub(r"\([^)]*\)", "", t).strip()
    if re.search(r"\d+\s*-\s*\d+", t):
        nums = re.findall(r"\d+", t)
        if len(nums) >= 2:
            a, b = int(nums[0]), int(nums[1])
            return list(range(min(a, b), max(a, b) + 1))
    mo = re.search(r"(\d+)", t)
    if mo:
        return [int(mo.group(1))]
    return []


def extract_ocbc_sgd_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: depends on #table-first and comparison-table structure.
    """
    OCBC Singapore SGD time deposit board (fixed-deposit-sgd-interest-rates.page).
    """
    table = soup.select_one("#table-first table.table__comparison-table")
    if not table:
        return []
    trs = table.find_all("tr")
    if not trs:
        return []
    hdr_cells = trs[0].find_all(["td", "th"])
    if len(hdr_cells) < 2:
        return []
    tier_labels = [
        re.sub(r"\s+", " ", c.get_text(" ", strip=True)) for c in hdr_cells[1:]
    ]
    rows_out: List[Dict[str, Any]] = []
    for tier_idx, lab in enumerate(tier_labels):
        r = _empty_sgd_board_row("OCBC", f"SGD TD board — {lab}")
        r["placement_range_text"] = lab
        extras: List[str] = []
        for tr in trs[1:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) <= tier_idx + 1:
                continue
            ten_raw = cells[0].get_text(" ", strip=True)
            months = _ocbc_tenure_cell_to_months(ten_raw)
            cell_txt = cells[tier_idx + 1].get_text(" ", strip=True)
            if re.match(r"^\s*N\.?\s*A\s*$", cell_txt, re.I):
                continue
            rate = _parse_percent(cell_txt)
            if rate is None:
                continue
            for m in months:
                mk = _month_key_from_int(m)
                if mk:
                    r[mk] = rate
                else:
                    extras.append(f"{m}m={rate}%")
        if extras:
            r["page_raw"] = "OCBC extra tenors (no dedicated column): " + "; ".join(
                extras
            )
        rows_out.append(r)
    return rows_out


def extract_rhb_sgd_board_pdf(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: PDF text layout / line breaks can change and break regex.
    """
    RHB Singapore deposit rates PDF — SGD fixed deposit grid (first page).
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return []
    rows: List[Dict[str, Any]] = []
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception:
        return rows
    if not reader.pages:
        return rows
    text = reader.pages[0].extract_text() or ""
    pos = text.find("SGD Fixed Deposit Rates")
    if pos < 0:
        return rows
    chunk = text[pos : pos + 1200]
    lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
    hdr_line: Optional[str] = None
    data_lines: List[str] = []
    for ln in lines:
        if re.search(r"1-mth", ln, re.I) and "3-mth" in ln:
            hdr_line = ln
            continue
        if hdr_line and re.match(r"^[\d.\s]+$", ln) and ln.count(".") >= 3:
            data_lines.append(ln)
            if len(data_lines) >= 2:
                break
    if not hdr_line or len(data_lines) < 1:
        return rows
    tenor_labels = re.findall(r"(\d+)-mth\*?", hdr_line, re.I)
    keys_order = [_month_key_from_int(int(x)) for x in tenor_labels]

    def _parse_floats(line: str) -> List[float]:
        return [float(x) for x in re.findall(r"[\d.]+", line)]

    for i, dl in enumerate(data_lines[:2], start=1):
        nums = _parse_floats(dl)
        if len(nums) < len(keys_order):
            continue
        r = _empty_sgd_board_row(
            "RHB",
            f"SGD FD board — published row {i} (see PDF for tier labels)",
        )
        r["placement_range_text"] = "SGD FD (PDF; row order as published)"
        r["page_raw"] = (
            "1-mth/2-mth may apply to Commercial/Corporate only per PDF footnote."
        )
        for j, rk in enumerate(keys_order):
            if rk and j < len(nums):
                r[rk] = nums[j]
        rows.append(r)
    return rows


def extract_sif_sgd_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: relies on specific table header wording for amount tiers.
    rows: List[Dict[str, Any]] = []
    target = None
    for table in soup.find_all("table"):
        txt = table.get_text(" ", strip=True).lower()
        if "fixed deposit board rates" in txt and "for personal & business accounts" in txt:
            target = table
            break
        if (
            "tenure" in txt
            and "$500 to < $50,000" in txt
            and "$50,000 and above" in txt
        ):
            target = table
            break
        if (
            "tenure" in txt
            and "deposit amount < $50,000" in txt
            and "deposit amount $50,000 and above" in txt
        ):
            target = table
            break
    if not target:
        return rows

    header_cells = [c.get_text(" ", strip=True) for c in target.find_all("tr")[0].find_all(["th", "td"])] if target.find_all("tr") else []
    tier1 = "$500 to < $50,000"
    tier2 = "$50,000 and above"
    if len(header_cells) >= 3:
        t1 = header_cells[1].strip()
        t2 = header_cells[2].strip()
        if t1:
            tier1 = t1
        if t2:
            tier2 = t2

    low = _empty_sgd_board_row("SingFinance", f"SGD FD Board — {tier1}")
    low["placement_range_text"] = tier1
    high = _empty_sgd_board_row(
        "SingFinance", f"SGD FD Board — {tier2}"
    )
    high["placement_range_text"] = tier2
    for tr in target.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 3:
            continue
        mo = re.search(r"(\d+)\s*month", cells[0].lower())
        if not mo:
            continue
        rk = _month_key_from_int(int(mo.group(1)))
        if not rk:
            continue
        v0 = _parse_percent(cells[1]) or _parse_board_rate_cell(cells[1])
        v1 = _parse_percent(cells[2]) or _parse_board_rate_cell(cells[2])
        if v0 is not None:
            low[rk] = v0
        if v1 is not None:
            high[rk] = v1
    rows.extend([low, high])
    return rows


def extract_scb_sgd_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: relies on "NEW TIME DEPOSIT PLACEMENTS..." table wording.
    rows: List[Dict[str, Any]] = []
    target = None
    for table in soup.find_all("table"):
        txt = table.get_text(" ", strip=True).lower()
        if "new time deposit placements" in txt and "1 mth" in txt and "24 mths" in txt:
            target = table
            break
    if not target:
        return rows
    headers = []
    trs = target.find_all("tr")
    if not trs:
        return rows
    for c in trs[0].find_all(["td", "th"]):
        headers.append(c.get_text(" ", strip=True))
    mkeys: List[Optional[str]] = [None]
    for h in headers[1:]:
        mm = re.search(r"(\d+)\s*mth", h.lower())
        mkeys.append(_month_key_from_int(int(mm.group(1))) if mm else None)
    for tr in trs[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        band = re.sub(r"\s+", " ", cells[0])
        if not re.search(r"\d", band):
            continue
        r = _empty_sgd_board_row("SCB", f"SGD TD Board — {band}")
        r["placement_range_text"] = band
        for i, rk in enumerate(mkeys):
            if not rk or i >= len(cells):
                continue
            v = _parse_percent(cells[i]) or _parse_board_rate_cell(cells[i])
            if v is not None:
                r[rk] = v
        rows.append(r)
    return rows


def extract_sbi_sgd_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: relies on "SGD Term Deposit with effect" section format.
    rows: List[Dict[str, Any]] = []
    target = None
    for table in soup.find_all("table"):
        txt = table.get_text(" ", strip=True).lower()
        if "sgd term deposit with effect" in txt and "period/amount" in txt:
            target = table
            break
    if not target:
        return rows
    r = _empty_sgd_board_row("SBI SG", "SGD Term Deposit Board — 5000-<1mio")
    r["placement_range_text"] = "5000-<1mio"
    r["min_amount_text"] = "SGD 5,000"
    r["max_amount_text"] = "< SGD 1,000,000"
    for tr in target.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        head = cells[0].lower()
        if "above 24 months to 60 months" in head:
            # Keep in raw text since internal columns do not include 60m.
            vv = _parse_percent(cells[1]) or _parse_board_rate_cell(cells[1])
            if vv is not None:
                r["page_raw"] = f"Above 24 months to 60 months: {vv}%"
            continue
        mo = re.search(r"(\d+)\s*month", head)
        if not mo:
            continue
        rk = _month_key_from_int(int(mo.group(1)))
        if not rk:
            continue
        v = _parse_percent(cells[1]) or _parse_board_rate_cell(cells[1])
        if v is not None:
            r[rk] = v
    rows.append(r)
    return rows


def extract_uob_sgd_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: relies on "Tenor (% p.a.)" table and tier headers.
    rows: List[Dict[str, Any]] = []
    target = None
    for table in soup.find_all("table"):
        txt = table.get_text(" ", strip=True).lower()
        if "tenor (% p.a.)" in txt and "below s$50,000" in txt and "s$500,000" in txt:
            target = table
            break
    if not target:
        return rows
    trs = target.find_all("tr")
    if not trs:
        return rows
    hdr = [re.sub(r"\s+", " ", c.get_text(" ", strip=True)) for c in trs[0].find_all(["td", "th"])]
    tiers = hdr[1:]
    acc: Dict[str, Dict[str, Any]] = {}
    for t in tiers:
        rr = _empty_sgd_board_row("UOB", f"SGD TD Board — {t}")
        rr["placement_range_text"] = t
        acc[t] = rr
    for tr in trs[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        mo = re.search(r"(\d+)\s*-\s*month|(\d+)\s*month", cells[0].lower())
        n = None
        if mo:
            n = int(mo.group(1) or mo.group(2))
        if n is None:
            continue
        rk = _month_key_from_int(n)
        if not rk:
            continue
        for i, t in enumerate(tiers, start=1):
            if i >= len(cells):
                break
            v = _parse_percent(cells[i]) or _parse_board_rate_cell(cells[i])
            if v is not None:
                acc[t][rk] = v
    rows.extend(acc.values())
    return rows


def extract_bea_sgd_board_from_json(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: BEA API field names/array order for fdr are endpoint-contract dependent.
    rows: List[Dict[str, Any]] = []
    root = data.get("data") if isinstance(data, dict) else {}
    payload_rows = root.get("fixedDepositRates") if isinstance(root, dict) else []
    if not isinstance(payload_rows, list) or not payload_rows:
        return rows
    timestamp = str(root.get("timestamp") or "")
    # 首行 TB2R1 为各档金额区间（非 tenor），后续行为期限利率。
    tier_labels: List[str] = []
    for item in payload_rows:
        if not isinstance(item, str) or "=" not in item:
            continue
        rhs = item.split("=", 1)[1]
        parts = [p.strip() for p in rhs.split(";") if p.strip()]
        if not parts:
            continue
        if "month" not in parts[0].lower():
            tier_labels = parts[:4]
            break

    for item in payload_rows:
        if not isinstance(item, str) or "=" not in item:
            continue
        rhs = item.split("=", 1)[1]
        parts = [p.strip() for p in rhs.split(";")]
        # header row: deposit tiers
        if parts and "month" not in parts[0].lower():
            continue
        if len(parts) < 2:
            continue
        m = re.search(r"(\d+)\s*month", parts[0], re.I)
        if not m:
            continue
        rk = _month_key_from_int(int(m.group(1)))
        if not rk:
            continue
        for i, rate_txt in enumerate(parts[1:5], start=1):
            tier_label = (
                tier_labels[i - 1]
                if i - 1 < len(tier_labels) and tier_labels[i - 1]
                else f"Tier {i}"
            )
            r = _empty_sgd_board_row("BEA", f"SGD FD Board — {tier_label}")
            r["placement_range_text"] = tier_label
            r["min_amount_text"] = tier_label
            r["page_raw"] = timestamp
            pv = _parse_board_rate_cell(rate_txt)
            if pv is not None:
                r[rk] = pv
            rows.append(r)
    # merge by product line
    merged: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        k = str(r.get("product_line") or "")
        if k not in merged:
            merged[k] = r
            continue
        for col in SGD_BOARD_INTERNAL_COLS:
            if col.startswith("rate_") and r.get(col) not in (None, "", NA):
                merged[k][col] = r[col]
    return list(merged.values())


def extract_bea_fcy_board_from_json(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: BEA API field names/array order for fcfdr are endpoint-contract dependent.
    rows: List[Dict[str, Any]] = []
    root = data.get("data") if isinstance(data, dict) else {}
    timestamp = str(root.get("timestamp") or "")
    board_rows = root.get("boardRates") if isinstance(root, dict) else []
    tier_rows = root.get("tierRates") if isinstance(root, dict) else []
    for arr_name, arr in (("Board", board_rows), ("Tier", tier_rows)):
        if not isinstance(arr, list):
            continue
        for item in arr:
            if not isinstance(item, str) or "=" not in item:
                continue
            rhs = item.split("=", 1)[1]
            parts = [p.strip() for p in rhs.split(";")]
            if len(parts) < 9:
                continue
            cur = _norm_currency_code(parts[1])
            if cur == "CNY":
                cur = "CNH"
            if not re.match(r"^[A-Z]{3}$", cur):
                continue
            r = _empty_fx_board_row("BEA", cur, f"FCY FD {arr_name} Rates — {cur}")
            min_amt = parts[2] or NA
            # 条件用金额，不用笼统的 Board/Tier；便于彩虹表 Amount 列展示。
            r["placement_range_text"] = min_amt if min_amt not in (None, "", NA) else arr_name
            r["min_amount_text"] = min_amt
            r["page_raw"] = timestamp
            # endpoint order: 1w,1m,2m,3m,6m,12m
            keys = [
                "rate_1w_pct",
                "rate_1m_pct",
                "rate_2m_pct",
                "rate_3m_pct",
                "rate_6m_pct",
                "rate_12m_pct",
            ]
            for k, v in zip(keys, parts[3:9]):
                pv = _parse_board_rate_cell(v)
                if pv is not None:
                    r[k] = pv
            rows.append(r)
    return rows


def extract_bea_sgd_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    BEA Singapore homepage promo snippet, e.g.
    "1.35% p.a.* For 3 months SGD Fixed Deposit".
    """
    out: Dict[str, Any] = {"rates": {}, "note_text": None}
    whole = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    for m in re.finditer(
        r"([\d.]+)\s*%\s*p\.?\s*a\.?\*?\s*For\s*(\d+)\s*months?\s*SGD\s*Fixed\s*Deposit",
        whole,
        re.I,
    ):
        try:
            rate = float(m.group(1))
            tenor = int(m.group(2))
        except Exception:
            continue
        out["rates"][f"{tenor}m"] = rate
    note = soup.find(string=re.compile(r"Terms\s*&?\s*Conditions apply", re.I))
    if note:
        out["note_text"] = re.sub(r"\s+", " ", str(note)).strip()
    return out


def append_bea_sgd_promo_rows(
    rows: List[Dict[str, Any]],
    bea: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not bea or bea.get("error"):
        return rows
    rates = bea.get("rates") or {}
    if not rates:
        return rows
    out = list(rows)
    note = bea.get("note_text") or "BEA SG homepage fixed deposit promotion."
    out.append(
        {
            "data_source": "BEA",
            "product_line": "SGD Fixed Deposit Promo (BEA SG homepage)",
            "min_amount_text": NA,
            "max_amount_text": NA,
            "placement_range_text": note,
            "rate_1m_pct": _rate_or_na(rates.get("1m")),
            "rate_3m_pct": _rate_or_na(rates.get("3m")),
            "rate_5m_pct": _rate_or_na(rates.get("5m")),
            "rate_6m_pct": _rate_or_na(rates.get("6m")),
            "rate_9m_pct": _rate_or_na(rates.get("9m")),
            "rate_12m_pct": _rate_or_na(rates.get("12m")),
            "page_raw": NA,
        }
    )
    return out


def append_bea_fcy_promo_rows(
    fx_rows: List[Dict[str, Any]],
    bea_fcy_board_rows: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    Convert BEA FCY RATE API rows into promo-table row shape.
    Use Tier rows as promo equivalent; fallback to Board rows when Tier absent.
    """
    if not bea_fcy_board_rows:
        return fx_rows
    # product_line 形如 "FCY FD Tier Rates — USD" / "FCY FD Board Rates — USD"
    tier_rows = [
        r
        for r in bea_fcy_board_rows
        if "tier" in str(r.get("product_line") or "").lower()
    ]
    src_rows = tier_rows or [
        r
        for r in bea_fcy_board_rows
        if "board" in str(r.get("product_line") or "").lower()
    ]
    if not src_rows:
        return fx_rows
    out = list(fx_rows)
    for r in src_rows:
        cur = str(r.get("currency") or "").upper()
        if not re.match(r"^[A-Z]{3}$", cur):
            continue
        note = "BEA FCY promo mapped from RATE API (rateType=fcfdr)."
        out.append(
            {
                "currency": cur,
                "rate_1m": _rate_or_na(r.get("rate_1m_pct")),
                "rate_3m": _rate_or_na(r.get("rate_3m_pct")),
                "rate_6m": _rate_or_na(r.get("rate_6m_pct")),
                "rate_9m": _rate_or_na(r.get("rate_9m_pct")),
                "rate_12m": _rate_or_na(r.get("rate_12m_pct")),
                "min_deposit_text": r.get("min_amount_text") or NA,
                "max_deposit_text": NA,
                "page_text_1m": note,
                "data_source": f"BEA SG FCY TD promo ({cur})",
            }
        )
    return out


def extract_boc_sgd_fcy_board(soup: BeautifulSoup) -> Dict[str, List[Dict[str, Any]]]:
    # HOTSPOT_DOM: BOC board page is mostly plain text; parsing depends on Chinese section ordering.
    out = {"sgd_rows": [], "fx_rows": []}
    txt = soup.get_text(" ", strip=True)
    txt = re.sub(r"\s+", " ", txt)

    # Section between SGD and USD.
    m_sgd = re.search(r"新加坡元\s*\(SGD\)\s+(.*?)\s+美元\s*\(USD\)\s", txt, re.S)
    sgd_blk = m_sgd.group(1) if m_sgd else ""
    tenors = [1, 3, 6, 9, 12, 18, 24, 36]
    for m in re.finditer(
        r"((?:[\d,]+以下|[\d,]+至\s*[\d,]+以下|[\d,]+及以上))\s+"
        r"([\d./]+)\s+([\d./]+)\s+([\d./]+)\s+([\d./]+)\s+([\d./]+)\s+([\d./]+)\s+([\d./]+)\s+([\d./]+)",
        sgd_blk,
    ):
        band = re.sub(r"\s+", " ", m.group(1)).strip()
        vals = [m.group(i) for i in range(2, 10)]
        r = _empty_sgd_board_row("BOC SG", f"个人定期存款挂牌利率 — SGD — {band}")
        r["placement_range_text"] = band
        for t, v in zip(tenors, vals):
            if v == "/":
                continue
            rk = _month_key_from_int(t)
            pv = _parse_board_rate_cell(v)
            if rk and pv is not None:
                r[rk] = pv
        out["sgd_rows"].append(r)

    # FCY sections (USD/AUD/CAD/RMB/EUR/GBP/HKD/JPY/NZD)
    # locate FCY section boundaries robustly with optional spaces before "(XXX)"
    marks = list(
        re.finditer(
            r"(美元|澳币|加拿大币|人民币|欧元|英镑|港币|日元|新西兰元)\s*\((USD|AUD|CAD|RMB|EUR|GBP|HKD|JPY|NZD)\)",
            txt,
        )
    )
    for mi, mk in enumerate(marks):
        code_raw = mk.group(2).upper()
        code = "CNH" if code_raw == "RMB" else code_raw
        start = mk.end()
        end = marks[mi + 1].start() if mi + 1 < len(marks) else len(txt)
        blk = txt[start:end]
        # rows look like: tier + 8 tenor values (with / possible)
        for mm in re.finditer(
            r"((?:[\d,]+以下|[\d,]+至\s*[\d,]+以下|[\d,]+及以上))\s+"
            r"([\d./]+)\s+([\d./]+)\s+([\d./]+)\s+([\d./]+)\s+([\d./]+)\s+([\d./]+)\s+([\d./]+)\s+([\d./]+)",
            blk,
        ):
            band = re.sub(r"\s+", " ", mm.group(1)).strip()
            vals = [mm.group(i) for i in range(2, 10)]  # 1,3,6,9,12,18,24,36
            r = _empty_fx_board_row("BOC SG", code, f"个人定期存款挂牌利率 — {code} — {band}")
            r["placement_range_text"] = band
            for t, v in zip(tenors, vals):
                if v == "/":
                    continue
                rk = _fx_month_key_from_int(t)
                pv = _parse_board_rate_cell(v)
                if rk and pv is not None:
                    r[rk] = _boc_fx_pct_normalize_for_sheet(code, pv)
            out["fx_rows"].append(r)
    return out


def extract_hl_fcy_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: FCY board table headers/order may change (Tenor + currencies).
    rows: List[Dict[str, Any]] = []
    target = None
    for t in soup.find_all("table"):
        txt = t.get_text(" ", strip=True)
        if "Board Rates % (p.a.)" in txt and "Tenor" in txt:
            target = t
            break
    if not target:
        return rows
    trs = target.find_all("tr")
    if len(trs) < 3:
        return rows
    hdr2 = [c.get_text(" ", strip=True).upper() for c in trs[1].find_all(["th", "td"])]
    currencies = [c for c in hdr2 if c and c != "TENOR"]
    acc: Dict[str, Dict[str, Any]] = {}
    for cur in currencies:
        if cur == "SGD":
            continue
        acc[cur] = _empty_fx_board_row("HL Bank", cur, f"FCY FD Board — {cur}")
    for tr in trs[2:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if len(cells) < 2:
            continue
        m = re.search(r"(\d+)\s*month", cells[0].lower())
        if not m:
            continue
        rk = _fx_month_key_from_int(int(m.group(1)))
        if not rk:
            continue
        for i, cur in enumerate(currencies, start=1):
            if cur == "SGD":
                continue
            if i >= len(cells):
                break
            v = _parse_board_rate_cell(cells[i])
            if v is not None:
                acc[cur][rk] = v
    rows.extend(acc.values())
    return rows


def extract_maybank_fcy_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: FCY tiers parsed from verbose HTML table text; fragile to wording changes.
    rows: List[Dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for table in soup.find_all("table"):
        # Only accept real FCY tier tables, avoid menu/other rate tables.
        first_non_empty = ""
        for tr0 in table.find_all("tr"):
            c0 = [c.get_text(" ", strip=True) for c in tr0.find_all(["td", "th"])]
            first_non_empty = " ".join([x for x in c0 if x]).strip()
            if first_non_empty:
                break
        tier_m = re.search(
            r"Foreign Currency Time Deposit\s*\(% p\.a\.\)\s*-\s*Tier\s*(\d+)",
            first_non_empty,
            re.I,
        )
        if not tier_m:
            continue
        tier = f"Tier {tier_m.group(1)}" if tier_m else "Tier"
        trs = table.find_all("tr")
        header_tr = None
        for tr in trs:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) >= 6 and "Currency" in " ".join(cells) and "Minimum" in " ".join(cells):
                header_tr = tr
                break
        if not header_tr:
            continue
        hdr = [c.get_text(" ", strip=True) for c in header_tr.find_all(["td", "th"])]
        idx = {"currency": 0, "min": 1}
        month_cols: Dict[int, int] = {}
        for i, h in enumerate(hdr):
            h2 = h.strip().lower()
            if h2 == "currency":
                idx["currency"] = i
            elif h2 == "minimum":
                idx["min"] = i
            elif re.match(r"^\d+$", h2):
                month_cols[int(h2)] = i
        for tr in trs[trs.index(header_tr) + 1 :]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            cur = _norm_currency_code(cells[idx["currency"]] if idx["currency"] < len(cells) else "")
            if (not re.match(r"^[A-Z]{3}$", cur)) or cur in ("CUR", "MIN"):
                continue
            r = _empty_fx_board_row("Maybank", cur, f"FCY TD Board — {tier}")
            r["placement_range_text"] = tier
            r["min_amount_text"] = cells[idx["min"]].strip() if idx["min"] < len(cells) else NA
            for mon, ci in month_cols.items():
                if ci >= len(cells):
                    continue
                rk = _fx_month_key_from_int(mon)
                if not rk:
                    continue
                v = _parse_board_rate_cell(cells[ci])
                if v is not None:
                    r[rk] = v
            # Dedup by currency + minimum + tier in case DOM duplicates rows.
            key = (str(r.get("currency")), str(r.get("min_amount_text")), str(r.get("placement_range_text")))
            if key in seen:
                continue
            seen.add(key)
            rows.append(r)
    return rows


def extract_scb_fcy_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: parsed from text blocks/section headings, not strict tables.
    rows: List[Dict[str, Any]] = []
    txt = soup.get_text("\n", strip=True)
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    currencies = ["USD", "GBP", "AUD", "NZD", "EUR", "CAD", "HKD", "CNH"]
    currency_idx = [i for i, ln in enumerate(lines) if ln in currencies]

    for pos, si in enumerate(currency_idx):
        cur = lines[si]
        ei = currency_idx[pos + 1] if pos + 1 < len(currency_idx) else len(lines)
        block = lines[si:ei]
        if not any("last updated" in x.lower() for x in block[:4]):
            continue

        i = 0
        while i < len(block):
            tier_label = block[i]
            if not re.search(r"\d[\d,]*\s+T[O0]\s+\d[\d,]*|\d[\d,]*\s+AND\s+ABOVE", tier_label, re.I):
                i += 1
                continue

            nums: List[float] = []
            j = i + 1
            while j < len(block) and len(nums) < 7:
                mnum = re.fullmatch(r"(\d+\.\d+)", block[j])
                if mnum:
                    nums.append(float(mnum.group(1)))
                    j += 1
                    continue
                # stop current tier if a new tier starts unexpectedly
                if re.search(r"\d[\d,]*\s+T[O0]\s+\d[\d,]*|\d[\d,]*\s+AND\s+ABOVE", block[j], re.I):
                    break
                j += 1
            if len(nums) >= 7:
                r = _empty_fx_board_row("SCB", cur, f"FCY Interest Rates — {cur} — {tier_label}")
                r["placement_range_text"] = tier_label
                r["min_amount_text"] = tier_label
                r["rate_1w_pct"] = nums[0]
                r["rate_2w_pct"] = nums[1]
                r["rate_1m_pct"] = nums[2]
                r["rate_2m_pct"] = nums[3]
                r["rate_3m_pct"] = nums[4]
                r["rate_6m_pct"] = nums[5]
                r["rate_12m_pct"] = nums[6]
                rows.append(r)
            i = max(i + 1, j)
    return rows


def extract_sbi_fcy_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: depends on "XXX deposit rates with effect" table captions.
    rows: List[Dict[str, Any]] = []
    for table in soup.find_all("table"):
        cap = table.get_text(" ", strip=True)
        cm = re.search(r"([A-Z]{3})\s+deposit rates with effect", cap, re.I)
        if not cm:
            continue
        cur = cm.group(1).upper()
        r = _empty_fx_board_row("SBI SG", cur, f"FCY Deposit Rates — {cur}")
        trs = table.find_all("tr")
        for tr in trs:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            ten = cells[0].lower()
            rate = _parse_board_rate_cell(cells[1])
            if rate is None:
                continue
            if "1 week" in ten:
                r["rate_1w_pct"] = rate
            elif "1 month" in ten:
                r["rate_1m_pct"] = rate
            elif "2 month" in ten:
                r["rate_2m_pct"] = rate
            elif "3 month" in ten:
                r["rate_3m_pct"] = rate
            elif "6 month" in ten:
                r["rate_6m_pct"] = rate
            elif "1 year" in ten or "12 month" in ten:
                r["rate_12m_pct"] = rate
            elif "18 month" in ten:
                r["rate_18m_pct"] = rate
            elif "24 month" in ten:
                r["rate_24m_pct"] = rate
        rows.append(r)
    return rows


def _extract_hsbc_fcy_board_from_pdf(pdf_bytes: bytes, source_tag: str) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: HSBC PDF tables can wrap across pages; parse table cells instead of raw lines.
    try:
        import pdfplumber
    except ImportError:
        return []
    rows: List[Dict[str, Any]] = []
    current_cur: Optional[str] = None
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for pg in pdf.pages:
            for table in pg.extract_tables() or []:
                for raw_row in table:
                    cells = [re.sub(r"\s+", " ", (c or "")).strip() for c in raw_row]
                    if not any(cells):
                        continue
                    row_text = " ".join(cells).strip()
                    first_cell = cells[0] if cells else ""
                    hm = re.search(r"\b([A-Z]{3})$", first_cell)
                    # Currency heading rows in this PDF usually have only the first column populated,
                    # e.g. "Euro EUR" / "US Dollar USD"; detect by first-cell code + empty tail cells.
                    if hm and all((not x) for x in cells[1:]):
                        current_cur = hm.group(1).upper()
                        if current_cur == "CNY":
                            current_cur = "CNH"
                        continue
                    if "Placement Amount" in row_text and "Term" in row_text:
                        continue
                    if not current_cur:
                        continue
                    if len(cells) < 5:
                        continue
                    placement = cells[0].replace("\n", " ").strip()
                    if not placement or not re.search(r"\d", placement):
                        continue

                    def _pct(cell: str) -> Optional[float]:
                        m = re.search(r"(\d+\.\d+)%", cell or "")
                        return float(m.group(1)) if m else None

                    p1 = _pct(cells[1])
                    p3 = _pct(cells[2])
                    p6 = _pct(cells[3])
                    p12 = _pct(cells[4])
                    if p1 is None and p3 is None and p6 is None and p12 is None:
                        continue
                    r = _empty_fx_board_row("HSBC", current_cur, f"FCY TD Board — {current_cur} — {source_tag}")
                    r["placement_range_text"] = placement
                    r["rate_1m_pct"] = p1 if p1 is not None else NA
                    r["rate_3m_pct"] = p3 if p3 is not None else NA
                    r["rate_6m_pct"] = p6 if p6 is not None else NA
                    r["rate_12m_pct"] = p12 if p12 is not None else NA
                    rows.append(r)
    dedup: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        k = f"{r.get('currency')}|{r.get('placement_range_text')}|{source_tag}"
        dedup[k] = r
    return list(dedup.values())


def extract_hsbc_fcy_board(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: finds FCY PDF links first, then parses PDFs.
    rows: List[Dict[str, Any]] = []
    links: List[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        txt = a.get_text(" ", strip=True).lower()
        if "fcy-time-deposits" in href and href.lower().endswith(".pdf"):
            links.append(href)
        elif "foreign currency time deposit rates" in txt and href.lower().endswith(".pdf"):
            links.append(href)
    uniq = []
    for h in links:
        if h not in uniq:
            uniq.append(h)
    sess = requests.Session()
    sess.headers.update({"User-Agent": USER_AGENT})
    for href in uniq:
        if href.startswith("/"):
            url = "https://www.hsbc.com.sg" + href
        elif href.startswith("http"):
            url = href
        else:
            url = "https://www.hsbc.com.sg/" + href.lstrip("/")
        try:
            rb = sess.get(url, timeout=60)
            rb.raise_for_status()
            tag = "Premier" if "pr.pdf" in url.lower() else "Personal Banking"
            rows.extend(_extract_hsbc_fcy_board_from_pdf(rb.content, tag))
        except requests.RequestException:
            continue
    return rows


def extract_rhb_fcy_board_pdf(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: RHB PDF page zones and per-line numeric extraction are layout-sensitive.
    try:
        import pdfplumber
    except ImportError:
        return []
    rows: List[Dict[str, Any]] = []
    tier_pat = re.compile(
        r"^(Up to 99,999|100,000 to 499,999|500,000 - 999,999|1,000,000 & above)\b",
        re.I,
    )
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for pg in pdf.pages:
            text = pg.extract_text() or ""
            if "Foreign Currency Fixed Deposit Rates" not in text:
                continue
            tier = "RHB FCY tier"
            for ln in text.splitlines():
                line = re.sub(r"\s+", " ", ln).strip()
                tm = tier_pat.search(line)
                if tm:
                    tier = tm.group(1)
                    continue
                if line.lower().startswith("currency "):
                    continue
                cm = re.search(r"\(([A-Z]{3})\)", line)
                if not cm:
                    continue
                cur = cm.group(1).upper()
                if cur == "CNY":
                    cur = "CNH"
                nums = re.findall(r"(?:\d+\.\d+|–|—|-|−|�C)", line)
                if len(nums) < 8:
                    continue
                vals: List[Optional[float]] = []
                for n in nums[-8:]:
                    if n in {"–", "—", "-", "−", "�C"}:
                        vals.append(None)
                    else:
                        vals.append(float(n))
                r = _empty_fx_board_row("RHB", cur, f"FCY FD Board — {cur} — {tier}")
                r["placement_range_text"] = tier
                # 1-wk,1m,2m,3m,6m,9m,12m,24m
                r["rate_1w_pct"] = vals[0] if vals[0] is not None else NA
                r["rate_1m_pct"] = vals[1] if vals[1] is not None else NA
                r["rate_2m_pct"] = vals[2] if vals[2] is not None else NA
                r["rate_3m_pct"] = vals[3] if vals[3] is not None else NA
                r["rate_6m_pct"] = vals[4] if vals[4] is not None else NA
                r["rate_9m_pct"] = vals[5] if vals[5] is not None else NA
                r["rate_12m_pct"] = vals[6] if vals[6] is not None else NA
                r["rate_24m_pct"] = vals[7] if vals[7] is not None else NA
                rows.append(r)
    # dedup by source/currency/tier
    dedup: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        k = f"{r.get('data_source')}|{r.get('currency')}|{r.get('placement_range_text')}"
        dedup[k] = r
    return list(dedup.values())


def build_sgd_merged(
    citi_sgd: Dict[str, Any],
    cimb: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Citibank segments first, then CIMB SGD online / WWFD-i rows."""
    rows: List[Dict[str, Any]] = []
    for seg in citi_sgd.get("segments") or []:
        rows.append(
            {
                "data_source": "Citibank",
                "product_line": seg.get("audience", ""),
                "min_amount_text": seg.get("min_amount_text") or NA,
                "max_amount_text": seg.get("max_amount_text") or NA,
                "placement_range_text": seg.get("placement_range_text") or NA,
                "rate_1m_pct": NA,
                "rate_3m_pct": seg.get("rate_3m_percent"),
                "rate_5m_pct": NA,
                "rate_6m_pct": seg.get("rate_6m_percent"),
                "rate_9m_pct": NA,
                "rate_12m_pct": NA,
                "page_raw": seg.get("raw") or "",
            }
        )
    if not cimb or cimb.get("error"):
        return rows
    tier = cimb.get("online_tier_note") or "S$10,000 and above (online promo)"
    op = cimb.get("online_personal") or {}
    oq = cimb.get("online_preferred") or {}
    if op:
        rows.append(
            {
                "data_source": "CIMB",
                "product_line": "SGD Online FD - Personal Banking",
                "min_amount_text": "S$10,000",
                "max_amount_text": NA,
                "placement_range_text": tier,
                "rate_1m_pct": NA,
                "rate_3m_pct": op.get("3m"),
                "rate_5m_pct": NA,
                "rate_6m_pct": op.get("6m"),
                "rate_9m_pct": op.get("9m"),
                "rate_12m_pct": op.get("12m"),
                "page_raw": NA,
            }
        )
    if oq:
        rows.append(
            {
                "data_source": "CIMB",
                "product_line": "SGD Online FD - Preferred Banking",
                "min_amount_text": "S$10,000",
                "max_amount_text": NA,
                "placement_range_text": tier,
                "rate_1m_pct": NA,
                "rate_3m_pct": oq.get("3m"),
                "rate_5m_pct": NA,
                "rate_6m_pct": oq.get("6m"),
                "rate_9m_pct": oq.get("9m"),
                "rate_12m_pct": oq.get("12m"),
                "page_raw": NA,
            }
        )
    ww = cimb.get("why_wait_fd_i") or {}
    if ww:
        rows.append(
            {
                "data_source": "CIMB",
                "product_line": "SGD Why Wait FD-i (online promo)",
                "min_amount_text": "S$10,000",
                "max_amount_text": NA,
                "placement_range_text": cimb.get("why_wait_tier_note")
                or "S$10,000 & Above (WWFD-i)",
                "rate_1m_pct": NA,
                "rate_3m_pct": ww.get("3m"),
                "rate_5m_pct": NA,
                "rate_6m_pct": ww.get("6m"),
                "rate_9m_pct": ww.get("9m"),
                "rate_12m_pct": ww.get("12m"),
                "page_raw": NA,
            }
        )
    return rows


def _hsbc_tenor_cn_to_key(text: str) -> Optional[str]:
    m = re.search(r"(\d+)\s*个月", text.strip())
    if not m:
        return None
    return f"{int(m.group(1))}m"


def extract_hsbc_sgd_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    HSBC Singapore SGD time-deposit promo (Chinese UI): desktop table by client segment.
    https://www.hsbc.com.sg/zh-sg/accounts/products/time-deposit/
    """
    out: Dict[str, Any] = {
        "segment_rates": [],
        "caption_text": None,
        "mobile_promo_paragraph": None,
        "mobile_promo_rate_3m": None,
    }
    table = None
    for t in soup.find_all("table", class_="desktop"):
        thead = t.find("thead")
        if thead and "客户" in thead.get_text():
            table = t
            break
    if not table:
        return out
    cap = table.find("caption")
    if cap:
        out["caption_text"] = cap.get_text(" ", strip=True)
    tbody = table.find("tbody")
    if not tbody:
        return out
    by_seg: Dict[str, Dict[str, Optional[float]]] = {}
    for tr in tbody.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 3:
            continue
        seg = cells[0].get_text(" ", strip=True)
        tenor_cn = cells[1].get_text(" ", strip=True)
        rate_raw = cells[2].get_text(" ", strip=True)
        tk = _hsbc_tenor_cn_to_key(tenor_cn)
        rp = _parse_percent(rate_raw)
        if not tk or rp is None:
            continue
        if seg not in by_seg:
            by_seg[seg] = {}
        by_seg[seg][tk] = float(rp)
    for seg, rates in by_seg.items():
        out["segment_rates"].append(
            {
                "segment": seg,
                "1m": rates.get("1m"),
                "3m": rates.get("3m"),
                "6m": rates.get("6m"),
                "9m": rates.get("9m"),
                "12m": rates.get("12m"),
            }
        )
    for p in soup.find_all("p"):
        t = p.get_text(" ", strip=True)
        if "手机银行" in t and "3个月" in t and "30,000" in t:
            out["mobile_promo_paragraph"] = t
            m = re.search(r"高达\s*([\d.]+)\s*%", t)
            if m:
                out["mobile_promo_rate_3m"] = float(m.group(1))
            else:
                m2 = re.search(r"([\d.]+)\s*%", t)
                if m2:
                    out["mobile_promo_rate_3m"] = float(m2.group(1))
            break
    return out


def extract_maybank_sgd_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Maybank SGD Time Deposit promotion page:
    https://www.maybank2u.com.sg/en/promotions/deposits/sgd-time-deposit.page
    """
    out: Dict[str, Any] = {
        "bundle_branch_6m": None,
        "bundle_general_9m": None,
        "bundle_general_12m": None,
        "standalone": {},
        "min_amount_text": "S$20,000",
        "note_text": None,
    }
    txt = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    # i) Deposits Bundle Promotion (Only at Branches): 6m
    m6 = re.search(
        r"i\.\s*Deposits Bundle Promotion.*?6\s*month.*?Promotional Rate.*?([\d.]+)\s*%",
        txt,
        re.I,
    )
    if m6:
        out["bundle_branch_6m"] = float(m6.group(1))
    # ii) Deposits Bundle Promotion (at branches and online): 9m/12m
    m9 = re.search(
        r"ii\.\s*Deposits Bundle Promotion.*?9\s*month.*?([\d.]+)\s*%",
        txt,
        re.I,
    )
    if m9:
        out["bundle_general_9m"] = float(m9.group(1))
    m12 = re.search(
        r"ii\.\s*Deposits Bundle Promotion.*?12\s*month.*?([\d.]+)\s*%",
        txt,
        re.I,
    )
    if m12:
        out["bundle_general_12m"] = float(m12.group(1))
    # iii) Standalone Time Deposit and Term Deposit-i table
    for table in soup.find_all("table"):
        ttxt = table.get_text(" ", strip=True).lower()
        if "tenure" not in ttxt or "promotional rates" not in ttxt:
            continue
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            m = re.search(r"(\d+)\s*month", cells[0], re.I)
            if not m:
                continue
            tk = f"{int(m.group(1))}m"
            rv = _parse_percent(cells[1]) or _parse_board_rate_cell(cells[1])
            if rv is not None:
                out["standalone"][tk] = rv
        if out["standalone"]:
            break
    note = soup.find(string=re.compile(r"Minimum placement of S\\$20,000", re.I))
    if note:
        out["note_text"] = re.sub(r"\s+", " ", str(note)).strip()
    return out


def _rate_or_na(v: Any) -> Any:
    return v if v is not None else NA


def _icbc_tenor_to_rate_key(tenor_cell: str) -> Optional[str]:
    t = re.sub(r"\s+", " ", tenor_cell.strip()).lower()
    if "1 year" in t and "e-banking" in t:
        return "12m_ebanking"
    if t == "1 year":
        return "12m"
    if t == "1 month":
        return "1m"
    if t == "3 months":
        return "3m"
    if t == "6 months":
        return "6m"
    if t == "9 months":
        return "9m"
    return None


def _parse_icbc_tier_table(table) -> Optional[Dict[str, Any]]:
    """ICBC SGD/RMB style: Tenor | tier low | tier high."""
    rows = table.find_all("tr")
    tier_low_label: Optional[str] = None
    tier_high_label: Optional[str] = None
    rates_low: Dict[str, float] = {}
    rates_high: Dict[str, float] = {}
    for tr in rows:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        a = cells[0].get_text(" ", strip=True)
        if a.lower() == "tenor":
            tier_low_label = cells[1].get_text(" ", strip=True)
            tier_high_label = cells[2].get_text(" ", strip=True)
            continue
        tk = _icbc_tenor_to_rate_key(a)
        if not tk:
            continue
        p_lo = _parse_percent(cells[1].get_text(" ", strip=True))
        p_hi = _parse_percent(cells[2].get_text(" ", strip=True))
        if p_lo is not None:
            rates_low[tk] = float(p_lo)
        if p_hi is not None:
            rates_high[tk] = float(p_hi)
    if not rates_low and not rates_high:
        return None
    return {
        "tier_low_label": tier_low_label,
        "tier_high_label": tier_high_label,
        "rates_low": rates_low,
        "rates_high": rates_high,
    }


def _parse_icbc_usd_table(table) -> Optional[Dict[str, Any]]:
    """ICBC USD: Tenor | Below USD5K | USD5K & Above."""
    rows = table.find_all("tr")
    tier_low_label: Optional[str] = None
    tier_high_label: Optional[str] = None
    rates_low: Dict[str, float] = {}
    rates_high: Dict[str, float] = {}
    for tr in rows:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        a = cells[0].get_text(" ", strip=True)
        if a.lower() == "tenor":
            if len(cells) >= 3:
                tier_low_label = cells[1].get_text(" ", strip=True)
                tier_high_label = cells[2].get_text(" ", strip=True)
            continue
        tk = _icbc_tenor_to_rate_key(a)
        if not tk:
            continue
        if len(cells) >= 3:
            p_lo = _parse_percent(cells[1].get_text(" ", strip=True))
            p_hi = _parse_percent(cells[2].get_text(" ", strip=True))
            if p_lo is not None:
                rates_low[tk] = float(p_lo)
            if p_hi is not None:
                rates_high[tk] = float(p_hi)
        else:
            p = _parse_percent(cells[1].get_text(" ", strip=True))
            if p is not None:
                rates_low[tk] = float(p)
    if not rates_low and not rates_high:
        return None
    return {
        "tier_low_label": tier_low_label,
        "tier_high_label": tier_high_label,
        "rates_low": rates_low,
        "rates_high": rates_high,
    }


def extract_icbc_fd_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    ICBC Singapore: SGD / USD / RMB fixed deposit promotion tables (English page).
    https://singapore.icbc.com.cn/en/page/721854535525236736.html
    """
    out: Dict[str, Any] = {
        "sgd": None,
        "usd": None,
        "rmb": None,
        "information_as_at": None,
        "sgd_min_note": None,
        "usd_min_note": None,
        "rmb_min_note": None,
    }
    content = soup.find("td", id="mypagehtmlcontent")
    if not content:
        content = soup.find("td", class_=lambda c: c and "LinkSec" in (c or ""))
    if not content:
        return out
    blob = content.get_text("\n", strip=True)
    m = re.search(r"Information as at\s+(.+?)(?:\n|$)", blob, re.I)
    if m:
        out["information_as_at"] = m.group(1).strip()
    for p in content.find_all("p"):
        t = p.get_text(" ", strip=True)
        if "minimum deposit amount" in t.lower() and "sgd" in t.lower():
            out["sgd_min_note"] = t
            break
    for p in content.find_all("p"):
        t = p.get_text(" ", strip=True)
        if "usd" in t.lower() and "minimum" in t.lower() and "deposit" in t.lower():
            out["usd_min_note"] = t
            break
    for p in content.find_all("p"):
        t = p.get_text(" ", strip=True)
        if "rmb" in t.lower() and "minimum" in t.lower() and "deposit" in t.lower():
            out["rmb_min_note"] = t
            break

    for table in content.find_all("table"):
        first_tr = table.find("tr")
        if not first_tr:
            continue
        fc = first_tr.find(["td", "th"])
        if not fc:
            continue
        lab = fc.get_text(" ", strip=True).upper()
        if lab.startswith("SGD"):
            out["sgd"] = _parse_icbc_tier_table(table)
        elif lab.startswith("USD"):
            out["usd"] = _parse_icbc_usd_table(table)
        elif lab.startswith("RMB"):
            out["rmb"] = _parse_icbc_tier_table(table)
    return out


def append_icbc_sgd_rows(
    rows: List[Dict[str, Any]],
    icbc: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not icbc or icbc.get("error"):
        return rows
    sgd = icbc.get("sgd")
    if not sgd:
        return rows
    out = list(rows)
    eff = icbc.get("information_as_at") or ""
    eff_note = f" | As at {eff}" if eff else ""
    min_note = icbc.get("sgd_min_note") or NA
    lo = sgd.get("rates_low") or {}
    hi = sgd.get("rates_high") or {}
    t_lo = sgd.get("tier_low_label") or "Below SGD200K (exclusive)"
    t_hi = sgd.get("tier_high_label") or "SGD200K (inclusive) & Above"

    def _row(tier_title: str, r: Dict[str, float]) -> Dict[str, Any]:
        return {
            "data_source": "ICBC SG",
            "product_line": f"SGD E-banking FD — {tier_title}",
            "min_amount_text": "S$500 (e-banking); S$20,000 (counter)",
            "max_amount_text": NA,
            "placement_range_text": f"{min_note}{eff_note}".strip(),
            "rate_1m_pct": _rate_or_na(r.get("1m")),
            "rate_3m_pct": _rate_or_na(r.get("3m")),
            "rate_5m_pct": NA,
            "rate_6m_pct": _rate_or_na(r.get("6m")),
            "rate_9m_pct": _rate_or_na(r.get("9m")),
            "rate_12m_pct": _rate_or_na(r.get("12m")),
            "page_raw": NA,
        }

    out.append(_row(t_lo, lo))
    out.append(_row(t_hi, hi))
    return out


def append_icbc_fx_rows(
    fx_rows: List[Dict[str, Any]],
    icbc: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not icbc or icbc.get("error"):
        return fx_rows
    out = list(fx_rows)
    eff = icbc.get("information_as_at") or ""
    eff_s = f" As at {eff}." if eff else ""

    usd = icbc.get("usd")
    if usd:
        rl = usd.get("rates_low") or {}
        rh = usd.get("rates_high") or {}
        tl = usd.get("tier_low_label") or "Below USD5K(exclusive)"
        th = usd.get("tier_high_label") or "USD5K(inclusive) & Above"
        for title, rr in ((tl, rl), (th, rh)):
            if not rr:
                continue
            out.append(
                {
                    "currency": "USD",
                    "rate_1m": _rate_or_na(rr.get("1m")),
                    "rate_3m": _rate_or_na(rr.get("3m")),
                    "rate_6m": _rate_or_na(rr.get("6m")),
                    "rate_9m": _rate_or_na(rr.get("9m")),
                    "rate_12m": _rate_or_na(rr.get("12m")),
                    "min_deposit_text": title,
                    "max_deposit_text": NA,
                    "page_text_1m": eff_s.strip() or NA,
                    "data_source": f"ICBC SG FD promo (USD) — {title}{eff_s}",
                }
            )

    rmb = icbc.get("rmb")
    if rmb:
        lo = rmb.get("rates_low") or {}
        hi = rmb.get("rates_high") or {}
        t_lo = rmb.get("tier_low_label") or "Below RMB50K (exclusive)"
        t_hi = rmb.get("tier_high_label") or "RMB50K (inclusive) & Above"
        min_txt = icbc.get("rmb_min_note") or NA

        for title, rd in ((t_lo, lo), (t_hi, hi)):
            out.append(
                {
                    "currency": f"CNY ({title})",
                    "rate_1m": _rate_or_na(rd.get("1m")),
                    "rate_3m": _rate_or_na(rd.get("3m")),
                    "rate_6m": _rate_or_na(rd.get("6m")),
                    "rate_9m": _rate_or_na(rd.get("9m")),
                    "rate_12m": _rate_or_na(rd.get("12m")),
                    "min_deposit_text": min_txt,
                    "max_deposit_text": NA,
                    "page_text_1m": eff_s.strip() or NA,
                    "data_source": f"ICBC SG FD promo (RMB / CNY) — {title}",
                }
            )
    return out


def _parse_ocbc_sgd_channels(table) -> List[Dict[str, Any]]:
    """
    OCBC comparison table: full rows have 6 cells; continuation rows have 2 cells
    (extra tenure/rate under same Banking type).
    """
    channels: List[Dict[str, Any]] = []
    tbody = table.find("tbody")
    if not tbody:
        return channels
    last: Optional[Dict[str, Any]] = None
    for tr in tbody.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        joined = " ".join(cells)
        if "SGD Time Deposit Rate" in joined:
            continue
        low0 = cells[0].strip().lower()
        if low0 == "currency" or (
            "currency" in low0 and "tenure" in joined.lower()
        ):
            continue
        if len(cells) == 6:
            cur, ten_s, bank, rate_s, min_p, apply_via = cells
            ten = int(re.sub(r"\D", "", ten_s) or "0")
            rp = _parse_percent(rate_s)
            blk: Dict[str, Any] = {
                "currency": cur,
                "banking_type": bank,
                "min_placement": min_p,
                "apply_via": apply_via,
                "tenors": {},
            }
            if ten and rp is not None:
                blk["tenors"][f"{ten}m"] = float(rp)
            channels.append(blk)
            last = blk
        elif len(cells) == 2 and last is not None:
            ten_s, rate_s = cells
            ten = int(re.sub(r"\D", "", ten_s) or "0")
            rp = _parse_percent(rate_s)
            if ten and rp is not None:
                last["tenors"][f"{ten}m"] = float(rp)
    return channels


def extract_ocbc_sgd_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    OCBC Singapore SGD time deposit promotional table (Branch vs Online).
    https://www.ocbc.com/personal-banking/deposits/fixed-deposit-account
    """
    out: Dict[str, Any] = {"channels": [], "caption": None}
    table = None
    for t in soup.find_all("table", class_=lambda c: c and "table__comparison-table" in c):
        if re.search(r"SGD\s+Time\s+Deposit\s+Rate", t.get_text(), re.I):
            table = t
            break
    if not table:
        for t in soup.find_all("table"):
            if re.search(r"SGD\s+Time\s+Deposit\s+Rate", t.get_text(), re.I):
                table = t
                break
    if not table:
        return out
    out["channels"] = _parse_ocbc_sgd_channels(table)
    cap = table.find_next("p", class_="caption")
    if cap:
        out["caption"] = cap.get_text(" ", strip=True)
    return out


def append_ocbc_sgd_rows(
    rows: List[Dict[str, Any]],
    ocbc: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not ocbc or ocbc.get("error"):
        return rows
    chs = ocbc.get("channels") or []
    if not chs:
        return rows
    out = list(rows)
    cap = (ocbc.get("caption") or "").strip()
    for ch in chs:
        tens = ch.get("tenors") or {}
        extra_parts: List[str] = []
        for k, v in sorted(
            tens.items(),
            key=lambda kv: int(re.sub(r"\D", "", kv[0]) or "0"),
        ):
            if k == "12m":
                continue
            mo = int(k.rstrip("m"))
            extra_parts.append(f"{mo} months: {v}% p.a.")
        page_raw = "; ".join(extra_parts) if extra_parts else NA
        placement = cap or NA
        bank = (ch.get("banking_type") or "Promo").strip()
        cur = (ch.get("currency") or "SGD").strip()
        out.append(
            {
                "data_source": "OCBC SG",
                "product_line": f"SGD TD — {bank} ({cur})",
                "min_amount_text": ch.get("min_placement") or NA,
                "max_amount_text": NA,
                "placement_range_text": placement,
                "rate_1m_pct": _rate_or_na(tens.get("1m")),
                "rate_3m_pct": _rate_or_na(tens.get("3m")),
                "rate_5m_pct": _rate_or_na(tens.get("5m")),
                "rate_6m_pct": _rate_or_na(tens.get("6m")),
                "rate_9m_pct": _rate_or_na(tens.get("9m")),
                "rate_12m_pct": _rate_or_na(tens.get("12m")),
                "page_raw": page_raw,
            }
        )
    return out


def extract_rhb_fd_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    RHB Singapore fixed deposit campaign page.
    Parses SGD promotional rates table and checks whether FCY promotional rates
    table is present on this same page.
    """
    out: Dict[str, Any] = {
        "sgd_personal": {},
        "sgd_premier": {},
        "min_placement_text": None,
        "note_text": None,
        "has_fcy_promo_table": False,
        "fcy_product_link": None,
    }
    for a in soup.find_all("a", href=True):
        href = a["href"]
        txt = a.get_text(" ", strip=True).lower()
        if "foreign-currency-fixed-deposit-account" in href:
            out["fcy_product_link"] = href
        if "foreign currency fixed deposit" in txt and not out["fcy_product_link"]:
            out["fcy_product_link"] = href

    target = None
    for table in soup.find_all("table"):
        head = table.get_text(" ", strip=True).lower()
        if (
            "tenure" in head
            and "personal banking" in head
            and "premier banking" in head
            and "minimum placement" in head
        ):
            target = table
            break
    if not target:
        return out
    for tr in target.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 4:
            continue
        tk = re.search(r"(\d+)\s*-\s*month|(\d+)\s*month", cells[0], re.I)
        if not tk:
            continue
        tenor = int(tk.group(1) or tk.group(2))
        p0 = _parse_percent(cells[1])
        p1 = _parse_percent(cells[2])
        if p0 is None and p1 is None:
            continue
        key = f"{tenor}m"
        if p0 is not None:
            out["sgd_personal"][key] = float(p0)
        if p1 is not None:
            out["sgd_premier"][key] = float(p1)
        if not out["min_placement_text"]:
            mn = cells[3].strip()
            if mn:
                out["min_placement_text"] = "S$" + mn if re.fullmatch(r"[\d,]+", mn) else mn
    foot = target.find_next(string=re.compile(r"Promotional rates are subject to change", re.I))
    if foot:
        out["note_text"] = re.sub(r"\s+", " ", str(foot)).strip()
    # This page only exposes SGD promo rates table; FCY here is product navigation.
    out["has_fcy_promo_table"] = False
    return out


def append_rhb_sgd_rows(
    rows: List[Dict[str, Any]],
    rhb: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not rhb or rhb.get("error"):
        return rows
    out = list(rows)
    mn = rhb.get("min_placement_text") or "S$20,000"
    note = rhb.get("note_text") or "RHB Mobile SG App fixed deposit campaign page."
    pp = rhb.get("sgd_personal") or {}
    pr = rhb.get("sgd_premier") or {}
    if pp:
        out.append(
            {
                "data_source": "RHB SG",
                "product_line": "SGD Fixed Deposit Promo - Personal Banking",
                "min_amount_text": mn,
                "max_amount_text": NA,
                "placement_range_text": note,
                "rate_1m_pct": NA,
                "rate_3m_pct": _rate_or_na(pp.get("3m")),
                "rate_5m_pct": NA,
                "rate_6m_pct": _rate_or_na(pp.get("6m")),
                "rate_9m_pct": NA,
                "rate_12m_pct": _rate_or_na(pp.get("12m")),
                "page_raw": NA,
            }
        )
    if pr:
        out.append(
            {
                "data_source": "RHB SG",
                "product_line": "SGD Fixed Deposit Promo - Premier Banking",
                "min_amount_text": mn,
                "max_amount_text": NA,
                "placement_range_text": note,
                "rate_1m_pct": NA,
                "rate_3m_pct": _rate_or_na(pr.get("3m")),
                "rate_5m_pct": NA,
                "rate_6m_pct": _rate_or_na(pr.get("6m")),
                "rate_9m_pct": NA,
                "rate_12m_pct": _rate_or_na(pr.get("12m")),
                "page_raw": NA,
            }
        )
    return out


def extract_rhb_fcy_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    RHB Singapore FCY fixed deposit campaign page:
    USD/GBP/AUD with 3/6/12 month promo rates and min placement.
    """
    out: Dict[str, Any] = {
        "currencies": {},
        "note_text": None,
    }
    table = None
    for t in soup.find_all("table"):
        head = t.get_text(" ", strip=True).lower()
        if (
            "currency of account" in head
            and "3-month" in head
            and "6-month" in head
            and "12-month" in head
            and "minimum placement amount" in head
        ):
            table = t
            break
    if not table:
        return out
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 5:
            continue
        cur = cells[0].strip().upper()
        if cur not in ("USD", "GBP", "AUD"):
            continue
        p3 = _parse_percent(cells[1])
        p6 = _parse_percent(cells[2])
        p12 = _parse_percent(cells[3])
        if p3 is None and p6 is None and p12 is None:
            continue
        out["currencies"][cur] = {
            "3m": float(p3) if p3 is not None else None,
            "6m": float(p6) if p6 is not None else None,
            "12m": float(p12) if p12 is not None else None,
            "min_deposit": cells[4].strip() or NA,
        }
    n = table.find_next(string=re.compile(r"Promotional rates are subject to change", re.I))
    if n:
        out["note_text"] = re.sub(r"\s+", " ", str(n)).strip()
    return out


def append_rhb_fcy_rows(
    fx_rows: List[Dict[str, Any]],
    rhb_fcy: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not rhb_fcy or rhb_fcy.get("error"):
        return fx_rows
    currs = rhb_fcy.get("currencies") or {}
    if not currs:
        return fx_rows
    out = list(fx_rows)
    note = rhb_fcy.get("note_text") or "RHB FCY fixed deposit campaign."
    for cur in ("USD", "GBP", "AUD"):
        row = currs.get(cur)
        if not row:
            continue
        out.append(
            {
                "currency": cur,
                "rate_1m": NA,
                "rate_3m": _rate_or_na(row.get("3m")),
                "rate_6m": _rate_or_na(row.get("6m")),
                "rate_9m": NA,
                "rate_12m": _rate_or_na(row.get("12m")),
                "min_deposit_text": row.get("min_deposit") or NA,
                "max_deposit_text": NA,
                "page_text_1m": note,
                "data_source": f"RHB SG FCY FD promo ({cur})",
            }
        )
    return out


def extract_uob_sgd_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    UOB SGD 促销表（页面改版后常见四列）：
      Tenor | Deposit Amount (Fresh Funds) | Base promotional rate | Wealth-tier rate

    10/12 个月行可能省略「起存」列，仅保留期限 + 两档利率。
    """
    out: Dict[str, Any] = {
        "rate_6m": None,
        "rate_12m": None,
        "rate_6m_wealth": None,
        "rate_12m_wealth": None,
        "extra_page_raw": None,
        "min_deposit_text": None,
        "note_text": None,
        "has_fcy_promo_table": False,
    }

    page_text = soup.get_text("\n", strip=True)
    m = re.search(
        r"This promotion is available from\s*(.*?)\s+to\s+(.*?)\.",
        page_text,
        re.I,
    )
    if m:
        out["note_text"] = " ".join((m.group(0) or "").split())

    target_table = None
    for table in soup.find_all("table"):
        ttxt = table.get_text(" ", strip=True).lower()
        if "tenor" not in ttxt or "fresh funds" not in ttxt:
            continue
        if "deposit" not in ttxt or "amount" not in ttxt:
            continue
        if "promotional" in ttxt or ("base" in ttxt and "interest" in ttxt):
            target_table = table
            break
    if not target_table:
        return out

    notes_10m: List[str] = []
    other_tenors: List[str] = []

    for tr in target_table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        tenor_raw = cells[0]
        if tenor_raw.strip().lower() in ("tenor", ""):
            continue

        mt = re.search(r"(\d+)\s*[- ]?\s*month", tenor_raw, re.I)
        if not mt:
            continue
        months = int(mt.group(1))

        pcts: List[float] = []
        dep_cell: Optional[str] = None
        for c in cells[1:]:
            if not c:
                continue
            pv = _parse_percent(c)
            if pv is not None:
                pcts.append(float(pv))
            elif re.search(r"minimum|s\$|fresh|deposit", c, re.I) and "%" not in c:
                dep_cell = c.strip()

        if not pcts:
            continue
        if dep_cell and out["min_deposit_text"] is None:
            out["min_deposit_text"] = dep_cell

        base = pcts[0]
        wealth = pcts[1] if len(pcts) > 1 else None

        if months == 6:
            out["rate_6m"] = base
            if wealth is not None:
                out["rate_6m_wealth"] = wealth
        elif months == 12:
            out["rate_12m"] = base
            if wealth is not None:
                out["rate_12m_wealth"] = wealth
        elif months == 10:
            seg = f"基准 {base}% p.a."
            if wealth is not None:
                seg += f"，含财富管理产品 {wealth}% p.a."
            notes_10m.append(seg)
        else:
            other_tenors.append(f"{months}M={base}% p.a.")

    chunks: List[str] = []
    if notes_10m:
        chunks.append("10个月期（Market 表无 10M 列）：" + "；".join(notes_10m))
    if other_tenors:
        chunks.append("其它期限：" + "；".join(other_tenors))
    wnote: List[str] = []
    if out.get("rate_6m_wealth") is not None:
        wnote.append(f"6M 含财富管理产品 {out['rate_6m_wealth']}% p.a.")
    if out.get("rate_12m_wealth") is not None:
        wnote.append(f"12M 含财富管理产品 {out['rate_12m_wealth']}% p.a.")
    if wnote:
        chunks.append(" ".join(wnote))
    out["extra_page_raw"] = " ".join(chunks) if chunks else None
    return out


def extract_uob_fcy_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Detect whether FCY promotional fixed deposit table exists on the same page.
    This UOB SGD promo page usually only contains SGD rates.
    """
    out: Dict[str, Any] = {
        "currencies": {},
        "note_text": None,
        "has_fcy_promo_table": False,
    }

    # Quick heuristic: if no "Foreign currency" section text exists, assume no FCY promo.
    whole = soup.get_text(" ", strip=True).lower()
    if "foreign currency time" not in whole and "foreign currency fixed" not in whole:
        return out

    # Try parse any promo table that looks like:
    # Currency | Tenor | Promotional Interest Rate (p.a.) | Minimum/Deposit Amount
    for table in soup.find_all("table"):
        ttxt = table.get_text(" ", strip=True)
        head = ttxt.lower()
        if "promotional interest" not in head or "deposit amount" not in head:
            continue
        # Require at least one known 3-letter currency code in the table.
        if not re.search(
            r"\b(usd|aud|gbp|eur|chf|jpy|cad|nzd|cnh)\b",
            head,
            re.I,
        ):
            continue

        header_cells = []
        for tr in table.find_all("tr"):
            header_cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if header_cells:
                break
        header_norm = [c.lower() for c in header_cells]
        currency_idx = None
        tenor_idx = None
        rate_idx = None
        dep_idx = None
        for i, c in enumerate(header_norm):
            if currency_idx is None and "currency" in c:
                currency_idx = i
            if tenor_idx is None and "tenor" in c:
                tenor_idx = i
            if rate_idx is None and ("promotional" in c and "rate" in c):
                rate_idx = i
            if dep_idx is None and ("deposit amount" in c or "minimum deposit" in c):
                dep_idx = i

        # If we cannot locate columns, skip.
        if currency_idx is None or tenor_idx is None or rate_idx is None or dep_idx is None:
            continue

        for tr in table.find_all("tr")[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) <= max(currency_idx, tenor_idx, rate_idx, dep_idx):
                continue
            cur = (cells[currency_idx] or "").strip().upper()
            tenor_raw = cells[tenor_idx] or ""
            rate_raw = cells[rate_idx] or ""
            dep_raw = cells[dep_idx] or ""
            if not cur:
                continue
            pct = _parse_percent(rate_raw)
            if pct is None:
                continue
            mt = re.search(r"(\d+)\s*[- ]?\s*month", tenor_raw, re.I)
            if not mt:
                continue
            months = int(mt.group(1))
            if months == 1:
                key = "1m"
            elif months == 3:
                key = "3m"
            elif months == 6:
                key = "6m"
            elif months == 9:
                key = "9m"
            elif months == 12:
                key = "12m"
            else:
                continue

            cur_info = out["currencies"].setdefault(cur, {})
            cur_info[key] = float(pct)
            if dep_raw and not cur_info.get("min_deposit_text"):
                cur_info["min_deposit_text"] = dep_raw

        if out["currencies"]:
            out["has_fcy_promo_table"] = True
            break
    return out


def append_uob_sgd_rows(
    rows: List[Dict[str, Any]],
    uob_sgd: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not uob_sgd or uob_sgd.get("error"):
        return rows
    out = list(rows)
    out.append(
        {
            "data_source": "UOB",
            "product_line": "SGD TD Promotion (Fixed Deposit - Fresh Funds)",
            "min_amount_text": uob_sgd.get("min_deposit_text") or NA,
            "max_amount_text": NA,
            "placement_range_text": uob_sgd.get("note_text") or NA,
            "rate_1m_pct": NA,
            "rate_3m_pct": NA,
            "rate_5m_pct": NA,
            "rate_6m_pct": _rate_or_na(uob_sgd.get("rate_6m")),
            "rate_9m_pct": NA,
            "rate_12m_pct": _rate_or_na(uob_sgd.get("rate_12m")),
            "page_raw": uob_sgd.get("extra_page_raw") or NA,
        }
    )
    return out


def append_uob_fcy_rows(
    fx_rows: List[Dict[str, Any]],
    uob_fcy: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not uob_fcy or uob_fcy.get("error"):
        return fx_rows
    currs = uob_fcy.get("currencies") or {}
    if not currs:
        return fx_rows
    out = list(fx_rows)
    note = uob_fcy.get("note_text") or "UOB FCY promotional fixed deposit rates."
    for cur, info in currs.items():
        out.append(
            {
                "currency": cur,
                "rate_1m": _rate_or_na(info.get("1m")),
                "rate_3m": _rate_or_na(info.get("3m")),
                "rate_6m": _rate_or_na(info.get("6m")),
                "rate_9m": _rate_or_na(info.get("9m")),
                "rate_12m": _rate_or_na(info.get("12m")),
                "min_deposit_text": info.get("min_deposit_text") or NA,
                "max_deposit_text": NA,
                "page_text_1m": note,
                "data_source": f"UOB FCY TD promo ({cur})",
            }
        )
    return out


def extract_sif_fd_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Sing Investments & Finance (SingFinance) fixed deposit online page.
    Parse SGD promo rates table and check if FCY promo table exists on same page.
    """
    out: Dict[str, Any] = {
        "sgd_tier_1000": {},
        "sgd_tier_10000": {},
        "sgd_flash_100k": {},
        "tier_1000_text": "$1,000",
        "tier_10000_text": "$10,000",
        "tier_flash_text": "$100,000",
        "note_text": None,
        "fresh_funds_only": False,
        "has_fcy_promo_table": False,
    }
    # Flash special section: 1-24 months at one flat rate for min $100,000
    for t in soup.find_all("table"):
        txt = t.get_text(" ", strip=True).lower()
        if "$100,000" not in txt or "1 - 24 months" not in txt:
            continue
        p = _parse_percent(txt)
        if p is None:
            continue
        for k in ("1m", "3m", "6m", "9m", "12m"):
            out["sgd_flash_100k"][k] = float(p)
        break
    table = None
    for t in soup.find_all("table"):
        txt = t.get_text(" ", strip=True).lower()
        if "tenure" not in txt or "minimum deposit amount" not in txt:
            continue
        # 页面上常有两张表：促销横向简表 + 主利率表。
        # 仅主利率表会出现“1 month/3 months ...”行。
        if "1 month" not in txt and "3 months" not in txt:
            continue
        if "$10,000" in txt:
            table = t
            break
    if not table:
        return out
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 3:
            continue
        tenor = cells[0].strip().lower()
        if tenor in ("tenure", ""):
            continue
        m = re.search(r"(\d+)\s*month", tenor)
        if not m:
            continue
        tk = f"{int(m.group(1))}m"
        p0 = _parse_percent(cells[1])
        p1 = _parse_percent(cells[2])
        if p0 is not None:
            out["sgd_tier_1000"][tk] = float(p0)
        if p1 is not None:
            out["sgd_tier_10000"][tk] = float(p1)
    whole = soup.get_text("\n", strip=True)
    if re.search(r"Applicable to fresh funds only", whole, re.I):
        out["fresh_funds_only"] = True
    note = soup.find(string=re.compile(r"The above rates are subject to changes", re.I))
    if note:
        out["note_text"] = re.sub(r"\s+", " ", str(note)).strip()
    # FCY only appears as generic site navigation/links on this page, no FCY promo rate table found.
    out["has_fcy_promo_table"] = False
    return out


def append_sif_sgd_rows(
    rows: List[Dict[str, Any]],
    sif: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not sif or sif.get("error"):
        return rows
    out = list(rows)
    r1 = sif.get("sgd_tier_1000") or {}
    r2 = sif.get("sgd_tier_10000") or {}
    note = sif.get("note_text") or "SingFinance FD Online rates page."
    if sif.get("fresh_funds_only"):
        note = f"Fresh funds only. {note}".strip()
    if r1:
        out.append(
            {
                "data_source": "SingFinance SG",
                "product_line": "FD Online - Minimum Deposit $1,000",
                "min_amount_text": sif.get("tier_1000_text") or "$1,000",
                "max_amount_text": NA,
                "placement_range_text": note,
                "rate_1m_pct": _rate_or_na(r1.get("1m")),
                "rate_3m_pct": _rate_or_na(r1.get("3m")),
                "rate_5m_pct": NA,
                "rate_6m_pct": _rate_or_na(r1.get("6m")),
                "rate_9m_pct": NA,
                "rate_12m_pct": _rate_or_na(r1.get("12m")),
                "page_raw": NA,
            }
        )
    if r2:
        out.append(
            {
                "data_source": "SingFinance SG",
                "product_line": "FD Online - Minimum Deposit $10,000",
                "min_amount_text": sif.get("tier_10000_text") or "$10,000",
                "max_amount_text": NA,
                "placement_range_text": note,
                "rate_1m_pct": _rate_or_na(r2.get("1m")),
                "rate_3m_pct": _rate_or_na(r2.get("3m")),
                "rate_5m_pct": NA,
                "rate_6m_pct": _rate_or_na(r2.get("6m")),
                "rate_9m_pct": NA,
                "rate_12m_pct": _rate_or_na(r2.get("12m")),
                "page_raw": NA,
            }
        )
    rf = sif.get("sgd_flash_100k") or {}
    if rf:
        out.append(
            {
                "data_source": "SingFinance SG",
                "product_line": "FD Online Flash Special Rate - Minimum Deposit $100,000",
                "min_amount_text": sif.get("tier_flash_text") or "$100,000",
                "max_amount_text": NA,
                "placement_range_text": note,
                "rate_1m_pct": _rate_or_na(rf.get("1m")),
                "rate_3m_pct": _rate_or_na(rf.get("3m")),
                "rate_5m_pct": NA,
                "rate_6m_pct": _rate_or_na(rf.get("6m")),
                "rate_9m_pct": _rate_or_na(rf.get("9m")),
                "rate_12m_pct": _rate_or_na(rf.get("12m")),
                "page_raw": "Flash Special Rate: 1-24 months",
            }
        )
    return out


def extract_scb_sgd_fd_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Standard Chartered Singapore SGD time deposit Fresh Funds promo.
    Page contains a single promo table with tenor/min placement and
    promotional interest rate split by customer tier.
    """
    out: Dict[str, Any] = {
        "tenor": None,
        "min_placement_text": None,
        "note_text": None,
        "rates": {},
        "has_fcy_promo_table": False,
    }

    page_text = soup.get_text("\n", strip=True)
    m = re.search(
        r"From\s+\d{2}\s+\w+\s+\d{4}\s+to\s+\d{2}\s+\w+\s+\d{4}.*?minimum of\s+(S\$[\d,]+).*?Fresh Funds",
        page_text,
        re.I,
    )
    if m:
        out["note_text"] = " ".join(m.group(0).split())

    target_table = None
    for table in soup.find_all("table"):
        ttxt = table.get_text(" ", strip=True)
        if "Promotional Interest Rate" not in ttxt:
            continue
        if "Fresh Funds" not in ttxt:
            continue
        if "Minimum Placement Amount" not in ttxt:
            continue
        target_table = table
        break

    if not target_table:
        # Fallback: still try to find the table by its column headers.
        for table in soup.find_all("table"):
            ttxt = table.get_text(" ", strip=True)
            if "Promotional Interest Rate" in ttxt and "Minimum Placement Amount" in ttxt:
                target_table = table
                break

    if not target_table:
        return out

    trs = target_table.find_all("tr")
    if not trs:
        return out

    for tr in trs:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        tenor_cell = cells[0].get_text(" ", strip=True)
        min_cell = cells[1].get_text(" ", strip=True)
        promo_cell = cells[2].get_text(" ", strip=True)

        mt = re.search(r"(\d+)\s*months?", tenor_cell, re.I)
        if not mt:
            continue
        out["tenor"] = f"{int(mt.group(1))}m"
        out["min_placement_text"] = min_cell if min_cell else out["min_placement_text"]

        # Example: Personal Banking: 1.10% p.a. Priority Banking: 1.15% p.a. Priority Private: 1.20% p.a.
        rm_personal = re.search(r"Personal Banking:\s*([\d.]+)\s*%", promo_cell, re.I)
        rm_priority = re.search(r"Priority Banking:\s*([\d.]+)\s*%", promo_cell, re.I)
        rm_private = re.search(r"Priority Private:\s*([\d.]+)\s*%", promo_cell, re.I)

        rates: Dict[str, Optional[float]] = {
            "Personal Banking": float(rm_personal.group(1)) if rm_personal else None,
            "Priority Banking": float(rm_priority.group(1)) if rm_priority else None,
            "Priority Private": float(rm_private.group(1)) if rm_private else None,
        }
        out["rates"] = {k: v for k, v in rates.items() if v is not None}
        break

    # FCY promo table existence check: look for the same promo-table shape but with FCY/Foreign Currency/USD/AUD/GBP.
    fcy_present = False
    for table in soup.find_all("table"):
        ttxt = table.get_text(" ", strip=True).lower()
        if "promotional interest rate" not in ttxt:
            continue
        if "minimum placement amount" not in ttxt:
            continue
        if any(x in ttxt for x in ["fcy", "foreign currency", "usd", "aud", "gbp"]):
            fcy_present = True
            break
    out["has_fcy_promo_table"] = fcy_present
    if not out["note_text"]:
        out["note_text"] = "Fresh Funds2 time deposit promo (see page for eligibility/terms)."
    return out


def append_scb_sgd_rows(
    rows: List[Dict[str, Any]],
    scb: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not scb or scb.get("error"):
        return rows
    out = list(rows)
    note = (scb.get("note_text") or "").strip() or NA
    tenor_key = scb.get("tenor") or "9m"

    # This page only has one tenor row; map it into the 9m column.
    def _row(tier_label: str, v: Optional[float]) -> Dict[str, Any]:
        return {
            "data_source": "SCB SG",
            "product_line": f"SGD TD Fresh Funds2 - {tier_label}",
            "min_amount_text": scb.get("min_placement_text") or NA,
            "max_amount_text": NA,
            "placement_range_text": note,
            "rate_1m_pct": NA,
            "rate_3m_pct": NA,
            "rate_5m_pct": NA,
            "rate_6m_pct": NA,
            "rate_9m_pct": _rate_or_na(v) if tenor_key == "9m" else NA,
            "rate_12m_pct": NA,
            "page_raw": NA,
        }

    rates = scb.get("rates") or {}
    if rates.get("Personal Banking") is not None:
        out.append(_row("Personal Banking", rates.get("Personal Banking")))
    if rates.get("Priority Banking") is not None:
        out.append(_row("Priority Banking", rates.get("Priority Banking")))
    if rates.get("Priority Private") is not None:
        out.append(_row("Priority Private", rates.get("Priority Private")))
    return out


def extract_sbi_sgd_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    SBI Singapore: SGD promotions page.
    Extract promotional SGD term deposit rates by tenor and minimum deposit.
    Also detect whether the table includes non-SGD promotional currencies.
    """
    out: Dict[str, Any] = {
        "rows": [],
        "note_text": None,
        "has_fcy_promo_table": False,
    }

    # A lightweight note grab for placement_range_text.
    note = soup.find(string=re.compile(r"Terms and Conditions Governing SBIS SGD", re.I))
    if not note:
        note = soup.find(string=re.compile(r"Applicable for fresh and renewal", re.I))
    if note:
        out["note_text"] = re.sub(r"\s+", " ", str(note)).strip()

    for table in soup.find_all("table"):
        ttxt = table.get_text(" ", strip=True).lower()
        if "promotional interest rate" not in ttxt:
            continue
        if "minimum deposit" not in ttxt:
            continue
        if "tenor" not in ttxt:
            continue

        trs = table.find_all("tr")
        if not trs:
            continue

        header_idx = None
        col_idx: Dict[str, int] = {}
        for i, tr in enumerate(trs[:5]):
            cells = [c.get_text(" ", strip=True).lower() for c in tr.find_all(["th", "td"])]
            if not cells:
                continue
            if not (any("currency" in c for c in cells) and any("tenor" in c for c in cells)):
                continue
            if not any("promotional interest rate" in c or "promotional interest rate" in c for c in cells):
                # tolerate partial header names
                pass
            header_idx = i
            for j, c in enumerate(cells):
                if "currency" in c:
                    col_idx["currency"] = j
                elif "tenor" in c:
                    col_idx["tenor"] = j
                elif "promotional" in c and "rate" in c:
                    col_idx["rate"] = j
                elif "minimum" in c and "deposit" in c:
                    col_idx["min"] = j
            break

        # Default column assumption (Currency, Tenor, Promotional Rate, Minimum Deposit)
        if header_idx is None:
            header_idx = 0
            col_idx = {"currency": 0, "tenor": 1, "rate": 2, "min": 3}

        for tr in trs[header_idx + 1 :]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < max(col_idx.values(), default=3) + 1:
                continue
            cur = (cells[col_idx.get("currency", 0)] or "").strip().upper()
            tenor_raw = cells[col_idx.get("tenor", 1)] or ""
            rate_raw = cells[col_idx.get("rate", 2)] or ""
            min_raw = cells[col_idx.get("min", 3)] or ""

            if not cur:
                continue
            tenor_key = None
            m = re.search(r"(\d+)\s*-\s*months?|(\d+)\s*month|(\d+)\s*months?|(\d+)\s*year", tenor_raw.lower())
            if m:
                # first non-empty group
                for g in m.groups():
                    if g:
                        n = int(g)
                        break
                else:
                    n = None
                if "year" in tenor_raw.lower():
                    tenor_key = f"{n * 12}m" if n is not None else None
                else:
                    tenor_key = f"{n}m" if n is not None else None
            if not tenor_key:
                continue

            pct = _parse_percent(rate_raw)
            if pct is None:
                continue

            if cur != "SGD":
                out["has_fcy_promo_table"] = True
                continue

            out["rows"].append(
                {
                    "tenor_key": tenor_key,
                    "rate_pct": float(pct),
                    "min_deposit_text": min_raw,
                }
            )
        return out

    return out


def append_sbi_sgd_rows(
    rows: List[Dict[str, Any]],
    sbi: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not sbi or sbi.get("error"):
        return rows
    out = list(rows)
    note = (sbi.get("note_text") or "").strip() or NA
    for r in sbi.get("rows") or []:
        tk = r.get("tenor_key")
        v = r.get("rate_pct")
        min_txt = r.get("min_deposit_text") or NA

        def _col(month_key: str) -> Any:
            return _rate_or_na(v) if tk == month_key else NA

        out.append(
            {
                "data_source": "SBI SG",
                "product_line": "SGD Term Deposit Promotion",
                "min_amount_text": min_txt,
                "max_amount_text": NA,
                "placement_range_text": note,
                "rate_1m_pct": _col("1m"),
                "rate_3m_pct": _col("3m"),
                "rate_5m_pct": NA,
                "rate_6m_pct": _col("6m"),
                "rate_9m_pct": _col("9m"),
                "rate_12m_pct": _col("12m"),
                "page_raw": NA,
            }
        )
    return out


def extract_sbi_fcy_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    SBI FCY promotions page (USD / maybe other FCY).
    Expected table:
      Currency | Tenor | Promotional Interest Rate* (p.a.) | Minimum Deposit
    """
    out: Dict[str, Any] = {
        "currencies": {},
        "note_text": None,
        "has_fcy_promo_table": False,
    }

    note = soup.find(string=re.compile(r"Terms and Conditions Governing SBIS", re.I))
    if note:
        out["note_text"] = re.sub(r"\s+", " ", str(note)).strip()

    for table in soup.find_all("table"):
        ttxt = table.get_text(" ", strip=True).lower()
        if "promotional interest rate" not in ttxt or "minimum deposit" not in ttxt:
            continue
        if "tenor" not in ttxt:
            continue
        out["has_fcy_promo_table"] = True
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 4:
                continue
            # Some pages repeat headers; filter by tenor/rate pattern.
            cur = (cells[0] or "").strip().upper()
            if not cur or cur in ("CURRENCY", "Ccy".upper()):
                continue
            tenor_raw = cells[1] or ""
            rate_raw = cells[2] or ""
            min_raw = cells[3] or ""
            pct = _parse_percent(rate_raw)
            if pct is None:
                continue
            m = re.search(r"(\d+)\s*[- ]?\s*month", tenor_raw, re.I)
            if m:
                tk = f"{int(m.group(1))}m"
            else:
                m2 = re.search(r"(\d+)\s*[- ]?\s*year", tenor_raw, re.I)
                if m2:
                    tk = f"{int(m2.group(1)) * 12}m"
                else:
                    continue

            out["currencies"][cur] = {
                tk: float(pct),
                "min_deposit_text": min_raw,
            }
        break

    # Normalize into expected columns later.
    return out


def append_sbi_fcy_rows(
    fx_rows: List[Dict[str, Any]],
    sbi_fcy: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not sbi_fcy or sbi_fcy.get("error"):
        return fx_rows
    currs = sbi_fcy.get("currencies") or {}
    if not currs:
        return fx_rows
    out = list(fx_rows)
    note = (sbi_fcy.get("note_text") or "").strip() or "SBI FCY promotions."

    def _get_rate(cur_rates: Dict[str, Any], key: str) -> Any:
        return _rate_or_na(cur_rates.get(key))

    for cur, info in currs.items():
        out.append(
            {
                "currency": cur,
                "rate_1m": NA,
                "rate_3m": NA,
                "rate_6m": NA,
                "rate_9m": NA,
                "rate_12m": NA,
                "min_deposit_text": info.get("min_deposit_text") or NA,
                "max_deposit_text": NA,
                "page_text_1m": note,
                "data_source": f"SBI SG FCY TD promo ({cur})",
            }
        )
        # Map available tenor(s) into the correct column.
        # We only support one tenor per currency on this page.
        out[-1]["rate_6m"] = _rate_or_na(info.get("6m"))
        out[-1]["rate_9m"] = _rate_or_na(info.get("9m"))
        out[-1]["rate_12m"] = _rate_or_na(info.get("12m"))
        out[-1]["rate_3m"] = _rate_or_na(info.get("3m"))
        out[-1]["rate_1m"] = _rate_or_na(info.get("1m"))
    return out


def extract_scb_fcy_fd_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Standard Chartered Singapore FCY time deposit special Fresh Funds promo.

    The page typically contains a single special table (e.g. USD, tenor 9 months)
    with tier-specific promotional interest rates.
    """
    out: Dict[str, Any] = {
        "currency": None,
        "tenor": None,
        "min_placement_text": None,
        "note_text": None,
        "rates": {},
        "has_fcy_promo_table": False,
        "raw_promo_cell": None,
    }

    target_table = None
    for table in soup.find_all("table"):
        ttxt = table.get_text(" ", strip=True)
        tlow = ttxt.lower()
        if "promotional interest rate" not in tlow:
            continue
        if "fresh funds" not in tlow:
            continue
        # Example: "USD Time Deposit (Fixed Deposit) Special Fresh Funds Promotion"
        if "usd" in tlow and "time deposit" in tlow:
            target_table = table
            break

    if not target_table:
        # Fallback: any FCY special table that contains "Fresh Funds in USD".
        for table in soup.find_all("table"):
            ttxt = table.get_text(" ", strip=True)
            tlow = ttxt.lower()
            if "promotional interest rate" in tlow and "fresh funds" in tlow and "usd" in tlow:
                target_table = table
                break

    if not target_table:
        return out

    trs = target_table.find_all("tr")
    for tr in trs:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        tenor_cell = cells[0].get_text(" ", strip=True)
        min_cell = cells[1].get_text(" ", strip=True)
        promo_cell = cells[2].get_text(" ", strip=True)

        mt = re.search(r"(\d+)\s*months?", tenor_cell, re.I)
        if not mt:
            continue
        out["tenor"] = f"{int(mt.group(1))}m"

        if "USD" in tenor_cell.upper() or "USD" in target_table.get_text(" ", strip=True):
            out["currency"] = "USD"

        out["min_placement_text"] = min_cell if min_cell else out["min_placement_text"]
        out["raw_promo_cell"] = promo_cell

        rm_personal = re.search(r"Personal Banking\s*:?\s*([\d.]+)\s*%", promo_cell, re.I)
        rm_priority = re.search(r"Priority Banking\s*:?\s*([\d.]+)\s*%", promo_cell, re.I)
        rm_private = re.search(
            r"Priority\s*Private\s*Banking\s*:?\s*([\d.]+)\s*%",
            promo_cell,
            re.I,
        )
        rates: Dict[str, Optional[float]] = {
            "Personal Banking": float(rm_personal.group(1)) if rm_personal else None,
            "Priority Banking": float(rm_priority.group(1)) if rm_priority else None,
            "Priority Private Banking": float(rm_private.group(1)) if rm_private else None,
        }
        out["rates"] = {k: v for k, v in rates.items() if v is not None}
        break

    note = soup.find(string=re.compile(r"promotional.*interest.*rates are only applicable", re.I))
    if note:
        out["note_text"] = re.sub(r"\s+", " ", str(note)).strip()
    out["has_fcy_promo_table"] = True
    return out


def append_scb_fcy_rows(
    fx_rows: List[Dict[str, Any]],
    scb_fcy: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not scb_fcy or scb_fcy.get("error"):
        return fx_rows
    out = list(fx_rows)

    cur = scb_fcy.get("currency") or "USD"
    note = (scb_fcy.get("note_text") or "").strip() or "SCB FCY Fresh Funds promo (see page)."
    promo_cell = (scb_fcy.get("raw_promo_cell") or "").strip()
    page_text = promo_cell or note

    v9 = None
    # This promo is tenor 9 months; map to rate_9m column.
    # (We store tier-specific rates as separate rows.)
    rates = scb_fcy.get("rates") or {}
    for tier, v in rates.items():
        if v is None:
            continue
        out.append(
            {
                "currency": cur,
                "rate_1m": NA,
                "rate_3m": NA,
                "rate_6m": NA,
                "rate_9m": _rate_or_na(v),
                "rate_12m": NA,
                "min_deposit_text": scb_fcy.get("min_placement_text") or NA,
                "max_deposit_text": NA,
                "page_text_1m": page_text,
                "data_source": f"SCB FCY {cur} Fresh Funds2 - {tier}",
            }
        )
    return out


def append_hsbc_sgd_rows(
    rows: List[Dict[str, Any]],
    hsbc: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not hsbc or hsbc.get("error"):
        return rows
    out = list(rows)
    cap = (hsbc.get("caption_text") or "").strip()
    base_note = cap or "非手机银行申请时适用（详见页面）"
    for sr in hsbc.get("segment_rates") or []:
        seg = sr.get("segment") or ""
        tier_label = f"客户分层：{seg}（非金额分层）" if seg else "按客户分层（非金额分层）"
        out.append(
            {
                "data_source": "HSBC SG",
                "product_line": f"新币定存 - {seg}",
                "min_amount_text": tier_label,
                "max_amount_text": tier_label,
                "placement_range_text": base_note,
                "rate_1m_pct": _rate_or_na(sr.get("1m")),
                "rate_3m_pct": _rate_or_na(sr.get("3m")),
                "rate_5m_pct": NA,
                "rate_6m_pct": _rate_or_na(sr.get("6m")),
                "rate_9m_pct": _rate_or_na(sr.get("9m")),
                "rate_12m_pct": _rate_or_na(sr.get("12m")),
                "page_raw": NA,
            }
        )
    mp = hsbc.get("mobile_promo_paragraph")
    r3 = hsbc.get("mobile_promo_rate_3m")
    if mp and r3 is not None:
        out.append(
            {
                "data_source": "HSBC SG",
                "product_line": "新币定存 - 限时优惠（手机银行，新资金≥S$30,000，3个月）",
                "min_amount_text": "S$30,000",
                "max_amount_text": NA,
                "placement_range_text": mp,
                "rate_1m_pct": NA,
                "rate_3m_pct": r3,
                "rate_5m_pct": NA,
                "rate_6m_pct": NA,
                "rate_9m_pct": NA,
                "rate_12m_pct": NA,
                "page_raw": mp,
            }
        )
    return out


def append_hsbc_fcy_promo_rows(
    fx_rows: List[Dict[str, Any]],
    hsbc_fcy_board_rows: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    if not hsbc_fcy_board_rows:
        return fx_rows
    out = list(fx_rows)
    for r in hsbc_fcy_board_rows:
        cur = str(r.get("currency") or "").upper()
        if not re.match(r"^[A-Z]{3}$", cur):
            continue
        out.append(
            {
                "currency": cur,
                "rate_1m": _rate_or_na(r.get("rate_1m_pct")),
                "rate_3m": _rate_or_na(r.get("rate_3m_pct")),
                "rate_6m": _rate_or_na(r.get("rate_6m_pct")),
                "rate_9m": _rate_or_na(r.get("rate_9m_pct")),
                "rate_12m": _rate_or_na(r.get("rate_12m_pct")),
                "min_deposit_text": r.get("placement_range_text") or NA,
                "max_deposit_text": NA,
                "page_text_1m": "HSBC FCY Time Deposits Personal Banking PDF.",
                "data_source": f"HSBC SG FCY TD promo ({cur})",
            }
        )
    return out


def append_maybank_sgd_rows(
    rows: List[Dict[str, Any]],
    maybank: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not maybank or maybank.get("error"):
        return rows
    out = list(rows)
    min_amt = maybank.get("min_amount_text") or "S$20,000"
    note = maybank.get("note_text") or "Maybank SGD Time Deposit promotion."
    if maybank.get("bundle_branch_6m") is not None:
        out.append(
            {
                "data_source": "Maybank SG",
                "product_line": "SGD Time Deposit - Deposits Bundle Promotion (branch, 6m)",
                "min_amount_text": min_amt,
                "max_amount_text": NA,
                "placement_range_text": note,
                "rate_1m_pct": NA,
                "rate_3m_pct": NA,
                "rate_5m_pct": NA,
                "rate_6m_pct": maybank.get("bundle_branch_6m"),
                "rate_9m_pct": NA,
                "rate_12m_pct": NA,
                "page_raw": NA,
            }
        )
    if maybank.get("bundle_general_9m") is not None or maybank.get("bundle_general_12m") is not None:
        out.append(
            {
                "data_source": "Maybank SG",
                "product_line": "SGD Time Deposit - Deposits Bundle Promotion (branch/online)",
                "min_amount_text": min_amt,
                "max_amount_text": NA,
                "placement_range_text": note,
                "rate_1m_pct": NA,
                "rate_3m_pct": NA,
                "rate_5m_pct": NA,
                "rate_6m_pct": NA,
                "rate_9m_pct": _rate_or_na(maybank.get("bundle_general_9m")),
                "rate_12m_pct": _rate_or_na(maybank.get("bundle_general_12m")),
                "page_raw": NA,
            }
        )
    st = maybank.get("standalone") or {}
    if st:
        out.append(
            {
                "data_source": "Maybank SG",
                "product_line": "SGD Time Deposit - Standalone promotion",
                "min_amount_text": min_amt,
                "max_amount_text": NA,
                "placement_range_text": note,
                "rate_1m_pct": _rate_or_na(st.get("1m")),
                "rate_3m_pct": _rate_or_na(st.get("3m")),
                "rate_5m_pct": _rate_or_na(st.get("5m")),
                "rate_6m_pct": _rate_or_na(st.get("6m")),
                "rate_9m_pct": _rate_or_na(st.get("9m")),
                "rate_12m_pct": _rate_or_na(st.get("12m")),
                "page_raw": NA,
            }
        )
    return out


def _parse_hlf_rate_cell(raw: str) -> Optional[float]:
    """HLF pages may double-encode e.g. 1.20&amp;percnt; in cell text."""
    t = html_module.unescape(html_module.unescape(raw))
    t = t.replace("&percnt;", "%").replace("percnt;", "%")
    return _parse_percent(t)


def extract_hlf_sgd_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Hong Leong Finance: branch/festival promo + online special (5/6/9/12 months).
    https://www.hlf.com.sg/personal/promotions/fixed-deposits-promotion-singapore.php
    """
    out: Dict[str, Any] = {
        "special_promo": [],
        "branch_promo": [],
        "online_promo": [],
        "published_as_of": None,
    }

    def _parse_hlf_tier_table(table) -> List[Dict[str, Any]]:
        rows_out: List[Dict[str, Any]] = []
        if not table:
            return rows_out
        trs = table.find_all("tr")
        if not trs:
            return rows_out
        hdr = trs[0].find_all(["th", "td"])
        if len(hdr) < 2:
            return rows_out
        month_cols: Dict[int, str] = {}
        for i, c in enumerate(hdr[1:], start=1):
            t = c.get_text(" ", strip=True)
            m = re.search(r"(\d+)\s*[-\s]*Month", t, re.I)
            if m:
                month_cols[i] = f"{int(m.group(1))}m"
        if not month_cols:
            return rows_out
        for tr in trs[1:]:
            cells = tr.find_all("td")
            if len(cells) < 2:
                continue
            tier = cells[0].get_text(" ", strip=True)
            row: Dict[str, Any] = {"tier": tier}
            any_rate = False
            for i, k in month_cols.items():
                if i >= len(cells):
                    continue
                v = _parse_hlf_rate_cell(cells[i].get_text())
                if v is None:
                    continue
                row[k] = v
                any_rate = True
            if not any_rate:
                continue
            rows_out.append(row)
        return rows_out

    def _find_rate_table_for_section(sec) -> Optional[Any]:
        for tbl in sec.find_all_next("table"):
            stop = tbl.find_previous(["h3", "h4"])
            if stop is not sec:
                break
            txt = tbl.get_text(" ", strip=True).lower()
            if "deposit amount" in txt and "month" in txt and "interest rates" not in txt:
                return tbl
        return None

    # 新版页面通常用 data-id=0/1/2 标识三块利率表（special/branch/online）
    t_special = soup.select_one("table.calculator-table[data-id='0']")
    t_branch = soup.select_one("table.calculator-table[data-id='1']")
    t_online = soup.select_one("table.calculator-table[data-id='2']")
    if t_special:
        out["special_promo"] = _parse_hlf_tier_table(t_special)
    if t_branch:
        out["branch_promo"] = _parse_hlf_tier_table(t_branch)
    if t_online:
        out["online_promo"] = _parse_hlf_tier_table(t_online)

    for sec in soup.find_all(["h3", "h4"]):
        ttl = sec.get_text(" ", strip=True).lower()
        tbl = _find_rate_table_for_section(sec)
        if not tbl:
            continue
        parsed = _parse_hlf_tier_table(tbl)
        if not parsed:
            continue
        if "special fixed deposit promotion" in ttl and not out["special_promo"]:
            out["special_promo"] = parsed
        elif ttl == "fixed deposit promotion" and not out["branch_promo"]:
            out["branch_promo"] = parsed
        elif "online fixed deposit special" in ttl and not out["online_promo"]:
            out["online_promo"] = parsed

    if not out["branch_promo"]:
        t1 = soup.select_one("table.calculator-table[data-id='1']")
        if t1:
            out["branch_promo"] = _parse_hlf_tier_table(t1)
    if not out["online_promo"]:
        t2 = soup.select_one("table.calculator-table[data-id='2']")
        if t2:
            out["online_promo"] = _parse_hlf_tier_table(t2)
    pub = soup.find(string=re.compile(r"Published rates are as of", re.I))
    if pub:
        out["published_as_of"] = pub.strip()
    return out


def append_hlf_sgd_rows(
    rows: List[Dict[str, Any]],
    hlf: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not hlf or hlf.get("error"):
        return rows
    out = list(rows)
    pub = (hlf.get("published_as_of") or "").strip()
    pub_note = f" | {pub}" if pub else ""
    for row in hlf.get("special_promo") or []:
        tier = (row.get("tier") or "").replace("\xa0", " ").strip()
        out.append(
            {
                "data_source": "HLF",
                "product_line": f"SGD FD - Special promo (fresh funds) ({tier})",
                "min_amount_text": tier or NA,
                "max_amount_text": NA,
                "placement_range_text": f"Special promo fresh funds{pub_note}".strip(),
                "rate_1m_pct": NA,
                "rate_3m_pct": row.get("3m", NA),
                "rate_5m_pct": row.get("5m", NA),
                "rate_6m_pct": row.get("6m", NA),
                "rate_9m_pct": row.get("9m", NA),
                "rate_12m_pct": row.get("12m", NA),
                "page_raw": NA,
            }
        )
    for row in hlf.get("branch_promo") or []:
        tier = (row.get("tier") or "").replace("\xa0", " ").strip()
        out.append(
            {
                "data_source": "HLF",
                "product_line": f"SGD FD - Branch / festival promo ({tier})",
                "min_amount_text": tier or NA,
                "max_amount_text": NA,
                "placement_range_text": f"Branch or counter promo{pub_note}".strip(),
                "rate_1m_pct": NA,
                "rate_3m_pct": row.get("3m", NA),
                "rate_5m_pct": row.get("5m", NA),
                "rate_6m_pct": row.get("6m", NA),
                "rate_9m_pct": row.get("9m", NA),
                "rate_12m_pct": row.get("12m", NA),
                "page_raw": NA,
            }
        )
    for row in hlf.get("online_promo") or []:
        tier = (row.get("tier") or "").replace("\xa0", " ").strip()
        out.append(
            {
                "data_source": "HLF",
                "product_line": f"SGD FD - Online special HLF Digital ({tier})",
                "min_amount_text": tier or NA,
                "max_amount_text": NA,
                "placement_range_text": f"Online via HLF Digital{pub_note}".strip(),
                "rate_1m_pct": NA,
                "rate_3m_pct": row.get("3m", NA),
                "rate_5m_pct": row.get("5m", NA),
                "rate_6m_pct": row.get("6m", NA),
                "rate_9m_pct": row.get("9m", NA),
                "rate_12m_pct": row.get("12m", NA),
                "page_raw": NA,
            }
        )
    return out


def extract_hl_sgd_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    HL Bank SGD Fresh Fund FD table (Online vs Branch, 6m / 12m).
    https://www.hlbank.com.sg/en/personal-banking/promotions/fixed-deposit-promotion-2026.html
    """
    out: Dict[str, Any] = {"online": None, "branch": None}
    table = None
    for cand in soup.find_all("table"):
        header = cand.get_text(" ", strip=True).lower()
        if "channel" in header and "promotional" in header and "minimum placement" in header:
            table = cand
            break
    if not table:
        for tag in soup.find_all("h4"):
            if "SGD Fresh Fund" in tag.get_text():
                par = tag.find_parent()
                if par:
                    table = par.find_next("table")
                break
    if not table:
        return out
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 4:
            continue
        ch = cells[0].strip().lower()
        if "channel" in ch or ch in ("6 months", "12 months"):
            continue
        p6 = _parse_percent(cells[1]) if len(cells) > 1 else None
        p12 = _parse_percent(cells[2]) if len(cells) > 2 else None
        if "online" in ch:
            out["online"] = {
                "6m": p6,
                "12m": p12,
                "min_placement": cells[3].replace("\xa0", " ").strip(),
                "channel_note": "HLB Connect only (online)",
            }
        elif ch == "branch":
            out["branch"] = {
                "6m": p6,
                "12m": p12,
                "min_placement": cells[3].replace("\xa0", " ").strip(),
            }
    return out


def extract_hl_fcy_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    HL Bank USD/AUD branch FD table (3 / 6 / 12 months) on same promo page.
    """
    out: Dict[str, Any] = {}
    for table in soup.find_all("table"):
        head = table.find("tr")
        if not head:
            continue
        ht = head.get_text(" ", strip=True).lower()
        if "tenure" not in ht or "promotional" not in ht:
            continue
        if "fixed deposit promotion" not in ht.replace("^", "").strip():
            continue
        tlow = table.get_text(" ", strip=True).lower()
        if "usd fixed" not in tlow and "aud fixed" not in tlow:
            continue
        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) < 4:
                continue
            name = cells[0].get_text(" ", strip=True).upper()
            if "USD FIXED" not in name and "AUD FIXED" not in name:
                continue
            rates: List[float] = []
            for p in cells[2].find_all("p"):
                v = _parse_percent(p.get_text())
                if v is not None:
                    rates.append(v)
            if len(rates) < 3:
                continue
            mn = cells[3].get_text(" ", strip=True)
            entry = {
                "3m": rates[0],
                "6m": rates[1],
                "12m": rates[2],
                "min_deposit": mn,
            }
            if "USD" in name:
                out["fcy_usd"] = entry
            else:
                out["fcy_aud"] = entry
        if out.get("fcy_usd") or out.get("fcy_aud"):
            break
    for p in soup.find_all("p"):
        t = p.get_text(" ", strip=True)
        if t.startswith("^") and "branch" in t.lower():
            out["fcy_branch_note"] = t
            break
    return out


def append_hl_sgd_rows(
    rows: List[Dict[str, Any]],
    hl: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not hl or hl.get("error"):
        return rows
    out = list(rows)
    on = hl.get("online")
    if on:
        out.append(
            {
                "data_source": "HL Bank",
                "product_line": "SGD Fresh Fund FD - Online (HLB Connect)",
                "min_amount_text": on.get("min_placement") or NA,
                "max_amount_text": NA,
                "placement_range_text": on.get("channel_note") or "Online promotion",
                "rate_1m_pct": NA,
                "rate_3m_pct": NA,
                "rate_5m_pct": NA,
                "rate_6m_pct": on.get("6m"),
                "rate_9m_pct": NA,
                "rate_12m_pct": on.get("12m"),
                "page_raw": NA,
            }
        )
    br = hl.get("branch")
    if br:
        out.append(
            {
                "data_source": "HL Bank",
                "product_line": "SGD Fresh Fund FD - Branch",
                "min_amount_text": br.get("min_placement") or NA,
                "max_amount_text": NA,
                "placement_range_text": "Branch promotion",
                "rate_1m_pct": NA,
                "rate_3m_pct": NA,
                "rate_5m_pct": NA,
                "rate_6m_pct": br.get("6m"),
                "rate_9m_pct": NA,
                "rate_12m_pct": br.get("12m"),
                "page_raw": NA,
            }
        )
    return out


def append_hl_fcy_rows(
    fx_rows: List[Dict[str, Any]],
    hl: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Append HL USD/AUD branch promo rows; drop legacy placeholder row if present."""
    if not hl or hl.get("error"):
        return fx_rows
    out = [r for r in fx_rows if r.get("currency") != "HL Bank (外币)"]
    usd = hl.get("fcy_usd")
    aud = hl.get("fcy_aud")
    note = hl.get("fcy_branch_note") or "Branch only (see HL promo page)"
    if usd:
        out.append(
            {
                "currency": "USD",
                "rate_1m": NA,
                "rate_3m": usd["3m"],
                "rate_6m": usd["6m"],
                "rate_9m": NA,
                "rate_12m": usd["12m"],
                "min_deposit_text": usd.get("min_deposit", NA),
                "max_deposit_text": NA,
                "page_text_1m": NA,
                "data_source": f"HL Bank Branch FD promo (USD). {note}",
            }
        )
    if aud:
        out.append(
            {
                "currency": "AUD",
                "rate_1m": NA,
                "rate_3m": aud["3m"],
                "rate_6m": aud["6m"],
                "rate_9m": NA,
                "rate_12m": aud["12m"],
                "min_deposit_text": aud.get("min_deposit", NA),
                "max_deposit_text": NA,
                "page_text_1m": NA,
                "data_source": f"HL Bank Branch FD promo (AUD). {note}",
            }
        )
    return out


# ---------------------------------------------------------------------------
# 合并与 Citi 主页解析：外币行合并、Citi 新元/外币定存区块、页面杂项利率
# ---------------------------------------------------------------------------


def merge_fx_citi_cimb(
    citi_fx: Dict[str, Any],
    cimb: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Keep Citibank and CIMB FX promo rows separated (no cross-bank merge/override).
    """
    citi_rates = citi_fx.get("rates") or []
    limits = citi_fx.get("deposit_limits") or {}
    cimb_cur = (cimb or {}).get("currencies") or {}
    cimb_min = (cimb or {}).get("min_deposit_text")

    rows: List[Dict[str, Any]] = []
    for r in citi_rates:
        cur = str(r.get("currency", "")).upper()
        if not cur:
            continue
        rp = r.get("rate_percent")
        rows.append(
            {
                "currency": cur,
                "rate_1m": rp if rp is not None else NA,
                "rate_3m": NA,
                "rate_6m": NA,
                "rate_9m": NA,
                "rate_12m": NA,
                "min_deposit_text": limits.get("min_deposit_text") or NA,
                "max_deposit_text": limits.get("max_deposit_text") or NA,
                "page_text_1m": r.get("rate_text") or NA,
                "data_source": "Citibank all-promo (1M FX TD)",
            }
        )
    for cur in sorted(cimb_cur.keys()):
        cm = cimb_cur[cur]
        rows.append(
            {
                "currency": cur,
                "rate_1m": cm["1m"],
                "rate_3m": cm["3m"],
                "rate_6m": cm["6m"],
                "rate_9m": NA,
                "rate_12m": cm["12m"],
                "min_deposit_text": cimb_min or NA,
                "max_deposit_text": NA,
                "page_text_1m": NA,
                "data_source": "CIMB Foreign Currency FD (online promo)",
            }
        )
    return rows


def extract_fx_time_deposit(soup: BeautifulSoup) -> Dict[str, Any]:
    empty_limits = {
        "min_deposit_text": None,
        "max_deposit_text": None,
        "terms_sentence": None,
    }
    out: Dict[str, Any] = {
        "section": "Foreign Currency FX Time Deposit Promotions",
        "tenor_label": "1 Month",
        "rates": [],
        "notes": [],
        "deposit_limits": empty_limits,
    }
    cmp_text = _find_column_cmp_text(
        soup,
        "Foreign Currency FX Time Deposit Promotions",
        fallback_tokens=["foreign currency", "time deposit", "promotion"],
    )
    if not cmp_text:
        return out
    table = cmp_text.find("table")
    if not table:
        return out
    rows = table.find_all("tr")
    if not rows:
        return out
    for tr in rows[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        cur, raw_rate = cells[0], cells[1]
        if cur.lower() == "currency":
            continue
        pct = _parse_percent(raw_rate)
        out["rates"].append({"currency": cur, "rate_percent": pct, "rate_text": raw_rate})
    for p in cmp_text.find_all("p"):
        t = p.get_text(" ", strip=True)
        if t:
            out["notes"].append(t)
    out["deposit_limits"] = parse_fx_deposit_limits(out["notes"])
    return out


def extract_boc_promo(soup: BeautifulSoup) -> Dict[str, Any]:
    # HOTSPOT_DOM: Chinese page text parsing; wording/order/spacing changes can break regex.
    """
    BOC SG promo page (Chinese): same page contains SGD and FCY FD promo rates.
    """
    out: Dict[str, Any] = {
        "sgd": {
            "rates": {},
            "tier_200k_9m": None,
            "tier_200k_12m": None,
        },
        "fx": {},
        "fx_min_by_currency": {},
        "validity_text": None,
        "as_at": None,
    }
    txt = soup.get_text(" ", strip=True)
    txt = re.sub(r"\s+", " ", txt)

    mv = re.search(r"有效期为([^。]+)。", txt)
    if mv:
        out["validity_text"] = mv.group(1).strip()
    ma = re.search(r"个人定期存款促销利率\(\d{8}\)\s+(\d{4}-\d{2}-\d{2})", txt)
    if ma:
        out["as_at"] = ma.group(1)

    msgd = re.search(r"新元\s+(.*?)\s+美元\s", txt, re.S)
    sgd_blk = msgd.group(1) if msgd else ""
    # 形态示例：
    # 9个月 500 1.35 200,000 1.38
    # 12个月 500 1.40
    for m in re.finditer(
        r"(1|2|3|4|5|6|9|12)个月\s+(?:(\d[\d,]*)\s+)?([\d.]+)(?:\s+(\d[\d,]*)\s+([\d.]+))?",
        sgd_blk,
    ):
        mon = int(m.group(1))
        rate_base = m.group(3)
        tier2_amount = m.group(4)
        tier2_rate = m.group(5)
        try:
            out["sgd"]["rates"][f"{mon}m"] = float(rate_base)
        except Exception:
            pass
        if tier2_amount and tier2_rate:
            amt = re.sub(r"\D", "", str(tier2_amount))
            try:
                r2 = float(tier2_rate)
            except Exception:
                r2 = None
            if r2 is not None:
                if mon == 9 and amt == "200000":
                    out["sgd"]["tier_200k_9m"] = r2
                if mon == 12 and amt == "200000":
                    out["sgd"]["tier_200k_12m"] = r2

    fx_map = {
        "美元": "USD",
        "澳元": "AUD",
        "新西兰元": "NZD",
        "欧元": "EUR",
        "英镑": "GBP",
    }
    for zh, code in fx_map.items():
        pat = rf"{zh}\s+(.*?)(?:(?:美元|澳元|新西兰元|欧元|英镑)\s+1个月|有效期为)"
        mfx = re.search(pat, txt, re.S)
        if not mfx:
            continue
        blk = mfx.group(1)
        rates: Dict[str, float] = {}
        # 形态示例：
        # 1个月 2,000 3.65
        # 3个月 3.70
        # 9个月 3.90
        first_min = None
        for mm in re.finditer(r"(1|3|6|9|12)个月\s+(?:(\d[\d,]*)\s+)?([\d.]+)", blk):
            mon = int(mm.group(1))
            min_amt = mm.group(2)
            rate_v = mm.group(3)
            try:
                rates[f"{mon}m"] = float(rate_v)
            except Exception:
                continue
            if mon == 1 and min_amt:
                first_min = min_amt
        if rates:
            out["fx"][code] = rates
            if first_min:
                out["fx_min_by_currency"][code] = first_min
    return out


def _boc_promo_annotation_text(boc: Dict[str, Any]) -> str:
    """
    中行促销页同时存在：
    - 促销「有效期」文案；
    - 标题/表头附近的利率表「标注日期」（as_at，常为 PDF/公告更新日）。

    与脚本「抓取时间」不是同一概念，故在写入 Excel 时用中文前缀区分，避免误读。
    """
    parts: List[str] = []
    ur = boc.get("url_resolution") or {}
    if ur.get("switched_from_configured"):
        parts.append("公告链接：已从官网栏目列表自动选用当前置顶稿（配置链为回退基准）")
    elif ur.get("index_error") and ur.get("follow_latest_from_index"):
        msg = str(ur.get("index_error") or "")[:120]
        parts.append(f"栏目页不可用已回退直达链：{msg}")
    elif ur.get("index_parse_empty") and ur.get("follow_latest_from_index"):
        parts.append("栏目页未解析到公告链，已按配置的直达 URL 抓取")
    note = (boc.get("validity_text") or "").strip()
    if note:
        parts.append(f"促销有效期（页面）：{note}")
    as_at = (boc.get("as_at") or "").strip()
    if as_at:
        parts.append(f"利率表标注日期（页面）：{as_at}")
    ft = (boc.get("fetched_at_utc") or "").strip()
    if ft:
        parts.append(f"脚本抓取时间(UTC)：{ft}")
    return "；".join(parts) if parts else NA


def _boc_promo_annotation_placement_short(boc: Dict[str, Any]) -> str:
    """写入「资金区间_页面」的短说明：不含公告链/栏目页长句，避免在表格里横向盖住利率列。"""
    parts: List[str] = []
    note = (boc.get("validity_text") or "").strip()
    if note:
        parts.append(f"促销有效期（页面）：{note}")
    as_at = (boc.get("as_at") or "").strip()
    if as_at:
        parts.append(f"利率表标注日期（页面）：{as_at}")
    ft = (boc.get("fetched_at_utc") or "").strip()
    if ft:
        parts.append(f"脚本抓取时间(UTC)：{ft}")
    return "；".join(parts) if parts else NA


def append_boc_sgd_rows(
    rows: List[Dict[str, Any]],
    boc: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: maps parsed BOC SGD tenors into 新元定存促销 columns.
    if not boc or boc.get("error"):
        return rows
    sgd = boc.get("sgd") or {}
    rates = sgd.get("rates") or {}
    if not rates:
        return rows
    out = list(rows)
    ann = _boc_promo_annotation_text(boc)
    ann_short = _boc_promo_annotation_placement_short(boc)
    out.append(
        {
            "data_source": "BOC SG",
            "product_line": "个人定期存款促销利率（手机银行）— 起存500",
            "min_amount_text": "S$500",
            "max_amount_text": NA,
            "placement_range_text": ann_short,
            "rate_1m_pct": _rate_or_na(rates.get("1m")),
            "rate_3m_pct": _rate_or_na(rates.get("3m")),
            "rate_5m_pct": _rate_or_na(rates.get("5m")),
            "rate_6m_pct": _rate_or_na(rates.get("6m")),
            "rate_9m_pct": _rate_or_na(rates.get("9m")),
            "rate_12m_pct": _rate_or_na(rates.get("12m")),
            "page_raw": ann,
        }
    )
    if sgd.get("tier_200k_9m") is not None or sgd.get("tier_200k_12m") is not None:
        t9 = sgd.get("tier_200k_9m")
        t12 = sgd.get("tier_200k_12m")
        out.append(
            {
                "data_source": "BOC SG",
                "product_line": "个人定期存款促销利率（手机银行）— 起存200,000",
                "min_amount_text": "S$200,000",
                "max_amount_text": NA,
                "placement_range_text": ann_short,
                "rate_1m_pct": _rate_or_na(rates.get("1m")),
                "rate_3m_pct": _rate_or_na(rates.get("3m")),
                "rate_5m_pct": _rate_or_na(rates.get("5m")),
                "rate_6m_pct": _rate_or_na(rates.get("6m")),
                "rate_9m_pct": _rate_or_na(t9 if t9 is not None else rates.get("9m")),
                "rate_12m_pct": _rate_or_na(t12 if t12 is not None else rates.get("12m")),
                "page_raw": ann,
            }
        )
    return out


def append_boc_fx_rows(
    fx_rows: List[Dict[str, Any]],
    boc: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    # HOTSPOT_DOM: maps parsed BOC FCY tenors into 外币定存促销 columns.
    if not boc or boc.get("error"):
        return fx_rows
    fx = boc.get("fx") or {}
    if not fx:
        return fx_rows
    out = list(fx_rows)
    ann = _boc_promo_annotation_text(boc)
    min_by_cur = boc.get("fx_min_by_currency") or {}
    for cur, r in fx.items():
        out.append(
            {
                "currency": cur,
                "rate_1m": _rate_or_na(r.get("1m")),
                "rate_3m": _rate_or_na(r.get("3m")),
                "rate_6m": _rate_or_na(r.get("6m")),
                "rate_9m": _rate_or_na(r.get("9m")),
                "rate_12m": _rate_or_na(r.get("12m")),
                "min_deposit_text": str(min_by_cur.get(cur) or "10,000"),
                "max_deposit_text": NA,
                "page_text_1m": ann,
                "data_source": f"BOC SG FD promo ({cur})",
            }
        )
    return out


def extract_sgd_time_deposit(soup: BeautifulSoup) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "section": "Exclusive SGD Time Deposit Promotions",
        "segments": [],
    }
    cmp_text = _find_column_cmp_text(soup, "Exclusive SGD Time Deposit Promotions")
    if not cmp_text:
        return out
    segment_title: Optional[str] = None
    for child in cmp_text.descendants:
        if getattr(child, "name", None) == "p":
            strong = child.find("b")
            if strong:
                segment_title = strong.get_text(" ", strip=True)
        elif getattr(child, "name", None) == "li" and segment_title:
            raw = child.get_text(" ", strip=True)
            m3 = re.search(
                r"([\d.]+)\s*%[^%]*p\.?\s*a\.\s*on\s*a\s*3[-\s]?month",
                raw,
                re.I,
            )
            m6 = re.search(
                r"([\d.]+)\s*%[^%]*p\.?\s*a\.\s*on\s*a\s*6[-\s]?month",
                raw,
                re.I,
            )
            if m3 or m6:
                placement = parse_sgd_funds_placement(raw)
                row = {
                    "audience": segment_title,
                    "raw": raw,
                    "rate_3m_percent": float(m3.group(1)) if m3 else None,
                    "rate_6m_percent": float(m6.group(1)) if m6 else None,
                }
                row.update(placement)
                out["segments"].append(row)
    return out


def extract_misc_rates(plain_text: str) -> Dict[str, Any]:
    """Best-effort regex for other p.a. mentions (use tag-stripped page text)."""
    misc: Dict[str, Any] = {}
    t = re.sub(r"\s+", " ", plain_text)
    # Citi Quick Cash
    q = re.search(
        r"as low as\s+([\d.]+)\s*%\s*p\.?\s*a.*?\(EIR\s+([\d.]+)\s*%\s*p\.?\s*a",
        t,
        re.I,
    )
    if q:
        misc["citi_quick_cash"] = {
            "advertised_rate_pa_percent": float(q.group(1)),
            "eir_pa_percent": float(q.group(2)),
        }
    # Citi–AIA time deposit promo (appears twice on page; footnote may stick to "p.a.")
    aia = re.findall(
        r"up to\s+([\d.]+)\s*%\s*p\.?\s*a\.?\s*\d*\s+on\s+a\s+2\s+month\s+SGD\s*/\s*USD\s+Time\s+Deposit",
        t,
        re.I,
    )
    if aia:
        vals = sorted({float(x) for x in aia})
        misc["citi_aia_insurance_time_deposit"] = {
            "max_promo_td_pa_percent": vals[-1] if vals else None,
            "occurrences": len(aia),
        }
    return misc


# 与项目其它模块一致：对 impl 内顶层 def 做异常兜底（stderr 中文原因 + SafeProxy 降级）
from bank_safety import auto_wrap_module_functions as _auto_wrap_module_functions

_auto_wrap_module_functions(
    globals(),
    module_name=__name__,
    exclude={"_icbc_singapore_get"},
)
