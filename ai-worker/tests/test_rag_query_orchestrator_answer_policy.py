from __future__ import annotations

from dataclasses import replace

import pytest

from app.capabilities.rag_orchestrator.answer_policy import (
    NO_EVIDENCE_MESSAGE,
    build_no_evidence_response,
    prepare_answer_handoff,
    verified_evidence_for_answer,
)
from app.capabilities.rag_orchestrator.evidence import QueryPolicy
from app.capabilities.rag_orchestrator.tools import fake_pdf_vector_search_tool


def _policy() -> QueryPolicy:
    return QueryPolicy(
        request_id="req-1",
        required_index_version="rag-ingestion-v2-candidate",
        allowed_source_file_types=["PDF"],
        allowed_parser_versions=["pdf-extract-v2"],
    )


def test_no_verified_evidence_returns_no_evidence_response():
    response = build_no_evidence_response(query="무엇인가요?")

    assert response.status == "blocked"
    assert response.answer == NO_EVIDENCE_MESSAGE
    assert response.used_evidence_ids == ()
    assert response.reason == "no_verified_evidence"


def test_unverified_evidence_only_blocks_answer_handoff():
    verified = fake_pdf_vector_search_tool("pdf", _policy()).evidence[0]
    unverified = replace(
        verified,
        evidence_id="unverified",
        verification_status="unchecked",
    )

    response = prepare_answer_handoff(query="pdf?", evidence=[unverified])

    assert response.status == "blocked"
    assert response.answer == NO_EVIDENCE_MESSAGE
    assert response.verified_evidence == ()


def test_verified_evidence_can_be_handed_to_answer_synthesis():
    evidence = fake_pdf_vector_search_tool("pdf", _policy()).evidence[0]

    response = prepare_answer_handoff(query="pdf?", evidence=[evidence])

    assert response.status == "ready"
    assert response.answer == ""
    assert response.used_evidence_ids == (evidence.evidence_id,)
    assert response.verified_evidence == (evidence,)


def test_used_evidence_ids_must_be_from_verified_set():
    evidence = fake_pdf_vector_search_tool("pdf", _policy()).evidence[0]

    with pytest.raises(ValueError, match="verified evidence ids"):
        prepare_answer_handoff(
            query="pdf?",
            evidence=[evidence],
            used_evidence_ids=[evidence.evidence_id, "outside-id"],
        )


def test_explicit_empty_used_evidence_ids_remains_empty():
    evidence = fake_pdf_vector_search_tool("pdf", _policy()).evidence[0]

    response = prepare_answer_handoff(
        query="pdf?",
        evidence=[evidence],
        used_evidence_ids=[],
    )

    assert response.status == "ready"
    assert response.used_evidence_ids == ()


def test_verified_evidence_filter_excludes_unverified_items():
    evidence = fake_pdf_vector_search_tool("pdf", _policy()).evidence[0]
    unverified = replace(
        evidence,
        evidence_id="unverified",
        verification_status="rejected",
    )

    assert verified_evidence_for_answer([unverified, evidence]) == (evidence,)
