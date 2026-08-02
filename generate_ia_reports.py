#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate Project Summary Report and Final Project Report (docx)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "docs" / "IA_Reports"
OUT_DIR.mkdir(parents=True, exist_ok=True)

STUDENT_NAME = "Xu Wenzhe"
COMPANY = "Bank of China Singapore Branch"
NUS_ADVISOR = "[NUS-ISS Advisor Name]"
SUPERVISOR = "[Internship Supervisor Name]"
CONTACT = "[Your Contact Number]"
PRESENTATION_SLOT = "[MMDD_HHMM – to be announced]"
PROJECT_TITLE = "RateStats – Market Rate Automation (Python → AI Search) | Bank of China Singapore"


def _shade_paragraph(paragraph, fill: str = "F2F2F2") -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    p_pr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill}"/>'))


def _h(doc: Document, text: str, level: int = 1) -> None:
    doc.add_heading(text, level=level)


def _p(doc: Document, text: str, *, bold: bool = False) -> None:
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.font.size = Pt(11)
    if bold:
        run.bold = True


def _bullet(doc: Document, items: list[str]) -> None:
    for item in items:
        para = doc.add_paragraph(item, style="List Bullet")
        for run in para.runs:
            run.font.size = Pt(11)


def _code(doc: Document, text: str) -> None:
    para = doc.add_paragraph()
    run = para.add_run(text.rstrip("\n"))
    run.font.name = "Consolas"
    run.font.size = Pt(9)
    _shade_paragraph(para)


def _table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.style = "Table Grid"
    for j, h in enumerate(headers):
        cell = t.rows[0].cells[j]
        cell.text = h
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.size = Pt(9)
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            t.rows[i + 1].cells[j].text = str(cell)
            for run in t.rows[i + 1].cells[j].paragraphs[0].runs:
                run.font.size = Pt(9)


def _cover_block(doc: Document, title: str, subtitle: str, extra_lines: list[str]) -> None:
    for line in extra_lines:
        para = doc.add_paragraph()
        run = para.add_run(line)
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00) if "Presentation" in line or "Contact" in line else None
    doc.add_paragraph()
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run(title)
    r.bold = True
    r.font.size = Pt(20)
    doc.add_paragraph()
    s = doc.add_paragraph()
    s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rs = s.add_run(subtitle)
    rs.font.size = Pt(14)
    doc.add_paragraph()
    meta = [
        f"Student: {STUDENT_NAME}",
        f"Company: {COMPANY}",
        f"Programme: NUS-ISS Diploma in Infocomm Technology (Industrial Attachment)",
        f"Date: {datetime.now().strftime('%d %B %Y')}",
    ]
    for m in meta:
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(m)
        run.font.size = Pt(11)
    doc.add_page_break()


# ---------------------------------------------------------------------------
# Code snippets (from repository)
# ---------------------------------------------------------------------------

# --- 5.1 ICBC → HLF: domain whitelist (url_host_rules.py) ---
CODE_ICBC_HLF_WHITELIST = '''# url_host_rules.py — per-dest allowed host fragments
# (hlf must be listed before hl so "hlf_" is not matched as "hl_")
_PREFIX_HOST_RULES: list[tuple[str, tuple[str, ...]]] = [
    ...
    ("icbc_", ("singapore.icbc.com.cn",)),   # icbc_url, icbc_sgd_board_url, ...
    ...
    ("hlf_", ("hlf.com.sg",)),                # hlf_url, hlf_sgd_board_url, ...
    ("hl_", ("hlbank.com.sg",)),              # hl_url — different bank from HLF
    ...
    ("icbc", ("singapore.icbc.com.cn",)),
    ("hlf", ("hlf.com.sg",)),
    ...
]'''

CODE_HOST_FRAGMENTS = '''def host_fragments_for_dest(dest: str) -> tuple[str, ...]:
    """Return allowed domain fragments for this dest."""
    if dest in _DEST_HOST_OVERRIDE:
        return _DEST_HOST_OVERRIDE[dest]
    for prefix, frags in _PREFIX_HOST_RULES:
        if dest.startswith(prefix) or dest == prefix.rstrip("_"):
            return frags
    return ()'''

