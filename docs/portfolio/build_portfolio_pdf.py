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
PROJECT_TITLE = "검증 가능한 문서 RAG 백엔드"
PROJECT_SUBTITLE = "후보 검색 · 원문 근거 · 답변 제어 · 실행 Trace"
PROJECT_LABEL = "Verifiable Document RAG Backend"
PROJECT_SECTION = "AI 백엔드 / 문서 RAG / 실행 Trace"

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
TOTAL_PAGES = 8
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
    c.drawString(MARGIN_X, PAGE_H - 25, PROJECT_TITLE)
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
    c.drawString(MARGIN_X, 360, PROJECT_TITLE)
    c.setFillColor(TEAL)
    c.setFont(FONT_BOLD, 16)
    draw_wrapped(c, PROJECT_SUBTITLE, MARGIN_X, 314, 820, font=FONT_BOLD, size=16, leading=22, color=TEAL)
    c.setFillColor(MUTED)
    c.setFont(FONT_BOLD, 10.5)
    c.drawString(MARGIN_X, 266, PROJECT_LABEL)
    cover_rows = [
        ("Input", "PDF · XLSX · Text"),
        ("Backend", "Job API · Worker · Retrieval"),
        ("Guard", "Citation · Stop · Trace"),
    ]
    card_w = 260
    for idx, (label, value) in enumerate(cover_rows):
        x = MARGIN_X + idx * (card_w + 22)
        draw_metric_box(c, x, 232, card_w, 76, label, value, accent=[ACCENT, TEAL, GREEN][idx], value_size=13.2)
    x = MARGIN_X
    for chip, color in [
        ("PDF/XLSX/Text", TEAL),
        ("Retrieval", ACCENT),
        ("Evidence Validation", GREEN),
        ("Agent Runtime", AMBER),
        ("Trace", TEAL),
        ("Contract Test", ACCENT),
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


def result_examples(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 2, "실제 실행 결과", section="결과물")
    intro = "Question · Evidence · Answer · Citation"
    draw_wrapped(c, intro, MARGIN_X, y + 4, 840, size=15, leading=22, color=MUTED)

    panel_x = MARGIN_X
    panel_y = y - 44
    panel_w = 540
    panel_h = 276
    c.setFillColor(HexColor("#EEF2F6"))
    c.roundRect(panel_x + 3, panel_y - panel_h - 3, panel_w, panel_h, 10, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setStrokeColor(HexColor("#D4DEE8"))
    c.roundRect(panel_x, panel_y - panel_h, panel_w, panel_h, 10, fill=1, stroke=1)
    c.setFillColor(HexColor("#F3F6F9"))
    c.roundRect(panel_x, panel_y - 36, panel_w, 36, 10, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 12.5)
    c.drawString(panel_x + 18, panel_y - 23, "Document QA Preview")
    c.setFillColor(GREEN)
    c.roundRect(panel_x + panel_w - 128, panel_y - 27, 108, 18, 4, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 8.8)
    c.drawCentredString(panel_x + panel_w - 74, panel_y - 22, "citation verified")

    content_x = panel_x + 22
    content_y = panel_y - 62
    content_w = panel_w - 44
    content_y = draw_kv_result(
        c,
        content_x,
        content_y,
        content_w,
        "Question",
        "2019년 2월 5호선의 승차총승객수는 몇 명입니까?",
        label_color=ACCENT,
        value_size=13,
    )
    content_y -= 12
    content_y = draw_kv_result(
        c,
        content_x,
        content_y,
        content_w,
        "Evidence",
        "철도 sheet / range A352:D401 / cell D352 / display value 15,446,522",
        label_color=TEAL,
        value_size=12.4,
    )
    content_y -= 12
    content_y = draw_kv_result(
        c,
        content_x,
        content_y,
        content_w,
        "Answer",
        "15,446,522명",
        label_color=GREEN,
        value_size=13,
    )
    content_y -= 12
    draw_kv_result(
        c,
        content_x,
        content_y,
        content_w,
        "Citation",
        "철도!D352, range A352:D401",
        label_color=AMBER,
        value_size=12.4,
    )

    draw_code_panel(
        c,
        MARGIN_X + 568,
        panel_y,
        274,
        276,
        "API RESPONSE",
        [
            "{",
            '  "status": "answered",',
            '  "source_family": "XLSX",',
            '  "answer": "15,446,522명",',
            '  "citation": {',
            '    "sheet": "철도",',
            '    "range": "A352:D401",',
            '    "cell": "D352"',
            "  },",
            '  "citation_verified": true',
            "}",
        ],
        font_size=8.2,
        leading=12.0,
    )
    draw_wrapped(
        c,
        "근거: README · XLSX 예시 · 계약 테스트",
        MARGIN_X,
        74,
        840,
        size=12.8,
        leading=18,
        color=TEAL,
        font=FONT_BOLD,
    )


def problem(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 7, "배경", section="배경")
    items = [
        "PDF 표 / Excel 셀 / Text chunk 위치 손실",
        "Vector 후보와 답변 근거 구분",
        "파싱 / 인덱싱 / 검색 / 답변 실패 지점 분리",
        "근거 부족 답변 차단",
    ]
    for idx, item in enumerate(items, 1):
        box_y = y - idx * 64 + 34
        c.setFillColor(SOFT if idx % 2 else WHITE)
        c.setStrokeColor(HexColor("#DCE4EC"))
        c.roundRect(MARGIN_X, box_y - 44, 820, 44, 6, fill=1, stroke=1)
        c.setFillColor(ACCENT)
        c.setFont(FONT_BOLD, 16)
        c.drawString(MARGIN_X + 16, box_y - 28, f"{idx}.")
        c.setFillColor(INK)
        c.setFont(FONT_BOLD, 16)
        c.drawString(MARGIN_X + 54, box_y - 28, item)
    footer = "문서 구조 · 비동기 처리 · 근거 판단 · 실패 추적"
    draw_wrapped(c, footer, MARGIN_X, 84, 820, size=16, leading=24, color=TEAL)


def system_structure(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 4, "시스템 구조", section="구조")
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
        5,
        "후보 -> 근거 -> 답변",
        section="문제 및 해결방안",
    )
    c.setFillColor(TEAL)
    c.setFont(FONT_BOLD, 21)
    c.drawString(MARGIN_X, y, "검색 후보와 답변 근거 분리")
    flow_y = y - 58
    cards = [
        ("1", "검색 후보", "관련 문서 조각", ACCENT),
        ("2", "원문 근거", "PDF page / Excel cell / Text chunk", TEAL),
        ("3", "답변 가능 여부", "필요 값 · 범위 · locator", GREEN),
        ("4", "답변 또는 중단", "answer + citation · stopped", AMBER),
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
            ["단계", "화면 결과", "구현 포인트"],
            ["검색 후보", "문서 후보 목록", "vector · keyword · table"],
            ["원문 근거", "page · sheet/range/cell · chunk", "locator 재확인"],
            ["답변 판단", "answered / stopped", "근거 부족 -> 중단"],
        ],
        font_size=11.2,
        header_size=12,
        leading=15,
        pad_y=8,
    )

