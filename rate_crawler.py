import argparse
import datetime as _dt
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup


TENOR_MONTHS_TO_LABEL = {
    1: "1M",
    3: "3M",
    6: "6M",
    9: "9M",
    12: "12M",
    18: "18M",
    24: "24M",
}

TENOR_LABELS = ["1M", "3M", "6M", "9M", "12M", "18M", "24M"]

_SESSION = requests.Session()
# Ignore HTTP(S)_PROXY injected by environment by default.
# (User can still run behind corporate proxy by editing this to True.)
_SESSION.trust_env = False

def normalize_currency(raw: str) -> str:
    """
    Normalize various currency labels to canonical keys used for sheet matching.
    Examples:
      - "SGD", "sgd促销", "SGD存款", "新元挂牌" -> "sgd"
      - "USD", "美元" -> "usd"
      - empty/others -> "others"
    """
    if raw is None:
        return "others"
    s = str(raw).strip().lower()
    if not s or s == "nan":
        return "others"
    # common synonyms
    if "sgd" in s or "新元" in s or "新加坡" in s:
        return "sgd"
    if "usd" in s or "美元" in s:
        return "usd"
    if "cny" in s or "rmb" in s or "人民币" in s or "人名币" in s:
        return "cny"
    if "hkd" in s or "港" in s:
        return "hkd"
    if "aud" in s or "澳" in s:
        return "aud"
    if "nzd" in s or "纽" in s:
        return "nzd"
    if "eur" in s or "欧" in s:
        return "eur"
    if "gbp" in s or "英" in s:
        return "gbp"
    if "cad" in s or "加" in s:
        return "cad"
    return s


def _auto_find_xlsx(curdir: str, mode: str) -> str:
    """
    mode:
      - rainbow: contains 20260311
      - market: contains 202603011
      - link: other xlsx
    """
    xs = [n for n in os.listdir(curdir) if n.lower().endswith(".xlsx")]
    if mode == "rainbow":
        matched = [n for n in xs if "20260311" in n]
    elif mode == "market":
        matched = [n for n in xs if "202603011" in n]
    elif mode == "link":
        rainbow = [n for n in xs if "20260311" in n]
        market = [n for n in xs if "202603011" in n]
        matched = [n for n in xs if n not in set(rainbow + market)]
    else:
        raise ValueError(f"Unknown mode: {mode}")
    if not matched:
        raise FileNotFoundError(f"Cannot auto-detect xlsx for mode={mode}, candidates={xs}")
    return sorted(matched, key=len)[0]


def _norm_header(s: str) -> str:
    return re.sub(r"\s+", "", (s or "")).strip().lower()


def _parse_percentish_rate(s: str) -> Optional[float]:
    """
    Convert rate string to a numeric value in *fraction* form (e.g. 1.15% -> 0.0115).
    Accepts:
      - 1.15%  / 1.15
      - 1.15E-2 / 1.15e-2
    """
    if not s:
        return None
    s0 = s.strip()
    # scientific notation first
    m_sci = re.search(r"([-+]?\d+(?:\.\d+)?)[ ]*[eE]([-+]?\d+)", s0)
    if m_sci:
        base = float(m_sci.group(1))
        exp = int(m_sci.group(2))
        val = base * (10 ** exp)
        return val

    # plain percent/decimal
    m = re.search(r"([-+]?\d+(?:\.\d+)?)\s*%?", s0)
    if not m:
        return None
    val = float(m.group(1))

    # Heuristic: values like 1.15 usually mean percent (1.15%), while 0.0115 is fraction.
    if val > 0.5:
        return val / 100.0
    return val


def fetch_html(url: str, timeout: int = 30, pause_s: float = 0.0) -> str:
    if pause_s:
        time.sleep(pause_s)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    }
    r = _SESSION.get(url, timeout=timeout, headers=headers)
    r.raise_for_status()
    # Many bank sites rely on meta charset=utf-8; requests may guess ISO-8859-1.
    if not r.encoding or (r.encoding or "").lower() in {"iso-8859-1", "latin-1"}:
        r.encoding = "utf-8"
    return r.text


