from __future__ import annotations

import pytest

from app.capabilities.rag_orchestrator.evidence import (
    EVIDENCE_CONTRACT_VERSION,
    EMBEDDING_STATUS_EMBEDDED,
    RETRIEVAL_BACKEND_VECTOR,
    Evidence,
    QueryPolicy,
)


def test_query_policy_is_code_created_and_normalizes_filters():
    policy = QueryPolicy(
        request_id=" req-1 ",
        required_index_version="rag-ingestion-v2-candidate",
        allowed_source_file_types=["pdf", "spreadsheet"],
        allowed_parser_versions=["pdf-extract-v2", "xlsx-extract-v2-hidden-safe"],
        acl_tags=[" team-a "],
    )

    assert policy.request_id == "req-1"
    assert policy.allowed_source_file_types == ("PDF", "SPREADSHEET")
    assert policy.allowed_parser_versions == (
        "pdf-extract-v2",
        "xlsx-extract-v2-hidden-safe",
    )
    assert policy.required_embedding_status == EMBEDDING_STATUS_EMBEDDED
    assert policy.created_by == "code"

    body = policy.to_dict()
    assert body["createdBy"] == "code"
    assert body["allowedSourceFileTypes"] == ["PDF", "SPREADSHEET"]
    assert body["aclTags"] == ["team-a"]
    assert EVIDENCE_CONTRACT_VERSION == "rag-evidence-v0"


def test_query_policy_cannot_be_marked_llm_created():
    with pytest.raises(TypeError):
        QueryPolicy(
            request_id="req-1",
            required_index_version="idx",
            allowed_source_file_types=["PDF"],
            allowed_parser_versions=["pdf-v1"],
            created_by="llm",
        )


def test_query_policy_requires_fail_closed_filters():
    with pytest.raises(ValueError, match="allowed_source_file_types"):
        QueryPolicy(
            request_id="req-1",
            required_index_version="idx",
            allowed_source_file_types=[],
            allowed_parser_versions=["pdf-v1"],
        )


def test_query_policy_requires_parser_allowlist():
    with pytest.raises(ValueError, match="allowed_parser_versions"):
        QueryPolicy(
            request_id="req-1",
            required_index_version="idx",
            allowed_source_file_types=["PDF"],
            allowed_parser_versions=[],
        )


def test_evidence_contract_serializes_same_nested_shape():
    evidence = Evidence(
        evidence_id="ev-1",
        retrieval_backend=RETRIEVAL_BACKEND_VECTOR,
        rank=1,
        source_file_id="source-1",
        source_file_name="report.pdf",
        source_file_type="pdf",
        document_id="doc-1",
        document_version_id="docver-1",
        parsed_artifact_id="artifact-1",
        index_version="rag-ingestion-v2-candidate",
        embedding_status="embedded",
        embedding_model="bge-m3",
        embedding_text_sha256="sha256",
        vector_id="rag-ingestion-v2-candidate:ev-1",
        parser_name="pdf-parser",
        parser_version="pdf-extract-v2",
        search_unit_id="unit-1",
        chunk_id="chunk-1",
        unit_type="PAGE",
        unit_key="page:2",
        chunk_type="pdf_page",
        text="A verified paragraph from page two.",
        display_text="page two paragraph",
        citation_text="report.pdf p. 2",
        location_type="pdf",
        location_json={"page_no": 2, "page_label": "2"},
        scores={"dense": 0.91, "final": 0.91},
        acl_tags=["team-a"],
    )

    body = evidence.to_dict()

    assert body["evidenceContractVersion"] == EVIDENCE_CONTRACT_VERSION
    assert body["retrievalBackend"] == RETRIEVAL_BACKEND_VECTOR
    assert body["source"]["sourceFileType"] == "PDF"
    assert body["index"]["embeddingStatus"] == EMBEDDING_STATUS_EMBEDDED
    assert body["unit"]["searchUnitId"] == "unit-1"
    assert body["content"]["citationText"] == "report.pdf p. 2"
    assert body["location"]["locationJson"] == {"page_no": 2, "page_label": "2"}
    assert body["policy"]["aclTags"] == ["team-a"]
    assert body["verification"] == {
        "status": "unchecked",
        "reasons": [],
        "warnings": [],
    }


def test_evidence_rejects_unknown_contract_version():
    with pytest.raises(ValueError, match="unsupported evidence_contract_version"):
        Evidence(
            evidence_contract_version="other.v1",
            evidence_id="ev-1",
            retrieval_backend=RETRIEVAL_BACKEND_VECTOR,
            rank=1,
            source_file_id="source-1",
            source_file_type="PDF",
            index_version="idx",
            embedding_status=EMBEDDING_STATUS_EMBEDDED,
            parser_version="pdf-v1",
            citation_text="citation",
            location_json={"page_no": 1},
            search_unit_id="unit-1",
            chunk_id="chunk-1",
            text="text",
        )
