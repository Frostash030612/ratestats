import argparse
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Optional


def col_letter_to_index(col: str) -> int:
    # Excel columns: A->1, B->2, ..., Z->26, AA->27 ...
    col = col.upper()
    idx = 0
    for ch in col:
        if not ("A" <= ch <= "Z"):
            raise ValueError(f"Invalid column letter: {col!r}")
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx


def cell_to_row_col(cell_ref: str) -> Tuple[int, int]:
    m = re.fullmatch(r"([A-Za-z]+)(\d+)", cell_ref)
    if not m:
        raise ValueError(f"Invalid cell ref: {cell_ref!r}")
    col_letters, row_str = m.group(1), m.group(2)
    return int(row_str), col_letter_to_index(col_letters)


def get_shared_strings(z: zipfile.ZipFile) -> List[str]:
    try:
        raw = z.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(raw)
    out: List[str] = []
    # <si><t>text</t></si>
    for si in root.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
        # A shared string can contain multiple <t> runs.
        parts = []
        for t in si.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"):
            parts.append(t.text or "")
        out.append("".join(parts))
    return out


def get_workbook_sheets(z: zipfile.ZipFile) -> List[Tuple[str, str]]:
    # Returns list of (sheet_name, target_xml_path) like ("Sheet1", "xl/worksheets/sheet1.xml")
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels_path = "xl/_rels/workbook.xml.rels"
    rels = {}
    if rels_path in z.namelist():
        rel_root = ET.fromstring(z.read(rels_path))
        for rel in rel_root.findall(".//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
            rid = rel.attrib.get("Id")
            target = rel.attrib.get("Target")
            if rid and target:
                # target is like "worksheets/sheet1.xml"
                rels[rid] = "xl/" + target.replace("\\", "/")

    sheets: List[Tuple[str, str]] = []
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    for sh in wb.findall(".//a:sheets/a:sheet", ns):
        name = sh.attrib.get("name")
        rid = sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        if not name or not rid:
            continue
        target = rels.get(rid)
        if target and target in z.namelist():
            sheets.append((name, target))
    # Fallback: if relationships missing, try common sheet paths.
    if not sheets:
        for n in sorted([n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]):
            sheets.append((n, n))
    return sheets


def read_worksheet_as_grid(z: zipfile.ZipFile, sheet_xml_path: str, shared_strings: List[str]) -> List[List[Optional[str]]]:
    raw = z.read(sheet_xml_path)
    root = ET.fromstring(raw)
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    # Collect cells
    cells: Dict[Tuple[int, int], Optional[str]] = {}
    max_r = 0
    max_c = 0
    for c in root.findall(".//a:sheetData/a:row/a:c", ns):
        r = c.attrib.get("r")
        if not r:
            continue
        row, col = cell_to_row_col(r)
        max_r = max(max_r, row)
        max_c = max(max_c, col)
        t = c.attrib.get("t")
        v = c.find("a:v", ns)
        if v is None:
            is_ = c.find("a:is", ns)
            if is_ is not None:
                t_node = is_.find("a:t", ns)
                cells[(row, col)] = (t_node.text if t_node is not None else "")
            else:
                cells[(row, col)] = None
            continue
        raw_val = v.text or ""
        if t == "s":
            idx = int(raw_val) if raw_val.strip() else 0
            cells[(row, col)] = shared_strings[idx] if idx < len(shared_strings) else ""
        elif t in (None, ""):
            # number
            cells[(row, col)] = raw_val
        elif t in ("inlineStr", "str"):
            # unlikely here (inlineStr usually handled elsewhere)
            cells[(row, col)] = raw_val
        else:
            cells[(row, col)] = raw_val

    grid: List[List[Optional[str]]] = [[None for _ in range(max_c)] for _ in range(max_r)]
    for (row, col), val in cells.items():
        grid[row - 1][col - 1] = val
    return grid


def print_preview(grid: List[List[Optional[str]]], max_rows: int = 25, max_cols: int = 30) -> None:
    if not grid:
        print("(empty)")
        return
    rows = min(len(grid), max_rows)
    cols = min(max(len(r) for r in grid), max_cols)
    for i in range(rows):
        row = grid[i][:cols]
        out = []
        for v in row:
            out.append("" if v is None else str(v))
        print(f"R{i+1}:\t" + "\t".join(out))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx_path", help="xlsx路径，或使用 AUTO_RAINBOW/AUTO_MARKET/AUTO_LINK 自动选择文件")
    ap.add_argument("--sheet", default=None, help="sheet name or index (0-based)")
    args = ap.parse_args()

    xlsx_path = args.xlsx_path
    if xlsx_path.upper() in {"AUTO_RAINBOW", "AUTO_MARKET", "AUTO_LINK"}:
        candidates = [n for n in __import__("os").listdir(".") if n.lower().endswith(".xlsx")]
        if not candidates:
            raise FileNotFoundError("No .xlsx files found in current directory")
        if xlsx_path.upper() == "AUTO_RAINBOW":
            matched = [n for n in candidates if "20260311" in n]
        elif xlsx_path.upper() == "AUTO_MARKET":
            matched = [n for n in candidates if "202603011" in n]
        else:
            rainbow = [n for n in candidates if "20260311" in n]
            market = [n for n in candidates if "202603011" in n]
            matched = [n for n in candidates if n not in set(rainbow + market)]
        if not matched:
            raise FileNotFoundError(f"Auto-select failed for {xlsx_path!r}, candidates={candidates!r}")
        if len(matched) > 1:
            # pick the shortest name to reduce ambiguity
            matched.sort(key=len)
        xlsx_path = matched[0]

    with zipfile.ZipFile(xlsx_path, "r") as z:
        shared = get_shared_strings(z)
        sheets = get_workbook_sheets(z)
        print("Sheets:")
        for i, (name, path) in enumerate(sheets):
            print(f"  [{i}] {name} -> {path}")

        if not sheets:
            raise RuntimeError("No sheets found")

        target: Tuple[str, str]
        if args.sheet is None:
            target = sheets[0]
        else:
            if args.sheet.isdigit():
                target = sheets[int(args.sheet)]
            else:
                found = [s for s in sheets if s[0] == args.sheet]
                if not found:
                    raise RuntimeError(f"Sheet {args.sheet!r} not found")
                target = found[0]

        name, path = target
        print(f"\nPreview sheet: {name!r} ({path})")
        grid = read_worksheet_as_grid(z, path, shared)
        print_preview(grid)


if __name__ == "__main__":
    main()