def parse_boc_rates(html: str, currency: str = "sgd") -> Dict[str, float]:
    """
    BOC specific parsing:
      - Find the table whose rows contain pattern like 'X个月'
      - For each row: extract month (X) and the last rate-like number (e.g. '1.15')
      - Map month -> tenor label: 1->1M, 3->3M, 6->6M, 9->9M, 12->12M ...
    """
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")
    cur_key = normalize_currency(currency)
    # detect currency switches inside table by row headers (Chinese)
    currency_markers = {
        "sgd": ["新元", "新加坡元", "sgd"],
        "usd": ["美元", "usd"],
        "aud": ["澳元", "aud"],
        "nzd": ["新西兰元", "纽元", "nzd"],
        "eur": ["欧元", "eur"],
        "gbp": ["英镑", "gbp"],
        "cny": ["人民币", "rmb", "cny"],
        "hkd": ["港币", "hkd"],
        "cad": ["加元", "cad"],
    }

    def detect_currency(text: str) -> Optional[str]:
        t = (text or "").strip().lower()
        for k, markers in currency_markers.items():
            for m in markers:
                if m.lower() in t:
                    return k
        return None

    # choose best table by scoring "month rows + decimal rates"
    best = None
    best_score = (-1, -1, -1)  # (bonus, month_hits, decimal_hits)
    for t in tables:
        text = t.get_text(" ", strip=True)
        month_hits = len(re.findall(r"\d+\s*个?月", text))
        dec_hits = len(re.findall(r"\d+\.\d+", text))
        if month_hits and dec_hits:
            bonus = 0
            t_low = text.lower()
            # Prefer mobile-banking promo tables when targeting SGD
            if cur_key == "sgd":
                if "手机银行" in text or "新存单" in text:
                    bonus += 5
                if "起存金额" in text:
                    bonus += 1
            score = (bonus, month_hits, dec_hits)
            if score > best_score:
                best_score = score
                best = t
    if best is None:
        return {}

    # If the chosen table doesn't even mention the target currency, don't guess.
    best_text_all = best.get_text(" ", strip=True).lower()
    wanted_markers = [m.lower() for m in currency_markers.get(cur_key, [])]
    if wanted_markers and not any(m in best_text_all for m in wanted_markers):
        return {}

    # Parse rows: keep current currency section; for each tenor, choose smallest amount threshold found.
    out_rate: Dict[str, float] = {}
    out_amt: Dict[str, int] = {}
    current_currency: Optional[str] = None
    for tr in best.find_all("tr"):
        tds = tr.find_all(["td", "th"])
        if not tds:
            continue
        cells = [td.get_text(" ", strip=True) for td in tds]
        row_text = " ".join(cells)

        cur = detect_currency(row_text)
        if cur:
            current_currency = cur

        # Require entering the desired currency section first.
        # If we never detect any currency marker, we fall back to parsing everything (last resort).
        if current_currency is None:
            if cur is None:
                continue
            if cur != cur_key:
                continue
            current_currency = cur

        if current_currency != cur_key:
            continue

        m_month = re.search(r"(\d+)\s*个?月", row_text)
        if not m_month:
            continue
        month = int(m_month.group(1))
        tenor = TENOR_MONTHS_TO_LABEL.get(month)
        if not tenor:
            continue

        # amount threshold (choose minimal if multiple). Common in BOC table: 500, 10,000, 200,000
        amt_candidates: List[int] = []
        for m in re.findall(r"(\d[\d,]{0,9})", row_text):
            try:
                amt_candidates.append(int(m.replace(",", "")))
            except Exception:
                pass
        amt = min(amt_candidates) if amt_candidates else 0

        # rate candidates: prefer decimal near end
        rate_candidates: List[float] = []
        for m in re.findall(r"([-+]?\d+(?:\.\d+)?)[ ]*[eE]([-+]?\d+)", row_text):
            base = float(m[0])
            exp = int(m[1])
            rate_candidates.append(base * (10 ** exp))
        for m in re.findall(r"([-+]?\d+\.\d+)", row_text):
            v = _parse_percentish_rate(m)
            if v is not None:
                rate_candidates.append(v)
        if not rate_candidates:
            continue
        rate = float(rate_candidates[-1])

        # keep minimal amount for same tenor; if no amount present, allow overwrite only if empty
        if tenor not in out_rate:
            out_rate[tenor] = rate
            out_amt[tenor] = amt
        else:
            prev_amt = out_amt.get(tenor, 0)
            if prev_amt == 0 and amt > 0:
                out_rate[tenor] = rate
                out_amt[tenor] = amt
            elif amt > 0 and (prev_amt == 0 or amt < prev_amt):
                out_rate[tenor] = rate
                out_amt[tenor] = amt
    return out_rate


