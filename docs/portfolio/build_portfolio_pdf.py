"""Build the Korean hiring portfolio PDF for the evidence-grounded RAG backend.

The PDF is authored directly with ReportLab so text remains selectable and
searchable. Run from the repository root:

    python docs/portfolio/build_portfolio_pdf.py
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Iterable, Sequence

from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs" / "portfolio"
PDF_PATH = OUT_DIR / "choi_byungchan_evidence_grounded_ai_document_qa_backend_portfolio.pdf"
LEGACY_PDF_PATH = OUT_DIR / "choi_byungchan_ai_document_qa_backend_portfolio.pdf"
VERSION_PDF_PATH = OUT_DIR / "choi_byungchan_ai_document_qa_backend_portfolio_result_first_v2.pdf"
PROJECT_TITLE = "Evidence-Grounded RAG Backend"
PROJECT_SUBTITLE = "Dense/Sparse/Hybrid 검색 실험 · bge-m3 + FAISS · BM25 · 근거 검증 · 답변 중단 정책"
PROJECT_LABEL = "AI Backend / Document RAG / Retrieval Quality Engineering"
PROJECT_SECTION = "AI 백엔드 / 문서 RAG / 검색 실험"
ACTIVE_TITLE = PROJECT_TITLE
ACTIVE_SUBTITLE = PROJECT_SUBTITLE
ACTIVE_LABEL = PROJECT_LABEL
TITLE_VARIANTS = [
    (
        OUT_DIR / "choi_byungchan_portfolio_evidence_grounded_document_qa_backend.pdf",
        "Evidence-Grounded RAG Backend",
        "Dense/Sparse/Hybrid 검색 실험 · SearchUnit/SearchView · 근거 검증 · 응답 제어",
        "AI Backend / Document RAG / Retrieval",
    ),
    (
        OUT_DIR / "choi_byungchan_portfolio_agent_runtime_document_qa_backend.pdf",
        "Document Retrieval & QA Backend",
        "검색 후보 · 원문 근거 · citation 검증 · 답변 가능 판단",
        "AI Backend / RAG Retrieval / QA",
    ),
    (
        OUT_DIR / "choi_byungchan_portfolio_citation_document_qa_backend.pdf",
        "Citation 기반 문서 RAG 백엔드",
        "원문 위치 확인 · citation 검증 · 답변 또는 중단 제어",
        "AI Backend / Citation / Evidence Validation",
    ),
]

PAGE_W = 960
PAGE_H = 540
MARGIN_X = 54
TOP = 498
BOTTOM = 42

FONT_REGULAR = "Malgun"
FONT_BOLD = "MalgunBold"

INK = HexColor("#182230")
MUTED = HexColor("#667382")
LIGHT = HexColor("#E3EAF1")
SOFT = HexColor("#F4F7FA")
PAPER = HexColor("#FBFCFD")
PANEL = HexColor("#FFFFFF")
ACCENT = HexColor("#0F62FE")
TEAL = HexColor("#087A83")
GREEN = HexColor("#2E7D55")
RED = HexColor("#B73A34")
AMBER = HexColor("#A86512")
DARK = HexColor("#111A24")
WHITE = HexColor("#FFFFFF")

REPO_URL = "https://github.com/sfr9802/async-ai-document-pipeline-with-domain-rag"
EVAL_README_URL = "https://github.com/sfr9802/async-ai-document-pipeline-with-domain-rag/blob/main/ai/eval/README.md"
EVAL_README_NOTE = "추가 질의 예시(PDF/XLSX/TEXT) 및 평가 관련 문서는 GitHub README에서 확인할 수 있습니다."
TOTAL_PAGES = 10
CARD_TEXT_X = 24
CARD_RIGHT_PAD = 24


def register_fonts() -> None:
    font_dir = Path(os.environ.get("WINDIR", "")) / "Fonts"
    regular = font_dir / "malgun.ttf"
    bold = font_dir / "malgunbd.ttf"
    if not regular.exists() or not bold.exists():
        raise FileNotFoundError("Required Korean font files were not found.")
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(regular)))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold)))


def sw(text: str, font: str, size: float) -> float:
    return pdfmetrics.stringWidth(text, font, size)


def wrap_text(text: str, font: str, size: float, width: float) -> list[str]:
    if not text:
        return []
    lines: list[str] = []
    for para in str(text).split("\n"):
        if not para:
            lines.append("")
            continue
        words = para.split(" ")
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if sw(candidate, font, size) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
            if sw(word, font, size) <= width:
                current = word
                continue
            chunk = ""
            for ch in word:
                next_chunk = f"{chunk}{ch}"
                if sw(next_chunk, font, size) <= width:
                    chunk = next_chunk
                else:
                    if chunk:
                        lines.append(chunk)
                    chunk = ch
            current = chunk
        if current:
            lines.append(current)
    return lines


def draw_wrapped(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    width: float,
    *,
    font: str = FONT_REGULAR,
    size: float = 14,
    leading: float | None = None,
    color=INK,
    max_lines: int | None = None,
) -> float:
    leading = leading or size * 1.45
    lines = wrap_text(text, font, size, width)
    if max_lines is not None:
        lines = lines[:max_lines]
    c.setFillColor(color)
    c.setFont(font, size)
    text_obj = c.beginText(x, y)
    text_obj.setLeading(leading)
    for line in lines:
        text_obj.textLine(line)
    c.drawText(text_obj)
    return y - max(1, len(lines)) * leading


def draw_footer(c: canvas.Canvas, page_num: int, section: str = "") -> None:
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setStrokeColor(LIGHT)
    c.setLineWidth(0.8)
    c.line(MARGIN_X, PAGE_H - 40, PAGE_W - MARGIN_X, PAGE_H - 40)
    c.setStrokeColor(HexColor("#D8E0E8"))
    c.line(MARGIN_X, 30, PAGE_W - MARGIN_X, 30)
    c.setFillColor(ACCENT)
    c.roundRect(MARGIN_X, PAGE_H - 42, 66, 4, 2, fill=1, stroke=0)
    c.setFillColor(MUTED)
    c.setFont(FONT_BOLD, 9)
    c.drawString(MARGIN_X, PAGE_H - 25, ACTIVE_TITLE)
    if section:
        c.setFont(FONT_REGULAR, 10)
        c.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 25, section)
    c.setFont(FONT_REGULAR, 9)
    c.drawRightString(PAGE_W - MARGIN_X, 13, f"{page_num:02d} / {TOTAL_PAGES:02d}")


def draw_page_title(
    c: canvas.Canvas,
    page_num: int,
    title: str,
    *,
    section: str,
    subtitle: str | None = None,
) -> float:
    draw_footer(c, page_num, section)
    y = PAGE_H - 76
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 29)
    c.drawString(MARGIN_X, y, title)
    y -= 28
    if subtitle:
        y = draw_wrapped(c, subtitle, MARGIN_X, y, PAGE_W - MARGIN_X * 2, size=14, color=MUTED, leading=20)
    return y - 18


def draw_chip(c: canvas.Canvas, text: str, x: float, y: float, *, color=ACCENT) -> float:
    size = 10
    pad_x = 10
    w = sw(text, FONT_BOLD, size) + pad_x * 2
    h = 24
    c.setFillColor(WHITE)
    c.setStrokeColor(HexColor("#D8E2EC"))
    c.roundRect(x, y - h, w, h, 4, fill=1, stroke=1)
    c.setFillColor(color)
    c.setFont(FONT_BOLD, size)
    c.drawCentredString(x + w / 2, y - 16, text)
    return x + w + 9


def draw_bullets(
    c: canvas.Canvas,
    items: Sequence[str],
    x: float,
    y: float,
    width: float,
    *,
    size: float = 14,
    leading: float = 20,
    color=INK,
    bullet_color=ACCENT,
) -> float:
    for item in items:
        c.setFillColor(bullet_color)
        marker_y = y - size * 0.36
        c.circle(x + 5, marker_y, 2.8, fill=1, stroke=0)
        y = draw_wrapped(c, item, x + 22, y, width - 22, size=size, leading=leading, color=color)
        y -= 8
    return y


def draw_card_body_lines(
    c: canvas.Canvas,
    items: Sequence[str],
    x: float,
    y: float,
    width: float,
    *,
    size: float = 12.5,
    leading: float = 17,
    color=INK,
    gap: float = 8,
) -> float:
    for item in items:
        y = draw_wrapped(c, item, x, y, width, size=size, leading=leading, color=color)
        y -= gap
    return y


def draw_card(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    body: Sequence[str],
    *,
    accent=ACCENT,
    title_size: float = 15,
    body_size: float = 12.5,
) -> None:
    compact = h <= 82
    title_y = y - (28 if compact else 34)
    body_y = y - (52 if compact else 64)
    c.setFillColor(HexColor("#EEF2F6"))
    c.roundRect(x + 3, y - h - 3, w, h, 6, fill=1, stroke=0)
    c.setFillColor(PANEL)
    c.setStrokeColor(HexColor("#D7E0E9"))
    c.roundRect(x, y - h, w, h, 6, fill=1, stroke=1)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, title_size)
    c.drawString(x + CARD_TEXT_X, title_y, title)
    draw_card_body_lines(
        c,
        list(body),
        x + CARD_TEXT_X,
        body_y,
        w - CARD_TEXT_X - CARD_RIGHT_PAD,
        size=body_size,
        leading=16 if compact else 17,
        gap=6 if compact else 8,
    )


def draw_text_card(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    lines: Sequence[str],
    *,
    accent=ACCENT,
    title_size: float = 15,
    body_size: float = 12,
    body_color=INK,
    fill=PANEL,
) -> None:
    compact = h <= 82
    title_y = y - (28 if compact else 34)
    body_y = y - (52 if compact else 62)
    c.setFillColor(HexColor("#EEF2F6"))
    c.roundRect(x + 2, y - h - 2, w, h, 7, fill=1, stroke=0)
    c.setFillColor(fill)
    c.setStrokeColor(HexColor("#D7E0E9"))
    c.roundRect(x, y - h, w, h, 7, fill=1, stroke=1)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, title_size)
    c.drawString(x + CARD_TEXT_X, title_y, title)
    yy = body_y
    for line in lines:
        font = FONT_BOLD if line.startswith(("POST ", "GET ")) else FONT_REGULAR
        color = accent if line.startswith(("POST ", "GET ")) else body_color
        yy = draw_wrapped(
            c,
            line,
            x + CARD_TEXT_X,
            yy,
            w - CARD_TEXT_X - CARD_RIGHT_PAD,
            font=font,
            size=body_size,
            leading=body_size + 5,
            color=color,
        )
        yy -= 7


def draw_metric_box(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
    value: str,
    *,
    accent=ACCENT,
    value_size: float = 13.5,
) -> None:
    c.setFillColor(WHITE)
    c.setStrokeColor(HexColor("#D7E0E9"))
    c.roundRect(x, y - h, w, h, 7, fill=1, stroke=1)
    c.setFillColor(accent)
    c.setFont(FONT_BOLD, 10.5)
    c.drawString(x + CARD_TEXT_X, y - 28, label)
    draw_wrapped(
        c,
        value,
        x + CARD_TEXT_X,
        y - 52,
        w - CARD_TEXT_X - CARD_RIGHT_PAD,
        font=FONT_BOLD,
        size=value_size,
        leading=value_size + 4,
        color=INK,
    )


def draw_section_label(c: canvas.Canvas, x: float, y: float, text: str, *, color=ACCENT) -> None:
    c.setFillColor(color)
    c.setFont(FONT_BOLD, 10.5)
    c.drawString(x, y, text)


def draw_code_panel(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    lines: Sequence[str],
    *,
    fill=HexColor("#111A24"),
    title_color=WHITE,
    text_color=HexColor("#DCE6EF"),
    accent=TEAL,
    font_size: float = 8.6,
    leading: float = 12.2,
) -> None:
    c.setFillColor(fill)
    c.roundRect(x, y - h, w, h, 8, fill=1, stroke=0)
    c.setFillColor(HexColor("#1F2B38"))
    c.roundRect(x + 14, y - 30, min(w - 28, sw(title, FONT_BOLD, 9.5) + 24), 20, 5, fill=1, stroke=0)
    c.setFillColor(title_color)
    c.setFont(FONT_BOLD, 9.5)
    c.drawString(x + 26, y - 24, title)
    yy = y - 50
    for line in lines:
        color = accent if line.strip().startswith(('"', "{", "}", "]")) else text_color
        c.setFillColor(color)
        c.setFont(FONT_REGULAR, font_size)
        c.drawString(x + 18, yy, line)
        yy -= leading
        if yy < y - h + 16:
            break


def draw_kv_result(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    label: str,
    value: str,
    *,
    label_color=MUTED,
    value_color=INK,
    value_size: float = 12.5,
) -> float:
    draw_section_label(c, x, y, label, color=label_color)
    return draw_wrapped(c, value, x, y - 20, w, size=value_size, leading=value_size + 5, color=value_color)


def draw_eval_readme_note(c: canvas.Canvas, y: float = 72) -> None:
    draw_wrapped(
        c,
        EVAL_README_NOTE,
        MARGIN_X,
        y,
        840,
        font=FONT_BOLD,
        size=10.8,
        leading=15,
        color=TEAL,
        max_lines=1,
    )
    c.setFillColor(ACCENT)
    c.setFont(FONT_REGULAR, 9.4)
    c.drawString(MARGIN_X, y - 18, EVAL_README_URL)
    c.linkURL(EVAL_README_URL, (MARGIN_X, y - 22, MARGIN_X + 620, y - 8), relative=0)


def draw_table(
    c: canvas.Canvas,
    x: float,
    y_top: float,
    col_widths: Sequence[float],
    rows: Sequence[Sequence[str]],
    *,
    font_size: float = 11.5,
    header_size: float = 12,
    leading: float = 15,
    pad_x: float = 8,
    pad_y: float = 8,
    header_fill=HexColor("#EAF1F8"),
    grid=HexColor("#D6E0EA"),
) -> float:
    y = y_top
    table_w = sum(col_widths)
    for row_idx, row in enumerate(rows):
        is_header = row_idx == 0
        font = FONT_BOLD if is_header else FONT_REGULAR
        size = header_size if is_header else font_size
        wrapped = [wrap_text(cell, font, size, w - pad_x * 2) for cell, w in zip(row, col_widths)]
        row_h = max((len(lines) or 1) * leading + pad_y * 2 for lines in wrapped)
        c.setFillColor(header_fill if is_header else (WHITE if row_idx % 2 else HexColor("#F8FAFC")))
        c.setStrokeColor(grid)
        c.rect(x, y - row_h, table_w, row_h, fill=1, stroke=1)
        cx = x
        for col_idx, (cell_lines, col_w) in enumerate(zip(wrapped, col_widths)):
            if col_idx:
                c.setStrokeColor(grid)
                c.line(cx, y, cx, y - row_h)
            c.setFillColor(INK if is_header else DARK)
            c.setFont(font, size)
            text = c.beginText(cx + pad_x, y - pad_y - size)
            text.setLeading(leading)
            for line in cell_lines:
                text.textLine(line)
            c.drawText(text)
            cx += col_w
        y -= row_h
    return y


def draw_arrow(c: canvas.Canvas, x1: float, y1: float, x2: float, y2: float, *, color=ACCENT) -> None:
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(2)
    c.line(x1, y1, x2, y2)
    path = c.beginPath()
    path.moveTo(x2, y2)
    path.lineTo(x2 - 8, y2 + 5)
    path.lineTo(x2 - 8, y2 - 5)
    path.close()
    c.drawPath(path, fill=1, stroke=0)


def draw_flow_box(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    *,
    fill=WHITE,
    stroke=HexColor("#D7DFE8"),
    title_size: float = 12,
) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.roundRect(x, y - h, w, h, 7, fill=1, stroke=1)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, title_size)
    lines = wrap_text(title, FONT_BOLD, title_size, w - 16)
    visible_lines = lines[:2]
    line_step = title_size + 3
    text_block_h = len(visible_lines) * title_size + max(0, len(visible_lines) - 1) * 3
    ty = y - (h - text_block_h) / 2 - title_size + 1
    for line in visible_lines:
        c.drawCentredString(x + w / 2, ty, line)
        ty -= line_step


def cover(c: canvas.Canvas) -> None:
    draw_footer(c, 1, PROJECT_SECTION)
    c.setFillColor(ACCENT)
    c.rect(0, PAGE_H - 7, PAGE_W, 7, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 38)
    c.drawString(MARGIN_X, 360, ACTIVE_TITLE)
    c.setFillColor(TEAL)
    c.setFont(FONT_BOLD, 16)
    draw_wrapped(c, ACTIVE_SUBTITLE, MARGIN_X, 314, 820, font=FONT_BOLD, size=16, leading=22, color=TEAL)
    c.setFillColor(MUTED)
    c.setFont(FONT_BOLD, 10.5)
    c.drawString(MARGIN_X, 266, ACTIVE_LABEL)
    cover_rows = [
        ("Input", "PDF · TEXT · XLSX"),
        ("Retrieval", "Dense · Sparse · Hybrid"),
        ("Guard", "Evidence · Citation · Stop"),
    ]
    card_w = 260
    for idx, (label, value) in enumerate(cover_rows):
        x = MARGIN_X + idx * (card_w + 22)
        draw_metric_box(c, x, 232, card_w, 76, label, value, accent=[ACCENT, TEAL, GREEN][idx], value_size=13.2)
    x = MARGIN_X
    for chip, color in [
        ("SearchUnit/View", TEAL),
        ("bge-m3 + FAISS", ACCENT),
        ("BM25", GREEN),
        ("Hybrid", AMBER),
        ("EvidenceBundle", TEAL),
        ("Stop Policy", RED),
    ]:
        x = draw_chip(c, chip, x, 148, color=color)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 13)
    c.drawString(MARGIN_X, 72, "GitHub")
    c.setFont(FONT_REGULAR, 12)
    c.setFillColor(MUTED)
    c.drawString(MARGIN_X + 58, 72, REPO_URL)
    c.setFillColor(ACCENT)
    c.setFont(FONT_BOLD, 14)
    c.drawString(MARGIN_X, 48, PROJECT_SECTION)


def document_example_page(
    c: canvas.Canvas,
    *,
    page_num: int,
    title: str,
    source_family: str,
    query: str,
    evidence: str,
    answer: str,
    citation: str,
    code_lines: Sequence[str],
    accent=ACCENT,
) -> None:
    y = draw_page_title(c, page_num, title, section="질의 예시")
    intro = "User Query · Evidence Surface · Response · Citation · API Response"
    draw_wrapped(c, intro, MARGIN_X, y + 4, 840, size=15, leading=22, color=MUTED)

    panel_x = MARGIN_X
    panel_y = y - 38
    panel_w = 540
    panel_h = 286
    c.setFillColor(HexColor("#EEF2F6"))
    c.roundRect(panel_x + 3, panel_y - panel_h - 3, panel_w, panel_h, 10, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setStrokeColor(HexColor("#D4DEE8"))
    c.roundRect(panel_x, panel_y - panel_h, panel_w, panel_h, 10, fill=1, stroke=1)
    c.setFillColor(HexColor("#F3F6F9"))
    c.roundRect(panel_x, panel_y - 36, panel_w, 36, 10, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 12.5)
    c.drawString(panel_x + 18, panel_y - 23, f"{source_family} Evidence Preview")
    c.setFillColor(accent)
    c.roundRect(panel_x + panel_w - 136, panel_y - 27, 116, 18, 4, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 8.8)
    c.drawCentredString(panel_x + panel_w - 78, panel_y - 22, "README sample")

    content_x = panel_x + 22
    content_y = panel_y - 62
    content_w = panel_w - 44
    content_y = draw_kv_result(
        c,
        content_x,
        content_y,
        content_w,
        "User Query",
        query,
        label_color=ACCENT,
        value_size=12.4,
    )
    content_y -= 10
    content_y = draw_kv_result(
        c,
        content_x,
        content_y,
        content_w,
        "Evidence Surface",
        evidence,
        label_color=TEAL,
        value_size=11.2,
    )
    content_y -= 8
    content_y = draw_kv_result(
        c,
        content_x,
        content_y,
        content_w,
        "Response",
        answer,
        label_color=GREEN,
        value_size=12.4,
    )
    content_y -= 10
    draw_kv_result(
        c,
        content_x,
        content_y,
        content_w,
        "Citation",
        citation,
        label_color=AMBER,
        value_size=11.8,
    )

    draw_code_panel(
        c,
        MARGIN_X + 568,
        panel_y,
        274,
        286,
        "API RESPONSE",
        code_lines,
        font_size=8.2,
        leading=12.0,
    )
    draw_eval_readme_note(c)


def xlsx_example(c: canvas.Canvas) -> None:
    document_example_page(
        c,
        page_num=2,
        title="XLSX 예시",
        source_family="XLSX",
        query="2019년 2월 5호선의 승차총승객수는 몇 명입니까?",
        evidence="서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx\n철도 A352:D401 · cell D352",
        answer="2019년 2월 5호선의 승차총승객수는 15,446,522명입니다.",
        citation="철도!D352",
        code_lines=[
            "{",
            '  "mode": "readme_sample",',
            '  "source_family": "XLSX",',
            '  "answer": "15,446,522명",',
            '  "citation": {',
            '    "sheet": "철도",',
            '    "range": "A352:D401",',
            '    "cell": "D352"',
            "  },",
            '  "citation_verified": true,',
            '  "not_quality_metric": true',
            "}",
        ],
        accent=GREEN,
    )


def pdf_example(c: canvas.Canvas) -> None:
    document_example_page(
        c,
        page_num=3,
        title="PDF 예시",
        source_family="PDF",
        query="2020년 한국 원달러 기말 환율은 얼마인가요?",
        evidence="2021_03_recent_economic_trends.pdf\np.65 · table_body",
        answer="2020년 한국 원달러 기말 환율은 1,088.0입니다.",
        citation="2021_03_recent_economic_trends.pdf p.65",
        code_lines=[
            "{",
            '  "mode": "readme_sample",',
            '  "source_family": "PDF",',
            '  "answer": "1,088.0",',
            '  "citation": {',
            '    "file": "2021_03_recent_economic_trends.pdf",',
            '    "page": 65,',
            '    "surface": "table_body"',
            "  },",
            '  "citation_verified": true,',
            '  "not_quality_metric": true',
            "}",
        ],
        accent=TEAL,
    )


def text_example(c: canvas.Canvas) -> None:
    document_example_page(
        c,
        page_num=4,
        title="TEXT 예시",
        source_family="TEXT",
        query="유우야키의 나이와 생일은 어떻게 적혀 있어",
        evidence="TEXT chunk/source context\ntext_namu_v2_1 · 7be08880",
        answer="유우야키의 나이는 16세이고 생일은 9월 29일입니다.",
        citation="TEXT chunk/source context",
        code_lines=[
            "{",
            '  "mode": "readme_sample",',
            '  "source_family": "TEXT",',
            '  "answer": "16세, 9월 29일",',
            '  "citation": {',
            '    "track": "TEXT",',
            '    "source": "text_namu_v2_1",',
            '    "chunk": "7be08880"',
            "  },",
            '  "citation_verified": true,',
            '  "not_quality_metric": true',
            "}",
        ],
        accent=ACCENT,
    )


def actual_response_smoke(c: canvas.Canvas) -> None:
    y = draw_page_title(
        c,
        8,
        "Actual Response Smoke",
        section="응답 정책",
        subtitle="29개 승인 질의에서 답변/중단 정책과 citation verification을 확인했습니다.",
    )

    card_w = 196
    card_h = 92
    gap = 18
    top = y - 16
    cards = [
        ("Approved Queries", "29", "PDF 4 · TEXT 6 · XLSX 19", ACCENT),
        ("Answered", "10", "PDF 4 · TEXT 6", GREEN),
        ("Citation Verified", "10", "answered rows only", TEAL),
        ("Stopped", "19", "stopped / fail_closed", AMBER),
    ]
    for idx, (label, value, desc, color) in enumerate(cards):
        x = MARGIN_X + idx * (card_w + gap)
        c.setFillColor(WHITE)
        c.setStrokeColor(HexColor("#D7E1EA"))
        c.roundRect(x, top - card_h, card_w, card_h, 7, fill=1, stroke=1)
        c.setFillColor(color)
        c.setFont(FONT_BOLD, 10)
        c.drawString(x + 18, top - 24, label)
        c.setFillColor(INK)
        c.setFont(FONT_BOLD, 21)
        c.drawString(x + 18, top - 52, value)
        draw_wrapped(c, desc, x + 18, top - 72, card_w - 36, size=9.8, leading=13, color=MUTED)

    table_y = top - card_h - 40
    draw_table(
        c,
        MARGIN_X,
        table_y,
        [150, 170, 190, 260],
        [
            ["Family", "Answered", "Citation verified", "Policy outcome"],
            ["PDF", "4 / 4", "4", "answered via RAG evidence"],
            ["TEXT", "6 / 6", "6", "answered via RAG evidence"],
            ["XLSX", "0 / 19", "0", "19 fail_closed, no XLSX-wide success claim"],
        ],
        font_size=11.2,
        header_size=12,
        leading=15,
        pad_y=8,
    )

    draw_wrapped(
        c,
        "해석 경계: answer quality metric이 아니라 response policy smoke입니다. 10개 answered + citation verified, 19개 stopped / fail_closed.",
        MARGIN_X,
        72,
        840,
        font=FONT_BOLD,
        size=11.4,
        leading=16,
        color=TEAL,
    )


def system_structure(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 6, "시스템 구조", section="구조")
    intro = "Request · Job · Worker · Search · Evidence · Trace"
    draw_wrapped(c, intro, MARGIN_X, y + 4, 840, size=15, leading=22, color=MUTED)
    flow_y = y - 52
    flow = [
        ("User", 62),
        ("Spring API", 116),
        ("Job ID", 66),
        ("FastAPI Worker", 122),
        ("Search", 92),
        ("Evidence", 94),
        ("Answer / Trace", 112),
    ]
    x = MARGIN_X
    for idx, (label, w) in enumerate(flow):
        draw_flow_box(c, x, flow_y, w, 42, label, fill=WHITE, title_size=9.2)
        if idx < len(flow) - 1:
            draw_arrow(c, x + w + 2, flow_y - 21, x + w + 18, flow_y - 21, color=ACCENT)
        x += w + 20
    card_y = flow_y - 82
    col_w = 264
    gap = 24
    draw_card(
        c,
        MARGIN_X,
        card_y,
        col_w,
        190,
        "API Server",
        [
            "문서 업로드와 Job 생성",
            "작업 상태와 결과 조회",
            "사용자 요청/응답 DTO 관리",
        ],
        accent=ACCENT,
        body_size=11.8,
    )
    draw_card(
        c,
        MARGIN_X + col_w + gap,
        card_y,
        col_w,
        190,
        "AI Worker",
        [
            "PDF/XLSX/Text 파싱",
            "검색 단위와 인덱스 생성",
            "검색 후보와 원문 근거 확인",
            "답변 또는 중단 결정",
        ],
        accent=TEAL,
        body_size=11.8,
    )
    draw_card(
        c,
        MARGIN_X + (col_w + gap) * 2,
        card_y,
        col_w,
        190,
        "Artifacts / Trace",
        [
            "답변과 citation 저장",
            "근거 참조와 실패 사유 기록",
            "실행 trace/report 확인",
        ],
        accent=GREEN,
        body_size=11.8,
    )
    draw_wrapped(
        c,
        "Job ID · Artifact · Status · Evidence",
        MARGIN_X,
        78,
        840,
        size=14.5,
        leading=21,
        color=TEAL,
        font=FONT_BOLD,
    )


def evidence_split(c: canvas.Canvas) -> None:
    y = draw_page_title(
        c,
        7,
        "후보 · 근거 · 응답 제어",
        section="문제 및 해결방안",
    )
    c.setFillColor(TEAL)
    c.setFont(FONT_BOLD, 21)
    c.drawString(MARGIN_X, y, "SearchView 후보와 SourceAtom/EvidenceBundle 근거 분리")
    flow_y = y - 58
    cards = [
        ("1", "검색 후보", "SearchUnit/SearchView", ACCENT),
        ("2", "원문 근거", "SourceAtom\nEvidenceBundle", TEAL),
        ("3", "Citation 검증", "근거 위치 확인", GREEN),
        ("4", "답변 또는 중단", "근거 부족이면 fail_closed", AMBER),
    ]
    card_w = 188
    card_h = 108
    gap = 28
    for idx, (num, title, body, color) in enumerate(cards):
        x = MARGIN_X + idx * (card_w + gap)
        c.setFillColor(WHITE)
        c.setStrokeColor(HexColor("#D7E1EA"))
        c.roundRect(x, flow_y - card_h, card_w, card_h, 7, fill=1, stroke=1)
        c.setFillColor(color)
        c.circle(x + 24, flow_y - 31, 13, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(FONT_BOLD, 11)
        c.drawCentredString(x + 24, flow_y - 35, num)
        c.setFillColor(INK)
        c.setFont(FONT_BOLD, 15)
        c.drawString(x + 48, flow_y - 34, title)
        draw_wrapped(c, body, x + 22, flow_y - 66, card_w - 44, size=11.4, leading=16.5, color=MUTED)
        if idx < len(cards) - 1:
            draw_arrow(c, x + card_w + 4, flow_y - card_h / 2, x + card_w + gap - 8, flow_y - card_h / 2, color=ACCENT)
    draw_table(
        c,
        MARGIN_X,
        flow_y - 134,
        [210, 300, 330],
        [
            ["단계", "왜 필요한가", "사용자에게 보이는 결과"],
            ["검색 후보", "관련 자료를 먼저 좁힘", "candidate-only SearchView"],
            ["원문 근거", "실제 위치와 값을 다시 확인", "SourceAtom/EvidenceBundle"],
            ["응답 제어", "근거 부족 답변 방지", "answered / stopped / fail_closed"],
        ],
        font_size=11.2,
        header_size=12,
        leading=15,
        pad_y=8,
    )

def trace_layer(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 6, "실행 Trace / Guard", section="Trace Guard")
    intro = "Thin execution sidecar · schema-bound tools · redacted refs · fail-closed guards"
    draw_wrapped(c, intro, MARGIN_X, y + 4, 840, size=14.5, leading=21, color=INK)
    flow_y = y - 72
    flow = ["Request", "Policy Guard", "Tools", "Evidence", "Decision", "Redacted Trace"]
    widths = [84, 112, 82, 104, 98, 120]
    x = MARGIN_X
    for idx, (label, w) in enumerate(zip(flow, widths)):
        draw_flow_box(c, x, flow_y, w, 42, label, fill=WHITE, title_size=9.8)
        if idx < len(flow) - 1:
            draw_arrow(c, x + w + 2, flow_y - 21, x + w + 18, flow_y - 21, color=ACCENT)
        x += w + 25
    draw_text_card(
        c,
        MARGIN_X,
        flow_y - 78,
        300,
        242,
        "Trace / Guard contract",
        [
            "query_ref / evidence_ref only",
            "selected_tools / tools_called schema bound",
            "out-of-scope evidence drift blocks answer",
            "runtime_contract_violation -> fail_closed",
            "raw question · raw evidence · local path not stored",
        ],
        accent=GREEN,
        body_size=10.9,
    )
    draw_code_panel(
        c,
        MARGIN_X + 330,
        flow_y - 78,
        512,
        242,
        "reports/agentops_sample_trace.json",
        [
            "{",
            '  "schema_version": "agentops_run_trace_v1",',
            '  "run_id": "agentops-portfolio-smoke",',
            '  "query": "query_ref:8a3fa83080fc7cb5",',
            '  "selected_tools": [',
            '    "retrieve_xlsx_table", "validate_evidence",',
            '    "classify_answerability"',
            "  ],",
            '  "tools_called": [',
            '    "rag.l0.query_routing",',
            '    "rag.l4.sourceatom_hydration"',
            "  ],",
            '  "evidence_ids": ["evidence_ref:01"],',
            '  "policy_decision": "allow_diagnostic",',
            '  "failure_category": "",',
            '  "final_decision": "diagnostic_only_answer"',
            "}",
        ],
        font_size=7.8,
        leading=10.8,
    )


def verified_scope(c: canvas.Canvas) -> None:
    y = draw_page_title(
        c,
        5,
        "Dense / Sparse / Hybrid 검색 실험",
        section="검색",
        subtitle="Source-derived SearchUnit/SearchView 300개 후보 가용성 진단",
    )
    intro = "PDF 100 · TEXT 100 · XLSX 100"
    draw_wrapped(c, intro, MARGIN_X, y + 4, 840, size=15, leading=22, color=MUTED)

    card_w = 196
    card_h = 118
    gap_x = 18
    start_y = y - 34
    proofs = [
        ("SearchUnit/SearchView 구축", "300", "PDF/TEXT/XLSX 각 100개 · source-derived", ACCENT),
        ("Dense Retrieval", "299 / 300", "BAAI/bge-m3 + FAISS IndexFlatIP", TEAL),
        ("Sparse Retrieval", "300 / 300", "BM25 candidate availability", GREEN),
        ("Hybrid Retrieval", "300 / 300", "Dense + Sparse merge", AMBER),
    ]
    for idx, (label, value, desc, color) in enumerate(proofs):
        x = MARGIN_X + idx * (card_w + gap_x)
        top = start_y
        c.setFillColor(WHITE)
        c.setStrokeColor(HexColor("#D7E1EA"))
        c.roundRect(x, top - card_h, card_w, card_h, 7, fill=1, stroke=1)
        c.setFillColor(color)
        c.setFont(FONT_BOLD, 10.5)
        c.drawString(x + 22, top - 24, label)
        c.setFillColor(INK)
        c.setFont(FONT_BOLD, 19)
        c.drawString(x + 22, top - 50, value)
        draw_wrapped(
            c,
            desc,
            x + 22,
            top - 68,
            card_w - 44,
            font=FONT_BOLD,
            size=10.8,
            leading=14,
            color=MUTED,
            max_lines=3,
        )

    metric_y = start_y - card_h - 36
    draw_table(
        c,
        MARGIN_X,
        metric_y,
        [170, 170, 430],
        [
            ["구분", "구현", "현재 포트폴리오에서 말하는 것"],
            ["Dense", "bge-m3 + FAISS", "vector 후보 가용성 299/300"],
            ["Sparse", "BM25", "lexical 후보 가용성 300/300"],
            ["Hybrid", "Dense + Sparse", "merged 후보 가용성 300/300"],
        ],
        font_size=11.2,
        header_size=12,
        leading=15,
        pad_y=8,
    )
    draw_wrapped(
        c,
        "계약 테스트: 53개 통과 · Hit@K/MRR/nDCG는 qrels gate 전까지 미계산 · 이 페이지는 검색 품질 점수가 아니라 후보 가용성 진단입니다.",
        MARGIN_X,
        74,
        840,
        font=FONT_BOLD,
        size=11.4,
        leading=16,
        color=TEAL,
    )


def retrieval_design_notes(c: canvas.Canvas) -> None:
    y = draw_page_title(
        c,
        9,
        "검색 설계 포인트",
        section="설계 선택",
        subtitle="RAG 검색 실험을 구현하면서 후보, 근거, 응답 정책을 분리했습니다.",
    )
    card_w = 410
    card_h = 116
    gap_x = 22
    gap_y = 24
    top = y - 38
    cards = [
        (
            "Dense / Sparse / Hybrid 비교",
            [
                "Dense: bge-m3 + FAISS로 의미 기반 후보 검색",
                "Sparse: BM25로 키워드/표현 일치 후보 검색",
                "Hybrid: 두 후보군을 병합해 후보 가용성 확인",
            ],
            ACCENT,
        ),
        (
            "SearchUnit / SearchView 분리",
            [
                "SearchUnit은 source-derived 검색 단위",
                "SearchView는 candidate-only retrieval view",
                "후보 표면과 근거 truth를 섞지 않음",
            ],
            TEAL,
        ),
        (
            "SourceAtom / EvidenceBundle 분리",
            [
                "SourceAtom은 원문 위치와 값의 근거 atom",
                "EvidenceBundle은 답변과 citation 검증 단위",
                "검색 후보가 곧 답변 근거가 되지 않게 설계",
            ],
            GREEN,
        ),
        (
            "근거 부족 시 답변 중단",
            [
                "citation이 확인된 10건만 answered",
                "근거가 부족한 19건은 stopped / fail_closed",
                "실패 지점은 실행 Trace로 확인 가능",
            ],
            AMBER,
        ),
    ]
    for idx, (title, body, color) in enumerate(cards):
        col = idx % 2
        row = idx // 2
        x = MARGIN_X + col * (card_w + gap_x)
        yy = top - row * (card_h + gap_y)
        draw_text_card(
            c,
            x,
            yy,
            card_w,
            card_h,
            title,
            body,
            accent=color,
            body_size=10.7,
        )
    draw_wrapped(
        c,
        "요약: 검색 실험 -> 근거 검증 -> 답변 중단 정책 -> 실행 Trace",
        MARGIN_X,
        70,
        840,
        size=14,
        leading=20,
        color=TEAL,
        font=FONT_BOLD,
    )


def closing(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 10, "회고", section="회고")
    intro = "프로젝트를 진행하며 배운 점"
    draw_wrapped(c, intro, MARGIN_X, y + 4, 840, size=15, leading=22, color=MUTED)

    cards = [
        (
            "검색 후보와 답변 근거는 다르다",
            [
                "SearchView는 candidate-only 표면입니다.",
                "최종 citation은 SourceAtom/EvidenceBundle에서 다시 확인해야 합니다.",
            ],
            ACCENT,
        ),
        (
            "Retrieval 성능과 Answer Quality는 별개다",
            [
                "후보 가용성이 좋아도 답변 품질을 자동으로 보장하지 않습니다.",
                "Hit@K/MRR/nDCG와 response smoke를 분리해 봐야 했습니다.",
            ],
            TEAL,
        ),
        (
            "PDF/XLSX는 일반 텍스트 검색과 다르다",
            [
                "PDF는 page/table context, XLSX는 sheet/range/cell이 중요합니다.",
                "문서 유형별 citation 단위를 다르게 다뤄야 했습니다.",
            ],
            GREEN,
        ),
        (
            "근거 부족 시 답변 중단 정책이 중요하다",
            [
                "그럴듯한 답변보다 검증 가능한 중단이 더 안전합니다.",
                "answered와 stopped/fail_closed를 함께 기록해야 운영 판단이 쉬워집니다.",
            ],
            AMBER,
        ),
    ]
    card_w = 410
    card_h = 116
    gap_x = 22
    gap_y = 24
    top = y - 44
    for idx, (title, body, color) in enumerate(cards):
        col = idx % 2
        row = idx // 2
        x = MARGIN_X + col * (card_w + gap_x)
        yy = top - row * (card_h + gap_y)
        draw_text_card(
            c,
            x,
            yy,
            card_w,
            card_h,
            title,
            body,
            accent=color,
            title_size=14.3,
            body_size=10.8,
        )

    draw_wrapped(
        c,
        "이번 프로젝트에서는 검색 후보, 근거 검증, 중단 정책을 분리해 설계하는 부분의 중요성을 크게 체감했습니다.",
        MARGIN_X,
        78,
        840,
        font=FONT_BOLD,
        size=12.8,
        leading=18,
        color=TEAL,
    )
    c.setFillColor(MUTED)
    c.setFont(FONT_REGULAR, 10)
    c.drawString(MARGIN_X, 52, REPO_URL)


SLIDES = [
    cover,
    xlsx_example,
    pdf_example,
    text_example,
    verified_scope,
    system_structure,
    evidence_split,
    actual_response_smoke,
    retrieval_design_notes,
    closing,
]


def build_pdf(
    path: Path = PDF_PATH,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    label: str | None = None,
) -> Path:
    global ACTIVE_LABEL, ACTIVE_SUBTITLE, ACTIVE_TITLE

    register_fonts()
    previous_title = ACTIVE_TITLE
    previous_subtitle = ACTIVE_SUBTITLE
    previous_label = ACTIVE_LABEL
    ACTIVE_TITLE = title or PROJECT_TITLE
    ACTIVE_SUBTITLE = subtitle or PROJECT_SUBTITLE
    ACTIVE_LABEL = label or PROJECT_LABEL
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    c.setTitle(ACTIVE_TITLE)
    c.setAuthor("Choi Byungchan")
    c.setSubject(ACTIVE_LABEL)
    try:
        for slide in SLIDES:
            slide(c)
            c.showPage()
        c.save()
    finally:
        ACTIVE_TITLE = previous_title
        ACTIVE_SUBTITLE = previous_subtitle
        ACTIVE_LABEL = previous_label
    return path


if __name__ == "__main__":
    built = build_pdf()
    same_output = LEGACY_PDF_PATH == built
    if not same_output:
        shutil.copyfile(built, LEGACY_PDF_PATH)
    same_version_output = VERSION_PDF_PATH == built
    if not same_version_output:
        shutil.copyfile(built, VERSION_PDF_PATH)
    variant_paths = []
    for variant_path, title, subtitle, label in TITLE_VARIANTS:
        variant_paths.append(
            build_pdf(variant_path, title=title, subtitle=subtitle, label=label)
        )
    print(built)
    print(LEGACY_PDF_PATH)
    print(VERSION_PDF_PATH)
    for variant_path in variant_paths:
        print(variant_path)
