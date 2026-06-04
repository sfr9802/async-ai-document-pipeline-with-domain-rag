from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "ai") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai"))

from app.api import create_app  # noqa: E402
from app.capabilities.rag_orchestrator.phase1_diagnostic_runtime import (  # noqa: E402
    SourceFirstRagService,
    XlsxDisplayContract,
    build_diagnostic_xlsx_source_atom,
)
from app.capabilities.rag_orchestrator.product_preview_runtime import (  # noqa: E402
    PRODUCT_PREVIEW_ROUTE_PATH,
)
from app.core.config import WorkerSettings  # noqa: E402


FORBIDDEN_RESPONSE_STRINGS = (
    "raw prompt",
    "raw response",
    "expected answer",
    "gold label",
    "gold locator",
    "target locator",
    "official_metric_input_rows_payload",
    "expected_answer_ko",
    "supporting_evidence_id",
    "supporting_evidence_ids",
    "supporting_evidence_note",
    "gold_status",
    "include_in_official_denominator",
    "citation_locator",
    "D:/private",
    "SecretWorkbook.xlsx",
    "XLSX:SecretWorkbook.xlsx",
)


class LlmRecorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, payload: dict[str, object]) -> str:
        self.calls.append(payload)
        return f"preview answer: {payload['rendered_value']}"


def enabled_settings(**overrides: object) -> WorkerSettings:
    return WorkerSettings(rag_product_preview_route_enabled=True, **overrides)


def xlsx_atom(
    atom_id: str = "xlsx-a1",
    *,
    workbook: str = "SecretWorkbook.xlsx",
    sheet: str = "Sheet1",
    cell: str = "A1",
    display_value: str = "75%",
) -> dict[str, object]:
    return build_diagnostic_xlsx_source_atom(
        atom_id,
        workbook=workbook,
        sheet=sheet,
        cell=cell,
        cell_range=cell,
        display_contract=XlsxDisplayContract(
            raw_value="0.75",
            normalized_value="0.75",
            display_value=display_value,
            number_format="0%",
            value_type="percentage",
            formula_cached_value="75%",
        ),
    )


def text_atom(atom_id: str = "text-a1") -> dict[str, object]:
    return {
        "source_atom_id": atom_id,
        "source_family": "TEXT",
        "source_identity": "TEXT:private-note",
        "document_id": "doc-text",
        "document_version_id": "doc-text:v1",
        "tenant_id": "diagnostic-local",
        "content_hash": hashlib.sha256(atom_id.encode("utf-8")).hexdigest(),
        "extraction_version": "test-preview-v1",
        "normalized_text_or_value_snapshot": "텍스트 근거 본문",
        "parent_pointers": {"preview_test": True},
        "canonical_citation_payload": {
            "source_family": "TEXT",
            "source_atom_id": atom_id,
            "title": "문서 발췌",
            "section": "개요",
            "source_identity": "TEXT:private-note",
            "locator_fingerprint": f"fp:{atom_id}",
            "search_unit_id": f"su:{atom_id}",
            "document_id": "doc-text",
            "text_locator": {
                "document_id": "doc-text",
                "chunk_id": "chunk-1",
                "section_path": ["개요"],
                "text_span": "1:12",
            },
        },
        "raw_locator": {
            "chunk_id": "chunk-1",
            "section_path": ["개요"],
            "text_span": "1:12",
            "source_identity": "TEXT:private-note",
        },
        "source_registry_version": "source-registry-v1",
        "raw_file_exists": False,
        "extraction_snapshot_present": True,
    }