def _extract_tenor_label_from_text(s: str) -> Optional[str]:
    s = s or ""
    # e.g. "1M", "3 M", "12M"
    m = re.search(r"\b([1-9]|1[0-9]|2[0-4])\s*M\b", s.upper())
    if m:
        mnum = int(m.group(1))
        return TENOR_MONTHS_TO_LABEL.get(mnum)
    # e.g. "1个月"
    m2 = re.search(r"(\d+)\s*个?月", s)
    if m2:
        mnum = int(m2.group(1))
        return TENOR_MONTHS_TO_LABEL.get(mnum)
    return None


def parse_generic_table_rates(html: str) -> Dict[str, float]:
    """
    Best-effort generic parser:
      - find a table whose text contains tenor patterns (e.g., '1M' or 'X个月')
      - scan rows for tenor+rate
    """
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")
    for t in tables:
        text = t.get_text(" ", strip=True)
        if not (re.search(r"\b1\s*M\b", text, flags=re.I) or re.search(r"\d+\s*个?月", text)):
            continue

        found: Dict[str, float] = {}
        for tr in t.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if not cells:
                continue
            cell_texts = [c.get_text(" ", strip=True) for c in cells]
            joined = " ".join(cell_texts)
            tenor = _extract_tenor_label_from_text(joined)
            if not tenor:
                continue

            # heuristic: rate is the first number-decimal/percent in the row
            rate = None
            # % forms
            m_pct = re.search(r"([-+]?\d+(?:\.\d+)?)\s*%", joined)
            if m_pct:
                rate = _parse_percentish_rate(m_pct.group(1) + "%")
            else:
                m_dec = re.findall(r"([-+]?\d+\.\d+)", joined)
                if m_dec:
                    rate = _parse_percentish_rate(m_dec[-1])
            if rate is not None:
                found[tenor] = float(rate)
        if found:
            return found
    return {}


@dataclass
class LinkEntry:
    bank: str
    currency: str
    rate_kind: str  # Promo/Board/others...
    url: str


def load_link_entries(link_xlsx: str) -> List[LinkEntry]:
    import pandas as pd  # local import; users run in their environment

    xls = pd.ExcelFile(link_xlsx)
    entries: List[LinkEntry] = []

    for sheet in xls.sheet_names:
        df = pd.read_excel(link_xlsx, sheet_name=sheet)
        if df.empty:
            continue

        # Normalize column names
        colmap = {_norm_header(c): c for c in df.columns}
        needed = ["bank", "currency", "promo/boardrate", "website"]
        # promo col could be "promo/board rate" or similar; we do fuzzy by contains.
        col_bank = colmap.get("bank")
        col_currency = colmap.get("currency")
        col_website = colmap.get("website")

        # promo/board col: any column containing 'promo' or 'board'
        promo_col = None
        for k, orig in colmap.items():
            if "promo" in k or "board" in k:
                promo_col = orig
                break
        if promo_col is None:
            # fallback: any column containing 'rate'
            for k, orig in colmap.items():
                if "rate" in k:
                    promo_col = orig
                    break

        # If standard headers not present, try to parse as a simple 2-col url list sheet:
        # e.g. first row is title, then rows: Bank | URL
        if not (col_bank and col_website):
            df2 = pd.read_excel(link_xlsx, sheet_name=sheet, header=None)
            if df2.shape[1] >= 2:
                for _, r in df2.iterrows():
                    b = r.iloc[0]
                    u = r.iloc[1]
                    if pd.isna(b) or pd.isna(u):
                        continue
                    b = str(b).strip()
                    u = str(u).strip()
                    if not b or "http" not in u:
                        continue
                    entries.append(LinkEntry(bank=b, currency=sheet, rate_kind="", url=u))
            continue

        if not (col_bank and col_currency and col_website and promo_col):
            # Some sheets may only have Website+Bank (e.g. only url list with headers missing parts)
            possible_website = colmap.get("website") or colmap.get("url")
            if not possible_website:
                possible_website = col_website
            promo_col = promo_col or col_currency or col_bank
            col_currency = col_currency or "Currency"
            col_website = possible_website

        # forward-fill bank/currency/kind to handle merged/blank cells
        for c in [col_bank, col_currency, promo_col]:
            if c in df.columns:
                df[c] = df[c].ffill()

        for _, row in df.iterrows():
            bank = str(row.get(col_bank, "")).strip()
            url = str(row.get(col_website, "")).strip()
            if not bank or bank.lower() == "nan" or not url or url.lower() == "nan":
                continue
            if "http" not in url:
                continue
            # skip directory-like urls that don't end with .html (unless needed)
            if url.endswith("/") and not url.endswith(".html"):
                continue
            currency = str(row.get(col_currency, "")).strip() if col_currency in df.columns else ""
            kind = str(row.get(promo_col, "")).strip() if promo_col in df.columns else ""
            entries.append(LinkEntry(bank=bank, currency=currency, rate_kind=kind, url=url))

    # de-duplicate by (bank,currency,url)
    seen = set()
    uniq: List[LinkEntry] = []
    for e in entries:
        key = (e.bank, e.currency, e.url)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    return uniq


