from __future__ import annotations

import csv
import json
import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "official_answer_citation_agentic_loop_run_v4_7_2_source_grounded_korean_query_review_packet_hydration_nonprod"
SOURCE_RUN_ID = "official_answer_citation_agentic_loop_run_v4_7_preofficial_external_holdout_candidate_manifest_registration_nonprod"
REPORT_DIR = ROOT / "reports" / "rag_eval" / "rag-ingestion" / "quality" / RUN_ID
REPORT_JSON = REPORT_DIR / "report.json"
PACKET_CSV = REPORT_DIR / "review_packet_ko_hydrated.csv"
PACKET_JSONL = REPORT_DIR / "review_packet_ko_hydrated.jsonl"
PACKET_XLSX = REPORT_DIR / "review_packet_ko_hydrated.xlsx"
SUMMARY_JSON = REPORT_DIR / "review_summary_ko.json"
GUIDELINES_MD = REPORT_DIR / "review_guidelines_ko.md"
STATUS_JSONL = ROOT / "reports" / "rag_eval" / "rag-ingestion" / "status.jsonl"


USER_OWNED_BLANK_COLUMNS = (
    "기대답변_한국어",
    "근거판단_한국어",
    "제외사유",
    "정책메모",
    "검수자",
    "검수일시",
)
FORBIDDEN_PACKET_TEXT_PATTERNS = (
    r"\bD:[\\/]",
    r"v4_7_external_pdf_document_sha256_",
    r"v4_7_external_xlsx_workbook_sha256_",
    r"target_locator",
    r"gold_locator",
    r"expected_answer",
    r"supporting_evidence",
    r"raw_llm_response",
    r"prompt_payload",
    r"checkpoint",
    r"=<[^>]+>",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _non_empty(value: object) -> bool:
    return bool(str(value or "").strip())


def _is_placeholder_query(text: str) -> bool:
    stripped = text.strip()
    return bool(re.fullmatch(r"v4_7_(?:pdf|xlsx)_query_\d+_\d+", stripped))


def test_v4_7_2_hydrated_packet_has_concrete_queries_and_guardrails() -> None:
    assert REPORT_JSON.exists()
    assert PACKET_CSV.exists()
    assert PACKET_JSONL.exists()
    assert PACKET_XLSX.exists()
    assert SUMMARY_JSON.exists()
    assert GUIDELINES_MD.exists()

    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    rows = _read_csv(PACKET_CSV)
    jsonl_rows = _read_jsonl(PACKET_JSONL)

    assert len(rows) == 204
    assert len(jsonl_rows) == 204
    assert sum(1 for row in rows if row["소스계열"] == "PDF") == 100
    assert sum(1 for row in rows if row["소스계열"] == "XLSX") == 104
    assert sum(1 for row in rows if row["소스계열"] == "TEXT") == 0
    assert report["hydrated_packet_row_count"] == 204
    assert report["hydrated_pdf_row_count"] == 100
    assert report["hydrated_xlsx_row_count"] == 104
    assert report["hydrated_packet_non_empty_query_count"] == 204
    assert report["extraction_failed_row_count"] == 0
    assert report["deterministic_query_generated_count"] == 0
    assert report["local_llm_query_generated_count"] == 204
    assert report["query_generation_strategy"]["local_llm_used"] is True
    assert report["query_generation_strategy"]["deterministic_template_fallback_enabled"] is False
    assert summary["hydrated_packet_non_empty_query_count"] == 204

    assert all(_non_empty(row["질의문"]) for row in rows)
    assert not any(_is_placeholder_query(row["질의문"]) for row in rows)
    assert not any("v4_7 report lacked query text" in row.get("machine_notes", "") for row in rows)
    assert not any("질의문이나 LLM 답변 artifact가 없으므로" in row.get("machine_notes", "") for row in rows)
    assert all(_non_empty(row.get("근거후보_스니펫") or row.get("evidence_preview_redacted")) for row in rows)
    assert all(_non_empty(row.get("근거후보_위치") or row.get("locator_preview_redacted")) for row in rows)
    assert all(_non_empty(row.get("질의생성방식")) for row in rows)
    assert {row["질의생성방식"] for row in rows} == {"local_llm_source_grounded_draft"}
    assert all(row["검수상태"] == "미검수" for row in rows)
    assert all(row["질의자연성"] == "보류" for row in rows)
    assert all(row["질의승인"] == "보류" for row in rows)
    assert all(row["관련성라벨"] == "보류" for row in rows)
    assert all(row["답변가능성라벨"] == "보류" for row in rows)
    assert all(row["공식분모포함판단"] == "보류" for row in rows)
    assert all(row["재검수필요"] == "보류" for row in rows)
    for column in USER_OWNED_BLANK_COLUMNS:
        assert all(row[column] == "" for row in rows), column

    assert all(row["기대답변_초안_비공식"].startswith("비공식 기계초안") for row in rows)
    assert all(row["source_report_run_id"] == SOURCE_RUN_ID for row in rows)
    assert all(row["source_disjointness_gate"] == "pass" for row in rows)
    assert all(row["query_fidelity_included"] == "true" for row in rows)
    assert all(row["prior_identity_collision"] == "false" for row in rows)
    assert all(row["leakage_bucket"] == "none" for row in rows)
    assert all(row["manifest_sha256"] == report["candidate_manifest_sha256"] for row in rows)

    pdf_rows = [row for row in rows if row["소스계열"] == "PDF"]
    xlsx_rows = [row for row in rows if row["소스계열"] == "XLSX"]
    assert all(_non_empty(row["문서명_표시"]) for row in pdf_rows)
    assert all(_non_empty(row["페이지_후보"]) for row in pdf_rows)
    assert all(_non_empty(row["워크북명_표시"]) for row in xlsx_rows)
    assert all(_non_empty(row["시트명_표시"]) for row in xlsx_rows)
    assert all(_non_empty(row["근거후보_범위"]) for row in xlsx_rows)
    assert not any("=" in row["근거후보_표시값_미리보기"] for row in xlsx_rows)

    with zipfile.ZipFile(PACKET_XLSX) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        for sheet in ("검수_대상_전체", "PDF_검수", "XLSX_검수", "추출실패_검수", "라벨_가이드", "제외_사유_가이드", "요약"):
            assert sheet in workbook

    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["v4_7_official_metric_gate_opened"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["promotion_evidence"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["ft_a_execution"] is False
    assert report["fine_tuning"] is False
    assert report["qrels_mutation"] is False
    assert report["gold_mutation"] is False
    assert report["label_mutation"] is False
    assert report["training_dataset_created"] is False
    assert report["source_report_run_id"] == SOURCE_RUN_ID

    packet_payload = "\n".join(
        [
            REPORT_JSON.read_text(encoding="utf-8"),
            PACKET_CSV.read_text(encoding="utf-8-sig"),
            PACKET_JSONL.read_text(encoding="utf-8"),
            SUMMARY_JSON.read_text(encoding="utf-8"),
            GUIDELINES_MD.read_text(encoding="utf-8"),
        ]
    )
    for pattern in FORBIDDEN_PACKET_TEXT_PATTERNS:
        assert not re.search(pattern, packet_payload), pattern

    status_events = _read_jsonl(STATUS_JSONL)
    matches = [event for event in status_events if event.get("run_id") == RUN_ID]
    assert len(matches) == 1
    assert matches[0]["status"] == "DIAGNOSTIC_V4_7_2_SOURCE_GROUNDED_KOREAN_QUERY_REVIEW_PACKET_HYDRATION_NONPROD_READY"
