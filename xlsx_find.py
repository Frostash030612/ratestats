import argparse
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple


NS_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
NS_SHEET = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def cell_to_row_col(cell_ref: str) -> Tuple[int, int]:
    m = re.fullmatch(r"([A-Za-z]+)(\d+)", cell_ref)
    if not m:
        raise ValueError(f"bad cell ref: {cell_ref}")
    col_letters, row_str = m.group(1).upper(), m.group(2)
    col = 0
    for ch in col_letters:
        col = col * 26 + (ord(ch) - ord("A") + 1)
    return int(row_str), col


def get_shared_strings(z: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    out: List[str] = []
    for si in root.findall(f".//{NS_SHEET}si"):
        parts = []
        for t in si.findall(f".//{NS_SHEET}t"):
            parts.append(t.text or "")
        out.append("".join(parts))
    return out


def get_workbook_sheet_map(z: zipfile.ZipFile) -> List[Tuple[str, str]]:
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels: Dict[str, str] = {}
    rels_path = "xl/_rels/workbook.xml.rels"
    if rels_path in z.namelist():
        rel_root = ET.fromstring(z.read(rels_path))
        for rel in rel_root.findall(".//" + NS_REL + "Relationship"):
            rid = rel.attrib.get("Id")
            target = rel.attrib.get("Target")
            if rid and target:
                rels[rid] = "xl/" + target.replace("\\", "/")

    out: List[Tuple[str, str]] = []
    for sh in wb.findall(f".//{NS_SHEET}sheets/{NS_SHEET}sheet"):
        name = sh.attrib.get("name")
        rid = sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        if not name or not rid:
            continue
        target = rels.get(rid)
        if target and target in z.namelist():
            out.append((name, target))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx_path")
    ap.add_argument("keyword", help="关键字：会在 sharedStrings 里匹配（包含关系）")
    args = ap.parse_args()

    xlsx_path = args.xlsx_path
    if xlsx_path.upper() in {"AUTO_RAINBOW", "AUTO_MARKET"}:
        import os

        candidates = [n for n in os.listdir(".") if n.lower().endswith(".xlsx")]
        if not candidates:
            raise FileNotFoundError("No .xlsx files found in current directory")
        if xlsx_path.upper() == "AUTO_RAINBOW":
            matched = [n for n in candidates if "20260311" in n]
        else:
            matched = [n for n in candidates if "202603011" in n]
        if not matched:
            # fall back to first/last by heuristic
            matched = [n for n in candidates if ("20260311" in n) or ("202603011" in n)]
        if not matched:
            raise FileNotFoundError(f"Auto-select failed for {xlsx_path!r}, candidates={candidates!r}")
        xlsx_path = sorted(matched, key=len)[0]

    with zipfile.ZipFile(xlsx_path, "r") as z:
        shared = get_shared_strings(z)
        matches = [i for i, s in enumerate(shared) if args.keyword in s]
        print("sharedStrings count", len(shared), "matching indices", len(matches))
        sheets = get_workbook_sheet_map(z)
        print("sheets", len(sheets))

        for sheet_name, sheet_xml in sheets:
            sheet_xml_str = z.read(sheet_xml)
            # quick filter
            if b"<v>" not in sheet_xml_str:
                continue
            root = ET.fromstring(sheet_xml_str)
            hits = []
            for c in root.findall(f".//{NS_SHEET}sheetData/{NS_SHEET}row/{NS_SHEET}c"):
                r = c.attrib.get("r")
                v = c.find(f"{NS_SHEET}v")
                t = c.attrib.get("t")
                # shared string is usually t="s"
                if t == "s" and r and v is not None and v.text and v.text.isdigit():
                    idx = int(v.text)
                    if idx in matches:
                        hits.append(r)
            if hits:
                # sort and show first 30
                hits_sorted = sorted(set(hits), key=lambda x: cell_to_row_col(x))
                print("sheet", repr(sheet_name), "hits", len(hits_sorted), "example", hits_sorted[:30])


if __name__ == "__main__":
    main()

