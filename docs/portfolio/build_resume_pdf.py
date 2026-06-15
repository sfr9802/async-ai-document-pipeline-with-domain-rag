"""Build the Korean AI engineer / agent engineer resume PDF.

The resume is authored with ReportLab so Korean and English text remains
selectable. Run from the repository root:

    python docs/portfolio/build_resume_pdf.py
"""

from __future__ import annotations

import shutil
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
PDF_PATH = OUT_DIR / "최병찬_AI_에이전트_엔지니어_이력서.pdf"
LEGACY_PDF_PATH = OUT_DIR / "최병찬_AI 백엔드 엔지니어 이력서.pdf"

PAGE_W, PAGE_H = A4
MARGIN_X = 38
TOP = PAGE_H - 38
BOTTOM = 39
CONTENT_W = PAGE_W - MARGIN_X * 2
FOOTER_LABEL = "AI Engineer / Agent Engineer | Evidence-Grounded RAG · Agent Guard · Async Backend"


def draw_footer(c: canvas.Canvas, page_num: int, total_pages: int) -> None:
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setStrokeColor(LIGHT)
    c.setLineWidth(0.7)
    c.line(MARGIN_X, 28, PAGE_W - MARGIN_X, 28)
    c.setFillColor(MUTED)
    c.setFont(FONT_REGULAR, 8)
    c.drawString(MARGIN_X, 14, FOOTER_LABEL)
    c.drawRightString(PAGE_W - MARGIN_X, 14, f"{page_num} / {total_pages}")


def draw_tag(c: canvas.Canvas, text: str, x: float, y: float, color=ACCENT) -> float:
    size = 8.1
    pad_x = 6.5
    width = sw(text, FONT_BOLD, size) + pad_x * 2
    c.setFillColor(WHITE)
    c.setStrokeColor(HexColor("#D6E0EA"))
    c.roundRect(x, y - 16, width, 16, 4, fill=1, stroke=1)
    c.setFillColor(color)
    c.setFont(FONT_BOLD, size)
    c.drawCentredString(x + width / 2, y - 11, text)
    return x + width + 5


def draw_tags(c: canvas.Canvas, tags: Sequence[tuple[str, object]], x: float, y: float, max_x: float) -> float:
    start_x = x
    line_y = y
    for tag, color in tags:
        width = sw(tag, FONT_BOLD, 8.1) + 13
        if x + width > max_x:
            x = start_x
            line_y -= 20
        x = draw_tag(c, tag, x, line_y, color=color)
    return line_y - 22


def section_title(c: canvas.Canvas, title: str, x: float, y: float) -> float:
    c.setFillColor(ACCENT)
    c.setFont(FONT_BOLD, 11.4)
    c.drawString(x, y, title)
    c.setStrokeColor(HexColor("#D7E0E9"))
    c.line(x, y - 5, PAGE_W - MARGIN_X, y - 5)
    return y - 17


def bullets(
    c: canvas.Canvas,
    items: Sequence[str],
    x: float,
    y: float,
    width: float,
    *,
    size: float = 8.7,
    leading: float | None = None,
    gap: float = 3.2,
    bullet_color=ACCENT,
) -> float:
    leading = leading or size * 1.36
    for item in items:
        c.setFillColor(bullet_color)
        c.circle(x + 3.1, y - 4.2, 1.8, fill=1, stroke=0)
        y = draw_wrapped(c, item, x + 12, y, width - 12, size=size, leading=leading, color=INK)
        y -= gap
    return y


def draw_small_line(c: canvas.Canvas, text: str, x: float, y: float, *, size: float = 8.2, color=MUTED) -> float:
    c.setFillColor(color)
    c.setFont(FONT_REGULAR, size)
    c.drawString(x, y, text)
    return y - size - 3.2