CODE_URL_MATCHES_DEST = '''def url_matches_dest(dest: str, url: str) -> bool:
    """Whether URL host/path belongs to the bank for this dest."""
    if not url or not str(url).startswith("http"):
        return False
    frags = host_fragments_for_dest(dest)
    if not frags:
        return True

    p = urlparse(url)
    host = (p.netloc or "").lower()
    path = (p.path or "").lower()

    # <<< ICBC → HLF fix: for dest="icbc_url", frags=("singapore.icbc.com.cn",)
    # hlf.com.sg fails here and returns False immediately.
    if not any(f in host for f in frags):
        return False

    # Extra path guards for OTHER banks (not related to ICBC/HLF case):
    if "bankofchina.com" in host and dest.startswith("boc"):
        if "/sg/" not in path:
            return False

    if "sc.com" in host and dest.startswith("scb"):
        if "/sg/" not in path:
            return False

    return True'''

CODE_PICK_ON_BANK_FILTER = '''# url_discovery_pick.py — pick_best_url()
unique = list(dict.fromkeys(candidates))
ranked = sorted(
    ((u, score_url(u, dest, reference_url=fallback)) for u in unique),
    key=lambda x: (-x[1], x[0]),
)

on_bank = [(u, s) for u, s in ranked if url_matches_dest(dest, u)]
if on_bank:
    ranked = on_bank
elif fallback and url_matches_dest(dest, fallback):
    return fallback, "fallback_no_bank_host_in_results"'''

CODE_SCORE_PENALTY = '''# url_discovery_pick.py — score_url()
if host_fragments_for_dest(dest):
    if url_matches_dest(dest, url):
        score += 25
    else:
        score -= 120   # wrong-bank candidate heavily penalised'''

# --- 5.2 OCBC Premier vs board page ---
CODE_HARD_REJECT = '''def url_hard_reject(dest: str, url: str) -> bool:
    """Hard-reject obvious wrong pages even in relaxed mode."""
    if not url or not str(url).startswith("http"):
        return True
    low = url.lower()
    for frag in _HARD_REJECT.get(dest, ()):
        if frag.lower() in low:
            return True
    if dest == "dbs_fcy_board_api_url":
        if is_dbs_fcy_board_api_url(url):
            return False
        if "dbs.com.sg" in low or "dbs.com" in low:
            return True
    if dest in ("rhb_board_pdf_url", "rhb_fcy_board_pdf_url"):
        if is_rhb_deposit_rates_board_pdf(url):
            return False
        if _rhb_host_ok(urlparse(low).netloc or "") or "rhbgroup.com" in low:
            return True
    if dest == "boc_url":
        if is_boc_promo_rate_page(url):
            return False
        if _boc_host_ok(urlparse(low).netloc or "") and "bocinfo/bi3" in low:
            return True
    if dest == "boc_board_url":
        if is_boc_board_rate_page(url):
            return False
        if _boc_host_ok(urlparse(low).netloc or "") and "bocinfo/bi3" in low:
            return True
    if dest == "ocbc_board_url":
        if "fixed-deposit-account" in low and "fixed-deposit-sgd-interest" not in low:
            return True
        if "time-deposit" in low and not is_ocbc_sgd_board_page(url):
            return True
    return False'''

CODE_OCBC_VALID_BOARD = '''def is_ocbc_sgd_board_page(url: str) -> bool:
    """OCBC SGD board: personal fixed-deposit-sgd-interest (not business/premier)."""
    low = (url or "").lower()
    if not low.startswith("http"):
        return False
    if any(
        x in low
        for x in ("business-banking", "corporate-banking", "sme-and-corporate", "premier-banking")
    ):
        return False
    if "fixed-deposit-sgd-interest" in low:
        return True
    if "personal-banking" in low and "sgd-fixed-deposit-interest" in low:
        return True
    return False'''

CODE_ML_PICK = '''def pick_best_url_ml(candidates, dest, fallback, ...):
    rule_scores = [score_url(u, dest, reference_url=fallback) for u in pool]
    margin = _rule_margin(pool, rule_scores)
    if cfg.use_ambiguous_gate and margin >= cfg.ambiguous_rule_margin:
        return pick_best_url(candidates, dest, fallback)  # clear winner
    for rank, (u, rs) in enumerate(zip(pool, rule_scores)):
        if url_hard_reject(dest, u):
            continue
        ml_p = ml_score(u, dest, reference_url=fallback, candidate_rank=rank)
        rule_norm = (rs - r_min) / r_span
        combined = blend * rule_norm + (1.0 - blend) * ml_p
        scored.append((u, combined, ml_p))
    if best_ml < min_p and fallback:
        return fallback, "ml_low_confidence_fallback"
    return best_url, "ml_pick"'''