def scrape_all(entries: List[LinkEntry], pause_s: float = 0.2) -> Dict[Tuple[str, str], Dict[str, float]]:
    """
    Returns:
      rates[(bank_lower, currency_lower)][tenor] = rate_fraction
    """
    rates: Dict[Tuple[str, str], Dict[str, float]] = {}
    pri_map: Dict[Tuple[str, str], Dict[str, int]] = {}
    for e in entries:
        bank_key = e.bank.strip().lower()
        cur_key = normalize_currency(e.currency)
        # prefer promo/mobile sources over board/others
        rk = (e.rate_kind or "").lower()
        pri = 1
        if any(x in rk for x in ["promo", "促销", "mobile", "手机", "online", "新存单"]):
            pri = 3
        elif any(x in rk for x in ["board", "挂牌"]):
            pri = 2
        # URL heuristics: many promo pages are dated news pages like .../202603/t202603xx_....html
        u = (e.url or "").lower()
        if re.search(r"/20\\d{2}(0[1-9]|1[0-2])/", u) and "t20" in u:
            # treat dated article pages as higher priority than directory/list pages
            pri = max(pri, 3)
        try:
            # BOC: for SGD prefer the dated promo article page; skip other BOC SGD URLs to avoid mixing tables
            if bank_key == "boc" and cur_key == "sgd":
                u0 = (e.url or "").lower()
                if not ("/202603/" in u0 and "t202603" in u0):
                    continue
            html = fetch_html(e.url, pause_s=pause_s)
        except Exception as ex:
            print(f"[WARN] fetch failed: {e.bank} {e.currency} {e.url} err={ex}", file=sys.stderr)
            continue

        if "bankofchina" in e.url.lower() or bank_key in {"boc", "bank of china", "中国银行"}:
            parsed = parse_boc_rates(html, currency=cur_key)
        else:
            parsed = parse_generic_table_rates(html)

        if not parsed:
            print(f"[WARN] parse empty: {e.bank} {e.currency} {e.url}", file=sys.stderr)
            continue

        key = (bank_key, cur_key)
        rates.setdefault(key, {})
        pri_map.setdefault(key, {})
        # merge; prefer already set if present? we overwrite for simplicity.
        for tenor, val in parsed.items():
            prev_pri = pri_map[key].get(tenor, -1)
            if pri >= prev_pri:
                rates[key][tenor] = val
                pri_map[key][tenor] = pri
    return rates