def trace_layer(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 6, "Trace / API", section="Trace")
    intro = "Tool · Evidence · Decision · Redacted refs"
    draw_wrapped(c, intro, MARGIN_X, y + 4, 840, size=14.5, leading=21, color=INK)
    flow_y = y - 72
    flow = ["Request", "Policy", "Tools", "Evidence", "Decision", "Trace"]
    widths = [84, 86, 82, 104, 98, 82]
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
        "Trace 확인",
        [
            "tool: retrieve_xlsx_table",
            "flow: request -> tools -> evidence -> decision",
            "refs: query_ref / evidence_ref",
            "decision: answered / stopped",
            "hidden: raw question · evidence · local path",
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
            '  "request_context": {',
            '    "source_family": "XLSX",',
            '    "answer_format_requirement": "answer_with_citations_or_abstain"',
            "  },",
            '  "selected_tools": [',
            '    "retrieve_xlsx_table", "validate_evidence",',
            '    "classify_answerability"',
            "  ],",
            '  "evidence_ids": ["evidence_ref:01"],',
            '  "policy_decision": "allow_diagnostic",',
            '  "final_decision": "diagnostic_only_answer"',
            "}",
        ],
        font_size=7.8,
        leading=10.8,
    )


def verified_scope(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 3, "숫자로 보는 결과", section="결과")
    intro = "산출물 기준 · 숫자 · 계약 테스트"
    draw_wrapped(c, intro, MARGIN_X, y + 4, 840, size=15, leading=22, color=MUTED)

    card_w = 410
    card_h = 78
    gap_x = 22
    gap_y = 18
    start_y = y - 42
    proofs = [
        ("문서 유형", "3 types", "PDF / XLSX / TEXT", ACCENT),
        ("검색 후보", "300 rows", "PDF 100 / TEXT 100 / XLSX 100", TEAL),
        ("응답 스모크", "29 rows", "10 answered · 10 citation verified · 19 stopped", GREEN),
        ("계약 테스트", "51 passed", "runtime · retrieval · trace contracts", AMBER),
    ]
    for idx, (label, value, desc, color) in enumerate(proofs):
        col = idx % 2
        row = idx // 2
        x = MARGIN_X + col * (card_w + gap_x)
        top = start_y - row * (card_h + gap_y)
        c.setFillColor(WHITE)
        c.setStrokeColor(HexColor("#D7E1EA"))
        c.roundRect(x, top - card_h, card_w, card_h, 7, fill=1, stroke=1)
        c.setFillColor(color)
        c.setFont(FONT_BOLD, 10.5)
        c.drawString(x + 22, top - 24, label)
        c.setFillColor(INK)
        c.setFont(FONT_BOLD, 20)
        c.drawString(x + 22, top - 50, value)
        c.setFillColor(MUTED)
        c.setFont(FONT_BOLD, 11.2)
        c.drawRightString(x + card_w - 22, top - 50, desc)

    scope_y = start_y - card_h * 2 - gap_y - 42
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 16)
    c.drawString(MARGIN_X, scope_y, "구현한 흐름")
    flow = [
        ("문서 구조 보존", "page · cell/range · chunk"),
        ("후보 검색", "vector · keyword · table"),
        ("근거 확인", "citation verified"),
        ("Trace / Test", "JSON report · contract"),
    ]
    flow_w = 196
    flow_gap = 16
    flow_top = scope_y - 28
    for idx, (title, body) in enumerate(flow):
        x = MARGIN_X + idx * (flow_w + flow_gap)
        draw_flow_box(c, x, flow_top, flow_w, 48, title, fill=WHITE, title_size=10.6)
        c.setFillColor(MUTED)
        c.setFont(FONT_REGULAR, 9.6)
        c.drawCentredString(x + flow_w / 2, flow_top - 38, body)
        if idx < len(flow) - 1:
            draw_arrow(c, x + flow_w + 4, flow_top - 24, x + flow_w + flow_gap - 8, flow_top - 24, color=ACCENT)