def draw_header(c: canvas.Canvas) -> float:
    c.setFillColor(ACCENT)
    c.rect(0, PAGE_H - 6, PAGE_W, 6, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 23)
    c.drawString(MARGIN_X, TOP - 4, "최병찬")
    c.setFillColor(ACCENT)
    c.setFont(FONT_BOLD, 12.9)
    c.drawString(MARGIN_X, TOP - 30, "AI Backend Engineer · Evidence-Grounded RAG · Agent Systems")
    c.setFillColor(MUTED)
    c.setFont(FONT_REGULAR, 8.7)
    c.drawString(MARGIN_X, TOP - 48, "010-2859-1364 | sfr9932@gmail.com | Daejeon, Korea")
    c.drawString(MARGIN_X, TOP - 62, "github.com/sfr9802 | arin-nya.tistory.com | linkedin.com/in/병찬-최-0031221b9")
    return draw_tags(
        c,
        [
            ("Python/FastAPI", ACCENT),
            ("Spring Boot", TEAL),
            ("Weaviate/Hybrid RAG", GREEN),
            ("SourceAtom/EvidenceBundle", AMBER),
            ("Agent Guard", RED),
            ("Codex Workflow", ACCENT),
        ],
        MARGIN_X,
        TOP - 82,
        PAGE_W - MARGIN_X,
    )


def draw_skill_column(c: canvas.Canvas, rows: Sequence[str], x: float, y: float, width: float) -> float:
    return bullets(c, rows, x, y, width, size=8.25, leading=11.2, gap=2.5, bullet_color=TEAL)


def page_one(c: canvas.Canvas) -> None:
    draw_footer(c, 1, 2)
    y = draw_header(c)

    y = section_title(c, "SUMMARY", MARGIN_X, y)
    summary = (
        "문서 RAG 백엔드와 agent guard를 함께 다루는 AI 백엔드 엔지니어입니다. "
        "PDF/XLSX/Text 문서의 검색 후보와 최종 답변 근거를 분리하고, SourceAtom/EvidenceBundle 기반 citation 검증과 "
        "근거 부족 시 fail-closed 응답 정책을 구현했습니다. 최근 작업은 route-selected Weaviate, SourceAtom v2 locator/axis "
        "materialization, selected-evidence gate, redacted trace/report 중심으로 정리되어 있습니다."
    )
    y = draw_wrapped(c, summary, MARGIN_X, y, CONTENT_W, size=8.95, leading=12.9, color=INK)
    y -= 6

    y = section_title(c, "SKILLS", MARGIN_X, y)
    col_w = (CONTENT_W - 18) / 2
    left = [
        "Backend: Python, FastAPI, Java, Spring Boot, REST API, PostgreSQL, Redis, pytest",
        "RAG/Retrieval: Weaviate hybrid, FAISS, BM25, Chroma, bge-m3, MMR, candidate/evidence split",
        "Document Processing: PDF page/table, XLSX sheet/range/cell/axis locator, Text chunk metadata",
    ]
    right = [
        "Agent Engineering: tool-style retrieval, answerability check, fail-closed response, redacted trace/report",
        "Evidence Guard: SourceAtom, EvidenceBundle, citation verification, selected-evidence gate",
        "Infra/Workflow: GCP Cloud Run/Tasks, Docker, Kubernetes/OpenShift, Codex/Claude Code",
    ]
    left_y = draw_skill_column(c, left, MARGIN_X, y, col_w)
    right_y = draw_skill_column(c, right, MARGIN_X + col_w + 18, y, col_w)
    y = min(left_y, right_y) - 6

    y = section_title(c, "FEATURED PROJECT", MARGIN_X, y)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 11.4)
    c.drawString(MARGIN_X, y, "검증 가능한 문서 RAG 백엔드")
    c.setFillColor(MUTED)
    c.setFont(FONT_REGULAR, 8.2)
    c.drawRightString(PAGE_W - MARGIN_X, y, "2026.05 - 2026.06")
    y -= 13
    y = draw_small_line(
        c,
        "개인 프로젝트 · AI Backend / Document RAG / Agent Guard · github.com/sfr9802/async-ai-document-pipeline-with-domain-rag",
        MARGIN_X,
        y,
        size=8.1,
    )
    y -= 2
    y = bullets(
        c,
        [
            "PDF/XLSX/Text 문서 업로드, 파싱, 인덱싱, 검색, 답변 artifact를 Job ID 기반 비동기 흐름으로 분리했습니다.",
            "SearchUnit/SearchView 300개 후보 가용성 진단을 거친 뒤, active evidence boundary는 route-selected Weaviate와 SourceAtom/EvidenceBundle로 분리했습니다.",
            "PDF page/table과 XLSX sheet/range/cell/axis locator를 SourceAtom v2에 materialize해 사람이 citation 근거를 다시 확인할 수 있게 했습니다.",
            "retrieved-context-only citation을 차단하는 selected-evidence gate를 구성해 `42 -> 0`, allowed/blocked `3/3 -> 5/1`, unsupported-after-gate `0.0`을 report-only로 확인했습니다.",
            "29개 승인 질의 smoke에서 10개 answered/citation-verified, 19개 stopped/fail_closed로 답변 가능성과 중단 정책을 분리했습니다.",
            "Trace/Guard는 플랫폼 과장 대신 redacted ref 중심 sidecar로 유지해 도구 선택, 근거 판단, 중단 사유만 검토 가능하게 남겼습니다.",
            "pytest contract test와 PyMuPDF PDF 검증으로 텍스트 레이어, 금지 문구, page count, selectable text를 확인했습니다.",
        ],
        MARGIN_X,
        y,
        CONTENT_W,
        size=8.25,
        leading=11.3,
        gap=2.7,
    )
    y -= 2
    draw_wrapped(
        c,
        "Tech: Python, FastAPI, pytest, Weaviate, FAISS, BM25, Hybrid Retrieval, PostgreSQL, PDF/XLSX/Text Parsing, Evidence Validation, Citation Verification, LLM API, OpenAI Codex",
        MARGIN_X,
        y,
        CONTENT_W,
        size=8.1,
        leading=11,
        color=MUTED,
    )