def pdf_atom(atom_id: str = "pdf-a1") -> dict[str, object]:
    return {
        "source_atom_id": atom_id,
        "source_family": "PDF",
        "source_identity": "PDF:private-report",
        "document_id": "pdf-doc",
        "document_version_id": "pdf-doc:v1",
        "tenant_id": "diagnostic-local",
        "content_hash": hashlib.sha256(atom_id.encode("utf-8")).hexdigest(),
        "extraction_version": "test-preview-v1",
        "normalized_text_or_value_snapshot": "PDF 근거 본문",
        "parent_pointers": {"preview_test": True},
        "canonical_citation_payload": {
            "source_family": "PDF",
            "source_atom_id": atom_id,
            "page": 3,
            "physical_page_index": 2,
            "bbox": [10, 20, 30, 40],
            "region_type": "paragraph",
            "source_identity": "PDF:private-report",
            "file_name": "report.pdf",
            "source_pdf_path": "D:/private/report.pdf",
            "source_path": "D:/private/report.pdf",
            "document_version_id": "pdf-doc:v1",
            "locator_fingerprint": f"fp:{atom_id}",
            "search_unit_id": f"su:{atom_id}",
        },
        "raw_locator": {
            "file_name": "report.pdf",
            "page": 3,
            "physical_page_index": 2,
            "bbox": [10, 20, 30, 40],
            "region_type": "paragraph",
            "source_pdf_path": "D:/private/report.pdf",
            "source_path": "D:/private/report.pdf",
        },
        "source_registry_version": "source-registry-v1",
        "raw_file_exists": False,
        "extraction_snapshot_present": True,
    }


def post_preview(
    service: SourceFirstRagService,
    payload: dict[str, Any],
    *,
    settings: WorkerSettings | None = None,
) -> TestClient:
    client = TestClient(
        create_app(
            settings=settings or enabled_settings(),
            rag_product_preview_service=service,
        )
    )
    return client.post(PRODUCT_PREVIEW_ROUTE_PATH, json=payload)


def assert_no_forbidden_payload_leak(response_text: str) -> None:
    for value in FORBIDDEN_RESPONSE_STRINGS:
        assert value not in response_text
    assert '"raw_prompt"' not in response_text
    assert '"raw_response"' not in response_text
    assert '"raw_llm_response"' not in response_text
    assert '"expected_answer"' not in response_text
    assert '"gold_' not in response_text
    assert '"target_' not in response_text
    assert '"official_metric_input_rows_payload"' not in response_text
    assert '"expected_answer_ko"' not in response_text
    assert '"supporting_evidence_note"' not in response_text
    assert '"include_in_official_denominator"' not in response_text
    assert '"citation_locator"' not in response_text


def test_product_rag_preview_route_is_default_disabled_and_production_disabled() -> None:
    disabled_client = TestClient(create_app(settings=WorkerSettings()))
    disabled = disabled_client.post(PRODUCT_PREVIEW_ROUTE_PATH, json={"query": "A1 값"})
    assert disabled.status_code == 404
    assert disabled.json()["detail"] == "product preview RAG route disabled"

    production_client = TestClient(
        create_app(settings=enabled_settings(rag_query_orchestrator_mode="production"))
    )
    production = production_client.post(PRODUCT_PREVIEW_ROUTE_PATH, json={"query": "A1 값"})
    assert production.status_code == 404
    assert production.json()["detail"] == "product preview RAG route disabled"


