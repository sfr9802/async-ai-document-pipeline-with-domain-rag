"""Default-off non-production product-preview RAG HTTP DTO bridge."""

from __future__ import annotations

from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, Field

from app.capabilities.rag_orchestrator.phase1_diagnostic_runtime import (
    RagDiagnosticQueryRequest,
    RagDiagnosticQueryResponse,
    SourceFirstRagService,
)

PRODUCT_PREVIEW_ROUTE_PATH = "/api/rag/query"
PRODUCT_PREVIEW_FEATURE_FLAG_NAME = "RAG_PRODUCT_PREVIEW_ROUTE_ENABLED"
PRODUCT_PREVIEW_SETTINGS_FEATURE_FIELD = "rag_product_preview_route_enabled"
PRODUCT_PREVIEW_RUN_KEY = "v5_6_1_fastapi_product_runtime_bridge_and_frontend_e2e_preview_nonprod"

FORBIDDEN_PREVIEW_KEYS = {
    "anchor_locator",
    "expected_answer",
    "gold_label",
    "gold_locator",
    "gold_qrels",
    "hidden_locator",
    "namespace",
    "prompt",
    "raw_locator",
    "raw_llm_response",
    "raw_prompt",
    "raw_response",
    "source_identity",
    "source_path",
    "source_pdf_path",
    "supporting_evidence_id",
    "supporting_evidence_ids",
    "target_locator",
    "workbook",
    "workbook_or_source_path",
}


class RagProductPreviewQueryRequest(BaseModel):
    query: str = Field(min_length=1)
    locale: str | None = None
    language: str | None = None
    session_id: str | None = None
    source_family: Literal["PDF", "XLSX", "TEXT"] | None = None
    file_id: str | None = None
    sheet: str | None = None
    page: int | None = None
    locator_text: str | None = None
    active_context: dict[str, Any] | None = None

    model_config = {"extra": "ignore"}


class RagProductPreviewResponse(BaseModel):
    answer: str
    status: Literal[
        "answered",
        "insufficient_context",
        "backend_unavailable",
        "unsupported",
        "validation_error",
    ]
    citations: list[dict[str, Any]] = Field(default_factory=list)
    evidence_cards: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    route: str = PRODUCT_PREVIEW_ROUTE_PATH
    feature_flag: str = PRODUCT_PREVIEW_FEATURE_FLAG_NAME
    run_key: str = PRODUCT_PREVIEW_RUN_KEY
    non_production_preview: bool = True
    production_routing: bool = False
    official_metric: bool = False
    promotion_evidence: bool = False
    product_success_evidence_allowed: bool = False
    live_db_index_cache_readiness: bool = False


def run_product_preview_query(
    service: SourceFirstRagService,
    request: RagProductPreviewQueryRequest,
) -> RagProductPreviewResponse:
    diagnostic_response = service.query(_to_diagnostic_request(request))
    status = _status_from_diagnostic(diagnostic_response)
    answer = diagnostic_response.final_answer if status == "answered" else ""
    return RagProductPreviewResponse(
        answer=answer,
        status=status,
        citations=_preview_citations(diagnostic_response),
        evidence_cards=_preview_evidence_cards(diagnostic_response),
        diagnostics=_preview_diagnostics(diagnostic_response),
    )


def _to_diagnostic_request(request: RagProductPreviewQueryRequest) -> RagDiagnosticQueryRequest:
    active_context = _active_context(request)
    source_family = _clean(request.source_family) or _clean(active_context.get("source_family"))
    file_id = _clean(request.file_id) or _clean(active_context.get("file_id"))
    sheet_name = _clean(request.sheet) or _clean(active_context.get("sheet"))
    page = request.page if request.page is not None else _int_or_none(active_context.get("page"))
    locator_text = _clean(request.locator_text) or _clean(active_context.get("locator_text"))
    cell = locator_text if _looks_like_cell(locator_text) else ""
    cell_range = locator_text if _looks_like_range(locator_text) else ""
    diagnostic_active_context = {
        key: value
        for key, value in active_context.items()
        if key in {"active_source_atom_id", "active_source_atom_ids", "source_atom_id", "source_atom_ids"}
    }
    return RagDiagnosticQueryRequest(
        query=request.query,
        source_family=source_family or None,
        file_id=file_id or None,
        source_identity=file_id or None,
        workbook_id=file_id or None,
        sheet_name=sheet_name or None,
        cell=cell or None,
        range=cell_range or None,
        page=page,
        active_context=diagnostic_active_context,
        tenant_id="diagnostic-local",
        debug=False,
    )


def _active_context(request: RagProductPreviewQueryRequest) -> dict[str, Any]:
    raw = request.active_context if isinstance(request.active_context, Mapping) else {}
    allowed: dict[str, Any] = {}
    for key in (
        "source_family",
        "file_id",
        "sheet",
        "page",
        "locator_text",
        "active_source_atom_id",
        "active_source_atom_ids",
        "source_atom_id",
        "source_atom_ids",
    ):
        if key in raw and raw[key] not in (None, "", [], {}):
            allowed[key] = raw[key]
    return allowed


def _status_from_diagnostic(response: RagDiagnosticQueryResponse) -> str:
    if response.answer_allowed_by_policy:
        return "answered"
    reason = _clean(response.fail_closed_reason or response.response_policy_bucket).upper()
    if "UNAVAILABLE" in reason or reason in {"CACHE_NAMESPACE_MISMATCH", "CONTRACT_VIOLATION"}:
        return "backend_unavailable"
    if "UNSUPPORTED" in reason or "OUT_OF_BOUNDS" in reason:
        return "unsupported"
    return "insufficient_context"