def draw_job(
    c: canvas.Canvas,
    y: float,
    company: str,
    period: str,
    role: str,
    items: Sequence[str],
    tech: str,
) -> float:
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 10.4)
    c.drawString(MARGIN_X, y, company)
    c.setFillColor(MUTED)
    c.setFont(FONT_REGULAR, 8.1)
    c.drawRightString(PAGE_W - MARGIN_X, y, period)
    y -= 12
    y = draw_small_line(c, role, MARGIN_X, y, size=8.2, color=TEAL)
    y = bullets(c, items, MARGIN_X, y, CONTENT_W, size=8.35, leading=11.2, gap=2.3)
    y = draw_wrapped(c, f"Tech: {tech}", MARGIN_X + 12, y, CONTENT_W - 12, size=8, leading=10.8, color=MUTED)
    return y - 8


def draw_additional_project(
    c: canvas.Canvas,
    y: float,
    title: str,
    meta: str,
    items: Sequence[str],
    link: str,
) -> float:
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 9.8)
    c.drawString(MARGIN_X, y, title)
    y -= 11
    y = draw_small_line(c, meta, MARGIN_X, y, size=8, color=MUTED)
    y = bullets(c, items, MARGIN_X, y, CONTENT_W, size=8.05, leading=10.6, gap=1.8)
    y = draw_small_line(c, link, MARGIN_X + 12, y, size=7.8, color=ACCENT)
    return y - 4


