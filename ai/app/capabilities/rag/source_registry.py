"""Source-first evidence contracts for RAG retrieval candidates.

Search indexes return SearchViews. Evidence and citations must hydrate through
SourceAtoms so vector metadata cannot become the owner of locator truth.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


SOURCE_REGISTRY_CONTRACT_VERSION = "source-registry-v1"
EVIDENCE_BUNDLE_SCHEMA_VERSION = "source-registry-evidence-bundle-v1"
SUPPORTED_SOURCE_FAMILIES = {"TEXT", "PDF", "XLSX"}


def validate_source_atom(atom: Mapping[str, Any]) -> dict[str, Any]:
    family = _clean(atom.get("source_family")).upper()
    payload = _mapping(atom.get("canonical_citation_payload"))
    missing: list[str] = []
    for field in (
        "source_atom_id",
        "source_family",
        "source_identity",
        "content_hash",
        "extraction_version",
        "raw_locator",
        "normalized_text_or_value_snapshot",
        "parent_pointers",
        "canonical_citation_payload",
    ):
        if atom.get(field) in (None, "", {}, []):
            missing.append(field)
    if not (atom.get("document_id") or atom.get("workbook_id")):
        missing.append("document_id_or_workbook_id")
    if not (atom.get("document_version_id") or atom.get("workbook_version_id")):
        missing.append("document_version_id_or_workbook_version_id")
    if family not in SUPPORTED_SOURCE_FAMILIES:
        missing.append("source_family")
    if payload and not render_citation_payload(payload).get("valid"):
        missing.append("canonical_citation_payload_renderable")
    return {
        "valid": not missing,
        "source_atom_id": _clean(atom.get("source_atom_id")),
        "source_family": family,
        "missing_fields": sorted(set(missing)),
        "source_registry_version": _clean(atom.get("source_registry_version")) or SOURCE_REGISTRY_CONTRACT_VERSION,
    }


def validate_search_view(search_view: Mapping[str, Any]) -> dict[str, Any]:
    source_atom_ids = _source_atom_ids(search_view)
    missing: list[str] = []
    if not _clean(search_view.get("search_view_id") or search_view.get("searchViewId")):
        missing.append("search_view_id")
    if not source_atom_ids:
        missing.append("source_atom_ids")
    return {
        "valid": not missing,
        "search_view_id": _clean(search_view.get("search_view_id") or search_view.get("searchViewId")),
        "source_atom_ids": source_atom_ids,
        "missing_fields": sorted(set(missing)),
    }


def hydrate_canonical_citation_payload(
    source_atom_id: str,
    *,
    source_registry: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    atom = _mapping(source_registry.get(source_atom_id))
    if not atom:
        return {
            "valid": False,
            "source_atom_id": source_atom_id,
            "failure_bucket": "SOURCE_REGISTRY_MISSING_BLOCKER",
            "missing_fields": ["source_atom_id"],
        }
    validation = validate_source_atom(atom)
    if not validation["valid"]:
        return {
            "valid": False,
            "source_atom_id": source_atom_id,
            "failure_bucket": "SOURCE_ATOM_SCHEMA_INCOMPLETE",
            "missing_fields": validation["missing_fields"],
        }
    return {
        "valid": True,
        "source_atom_id": source_atom_id,
        "payload": dict(_mapping(atom.get("canonical_citation_payload"))),
        "canonical_payload_source": "source_registry",
        "source_registry_version": validation["source_registry_version"],
    }


def render_citation(
    source_atom_id: str,
    *,
    source_registry: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    payload_result = hydrate_canonical_citation_payload(source_atom_id, source_registry=source_registry)
    if not payload_result["valid"]:
        return payload_result
    rendered = render_citation_payload(_mapping(payload_result.get("payload")))
    rendered["source_atom_id"] = source_atom_id
    rendered["canonical_payload_source"] = "source_registry"
    rendered["source_registry_version"] = payload_result["source_registry_version"]
    if not rendered["valid"]:
        rendered["failure_bucket"] = "EVIDENCE_BUNDLE_CONTRACT_INCOMPLETE"
    return rendered


def render_citation_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    family = _clean(payload.get("source_family") or payload.get("sourceFamily")).upper()
    track_locator = _mapping(payload.get("track_locator_payload") or payload.get("trackLocatorPayload"))
    citation: dict[str, Any] = {
        "source_family": family,
        "source_identity": _clean(payload.get("source_identity") or payload.get("sourceIdentity")),
        "locator_fingerprint": _clean(payload.get("locator_fingerprint") or payload.get("locatorFingerprint")),
        "search_unit_id": _clean(payload.get("search_unit_id") or payload.get("searchUnitId")),
    }
    if family == "TEXT":
        text_locator = _mapping(payload.get("text_locator") or payload.get("textLocator"))
        if not text_locator:
            text_locator = _mapping(track_locator.get("text_locator") or track_locator.get("textLocator")) or track_locator
        citation["text_locator"] = {
            "document_id": _clean(payload.get("document_id") or payload.get("documentId") or track_locator.get("document_id")),
            "chunk_id": _clean(text_locator.get("chunk_id") or text_locator.get("chunkId") or track_locator.get("chunk_id")),
            "source_corpus_path": _clean(text_locator.get("source_corpus_path") or track_locator.get("source_corpus_path")),
            "section_path": text_locator.get("section_path") or track_locator.get("section_path") or [],
            "text_span": _clean(text_locator.get("text_span") or text_locator.get("textSpan") or track_locator.get("text_span")),
        }
        valid = bool(
            citation["source_identity"]
            and citation["locator_fingerprint"]
            and citation["search_unit_id"]
            and citation["text_locator"]["document_id"]
            and citation["text_locator"]["chunk_id"]
        )
    elif family == "PDF":
        citation["pdf_locator"] = {
            "source_pdf_path": _clean(payload.get("source_pdf_path") or payload.get("sourcePdfPath") or track_locator.get("source_pdf_path")),
            "document_version_id": _clean(
                payload.get("document_version_id")
                or payload.get("documentVersionId")
                or track_locator.get("document_version_id")
            ),
            "page": payload.get("page") if payload.get("page") is not None else track_locator.get("page"),
            "physical_page_index": (
                payload.get("physical_page_index")
                if payload.get("physical_page_index") is not None
                else track_locator.get("physical_page_index")
            ),
            "bbox": payload.get("bbox") or track_locator.get("bbox"),
            "region_type": _clean(payload.get("region_type") or payload.get("regionType") or track_locator.get("region_type")),
        }
        valid = bool(
            citation["source_identity"]
            and citation["locator_fingerprint"]
            and citation["search_unit_id"]
            and citation["pdf_locator"]["source_pdf_path"]
            and citation["pdf_locator"]["document_version_id"]
            and citation["pdf_locator"]["page"] is not None
            and citation["pdf_locator"]["physical_page_index"] is not None
            and citation["pdf_locator"]["bbox"]
            and citation["pdf_locator"]["region_type"]
        )
    elif family == "XLSX":
        citation["xlsx_locator"] = {
            "workbook": _clean(payload.get("workbook") or payload.get("source_workbook") or track_locator.get("workbook")),
            "sheet": _clean(payload.get("sheet") or payload.get("sheetName") or track_locator.get("sheet")),
            "range": _clean(payload.get("range") or payload.get("cell_range") or track_locator.get("range")),
            "cell": _clean(payload.get("cell") or track_locator.get("cell")),
            "row_label": _clean(payload.get("row_label") or payload.get("rowLabel") or track_locator.get("row_label")),
            "target_column": _clean(payload.get("target_column") or payload.get("targetColumn") or track_locator.get("target_column")),
            "normalized_value": _clean(payload.get("normalized_value") or payload.get("normalizedValue") or track_locator.get("normalized_value")),
        }
        valid = bool(
            citation["source_identity"]
            and citation["locator_fingerprint"]
            and citation["search_unit_id"]
            and citation["xlsx_locator"]["workbook"]
            and citation["xlsx_locator"]["sheet"]
            and (citation["xlsx_locator"]["range"] or citation["xlsx_locator"]["cell"])
        )
    else:
        valid = False
    return {"valid": valid, "citation": citation}


def assemble_evidence_bundle(
    source_atom_id: str,
    *,
    source_registry: Mapping[str, Mapping[str, Any]],
    mode: str,
    search_view_id: str | None = None,
) -> dict[str, Any]:
    atom = _mapping(source_registry.get(source_atom_id))
    rendered = render_citation(source_atom_id, source_registry=source_registry)
    if not rendered.get("valid"):
        return rendered
    family = _clean(atom.get("source_family")).upper()
    raw_locator = dict(_mapping(atom.get("raw_locator")))
    matched = _clean(atom.get("normalized_text_or_value_snapshot"))
    raw_file_exists = bool(atom.get("raw_file_exists"))
    extraction_snapshot_present = (
        bool(atom.get("extraction_snapshot_present"))
        if "extraction_snapshot_present" in atom
        else bool(matched)
    )
    policy = hydration_policy(
        raw_file_exists=raw_file_exists,
        extraction_snapshot_present=extraction_snapshot_present,
    )
    registry_version = _clean(atom.get("source_registry_version")) or SOURCE_REGISTRY_CONTRACT_VERSION
    resolved_search_view_id = _clean(search_view_id) or _first_search_view_id(atom)
    bundle: dict[str, Any] = {
        "schema_version": EVIDENCE_BUNDLE_SCHEMA_VERSION,
        "source_registry_version": registry_version,
        "source_atom_id": source_atom_id,
        "search_view_id": resolved_search_view_id,
        "source_family": family,
        "anchor_locator": raw_locator,
        "matched_text_or_value": matched,
        "nearby_context": matched[:500],
        "locator_completeness": "complete",
        "support_strength": "traceable_locator_not_answer_correctness",
        "official_evidence_allowed": mode == "official_evidence" and bool(policy["official_evidence_allowed"]),
        "runtime_evidence_allowed": bool(policy["runtime_answer_allowed"]),
        "runtime_answer_allowed": bool(policy["runtime_answer_allowed"]),
        "diagnostic_only_reason": "" if policy["official_evidence_allowed"] else policy["diagnostic_only_reason"],
        "citation": dict(_mapping(rendered.get("citation"))),
        "canonical_payload_source": "source_registry",
    }
    if family == "TEXT":
        bundle["text_evidence"] = {
            "source_document_id_or_path": _clean(atom.get("document_id") or raw_locator.get("source_path")),
            "section_chunk_span_identity": _clean(raw_locator.get("chunk_id") or raw_locator.get("text_span")),
            "text_span": _clean(raw_locator.get("text_span")),
            "parent_paragraph_or_section": raw_locator.get("section_path") or [],
            "nearby_context": matched[:500],
        }
    elif family == "PDF":
        bundle["pdf_evidence"] = {
            "source_pdf_path": _clean(raw_locator.get("source_pdf_path")),
            "document_version_id": _clean(atom.get("document_version_id")),
            "page": raw_locator.get("page"),
            "physical_page_index": raw_locator.get("physical_page_index"),
            "bbox": raw_locator.get("bbox"),
            "region_type": _clean(raw_locator.get("region_type")),
            "matched_text": matched,
            "nearby_paragraph_or_window": matched[:500],
            "section_heading": _clean(raw_locator.get("section_heading")),
            "ocr_confidence": raw_locator.get("ocr_confidence"),
        }
    elif family == "XLSX":
        xlsx_display_metadata = _xlsx_display_metadata(atom)
        bundle["xlsx_evidence"] = {
            "workbook_or_source_path": _clean(raw_locator.get("workbook") or raw_locator.get("source_path")),
            "sheet": _clean(raw_locator.get("sheet")),
            "table_or_range": _clean(raw_locator.get("range")),
            "matched_cells": [_clean(raw_locator.get("cell"))] if raw_locator.get("cell") else [],
            "row_or_column_labels": {
                "row_label": _clean(raw_locator.get("row_label")),
                "column_label": _clean(raw_locator.get("column_label") or raw_locator.get("target_column")),
            },
            "nearby_row_or_range_context": matched[:500],
            "value_locator": _clean(raw_locator.get("value_locator") or raw_locator.get("cell")),
        }
        if xlsx_display_metadata:
            bundle["xlsx_evidence"]["xlsx_display_metadata"] = xlsx_display_metadata
    return {"valid": True, "source_atom_id": source_atom_id, "evidence_bundle": bundle}


def hydration_policy(*, raw_file_exists: bool, extraction_snapshot_present: bool) -> dict[str, Any]:
    if raw_file_exists and extraction_snapshot_present:
        return {
            "hydration_allowed": True,
            "official_evidence_allowed": True,
            "runtime_answer_allowed": True,
            "diagnostic_only_reason": "",
            "fail_closed": False,
            "failure_bucket": "",
        }
    if extraction_snapshot_present:
        return {
            "hydration_allowed": True,
            "official_evidence_allowed": False,
            "runtime_answer_allowed": True,
            "diagnostic_only_reason": "raw_file_missing_extraction_snapshot_present",
            "fail_closed": False,
            "failure_bucket": "RAW_FILE_MISSING_EXTRACTION_SNAPSHOT_PRESENT",
        }
    return {
        "hydration_allowed": False,
        "official_evidence_allowed": False,
        "runtime_answer_allowed": False,
        "diagnostic_only_reason": "raw_and_extraction_snapshot_missing",
        "fail_closed": True,
        "failure_bucket": "SOURCE_REGISTRY_MISSING_BLOCKER",
    }


def evidence_bundle_from_search_view(
    search_view: Mapping[str, Any],
    *,
    source_registry: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    source_atom_ids = _source_atom_ids(search_view)
    search_view_id = _clean(search_view.get("search_view_id") or search_view.get("searchViewId"))
    if not source_atom_ids:
        bucket = (
            "RETRIEVAL_RESULT_CHUNK_ONLY_NOT_SEARCHUNIT"
            if search_view.get("chunk_id") or search_view.get("chunkId")
            else "SEARCH_VIEW_SOURCE_ATOM_POINTER_MISSING"
        )
        return {
            "valid": False,
            "failure_bucket": bucket,
            "vector_payload_used_as_evidence_truth": False,
            "ignored_vector_canonical_payload": bool(
                search_view.get("canonical_citation_payload") or search_view.get("canonicalCitationPayload")
            ),
        }
    for source_atom_id in source_atom_ids:
        if source_atom_id in source_registry:
            result = assemble_evidence_bundle(
                source_atom_id,
                source_registry=source_registry,
                mode="runtime_evidence",
                search_view_id=search_view_id,
            )
            result["vector_payload_used_as_evidence_truth"] = False
            result["source_atom_hydrated_from_registry"] = True
            result["ignored_vector_canonical_payload"] = bool(
                search_view.get("canonical_citation_payload") or search_view.get("canonicalCitationPayload")
            )
            return result
    return {
        "valid": False,
        "failure_bucket": "VECTOR_HIT_SOURCE_ATOM_MISSING",
        "vector_payload_used_as_evidence_truth": False,
        "ignored_vector_canonical_payload": bool(
            search_view.get("canonical_citation_payload") or search_view.get("canonicalCitationPayload")
        ),
    }


def _source_atom_ids(search_view: Mapping[str, Any]) -> list[str]:
    value = (
        search_view.get("source_atom_ids")
        or search_view.get("sourceAtomIds")
        or search_view.get("source_atom_id")
        or search_view.get("sourceAtomId")
    )
    if isinstance(value, str):
        return [_clean(value)] if _clean(value) else []
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [_clean(item) for item in value if _clean(item)]
    return []


def _first_search_view_id(atom: Mapping[str, Any]) -> str:
    parent_pointers = _mapping(atom.get("parent_pointers"))
    value = parent_pointers.get("search_view_ids") or parent_pointers.get("searchViewIds")
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            if _clean(item):
                return _clean(item)
    return ""


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _xlsx_display_metadata(atom: Mapping[str, Any]) -> dict[str, Any]:
    contract = _mapping(atom.get("xlsx_display_contract") or atom.get("xlsx_display_metadata"))
    if not contract:
        return {}
    return {
        "display_value": _clean(contract.get("display_value")),
        "raw_value": _clean(contract.get("raw_value")),
        "normalized_value": _clean(contract.get("normalized_value")),
        "number_format": _clean(contract.get("number_format")),
        "value_type": _clean(contract.get("value_type")),
        "formula_cached_value_present": bool(_clean(contract.get("formula_cached_value"))),
        "formula_text_visible_to_user": False,
        "formula_evaluation_at_query_time": False,
        "format_confidence": _clean(contract.get("format_confidence")),
        "format_provenance": _clean(contract.get("format_provenance")),
        "format_drop_reason": _clean(contract.get("format_drop_reason")),
        "merged_cell": bool(contract.get("merged_cell")),
        "merged_range": _clean(contract.get("merged_range")),
        "merged_owner_cell": _clean(contract.get("merged_owner_cell")),
    }
