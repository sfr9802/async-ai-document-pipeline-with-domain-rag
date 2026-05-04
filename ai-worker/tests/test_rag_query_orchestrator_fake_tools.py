from __future__ import annotations

from app.capabilities.rag_orchestrator.citation_verify import (
    FATAL_INDEX_VERSION,
    FATAL_MISSING_CITATION,
    FATAL_MISSING_LOCATION,
    FATAL_PARSER_VERSION,
    FATAL_SOURCE_TYPE,
    citation_verify_tool,
)
from app.capabilities.rag_orchestrator.evidence import (
    RETRIEVAL_BACKEND_VECTOR,
    QueryPolicy,
)
from app.capabilities.rag_orchestrator.tools import (
    FAKE_VECTOR_BACKEND,
    TEXT_CONTRACT_READINESS_WARNING,
    ToolResult,
    fake_pdf_vector_search_tool,
    fake_text_vector_search_tool,
    fake_xlsx_vector_search_tool,
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
        top_k=5,
    )


def test_pdf_fake_tool_returns_valid_pdf_evidence_shape():
    result = fake_pdf_vector_search_tool("find page", _policy())

    assert isinstance(result, ToolResult)
    assert len(result.evidence) == 1
    assert result.rejected == ()
    evidence = result.evidence[0]
    body = evidence.to_dict()

    assert evidence.source_file_type == "PDF"
    assert evidence.retrieval_backend == RETRIEVAL_BACKEND_VECTOR
    assert evidence.verification_status == "verified"
    assert body["source"]["sourceFileType"] == "PDF"
    assert body["location"]["locationType"] == "pdf"
    assert body["location"]["locationJson"]["page_no"] == 2
    assert body["verification"]["status"] == "verified"


def test_xlsx_fake_tool_returns_valid_xlsx_evidence_shape():
    policy = _policy(
        source_types=("SPREADSHEET",),
        parser_versions=("xlsx-extract-v2-hidden-safe",),
    )

    result = fake_xlsx_vector_search_tool("sum sales", policy)

    assert len(result.evidence) == 1
    assert result.rejected == ()
    evidence = result.evidence[0]
    body = evidence.to_dict()
    assert evidence.source_file_type == "SPREADSHEET"
    assert body["location"]["locationType"] == "xlsx"
    assert body["location"]["locationJson"]["sheetName"] == "Sales"
    assert body["location"]["locationJson"]["cellRange"] == "A1:D5"


def test_text_fake_tool_returns_shape_with_readiness_warning():
    policy = _policy(source_types=("TEXT",), parser_versions=("text-parser-v0",))

    result = fake_text_vector_search_tool("find text", policy)

    assert len(result.evidence) == 1
    assert result.rejected == ()
    evidence = result.evidence[0]
    assert evidence.source_file_type == "TEXT"
    assert TEXT_CONTRACT_READINESS_WARNING in evidence.verification_warnings
    assert (
        TEXT_CONTRACT_READINESS_WARNING
        in evidence.to_dict()["verification"]["warnings"]
    )


def test_policy_source_type_mismatch_is_rejected():
    result = fake_pdf_vector_search_tool(
        "find page",
        _policy(source_types=("TEXT",), parser_versions=("pdf-extract-v2",)),
    )

    assert result.evidence == ()
    assert len(result.rejected) == 1
    assert FATAL_SOURCE_TYPE in result.rejected[0].reasons


def test_index_version_mismatch_fixture_is_rejected():
    result = fake_pdf_vector_search_tool("find page", _policy(), fixture="mismatch")

    by_fixture = {
        item.evidence.extra["fixture"]: item.reasons for item in result.rejected
    }
    assert FATAL_INDEX_VERSION in by_fixture["wrong_index_version"]


def test_parser_version_mismatch_fixture_is_rejected():
    result = fake_xlsx_vector_search_tool(
        "sum sales",
        _policy(
            source_types=("SPREADSHEET",),
            parser_versions=("xlsx-extract-v2-hidden-safe",),
        ),
        fixture="mismatch",
    )

    by_fixture = {
        item.evidence.extra["fixture"]: item.reasons for item in result.rejected
    }
    assert FATAL_PARSER_VERSION in by_fixture["wrong_parser_version"]


def test_missing_citation_and_location_fixtures_are_rejected():
    result = fake_pdf_vector_search_tool("find page", _policy(), fixture="mismatch")

    by_fixture = {
        item.evidence.extra["fixture"]: item.reasons for item in result.rejected
    }
    assert FATAL_MISSING_CITATION in by_fixture["missing_citation"]
    assert FATAL_MISSING_LOCATION in by_fixture["missing_location"]


def test_wrong_source_type_mismatch_fixture_is_rejected():
    result = fake_xlsx_vector_search_tool(
        "sum sales",
        _policy(
            source_types=("SPREADSHEET",),
            parser_versions=("xlsx-extract-v2-hidden-safe",),
        ),
        fixture="mismatch",
    )

    by_fixture = {
        item.evidence.extra["fixture"]: item.reasons for item in result.rejected
    }
    assert FATAL_SOURCE_TYPE in by_fixture["wrong_source_type"]


def test_all_tool_outputs_share_same_top_level_shape():
    outputs = [
        fake_pdf_vector_search_tool("pdf", _policy()),
        fake_xlsx_vector_search_tool(
            "xlsx",
            _policy(
                source_types=("SPREADSHEET",),
                parser_versions=("xlsx-extract-v2-hidden-safe",),
            ),
        ),
        fake_text_vector_search_tool(
            "text",
            _policy(source_types=("TEXT",), parser_versions=("text-parser-v0",)),
        ),
    ]

    shapes = [set(result.to_dict().keys()) for result in outputs]
    assert shapes == [
        {"tool", "evidence", "rejected", "backend_identity"},
        {"tool", "evidence", "rejected", "backend_identity"},
        {"tool", "evidence", "rejected", "backend_identity"},
    ]
    for result in outputs:
        identity = result.to_dict()["backend_identity"]
        assert identity["backend"] == FAKE_VECTOR_BACKEND
        assert identity["retrieval_backend"] == RETRIEVAL_BACKEND_VECTOR
        assert identity["index_namespace_filter"] == "rag-ingestion-v2-candidate"


def test_valid_pdf_and_xlsx_fake_evidence_verify_with_citation_verifier():
    pdf_policy = _policy()
    xlsx_policy = _policy(
        source_types=("SPREADSHEET",),
        parser_versions=("xlsx-extract-v2-hidden-safe",),
    )
    pdf_result = fake_pdf_vector_search_tool("pdf", pdf_policy)
    xlsx_result = fake_xlsx_vector_search_tool("xlsx", xlsx_policy)

    pdf_verified = citation_verify_tool(pdf_result.evidence, pdf_policy)
    xlsx_verified = citation_verify_tool(xlsx_result.evidence, xlsx_policy)

    assert len(pdf_verified.verified) == 1
    assert pdf_verified.rejected == ()
    assert len(xlsx_verified.verified) == 1
    assert xlsx_verified.rejected == ()
