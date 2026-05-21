"""Runtime-safe SearchUnit citation helpers for RAG answers.

This module owns the pure citation/adaptor contract that used to live inside
the large diagnostic runner. It deliberately depends only on runtime RAG
types, so FastAPI/worker code can reuse it without importing report writers or
eval-only state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.capabilities.rag.retrieval_contract import citation_payload

SEARCH_UNIT_CITATION_PAYLOAD_MISSING = "SEARCH_UNIT_CITATION_PAYLOAD_MISSING"
SEARCH_UNIT_SOURCE_IDENTITY_MISSING = "SEARCH_UNIT_SOURCE_IDENTITY_MISSING"
SEARCH_UNIT_LOCATOR_INCOMPLETE = "SEARCH_UNIT_LOCATOR_INCOMPLETE"
STRUCTURED_LOCATOR_DROPPED = "STRUCTURED_LOCATOR_DROPPED"
OFF_TRACK_CITATION_FOR_QUERY_TRACK = "OFF_TRACK_CITATION_FOR_QUERY_TRACK"
SAME_TRACK_LOCATOR_INCOMPLETE = "SAME_TRACK_LOCATOR_INCOMPLETE"
SEARCH_UNIT_MANIFEST_MISMATCH = "SEARCH_UNIT_MANIFEST_MISMATCH"

TEXT_REQUIRED_CITATION_FIELDS = (
    "document_id",
    "document_version_id",
    "search_unit_id",
    "text_locator",
)
XLSX_REQUIRED_CITATION_FIELDS = (
    "workbook",
    "sheet",
    "range",
    "cell",
    "row_label",
    "target_column",
    "normalized_value",
    "search_unit_id",
    "document_version_id",
)
PDF_REQUIRED_CITATION_FIELDS = (
    "source_pdf_path",
    "page",
    "physical_page_index",
    "bbox",
    "region_type",
    "row_label",
    "target_column",
    "search_unit_id",
    "document_version_id",
)
REQUIRED_CITATION_FIELDS_BY_TRACK = {
    "text_namu_v2_1": TEXT_REQUIRED_CITATION_FIELDS,
    "xlsx_business_structured": XLSX_REQUIRED_CITATION_FIELDS,
    "pdf_business_ocr_mm": PDF_REQUIRED_CITATION_FIELDS,
}
SOURCE_FAMILY_BY_TRACK = {
    "text_namu_v2_1": "text",
    "xlsx_business_structured": "xlsx",
    "pdf_business_ocr_mm": "pdf",
}
LOCATOR_SCHEMA_BY_TRACK = {
    "text_namu_v2_1": "text_locator_v1",
    "xlsx_business_structured": "xlsx_cell_v1",
    "pdf_business_ocr_mm": "pdf_source_bound_v1",
}
STRUCTURED_TRACKS = {"xlsx_business_structured", "pdf_business_ocr_mm"}


def source_family_for_track(track: str) -> str:
    return SOURCE_FAMILY_BY_TRACK.get(clean_any(track), "")


def locator_schema_for_track(track: str) -> str:
    return LOCATOR_SCHEMA_BY_TRACK.get(clean_any(track), "")


def scored_citation_contract(
    citations: Sequence[Mapping[str, Any]],
    *,
    track: str,
) -> dict[str, Any]:
    scored: list[Mapping[str, Any]] = []
    discarded_off_track: list[Mapping[str, Any]] = []
    same_track_invalid: list[Mapping[str, Any]] = []
    scored_indices: list[int] = []
    for index, citation in enumerate(citations):
        validation = citation_validation(citation)
        if validation.get("off_track") is True:
            discarded_off_track.append(citation)
            continue
        if validation.get("ok") is True:
            scored.append(citation)
            scored_indices.append(index)
        else:
            same_track_invalid.append(citation)
    primary_failure = None
    if same_track_invalid:
        primary_failure = citation_validation(same_track_invalid[0])
    elif discarded_off_track:
        primary_failure = citation_validation(discarded_off_track[0])
    return {
        "query_track": clean_any(track),
        "scored_citations": scored,
        "scored_generated_citation_indices": scored_indices,
        "discarded_off_track_citations": discarded_off_track,
        "discarded_off_track_citation_count": len(discarded_off_track),
        "same_track_valid_citation_count": len(scored),
        "schema_mismatch_residual_count": len(same_track_invalid),
        "primary_failure_validation": primary_failure or {},
    }


def chunks_from_scored_citation_contract(
    chunks: Sequence[Any],
    citation_contract: Mapping[str, Any],
) -> list[Any]:
    selected: list[Any] = []
    for index in citation_contract.get("scored_generated_citation_indices") or []:
        if isinstance(index, int) and 0 <= index < len(chunks):
            selected.append(chunks[index])
    return selected


def citations_from_chunks(
    chunks: Sequence[Any],
    *,
    track: str = "",
    query_id: str = "",
    require_official_compatible: bool = False,
    structured_adapters_enabled: bool = False,
    allowed_manifest_search_unit_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks[:5]):
        locator = {
            "chunk_id": getattr(chunk, "chunk_id", ""),
            "doc_id": getattr(chunk, "doc_id", ""),
            "search_unit_id": getattr(chunk, "search_unit_id", None),
            "source_file_id": getattr(chunk, "source_file_id", None),
            "source_file_name": getattr(chunk, "source_file_name", None),
            "page_start": getattr(chunk, "page_start", None),
            "page_end": getattr(chunk, "page_end", None),
        }
        canonical_payload = citation_payload(chunk)
        validation = validate_search_unit_citation_payload(
            canonical_payload,
            track=track,
            query_id=query_id,
            require_official_compatible=require_official_compatible,
            original_chunk=chunk,
            allowed_manifest_search_unit_ids=allowed_manifest_search_unit_ids,
        )
        item = {
            "generated_citation_index": index,
            "citation_text": clean_any(getattr(chunk, "text", ""))[:500],
            "locator": {
                key: value for key, value in locator.items() if value not in (None, "")
            },
            "search_unit_citation_payload": canonical_payload,
            "citation_payload_validation": validation,
            "official_compatible_locator": validation["ok"],
            "structured_source_bound_adapter_enabled": bool(structured_adapters_enabled),
            "structured_adapter_output_from_source_bound_search_unit": False,
        }
        if structured_adapters_enabled and validation["ok"]:
            if track == "xlsx_business_structured":
                item["structured_source_bound_adapter"] = xlsx_source_bound_adapter_payload(
                    canonical_payload
                )
                item["structured_adapter_output_from_source_bound_search_unit"] = True
            elif track == "pdf_business_ocr_mm":
                item["structured_source_bound_adapter"] = pdf_source_bound_adapter_payload(
                    canonical_payload
                )
                item["structured_adapter_output_from_source_bound_search_unit"] = True
        citations.append(item)
    return citations


def validate_search_unit_citation_payload(
    payload: Mapping[str, Any] | None,
    *,
    track: str,
    query_id: str = "",
    require_official_compatible: bool,
    original_chunk: Any,
    allowed_manifest_search_unit_ids: set[str] | None = None,
) -> dict[str, Any]:
    row_query_id = clean_any(query_id)
    if not isinstance(payload, Mapping) or not payload:
        return {
            "ok": False,
            "category": SEARCH_UNIT_CITATION_PAYLOAD_MISSING,
            "validation_category": SEARCH_UNIT_CITATION_PAYLOAD_MISSING,
            "missing_fields": [],
            "query_track": clean_any(track),
            "manifest_track": "",
            "row_query_id": row_query_id,
            "manifest_query_id": "",
            "manifest_source_family": "",
            "locator_schema": "",
            "off_track": False,
            "detail": "canonical SearchUnit citation payload is missing",
        }
    if not require_official_compatible:
        return {
            "ok": True,
            "category": None,
            "validation_category": None,
            "missing_fields": [],
            "query_track": clean_any(track),
            "manifest_track": citation_manifest_track(payload, original_chunk),
            "row_query_id": row_query_id,
            "manifest_query_id": citation_manifest_query_id(payload, original_chunk),
            "manifest_source_family": citation_manifest_source_family(payload, original_chunk),
            "locator_schema": citation_locator_schema(payload, original_chunk),
            "off_track": False,
            "detail": "",
        }

    query_track = clean_any(track)
    manifest_track = citation_manifest_track(payload, original_chunk)
    manifest_query_id = citation_manifest_query_id(payload, original_chunk)
    manifest_source_family = citation_manifest_source_family(payload, original_chunk)
    locator_schema = citation_locator_schema(payload, original_chunk)
    if query_track and manifest_track and query_track != manifest_track:
        return {
            "ok": False,
            "category": OFF_TRACK_CITATION_FOR_QUERY_TRACK,
            "validation_category": OFF_TRACK_CITATION_FOR_QUERY_TRACK,
            "missing_fields": [],
            "query_track": query_track,
            "manifest_track": manifest_track,
            "row_query_id": row_query_id,
            "manifest_query_id": manifest_query_id,
            "manifest_source_family": manifest_source_family,
            "locator_schema": locator_schema,
            "off_track": True,
            "detail": "citation manifest track does not match the query track and is excluded from scoring",
        }
    if not clean_any(getattr(original_chunk, "search_unit_id", None)):
        category = (
            STRUCTURED_LOCATOR_DROPPED
            if track in STRUCTURED_TRACKS
            else SEARCH_UNIT_SOURCE_IDENTITY_MISSING
        )
        return {
            "ok": False,
            "category": category,
            "validation_category": SAME_TRACK_LOCATOR_INCOMPLETE,
            "missing_fields": ["search_unit_id"],
            "query_track": query_track,
            "manifest_track": manifest_track,
            "row_query_id": row_query_id,
            "manifest_query_id": manifest_query_id,
            "manifest_source_family": manifest_source_family,
            "locator_schema": locator_schema,
            "off_track": False,
            "detail": "retrieved evidence has only a weak chunk locator, not a source-bound SearchUnit id",
        }
    search_unit_id = clean_any(getattr(original_chunk, "search_unit_id", None))
    if (
        allowed_manifest_search_unit_ids is not None
        and search_unit_id not in allowed_manifest_search_unit_ids
    ):
        return {
            "ok": False,
            "category": SEARCH_UNIT_MANIFEST_MISMATCH,
            "validation_category": SEARCH_UNIT_MANIFEST_MISMATCH,
            "missing_fields": [],
            "query_track": query_track,
            "manifest_track": manifest_track,
            "row_query_id": row_query_id,
            "manifest_query_id": manifest_query_id,
            "manifest_source_family": manifest_source_family,
            "locator_schema": locator_schema,
            "off_track": False,
            "detail": "retrieved SearchUnit is not present in the source-bound official manifest",
        }
    source_identity = (
        clean_any(getattr(original_chunk, "source_file_id", None))
        or clean_any(payload.get("sourceFileId"))
        or clean_any(payload.get("source_file_id"))
        or clean_any(payload.get("document_version_id"))
        or clean_any(payload.get("documentVersionId"))
    )
    if not source_identity:
        return {
            "ok": False,
            "category": SEARCH_UNIT_SOURCE_IDENTITY_MISSING,
            "validation_category": SAME_TRACK_LOCATOR_INCOMPLETE,
            "missing_fields": ["source_file_id_or_document_version_id"],
            "query_track": query_track,
            "manifest_track": manifest_track,
            "row_query_id": row_query_id,
            "manifest_query_id": manifest_query_id,
            "manifest_source_family": manifest_source_family,
            "locator_schema": locator_schema,
            "off_track": False,
            "detail": "SearchUnit citation payload is missing source identity",
        }

    missing_fields = [
        field
        for field in REQUIRED_CITATION_FIELDS_BY_TRACK.get(track, ())
        if not has_required_citation_value(payload.get(field), field=field)
    ]
    if missing_fields:
        category = (
            STRUCTURED_LOCATOR_DROPPED
            if track in STRUCTURED_TRACKS
            else SEARCH_UNIT_LOCATOR_INCOMPLETE
        )
        return {
            "ok": False,
            "category": category,
            "validation_category": SAME_TRACK_LOCATOR_INCOMPLETE,
            "missing_fields": missing_fields,
            "query_track": query_track,
            "manifest_track": manifest_track,
            "row_query_id": row_query_id,
            "manifest_query_id": manifest_query_id,
            "manifest_source_family": manifest_source_family,
            "locator_schema": locator_schema,
            "off_track": False,
            "detail": "SearchUnit citation payload is missing official-compatible locator fields",
        }
    return {
        "ok": True,
        "category": None,
        "validation_category": None,
        "missing_fields": [],
        "query_track": query_track,
        "manifest_track": manifest_track,
        "row_query_id": row_query_id,
        "manifest_query_id": manifest_query_id,
        "manifest_source_family": manifest_source_family,
        "locator_schema": locator_schema,
        "off_track": False,
        "detail": "",
    }


def citation_manifest_track(payload: Mapping[str, Any], original_chunk: Any) -> str:
    track = clean_any(
        payload.get("track")
        or payload.get("manifest_track")
        or as_mapping(getattr(original_chunk, "metadata_json", None)).get("track")
    )
    if track:
        return track
    chunk_section = clean_any(getattr(original_chunk, "section", ""))
    return chunk_section if chunk_section in REQUIRED_CITATION_FIELDS_BY_TRACK else ""


def citation_manifest_query_id(payload: Mapping[str, Any], original_chunk: Any) -> str:
    return clean_any(
        payload.get("manifest_query_id")
        or payload.get("manifestQueryId")
        or as_mapping(getattr(original_chunk, "metadata_json", None)).get("manifest_query_id")
    )


def citation_manifest_source_family(payload: Mapping[str, Any], original_chunk: Any) -> str:
    source_family = clean_any(
        payload.get("source_family")
        or payload.get("sourceFamily")
        or as_mapping(getattr(original_chunk, "metadata_json", None)).get("source_family")
    )
    return source_family or source_family_for_track(citation_manifest_track(payload, original_chunk))


def citation_locator_schema(payload: Mapping[str, Any], original_chunk: Any) -> str:
    locator_schema = clean_any(
        payload.get("locator_schema")
        or payload.get("locatorSchema")
        or as_mapping(getattr(original_chunk, "metadata_json", None)).get("locator_schema")
    )
    return locator_schema or locator_schema_for_track(citation_manifest_track(payload, original_chunk))


def xlsx_source_bound_adapter_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    require_source_bound_adapter_payload(payload)
    return {
        "adapter": "xlsx_source_bound_deterministic_v1",
        "output_from_source_bound_search_unit": True,
        "workbook": clean_any(payload.get("workbook")),
        "sheet": clean_any(payload.get("sheet") or payload.get("sheetName") or payload.get("sheet_name")),
        "range": clean_any(payload.get("range") or payload.get("cellRange") or payload.get("cell_range")),
        "cell": clean_any(payload.get("cell")),
        "row_label": clean_any(payload.get("row_label") or payload.get("rowLabel")),
        "target_column": clean_any(payload.get("target_column") or payload.get("targetColumn")),
        "normalized_value": clean_any(payload.get("normalized_value") or payload.get("normalizedValue")),
        "search_unit_id": clean_any(payload.get("search_unit_id") or payload.get("searchUnitId")),
        "document_version_id": clean_any(payload.get("document_version_id") or payload.get("documentVersionId")),
    }


def pdf_source_bound_adapter_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    require_source_bound_adapter_payload(payload)
    return {
        "adapter": "pdf_source_bound_deterministic_v1",
        "output_from_source_bound_search_unit": True,
        "source_pdf_path": clean_any(first_present(payload, "source_pdf_path", "sourcePdfPath")),
        "page": first_present(payload, "page"),
        "physical_page_index": first_present(payload, "physical_page_index", "physicalPageIndex"),
        "bbox": list(payload.get("bbox") or []),
        "region_type": clean_any(first_present(payload, "region_type", "regionType")),
        "row_label": clean_any(first_present(payload, "row_label", "rowLabel")),
        "target_column": clean_any(first_present(payload, "target_column", "targetColumn")),
        "search_unit_id": clean_any(first_present(payload, "search_unit_id", "searchUnitId")),
        "document_version_id": clean_any(first_present(payload, "document_version_id", "documentVersionId")),
    }


def first_present(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def require_source_bound_adapter_payload(payload: Mapping[str, Any]) -> None:
    candidate_keys = {
        "candidate_result_jsonl",
        "candidate_path",
        "candidate_artifact_path",
        "candidate_results_path",
    }
    if payload.get("source_bound_official_denominator") is not True:
        raise ValueError("adapter input must be a retrieved source-bound SearchUnit payload")
    if any(clean_any(payload.get(key)) for key in candidate_keys):
        raise ValueError("adapter input must be a retrieved source-bound SearchUnit payload")
    if payload.get("candidate_artifact_generation_source") is True:
        raise ValueError("adapter input must be a retrieved source-bound SearchUnit payload")


def has_required_citation_value(value: Any, *, field: str) -> bool:
    if field == "bbox":
        return isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 4
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return bool(value)
    return value is not None


def same_track_generated_citations(citations: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [item for item in citations if not citation_validation(item).get("off_track")]


def citation_validation(citation: Mapping[str, Any]) -> Mapping[str, Any]:
    validation = citation.get("citation_payload_validation")
    return validation if isinstance(validation, Mapping) else {}


def is_invalid_same_track_citation(citation: Mapping[str, Any]) -> bool:
    validation = citation_validation(citation)
    return validation.get("ok") is not True and validation.get("off_track") is not True


def citation_source_bound(citation: Mapping[str, Any]) -> bool:
    payload = citation.get("search_unit_citation_payload")
    return isinstance(payload, Mapping) and payload.get("source_bound_official_denominator") is True


def citations_source_bound(citations: Sequence[Mapping[str, Any]]) -> bool:
    return bool(citations) and all(citation_source_bound(item) for item in citations)


def adapter_output_for_same_track_citations(citations: Sequence[Mapping[str, Any]]) -> bool:
    adapter_citations = [
        item
        for item in citations
        if item.get("structured_source_bound_adapter_enabled") is True
    ]
    if not adapter_citations:
        return False
    return all(
        bool(item.get("structured_adapter_output_from_source_bound_search_unit"))
        for item in adapter_citations
    )


def query_bound_citation_count(citations: Sequence[Mapping[str, Any]], row_query_id: str) -> int:
    if not row_query_id:
        return 0
    return sum(
        1
        for item in citations
        if clean_any(citation_validation(item).get("manifest_query_id")) == row_query_id
    )


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def clean_any(value: Any) -> str:
    return str(value or "").strip()
