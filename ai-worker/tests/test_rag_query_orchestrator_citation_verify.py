from __future__ import annotations

import pytest

from app.capabilities.rag_orchestrator.citation_verify import (
    FATAL_EMBEDDING_STATUS,
    FATAL_INDEX_VERSION,
    FATAL_INVALID_LOCATION,
    FATAL_MISSING_CITATION,
    FATAL_MISSING_LOCATION,
    FATAL_PARSER_VERSION,
    FATAL_PDF_PAGE,
    FATAL_RETRIEVAL_BACKEND,
    FATAL_SOURCE_TYPE,
    FATAL_XLSX_RANGE,
    FATAL_XLSX_SHEET,
    WARNING_BBOX_CONFIDENCE_LOW,
    WARNING_OCR_LOWER_TRUST,
    WARNING_TABLE_TRUNCATED,
    citation_verify_tool,
)
from app.capabilities.rag_orchestrator.evidence import (
    EMBEDDING_STATUS_EMBEDDED,
    RETRIEVAL_BACKEND_VECTOR,
    Evidence,
    QueryPolicy,
)


def _policy(
    *,
    source_types=("PDF",),
    parser_versions=("pdf-extract-v2",),
    index_version="rag-ingestion-v2-candidate",
) -> QueryPolicy:
    return QueryPolicy(
        request_id="req-1",
        required_index_version=index_version,
        allowed_source_file_types=list(source_types),
        allowed_parser_versions=list(parser_versions),
    )


def _evidence(**overrides) -> Evidence:
    values = {
        "evidence_id": "ev-1",
        "retrieval_backend": RETRIEVAL_BACKEND_VECTOR,
        "rank": 1,
        "source_file_id": "source-1",
        "source_file_type": "PDF",
        "index_version": "rag-ingestion-v2-candidate",
        "embedding_status": EMBEDDING_STATUS_EMBEDDED,
        "parser_version": "pdf-extract-v2",
        "citation_text": "report.pdf p. 2",
        "location_json": {"page_no": 2},
        "search_unit_id": "unit-1",
        "chunk_id": "chunk-1",
        "text": "grounded text",
        "location_type": "pdf",
    }
    values.update(overrides)
    return Evidence(**values)


def test_citation_verify_accepts_vector_pdf_evidence():
    result = citation_verify_tool([_evidence()], _policy())

    assert len(result.verified) == 1
    assert result.verified[0].verified is True
    assert result.rejected == ()
    assert result.metrics == {
        "verified_count": 1,
        "rejected_count": 0,
        "warning_count": 0,
    }
    verified_body = result.to_dict()["verified"][0]["evidence"]
    assert verified_body["verification"]["status"] == "verified"


def test_citation_verify_accepts_vector_xlsx_evidence():
    policy = _policy(
        source_types=("SPREADSHEET",),
        parser_versions=("xlsx-extract-v2-hidden-safe",),
    )
    evidence = _evidence(
        evidence_id="xlsx-1",
        source_file_type="SPREADSHEET",
        parser_version="xlsx-extract-v2-hidden-safe",
        citation_text="book.xlsx Sales!A1:B2",
        location_type="xlsx",
        location_json={
            "sheetName": "Sales",
            "cellRange": "A1:B2",
            "tableId": "sales-table",
        },
    )

    result = citation_verify_tool([evidence], policy)

    assert len(result.verified) == 1
    assert result.rejected == ()


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"retrieval_backend": "library_search"}, FATAL_RETRIEVAL_BACKEND),
        ({"index_version": "old-index"}, FATAL_INDEX_VERSION),
        ({"embedding_status": "PENDING"}, FATAL_EMBEDDING_STATUS),
        ({"citation_text": ""}, FATAL_MISSING_CITATION),
        ({"location_json": {}}, FATAL_MISSING_LOCATION),
        ({"source_file_type": "TEXT"}, FATAL_SOURCE_TYPE),
        ({"parser_version": "pdf-extract-v1"}, FATAL_PARSER_VERSION),
        ({"location_json": {"page_label": "ii"}}, FATAL_PDF_PAGE),
        ({"location_json": {"page_no": 0}}, FATAL_PDF_PAGE),
        ({"location_json": "page 2"}, FATAL_INVALID_LOCATION),
    ],
)
def test_citation_verify_fatal_rejects_pdf_policy_violations(overrides, reason):
    result = citation_verify_tool([_evidence(**overrides)], _policy())

    assert result.verified == ()
    assert len(result.rejected) == 1
    assert reason in result.rejected[0].fatal_reasons
    assert result.metrics["rejected_count"] == 1