CODE_FEATURES = '''FEATURE_NAMES: tuple[str, ...] = (
    "rule_score",
    "path_rule_adj",
    "intent_rule_adj",
    "hard_reject_flag",
    "matches_dest",
    "same_host_as_ref",
    "path_jaccard_ref",
    "path_prefix_match_ref",
    "dest_is_board",
    "dest_is_promo",
    "dest_is_api",
    "dest_is_pdf",
    "url_has_api_hint",
    "url_has_pdf",
    "url_has_promo_kw",
    "url_has_board_kw",
    "pat_premier_banking",
    "pat_business_banking",
    "pat_fixed_deposit_sgd",
    "pat_sgd_fd_business",
    "pat_sg_rates_api",
    "pat_treasury_api",
    "pat_fd_account_only",
    "pat_ocbc_valid_board",
    "pat_dbs_fcy_api_valid",
    "pat_rhb_board_pdf_valid",
    "pat_boc_promo_valid",
    "pat_boc_board_valid",
    "path_depth",
    "candidate_rank",
    "url_len",
)'''

CODE_CHECK_URL = '''def check_one(session, key, url):
    resp = session.get(url, timeout=20, allow_redirects=True)
    out["status"] = str(resp.status_code)
    out["final_url"] = resp.url
    if resp.status_code >= 400:
        out["note"] = "http_error"
    elif resp.url != url:
        out["note"] = "redirected"
    return out'''

CODE_TUNING = '''{
  "blend_rule_weight": 0.15,
  "min_ml_proba": 0.12,
  "use_ambiguous_gate": true,
  "ambiguous_rule_margin": 0.12
}'''

STATUS_ROWS = [
    ["Python extraction engine (HTML / PDF / API) [built first]", "bank_fetch_and_extract.py, bank_extractors/", "C", "C", "C", "C", "C"],
    ["Excel Report Generation (MarketRateData + Rainbow)", "Python, openpyxl", "C", "C", "C", "C", "C"],
    ["Automated Batch Pipeline & Scheduling", "Batch scripts, Windows Task Scheduler, runs/YYYYMMDD/", "C", "C", "C", "C", "C"],
    ["URL Health Monitoring", "check_url_health.py", "C", "C", "C", "C", "C"],
    ["AI URL Discovery (Vertex) [added into existing flow]", "Python, Vertex AI API, vertex_url_discovery.py", "C", "C", "C", "C", "C"],
    ["Rule-Based URL Scoring & Host Validation", "url_host_rules.py, url_discovery_pick.py", "C", "C", "C", "C", "C"],
    ["Multi-AI Benchmarking (Serper / Brave / Tavily)", "AI_Compare/run_all_providers_market.py", "C", "C", "C", "C", "C"],
    ["ML URL Ranker (hybrid picker, 31 features)", "RateStats_ML/picker.py, features.py, scikit-learn", "C", "C", "C", "C", "I"],
]

STATUS_ROWS_SUMMARY = STATUS_ROWS + [
    ["RPA bots for fixed office workflows (secondary stream)", "Python / bank-approved RPA stack", "C", "C", "C", "C", "C"],
]

APPENDIX_A = [
    "RateStats_Portable/ – main portable pipeline (Python extract + later AI discovery + Excel)",
    "RateStats_Portable/bank_fetch_and_extract.py – unified fetch and parse entry point [foundation]",
    "RateStats_Portable/bank_extractors/impl.py – bank-specific HTML/PDF/API parsers [foundation]",
    "RateStats_Portable/vertex_url_discovery.py – Vertex AI Search URL discovery [AI extension]",
    "RateStats_Portable/url_host_rules.py – per-bank domain whitelist constraints",
    "RateStats_Portable/url_discovery_pick.py – rule-based URL scoring and selection",
    "RateStats_Portable/check_url_health.py – automated URL health inspection",
    "RateStats_ML/ – ML URL ranker training, tuning, and evaluation module",
    "RateStats_ML/models/url_ranker.joblib – trained HistGradientBoostingClassifier",
    "RateStats_ML/models/picker_tuning.json – Grid Search fusion weights",
    "RateStats_ML/data/hard_negatives.csv – curated wrong-link negative samples",
    "RateStats_ML/docs/RateStats_ML选链流程说明.docx – ML workflow documentation",
    "AI_Compare/ – horizontal benchmarking across Vertex, Serper, Brave, Tavily",
    "runs/20260603/, runs/20260604/, … – dated batch outputs (MarketRateData, compare reports)",
    "RateStats_Portable/assets/url_params.xlsx – golden manual URL reference",
    "RateStats_Portable/assets/ai_search_discovered_*.xlsx – AI discovery audit trails",
    "RPA automation scripts / bots for bank-approved fixed workflows (details withheld for confidentiality)",
]

