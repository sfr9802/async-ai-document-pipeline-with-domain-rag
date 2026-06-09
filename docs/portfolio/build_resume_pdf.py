"""Build the Korean AI backend / RAG / execution-trace resume PDF.

The resume is authored with ReportLab so the Korean and English text remains
selectable. Run from the repository root:

    python docs/portfolio/build_resume_pdf.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

try:
    from .build_portfolio_pdf import (
        ACCENT,
        AMBER,
        FONT_BOLD,
        FONT_REGULAR,
        GREEN,
        INK,
        LIGHT,
        MUTED,
        PAPER,
        RED,
        TEAL,
        WHITE,
        draw_wrapped,
        register_fonts,
        sw,
    )
except ImportError:
    from build_portfolio_pdf import (
        ACCENT,
        AMBER,
        FONT_BOLD,
        FONT_REGULAR,
        GREEN,
        INK,
        LIGHT,
        MUTED,
        PAPER,
        RED,
        TEAL,
        WHITE,
        draw_wrapped,
        register_fonts,
        sw,
    )


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs" / "portfolio"
PDF_PATH = OUT_DIR / "최병찬_AI 백엔드 엔지니어 이력서.pdf"

PAGE_W, PAGE_H = A4
MARGIN_X = 42
TOP = PAGE_H - 42
BOTTOM = 42


def draw_footer(c: canvas.Canvas, page_num: int, total_pages: int) -> None:
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setStrokeColor(LIGHT)
    c.setLineWidth(0.7)
    c.line(MARGIN_X, 28, PAGE_W - MARGIN_X, 28)
    c.setFillColor(MUTED)
    c.setFont(FONT_REGULAR, 8.5)
    c.drawString(MARGIN_X, 14, "AI 백엔드 엔지니어 | 문서 RAG · 비동기 처리 · 실행 추적")
    c.drawRightString(PAGE_W - MARGIN_X, 14, f"{page_num} / {total_pages}")


def draw_tag(c: canvas.Canvas, text: str, x: float, y: float, color=ACCENT) -> float:
    size = 8.5
    pad_x = 7
    width = sw(text, FONT_BOLD, size) + pad_x * 2
    c.setFillColor(WHITE)
    c.setStrokeColor(HexColor("#D6E0EA"))
    c.roundRect(x, y - 17, width, 17, 4, fill=1, stroke=1)
    c.setFillColor(color)
    c.setFont(FONT_BOLD, size)
    c.drawCentredString(x + width / 2, y - 11.5, text)
    return x + width + 6


def section_title(c: canvas.Canvas, title: str, x: float, y: float) -> float:
    c.setFillColor(ACCENT)
    c.setFont(FONT_BOLD, 12.5)
    c.drawString(x, y, title)
    c.setStrokeColor(HexColor("#D7E0E9"))
    c.line(x, y - 6, PAGE_W - MARGIN_X, y - 6)
    return y - 20


def bullets(c: canvas.Canvas, items: Sequence[str], x: float, y: float, width: float, *, size: float = 9.8) -> float:
    for item in items:
        c.setFillColor(ACCENT)
        c.circle(x + 3.5, y - 4.5, 2.1, fill=1, stroke=0)
        y = draw_wrapped(c, item, x + 13, y, width - 13, size=size, leading=size * 1.45, color=INK)
        y -= 4.5
    return y


def draw_header(c: canvas.Canvas) -> float:
    c.setFillColor(ACCENT)
    c.rect(0, PAGE_H - 6, PAGE_W, 6, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 24)
    c.drawString(MARGIN_X, TOP - 8, "최병찬")
    c.setFillColor(ACCENT)
    c.setFont(FONT_BOLD, 13.8)
    c.drawString(MARGIN_X, TOP - 36, "AI 백엔드 엔지니어 | 문서 RAG · 비동기 처리 · 실행 추적")
    c.setFillColor(MUTED)
    c.setFont(FONT_BOLD, 9.5)
    c.drawString(MARGIN_X, TOP - 57, "Evidence-Grounded RAG Backend with Execution Trace")
    x = MARGIN_X
    for tag, color in [
        ("Python/FastAPI", ACCENT),
        ("문서 RAG", TEAL),
        ("비동기 Job", GREEN),
        ("근거 검증", AMBER),
        ("실행 Trace", RED),
    ]:
        x = draw_tag(c, tag, x, TOP - 82, color=color)
    return TOP - 108


def page_one(c: canvas.Canvas) -> None:
    draw_footer(c, 1, 2)
    y = draw_header(c)

    y = section_title(c, "요약", MARGIN_X, y)
    summary = (
        "문서 기반 RAG와 비동기 작업 처리에 초점을 둔 AI 백엔드 엔지니어입니다. "
        "PDF·XLSX·Text 문서의 구조와 원문 위치를 보존하고, 검색 후보와 실제 답변 근거를 분리해 "
        "근거가 부족한 경우 답변을 중단하는 백엔드 구조를 설계했습니다. 최근에는 이 구조 위에 얇은 실행 추적 "
        "레이어를 추가해 도구 선택, 근거 검증, 답변 가능 여부, trace/report 흐름을 정리했습니다. "
        "Job ID, worker claim, idempotent result artifact처럼 실무적인 비동기 작업 소유권과 "
        "디버깅 가능한 상태 전이에 관심이 많습니다."
    )
    y = draw_wrapped(c, summary, MARGIN_X, y, PAGE_W - MARGIN_X * 2, size=9.8, leading=14.5, color=INK)
    y -= 10

    y = section_title(c, "대표 프로젝트 - 근거를 확인할 수 있는 AI 문서 QA 백엔드", MARGIN_X, y)
    y = bullets(
        c,
        [
            "PDF·XLSX·Text 문서를 형식별로 파싱하고, 원문 위치를 확인할 수 있도록 페이지·시트·범위·셀·chunk 정보를 보존했습니다.",
            "검색 후보와 실제 답변 근거를 분리해, 검색 결과를 바로 LLM 답변 근거로 사용하지 않도록 설계했습니다.",
            "질문 유형에 따라 vector search, keyword search, table search를 조합하고 후보 병합·중복 제거·재정렬 흐름을 구성했습니다.",
            "근거가 부족하거나 질문 범위가 모호한 경우 답변을 생성하지 않는 답변 중단 정책을 적용했습니다.",
            "기존 RAG 백엔드 위에 얇은 실행 추적 레이어를 추가해 도구 선택, 근거 검증, 답변 가능 여부, trace/report 흐름을 정리했습니다.",
            "pytest 기반 contract test와 JSON 검증으로 주요 구현 계약을 확인했습니다.",
            "Codex를 활용해 구현, 테스트, 문서 갱신을 반복하는 개발 workflow를 구성했습니다.",
        ],
        MARGIN_X,
        y,
        PAGE_W - MARGIN_X * 2,
        size=9.25,
    )
    y -= 4

    y = section_title(c, "백엔드 / 비동기 처리 경험", MARGIN_X, y)
    bullets(
        c,
        [
            "upload, job state, worker dispatch, callback, artifact download 흐름을 분리했습니다.",
            "Job ID와 worker claim lock으로 중복 실행 위험을 줄이고 실패를 추적 가능하게 만들었습니다.",
            "결과 artifact와 report를 남겨 RAG 실패를 검색, 근거, 답변 가능성 단계로 살펴볼 수 있게 했습니다.",
        ],
        MARGIN_X,
        y,
        PAGE_W - MARGIN_X * 2,
    )


def page_two(c: canvas.Canvas) -> None:
    draw_footer(c, 2, 2)
    y = TOP - 4

    y = section_title(c, "평가 / 추적 관점", MARGIN_X, y)
    y = bullets(
        c,
        [
            "Trace에는 원문 prompt/evidence를 그대로 저장하지 않고, 요청별 도구 선택과 근거 판단을 검토 가능한 형태로 남깁니다.",
            "검색 후보와 답변 근거를 분리하고, 별도 검수 전에는 공식 성능 수치나 최종 답변 품질 점수로 주장하지 않습니다.",
            "도구 미지원, 근거 부족, 질문 범위 모호성을 답변 중단 사유로 남깁니다.",
            "운영 준비 완료나 제품 성과는 이 이력서 범위에서 주장하지 않습니다.",
        ],
        MARGIN_X,
        y,
        PAGE_W - MARGIN_X * 2,
        size=9.35,
    )
    y -= 8

    y = section_title(c, "주요 산출물", MARGIN_X, y)
    y = bullets(
        c,
        [
            "실행 추적 레이어: ai/app/capabilities/rag_orchestrator/agentops_runtime.py",
            "Trace schema/sample: docs/agentops_trace_schema.json, reports/agentops_sample_trace.json",
            "Portfolio report: reports/portfolio_agentops_report.md",
            "진행 기록: docs/rag-ingestion-progress.md",
            "Contract tests: ai/tests/test_agentops_portfolio_runtime_contract.py",
        ],
        MARGIN_X,
        y,
        PAGE_W - MARGIN_X * 2,
        size=9.35,
    )
    y -= 8

    y = section_title(c, "기술 역량", MARGIN_X, y)
    left = [
        "Backend: Python, FastAPI, Spring Boot API surface",
        "RAG / LLM: SearchUnit/SearchView, FAISS/BM25/Hybrid retrieval",
        "AgentOps / LLMOps: tool registry, evidence validation, trace/report",
        "Document / Data: PDF page/table, XLSX sheet/range/cell, Text chunk locator",
        "Infra / Async: PostgreSQL, Redis, Job ID, worker claim, artifact state",
    ]
    right = [
        "근거 검증: SourceAtom/EvidenceBundle, citation/evidence boundary",
        "평가 거버넌스: 진단용 trace, 답변 중단, 사람 검수 gate",
        "구현/검증: pytest contract test와 JSON 검증",
        "문서화: ReportLab PDF generation, progress/report ledger",
        "협업 방식: Codex-assisted implementation/test/report workflow",
    ]
    col_w = (PAGE_W - MARGIN_X * 2 - 24) / 2
    left_y = bullets(c, left, MARGIN_X, y, col_w, size=9.4)
    right_y = bullets(c, right, MARGIN_X + col_w + 24, y, col_w, size=9.4)

    y = min(left_y, right_y) - 12
    y = section_title(c, "기타 경험은 보조로 정리", MARGIN_X, y)
    bullets(
        c,
        [
            "Discord bot, 일반 crawling, 단순 자동화 경험은 이번 지원 포지션과 직접 맞닿는 백엔드 신뢰성, traceability, RAG evidence 품질 중심으로만 언급합니다.",
            "이 이력서는 챗봇/크롤링 포트폴리오가 아니라 SIA AI Agents Platform Engineer coffee-chat에 맞춘 문서 RAG 백엔드와 실행 추적 중심 자료입니다.",
        ],
        MARGIN_X,
        y,
        PAGE_W - MARGIN_X * 2,
        size=9.4,
    )


def build_pdf(path: Path = PDF_PATH) -> Path:
    register_fonts()
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    c.setTitle("최병찬 - AI 백엔드 엔지니어 | 문서 RAG · 비동기 처리 · 실행 추적")
    c.setAuthor("Choi Byungchan")
    c.setSubject("Evidence-Grounded RAG Backend with Execution Trace resume")
    page_one(c)
    c.showPage()
    page_two(c)
    c.showPage()
    c.save()
    return path


if __name__ == "__main__":
    print(build_pdf())
