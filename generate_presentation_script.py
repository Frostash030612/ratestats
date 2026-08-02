#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate polished 10-min presentation script + PPT outline."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

OUT = Path(__file__).resolve().parent / "docs" / "IA_Reports"
OUT.mkdir(parents=True, exist_ok=True)


def _h(doc: Document, text: str, level: int = 1) -> None:
    doc.add_heading(text, level=level)


def _p(doc: Document, text: str, *, bold: bool = False, italic: bool = False) -> None:
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.font.size = Pt(11)
    run.bold = bold
    run.italic = italic


def _bullet(doc: Document, items: list[str]) -> None:
    for item in items:
        para = doc.add_paragraph(item, style="List Bullet")
        for run in para.runs:
            run.font.size = Pt(11)


def _note(doc: Document, text: str) -> None:
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.font.size = Pt(10)
    run.italic = True
    run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)


def build() -> Path:
    doc = Document()

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = title.add_run("10-Minute Presentation Script & PPT Outline")
    r.bold = True
    r.font.size = Pt(18)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sr = sub.add_run(
        "Xu Wenzhe | Bank of China Singapore Branch | FinTech Department"
    )
    sr.font.size = Pt(12)

    _note(
        doc,
        "Timing guide: ~10 minutes total. RPA ≈ 4 min | RateStats AI ≈ 4 min | "
        "Open / Close ≈ 2 min. Speak from the script; slides stay sparse.",
    )

    # ------------------------------------------------------------------
    _h(doc, "Part A — Polished Spoken Script (English)", 1)

    _h(doc, "Opening (≈ 45 seconds)", 2)
    _p(
        doc,
        "Hi everyone. Today I will share my industrial attachment experience at "
        "Bank of China Singapore Branch, where I worked in the Financial Technology "
        "department as a developer.",
    )
    _p(
        doc,
        "My work covered two main areas. The first is Robotic Process Automation — "
        "RPA — which automates fixed, repetitive office workflows. The second is an "
        "AI-assisted market interest rate project, which was the first AI initiative "
        "our team asked me to build from scratch. I will spend roughly equal time on "
        "both parts.",
    )

    _h(doc, "Part 1 — RPA (≈ 4 minutes)", 2)
    _p(
        doc,
        "Let me start with RPA. Robotic Process Automation means using software robots "
        "and scripts to run a fixed process end to end — without a person clicking "
        "through the same screens every day.",
    )
    _p(
        doc,
        "In the bank, many daily jobs look simple but must be done carefully and "
        "consistently: downloading files from internal or partner websites, renaming "
        "and sorting them, updating Excel workbooks, and preparing the next step for "
        "another team. My role was to develop and maintain the automation code for "
        "these workflows.",
    )
    _p(
        doc,
        "It may not sound like advanced research, but in a banking environment it is "
        "very important. Banks have strict security and compliance requirements. "
        "They cannot freely send sensitive operations to external AI services or "
        "cloud agents. RPA, by contrast, is a mature and controllable approach: "
        "the logic stays on approved systems, the steps are auditable, and the "
        "risk profile is well understood.",
    )
    _p(
        doc,
        "By taking over repetitive work, RPA frees colleagues to focus on analysis "
        "and exception handling instead of copy-paste tasks. That is the real "
        "business value.",
    )
    _p(
        doc,
        "Because of confidentiality, I cannot show the full production processes. "
        "I will instead play a short sanitized demo — a GIF of a small sample "
        "flow — so you can see the style of work: the robot opens the site, "
        "downloads a file, updates Excel, and finishes the hand-off to the next step.",
    )
    _note(doc, "[Slide: play RPA demo GIF here — 20–30 seconds, then resume.]")
    _p(
        doc,
        "So that was the first half of my internship: building reliable automation "
        "for day-to-day banking operations under security constraints.",
    )

    _h(doc, "Part 2 — RateStats AI Project (≈ 4 minutes)", 2)
    _p(
        doc,
        "The second part is the AI project. Bank of China wanted to start exploring "
        "AI carefully. Because of security, we could not deploy large language models "
        "or cloud AI agents that might expose sensitive information. So this first "
        "project is a focused, controlled use of AI: AI search to discover bank rate "
        "pages, then Python to extract rates and produce Excel reports for business users.",
    )
    _p(
        doc,
        "I was responsible for the full development cycle. Other departments gave me "
        "the requirements; I designed the pipeline, implemented discovery and "
        "extraction, and delivered the final MarketRateData and Rainbow Table outputs.",
    )
    _p(
        doc,
        "You can see the high-level use case on this slide. There are two main stages. "
        "First, AI search finds the correct website for each bank and each rate type. "
        "Second, Python fetches HTML, PDF, or API data, cleans it, and writes a "
        "standard Excel workbook.",
    )
    _p(
        doc,
        "For example, for ICBC I need SGD board rates, SGD promotional rates, "
        "foreign-currency board rates, and foreign-currency promotional rates. "
        "Across Singapore’s major local and foreign banks — about 17 banks — that "
        "maps to dozens of destination URLs, roughly 47 rate nodes in total.",
    )
    _p(
        doc,
        "The hard part is not only scraping numbers. AI search sometimes returns a "
        "page that looks right but is wrong — for example, sending ICBC to an HLF "
        "domain, or mixing OCBC Premier pages with personal board-rate pages. "
        "So I built a hybrid filter: domain whitelist rules plus a machine-learning "
        "URL ranker, and we reached around 95% hit rate on evaluation.",
    )
    _note(doc, "[Slide: architecture diagram — AI Search → Rules+ML → Extract → Excel]")
    _p(
        doc,
        "If time allows, I will show a short run of the batch pipeline generating "
        "the Excel output. That completes the AI half of the story.",
    )

    _h(doc, "Closing (≈ 30–45 seconds)", 2)
    _p(
        doc,
        "To summarize: in FinTech at Bank of China Singapore, I delivered two "
        "complementary streams — RPA for secure, repeatable operations, and a "
        "controlled AI search pipeline for market rate intelligence. Both reduce "
        "manual work and respect banking security boundaries. Thank you. I am happy "
        "to take questions.",
    )

    # ------------------------------------------------------------------
    _h(doc, "Part B — 10-Minute PPT Structure (≈ 12 slides)", 1)
    _p(
        doc,
        "Keep slides visual. Do not paste long paragraphs. Each slide has 3–5 bullets "
        "maximum. Timing below assumes ~50–55 seconds average per content slide.",
    )

    _table_note = [
        ("1", "Title", "0:20", "RateStats & RPA @ Bank of China Singapore | Your name | NUS-ISS & BOC logos"),
        ("2", "Agenda", "0:20", "Two parts: (1) RPA  (2) AI RateStats — equal weight"),
        ("3", "Background & Role", "0:40", "FinTech dept | Developer | Security-first bank environment"),
        ("4", "RPA — What & Why", "0:50", "Automate fixed workflows | Why banks prefer RPA over external AI"),
        ("5", "RPA — What I Built", "0:50", "Download / Excel transform / hand-off | Mature & auditable"),
        ("6", "RPA Demo (GIF)", "0:40", "Sanitized demo only — no real prod credentials or full flow"),
        ("7", "AI Project — Context", "0:40", "First AI pilot | No LLM agents on cloud | Controlled AI Search"),
        ("8", "AI — Use Case / Scope", "0:50", "~17 banks × 4 rate types ≈ 47 nodes | Excel deliverables"),
        ("9", "AI — Architecture", "0:50", "Discover → Score (Rules+ML) → Extract → Excel"),
        ("10", "AI — Challenge & Fix", "0:50", "ICBC→HLF / OCBC Premier | Hybrid rules + ML ~95%"),
        ("11", "Status & Value", "0:40", "Status table C/I | Efficiency + accuracy + decision support"),
        ("12", "Conclusion & Q&A", "0:30", "Two streams, one theme: automation under bank security"),
    ]

    t = doc.add_table(rows=1 + len(_table_note), cols=4)
    t.style = "Table Grid"
    headers = ["#", "Slide", "Time", "Content cues"]
    for j, h in enumerate(headers):
        t.rows[0].cells[j].text = h
        for run in t.rows[0].cells[j].paragraphs[0].runs:
            run.bold = True
            run.font.size = Pt(9)
    for i, row in enumerate(_table_note):
        for j, cell in enumerate(row):
            t.rows[i + 1].cells[j].text = cell
            for run in t.rows[i + 1].cells[j].paragraphs[0].runs:
                run.font.size = Pt(9)

    _h(doc, "How to Expand to Fill 10 Minutes Equally", 2)
    _bullet(
        doc,
        [
            "RPA side: add one slide on 'before vs after' (manual hours → scheduled robot), "
            "plus the GIF. Do NOT invent fake bank internals — keep examples generic "
            "(download file → update Excel → notify next step).",
            "AI side: architecture + one concrete bug story (ICBC→HLF) is enough for "
            "technical depth. Optional 15-second Excel screenshot if demo time is short.",
            "If you finish early: spend 20 seconds on 'what I learned' — hybrid > pure AI "
            "in banking. If you run late: skip Excel demo; keep GIF + architecture.",
            "Practice with a timer twice. Aim to finish speaking at 9:30 so Q&A buffer exists.",
        ],
    )

    _h(doc, "Chinese Cue Card (optional, for rehearsal)", 2)
    _p(
        doc,
        "开场：中国银行新加坡分行 · 金融科技部 · 开发岗实习；两块工作：RPA 与 AI 利率项目，时间对半。",
    )
    _p(
        doc,
        "RPA：用程序跑固定流程（下载、改 Excel、交接）；银行要安全合规，不宜把敏感操作交给外部大模型；"
        "RPA 成熟可控；因保密只演示脱敏 GIF。",
    )
    _p(
        doc,
        "AI：银行首个探索项目；不能上云 Agent；做 AI 搜索找利率页 + Python 抓取出 Excel；"
        "约 17 家银行、每家挂牌/促销 × 新币/外币；难点是错链（ICBC→HLF、OCBC Premier）；"
        "规则+ML 混合选链，命中约 95%。",
    )
    _p(doc, "收尾：两条线都是「在银行安全边界内做自动化」；谢谢，欢迎提问。")

    path = OUT / "Presentation_Script_and_PPT_Outline.docx"
    doc.save(path)
    return path


if __name__ == "__main__":
    print(build())
