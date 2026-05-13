from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.capabilities.rag.generation import RetrievedChunk
from app.capabilities.rag_orchestrator.citation_verify import (
    FATAL_EMBEDDING_STATUS,
    FATAL_INDEX_VERSION,
    FATAL_MISSING_CITATION,
    FATAL_MISSING_LOCATION,
    FATAL_PDF_STABLE_IDENTITY_REQUIRED,
    FATAL_PARSER_VERSION,
    FATAL_SOURCE_TYPE,
    FATAL_XLSX_HIDDEN_NEGATIVE_OR_EXCLUDED_ROW,
)
from app.capabilities.rag_orchestrator.evidence import QueryPolicy
from app.capabilities.rag_orchestrator.tools import ToolResult
from app.capabilities.rag_orchestrator.vector_tools import (
    TEXT_VECTOR_READINESS_WARNING,
    pdf_vector_search_tool,
    text_vector_search_tool,
    xlsx_vector_search_tool,
)


@dataclass(frozen=True)
class _Report:
    query: str
    top_k: int
    index_version: str
    embedding_model: str
    results: list[RetrievedChunk]


class _FakeRetriever:
    def __init__(self, rows: list[RetrievedChunk]) -> None:
        self._rows = rows
        self._top_k = 2
        self._candidate_k = 2
        self.calls: list[dict[str, Any]] = []

    def retrieve(self, query: str, filters=None):
        self.calls.append(
            {
                "query": query,
                "filters": filters,
                "top_k": self._top_k,
                "candidate_k": self._candidate_k,
            }
        )
        return _Report(
            query=query,
            top_k=self._top_k,
            index_version="rag-ingestion-v2-candidate",
            embedding_model="fake-embedding-model",
            results=self._rows[: self._top_k],
        )


def _policy(
    *,
    source_types=("PDF",),
    parser_versions=("pdf-extract-v2",),
    top_k=2,
) -> QueryPolicy:
    return QueryPolicy(
        request_id="req-vector-1",
        required_index_version="rag-ingestion-v2-candidate",
        allowed_source_file_types=list(source_types),
        allowed_parser_versions=list(parser_versions),
        top_k=top_k,
    )