def _preview_citations(response: RagDiagnosticQueryResponse) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for index, raw in enumerate(response.citations):
        citation = _sanitize_for_preview(raw)
        if isinstance(citation, dict):
            if index < len(response.selected_source_atom_ids):
                citation.setdefault("source_atom_id", response.selected_source_atom_ids[index])
            citation.setdefault("citation_key", _citation_key(citation, index))
            citations.append(citation)
    return citations if response.answer_allowed_by_policy else []


def _preview_evidence_cards(response: RagDiagnosticQueryResponse) -> list[dict[str, Any]]:
    if not response.answer_allowed_by_policy:
        return []
    cards: list[dict[str, Any]] = []
    for bundle in response.evidence_bundles:
        family = _clean(bundle.get("source_family")).upper()
        card: dict[str, Any] = {
            "source_atom_id": _clean(bundle.get("source_atom_id")),
            "source_family": family,
            "kind": family.lower(),
            "matched_text": _clean(bundle.get("matched_text_or_value")),
            "evidence_truth_source": _clean(bundle.get("evidence_truth_source")) or "source_atom_evidence_bundle",
        }
        if family == "XLSX":
            xlsx = _mapping(bundle.get("xlsx_evidence"))
            metadata = _mapping(xlsx.get("xlsx_display_metadata"))
            card.update(
                {
                    "display_value": _clean(metadata.get("display_value")) or card["matched_text"],
                    "sheet": _clean(xlsx.get("sheet")),
                    "table_or_range": _clean(xlsx.get("table_or_range")),
                    "matched_cells": list(_sequence(xlsx.get("matched_cells"))),
                    "formula_text_visible_to_user": bool(metadata.get("formula_text_visible_to_user")),
                    "formula_evaluation_at_query_time": bool(metadata.get("formula_evaluation_at_query_time")),
                }
            )
        elif family == "PDF":
            pdf = _mapping(bundle.get("pdf_evidence"))
            card.update(
                {
                    "page": pdf.get("page"),
                    "bbox": pdf.get("bbox") or [],
                    "region_type": _clean(pdf.get("region_type")),
                }
            )
        elif family == "TEXT":
            text = _mapping(bundle.get("text_evidence"))
            card.update(
                {
                    "section": text.get("parent_paragraph_or_section") or [],
                    "text_span": _clean(text.get("text_span")),
                }
            )
        cards.append(_sanitize_for_preview(card))
    return [card for card in cards if isinstance(card, dict)]


def _preview_diagnostics(response: RagDiagnosticQueryResponse) -> dict[str, Any]:
    return {
        "redacted": True,
        "request_id": response.request_id,
        "status_bucket": response.response_policy_bucket,
        "response_policy_bucket": response.response_policy_bucket,
        "fail_closed_reason": response.fail_closed_reason,
        "llm_invoked": response.llm_invoked,
        "warnings": list(response.warnings),
        "evidence_truth_source": response.evidence_truth_source,
        "search_view_candidate_metadata_only": response.search_view_candidate_metadata_only,
        "vector_payload_used_as_evidence_truth": response.vector_payload_used_as_evidence_truth,
        "selected_source_atom_count": len(response.selected_source_atom_ids),
        "official_metric_input_rows": 0,
        "protected_namespaces_touched": [],
        "production_db_mutated": False,
        "index_rebuilt": False,
        "cache_mutated": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }


def _sanitize_for_preview(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for raw_key, raw_child in value.items():
            key = str(raw_key)
            if key in FORBIDDEN_PREVIEW_KEYS:
                if key == "source_identity":
                    source_hash = _clean(value.get("source_identity_hash"))
                    if source_hash:
                        sanitized["source_identity_hash"] = source_hash
                continue
            if key.endswith("_hash"):
                sanitized[key] = raw_child
                continue
            sanitized[key] = _sanitize_for_preview(raw_child)
        return sanitized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_sanitize_for_preview(item) for item in value]
    if isinstance(value, str) and _looks_like_local_path(value):
        return "__redacted__"
    return value


def _citation_key(citation: Mapping[str, Any], index: int) -> str:
    text_locator = _mapping(citation.get("text_locator"))
    identity = {
        "index": index,
        "source_atom_id": _clean(citation.get("source_atom_id")),
        "source_family": _clean(citation.get("source_family")),
        "locator_fingerprint": _clean(citation.get("locator_fingerprint")),
        "search_unit_id": _clean(citation.get("search_unit_id")),
        "page": citation.get("page"),
        "bbox": citation.get("bbox") or [],
        "chunk_id": _clean(citation.get("chunk_id") or text_locator.get("chunk_id")),
        "section": citation.get("section") or [],
        "text_span": _clean(citation.get("text_span")),
        "sheet": _clean(citation.get("sheet")),
        "table_or_range": _clean(citation.get("table_or_range")),
        "matched_cells": list(_sequence(citation.get("matched_cells"))),
    }
    import hashlib
    import json

    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return f"citation:{digest[:16]}"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> tuple[Any, ...]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(value)
    return ()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _looks_like_cell(value: str) -> bool:
    import re

    return bool(re.match(r"^[A-Z]{1,3}[1-9][0-9]*$", _clean(value).upper()))


def _looks_like_range(value: str) -> bool:
    import re

    return bool(re.match(r"^[A-Z]{1,3}[1-9][0-9]*:[A-Z]{1,3}[1-9][0-9]*$", _clean(value).upper()))


def _looks_like_local_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return "://" not in normalized and (
        ":/" in normalized or normalized.startswith(("/data/", "/home/", "/mnt/", "/private/", "/tmp/", "/Users/"))
    )