APPENDIX_B = [
    "Week 9 Report_Xu Wenzhe.docx",
    "Week 9 Report_Xu Wenzhe (revised).docx",
    "Week 10 Report_Xu Wenzhe.docx",
    "Week 11 Report_Xu Wenzhe.docx",
    "Week 15 report_Xu Wenzhe.docx",
    "[Project Plan – attach if provided separately]",
]


def build_project_summary_report() -> Path:
    doc = Document()
    _cover_block(
        doc,
        "Project Summary Report",
        PROJECT_TITLE,
        [
            f"Presentation Slot: {PRESENTATION_SLOT}",
            "(Place date and time slot at the top of the cover page as required)",
        ],
    )

    _note_para = doc.add_paragraph()
    nr = _note_para.add_run(
        "Note for reviewers: This summary focuses on RateStats — the project where I spent "
        "the most development effort. A secondary RPA workstream is mentioned briefly; "
        "full detail is in the Final Project Report."
    )
    nr.italic = True
    nr.font.size = Pt(10)

    _h(doc, "1. Project Background", 1)
    _p(
        doc,
        "Host organisation: Bank of China Singapore Branch, Financial Technology department. "
        "RateStats addresses the collection of Singapore bank deposit and promotional interest "
        "rates across about 17 banks (≈ 47 destination keys such as CIMB, DBS, OCBC, HSBC, UOB) "
        "for internal market comparison reports (MarketRateData and Rainbow Table Excel).",
    )
    _p(doc, "How the project evolved (not “AI-first”):", bold=True)
    _bullet(
        doc,
        [
            "Stage 0 — Fully manual: staff opened bank websites, copied rates, and maintained Excel by hand.",
            "Stage 1 — Python application I built: fetch pages, parse HTML / PDF / API, generate "
            "MarketRateData and Rainbow Excel. URLs were still fed manually via url_params.xlsx, "
            "so bank site redesigns still broke runs when links went stale.",
            "Stage 2 — AI Search plugged into that same pipeline: discover candidate URLs → "
            "validate with rules + ML → reuse the existing Python extractors and Excel outputs.",
        ],
    )
    _p(
        doc,
        "Because this is a bank environment, AI is used in a controlled way (search and scoring), "
        "not as unrestricted cloud LLM agents on sensitive operational steps.",
    )

    _h(doc, "2. Business Value", 1)
    _bullet(
        doc,
        [
            "Manpower: Stage 1 already removed most hand-copying of rate numbers; Stage 2 reduced "
            "remaining manual URL hunting and inspection across ~47 nodes.",
            "Reliability: scheduled batch runs with fallback URLs and health checks → fewer silent "
            "missing rows in market-rate Excel.",
            "Accuracy: hybrid rules + ML URL picker ≈ 95% hit rate on evaluation discovery reports.",
            "Decision support: four-provider benchmark (Vertex / Serper / Brave / Tavily) gave "
            "evidence to prefer Vertex for this use case.",
            "Security fit: useful automation without sending sensitive bank processes to external agents.",
        ],
    )

    _h(doc, "3. Major Features Developed or Delivered", 1)
    _p(doc, "A. Python foundation (built first)", bold=True)
    _bullet(
        doc,
        [
            "Multi-source extraction: HTML DOM, cell-level PDF (e.g. HSBC / RHB), JSON APIs "
            "(e.g. DBS / BEA) via bank_fetch_and_extract.py and bank_extractors/.",
            "Standard Excel outputs: MarketRateData and Rainbow Table under dated runs/YYYYMMDD/.",
            "Operations: URL health inspection (check_url_health.py), email notification, "
            "Windows Task Scheduler packaging.",
        ],
    )
    _p(doc, "B. AI Search extension (added into the existing flow)", bold=True)
    _bullet(
        doc,
        [
            "Discovery: Vertex AI Search (vertex_url_discovery.py) to propose candidate URLs per dest.",
            "Smart scoring: domain whitelist (url_host_rules.py), intent / hard-reject rules, "
            "and ML re-ranking (RateStats_ML/picker.py, 31 features, 6,207 training samples).",
            "Benchmarking: AI_Compare module across Vertex, Serper, Brave, Tavily.",
        ],
    )
    _p(doc, "C. Secondary stream (brief)", bold=True)
    _bullet(
        doc,
        [
            "RPA bots for fixed office workflows (download / Excel / hand-off) under bank-approved "
            "platforms. Details are confidential; see Final Project Report.",
        ],
    )

    _h(doc, "4. Project Status", 1)
    _p(doc, "Legend: C = Completed, I = In Progress (started, in progress).", bold=True)
    _p(
        doc,
        "Rows are ordered to reflect build order: Python extract/output first, then AI discovery "
        "and scoring layered on top.",
    )
    _table(
        doc,
        [
            "Feature / Use Case",
            "Implementation Technologies",
            "Req & Design",
            "Development",
            "Integration",
            "UAT",
            "Production",
        ],
        STATUS_ROWS_SUMMARY,
    )

    _h(doc, "5. Benefits Derived by the Organization", 1)
    _p(
        doc,
        "The organisation moved market-rate collection from a fully manual activity to a "
        "schedulable Python application, and then reduced remaining URL-maintenance labour "
        "by adding AI Search with hybrid validation. Weekly (or scheduled) runs produce "
        "timestamped Excel under runs/ with less developer intervention. Edge cases "
        "(e.g. RHB PDF, BOC dynamic directories) are handled by fallbacks and curated "
        "hard-negative samples rather than full manual re-inspection of all banks.",
    )
    _p(
        doc,
        "The multi-AI benchmarking exercise provided evidence-based justification for "
        "adopting Vertex AI Search as the primary discovery engine. Overall, RateStats "
        "demonstrates a practical path: build a working Python product first, then extend "
        "it with controlled AI under banking security constraints.",
    )

    out = OUT_DIR / "Project_Summary_Report_Xu_Wenzhe.docx"
    doc.save(out)
    return out


