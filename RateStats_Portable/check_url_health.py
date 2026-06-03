#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""巡检 url_params.json 中的 URL 可用性并输出报告。"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, List, Tuple

import requests


RISK_HIGH_KEYS = {
    "boc_url",
    "boc_board_url",
    "rhb_board_pdf_url",
    "rhb_fcy_board_pdf_url",
}

RISK_MEDIUM_KEYS = {
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
    "cimb_url",
    "cimb_sgd_url",
}


def risk_level(key: str) -> str:
    if key in RISK_HIGH_KEYS:
        return "high"
    if key in RISK_MEDIUM_KEYS:
        return "medium"
    return "normal"


def check_one(session: requests.Session, key: str, url: str) -> Dict[str, str]:
    out: Dict[str, str] = {
        "key": key,
        "risk": risk_level(key),
        "url": url,
        "status": "ERR",
        "final_url": "",
        "note": "",
    }
    try:
        resp = session.get(url, timeout=20, allow_redirects=True)
        out["status"] = str(resp.status_code)
        out["final_url"] = resp.url
        if resp.status_code >= 400:
            out["note"] = "http_error"
        elif resp.url != url:
            out["note"] = "redirected"
    except Exception as exc:
        out["note"] = str(exc)
    return out


def summarize(results: List[Dict[str, str]]) -> Tuple[int, int, int]:
    ok = sum(1 for x in results if x["status"].isdigit() and int(x["status"]) < 400)
    warn = sum(1 for x in results if x["status"].isdigit() and int(x["status"]) >= 400)
    err = sum(1 for x in results if not x["status"].isdigit())
    return ok, warn, err


def main() -> int:
    base = os.path.dirname(os.path.abspath(__file__))
    conf = os.path.join(base, "assets", "url_params.json")
    if not os.path.exists(conf):
        print(f"[CHECK] 配置文件不存在: {conf}")
        return 1

    with open(conf, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    session = requests.Session()
    results: List[Dict[str, str]] = []
    for key in sorted(cfg.keys()):
        url = str(cfg[key] or "").strip()
        if not url.startswith("http"):
            continue
        results.append(check_one(session, key, url))

    ok, warn, err = summarize(results)
    print(f"[CHECK] total={len(results)} ok={ok} http_err={warn} exception={err}")
    print("[CHECK] ---- details ----")
    for item in results:
        print(
            f"{item['key']}: risk={item['risk']} status={item['status']} "
            f"note={item['note']} url={item['url']} final={item['final_url']}"
        )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(base, f"url_health_report_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"summary": {"total": len(results), "ok": ok, "http_err": warn, "exception": err}, "results": results}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[CHECK] report={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