def test_product_rag_preview_enabled_success_returns_frontend_safe_dto_without_gold_or_raw_leakage() -> None:
    recorder = LlmRecorder()
    service = SourceFirstRagService(
        source_atoms=[xlsx_atom()],
        llm_invoker=recorder,
        index_available=True,
        source_atom_store_available=True,
    )

    response = post_preview(
        service,
        {
            "query": "SecretWorkbook.xlsx Sheet1 A1 값을 알려줘",
            "locale": "ko-KR",
            "session_id": "session-1",
            "active_context": {
                "source_family": "XLSX",
                "file_id": "SecretWorkbook.xlsx",
                "sheet": "Sheet1",
                "locator_text": "A1",
                "gold_locator": "must not leak",
                "expected_answer": "must not leak",
                "raw_prompt": "raw prompt",
                "raw_response": "raw response",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["answer"] == "preview answer: 75%"
    assert body["route"] == PRODUCT_PREVIEW_ROUTE_PATH
    assert body["non_production_preview"] is True
    assert body["production_routing"] is False
    assert body["official_metric"] is False
    assert body["promotion_evidence"] is False
    assert body["product_success_evidence_allowed"] is False
    assert body["live_db_index_cache_readiness"] is False
    assert body["diagnostics"]["redacted"] is True
    assert body["diagnostics"]["llm_invoked"] is True
    assert body["diagnostics"]["evidence_truth_source"] == "source_atom_evidence_bundle"
    assert body["diagnostics"]["search_view_candidate_metadata_only"] is True
    assert body["diagnostics"]["vector_payload_used_as_evidence_truth"] is False
    assert body["citations"][0]["source_family"] == "XLSX"
    assert body["citations"][0]["source_identity_hash"]
    assert "source_identity" not in body["citations"][0]
    assert body["evidence_cards"][0]["source_family"] == "XLSX"
    assert body["evidence_cards"][0]["display_value"] == "75%"
    assert body["evidence_cards"][0]["formula_text_visible_to_user"] is False
    assert body["evidence_cards"][0]["formula_evaluation_at_query_time"] is False
    assert len(recorder.calls) == 1
    assert_no_forbidden_payload_leak(response.text)


def test_product_rag_preview_backend_unavailable_and_deictic_queries_fail_closed_without_llm() -> None:
    unavailable_recorder = LlmRecorder()
    unavailable_service = SourceFirstRagService(
        source_atoms=[xlsx_atom()],
        llm_invoker=unavailable_recorder,
        index_available=False,
    )
    unavailable = post_preview(
        unavailable_service,
        {
            "query": "SecretWorkbook.xlsx Sheet1 A1 값",
            "active_context": {"source_family": "XLSX", "file_id": "SecretWorkbook.xlsx", "sheet": "Sheet1", "locator_text": "A1"},
        },
    ).json()
    assert unavailable["status"] == "backend_unavailable"
    assert unavailable["answer"] == ""
    assert unavailable["diagnostics"]["llm_invoked"] is False
    assert unavailable_recorder.calls == []

    deictic_recorder = LlmRecorder()
    deictic_service = SourceFirstRagService(
        source_atoms=[xlsx_atom()],
        llm_invoker=deictic_recorder,
        index_available=True,
    )
    deictic = post_preview(deictic_service, {"query": "이 표 값은?", "locale": "ko-KR"}).json()
    assert deictic["status"] == "insufficient_context"
    assert deictic["answer"] == ""
    assert deictic["citations"] == []
    assert deictic["evidence_cards"] == []
    assert deictic["diagnostics"]["response_policy_bucket"] == "CONTEXT_REQUIRED"
    assert deictic["diagnostics"]["llm_invoked"] is False
    assert deictic_recorder.calls == []


def test_product_rag_preview_citation_and_evidence_cards_support_text_pdf_and_xlsx_shapes() -> None:
    cases = [
        (
            "TEXT",
            text_atom(),
            {"query": "텍스트 근거", "active_context": {"source_family": "TEXT"}},
            {"citation_keys": {"source_family", "source_atom_id", "title", "section"}, "evidence_kind": "text"},
        ),
        (
            "PDF",
            pdf_atom(),
            {"query": "report.pdf page 3 내용", "active_context": {"source_family": "PDF", "file_id": "report.pdf", "page": 3}},
            {"citation_keys": {"source_family", "source_atom_id", "page", "bbox"}, "evidence_kind": "pdf"},
        ),
        (
            "XLSX",
            xlsx_atom(),
            {"query": "SecretWorkbook.xlsx Sheet1 A1 값", "active_context": {"source_family": "XLSX", "file_id": "SecretWorkbook.xlsx", "sheet": "Sheet1", "locator_text": "A1"}},
            {"citation_keys": {"source_family", "source_atom_id", "source_identity_hash"}, "evidence_kind": "xlsx"},
        ),
    ]

    for family, source_atom, payload, expected in cases:
        service = SourceFirstRagService(
            source_atoms=[source_atom],
            llm_invoker=LlmRecorder(),
            index_available=True,
            source_atom_store_available=True,
        )
        response = post_preview(service, payload)
        assert response.status_code == 200, family
        body = response.json()
        assert body["status"] == "answered", family
        assert body["citations"], family
        assert expected["citation_keys"] <= set(body["citations"][0]), family
        assert body["evidence_cards"][0]["source_family"] == family
        assert body["evidence_cards"][0]["kind"] == expected["evidence_kind"]
        assert_no_forbidden_payload_leak(response.text)


def test_product_rag_preview_preserves_duplicate_supporting_evidence_id_rows_by_locator() -> None:
    first = text_atom("text-dup-a")
    second = text_atom("text-dup-b")
    first["canonical_citation_payload"]["supporting_evidence_id"] = "shared-supporting-evidence"
    first["canonical_citation_payload"]["locator_fingerprint"] = "locator-row-a"
    first["canonical_citation_payload"]["title"] = "문서 발췌 A"
    second["canonical_citation_payload"]["supporting_evidence_id"] = "shared-supporting-evidence"
    second["canonical_citation_payload"]["locator_fingerprint"] = "locator-row-b"
    second["canonical_citation_payload"]["title"] = "문서 발췌 B"
    service = SourceFirstRagService(
        source_atoms=[first, second],
        llm_invoker=LlmRecorder(),
        index_available=True,
        source_atom_store_available=True,
    )

    response = post_preview(
        service,
        {
            "query": "두 텍스트 근거를 요약해줘",
            "active_context": {
                "source_family": "TEXT",
                "source_atom_ids": ["text-dup-a", "text-dup-b"],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert len(body["citations"]) == 2
    assert "shared-supporting-evidence" not in response.text
    assert all("supporting_evidence_id" not in citation for citation in body["citations"])
    assert {citation["source_atom_id"] for citation in body["citations"]} == {"text-dup-a", "text-dup-b"}
    assert {citation["locator_fingerprint"] for citation in body["citations"]} == {
        "locator-row-a",
        "locator-row-b",
    }
    assert len({citation["citation_key"] for citation in body["citations"]}) == 2
    assert len(body["evidence_cards"]) == 2
    assert {card["source_atom_id"] for card in body["evidence_cards"]} == {"text-dup-a", "text-dup-b"}
    assert_no_forbidden_payload_leak(response.text)


def test_product_rag_preview_validation_errors_and_mutation_surfaces_are_redacted() -> None:
    client = TestClient(create_app(settings=enabled_settings()))

    invalid = client.post(
        PRODUCT_PREVIEW_ROUTE_PATH,
        json={
            "query": "",
            "raw_prompt": "raw prompt",
            "expected_answer": "expected answer",
            "gold_label": "gold label",
        },
    )
    assert invalid.status_code == 422
    assert_no_forbidden_payload_leak(invalid.text)

    service = SourceFirstRagService(source_atoms=[xlsx_atom()], llm_invoker=LlmRecorder())
    response = post_preview(
        service,
        {
            "query": "SecretWorkbook.xlsx Sheet1 A1 값",
            "active_context": {
                "source_family": "XLSX",
                "file_id": "SecretWorkbook.xlsx",
                "sheet": "Sheet1",
                "locator_text": "A1",
                "namespace": "production-index",
                "cache_namespace": "production-cache",
            },
        },
    )
    body = response.json()
    serialized = json.dumps(body, ensure_ascii=False)
    assert body["diagnostics"]["protected_namespaces_touched"] == []
    assert body["diagnostics"]["production_db_mutated"] is False
    assert body["diagnostics"]["index_rebuilt"] is False
    assert body["diagnostics"]["cache_mutated"] is False
    assert "production-index" not in serialized
    assert "production-cache" not in serialized