def build_final_project_report() -> Path:
    doc = Document()
    _cover_block(
        doc,
        "Final Project Report",
        PROJECT_TITLE,
        [
            f"Contact Number: {CONTACT}",
            "(Provide your contact number on the project report cover as required)",
        ],
    )

    # --- 1 Introduction ---
    _h(doc, "1. Introduction", 1)
    _h(doc, "1.1 Project Background", 2)
    _p(
        doc,
        "I completed my industrial attachment in the Financial Technology department at "
        "Bank of China Singapore Branch. The department supports digital operations and "
        "exploratory automation for business units. My assignment covered two workstreams: "
        "RateStats (primary development effort for this attachment) and Robotic Process "
        "Automation (RPA) for internal fixed workflows.",
    )
    _p(
        doc,
        "RateStats collects Singapore bank deposit and promotional interest rates across "
        "about 17 banks and approximately 47 destination keys (promotional pages, board-rate "
        "pages, PDF documents, or JSON APIs). The project did not start as an “AI system”. "
        "It evolved in three stages:",
    )
    _bullet(
        doc,
        [
            "Fully manual collection: staff opened bank sites, copied rates, and maintained Excel by hand.",
            "Python application: I built fetch / parse / Excel generation (MarketRateData and "
            "Rainbow Table). URLs were still configured manually in url_params.xlsx / "
            "url_params.json — fragile when banks redesigned pages.",
            "AI Search extension: Vertex AI Search (and provider benchmarks) was plugged into "
            "the same pipeline to discover and validate URLs, then reuse the existing Python "
            "extractors. Hybrid rules + ML keep wrong candidates out.",
        ],
    )
    _p(
        doc,
        "RPA is a separate workstream for repetitive internal steps (download files, update "
        "Excel, hand off to the next process). In a regulated bank these steps must stay "
        "auditable and must not freely use external generative-AI agents. Production RPA "
        "details are confidential; this report describes responsibilities at a high level.",
    )

    _h(doc, "1.2 Objectives", 2)
    _p(doc, "Company's point of view:", bold=True)
    _bullet(
        doc,
        [
            "Replace hand-copying of market rates with a reliable Python extraction and Excel pipeline.",
            "Reduce remaining manual URL maintenance when bank websites change.",
            "Explore AI in a controlled way (search + scoring) that respects banking security.",
            "Reduce manual effort on repetitive operational workflows via RPA.",
            "Establish an auditable, schedulable pipeline for standard market-rate reports.",
        ],
    )
    _p(doc, "Intern's point of view:", bold=True)
    _bullet(
        doc,
        [
            "Build a usable Python product first (parsers + Excel), not only a research prototype.",
            "Extend that product with AI URL discovery and hybrid validation.",
            "Build a hybrid rule-plus-ML URL selection model for ambiguous search results.",
            "Deliver production-grade engineering: logging, fallback, health checks, and deployment.",
            "Design and implement RPA scripts for bank-approved fixed processes.",
        ],
    )

    # --- 2 Overview ---
    _h(doc, "2. Overview of Activities", 1)
    _p(
        doc,
        "The following is a high-level summary of both workstreams, deliverables, and my "
        "personal involvement. RateStats is presented first because it was the primary "
        "engineering focus for demonstration and reporting. Detailed weekly logs for "
        "RateStats phases are listed in Appendix B. RPA production artefacts are omitted "
        "for confidentiality.",
    )

    _h(doc, "2.1 Workstream A — RateStats (Primary): Manual → Python → AI Search", 2)
    _p(
        doc,
        "I owned the full development cycle. First I turned the manual rate-collection job "
        "into a Python application: bank-specific extractors and Excel generation that "
        "business users can run. Then I added AI Search into that existing flow so URLs "
        "no longer had to be hand-fed for every destination.",
    )
    _table(
        doc,
        ["Phase", "Period", "Deliverables", "My Role & Effort"],
        [
            [
                "Python extraction & Excel (foundation)",
                "Week 9–10",
                "bank_extractors/impl.py; fetch_and_extract; daily output folders; health check; email",
                "Primary developer: HSBC PDF, UOB dynamic tables, Maybank/SCB/RHB FCY parsing; "
                "MarketRateData + Rainbow outputs",
            ],
            [
                "AI Search integrated into the same pipeline",
                "Week 11–13",
                "vertex_url_discovery.py; url_params_ai.xlsx; rule-based pick_best_url",
                "Primary developer: Vertex integration; domain rules and intent scoring on top of "
                "existing extractors",
            ],
            [
                "ML optimisation & benchmarking",
                "Week 14–15",
                "RateStats_ML module; picker_tuning.json; AI_Compare reports",
                "Primary developer: 31-feature ranker, hard negatives, Grid Search tuning; "
                "four-provider benchmark",
            ],
            [
                "Deployment & operations",
                "Week 15+",
                "Scheduled pipeline; runs/ structure; portable packaging",
                "Primary developer: batch scripts, Task Scheduler, GitHub backup",
            ],
        ],
    )

    _h(doc, "2.2 Workstream B — Robotic Process Automation (RPA)", 2)
    _p(
        doc,
        "RPA uses software robots and scripts to execute a fixed business process end to end. "
        "Typical tasks I automated include downloading files from designated websites or "
        "portals, renaming and organising artefacts, updating Excel workbooks for the next "
        "operational step, and completing hand-offs between teams.",
    )
    _p(
        doc,
        "Although individual steps can look simple, RPA is strategically important in banking. "
        "Security and compliance requirements mean the bank cannot freely outsource such "
        "operations to external AI cloud agents. RPA runs on approved infrastructure, produces "
        "auditable step logs, and has a mature operational model. By absorbing repetitive work, "
        "it frees staff time for exception handling and higher-value analysis.",
    )
    _p(
        doc,
        "My role was developer: receive process requirements from operations teams, implement "
        "and debug the automation, validate outputs with stakeholders, and hand over runnable "
        "bots/scripts. Because of confidentiality, this report does not include screenshots, "
        "credentials, or full process diagrams of production robots.",
    )
    _table(
        doc,
        ["Aspect", "Description"],
        [
            ["Scope", "Fixed, repeatable office workflows (download / Excel transform / hand-off)"],
            ["My role", "Primary developer of RPA scripts/bots for assigned processes"],
            ["Constraints", "Bank security — no external LLM agents on sensitive steps"],
            ["Status", "Delivered into production use (Completed)"],
            ["Evidence", "Sanitized demo GIF for presentation only; prod details withheld"],
        ],
    )

    _h(doc, "2.3 Personal Contribution Summary", 2)
    _p(
        doc,
        "Across both workstreams I was the primary developer. For RateStats, I first delivered "
        "a working Python product (parsers + Excel), then plugged AI Search and hybrid "
        "validation into that real pipeline; trained and evaluated the ML ranker on 6,207 "
        "labelled samples; produced weekly progress reports; and set up automated scheduling. "
        "For RPA, I implemented assigned automation bots for operational teams under bank "
        "security guidelines.",
    )

    _h(doc, "3. Recommendations", 1)
    _h(doc, "3.1 Short-Term", 2)
    _bullet(
        doc,
        [
            "RateStats: Continue appending mis-discovered URLs to RateStats_ML/data/hard_negatives.csv "
            "for challenging targets (RHB PDF, BOC dynamic directories, DBS FCY API).",
            "Re-run tune_picker.py after each discovery batch to refresh picker_tuning.json.",
            "Run check_url_health.py before scheduled production runs to catch 404/redirect issues early.",
            "RPA: Continue expanding bot coverage to adjacent fixed workflows with the same "
            "security review checklist.",
        ],
    )
    _h(doc, "3.2 Long-Term", 2)
    _bullet(
        doc,
        [
            "Keep the proven pattern: deliver a working Python (or RPA) product first, then "
            "add controlled AI only where data classification allows.",
            "Scale the AI-driven discovery architecture to other external data monitoring use cases.",
            "Replace reliance on Windows Task Scheduler and local Excel with a unified web Dashboard.",
            "Introduce automated regression tests when bank parser structures change.",
        ],
    )

    # --- 4 Things Learned ---
    _h(doc, "4. Things Learned", 1)
    _bullet(
        doc,
        [
            "Starting from a usable Python application made AI integration safer and more useful "
            "than building an AI demo first — extractors and Excel already had business owners.",
            "In banking, mature RPA is often a better first automation choice than external "
            "generative AI for sensitive, fixed operational steps — because of auditability "
            "and data-residency constraints.",
            "Pure search / generative AI can return plausible but incorrect URLs. A hybrid "
            "architecture (rule-based hard constraints + ML soft scoring) is far more reliable.",
            "Heterogeneous data extraction (PDF cell-level parsing, dynamic API endpoints, DOM "
            "selectors) requires bank-specific knowledge and robust fallback logic.",
            "Enterprise batch engineering matters as much as algorithms: logging, encoding "
            "(UTF-8 BOM for Chinese filenames on Windows), exception handling, and dated runs/ folders.",
        ],
    )

    # --- 5 Problems and Solutions ---
    _h(doc, "5. Problems and Solutions", 1)

    _h(doc, "5.0 RPA: Balancing Automation Scope with Banking Confidentiality", 2)
    _p(
        doc,
        "Problem: Operational teams wanted more automation, but every process involves "
        "credentials, file paths, or business rules that cannot be shared outside the bank. "
        "External AI agents were not an acceptable shortcut.",
    )
    _p(
        doc,
        "Solution: Keep automation inside bank-approved RPA/scripting platforms; document "
        "steps for auditors; deliver only sanitized demos externally. This preserved security "
        "while still reducing repetitive manual work.",
    )

    _h(doc, "5.1 Problem: AI Misrouting Across Similar Bank Domains (ICBC → HLF)", 2)
    _p(
        doc,
        "Vertex AI Search occasionally returned URLs on hlf.com.sg when the destination was "
        "icbc_url. Both pages discuss fixed deposits, but HLF (Hong Leong Finance) is a "
        "different institution from ICBC (Industrial and Commercial Bank of China).",
    )
    _p(
        doc,
        "Root cause: without a per-dest domain whitelist, keyword-based search ranking could "
        "treat any plausible deposit page as a valid hit.",
    )
    _p(doc, "Solution (Step 1): Map each dest to its allowed bank domain in url_host_rules.py:", bold=True)
    _code(doc, CODE_ICBC_HLF_WHITELIST)
    _p(doc, "Solution (Step 2): Resolve fragments and reject wrong-bank hosts — full url_matches_dest():", bold=True)
    _code(doc, CODE_HOST_FRAGMENTS)
    _code(doc, CODE_URL_MATCHES_DEST)
    _p(
        doc,
        "Note: the bankofchina.com and sc.com blocks at the bottom of url_matches_dest() are "
        "additional path guards for BOC and SCB destinations only. They are NOT part of the "
        "ICBC → HLF fix. For ICBC, the rejection happens at the generic host check: when "
        'dest="icbc_url", frags=("singapore.icbc.com.cn",) and any hlf.com.sg URL returns False.',
    )
    _p(doc, "Solution (Step 3): Enforce at selection time in pick_best_url() and score_url():", bold=True)
    _code(doc, CODE_PICK_ON_BANK_FILTER)
    _code(doc, CODE_SCORE_PENALTY)
    _p(
        doc,
        "Wrong-bank candidates are dropped from the ranked pool (on_bank filter) and receive "
        "a -120 score penalty if they remain. ML inference in picker.py also pre-filters with "
        "url_matches_dest() before scoring.",
    )

    _h(doc, "5.2 Problem: AI Selecting Wrong Page Type (OCBC Premier vs SGD Board)", 2)
    _p(
        doc,
        "Search results frequently returned OCBC Premier Banking time-deposit pages instead of the "
        "standard SGD board-rate page (fixed-deposit-sgd-interest). This is a same-bank but "
        "wrong page-type error — different from the cross-bank ICBC/HLF case in §5.1.",
    )
    _p(doc, "Solution: Hard-reject patterns in url_dest_intent.py (full function):", bold=True)
    _code(doc, CODE_HARD_REJECT)
    _p(doc, "Supporting validator is_ocbc_sgd_board_page() referenced by url_hard_reject:", bold=True)
    _code(doc, CODE_OCBC_VALID_BOARD)
    _p(doc, "ML feature vector (full FEATURE_NAMES from features.py):", bold=True)
    _code(doc, CODE_FEATURES)
    _p(
        doc,
        "Wrong links were also added to hard_negatives.csv for supervised negative training. "
        "Combined with Grid Search tuning (blend_rule_weight=0.15, min_ml_proba=0.12), "
        "overall URL hit rate improved to approximately 95% on evaluation reports.",
    )

    _h(doc, "5.3 Problem: When to Trust Rules vs ML (Ambiguous Candidates)", 2)
    _p(
        doc,
        "When rule scores clearly separate candidates, ML added latency without benefit. When "
        "scores were close, ML disambiguation was critical.",
    )
    _p(doc, "Solution: Ambiguous-gate hybrid picker in picker.py:", bold=True)
    _code(doc, CODE_ML_PICK)
    _code(doc, CODE_TUNING)

    _h(doc, "5.4 Problem: Silent URL Failures After Bank Site Changes", 2)
    _p(
        doc,
        "Manual url_params.json entries could redirect or return HTTP 404 without immediate visibility.",
    )
    _p(doc, "Solution: Automated health inspection with risk classification:", bold=True)
    _code(doc, CODE_CHECK_URL)

    _h(doc, "5.5 Problem: Heterogeneous HSBC / RHB PDF Parsing", 2)
    _p(
        doc,
        "HSBC foreign-currency board rates are published as multi-page PDFs with segment-specific "
        "tables. Line-based text extraction produced truncated ranges and currency misclassification.",
    )
    _p(
        doc,
        "Solution: Refactored bank_extractors/impl.py to parse PDF tables cell-by-cell, with "
        "currency-heading detection and CNH normalisation. RHB FCY PDF parsing now tracks tier "
        "headers line-by-line to fix column misalignment.",
    )

    # --- 6 Looking Back ---
    _h(doc, "6. Looking Back", 1)
    _p(
        doc,
        "Building the Python extract/Excel product before AI Search was the right sequence. "
        "If I had started with AI discovery alone, there would have been no stable parsers "
        "to consume the URLs. I would still have invested earlier in a shared extractor "
        "interface (bank_extractors/) to reduce later refactoring when HSBC / OCBC page "
        "variants appeared.",
    )
    _p(
        doc,
        "On the RPA side, I would have built a shared component library earlier (download, "
        "Excel update, notification) so each new bot reused the same building blocks.",
    )
    _p(
        doc,
        "Introducing version control and unified configuration management (JSON/XLSX sync, "
        "environment variables for runs/ output) earlier would have avoided Windows encoding "
        "issues and simplified portable deployment.",
    )
    _p(
        doc,
        "Despite these retrospective improvements, delivering weekly RateStats Excel outputs "
        "and RPA bots provided continuous validation feedback from supervisors and end users.",
    )

    # --- 7 Acknowledgement ---
    _h(doc, "7. Acknowledgement", 1)
    _p(
        doc,
        f"I would like to thank my internship supervisor, {SUPERVISOR}, and colleagues in the "
        f"Financial Technology department at Bank of China Singapore Branch for guidance on "
        f"business requirements, RPA process ownership, and validation of MarketRateData "
        f"outputs. I also thank my NUS-ISS advisor, {NUS_ADVISOR}, for academic support "
        "throughout the attachment.",
    )

    # --- Appendices ---
    doc.add_page_break()
    _h(doc, "Appendix A: Listing of All Deliverables", 1)
    _bullet(doc, APPENDIX_A)

    doc.add_page_break()
    _h(doc, "Appendix B: Weekly Progress Reports and Project Plan", 1)
    _p(
        doc,
        "Please attach the following weekly reports as separate files when uploading to Canvas "
        "(do not zip). They are located in the RateStats project root directory:",
    )
    _bullet(doc, APPENDIX_B)
    _p(
        doc,
        "Submission reminder (Post IA 61 Briefing): export this Final Project Report to PDF; "
        "upload to Canvas; and email the PDF to your NUS-ISS advisor by the deadline. "
        "Fill the cover contact number and supervisor / advisor names before submission.",
    )

    out = OUT_DIR / "Final_Project_Report_Xu_Wenzhe.docx"
    doc.save(out)
    return out


def main() -> int:
    summary = build_project_summary_report()
    final = build_final_project_report()
    print(f"Generated: {summary}")
    print(f"Generated: {final}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