def write_to_market_matrix(template_xlsx: str, output_xlsx: str, rates: Dict[Tuple[str, str], Dict[str, float]]) -> None:
    """
    Update the market survey workbook cells where:
      header contains 1M/3M/... and bank row contains bank name.
    """
    import openpyxl  # type: ignore

    def sheet_currency_hint(sheet_title: str) -> str:
        t = (sheet_title or "").upper()
        for key in ["SGD", "USD", "CNY", "HKD", "AUD", "NZD", "CAD", "EUR", "GBP", "GBP"]:
            if key in t:
                return key.lower()
        return ""

    wb = openpyxl.load_workbook(template_xlsx)
    formula_ref_re = re.compile(r"^=\s*('?[^']+'?|[^!]+)!\$?([A-Z]+)\$?(\d+)\s*$")
    for ws in wb.worksheets:
        # detect a "matrix header row" that contains Bank + tenor columns
        header_row_idx = None
        bank_col_idx = None
        tenor_col: Dict[str, int] = {}

        for r_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=60), start=1):
            row_bank_col = None
            row_tenor_col: Dict[str, int] = {}
            for cell in row:
                v = cell.value
                if isinstance(v, str):
                    v_str = v.strip()
                    if v_str.lower() == "bank":
                        row_bank_col = cell.col_idx
                    v_norm = v_str.replace(" ", "").upper()
                    if v_norm in TENOR_LABELS:
                        row_tenor_col[v_norm] = cell.col_idx
                        continue
                    m = re.search(r"\b(1|3|6|9|12|18|24)MONTH", v_norm)
                    if m:
                        n = int(m.group(1))
                        tenor = TENOR_MONTHS_TO_LABEL.get(n)
                        if tenor:
                            row_tenor_col[tenor] = cell.col_idx
            if row_bank_col and len(row_tenor_col) >= 3:
                header_row_idx = r_idx
                bank_col_idx = row_bank_col
                tenor_col = row_tenor_col
                break

        if not (header_row_idx and bank_col_idx and tenor_col):
            continue

        # Build bank row map based on the detected matrix bank column only
        bank_cells: Dict[str, int] = {}
        rate_bank_keys = {bk for (bk, _cur) in rates.keys()}
        for r in range(header_row_idx + 1, min(ws.max_row, header_row_idx + 300) + 1):
            val = ws.cell(r, bank_col_idx).value
            if isinstance(val, str):
                bk = val.strip().lower()
                if bk in rate_bank_keys:
                    bank_cells[bk] = r
        sheet_cur = sheet_currency_hint(ws.title)
        for (bank_key, cur_key), tenor_vals in rates.items():
            if bank_key not in bank_cells:
                continue
            # currency matching (best-effort)
            cur_key_norm = (cur_key or "").strip().lower()
            if sheet_cur and cur_key_norm and sheet_cur != cur_key_norm:
                continue

            row_idx = bank_cells[bank_key]
            for tenor, rate in tenor_vals.items():
                col_idx = tenor_col.get(tenor)
                if not col_idx:
                    continue
                cell = ws.cell(row_idx, col_idx)
                # If it's a formula referencing another sheet, write into the referenced cell instead.
                if isinstance(cell.value, str) and cell.value.strip().startswith("=") and "!" in cell.value:
                    m = formula_ref_re.match(cell.value.strip())
                    if m:
                        sh = m.group(1)
                        col = m.group(2)
                        rnum = m.group(3)
                        if sh.startswith("'") and sh.endswith("'"):
                            sh = sh[1:-1]
                        if sh in wb.sheetnames:
                            wb[sh][f"{col}{rnum}"].value = float(rate)
                            continue
                # Otherwise overwrite directly.
                cell.value = float(rate)

    wb.save(output_xlsx)

    # also export raw scraped matrix via pandas (helps debugging & meets "pandas output to Excel")
    try:
        import pandas as pd
        rows: List[Dict[str, object]] = []
        for (bank_key, cur_key), tenor_vals in rates.items():
            for tenor, rate in tenor_vals.items():
                rows.append(
                    {
                        "bank": bank_key,
                        "currency": cur_key,
                        "tenor": tenor,
                        "rate_fraction": rate,
                    }
                )
        df = pd.DataFrame(rows)
        with pd.ExcelWriter(output_xlsx, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df.to_excel(writer, sheet_name="ScrapedRates", index=False)
    except Exception:
        # don't fail the main template write
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--link", default=None, help="利率链接.xlsx 路径（可选，未传则自动识别）")
    ap.add_argument("--rainbow", default=None, help="彩虹表 20260311.xlsx（可选，目前用于参考/扩展）")
    ap.add_argument("--market", default=None, help="202603011市场利率调研.xlsx 路径（用于输出写入矩阵）")
    ap.add_argument("--out", default=None, help="输出excel路径（可选）")
    ap.add_argument("--pause", type=float, default=0.2, help="抓取间隔秒数")
    ap.add_argument("--only-banks", default="", help="只抓取指定银行（逗号分隔，如 BOC,DBS）。为空则抓取全部")
    args = ap.parse_args()

    curdir = os.path.dirname(os.path.abspath(__file__))

    link_xlsx = args.link or _auto_find_xlsx(curdir, "link")
    market_xlsx = args.market or _auto_find_xlsx(curdir, "market")
    rainbow_xlsx = args.rainbow or _auto_find_xlsx(curdir, "rainbow")

    out_xlsx = args.out
    if not out_xlsx:
        today = _dt.date.today().strftime("%Y%m%d")
        out_xlsx = os.path.join(curdir, f"rate_output_{today}.xlsx")

    entries = load_link_entries(link_xlsx)
    if args.only_banks.strip():
        allow = {b.strip().lower() for b in args.only_banks.split(",") if b.strip()}
        entries = [e for e in entries if e.bank.strip().lower() in allow]
    print(f"Loaded {len(entries)} link entries from {os.path.basename(link_xlsx)}")

    rates = scrape_all(entries, pause_s=args.pause)
    print(f"Scraped rates banks/currencies: {len(rates)}")

    # write into market matrix
    write_to_market_matrix(market_xlsx, out_xlsx, rates)
    print(f"Saved: {out_xlsx}")


if __name__ == "__main__":
    main()