def page_two(c: canvas.Canvas) -> None:
    draw_footer(c, 2, 2)
    y = TOP - 4

    y = section_title(c, "WORK EXPERIENCE", MARGIN_X, y)
    y = draw_job(
        c,
        y,
        "㈜ 써밋라이즈에듀",
        "2026.02 - 2026.05",
        "개발 · 사원 | 서버리스 비동기 문서 처리 및 ERP 시스템 구축",
        [
            "GCP Cloud Run / Cloud Tasks 기반 서버리스 비동기 작업 처리 구조를 설계·구현했습니다.",
            "Spring Boot Core API와 FastAPI Worker를 분리해 요청 수락, 작업 실행, 결과 반영 책임을 나눴습니다.",
            "claim-before-execute 작업 소유권 제어와 callbackId 멱등성 처리로 중복 실행, 콜백 실패, 상태 불일치 위험을 줄였습니다.",
        ],
        "Java, Spring Boot, Python, FastAPI, GCP Cloud Run, Cloud Tasks, PostgreSQL, Redis",
    )
    y = draw_job(
        c,
        y,
        "㈜ 에트넷",
        "2024.07 - 2025.08",
        "백엔드/서버개발 | 통신사 상담사 서비스 프로젝트",
        [
            "통신사 상담사용 단말 품질 모니터링 대시보드와 로그 조회 API 응답 가공 흐름을 구현했습니다.",
            "Servlet + Flask 기반 API 서버와 통신사 Log 데이터 처리/조회 흐름을 구성했습니다.",
            "React UsageDashboard.jsx와 Chart.js를 연동해 Pie/Line 차트, 시계열 분석, 단말별 통계 화면을 만들었습니다.",
            "Kubernetes + OpenShift 운영 환경에서 배포, 모니터링, 인증 불일치와 상태 동기화 이슈를 추적했습니다.",
        ],
        "Flask, Servlet, React, Chart.js, Kubernetes, OpenShift, Tibero, SQL",
    )

    y = section_title(c, "SELECTED ADDITIONAL WORK", MARGIN_X, y)
    y = draw_additional_project(
        c,
        y,
        "Async Document Pipeline",
        "공개 repo · Spring Boot + FastAPI · Job lifecycle · claim/callback/idempotency",
        [
            "Core API가 Job 상태와 DB를 소유하고, FastAPI Worker가 claim 후 artifact를 쓰고 callback으로 결과를 반영하는 비동기 문서 처리 구조를 구현했습니다.",
            "서비스 간 JSON Schema 계약, Flyway migration, 상태 머신, callbackId 멱등성으로 실패 지점이 보이는 백엔드 흐름을 정리했습니다.",
        ],
        "github.com/sfr9802/async-document-pipeline",
    )
    y = draw_additional_project(
        c,
        y,
        "도메인 특화 RAG 검색·응답 파이프라인",
        "개인 프로젝트 · 2025 · FastAPI · Chroma · bge-m3 · MMR · Docker Compose",
        [
            "나무위키 애니메이션 문서 약 7,700건을 수집·정제하고, Chroma + bge-m3 + MMR 기반 retrieval-only benchmark를 구성했습니다.",
        ],
        "github.com/sfr9802/RAG_Project",
    )
    y = draw_additional_project(
        c,
        y,
        "AI 개발 도구 기반 구현 workflow",
        "개인 프로젝트/실험 · OpenAI Codex · Claude Code · Contract Test",
        [
            "Optuna 실험 결과를 round artifact로 정리하고, LLM이 완료된 round bundle만 읽어 다음 설정을 제안하는 schema-validated Skill을 제작했습니다.",
        ],
        "github.com/sfr9802/optuna-round-refinement",
    )

    y = section_title(c, "EDUCATION / TRAINING", MARGIN_X, y)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 9.5)
    c.drawString(MARGIN_X, y, "대덕대학")
    c.setFillColor(MUTED)
    c.setFont(FONT_REGULAR, 8.1)
    c.drawRightString(PAGE_W - MARGIN_X, y, "2018.02 - 2020.02")
    y -= 11
    y = draw_small_line(c, "컴퓨터정보학과 · 대학교(2·3년제) 졸업 · 학점 3.8 / 4.5", MARGIN_X, y, size=8)
    c.setFillColor(INK)
    c.setFont(FONT_BOLD, 9.5)
    c.drawString(MARGIN_X, y, "Grepp / 프로그래머스 데이터·AI 교육")
    c.setFillColor(MUTED)
    c.setFont(FONT_REGULAR, 8.1)
    c.drawRightString(PAGE_W - MARGIN_X, y, "2024.02 - 2024.06")
    y -= 11
    draw_wrapped(
        c,
        "SQL, Python, Pandas 기반 데이터 처리와 시각화 과정을 이수하고, ML/DL 기초와 3회 프로젝트를 통해 데이터 분석 흐름을 경험했습니다.",
        MARGIN_X,
        y,
        CONTENT_W,
        size=8,
        leading=10.8,
        color=MUTED,
    )


def build_pdf(path: Path = PDF_PATH) -> Path:
    register_fonts()
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    c.setTitle("최병찬 - AI 에이전트 엔지니어 | Evidence-Grounded RAG")
    c.setAuthor("Choi Byungchan")
    c.setSubject("AI engineer and agent engineer resume focused on evidence-grounded RAG backend")
    page_one(c)
    c.showPage()
    page_two(c)
    c.showPage()
    c.save()
    return path


if __name__ == "__main__":
    built = build_pdf()
    if LEGACY_PDF_PATH != built:
        shutil.copyfile(built, LEGACY_PDF_PATH)
    print(built)
    print(LEGACY_PDF_PATH)
