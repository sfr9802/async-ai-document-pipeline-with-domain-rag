from __future__ import annotations

from dataclasses import replace

import pytest

from app.capabilities.rag_orchestrator.evidence import QueryPolicy
from app.capabilities.rag_orchestrator.evidence_merge import evidence_merge_tool
from app.capabilities.rag_orchestrator.tools import (
    ToolResult,
    fake_pdf_vector_search_tool,
    fake_xlsx_vector_search_tool,
)


def _pdf_policy() -> QueryPolicy:
    return QueryPolicy(
        request_id="req-pdf",
        required_index_version="rag-ingestion-v2-candidate",
        allowed_source_file_types=["PDF"],
        allowed_parser_versions=["pdf-extract-v2"],
    )


def _xlsx_policy() -> QueryPolicy:
    return QueryPolicy(
        request_id="req-xlsx",
        required_index_version="rag-ingestion-v2-candidate",
        allowed_source_file_types=["SPREADSHEET"],
        allowed_parser_versions=["xlsx-extract-v2-hidden-safe"],
    )


def _tool_result(evidence) -> ToolResult:
    return ToolResult(
        tool="fixture",
        evidence=tuple(evidence),
        rejected=(),
        backend_identity={
            "backend": "fake_vector",
            "retrieval_backend": "vector",
            "index_namespace_filter": "rag-ingestion-v2-candidate",
        },
    )


def test_same_search_unit_id_is_deduped():
    first = fake_pdf_vector_search_tool("pdf", _pdf_policy()).evidence[0]
    second = replace(
        first,
        evidence_id="pdf-duplicate-search-unit",
        chunk_id="chunk-other",
        unit_key="page:other",
    )

    result = evidence_merge_tool([_tool_result([first, second])])

    assert [item.evidence_id for item in result.merged_evidence] == [first.evidence_id]
    assert result.dedupe_stats["deduped_by_search_unit_id_count"] == 1


def test_same_chunk_id_is_deduped():
    first = fake_pdf_vector_search_tool("pdf", _pdf_policy()).evidence[0]
    second = replace(
        first,
        evidence_id="pdf-duplicate-chunk",
        search_unit_id="unit-other",
        unit_key="page:other",
    )

    result = evidence_merge_tool([_tool_result([first, second])])

    assert [item.evidence_id for item in result.merged_evidence] == [first.evidence_id]
    assert result.dedupe_stats["deduped_by_chunk_id_count"] == 1


def test_same_source_file_and_unit_key_is_deduped():
    first = fake_pdf_vector_search_tool("pdf", _pdf_policy()).evidence[0]
    second = replace(
        first,
        evidence_id="pdf-duplicate-source-unit",
        search_unit_id="unit-other",
        chunk_id="chunk-other",
    )

    result = evidence_merge_tool([_tool_result([first, second])])

    assert [item.evidence_id for item in result.merged_evidence] == [first.evidence_id]
    assert result.dedupe_stats["deduped_by_source_unit_count"] == 1


def test_rejected_evidence_is_excluded_from_merge():
    tool_result = fake_pdf_vector_search_tool("pdf", _pdf_policy(), fixture="mixed")

    result = evidence_merge_tool([tool_result])

    assert [item.extra["fixture"] for item in result.merged_evidence] == ["valid"]
    assert all(item.verification_status == "verified" for item in result.merged_evidence)


def test_merge_rejects_raw_evidence_iterables():
    evidence = fake_pdf_vector_search_tool("pdf", _pdf_policy()).evidence[0]

    with pytest.raises(TypeError, match="ToolResult"):
        evidence_merge_tool([[evidence]])


def test_max_evidence_is_applied():
    pdf = fake_pdf_vector_search_tool("pdf", _pdf_policy()).evidence[0]
    xlsx = fake_xlsx_vector_search_tool("xlsx", _xlsx_policy()).evidence[0]

    result = evidence_merge_tool([_tool_result([pdf, xlsx])], max_evidence=1)

    assert len(result.merged_evidence) == 1
    assert result.dedupe_stats["truncated_count"] == 1


def test_source_type_counts_include_mixed_pdf_and_xlsx():
    pdf = fake_pdf_vector_search_tool("pdf", _pdf_policy()).evidence[0]
    xlsx = fake_xlsx_vector_search_tool("xlsx", _xlsx_policy()).evidence[0]

    result = evidence_merge_tool([_tool_result([pdf]), _tool_result([xlsx])])

    assert result.source_type_counts == {"PDF": 1, "SPREADSHEET": 1}
    assert result.to_dict()["source_type_counts"] == {"PDF": 1, "SPREADSHEET": 1}