def _chunk(
    *,
    source_file_type="PDF",
    parser_version="pdf-extract-v2",
    index_version="rag-ingestion-v2-candidate",
    embedding_status="EMBEDDED",
    citation_text="fake.pdf p. 1",
    location_json: dict[str, Any] | None = None,
    chunk_id="chunk-1",
    extra_metadata: dict[str, Any] | None = None,
) -> RetrievedChunk:
    if location_json is None and source_file_type == "PDF":
        location_json = {
            "page_no": 1,
            "bbox": [72, 120, 510, 680],
            "region_type": "paragraph",
            "section_heading": "Contract terms",
            "nearby_paragraphs": ["Previous paragraph.", "Next paragraph."],
            "ocr_confidence": 0.96,
        }
    if location_json is None and source_file_type == "SPREADSHEET":
        location_json = {
            "sheetName": "Sales",
            "cellRange": "A1:D5",
            "tableId": "sales-table",
            "rowStart": 2,
            "rowEnd": 2,
            "columnStart": "A",
            "columnEnd": "D",
            "headerRows": [1],
            "columnHeaders": ["Region", "Quarter", "Revenue", "Units"],
            "rowValues": {
                "Region": "KR",
                "Quarter": "Q1",
                "Revenue": 100,
                "Units": 10,
            },
            "nearbyRows": [
                {
                    "Region": "KR",
                    "Quarter": "Q2",
                    "Revenue": 150,
                    "Units": 12,
                }
            ],
            "mergedCellContext": ["A1:D1"],
            "tableTitle": "Sales table",
        }
    if location_json is None and source_file_type == "TEXT":
        location_json = {"section_path": "Overview", "char_start": 0, "char_end": 40}

    metadata = {
        "sourceFileType": source_file_type,
        "parserVersion": parser_version,
        "indexVersion": index_version,
        "embeddingStatus": embedding_status,
        "citationText": citation_text,
        "locationJson": location_json,
        "locationType": _location_type(source_file_type),
        "chunkType": _chunk_type(source_file_type),
        "documentVersionId": f"docver-{chunk_id}",
        "embeddingModel": "fake-embedding-model",
        "embeddingTextSha256": f"sha256-{chunk_id}",
        "vectorId": f"{index_version}:{chunk_id}",
        "hiddenPolicyVersion": (
            "exclude-hidden-v1" if source_file_type == "SPREADSHEET" else None
        ),
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return RetrievedChunk(
        chunk_id=chunk_id,
        doc_id=f"doc-{chunk_id}",
        section="section",
        text=f"Retrieved text for {source_file_type} {chunk_id}.",
        score=0.91,
        rerank_score=0.95,
        dense_score=0.91,
        sparse_score=0.12,
        search_unit_id=f"unit-{chunk_id}",
        source_file_id=f"source-{chunk_id}",
        source_file_name=f"{chunk_id}.{_extension(source_file_type)}",
        extracted_artifact_id=f"artifact-{chunk_id}",
        artifact_type=source_file_type,
        unit_type="TABLE" if source_file_type == "SPREADSHEET" else "PAGE",
        unit_key=f"unit-key-{chunk_id}",
        page_start=1 if source_file_type == "PDF" else None,
        page_end=1 if source_file_type == "PDF" else None,
        metadata_json=metadata,
    )


def test_pdf_retrieved_chunk_is_adapted_to_verified_evidence():
    retriever = _FakeRetriever([_chunk()])
    policy = _policy(top_k=2)

    result = pdf_vector_search_tool("pdf query", policy, retriever=retriever)

    assert isinstance(result, ToolResult)
    assert len(result.evidence) == 1
    assert result.rejected == ()
    evidence = result.evidence[0]
    assert evidence.source_file_type == "PDF"
    assert evidence.parser_version == "pdf-extract-v2"
    assert evidence.index_version == "rag-ingestion-v2-candidate"
    assert evidence.embedding_status == "EMBEDDED"
    assert evidence.citation_text == "fake.pdf p. 1"
    assert evidence.location_json["page_no"] == 1
    assert evidence.extra["track_evidence_contract"] == "pdf-business-ocr-mm-context-v1"
    pdf_context = evidence.extra["pdf_evidence_context"]
    assert pdf_context["page"] == 1
    assert pdf_context["bbox"] == [72.0, 120.0, 510.0, 680.0]
    assert pdf_context["region_type"] == "paragraph"
    assert pdf_context["section_heading"] == "Contract terms"
    assert pdf_context["nearby_paragraphs"] == [
        "Previous paragraph.",
        "Next paragraph.",
    ]
    assert pdf_context["OCR_confidence"] == 0.96
    assert pdf_context["diagnostic_only"] is False
    assert evidence.verification_status == "verified"
    assert retriever.calls[0]["top_k"] > policy.top_k
    assert retriever._top_k == 2
    assert retriever._candidate_k == 2


def test_xlsx_retrieved_chunk_is_adapted_to_verified_evidence():
    retriever = _FakeRetriever(
        [
            _chunk(
                source_file_type="SPREADSHEET",
                parser_version="xlsx-extract-v2-hidden-safe",
                citation_text="fake.xlsx Sales!A1:D5",
            )
        ]
    )
    policy = _policy(
        source_types=("SPREADSHEET",),
        parser_versions=("xlsx-extract-v2-hidden-safe",),
    )

    result = xlsx_vector_search_tool("xlsx query", policy, retriever=retriever)

    assert len(result.evidence) == 1
    evidence = result.evidence[0]
    assert evidence.source_file_type == "SPREADSHEET"
    assert evidence.location_json["sheetName"] == "Sales"
    assert evidence.location_json["cellRange"] == "A1:D5"
    assert evidence.hidden_policy_version == "exclude-hidden-v1"
    assert evidence.extra["track_evidence_contract"] == "xlsx-business-structured-context-v1"
    xlsx_context = evidence.extra["xlsx_evidence_context"]
    assert xlsx_context["file"] == "chunk-1.xlsx"
    assert xlsx_context["sheet"] == "Sales"
    assert xlsx_context["table_id"] == "sales-table"
    assert xlsx_context["matched_cells"] == ["A1:D5"]
    assert xlsx_context["header_rows"] == [1]
    assert xlsx_context["target_rows"] == [2]
    assert xlsx_context["target_columns"] == ["A", "B", "C", "D"]
    assert xlsx_context["row_values"]["Revenue"] == 100
    assert xlsx_context["column_headers"] == ["Region", "Quarter", "Revenue", "Units"]
    assert xlsx_context["nearby_rows"][0]["Quarter"] == "Q2"
    assert xlsx_context["merged_cell_context"] == ["A1:D1"]
    assert xlsx_context["table_title_candidate"] == "Sales table"
    assert xlsx_context["diagnostic_only"] is False


def test_text_vector_tool_marks_contract_readiness_warning():
    retriever = _FakeRetriever(
        [
            _chunk(
                source_file_type="TEXT",
                parser_version="text-parser-v0",
                citation_text="fake.txt Overview",
            )
        ]
    )
    policy = _policy(source_types=("TEXT",), parser_versions=("text-parser-v0",))

    result = text_vector_search_tool("text query", policy, retriever=retriever)

    assert len(result.evidence) == 1
    assert TEXT_VECTOR_READINESS_WARNING in result.evidence[0].verification_warnings


def test_index_version_mismatch_is_rejected():
    result = pdf_vector_search_tool(
        "pdf query",
        _policy(),
        retriever=_FakeRetriever([_chunk(index_version="wrong-index")]),
    )

    assert result.evidence == ()
    assert FATAL_INDEX_VERSION in result.rejected[0].reasons


def test_parser_version_mismatch_is_rejected():
    result = pdf_vector_search_tool(
        "pdf query",
        _policy(parser_versions=("pdf-extract-v2",)),
        retriever=_FakeRetriever([_chunk(parser_version="pdf-extract-v1")]),
    )

    assert result.evidence == ()
    assert FATAL_PARSER_VERSION in result.rejected[0].reasons


def test_source_file_type_mismatch_is_rejected():
    result = pdf_vector_search_tool(
        "pdf query",
        _policy(source_types=("PDF", "SPREADSHEET")),
        retriever=_FakeRetriever(
            [
                _chunk(
                    source_file_type="SPREADSHEET",
                    parser_version="xlsx-extract-v2-hidden-safe",
                    citation_text="fake.xlsx Sales!A1:D5",
                )
            ]
        ),
    )

    assert result.evidence == ()
    assert FATAL_SOURCE_TYPE in result.rejected[0].reasons


def test_embedding_status_mismatch_is_rejected():
    result = pdf_vector_search_tool(
        "pdf query",
        _policy(),
        retriever=_FakeRetriever([_chunk(embedding_status="PENDING")]),
    )

    assert result.evidence == ()
    assert FATAL_EMBEDDING_STATUS in result.rejected[0].reasons


def test_missing_citation_is_rejected_by_verifier():
    result = pdf_vector_search_tool(
        "pdf query",
        _policy(),
        retriever=_FakeRetriever([_chunk(citation_text="")]),
    )

    assert result.evidence == ()
    assert FATAL_MISSING_CITATION in result.rejected[0].reasons


def test_missing_location_is_rejected_by_verifier():
    result = pdf_vector_search_tool(
        "pdf query",
        _policy(),
        retriever=_FakeRetriever([_chunk(location_json={})]),
    )

    assert result.evidence == ()
    assert FATAL_MISSING_LOCATION in result.rejected[0].reasons


def test_pdf_file_identity_rejects_generic_filename_without_stable_identity():
    result = pdf_vector_search_tool(
        "pdf 파일 찾아줘",
        _policy(),
        retriever=_FakeRetriever(
            [
                _chunk(
                    extra_metadata={
                        "requestedEvidenceLane": "pdf_file_document_identity",
                        "genericFilenameIdentity": True,
                        "stableDocumentIdentity": False,
                    }
                )
            ]
        ),
    )

    assert result.evidence == ()
    assert FATAL_PDF_STABLE_IDENTITY_REQUIRED in result.rejected[0].reasons


def test_xlsx_hidden_or_excluded_candidate_is_rejected_before_answer_surface():
    result = xlsx_vector_search_tool(
        "숨김 행 알려줘",
        _policy(
            source_types=("SPREADSHEET",),
            parser_versions=("xlsx-extract-v2-hidden-safe",),
        ),
        retriever=_FakeRetriever(
            [
                _chunk(
                    source_file_type="SPREADSHEET",
                    parser_version="xlsx-extract-v2-hidden-safe",
                    citation_text="fake.xlsx Hidden!A1:B2",
                    extra_metadata={
                        "hidden": True,
                        "excludedRow": True,
                        "policyGuard": "hidden_negative_or_excluded_row_guard",
                    },
                )
            ]
        ),
    )

    assert result.evidence == ()
    assert FATAL_XLSX_HIDDEN_NEGATIVE_OR_EXCLUDED_ROW in result.rejected[0].reasons


def test_backend_identity_exposes_faiss_vector_post_filter_boundary():
    policy = _policy(top_k=3)
    result = pdf_vector_search_tool(
        "pdf query",
        policy,
        retriever=_FakeRetriever([_chunk()]),
    )
    identity = result.backend_identity

    assert identity["backend"] == "faiss"
    assert identity["retrieval_backend"] == "vector"
    assert identity["index_namespace_filter"] == policy.required_index_version
    assert identity["overfetch_k"] > policy.top_k
    assert identity["post_filter_applied"] is True
    assert identity["production_filter_enforcement"] is False
    assert identity["library_search_used"] is False


def test_output_shape_is_compatible_with_fake_tool_result_shape():
    result = pdf_vector_search_tool(
        "pdf query",
        _policy(),
        retriever=_FakeRetriever([_chunk()]),
    )

    assert set(result.to_dict()) == {
        "tool",
        "evidence",
        "rejected",
        "backend_identity",
    }


def test_wrapper_calls_retriever_only_not_library_search():
    retriever = _FakeRetriever([_chunk()])

    result = pdf_vector_search_tool("pdf query", _policy(), retriever=retriever)

    assert len(retriever.calls) == 1
    assert result.backend_identity["library_search_used"] is False


def _location_type(source_file_type: str) -> str:
    if source_file_type == "PDF":
        return "pdf"
    if source_file_type == "SPREADSHEET":
        return "xlsx"
    return "text"


def _chunk_type(source_file_type: str) -> str:
    if source_file_type == "PDF":
        return "pdf_page"
    if source_file_type == "SPREADSHEET":
        return "xlsx_table"
    return "text_span"


def _extension(source_file_type: str) -> str:
    if source_file_type == "PDF":
        return "pdf"
    if source_file_type == "SPREADSHEET":
        return "xlsx"
    return "txt"