@pytest.mark.parametrize(
    ("location_json", "reason"),
    [
        ({"cellRange": "A1:B2"}, FATAL_XLSX_SHEET),
        ({"sheetName": "Sales"}, FATAL_XLSX_RANGE),
    ],
)
def test_citation_verify_fatal_rejects_xlsx_locator_gaps(location_json, reason):
    policy = _policy(
        source_types=("SPREADSHEET",),
        parser_versions=("xlsx-extract-v2-hidden-safe",),
    )
    evidence = _evidence(
        source_file_type="SPREADSHEET",
        parser_version="xlsx-extract-v2-hidden-safe",
        citation_text="book.xlsx Sales!A1:B2",
        location_type="xlsx",
        location_json=location_json,
    )

    result = citation_verify_tool([evidence], policy)

    assert result.verified == ()
    assert reason in result.rejected[0].fatal_reasons


def test_citation_verify_accepts_xlsx_table_id_locator_without_cell_range():
    policy = _policy(
        source_types=("SPREADSHEET",),
        parser_versions=("xlsx-extract-v2-hidden-safe",),
    )
    evidence = _evidence(
        source_file_type="SPREADSHEET",
        parser_version="xlsx-extract-v2-hidden-safe",
        citation_text="book.xlsx Sales table sales-table",
        location_type="xlsx",
        location_json={"sheetName": "Sales", "tableId": "sales-table"},
    )

    result = citation_verify_tool([evidence], policy)

    assert len(result.verified) == 1
    assert result.rejected == ()


def test_citation_verify_rejects_malformed_xlsx_range():
    policy = _policy(
        source_types=("SPREADSHEET",),
        parser_versions=("xlsx-extract-v2-hidden-safe",),
    )
    evidence = _evidence(
        source_file_type="SPREADSHEET",
        parser_version="xlsx-extract-v2-hidden-safe",
        citation_text="book.xlsx Sales!not-a-range",
        location_type="xlsx",
        location_json={"sheetName": "Sales", "cellRange": "not-a-range"},
    )

    result = citation_verify_tool([evidence], policy)

    assert result.verified == ()
    assert FATAL_XLSX_RANGE in result.rejected[0].fatal_reasons


def test_citation_verify_keeps_lower_trust_and_truncation_as_warnings():
    policy = _policy(
        source_types=("SPREADSHEET",),
        parser_versions=("xlsx-extract-v2-hidden-safe",),
    )
    evidence = _evidence(
        source_file_type="SPREADSHEET",
        parser_version="xlsx-extract-v2-hidden-safe",
        citation_text="book.xlsx Sales!A1:B2",
        location_type="xlsx",
        location_json={
            "sheetName": "Sales",
            "cellRange": "A1:B2",
            "tableTruncated": True,
            "bboxConfidence": 0.42,
        },
        extra={"ocrLowerTrust": True},
    )

    result = citation_verify_tool([evidence], policy)

    assert len(result.verified) == 1
    assert result.rejected == ()
    assert result.verified[0].warnings == (
        WARNING_OCR_LOWER_TRUST,
        WARNING_BBOX_CONFIDENCE_LOW,
        WARNING_TABLE_TRUNCATED,
    )
    assert result.metrics["warning_count"] == 3
