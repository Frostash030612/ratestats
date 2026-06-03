import re
import requests
from bs4 import BeautifulSoup


URL = "https://www.bankofchina.com/sg/cn/bocinfo/bi3/bi31/202603/t20260302_25651264.html"
DEC_RE = re.compile(r"\d+\.\d+")
INT_RE = re.compile(r"\b\d+\b")


def main() -> None:
    r = requests.get(URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    tables = soup.find_all("table")
    print("tables", len(tables), "html_len", len(r.text))

    # Candidate tables were earlier found by "decimal density"
    targets = [8]
    for ti in targets:
        if ti >= len(tables):
            print("table index out of range", ti)
            continue
        t = tables[ti]
        rows = t.find_all("tr")
        print("TABLE", ti, "tr", len(rows), "id", t.get("id"), "class", t.get("class"))
        for ri, tr in enumerate(rows[:30]):
            cells = tr.find_all(["td", "th"])
            rate_cells = []
            for c in cells:
                txt = c.get_text(" ", strip=True)
                decs = DEC_RE.findall(txt)
                if decs:
                    rate_cells.append((len(txt), decs))
            if rate_cells:
                # print row content in ASCII-safe escaped form
                row_parts = []
                for c in cells:
                    txt = c.get_text(" ", strip=True)
                    escaped = txt.encode("ascii", errors="backslashreplace").decode("ascii")
                    row_parts.append(escaped[:80])
                print("  row", ri, "rate_cells", rate_cells, "cells_ascii_esc", row_parts[:8])


if __name__ == "__main__":
    main()

