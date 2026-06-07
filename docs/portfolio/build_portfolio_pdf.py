"""Build the AI Document QA backend portfolio PDF.

The PDF is authored directly with ReportLab so text remains selectable and
searchable. Run from the repository root:

    python docs/portfolio/build_portfolio_pdf.py
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Sequence

from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs" / "portfolio"
PDF_PATH = OUT_DIR / "choi_byungchan_ai_document_qa_backend_portfolio.pdf"

PAGE_W = 960
PAGE_H = 540
MARGIN_X = 54
TOP = 498
BOTTOM = 42

FONT_REGULAR = "Malgun"
FONT_BOLD = "MalgunBold"

INK = HexColor("#1E2933")
MUTED = HexColor("#64707D")
LIGHT = HexColor("#E8EDF2")
SOFT = HexColor("#F6F8FA")
ACCENT = HexColor("#1464C8")
TEAL = HexColor("#0B7A82")
GREEN = HexColor("#2E7D55")
RED = HexColor("#B43A34")
AMBER = HexColor("#B7791F")
DARK = HexColor("#15202B")
WHITE = HexColor("#FFFFFF")

REPO_URL = "https://github.com/sfr9802/async-ai-document-pipeline-with-domain-rag"
TOTAL_PAGES = 14


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
    c.setStrokeColor(LIGHT)
    c.setLineWidth(1)
    c.line(MARGIN_X, PAGE_H - 38, PAGE_W - MARGIN_X, PAGE_H - 38)
    c.line(MARGIN_X, 28, PAGE_W - MARGIN_X, 28)
    c.setFillColor(MUTED)
    c.setFont(FONT_BOLD, 9)
    c.drawString(MARGIN_X, PAGE_H - 25, "Evidence-Grounded Document QA Backend")
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
    c.setFont(FONT_BOLD, 28)
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
    c.setFillColor(SOFT)
    c.setStrokeColor(HexColor("#D5DDE5"))
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
        c.circle(x + 4, y - 5, 3, fill=1, stroke=0)
        y = draw_wrapped(c, item, x + 18, y, width - 18, size=size, leading=leading, color=color)
        y -= 8
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
    c.setFillColor(WHITE)
    c.setStrokeColor(HexColor("#D9E1E8"))
    c.roundRect(x, y - h, w, h, 6, fill=1, stroke=1)
    c.setFillColor(accent)
    c.rect(x, y - 4, w, 4, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, title_size)
    c.drawString(x + 16, y - 28, title)
    draw_bullets(c, list(body), x + 16, y - 54, w - 32, size=body_size, leading=17, bullet_color=accent)


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
    header_fill=HexColor("#EDF3F8"),
    grid=HexColor("#D7DFE8"),
) -> float:
    y = y_top
    table_w = sum(col_widths)
    for row_idx, row in enumerate(rows):
        is_header = row_idx == 0
        font = FONT_BOLD if is_header else FONT_REGULAR
        size = header_size if is_header else font_size
        wrapped = [wrap_text(cell, font, size, w - pad_x * 2) for cell, w in zip(row, col_widths)]
        row_h = max((len(lines) or 1) * leading + pad_y * 2 for lines in wrapped)
        c.setFillColor(header_fill if is_header else WHITE)
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
    fill=SOFT,
    stroke=HexColor("#D7DFE8"),
    title_size: float = 12,
) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.roundRect(x, y - h, w, h, 6, fill=1, stroke=1)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, title_size)
    lines = wrap_text(title, FONT_BOLD, title_size, w - 16)
    ty = y - 18
    for line in lines[:2]:
        c.drawCentredString(x + w / 2, ty, line)
        ty -= title_size + 3


def cover(c: canvas.Canvas) -> None:
    draw_footer(c, 1, "Backend / LLM-RAG Pipeline")
    c.setFillColor(ACCENT)
    c.rect(0, PAGE_H - 7, PAGE_W, 7, fill=1, stroke=0)
    c.setFillColor(ACCENT)
    c.setFont(FONT_BOLD, 20)
    c.drawString(MARGIN_X, 404, "근거 검증형 AI 문서 QA 백엔드")
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 42)
    c.drawString(MARGIN_X, 348, "Evidence-Grounded")
    c.drawString(MARGIN_X, 298, "Document QA Backend")
    subtitle = (
        "PDF/XLSX/Text 문서의 비동기 처리, 검색 후보 생성, "
        "EvidenceBundle 기반 답변, fail-closed 정책을 분리한 LLM 백엔드 파이프라인"
    )
    draw_wrapped(c, subtitle, MARGIN_X, 246, 620, size=15, leading=23, color=MUTED)
    x = MARGIN_X
    for chip, color in [
        ("Async Job", ACCENT),
        ("PDF/XLSX/Text", TEAL),
        ("Hybrid Retrieval", GREEN),
        ("EvidenceBundle", AMBER),
        ("Citation Verification", ACCENT),
        ("fail-closed", RED),
    ]:
        x = draw_chip(c, chip, x, 176, color=color)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 13)
    c.drawString(MARGIN_X, 116, "GitHub")
    c.setFont(FONT_REGULAR, 12)
    c.setFillColor(MUTED)
    c.drawString(MARGIN_X + 58, 116, REPO_URL)
    c.setFillColor(ACCENT)
    c.setFont(FONT_BOLD, 14)
    c.drawString(MARGIN_X, 82, "Backend / LLM-RAG Pipeline")
    c.setStrokeColor(HexColor("#DCE4EC"))
    c.setLineWidth(1.2)
    x0 = 690
    y0 = 360
    steps = ["Job", "Parse", "Retrieve", "Evidence", "Answer"]
    for i, step in enumerate(steps):
        yy = y0 - i * 54
        draw_flow_box(c, x0, yy, 178, 34, step, fill=WHITE, title_size=12)
        if i < len(steps) - 1:
            c.setStrokeColor(ACCENT)
            c.line(x0 + 89, yy - 34, x0 + 89, yy - 50)
            path = c.beginPath()
            path.moveTo(x0 + 89, yy - 54)
            path.lineTo(x0 + 84, yy - 46)
            path.lineTo(x0 + 94, yy - 46)
            path.close()
            c.setFillColor(ACCENT)
            c.drawPath(path, fill=1, stroke=0)


def summary(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 2, "30초 요약", section="요약")
    text = (
        "문서 업로드부터 파싱, 인덱싱, 검색, 답변 생성, citation 검증까지를 "
        "Job ID 기반 비동기 백엔드 흐름으로 분리했습니다.\n"
        "PDF/XLSX/Text 문서 구조를 보존하고, 검색 후보와 답변 근거를 분리해 "
        "근거가 부족한 경우 fail-closed로 응답하도록 설계했습니다."
    )
    y = draw_wrapped(c, text, MARGIN_X, y, 828, size=17, leading=27, color=INK)
    items = [
        "확장 - Text-only RAG를 PDF page/table, XLSX sheet/range/cell, Text chunk 단위로 확장",
        "분리 - API 요청, 비동기 작업, 문서 파싱, 검색, 답변 생성을 단계별로 분리",
        "제어 - Vector, Keyword, Metadata, Table Search를 질문 유형별로 조합",
        "방어 - 근거 부족, locator 모호성, 범위 과다 요청은 답변 생성 전에 fail-closed",
    ]
    y -= 26
    draw_bullets(c, items, MARGIN_X + 6, y, 820, size=16, leading=24, bullet_color=ACCENT)


def problem(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 3, "문제 정의", section="요약")
    items = [
        "Text 중심 처리로 인한 PDF/XLSX 구조 손실",
        "대형 문서 처리 지연과 실패 추적 어려움",
        "단일 Vector Search의 한계",
        "검색 후보와 실제 답변 근거의 혼동",
        "테스트셋에만 맞춘 성능 착시",
    ]
    for idx, item in enumerate(items, 1):
        box_y = y - idx * 54 + 28
        c.setFillColor(SOFT if idx % 2 else WHITE)
        c.setStrokeColor(HexColor("#DCE4EC"))
        c.roundRect(MARGIN_X, box_y - 38, 820, 38, 6, fill=1, stroke=1)
        c.setFillColor(ACCENT)
        c.setFont(FONT_BOLD, 16)
        c.drawString(MARGIN_X + 16, box_y - 25, f"{idx}.")
        c.setFillColor(INK)
        c.setFont(FONT_BOLD, 16)
        c.drawString(MARGIN_X + 54, box_y - 25, item)
    footer = (
        "문제는 검색 정확도 하나가 아니라 문서 형식, 처리 흐름, 근거 판단, "
        "평가 방식이 동시에 섞이는 데서 발생했습니다."
    )
    draw_wrapped(c, footer, MARGIN_X, 84, 820, size=16, leading=24, color=TEAL)


def component_map(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 4, "Backend Component Map", section="구조")
    col_w = 264
    gap = 24
    x1 = MARGIN_X
    x2 = x1 + col_w + gap
    x3 = x2 + col_w + gap
    card_y = y + 4
    card_h = 306
    draw_card(
        c,
        x1,
        card_y,
        col_w,
        card_h,
        "API Server",
        [
            "문서 업로드 요청 수락",
            "Job 생성 및 상태 조회",
            "결과 artifact 조회",
            "사용자 요청/응답 DTO 관리",
        ],
        accent=ACCENT,
    )
    draw_card(
        c,
        x2,
        card_y,
        col_w,
        card_h,
        "AI Worker",
        [
            "PDF/XLSX/Text 파싱",
            "SearchUnit/SearchView 생성",
            "Embedding / FAISS / BM25 / Hybrid retrieval",
            "SourceAtom/EvidenceBundle hydration",
            "answer rendering / citation verification",
        ],
        accent=TEAL,
    )
    draw_card(
        c,
        x3,
        card_y,
        col_w,
        card_h,
        "Storage / Async Control",
        [
            "PostgreSQL: job/document metadata, result state",
            "Redis signal: worker dispatch and status signal",
            "Artifact files: diagnostic report, evidence bundle, failure taxonomy",
        ],
        accent=GREEN,
    )
    note = (
        "구현 증거가 있는 스택과 비동기 제어만 본문에 배치했습니다. "
        "운영 배포, live-readiness, product-success 주장은 열지 않았습니다."
    )
    draw_wrapped(c, note, MARGIN_X, 80, 840, size=12.5, leading=18, color=MUTED)


def architecture(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 5, "전체 시스템 아키텍처", section="구조")
    top_y = y + 12
    xs = [70, 232, 394, 556, 718]
    labels = ["사용자/화면", "Spring Boot API", "Job 상태 저장", "Worker Dispatch", "FastAPI Worker"]
    for x, label in zip(xs, labels):
        draw_flow_box(c, x, top_y, 128, 48, label, fill=WHITE, title_size=11.5)
    for i in range(len(xs) - 1):
        draw_arrow(c, xs[i] + 128, top_y - 24, xs[i + 1] - 8, top_y - 24, color=ACCENT)
    c.setFillColor(ACCENT)
    c.setFont(FONT_BOLD, 12)
    c.drawString(MARGIN_X, top_y + 14, "Flow 1")

    bottom_y = top_y - 132
    xs2 = [72, 220, 368, 516, 664, 812]
    labels2 = ["문서 파싱", "SearchUnit", "SearchView", "SourceAtom/\nEvidenceBundle", "답변 + citation", "answer/\nfail-closed"]
    widths2 = [112, 112, 112, 128, 122, 92]
    colors2 = [SOFT, SOFT, HexColor("#EEF6F6"), HexColor("#FFF8E8"), HexColor("#EEF3FA"), HexColor("#FFF1F0")]
    for x, w, label, fill in zip(xs2, widths2, labels2, colors2):
        draw_flow_box(c, x, bottom_y, w, 52, label, fill=fill, title_size=10.5)
    for i in range(len(xs2) - 1):
        draw_arrow(c, xs2[i] + widths2[i], bottom_y - 26, xs2[i + 1] - 8, bottom_y - 26, color=TEAL)
    c.setFillColor(TEAL)
    c.setFont(FONT_BOLD, 12)
    c.drawString(MARGIN_X, bottom_y + 14, "Flow 2")

    explanation = (
        "API 서버는 요청 수락, Job 생성, 상태 조회를 담당하고, AI Worker는 긴 문서 파싱, "
        "인덱싱, 검색, 답변 생성처럼 실패와 지연이 큰 작업을 분리해 처리합니다."
    )
    draw_wrapped(c, explanation, MARGIN_X, 118, 840, size=15, leading=22, color=INK)


def async_pipeline(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 6, "비동기 문서 처리 파이프라인", section="구조")
    steps = [
        ("1", "job 생성", "작업 ID와 초기 상태 생성"),
        ("2", "claim-before-execute", "중복 실행 방지 및 작업 소유권 확보"),
        ("3", "dispatch", "worker 처리 요청"),
        ("4", "parse/index", "문서 형식별 파싱, 검색 단위 생성"),
        ("5", "result artifact", "답변, 근거, 실패 사유, 진단 결과 저장"),
    ]
    x = MARGIN_X
    w = 158
    gap = 20
    for idx, (num, title, body) in enumerate(steps):
        draw_flow_box(c, x, y + 20, w, 168, "", fill=WHITE)
        c.setFillColor(ACCENT if idx < 4 else TEAL)
        c.circle(x + 28, y - 10, 16, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(FONT_BOLD, 14)
        c.drawCentredString(x + 28, y - 15, num)
        c.setFillColor(INK)
        c.setFont(FONT_BOLD, 14)
        c.drawString(x + 16, y - 48, title)
        draw_wrapped(c, body, x + 16, y - 76, w - 32, size=11.5, leading=16, color=MUTED)
        if idx < 4:
            draw_arrow(c, x + w + 2, y - 60, x + w + gap - 4, y - 60, color=ACCENT)
        x += w + gap
    message = "요청은 짧게, 처리는 추적 가능하게, 실패는 단계별로 남기는 구조입니다."
    draw_wrapped(c, message, MARGIN_X, 100, 840, size=18, leading=26, color=TEAL, font=FONT_BOLD)


def api_design(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 7, "API 설계", section="구조")
    rows = [
        ["Route", "역할", "구현 상태"],
        ["POST /api/v1/library/source-files", "문서 업로드 및 source file 등록", "Spring Boot API 구현"],
        ["POST /api/v1/jobs", "Text/file 입력 기반 Job 생성과 enqueue", "Spring Boot API 구현"],
        ["GET /api/v1/jobs/{jobId}", "작업 상태와 claim 상태 조회", "Spring Boot API 구현"],
        ["GET /api/v1/jobs/{jobId}/result", "작업 결과와 artifact 목록 조회", "Spring Boot API 구현"],
        ["GET /api/v1/artifacts/{id}/content", "결과 artifact 다운로드", "Spring Boot API 구현"],
        ["POST /api/internal/jobs/claim", "worker claim과 작업 소유권 확보", "내부 API 구현"],
        ["POST /api/internal/jobs/callback", "worker 완료 callback과 결과 상태 반영", "내부 API 구현"],
        ["POST /api/rag/query", "문서 기반 QA preview bridge", "default-off non-production preview"],
    ]
    draw_table(c, MARGIN_X, y + 8, [250, 320, 250], rows, font_size=10.2, header_size=11.2, leading=13.5)
    note = "SSE/WebSocket 스트리밍 route는 구현 증거가 없어 본문 API가 아니라 보완 예정으로 분리했습니다."
    draw_wrapped(c, note, MARGIN_X, 70, 840, size=12.5, leading=18, color=MUTED)


def structure_preservation(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 8, "문서 형식별 구조 보존", section="근거")
    rows = [
        ["형식", "보존한 구조", "답변 검증에서 쓰는 방식"],
        ["PDF", "page, paragraph, table context, page citation", "답변 citation을 문서 페이지와 표 주변 정보로 확인"],
        ["XLSX", "sheet, range, row, column, header, cell display value", "셀 값 응답과 표 범위 응답을 분리하고 추적"],
        ["Text", "chunk, source context, locator", "서술형 문맥의 근거 위치 확인"],
    ]
    draw_table(c, MARGIN_X, y + 10, [130, 360, 350], rows, font_size=13, header_size=13.5, leading=19, pad_y=13)
    message = "문서를 단순 문자열로 변환하지 않고, 답변 검증에 필요한 위치와 표시값을 함께 보존했습니다."
    draw_wrapped(c, message, MARGIN_X, 92, 840, size=17, leading=25, color=TEAL, font=FONT_BOLD)


def evidence_split(c: canvas.Canvas) -> None:
    y = draw_page_title(
        c,
        9,
        "Vector Search 결과를 바로 답변 근거로 쓰지 않았습니다",
        section="근거",
    )
    c.setFillColor(TEAL)
    c.setFont(FONT_BOLD, 22)
    c.drawString(MARGIN_X, y, "\"검색되었다\"와 \"답변할 수 있다\"를 분리했습니다.")
    flow_y = y - 56
    flow = ["검색 결과", "후보 근거", "원문 근거 hydration", "답변용 근거", "충분성 판단", "답변 또는 fail-closed"]
    x = MARGIN_X
    widths = [94, 94, 150, 114, 114, 146]
    for idx, (label, w) in enumerate(zip(flow, widths)):
        draw_flow_box(c, x, flow_y, w, 42, label, fill=WHITE, title_size=10.5)
        if idx < len(flow) - 1:
            draw_arrow(c, x + w + 2, flow_y - 21, x + w + 20, flow_y - 21, color=ACCENT)
        x += w + 28
    rows = [
        ["구분", "의미", "정책"],
        ["검색 결과", "관련 있어 보이는 문서 조각 후보", "바로 답변 근거로 쓰지 않음"],
        ["원문 근거", "PDF page, XLSX cell/range, Text chunk", "사용자가 확인할 수 있어야 함"],
        ["답변용 근거", "질문에 필요한 범위와 값이 충분한 근거", "부족하면 fail-closed"],
    ]
    draw_table(c, MARGIN_X, flow_y - 78, [150, 410, 280], rows, font_size=12.3, header_size=13, leading=18, pad_y=10)
    c.setFillColor(MUTED)
    c.setFont(FONT_BOLD, 12)
    c.drawString(MARGIN_X, 62, "SearchView/vector payload = candidate only")
    c.setFillColor(TEAL)
    c.drawString(MARGIN_X + 330, 62, "SourceAtom/EvidenceBundle = evidence truth")


def retrieval_control(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 10, "질문 유형별 검색/답변 제어", section="근거")
    draw_card(
        c,
        MARGIN_X,
        y + 6,
        274,
        254,
        "Retrieval",
        [
            "Vector Search: 서술형 의미 유사도와 문맥 후보 탐색",
            "Keyword Search: 고유명사, 항목명, 수치, 날짜 단서 확인",
            "Metadata Search: 파일, page, sheet 등 위치 단서 사용",
            "Table Search: 행/열/헤더/셀 표시값이 필요한 표 기반 질문",
        ],
        accent=ACCENT,
        body_size=11.3,
    )
    draw_card(
        c,
        MARGIN_X + 300,
        y + 6,
        246,
        254,
        "Post-processing",
        [
            "후보 병합",
            "중복 제거",
            "후보 재정렬",
            "evidence hydration",
        ],
        accent=TEAL,
        body_size=12.5,
    )
    draw_card(
        c,
        MARGIN_X + 572,
        y + 6,
        268,
        254,
        "Answer Control",
        [
            "citation verification",
            "answerability check",
            "fail-closed",
        ],
        accent=RED,
        body_size=12.5,
    )
    message = "목표는 검색 도구 나열이 아니라, 질문이 요구하는 근거 형태를 먼저 좁히는 것입니다."
    draw_wrapped(c, message, MARGIN_X, 96, 840, size=17, leading=24, color=TEAL, font=FONT_BOLD)


def examples(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 11, "대표 질의응답 사례", section="근거")
    rows = [
        ["유형", "질문 / 응답 요약", "근거 또는 fail-closed 사유"],
        [
            "PDF 성공",
            "Q. 2020년 한국 원/달러 기말 환율은 얼마인가요?\nA. 2020년 한국 원/달러 기말 환율은 1,088.0원입니다.",
            "경제동향 PDF p.65 table citation",
        ],
        [
            "XLSX 성공",
            "Q. 2019년 2월 5호선 승차총승객수는 몇 명입니까?\nA. 2019년 2월 5호선의 승차총승객수는 15,446,522명입니다.",
            "철도 sheet, range A352:D401, cell D352 evidence",
        ],
        [
            "PDF 중단",
            "사업보고서 문맥이 얇은 사례",
            "PDF_CONTENT_WINDOW_TOO_THIN - 문서는 찾았지만 답변 문맥이 부족해 중단",
        ],
        [
            "XLSX 중단",
            "anchor가 부족한 사례",
            "XLSX_QUERY_ANCHOR_MISSING - 어떤 시트/범위/행을 기준으로 답할지 불명확해 중단",
        ],
        [
            "XLSX 중단",
            "과대 범위 요청",
            "UNSUPPORTED_RANGE_TOO_LARGE - 지나치게 넓은 범위 요청은 요약/계산 오류 위험 때문에 중단",
        ],
    ]
    draw_table(c, MARGIN_X, y + 8, [118, 446, 276], rows, font_size=10.5, header_size=11.5, leading=14, pad_y=8)
    draw_wrapped(
        c,
        "Text 예시는 채용 문서의 전문성을 떨어뜨리는 약한 사례를 제외하고, PDF/XLSX의 artifact-backed 사례에 집중했습니다.",
        MARGIN_X,
        64,
        840,
        size=11.5,
        leading=16,
        color=MUTED,
    )


def validation_boundary(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 12, "검증 경계와 내부 진단", section="평가")
    draw_card(
        c,
        MARGIN_X,
        y + 4,
        396,
        260,
        "검증한 것",
        [
            "SearchUnit/SearchView materialization",
            "FAISS/BM25/Hybrid candidate availability",
            "SourceAtom/EvidenceBundle hydration",
            "citation verification",
            "fail-closed reason taxonomy",
        ],
        accent=GREEN,
        body_size=12.5,
    )
    draw_card(
        c,
        MARGIN_X + 432,
        y + 4,
        408,
        260,
        "검증하지 않은 것",
        [
            "공식 answer-quality metric",
            "product-success claim",
            "production/live-readiness claim",
            "user-approved gold/qrels 기반 최종 성능 주장",
        ],
        accent=RED,
        body_size=12.5,
    )
    rows = [
        ["진단 수치", "의미"],
        ["300 SearchUnit/SearchView", "PDF/TEXT/XLSX 100개씩 source-derived materialization"],
        ["bge-m3 + FAISS smoke", "vector/BM25/hybrid 후보 availability 확인"],
        ["gold-29 smoke", "rendered 10 / citation_verified 10 / fail_closed 19"],
    ]
    draw_table(c, MARGIN_X, 156, [250, 590], rows, font_size=11.2, header_size=12, leading=15, pad_y=8)


def failure_taxonomy(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 13, "실패를 오답 하나로 보지 않았습니다", section="평가")
    quote = (
        "프롬프트를 특정 질문에 맞춰 고치는 대신, 실패 원인을 검색·정렬·문서 처리·답변 생성 단계로 분해했습니다."
    )
    y = draw_wrapped(c, quote, MARGIN_X, y + 4, 840, size=16, leading=24, color=TEAL, font=FONT_BOLD)
    cards = [
        ("후보 근거 부족", "검색 후보 안에 필요한 근거가 없음", ACCENT),
        ("후보 순위 문제", "근거는 있으나 top-k 안에서 밀림", TEAL),
        ("문서 구조 문제", "PDF 표, XLSX 행/열/축을 잘못 해석", AMBER),
        ("답변 생성 문제", "근거는 있으나 응답 조립 실패", GREEN),
        ("답변 불가 문제", "근거가 없거나 범위가 과도함", RED),
    ]
    x = MARGIN_X
    y_cards = y - 20
    for title, body, color in cards:
        draw_card(c, x, y_cards, 156, 112, title, [body], accent=color, title_size=12, body_size=10.5)
        x += 171
    rows = [
        ["검수 필요 항목", "질문"],
        ["근거 관련성", "근거가 질문에 실제로 관련 있는가"],
        ["답변 충분성", "해당 근거만으로 답할 수 있는가"],
        ["gold 채택 여부", "정답/근거를 gold로 채택할 수 있는가"],
    ]
    draw_table(c, MARGIN_X, 178, [220, 620], rows, font_size=12, header_size=12.5, leading=17, pad_y=8)


def result_limits(c: canvas.Canvas) -> None:
    y = draw_page_title(c, 14, "결과와 한계", section="마무리")
    draw_card(
        c,
        MARGIN_X,
        y + 8,
        400,
        294,
        "구현/정리한 부분",
        [
            "PDF/XLSX/Text 혼합 문서 처리",
            "Job ID 기반 비동기 처리",
            "문서 구조 보존",
            "질문 유형별 검색 제어",
            "검색 후보와 답변 근거 분리",
            "fail-closed 응답 정책",
            "실패 유형 분리와 검증 경계 정리",
        ],
        accent=ACCENT,
        body_size=12.2,
    )
    draw_card(
        c,
        MARGIN_X + 440,
        y + 8,
        400,
        294,
        "보완 예정",
        [
            "SSE/WebSocket 기반 스트리밍 응답",
            "권한 기반 검색",
            "문서 버전 관리",
            "장기 regression test",
            "운영 모니터링/알림",
            "사용자 검수 기반 gold/qrels 확장",
        ],
        accent=AMBER,
        body_size=12.2,
    )
    final = (
        "이 프로젝트는 \"RAG 성능 수치\"보다, AI 문서 QA 백엔드에서 검색 후보, 원문 근거, "
        "답변 생성, 실패 통제를 어떻게 분리할지에 초점을 맞췄습니다."
    )
    draw_wrapped(c, final, MARGIN_X, 92, 840, size=16, leading=24, color=TEAL, font=FONT_BOLD)


SLIDES = [
    cover,
    summary,
    problem,
    component_map,
    architecture,
    async_pipeline,
    api_design,
    structure_preservation,
    evidence_split,
    retrieval_control,
    examples,
    validation_boundary,
    failure_taxonomy,
    result_limits,
]


def build_pdf(path: Path = PDF_PATH) -> Path:
    register_fonts()
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    c.setTitle("근거 검증형 AI 문서 QA 백엔드")
    c.setAuthor("Choi Byungchan")
    c.setSubject("Evidence-Grounded Document QA Backend portfolio")
    for slide in SLIDES:
        slide(c)
        c.showPage()
    c.save()
    return path


if __name__ == "__main__":
    print(build_pdf())