def closing(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 8, "마무리", section="마무리")
    intro = "Result-first · Evidence-grounded · Backend-focused"
    draw_wrapped(c, intro, MARGIN_X, y + 4, 840, size=15, leading=22, color=MUTED)
    cards = [
        ("핵심 결과", "Q -> Evidence -> Answer -> API"),
        ("백엔드 초점", "Job API · Worker · Retrieval · Trace"),
        ("검증 방식", "citation · stop · contract"),
    ]
    card_w = 264
    gap = 24
    top = y - 60
    for idx, (title, body) in enumerate(cards):
        x = MARGIN_X + idx * (card_w + gap)
        c.setFillColor(WHITE)
        c.setStrokeColor(HexColor("#D7E1EA"))
        c.roundRect(x, top - 126, card_w, 126, 8, fill=1, stroke=1)
        c.setFillColor([ACCENT, TEAL, GREEN][idx])
        c.setFont(FONT_BOLD, 11)
        c.drawString(x + 22, top - 30, f"0{idx + 1}")
        c.setFillColor(INK)
        c.setFont(FONT_BOLD, 17)
        c.drawString(x + 22, top - 58, title)
        draw_wrapped(c, body, x + 22, top - 86, card_w - 44, size=11.6, leading=16, color=MUTED, font=FONT_BOLD)
    draw_table(
        c,
        MARGIN_X,
        top - 176,
        [176, 664],
        [
            ["구분", "요약"],
            ["Portfolio", "실제 실행 결과와 산출물 숫자 우선"],
            ["Repository", REPO_URL],
            ["Next", "권한 검색 · 문서 버전 · 장기 regression · 운영 모니터링"],
        ],
        font_size=11.4,
        header_size=12.2,
        leading=16,
        pad_y=8,
    )


SLIDES = [
    cover,
    result_examples,
    verified_scope,
    system_structure,
    evidence_split,
    trace_layer,
    problem,
    closing,
]


def build_pdf(path: Path = PDF_PATH) -> Path:
    register_fonts()
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    c.setTitle(PROJECT_TITLE)
    c.setAuthor("Choi Byungchan")
    c.setSubject(PROJECT_LABEL)
    for slide in SLIDES:
        slide(c)
        c.showPage()
    c.save()
    return path


if __name__ == "__main__":
    built = build_pdf()
    same_output = LEGACY_PDF_PATH == built
    if not same_output:
        shutil.copyfile(built, LEGACY_PDF_PATH)
    same_version_output = VERSION_PDF_PATH == built
    if not same_version_output:
        shutil.copyfile(built, VERSION_PDF_PATH)
    print(built)
    print(LEGACY_PDF_PATH)
    print(VERSION_PDF_PATH)
